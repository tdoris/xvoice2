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
import datetime
from typing import Generator, Tuple, Optional
import config

def debug_log(message: str, end: Optional[str] = None) -> None:
    """
    Print a debug message with a timestamp.
    
    Args:
        message: The message to print
        end: Optional ending character (default is newline)
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    if end is not None:
        print(f"[{timestamp}] {message}", end=end, flush=True)
    else:
        print(f"[{timestamp}] {message}")

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
        
        # For tracking speech and processing times
        self.speech_end_time = None
        self.transcription_start_time = None
    
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
            
            # Specifically prioritize the MacBook Air Microphone
            if max_input_channels > 0:
                if not found_device or "MacBook Air Microphone" in name:
                    self.device_index = i
                    found_device = True
                    
                    if "MacBook Air Microphone" in name:
                        print(f"    -> Selected this device (MacBook Air Microphone preferred)")
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
        # Hardcoded threshold that matches the scale of int16 audio
        actual_threshold = 1000
        
        max_amplitude = np.max(np.abs(data_array))
        return max_amplitude < actual_threshold
    
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
        silence_after_speech = False
        
        # Use configured maximum sentence duration
        max_frames = int(self.sample_rate / self.chunk_size * config.MAX_SENTENCE_DURATION)
        max_amplitude_seen = 0
        
        try:
            # First, wait for speech to begin
            print("Waiting for speech...")
            while not speech_detected and len(frames) < max_frames:
                data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                frames.append(data)
                
                # Convert to numpy array for silence detection
                data_array = np.frombuffer(data, dtype=np.int16)
                current_max = np.max(np.abs(data_array))
                
                # Check if this frame contains speech
                if not self.is_silent(data_array):
                    speech_detected = True
                    print("Speech detected! Capturing full sentence...")
                
                # If we've captured a lot of frames with no speech, discard them and keep waiting
                if len(frames) > 30 and not speech_detected:  # ~1 second of silence
                    frames = frames[-10:]  # Keep only last ~0.3 seconds
            
            # If no speech detected after max_frames, return early
            if not speech_detected:
                return "", False
                
            # Now capture the rest of the sentence until silence
            consecutive_silence_frames = 0
            required_silence_frames = int(self.silence_duration * self.sample_rate / self.chunk_size)
            
            while not silence_after_speech and len(frames) < max_frames:
                data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                frames.append(data)
                
                # Convert to numpy array for silence detection
                data_array = np.frombuffer(data, dtype=np.int16)
                current_max = np.max(np.abs(data_array))
                max_amplitude_seen = max(max_amplitude_seen, current_max)
                
                # Check if this frame is silent
                if self.is_silent(data_array):
                    consecutive_silence_frames += 1
                    # If we've had enough consecutive silent frames, consider the sentence complete
                    if consecutive_silence_frames >= required_silence_frames:
                        silence_after_speech = True
                        print("End of sentence detected.")
                        # Store timestamp when speech ended
                        self.speech_end_time = datetime.datetime.now()
                        debug_log("Speech capture complete")
                        break
                else:
                    consecutive_silence_frames = 0
            
        except Exception as e:
            print(f"Error capturing audio: {e}")
            return "", False
        
        # If we've reached max frames without ending silence, that's okay - we'll process what we have
        if len(frames) >= max_frames:
            print(f"Reached maximum recording length ({config.MAX_SENTENCE_DURATION}s), processing sentence.")
            
        # We've definitely detected speech at this point
        speech_detected = True
            
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
                try:
                    file_path, speech_detected = self.capture_chunk()
                    if speech_detected:
                        # Record when we start processing this file
                        self.transcription_start_time = datetime.datetime.now()
                        if self.speech_end_time:
                            processing_delay = (self.transcription_start_time - self.speech_end_time).total_seconds()
                            debug_log(f"Time between speech end and processing start: {processing_delay:.3f}s")
                        yield file_path
                    else:
                        time.sleep(0.1)  # Short pause when no speech detected
                except KeyboardInterrupt:
                    print("\nGracefully shutting down...")
                    break
                except Exception as e:
                    print(f"Error in audio capture: {e}")
                    # Continue attempting to capture audio instead of crashing
                    time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nGracefully shutting down...")
        except Exception as e:
            print(f"Fatal error in audio capture: {e}")
        finally:
            print("Cleaning up audio resources...")
            self.close()
