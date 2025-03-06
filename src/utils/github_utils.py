"""GitHub integration utilities for the readme generator."""

import os
import re
import tempfile
import logging
import urllib.parse
import shutil
import time
import subprocess
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

# Optional imports - try to load them once
_git = None
_github_class = None

def _load_git():
    """Lazily load the git module when needed."""
    global _git
    if _git is None:
        try:
            import git
            _git = git
        except ImportError:
            raise ImportError("GitPython not installed. Install with: pip install gitpython")
    return _git

def _load_github(token=None):
    """Lazily load the PyGithub module when needed.
    
    Args:
        token: GitHub token for authentication
        
    Returns:
        Github class if no token provided, or authenticated Github instance if token provided
    """
    global _github_class
    if _github_class is None:
        try:
            from github import Github
            _github_class = Github
        except ImportError:
            raise ImportError("PyGithub not installed. Install with: pip install PyGithub")
    
    # Return the class if no token, or an instance if token provided
    if token is None:
        return _github_class
    else:
        return _github_class(token)

def is_valid_github_url(url: str) -> bool:
    """Validate if a URL is a valid GitHub repository URL.
    
    Args:
        url: GitHub repository URL
        
    Returns:
        bool: True if valid, False otherwise
    """
    # Basic pattern for GitHub repository URLs
    pattern = r'^https?://github\.com/[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+(/)?$'
    return re.match(pattern, url) is not None

async def clone_github_repository(url: str, github_token: Optional[str] = None) -> Path:
    """Clone a GitHub repository to a temporary directory and return the path.
    
    Args:
        url: GitHub repository URL
        github_token: Optional GitHub Personal Access Token for authentication
        
    Returns:
        Path to the cloned repository
    
    Raises:
        Exception: If cloning fails
    """
    # Try creating temp directory in user home first, then fallback to system temp
    try:
        # Create directory in user's home directory
        home_dir = Path.home()
        temp_base = home_dir / "readme_gen_temp"
        os.makedirs(temp_base, exist_ok=True)
        
        # Create a unique subdirectory
        timestamp = int(time.time())
        repo_name = url.split('/')[-1].replace('.git', '')
        temp_dir = temp_base / f"{repo_name}_{timestamp}"
        os.makedirs(temp_dir, exist_ok=True)
        
        logging.info(f"Created user home temporary directory: {temp_dir}")
    except Exception as e:
        logging.warning(f"Could not create directory in user home, falling back to system temp: {e}")
        # Fallback to system temp directory
        temp_dir = Path(tempfile.mkdtemp(prefix='readme_gen_'))
    
    try:
        # Set full permissions
        os.chmod(temp_dir, 0o777)
        logging.info(f"Created temporary directory: {temp_dir}")
        
        # Modify URL to include token if provided
        clone_url = url
        if github_token:
            parsed_url = urllib.parse.urlparse(url)
            auth_url = f"https://{github_token}@{parsed_url.netloc}{parsed_url.path}"
            if not auth_url.endswith('.git'):
                auth_url += '.git'
            clone_url = auth_url
        
        # Try using direct subprocess call instead of GitPython
        logging.info(f"Cloning repository using subprocess: {url}")
        
        try:
            # First try with subprocess
            result = subprocess.run(
                ["git", "clone", clone_url, str(temp_dir)],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                logging.warning(f"Subprocess git clone failed: {result.stderr}")
                # Fall back to GitPython
                git = _load_git()
                logging.info("Falling back to GitPython")
                git.Repo.clone_from(clone_url, str(temp_dir))
        except Exception as e:
            logging.warning(f"Subprocess approach failed: {str(e)}, trying GitPython")
            git = _load_git()
            git.Repo.clone_from(clone_url, str(temp_dir))
            
        logging.info(f"Repository cloned successfully to {temp_dir}")
        return temp_dir
        
    except Exception as e:
        logging.error(f"Error cloning repository: {str(e)}")
        cleanup_temp_dir(temp_dir)
        raise Exception(f"Error cloning repository: {str(e)}")

def cleanup_temp_dir(temp_dir: Path) -> None:
    """Clean up a temporary directory, handling Git repositories properly."""
    if not temp_dir or not os.path.exists(temp_dir):
        return
        
    try:
        # Wait a moment for any processes to release locks
        time.sleep(2)
        
        # On Windows, make files writable before removal
        if os.name == 'nt':
            for root, dirs, files in os.walk(temp_dir):
                for dir_name in dirs:
                    try:
                        dir_path = os.path.join(root, dir_name)
                        os.chmod(dir_path, 0o777)
                    except:
                        pass
                for file_name in files:
                    try:
                        file_path = os.path.join(root, file_name)
                        os.chmod(file_path, 0o777)
                    except:
                        pass
        
        # Try to remove with standard approach first
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            logging.warning(f"Standard cleanup failed, trying alternative approach: {e}")
            
            # Try with subprocess on Windows
            if os.name == 'nt':
                try:
                    subprocess.run(['cmd', '/c', f'rd /s /q "{temp_dir}"'], check=False)
                except Exception as e2:
                    logging.warning(f"CMD cleanup failed: {e2}")
            else:
                # For non-Windows, try with force
                try:
                    subprocess.run(['rm', '-rf', str(temp_dir)], check=False)
                except:
                    pass
                    
        logging.info(f"Cleaned up temporary directory: {temp_dir}")
    except Exception as e:
        logging.warning(f"Failed to clean up directory {temp_dir}: {str(e)}")

def find_existing_pr(github_url: str, token: str, branch_name: str) -> Optional[Dict[str, Any]]:
    """Find an existing pull request for the specified branch.
    
    Args:
        github_url: GitHub repository URL
        token: GitHub token for authentication
        branch_name: Name of the branch to check
        
    Returns:
        Optional dict with PR info if found, None otherwise
    """
    try:
        g = _load_github(token)
        
        # Extract repo owner and name from URL
        owner, repo_name = extract_repo_info(github_url)
        
        # Initialize GitHub client
        repo = g.get_repo(f"{owner}/{repo_name}")
        
        # Look for open PRs from this branch
        for pr in repo.get_pulls(state='open'):
            if pr.head.ref == branch_name:
                return {
                    'number': pr.number,
                    'url': pr.html_url,
                    'title': pr.title,
                    'object': pr
                }
        
        return None
    except ImportError:
        print("PyGithub package not installed. Install with: pip install PyGithub")
        return None
    except Exception as e:
        print(f"Error finding existing PR: {str(e)}")
        return None

def close_pull_request(pr_object) -> bool:
    """Close an open pull request."""
    try:
        pr_object.edit(state="closed")
        return True
    except Exception as e:
        print(f"Error closing pull request: {str(e)}")
        return False

def delete_branch(github_url: str, token: str, branch_name: str) -> bool:
    """Delete a branch from the repository.
    
    Args:
        github_url: GitHub repository URL
        token: GitHub token for authentication
        branch_name: Name of the branch to delete
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        g = _load_github(token)
        
        # Extract repo owner and name from URL
        owner, repo_name = extract_repo_info(github_url)
        
        # Initialize GitHub client
        repo = g.get_repo(f"{owner}/{repo_name}")
        
        # Find the reference to the branch
        git_ref = f"heads/{branch_name}"
        try:
            ref = repo.get_git_ref(git_ref)
            ref.delete()
            print(f"Deleted branch '{branch_name}' from remote repository")
            return True
        except Exception as e:
            if "Not Found" in str(e):
                print(f"Branch '{branch_name}' doesn't exist in remote repository")
                return True  # Consider it a success if branch doesn't exist
            else:
                raise
    except ImportError:
        print("PyGithub package not installed. Install with: pip install PyGithub")
        return False
    except Exception as e:
        print(f"Error deleting branch: {str(e)}")
        return False

def create_git_branch(repo_dir: Path, branch_name: str) -> bool:
    """Create a new git branch in the repository.
    
    Args:
        repo_dir: Path to the repository
        branch_name: Name of the branch to create
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        git = _load_git()
        
        # Open the repository
        repo = git.Repo(repo_dir)
        
        # Check if we're already on the branch
        current_branch = repo.active_branch.name
        if current_branch == branch_name:
            print(f"Already on branch {branch_name}")
            return True
        
        # Check if branch exists locally
        branch_exists = branch_name in [ref.name for ref in repo.references if isinstance(ref, git.refs.Reference)]
        
        if branch_exists:
            # Checkout existing branch
            repo.git.checkout(branch_name)
            print(f"Checked out existing branch: {branch_name}")
        else:
            # Create and checkout new branch
            repo.git.checkout('-b', branch_name)
            print(f"Created and checked out branch: {branch_name}")
            
        return True
        
    except ImportError:
        print("GitPython not installed. Install with: pip install gitpython")
        return False
    except Exception as e:
        print(f"Error creating branch: {str(e)}")
        return False

def commit_documentation_changes(repo_dir: Path, message: str = "Add generated documentation") -> bool:
    """Commit documentation changes to the repository.
    
    Args:
        repo_dir: Path to the repository
        message: Commit message
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        git = _load_git()
        
        # Open the repository
        repo = git.Repo(repo_dir)
        
        # Add README.md and docs/ARCHITECTURE.md
        repo.git.add("README.md")
        
        # Ensure docs directory exists before adding
        docs_dir = repo_dir / "docs"
        arch_file = docs_dir / "ARCHITECTURE.md"
        
        if arch_file.exists():
            repo.git.add("docs/ARCHITECTURE.md")
        
        # Check if there are changes to be committed
        if not repo.index.diff("HEAD") and not repo.untracked_files:
            print("No changes to commit")
            return True
            
        # Commit changes
        repo.index.commit(message)
        print(f"Committed changes with message: {message}")
        return True
        
    except ImportError:
        print("GitPython not installed. Install with: pip install gitpython")
        return False
    except Exception as e:
        print(f"Error committing changes: {str(e)}")
        return False

async def push_branch_to_remote(repo_dir: Path, branch_name: str, token: str, github_url: str) -> bool:
    """Push a branch to the remote repository."""
    repo = None
    try:
        git = _load_git()
        
        # Open the repository
        repo = git.Repo(repo_dir)
        
        # Ensure we're on the correct branch
        if repo.active_branch.name != branch_name:
            repo.git.checkout(branch_name)
        
        # Format remote URL with token for authentication
        parsed_url = urllib.parse.urlparse(github_url)
        auth_url = f"https://{token}@{parsed_url.netloc}{parsed_url.path}"
        if not auth_url.endswith('.git'):
            auth_url += '.git'
            
        # Check if remote exists, set URL with token
        if 'origin' in [remote.name for remote in repo.remotes]:
            remote = repo.remote('origin')
            # Update remote URL with authentication
            remote.set_url(auth_url)
        else:
            # Add new remote
            remote = repo.create_remote('origin', auth_url)
        
        # Push to remote
        remote.push(branch_name, force=True)  # Use force=True to ensure we can update existing branch
        print(f"Pushed branch {branch_name} to remote")
        
        # Reset remote URL to not contain token (security)
        remote.set_url(github_url)
        
        return True
        
    except ImportError:
        print("GitPython not installed. Install with: pip install gitpython")
        return False
    except Exception as e:
        print(f"Error pushing branch: {str(e)}")
        return False
    finally:
        # Close the repository to prevent file locks
        if repo:
            try:
                repo.close()
                if hasattr(repo.git, 'clear_cache'):
                    repo.git.clear_cache()
            except:
                pass

def extract_repo_info(github_url: str) -> Tuple[str, str]:
    """Extract owner and repository name from GitHub URL.
    
    Args:
        github_url: GitHub repository URL
        
    Returns:
        Tuple of (owner, repo_name)
    """
    # Parse the URL
    path_parts = github_url.rstrip('/').split('/')
    
    # The last part is the repository name
    repo_name = path_parts[-1]
    
    # The second-to-last part is the owner
    owner = path_parts[-2]
    
    return owner, repo_name

async def prepare_github_branch(github_url: str, token: str, branch_name: str) -> bool:
    """Clean up any existing branch and PR for re-running.
    
    This function checks for existing PRs and branches with the same name,
    closes any open PRs, and deletes the branch to start fresh.
    
    Args:
        github_url: GitHub repository URL
        token: GitHub token for authentication
        branch_name: Name of the branch to prepare
        
    Returns:
        bool: True if cleanup successful, False otherwise
    """
    print(f"Checking for existing documentation branch '{branch_name}'...")
    
    # Check for existing PR
    existing_pr = find_existing_pr(github_url, token, branch_name)
    
    if existing_pr:
        print(f"Found existing PR #{existing_pr['number']}: {existing_pr['title']}")
        # Close the PR
        if not close_pull_request(existing_pr['object']):
            print("Failed to close existing PR. Continuing anyway...")
    
    # Delete the branch if it exists
    if not delete_branch(github_url, token, branch_name):
        print("Failed to delete existing branch. Continuing anyway...")
    
    return True

async def create_pull_request(github_url: str, token: str, branch_name: str, 
                             pr_title: str, pr_body: str) -> Optional[str]:
    """Create a pull request on GitHub using PyGithub."""
    try:
        # Pass the token to get an authenticated instance
        g = _load_github(token)
        
        # Extract repo owner and name from URL
        owner, repo_name = extract_repo_info(github_url)
        
        # Initialize GitHub client - now g is already an instance
        repo = g.get_repo(f"{owner}/{repo_name}")
        
        # Get default branch to use as base
        default_branch = repo.default_branch
        
        # Create pull request
        pr = repo.create_pull(
            title=pr_title,
            body=pr_body,
            head=branch_name,
            base=default_branch
        )
        
        print(f"Created pull request: {pr.html_url}")
        return pr.html_url
    except ImportError as ie:
        print(f"PyGithub package not installed: {str(ie)}")
        print("Install with: pip install PyGithub")
        return None
    except Exception as e:
        print(f"Error creating pull request: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        return None 