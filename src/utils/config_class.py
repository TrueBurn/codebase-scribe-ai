#!/usr/bin/env python3

"""
Configuration class for codebase-scribe.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any


@dataclass
class BlacklistConfig:
    """Configuration for file and directory blacklisting."""
    extensions: List[str] = field(default_factory=lambda: ['.pyc', '.pyo', '.pyd'])
    path_patterns: List[str] = field(default_factory=lambda: ['__pycache__', '\.git'])


@dataclass
class CacheConfig:
    """Configuration for caching."""
    enabled: bool = True
    ttl: int = 3600  # Time to live in seconds
    max_size: int = 1048576  # Max cache size in bytes
    location: str = "repo"  # Cache location ('repo' or 'home')
    directory: str = ".test_cache"  # Cache directory name
    global_directory: str = ".test_global_cache"  # Global cache directory name
    hash_algorithm: str = "sha256"  # Hash algorithm for file content hashing


@dataclass
class LLMProviderConfig:
    """Base configuration for LLM providers."""
    concurrency: int = 1


@dataclass
class OllamaConfig(LLMProviderConfig):
    """Configuration for Ollama LLM provider."""
    model: str = "llama2"
    base_url: str = "http://localhost:11434"
    timeout: int = 60
    max_tokens: int = 2048
    retries: int = 5
    retry_delay: float = 2.0
    temperature: float = 0.5


@dataclass
class BedrockConfig(LLMProviderConfig):
    """Configuration for Bedrock LLM provider."""
    model_id: str = "test-model-id"
    region: str = "us-west-2"
    concurrency: int = 3
    timeout: int = 60
    max_tokens: int = 2048
    retries: int = 5
    retry_delay: float = 2.0
    verify_ssl: bool = False
    temperature: float = 0.0


@dataclass
class ScribeConfig:
    """Main configuration class for codebase-scribe."""
    # General settings
    debug: bool = False
    test_mode: bool = False
    no_cache: bool = False
    optimize_order: bool = False
    preserve_existing: bool = True
    
    # Repository settings
    github_repo_id: Optional[str] = None
    
    # Blacklist settings
    blacklist: BlacklistConfig = field(default_factory=BlacklistConfig)
    
    # Cache settings
    cache: CacheConfig = field(default_factory=CacheConfig)
    
    # LLM provider settings
    llm_provider: str = "ollama"
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    bedrock: BedrockConfig = field(default_factory=BedrockConfig)
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'ScribeConfig':
        """Create a ScribeConfig instance from a dictionary.
        
        Args:
            config_dict: Dictionary containing configuration values
            
        Returns:
            A ScribeConfig instance
        """
        config = cls()
        
        # Set general settings
        config.debug = config_dict.get('debug', False)
        config.test_mode = config_dict.get('test_mode', False)
        config.no_cache = config_dict.get('no_cache', False)
        config.optimize_order = config_dict.get('optimize_order', False)
        config.github_repo_id = config_dict.get('github_repo_id')
        
        # Set blacklist settings
        if 'blacklist' in config_dict:
            blacklist_dict = config_dict['blacklist']
            config.blacklist = BlacklistConfig(
                extensions=blacklist_dict.get('extensions', ['.pyc', '.pyo', '.pyd']),
                path_patterns=blacklist_dict.get('path_patterns', ['__pycache__', '\.git'])
            )
        
        # Set cache settings
        if 'cache' in config_dict:
            cache_dict = config_dict['cache']
            config.cache = CacheConfig(
                enabled=not config.no_cache,
                ttl=cache_dict.get('ttl', 3600),
                max_size=cache_dict.get('max_size', 1048576)
            )
        
        # Set LLM provider settings
        config.llm_provider = config_dict.get('llm_provider', 'ollama')
        
        # Set Ollama settings
        if 'ollama' in config_dict:
            ollama_dict = config_dict['ollama']
            config.ollama = OllamaConfig(
                concurrency=ollama_dict.get('concurrency', 1),
                model=ollama_dict.get('model', 'llama2'),
                base_url=ollama_dict.get('base_url', 'http://localhost:11434'),
                timeout=ollama_dict.get('timeout', 60)
            )
        
        # Set Bedrock settings
        if 'bedrock' in config_dict:
            bedrock_dict = config_dict['bedrock']
            config.bedrock = BedrockConfig(
                concurrency=bedrock_dict.get('concurrency', 1),
                model_id=bedrock_dict.get('model_id', 'anthropic.claude-v2'),
                region=bedrock_dict.get('region', 'us-east-1'),
                timeout=bedrock_dict.get('timeout', 120)
            )
        
        return config
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the ScribeConfig instance to a dictionary.
        
        Returns:
            A dictionary representation of the configuration
        """
        return {
            'debug': self.debug,
            'test_mode': self.test_mode,
            'no_cache': self.no_cache,
            'optimize_order': self.optimize_order,
            'github_repo_id': self.github_repo_id,
            'blacklist': {
                'extensions': self.blacklist.extensions,
                'path_patterns': self.blacklist.path_patterns
            },
            'cache': {
                'enabled': self.cache.enabled,
                'ttl': self.cache.ttl,
                'max_size': self.cache.max_size
            },
            'llm_provider': self.llm_provider,
            'ollama': {
                'concurrency': self.ollama.concurrency,
                'model': self.ollama.model,
                'base_url': self.ollama.base_url,
                'timeout': self.ollama.timeout
            },
            'bedrock': {
                'concurrency': self.bedrock.concurrency,
                'model_id': self.bedrock.model_id,
                'region': self.bedrock.region,
                'timeout': self.bedrock.timeout
            }
        }
    
    def get_concurrency(self) -> int:
        """Get the concurrency setting based on the LLM provider.
        
        Returns:
            The concurrency setting
        """
        if self.llm_provider.lower() == 'bedrock':
            return self.bedrock.concurrency
        else:
            return self.ollama.concurrency