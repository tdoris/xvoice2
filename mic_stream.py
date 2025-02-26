"""
Microphone input handling module using PortAudio.
Captures audio in chunks and processes it for transcription.
"""

import pyaudio
import numpy as np
import wave
import os
import tempfile
import time
import platform
from typing import Generator, Tuple, Optional
import config

class MicrophoneStream:
    """Handles microphone streaming and processing for voice dictation."""
    
    def __init__(self):
        """Initialize the microphone stream with configuration settings."""
        self.sample_rate = config.SAMPLE_RATE
        self.chunk_size = config.FRAMES_PER_BUFFER
        self.channels = config.CHANNELS
        self.format_map = {
            'int16': pyaudio.paInt16,
            'int32': pyaudio.paInt32,
            'float32': pyaudio.paFloat32
        }
        self.format = self.format_map.get(config.FORMAT, pyaudio.paInt16)
        self.silence_threshold = config.SILENCE_THRESHOLD
        self.silence_duration = config.SILENCE_DURATION
        self.chunk_duration = config.CHUNK_DURATION
        self.is_macos = platform.system() == "Darwin"
        
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.temp_dir = tempfile.mkdtemp()
        self.device_index = None
    
    def __enter__(self):
        """Context manager entry point."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit point. Clean up resources."""
        self.close()
    
    def _find_input_device(self):
        """Find a valid audio input device with macOS preference."""
        # Get information about audio devices
        info = self.audio.get_host_api_info_by_index(0)
        num_devices = info.get('deviceCount')
        
        print("Available input devices:")
        found_device = False
        
        # Try to find an input device
        for i in range(num_devices):
            device_info = self.audio.get_device_info_by_index(i)
            max_input_channels = device_info.get('maxInputChannels')
            name = device_info.get('name')
            
            print(f"  - Device {i}: {name} (max inputs: {max_input_channels})")
            
            # On macOS, prioritize built-in input devices
            if max_input_channels > 0:
                if not found_device or (self.is_macos and "built-in" in name.lower()):
                    self.device_index = i
                    found_device = True
                    
                    if self.is_macos and "built-in" in name.lower():
                        print(f"    -> Selected this device (macOS built-in preferred)")
                        break
                    else:
                        print(f"    -> Selected this device")
        
        if not found_device:
            print("Warning: No input devices found. Using default device.")
            self.device_index = None
            
        return found_device
        
    def start_stream(self) -> None:
        """Start the audio stream for capturing microphone input."""
        # Try to find a valid input device first
        self._find_input_device()
        
        try:
            # First try with the selected device
            self.stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=self.chunk_size
            )
            print(f"Successfully opened audio stream with device index: {self.device_index}")
        except Exception as e:
            print(f"Error opening audio stream: {e}")
            print("Attempting to use alternative configuration...")
            
            try:
                # Try with default device as fallback
                self.stream = self.audio.open(
                    format=self.format,
                    channels=self.channels,
                    rate=self.sample_rate,
                    input=True,
                    frames_per_buffer=self.chunk_size
                )
                print("Successfully opened audio stream with default device")
            except Exception as e:
                print(f"Fatal error: Could not open any audio stream: {e}")
                if self.is_macos:
                    print("On macOS, make sure you've granted microphone permissions to Terminal or your application.")
                print("Please check your audio configuration or try running with different audio hardware.")
                raise
    
    def close(self) -> None:
        """Close and clean up audio resources."""
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.audio.terminate()
        
        # Clean up temporary files
        for file in os.listdir(self.temp_dir):
            os.remove(os.path.join(self.temp_dir, file))
        os.rmdir(self.temp_dir)
    
    def is_silent(self, data_array: np.ndarray) -> bool:
        """
        Determine if the audio chunk is silent.
        
        Args:
            data_array: Numpy array of audio data
            
        Returns:
            True if the audio is below the silence threshold
        """
        return np.max(np.abs(data_array)) < self.silence_threshold
    
    def capture_chunk(self) -> Tuple[str, bool]:
        """
        Capture a chunk of audio until silence is detected.
        
        Returns:
            Tuple containing:
                - Path to the WAV file with the captured audio
                - Boolean indicating if speech was detected
        """
        if not self.stream:
            self.start_stream()
            
        frames = []
        silent_frames = 0
        speech_detected = False
        max_frames = int(self.sample_rate / self.chunk_size * self.chunk_duration)
        
        try:
            # Capture audio for the specified chunk duration or until silence
            for _ in range(max_frames):
                data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                frames.append(data)
                
                # Convert to numpy array for silence detection
                data_array = np.frombuffer(data, dtype=np.int16)
                
                # Check if this frame is silent
                if self.is_silent(data_array):
                    silent_frames += 1
                    # If we've had enough consecutive silent frames, break
                    if silent_frames > int(self.silence_duration * self.sample_rate / self.chunk_size) and speech_detected:
                        break
                else:
                    silent_frames = 0
                    speech_detected = True
        except Exception as e:
            print(f"Error capturing audio: {e}")
            return "", False
        
        # If no speech was detected, return early
        if not speech_detected:
            return "", False
            
        # Save the audio chunk to a temporary WAV file
        temp_file = os.path.join(self.temp_dir, f"chunk_{time.time()}.wav")
        try:
            with wave.open(temp_file, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.audio.get_sample_size(self.format))
                wf.setframerate(self.sample_rate)
                wf.writeframes(b''.join(frames))
        except Exception as e:
            print(f"Error saving audio file: {e}")
            return "", False
            
        return temp_file, True
    
    def listen_continuous(self) -> Generator[str, None, None]:
        """
        Generator that continuously captures audio chunks when speech is detected.
        
        Yields:
            Path to audio file containing the captured speech
        """
        try:
            self.start_stream()
            print("Audio stream started successfully. Listening...")
            
            while True:
                file_path, speech_detected = self.capture_chunk()
                if speech_detected:
                    yield file_path
                else:
                    time.sleep(0.1)  # Short pause when no speech detected
        except KeyboardInterrupt:
            pass
        except Exception as e:
            print(f"Fatal error in audio capture: {e}")
        finally:
            self.close()
