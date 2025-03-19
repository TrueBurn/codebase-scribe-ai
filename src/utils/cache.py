# Standard library imports
import json
import logging
import os
import pickle
import re
import sqlite3
import time
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, Union

@dataclass
class CacheEntry:
    """Represents a cached item with metadata."""
    key: str
    value: Any
    hash: str
    timestamp: float
    metadata: Dict[str, Any]

class CacheBackend(ABC):
    """Abstract base class for cache backends."""
    
    @abstractmethod
    def get(self, key: str) -> Optional[CacheEntry]:
        """Retrieve a value from cache."""
        pass
    
    @abstractmethod
    def set(self, key: str, entry: CacheEntry) -> None:
        """Store a value in cache."""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all cached values."""
        pass

class SQLiteCache(CacheBackend):
    """SQLite-based cache backend for persistence."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value BLOB,
                    hash TEXT,
                    timestamp REAL,
                    metadata BLOB
                )
            """)
    
    def get(self, key: str) -> Optional[CacheEntry]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT value, hash, timestamp, metadata FROM cache WHERE key = ?",
                (key,)
            ).fetchone()
            
            if row:
                return CacheEntry(
                    key=key,
                    value=pickle.loads(row[0]),
                    hash=row[1],
                    timestamp=row[2],
                    metadata=pickle.loads(row[3])
                )
        return None
    
    def set(self, key: str, entry: CacheEntry) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache VALUES (?, ?, ?, ?, ?)",
                (
                    key,
                    pickle.dumps(entry.value),
                    entry.hash,
                    entry.timestamp,
                    pickle.dumps(entry.metadata)
                )
            )

    def clear(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache")

class MemoryCache(CacheBackend):
    """In-memory cache backend for fast access."""
    
    def __init__(self):
        self.cache: Dict[str, CacheEntry] = {}
    
    def get(self, key: str) -> Optional[CacheEntry]:
        return self.cache.get(key)
    
    def set(self, key: str, entry: CacheEntry) -> None:
        self.cache[key] = entry
    
    def clear(self) -> None:
        self.cache.clear()

def hash_path(path: Path) -> str:
    """Generate a stable hash for a file path."""
    return str(abs(hash(str(path.absolute()))) % 10000)
class CacheManager:
    """Manages caching of file summaries.
    
    This class provides functionality to cache file summaries and other data
    to avoid redundant processing. It supports repository-aware caching with
    content-based invalidation using file hashing.
    """
    
    # Default cache directory name in user's home directory
    DEFAULT_GLOBAL_CACHE_DIR = '.readme_generator_cache'
    
    # Default cache directory name in repository
    DEFAULT_REPO_CACHE_DIR = '.cache'
    
    # Default hash algorithm
    DEFAULT_HASH_ALGORITHM = 'md5'
    
    def __init__(self, enabled: bool = True, repo_identifier: str = None, repo_path: Optional[Path] = None, config: Optional[Dict[str, Any]] = None):
        """Initialize the cache manager.
        
        Args:
            enabled: Whether caching is enabled
            repo_identifier: Unique identifier for the repository (e.g., GitHub repo name)
            repo_path: Path to the repository
            config: Configuration dictionary with cache settings
        """
        self.enabled = enabled
        self.repo_identifier = repo_identifier
        self.debug = False  # Debug flag
        self._repo_path = repo_path  # Store the repository path
        
        # Get cache configuration
        self.cache_config = config.get('cache', {}) if config else {}
        cache_location = self.cache_config.get('location', 'repo')
        cache_dir_name = self.cache_config.get('directory', self.DEFAULT_REPO_CACHE_DIR)
        self.hash_algorithm = self.cache_config.get('hash_algorithm', self.DEFAULT_HASH_ALGORITHM)
        
        # Create cache directory based on location setting
        if cache_location == 'home' or not repo_path:
            # Use user's home directory
            global_cache_dir = self.cache_config.get('global_directory', self.DEFAULT_GLOBAL_CACHE_DIR)
            self.cache_dir = Path.home() / global_cache_dir
        else:
            # Use repository path with configured directory name
            self.cache_dir = repo_path / cache_dir_name
            
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Initialize repo cache directory and db path
        if repo_identifier:
            repo_cache_dir = self.get_repo_cache_dir()
        else:
            repo_cache_dir = self.cache_dir
            
        os.makedirs(repo_cache_dir, exist_ok=True)
        
        # Set up SQLite db path
        self.db_path = repo_cache_dir / 'file_cache.db'
        self._init_db()
        
    def _init_db(self):
        """Initialize SQLite database for file caching."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS file_cache (
                    file_path TEXT PRIMARY KEY,
                    summary TEXT,
                    timestamp REAL,
                    content_hash TEXT
                )
            """)
        
    def get_repo_cache_dir(self, repo_path: Optional[Path] = None) -> Path:
        """Get the cache directory for a repository."""
        # If repo_path is not provided, use the stored repo_path
        if not repo_path and self._repo_path:
            repo_path = self._repo_path
            
        if self.repo_identifier:
            # Use stable identifier (for GitHub repos)
            # Normalize the identifier to be safe for all filesystems
            safe_id = self.repo_identifier.replace('/', '_')
            safe_id = re.sub(r'[<>:"|?*]', '_', safe_id)  # Replace Windows-invalid chars
            
            if self.debug:
                print(f"Using normalized cache directory name: {safe_id}")
            
            # Determine cache directory based on whether we're using home or repo location
            # This is determined by where self.cache_dir is set in __init__
            if str(self.cache_dir).startswith(str(Path.home())):
                # Using home directory
                return self.cache_dir / safe_id
            else:
                # Using repository directory
                if repo_path:
                    cache_dir_name = self.cache_config.get('directory', '.cache')
                    return repo_path / cache_dir_name / safe_id
                else:
                    return self.cache_dir / safe_id
        else:
            # Use repo path as before
            if not repo_path:
                raise ValueError("Repository path is required when no repo identifier is provided")
                
            # Determine cache directory based on whether we're using home or repo location
            if str(self.cache_dir).startswith(str(Path.home())):
                # Using home directory - create a subdirectory based on repo name
                repo_name = repo_path.name
                repo_hash = hash_path(repo_path)
                safe_name = re.sub(r'[<>:"|?*]', '_', repo_name)
                safe_dir = f"{safe_name}_{repo_hash}"
                return self.cache_dir / safe_dir
            else:
                # Using repository directory
                cache_dir_name = self.cache_config.get('directory', '.cache')
                cache_dir = repo_path / cache_dir_name
                
                if self.debug:
                    print(f"Using repository cache directory: {cache_dir}")
                
                return cache_dir
            
    def clear_repo_cache(self):
        """Clear the cache for the current repository."""
        if not self.enabled:
            return
            
        try:
            # Clear the database
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('DELETE FROM file_cache')
                
            # Vacuum the database to reclaim space
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('VACUUM')
                
            print(f"Cache cleared for repository")
            
            # Log the location of the cleared cache
            if self._repo_path:
                cache_dir_name = self.cache_config.get('directory', '.cache')
                print(f"Cache location: {self._repo_path / cache_dir_name}")
        except Exception as e:
            logging.warning(f"Failed to clear cache: {e}")
            
    def get(self, key: str) -> Optional[str]:
        """Get value from cache.
        
        Args:
            key: Cache key (file path as string)
            
        Returns:
            Cached value or None if not found
        """
        return self.get_cached_summary(Path(key))

    def set(self, key: str, value: str) -> None:
        """Set value in cache.
        
        Args:
            key: Cache key (file path as string)
            value: Value to cache
        """
        self.save_summary(Path(key), value)

    def save_summary(self, file_path: Path, summary: str) -> None:
        """Save a file summary to the cache."""
        if not self.enabled:
            return
        
        try:
            cache_key = self._create_cache_key(file_path)
            content_hash = self._calculate_file_hash(file_path)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    'INSERT OR REPLACE INTO file_cache (file_path, summary, timestamp, content_hash) VALUES (?, ?, ?, ?)',
                    (cache_key, summary, time.time(), content_hash)
                )
            
            if self.debug:
                print(f"Saved to cache: {cache_key}")
        except Exception as e:
            if self.debug:
                print(f"Error saving to cache: {e}")

    def get_cached_summary(self, file_path: Path) -> Optional[str]:
        """Get cached summary for a file.
        
        Args:
            file_path: Path to file
            
        Returns:
            Cached summary or None if not found or outdated
        """
        if not self.enabled:
            return None
        
        try:
            # Create cache key
            cache_key = self._create_cache_key(file_path)
            
            # Check if file has been modified
            if self._is_file_modified(file_path):
                if self.debug:
                    print(f"Cache: File modified, invalidating cache for {cache_key}")
                return None
            
            # Get from cache
            with sqlite3.connect(self.db_path) as conn:
                result = conn.execute(
                    'SELECT summary FROM file_cache WHERE file_path = ?',
                    (cache_key,)
                ).fetchone()
                
                if result:
                    if self.debug:
                        print(f"Cache hit for: {cache_key}")
                    return result[0]
                else:
                    if self.debug:
                        print(f"Cache miss for: {cache_key}")
                    return None
        except Exception as e:
            if self.debug:
                print(f"Error retrieving from cache: {e}")
            return None

    def is_file_changed(self, file_path: Path) -> bool:
        """Check if file has changed since last cache.
        
        This method compares the current file hash with the cached hash
        to determine if the file has been modified.
        
        Args:
            file_path: Path to the file to check
            
        Returns:
            True if file has changed or has no cache entry, False otherwise
        """
        # Use the internal method for consistency
        return self._is_file_modified(file_path)

    def _create_cache_key(self, file_path: Path) -> str:
        """Create a consistent cache key for a file path.
        
        Always uses the path relative to the repository root, ensuring
        cache hits even when the repository is cloned to different locations.
        """
        try:
            # Convert to absolute paths to handle relative paths correctly
            abs_file_path = file_path.absolute()
            
            # If we have a repo_path, use it to create a relative path
            if self._repo_path:
                abs_repo_path = Path(self._repo_path).absolute()
                
                # Create relative path from repo root
                rel_path = abs_file_path.relative_to(abs_repo_path)
                
                # Normalize path separators to forward slashes for cross-platform compatibility
                cache_key = str(rel_path).replace('\\', '/')
                
                if self.debug:
                    print(f"Created cache key from repo path: {cache_key}")
                
                return cache_key
        except Exception as e:
            if self.debug:
                print(f"Error creating cache key: {e}")
        
        # Fallback: use the filename only as a last resort
        return file_path.name

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate a hash of the file contents using the configured algorithm.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Hexadecimal hash string of the file contents
        """
        try:
            with open(file_path, 'rb') as f:
                file_content = f.read()
                
            if self.hash_algorithm == 'md5':
                file_hash = hashlib.md5(file_content).hexdigest()
            elif self.hash_algorithm == 'sha1':
                file_hash = hashlib.sha1(file_content).hexdigest()
            elif self.hash_algorithm == 'sha256':
                file_hash = hashlib.sha256(file_content).hexdigest()
            else:
                # Default to md5 if unknown algorithm specified
                file_hash = hashlib.md5(file_content).hexdigest()
                
            return file_hash
        except Exception as e:
            if self.debug:
                print(f"Error calculating file hash: {e}")
            # Return a timestamp-based hash as fallback
            return str(os.path.getmtime(file_path))

    def _is_file_modified(self, file_path: Path) -> bool:
        """Check if a file has been modified since it was cached.
        
        Uses content hash instead of modification time for more reliable detection.
        """
        if not file_path.exists():
            return True
        
        try:
            # Calculate content hash
            content_hash = self._calculate_file_hash(file_path)
            cache_key = self._create_cache_key(file_path)
            
            with sqlite3.connect(self.db_path) as conn:
                result = conn.execute(
                    'SELECT content_hash FROM file_cache WHERE file_path = ?',
                    (cache_key,)
                ).fetchone()

                if not result:
                    if self.debug:
                        print(f"No cache entry for: {cache_key}")
                    return True

                cached_hash = result[0]
                return content_hash != cached_hash
        except Exception as e:
            if self.debug:
                print(f"Error checking if file modified: {e}")
            return True

    # Removed unused save() method

    @classmethod
    def clear_all_caches(cls, cache_dir: Optional[Path] = None, repo_path: Optional[Path] = None, config: Optional[Dict[str, Any]] = None) -> None:
        """Clear all caches for all repositories.
        
        Args:
            cache_dir: The cache directory to clear (default: None, will use config)
            repo_path: The repository path to clear cache for (default: None)
            config: Configuration dictionary (default: None)
        """
        # Get cache directory name from config if provided
        cache_dir_name = '.cache'
        if config and 'cache' in config:
            cache_dir_name = config.get('cache', {}).get('directory', '.cache')
            
        # Use provided cache_dir or default
        if cache_dir is None:
            cache_dir = Path(cache_dir_name)
        try:
            # If repo_path is provided, clear the repository's cache directory
            if repo_path:
                repo_cache_dir = repo_path / cache_dir_name
                if repo_cache_dir.exists():
                    print(f"Clearing cache in repository: {repo_cache_dir}")
                    for file in repo_cache_dir.glob('*.db'):
                        file.unlink()
                    for file in repo_cache_dir.glob('*.cache'):
                        file.unlink()
                    if not any(repo_cache_dir.iterdir()):  # If directory is empty
                        repo_cache_dir.rmdir()  # Remove the directory itself
            
            # Also clear the global cache directory
            if cache_dir.exists():
                print(f"Clearing global cache: {cache_dir}")
                for file in cache_dir.glob('*.db'):
                    file.unlink()
                for file in cache_dir.glob('*.cache'):
                    file.unlink()
                if not any(cache_dir.iterdir()):  # If directory is empty
                    cache_dir.rmdir()  # Remove the directory itself
        except Exception as e:
            logging.error(f"Error clearing caches: {e}")

    @property
    def repo_path(self):
        return self._repo_path

    @repo_path.setter
    def repo_path(self, path):
        self._repo_path = path
        if self.debug:
            print(f"Cache: Set repository path to {path}") 