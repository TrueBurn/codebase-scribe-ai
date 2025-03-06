import asyncio
from functools import wraps
import logging
from typing import TypeVar, Callable, Optional
import time

T = TypeVar('T')

class RetryException(Exception):
    """Custom exception for retry-related errors."""
    pass

def async_retry(
    retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    logger: Optional[logging.Logger] = None,
):
    """
    Decorator for async functions to implement retry logic with exponential backoff.
    
    Args:
        retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch and retry
        logger: Optional logger instance for logging retry attempts
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None
            current_delay = delay
            
            for attempt in range(retries + 1):
                try:
                    return await func(*args, **kwargs)
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == retries:
                        if logger:
                            logger.error(f"Final retry attempt failed for {func.__name__}: {str(e)}")
                        raise RetryException(f"Max retries ({retries}) exceeded") from e
                    
                    if logger:
                        logger.warning(
                            f"Retry attempt {attempt + 1}/{retries} for {func.__name__} "
                            f"failed: {str(e)}. Retrying in {current_delay:.1f}s..."
                        )
                    
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
            
            raise last_exception
        return wrapper
    return decorator

def sync_retry(
    retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    logger: Optional[logging.Logger] = None,
):
    """Synchronous version of the retry decorator."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            current_delay = delay
            
            for attempt in range(retries + 1):
                try:
                    return func(*args, **kwargs)
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == retries:
                        if logger:
                            logger.error(f"Final retry attempt failed for {func.__name__}: {str(e)}")
                        raise RetryException(f"Max retries ({retries}) exceeded") from e
                    
                    if logger:
                        logger.warning(
                            f"Retry attempt {attempt + 1}/{retries} for {func.__name__} "
                            f"failed: {str(e)}. Retrying in {current_delay:.1f}s..."
                        )
                    
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            raise last_exception
        return wrapper
    return decorator 