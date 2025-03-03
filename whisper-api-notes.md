# OpenAI Whisper API Integration for XVoice2

This document outlines the changes required to integrate OpenAI's Whisper API into XVoice2 while maintaining the option to use local whisper.cpp models.

## 1. Configuration Updates (config.py)

Add these settings to `config.py`:

```python
# Whisper API settings
USE_WHISPER_API = False  # Enable/disable OpenAI Whisper API for transcription
WHISPER_API_KEY = os.environ.get("OPENAI_API_KEY", "")  # Reuse OpenAI key or set separately
WHISPER_API_MODEL = "whisper-1"  # OpenAI Whisper model to use
WHISPER_API_LANGUAGE = "en"  # Language hint for API (optional)
```

## 2. Transcriber Class Modifications (transcriber.py)

The most significant changes are needed in the `Transcriber` class to support both local and API modes:

```python
"""
Speech-to-text transcription module supporting both whisper.cpp and OpenAI Whisper API.
"""

import subprocess
import json
import os
import platform
import requests
from typing import Optional
import config

class Transcriber:
    """Interface for speech-to-text using whisper.cpp and OpenAI Whisper API."""
    
    def __init__(self):
        """Initialize the transcriber with configuration settings."""
        self.model = config.WHISPER_MODEL
        self.whisper_executable = config.WHISPER_EXECUTABLE
        self.is_macos = platform.system() == "Darwin"
        self._model_path = None  # Will be set when validated
        
        # Whisper API settings
        self.use_api = config.USE_WHISPER_API
        self.api_key = config.WHISPER_API_KEY
        self.api_model = config.WHISPER_API_MODEL
        self.api_language = config.WHISPER_API_LANGUAGE
    
    # Existing methods remain unchanged: _find_model_path, is_model_available, etc.
    
    def transcribe(self, audio_file: str) -> Optional[str]:
        """
        Transcribe audio file using either whisper.cpp or OpenAI Whisper API.
        
        Args:
            audio_file: Path to the audio file to transcribe
            
        Returns:
            Transcribed text or None if transcription failed
        """
        if not os.path.exists(audio_file):
            print(f"Audio file not found: {audio_file}")
            return None
        
        # Decide which transcription method to use
        if self.use_api and self.api_key:
            print("[DEBUG] Using OpenAI Whisper API for transcription")
            return self._transcribe_with_api(audio_file)
        else:
            print("[DEBUG] Using local whisper.cpp for transcription")
            return self._transcribe_with_local(audio_file)
    
    def _transcribe_with_local(self, audio_file: str) -> Optional[str]:
        """
        Transcribe audio file using whisper.cpp (existing implementation).
        
        Args:
            audio_file: Path to the audio file to transcribe
            
        Returns:
            Transcribed text or None if transcription failed
        """
        # Move existing transcribe() implementation here
        # Find model path
        model_path = self._find_model_path()
        if not model_path:
            print(f"Error: Model '{self.model}' not found.")
            return None
            
        try:
            # Call whisper.cpp using subprocess
            command = [
                self.whisper_executable,
                "-m", model_path,
                "-f", audio_file,
                "-oj"  # Output JSON flag
            ]
            
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            
            # Parse the JSON output
            try:
                output = json.loads(result.stdout)
                
                # Extract and clean the text
                raw_text = output.get('text', '').strip()
                
                # Clean up timestamp patterns and [BLANK_AUDIO]
                import re
                
                # Remove timestamp patterns like [00:00:00.000 --> 00:00:02.000]
                clean_text = re.sub(r'\[\d+:\d+:\d+\.\d+ --> \d+:\d+:\d+\.\d+\]\s*', '', raw_text)
                
                # Remove [BLANK_AUDIO] entries
                clean_text = re.sub(r'\[BLANK_AUDIO\]', '', clean_text)
                
                # Remove double spaces and trim
                clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                
                return clean_text
            except json.JSONDecodeError:
                # Try to extract the actual transcription from raw output
                import re
                
                # Extract what appears to be the actual text content (remove timestamps and [BLANK_AUDIO])
                raw_text = result.stdout.strip()
                clean_text = re.sub(r'\[\d+:\d+:\d+\.\d+ --> \d+:\d+:\d+\.\d+\]\s*', '', raw_text)
                clean_text = re.sub(r'\[BLANK_AUDIO\]', '', clean_text)
                clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                
                return clean_text
                
        except subprocess.CalledProcessError as e:
            print(f"Transcription error: {e}")
            print(f"stderr: {e.stderr}")
            return None
        except Exception as e:
            print(f"Unexpected error during transcription: {e}")
            return None
    
    def _transcribe_with_api(self, audio_file: str) -> Optional[str]:
        """
        Transcribe audio file using OpenAI Whisper API.
        
        Args:
            audio_file: Path to the audio file to transcribe
            
        Returns:
            Transcribed text or None if transcription failed
        """
        try:
            # Read audio file as binary data
            with open(audio_file, "rb") as audio:
                audio_data = audio.read()
            
            # Create the form data with the audio file and parameters
            files = {
                "file": (os.path.basename(audio_file), audio_data, "audio/wav"),
                "model": (None, self.api_model),
                "response_format": (None, "json")
            }
            
            # Add language if specified
            if self.api_language:
                files["language"] = (None, self.api_language)
            
            # Send request to OpenAI API
            response = requests.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                files=files,
                timeout=10  # Longer timeout for audio processing
            )
            
            # Check response status
            if response.status_code != 200:
                print(f"API error: {response.status_code} - {response.text}")
                return None
            
            # Parse response
            result = response.json()
            transcription = result.get("text", "").strip()
            
            if not transcription:
                print("API returned empty transcription")
                return None
                
            return transcription
            
        except Exception as e:
            print(f"Error calling Whisper API: {e}")
            return None
    
    def is_api_available(self) -> bool:
        """
        Check if Whisper API is configured and available.
        
        Returns:
            True if API is available, False otherwise
        """
        if not self.use_api or not self.api_key:
            return False
            
        try:
            # Simple test request to check API key validity
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # This endpoint is used to check API key validity
            response = requests.get(
                "https://api.openai.com/v1/models",
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 200:
                # Check if the Whisper model is available
                models = response.json().get("data", [])
                model_ids = [model.get("id") for model in models]
                
                return self.api_model in model_ids
            return False
            
        except Exception:
            return False
    
    def is_available(self) -> bool:
        """
        Check if any transcription method is available.
        
        Returns:
            True if at least one transcription method is available
        """
        # Check if API is available first
        if self.use_api and self.api_key and self.is_api_available():
            return True
            
        # Fall back to checking local whisper.cpp
        try:
            subprocess.run(
                [self.whisper_executable, "--help"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
```

## 3. Command Line Interface Updates (main.py)

Add a new command-line argument to enable the Whisper API:

```python
# Add to existing argument parser in main.py
parser.add_argument(
    "--use-whisper-api",
    action="store_true",
    help="Use OpenAI Whisper API for transcription instead of local whisper.cpp"
)

# Add to the argument processing section
if args.use_whisper_api:
    config.USE_WHISPER_API = True
    # Print debug info about API key
    if config.WHISPER_API_KEY:
        print(f"Using OpenAI API key from {'environment variable' if os.environ.get('OPENAI_API_KEY') else 'config file'}")
    else:
        print("Warning: OpenAI API key not found. Set OPENAI_API_KEY environment variable or update config_local.py")
```

## 4. Dependencies

The application already includes `requests` in its dependencies, which is needed for API calls. No additional dependencies are required.

## 5. Test Updates

Update the test suite in `tests/unit/test_transcriber.py` to include tests for the Whisper API functionality:

```python
@patch('requests.post')
def test_transcribe_with_api_success(self, mock_post, tmp_path):
    """Test successful transcription using the Whisper API."""
    # Mock successful API response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"text": "test api transcription"}
    mock_post.return_value = mock_response
    
    # Create a temporary audio file
    audio_file = tmp_path / "test_audio.wav"
    audio_file.write_text("mock audio content")
    
    # Configure transcriber to use API
    with patch.object(config, 'USE_WHISPER_API', True):
        with patch.object(config, 'WHISPER_API_KEY', 'test_key'):
            transcriber = Transcriber()
            result = transcriber.transcribe(str(audio_file))
    
    assert result == "test api transcription"
    mock_post.assert_called_once()

@patch('requests.post')
def test_transcribe_with_api_failure(self, mock_post, tmp_path):
    """Test transcription behavior when API call fails."""
    # Mock API error
    mock_post.side_effect = requests.RequestException("API error")
    
    # Create a temporary audio file
    audio_file = tmp_path / "test_audio.wav"
    audio_file.write_text("mock audio content")
    
    # Configure transcriber to use API
    with patch.object(config, 'USE_WHISPER_API', True):
        with patch.object(config, 'WHISPER_API_KEY', 'test_key'):
            transcriber = Transcriber()
            result = transcriber.transcribe(str(audio_file))
    
    assert result is None
```

## 6. Implementation Notes

### Configuration Strategy

- Users can choose between local and API transcription via config or command-line
- The system will try API first if enabled, with fallback to local
- Reuses OpenAI API key from the LLM formatter to minimize configuration

### Error Handling

- Added robust error handling for API calls with detailed error messages
- Graceful fallback if API is unavailable or encounters errors

### Usage Instructions

To use the Whisper API:

```bash
python main.py --use-whisper-api
```

To use the local whisper.cpp (default):

```bash
python main.py
```

## 7. Benefits and Considerations

### Benefits

- No local model files required when using API
- Potentially higher accuracy with OpenAI's latest models
- Reduced CPU/memory usage on the local machine

### Considerations

- API usage incurs costs based on OpenAI's pricing
- Internet connection required for API mode
- May introduce latency compared to local processing
- Privacy considerations for sensitive audio data

This implementation maintains all existing functionality while adding the flexibility to choose between local and cloud-based transcription.