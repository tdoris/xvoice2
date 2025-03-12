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
        
        # Auto-calibration for silence detection
        self.calibration_samples = []
        self.adaptive_threshold = None
        self.auto_calibration_complete = False
        self.calibration_factor = 2.0  # Multiplier above ambient noise floor
    
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
        max_amplitude = np.max(np.abs(data_array))
        
        # Use the dynamically calibrated threshold if available, otherwise fallback to hardcoded value
        threshold = getattr(self, 'adaptive_threshold', 1000)
        return max_amplitude < threshold
    
    def calibrate_silence_threshold(self):
        """
        Calibrate silence threshold based on ambient noise levels.
        Collects audio samples to determine the background noise floor,
        then sets the threshold to a multiple of that level.
        """
        if not self.stream:
            self.start_stream()
            
        debug_log("Calibrating microphone silence threshold...")
        
        # Collect ambient noise samples (2 seconds)
        self.calibration_samples = []
        calibration_frames = 60  # ~2 seconds of audio at typical settings
        
        # Ask user to be quiet during calibration
        print("Calibrating microphone... please remain quiet for 2 seconds.")
        
        for i in range(calibration_frames):
            try:
                data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                data_array = np.frombuffer(data, dtype=np.int16)
                max_amplitude = np.max(np.abs(data_array))
                self.calibration_samples.append(max_amplitude)
                
                # Print a simple progress indicator
                if i % 15 == 0:  # Show progress roughly every 0.5 seconds
                    progress = int((i / calibration_frames) * 100)
                    debug_log(f"Calibration progress: {progress}%")
            except Exception as e:
                debug_log(f"Error during calibration: {e}")
                break
                
        if not self.calibration_samples:
            debug_log("Calibration failed - using default threshold")
            self.adaptive_threshold = 1000  # Fallback to default
            return
        
        # Calculate statistics on the ambient noise
        min_level = np.min(self.calibration_samples)
        mean_level = np.mean(self.calibration_samples)
        max_level = np.max(self.calibration_samples)
        p90_level = np.percentile(self.calibration_samples, 90)
        
        # Use a smart approach based on the noise profile
        # - If the environment is very quiet, use a reasonable minimum threshold
        # - If noise fluctuates a lot, use a more conservative approach
        noise_range = max_level - min_level
        if noise_range > mean_level * 2:
            # High variance environment - use 95th percentile + buffer
            self.adaptive_threshold = np.percentile(self.calibration_samples, 95) * 1.5
        else:
            # Standard environment - use 90th percentile * factor
            self.adaptive_threshold = max(p90_level * self.calibration_factor, 500)
        
        # Apply config factor if specified
        if hasattr(config, 'THRESHOLD_ADJUSTMENT_FACTOR'):
            self.adaptive_threshold *= config.THRESHOLD_ADJUSTMENT_FACTOR
        
        debug_log(f"Calibration complete - noise profile: min={min_level:.1f}, mean={mean_level:.1f}, max={max_level:.1f}")
        debug_log(f"Silence threshold set to: {self.adaptive_threshold:.1f}")
        
        print(f"Calibration complete! (ambient noise level: {mean_level:.0f})")
        self.auto_calibration_complete = True
        self.last_calibration_time = time.time()
    
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
            
        # Auto-calibrate on first use if enabled and not done already
        if not self.auto_calibration_complete and getattr(config, 'CALIBRATION_ENABLED', True):
            self.calibrate_silence_threshold()
            
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
    
    def recalibrate_if_needed(self, false_trigger_count: int = 0) -> None:
        """
        Recalibrate the silence threshold if needed based on false triggers.
        
        Args:
            false_trigger_count: Number of recent false triggers
        """
        # Increase threshold if we're getting too many false positives
        if false_trigger_count > 0:
            old_threshold = self.adaptive_threshold
            # Increase by 20% for each false trigger (up to doubling)
            self.adaptive_threshold = min(old_threshold * (1 + 0.2 * false_trigger_count), old_threshold * 2)
            debug_log(f"Adjusted threshold after false trigger: {old_threshold:.1f} → {self.adaptive_threshold:.1f}")
            
        # Periodically recalibrate after long idle periods (randomly, ~10% chance when idle)
        if not hasattr(self, 'last_calibration_time') or time.time() - self.last_calibration_time > 60:
            if np.random.random() < 0.1:  # 10% chance to recalibrate when idle
                self.calibrate_silence_threshold()
                self.last_calibration_time = time.time()
    
    def listen_continuous(self) -> Generator[str, None, None]:
        """
        Generator that continuously captures audio chunks when speech is detected.
        
        Yields:
            Path to audio file containing the captured speech
        """
        try:
            self.start_stream()
            print("Audio stream started successfully. Listening...")
            
            # Initialize tracking for false positives
            false_trigger_count = 0
            self.last_calibration_time = time.time()
            
            while True:
                try:
                    file_path, speech_detected = self.capture_chunk()
                    if speech_detected:
                        # Record when we start processing this file
                        self.transcription_start_time = datetime.datetime.now()
                        if self.speech_end_time:
                            processing_delay = (self.transcription_start_time - self.speech_end_time).total_seconds()
                            debug_log(f"Time between speech end and processing start: {processing_delay:.3f}s")
                        
                        # Check for false positives by examining audio characteristics 
                        try:
                            with wave.open(file_path, 'rb') as wf:
                                # Calculate duration
                                frames = wf.getnframes()
                                rate = wf.getframerate()
                                duration = frames / float(rate)
                                
                                # Read audio data
                                audio_data = wf.readframes(frames)
                                audio_array = np.frombuffer(audio_data, dtype=np.int16)
                                
                                # Calculate energy/amplitude metrics
                                avg_amplitude = np.mean(np.abs(audio_array))
                                max_amplitude = np.max(np.abs(audio_array))
                                
                                # False positive detection
                                if duration < 0.3 or avg_amplitude < (self.adaptive_threshold * 0.7):
                                    debug_log(f"Possible false trigger: duration={duration:.2f}s, avg_amp={avg_amplitude:.1f}, max_amp={max_amplitude:.1f}")
                                    false_trigger_count += 1
                                    self.recalibrate_if_needed(false_trigger_count)
                                    os.remove(file_path)  # Clean up the audio file
                                    continue
                        except Exception as e:
                            debug_log(f"Error checking audio: {e}")
                    
                        # Reset false trigger count on successful capture
                        false_trigger_count = 0
                        yield file_path
                    else:
                        # Occasionally recalibrate during idle periods
                        self.recalibrate_if_needed()
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
