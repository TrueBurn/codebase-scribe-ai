"""Shared utilities for LLM clients."""
from typing import Dict, Any, List
import logging
from pathlib import Path
import re
from collections import defaultdict
import json

def format_project_structure(file_manifest: dict, debug: bool = False) -> str:
    """Build a tree-like project structure string from file manifest."""
    try:
        # Create a nested dictionary to represent the directory structure
        directories = {}
        
        for path in file_manifest.keys():
            parts = path.split('/')
            current_dir = directories
            
            # Navigate through the directory structure
            for i, part in enumerate(parts[:-1]):  # All parts except the last one (filename)
                if part not in current_dir:
                    current_dir[part] = {}
                current_dir = current_dir[part]
            
            # Add the file to the current directory
            if '_files' not in current_dir:
                current_dir['_files'] = []
            current_dir['_files'].append(parts[-1])  # The last part is the filename
        
        # Format the directory structure as a string
        def format_dir(dir_dict, indent=0):
            result = []
            # First list all files in the current directory
            if '_files' in dir_dict:
                for file in sorted(dir_dict['_files']):
                    result.append(' ' * indent + '- ' + file)
            
            # Then list all subdirectories
            for name, contents in sorted(dir_dict.items()):
                if name != '_files':
                    result.append(' ' * indent + '+ ' + name + '/')
                    result.extend(format_dir(contents, indent + 2))
            
            return result
        
        structure_lines = format_dir(directories)
        return '\n'.join(structure_lines)
    except Exception as e:
        if debug:
            print(f"Error formatting project structure: {e}")
        return "Error formatting project structure"

def find_common_dependencies(file_manifest: dict, debug: bool = False) -> str:
    """Extract common dependencies from file manifest."""
    try:
        # Collect all dependencies
        dependencies = defaultdict(int)
        
        # Look for package.json files
        for path, info in file_manifest.items():
            if path.endswith('package.json') and not info.get('is_binary', False):
                try:
                    content = info.get('content', '')
                    if content and '"dependencies"' in content:
                        # Extract dependencies section
                        deps_match = re.search(r'"dependencies"\s*:\s*{([^}]+)}', content)
                        if deps_match:
                            deps_str = deps_match.group(1)
                            # Extract each dependency
                            for dep_match in re.finditer(r'"([^"]+)"\s*:\s*"([^"]+)"', deps_str):
                                dep_name = dep_match.group(1)
                                dep_version = dep_match.group(2)
                                dependencies[f"{dep_name}@{dep_version}"] += 1
                except Exception as e:
                    if debug:
                        print(f"Error parsing package.json: {e}")
        
        # Look for requirements.txt files
        for path, info in file_manifest.items():
            if path.endswith('requirements.txt') and not info.get('is_binary', False):
                try:
                    content = info.get('content', '')
                    if content:
                        # Extract each dependency
                        for line in content.split('\n'):
                            line = line.strip()
                            if line and not line.startswith('#'):
                                dependencies[line] += 1
                except Exception as e:
                    if debug:
                        print(f"Error parsing requirements.txt: {e}")
        
        # Format the dependencies as a string
        if dependencies:
            result = "Detected dependencies:\n"
            for dep, count in sorted(dependencies.items(), key=lambda x: (-x[1], x[0])):
                result += f"- {dep}\n"
            return result
        else:
            return "No dependencies detected."
    except Exception as e:
        if debug:
            print(f"Error finding common dependencies: {e}")
        return "Error finding common dependencies"

def identify_key_components(file_manifest: dict, debug: bool = False) -> str:
    """Identify key components from file manifest."""
    try:
        # Group files by directory
        directories = defaultdict(list)
        for path in file_manifest.keys():
            directory = str(Path(path).parent)
            if directory == '.':
                directory = 'root'
            directories[directory].append(path)
        
        # Sort directories by number of files
        sorted_dirs = sorted(directories.items(), key=lambda x: len(x[1]), reverse=True)
        
        # Format the key components as a string
        result = "Key components:\n"
        for directory, files in sorted_dirs[:10]:  # Limit to top 10 directories
            result += f"- {directory} ({len(files)} files)\n"
        
        return result
    except Exception as e:
        if debug:
            print(f"Error identifying key components: {e}")
        return "Error identifying key components"

def get_default_order(core_files: dict, resource_files: dict) -> List[str]:
    """Get a sensible default order when LLM ordering fails."""
    # Start with configuration files
    config_files = [p for p in core_files if p.endswith(('.json', '.config', '.settings'))]
    # Then other core files
    other_files = [p for p in core_files if p not in config_files]
    # End with resource files
    resource_list = list(resource_files.keys())
    
    return config_files + other_files + resource_list

def fix_markdown_issues(content: str) -> str:
    """Fix common markdown formatting issues before returning content."""
    if not content:
        return content
        
    lines = content.split('\n')
    fixed_lines = []
    
    # Track header levels to ensure proper hierarchy
    header_levels = []
    in_list = False
    list_indent_level = 0
    
    for i, line in enumerate(lines):
        # Fix headers without space after #
        if re.match(r'^#+[^#\s]', line):
            line = re.sub(r'^(#+)([^#\s])', r'\1 \2', line)
        
        # Track header levels for hierarchy
        header_match = re.match(r'^(#+)\s', line)
        if header_match:
            level = len(header_match.group(1))
            
            # Ensure there's a blank line before headers (except at the start)
            if i > 0 and fixed_lines and fixed_lines[-1].strip():
                fixed_lines.append('')
            
            # Ensure there's a blank line after headers
            if i < len(lines) - 1 and lines[i+1].strip():
                line = line + '\n'
            
            # Check header hierarchy
            if not header_levels or level <= header_levels[-1]:
                header_levels.append(level)
            elif level > header_levels[-1] + 1:
                # Header level jumped too much, adjust it
                level = header_levels[-1] + 1
                line = '#' * level + line[header_match.end(1):]
                header_levels.append(level)
            else:
                header_levels.append(level)
        
        # Fix list indentation
        list_match = re.match(r'^(\s*)[-*+]\s', line)
        if list_match:
            indent = len(list_match.group(1))
            if not in_list:
                in_list = True
                list_indent_level = indent
            elif indent > list_indent_level and indent - list_indent_level != 2:
                # Adjust indentation to be multiple of 2
                new_indent = list_indent_level + 2
                line = ' ' * new_indent + line.lstrip()
        elif line.strip() and in_list:
            in_list = False
        
        fixed_lines.append(line)
    
    return '\n'.join(fixed_lines)

def prepare_file_order_data(project_files: dict, debug: bool = False) -> tuple:
    """Prepare data for file order optimization."""
    # Define patterns for vendor/resource files to exclude from LLM analysis
    vendor_patterns = [
        r'[\\/]bootstrap[\\/]',           # Bootstrap files
        r'[\\/]vendor[\\/]',              # Vendor directories
        r'[\\/]wwwroot[\\/]lib[\\/]',     # Library resources
        r'\.min\.(js|css|map)$',          # Minified files
        r'\.css\.map$',                   # Source maps
        r'\.ico$|\.png$|\.jpg$|\.gif$',   # Images
        r'[\\/]node_modules[\\/]',        # Node modules
        r'[\\/]dist[\\/]',                # Distribution files
        r'[\\/]packages[\\/]',            # Package files
        r'[\\/]PublishProfiles[\\/]',     # Publish profiles
        r'\.pubxml(\.user)?$',            # Publish XML files
        r'\.csproj(\.user)?$',            # Project files
        r'\.sln$'                         # Solution files
    ]
    
    # Filter out vendor/resource files
    core_files = {}
    resource_files = {}
    
    if debug:
        print("Filtering files...")
    
    for path, info in project_files.items():
        is_vendor = any(re.search(pattern, path, re.IGNORECASE) for pattern in vendor_patterns)
        if is_vendor:
            resource_files[path] = info
        else:
            core_files[path] = info
    
    if debug:
        print(f"Filtered {len(core_files)} core files and {len(resource_files)} resource files")
    logging.info(f"File filtering: {len(core_files)} core files and {len(resource_files)} resource files")
    
    # Build simplified file info for core files only
    if debug:
        print("Building file information...")
    files_info = {}
    
    for path, info in core_files.items():
        # Get attributes with safe defaults
        deps = getattr(info, 'dependencies', None) or []
        exports = getattr(info, 'exports', None) or []
        
        files_info[path] = {
            "type": info.get('file_type', Path(path).suffix),
            "size": info.get('size', 0),
            "is_binary": info.get('is_binary', False),
            "dependencies": list(deps),
            "exports": list(exports)
        }
    
    return core_files, resource_files, files_info

def process_file_order_response(content: str, core_files: dict, resource_files: dict, debug: bool = False) -> list:
    """Process LLM response to extract file order."""
    try:
        # Try to parse as JSON first
        result = json.loads(content)
        if isinstance(result, dict) and "file_order" in result:
            file_order = result["file_order"]
            # Validate paths exist in original files
            valid_paths = [path for path in file_order if path in core_files]
            
            if valid_paths:
                if debug and "reasoning" in result:
                    reasoning = result.get("reasoning", "")
                    print(f"Ordering reasoning: {reasoning[:100]}..." if len(reasoning) > 100 else reasoning)
                
                # Append resource files at the end
                full_order = valid_paths + list(resource_files.keys())
                return full_order
    except:
        # If JSON parsing fails, try to extract file paths from text
        lines = content.split('\n')
        file_paths = []
        for line in lines:
            # Look for file paths in the response
            for path in core_files.keys():
                if path in line:
                    file_paths.append(path)
                    break
        
        if file_paths:
            # Append resource files at the end
            full_order = file_paths + list(resource_files.keys())
            return full_order
    
    # If all else fails, use default order
    return get_default_order(core_files, resource_files) 