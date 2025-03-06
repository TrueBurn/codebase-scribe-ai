from typing import Dict, Any, Optional, List
import boto3
import json
import logging
import asyncio
from tqdm import tqdm
import time
import os
from dotenv import load_dotenv
from ..utils.prompt_manager import PromptTemplate
from ..utils.retry import async_retry
from pydantic import BaseModel
from .base_llm import BaseLLMClient
from .message_manager import MessageManager
from ..analyzers.codebase import CodebaseAnalyzer
from .llm_utils import (
    format_project_structure,
    find_common_dependencies,
    identify_key_components,
    get_default_order,
    fix_markdown_issues,
    prepare_file_order_data,
    process_file_order_response
)
import re
from pathlib import Path
import traceback
import botocore
from botocore.config import Config as BotocoreConfig

class BedrockClientError(Exception):
    """Custom exception for Bedrock client errors."""

class BedrockClient(BaseLLMClient):
    """Handles all interactions with AWS Bedrock."""
    
    def __init__(self, config: Dict[str, Any]):
        # Load environment variables from .env file
        load_dotenv()
        
        # Get Bedrock config with defaults
        bedrock_config = config.get('bedrock', {})
        
        # Use environment variables if available, otherwise use config
        self.region = os.getenv('AWS_REGION') or bedrock_config.get('region', 'us-east-1')
        
        # Use environment variable for model_id if available, otherwise use config
        # Default to the correct Claude 3 Sonnet model ID
        self.model_id = os.getenv('AWS_BEDROCK_MODEL_ID') or bedrock_config.get(
            'model_id', 'us.anthropic.claude-3-5-sonnet-20241022-v2:0'
        )
        
        # Print model ID for debugging
        if config.get('debug', False):
            print(f"Using Bedrock model ID: {self.model_id}")
        
        self.max_tokens = bedrock_config.get('max_tokens', 4096)
        self.retries = bedrock_config.get('retries', 3)
        self.retry_delay = bedrock_config.get('retry_delay', 1.0)
        
        # Increase default timeout from 30 to 120 seconds
        self.timeout = bedrock_config.get('timeout', 120)
        
        self.debug = config.get('debug', False)
        self.project_structure = None
        
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
        
        # Initialize Bedrock client with credentials from environment and longer timeout
        # AWS SDK will automatically use AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY from env
        self.client = boto3.client(
            'bedrock-runtime', 
            region_name=self.region,
            verify=self.verify_ssl,
            config=BotocoreConfig(
                connect_timeout=self.timeout,
                read_timeout=self.timeout,
                retries={'max_attempts': self.retries}
            )
        )
        self.prompt_template = PromptTemplate(config.get('template_path'))
        
        # Add temperature setting
        self.temperature = bedrock_config.get('temperature', 0)  # Default to 0 for deterministic output
        
    async def initialize(self):
        """Async initialization"""
        try:
            print(f"\nInitialized with model: {self.model_id}")
            print(f"Using AWS region: {self.region}")
            print("Starting analysis...\n")
            
            if self.debug:
                print(f"Selected model: {self.model_id}")
                print(f"AWS credentials: {'Found' if os.getenv('AWS_ACCESS_KEY_ID') else 'Not found'} in environment")
            
            # Initialize project structure if not already done
            if self.project_structure is None:
                self.project_structure = "Project structure not initialized. Please analyze repository first."
            
        except Exception as e:
            if self.debug:
                print(f"Initialization error: {str(e)}")
            raise BedrockClientError(f"Failed to initialize client: {str(e)}")
    
    @async_retry(
        retries=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(ConnectionError, TimeoutError),
    )
    async def generate_summary(self, prompt: str) -> Optional[str]:
        """Generate a summary for a file's content."""
        async with self.semaphore:  # Use semaphore to control concurrency
            try:
                messages = MessageManager.get_file_summary_messages(prompt)
                
                # For Claude models in Bedrock, we need to use a different format
                # Claude 3 in Bedrock expects "user" and "assistant" roles, not "system"
                
                # Extract the system message content
                system_content = next((msg["content"] for msg in messages if msg["role"] == "system"), "")
                user_content = next((msg["content"] for msg in messages if msg["role"] == "user"), "")
                
                # Combine system and user content for Claude
                combined_content = f"{system_content}\n\n{user_content}"
                
                # Create proper Bedrock format
                bedrock_messages = [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": combined_content}]
                    }
                ]
                
                response = await asyncio.to_thread(
                    self.client.invoke_model,
                    body=json.dumps({
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": self.max_tokens,
                        "messages": bedrock_messages,
                        "temperature": self.temperature
                    }),
                    modelId=self.model_id
                )
                
                response_body = json.loads(response.get('body').read())
                content = response_body['content'][0]['text']
                return self._fix_markdown_issues(content)
                
            except Exception as e:
                logging.error(f"Error generating summary: {e}")
                return None
    
    async def _update_progress(self, pbar):
        """Updates progress bar while waiting for response."""
        try:
            while True:
                # Format elapsed time into human readable format
                elapsed = pbar.format_dict['elapsed']
                minutes = int(elapsed // 60)
                seconds = int(elapsed % 60)
                time_str = f"{minutes:02d}:{seconds:02d}" if minutes else f"{seconds}s"
                
                # Set a clean description with the time
                base_desc = "Generating project overview"
                pbar.set_description(f"{base_desc}: {time_str}")
                
                pbar.refresh()
                
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
    
    def _fix_markdown_issues(self, content: str) -> str:
        """Fix common markdown formatting issues before returning content."""
        return fix_markdown_issues(content)
    
    @async_retry(
        retries=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(ConnectionError, TimeoutError),
    )
    async def generate_project_overview(self, file_manifest: dict) -> str:
        """Generate a comprehensive overview of the project."""
        async with self.semaphore:  # Use semaphore to control concurrency
            # Use a single progress bar with a unique description to avoid duplicates
            with tqdm(
                desc="Generating project overview",
                bar_format='{desc}|{bar}| {percentage:3.0f}%',
                ncols=100,
                position=0,  # Force position to 0 to avoid multiple bars
                leave=True   # Keep the bar after completion
            ) as pbar:
                try:
                    update_task = asyncio.create_task(self._update_progress(pbar))
                    
                    # Ensure project structure is set
                    if not self.project_structure or len(self.project_structure) < 10:
                        self.project_structure = self._format_project_structure(file_manifest)
                        if self.debug:
                            print(f"Project structure generated ({len(self.project_structure)} chars)")
                    
                    # Get detected technologies
                    tech_report = self._find_common_dependencies(file_manifest)
                    
                    # Get key components with the improved method
                    key_components = self._identify_key_components(file_manifest)
                    
                    # Create a summary of file contents for context
                    file_summaries = []
                    
                    # First, categorize files by directory/component
                    file_by_component = {}
                    for path, info in file_manifest.items():
                        # Check if info is a FileInfo object or a dictionary
                        if hasattr(info, 'summary') and not getattr(info, 'is_binary', False):
                            directory = str(Path(path).parent)
                            if directory not in file_by_component:
                                file_by_component[directory] = []
                            file_by_component[directory].append((path, getattr(info, 'summary', 'No summary available')))
                    
                    # For each component, include a representative sample of files
                    for directory, files in file_by_component.items():
                        # Add component header
                        file_summaries.append(f"## Component: {directory}")
                        
                        # Sort files by potential importance (e.g., longer summaries might be more important)
                        files.sort(key=lambda x: len(x[1]), reverse=True)
                        
                        # Take up to 5 files per component to ensure broad coverage
                        for path, summary in files[:5]:
                            file_summaries.append(f"File: {path}\nSummary: {summary}")
                    
                    # If we still have too many summaries, prioritize by component size
                    if len('\n\n'.join(file_summaries)) > 12000:  # Approximate token limit
                        # Sort components by number of files (largest first)
                        sorted_components = sorted(file_by_component.items(), key=lambda x: len(x[1]), reverse=True)
                        
                        # Reset file_summaries and rebuild with top components
                        file_summaries = []
                        for directory, files in sorted_components[:10]:  # Top 10 components
                            file_summaries.append(f"## Component: {directory}")
                            for path, summary in files[:3]:  # Top 3 files per component
                                file_summaries.append(f"File: {path}\nSummary: {summary}")
                    
                    file_summaries_text = "\n\n".join(file_summaries)
                    
                    # Debug output
                    if self.debug:
                        print(f"Tech report: {len(tech_report)} chars")
                        print(f"Key components: {len(key_components)} chars")
                        print(f"File summaries: {len(file_summaries)} entries, {len(file_summaries_text)} chars")
                    
                    # Get template content
                    template_content = self.prompt_template.get_template('project_overview', {
                        'project_name': self._derive_project_name(file_manifest),
                        'file_count': len(file_manifest),
                        'key_components': key_components,
                        'dependencies': tech_report,
                        'project_structure': self.project_structure
                    })
                    
                    # Get messages from MessageManager
                    messages = MessageManager.get_project_overview_messages(
                        self.project_structure, 
                        tech_report, 
                        template_content
                    )
                    
                    # Extract system and user content
                    system_content = next((msg["content"] for msg in messages if msg["role"] == "system"), "")
                    user_content = next((msg["content"] for msg in messages if msg["role"] == "user"), "")
                    
                    # Add file summaries to provide more context
                    user_content += f"\n\nFile Summaries:\n{file_summaries_text}"
                    
                    # Combine for Claude
                    combined_content = f"{system_content}\n\n{user_content}"
                    
                    # Debug output
                    if self.debug:
                        print(f"Combined content length: {len(combined_content)} chars")
                    
                    # Create proper Bedrock format
                    bedrock_messages = [
                        {
                            "role": "user",
                            "content": [{"type": "text", "text": combined_content}]
                        }
                    ]
                    
                    # Convert to async operation
                    response = await asyncio.to_thread(
                        self.client.invoke_model,
                        body=json.dumps({
                            "anthropic_version": "bedrock-2023-05-31",
                            "max_tokens": self.max_tokens,
                            "messages": bedrock_messages,
                            "temperature": self.temperature
                        }),
                        modelId=self.model_id
                    )
                    
                    update_task.cancel()
                    
                    # Process response
                    response_body = json.loads(response.get('body').read())
                    content = response_body['content'][0]['text']
                    
                    # Fix any remaining markdown issues
                    fixed_content = self._fix_markdown_issues(content)
                    return fixed_content
                    
                except Exception as e:
                    if self.debug:
                        print(f"\nError generating overview: {str(e)}")
                    
                    # Instead of returning an error message, extract from ARCHITECTURE.md if available
                    project_name = self._derive_project_name(file_manifest)
                    
                    # Try to find an overview from the first file that might contain it
                    for path, info in file_manifest.items():
                        if hasattr(info, 'summary') and len(getattr(info, 'summary', '')) > 100:
                            return getattr(info, 'summary')
                    
                    # Return a more useful fallback that won't show as an error
                    return f"{project_name} is a software project containing {len(file_manifest)} files. For more details, please refer to the documentation."
    
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
    
    def set_project_structure(self, structure: str):
        """Set the project structure for use in prompts."""
        self.project_structure = structure
        if self.debug:
            print(f"Project structure set ({len(structure)} chars)")
    
    def _build_project_structure(self, file_manifest: dict) -> str:
        """Build a tree-like project structure string."""
        # Implementation similar to OllamaClient
        # For brevity, just returning a placeholder
        return "Project structure"
    
    @async_retry(
        retries=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(ConnectionError, TimeoutError),
    )
    async def generate_architecture_content(self, file_manifest: dict, analyzer) -> str:
        """Generate architecture documentation content with flow diagrams."""
        async with self.semaphore:
            with tqdm(
                desc="Generating architecture documentation",
                bar_format='{desc} {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt}',
                ncols=150
            ) as pbar:
                try:
                    update_task = asyncio.create_task(self._update_progress(pbar))
                    
                    # Ensure project structure is set
                    if not self.project_structure or len(self.project_structure) < 10:
                        self.project_structure = self._format_project_structure(file_manifest)
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
                    
                    # Combine for Claude
                    combined_content = f"{system_content}\n\n{user_content}"
                    
                    # Create proper Bedrock format
                    bedrock_messages = [
                        {
                            "role": "user",
                            "content": [{"type": "text", "text": combined_content}]
                        }
                    ]
                    
                    response = await asyncio.to_thread(
                        self.client.invoke_model,
                        body=json.dumps({
                            "anthropic_version": "bedrock-2023-05-31",
                            "max_tokens": self.max_tokens,
                            "messages": bedrock_messages,
                            "temperature": self.temperature
                        }),
                        modelId=self.model_id
                    )
                    
                    update_task.cancel()
                    
                    # Process response
                    response_body = json.loads(response.get('body').read())
                    content = response_body['content'][0]['text']
                    
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
        exceptions=(ConnectionError, TimeoutError, botocore.exceptions.ReadTimeoutError),
    )
    async def generate_architecture_doc(self, file_manifest: dict) -> str:
        """Generate architecture documentation for the project."""
        try:
            # Get detected technologies
            tech_report = self._find_common_dependencies(file_manifest)
            
            # Get key components
            key_components = self._identify_key_components(file_manifest)
            
            # Log for debugging
            if self.debug:
                print(f"Technology report generated ({len(tech_report)} chars)")
                print(f"Key components identified: {len(key_components)} chars)")
            
            # Get messages from MessageManager - FIX: Use the correct method name
            messages = MessageManager.get_architecture_content_messages(
                self.project_structure,
                key_components,
                tech_report
            )
            
            # Extract system and user content
            system_content = next((msg["content"] for msg in messages if msg["role"] == "system"), "")
            user_content = next((msg["content"] for msg in messages if msg["role"] == "user"), "")
            
            # Combine for Claude
            combined_content = f"{system_content}\n\n{user_content}"
            
            # Create proper Bedrock format
            bedrock_messages = [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": combined_content}]
                }
            ]
            
            # Rest of the method remains unchanged
            logging.info("Sending architecture documentation request to LLM")
            
            # Convert to async operation with explicit timeout
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.invoke_model,
                    body=json.dumps({
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": self.max_tokens,
                        "messages": bedrock_messages,
                        "temperature": self.temperature
                    }),
                    modelId=self.model_id
                ),
                timeout=self.timeout
            )
            
            # Process response
            response_body = json.loads(response.get('body').read())
            content = response_body['content'][0]['text']
            logging.info(f"Received architecture content ({len(content)} chars)")
            
            # Fix any markdown issues
            return self._fix_markdown_issues(content)
        
        except asyncio.TimeoutError:
            logging.error(f"Request timed out after {self.timeout} seconds")
            raise TimeoutError(f"Request timed out after {self.timeout} seconds")
        
        except Exception as e:
            logging.error(f"Error in Bedrock API call: {str(e)}")
            raise
    
    @async_retry(
        retries=3,
        delay=1.0,
        backoff=2.0,
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
                
                # Extract system and user content
                system_content = next((msg["content"] for msg in messages if msg["role"] == "system"), "")
                user_content = next((msg["content"] for msg in messages if msg["role"] == "user"), "")
                
                # Combine for Claude
                combined_content = f"{system_content}\n\n{user_content}"
                
                # Create proper Bedrock format
                bedrock_messages = [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": combined_content}]
                    }
                ]
                
                response = await asyncio.to_thread(
                    self.client.invoke_model,
                    body=json.dumps({
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": self.max_tokens,
                        "messages": bedrock_messages,
                        "temperature": self.temperature
                    }),
                    modelId=self.model_id
                )
                
                # Process response
                response_body = json.loads(response.get('body').read())
                content = response_body['content'][0]['text']
                
                # Fix any remaining markdown issues
                fixed_content = self._fix_markdown_issues(content)
                return fixed_content
                
            except Exception as e:
                if self.debug:
                    print(f"\nError generating component relationships: {str(e)}")
                return "Error generating component relationship documentation."
    
    @async_retry(
        retries=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(ConnectionError, TimeoutError),
    )
    async def enhance_documentation(self, existing_content: str, file_manifest: dict, doc_type: str) -> str:
        """Enhance existing documentation with new insights."""
        async with self.semaphore:
            try:
                # Get detected technologies
                tech_report = self._find_common_dependencies(file_manifest)
                
                # Get key components
                key_components = self._identify_key_components(file_manifest)
                
                # Get messages from MessageManager
                messages = MessageManager.get_enhance_documentation_messages(
                    existing_content,
                    self.project_structure,
                    key_components,
                    tech_report,
                    doc_type
                )
                
                # Extract system and user content
                system_content = next((msg["content"] for msg in messages if msg["role"] == "system"), "")
                user_content = next((msg["content"] for msg in messages if msg["role"] == "user"), "")
                
                # Combine for Claude
                combined_content = f"{system_content}\n\n{user_content}"
                
                # Create proper Bedrock format
                bedrock_messages = [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": combined_content}]
                    }
                ]
                
                response = await asyncio.to_thread(
                    self.client.invoke_model,
                    body=json.dumps({
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": self.max_tokens,
                        "messages": bedrock_messages,
                        "temperature": self.temperature
                    }),
                    modelId=self.model_id
                )
                
                # Process response
                response_body = json.loads(response.get('body').read())
                content = response_body['content'][0]['text']
                
                # Fix any remaining markdown issues
                fixed_content = self._fix_markdown_issues(content)
                return fixed_content
                
            except Exception as e:
                if self.debug:
                    print(f"\nError enhancing documentation: {str(e)}")
                return existing_content  # Return original content on error

    @async_retry(
        retries=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(ConnectionError, TimeoutError),
    )
    async def generate_usage_guide(self, file_manifest: dict) -> str:
        """Generate usage guide based on project structure."""
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
                
                # Combine for Claude
                combined_content = f"{system_content}\n\n{user_content}"
                
                # Create proper Bedrock format
                bedrock_messages = [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": combined_content}]
                    }
                ]
                
                response = await asyncio.to_thread(
                    self.client.invoke_model,
                    body=json.dumps({
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": self.max_tokens,
                        "messages": bedrock_messages,
                        "temperature": self.temperature
                    }),
                    modelId=self.model_id
                )
                
                # Process response
                response_body = json.loads(response.get('body').read())
                content = response_body['content'][0]['text']
                
                # Fix any remaining markdown issues
                fixed_content = self._fix_markdown_issues(content)
                return fixed_content
                
            except Exception as e:
                if self.debug:
                    print(f"\nError generating usage guide: {str(e)}")
                return "### Usage\n\nUsage instructions could not be generated."

    @async_retry(
        retries=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(ConnectionError, TimeoutError),
    )
    async def generate_contributing_guide(self, file_manifest: dict) -> str:
        """Generate contributing guide based on project structure."""
        async with self.semaphore:
            try:
                # Get messages from MessageManager
                messages = MessageManager.get_contributing_guide_messages(
                    self.project_structure
                )
                
                # Extract system and user content
                system_content = next((msg["content"] for msg in messages if msg["role"] == "system"), "")
                user_content = next((msg["content"] for msg in messages if msg["role"] == "user"), "")
                
                # Combine for Claude
                combined_content = f"{system_content}\n\n{user_content}"
                
                # Create proper Bedrock format
                bedrock_messages = [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": combined_content}]
                    }
                ]
                
                response = await asyncio.to_thread(
                    self.client.invoke_model,
                    body=json.dumps({
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": self.max_tokens,
                        "messages": bedrock_messages,
                        "temperature": self.temperature
                    }),
                    modelId=self.model_id
                )
                
                # Process response
                response_body = json.loads(response.get('body').read())
                content = response_body['content'][0]['text']
                
                # Fix any remaining markdown issues
                fixed_content = self._fix_markdown_issues(content)
                return fixed_content
                
            except Exception as e:
                if self.debug:
                    print(f"\nError generating contributing guide: {str(e)}")
                return "### Contributing\n\nContributing guidelines could not be generated."

    @async_retry(
        retries=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(ConnectionError, TimeoutError),
    )
    async def generate_license_info(self, file_manifest: dict) -> str:
        """Generate license information based on project structure."""
        async with self.semaphore:
            try:
                # Get messages from MessageManager
                messages = MessageManager.get_license_info_messages(
                    self.project_structure
                )
                
                # Extract system and user content
                system_content = next((msg["content"] for msg in messages if msg["role"] == "system"), "")
                user_content = next((msg["content"] for msg in messages if msg["role"] == "user"), "")
                
                # Combine for Claude
                combined_content = f"{system_content}\n\n{user_content}"
                
                # Create proper Bedrock format
                bedrock_messages = [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": combined_content}]
                    }
                ]
                
                response = await asyncio.to_thread(
                    self.client.invoke_model,
                    body=json.dumps({
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": self.max_tokens,
                        "messages": bedrock_messages,
                        "temperature": self.temperature
                    }),
                    modelId=self.model_id
                )
                
                # Process response
                response_body = json.loads(response.get('body').read())
                content = response_body['content'][0]['text']
                
                # Fix any remaining markdown issues
                fixed_content = self._fix_markdown_issues(content)
                return fixed_content
                
            except Exception as e:
                if self.debug:
                    print(f"\nError generating license info: {str(e)}")
                return "This project's license information could not be determined."

    def _get_default_order(self, core_files: dict, resource_files: dict) -> list[str]:
        """Get a sensible default order when LLM ordering fails."""
        return get_default_order(core_files, resource_files)

    async def get_file_order(self, project_files: dict) -> list[str]:
        """Ask LLM to determine optimal file processing order."""
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
            
            # Combine for Claude
            combined_content = f"{system_content}\n\n{user_content}"
            
            # Create proper Bedrock format
            bedrock_messages = [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": combined_content}]
                }
            ]
            
            # Convert to async operation
            response = await asyncio.to_thread(
                self.client.invoke_model,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": self.max_tokens,
                    "messages": bedrock_messages,
                    "temperature": self.temperature
                }),
                modelId=self.model_id
            )
            
            # Process response
            response_body = json.loads(response.get('body').read())
            content = response_body['content'][0]['text']
            
            # Use common utility to process response
            return process_file_order_response(content, core_files, resource_files, self.debug)
        
        except Exception as e:
            print(f"Error in file order optimization: {str(e)}")
            logging.error(f"Error getting file order: {str(e)}", exc_info=True)
            return list(project_files.keys())
