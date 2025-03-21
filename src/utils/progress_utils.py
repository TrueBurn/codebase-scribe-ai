#!/usr/bin/env python3

"""
Utilities for progress tracking and display.
"""

from pathlib import Path
from typing import Optional, Dict, Any

from src.utils.progress import ProgressTracker


def create_file_processing_progress_bar(
    repo_path: Path,
    total_files: int,
    concurrency: int,
    desc_prefix: str = "Analyzing files"
) -> Any:
    """Create a progress bar for file processing.
    
    Args:
        repo_path: Path to the repository
        total_files: Total number of files to process
        concurrency: Number of concurrent operations
        desc_prefix: Prefix for the progress bar description
        
    Returns:
        A progress bar instance
    """
    progress_tracker = ProgressTracker.get_instance(repo_path)
    return progress_tracker.progress_bar(
        total=total_files,
        desc=f"{desc_prefix}{' (sequential)' if concurrency == 1 else f' (max {concurrency} concurrent)'}",
        unit="file",
        ncols=150,
        bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
        colour='green',
        position=0
    )


def create_optimization_progress_bar(repo_path: Path) -> Any:
    """Create a progress bar for file order optimization.
    
    Args:
        repo_path: Path to the repository
        
    Returns:
        A progress bar instance
    """
    progress_tracker = ProgressTracker.get_instance(repo_path)
    return progress_tracker.progress_bar(
        desc="Determining optimal file processing order",
        total=5,  # Five stages: start, filtering, request, parsing, validation
        unit="step",
        ncols=150,
        bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} steps {elapsed}',
        mininterval=0.1,
        colour='cyan'
    )


def create_documentation_progress_bar(repo_path: Path) -> Any:
    """Create a progress bar for documentation generation.
    
    Args:
        repo_path: Path to the repository
        
    Returns:
        A progress bar instance
    """
    progress_tracker = ProgressTracker.get_instance(repo_path)
    return progress_tracker.progress_bar(
        total=2,
        desc="Generating documentation",
        unit="file",
        ncols=150,
        bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
        colour='yellow'
    )