from pathlib import Path
import yaml
from typing import Dict, Any, Optional
import os
import logging

DEFAULT_CONFIG = {
    # LLM provider configuration
    'llm_provider': 'ollama',  # Default to ollama
    'debug': False,  # Default debug setting
    
    'ollama': {
        'base_url': 'http://localhost:11434',
        'max_tokens': 4096,
        'retries': 3,
        'retry_delay': 1.0,
        'timeout': 30,
        'concurrency': 1,  # Default to sequential processing
        'temperature': 0.0  # Default to deterministic output
    },
    
    'bedrock': {
        'region': 'us-east-1',
        'model_id': 'us.anthropic.claude-3-5-sonnet-20241022-v2:0',
        'max_tokens': 8192,
        'retries': 3,
        'retry_delay': 1.0,
        'timeout': 120,  # Default to 2 minutes
        'verify_ssl': True,
        'concurrency': 5,  # Default to moderate concurrency
        'temperature': 0.0  # Default to deterministic output
    },
    
    'cache': {
        'enabled': True,
        'directory': '.cache',
        'location': 'repo'  # 'repo' (in target repository) or 'home' (in user's home directory)
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
            'enhance_documentation': """
You are enhancing an existing {doc_type} file. 

EXISTING CONTENT:
{existing_content}

REPOSITORY ANALYSIS:
{analysis}

Your task is to create the best possible documentation by intelligently combining the existing content with new insights from the repository analysis.

Guidelines:
1. Preserve valuable information from the existing content, especially specific implementation details, configuration examples, and custom instructions.
2. Feel free to reorganize the document structure to improve clarity and flow.
3. Remove outdated, redundant, or incorrect information.
4. Add missing information and technical details based on the repository analysis.
5. Ensure proper markdown formatting with consistent header hierarchy.
6. Maintain code snippets and examples, updating them only if they're incorrect.
7. If the existing content has a specific tone or style, try to maintain it.

Return a completely restructured document that represents the best possible documentation for this codebase, combining the strengths of the existing content with new insights.
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
    
    def __getitem__(self, key):
        """Allow dictionary-like access to config."""
        return self.config[key]
    
    def get(self, key, default=None):
        """Add dict-like get method"""
        return self.config.get(key, default)
    
    def _load_config(self, config_path: str) -> dict:
        """Load and merge custom configuration."""
        try:
            with open(config_path) as f:
                custom_config = yaml.safe_load(f)
            
            if custom_config is None:
                logging.warning(f"Empty or invalid config file: {config_path}")
                custom_config = {}
                
            # Merge with default configuration
            merged_config = self._deep_merge(DEFAULT_CONFIG, custom_config)
            
            # Apply environment variable overrides
            merged_config = self._apply_env_overrides(merged_config)
            
            return merged_config
            
        except Exception as e:
            logging.error(f"Error loading config from {config_path}: {str(e)}")
            logging.info("Using default configuration")
            return DEFAULT_CONFIG
    
    def _deep_merge(self, default: dict, custom: dict) -> dict:
        """Deep merge two dictionaries, with custom values taking precedence."""
        result = default.copy()
        
        for key, value in custom.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # Recursively merge nested dictionaries
                result[key] = self._deep_merge(result[key], value)
            else:
                # Override or add the custom value
                result[key] = value
                
        return result
    
    def _apply_env_overrides(self, config: dict) -> dict:
        """Apply environment variable overrides to config."""
        # LLM provider override
        if os.getenv('LLM_PROVIDER'):
            config['llm_provider'] = os.getenv('LLM_PROVIDER')
        
        # Debug mode override
        if os.getenv('DEBUG'):
            config['debug'] = os.getenv('DEBUG').lower() in ('true', '1', 'yes')
        
        # AWS region override
        if os.getenv('AWS_REGION'):
            config['bedrock']['region'] = os.getenv('AWS_REGION')
        
        # Bedrock model ID override
        if os.getenv('AWS_BEDROCK_MODEL_ID'):
            config['bedrock']['model_id'] = os.getenv('AWS_BEDROCK_MODEL_ID')
        
        # SSL verification override
        if os.getenv('AWS_VERIFY_SSL'):
            config['bedrock']['verify_ssl'] = os.getenv('AWS_VERIFY_SSL').lower() in ('true', '1', 'yes')
        
        # Cache enabled override
        if os.getenv('CACHE_ENABLED'):
            config['cache']['enabled'] = os.getenv('CACHE_ENABLED').lower() in ('true', '1', 'yes')
        
        return config
    
    def get_template(self, category: str, name: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Get a specific template from config and optionally format it with context.
        
        Args:
            category: Template category ('prompts' or 'docs')
            name: Template name
            context: Optional context for formatting
            
        Returns:
            The template string, optionally formatted with context
        """
        if category not in self.config['templates'] or name not in self.config['templates'][category]:
            logging.warning(f"Template {category}/{name} not found in config")
            return f"Template {category}/{name} not found"
        
        template = self.config['templates'][category][name]
        
        if context:
            try:
                return template.format(**context)
            except KeyError as e:
                logging.warning(f"Missing key in template formatting: {e}")
                return template
        
        return template
    
    def get_ollama_config(self) -> Dict[str, Any]:
        """Get Ollama-specific configuration."""
        return self.config['ollama']
    
    def get_bedrock_config(self) -> Dict[str, Any]:
        """Get Bedrock-specific configuration."""
        return self.config['bedrock']
    
    def get_cache_config(self) -> Dict[str, Any]:
        """Get cache-specific configuration."""
        return self.config['cache']

def load_config(config_path: Path) -> dict:
    """Load configuration from YAML file."""
    config_manager = ConfigManager(config_path)
    return config_manager.config 