#!/usr/bin/env python3

"""
Utilities for working with configuration in codebase-scribe.

This module provides functions to bridge between the old dictionary-based
configuration and the new ScribeConfig class-based configuration.
"""

from pathlib import Path
from typing import Dict, Any, Union, Optional

from src.utils.config import load_config as load_config_dict
from src.utils.config_class import ScribeConfig


def load_config(config_path: Union[str, Path]) -> ScribeConfig:
    """
    Load configuration from YAML file and convert to ScribeConfig.
    
    Args:
        config_path: Path to the YAML configuration file
        
    Returns:
        ScribeConfig instance
    """
    # Load the config as a dictionary first
    config_dict = load_config_dict(str(config_path))
    
    # Convert to ScribeConfig
    return ScribeConfig.from_dict(config_dict)

def update_config_with_args(config: Union[Dict[str, Any], ScribeConfig], args: Any) -> ScribeConfig:
    """
    Update configuration with command-line arguments.
    
    Args:
        config: ScribeConfig instance or dictionary
        args: Command-line arguments
        
    Returns:
        Updated ScribeConfig instance
    """
    # Create a dictionary from the current config
    if isinstance(config, dict):
        config_dict = config
    else:
        config_dict = config.to_dict()
    
    # Update with command-line arguments
    if hasattr(args, 'debug'):
        config_dict['debug'] = args.debug
    
    if hasattr(args, 'test_mode'):
        config_dict['test_mode'] = args.test_mode
    
    if hasattr(args, 'no_cache'):
        config_dict['no_cache'] = args.no_cache
    
    if hasattr(args, 'optimize_order'):
        config_dict['optimize_order'] = args.optimize_order
    
    if hasattr(args, 'llm_provider') and args.llm_provider:
        config_dict['llm_provider'] = args.llm_provider
    
    # Convert back to ScribeConfig
    return ScribeConfig.from_dict(config_dict)


def config_to_dict(config: Union[ScribeConfig, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Convert configuration to dictionary.
    
    Args:
        config: ScribeConfig instance or dictionary
        
    Returns:
        Configuration dictionary
    """
    if isinstance(config, ScribeConfig):
        return config.to_dict()
    return config


def dict_to_config(config_dict: Dict[str, Any]) -> ScribeConfig:
    """
    Convert dictionary to ScribeConfig.
    
    Args:
        config_dict: Configuration dictionary
        
    Returns:
        ScribeConfig instance
    """
    return ScribeConfig.from_dict(config_dict)


def get_concurrency(config: Union[ScribeConfig, Dict[str, Any]]) -> int:
    """
    Get concurrency setting from configuration.
    
    Args:
        config: ScribeConfig instance or dictionary
        
    Returns:
        Concurrency setting
    """
    if isinstance(config, ScribeConfig):
        return config.get_concurrency()
    
    # Handle dictionary-based config
    llm_provider = config.get('llm_provider', 'ollama').lower()
    if llm_provider == 'bedrock':
        return config.get('bedrock', {}).get('concurrency', 1)
    else:
        return config.get('ollama', {}).get('concurrency', 1)