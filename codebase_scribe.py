#!/usr/bin/env python3

# Standard library imports
import argparse
import asyncio
import logging
import os
import shutil
import sys
import time
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# Third-party imports
import psutil
import urllib3
from dotenv import load_dotenv

# Local imports
from src.analyzers.codebase import CodebaseAnalyzer
from src.clients.base_llm import BaseLLMClient
from src.clients.llm_factory import LLMClientFactory
from src.generators.architecture import generate_architecture
from src.generators.readme import generate_readme
from src.models.file_info import FileInfo
from src.utils.badges import generate_badges
from src.utils.cache import CacheManager
from src.utils.cache_utils import display_cache_stats, display_github_cache_stats
from src.utils.config_utils import load_config, update_config_with_args, config_to_dict
from src.utils.config_class import ScribeConfig
from src.utils.doc_utils import add_ai_attribution
from src.utils.exceptions import (
    ScribeError,
    ConfigurationError,
    RepositoryError,
    FileProcessingError,
    LLMError,
    GitHubError
)
from src.utils.github_utils import (
    is_valid_github_url,
    clone_github_repository,
    create_git_branch,
    commit_documentation_changes,
    push_branch_to_remote,
    create_pull_request,
    extract_repo_info,
    prepare_github_branch
)
from src.utils.progress_utils import (
    create_file_processing_progress_bar,
    create_optimization_progress_bar,
    create_documentation_progress_bar
)
from src.utils.progress import ProgressTracker

# Load environment variables from .env file
load_dotenv()

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)

# Disable bytecode caching
sys.dont_write_bytecode = True

def setup_logging(debug: bool = False, log_to_file: bool = True) -> None:
    """Configure logging based on debug flag.
    
    Args:
        debug: If True, sets logging level to DEBUG, otherwise INFO
        log_to_file: If True, logs to both file and console, otherwise just console
    """
    log_level = logging.DEBUG if debug else logging.INFO
    
    # Create logs directory if it doesn't exist
    if log_to_file:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Create a timestamped log file
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        log_file = log_dir / f"readme_generator_{timestamp}.log"
        
        # Configure logging to file and console
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        
        logging.info(f"Debug logging enabled. Log file: {log_file}")
    else:
        # Configure logging to console only
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

# Function moved: process_file is now a nested function within process_files
# Function removed: calculate_max_concurrent was unused

async def determine_processing_order(
    file_manifest: Dict[str, FileInfo],
    llm_client: BaseLLMClient
) -> List[str]:
    """Ask LLM to determine optimal file processing order based on project structure.
    
    Args:
        file_manifest: Dictionary mapping file paths to FileInfo objects
        llm_client: LLM client to use for determining file order
        
    Returns:
        List of file paths in the determined processing order
        
    Raises:
        LLMError: If there's an error with the LLM client
    """
    logging.info(f"Starting file ordering optimization for {len(file_manifest)} files")
    
    with create_optimization_progress_bar(Path(".")) as pbar:
        try:
            # Stage 1: Starting
            pbar.update(1)
            
            # Log before LLM call
            logging.info("Starting LLM call for file ordering")
            start_time = time.time()
            
            # Get order from LLM
            try:
                processing_order = await llm_client.get_file_order(file_manifest)
            except Exception as e:
                raise LLMError(f"Failed to get file order from LLM: {str(e)}") from e
            
            # Log after LLM call
            elapsed = time.time() - start_time
            pbar.update(4)  # Complete remaining steps
            logging.info(f"LLM file ordering completed in {elapsed:.2f} seconds")
            
            # Ensure we have all files
            manifest_files = set(file_manifest.keys())
            ordered_files = set(processing_order)
            
            # Add any missing files to the end
            missing_files = manifest_files - ordered_files
            if missing_files:
                print()  # Add newline before warning
                logging.warning(f"Adding {len(missing_files)} files missing from LLM order")
                processing_order.extend(sorted(missing_files))
                for i, missing in enumerate(sorted(missing_files)[:5], 1):
                    logging.debug(f"  Missing file {i}: {missing}")
                if len(missing_files) > 5:
                    logging.debug(f"  ... and {len(missing_files) - 5} more")
            
            # Remove any extra files that don't exist
            extra_files = ordered_files - manifest_files
            if extra_files:
                print()  # Add newline before warning
                logging.warning(f"Removing {len(extra_files)} non-existent files from LLM order")
                processing_order = [f for f in processing_order if f in manifest_files]
                for i, extra in enumerate(sorted(extra_files)[:5], 1):
                    logging.debug(f"  Extra file {i}: {extra}")
                if len(extra_files) > 5:
                    logging.debug(f"  ... and {len(extra_files) - 5} more")
            
            # Log first few files in determined order for verification
            logging.info(f"Determined processing order with {len(processing_order)} files")
            for i, file_path in enumerate(processing_order[:5], 1):
                logging.debug(f"  Order position {i}: {file_path}")
            if len(processing_order) > 5:
                logging.debug(f"  ... and {len(processing_order) - 5} more files")
                
            # Only print full order in debug mode
            if logging.getLogger().getEffectiveLevel() == logging.DEBUG:
                print("\nDetermined processing order:")
                for i, file_path in enumerate(processing_order, 1):
                    print(f"{i}. {file_path}")
                print()
            
            return processing_order
            
        except Exception as e:
            pbar.update(5 - pbar.n)  # Complete progress bar on error
            logging.error(f"Error determining processing order: {e}", exc_info=True)
            print("\nFailed to determine optimal order, using default order")
            return list(file_manifest.keys())

async def process_files(
    manifest: Dict[str, FileInfo],
    repo_path: Path,
    llm_client: BaseLLMClient,
    analyzer: CodebaseAnalyzer,
    cache: Optional[CacheManager] = None,
    config: Optional[Dict[str, Any]] = None,
    processing_order: Optional[List[str]] = None
) -> Dict[str, FileInfo]:
    """Process files concurrently with progress tracking.
    
    Args:
        manifest: Dictionary mapping file paths to FileInfo objects
        repo_path: Path to the repository
        llm_client: LLM client to use for generating summaries
        analyzer: CodebaseAnalyzer instance
        cache: Optional CacheManager instance
        config: Optional configuration dictionary
        processing_order: Optional list of file paths in the desired processing order
        
    Returns:
        Dictionary mapping file paths to processed FileInfo objects
        
    Raises:
        FileProcessingError: If there's an error processing files
    """
    
    async def process_file(file_info: FileInfo, repo_path: Path, llm_client: BaseLLMClient, cache: Optional[CacheManager] = None) -> Optional[str]:
        """Process a single file with the LLM.
        
        Args:
            file_info: FileInfo object for the file to process
            repo_path: Path to the repository
            llm_client: LLM client to use for generating summaries
            cache: Optional CacheManager instance
            
        Returns:
            Generated summary or None if processing failed
            
        Raises:
            LLMError: If there's an error with the LLM client
        """
        try:
            file_path = file_info.path
            
            # Check cache first
            if cache and cache.enabled:
                cached_summary = cache.get_cached_summary(repo_path / file_path)
                if cached_summary:
                    return cached_summary
            
            # If not in cache, generate with LLM
            content = file_info.content
            if not content:
                return None
                
            # Generate summary using LLM
            prompt = f"""
            File: {file_path}
            
            Content:
            ```
            {content}
            ```
            
            Please provide a concise summary of this file's purpose and functionality.
            """
            
            # Use the LLM client to generate the summary
            try:
                summary = await llm_client.generate_summary(prompt)
            except Exception as e:
                raise LLMError(f"Failed to generate summary for {file_path}: {str(e)}") from e
            
            # Cache the result if caching is enabled
            if cache and cache.enabled and summary:
                cache.save_summary(repo_path / file_path, summary)
                
            return summary
            
        except Exception as e:
            logging.error(f"Error processing file {file_path}: {e}")
            return None
    
    # Helper function for processing a file and updating progress
    async def process_and_update(path: str, info: FileInfo) -> Tuple[str, FileInfo]:
        """Process a file and update progress.
        
        Args:
            path: Path to the file
            info: FileInfo object for the file
            
        Returns:
            Tuple of (path, updated FileInfo)
        """
        try:
            summary = await process_file(info, repo_path, llm_client, cache if cache_enabled else None)
            if summary:
                info.summary = summary
                info.from_cache = True
            pbar.update(1)
            return path, info
        except Exception as e:
            logging.error(f"Error processing {path}: {e}")
            pbar.update(1)
            return path, info
    
    try:
        # Prepare processing order
        if processing_order is None:
            processing_order = list(manifest.keys())
        else:
            # Ensure all files in manifest are included in processing_order
            missing_files = set(manifest.keys()) - set(processing_order)
            if missing_files:
                logging.warning(f"Adding {len(missing_files)} files missing from processing order")
                processing_order.extend(missing_files)
        
        if not processing_order:
            logging.warning("No files to process!")
            return manifest
        
        # Start time for the entire processing operation
        total_start_time = time.time()
        
        print(f"\nProcessing {len(processing_order)} files...")
        
        # If in test mode, limit to first 5 files while maintaining order
        if config and config.get('test_mode'):
            processing_order = processing_order[:5]
            print(f"Test mode: Limited to first {len(processing_order)} files")
            # Log which files will be processed
            for i, file_path in enumerate(processing_order, 1):
                logging.debug(f"{i}. Processing: {file_path}")
        
        # Get concurrency setting
        concurrency = 1
        if config:
            scribe_config = ScribeConfig.from_dict(config)
            concurrency = scribe_config.get_concurrency()
        
        # Create a new manifest with ordered files
        ordered_manifest = {path: manifest[path] for path in processing_order}
        
        # Track cache statistics
        cache_stats = {"from_cache": 0, "from_llm": 0, "skipped": 0}
        
        # Create progress bar
        with create_file_processing_progress_bar(repo_path, len(ordered_manifest), concurrency) as pbar:
            # Process binary files separately (they don't need LLM)
            binary_files = {path: info for path, info in ordered_manifest.items() if info.is_binary}
            for file_path, file_info in binary_files.items():
                cache_stats["skipped"] += 1
                pbar.update(1)
            
            # Process non-binary files concurrently
            non_binary_files = {path: info for path, info in ordered_manifest.items() if not info.is_binary}
            
            # Check which files are already in cache - only if cache is enabled AND no-cache flag is not set
            cache_enabled = cache and cache.enabled and not (config and config.get('no_cache', False))
            if cache_enabled:
                cached_files = {}
                for file_path, file_info in non_binary_files.items():
                    cached_summary = cache.get_cached_summary(repo_path / file_path)
                    if cached_summary:
                        file_info.summary = cached_summary
                        file_info.from_cache = True
                        cached_files[file_path] = file_info
                        cache_stats["from_cache"] += 1
                        pbar.update(1)
                
                # Remove cached files from the processing list
                for file_path in cached_files:
                    non_binary_files.pop(file_path)
                    ordered_manifest[file_path] = cached_files[file_path]
            
            # Process remaining files concurrently
            if non_binary_files:
                cache_stats["from_llm"] += len(non_binary_files)
                
                # Create a task for each file and process concurrently
                tasks = []
                for file_path, file_info in non_binary_files.items():
                    task = asyncio.create_task(process_and_update(file_path, file_info))
                    tasks.append(task)
                
                # Wait for all tasks to complete
                for completed_task in asyncio.as_completed(tasks):
                    file_path, file_info = await completed_task
                    ordered_manifest[file_path] = file_info
        
        # Display cache statistics
        total_elapsed = time.time() - total_start_time
        display_cache_stats(cache_stats, total_elapsed, cache and cache.enabled)
        
        # Display GitHub repository cache statistics
        display_github_cache_stats(config, analyzer)
        
        return ordered_manifest
        
    except Exception as e:
        raise FileProcessingError(f"Error processing files: {str(e)}") from e
# Function moved to src/utils/doc_utils.py

async def main():
    """Main entry point for the codebase-scribe tool."""
    parser = argparse.ArgumentParser(description='Generate documentation for a code repository')
    
    # Create a mutually exclusive group for repo source
    repo_source = parser.add_mutually_exclusive_group(required=True)
    repo_source.add_argument('--repo', help='Path to the local repository')
    repo_source.add_argument('--github', help='GitHub repository URL (e.g., https://github.com/username/repo)')
    
    # Add authentication options for GitHub
    parser.add_argument('--github-token', help='GitHub Personal Access Token for private repositories')
    parser.add_argument('--keep-clone', action='store_true', 
                      help='Keep cloned repository after processing (default: remove)')
    
    # Add branch and PR options
    parser.add_argument('--create-pr', action='store_true',
                       help='Create a pull request with generated documentation (GitHub only)')
    parser.add_argument('--branch-name', default='docs/auto-generated-readme',
                       help='Branch name for PR creation (default: docs/auto-generated-readme)')
    parser.add_argument('--pr-title', default='Add AI-generated documentation',
                       help='Title for the pull request')
    parser.add_argument('--pr-body', default='This PR adds automatically generated README.md and ARCHITECTURE.md files.',
                       help='Body text for the pull request')
    
    # Existing arguments
    parser.add_argument('--output', '-o', default='README.md', help='Output file name')
    parser.add_argument('--config', '-c', default='config.yaml', help='Configuration file path')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--log-file', action='store_true', help='Log debug output to file')
    parser.add_argument('--test-mode', action='store_true', 
                       help='Enable test mode (process only first 5 files)')
    parser.add_argument('--no-cache', action='store_true',
                       help='Disable caching of file summaries')
    parser.add_argument('--clear-cache', action='store_true',
                       help='Clear the cache for this repository before processing')
    parser.add_argument('--optimize-order', action='store_true',
                       help='Use LLM to determine optimal file processing order')
    parser.add_argument('--llm-provider', choices=['ollama', 'bedrock'], default=None,
                       help='LLM provider to use (overrides config file)')
    args = parser.parse_args()

    # Set up logging based on debug flag
    setup_logging(debug=args.debug, log_to_file=args.log_file)
    
    # Load config and update with command-line args
    config = load_config(args.config)
    config = update_config_with_args(config, args)
    
    if config.debug:
        logging.debug("Debug mode enabled")
    
    # Convert to dictionary for backward compatibility with existing code
    config_dict = config_to_dict(config)
    
    # Get GitHub token from args or environment
    github_token = args.github_token
    if not github_token and 'GITHUB_TOKEN' in os.environ:
        github_token = os.environ.get('GITHUB_TOKEN')
        if github_token:
            print("Using GitHub token from environment variables")
    
    # Temp directory for cloned repo
    temp_dir = None
    
    # Create output directory for potential copying later (only if needed)
    output_dir = None
    if args.github:
        # Create an output directory in the script's location
        script_dir = Path(__file__).parent.absolute()
        output_dir = script_dir / "generated_docs"
        os.makedirs(output_dir, exist_ok=True)
        
        # Create a .gitignore file in the output directory if it doesn't exist
        gitignore_path = output_dir / ".gitignore"
        if not gitignore_path.exists():
            with open(gitignore_path, "w") as f:
                f.write("# Ignore all generated documentation\n*\n!.gitignore\n")
        
        print(f"Generated files will be saved to: {output_dir}")

    try:
        # Check if the user wants to create a PR
        create_pr = args.create_pr
        
        if create_pr and args.repo:
            print("Warning: --create-pr can only be used with --github. Ignoring PR creation.")
            create_pr = False
            
        if create_pr and not github_token:
            print("Error: GitHub token is required for PR creation. Use --github-token or set GITHUB_TOKEN environment variable.")
            return
            
        # Process GitHub URL if provided 
        if args.github:
            # Validate GitHub URL
            if not is_valid_github_url(args.github):
                print(f"Error: Invalid GitHub repository URL: {args.github}")
                print("Expected format: https://github.com/username/repository")
                return
                
            # Extract a stable repo identifier for caching
            repo_owner, repo_name = extract_repo_info(args.github)
            repo_id = f"{repo_owner}/{repo_name}"
            print(f"Using repository ID for caching: {repo_id}")
            
            # Clone the repository
            print(f"Cloning GitHub repository: {args.github}")
            try:
                temp_dir = await clone_github_repository(args.github, github_token)
                repo_path = Path(temp_dir).absolute()
                print(f"Repository cloned successfully to: {repo_path}")
                
                # Tell analyzer to use the stable repo ID for caching
                config_dict['github_repo_id'] = repo_id
                config = dict_to_config(config_dict)
            except Exception as e:
                print(f"Error: {e}")
                return
        else:
            # Use provided local repository path
            repo_path = Path(args.repo).absolute()
        
        # Handle cache clearing first and exit
        if args.clear_cache:
            analyzer = CodebaseAnalyzer(repo_path, config_dict)
            analyzer.cache.clear_repo_cache()
            print(f"Cleared cache for repository: {repo_path.name}")
            
            # Also clear the global cache for this repository
            CacheManager.clear_all_caches(repo_path=repo_path, config=config_dict)
            
            if temp_dir and not args.keep_clone:
                shutil.rmtree(temp_dir, ignore_errors=True)
            return  # Exit after clearing cache
        
        # Initialize LLM client using factory
        print(f"Initializing {config.llm_provider} client...")
        
        try:
            # Create and initialize the appropriate LLM client
            llm_client = await LLMClientFactory.create_client(config_dict)
        except Exception as e:
            print(f"Failed to initialize LLM client: {e}")
            sys.exit(1)
        
        # Now start repository analysis
        print("\nInitializing repository analysis...")
        analyzer = CodebaseAnalyzer(repo_path, config_dict)
        
        # First analyze repository to get file manifest
        print("Analyzing repository structure...")
        manifest = await analyzer.analyze_repository(show_progress=True)  # Enable progress bar
        
        if not manifest:
            print("No files found to analyze!")
            return
        
        print(f"\nFound {len(manifest)} files to analyze")
        
        # Set project structure and get processing order
        llm_client.set_project_structure(manifest)
        processing_order = None
        if config.optimize_order:
            print("Determining optimal file processing order...")
            logging.info(f"Starting file order optimization with {len(manifest)} files")
            optimization_start = time.time()
            processing_order = await determine_processing_order(manifest, llm_client)
            optimization_time = time.time() - optimization_start
            logging.info(f"File order optimization completed in {optimization_time:.2f} seconds")
            print(f"Optimized processing order determined for {len(processing_order)} files")
        else:
            # Skip LLM ordering if not enabled
            print("Using default file processing order...")
            processing_order = list(manifest.keys())
            logging.info(f"Using default file order with {len(processing_order)} files")
        
        # Process files with analyzer instance
        processed_files = await process_files(
            manifest=manifest,  # Now manifest should have content
            repo_path=repo_path,
            llm_client=llm_client,
            analyzer=analyzer,
            cache=analyzer.cache,
            config=config_dict,
            processing_order=processing_order
        )

        # Add a newline for better spacing after file processing
        print("\n")

        # Generate documentation with progress tracking
        # Get progress tracker instance
        progress_tracker = ProgressTracker.get_instance(repo_path)
        with progress_tracker.progress_bar(
            total=2,
            desc="Generating documentation",
            unit="file",
            ncols=150,
            bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
            colour='yellow'
        ) as pbar:
            # First generate and write Architecture doc
            arch_content = await generate_architecture(
                repo_path=repo_path,
                file_manifest=processed_files,
                llm_client=llm_client,
                config=config_dict
            )
            
            # Create docs directory if it doesn't exist and write ARCHITECTURE.md
            arch_dir = repo_path / "docs"
            os.makedirs(arch_dir, exist_ok=True)
            arch_path = arch_dir / "ARCHITECTURE.md"
            arch_path.write_text(arch_content, encoding='utf-8')
            pbar.update(1)
            
            # Generate badges AFTER creating the docs directory
            # This ensures the docs badge will be included if we've created the docs directory
            badges = generate_badges(processed_files, repo_path)
            logging.info(f"Generated badges: {badges}")
            
            # Add attribution to architecture document with badges
            arch_content = add_ai_attribution(arch_content, doc_type="ARCHITECTURE.md", badges=badges)
            # Write the updated content with badges
            arch_path.write_text(arch_content, encoding='utf-8')
            
            # Then generate README that links to the now-existing ARCHITECTURE.md
            readme_content = await generate_readme(
                repo_path=repo_path,
                llm_client=llm_client,
                file_manifest=processed_files,
                file_summaries=processed_files,
                config=config_dict,
                analyzer=analyzer,
                output_dir=output_dir,
                architecture_file_exists=True
            )
            
            # Add attribution to README document with badges
            readme_content = add_ai_attribution(readme_content, doc_type="README", badges=badges)
            
            # Write README.md to repository
            readme_path = repo_path / "README.md"
            readme_path.write_text(readme_content, encoding='utf-8')
            pbar.update(1)
            
            # If using GitHub with --create-pr, don't ask about copying files
            if args.github and create_pr:
                print("\nPreparing branch and creating pull request...")
                
                # First prepare the branch (cleanup existing PRs and branch)
                await prepare_github_branch(
                    github_url=args.github,
                    token=github_token,
                    branch_name=args.branch_name
                )
                
                # Create a local branch
                print(f"Creating local branch: {args.branch_name}")
                if not create_git_branch(repo_path, args.branch_name):
                    print("Failed to create git branch")
                    return
                
                # Commit the changes
                print("Committing documentation changes...")
                if not commit_documentation_changes(repo_path, "Update documentation"):
                    print("Failed to commit changes")
                    return
                
                # Push the branch to GitHub
                print(f"Pushing branch {args.branch_name} to GitHub...")
                if not await push_branch_to_remote(repo_path, args.branch_name, github_token, args.github):
                    print("Failed to push branch to GitHub")
                    return
                
                # Then create the pull request
                pr_url = await create_pull_request(
                    github_url=args.github,
                    token=github_token,
                    branch_name=args.branch_name,
                    pr_title=args.pr_title,
                    pr_body=args.pr_body
                )
                
                if pr_url:
                    print(f"✅ Pull request created successfully: {pr_url}")
                else:
                    print("❌ Failed to create pull request")
            # Only ask about copying files if we're using GitHub without PR creation
            elif args.github and not create_pr and output_dir:
                # Copy generated files to output directory
                copy_choice = input(f"\nDo you want to copy the generated files to {output_dir}? (y/n): ").lower()
                if copy_choice.startswith('y'):
                    # Copy README.md
                    shutil.copy2(readme_path, output_dir / "README.md")
                    # Copy ARCHITECTURE.md
                    os.makedirs(output_dir / "docs", exist_ok=True)
                    shutil.copy2(arch_path, output_dir / "docs" / "ARCHITECTURE.md")
                    print(f"Files copied to {output_dir}")
        
        # Final success message
        print(f"\nSuccessfully generated documentation:")
        if output_dir and args.github:
            print(f"- README.md: {readme_path}")
            print(f"- docs/ARCHITECTURE.md: {arch_path}")
            print(f"\nFiles are saved in: {output_dir}")
            print("These files won't overwrite the script's own documentation.")
        
    finally:
        # Clean up temporary directory if we created one
        if temp_dir and not args.keep_clone and not (create_pr and args.keep_clone):
            print(f"Cleaning up temporary repository: {temp_dir}")
            try:
                def make_writable(path):
                    """Make a file or directory writable."""
                    try:
                        os.chmod(path, 0o777)
                    except:
                        pass  # Ignore errors and continue
                
                # Make all files and directories writable to ensure we can delete them
                if os.path.exists(temp_dir):
                    for root, dirs, files in os.walk(temp_dir, topdown=False):
                        for file in files:
                            make_writable(os.path.join(root, file))
                        for dir_name in dirs:
                            make_writable(os.path.join(root, dir_name))
                
                # Try to remove the directory
                shutil.rmtree(temp_dir, ignore_errors=True)
                
                # If directory still exists, try platform-specific commands as a last resort
                if os.path.exists(temp_dir):
                    print(f"Standard cleanup failed, trying alternative method...")
                    if os.name == 'nt':  # Windows
                        os.system(f'rmdir /S /Q "{temp_dir}"')
                    else:  # Unix/Linux/Mac
                        os.system(f'rm -rf "{temp_dir}"')
            except Exception as e:
                print(f"Warning: Could not fully clean up temporary directory: {e}")
                print(f"You may need to manually delete: {temp_dir}")

if __name__ == "__main__":
    asyncio.run(main())