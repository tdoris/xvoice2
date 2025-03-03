"""
Unit tests for Whisper API integration in the Transcriber class.
"""

import pytest
import os
import json
from unittest.mock import patch, MagicMock
import tempfile

import config
from transcriber import Transcriber

class TestWhisperAPI:
    """Tests for the Whisper API integration in the Transcriber class."""
    
    def test_init_with_api_enabled(self):
        """Test initialization with Whisper API enabled."""
        with patch('config.USE_WHISPER_API', True):
            with patch('config.WHISPER_API_KEY', 'test_key'):
                transcriber = Transcriber()
                
                assert transcriber.use_api is True
                assert transcriber.api_key == 'test_key'
                assert transcriber.api_model == config.WHISPER_API_MODEL
    
    def test_transcribe_routing_to_api(self):
        """Test that transcribe routes to API method when enabled."""
        with patch('config.USE_WHISPER_API', True):
            with patch('config.WHISPER_API_KEY', 'test_key'):
                transcriber = Transcriber()
                
                # Create a temporary audio file
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                    temp_file.write(b'dummy audio content')
                    temp_path = temp_file.name
                
                try:
                    # Mock the API transcription method
                    with patch.object(transcriber, '_transcribe_with_api', return_value='API transcription result') as mock_api:
                        with patch.object(transcriber, '_transcribe_with_local') as mock_local:
                            result = transcriber.transcribe(temp_path)
                            
                            # Should route to API method
                            mock_api.assert_called_once_with(temp_path)
                            # Should not call local method
                            mock_local.assert_not_called()
                            # Should return API method result
                            assert result == 'API transcription result'
                finally:
                    # Clean up the temporary file
                    os.unlink(temp_path)
    
    def test_transcribe_routing_to_local(self):
        """Test that transcribe routes to local method when API is disabled."""
        with patch('config.USE_WHISPER_API', False):
            transcriber = Transcriber()
            
            # Create a temporary audio file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(b'dummy audio content')
                temp_path = temp_file.name
            
            try:
                # Mock the transcription methods
                with patch.object(transcriber, '_transcribe_with_local', return_value='Local transcription result') as mock_local:
                    with patch.object(transcriber, '_transcribe_with_api') as mock_api:
                        result = transcriber.transcribe(temp_path)
                        
                        # Should route to local method
                        mock_local.assert_called_once_with(temp_path)
                        # Should not call API method
                        mock_api.assert_not_called()
                        # Should return local method result
                        assert result == 'Local transcription result'
            finally:
                # Clean up the temporary file
                os.unlink(temp_path)
    
    @patch('requests.post')
    def test_transcribe_with_api_success(self, mock_post):
        """Test successful Whisper API transcription."""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"text": "test api transcription"}
        mock_post.return_value = mock_response
        
        # Create a temporary audio file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_file.write(b'dummy audio content')
            temp_path = temp_file.name
        
        try:
            # Configure transcriber to use API
            with patch('config.USE_WHISPER_API', True):
                with patch('config.WHISPER_API_KEY', 'test_key'):
                    transcriber = Transcriber()
                    result = transcriber._transcribe_with_api(temp_path)
            
            # Verify the result
            assert result == "test api transcription"
            mock_post.assert_called_once()
            
            # Verify the API call parameters
            args, kwargs = mock_post.call_args
            assert args[0] == "https://api.openai.com/v1/audio/transcriptions"
            assert kwargs['headers']['Authorization'] == "Bearer test_key"
            assert 'files' in kwargs
        finally:
            # Clean up the temporary file
            os.unlink(temp_path)
    
    @patch('requests.post')
    def test_transcribe_with_api_failure(self, mock_post):
        """Test transcription behavior when API call fails."""
        # Mock API error
        mock_response = MagicMock()
        mock_response.status_code = 401  # Unauthorized
        mock_response.text = "Invalid API key"
        mock_post.return_value = mock_response
        
        # Create a temporary audio file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_file.write(b'dummy audio content')
            temp_path = temp_file.name
        
        try:
            # Configure transcriber to use API
            with patch('config.USE_WHISPER_API', True):
                with patch('config.WHISPER_API_KEY', 'invalid_key'):
                    transcriber = Transcriber()
                    result = transcriber._transcribe_with_api(temp_path)
            
            # Should return None on API error
            assert result is None
        finally:
            # Clean up the temporary file
            os.unlink(temp_path)
    
    @patch('requests.post')
    def test_transcribe_with_api_exception(self, mock_post):
        """Test handling of exceptions during API calls."""
        # Mock exception during API call
        mock_post.side_effect = Exception("Network error")
        
        # Create a temporary audio file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_file.write(b'dummy audio content')
            temp_path = temp_file.name
        
        try:
            # Configure transcriber to use API
            with patch('config.USE_WHISPER_API', True):
                with patch('config.WHISPER_API_KEY', 'test_key'):
                    transcriber = Transcriber()
                    result = transcriber._transcribe_with_api(temp_path)
            
            # Should return None on exception
            assert result is None
        finally:
            # Clean up the temporary file
            os.unlink(temp_path)
    
    @patch('requests.get')
    def test_is_api_available_success(self, mock_get):
        """Test successful API availability check."""
        # Mock successful models API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": "whisper-1"},
                {"id": "other-model"}
            ]
        }
        mock_get.return_value = mock_response
        
        # Configure transcriber to use API
        with patch('config.USE_WHISPER_API', True):
            with patch('config.WHISPER_API_KEY', 'test_key'):
                with patch('config.WHISPER_API_MODEL', 'whisper-1'):
                    transcriber = Transcriber()
                    result = transcriber.is_api_available()
        
        # Should return True when API and model are available
        assert result is True
        mock_get.assert_called_once()
    
    @patch('requests.get')
    def test_is_api_available_failure(self, mock_get):
        """Test API availability check when API is unavailable."""
        # Mock API error
        mock_response = MagicMock()
        mock_response.status_code = 401  # Unauthorized
        mock_get.return_value = mock_response
        
        # Configure transcriber to use API
        with patch('config.USE_WHISPER_API', True):
            with patch('config.WHISPER_API_KEY', 'invalid_key'):
                transcriber = Transcriber()
                result = transcriber.is_api_available()
        
        # Should return False when API is unavailable
        assert result is False
    
    def test_is_api_available_no_key(self):
        """Test API availability check when no API key is provided."""
        # Configure transcriber to use API but with no key
        with patch('config.USE_WHISPER_API', True):
            with patch('config.WHISPER_API_KEY', ''):
                transcriber = Transcriber()
                result = transcriber.is_api_available()
        
        # Should return False when no API key is provided
        assert result is False
    
    def test_is_available_with_api(self):
        """Test is_available when API is available."""
        with patch('config.USE_WHISPER_API', True):
            with patch('config.WHISPER_API_KEY', 'test_key'):
                transcriber = Transcriber()
                
                # Mock is_api_available to return True
                with patch.object(transcriber, 'is_api_available', return_value=True):
                    # No need to check local availability if API is available
                    with patch('subprocess.run') as mock_run:
                        result = transcriber.is_available()
                        
                        # Should return True
                        assert result is True
                        # Should not check local availability
                        mock_run.assert_not_called()
    
    def test_is_available_fallback_to_local(self):
        """Test is_available falls back to checking local when API is unavailable."""
        with patch('config.USE_WHISPER_API', True):
            with patch('config.WHISPER_API_KEY', 'test_key'):
                transcriber = Transcriber()
                
                # Mock is_api_available to return False
                with patch.object(transcriber, 'is_api_available', return_value=False):
                    # Mock subprocess.run to indicate local executable is available
                    with patch('subprocess.run', return_value=MagicMock()) as mock_run:
                        result = transcriber.is_available()
                        
                        # Should return True if local executable is available
                        assert result is True
                        # Should check local availability
                        mock_run.assert_called_once()