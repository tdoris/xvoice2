"""
Speech-to-text transcription module using whisper.cpp.
"""

import subprocess
import json
import os
import platform
from typing import Optional
import config

class Transcriber:
    """Interface for the whisper.cpp speech-to-text engine."""
    
    def __init__(self):
        """Initialize the transcriber with configuration settings."""
        self.model = config.WHISPER_MODEL
        self.whisper_executable = config.WHISPER_EXECUTABLE
        self.is_macos = platform.system() == "Darwin"
        self._model_path = None  # Will be set when validated
        
    def _find_model_path(self) -> Optional[str]:
        """
        Find the path to the selected whisper model.
        
        Returns:
            Path to the model file if found, None otherwise
        """
        # If we already found the path, return it
        if self._model_path and os.path.exists(self._model_path):
            return self._model_path
            
        # On macOS, models could be in various locations - we'll check a few
        if self.is_macos:
            model_paths = [
                f"models/ggml-{self.model}.bin",
                f"/opt/homebrew/share/whisper/models/ggml-{self.model}.bin",
                os.path.expanduser(f"~/whisper.cpp/models/ggml-{self.model}.bin"),
                os.path.join(os.path.dirname(self.whisper_executable), f"../models/ggml-{self.model}.bin")
            ]
            
            for path in model_paths:
                if os.path.exists(path):
                    self._model_path = path
                    return path
        else:
            # Linux locations
            model_paths = [
                f"models/ggml-{self.model}.bin",
                # Add path relative to the executable
                os.path.join(os.path.dirname(self.whisper_executable), f"../models/ggml-{self.model}.bin"),
                # Add user home directory path
                os.path.expanduser(f"~/whisper.cpp/models/ggml-{self.model}.bin")
            ]
            
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
        Transcribe audio file using whisper.cpp.
        
        Args:
            audio_file: Path to the audio file to transcribe
            
        Returns:
            Transcribed text or None if transcription failed
        """
        if not os.path.exists(audio_file):
            print(f"Audio file not found: {audio_file}")
            return None
            
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
                "-ojson"
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
                transcription = output.get('text', '').strip()
                return transcription
            except json.JSONDecodeError:
                # Fallback to raw output if JSON parsing fails
                return result.stdout.strip()
                
        except subprocess.CalledProcessError as e:
            print(f"Transcription error: {e}")
            print(f"stderr: {e.stderr}")
            return None
        except Exception as e:
            print(f"Unexpected error during transcription: {e}")
            return None
            
    def is_available(self) -> bool:
        """
        Check if whisper.cpp is available and working.
        
        Returns:
            True if whisper.cpp is available and functional
        """
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
        
        # On macOS, check additional locations
        if self.is_macos:
            model_dirs.extend([
                "/opt/homebrew/share/whisper/models",
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
