import pytest
from pathlib import Path
from src.analyzers.codebase import CodebaseAnalyzer
from src.clients.ollama import OllamaClient
from src.utils.config import ConfigManager

@pytest.fixture
def config():
    return ConfigManager("config.yaml")

@pytest.fixture
def repo_path():
    return Path(__file__).parent.parent

@pytest.mark.asyncio
async def test_basic_analysis(config, repo_path):
    analyzer = CodebaseAnalyzer(repo_path, config)
    manifest = analyzer.analyze_repository()  # Removed await since this is not an async method
    assert manifest is not None
    assert len(manifest) > 0