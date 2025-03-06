import asyncio
from typing import TypeVar, List, Callable, Awaitable, Optional
from dataclasses import dataclass
from ..utils.progress import ProgressTracker

T = TypeVar('T')

@dataclass
class ParallelResult:
    """Result of a parallel operation."""
    success: bool
    result: Optional[T] = None
    error: Optional[Exception] = None

class ParallelProcessor:
    """Handles parallel processing with controlled concurrency."""
    
    def __init__(
        self,
        max_concurrent: int = 3,
        progress: Optional[ProgressTracker] = None
    ):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.progress = progress
    
    async def _process_item(
        self,
        item: T,
        operation: Callable[[T], Awaitable[T]],
        task_name: str
    ) -> ParallelResult:
        """Process a single item with error handling."""
        try:
            async with self.semaphore:
                if self.progress:
                    self.progress.start_task(task_name)
                
                result = await operation(item)
                
                if self.progress:
                    self.progress.complete_task(task_name)
                
                return ParallelResult(success=True, result=result)
                
        except Exception as e:
            if self.progress:
                self.progress.complete_task(task_name, success=False, message=str(e))
            return ParallelResult(success=False, error=e)
    
    async def process_items(
        self,
        items: List[T],
        operation: Callable[[T], Awaitable[T]],
        task_name_fn: Callable[[T], str]
    ) -> List[ParallelResult]:
        """
        Process multiple items in parallel.
        
        Args:
            items: List of items to process
            operation: Async function to process each item
            task_name_fn: Function to generate task name from item
        """
        tasks = [
            self._process_item(item, operation, task_name_fn(item))
            for item in items
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=False)
        return results 