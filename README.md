# DeCentGit: A Decentralized Git Protocol Prototype

This repository contains a proof-of-concept implementation of the DeCentGit protocol, a decentralized version control system that uses a blockchain for responsibility tracking.

For a detailed log of recent enhancements and fixes, please see `progress_updates.md`.

## Core Concepts

DeCentGit separates the data (your Git objects) from the ordering and responsibility of changes. Git remains the authoritative data plane, while a simple blockchain provides a canonical ledger of signed "PushAttestations". This architecture enables decentralized accountability without the scalability costs of full on-chain version control.

The prototype consists of three main components:
1.  `blockchain`: A simple Flask-based web server that acts as the blockchain node for storing `PushAttestations`.
2.  `indexer`: A service that listens to the blockchain and builds a local, queryable SQLite database of the derived repository states, enabling fast lookups.
3.  `cli`: A command-line interface tool (`decentgit`) for interacting with local git repositories and the DeCentGit protocol.

## Key Features
*   **Event-Sourced State:** Repository state is derived by replaying a chain of `PushAttestations`.
*   **Cryptographic Identity:** Each repository is identified by a unique ECDSA key pair, and all attestations are cryptographically signed.
*   **Time-Decaying Reputation:** The `reputation` command calculates an identity's score based on their history of contributions.
*   **Git Notes Integration:** Successful attestations are linked back to the corresponding git commit using `git notes`.
*   **Untrusted Indexer:** An optional indexer provides fast queries (`--fast`), while the default `log` command performs a full, trustless verification by replaying the entire chain.

## Setup & Usage (Docker)

The recommended way to run DeCentGit is using Docker and Docker Compose, which handles all services and dependencies.

### Prerequisites
*   [Docker](https://docs.docker.com/get-docker/)
*   [Docker Compose](https://docs.docker.com/compose/install/)

### 1. Start the Services
From the project root, run:
```bash
docker-compose up -d --build
```
This command will build the Docker images for the `blockchain`, `indexer`, and `cli` services, and start the `blockchain` and `indexer` in the background. The blockchain will be accessible from your host machine on port `5001`.

### 2. Use the DeCentGit CLI
All `decentgit` commands are run via `docker-compose run` in a Git-initialized directory.

#### a. Initialize a Git Repository (if you don't have one)
```bash
# These commands run on your local machine
git init --initial-branch=main
git config user.name "Your Name"
git config user.email "you@example.com"
git commit --allow-empty -m "Initial commit"
```

#### b. Initialize DeCentGit
This creates a `.decentgit` directory and generates a unique cryptographic keypair to act as your repository's identity. The node URL will be automatically configured for the Docker environment.
```bash
docker-compose run --rm cli init
```

#### c. Attest a Commit
This creates a signed `PushAttestation` on the blockchain for the `main` branch.
```bash
docker-compose run --rm cli push main
```

#### d. Verify History (Trustless Mode)
Use the `log` command to fetch the entire chain, verify every signature, and reconstruct the history of `main`.
```bash
docker-compose run --rm cli log main
```

#### e. Query History (Indexer Mode)
Use the `--fast` flag to get a rapid result from the indexer's local database.
```bash
docker-compose run --rm cli log main --fast
```

#### f. Check Reputation
Calculate the time-decayed reputation score for your repository's identity.
```bash
docker-compose run --rm cli reputation
```

### 3. Stop the Services
When you are finished, you can stop all services and remove the containers and volumes with:
```bash
docker-compose down -v
```

## Running the Test Suite
The project includes a `pytest`-based integration test suite that runs against the containerized services.

### Prerequisites
*   `pytest` and other Python dependencies must be installed in your local environment:
    ```bash
    pip install -r requirements.txt
    ```

### Run Tests
From the project root, execute:
```bash
pytest tests/test_cli.py
```
The test suite will automatically start and stop the Docker environment.
