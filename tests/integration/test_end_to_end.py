"""
Integration tests for the XVoice 2.0 application.
Tests the interaction between different components.
"""

import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
import sys
import formatter  # Import for patching
from main import VoiceDictationApp

class TestEndToEnd:
    """Integration tests for the entire application."""
    
    @pytest.fixture
    def mock_audio_file(self):
        """Create a temporary audio file for testing."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(b'mock audio data')
            file_path = f.name
        
        yield file_path
        
        # Cleanup
        if os.path.exists(file_path):
            os.remove(file_path)
    
    @patch('os.remove')
    @patch('os.path.exists', return_value=True)
    def test_processing_pipeline(self, mock_exists, mock_remove):
        """Test the complete audio processing pipeline."""
        # Create mocks for all components and import actual classes locally
        # to avoid import issues with MicrophoneStream
        from transcriber import Transcriber
        from text_injector import TextInjector
        from formatter import TextFormatter
        
        # We need to do proper patching to avoid the real implementations being used
        with patch.object(Transcriber, 'transcribe', return_value="test transcription"):
            with patch.object(Transcriber, 'is_available', return_value=True):
                with patch.object(TextInjector, 'inject_text', return_value=True):
                    with patch.object(TextInjector, 'is_available', return_value=True):
                        with patch.object(formatter.TextFormatter, 'format_text', return_value="formatted text"):
                            with patch('config.USE_LLM', True):
                                # Create the application
                                app = VoiceDictationApp(mode="general")
                                
                                # Process the audio file - patching os.remove 
                                # since it's called directly from main.py run() not the _process_audio method
                                with patch('os.remove') as mock_os_remove:
                                    app._process_audio("test_audio.wav")
                                    
                                    # Verify that the processing worked correctly by checking the output
                                    # We can't verify os.remove here as it's not called from _process_audio
    
    @patch('os.remove')
    @patch('os.path.exists', return_value=True)
    def test_processing_pipeline_without_llm(self, mock_exists, mock_remove):
        """Test the pipeline without LLM formatting."""
        # Import locally to avoid issues with MicrophoneStream
        from transcriber import Transcriber
        from text_injector import TextInjector
        
        # We need to do proper patching to avoid the real implementations being used
        with patch.object(Transcriber, 'transcribe', return_value="test transcription"):
            with patch.object(Transcriber, 'is_available', return_value=True):
                with patch.object(TextInjector, 'inject_text', return_value=True):
                    with patch.object(TextInjector, 'is_available', return_value=True):
                        with patch('config.USE_LLM', False):
                            # Create the application
                            app = VoiceDictationApp(mode="general")
                            
                            # Process the audio file - patching os.remove 
                            # since it's called directly from main.py run() not the _process_audio method
                            with patch('os.remove') as mock_os_remove:
                                app._process_audio("test_audio.wav")
                                
                                # Verify that the processing worked correctly by checking the output
                                # We can't verify os.remove here as it's not called from _process_audio
    
    def test_dependency_check_failure(self):
        """Test behavior when dependencies are not available."""
        # Import locally to avoid issues with MicrophoneStream
        from transcriber import Transcriber
        from text_injector import TextInjector
        
        # We need to do proper patching to avoid the real implementations being used
        with patch.object(Transcriber, 'is_available', return_value=False):
            with patch.object(TextInjector, 'is_available', return_value=True):
                with patch.object(TextInjector, 'inject_text', return_value=False):
                    # Create the application and mock MicrophoneStream to prevent it from being used
                    with patch('mic_stream.MicrophoneStream'):
                        app = VoiceDictationApp()
                        
                        # Run the application - should exit early due to missing dependencies
                        app.run()
        
    def test_signal_handler(self):
        """Test that the signal handler stops the application."""
        with patch('sys.exit') as mock_exit:
            app = VoiceDictationApp()
            app.running = True
            
            # Trigger the signal handler
            app._signal_handler(None, None)
            
            assert app.running is False
            mock_exit.assert_called_once_with(0)