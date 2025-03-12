"""
Unit tests for the mic_stream module.
"""

import pytest
import os
import tempfile
import numpy as np
from unittest.mock import patch, MagicMock

from xvoice2 import config
from xvoice2.mic_stream import MicrophoneStream

class TestMicrophoneStream:
    """Tests for the MicrophoneStream class."""
    
    def test_init(self):
        """Test initialization of MicrophoneStream."""
        with patch('pyaudio.PyAudio'):
            stream = MicrophoneStream()
            
            assert stream.sample_rate == config.SAMPLE_RATE
            assert stream.chunk_size == config.FRAMES_PER_BUFFER
            assert stream.channels == config.CHANNELS
            assert stream.silence_threshold == config.SILENCE_THRESHOLD
    
    def test_find_input_device(self, mock_pyaudio):
        """Test finding input devices."""
        stream = MicrophoneStream()
        result = stream._find_input_device()
        
        assert result is True
        assert stream.device_index == 1  # Second device (index 1) has input channels
    
    def test_is_silent_with_silent_data(self, mock_audio_data_silent):
        """Test silence detection with silent audio."""
        with patch('pyaudio.PyAudio'):
            stream = MicrophoneStream()
            # Set a fixed adaptive threshold for testing
            stream.adaptive_threshold = 500
            stream.auto_calibration_complete = True
            
            result = stream.is_silent(mock_audio_data_silent)
            assert result == True
    
    def test_is_silent_with_speech_data(self, mock_audio_data_speech):
        """Test silence detection with speech audio."""
        with patch('pyaudio.PyAudio'):
            stream = MicrophoneStream()
            # Set a fixed adaptive threshold for testing
            stream.adaptive_threshold = 500
            stream.auto_calibration_complete = True
            
            result = stream.is_silent(mock_audio_data_speech)
            assert result == False
    
    @patch('tempfile.mkdtemp')
    def test_context_manager(self, mock_mkdtemp):
        """Test that context manager properly initializes and cleans up."""
        mock_mkdtemp.return_value = "/tmp/mock_dir"
        
        with patch('pyaudio.PyAudio'):
            with patch('os.listdir', return_value=[]):
                with patch('os.rmdir') as mock_rmdir:
                    with MicrophoneStream() as stream:
                        assert isinstance(stream, MicrophoneStream)
                    
                    # Check cleanup was called
                    mock_rmdir.assert_called_once_with("/tmp/mock_dir")
    
    @patch('wave.open')
    @patch('os.path.join')
    @patch('time.time')
    @patch('tempfile.mkdtemp')
    def test_capture_chunk_with_speech(self, mock_mkdtemp, mock_time, mock_join, mock_wave, mock_audio_data_speech):
        """Test capturing an audio chunk with speech."""
        mock_mkdtemp.return_value = "/tmp/test_dir"
        mock_time.return_value = 12345.67
        mock_join.return_value = "/tmp/test_dir/chunk_12345.67.wav"
        
        with patch('pyaudio.PyAudio') as mock_pyaudio:
            # Mock the audio stream
            mock_stream = MagicMock()
            mock_stream.read.return_value = b'mock_audio_data'
            
            mock_instance = MagicMock()
            mock_pyaudio.return_value = mock_instance
            mock_instance.open.return_value = mock_stream
            
            # Disable calibration for testing
            with patch.object(config, 'CALIBRATION_ENABLED', False):
                # Mock numpy array conversion to detect speech
                with patch('numpy.frombuffer', return_value=mock_audio_data_speech):
                    stream = MicrophoneStream()
                    # Set a fixed adaptive threshold for testing
                    stream.adaptive_threshold = 500
                    stream.auto_calibration_complete = True
                    stream.stream = mock_stream  # Set the mocked stream
                    
                    filepath, speech_detected = stream.capture_chunk()
                    
                    assert speech_detected is True
                    assert filepath == "/tmp/test_dir/chunk_12345.67.wav"
    
    @patch('time.sleep')  # Mock sleep to speed up the test
    def test_listen_continuous(self, mock_sleep):
        """Test the continuous listening generator."""
        with patch('pyaudio.PyAudio'):
            stream = MicrophoneStream()
            
            # Mock capture_chunk to return some predetermined values
            mock_return_values = [
                ("/tmp/chunk1.wav", True),  # First chunk has speech
                ("/tmp/chunk2.wav", False),  # Second chunk has no speech
                ("", False),                # Third chunk has error
                Exception("Test exception")  # Fourth call raises exception to exit
            ]
            
            stream.start_stream = MagicMock()  # Mock start_stream
            stream.capture_chunk = MagicMock(side_effect=mock_return_values)
            stream.close = MagicMock()  # Mock close
            
            # Call the generator and collect results
            results = []
            try:
                for file_path in stream.listen_continuous():
                    results.append(file_path)
                    if len(results) >= 1:  # Only get the first result to exit the loop
                        break
            except Exception:
                pass  # Expected exception to terminate the loop
            
            assert results == ["/tmp/chunk1.wav"]  # Only the chunk with speech
            stream.start_stream.assert_called_once()
            stream.close.assert_called_once()