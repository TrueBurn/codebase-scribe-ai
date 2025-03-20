from typing import Dict, Any, Type, Optional, ClassVar, Mapping
from .base_llm import BaseLLMClient
from .ollama import OllamaClient
from .bedrock import BedrockClient
import logging
from types import TracebackType

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
    def validate_config(cls, config: Dict[str, Any]) -> bool:
        """
        Validate the configuration dictionary.
        
        Args:
            config: The configuration dictionary
            
        Returns:
            bool: True if configuration is valid
            
        Raises:
            ConfigValidationError: If configuration is invalid
        """
        if not isinstance(config, dict):
            raise ConfigValidationError("Configuration must be a dictionary")
        
        # Check if provider is valid
        provider = config.get('llm_provider', 'ollama').lower()
        if provider not in cls._client_registry:
            raise ConfigValidationError(
                f"Invalid provider: {provider}. "
                f"Supported providers: {', '.join(cls._client_registry.keys())}"
            )
            
        # Provider-specific validation
        if provider == 'bedrock':
            bedrock_config = config.get('bedrock', {})
            if not isinstance(bedrock_config, dict):
                raise ConfigValidationError("Bedrock configuration must be a dictionary")
                
        elif provider == 'ollama':
            ollama_config = config.get('ollama', {})
            if not isinstance(ollama_config, dict):
                raise ConfigValidationError("Ollama configuration must be a dictionary")
                
        return True
    
    @classmethod
    async def create_client(cls, config: Dict[str, Any]) -> BaseLLMClient:
        """
        Create and initialize an LLM client based on configuration.
        
        Args:
            config: Configuration dictionary with provider and client-specific settings
            
        Returns:
            BaseLLMClient: Initialized LLM client
            
        Raises:
            ConfigValidationError: If configuration is invalid
            ClientInitializationError: If client initialization fails
        """
        # Validate configuration
        try:
            cls.validate_config(config)
        except ConfigValidationError as e:
            logging.error(f"Configuration validation failed: {e}")
            raise
            
        provider = config.get('llm_provider', 'ollama').lower()
        
        # Add debug logging to see what provider is being selected
        debug = config.get('debug', False)
        if debug:
            logging.info(f"Creating LLM client with provider: {provider}")
            logging.info(f"Config keys: {list(config.keys())}")
        
        if provider == 'bedrock':
            try:
                if debug:
                    logging.info("Initializing Bedrock client...")
                client = BedrockClient(config)
                await client.initialize()
                if debug:
                    logging.info("Bedrock client initialized successfully")
                return client
            except Exception as e:
                error_msg = f"Error initializing Bedrock client: {e}"
                logging.error(error_msg)
                print(f"\n{error_msg}")
                print("Falling back to Ollama client...")
                provider = 'ollama'
        
        # Default to Ollama
        if debug:
            logging.info("Initializing Ollama client...")
            
        try:
            client = OllamaClient(config)
            await client.initialize()
            return client
        except Exception as e:
            error_msg = f"Error initializing Ollama client: {e}"
            logging.error(error_msg)
            raise ClientInitializationError(error_msg) from e