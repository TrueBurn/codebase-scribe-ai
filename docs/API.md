# API Documentation

This document details the key classes and functions in the AI README Generator.

## Table of Contents
- [Core Components](#core-components)
  - [CodebaseAnalyzer](#codebaseanalyzer)
  - [OllamaClient](#ollamaclient)
  - [DocumentationGenerator](#documentationgenerator)
- [Utility Components](#utility-components)
  - [CacheManager](#cachemanager)
  - [LinkValidator](#linkvalidator)
  - [ReadabilityScorer](#readabilityscorer)

## Core Components

### CodebaseAnalyzer

```python
class CodebaseAnalyzer:
    """Analyzes repository structure and code relationships.
    
    Uses configuration from config.yaml to determine:
    - File extensions to blacklist
    - Path patterns to exclude
    - Special directories to include
    """
    
    def __init__(self, repo_path: Path, config: Dict[str, Any]):
        """Initialize analyzer with repository path and configuration.
        
        Args:
            repo_path: Path to repository root
            config: Configuration dictionary
        """
        
    async def analyze_repository(self) -> Dict[str, FileInfo]:
        """Analyze repository while respecting blacklist rules.
        
        Returns:
            Filtered dictionary of file paths to FileInfo objects
        """
        
    def build_dependency_graph(self) -> nx.DiGraph:
        """Build dependency graph of repository.
        
        Returns:
            NetworkX directed graph of file dependencies
        """
```

### OllamaClient

```python
class OllamaClient:
    """Handles all interactions with local Ollama instance."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Ollama client with configuration.
        
        Args:
            config: Configuration dictionary containing:
                - model: Model name
                - base_url: API endpoint
                - max_tokens: Maximum tokens per request
                - retries: Number of retry attempts
        """
    
    def set_project_structure(self, file_manifest: dict) -> None:
        """Set the project structure for context in all requests.
        
        Args:
            file_manifest: Dictionary mapping file paths to FileInfo objects
        """
    
    def _build_project_structure(self, file_manifest: dict) -> str:
        """Build a tree-like project structure string.
        
        Args:
            file_manifest: Dictionary mapping file paths to FileInfo objects
            
        Returns:
            Formatted string representing project structure
        """
    
    @async_retry(retries=3, delay=1.0)
    async def generate_summary(self, file_content: str, context: Dict) -> str:
        """Generate a summary for a single file.
        
        Args:
            file_content: Content of file to summarize
            context: Additional context (file path, type, etc.)
            
        Returns:
            Generated summary text
        """
    
    async def generate_component_relationships(self, file_manifest: dict) -> str:
        """Generate description of how components interact.
        
        Args:
            file_manifest: Dictionary mapping file paths to FileInfo objects
            
        Returns:
            Generated component relationship description
        """
```

### DocumentationGenerator

```python
class DocumentationGenerator:
    """Generates various documentation files."""
    
    def __init__(self, file_manifest: Dict[str, FileInfo], config: Dict[str, Any]):
        """Initialize generator with file manifest and configuration.
        
        Args:
            file_manifest: Dictionary of file information
            config: Configuration dictionary
        """
    
    def generate_readme(self) -> str:
        """Generate README.md content.
        
        Returns:
            Generated README content
        """
    
    def generate_architecture_doc(self) -> str:
        """Generate architecture documentation.
        
        Returns:
            Generated architecture documentation
        """
```

## Utility Components

### CacheManager

```python
class CacheManager:
    """Manages caching with multiple backends and intelligent invalidation."""
    
    def __init__(self, repo_path: Path, config: Dict[str, Any]):
        """Initialize cache manager.
        
        Args:
            repo_path: Repository root path
            config: Cache configuration including:
                - enabled: bool (default: True)
                - directory: str (default: '.cache')
                - ttl: int (default: 86400)
                - max_size: int (default: 104857600)
                
        Notes:
            - Creates cache directory if it doesn't exist
            - Initializes SQLite database automatically
            - Falls back to disabled cache if initialization fails
        """
    
    def _init_db(self):
        """Initialize SQLite database.
        
        Creates the database and required tables if they don't exist.
        Disables caching if initialization fails instead of raising an error.
        """
    
    def clear_repo_cache(self) -> None:
        """Clear all cached data for this repository.
        
        Removes both SQLite database and cache file.
        Handles locked files gracefully.
        """
    
    @classmethod
    def clear_all_caches(cls, cache_dir: Path = Path('.cache')) -> None:
        """Clear all caches for all repositories.
        
        Args:
            cache_dir: Directory containing cache files
        """
    
    def get_cached_summary(self, file_path: Path) -> Optional[str]:
        """Get cached summary for a file if available and valid.
        
        Args:
            file_path: Path to file
            
        Returns:
            Cached summary if available and not expired
        """
    
    def save_summary(self, file_path: Path, summary: str) -> None:
        """Save summary to cache.
        
        Args:
            file_path: Path to file
            summary: Summary to cache
        """
```

### LinkValidator

```python
class LinkValidator:
    """Validates internal and external links in documentation."""
    
    def __init__(self, repo_path: Path):
        """Initialize link validator.
        
        Args:
            repo_path: Repository root path
        """
    
    async def validate_document(self, content: str, base_path: Path) -> List[LinkIssue]:
        """Validate all links in a markdown document.
        
        Args:
            content: Document content
            base_path: Base path for relative links
            
        Returns:
            List of link validation issues
        """
```

### ReadabilityScorer

```python
class ReadabilityScorer:
    """Analyzes and scores documentation readability."""
    
    def analyze_text(self, text: str, section_name: str) -> Dict:
        """Analyze text and return readability metrics.
        
        Args:
            text: Text to analyze
            section_name: Name of section being analyzed
            
        Returns:
            Dictionary of readability metrics
        """
    
    def get_recommendations(self, section_name: str) -> List[str]:
        """Get improvement recommendations based on scores.
        
        Args:
            section_name: Name of analyzed section
            
        Returns:
            List of improvement recommendations
        """
```

## Usage Examples

### Basic Usage

```python
# Initialize components
analyzer = CodebaseAnalyzer(repo_path, config)
ollama = OllamaClient(config)
cache = CacheManager(repo_path, config)

# Analyze repository
file_manifest = await analyzer.analyze_repository()

# Generate documentation
generator = DocumentationGenerator(file_manifest, config)
readme_content = generator.generate_readme()

# Validate documentation
validator = LinkValidator(repo_path)
issues = await validator.validate_document(readme_content, repo_path)
```

### Advanced Usage

```python
# Readability analysis
scorer = ReadabilityScorer()
metrics = scorer.analyze_text(content, "overview")
recommendations = scorer.get_recommendations("overview")
```

## Error Handling

All components use custom exceptions for specific error cases:

```python
class OllamaClientError(Exception):
    """Raised for Ollama API related errors."""

class CacheError(Exception):
    """Raised for caching related errors."""

class ValidationError(Exception):
    """Raised for validation related errors."""
```

## Configuration

See [README.md](../README.md#configuration) for detailed configuration options. 

### Error Handling

The cache system is designed to fail gracefully:

1. **Missing Directory**: Creates `.cache` directory if it doesn't exist
2. **Database Initialization**: Creates database and tables if missing
3. **Access Errors**: Disables caching instead of failing
4. **Concurrent Access**: Handles multiple processes safely

# ... rest of existing content ... 