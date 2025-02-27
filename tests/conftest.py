"""
Shared pytest fixtures for XVoice 2.0 tests.
"""

import pytest
from unittest.mock import MagicMock, patch
import numpy as np
import platform

@pytest.fixture
def mock_platform_linux():
    """Fixture that mocks platform.system() to return 'Linux'."""
    with patch('platform.system', return_value='Linux'):
        yield

@pytest.fixture
def mock_platform_macos():
    """Fixture that mocks platform.system() to return 'Darwin'."""
    with patch('platform.system', return_value='Darwin'):
        yield

@pytest.fixture
def mock_pyaudio():
    """Fixture that mocks pyaudio.PyAudio for testing without hardware devices."""
    with patch('pyaudio.PyAudio') as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        
        # Configure mock to return some device info
        mock_info = MagicMock()
        mock_info.get.return_value = 2  # deviceCount
        mock_instance.get_host_api_info_by_index.return_value = mock_info
        
        # Mock device info responses
        device_info1 = {"maxInputChannels": 0, "name": "Test Device 1"}
        device_info2 = {"maxInputChannels": 2, "name": "Test Device 2"}
        mock_instance.get_device_info_by_index.side_effect = [device_info1, device_info2]
        
        yield mock_instance

@pytest.fixture
def mock_audio_data_silent():
    """Fixture that returns silent audio data for testing."""
    # Create a silent audio buffer (values close to zero)
    return np.zeros(1024, dtype=np.int16)

@pytest.fixture
def mock_audio_data_speech():
    """Fixture that returns audio data simulating speech for testing."""
    # Create an audio buffer with values that exceed silence threshold
    return np.ones(1024, dtype=np.int16) * 1000  # Non-silent audio

@pytest.fixture
def mock_subprocess_run():
    """Fixture that mocks subprocess.run for testing command execution."""
    with patch('subprocess.run') as mock_run:
        mock_result = MagicMock()
        mock_result.stdout = '{"text": "test transcription"}'
        mock_run.return_value = mock_result
        yield mock_run

@pytest.fixture
def mock_requests_post():
    """Fixture that mocks requests.post for testing API calls."""
    with patch('requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {"message": {"content": "formatted text"}}
            ]
        }
        mock_post.return_value = mock_response
        yield mock_post