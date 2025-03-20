# Architecture Generator Documentation

This document provides detailed information about the architecture documentation generation system in the codebase-scribe-ai project.

## Overview

The Architecture Generator is responsible for creating comprehensive architecture documentation for a codebase. It analyzes the repository structure, uses an LLM to generate content, and formats the output with proper markdown structure, including Mermaid diagrams for visual representation.

## Implementation

The Architecture Generator is implemented in `src/generators/architecture.py` and follows a modular design:

```
src/generators/architecture.py
```

## Key Components

### Main Function

```python
async def generate_architecture(
    repo_path: Path,
    file_manifest: dict,
    llm_client: BaseLLMClient,
    config: dict
) -> str:
    """
    Generate architecture documentation for the repository.
    
    This function uses an LLM to generate comprehensive architecture documentation
    with proper formatting, table of contents, and sections. If the LLM fails or
    returns invalid content, it falls back to a basic architecture document.
    """
```

This is the main function for architecture documentation generation. It takes a repository path, file manifest, LLM client, and configuration parameters.

### Supporting Functions

The module provides several supporting functions:

1. **create_fallback_architecture**: Creates a basic architecture document when LLM generation fails
2. **analyze_basic_structure**: Analyzes the file manifest to determine technology stack and project patterns
3. **_format_section_anchor**: Helper function to format section names into valid markdown anchors

## Configuration Options

The Architecture Generator supports several configuration options through constants:

```python
# Constants for configuration
DEFAULT_DIAGRAM_DIRECTION = "TB"  # Top-to-bottom for better package visualization
DEPENDENCY_DIAGRAM_DIRECTION = "LR"  # Left-to-right for dependency flowcharts
MAX_TREE_LINES = 100  # Maximum number of tree lines to display
MAX_COMPONENT_NAMES = 5  # Maximum number of component names to extract
MIN_CONTENT_LENGTH = 100  # Minimum length for valid architecture content
```

## Integration with MermaidGenerator

The Architecture Generator uses the MermaidGenerator to create visual diagrams of the codebase structure. In the previous implementation, it would configure the MermaidGenerator with appropriate settings for each diagram type:

```python
# Create MermaidGenerator with appropriate configuration
mermaid = MermaidGenerator(
    analyzer.graph,
    direction="TB",  # Top-to-bottom for better package visualization
    sanitize_nodes=True
)

# Add package-level overview
content += "## Package Structure\n\n"
content += "The following diagram shows the high-level package organization:\n\n"
content += mermaid.generate_package_diagram(custom_direction="TB")

# Add module dependencies
content += "## Module Dependencies\n\n"
content += "This flowchart shows the dependencies between modules:\n\n"
content += mermaid.generate_dependency_flowchart(custom_direction="LR")

# Add detailed class diagram
content += "## Class Structure\n\n"
content += "The following class diagram shows the detailed structure including exports:\n\n"
content += mermaid.generate_class_diagram()
```

However, in the current implementation, the LLM is responsible for generating the architecture content, including any Mermaid diagrams. The architecture generator focuses on formatting, validation, and providing fallback mechanisms when the LLM fails.

## Error Handling

The Architecture Generator implements comprehensive error handling:

- Try/except blocks around LLM calls
- Fallback mechanism for when LLM generation fails
- Validation of LLM-generated content
- Logging of errors and warnings

## Testing

The Architecture Generator has comprehensive tests in `tests/test_architecture.py` that cover:

- Successful LLM response handling
- LLM failure handling
- Short content handling
- Debug mode behavior
- Fallback architecture generation
- Basic structure analysis

## Usage

The Architecture Generator is typically used in the main application flow:

```python
# Generate architecture documentation
arch_content = await generate_architecture(
    repo_path=repo_path,
    file_manifest=processed_files,
    llm_client=llm_client,
    config=config
)

# Write to file
arch_path = repo_path / "docs" / "ARCHITECTURE.md"
arch_path.write_text(arch_content, encoding='utf-8')
```

## Extending

To extend the Architecture Generator:

1. Add new analysis functions for different aspects of the codebase
2. Enhance the fallback mechanism with more detailed analysis
3. Improve the LLM prompting for better architecture content
4. Add new configuration options for customization