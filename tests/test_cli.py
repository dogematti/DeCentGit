import pytest
import subprocess
import os
import time
import requests
import json

# Define the path to the decentgit CLI script
CLI_SCRIPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'cli', 'decentgit')
CLI_EXECUTABLE = ["python3", CLI_SCRIPT_PATH]

# Define the node URL for the Dockerized blockchain service
NODE_URL = "http://localhost:5001" # Use localhost as docker-compose exposes port 5001

@pytest.fixture(scope="module", autouse=True)
def docker_compose_up():
    """Brings up Docker Compose services before tests and tears them down afterwards."""
    print("\nBringing up Docker Compose services...")
    # Using the project root as cwd for docker-compose commands
    subprocess.run(["docker-compose", "up", "-d", "--build"], check=True, cwd=os.path.dirname(os.path.abspath(__file__)) + "/..")
    
    # Wait for the blockchain service to be ready
    print("Waiting for blockchain service to be ready...")
    for _ in range(30): # Wait up to 30 seconds
        try:
            # Use NODE_URL for checking readiness, which is exposed on host:5001
            response = requests.get(f"{NODE_URL}/chain")
            if response.status_code == 200:
                print("Blockchain service is ready.")
                break
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(1)
    else:
        pytest.fail("Blockchain service did not start in time.")
    
    yield
    
    print("Tearing down Docker Compose services...")
    # Using the project root as cwd for docker-compose commands
    subprocess.run(["docker-compose", "down", "-v"], check=True, cwd=os.path.dirname(os.path.abspath(__file__)) + "/..")

@pytest.fixture
def clean_repo(tmp_path):
    """
    Creates a temporary directory for a git repository, initializes it,
    and cleans up .decentgit config after each test.
    """
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    
    # Initialize a git repository
    subprocess.run(["git", "init", "--initial-branch=main"], check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], check=True)
    
    # Create an initial commit
    (tmp_path / "README.md").write_text("Hello World")
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], check=True)
    
    # Ensure any previous .decentgit state is removed
    decentgit_dir = tmp_path / ".decentgit"
    if decentgit_dir.exists():
        import shutil
        shutil.rmtree(decentgit_dir)

    yield tmp_path
    
    # Clean up .decentgit directory if it exists
    if decentgit_dir.exists():
        import shutil
        shutil.rmtree(decentgit_dir)
        
    os.chdir(original_cwd)


def run_cli_command(*command, expected_exit_code=0):
    """Helper to run decentgit CLI commands directly."""
    result = subprocess.run(CLI_EXECUTABLE + list(command), capture_output=True, text=True, cwd=os.getcwd())
    if result.returncode != expected_exit_code:
        print(f"Command failed: {' '.join(command)}")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        pytest.fail(f"Expected exit code {expected_exit_code}, got {result.returncode}")
    return result

def run_cli_command_in_docker(*command, expected_exit_code=0):
    """Helper to run decentgit CLI commands inside a docker container."""
    # The cwd for docker-compose command is the project root
    project_root = os.path.dirname(os.path.abspath(__file__)) + "/.."
    
    # Pass the current working directory (which is the temporary test repo)
    # as the workdir for the cli service inside the container.
    docker_command = ["docker-compose", "run", "--rm", "--workdir", "/app/local_repo", "cli"] + list(command)
    result = subprocess.run(docker_command, capture_output=True, text=True, cwd=project_root)
    if result.returncode != expected_exit_code:
        print(f"Docker Command failed: {' '.join(docker_command)}")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        pytest.fail(f"Expected exit code {expected_exit_code}, got {result.returncode}")
    return result


def test_cli_init_command(clean_repo):
    """Test the 'decentgit init' command."""
    result = run_cli_command("init", "--node", NODE_URL)
    assert "DeCentGit initialized." in result.stdout
    assert os.path.exists(".decentgit/config")
    assert os.path.exists(".decentgit/id_ecdsa")
    assert os.path.exists(".decentgit/id_ecdsa.pub")

    # Verify config content
    with open(".decentgit/config", "r") as f:
        config = json.load(f)
        assert "repo_id" in config
        assert config["node"] == NODE_URL
        assert "signer_identity" in config

    # Test force re-initialization
    result = run_cli_command("init", "--force", "--node", NODE_URL)
    assert "Reinitializing existing DeCentGit repository" in result.stdout
    assert "DeCentGit initialized." in result.stdout

    # Test init without --node (should use _get_node_url logic)
    # Temporarily remove .decentgit to re-init
    import shutil
    shutil.rmtree(".decentgit")
    
    # Set the DECENTGIT_NODE_URL env var for this specific run
    os.environ['DECENTGIT_NODE_URL'] = NODE_URL
    result = run_cli_command("init")
    del os.environ['DECENTGIT_NODE_URL'] # Clean up env var
    assert "DeCentGit initialized." in result.stdout
    with open(".decentgit/config", "r") as f:
        config = json.load(f)
        assert config["node"] == NODE_URL


def test_cli_push_command(clean_repo):
    """Test the 'decentgit push' command."""
    run_cli_command("init", "--node", NODE_URL)
    result = run_cli_command("push", "main")
    assert "Attestation submitted" in result.stdout
    assert "Block mined successfully!" in result.stdout
    assert "Added git note to commit" in result.stdout

    # Make another commit and push
    (clean_repo / "file2.txt").write_text("Second file")
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", "Second commit"], check=True)
    
    result = run_cli_command("push", "main")
    assert "Attestation submitted" in result.stdout
    assert "Block mined successfully!" in result.stdout

def test_cli_log_command(clean_repo):
    """Test the 'decentgit log' command."""
    run_cli_command("init", "--node", NODE_URL)
    run_cli_command("push", "main")
    
    result = run_cli_command("log", "main")
    assert "Verification successful." in result.stdout
    assert "Current authoritative head for 'main'" in result.stdout
    
    # Test with an invalid ref
    result = run_cli_command("log", "nonexistent-ref", expected_exit_code=0)
    assert "No attestations found for ref" in result.stdout

def test_cli_log_fast_command(clean_repo):
    """Test the 'decentgit log --fast' command."""
    # Initialize repo and push using the Docker CLI
    run_cli_command_in_docker("init", "--force", "--node", "http://blockchain:5000")
    run_cli_command_in_docker("push", "main")
    
    # Ensure indexer has time to process (it polls every 15s by default)
    print("Waiting for indexer to catch up...")
    time.sleep(60)
    # Now run the log --fast command inside the Docker container
    result = run_cli_command_in_docker("log", "main", "--fast")
    assert "Indexer's authoritative head for 'main' is" in result.stdout
    assert "Verification successful." not in result.stdout # Should not perform full verification

def test_cli_reputation_command(clean_repo):
    """Test the 'decentgit reputation' command."""
    run_cli_command("init", "--node", NODE_URL)
    run_cli_command("push", "main")

    result = run_cli_command("reputation")
    assert "Calculating reputation for current user identity" in result.stdout
    assert "Total Reputation Score:" in result.stdout
    
    # Make another commit and push to increase reputation
    (clean_repo / "another.txt").write_text("Another change")
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", "Third commit"], check=True)
    run_cli_command("push", "main")
    
    result_after_second_push = run_cli_command("reputation")
    # Reputation should be higher or roughly equal (depending on decay over very short time)
    # This check is basic, more detailed assertion might be needed if decay is faster
    assert float(result_after_second_push.stdout.split("Total Reputation Score: ")[1].strip()) > 0.0
