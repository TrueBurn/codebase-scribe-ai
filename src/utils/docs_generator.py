from pathlib import Path
from typing import Dict, List, Optional
import inspect
import importlib
import pkgutil
from dataclasses import dataclass

@dataclass
class DocItem:
    """Represents a documentation item."""
    name: str
    docstring: Optional[str]
    signature: Optional[str]
    type: str  # 'module', 'class', 'function', 'method'
    source_file: Path

class DevDocsGenerator:
    """Generates developer documentation for the project."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.src_dir = project_root / 'src'
    
    def generate_docs(self) -> Dict[str, str]:
        """Generate all developer documentation."""
        return {
            'CONTRIBUTING.md': self._generate_contributing_guide(),
            'DEVELOPMENT.md': self._generate_development_guide(),
            'API.md': self._generate_api_documentation(),
            'ARCHITECTURE.md': self._generate_architecture_guide()
        }
    
    def _generate_contributing_guide(self) -> str:
        """Generate the CONTRIBUTING.md file."""
        return f"""# Contributing Guide

## Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/your-username/readme-generator.git
   cd readme-generator
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Process

1. Make your changes
2. Run tests:
   ```bash
   pytest
   ```
3. Update documentation if needed
4. Submit a pull request

## Code Style

- Follow PEP 8 guidelines
- Use type hints
- Write docstrings for all public functions/classes
- Keep functions focused and small
- Add tests for new features

## Commit Messages

Follow the conventional commits specification:
- feat: New feature
- fix: Bug fix
- docs: Documentation changes
- refactor: Code refactoring
- test: Test updates
- chore: Maintenance tasks

## Pull Request Process

1. Update documentation
2. Add tests for new features
3. Ensure all tests pass
4. Update CHANGELOG.md
5. Request review

## Code Review Process

- All changes require review
- Address review comments
- Maintain a respectful dialogue
- Focus on code, not individuals

## Development Setup

1. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```
2. Set up pre-commit hooks:
   ```bash
   pre-commit install
   ```
3. Configure your editor for:
   - Black formatting
   - Flake8 linting
   - MyPy type checking

## Testing

- Write unit tests for new features
- Maintain test coverage
- Run the full test suite before submitting PRs
- Add integration tests for complex features

## Documentation

- Update API documentation
- Keep README.md current
- Document breaking changes
- Add examples for new features
"""
    
    def _generate_development_guide(self) -> str:
        """Generate the DEVELOPMENT.md file."""
        return f"""# Development Guide

## Project Structure

```python
src/
├── analyzers/      # Code analysis tools
├── clients/        # External service clients
├── generators/     # Content generation
├── models/         # Data models
└── utils/          # Utility functions
```

## Core Components

1. **CodebaseAnalyzer**: Analyzes repository structure
2. **OllamaClient**: Handles AI interactions
3. **MarkdownValidator**: Ensures documentation quality
4. **CacheManager**: Manages caching system

## Development Workflow

1. **Setup Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # or `venv\\Scripts\\activate` on Windows
   pip install -r requirements-dev.txt
   ```

2. **Run Tests**
   ```bash
   pytest
   pytest --cov=src tests/
   ```

3. **Code Quality**
   ```bash
   black src tests
   flake8 src tests
   mypy src
   ```

## Key Concepts

1. **File Analysis**
   - AST parsing
   - Dependency tracking
   - Cache management

2. **Documentation Generation**
   - Template system
   - Markdown validation
   - Link checking

3. **Performance Optimization**
   - Memory management
   - Parallel processing
   - Caching strategies

## Common Tasks

1. **Adding a New Feature**
   - Create feature branch
   - Add tests first
   - Implement feature
   - Update documentation
   - Submit PR

2. **Fixing Bugs**
   - Add regression test
   - Fix issue
   - Update changelog
   - Submit PR

3. **Updating Dependencies**
   - Update requirements.txt
   - Run tests
   - Check for breaking changes
   - Update documentation

## Best Practices

1. **Code Style**
   - Use type hints
   - Write clear docstrings
   - Follow PEP 8
   - Keep functions focused

2. **Testing**
   - Write unit tests
   - Use fixtures
   - Mock external services
   - Test edge cases

3. **Documentation**
   - Keep docs current
   - Add examples
   - Document breaking changes
   - Update API docs

## Troubleshooting

Common issues and solutions...
"""
    
    def _generate_api_documentation(self) -> str:
        """Generate API documentation."""
        return """# API Documentation

## Classes

### CodebaseAnalyzer
Main class for analyzing repository structure and content.

### OllamaClient
Handles interactions with the Ollama API.

### CacheManager
Manages caching with multiple backends.

## Functions

### async_retry
Decorator for retrying async functions with backoff.
"""
    
    def _generate_architecture_guide(self) -> str:
        """Generate the ARCHITECTURE.md file."""
        return """# Architecture Guide

## System Overview

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
```

## Core Components

### 1. Codebase Analysis
- File traversal
- AST parsing
- Dependency tracking
- Import/export detection

### 2. AI Integration
- Local Ollama instance
- Context management
- Prompt templates
- Response processing

### 3. Documentation Generation
- Template system
- Markdown validation
- Link checking
- Readability scoring

### 4. Cache System
- Multi-level caching
- Intelligent invalidation
- Memory optimization
- Persistence

## Data Flow

1. **Input Processing**
   - Repository scanning
   - File classification
   - Metadata collection

2. **Analysis Phase**
   - Code structure analysis
   - Dependency mapping
   - Context building

3. **Generation Phase**
   - Content generation
   - Documentation assembly
   - Validation and fixes

4. **Output Phase**
   - File writing
   - Link validation
   - Format checking

## Design Decisions

1. **Local Processing**
   - Security focus
   - Data privacy
   - Reduced latency

2. **Caching Strategy**
   - Multiple backends
   - Intelligent invalidation
   - Memory efficiency

3. **Modular Design**
   - Loose coupling
   - High cohesion
   - Easy extension

## Future Considerations

1. **Scalability**
   - Parallel processing
   - Distributed caching
   - Worker pools

2. **Extensibility**
   - Plugin system
   - Custom templates
   - Additional backends

3. **Integration**
   - CI/CD pipelines
   - IDE extensions
   - Git hooks
"""
    
    def _get_modules(self) -> List[DocItem]:
        """Extract documentation from all project modules."""
        modules = []
        
        for module_info in pkgutil.walk_packages([str(self.src_dir)]):
            if module_info.name.startswith('_'):
                continue
                
            try:
                module = importlib.import_module(f"src.{module_info.name}")
                module_path = Path(inspect.getfile(module))
                
                # Document the module itself
                modules.append(DocItem(
                    name=module_info.name,
                    docstring=module.__doc__,
                    signature=None,
                    type='module',
                    source_file=module_path
                ))
                
                # Document classes and functions
                for name, obj in inspect.getmembers(module):
                    if name.startswith('_'):
                        continue
                        
                    if inspect.isclass(obj):
                        modules.append(DocItem(
                            name=name,
                            docstring=obj.__doc__,
                            signature=f"class {name}{str(inspect.signature(obj))}",
                            type='class',
                            source_file=module_path
                        ))
                    elif inspect.isfunction(obj):
                        modules.append(DocItem(
                            name=name,
                            docstring=obj.__doc__,
                            signature=f"def {name}{str(inspect.signature(obj))}",
                            type='function',
                            source_file=module_path
                        ))
                        
            except Exception as e:
                print(f"Error documenting {module_info.name}: {e}")
        
        return modules 