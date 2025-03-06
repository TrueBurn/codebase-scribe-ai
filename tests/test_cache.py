import pytest
import time
from pathlib import Path
from src.utils.cache import CacheManager, CacheEntry
from datetime import datetime, timedelta

@pytest.fixture
def cache_dir(tmp_path):
    return tmp_path / 'cache'

@pytest.fixture
def config():
    return {
        'ollama': {
            'model': 'codellama',
            'base_url': 'http://localhost:11434',
            'max_tokens': 4096,
            'retries': 3,
            'retry_delay': 1.0,
            'timeout': 30
        },
        'cache': {
            'ttl': 3600,
            'max_size': 104857600
        }
    }

@pytest.fixture
def cache_manager(cache_dir, config):
    return CacheManager(cache_dir, config)

@pytest.fixture
def test_file(tmp_path):
    """Create a test file in the temporary directory"""
    test_dir = tmp_path / "test_files"
    test_dir.mkdir(parents=True, exist_ok=True)
    file_path = test_dir / "test.py"
    file_path.write_text("print('test')")
    return file_path

def test_cache_save_and_get(cache_manager, test_file):
    value = 'test_value'
    cache_manager.save_summary(test_file, value)
    
    result = cache_manager.get_cached_summary(test_file)
    assert result == value

def test_cache_invalidation(cache_manager, test_file):
    value = 'test_value'
    cache_manager.save_summary(test_file, value)
    
    # Modify file timestamp
    time.sleep(1)
    test_file.touch()
    
    result = cache_manager.get_cached_summary(test_file)
    assert result is None

@pytest.fixture
def cache_config():
    return {
        'cache': {
            'ttl': 3600,  # 1 hour
            'max_size': 1024 * 1024  # 1MB
        }
    }

@pytest.fixture
def cache_manager(tmp_path, cache_config):
    """Create a cache manager with a temporary directory"""
    return CacheManager(tmp_path, cache_config)

def test_cache_initialization(cache_manager):
    """Test that cache is properly initialized"""
    assert cache_manager.cache_dir.exists()
    assert cache_manager.ttl == 3600
    assert cache_manager.max_size == 1024 * 1024

def test_save_and_get_summary(cache_manager, tmp_path):
    """Test saving and retrieving a summary"""
    test_file = tmp_path / "test.py"
    test_file.write_text("print('test')")
    
    test_summary = "This is a test summary"
    cache_manager.save_summary(test_file, test_summary)
    
    retrieved_summary = cache_manager.get_cached_summary(test_file)
    assert retrieved_summary == test_summary

def test_file_change_detection(cache_manager, tmp_path):
    """Test detection of file changes"""
    test_file = tmp_path / "test.py"
    test_file.write_text("print('test')")
    
    # Save initial summary
    cache_manager.save_summary(test_file, "initial summary")
    
    # File hasn't changed
    assert not cache_manager.is_file_changed(test_file)
    
    # Modify file
    time.sleep(0.1)  # Ensure file timestamp changes
    test_file.write_text("print('modified')")
    
    # File has changed
    assert cache_manager.is_file_changed(test_file)

def test_cache_ttl(cache_manager, tmp_path):
    """Test cache time-to-live functionality"""
    test_file = tmp_path / "test.py"
    test_file.write_text("print('test')")
    
    # Save with short TTL
    cache_manager.ttl = 1  # 1 second TTL
    cache_manager.save_summary(test_file, "test summary")
    
    # Immediate retrieval should work
    assert cache_manager.get_cached_summary(test_file) == "test summary"
    
    # Wait for TTL to expire
    time.sleep(1.1)
    
    # Should return None after TTL expires
    assert cache_manager.get_cached_summary(test_file) is None

def test_cache_size_limit(cache_manager, tmp_path):
    """Test cache size limiting"""
    # Create a large summary
    large_summary = "x" * (cache_manager.max_size // 2)
    
    # Save two large summaries
    test_file1 = tmp_path / "test1.py"
    test_file2 = tmp_path / "test2.py"
    test_file1.write_text("print('test1')")
    test_file2.write_text("print('test2')")
    
    cache_manager.save_summary(test_file1, large_summary)
    cache_manager.save_summary(test_file2, large_summary)
    
    # Verify cache management
    assert cache_manager.get_cached_summary(test_file2) == large_summary
    # First entry might be evicted due to size
    
def test_cache_save_persistence(cache_manager, tmp_path):
    """Test that cache persists after save"""
    test_file = tmp_path / "test.py"
    test_file.write_text("print('test')")
    
    cache_manager.save_summary(test_file, "test summary")
    cache_manager.save()
    
    # Create new cache manager instance
    new_cache_manager = CacheManager(tmp_path, {'cache': {'ttl': 3600, 'max_size': 1024 * 1024}})
    
    # Verify data persisted
    assert new_cache_manager.get_cached_summary(test_file) == "test summary"

def test_cache_invalid_file(cache_manager):
    """Test handling of non-existent files"""
    non_existent = Path("non_existent.py")
    assert cache_manager.get_cached_summary(non_existent) is None
    assert cache_manager.is_file_changed(non_existent) is True

@pytest.mark.asyncio
async def test_cache_concurrent_access(cache_manager, tmp_path):
    """Test concurrent cache access"""
    test_file = tmp_path / "test.py"
    test_file.write_text("print('test')")
    
    import asyncio
    
    async def concurrent_save(i):
        await asyncio.sleep(0.1 * (i % 3))  # Stagger saves
        cache_manager.save_summary(test_file, f"summary_{i}")
    
    # Run multiple concurrent saves
    await asyncio.gather(*[concurrent_save(i) for i in range(5)])
    
    # Verify final state
    final_summary = cache_manager.get_cached_summary(test_file)
    assert final_summary.startswith("summary_") 