import os
import json
import time
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union
import hashlib

class CacheManager:
    """Manages caching of file summaries and other data."""
    
    def __init__(self, repo_path: Union[str, Path], config: Dict[str, Any], no_cache: bool = False):
        """Initialize cache manager."""
        self.enabled = config.get('cache', {}).get('enabled', True) and not no_cache
        self.repo_path = Path(repo_path) if isinstance(repo_path, str) else repo_path
        self.debug = config.get('debug', False)
        
        if not self.enabled:
            if self.debug:
                print("Cache disabled")
            return
            
        # Get cache directory and location from config
        cache_dir = config.get('cache', {}).get('directory', '.cache')
        cache_location = config.get('cache', {}).get('location', 'repo')
        
        # Determine cache directory based on location setting
        if cache_location == 'home':
            # Use user's home directory
            if not os.path.isabs(cache_dir):
                cache_dir = os.path.join(str(Path.home()), f".readme_generator_cache")
        else:
            # Default to repository path
            if not os.path.isabs(cache_dir):
                cache_dir = os.path.join(str(self.repo_path), cache_dir)
        
        # Create a normalized repo identifier that works for both local and GitHub repos
        if str(self.repo_path).startswith(('http://', 'https://')):
            # For GitHub URLs, extract org/repo
            parts = str(self.repo_path).split('/')
            if 'github.com' in parts:
                # Format: org_repo
                github_index = parts.index('github.com')
                if len(parts) > github_index + 2:
                    repo_id = f"{parts[github_index+1]}_{parts[github_index+2]}"
                else:
                    # Fallback to a hash if URL format is unexpected
                    repo_id = hashlib.md5(str(self.repo_path).encode()).hexdigest()
            else:
                # Non-GitHub URL, use hash
                repo_id = hashlib.md5(str(self.repo_path).encode()).hexdigest()
        else:
            # For local paths, use the repository name
            repo_id = self.repo_path.name
            
            # If repo name is not unique enough, add parent folder
            if len(repo_id) < 5:  # Very short names might not be unique
                parent = self.repo_path.parent.name
                repo_id = f"{parent}_{repo_id}"
        
        # Create cache directory for this repository
        self.repo_cache_dir = Path(cache_dir) / repo_id
        self.repo_cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Set up SQLite database
        self.db_path = self.repo_cache_dir / 'cache.db'
        
        try:
            self._init_db()
            # Log cache location information
            print(f"Cache location: {self.repo_cache_dir}")
            print(f"Cache database: {self.db_path}")
            logging.info(f"Cache initialized at {self.repo_cache_dir}")
            logging.info(f"Cache database file: {self.db_path}")
            
            if self.debug:
                print(f"Cache initialized at {self.repo_cache_dir}")
        except Exception as e:
            self.enabled = False
            print(f"Error initializing cache: {e}")
    
    # Rest of the class implementation remains unchanged 