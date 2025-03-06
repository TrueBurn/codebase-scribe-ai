from dataclasses import dataclass
from pathlib import Path
from typing import Set, Optional, List

@dataclass
class FileInfo:
    """Information about a file in the codebase."""
    path: str
    size: int
    language: str = None
    is_binary: bool = False
    content: str = None
    summary: str = None
    imports: List[str] = None
    exports: List[str] = None
    from_cache: bool = False  # Track if summary came from cache
    
    def __post_init__(self):
        # Initialize empty collections if None
        if self.imports is None:
            self.imports = []
        if self.exports is None:
            self.exports = []

@dataclass
class FileInfo:
    """Information about a source file in the repository."""
    path: Path
    is_binary: bool = False
    size: int = 0
    summary: Optional[str] = None
    file_type: str = ""
    last_modified: float = 0.0
    imports: Set[str] = None
    exports: Set[str] = None
    from_cache: bool = False  # Add this field to track cache source 