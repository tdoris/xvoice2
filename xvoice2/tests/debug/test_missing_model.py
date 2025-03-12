#!/usr/bin/env python3
"""
Test script to check behavior when a non-existent model is requested
"""

import os
import sys
from xvoice2 import config
from xvoice2.transcriber import Transcriber

def main():
    """Test what happens when a non-existent model is requested"""
    # Override config
    config.WHISPER_MODEL = "nonexistent"
    
    # Initialize transcriber
    transcriber = Transcriber()
    
    # Check if whisper.cpp is available
    print(f"Whisper executable available: {transcriber.is_available()}")
    
    # Get available models
    print(f"Available models: {transcriber.get_available_models()}")
    
    # Check if the model file exists
    model_path = f"models/ggml-{config.WHISPER_MODEL}.bin"
    print(f"Model file {model_path} exists: {os.path.exists(model_path)}")
    
    # Test what would happen during transcription
    audio_file = "test_audio.wav"
    # Create empty test file
    with open(audio_file, "w") as f:
        f.write("test")
    
    print(f"Attempting to transcribe with missing model...")
    try:
        result = transcriber.transcribe(audio_file)
        print(f"Transcription result: {result}")
    except Exception as e:
        print(f"Exception during transcription: {e}")
        import traceback
        traceback.print_exc()
    
    # Clean up
    os.remove(audio_file)

if __name__ == "__main__":
    main()