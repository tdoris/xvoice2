#!/usr/bin/env python3

import os
import wave
import numpy as np
import pyaudio
import time
import tempfile
from transcriber import Transcriber

# Create a test WAV file with a simple tone
def create_test_audio():
    # Create a temporary file
    temp_dir = tempfile.mkdtemp()
    test_file = os.path.join(temp_dir, "test_audio.wav")
    
    # Parameters
    sample_rate = 16000
    duration = 2  # seconds
    frequency = 440  # Hz (A4 note)
    
    # Generate a sine wave
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    tone = np.sin(2 * np.pi * frequency * t) * 32767
    audio_data = tone.astype(np.int16)
    
    # Write to WAV file
    with wave.open(test_file, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 2 bytes for int16
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data.tobytes())
    
    print(f"Created test audio file: {test_file}")
    return test_file, temp_dir

# Test the transcriber with a test file
def main():
    test_file, temp_dir = create_test_audio()
    
    try:
        # Initialize transcriber
        transcriber = Transcriber()
        
        # Check if transcriber is available
        if not transcriber.is_available():
            print("Error: Transcriber not available")
            return
        
        # Check if model is available
        if not transcriber.is_model_available():
            print(f"Error: Model '{transcriber.model}' not available")
            print(transcriber.get_model_installation_instructions())
            return
        
        # Try to transcribe the test file
        print("Transcribing test audio...")
        result = transcriber.transcribe(test_file)
        
        if result:
            print(f"Transcription result: '{result}'")
        else:
            print("Transcription failed or returned empty result")
            
    finally:
        # Clean up
        if os.path.exists(test_file):
            os.remove(test_file)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)

if __name__ == "__main__":
    main()