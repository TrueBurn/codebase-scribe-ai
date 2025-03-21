from typing import Dict, Any, Type, Optional, ClassVar, Mapping, Union
from .base_llm import BaseLLMClient
from .ollama import OllamaClient
from .bedrock import BedrockClient
import logging
from types import TracebackType

from src.utils.config_class import ScribeConfig
from src.utils.config_utils import config_to_dict, dict_to_config

class LLMClientFactoryError(Exception):
    """Base exception for LLM client factory errors."""
    pass

class ConfigValidationError(LLMClientFactoryError):
    """Exception raised when configuration validation fails."""
    pass

class ClientInitializationError(LLMClientFactoryError):
    """Exception raised when client initialization fails."""
    pass

class LLMClientFactory:
    """
    Factory for creating LLM clients.
    
    This factory creates and initializes LLM clients based on configuration.
    
    Supported providers:
    - 'ollama': Uses the local Ollama instance (default)
    - 'bedrock': Uses AWS Bedrock service
    
    Example:
        ```python
        config = {
            'llm_provider': 'ollama',
            'ollama': {
                'base_url': 'http://localhost:11434',
                'max_tokens': 4096
            }
        }
        
        # Create the client using the factory
        llm_client = await LLMClientFactory.create_client(config)
        ```
    """
    
    # Registry of available client types
    _client_registry: ClassVar[Dict[str, Type[BaseLLMClient]]] = {
        'ollama': OllamaClient,
        'bedrock': BedrockClient
    }
    
    @classmethod
    def register_client_type(cls, provider_name: str, client_class: Type[BaseLLMClient]) -> None:
        """
        Register a new client type with the factory.
        
        Args:
            provider_name: The name of the provider (used in configuration)
            client_class: The client class to instantiate for this provider
            
        Example:
            ```python
            class NewProviderClient(BaseLLMClient):
                # Implementation here
                pass
                
            LLMClientFactory.register_client_type('new_provider', NewProviderClient)
            ```
        """
        cls._client_registry[provider_name.lower()] = client_class
        logging.info(f"Registered new LLM client type: {provider_name}")
    
    @classmethod
    def validate_config(cls, config: Union[ScribeConfig, Dict[str, Any]]) -> bool:
        """
        Validate the configuration.
        
        Args:
            config: The configuration (ScribeConfig or dictionary)
            
        Returns:
            bool: True if configuration is valid
            
        Raises:
            ConfigValidationError: If configuration is invalid
        """
        # Convert to ScribeConfig if it's a dictionary
        if isinstance(config, dict):
            try:
                config = dict_to_config(config)
            except Exception as e:
                raise ConfigValidationError(f"Invalid configuration format: {e}")
        elif not isinstance(config, ScribeConfig):
            raise ConfigValidationError(f"Configuration must be a ScribeConfig instance or dictionary, got {type(config)}")
        
        # Check if provider is valid
        provider = config.llm_provider.lower()
        if provider not in cls._client_registry:
            raise ConfigValidationError(
                f"Invalid provider: {provider}. "
                f"Supported providers: {', '.join(cls._client_registry.keys())}"
            )
                
        return True
    
    @classmethod
    async def create_client(cls, config: Union[ScribeConfig, Dict[str, Any]]) -> BaseLLMClient:
        """
        Create and initialize an LLM client based on configuration.
        
        Args:
            config: Configuration (ScribeConfig or dictionary) with provider and client-specific settings
            
        Returns:
            BaseLLMClient: Initialized LLM client
            
        Raises:
            ConfigValidationError: If configuration is invalid
            ClientInitializationError: If client initialization fails
        """
        # Convert to ScribeConfig if it's a dictionary
        if isinstance(config, dict):
            config_dict = config
            config = dict_to_config(config)
        else:
            config_dict = config_to_dict(config)
            
        # Validate configuration
        try:
            cls.validate_config(config)
        except ConfigValidationError as e:
            logging.error(f"Configuration validation failed: {e}")
            raise
            
        provider = config.llm_provider.lower()
        
        # Add debug logging to see what provider is being selected
        if config.debug:
            logging.info(f"Creating LLM client with provider: {provider}")
            logging.info(f"Config keys: {list(config_dict.keys())}")
        
        if provider == 'bedrock':
            try:
                if config.debug:
                    logging.info("Initializing Bedrock client...")
                client = BedrockClient(config_dict)  # Pass dict for backward compatibility
                await client.initialize()
                if config.debug:
                    logging.info("Bedrock client initialized successfully")
                return client
            except Exception as e:
                error_msg = f"Error initializing Bedrock client: {e}"
                logging.error(error_msg)
                print(f"\n{error_msg}")
                print("Falling back to Ollama client...")
                provider = 'ollama'
        
        # Default to Ollama
        if config.debug:
            logging.info("Initializing Ollama client...")
            
        try:
            client = OllamaClient(config_dict)  # Pass dict for backward compatibility
            await client.initialize()
            return client
        except Exception as e:
            error_msg = f"Error initializing Ollama client: {e}"
            logging.error(error_msg)
            raise ClientInitializationError(error_msg) from e