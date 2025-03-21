#!/usr/bin/env python3

"""
Utilities for cache management and statistics.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional

from src.utils.cache import CacheManager
from src.analyzers.codebase import CodebaseAnalyzer


def display_cache_stats(cache_stats: Dict[str, int], total_elapsed: float, cache_enabled: bool) -> None:
    """Display cache statistics.
    
    Args:
        cache_stats: Dictionary containing cache statistics (from_cache, from_llm, skipped)
        total_elapsed: Total elapsed time in seconds
        cache_enabled: Whether caching is enabled
    """
    total_mins, total_secs = divmod(int(total_elapsed), 60)
    total_hrs, total_mins = divmod(total_mins, 60)
    
    if total_hrs > 0:
        total_time_str = f"{total_hrs:02d}:{total_mins:02d}:{total_secs:02d}"
    else:
        total_time_str = f"{total_mins:02d}:{total_secs:02d}"
    
    if cache_enabled:
        total_processed = cache_stats["from_cache"] + cache_stats["from_llm"]
        if total_processed > 0:
            cache_percent = (cache_stats["from_cache"] / total_processed) * 100
            print(f"\nCache statistics: {cache_stats['from_cache']} files from cache ({cache_percent:.1f}%), " +
                  f"{cache_stats['from_llm']} files processed by LLM, {cache_stats['skipped']} binary files skipped")
            print(f"Total processing time: {total_time_str}")


def display_github_cache_stats(config: Dict[str, Any], analyzer: CodebaseAnalyzer) -> None:
    """Display GitHub repository cache statistics.
    
    Args:
        config: Configuration dictionary
        analyzer: CodebaseAnalyzer instance
    """
    if config and config.get('github_repo_id'):
        print("\nCache statistics for GitHub repository:")
        print(f"Repository ID: {config['github_repo_id']}")
        print(f"Cache directory: {analyzer.cache.get_repo_cache_dir()}")
        
        # Check if cache is enabled
        if analyzer.cache.enabled:
            print("Cache is enabled")
        else:
            print("Cache is disabled")
            
        # Print cache hit rate
        cache_hits = sum(1 for file_info in analyzer.file_manifest.values() 
                       if hasattr(file_info, 'from_cache') and file_info.from_cache)
        total_files = len(analyzer.file_manifest)
        cache_hit_rate = cache_hits / total_files * 100 if total_files > 0 else 0
        
        print(f"Cache hit rate: {cache_hits}/{total_files} files ({cache_hit_rate:.1f}%)")


def clear_all_caches(repo_path: Path, config: Dict[str, Any]) -> None:
    """Clear all caches for a repository.
    
    Args:
        repo_path: Path to the repository
        config: Configuration dictionary
    """
    CacheManager.clear_all_caches(repo_path=repo_path, config=config)
    print(f"Cleared all caches for repository: {repo_path.name}")