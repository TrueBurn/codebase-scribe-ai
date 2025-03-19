# Configuration System

This document provides detailed information about the configuration system used in the Codebase Scribe AI project.

## Overview

The configuration system is designed to be flexible and extensible, allowing users to customize the behavior of the application through a YAML configuration file. The system supports:

- Default configuration values
- Custom overrides from YAML files
- Environment variable overrides
- Type validation
- Configuration dumping for debugging

## Configuration File

The default configuration file is `config.yaml` in the project root directory. You can specify a different configuration file using the `--config` command-line argument.

```bash
python codebase_scribe.py --repo ./my-project --config custom_config.yaml
```

## Configuration Schema

The configuration file uses a YAML format with the following structure:

```yaml
# LLM provider configuration
llm_provider: "ollama"  # or "bedrock"
debug: false  # Enable debug logging

# Ollama-specific configuration
ollama:
  base_url: "http://localhost:11434"
  max_tokens: 4096
  retries: 3
  retry_delay: 1.0
  timeout: 30
  concurrency: 1  # Number of concurrent requests
  temperature: 0.0  # 0.0 = deterministic output

# AWS Bedrock-specific configuration
bedrock:
  region: "us-east-1"
  model_id: "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
  max_tokens: 8192
  retries: 3
  retry_delay: 1.0
  timeout: 120  # Default to 2 minutes
  verify_ssl: true
  concurrency: 5  # Default to moderate concurrency
  temperature: 0.0  # Default to deterministic output

# Cache configuration
cache:
  enabled: true
  directory: ".cache"
  location: "home"  # "repo" or "home"
  hash_algorithm: "md5"  # "md5", "sha1", or "sha256"
  global_directory: ".readme_generator_cache"  # Used when location is "home"

# Processing options
optimize_order: false
preserve_existing: true
no_cache: false
test_mode: false

# File filtering
blacklist:
  extensions: [".txt", ".log"]
  path_patterns:
    - "/temp/"
    - "/cache/"
    - "/node_modules/"
    - "/__pycache__/"
    - "/wwwroot/"
    - "^aql/"
    - "aql/"
    - "/aql/"

# Templates for prompts and documentation
templates:
  prompts:
    file_summary: |
      Analyze the following code file and provide a clear, concise summary:
      File: {file_path}
      Type: {file_type}
      Context: {context}

      Code:
      {code}
    # Other prompt templates...
  docs:
    readme: |
      # {project_name}

      {project_overview}

      ## Documentation

      {usage}

      ## Development

      {contributing}

      ## License

      {license}
    # Other documentation templates...
```

## Environment Variables

The configuration system supports overriding settings using environment variables. The following environment variables are supported:

| Environment Variable | Configuration Setting | Description |
|---------------------|------------------------|-------------|
| `LLM_PROVIDER` | `llm_provider` | LLM provider to use ("ollama" or "bedrock") |
| `DEBUG` | `debug` | Enable debug logging (true/false) |
| `AWS_REGION` | `bedrock.region` | AWS region for Bedrock |
| `AWS_BEDROCK_MODEL_ID` | `bedrock.model_id` | Bedrock model ID |
| `AWS_VERIFY_SSL` | `bedrock.verify_ssl` | Whether to verify SSL certificates (true/false) |
| `CACHE_ENABLED` | `cache.enabled` | Enable caching (true/false) |

Example:

```bash
export LLM_PROVIDER=bedrock
export AWS_REGION=us-west-2
python codebase_scribe.py --repo ./my-project
```

## Configuration Validation

The configuration system validates the configuration values to ensure they meet the expected types and constraints. If validation fails, the system will log an error and fall back to the default configuration.

Validation checks include:

- LLM provider must be "ollama" or "bedrock"
- Ollama and Bedrock configurations must be dictionaries
- Numeric values must be of the correct type and within valid ranges
- Cache location must be "repo" or "home"

## Using the Configuration System in Code

### Loading Configuration

```python
from src.utils.config import load_config

# Load configuration from default file (config.yaml)
config = load_config("config.yaml")

# Access configuration values
llm_provider = config["llm_provider"]
debug_mode = config["debug"]
```

### Using ConfigManager

```python
from src.utils.config import ConfigManager

# Create a ConfigManager instance
config_manager = ConfigManager("config.yaml")

# Access configuration values
llm_provider = config_manager["llm_provider"]
debug_mode = config_manager.get("debug", False)  # With default value

# Get provider-specific configuration
ollama_config = config_manager.get_ollama_config()
bedrock_config = config_manager.get_bedrock_config()
cache_config = config_manager.get_cache_config()

# Get a template
template = config_manager.get_template("prompts", "file_summary")

# Format a template with context
formatted_template = config_manager.get_template("prompts", "file_summary", {
    "file_path": "src/main.py",
    "file_type": "Python",
    "context": "Main application entry point",
    "code": "print('Hello, world!')"
})

# Dump configuration for debugging
config_dict = config_manager.dump_config("dict")
config_yaml = config_manager.dump_config("yaml")
config_json = config_manager.dump_config("json")
```

## Extending the Configuration System

To add new configuration options:

1. Add the new option to the `DEFAULT_CONFIG` dictionary in `src/utils/config.py`
2. Update the type definitions in `ConfigDict` and related TypedDict classes
3. Add validation for the new option in the `_validate_config` method
4. Add environment variable support in the `_apply_env_overrides` method if needed
5. Update the documentation in this file

## Best Practices

1. **Use the ConfigManager class** instead of directly accessing the configuration dictionary
2. **Provide default values** when getting configuration options
3. **Validate configuration values** before using them
4. **Use environment variables** for sensitive information or deployment-specific settings
5. **Document new configuration options** in this file

## Troubleshooting

### Common Issues

1. **Configuration file not found**
   - Check that the configuration file exists at the specified path
   - The system will fall back to default configuration

2. **Invalid YAML syntax**
   - Check the YAML syntax in your configuration file
   - The system will fall back to default configuration

3. **Validation errors**
   - Check the error message in the logs
   - Ensure configuration values meet the expected types and constraints
   - The system will fall back to default configuration

4. **Environment variables not applied**
   - Check that environment variables are set correctly
   - Environment variables are case-sensitive