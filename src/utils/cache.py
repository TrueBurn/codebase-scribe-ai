import json
import time
from pathlib import Path
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
import sqlite3
import pickle
from dataclasses import dataclass
import os
import logging
from ..models.file_info import FileInfo
import re

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
    """Manages caching of file summaries."""
    
    def __init__(self, enabled: bool = True, repo_identifier: str = None):
        self.enabled = enabled
        self.repo_identifier = repo_identifier
        self.debug = False  # Add debug flag
        self.ttl = 24 * 60 * 60  # Default TTL: 24 hours in seconds
        self._repo_path = None  # Add repo_path property
        
        # Create cache directory if it doesn't exist
        self.cache_dir = Path.home() / '.readme_generator_cache'
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
        if self.repo_identifier:
            # Use stable identifier (for GitHub repos)
            # Normalize the identifier to be safe for all filesystems
            safe_id = self.repo_identifier.replace('/', '_')
            safe_id = re.sub(r'[<>:"|?*]', '_', safe_id)  # Replace Windows-invalid chars
            
            if self.debug:
                print(f"Using normalized cache directory name: {safe_id}")
            
            return self.cache_dir / safe_id
        else:
            # Use repo path as before
            if not repo_path:
                raise ValueError("Repository path is required when no repo identifier is provided")
            repo_name = repo_path.name
            repo_hash = hash_path(repo_path)
            
            # Normalize the path for filesystem compatibility
            safe_name = re.sub(r'[<>:"|?*]', '_', repo_name)
            safe_dir = f"{safe_name}_{repo_hash}"
            
            if self.debug:
                print(f"Using normalized cache directory name: {safe_dir}")
            
            return self.cache_dir / safe_dir
            
    def clear_repo_cache(self):
        """Clear the cache for the current repository."""
        if not self.enabled:
            return
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('DELETE FROM file_cache')
            print(f"Cache cleared for repository")
        except Exception as e:
            logging.warning(f"Failed to clear cache: {e}")
            
    def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        return self.get_cached_summary(Path(key))

    def set(self, key: str, value: str) -> None:
        """Set value in cache."""
        self.save_summary(Path(key), value)

    def _load_cache(self) -> None:
        """Load cache from file."""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.cache_data = json.load(f)
                self.enabled = True
        except Exception as e:
            logging.warning(f"Failed to load cache: {e}")
            self.cache_data = {}
            self.enabled = False

    def _save_cache(self) -> None:
        """Save cache to file."""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache_data, f, indent=2)
        except Exception as e:
            logging.warning(f"Failed to save cache: {e}")

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
        """Check if file has changed since last cache."""
        if not self.enabled:
            return True  # Always return True if cache is disabled
            
        if not file_path.exists():
            return True
        
        # Create a repository-relative cache key
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
            current_hash = self._calculate_file_hash(file_path)
            return current_hash != cached_hash

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
        """Calculate a hash of the file contents."""
        import hashlib
        
        try:
            with open(file_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
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

    def save(self):
        # Skip saving in debug mode
        if self.debug:
            return
            
        """Save the cache to disk."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'w') as f:
                json.dump(self._cache, f)
        except Exception as e:
            if self.debug:
                logging.error(f"Error saving cache: {e}")
            print(f"Warning: Could not save cache: {e}") 

    @classmethod
    def clear_all_caches(cls, cache_dir: Path = Path('.cache')) -> None:
        """Clear all caches for all repositories."""
        try:
            if cache_dir.exists():
                for file in cache_dir.glob('*.db'):
                    file.unlink()
                for file in cache_dir.glob('*.cache'):
                    file.unlink()
                if not any(cache_dir.iterdir()):  # If directory is empty
                    cache_dir.rmdir()  # Remove the directory itself
        except Exception as e:
            logging.error(f"Error clearing all caches: {e}") 

    @property
    def repo_path(self):
        return self._repo_path

    @repo_path.setter
    def repo_path(self, path):
        self._repo_path = path
        if self.debug:
            print(f"Cache: Set repository path to {path}") 