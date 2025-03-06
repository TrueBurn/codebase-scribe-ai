from pathlib import Path
from typing import Dict, Any, Optional
import networkx as nx
from gitignore_parser import parse_gitignore
import os
import logging
import magic
import re
from tqdm import tqdm

from ..models.file_info import FileInfo
from ..utils.cache import CacheManager

class CodebaseAnalyzer:
    """Analyzes repository structure and content."""
    
    def __init__(self, repo_path: Path, config: dict):
        # Windows-specific normalization
        if os.name == 'nt':
            self.repo_path = Path(os.path.normpath(str(repo_path))).absolute()
        else:
            self.repo_path = Path(repo_path).absolute()
        self.config = config
        
        # Initialize debug flag first before using it in other methods
        self.debug = config.get('debug', False)
        
        if self.debug:
            logging.basicConfig(level=logging.DEBUG)
            self.logger = logging.getLogger('codebase_analyzer')
            self.logger.debug(f"Initialized analyzer for repo: {self.repo_path}")
        
        # Now load gitignore after debug is initialized
        self.gitignore = self._load_gitignore()
        
        self.graph = nx.DiGraph()
        self.file_manifest: Dict[str, FileInfo] = {}
        
        # Set up cache using github_repo_id if available
        if config.get('github_repo_id'):
            # Use stable GitHub repo ID for caching
            repo_identifier = config['github_repo_id']
            if self.debug:
                self.logger.debug(f"Using GitHub repo ID for caching: {repo_identifier}")
        else:
            # Use repository path as identifier
            repo_identifier = str(self.repo_path)
        
        # Initialize cache with correct parameters
        self.cache = CacheManager(
            enabled=not config.get('no_cache', False),
            repo_identifier=repo_identifier
        )
        
        # Set debug mode on cache if needed
        self.cache.debug = self.debug
        
        # IMPORTANT: Set the repo_path in the cache manager
        self.cache.repo_path = self.repo_path
        
    def _load_gitignore(self):
        """Load all .gitignore files from the repository"""
        try:
            ignore_funcs = []
            # Find all .gitignore files in the repository
            for gitignore_path in self.repo_path.rglob('.gitignore'):
                if gitignore_path.is_file():
                    if self.debug:
                        logging.debug(f"Found .gitignore file: {gitignore_path}")
                    # Get relative path to repo root
                    rel_path = gitignore_path.parent.relative_to(self.repo_path)
                    ignore_func = parse_gitignore(gitignore_path, base_dir=str(self.repo_path))
                    ignore_funcs.append(ignore_func)
                    
                    # Print the first few patterns from this gitignore for debugging
                    if self.debug:
                        try:
                            with open(gitignore_path, 'r') as f:
                                patterns = [line.strip() for line in f if line.strip() and not line.startswith('#')][:5]
                                logging.debug(f"Sample patterns from {gitignore_path}: {patterns}")
                        except Exception as e:
                            logging.error(f"Error reading gitignore patterns: {e}")
            
            # Combine all gitignore rules
            def combined_ignore(path):
                # Convert to absolute path if it's not already
                if not isinstance(path, Path):
                    path = Path(path)
                    
                if not path.is_absolute():
                    abs_path = (self.repo_path / path).absolute()
                else:
                    abs_path = path.absolute()
                    
                # Get path relative to repo root for gitignore matching
                try:
                    rel_path = abs_path.relative_to(self.repo_path)
                    path_str = str(rel_path)
                    
                    # Check if any ignore function matches
                    for fn in ignore_funcs:
                        if fn(path_str):
                            if self.debug:
                                logging.debug(f"Ignoring {path_str} due to gitignore rule")
                            return True
                    return False
                except ValueError:
                    # Path is not relative to repo_path
                    return False
            
            return combined_ignore
            
        except Exception as e:
            if self.debug:
                logging.error(f"Error loading .gitignore: {e}")
            return lambda _: False

    def is_binary(self, file_path: Path) -> bool:
        """Check if a file is binary."""
        try:
            if not os.access(str(file_path), os.R_OK):
                return False
                
            if not file_path.exists():
                return False
                
            mime = magic.from_file(str(file_path), mime=True)
            return not mime.startswith(('text/', 'application/json', 'application/xml'))
        except (OSError, PermissionError) as e:
            if self.debug:
                logging.error(f"Error checking if file is binary: {e}")
            # Fall back to simple binary check
            return self._is_binary(file_path)

    def should_ignore(self, file_path: Path) -> bool:
        """Check if file should be ignored."""
        # Convert to string for gitignore checking
        path_str = str(file_path)
        
        # Always ignore common patterns
        if any(part.startswith('.') and part != '.gitignore' for part in Path(file_path).parts):
            return True
            
        return self.gitignore(path_str)

    async def analyze_repository(self, show_progress: bool = False) -> Dict[str, FileInfo]:
        """Analyze the full repository structure."""
        # Tell the cache manager about our repository path
        if hasattr(self.cache, 'repo_path'):
            self.cache.repo_path = self.repo_path
        
        try:
            # Initialize blacklist from config
            blacklist_config = self.config.get('blacklist', {})
            self.blacklist_extensions = set(blacklist_config.get('extensions', []))
            self.blacklist_patterns = blacklist_config.get('path_patterns', [])
            
            if self.debug:
                logging.debug(f"Blacklist extensions: {self.blacklist_extensions}")
                logging.debug(f"Blacklist patterns: {self.blacklist_patterns}")
            
            # Get all files in repository
            all_files = []
            for root, _, files in os.walk(self.repo_path):
                root_path = Path(root)
                for file in files:
                    file_path = root_path / file
                    rel_path = file_path.relative_to(self.repo_path)
                    
                    # Skip hidden files and directories except .github
                    parts = rel_path.parts
                    if any(part.startswith('.') for part in parts) and not any(part == '.github' for part in parts) and not str(rel_path).endswith('.gitignore'):
                        continue
                        
                    # Use our custom inclusion method
                    if self._should_include_file(rel_path):
                        all_files.append(file_path)
            
            # Debug output for file detection
            print(f"Found {len(all_files)} files to analyze")
            if len(all_files) == 0:
                print(f"Repository path: {self.repo_path}")
                print(f"Repository path exists: {self.repo_path.exists()}")
                print(f"Repository path is directory: {self.repo_path.is_dir()}")
                if self.repo_path.is_dir():
                    print(f"Repository contents: {list(self.repo_path.iterdir())}")
                return {}
            
            # Test mode - limit to first 5 files
            if self.config.get('test_mode', False):
                all_files = all_files[:5]
                if self.debug:
                    logging.debug(f"Test mode enabled, limiting to {len(all_files)} files")
            
            # Show progress if requested
            if show_progress:
                iterator = tqdm(all_files, desc="Analyzing repository", unit="files")
            else:
                iterator = all_files
                
            # Process each file
            for file_path in iterator:
                rel_path = file_path.relative_to(self.repo_path)
                
                # Skip files that should be ignored
                if self.should_ignore(rel_path):
                    continue
                    
                # Analyze file - make sure to await the async method
                file_info = self._analyze_file(file_path)  # Changed from await to regular call
                
                # Add to manifest
                self.file_manifest[str(rel_path)] = file_info
                
            if self.debug:
                logging.debug(f"Analyzed {len(self.file_manifest)} files")
                
            # Print a summary of the analysis
            print(f"Successfully analyzed {len(self.file_manifest)} files")
            
            return self.file_manifest
            
        except Exception as e:
            if self.debug:
                logging.error(f"Error analyzing repository: {e}")
            print(f"Error analyzing repository: {e}")
            return {}

    def _is_binary(self, file_path: Path) -> bool:
        """Simple binary file detection"""
        try:
            with open(file_path, 'rb') as f:
                return b'\0' in f.read(1024)
        except Exception as e:
            if self.debug:
                self.logger.error(f"Error reading {file_path}: {e}")
            return True

    def _should_include_file(self, rel_path: Path) -> bool:
        """Determine if a file should be included in analysis."""
        # Always include README.md and ARCHITECTURE.md for enhancement
        if rel_path.name == "README.md" or rel_path.name == "ARCHITECTURE.md" or rel_path.name.endswith("CONTRIBUTING.md"):
            return True
        
        # Special case for .github directory - always include it
        if '.github' in rel_path.parts:
            return True
        
        # Skip files that should be ignored
        if self.should_ignore(rel_path):
            if self.debug:
                logging.debug(f"Ignoring file due to ignore patterns: {rel_path}")
            return False
        
        # Skip files with blacklisted extensions
        if rel_path.suffix.lower() in self.blacklist_extensions:
            if self.debug:
                logging.debug(f"Skipping file with blacklisted extension: {rel_path}")
            return False
        
        # Skip files matching blacklisted path patterns
        for pattern in self.blacklist_patterns:
            if re.search(pattern, str(rel_path)):
                if self.debug:
                    logging.debug(f"Skipping file matching blacklist pattern '{pattern}': {rel_path}")
                return False
            
        # Skip hidden files and directories (except .github which is handled above)
        if any(part.startswith('.') for part in rel_path.parts) and not str(rel_path).endswith('.gitignore'):
            if self.debug:
                logging.debug(f"Skipping hidden file/directory: {rel_path}")
            return False
        
        return True

    def _get_repository_files(self) -> list[Path]:
        """Get all files in repository that should be analyzed."""
        files = []
        try:
            for file_path in self.repo_path.rglob('*'):
                if not file_path.is_file():  # Skip directories
                    continue
                    
                # Get path relative to repo root for filtering
                rel_path = file_path.relative_to(self.repo_path)
                
                # Skip files that shouldn't be included
                if not self._should_include_file(rel_path):
                    if self.debug:
                        logging.debug(f"Excluding file due to inclusion rules: {rel_path}")
                    continue
                    
                logging.debug(f"Including file for analysis: {rel_path}")
                files.append(file_path)
                
            if self.debug:
                logging.debug(f"Found {len(files)} files to analyze")
                
            return sorted(files)  # Sort for consistent ordering
            
        except Exception as e:
            if self.debug:
                logging.error(f"Error getting repository files: {e}")
            return [] 

    def _analyze_file(self, file_path: Path) -> FileInfo:
        """Analyze a single file and return FileInfo object."""
        try:
            # Create basic FileInfo object
            file_info = FileInfo(
                path=file_path.relative_to(self.repo_path),
                is_binary=self.is_binary(file_path)
            )
            
            # Skip detailed analysis for binary files
            if file_info.is_binary:
                return file_info
            
            # Try to read file content
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    file_info.content = content
            except UnicodeDecodeError:
                # If we can't read as text, mark as binary
                file_info.is_binary = True
                return file_info
            
            # Extract exports (functions, classes, etc.)
            if file_path.suffix in {'.py', '.js', '.ts', '.cs', '.java'}:
                file_info.exports = self._extract_exports(content)
            
            # Extract dependencies (imports, requires, etc.)
            if hasattr(file_info, 'exports'):
                file_info.dependencies = self._extract_dependencies(content)
            
            # Update dependency graph
            for dep in getattr(file_info, 'dependencies', []):
                self.graph.add_edge(str(file_info.path), dep)
            
            return file_info
            
        except Exception as e:
            if self.debug:
                logging.error(f"Error analyzing file {file_path}: {e}")
            # Return basic FileInfo on error
            return FileInfo(
                path=file_path.relative_to(self.repo_path),
                is_binary=False
            )

    def _extract_exports(self, content: str) -> set[str]:
        """Extract exported symbols from file content."""
        exports = set()
        
        # Simple regex patterns for common exports
        patterns = [
            r'(?:^|\s)class\s+(\w+)',  # Classes
            r'(?:^|\s)def\s+(\w+)',    # Python functions
            r'function\s+(\w+)',       # JavaScript functions
            r'export\s+(?:const|let|var|function|class)\s+(\w+)',  # JS/TS exports
            r'public\s+(?:class|interface|enum)\s+(\w+)',  # C#/Java
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, content, re.MULTILINE)
            exports.update(match.group(1) for match in matches)
        
        return exports

    def _extract_dependencies(self, content: str) -> set[str]:
        """Extract dependencies from file content."""
        deps = set()
        
        # Simple regex patterns for common imports
        patterns = [
            r'import\s+(\w+)',         # Python/Java imports
            r'from\s+(\S+)\s+import',  # Python from imports
            r'require\([\'"](.+?)[\'"]\)',  # Node.js requires
            r'using\s+(.+?);',         # C# using statements
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, content, re.MULTILINE)
            deps.update(match.group(1) for match in matches)
        
        return deps 

    def _check_headers(self):
        """Check header formatting and hierarchy."""
        issues = []
        lines = self.content.split('\n')
        
        for i, line in enumerate(lines):
            # Skip lines that aren't headers
            match = re.match(r'^#+', line)
            if not match:
                continue
            
            level = len(match.group())
            
            # Check maximum header level (usually shouldn't go beyond h4 or h5)
            if level > 5:
                issues.append(f"Header on line {i+1} has too many # symbols (level {level})")
            
            # Check for space after #
            if not re.match(r'^#+\s', line):
                issues.append(f"Header on line {i+1} is missing a space after # symbols")
            
            # Check for capitalization
            header_text = line.lstrip('#').strip()
            if header_text and not header_text[0].isupper():
                issues.append(f"Header on line {i+1} should start with a capital letter")
            
        return issues 

    def derive_project_name(self, debug: bool = False) -> str:
        """Derive project name from repository structure."""
        try:
            # Dictionary of file patterns and their corresponding regex patterns
            name_patterns = {
                # JavaScript/Node.js
                'package.json': r'"name"\s*:\s*"([^"]+)"',
                
                # Python
                'setup.py': r'name=[\'"]([^\'"]+)[\'"]',
                'pyproject.toml': r'name\s*=\s*[\'"]([^\'"]+)[\'"]',
                
                # Java/Kotlin
                'pom.xml': r'<artifactId>([^<]+)</artifactId>|<name>([^<]+)</name>',
                'build.gradle': r'rootProject\.name\s*=\s*[\'"]([^\'"]+)[\'"]',
                'settings.gradle': r'rootProject\.name\s*=\s*[\'"]([^\'"]+)[\'"]',
                
                # C#/.NET
                '.csproj': r'<AssemblyName>([^<]+)</AssemblyName>|<RootNamespace>([^<]+)</RootNamespace>',
                
                # Ruby
                'Gemfile': r'^\s*#\s*([^\s]+)\s*$|gemspec.*name\s*=\s*[\'"]([^\'"]+)[\'"]',
                '.gemspec': r'\.name\s*=\s*[\'"]([^\'"]+)[\'"]',
                
                # Go
                'go.mod': r'module\s+([^\s]+)',
                
                # Rust
                'Cargo.toml': r'name\s*=\s*[\'"]([^\'"]+)[\'"]',
                
                # PHP
                'composer.json': r'"name"\s*:\s*"([^"]+)"',
            }
            
            # Check for each file pattern
            for file_pattern, regex_pattern in name_patterns.items():
                for path, info in self.file_manifest.items():
                    # Handle both dictionary and object access
                    is_binary = info.get('is_binary', False) if hasattr(info, 'get') else getattr(info, 'is_binary', False)
                    
                    if path.endswith(file_pattern) and not is_binary:
                        try:
                            # Handle both dictionary and object access
                            content = info.get('content', '') if hasattr(info, 'get') else getattr(info, 'content', '')
                            
                            if content:
                                # Special handling for pom.xml to prioritize the name tag over artifactId
                                if file_pattern == 'pom.xml':
                                    # First try to find the name tag
                                    name_match = re.search(r'<name>([^<]+)</name>', content)
                                    if name_match and name_match.group(1).strip():
                                        return name_match.group(1).strip()
                                    
                                    # If no name tag, look for artifactId at the project level (not in dependencies)
                                    # Find the main artifactId (not in a dependency section)
                                    artifact_matches = list(re.finditer(r'<artifactId>([^<]+)</artifactId>', content))
                                    for match in artifact_matches:
                                        # Check if this artifactId is not inside a dependency
                                        pos = match.start()
                                        section_before = content[:pos]
                                        # If the last opening tag before this is not a dependency, it's likely the project artifactId
                                        if '<dependency>' not in section_before[-500:]:
                                            return match.group(1)
                                else:
                                    # Extract name using regex for other file types
                                    match = re.search(regex_pattern, content)
                                    if match:
                                        # Get the first non-empty group
                                        for group in match.groups():
                                            if group:
                                                # Clean up the name (remove organization prefixes for some formats)
                                                name = group.split('/')[-1] if '/' in group else group
                                                return name
                        except Exception as e:
                            if debug:
                                print(f"Error parsing {path} for name: {e}")
            
            # If no name found in config files, try to derive from directory structure
            # Look for src/main/java/com/company/project pattern (common in Java)
            java_pattern = re.compile(r'src/main/java/([^/]+)/([^/]+)/([^/]+)')
            for path in self.file_manifest.keys():
                match = java_pattern.search(path)
                if match:
                    # Use the last component as the project name
                    return match.group(3)
            
            # Look for namespace declarations in C# files
            for path, info in self.file_manifest.items():
                if path.endswith('.cs') and not info.get('is_binary', False):
                    try:
                        content = info.get('content', '')
                        if content:
                            namespace_match = re.search(r'namespace\s+([^\s.;{]+)', content)
                            if namespace_match:
                                return namespace_match.group(1)
                    except Exception as e:
                        if debug:
                            print(f"Error parsing C# file for namespace: {e}")
            
            # Try to derive from directory name (use the repository root name)
            # This is a fallback if no other method works
            for path in self.file_manifest.keys():
                parts = path.split('/')
                if len(parts) > 1:
                    # The first part is usually the repository name
                    return parts[0]
            
            # Default fallback
            return "Project"
        except Exception as e:
            if debug:
                print(f"Error deriving project name: {e}")
            return "Project" 