import requests
import time
import json
import ecdsa
import sqlite3
import os
from db import get_db_connection, setup_database

# Default NODE_URL, used if environment variable is not set
DEFAULT_NODE_URL = "http://127.0.0.1:5000"

# Get NODE_URL from environment variable, with a fallback to the default
NODE_URL = os.environ.get("DECENTGIT_NODE_URL", DEFAULT_NODE_URL)

GENESIS_COMMIT = '0000000000000000000000000000000000000000'

def verify_signature(att):
    """Verifies the signature of an attestation."""
    try:
        vk = ecdsa.VerifyingKey.from_string(bytes.fromhex(att['signer_identity']), curve=ecdsa.NIST256p)
        attestation_data = {k: v for k, v in att.items() if k in ['repo_id', 'ref', 'old_commit', 'new_commit']}
        message = json.dumps(attestation_data, sort_keys=True).encode('utf-8')
        signature = bytes.fromhex(att['signature'])
        vk.verify(signature, message)
        return True
    except (ecdsa.keys.BadSignatureError, KeyError, ValueError):
        return False

def process_chain():
    """Fetches the chain and updates the index."""
    print("Connecting to database...", flush=True)
    conn = get_db_connection()
    c = conn.cursor()
    print("Database connected.", flush=True)

    try:
        # Get the last block we processed
        c.execute("SELECT value FROM meta WHERE key = 'last_processed_block'")
        last_processed_block_row = c.fetchone()
        last_processed_block = last_processed_block_row['value'] if last_processed_block_row else 0
        print(f"Last processed block: {last_processed_block}", flush=True)
        
        # Fetch the full chain from the node
        print(f"Fetching chain from {NODE_URL}/chain", flush=True)
        response = requests.get(f"{NODE_URL}/chain")
        response.raise_for_status()
        chain = response.json()['chain']
        print(f"Chain received. Length: {len(chain)}", flush=True)
        
        new_blocks = [b for b in chain if b['index'] > last_processed_block]
        
        if not new_blocks:
            print("No new blocks to process.", flush=True)
            return

        print(f"Processing {len(new_blocks)} new blocks...", flush=True)

        for block in sorted(new_blocks, key=lambda x: x['index']):
            print(f"Processing block {block['index']}", flush=True)
            for tx in block['transactions']:
                # Ensure it's a valid PushAttestation
                if not all(k in tx for k in ['repo_id', 'ref', 'old_commit', 'new_commit', 'signer_identity', 'signature']):
                    print(f"  Skipping non-attestation transaction in block {block['index']}", flush=True)
                    continue
                
                print(f"  Processing attestation for {tx['repo_id'][:6]}/{tx['ref']}", flush=True)
                # 1. Verify signature
                if not verify_signature(tx):
                    print(f"  [Block {block['index']}] Skipping transaction with invalid signature.", flush=True)
                    continue

                # 2. Verify chain consistency
                c.execute("SELECT commit_hash FROM refs WHERE repo_id = ? AND ref_name = ?", (tx['repo_id'], tx['ref']))
                result = c.fetchone()
                current_commit_in_db = result['commit_hash'] if result else GENESIS_COMMIT
                
                if tx['old_commit'] != current_commit_in_db:
                    print(f"  [Block {block['index']}] Chain inconsistency for {tx['repo_id']}/{tx['ref']}. DB has {current_commit_in_db[:7]}, att has {tx['old_commit'][:7]}. Skipping.", flush=True)
                    continue
                    
                # 3. All good, update the database
                print(f"  Updating {tx['repo_id'][:6]}/{tx['ref']} -> {tx['new_commit'][:7]}", flush=True)
                c.execute("""
                    INSERT OR REPLACE INTO refs (repo_id, ref_name, commit_hash, updated_at)
                    VALUES (?, ?, ?, ?)
                """, (tx['repo_id'], tx['ref'], tx['new_commit'], block['timestamp']))

            # Update the last processed block index
            print(f"  Updating last processed block to {block['index']}", flush=True)
            c.execute("UPDATE meta SET value = ? WHERE key = 'last_processed_block'", (block['index'],))
            conn.commit()
            print(f"  Block {block['index']} processed and committed.", flush=True)

    except requests.exceptions.RequestException as e:
        print(f"Error fetching chain from node: {e}", flush=True)
    except sqlite3.Error as e:
        print(f"Database error: {e}", flush=True)
    finally:
        print("Closing database connection.", flush=True)
        conn.close()

if __name__ == "__main__":
    print("Setting up database...", flush=True)
    setup_database()
    print("Database setup complete.", flush=True)
    print(f"Indexer started. Polling for new blocks from {NODE_URL} every 15 seconds...", flush=True)
    while True:
        process_chain()
        time.sleep(15)
