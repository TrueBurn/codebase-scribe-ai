from typing import Dict, List, Optional
from pathlib import Path

class ReadmeTemplate:
    """Handles README.md template generation with multiple sections."""
    
    def __init__(self, file_manifest: Dict, repo_path: Path):
        self.file_manifest = file_manifest
        self.repo_path = repo_path
        self.project_name = repo_path.name
        
    def generate_initial_content(self, project_overview: str) -> str:
        """Generate the initial content with project overview."""
        content = f"# {self.project_name}\n\n"
        content += f"{project_overview}\n\n"
        return content
    
    def generate_usage_section(self) -> str:
        """Generate usage instructions."""
        content = "## Usage\n\n"
        content += "[Add usage instructions here]\n\n"
        return content
    
    def generate_structure_section(self) -> str:
        """Generate project structure section."""
        content = "## Project Structure\n\n```\n"
        # Add file tree structure
        for file_path in sorted(self.file_manifest.keys()):
            content += f"{file_path}\n"
        content += "```\n\n"
        return content
    
    def generate_contributing_section(self) -> str:
        """Generate contributing guidelines."""
        content = "## Contributing\n\n"
        if (self.repo_path / 'CONTRIBUTING.md').exists():
            content += "Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.\n\n"
        else:
            content += "Contributions are welcome! Please feel free to submit a Pull Request.\n\n"
        return content
    
    def generate_license_section(self) -> str:
        """Generate license section."""
        content = "## License\n\n"
        license_file = self._detect_license()
        if license_file:
            content += f"This project is licensed under the terms of the {license_file}.\n\n"
        else:
            content += "[Add license information here]\n\n"
        return content
    
    def generate_overview_section(self) -> str:
        """Generate project overview section."""
        return (
            "## Project Overview\n"
            "This tool generates comprehensive documentation using local AI models. "
            "It analyzes your codebase, builds a dependency graph, and generates clear, "
            "concise documentation to help understand your project architecture and usage."
        )
    
    def generate_title_section(self) -> str:
        """Generate the title section of the README."""
        return f"# {self.project_name}\n"
    
    def _detect_license(self) -> Optional[str]:
        """Detect license from common license files."""
        license_files = ['LICENSE', 'LICENSE.md', 'LICENSE.txt']
        for license_file in license_files:
            if (self.repo_path / license_file).exists():
                return f"[{license_file}]({license_file})"
        return None
    
    def _detect_requirements(self) -> List[str]:
        """Detect project requirements from common requirement files."""
        requirements = []
        req_files = ['requirements.txt', 'pyproject.toml', 'setup.py']
        for req_file in req_files:
            if (self.repo_path / req_file).exists():
                requirements.append(req_file)
        return requirements 