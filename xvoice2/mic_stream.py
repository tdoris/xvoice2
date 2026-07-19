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
from xvoice2 import config
from xvoice2.logging_util import debug_log

def list_input_devices():
    """List available audio input (capture) devices.

    Returns:
        A list of (index, name) tuples for devices with input channels. Used by
        the GUI microphone picker. Safe to call standalone; opens no stream.
    """
    devices = []
    pa = pyaudio.PyAudio()
    try:
        info = pa.get_host_api_info_by_index(0)
        for i in range(info.get('deviceCount', 0)):
            d = pa.get_device_info_by_index(i)
            if d.get('maxInputChannels', 0) > 0:
                devices.append((i, d.get('name', f'Device {i}')))
    except Exception as e:
        debug_log(f"Could not enumerate input devices: {e}")
    finally:
        pa.terminate()
    return devices


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
        self._closed = False
        
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

            if max_input_channels > 0:
                # Honor a user-configured microphone (by name substring). This
                # is what the GUI's microphone picker sets, e.g. a USB mic.
                preferred = getattr(config, 'INPUT_DEVICE_NAME', '') or ''
                if preferred and name and preferred.lower() in name.lower():
                    self.device_index = i
                    found_device = True
                    print(f"    -> Selected this device (matches configured '{preferred}')")
                    break

                # Otherwise take the first input device (macOS: prefer built-in).
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
        """Close and clean up audio resources.

        Safe to call more than once: both ``listen_continuous`` (in its
        ``finally`` block) and the context-manager ``__exit__`` invoke this, so
        it must be idempotent.
        """
        if self._closed:
            return
        self._closed = True

        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception as e:
                debug_log(f"Error closing audio stream: {e}")
            self.stream = None

        if self.audio:
            try:
                self.audio.terminate()
            except Exception as e:
                debug_log(f"Error terminating PyAudio: {e}")
            self.audio = None

        # Clean up temporary files
        if self.temp_dir:
            try:
                for file in os.listdir(self.temp_dir):
                    os.remove(os.path.join(self.temp_dir, file))
                os.rmdir(self.temp_dir)
            except OSError as e:
                debug_log(f"Error cleaning up temp directory: {e}")
    
    def effective_threshold(self) -> float:
        """
        Return the silence threshold to use for detection and diagnostics.

        Uses the dynamically calibrated threshold when available, otherwise the
        configured static threshold. ``adaptive_threshold`` is initialized to
        None (calibration disabled or not yet run), so every consumer that does
        math or formatting with it must go through here to avoid a TypeError.
        """
        if self.adaptive_threshold is not None:
            return self.adaptive_threshold
        return self.silence_threshold

    def _voice_activity_ratio(self, audio_array: np.ndarray, threshold: float) -> float:
        """
        Fraction of frames in a clip whose peak amplitude crosses the threshold.

        This is a robust discriminator between genuine speech (many active
        frames) and a stray click/pop (a single spike in otherwise silent
        audio). It is unaffected by the trailing silence and inter-word gaps
        that drag down a clip's average amplitude.

        Args:
            audio_array: int16 samples of the captured clip
            threshold: Amplitude threshold for an "active" frame

        Returns:
            Ratio in [0.0, 1.0]
        """
        frame_len = self.chunk_size
        n_frames = len(audio_array) // frame_len
        if n_frames == 0:
            max_amplitude = np.max(np.abs(audio_array)) if len(audio_array) else 0
            return 1.0 if max_amplitude > threshold else 0.0

        frame_peaks = np.max(
            np.abs(audio_array[:n_frames * frame_len].reshape(n_frames, frame_len)),
            axis=1,
        )
        return float(np.mean(frame_peaks > threshold))

    def _rejection_reason(
        self,
        duration: float,
        active_ratio: float,
        max_amplitude: float,
        threshold: float,
        voiced_seconds: Optional[float] = None,
    ) -> Optional[str]:
        """Decide whether a captured clip should be rejected as non-speech.

        Returns a short human-readable reason to reject the clip, or None if it
        looks like genuine speech. Keeping this pure (no I/O) makes the VAD gate
        unit-testable and easy to tune via config.

        Args:
            duration: Clip length in seconds.
            active_ratio: Fraction of frames whose peak crosses the threshold.
            max_amplitude: Peak absolute amplitude in the clip.
            threshold: The silence threshold in effect.
            voiced_seconds: Seconds of voiced audio (see _voiced_seconds). When
                provided and REQUIRE_VOICED is set, a clip with too little voiced
                audio (e.g. keyboard clatter) is rejected.

        Returns:
            A rejection reason string, or None to accept the clip.
        """
        min_active_ratio = getattr(config, 'MIN_VOICE_ACTIVITY_RATIO', 0.10)
        min_speech_duration = getattr(config, 'MIN_SPEECH_DURATION', 0.25)
        speech_margin = getattr(config, 'SPEECH_MARGIN_FACTOR', 1.2)
        # "Active seconds" approximates voiced content by amplitude alone; the
        # ZCR-based voiced_seconds below is the stronger, keyboard-aware check.
        active_seconds = active_ratio * duration

        if duration < 0.3:
            return f"too short ({duration:.2f}s < 0.30s)"
        if active_ratio < min_active_ratio:
            return f"low activity ratio ({active_ratio:.2f} < {min_active_ratio:.2f})"
        if active_seconds < min_speech_duration:
            return f"insufficient active audio ({active_seconds:.2f}s < {min_speech_duration:.2f}s)"
        if threshold > 0 and max_amplitude < threshold * speech_margin:
            return (f"too quiet (max_amp {max_amplitude:.0f} < "
                    f"{speech_margin:.1f}x threshold {threshold:.0f})")
        if (getattr(config, 'REQUIRE_VOICED', True) and voiced_seconds is not None):
            min_voiced = getattr(config, 'MIN_VOICED_DURATION', 0.12)
            if voiced_seconds < min_voiced:
                return (f"no sustained voiced speech (voiced={voiced_seconds:.2f}s < "
                        f"{min_voiced:.2f}s) — likely keyboard/noise")
        return None

    def _voiced_seconds(self, audio_array: np.ndarray, threshold: float) -> float:
        """
        Estimate the seconds of loud, *voiced* audio in a clip.

        A frame counts if it is both active (peak crosses the threshold) and
        voiced (zero-crossing rate below MAX_VOICED_ZCR). Voiced speech (vowels)
        has a low ZCR; keyboard clicks and other impulsive noise are broadband
        transients with a high ZCR. Requiring a minimum amount of voiced audio is
        therefore what distinguishes a spoken phrase from keyboard clatter that
        is otherwise loud and long enough to pass the amplitude-based gates.

        Args:
            audio_array: int16 samples of the captured clip.
            threshold: Amplitude threshold for an "active" frame.

        Returns:
            Estimated seconds of voiced audio.
        """
        frame_len = self.chunk_size
        n_frames = len(audio_array) // frame_len
        if n_frames == 0:
            return 0.0

        frames = audio_array[:n_frames * frame_len].reshape(n_frames, frame_len).astype(np.float64)
        peaks = np.max(np.abs(frames), axis=1)

        # Zero-crossing rate per frame: fraction of adjacent sample pairs that
        # change sign. Silence (all zeros) yields 0, so it never counts as voiced
        # and is correctly excluded by the amplitude test below anyway.
        signs = np.sign(frames)
        zcr = np.mean(np.diff(signs, axis=1) != 0, axis=1)

        max_zcr = getattr(config, 'MAX_VOICED_ZCR', 0.20)
        voiced_frames = int(np.sum((peaks > threshold) & (zcr < max_zcr)))
        frame_duration = frame_len / float(self.sample_rate)
        return voiced_frames * frame_duration

    def is_silent(self, data_array: np.ndarray) -> bool:
        """
        Determine if the audio chunk is silent.

        Args:
            data_array: Numpy array of audio data

        Returns:
            True if the audio is below the silence threshold
        """
        max_amplitude = np.max(np.abs(data_array))
        return max_amplitude < self.effective_threshold()
    
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
        median_level = np.median(self.calibration_samples)
        max_level = np.max(self.calibration_samples)
        p90_level = np.percentile(self.calibration_samples, 90)
        
        # Use a smart approach based on the noise profile
        # - If the environment is very quiet, use a reasonable minimum threshold
        # - If noise fluctuates a lot, use a more conservative approach
        noise_range = max_level - min_level
        
        # More conservative approach - ensure threshold isn't too high or too low
        if mean_level < 100:
            # Very quiet environment - use a minimum threshold to avoid over-sensitivity
            base_threshold = 500
            debug_log(f"Very quiet environment detected (mean level: {mean_level:.1f}), using minimum threshold")
        elif noise_range > mean_level * 2:
            # High variance environment - use 95th percentile + buffer
            base_threshold = np.percentile(self.calibration_samples, 95) * 1.5
            debug_log(f"High variance environment detected (range: {noise_range:.1f}), using conservative threshold")
        else:
            # Standard environment - use median * factor for better stability than mean
            base_threshold = max(median_level * self.calibration_factor, 500)
            debug_log(f"Standard environment detected, using median-based threshold")
        
        # Apply config factor if specified
        if hasattr(config, 'THRESHOLD_ADJUSTMENT_FACTOR'):
            base_threshold *= config.THRESHOLD_ADJUSTMENT_FACTOR
            
        # Set a reasonable upper bound on initial threshold to prevent over-dampening
        self.adaptive_threshold = min(base_threshold, 2000)
        
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
        speech_detected = False
        silence_after_speech = False

        # Use configured maximum sentence duration
        max_frames = int(self.sample_rate / self.chunk_size * config.MAX_SENTENCE_DURATION)
        max_amplitude_seen = 0

        try:
            # First, wait for speech to begin.
            #
            # We keep only a short rolling buffer of pre-speech audio (so the
            # start of the utterance isn't clipped) while capping how long we
            # wait so the caller can periodically recalibrate during silence.
            # `frames` is trimmed for memory, so track the total frames read
            # separately to make the wait timeout actually reachable.
            print("Waiting for speech...")
            wait_frames_read = 0
            while not speech_detected and wait_frames_read < max_frames:
                data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                frames.append(data)
                wait_frames_read += 1

                # Convert to numpy array for silence detection
                data_array = np.frombuffer(data, dtype=np.int16)

                # Check if this frame contains speech
                if not self.is_silent(data_array):
                    speech_detected = True
                    print("Speech detected! Capturing full sentence...")

                # If we've captured a lot of frames with no speech, discard them and keep waiting
                if len(frames) > 30 and not speech_detected:  # ~1 second of silence
                    frames = frames[-10:]  # Keep only last ~0.3 seconds

            # If no speech detected within the wait window, return early so the
            # caller can recalibrate / idle.
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
            # Fall back to the static threshold if calibration never ran, so we
            # never do arithmetic on None.
            old_threshold = self.effective_threshold()
            # More conservative adjustment: increase by 10% for first trigger,
            # then more gradually for subsequent triggers
            adjustment_factor = min(0.1 * false_trigger_count, 0.5)  # Cap at 50% increase
            self.adaptive_threshold = old_threshold * (1 + adjustment_factor)
            
            # Put a cap on the maximum threshold to prevent it from getting too high
            max_reasonable_threshold = 3000  # Based on typical int16 audio values
            if self.adaptive_threshold > max_reasonable_threshold:
                self.adaptive_threshold = max_reasonable_threshold
                debug_log(f"Threshold capped at maximum reasonable value: {max_reasonable_threshold}")
                
            debug_log(f"Adjusted threshold after false trigger: {old_threshold:.1f} → {self.adaptive_threshold:.1f}")
            
        # Allow periodic recalibration to recover from a threshold that's been raised too high
        if false_trigger_count >= 3:
            # If we've had several false triggers in a row, do a fresh calibration
            debug_log("Multiple false triggers detected - performing fresh calibration")
            self.calibrate_silence_threshold()
            self.last_calibration_time = time.time()
            return
            
        # Periodically recalibrate after long idle periods (randomly, ~10% chance when idle)
        if not hasattr(self, 'last_calibration_time') or time.time() - self.last_calibration_time > 60:
            if np.random.random() < 0.1:  # 10% chance to recalibrate when idle
                debug_log("Performing periodic recalibration during idle time")
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

                                # Voice-activity ratio: the fraction of frames
                                # whose peak crosses the threshold. This is a far
                                # better discriminator than average amplitude,
                                # which is dragged down by the trailing silence
                                # and inter-word gaps in a real utterance (a whole
                                # spoken sentence can average well under the
                                # threshold while still being genuine speech).
                                threshold = self.effective_threshold()
                                active_ratio = self._voice_activity_ratio(audio_array, threshold)
                                voiced_seconds = self._voiced_seconds(audio_array, threshold)

                                # False positive detection: discard clips that
                                # don't look like genuine speech (too short, too
                                # little active/voiced audio, or too quiet). The
                                # voiced-audio check is the main defense against
                                # keyboard clicks being transcribed while typing.
                                # Tunable via config.
                                reason = self._rejection_reason(
                                    duration, active_ratio, max_amplitude, threshold, voiced_seconds)
                                if reason:
                                    debug_log(f"Rejected non-speech clip: {reason} "
                                              f"[duration={duration:.2f}s, active_ratio={active_ratio:.2f}, "
                                              f"voiced={voiced_seconds:.2f}s, avg_amp={avg_amplitude:.1f}, "
                                              f"max_amp={max_amplitude:.1f}, threshold={threshold:.1f}]")
                                    false_trigger_count += 1
                                    self.recalibrate_if_needed(false_trigger_count)
                                    os.remove(file_path)  # Clean up the audio file
                                    continue

                                # Log actual speech characteristics for debugging
                                debug_log(f"Accepted speech clip: duration={duration:.2f}s, active_ratio={active_ratio:.2f}, "
                                          f"voiced={voiced_seconds:.2f}s, avg_amp={avg_amplitude:.1f}, "
                                          f"max_amp={max_amplitude:.1f}, threshold={threshold:.1f}")
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
