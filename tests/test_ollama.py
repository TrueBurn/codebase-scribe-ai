import pytest
from unittest.mock import AsyncMock, MagicMock
from src.clients.ollama import OllamaClient, OllamaClientError

@pytest.fixture
def mock_ollama_response():
    return MagicMock(response="Test response")

@pytest.fixture
def ollama_client(config, mock_ollama_response):
    client = OllamaClient(config['ollama'])
    # Mock the AsyncClient
    client.client = AsyncMock()
    client.client.generate = AsyncMock(return_value=mock_ollama_response)
    # Mock the PromptTemplate
    client.prompt_template = MagicMock()
    client.prompt_template.get_template = MagicMock(return_value="Test prompt")
    return client

@pytest.mark.asyncio
async def test_generate_summary(ollama_client):
    context = {
        'file_path': 'test.py',
        'file_type': 'python',
        'context': 'Test context'
    }
    code = 'def test(): pass'
    
    summary = await ollama_client.generate_summary(code, context)
    assert isinstance(summary, str)
    assert len(summary) > 0

@pytest.mark.asyncio
async def test_generate_project_overview(ollama_client):
    context = {
        'project_name': 'Test Project',
        'file_count': 5,
        'key_components': ['component1', 'component2']
    }
    
    overview = await ollama_client.generate_project_overview(context)
    assert isinstance(overview, str)
    assert len(overview) > 0

@pytest.mark.asyncio
async def test_retry_mechanism(ollama_client):
    # Make the generate call raise an error
    ollama_client.client.generate.side_effect = ConnectionError("Test connection error")
    
    with pytest.raises(OllamaClientError):
        await ollama_client.generate_summary('', {'file_path': ''}) 