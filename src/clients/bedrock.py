# Standard library imports
import asyncio
import json
import logging
import os
import traceback
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

# Third-party imports
import boto3
import botocore
from botocore.config import Config as BotocoreConfig
from dotenv import load_dotenv

# Local imports
from .base_llm import BaseLLMClient
from .message_manager import MessageManager
from .llm_utils import (
    format_project_structure,
    find_common_dependencies,
    identify_key_components,
    get_default_order,
    fix_markdown_issues,
    prepare_file_order_data,
    process_file_order_response
)
from ..analyzers.codebase import CodebaseAnalyzer
from ..utils.prompt_manager import PromptTemplate
from ..utils.progress import ProgressTracker
from ..utils.retry import async_retry
from ..utils.tokens import TokenCounter

# Constants
DEFAULT_REGION = 'us-east-1'
DEFAULT_MODEL_ID = 'us.anthropic.claude-3-7-sonnet-20250219-v1:0'
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TIMEOUT = 120
DEFAULT_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0
DEFAULT_TEMPERATURE = 0
BEDROCK_API_VERSION = "bedrock-2023-05-31"

class BedrockClientError(Exception):
    """Custom exception for Bedrock client errors."""

class BedrockClient(BaseLLMClient):
    """Handles all interactions with AWS Bedrock."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the BedrockClient with the provided configuration.
        
        Args:
            config: Dictionary containing configuration parameters
                - bedrock: Dictionary with Bedrock-specific configuration
                - debug: Boolean to enable debug output
                - template_path: Path to prompt templates
        """
        # Call parent class constructor
        super().__init__()
        
        # Load environment variables from .env file
        load_dotenv()
        
        # Get Bedrock config with defaults
        bedrock_config = config.get('bedrock', {})
        
        # Use environment variables if available, otherwise use config
        self.region = os.getenv('AWS_REGION') or bedrock_config.get('region', DEFAULT_REGION)
        
        # Use environment variable for model_id if available, otherwise use config
        self.model_id = os.getenv('AWS_BEDROCK_MODEL_ID') or bedrock_config.get(
            'model_id', DEFAULT_MODEL_ID
        )
        
        # Print model ID for debugging
        if config.get('debug', False):
            print(f"Using Bedrock model ID: {self.model_id}")
        
        self.max_tokens = bedrock_config.get('max_tokens', DEFAULT_MAX_TOKENS)
        self.retries = bedrock_config.get('retries', DEFAULT_RETRIES)
        self.retry_delay = bedrock_config.get('retry_delay', DEFAULT_RETRY_DELAY)
        self.timeout = bedrock_config.get('timeout', DEFAULT_TIMEOUT)
        self.debug = config.get('debug', False)
        
        # Add concurrency support
        self.concurrency = bedrock_config.get('concurrency', 1)
        self.semaphore = asyncio.Semaphore(self.concurrency)
        
        # Get SSL verification setting from config or environment
        # Environment variable takes precedence over config
        env_verify_ssl = os.getenv('AWS_VERIFY_SSL')
        if env_verify_ssl is not None:
            self.verify_ssl = env_verify_ssl.lower() != 'false'
        else:
            self.verify_ssl = bedrock_config.get('verify_ssl', True)
        
        # Set environment variable for tiktoken SSL verification to match our setting
        if not self.verify_ssl:
            os.environ['TIKTOKEN_VERIFY_SSL'] = 'false'
            if self.debug:
                print("SSL verification disabled for tiktoken")
        
        # Initialize Bedrock client
        self.client = self._initialize_bedrock_client()
        self.prompt_template = PromptTemplate(config.get('template_path'))
        
        # Add temperature setting
        self.temperature = bedrock_config.get('temperature', DEFAULT_TEMPERATURE)
        
    def _initialize_bedrock_client(self) -> boto3.client:
        """
        Initialize the AWS Bedrock client with proper configuration.
        
        Returns:
            boto3.client: Configured Bedrock client
        """
        # AWS SDK will automatically use AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY from env
        return boto3.client(
            'bedrock-runtime',
            region_name=self.region,
            verify=self.verify_ssl,
            config=BotocoreConfig(
                connect_timeout=self.timeout,
                read_timeout=self.timeout,
                retries={'max_attempts': self.retries}
            )
        )
    
    async def validate_aws_credentials(self) -> bool:
        """
        Validate that AWS credentials are properly configured.
        
        Returns:
            bool: True if credentials are valid, False otherwise
        """
        try:
            # Try a simple operation to validate credentials
            await asyncio.to_thread(
                self.client.list_foundation_models
            )
            logging.info("AWS credentials validated successfully")
            return True
        except botocore.exceptions.ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code in ('UnrecognizedClientException', 'AccessDeniedException'):
                logging.error(f"AWS credential validation failed: {error_code}")
                if self.debug:
                    print(f"AWS credential error: {str(e)}")
                return False
            # For other errors, credentials might be valid but other issues exist
            return True
        except Exception as e:
            logging.warning(f"AWS credential validation error: {str(e)}")
            return False
    
    async def initialize(self) -> None:
        """
        Perform async initialization tasks.
        
        Initializes token counter, validates credentials, and sets up project structure.
        
        Raises:
            BedrockClientError: If initialization fails
        """
        try:
            # Initialize token counter
            self.init_token_counter()
            
            print(f"\nInitialized with model: {self.model_id}")
            print(f"Using AWS region: {self.region}")
            print("Starting analysis...\n")
            
            if self.debug:
                print(f"Selected model: {self.model_id}")
                print(f"AWS credentials: {'Found' if os.getenv('AWS_ACCESS_KEY_ID') else 'Not found'} in environment")
                
                # Validate credentials
                is_valid = await self.validate_aws_credentials()
                print(f"AWS credentials valid: {is_valid}")
            
            # Initialize project structure if not already done
            if self.project_structure is None:
                self.project_structure = "Project structure not initialized. Please analyze repository first."
            
        except Exception as e:
            if self.debug:
                print(f"Initialization error: {str(e)}")
            raise BedrockClientError(f"Failed to initialize client: {str(e)}")
    
    def init_token_counter(self) -> None:
        """Initialize the token counter for this client."""
        self.token_counter = TokenCounter(model_name=self.model_id, debug=self.debug)
    
    async def close(self) -> None:
        """
        Clean up resources when the client is no longer needed.
        
        This method should be called when you're done using the client to ensure
        proper cleanup of resources.
        """
        # Cancel any pending tasks
        tasks = [task for task in asyncio.all_tasks()
                if task is not asyncio.current_task() and not task.done()]
        
        for task in tasks:
            task.cancel()
            
        # Wait for tasks to be cancelled
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            
        logging.info("BedrockClient resources cleaned up")
    
    @async_retry(
        retries=3,
        delay=1.0,
        backoff=2.0,
        max_delay=30.0,
        jitter=True,
        exceptions=(ConnectionError, TimeoutError),
    )
    async def generate_summary(self, prompt: str) -> Optional[str]:
        """Generate a summary for a file's content."""
        async with self.semaphore:  # Use semaphore to control concurrency
            try:
                messages = MessageManager.get_file_summary_messages(prompt)
                
                # Use the new token-aware invocation method
                content = await self._invoke_model_with_token_management(messages)
                return content
                
            except Exception as e:
                logging.error(f"Error generating summary: {e}")
                return None
    
    # _update_progress method removed - now using ProgressTracker.update_progress_async
    
    def _fix_markdown_issues(self, content: str) -> str:
        """Fix common markdown formatting issues before returning content."""
        return fix_markdown_issues(content)
    
    @async_retry(
        retries=3,
        delay=1.0,
        backoff=2.0,
        max_delay=30.0,
        jitter=True,
        exceptions=(botocore.exceptions.ClientError, ConnectionError, TimeoutError),
    )
    async def generate_project_overview(self, file_manifest: dict) -> str:
        """Generate project overview based on file manifest."""
        try:
            # Get progress tracker instance
            progress_tracker = ProgressTracker.get_instance(Path("."))
            with progress_tracker.progress_bar(
                total=100,
                desc="Generating project overview",
                bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}'
            ) as pbar:
                # Create progress update task
                update_task = asyncio.create_task(progress_tracker.update_progress_async(pbar))
                
                # Get project name
                project_name = self._derive_project_name(file_manifest)
                
                # Get detected technologies
                tech_report = self._find_common_dependencies(file_manifest)
                
                # Get key components
                key_components = self._identify_key_components(file_manifest)
                
                # Get template content
                template_content = self.prompt_template.get_template("project_overview").format(
                    project_name=project_name,
                    file_count=len(file_manifest),
                    key_components=key_components
                )
                
                # Get messages
                messages = MessageManager.get_project_overview_messages(
                    self.project_structure,
                    tech_report,
                    template_content
                )
                
                # Check token limits and truncate if needed
                if self.token_counter:
                    messages = MessageManager.check_and_truncate_messages(
                        messages, 
                        self.token_counter, 
                        self.model_id
                    )
                
                # Extract system and user content
                system_content = next((msg["content"] for msg in messages if msg["role"] == "system"), "")
                user_content = next((msg["content"] for msg in messages if msg["role"] == "user"), "")
                
                # Update progress
                pbar.update(20)
                
                # Use the helper method to create and invoke the request
                content = await self._create_and_invoke_bedrock_request(system_content, user_content)
                
                # Update progress
                pbar.update(70)
                
                # Update progress
                pbar.update(10)
                
                # Cancel progress update task
                update_task.cancel()
                
                # Fix any markdown issues
                fixed_content = self._fix_markdown_issues(content)
                
                return fixed_content
                
        except Exception as e:
            if self.debug:
                print(f"\nError generating overview: {str(e)}")
            raise
    
    def _format_project_structure(self, file_manifest: dict) -> str:
        """Build a tree-like project structure string."""
        return format_project_structure(file_manifest, self.debug)
    
    def _find_common_dependencies(self, file_manifest: dict) -> str:
        """Extract common dependencies from file manifest."""
        return find_common_dependencies(file_manifest, self.debug)
    
    def _identify_key_components(self, file_manifest: dict) -> str:
        """Identify key components from file manifest."""
        return identify_key_components(file_manifest, self.debug)
    
    def _derive_project_name(self, file_manifest: dict) -> str:
        """Derive project name from repository structure."""
        # Create a temporary analyzer instance to use its method
        temp_analyzer = CodebaseAnalyzer(Path("."), {"debug": self.debug})
        temp_analyzer.file_manifest = file_manifest
        return temp_analyzer.derive_project_name(self.debug)
    
    def set_project_structure(self, structure: str) -> None:
        """
        Set the project structure for use in prompts.
        
        Args:
            structure: String representation of the project structure
        """
        self.project_structure = structure
        if self.debug:
            print(f"Project structure set ({len(structure)} chars)")
            
    def set_project_structure_from_manifest(self, file_manifest: Dict[str, Any]) -> None:
        """
        Set the project structure from a file manifest.
        
        This is a convenience method that formats the file manifest into a
        string representation and then sets it as the project structure.
        
        Args:
            file_manifest: Dictionary mapping file paths to file information
        """
        self.project_structure = self._format_project_structure(file_manifest)
    
    async def _create_and_invoke_bedrock_request(
        self,
        system_content: str,
        user_content: str,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Helper method to create and invoke a Bedrock request with the given content.
        
        Args:
            system_content: System message content
            user_content: User message content
            max_tokens: Maximum tokens to generate (uses default if None)
            
        Returns:
            str: The generated content with markdown issues fixed
            
        Raises:
            Various exceptions from the underlying API call
        """
        # Combine for Claude
        combined_content = f"{system_content}\n\n{user_content}"
        
        # Create proper Bedrock format
        bedrock_messages = [
            {
                "role": "user",
                "content": [{"type": "text", "text": combined_content}]
            }
        ]
        
        # Use provided max_tokens or default
        tokens_to_generate = max_tokens or self.max_tokens
        
        # Invoke model
        response = await asyncio.to_thread(
            self.client.invoke_model,
            body=json.dumps({
                "anthropic_version": BEDROCK_API_VERSION,
                "max_tokens": tokens_to_generate,
                "messages": bedrock_messages,
                "temperature": self.temperature
            }),
            modelId=self.model_id
        )
        
        # Process response
        response_body = json.loads(response.get('body').read())
        content = response_body['content'][0]['text']
        
        # Fix any markdown issues
        return self._fix_markdown_issues(content)
    
    @async_retry(
        retries=3,
        delay=1.0,
        backoff=2.0,
        max_delay=30.0,
        jitter=True,
        exceptions=(ConnectionError, TimeoutError),
    )
    async def generate_architecture_content(self, file_manifest: dict, analyzer) -> str:
        """Generate architecture documentation content with flow diagrams."""
        async with self.semaphore:
            # Get progress tracker instance
            progress_tracker = ProgressTracker.get_instance(Path("."))
            with progress_tracker.progress_bar(
                desc="Generating architecture documentation",
                bar_format='{desc} {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt}',
                ncols=150
            ) as pbar:
                try:
                    update_task = asyncio.create_task(progress_tracker.update_progress_async(pbar))
                    
                    # Ensure project structure is set
                    if not self.project_structure or len(self.project_structure) < 10:
                        self.set_project_structure_from_manifest(file_manifest)
                        if self.debug:
                            print(f"Project structure generated ({len(self.project_structure)} chars)")
                    
                    # Get detected technologies
                    tech_report = self._find_common_dependencies(file_manifest)
                    
                    # Get key components
                    key_components = self._identify_key_components(file_manifest)
                    
                    # Create a summary of file contents for context
                    file_summaries = []
                    
                    # First, categorize files by directory/component
                    file_by_component = {}
                    for path, info in file_manifest.items():
                        if info.get('summary') and not info.get('is_binary', False):
                            directory = str(Path(path).parent)
                            if directory not in file_by_component:
                                file_by_component[directory] = []
                            file_by_component[directory].append((path, info.get('summary', 'No summary available')))
                    
                    # For each component, include a representative sample of files
                    for directory, files in file_by_component.items():
                        # Add component header
                        file_summaries.append(f"## Component: {directory}")
                        
                        # Sort files by potential importance (e.g., longer summaries might be more important)
                        files.sort(key=lambda x: len(x[1]), reverse=True)
                        
                        # Take up to 3 files per component to ensure broad coverage
                        for path, summary in files[:3]:
                            file_summaries.append(f"File: {path}\nSummary: {summary}")
                    
                    file_summaries_text = "\n\n".join(file_summaries)
                    
                    # Get messages from MessageManager
                    messages = MessageManager.get_architecture_content_messages(
                        self.project_structure, 
                        key_components,
                        tech_report
                    )
                    
                    # Add file summaries to the user message
                    for i, msg in enumerate(messages):
                        if msg["role"] == "user":
                            messages[i]["content"] += f"\n\nFile Summaries:\n{file_summaries_text}"
                            break
                    
                    # Extract system and user content
                    system_content = next((msg["content"] for msg in messages if msg["role"] == "system"), "")
                    user_content = next((msg["content"] for msg in messages if msg["role"] == "user"), "")
                    
                    # Use the helper method to create and invoke the request
                    content = await self._create_and_invoke_bedrock_request(system_content, user_content)
                    
                    update_task.cancel()
                    
                    # Ensure the project structure is included in the output
                    if "```" not in content[:500]:
                        content = f"# Architecture Documentation\n\n## Project Structure\n```\n{self.project_structure}\n```\n\n{content}"
                    
                    # Fix any remaining markdown issues
                    fixed_content = self._fix_markdown_issues(content)
                    return fixed_content
                    
                except Exception as e:
                    if self.debug:
                        print(f"\nError generating architecture content: {str(e)}")
                    return "Error generating architecture documentation."
    
    @async_retry(
        retries=3,
        delay=1.0,
        backoff=2.0,
        max_delay=30.0,
        jitter=True,
        exceptions=(botocore.exceptions.ClientError, ConnectionError, TimeoutError),
    )
    async def generate_architecture_doc(self, file_manifest: dict) -> str:
        """Generate architecture documentation based on file manifest."""
        try:
            # Get progress tracker instance
            progress_tracker = ProgressTracker.get_instance(Path("."))
            with progress_tracker.progress_bar(
                total=100,
                desc="Generating architecture documentation",
                bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}'
            ) as pbar:
                # Create progress update task
                update_task = asyncio.create_task(progress_tracker.update_progress_async(pbar))
                
                # Get project name
                project_name = self._derive_project_name(file_manifest)
                
                # Get detected technologies
                tech_report = self._find_common_dependencies(file_manifest)
                
                # Get key components
                key_components = self._identify_key_components(file_manifest)
                
                # Get messages
                messages = MessageManager.get_architecture_content_messages(
                    self.project_structure,
                    key_components,
                    tech_report
                )
                
                # Update progress
                pbar.update(20)
                
                try:
                    # Use the new token-aware invocation method
                    content = await self._invoke_model_with_token_management(messages)
                    
                    # Update progress
                    pbar.update(70)
                    
                    # Cancel progress update task
                    update_task.cancel()
                    
                    logging.info("Successfully received architecture content from LLM")
                    return content
                    
                except Exception as e:
                    # Cancel progress update task
                    update_task.cancel()
                    
                    logging.error(f"Error in LLM architecture generation: {str(e)}")
                    logging.error(f"Exception details: {traceback.format_exc()}")
                    
                    # Return a fallback message
                    return "# Architecture Documentation\n\nUnable to generate architecture documentation due to an error."
                
        except Exception as e:
            if self.debug:
                print(f"\nError generating architecture documentation: {str(e)}")
            logging.error(f"Error in LLM architecture generation: {str(e)}")
            logging.error(f"Exception details: {traceback.format_exc()}")
            return "# Architecture Documentation\n\nUnable to generate architecture documentation due to an error."
    
    @async_retry(
        retries=3,
        delay=1.0,
        backoff=2.0,
        max_delay=30.0,
        jitter=True,
        exceptions=(ConnectionError, TimeoutError),
    )
    async def generate_component_relationships(self, file_manifest: dict) -> str:
        """Generate description of how components interact."""
        async with self.semaphore:
            try:
                # Get detected technologies
                tech_report = self._find_common_dependencies(file_manifest)
                
                # Get messages from MessageManager
                messages = MessageManager.get_component_relationship_messages(
                    self.project_structure, 
                    tech_report
                )
                
                # Use the new token-aware invocation method
                content = await self._invoke_model_with_token_management(messages)
                return content
                
            except Exception as e:
                if self.debug:
                    print(f"\nError generating component relationships: {str(e)}")
                return "# Component Relationships\n\nUnable to generate component relationships due to an error."
    
    @async_retry(
        retries=3,
        delay=1.0,
        backoff=2.0,
        max_delay=30.0,
        jitter=True,
        exceptions=(botocore.exceptions.ClientError, ConnectionError, TimeoutError),
    )
    async def enhance_documentation(self, existing_content: str, file_manifest: dict, doc_type: str) -> str:
        """Enhance existing documentation with new insights."""
        try:
            # Get detected technologies
            tech_report = self._find_common_dependencies(file_manifest)
            
            # Get key components
            key_components = self._identify_key_components(file_manifest)
            
            # Ensure project structure is set
            if not self.project_structure or len(self.project_structure) < 10:
                self.set_project_structure_from_manifest(file_manifest)
                if self.debug:
                    print(f"Project structure generated ({len(self.project_structure)} chars)")
            
            # Create context for template
            context = {
                "doc_type": doc_type,
                "existing_content": existing_content
            }
            
            # Get template content with context
            template_content = self.prompt_template.get_template("enhance_documentation", context)
            
            # Get messages
            messages = MessageManager.get_enhance_documentation_messages(
                existing_content,
                self.project_structure,
                key_components,
                tech_report,
                doc_type
            )
            
            # Use the token-aware invocation method
            content = await self._invoke_model_with_token_management(messages)
            
            # Fix any markdown issues
            return self._fix_markdown_issues(content)
            
        except Exception as e:
            if self.debug:
                print(f"\nError enhancing documentation: {str(e)}")
            logging.error(f"Error enhancing documentation: {str(e)}")
            return existing_content  # Return original content on error

    @async_retry(
        retries=3,
        delay=1.0,
        backoff=2.0,
        max_delay=30.0,
        jitter=True,
        exceptions=(ConnectionError, TimeoutError),
    )
    async def generate_usage_guide(self, file_manifest: dict) -> str:
        """
        Generate usage guide based on project structure.
        
        Args:
            file_manifest: Dictionary mapping file paths to file information
            
        Returns:
            str: Generated usage guide content in markdown format
        """
        async with self.semaphore:
            try:
                # Get messages from MessageManager
                messages = MessageManager.get_usage_guide_messages(
                    self.project_structure,
                    self._find_common_dependencies(file_manifest)
                )
                
                # Extract system and user content
                system_content = next((msg["content"] for msg in messages if msg["role"] == "system"), "")
                user_content = next((msg["content"] for msg in messages if msg["role"] == "user"), "")
                
                # Use the helper method to create and invoke the request
                return await self._create_and_invoke_bedrock_request(system_content, user_content)
                
            except Exception as e:
                if self.debug:
                    print(f"\nError generating usage guide: {str(e)}")
                logging.error(f"Error generating usage guide: {str(e)}")
                return "### Usage\n\nUsage instructions could not be generated."

    @async_retry(
        retries=3,
        delay=1.0,
        backoff=2.0,
        max_delay=30.0,
        jitter=True,
        exceptions=(ConnectionError, TimeoutError),
    )
    async def generate_contributing_guide(self, file_manifest: dict) -> str:
        """
        Generate contributing guide based on project structure.
        
        Args:
            file_manifest: Dictionary mapping file paths to file information
            
        Returns:
            str: Generated contributing guide content in markdown format
        """
        async with self.semaphore:
            try:
                # Get messages from MessageManager
                messages = MessageManager.get_contributing_guide_messages(
                    self.project_structure
                )
                
                # Extract system and user content
                system_content = next((msg["content"] for msg in messages if msg["role"] == "system"), "")
                user_content = next((msg["content"] for msg in messages if msg["role"] == "user"), "")
                
                # Use the helper method to create and invoke the request
                return await self._create_and_invoke_bedrock_request(system_content, user_content)
                
            except Exception as e:
                if self.debug:
                    print(f"\nError generating contributing guide: {str(e)}")
                logging.error(f"Error generating contributing guide: {str(e)}")
                return "### Contributing\n\nContributing guidelines could not be generated."

    @async_retry(
        retries=3,
        delay=1.0,
        backoff=2.0,
        max_delay=30.0,
        jitter=True,
        exceptions=(ConnectionError, TimeoutError),
    )
    async def generate_license_info(self, file_manifest: dict) -> str:
        """
        Generate license information based on project structure.
        
        Args:
            file_manifest: Dictionary mapping file paths to file information
            
        Returns:
            str: Generated license information content in markdown format
        """
        async with self.semaphore:
            try:
                # Get messages from MessageManager
                messages = MessageManager.get_license_info_messages(
                    self.project_structure
                )
                
                # Extract system and user content
                system_content = next((msg["content"] for msg in messages if msg["role"] == "system"), "")
                user_content = next((msg["content"] for msg in messages if msg["role"] == "user"), "")
                
                # Use the helper method to create and invoke the request
                return await self._create_and_invoke_bedrock_request(system_content, user_content)
                
            except Exception as e:
                if self.debug:
                    print(f"\nError generating license info: {str(e)}")
                logging.error(f"Error generating license info: {str(e)}")
                return "This project's license information could not be determined."

    def _get_default_order(self, core_files: dict, resource_files: dict) -> list[str]:
        """Get a sensible default order when LLM ordering fails."""
        return get_default_order(core_files, resource_files)

    async def get_file_order(self, project_files: dict) -> list[str]:
        """
        Ask LLM to determine optimal file processing order.
        
        Args:
            project_files: Dictionary mapping file paths to file information
            
        Returns:
            list[str]: Ordered list of file paths
        """
        try:
            print("\nStarting file order optimization...")
            logging.info("Preparing file order optimization request")
            
            # Use common utility to prepare data
            core_files, resource_files, files_info = prepare_file_order_data(project_files, self.debug)
            
            print(f"Sending request to LLM with {len(files_info)} files...")
            logging.info(f"Sending file order request to LLM with {len(files_info)} files")
            
            # Get messages from MessageManager
            messages = MessageManager.get_file_order_messages(files_info)
            
            # Extract system and user content
            system_content = next((msg["content"] for msg in messages if msg["role"] == "system"), "")
            user_content = next((msg["content"] for msg in messages if msg["role"] == "user"), "")
            
            # Use the helper method to create and invoke the request
            content = await self._create_and_invoke_bedrock_request(system_content, user_content)
            
            # Use common utility to process response
            return process_file_order_response(content, core_files, resource_files, self.debug)
        
        except Exception as e:
            print(f"Error in file order optimization: {str(e)}")
            logging.error(f"Error getting file order: {str(e)}", exc_info=True)
            return list(project_files.keys())

    @async_retry(
        retries=3,
        delay=1.0,
        backoff=2.0,
        max_delay=30.0,
        jitter=True,
        exceptions=(botocore.exceptions.ClientError, ConnectionError, TimeoutError),
    )
    async def _invoke_model_with_token_management(self, messages, max_tokens=None, retry_on_token_error=True):
        """Invoke model with automatic token management to prevent 'Input is too long' errors."""
        try:
            # Extract system and user content
            system_content = next((msg["content"] for msg in messages if msg["role"] == "system"), "")
            user_content = next((msg["content"] for msg in messages if msg["role"] == "user"), "")
            
            # Combine for Claude
            combined_content = f"{system_content}\n\n{user_content}"
            
            # Check token count before sending
            if self.token_counter:
                total_tokens = self.token_counter.count_tokens(combined_content)
                model_limit = self.token_counter.get_token_limit(self.model_id)
                logging.info(f"Request content: {total_tokens} tokens (model limit: {model_limit})")
                
                # If we're over the limit, truncate
                if total_tokens > model_limit:
                    logging.warning(f"Content exceeds token limit: {total_tokens} > {model_limit}")
                    # Use the intelligent reduction method first
                    combined_content = self.token_counter.handle_oversized_input(
                        combined_content, 
                        target_percentage=0.8
                    )
                    new_tokens = self.token_counter.count_tokens(combined_content)
                    logging.info(f"Intelligently reduced content from {total_tokens} to {new_tokens} tokens")
                    
                    # If still over limit, use more aggressive truncation
                    if new_tokens > model_limit:
                        combined_content = self.token_counter.truncate_text(
                            combined_content, 
                            int(model_limit * 0.9)
                        )
                        final_tokens = self.token_counter.count_tokens(combined_content)
                        logging.info(f"Further truncated to {final_tokens} tokens")
                
                # Log final token count
                final_tokens = self.token_counter.count_tokens(combined_content)
                logging.info(f"Final combined content: {final_tokens} tokens")
            
            # Create proper Bedrock format
            bedrock_messages = [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": combined_content}]
                }
            ]
            
            # Use provided max_tokens or default
            tokens_to_generate = max_tokens or self.max_tokens
            
            # Create request body
            request_body = json.dumps({
                "anthropic_version": BEDROCK_API_VERSION,
                "max_tokens": tokens_to_generate,
                "messages": bedrock_messages,
                "temperature": self.temperature
            })
            
            logging.info(f"Request body size: {len(request_body)} bytes")
            
            # Invoke model with timeout
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.client.invoke_model,
                        body=request_body,
                        modelId=self.model_id
                    ),
                    timeout=self.timeout
                )
                
                # Process response
                response_body = json.loads(response.get('body').read())
                content = response_body['content'][0]['text']
                
                # Fix any markdown issues
                fixed_content = self._fix_markdown_issues(content)
                
                return fixed_content
                
            except asyncio.TimeoutError:
                logging.error(f"Request timed out after {self.timeout} seconds")
                raise TimeoutError(f"Bedrock API call timed out after {self.timeout} seconds")
                
            except botocore.exceptions.ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                error_message = e.response.get('Error', {}).get('Message', str(e))
                logging.error(f"Error in Bedrock API call: {error_code} - {error_message}")
                
                # Handle "Input is too long" error with emergency truncation
                if retry_on_token_error and error_code == 'ValidationException' and 'Input is too long' in error_message:
                    logging.warning("Input too long error detected, attempting emergency truncation")
                    
                    # Try with even more aggressive truncation as a last resort
                    if self.token_counter:
                        # Use only 50% of the limit for emergency cases
                        max_emergency_tokens = int(model_limit * 0.5)
                        emergency_content = self.token_counter.truncate_text(combined_content, max_emergency_tokens)
                        emergency_tokens = self.token_counter.count_tokens(emergency_content)
                        logging.info(f"Emergency truncation to {emergency_tokens} tokens (50% of limit)")
                        
                        # Create emergency messages
                        emergency_messages = [
                            {"role": "system", "content": "Provide a concise response due to input length constraints."},
                            {"role": "user", "content": emergency_content}
                        ]
                        
                        # Recursive call with emergency truncation, but prevent infinite recursion
                        return await self._invoke_model_with_token_management(
                            emergency_messages, 
                            max_tokens=tokens_to_generate,
                            retry_on_token_error=False  # Prevent infinite recursion
                        )
                
                # Re-raise the exception if we can't handle it
                raise
                
        except Exception as e:
            if self.debug:
                print(f"Error in model invocation: {str(e)}")
            logging.error(f"Error in model invocation: {str(e)}")
            logging.error(f"Exception details: {traceback.format_exc()}")
            raise
