from ..analyzers.codebase import CodebaseAnalyzer
from .mermaid import MermaidGenerator
from ..utils.markdown_validator import MarkdownValidator
from pathlib import Path
from ..clients.base_llm import BaseLLMClient
import logging
import re
import json
from typing import Dict, Optional
import traceback
from ..generators.readme import _format_anchor_link

def generate_architecture(analyzer: CodebaseAnalyzer) -> str:
    """Generate Architecture.md content with Mermaid diagrams."""
    content = "# Project Architecture\n\n"
    
    if not analyzer.graph.edges():
        content += "No dependency relationships detected.\n"
        return content
    
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
    
    # Add textual description
    content += "## Dependency Details\n\n"
    content += "### Direct Dependencies\n\n"
    for src, dst in analyzer.graph.edges():
        content += f"- **{src}** → **{dst}**\n"
    
    # Validate and fix markdown
    validator = MarkdownValidator(content)
    issues = validator.validate()
    
    # Log validation issues
    if issues:
        print("\nMarkdown validation issues in Architecture.md:")
        for issue in issues:
            print(f"Line {issue.line_number}: {issue.message} ({issue.severity})")
            if issue.suggestion:
                print(f"  Suggestion: {issue.suggestion}")
    
    # Fix common issues
    content = validator.fix_common_issues()
    
    if "_This ARCHITECTURE" not in content:
        content += "\n\n---\n_This ARCHITECTURE documentation was generated using AI analysis and may contain inaccuracies. Please verify critical information._"
    
    return content

def _build_file_table(files: dict) -> str:
    """Generate nested markdown structure of files with summaries."""
    # Build directory tree
    tree = {'__files__': []}
    for path, info in files.items():
        parts = Path(path).parts
        current = tree
        for part in parts[:-1]:
            if part not in current:
                current[part] = {'__files__': []}
            current = current[part]
        current['__files__'].append((parts[-1], info))

    def _build_section(name: str, content: dict, level: int = 0) -> list[str]:
        lines = []
        indent = '\t' * level
        
        # Add directory header
        if name != '__root__':
            lines.append(f"{indent}<details>")
            lines.append(f"{indent}\t<summary><b><code>{name}/</code> - {_get_directory_purpose(name)}</b></summary>")
            lines.append(f"{indent}\t<blockquote>")
        else:
            # Add root section header for top-level files
            lines.append(f"{indent}<details>")
            lines.append(f"{indent}\t<summary><b>Root Directory</b> - top-level project files</summary>")
            lines.append(f"{indent}\t<blockquote>")
        
        # Add files table if there are files
        if content['__files__']:
            lines.append(f"{indent}\t<table>")
            for filename, info in sorted(content['__files__']):
                summary = info.summary.replace('\n', '<br>') if info.summary else ""
                # Fix path joining logic
                if name == '__root__':
                    file_path = f"/{filename}"
                else:
                    file_path = f"/{name}/{filename}"
                lines.append(f"{indent}\t<tr>")
                lines.append(f"{indent}\t\t<td><b><a href='{file_path}'>{filename}</a></b></td>")
                lines.append(f"{indent}\t\t<td>{summary}</td>")
                lines.append(f"{indent}\t</tr>")
            lines.append(f"{indent}\t</table>")
        
        # Process subdirectories
        subdirs = {k: v for k, v in content.items() if k != '__files__'}
        for subdir, subcontent in sorted(subdirs.items()):
            lines.extend(_build_section(subdir, subcontent, level + 1))
        
        if name != '__root__':
            lines.append(f"{indent}\t</blockquote>")
            lines.append(f"{indent}</details>")
        
        return lines

    root = {'__root__': {'__files__': []}}
    root['__root__'].update(tree)
    
    return "\n".join(_build_section('__root__', root['__root__']))

async def generate_architecture(
    repo_path: Path,
    file_manifest: dict,
    llm_client: BaseLLMClient,
    config: dict
) -> str:
    """Generate architecture documentation for the repository."""
    try:
        # Create a temporary analyzer to use its method
        from src.analyzers.codebase import CodebaseAnalyzer
        temp_analyzer = CodebaseAnalyzer(repo_path, config)
        temp_analyzer.file_manifest = file_manifest
        project_name = temp_analyzer.derive_project_name(config.get('debug', False))
        
        # Set up logging
        debug = config.get('debug', False)
        if debug:
            logging.info(f"Generating architecture documentation for {project_name}")
        
        # Generate architecture content using LLM
        try:
            logging.info("Calling LLM to generate architecture documentation...")
            architecture_content = await llm_client.generate_architecture_doc(file_manifest)
            
            # Log the response for debugging
            if debug:
                content_preview = architecture_content[:200] if architecture_content else "None"
                logging.info(f"LLM response preview: {content_preview}...")
                logging.info(f"Generated architecture content length: {len(architecture_content) if architecture_content else 0}")
        except Exception as e:
            logging.error(f"Error in LLM architecture generation: {str(e)}")
            logging.error(f"Exception details: {traceback.format_exc()}")
            # Create a more detailed fallback with project structure
            return create_fallback_architecture(project_name, file_manifest)
        
        # If we got a valid response, format it properly
        if architecture_content and len(architecture_content) > 100:
            # Log successful generation
            logging.info("Successfully received architecture content from LLM")
            
            # Extract sections to build table of contents
            sections = []
            for line in architecture_content.split('\n'):
                if line.startswith('## '):
                    section_name = line[3:].strip()
                    section_anchor = section_name.lower().replace(' ', '-').replace('/', '').replace('(', '').replace(')', '').replace('.', '')
                    sections.append(f"- [{section_name}](#{section_anchor})")
            
            # If no sections were found, add a default one
            if not sections:
                sections = ["- [Overview](#overview)"]
                # Add an overview section if it doesn't exist
                if "## Overview" not in architecture_content:
                    architecture_content += "\n\n## Overview\n\nThis section provides an overview of the project architecture."
            
            # Create table of contents
            toc = "## Table of Contents\n" + "\n".join(sections) + "\n\n"
            
            # Ensure the document has a proper title
            if not architecture_content.strip().startswith('# '):
                architecture_content = f"# Project Architecture Analysis: {project_name}\n\n{toc}{architecture_content}"
            else:
                # Replace any existing title with our properly formatted one
                architecture_content = re.sub(
                    r'^#\s+.*$', 
                    f"# Project Architecture Analysis: {project_name}", 
                    architecture_content, 
                    count=1, 
                    flags=re.MULTILINE
                )
                
                # Check if there's already a table of contents
                if "## Table of Contents" not in architecture_content:
                    # Find the position after the title to insert TOC
                    lines = architecture_content.split('\n')
                    title_index = next((i for i, line in enumerate(lines) if line.startswith('# ')), 0)
                    
                    # Insert TOC after the title and a blank line
                    if title_index + 1 < len(lines) and lines[title_index + 1].strip() == '':
                        lines.insert(title_index + 2, toc)
                    else:
                        lines.insert(title_index + 1, '\n' + toc)
                    
                    architecture_content = '\n'.join(lines)
            
            if debug:
                logging.info("Successfully formatted architecture content with TOC")
            return architecture_content
        else:
            # Fallback for invalid or empty content
            logging.warning(f"Architecture content too short or invalid: {architecture_content[:100]}...")
            return create_fallback_architecture(project_name, file_manifest)
    except Exception as e:
        logging.error(f"Error generating architecture documentation: {e}")
        return create_fallback_architecture("Project", file_manifest)

def create_fallback_architecture(project_name: str, file_manifest: dict) -> str:
    """Create a fallback architecture document with basic project structure."""
    # Create a basic structure analysis
    structure_sections = analyze_basic_structure(file_manifest)
    
    # Build the document
    content = f"# Project Architecture Analysis: {project_name}\n\n"
    content += "## Table of Contents\n"
    content += "- [Overview](#overview)\n"
    content += "- [Project Structure](#project-structure)\n"
    
    # Add more sections if available
    if structure_sections:
        for section in structure_sections.keys():
            if section != "Overview":
                # Use the _format_anchor_link function from readme.py
                anchor = _format_anchor_link(section)
                content += f"- [{section}](#{anchor})\n"
    
    content += "\n## Overview\n\n"
    content += "This document provides a basic analysis of the project architecture. "
    content += "A more detailed analysis could not be generated automatically.\n\n"
    
    content += "## Project Structure\n\n"
    content += "```\n"
    
    # Add a simplified file tree
    dirs = {}
    for path in file_manifest.keys():
        parts = path.split('/')
        current = dirs
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        if '_files' not in current:
            current['_files'] = []
        current['_files'].append(parts[-1])
    
    # Format the tree
    def format_tree(d, indent=0):
        result = []
        if '_files' in d:
            for f in sorted(d['_files']):
                result.append(' ' * indent + f)
        
        for k in sorted(d.keys()):
            if k != '_files':
                result.append(' ' * indent + k + '/')
                result.extend(format_tree(d[k], indent + 2))
        return result
    
    tree_lines = format_tree(dirs)
    content += '\n'.join(tree_lines[:100])  # Limit to first 100 lines
    if len(tree_lines) > 100:
        content += "\n... (truncated)"
    content += "\n```\n\n"
    
    # Add any additional structure sections
    if structure_sections:
        for section, text in structure_sections.items():
            if section != "Overview":
                content += f"## {section}\n\n{text}\n\n"
    
    return content

def analyze_basic_structure(file_manifest: dict) -> Dict[str, str]:
    """Perform basic structure analysis without LLM."""
    sections = {}
    
    # Count file types
    file_types = {}
    for path in file_manifest.keys():
        ext = path.split('.')[-1] if '.' in path else 'unknown'
        file_types[ext] = file_types.get(ext, 0) + 1
    
    # Create technology stack section based on file extensions
    tech_stack = "Based on file extensions, this project appears to use:\n\n"
    if file_types.get('py', 0) > 0:
        tech_stack += "- Python\n"
    if file_types.get('js', 0) > 0:
        tech_stack += "- JavaScript\n"
    if file_types.get('jsx', 0) > 0 or file_types.get('tsx', 0) > 0:
        tech_stack += "- React\n"
    if file_types.get('ts', 0) > 0:
        tech_stack += "- TypeScript\n"
    if file_types.get('html', 0) > 0:
        tech_stack += "- HTML\n"
    if file_types.get('css', 0) > 0:
        tech_stack += "- CSS\n"
    if file_types.get('java', 0) > 0:
        tech_stack += "- Java\n"
    if file_types.get('cs', 0) > 0:
        tech_stack += "- C#\n"
    
    sections["Technology Stack"] = tech_stack
    
    # Look for common project patterns
    has_tests = any('test' in path.lower() for path in file_manifest.keys())
    has_docs = any('doc' in path.lower() for path in file_manifest.keys())
    has_ci = any('.github/workflows' in path for path in file_manifest.keys())
    
    project_patterns = "The project structure indicates:\n\n"
    if has_tests:
        project_patterns += "- Test suite is present\n"
    if has_docs:
        project_patterns += "- Documentation is available\n"
    if has_ci:
        project_patterns += "- CI/CD configuration is set up\n"
    
    sections["Project Patterns"] = project_patterns
    
    return sections

def _generate_fallback_components(file_manifest: dict) -> str:
    """Generate a basic component list from file types."""
    components = {}
    
    # Group files by directory/type
    for path, info in file_manifest.items():
        parts = path.split('/')
        if len(parts) > 1:
            component = parts[0]  # Use top-level directory as component
        else:
            # Use file extension as component type
            ext = Path(path).suffix.lstrip('.') or "misc"
            component = f"{ext} files"
            
        if component not in components:
            components[component] = []
        components[component].append(path)
    
    # Format as markdown
    result = ""
    for component, files in components.items():
        result += f"### {component.capitalize()}\n\n"
        result += "Contains the following files:\n"
        for file in sorted(files)[:5]:  # Limit to 5 files per component
            result += f"- `{file}`\n"
        if len(files) > 5:
            result += f"- *(and {len(files)-5} more files)*\n"
        result += "\n"
    
    return result

def _get_directory_purpose(directory: str) -> str:
    """Return a general description based on common directory names."""
    purposes = {
        "src": "source code and main implementation",
        "tests": "test files and test utilities",
        "docs": "documentation files",
        "scripts": "automation and utility scripts",
        "config": "configuration files",
        "assets": "static assets and resources",
        ".github": "GitHub-specific configuration and workflows",
    }
    
    dir_name = Path(directory).name
    return purposes.get(dir_name, "project components")

async def generate_architecture_documentation(llm_client, file_manifest, analyzer):
    """Generate architecture documentation for the project."""
    try:
        print("\nGenerating architecture documentation...")
        
        # Generate architecture content
        content = await llm_client.generate_architecture_content(file_manifest, analyzer)
        
        # Ensure the content has proper markdown formatting
        if not content.startswith("# "):
            content = "# Architecture Documentation\n\n" + content
        
        # Check if content contains a mermaid diagram, if not, try to add one
        if "```mermaid" not in content:
            # Get key components to generate a basic diagram
            key_components = llm_client._identify_key_components(file_manifest)
            component_names = re.findall(r'- ([^(]+)', key_components)[:5]  # Extract up to 5 component names
            
            # Create a simple mermaid diagram
            mermaid_diagram = "```mermaid\nflowchart TD\n"
            for i, component in enumerate(component_names):
                component = component.strip()
                mermaid_diagram += f"    C{i}[\"{component}\"] "
                if i > 0:
                    mermaid_diagram += f"--> C{i-1} "
                mermaid_diagram += "\n"
            mermaid_diagram += "```\n\n"
            
            # Insert the diagram after the project structure section
            structure_section_end = content.find("```", content.find("Project Structure"))
            if structure_section_end > 0:
                structure_section_end = content.find("\n", structure_section_end)
                content = content[:structure_section_end+2] + "\n## Component Diagram\n\n" + mermaid_diagram + content[structure_section_end+2:]
        
        return content
    except Exception as e:
        logging.error(f"Error generating architecture documentation: {e}", exc_info=True)
        return "# Architecture Documentation\n\nUnable to generate architecture documentation." 