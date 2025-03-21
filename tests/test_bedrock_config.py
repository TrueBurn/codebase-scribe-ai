#!/usr/bin/env python3

"""
Tests for BedrockClient with ScribeConfig
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import os
from typing import Dict, Any

from src.clients.bedrock import BedrockClient
from src.utils.config_class import ScribeConfig


@pytest.fixture
def sample_config_dict():
    """Create a sample configuration dictionary."""
    return {
        'debug': True,
        'bedrock': {
            'region': 'us-west-2',
            'model_id': 'test-model-id',
            'max_tokens': 2048,
            'retries': 5,
            'retry_delay': 2.0,
            'timeout': 60,
            'verify_ssl': False,
            'concurrency': 3,
            'temperature': 0.5
        }
    }


@pytest.fixture
def sample_config(sample_config_dict):
    """Create a sample ScribeConfig instance."""
    return ScribeConfig.from_dict(sample_config_dict)


class TestBedrockClient:
    """Test suite for BedrockClient with ScribeConfig."""

    @patch('src.clients.bedrock.load_dotenv')
    def test_init_with_dict(self, mock_load_dotenv, sample_config_dict):
        """Test initializing BedrockClient with a dictionary."""
        # Mock environment variables
        with patch.dict(os.environ, {}, clear=True):
            client = BedrockClient(sample_config_dict)
            
            assert client.region == 'us-west-2'
            assert client.model_id == 'test-model-id'
            assert client.max_tokens == 2048
            assert client.retries == 5
            assert client.retry_delay == 2.0
            assert client.timeout == 60
            assert client.verify_ssl is False
            assert client.concurrency == 3
            assert client.debug is True

    @patch('src.clients.bedrock.load_dotenv')
    def test_init_with_scribe_config(self, mock_load_dotenv, sample_config):
        """Test initializing BedrockClient with a ScribeConfig instance."""
        # Mock environment variables
        with patch.dict(os.environ, {}, clear=True):
            client = BedrockClient(sample_config)
            
            assert client.region == 'us-west-2'
            assert client.model_id == 'test-model-id'
            assert client.max_tokens == 2048
            assert client.retries == 5
            assert client.retry_delay == 2.0
            assert client.timeout == 60
            assert client.verify_ssl is False
            assert client.concurrency == 3
            assert client.debug is True

    @patch('src.clients.bedrock.load_dotenv')
    def test_env_vars_override_config(self, mock_load_dotenv, sample_config_dict):
        """Test that environment variables override configuration values."""
        # Mock environment variables
        with patch.dict(os.environ, {
            'AWS_REGION': 'eu-central-1',
            'AWS_BEDROCK_MODEL_ID': 'env-model-id',
            'AWS_VERIFY_SSL': 'false'
        }):
            client = BedrockClient(sample_config_dict)
            
            # These should be from environment variables
            assert client.region == 'eu-central-1'
            assert client.model_id == 'env-model-id'
            assert client.verify_ssl is False
            
            # These should still be from config
            assert client.max_tokens == 2048
            assert client.retries == 5

    @pytest.mark.asyncio
    @patch('src.clients.bedrock.load_dotenv')
    @patch('src.clients.bedrock.boto3')
    @patch('src.clients.bedrock.BotocoreConfig')
    async def test_initialize_method(self, mock_botocoreconfig, mock_boto3, mock_load_dotenv, sample_config):
        """Test the initialize method."""
        # Create a mock for the boto3 client
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        
        # Mock environment variables
        with patch.dict(os.environ, {}, clear=True):
            client = BedrockClient(sample_config)
            
            # Call initialize with await since it's an async method
            await client.initialize()
            
            # Check that boto3.client was called with the correct arguments
            mock_boto3.client.assert_called_once()
            args, kwargs = mock_boto3.client.call_args
            assert args[0] == 'bedrock-runtime'
            assert kwargs['region_name'] == 'us-west-2'
            
            # Check that BotocoreConfig was called with the correct arguments
            mock_botocoreconfig.assert_called_once()
            args, kwargs = mock_botocoreconfig.call_args
            assert kwargs['connect_timeout'] == 60
            assert kwargs['read_timeout'] == 60
            assert kwargs['retries']['max_attempts'] == 5