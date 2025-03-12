"""
Unit tests for the transcriber module.
"""

import pytest
import os
import json
import platform
from unittest.mock import patch, MagicMock

from xvoice2 import config
from xvoice2.transcriber import Transcriber

class TestTranscriber:
    """Tests for the Transcriber class."""
    
    def test_init(self):
        """Test that the Transcriber initializes with correct values."""
        transcriber = Transcriber()
        assert transcriber.model == config.WHISPER_MODEL
        assert transcriber.whisper_executable == config.WHISPER_EXECUTABLE
        assert transcriber.is_macos == (platform.system() == "Darwin")
    
    @pytest.mark.parametrize("platform_fixture,expected", [
        ("mock_platform_linux", False),
        ("mock_platform_macos", True)
    ])
    def test_platform_detection(self, request, platform_fixture, expected):
        """Test platform detection logic."""
        # Get the fixture dynamically
        request.getfixturevalue(platform_fixture)
        
        transcriber = Transcriber()
        assert transcriber.is_macos == expected
    
    @patch('os.path.exists')
    def test_transcribe_missing_file(self, mock_exists):
        """Test transcribe behavior when the audio file doesn't exist."""
        mock_exists.return_value = False
        
        transcriber = Transcriber()
        result = transcriber.transcribe("nonexistent.wav")
        
        assert result is None
    
    def test_transcribe_successful(self, mock_subprocess_run, tmp_path):
        """Test successful transcription with mocked subprocess."""
        # Create a temporary audio file
        audio_file = tmp_path / "test_audio.wav"
        audio_file.write_text("mock audio content")
        
        with patch('os.path.exists', return_value=True):
            with patch('transcriber.Transcriber._find_model_path', return_value='mock_model_path'):
                with patch('config.USE_PERSISTENT_WHISPER', False):  # Disable persistence
                    transcriber = Transcriber()
                    # Make sure persistent whisper is disabled
                    transcriber.use_persistent = False
                    result = transcriber.transcribe(str(audio_file))
        
        assert result == "test transcription"
        mock_subprocess_run.assert_called_once()
    
    def test_transcribe_subprocess_error(self, tmp_path):
        """Test transcription behavior when subprocess fails."""
        # Create a temporary audio file
        audio_file = tmp_path / "test_audio.wav"
        audio_file.write_text("mock audio content")
        
        with patch('os.path.exists', return_value=True):
            with patch('transcriber.Transcriber._find_model_path', return_value='mock_model_path'):
                with patch('config.USE_PERSISTENT_WHISPER', False):
                    with patch('subprocess.run', side_effect=Exception("Command failed")):
                        transcriber = Transcriber()
                        # Disable persistent mode to ensure we use one-time transcription
                        transcriber.use_persistent = False
                        result = transcriber.transcribe(str(audio_file))
        
        assert result is None
    
    def test_is_available_success(self, mock_subprocess_run):
        """Test is_available when whisper.cpp is available."""
        transcriber = Transcriber()
        result = transcriber.is_available()
        
        assert result is True
        mock_subprocess_run.assert_called_once()
    
    def test_is_available_failure(self):
        """Test is_available when whisper.cpp is not available."""
        with patch('subprocess.run', side_effect=FileNotFoundError("Command not found")):
            transcriber = Transcriber()
            result = transcriber.is_available()
        
        assert result is False
    
    @patch('os.path.exists')
    @patch('os.listdir')
    def test_get_available_models(self, mock_listdir, mock_exists):
        """Test retrieving available models."""
        mock_exists.return_value = True
        mock_listdir.return_value = [
            "ggml-tiny.bin", 
            "ggml-base.bin", 
            "ggml-small.bin", 
            "some_other_file.txt"
        ]
        
        transcriber = Transcriber()
        models = transcriber.get_available_models()
        
        assert "tiny" in models
        assert "base" in models
        assert "small" in models
        assert len(models) == 3  # Should only include the valid model files