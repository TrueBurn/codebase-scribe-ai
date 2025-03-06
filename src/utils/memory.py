import sys
import psutil
import gc
from typing import Optional, Callable, TypeVar
from functools import wraps
import logging
from pathlib import Path

T = TypeVar('T')

class MemoryManager:
    """Manages memory usage during processing."""
    
    def __init__(self, target_usage: float = 0.75, logger: Optional[logging.Logger] = None):
        self.target_usage = target_usage  # Target memory usage (75% by default)
        self.process = psutil.Process()
        self.logger = logger or logging.getLogger(__name__)
    
    def get_memory_usage(self) -> float:
        """Get current memory usage as a percentage."""
        return self.process.memory_percent()
    
    def check_memory(self) -> bool:
        """Check if memory usage is within acceptable limits."""
        return self.get_memory_usage() <= self.target_usage
    
    def optimize_memory(self) -> None:
        """Attempt to optimize memory usage."""
        if not self.check_memory():
            self.logger.warning(f"High memory usage detected: {self.get_memory_usage():.1f}%")
            gc.collect()
            if hasattr(sys, 'exc_clear'):
                sys.exc_clear()  # Clear any exception info
    
    def chunk_text(self, text: str, chunk_size: int = 1024 * 1024) -> list[str]:
        """Split large text into manageable chunks."""
        return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
    
    def stream_file_content(self, file_path: Path, chunk_size: int = 1024 * 1024):
        """Stream file content instead of loading entirely into memory."""
        with open(file_path, 'r', encoding='utf-8') as f:
            while chunk := f.read(chunk_size):
                yield chunk

def memory_efficient(threshold: float = 0.75):
    """Decorator for memory-intensive functions."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            manager = MemoryManager(threshold)
            
            # Check memory before execution
            if not manager.check_memory():
                manager.optimize_memory()
            
            result = func(*args, **kwargs)
            
            # Check memory after execution
            if not manager.check_memory():
                manager.optimize_memory()
            
            return result
        return wrapper
    return decorator 