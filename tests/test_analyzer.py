import pytest
from pathlib import Path
from src.analyzers.codebase import CodebaseAnalyzer
from src.models.file_info import FileInfo

@pytest.fixture
def test_repo():
    return Path(__file__).parent / 'fixtures' / 'test_repo'

@pytest.fixture
def analyzer(test_repo, config):
    return CodebaseAnalyzer(test_repo, config)

@pytest.mark.asyncio
async def test_analyze_repository(analyzer):
    manifest = await analyzer.analyze_repository()
    assert isinstance(manifest, dict)
    assert all(isinstance(v, FileInfo) for v in manifest.values())

def test_analyze_python_files(analyzer):
    result = analyzer.analyze_python_files()
    assert isinstance(result, dict)
    assert all(path.suffix == '.py' for path in result.keys())

def test_build_dependency_graph(analyzer):
    graph = analyzer.build_dependency_graph()
    assert len(graph.nodes()) > 0
    assert all(isinstance(n, str) for n in graph.nodes()) 