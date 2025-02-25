"""
Speech-to-text transcription module using whisper.cpp.
"""

import subprocess
import json
import os
from typing import Optional
import config

class Transcriber:
    """Interface for the whisper.cpp speech-to-text engine."""
    
    def __init__(self):
        """Initialize the transcriber with configuration settings."""
        self.model = config.WHISPER_MODEL
        self.whisper_executable = config.WHISPER_EXECUTABLE
        
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
            
        try:
            # Call whisper.cpp using subprocess
            # The -m flag specifies the model, -f the file, and -ojson outputs in JSON format
            command = [
                self.whisper_executable,
                "-m", f"models/ggml-{self.model}.bin",
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
        models_dir = "models"  # Assuming models are in a 'models' directory
        
        if os.path.exists(models_dir):
            for file in os.listdir(models_dir):
                if file.startswith("ggml-") and file.endswith(".bin"):
                    model_name = file[5:-4]  # Remove 'ggml-' prefix and '.bin' suffix
                    models.append(model_name)
                    
        return models
