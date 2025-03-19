from dataclasses import dataclass
from pathlib import Path
from typing import Set, Optional, List, Union

@dataclass
class FileInfo:
    """Information about a source file in the repository."""
    path: Union[str, Path]  # Support both string and Path objects
    is_binary: bool = False
    size: int = 0
    language: str = None
    content: str = None
    summary: Optional[str] = None
    file_type: str = ""
    last_modified: float = 0.0
    imports: Union[List[str], Set[str]] = None
    exports: Union[List[str], Set[str]] = None
    from_cache: bool = False  # Track if summary came from cache
    
    def __post_init__(self):
        # Initialize empty collections if None
        if self.imports is None:
            self.imports = set()
        if self.exports is None:
            self.exports = set()
        
        # Convert path to Path object if it's a string
        if isinstance(self.path, str):
            self.path = Path(self.path)