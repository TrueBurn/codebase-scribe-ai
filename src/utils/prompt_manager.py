from pathlib import Path
from typing import Dict, Optional
import yaml

class PromptTemplate:
    """Manages customizable prompt templates with context injection."""
    
    DEFAULT_TEMPLATES = {
        'file_summary': """
Analyze the following code file and provide a clear, concise summary:

File: {file_path}
Type: {file_type}
Context:
- Imports: {imports}
- Exports: {exports}
- Dependencies: {dependencies}

Code:
{code}

Generate a summary that includes:
1. Main purpose of the file
2. Key components and their roles
3. How it interacts with other modules
4. Any notable patterns or design choices

Keep the summary clear and concise.
""".strip(),
        
        'project_overview': """
Analyze this project's structure and generate a comprehensive overview:

Project: {project_name}
Files: {file_count}
Key Components:
{key_components}

Dependencies:
{dependencies}

Generate a project overview that includes:
1. Main purpose and goals
2. Key features and capabilities
3. Architecture overview
4. Technology stack and design patterns

Focus on high-level understanding while highlighting unique aspects.
""".strip()
    }
    
    def __init__(self, config_path: Optional[Path] = None):
        self.templates = self.DEFAULT_TEMPLATES.copy()
        if config_path and config_path.exists():
            self._load_custom_templates(config_path)
    
    def _load_custom_templates(self, config_path: Path):
        """Load custom templates from config file."""
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        if 'templates' in config:
            self.templates.update(config['templates'])
    
    def get_template(self, template_name: str, context: Dict) -> str:
        """Get a template with context variables injected."""
        if template_name not in self.templates:
            raise ValueError(f"Template '{template_name}' not found")
        
        template = self.templates[template_name]
        return template.format(**self._prepare_context(context))
    
    def _prepare_context(self, context: Dict) -> Dict:
        """Prepare context variables for template injection."""
        # Ensure all potential template variables have defaults
        defaults = {
            'file_path': '',
            'file_type': '',
            'imports': '(none)',
            'exports': '(none)',
            'dependencies': '(none)',
            'code': '',
            'project_name': 'Unknown Project',
            'file_count': 0,
            'key_components': '(none)',
        }
        
        # Update defaults with provided context
        defaults.update(context)
        
        # Format lists and dicts for better display
        for key, value in defaults.items():
            if isinstance(value, (list, set)):
                defaults[key] = '\n'.join(f'- {item}' for item in sorted(value))
            elif isinstance(value, dict):
                defaults[key] = '\n'.join(f'- {k}: {v}' for k, v in sorted(value.items()))
        
        return defaults 