"""
Unit tests for the Ollama integration in the formatter module.
"""

import pytest
from unittest.mock import patch, MagicMock
import requests
import json

from xvoice2 import config
from xvoice2.formatter import TextFormatter
from xvoice2.main import VoiceDictationApp

class TestOllamaIntegration:
    """Tests for the Ollama integration features."""
    
    def test_init_ollama_settings(self):
        """Test that TextFormatter correctly initializes Ollama settings."""
        formatter = TextFormatter()
        
        assert formatter.use_local_llm == config.USE_LOCAL_LLM
        assert formatter.ollama_model == config.OLLAMA_MODEL
        assert formatter.ollama_url == config.OLLAMA_URL
    
    def test_format_text_with_ollama(self):
        """Test that formatter correctly uses Ollama when local LLM is enabled."""
        # Temporarily override config settings
        with patch('xvoice2.config.USE_LOCAL_LLM', True), \
             patch('xvoice2.config.USE_LLM', False):
            
            formatter = TextFormatter()
            
            # Mock the Ollama API call
            with patch.object(formatter, '_call_ollama_api', return_value="Ollama formatted text") as mock_call:
                result = formatter.format_text("test text")
                
                # Verify Ollama was used
                mock_call.assert_called_once()
                assert result == "Ollama formatted text"
    
    def test_format_text_prioritizes_ollama(self):
        """Test that Ollama is prioritized when both LLM options are enabled."""
        # Temporarily override config settings to enable both LLM options
        with patch('xvoice2.config.USE_LOCAL_LLM', True), \
             patch('xvoice2.config.USE_LLM', True), \
             patch('xvoice2.config.LLM_API_KEY', 'fake_key'):
            
            formatter = TextFormatter()
            
            # Mock both API methods
            with patch.object(formatter, '_call_ollama_api', return_value="Ollama formatted text") as mock_ollama, \
                 patch.object(formatter, '_call_openai_api', return_value="OpenAI formatted text") as mock_openai:
                
                result = formatter.format_text("test text")
                
                # Verify Ollama was used and OpenAI was not
                mock_ollama.assert_called_once()
                mock_openai.assert_not_called()
                assert result == "Ollama formatted text"
    
    def test_call_ollama_api(self):
        """Test calling the Ollama API with proper parameters."""
        with patch('xvoice2.config.OLLAMA_MODEL', 'test-model'), \
             patch('xvoice2.config.OLLAMA_URL', 'http://test-url'):
            
            formatter = TextFormatter()
            
            # Create a mock response
            mock_response = MagicMock()
            mock_response.json.return_value = {"response": "ollama formatted text"}
            
            # Mock the requests.post method
            with patch('requests.post', return_value=mock_response) as mock_post:
                result = formatter._call_ollama_api("Test prompt")
                
                assert result == "ollama formatted text"
                
                # Check that the API was called with the right parameters
                mock_post.assert_called_once()
                args, kwargs = mock_post.call_args
                
                assert args[0] == 'http://test-url'
                assert kwargs['headers']['Content-Type'] == 'application/json'
                
                # Check the data sent to the API
                data = json.loads(kwargs['data'])
                assert data['model'] == 'test-model'
                assert data['prompt'] == 'Test prompt'
                assert data['system'] == 'You are a helpful assistant that fixes grammar and punctuation only.'
                assert data['temperature'] == 0.3
                assert data['stream'] is False
                assert kwargs['timeout'] == 5
    
    def test_call_ollama_api_exception(self):
        """Test handling of Ollama API exceptions."""
        formatter = TextFormatter()
        
        # Mock the requests.post method to raise an exception
        with patch('requests.post', side_effect=requests.RequestException("Connection error")):
            result = formatter._call_ollama_api("Test prompt")
            
            assert result is None  # Should return None on error
    
    def test_check_ollama_availability_success(self):
        """Test that the application correctly checks Ollama availability."""
        # Mock the requests.get method for successful responses
        version_response = MagicMock()
        version_response.status_code = 200
        
        model_response = MagicMock()
        model_response.status_code = 200
        model_response.json.return_value = {
            "models": [
                {"name": "llama3"},
                {"name": "mistral"}
            ]
        }
        
        with patch('xvoice2.config.USE_LOCAL_LLM', True), \
             patch('xvoice2.config.OLLAMA_MODEL', 'llama3'), \
             patch('requests.get', side_effect=[version_response, model_response]):
            
            app = VoiceDictationApp()
            
            # Mock the other dependency checks to pass
            with patch.object(app.transcriber, 'is_available', return_value=True), \
                 patch.object(app.transcriber, 'is_model_available', return_value=True), \
                 patch.object(app.text_injector, 'is_available', return_value=True):
                
                result = app.check_dependencies()
                assert result is True
    
    def test_check_ollama_server_unavailable(self):
        """Test handling when Ollama server is not running."""
        with patch('xvoice2.config.USE_LOCAL_LLM', True), \
             patch('requests.get', side_effect=requests.RequestException("Connection refused")):
            
            app = VoiceDictationApp()
            
            # Mock the other dependency checks to pass
            with patch.object(app.transcriber, 'is_available', return_value=True), \
                 patch.object(app.transcriber, 'is_model_available', return_value=True), \
                 patch.object(app.text_injector, 'is_available', return_value=True):
                
                result = app.check_dependencies()
                assert result is False
    
    def test_check_ollama_model_missing(self):
        """Test handling when requested Ollama model is not available."""
        # Mock the requests.get method for successful server response but missing model
        version_response = MagicMock()
        version_response.status_code = 200
        
        model_response = MagicMock()
        model_response.status_code = 200
        model_response.json.return_value = {
            "models": [
                {"name": "mistral"},
                {"name": "llama2"}
            ]
        }
        
        with patch('xvoice2.config.USE_LOCAL_LLM', True), \
             patch('xvoice2.config.OLLAMA_MODEL', 'llama3'), \
             patch('requests.get', side_effect=[version_response, model_response]):
            
            app = VoiceDictationApp()
            
            # Mock the other dependency checks to pass
            with patch.object(app.transcriber, 'is_available', return_value=True), \
                 patch.object(app.transcriber, 'is_model_available', return_value=True), \
                 patch.object(app.text_injector, 'is_available', return_value=True):
                
                result = app.check_dependencies()
                assert result is False