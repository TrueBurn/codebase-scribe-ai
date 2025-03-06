import pytest
from src.utils.memory import MemoryManager

@pytest.fixture
def memory_manager():
    return MemoryManager(target_usage=0.75)

def test_check_memory(memory_manager):
    result = memory_manager.check_memory()
    assert isinstance(result, bool)

def test_optimize_memory(memory_manager):
    initial_usage = memory_manager.get_memory_usage()
    memory_manager.optimize_memory()
    final_usage = memory_manager.get_memory_usage()
    assert final_usage <= initial_usage

def test_chunk_text(memory_manager):
    text = "a" * 1024 * 1024  # 1MB of text
    chunks = memory_manager.chunk_text(text, chunk_size=1024)
    assert all(len(chunk) <= 1024 for chunk in chunks)
    assert ''.join(chunks) == text 