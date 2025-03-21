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
    
    # Debug logging
    import logging
    logging.debug(f"Loaded config from {config_path}")
    if 'cache' in config_dict:
        logging.debug(f"Cache config: {config_dict['cache']}")
        logging.debug(f"Cache location: {config_dict['cache'].get('location', 'default')}")
    
    # Convert to ScribeConfig
    config = ScribeConfig.from_dict(config_dict)
    
    # Debug logging
    if hasattr(config, 'cache'):
        logging.debug(f"ScribeConfig cache location: {config.cache.location}")
    
    return config

def update_config_with_args(config: Union[Dict[str, Any], ScribeConfig], args: Any) -> ScribeConfig:
    """
    Update configuration with command-line arguments.
    
    Args:
        config: ScribeConfig instance or dictionary
        args: Command-line arguments
        
    Returns:
        Updated ScribeConfig instance
    """
    import logging
    
    # Debug logging
    logging.debug(f"Updating config with args")
    
    # Create a dictionary from the current config
    if isinstance(config, dict):
        config_dict = config
        logging.debug(f"Config is a dictionary")
    else:
        config_dict = config.to_dict()
        logging.debug(f"Config is a ScribeConfig instance")
    
    # Debug logging
    if 'cache' in config_dict:
        logging.debug(f"Before update - Cache config: {config_dict['cache']}")
        logging.debug(f"Before update - Cache location: {config_dict['cache'].get('location', 'default')}")
    
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
    
    # Debug logging
    if 'cache' in config_dict:
        logging.debug(f"After update - Cache config: {config_dict['cache']}")
        logging.debug(f"After update - Cache location: {config_dict['cache'].get('location', 'default')}")
    
    # Convert back to ScribeConfig
    config = ScribeConfig.from_dict(config_dict)
    
    # Debug logging
    if hasattr(config, 'cache'):
        logging.debug(f"After conversion - ScribeConfig cache location: {config.cache.location}")
    
    return config


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