# Architecture Guide

This document provides a detailed overview of the AI README Generator's architecture, design decisions, and system interactions.

## Table of Contents
- [System Overview](#system-overview)
- [Core Components](#core-components)
- [Data Flow](#data-flow)
- [Design Patterns](#design-patterns)
- [Performance Considerations](#performance-considerations)
- [Security](#security)
- [Extensibility](#extensibility)
- [Project Structure](#project-structure)

## System Overview

### High-Level Architecture

```mermaid
graph TD
    A[Repository] --> B[CodebaseAnalyzer]
    B --> C[File Analysis]
    B --> D[Dependency Graph]
    C --> E[OllamaClient]
    D --> E
    E --> F[Documentation Generator]
    F --> G[Markdown Files]
    H[Cache System] --> B
    H --> E
    I[Memory Manager] --> B
    I --> E
    J[Validators] --> F
```

### Key Components Interaction

```mermaid
sequenceDiagram
    participant User
    participant Analyzer
    participant Ollama
    participant Cache
    participant Generator
    
    User->>Analyzer: Analyze Repository
    Analyzer->>Cache: Check Cache
    Cache-->>Analyzer: Return Cached Data
    Analyzer->>Ollama: Generate Summaries
    Ollama-->>Cache: Store Results
    Analyzer->>Generator: Generate Docs
    Generator->>User: Return Documentation
```

## Core Components

### 1. CodebaseAnalyzer
The central component for repository analysis.

#### Responsibilities
- Repository traversal
- File classification
- AST parsing
- Dependency tracking
- Import/export detection

#### Implementation
```python
class CodebaseAnalyzer:
    def __init__(self, repo_path: Path, config: Dict):
        self.repo_path = repo_path
        self.config = config
        self.file_manifest: Dict[str, FileInfo] = {}
        self.graph = nx.DiGraph()
```

### 2. OllamaClient
Handles all AI model interactions.

#### Responsibilities
- Model communication
- Context management
- Response processing
- Error handling
- Retry logic

#### Implementation
```python
class OllamaClient:
    def __init__(self, config: Dict):
        self.model = config['model']
        self.max_tokens = config['max_tokens']
        self.retries = config['retries']
```

### 3. Cache System
Multi-level caching system.

#### Architecture
```mermaid
graph LR
    A[Request] --> B[Memory Cache]
    B -- Miss --> C[Disk Cache]
    C -- Miss --> D[Generate New]
    D --> C
    C --> B
```

#### Implementation
```python
class CacheManager:
    def __init__(self):
        self.memory_cache = MemoryCache()
        self.disk_cache = SQLiteCache()
```

## Data Flow

### 1. Repository Analysis
```mermaid
graph TD
    A[Input Repository] --> B[File Discovery]
    B --> C[File Classification]
    C --> D[AST Analysis]
    D --> E[Dependency Graph]
    E --> F[File Manifest]
```

### 2. Documentation Generation
```mermaid
graph TD
    A[File Manifest] --> B[Template Selection]
    B --> C[Content Generation]
    C --> D[Validation]
    D --> E[Output Files]
```

## Design Patterns

### 1. Factory Pattern
Used for creating different types of analyzers and generators.

```python
class AnalyzerFactory:
    @staticmethod
    def create_analyzer(file_type: str) -> BaseAnalyzer:
        if file_type == 'python':
            return PythonAnalyzer()
        # ... other analyzers
```

### 2. Strategy Pattern
Used for different processing strategies.

```python
class ProcessingStrategy(ABC):
    @abstractmethod
    def process(self, content: str) -> str:
        pass

class ChunkedProcessing(ProcessingStrategy):
    def process(self, content: str) -> str:
        # Process in chunks
```

### 3. Observer Pattern
Used for progress tracking and event handling.

```python
class ProgressTracker:
    def __init__(self):
        self.observers: List[ProgressObserver] = []

    def notify_progress(self, progress: float):
        for observer in self.observers:
            observer.update(progress)
```

## Performance Considerations

### 1. Memory Management
- Streaming file processing
- Chunk-based handling
- Automatic garbage collection
- Memory usage monitoring

```python
class MemoryManager:
    def __init__(self, target_usage: float = 0.75):
        self.target_usage = target_usage
        self.process = psutil.Process()
```

### 2. Caching Strategy
- Multi-level cache
- TTL-based invalidation
- Size-based limits
- Intelligent prefetching

### 3. Parallel Processing
- Async operations
- Worker pools
- Rate limiting
- Resource management

### Test Mode
- Processes first 5 non-ignored files
- Bypasses cache validation
- Disables parallel processing
- Provides quick validation of core functionality

## Security

### 1. Local Processing
All processing is done locally to ensure:
- Data privacy
- Network isolation
- Resource control
- Access management

### 2. Input Validation
- File type verification
- Content sanitization
- Path traversal prevention
- Size limits

### 3. Output Validation
- Link verification
- Content validation
- Format checking
- Security scanning

## Extensibility

### 1. Plugin System
```python
class Plugin(ABC):
    @abstractmethod
    def initialize(self, config: Dict):
        pass

    @abstractmethod
    def process(self, content: str) -> str:
        pass
```

### 2. Custom Analyzers
```python
class CustomAnalyzer(BaseAnalyzer):
    def analyze(self, content: str) -> AnalysisResult:
        # Custom analysis logic
```

### 3. Template System
```python
class TemplateManager:
    def __init__(self, template_dir: Path):
        self.template_dir = template_dir
        self.templates: Dict[str, Template] = {}
```

## Project Structure

The codebase follows a modular structure with clear separation of concerns:

```
src/
├── analyzers/          # Code analysis tools
│   └── codebase.py     # Repository analysis
├── clients/            # External service clients
│   └── ollama.py       # Ollama API integration
├── generators/         # Content generation
│   ├── readme.py       # README generation
│   └── templates.py    # Template handling
├── models/            # Data models
│   └── file_info.py   # File information
└── utils/             # Utility functions
    ├── cache.py       # Caching system
    └── [other utility modules]
```

### Directory Purposes

- **analyzers/**: Contains tools for analyzing repository structure and code relationships
- **clients/**: Manages external service interactions, particularly with Ollama
- **generators/**: Handles generation of documentation files
- **models/**: Defines data structures and types
- **utils/**: Houses utility functions and helper modules

## Future Considerations

### 1. Scalability
- Distributed processing
- Cloud integration
- Microservices architecture
- Load balancing

### 2. Integration
- CI/CD pipelines
- IDE plugins
- Git hooks
- API endpoints

### 3. Enhancement
- Additional languages
- More documentation types
- Advanced analytics
- Custom workflows

# Project Architecture

## Overview
The AI README Generator is a Python-based tool that analyzes codebases and generates comprehensive documentation using local AI models.

## Project Structure
```
src/
├── analyzers/          # Code analysis tools
│   └── codebase.py     # Repository analysis
├── clients/            # External service clients
│   └── ollama.py       # Ollama API integration
├── generators/         # Content generation
│   ├── readme.py       # README generation
│   └── templates.py    # Template handling
├── models/            # Data models
│   └── file_info.py   # File information
└── utils/             # Utility functions
    ├── cache.py       # Caching system
    └── [other utility modules]
```

## Project Index
<details open>
    <summary><b>Repository Structure</b></summary>
    <blockquote>
        <table>
        <tr>
            <td><b><code>.github/</code></b></td>
            <td>GitHub-specific configuration files and workflows</td>
        </tr>
        <tr>
            <td><b><code>src/</code></b></td>
            <td>Source code for the project</td>
        </tr>
        <tr>
            <td><b><code>tests/</code></b></td>
            <td>Test suite and test fixtures</td>
        </tr>
        <tr>
            <td><b><code>docs/</code></b></td>
            <td>Project documentation</td>
        </tr>
        </table>
    </blockquote>
</details>

## File Filtering

The project implements intelligent file filtering that can be configured via:

```yaml
blacklist:
  extensions: [".md", ".txt", ".log"]
  path_patterns: 
    - "/temp/"
    - "/cache/"
    - "/node_modules/"
    - "/__pycache__/"
```

### Included Files
- All regular source code files
- Documentation files
- Configuration files
- `.github` directory contents
- Essential project files (README, LICENSE, etc.)

### Excluded Files
- Files matching blacklisted extensions (configurable)
- Paths matching blacklisted patterns (configurable)
- Hidden files/directories (except `.github`)
- Build directories (bin, obj, dist, build)
- Cache directories
- Package manager directories (node_modules, venv)
- Binary/compiled files
- IDE configuration directories
- Temporary files

This filtering ensures that generated documentation focuses on the essential project components while excluding unnecessary technical artifacts 