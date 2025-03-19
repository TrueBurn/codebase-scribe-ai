#!/usr/bin/env python3

import argparse
import asyncio
from pathlib import Path
from typing import Dict, Optional
import sys
import logging
import psutil
import time
import urllib3
import warnings
import os
import shutil
import urllib.parse
from dotenv import load_dotenv
import re

# Load environment variables from .env file
load_dotenv()

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)

# Disable bytecode caching
sys.dont_write_bytecode = True

from src.utils.config import load_config
from src.analyzers.codebase import CodebaseAnalyzer
from src.clients.ollama import OllamaClient
from src.generators.readme import generate_readme
from src.generators.architecture import generate_architecture
from src.utils.cache import CacheManager
from src.utils.progress import ProgressTracker
from src.models.file_info import FileInfo
from src.clients.llm_factory import LLMClientFactory
from src.clients.base_llm import BaseLLMClient

# Import the GitHub utilities
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

# Import the new badges utility
from src.utils.badges import generate_badges

def setup_logging(debug=False, log_to_file=True):
    """Configure logging based on debug flag."""
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

async def process_file(file_info: FileInfo, repo_path: Path, llm_client: BaseLLMClient, cache: Optional[CacheManager] = None) -> Optional[str]:
    """Process a single file with the LLM."""
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
        summary = await llm_client.generate_summary(prompt)
        
        # Cache the result if caching is enabled
        if cache and cache.enabled and summary:
            cache.save_summary(repo_path / file_path, summary)
            
        return summary
        
    except Exception as e:
        logging.error(f"Error processing file {file_path}: {e}")
        return None

def calculate_max_concurrent() -> int:
    """Calculate optimal number of concurrent operations based on system resources."""
    try:
        # Get CPU count and available memory
        cpu_count = psutil.cpu_count(logical=False) or 1  # Physical CPU count
        memory_percent = psutil.virtual_memory().percent
        
        # Base concurrency on CPU count but reduce if memory usage is high
        if memory_percent > 80:
            return 1  # Sequential if memory pressure is high
        elif memory_percent > 60:
            return max(1, cpu_count // 2)  # Half of CPUs if moderate memory pressure
        else:
            return max(1, cpu_count)  # Use physical CPU count, minimum 1
            
    except Exception as e:
        logging.warning(f"Error calculating concurrency, defaulting to 1: {e}")
        return 1

async def determine_processing_order(
    file_manifest: Dict[str, FileInfo],
    ollama: OllamaClient
) -> list[str]:
    """Ask LLM to determine optimal file processing order based on project structure."""
    logging.info(f"Starting file ordering optimization for {len(file_manifest)} files")
    
    # Get progress tracker instance
    progress_tracker = ProgressTracker.get_instance(Path("."))
    with progress_tracker.progress_bar(
        desc="Determining optimal file processing order",
        total=5,  # Five stages: start, filtering, request, parsing, validation
        unit="step",
        ncols=150,  # Increased width from 100 to 150
        bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} steps {elapsed}',
        mininterval=0.1,
        colour='cyan'
    ) as pbar:
        try:
            # Stage 1: Starting
            pbar.update(1)
            
            # Log before LLM call
            logging.info("Starting LLM call for file ordering")
            start_time = time.time()
            
            # Get order from LLM
            processing_order = await ollama.get_file_order(file_manifest)
            
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
    config: Optional[dict] = None,
    processing_order: Optional[list] = None
) -> Dict[str, FileInfo]:
    """Process files concurrently with progress tracking."""
    # Use provided order or get all files if none provided
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
    
    # Get concurrency from config file based on the LLM provider
    llm_provider = config.get('llm_provider', 'ollama').lower()
    if llm_provider == 'bedrock':
        concurrency = config.get('bedrock', {}).get('concurrency', 1)
    else:
        concurrency = config.get('ollama', {}).get('concurrency', 1)
    
    semaphore = asyncio.Semaphore(concurrency)
    
    # Create a new manifest with ordered files
    ordered_manifest = {
        path: manifest[path]
        for path in processing_order
    }
    
    # Track cache statistics
    cache_stats = {
        "from_cache": 0,
        "from_llm": 0,
        "skipped": 0
    }
    
    # File processing progress bar (Green)
    # Get progress tracker instance
    progress_tracker = ProgressTracker.get_instance(repo_path)
    with progress_tracker.progress_bar(
        total=len(ordered_manifest),
        desc=f"Analyzing files{' (sequential)' if concurrency == 1 else f' (max {concurrency} concurrent)'}",
        unit="file",
        ncols=150,
        bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
        colour='green',
        position=0
    ) as pbar:
        # Process binary files separately (they don't need LLM)
        binary_files = {path: info for path, info in ordered_manifest.items() if info.is_binary}
        for file_path, file_info in binary_files.items():
            cache_stats["skipped"] += 1
            pbar.update(1)
        
        # Process non-binary files concurrently
        non_binary_files = {path: info for path, info in ordered_manifest.items() if not info.is_binary}
        
        # Check which files are already in cache - only if cache is enabled AND no-cache flag is not set
        cache_enabled = cache and cache.enabled and not config.get('no_cache', False)
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
                async def process_and_update(path, info):
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
                
                task = asyncio.create_task(process_and_update(file_path, file_info))
                tasks.append(task)
            
            # Wait for all tasks to complete
            for completed_task in asyncio.as_completed(tasks):
                file_path, file_info = await completed_task
                ordered_manifest[file_path] = file_info
    
    # Display cache statistics with total processing time
    total_elapsed = time.time() - total_start_time
    total_mins, total_secs = divmod(int(total_elapsed), 60)
    total_hrs, total_mins = divmod(total_mins, 60)
    
    if total_hrs > 0:
        total_time_str = f"{total_hrs:02d}:{total_mins:02d}:{total_secs:02d}"
    else:
        total_time_str = f"{total_mins:02d}:{total_secs:02d}"
    
    if cache and cache.enabled:
        total_processed = cache_stats["from_cache"] + cache_stats["from_llm"]
        if total_processed > 0:
            cache_percent = (cache_stats["from_cache"] / total_processed) * 100
            print(f"\nCache statistics: {cache_stats['from_cache']} files from cache ({cache_percent:.1f}%), " +
                  f"{cache_stats['from_llm']} files processed by LLM, {cache_stats['skipped']} binary files skipped")
            print(f"Total processing time: {total_time_str}")
    
    # Add this after the file processing loop
    # Print cache statistics more clearly
    if config and config.get('github_repo_id'):
        print("\nCache statistics for GitHub repository:")
        print(f"Repository ID: {config['github_repo_id']}")
        print(f"Cache directory: {analyzer.cache.get_repo_cache_dir()}")
        
        # Check if cache is enabled
        if analyzer.cache.enabled:
            print("Cache is enabled")
        else:
            print("Cache is disabled")
            
        # Print cache hit rate - fix the attribute access
        cache_hits = sum(1 for file_info in analyzer.file_manifest.values() 
                        if hasattr(file_info, 'from_cache') and file_info.from_cache)
        total_files = len(analyzer.file_manifest)
        cache_hit_rate = cache_hits / total_files * 100 if total_files > 0 else 0
        
        print(f"Cache hit rate: {cache_hits}/{total_files} files ({cache_hit_rate:.1f}%)")
    
    return ordered_manifest

# Update the add_ai_attribution function to be simpler and more focused
def add_ai_attribution(content: str, doc_type: str = "documentation", badges: str = "") -> str:
    """Add AI attribution footer and badges to generated content if not already present."""
    attribution_text = f"\n\n---\n_This {doc_type} was generated using AI analysis and may contain inaccuracies. Please verify critical information._"
    
    # Check if content already has an attribution footer
    if "_This " in content and ("generated" in content.lower() or "enhanced" in content.lower()) and "AI" in content:
        # Already has attribution, just add badges if needed
        if badges and "![" not in content[:500]:  # Only add badges if they don't exist in the first 500 chars
            # Find the title line
            title_match = re.search(r"^# (.+?)(?:\n|$)", content)
            if title_match:
                # Insert badges after the title
                title_end = title_match.end()
                content = content[:title_end] + "\n\n" + badges + "\n" + content[title_end:]
        return content
    
    # Add badges after the title if provided
    if badges:
        title_match = re.search(r"^# (.+?)(?:\n|$)", content)
        if title_match:
            # Insert badges after the title
            title_end = title_match.end()
            content = content[:title_end] + "\n\n" + badges + "\n" + content[title_end:]
    
    # Add the attribution
    return content + attribution_text

async def main():
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
    
    # Load config and merge with command-line args
    config = load_config(args.config)
    if args.debug:
        config['debug'] = True
        logging.debug("Debug mode enabled")
    if args.test_mode:
        config['test_mode'] = True
    if args.no_cache:
        config['no_cache'] = True
    if args.optimize_order:
        config['optimize_order'] = True
    if args.llm_provider:
        config['llm_provider'] = args.llm_provider
    
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
                config['github_repo_id'] = repo_id
            except Exception as e:
                print(f"Error: {e}")
                return
        else:
            # Use provided local repository path
            repo_path = Path(args.repo).absolute()
        
        # Handle cache clearing first and exit
        if args.clear_cache:
            analyzer = CodebaseAnalyzer(repo_path, config)
            analyzer.cache.clear_repo_cache()
            print(f"Cleared cache for repository: {repo_path.name}")
            
            # Also clear the global cache for this repository
            from src.utils.cache import CacheManager
            CacheManager.clear_all_caches(repo_path=repo_path, config=config)
            
            if temp_dir and not args.keep_clone:
                shutil.rmtree(temp_dir, ignore_errors=True)
            return  # Exit after clearing cache
        
        # Initialize LLM client using factory
        print(f"Initializing {config.get('llm_provider', 'ollama')} client...")
        
        try:
            # Create and initialize the appropriate LLM client
            llm_client = await LLMClientFactory.create_client(config)
        except Exception as e:
            print(f"Failed to initialize LLM client: {e}")
            sys.exit(1)
        
        # Now start repository analysis
        print("\nInitializing repository analysis...")
        analyzer = CodebaseAnalyzer(repo_path, config)
        
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
        if config.get('optimize_order', False):
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
            config=config,
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
                config=config
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
                config=config,
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
                # First, make all files writable to ensure we can delete them
                if os.path.exists(temp_dir):
                    for root, dirs, files in os.walk(temp_dir, topdown=False):
                        for file in files:
                            file_path = os.path.join(root, file)
                            try:
                                # Make the file writable
                                os.chmod(file_path, 0o777)
                            except:
                                pass  # Ignore errors and continue
                        
                        # Also make directories writable
                        for dir_name in dirs:
                            dir_path = os.path.join(root, dir_name)
                            try:
                                os.chmod(dir_path, 0o777)
                            except:
                                pass  # Ignore errors and continue
                
                # Now try to remove the directory
                shutil.rmtree(temp_dir, ignore_errors=True)
                
                # Check if directory still exists and try alternative method if needed
                if os.path.exists(temp_dir):
                    print(f"Standard cleanup failed, trying alternative method...")
                    if os.name == 'nt':  # Windows
                        # Use system command as last resort on Windows
                        os.system(f'rmdir /S /Q "{temp_dir}"')
                    else:  # Unix/Linux/Mac
                        os.system(f'rm -rf "{temp_dir}"')
            except Exception as e:
                print(f"Warning: Could not fully clean up temporary directory: {e}")
                print(f"You may need to manually delete: {temp_dir}")

if __name__ == "__main__":
    asyncio.run(main()) 