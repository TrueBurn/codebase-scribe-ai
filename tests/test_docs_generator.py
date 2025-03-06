import pytest
from pathlib import Path
from src.utils.docs_generator import DevDocsGenerator

@pytest.fixture
def docs_generator(test_repo):
    return DevDocsGenerator(test_repo)

def test_generate_docs(docs_generator):
    docs = docs_generator.generate_docs()
    assert isinstance(docs, dict)
    assert 'CONTRIBUTING.md' in docs
    assert 'DEVELOPMENT.md' in docs
    assert 'API.md' in docs
    assert 'ARCHITECTURE.md' in docs

def test_api_documentation(docs_generator):
    api_doc = docs_generator._generate_api_documentation()
    assert isinstance(api_doc, str)
    assert '# API Documentation' in api_doc
    assert 'class' in api_doc.lower()
    assert 'function' in api_doc.lower()

def test_architecture_guide(docs_generator):
    arch_doc = docs_generator._generate_architecture_guide()
    assert isinstance(arch_doc, str)
    assert 'mermaid' in arch_doc.lower()
    assert 'graph' in arch_doc.lower() 