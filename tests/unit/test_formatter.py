"""
Unit tests for the formatter module.
"""

import pytest
import platform
from unittest.mock import patch, MagicMock

import config
from formatter import TextFormatter

class TestTextFormatter:
    """Tests for the TextFormatter class."""
    
    def test_init(self):
        """Test initialization of TextFormatter."""
        formatter = TextFormatter()
        
        assert formatter.use_llm == config.USE_LLM
        assert formatter.api_key == config.LLM_API_KEY
        assert formatter.model == config.LLM_MODEL
        assert formatter.prompt == config.LLM_PROMPT
    
    def test_format_text_llm_disabled(self):
        """Test that formatting is skipped when LLM is disabled."""
        # Temporarily override config.USE_LLM
        with patch('config.USE_LLM', False):
            formatter = TextFormatter()
            result = formatter.format_text("test text")
            
            assert result == "test text"  # Original text should be returned unchanged
    
    def test_format_text_empty_input(self):
        """Test formatting with empty input text."""
        formatter = TextFormatter()
        result = formatter.format_text("")
        
        assert result == ""  # Empty text should be returned unchanged
    
    def test_format_text_empty_api_key(self):
        """Test that formatting is skipped when API key is empty."""
        # Temporarily override config
        with patch('config.USE_LLM', True):
            with patch('config.LLM_API_KEY', ''):
                formatter = TextFormatter()
                result = formatter.format_text("test text")
                
                assert result == "test text"  # Original text should be returned unchanged
    
    def test_format_text_api_exception(self):
        """Test handling of API exceptions."""
        # Temporarily override config
        with patch('config.USE_LLM', True):
            with patch('config.LLM_API_KEY', 'fake_key'):
                formatter = TextFormatter()
                
                # Mock the API call to raise an exception
                with patch.object(formatter, '_call_openai_api', side_effect=Exception("API error")):
                    result = formatter.format_text("test text")
                    
                    assert result == "test text"  # Original text should be returned on error
    
    def test_format_text_success(self, mock_requests_post):
        """Test successful text formatting with mocked API response."""
        # Temporarily override config
        with patch('config.USE_LLM', True):
            with patch('config.LLM_API_KEY', 'fake_key'):
                formatter = TextFormatter()
                result = formatter.format_text("test text")
                
                assert result == "formatted text"  # Should get the mocked API response
                mock_requests_post.assert_called_once()
    
    @pytest.mark.parametrize("mode", [
        "general",
        "email",
        "command"
    ])
    def test_get_mode_prompt(self, mode):
        """Test getting the appropriate prompt for different modes."""
        formatter = TextFormatter()
        prompt = formatter._get_mode_prompt(mode)
        
        # Just verify the prompt isn't empty and is a string
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        
        # For command mode, verify it contains platform-specific content
        if mode == "command":
            is_macos = platform.system() == "Darwin"
            os_name = "macOS" if is_macos else "Linux"
            assert os_name in prompt
            assert "command-line expert" in prompt
    
    def test_call_openai_api(self, mock_requests_post):
        """Test calling the OpenAI API with proper parameters."""
        with patch('config.LLM_API_KEY', 'fake_key'):
            with patch('config.LLM_MODEL', 'test-model'):
                formatter = TextFormatter()
                result = formatter._call_openai_api("Test prompt")
                
                assert result == "formatted text"
                
                # Check that the API was called with the right parameters
                mock_requests_post.assert_called_once()
                args, kwargs = mock_requests_post.call_args
                
                assert args[0] == "https://api.openai.com/v1/chat/completions"
                assert kwargs['headers']['Authorization'] == "Bearer fake_key"
                assert kwargs['data'] is not None
                assert kwargs['timeout'] == 5