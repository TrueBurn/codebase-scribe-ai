import sys
import time
from typing import Optional, Dict, Generator
from dataclasses import dataclass
from enum import Enum
import logging
from pathlib import Path
from tqdm import tqdm
from contextlib import contextmanager

class TaskStatus(Enum):
    PENDING = "⏳"
    RUNNING = "🔄"
    SUCCESS = "✅"
    ERROR = "❌"
    SKIPPED = "⏭️"

@dataclass
class Task:
    """Represents a task in the generation process."""
    name: str
    status: TaskStatus = TaskStatus.PENDING
    message: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    progress_bar: Optional[tqdm] = None

    @property
    def duration(self) -> Optional[float]:
        """Calculate task duration in seconds."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None

class ProgressTracker:
    """Tracks and displays progress of the generation process."""
    
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.tasks: Dict[str, Task] = {}
        self.current_task: Optional[Task] = None
        
        # Set up logging
        self.log_file = repo_path / '.readme_cache' / 'generation.log'
        self.log_file.parent.mkdir(exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger('readme_generator')
        
        # Main progress bar for overall progress
        self.main_pbar = tqdm(
            desc="Overall Progress",
            unit="task",
            position=0,
            leave=True
        )
    
    def start_task(self, name: str, total: Optional[int] = None) -> None:
        """Start a new task with optional subtasks."""
        task = Task(name=name, status=TaskStatus.RUNNING)
        task.start_time = time.time()
        
        # Create progress bar for this task
        task.progress_bar = tqdm(
            desc=name,
            total=total or 1,
            unit="step",
            position=len(self.tasks) + 1,
            leave=False
        )
        
        self.tasks[name] = task
        self.current_task = task
        self.logger.info(f"Started task: {name}")
    
    def update_task(self, name: str, advance: int = 1, message: Optional[str] = None) -> None:
        """Update task progress."""
        if name in self.tasks:
            task = self.tasks[name]
            if task.progress_bar:
                task.progress_bar.update(advance)
                if message:
                    task.progress_bar.set_postfix_str(message)
    
    def complete_task(self, name: str, success: bool = True, message: Optional[str] = None) -> None:
        """Complete a task with success or error."""
        if name in self.tasks:
            task = self.tasks[name]
            task.end_time = time.time()
            task.status = TaskStatus.SUCCESS if success else TaskStatus.ERROR
            task.message = message
            
            # Update and close task progress bar
            if task.progress_bar:
                task.progress_bar.update(task.progress_bar.total - task.progress_bar.n)
                if message:
                    task.progress_bar.set_postfix_str(message)
                task.progress_bar.close()
            
            # Update main progress bar
            self.main_pbar.update(1)
            
            log_level = logging.INFO if success else logging.ERROR
            duration = task.duration
            duration_str = f" ({duration:.2f}s)" if duration else ""
            self.logger.log(log_level, f"Completed task: {name}{duration_str} - {message if message else 'Done'}")
    
    def skip_task(self, name: str, reason: str) -> None:
        """Mark a task as skipped."""
        task = Task(name=name, status=TaskStatus.SKIPPED, message=reason)
        task.progress_bar = tqdm(
            desc=name,
            total=1,
            unit="step",
            position=len(self.tasks) + 1,
            leave=False
        )
        task.progress_bar.update(1)
        task.progress_bar.set_postfix_str(f"Skipped: {reason}")
        task.progress_bar.close()
        
        self.tasks[name] = task
        self.main_pbar.update(1)
        self.logger.info(f"Skipped task: {name} - {reason}")
    
    def summary(self) -> None:
        """Display final summary of all tasks."""
        self.main_pbar.close()
        
        total_time = 0
        successful = 0
        failed = 0
        skipped = 0
        
        for task in self.tasks.values():
            if task.duration:
                total_time += task.duration
            if task.status == TaskStatus.SUCCESS:
                successful += 1
            elif task.status == TaskStatus.ERROR:
                failed += 1
            elif task.status == TaskStatus.SKIPPED:
                skipped += 1
        
        print("\nGeneration Summary:")
        print(f"Total time: {total_time:.2f}s")
        print(f"Tasks: {len(self.tasks)} total, {successful} successful, {failed} failed, {skipped} skipped")
        
        if failed > 0:
            print("\nFailed tasks:")
            for task in self.tasks.values():
                if task.status == TaskStatus.ERROR:
                    print(f"❌ {task.name}: {task.message}")

    @contextmanager
    def task(self, description: str) -> Generator[None, None, None]:
        """Context manager for tracking task progress"""
        try:
            self.current_task = description
            print(f"\n🔄 {description}...", file=sys.stderr)
            yield
            print(f"✅ {description} completed", file=sys.stderr)
        except Exception as e:
            print(f"❌ {description} failed: {e}", file=sys.stderr)
            raise
        finally:
            self.current_task = None 