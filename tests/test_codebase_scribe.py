#!/usr/bin/env python3

"""
Tests for codebase_scribe.py
"""

import os
import pytest
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import codebase_scribe
from src.utils.config_class import ScribeConfig
from src.utils.exceptions import ScribeError, ConfigurationError, RepositoryError
from src.models.file_info import FileInfo


@pytest.fixture
def temp_repo():
    """Create a temporary repository with test files."""
    temp_dir = tempfile.mkdtemp()
    try:
        # Create a simple project structure
        # Python files
        os.makedirs(os.path.join(temp_dir, "src", "main"), exist_ok=True)
        with open(os.path.join(temp_dir, "src", "main", "app.py"), "w") as f:
            f.write("import os\nimport sys\n\nclass App:\n    def run(self):\n        print('Running app')\n")
        
        with open(os.path.join(temp_dir, "src", "main", "utils.py"), "w") as f:
            f.write("def helper():\n    return 'Helper function'\n")
        
        # Create a README.md file
        with open(os.path.join(temp_dir, "README.md"), "w") as f:
            f.write("# Test Project\n\n## Overview\n\nThis is a test project.\n")
        
        yield Path(temp_dir)
    finally:
        # Clean up
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def config():
    """Create a test configuration."""
    return ScribeConfig(
        debug=True,
        test_mode=True,
        blacklist={
            'extensions': ['.pyc', '.pyo', '.pyd'],
            'path_patterns': ['__pycache__', '\\.git']
        },
        cache={
            'ttl': 3600,
            'max_size': 1048576
        }
    )


@pytest.mark.asyncio
async def test_setup_logging():
    """Test the setup_logging function."""
    # Test with debug=True and log_to_file=False
    with patch('logging.basicConfig') as mock_basic_config:
        codebase_scribe.setup_logging(debug=True, log_to_file=False)
        mock_basic_config.assert_called_once()
        args, kwargs = mock_basic_config.call_args
        assert kwargs['level'] == codebase_scribe.logging.DEBUG
    
    # Test with debug=False and log_to_file=False
    with patch('logging.basicConfig') as mock_basic_config:
        codebase_scribe.setup_logging(debug=False, log_to_file=False)
        mock_basic_config.assert_called_once()
        args, kwargs = mock_basic_config.call_args
        assert kwargs['level'] == codebase_scribe.logging.INFO


@pytest.mark.asyncio
async def test_determine_processing_order():
    """Test the determine_processing_order function."""
    # Create mock file manifest
    file_manifest = {
        'src/main/app.py': FileInfo(path='src/main/app.py', language='python'),
        'src/main/utils.py': FileInfo(path='src/main/utils.py', language='python'),
        'README.md': FileInfo(path='README.md', language='markdown')
    }
    
    # Create mock LLM client
    mock_llm_client = AsyncMock()
    mock_llm_client.get_file_order.return_value = [
        'README.md',
        'src/main/app.py',
        'src/main/utils.py'
    ]
    
    # Test with valid inputs
    with patch('codebase_scribe.ProgressTracker') as mock_progress_tracker:
        mock_progress_bar = MagicMock()
        mock_progress_tracker.get_instance.return_value.progress_bar.return_value.__enter__.return_value = mock_progress_bar
        
        result = await codebase_scribe.determine_processing_order(file_manifest, mock_llm_client)
        
        assert result == ['README.md', 'src/main/app.py', 'src/main/utils.py']
        mock_llm_client.get_file_order.assert_called_once_with(file_manifest)
    
    # Test with LLM returning extra files
    mock_llm_client.get_file_order.return_value = [
        'README.md',
        'src/main/app.py',
        'src/main/utils.py',
        'nonexistent.py'
    ]
    
    with patch('codebase_scribe.ProgressTracker') as mock_progress_tracker:
        mock_progress_bar = MagicMock()
        mock_progress_tracker.get_instance.return_value.progress_bar.return_value.__enter__.return_value = mock_progress_bar
        
        result = await codebase_scribe.determine_processing_order(file_manifest, mock_llm_client)
        
        assert set(result) == set(['README.md', 'src/main/app.py', 'src/main/utils.py'])
        assert 'nonexistent.py' not in result
    
    # Test with LLM returning missing files
    mock_llm_client.get_file_order.return_value = [
        'README.md',
        'src/main/app.py'
    ]
    
    with patch('codebase_scribe.ProgressTracker') as mock_progress_tracker:
        mock_progress_bar = MagicMock()
        mock_progress_tracker.get_instance.return_value.progress_bar.return_value.__enter__.return_value = mock_progress_bar
        
        result = await codebase_scribe.determine_processing_order(file_manifest, mock_llm_client)
        
        assert set(result) == set(['README.md', 'src/main/app.py', 'src/main/utils.py'])
    
    # Test with LLM raising an exception
    mock_llm_client.get_file_order.side_effect = Exception("LLM error")
    
    with patch('codebase_scribe.ProgressTracker') as mock_progress_tracker:
        mock_progress_bar = MagicMock()
        mock_progress_tracker.get_instance.return_value.progress_bar.return_value.__enter__.return_value = mock_progress_bar
        
        result = await codebase_scribe.determine_processing_order(file_manifest, mock_llm_client)
        
        assert set(result) == set(['src/main/app.py', 'src/main/utils.py', 'README.md'])


@pytest.mark.asyncio
async def test_process_files(temp_repo, config):
    """Test the process_files function."""
    # Create mock file manifest
    file_manifest = {
        'src/main/app.py': FileInfo(path='src/main/app.py', language='python', content='print("Hello")'),
        'src/main/utils.py': FileInfo(path='src/main/utils.py', language='python', content='print("World")'),
        'README.md': FileInfo(path='README.md', language='markdown', content='# Test')
    }
    
    # Create mock LLM client
    mock_llm_client = AsyncMock()
    mock_llm_client.generate_summary.return_value = "Test summary"
    
    # Create mock analyzer
    mock_analyzer = MagicMock()
    mock_analyzer.cache.enabled = True
    mock_analyzer.cache.get_cached_summary.return_value = None
    
    # Test with valid inputs
    with patch('codebase_scribe.ProgressTracker') as mock_progress_tracker:
        mock_progress_bar = MagicMock()
        mock_progress_tracker.get_instance.return_value.progress_bar.return_value.__enter__.return_value = mock_progress_bar
        
        # Create a simple config dictionary instead of using config.to_dict()
        config_dict = {
            'debug': True,
            'test_mode': True,
            'no_cache': True,
            'blacklist': {
                'extensions': ['.pyc', '.pyo', '.pyd'],
                'path_patterns': ['__pycache__', '\\.git']
            }
        }
        
        result = await codebase_scribe.process_files(
            manifest=file_manifest,
            repo_path=temp_repo,
            llm_client=mock_llm_client,
            analyzer=mock_analyzer,
            config=config_dict
        )
        
        assert len(result) == 3
        assert mock_llm_client.generate_summary.call_count == 3


@pytest.mark.asyncio
async def test_add_ai_attribution():
    """Test the add_ai_attribution function."""
    # Test with content that doesn't have attribution
    content = "# Test Document\n\nThis is a test document."
    result = codebase_scribe.add_ai_attribution(content, doc_type="TEST", badges="![Badge](badge.svg)")
    
    assert "# Test Document" in result
    assert "![Badge](badge.svg)" in result
    assert "_This TEST was generated using AI analysis" in result
    
    # Test with content that already has attribution
    content_with_attribution = "# Test Document\n\nThis is a test document.\n\n---\n_This TEST was generated using AI analysis and may contain inaccuracies. Please verify critical information._"
    result = codebase_scribe.add_ai_attribution(content_with_attribution, doc_type="TEST", badges="![Badge](badge.svg)")
    
    assert "# Test Document" in result
    assert "![Badge](badge.svg)" in result
    assert result.count("_This TEST was generated using AI analysis") == 1  # Should not add another attribution


@pytest.mark.asyncio
async def test_main_with_local_repo(temp_repo):
    """Test the main function with a local repository."""
    # Mock command line arguments
    mock_args = MagicMock()
    mock_args.repo = str(temp_repo)
    mock_args.github = None
    mock_args.debug = True
    mock_args.test_mode = True
    mock_args.no_cache = True
    mock_args.optimize_order = False
    mock_args.clear_cache = False
    mock_args.github_token = None
    mock_args.keep_clone = False
    mock_args.create_pr = False
    mock_args.output = "README.md"
    mock_args.config = "config.yaml"
    mock_args.log_file = False
    mock_args.llm_provider = None
    
    # Mock argparse
    with patch('argparse.ArgumentParser.parse_args', return_value=mock_args):
        # Mock setup_logging
        with patch('codebase_scribe.setup_logging') as mock_setup_logging:
            # Mock load_config
            with patch('codebase_scribe.load_config', return_value={}) as mock_load_config:
                # Mock LLMClientFactory
                with patch('codebase_scribe.LLMClientFactory') as mock_llm_factory:
                    mock_llm_client = AsyncMock()
                    # Set up the create_client method as an AsyncMock that returns the mock_llm_client
                    mock_llm_factory.create_client = AsyncMock(return_value=mock_llm_client)
                    
                    # Mock CodebaseAnalyzer
                    with patch('codebase_scribe.CodebaseAnalyzer') as mock_analyzer_class:
                        mock_analyzer = MagicMock()
                        file_manifest = {
                            'src/main/app.py': FileInfo(path='src/main/app.py', language='python', content='print("Hello")'),
                            'src/main/utils.py': FileInfo(path='src/main/utils.py', language='python', content='print("World")'),
                            'README.md': FileInfo(path='README.md', language='markdown', content='# Test')
                        }
                        # Make analyze_repository an AsyncMock that returns the file_manifest
                        mock_analyzer.analyze_repository = AsyncMock(return_value=file_manifest)
                        mock_analyzer.cache.enabled = True
                        mock_analyzer_class.return_value = mock_analyzer
                        
                        # Mock process_files as an AsyncMock
                        with patch('codebase_scribe.process_files', new_callable=AsyncMock) as mock_process_files:
                            mock_process_files.return_value = file_manifest
                            
                            # Mock generate_architecture as an AsyncMock
                            with patch('codebase_scribe.generate_architecture', new_callable=AsyncMock) as mock_generate_architecture:
                                mock_generate_architecture.return_value = "# Architecture\n\nThis is the architecture document."
                                
                                # Mock generate_readme as an AsyncMock
                                with patch('codebase_scribe.generate_readme', new_callable=AsyncMock) as mock_generate_readme:
                                    mock_generate_readme.return_value = "# README\n\nThis is the README document."
                                    
                                    # Mock generate_badges
                                    with patch('codebase_scribe.generate_badges') as mock_generate_badges:
                                        mock_generate_badges.return_value = "![Badge](badge.svg)"
                                        
                                        # Mock Path.write_text
                                        with patch('pathlib.Path.write_text') as mock_write_text:
                                            # Run the main function
                                            await codebase_scribe.main()
                                            
                                            # Verify the function calls
                                            mock_setup_logging.assert_called_once()
                                            mock_load_config.assert_called_once()
                                            mock_llm_factory.create_client.assert_called_once()
                                            mock_analyzer_class.assert_called_once()
                                            mock_analyzer.analyze_repository.assert_called_once()
                                            mock_process_files.assert_called_once()
                                            mock_generate_architecture.assert_called_once()
                                            mock_generate_readme.assert_called_once()
                                            mock_generate_badges.assert_called_once()
                                            assert mock_write_text.call_count >= 2  # At least README.md and ARCHITECTURE.md