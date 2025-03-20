# LLM Clients

This document provides detailed information about the LLM (Large Language Model) clients used in the Codebase Scribe AI project.

## Table of Contents
- [Overview](#overview)
- [BaseLLMClient](#basellmclient)
- [OllamaClient](#ollamaclient)
- [BedrockClient](#bedrockclient)
- [LLMClientFactory](#llmclientfactory)
- [LLM Utilities](#llm-utilities)
- [Usage Examples](#usage-examples)
- [Extending with New Providers](#extending-with-new-providers)

## Overview

The LLM clients provide a unified interface for interacting with different language model providers. The system uses an abstract base class (`BaseLLMClient`) that defines the interface, with concrete implementations for specific providers like Ollama and AWS Bedrock.

```mermaid
graph TD
    A[BaseLLMClient] --> B[OllamaClient]
    A[BaseLLMClient] --> C[BedrockClient]
    D[LLMClientFactory] --> B
    D[LLMClientFactory] --> C
```

## BaseLLMClient

The `BaseLLMClient` is an abstract base class that defines the interface for all LLM clients. It provides a common set of methods that must be implemented by concrete subclasses.

### Key Features

- Version tracking for API compatibility
- Input validation methods
- Token counting and management
- Comprehensive documentation with examples
- Type hints for better IDE support

### Core Methods

```python
class BaseLLMClient(ABC):
    """
    Base abstract class for LLM clients.
    
    This class defines the interface that all LLM client implementations must follow.
    It provides abstract methods for interacting with language models to generate
    documentation and analyze code.
    
    Version: 1.0.0
    """
    
    VERSION = "1.0.0"
    
    def __init__(self):
        """Initialize the base client."""
        self.token_counter = None
        self.project_structure = None
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the client."""
        pass
    
    @abstractmethod
    def init_token_counter(self) -> None:
        """Initialize the token counter for this client."""
        pass
    
    def validate_input(self, text: str) -> bool:
        """Validate input text before sending to the LLM."""
        if not text or not isinstance(text, str):
            return False
        return True
    
    def validate_file_manifest(self, file_manifest: Dict[str, Any]) -> bool:
        """Validate the file manifest structure."""
        if not isinstance(file_manifest, dict):
            return False
        return True
    
    @abstractmethod
    async def generate_summary(self, prompt: str) -> Optional[str]:
        """Generate a summary for a file's content."""
        pass
    
    # ... other abstract methods
```

## OllamaClient

The `OllamaClient` is a concrete implementation of `BaseLLMClient` that interacts with the Ollama API for local LLM processing.

### Key Features

- Local model execution
- Interactive model selection
- Automatic token management
- Retry logic for resilience
- Progress tracking

### Implementation Details

```python
class OllamaClient(BaseLLMClient):
    """Handles all interactions with local Ollama instance."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        
        # Get Ollama config with defaults
        ollama_config = config.get('ollama', {})
        self.base_url = ollama_config.get('base_url', 'http://localhost:11434')
        self.max_tokens = ollama_config.get('max_tokens', 4096)
        self.retries = ollama_config.get('retries', 3)
        self.retry_delay = ollama_config.get('retry_delay', 1.0)
        self.timeout = ollama_config.get('timeout', 30)
        self.temperature = ollama_config.get('temperature', 0)
        self.client = AsyncClient(host=self.base_url)
        self.prompt_template = PromptTemplate(config.get('template_path'))
        self.debug = config.get('debug', False)
        self.available_models = []
        self.selected_model = None
```

## BedrockClient

The `BedrockClient` is a concrete implementation of `BaseLLMClient` that interacts with AWS Bedrock for enterprise-grade LLM processing.

### Key Features

- AWS Bedrock integration
- Environment variable support
- SSL verification configuration
- Concurrency control
- Automatic token management

### Implementation Details

```python
class BedrockClient(BaseLLMClient):
    """Handles all interactions with AWS Bedrock."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        
        # Load environment variables from .env file
        load_dotenv()
        
        # Get Bedrock config with defaults
        bedrock_config = config.get('bedrock', {})
        
        # Use environment variables if available, otherwise use config
        self.region = os.getenv('AWS_REGION') or bedrock_config.get('region', 'us-east-1')
        self.model_id = os.getenv('AWS_BEDROCK_MODEL_ID') or bedrock_config.get(
            'model_id', 'us.anthropic.claude-3-5-sonnet-20241022-v2:0'
        )
```

## LLMClientFactory

The `LLMClientFactory` is responsible for creating the appropriate LLM client based on configuration. It uses a registration pattern to support extensibility and includes configuration validation.

### Key Features

- Client registration pattern for extensibility
- Configuration validation
- Specific error types for better error handling
- Fallback mechanism from Bedrock to Ollama

### Implementation

```python
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
    """
    
    # Registry of available client types
    _client_registry: ClassVar[Dict[str, Type[BaseLLMClient]]] = {
        'ollama': OllamaClient,
        'bedrock': BedrockClient
    }
    
    @classmethod
    def register_client_type(cls, provider_name: str, client_class: Type[BaseLLMClient]) -> None:
        """Register a new client type with the factory."""
        cls._client_registry[provider_name.lower()] = client_class
        logging.info(f"Registered new LLM client type: {provider_name}")
    
    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> bool:
        """Validate the configuration dictionary."""
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
        # ...
        
        return True
    
    @classmethod
    async def create_client(cls, config: Dict[str, Any]) -> BaseLLMClient:
        """Create and initialize an LLM client based on configuration."""
        # Validate configuration
        try:
            cls.validate_config(config)
        except ConfigValidationError as e:
            logging.error(f"Configuration validation failed: {e}")
            raise
            
        provider = config.get('llm_provider', 'ollama').lower()
        
        if provider == 'bedrock':
            try:
                client = BedrockClient(config)
                await client.initialize()
                return client
            except Exception as e:
                error_msg = f"Error initializing Bedrock client: {e}"
                logging.error(error_msg)
                print(f"\n{error_msg}")
                print("Falling back to Ollama client...")
                provider = 'ollama'
        
        # Default to Ollama
        try:
            client = OllamaClient(config)
            await client.initialize()
            return client
        except Exception as e:
            error_msg = f"Error initializing Ollama client: {e}"
            logging.error(error_msg)
            raise ClientInitializationError(error_msg) from e
```

## LLM Utilities

The `llm_utils.py` module provides shared utility functions used by all LLM clients. These utilities handle common tasks like formatting project structure, analyzing dependencies, and processing LLM responses.

### Key Features

- Project structure formatting
- Dependency analysis
- File ordering optimization
- Markdown formatting fixes
- Configurable vendor file filtering

### Core Utilities

The module provides the following utility functions:

#### Project Structure Formatting

```python
def format_project_structure(file_manifest: Dict[str, Dict], debug: bool = False) -> str:
    """
    Build a tree-like project structure string from file manifest.
    
    Args:
        file_manifest: Dictionary mapping file paths to file information
        debug: Whether to print debug information
        
    Returns:
        A formatted string representing the project structure
    """
```

This function creates a hierarchical tree representation of the project's file structure, making it easier for LLMs to understand the codebase organization.

#### Dependency Analysis

```python
def find_common_dependencies(file_manifest: Dict[str, Dict], debug: bool = False) -> str:
    """
    Extract common dependencies from file manifest.
    
    Args:
        file_manifest: Dictionary mapping file paths to file information
        debug: Whether to print debug information
        
    Returns:
        A formatted string listing detected dependencies
    """
```

This function analyzes package.json and requirements.txt files to identify project dependencies, helping LLMs understand the project's technology stack.

#### Key Component Identification

```python
def identify_key_components(file_manifest: Dict[str, Dict], debug: bool = False,
                           max_components: int = DEFAULT_MAX_COMPONENTS) -> str:
    """
    Identify key components from file manifest.
    
    Args:
        file_manifest: Dictionary mapping file paths to file information
        debug: Whether to print debug information
        max_components: Maximum number of key components to display
        
    Returns:
        A formatted string listing key components
    """
```

This function identifies the most important directories in the project based on file count, helping LLMs focus on the core components.

#### Markdown Formatting

```python
def fix_markdown_issues(content: str) -> str:
    """
    Fix common markdown formatting issues before returning content.
    
    Args:
        content: The markdown content to fix
        
    Returns:
        The fixed markdown content
    """
```

This function corrects common markdown formatting issues in LLM-generated content, ensuring consistent and well-formatted documentation.

#### File Order Optimization

```python
def prepare_file_order_data(project_files: Dict[str, Dict], debug: bool = False,
                           vendor_patterns: List[str] = DEFAULT_VENDOR_PATTERNS) -> Tuple[Dict[str, Dict], Dict[str, Dict], Dict[str, Dict]]:
    """
    Prepare data for file order optimization.
    
    Args:
        project_files: Dictionary mapping file paths to file information
        debug: Whether to print debug information
        vendor_patterns: List of regex patterns to identify vendor/resource files
        
    Returns:
        A tuple containing (core_files, resource_files, files_info)
    """
```

This function separates core project files from vendor/resource files, enabling more efficient processing by LLMs.

```python
def process_file_order_response(content: str, core_files: Dict[str, Dict], resource_files: Dict[str, Dict], debug: bool = False) -> List[str]:
    """
    Process LLM response to extract file order.
    
    Args:
        content: The LLM response content to process
        core_files: Dictionary of core files to order
        resource_files: Dictionary of resource files to append at the end
        debug: Whether to print debug information
        
    Returns:
        A list of file paths in the extracted order
    """
```

This function processes LLM responses to extract an optimal file processing order, improving the quality of generated documentation.

### Configuration Constants

The module defines configurable constants for customization:

```python
# Maximum number of key components to display
DEFAULT_MAX_COMPONENTS = 10

# Default vendor patterns for file filtering
DEFAULT_VENDOR_PATTERNS = [
    r'[\\/]bootstrap[\\/]',           # Bootstrap files
    r'[\\/]vendor[\\/]',              # Vendor directories
    r'[\\/]wwwroot[\\/]lib[\\/]',     # Library resources
    r'\.min\.(js|css|map)$',          # Minified files
    r'\.css\.map$',                   # Source maps
    r'\.ico$|\.png$|\.jpg$|\.gif$',   # Images
    r'[\\/]node_modules[\\/]',        # Node modules
    r'[\\/]dist[\\/]',                # Distribution files
    r'[\\/]packages[\\/]',            # Package files
    r'[\\/]PublishProfiles[\\/]',     # Publish profiles
    r'\.pubxml(\.user)?$',            # Publish XML files
    r'\.csproj(\.user)?$',            # Project files
    r'\.sln$'                         # Solution files
]
```

These constants can be adjusted to customize the behavior of the utility functions.

## Usage Examples

### Basic Usage

```python
# Create and initialize an LLM client
config = {
    'llm_provider': 'ollama',
    'ollama': {
        'base_url': 'http://localhost:11434',
        'max_tokens': 4096
    }
}

# Create the client using the factory
llm_client = await LLMClientFactory.create_client(config)

# Generate a summary for a file
summary = await llm_client.generate_summary("def hello(): print('Hello world')")

# Generate project overview
overview = await llm_client.generate_project_overview(file_manifest)
```

### Using AWS Bedrock

```python
# Configure for AWS Bedrock
config = {
    'llm_provider': 'bedrock',
    'bedrock': {
        'region': 'us-east-1',
        'model_id': 'us.anthropic.claude-3-5-sonnet-20241022-v2:0'
    }
}

# Create the client using the factory
llm_client = await LLMClientFactory.create_client(config)

# Use the client as before
summary = await llm_client.generate_summary("def hello(): print('Hello world')")
```

## Extending with New Providers

To add a new LLM provider:

1. Create a new class that inherits from `BaseLLMClient`
2. Implement all abstract methods
3. Register the new provider with the `LLMClientFactory`

Example:

```python
class NewProviderClient(BaseLLMClient):
    """Handles interactions with a new LLM provider."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        # Initialize with provider-specific configuration
        
    async def initialize(self) -> None:
        # Implementation
        pass
        
    def init_token_counter(self) -> None:
        # Implementation
        pass
        
    # Implement other abstract methods
```

Then register the new client type with the factory:

```python
# Register the new provider
LLMClientFactory.register_client_type('new_provider', NewProviderClient)

# Now you can use it with the factory
config = {
    'llm_provider': 'new_provider',
    'new_provider': {
        # Provider-specific configuration
    }
}

# Create the client using the factory
llm_client = await LLMClientFactory.create_client(config)