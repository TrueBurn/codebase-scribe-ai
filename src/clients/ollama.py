from ollama import AsyncClient
from typing import Dict, Any, Optional
import httpx
from ..utils.prompt_manager import PromptTemplate
from ..utils.retry import async_retry
from pathlib import Path
import yaml
import json
import re
from collections import defaultdict
import traceback
from tqdm import tqdm
import asyncio
from ..utils.progress import ProgressTracker
import logging
from pydantic import BaseModel
from typing import List, Optional
import time
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
from ..utils.tokens import TokenCounter

class OllamaClientError(Exception):
    """Custom exception for Ollama client errors."""
    pass

class OllamaClient(BaseLLMClient):
    """Handles all interactions with local Ollama instance."""
    
    def __init__(self, config: Dict[str, Any]):
        # Call parent class constructor
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
    
    async def initialize(self):
        """Async initialization"""
        try:
            self.available_models = await self._get_available_models()
            if not self.available_models:
                raise OllamaClientError("No models available in Ollama instance")
            
            self.selected_model = await self._select_model_interactive()
            
            # Initialize token counter after model selection
            self.init_token_counter()
            
            print(f"\nInitialized with model: {self.selected_model}")
            print("Starting analysis...\n")
            
            if self.debug:
                print(f"Selected model: {self.selected_model}")
            
        except Exception as e:
            if self.debug:
                print(f"Initialization error: {traceback.format_exc()}")
            raise OllamaClientError(f"Failed to initialize client: {str(e)}")

    def init_token_counter(self):
        """Initialize the token counter for this client."""
        self.token_counter = TokenCounter(model_name=self.selected_model, debug=self.debug)

    async def _get_available_models(self) -> list:
        """Get list of available models from Ollama."""
        try:
            response = await self.client.list()
            models = response.models
            return [model.model for model in models]
        except Exception as e:
            if self.debug:
                print(f"Error fetching models: {str(e)}")
            return []

    @async_retry(
        retries=3,
        delay=1.0,
        backoff=2.0,
        max_delay=30.0,
        jitter=True,
        exceptions=(httpx.HTTPError, ConnectionError, TimeoutError),
    )
    async def generate_summary(self, prompt: str) -> Optional[str]:
        """Generate a summary for a file's content."""
        try:
            # Check token count
            will_exceed, token_count = self.token_counter.will_exceed_limit(prompt, self.selected_model)
            
            if will_exceed:
                if self.debug:
                    print(f"Content exceeds token limit ({token_count} tokens). Truncating...")
                prompt = self.token_counter.truncate_text(prompt)
                
                # Re-check after truncation
                _, new_token_count = self.token_counter.will_exceed_limit(prompt, self.selected_model)
                if self.debug:
                    print(f"Truncated to {new_token_count} tokens")
            
            response = await self.client.chat(
                model=self.selected_model,
                messages=MessageManager.get_file_summary_messages(prompt),
                options={"temperature": self.temperature}
            )
            
            if response and 'message' in response:
                content = response['message'].get('content', '')
                return self._fix_markdown_issues(content)
            
            return None
            
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
        exceptions=(httpx.HTTPError, ConnectionError, TimeoutError),
    )
    async def generate_project_overview(self, file_manifest: dict) -> str:
        """Generate project overview based strictly on observed evidence."""
        # Get progress tracker instance
        progress_tracker = ProgressTracker.get_instance(Path("."))
        with progress_tracker.progress_bar(
            desc="Generating project overview",
            bar_format='{desc} {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt}',
            ncols=150
        ) as pbar:
            try:
                update_task = asyncio.create_task(progress_tracker.update_progress_async(pbar))
                
                # Get detected technologies
                tech_report = self._find_common_dependencies(file_manifest)
                
                # Get key components with the improved method
                key_components = self._identify_key_components(file_manifest)
                
                # Your existing template code
                template_content = self.prompt_template.get_template('project_overview', {
                    'project_name': self._derive_project_name(file_manifest),
                    'file_count': len(file_manifest),
                    'key_components': key_components,
                    'dependencies': tech_report,
                    'project_structure': self.project_structure
                })
                
                response = await self.client.chat(
                    model=self.selected_model,
                    messages=MessageManager.get_project_overview_messages(
                        self.project_structure, 
                        tech_report, 
                        template_content
                    ),
                    options={"temperature": self.temperature}
                )
                
                update_task.cancel()
                content = response['message']['content']
                
                # Fix any remaining markdown issues
                fixed_content = self._fix_markdown_issues(content)
                return fixed_content
                
            except Exception as e:
                if self.debug:
                    print(f"\nError generating overview: {str(e)}")
                raise

    def _chunk_content(self, content: str, chunk_size: int = 1000) -> str:
        """
        Chunk large content to fit within context window.
        Returns a representative sample if content is too large.
        """
        if len(content) <= chunk_size:
            return content
            
        # Take the first and last portions of the content
        half_chunk = chunk_size // 2
        start = content[:half_chunk]
        end = content[-half_chunk:]
        return f"{start}\n\n... [content truncated for length] ...\n\n{end}"

    def _format_project_structure(self, file_manifest: dict) -> str:
        """Build a tree-like project structure string."""
        return format_project_structure(file_manifest, self.debug)

    def set_project_structure(self, structure: str) -> None:
        """
        Set the project structure for use in prompts.
        
        Args:
            structure: String representation of the project structure
        """
        self.project_structure = structure
        
    def set_project_structure_from_manifest(self, file_manifest: Dict[str, Any]) -> None:
        """
        Set the project structure from a file manifest.
        
        This is a convenience method that formats the file manifest into a
        string representation and then sets it as the project structure.
        
        Args:
            file_manifest: Dictionary mapping file paths to file information
        """
        self.project_structure = self._format_project_structure(file_manifest)

    @async_retry(
        retries=3,
        delay=1.0,
        backoff=2.0,
        max_delay=30.0,
        jitter=True,
        exceptions=(httpx.HTTPError, ConnectionError, TimeoutError),
    )
    async def generate_component_relationships(self, file_manifest: dict) -> str:
        """Generate description of how components interact."""
        
        # Get detected technologies first
        tech_report = self._find_common_dependencies(file_manifest)
        
        response = await self.client.chat(
            model=self.selected_model,
            messages=MessageManager.get_component_relationship_messages(
                self.project_structure, 
                tech_report
            ),
            options={"temperature": self.temperature}
        )
        content = response['message']['content']
        
        # Fix any markdown issues
        return self._fix_markdown_issues(content)

    def _identify_key_components(self, file_manifest: dict) -> str:
        """Identify key components from file manifest."""
        return identify_key_components(file_manifest, self.debug)

    def _find_common_dependencies(self, file_manifest: dict) -> str:
        """Extract common dependencies from file manifest."""
        return find_common_dependencies(file_manifest, self.debug)

    async def _select_model_interactive(self) -> str:
        """Interactive model selection."""
        while True:
            print("Available Ollama models:")
            for i, model in enumerate(self.available_models, 1):
                print(f"{i}. {model}")
            
            try:
                selection = int(input("Enter the number of the model to use: "))
                if 1 <= selection <= len(self.available_models):
                    return self.available_models[selection - 1]
                else:
                    print(f"\nError: '{selection}' is not a valid option.")
                    print(f"Please choose a number between 1 and {len(self.available_models)}")
                    print("\n" + "-" * 50 + "\n")
            except ValueError:
                print("\nError: Please enter a valid number, not text.")
                print("\n" + "-" * 50 + "\n")            

    class FileOrderResponse(BaseModel):
        """Schema for file ordering response"""
        file_order: List[str]
        reasoning: Optional[str] = None

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
            
            # Send request to Ollama
            response = await self.client.chat(
                model=self.selected_model,
                messages=messages,
                options={"temperature": self.temperature}
            )
            
            content = response['message']['content']
            
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
        exceptions=(httpx.HTTPError, ConnectionError, TimeoutError),
    )
    async def generate_architecture_content(self, file_manifest: dict, analyzer) -> str:
        """Generate architecture documentation content with flow diagrams."""
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
                
                # Get messages from MessageManager with enhanced content
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
                
                response = await self.client.chat(
                    model=self.selected_model,
                    messages=messages,
                    options={"temperature": self.temperature}
                )
                
                update_task.cancel()
                content = response['message']['content']
                
                # Ensure the project structure is included in the output
                if "```" not in content[:500]:
                    content = f"# Architecture Documentation\n\n## Project Structure\n```\n{self.project_structure}\n```\n\n{content}"
                
                # Fix any markdown issues
                return self._fix_markdown_issues(content)
                
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
        exceptions=(httpx.HTTPError, ConnectionError, TimeoutError),
    )
    async def generate_usage_guide(self, file_manifest: dict) -> str:
        """Generate usage guide based on project structure."""
        try:
            response = await self.client.chat(
                model=self.selected_model,
                messages=MessageManager.get_usage_guide_messages(
                    self.project_structure,
                    self._find_common_dependencies(file_manifest)
                ),
                options={"temperature": self.temperature}
            )
            
            content = response['message']['content']
            
            # Fix any markdown issues
            return self._fix_markdown_issues(content)
            
        except Exception as e:
            if self.debug:
                print(f"\nError generating usage guide: {str(e)}")
            return "### Usage\n\nUsage instructions could not be generated."

    @async_retry(
        retries=3,
        delay=1.0,
        backoff=2.0,
        max_delay=30.0,
        jitter=True,
        exceptions=(httpx.HTTPError, ConnectionError, TimeoutError),
    )
    async def generate_contributing_guide(self, file_manifest: dict) -> str:
        """Generate contributing guide based on project structure."""
        try:
            response = await self.client.chat(
                model=self.selected_model,
                messages=MessageManager.get_contributing_guide_messages(
                    self.project_structure
                ),
                options={"temperature": self.temperature}
            )
            
            content = response['message']['content']
            
            # Fix any markdown issues
            return self._fix_markdown_issues(content)
            
        except Exception as e:
            if self.debug:
                print(f"\nError generating contributing guide: {str(e)}")
            return "### Contributing\n\nContribution guidelines could not be generated."

    @async_retry(
        retries=3,
        delay=1.0,
        backoff=2.0,
        max_delay=30.0,
        jitter=True,
        exceptions=(httpx.HTTPError, ConnectionError, TimeoutError),
    )
    async def generate_license_info(self, file_manifest: dict) -> str:
        """Generate license information based on project structure."""
        try:
            response = await self.client.chat(
                model=self.selected_model,
                messages=MessageManager.get_license_info_messages(
                    self.project_structure
                ),
                options={"temperature": self.temperature}
            )
            
            content = response['message']['content']
            
            # Fix any markdown issues
            return self._fix_markdown_issues(content)
            
        except Exception as e:
            if self.debug:
                print(f"\nError generating license info: {str(e)}")
            return "This project's license information could not be determined."

    @async_retry(
        retries=3,
        delay=1.0,
        backoff=2.0,
        max_delay=30.0,
        jitter=True,
        exceptions=(httpx.HTTPError, ConnectionError, TimeoutError),
    )
    async def enhance_documentation(self, existing_content: str, file_manifest: dict, doc_type: str) -> str:
        """Enhance existing documentation with new insights."""
        try:
            # Get detected technologies
            tech_report = self._find_common_dependencies(file_manifest)
            
            # Get key components
            key_components = self._identify_key_components(file_manifest)
            
            response = await self.client.chat(
                model=self.selected_model,
                messages=MessageManager.get_enhance_documentation_messages(
                    existing_content,
                    self.project_structure,
                    key_components,
                    tech_report,
                    doc_type
                ),
                options={"temperature": self.temperature}
            )
            
            content = response['message']['content']
            
            # Fix any markdown issues
            return self._fix_markdown_issues(content)
            
        except Exception as e:
            if self.debug:
                print(f"\nError enhancing documentation: {str(e)}")
            return existing_content  # Return original content on error 

    def _derive_project_name(self, file_manifest: dict) -> str:
        """Derive project name from repository structure."""
        # Create a temporary analyzer instance to use its method
        from ..analyzers.codebase import CodebaseAnalyzer
        from pathlib import Path
        temp_analyzer = CodebaseAnalyzer(Path("."), {"debug": self.debug})
        temp_analyzer.file_manifest = file_manifest
        return temp_analyzer.derive_project_name(self.debug)