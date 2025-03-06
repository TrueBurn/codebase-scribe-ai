from pathlib import Path
import yaml
from typing import Dict, Any

DEFAULT_CONFIG = {
    # LLM provider configuration
    'llm_provider': 'ollama',  # Default to ollama
    
    'ollama': {
        'base_url': 'http://localhost:11434',
        'max_tokens': 4096,
        'retries': 3,
        'retry_delay': 1.0,
        'timeout': 30,
        'concurrency': 1  # Default to sequential processing
    },
    
    'bedrock': {
        'region': 'us-east-1',
        'model_id': 'us.anthropic.claude-3-5-sonnet-20241022-v2:0',
        'max_tokens': 4096,
        'retries': 3,
        'retry_delay': 1.0,
        'timeout': 30,
        'verify_ssl': True,
        'concurrency': 5  # Default to moderate concurrency
    },
    
    'cache': {
        'enabled': True,
        'directory': '.cache',
        'ttl': 86400,  # 24 hours in seconds
        'max_size': 104857600  # 100MB
    },
    
    # Processing options
    'optimize_order': False,
    'preserve_existing': True,
    'no_cache': False,  # New option to disable cache via command line
    'test_mode': False,
    
    'blacklist': {
        'extensions': ['.txt', '.log'],
        'path_patterns': [
            '/temp/',
            '/cache/',
            '/node_modules/',
            '/__pycache__/',
            '/wwwroot/',
            '^aql/',
            'aql/',
            '/aql/'
        ]
    },
    
    'templates': {
        'prompts': {
            'file_summary': """
Analyze the following code file and provide a clear, concise summary:
File: {file_path}
Type: {file_type}
Context: {context}

Code:
{code}
""".strip(),
            'project_overview': """
Generate a comprehensive overview for:
Project: {project_name}
Files: {file_count}
Components: {key_components}
""".strip(),
            'enhance_existing': """
You are enhancing an existing {doc_type} file. 

EXISTING CONTENT:
{existing_content}

REPOSITORY ANALYSIS:
{analysis}

Your task is to preserve the valuable information in the existing content while enhancing it with insights from the repository analysis.
Do not remove specific implementation details, configuration examples, or custom instructions from the original.
Focus on adding missing information, improving organization, and updating technical details based on the analysis.
Maintain the original structure where possible, especially for configuration examples and code snippets.

Return the enhanced document that preserves the original's valuable content while incorporating new insights.
""".strip()
        },
        'docs': {
            'readme': """
# {project_name}

{project_overview}

## Documentation

{usage}

## Development

{contributing}

## License

{license}
""".strip()
        }
    }
}

class ConfigManager:
    """Manages configuration with defaults and custom overrides."""
    
    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
    
    def get(self, key, default=None):
        """Add dict-like get method"""
        return self.config.get(key, default)
    
    def _load_config(self, config_path: str) -> dict:
        """Load and merge custom configuration."""
        with open(config_path) as f:
            custom_config = yaml.safe_load(f)
        
        # Merge with default configuration
        merged_config = {**DEFAULT_CONFIG, **custom_config}
        
        # Deep merge for nested dictionaries
        for key in ['ollama', 'bedrock', 'cache', 'templates', 'blacklist']:
            if key in DEFAULT_CONFIG and key in custom_config:
                merged_config[key] = {**DEFAULT_CONFIG.get(key, {}), **custom_config.get(key, {})}
                
                # Special handling for nested template dictionaries
                if key == 'templates' and 'prompts' in DEFAULT_CONFIG[key] and 'prompts' in custom_config[key]:
                    merged_config[key]['prompts'] = {
                        **DEFAULT_CONFIG[key]['prompts'], 
                        **custom_config[key]['prompts']
                    }
                if key == 'templates' and 'docs' in DEFAULT_CONFIG[key] and 'docs' in custom_config[key]:
                    merged_config[key]['docs'] = {
                        **DEFAULT_CONFIG[key]['docs'], 
                        **custom_config[key]['docs']
                    }
        
        return merged_config
    
    def get_template(self, category: str, name: str) -> str:
        """Get a specific template from config."""
        return self.config['templates'][category][name]
    
    def get_ollama_config(self) -> Dict[str, Any]:
        """Get Ollama-specific configuration."""
        return self.config['ollama']
    
    def get_bedrock_config(self) -> Dict[str, Any]:
        """Get Bedrock-specific configuration."""
        return self.config['bedrock']

def load_config(config_path: Path) -> dict:
    """Load configuration from YAML file."""
    with open(config_path) as f:
        return yaml.safe_load(f) 