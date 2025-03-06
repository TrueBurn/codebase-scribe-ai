from typing import Dict, Any
from .base_llm import BaseLLMClient
from .ollama import OllamaClient
from .bedrock import BedrockClient
import logging

class LLMClientFactory:
    """Factory for creating LLM clients."""
    
    @staticmethod
    async def create_client(config: Dict[str, Any]) -> BaseLLMClient:
        """Create and initialize an LLM client based on configuration."""
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
        client = OllamaClient(config)
        await client.initialize()
        return client 