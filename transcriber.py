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
        
    def _find_model_path(self) -> Optional[str]:
        """
        Find the path to the selected whisper model.
        
        Returns:
            Path to the model file if found, None otherwise
        """
        # If we already found the path, return it
        if self._model_path and os.path.exists(self._model_path):
            return self._model_path
            
        # Check if WHISPER_ROOT is defined in config
        if hasattr(config, 'WHISPER_ROOT'):
            # Try WHISPER_ROOT models directory first
            models_path = os.path.join(config.WHISPER_ROOT, f"models/ggml-{self.model}.bin")
            if os.path.exists(models_path):
                self._model_path = models_path
                return models_path
                
        # Then check platform-specific locations
        if self.is_macos:
            model_paths = [
                f"models/ggml-{self.model}.bin",
                f"/opt/homebrew/share/whisper/models/ggml-{self.model}.bin",
                os.path.expanduser(f"~/whisper.cpp/models/ggml-{self.model}.bin"),
                os.path.join(os.path.dirname(self.whisper_executable), f"../models/ggml-{self.model}.bin")
            ]
        else:
            # Linux locations
            model_paths = [
                f"models/ggml-{self.model}.bin",
                # Add path relative to the executable
                os.path.join(os.path.dirname(self.whisper_executable), f"../models/ggml-{self.model}.bin"),
                # Add user home directory path
                os.path.expanduser(f"~/whisper.cpp/models/ggml-{self.model}.bin")
            ]
        
        # Check all possible locations
        for path in model_paths:
            if os.path.exists(path):
                self._model_path = path
                return path
                    
        return None
    
    def is_model_available(self) -> bool:
        """
        Check if the selected model file exists.
        
        Returns:
            True if the model file is found, False otherwise
        """
        return self._find_model_path() is not None
        
    def get_model_installation_instructions(self) -> str:
        """
        Get instructions for installing the missing model.
        
        Returns:
            String with installation instructions
        """
        return (
            f"Model '{self.model}' not found. To install it:\n"
            f"1. Navigate to your whisper.cpp directory\n"
            f"2. Run: bash ./models/download-ggml-model.sh {self.model}\n"
            f"3. Restart the application\n\n"
            f"Available models: tiny, base, small, medium, large"
        )
    
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
        Transcribe audio file using local whisper.cpp installation.
        
        Args:
            audio_file: Path to the audio file to transcribe
            
        Returns:
            Transcribed text or None if transcription failed
        """
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
            # Try to run whisper.cpp with --help to check if it's available
            subprocess.run(
                [self.whisper_executable, "--help"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
            
    def get_available_models(self) -> list:
        """
        Get a list of available whisper models.
        
        Returns:
            List of available model names
        """
        models = []
        model_dirs = ["models"]  # Default models directory
        
        # First check config.WHISPER_ROOT if available
        if hasattr(config, 'WHISPER_ROOT'):
            whisper_models_dir = os.path.join(config.WHISPER_ROOT, "models")
            if os.path.exists(whisper_models_dir):
                model_dirs.append(whisper_models_dir)
        
        # Then check platform-specific locations
        if self.is_macos:
            model_dirs.extend([
                "/opt/homebrew/share/whisper/models",
                os.path.expanduser("~/whisper.cpp/models"),
                os.path.join(os.path.dirname(self.whisper_executable), "../models")
            ])
        else:
            # Linux locations
            model_dirs.extend([
                os.path.expanduser("~/whisper.cpp/models"),
                os.path.join(os.path.dirname(self.whisper_executable), "../models")
            ])
        
        for models_dir in model_dirs:
            if os.path.exists(models_dir):
                for file in os.listdir(models_dir):
                    if file.startswith("ggml-") and file.endswith(".bin"):
                        model_name = file[5:-4]  # Remove 'ggml-' prefix and '.bin' suffix
                        if model_name not in models:
                            models.append(model_name)
                    
        return models
