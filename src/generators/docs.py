from pathlib import Path
from typing import Dict
from src.models.file_info import FileInfo

async def generate_readme(
    repo_path: Path,
    file_manifest: Dict[str, FileInfo],
    project_overview: str
) -> str:
    """Generate README.md content."""
    
    # Detect package managers and requirement files
    has_package_json = any(f for f in file_manifest if f.endswith('package.json'))
    has_requirements = any(f for f in file_manifest if f.endswith('requirements.txt'))
    has_poetry = any(f for f in file_manifest if f.endswith('pyproject.toml'))
    has_setup_py = any(f for f in file_manifest if f.endswith('setup.py'))
    has_pom_xml = any(f for f in file_manifest if f.endswith('pom.xml'))
    has_gradle = any(f for f in file_manifest if f.endswith('build.gradle') or f.endswith('build.gradle.kts'))
    has_csproj = any(f for f in file_manifest if f.endswith('.csproj'))
    has_sln = any(f for f in file_manifest if f.endswith('.sln'))
    has_cargo = any(f for f in file_manifest if f.endswith('Cargo.toml'))
    has_gemfile = any(f for f in file_manifest if f.endswith('Gemfile'))
    
    install_cmd = ""
    build_cmd = ""
    
    if has_package_json:
        install_cmd = "npm install"
    elif has_poetry:
        install_cmd = "poetry install"
    elif has_requirements:
        install_cmd = "pip install -r requirements.txt"
    elif has_setup_py:
        install_cmd = "pip install ."
    elif has_pom_xml:
        install_cmd = "./mvnw install"  # Use Maven wrapper if available
        build_cmd = "./mvnw spring-boot:run"  # Assume Spring Boot
    elif has_gradle:
        install_cmd = "./gradlew build"
        build_cmd = "./gradlew bootRun"  # Assume Spring Boot
    elif has_csproj or has_sln:
        install_cmd = "dotnet restore"
        build_cmd = "dotnet build"
    elif has_cargo:
        install_cmd = "cargo build"
    elif has_gemfile:
        install_cmd = "bundle install"
    
    # Basic structure
    readme_content = f"""# {repo_path.name}

{project_overview}

## Project Structure
```
{_generate_tree_structure(file_manifest)}
```

## Usage

[Add usage instructions here]

## Contributing

Contributions are welcome! Please read our contributing guidelines.

## License

[Add license information here]
"""
    return readme_content

async def generate_architecture(
    repo_path: Path,
    file_manifest: Dict[str, FileInfo]
) -> str:
    """Generate ARCHITECTURE.md content."""
    
    arch_content = f"""# Architecture Documentation

## Overview

This document describes the architecture of {repo_path.name}.

## Components

{_generate_component_description(file_manifest)}

## Dependencies

[List major dependencies and their purposes]

## Data Flow

[Describe how data flows through the system]
"""
    return arch_content

def _generate_tree_structure(file_manifest: Dict[str, FileInfo]) -> str:
    """Generate a tree-like structure of the project files."""
    tree = []
    for file_path in sorted(file_manifest.keys()):
        tree.append(f"{file_path}")
    return "\n".join(tree)

def _generate_component_description(file_manifest: Dict[str, FileInfo]) -> str:
    """Generate descriptions of major components."""
    components = {}
    
    # Group files by directory
    for file_info in file_manifest.values():
        dir_path = file_info.path.parent
        if dir_path not in components:
            components[dir_path] = []
        components[dir_path].append(file_info)
    
    # Generate description
    description = []
    for dir_path, files in sorted(components.items()):
        description.append(f"### {dir_path or 'Root'}")
        for file_info in files:
            description.append(f"- {file_info.path.name}")
            if file_info.summary:
                description.append(f"  {file_info.summary}")
        description.append("")
    
    return "\n".join(description) 