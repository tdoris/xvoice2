"""
Unit tests for the mic_stream module.
"""

import pytest
import os
import tempfile
import numpy as np
from unittest.mock import patch, MagicMock

from xvoice2 import config
from xvoice2.mic_stream import MicrophoneStream

class TestMicrophoneStream:
    """Tests for the MicrophoneStream class."""
    
    def test_init(self):
        """Test initialization of MicrophoneStream."""
        with patch('pyaudio.PyAudio'):
            stream = MicrophoneStream()
            
            assert stream.sample_rate == config.SAMPLE_RATE
            assert stream.chunk_size == config.FRAMES_PER_BUFFER
            assert stream.channels == config.CHANNELS
            assert stream.silence_threshold == config.SILENCE_THRESHOLD
    
    def test_find_input_device(self, mock_pyaudio):
        """Test finding input devices."""
        stream = MicrophoneStream()
        result = stream._find_input_device()
        
        assert result is True
        assert stream.device_index == 1  # Second device (index 1) has input channels
    
    def test_is_silent_with_silent_data(self, mock_audio_data_silent):
        """Test silence detection with silent audio."""
        with patch('pyaudio.PyAudio'):
            stream = MicrophoneStream()
            # Set a fixed adaptive threshold for testing
            stream.adaptive_threshold = 500
            stream.auto_calibration_complete = True
            
            result = stream.is_silent(mock_audio_data_silent)
            assert result == True
    
    def test_is_silent_with_speech_data(self, mock_audio_data_speech):
        """Test silence detection with speech audio."""
        with patch('pyaudio.PyAudio'):
            stream = MicrophoneStream()
            # Set a fixed adaptive threshold for testing
            stream.adaptive_threshold = 500
            stream.auto_calibration_complete = True
            
            result = stream.is_silent(mock_audio_data_speech)
            assert result == False

    def test_is_silent_uses_fallback_when_uncalibrated(self, mock_audio_data_silent):
        """Regression: is_silent must not crash when adaptive_threshold is None.

        adaptive_threshold is initialized to None, so it must fall back to the
        configured static threshold rather than comparing against None.
        """
        with patch('pyaudio.PyAudio'):
            stream = MicrophoneStream()
            assert stream.adaptive_threshold is None  # never calibrated
            # Should use config.SILENCE_THRESHOLD and not raise a TypeError
            assert stream.is_silent(mock_audio_data_silent) == True

    def test_voice_activity_ratio_detects_real_speech(self):
        """Regression: a real utterance must not be treated as a false trigger.

        Reproduces the logged failure where clips with strong speech peaks were
        discarded because their *average* amplitude fell below 30% of threshold.
        A low-average clip with sustained above-threshold frames must yield a
        high voice-activity ratio.
        """
        with patch('pyaudio.PyAudio'):
            stream = MicrophoneStream()
            stream.chunk_size = 1024
            threshold = 500

            # The "speech" half models a real waveform: strong per-frame peaks
            # that oscillate through zero, so the per-frame peak is high while
            # the overall average stays low (like the wrongly-discarded clips).
            speech = np.zeros(1024 * 24, dtype=np.int16)
            speech[::1024] = 5000
            speech[512::1024] = -5000
            silence = np.zeros(1024 * 24, dtype=np.int16)
            clip = np.concatenate([speech, silence])

            ratio = stream._voice_activity_ratio(clip, threshold)
            assert ratio > 0.10
            # Its average amplitude would have failed the old avg < 0.3*thr test
            assert np.mean(np.abs(clip)) < threshold * 0.3

    def test_voice_activity_ratio_rejects_stray_click(self):
        """A lone click in a sea of silence yields a near-zero activity ratio."""
        with patch('pyaudio.PyAudio'):
            stream = MicrophoneStream()
            stream.chunk_size = 1024
            threshold = 500

            clip = np.zeros(1024 * 20, dtype=np.int16)
            clip[5000:5050] = 8000  # a single brief spike

            ratio = stream._voice_activity_ratio(clip, threshold)
            assert ratio < 0.10

    def test_rejection_reason_accepts_genuine_speech(self):
        """A clip with ample loud, voiced audio is accepted (reason is None)."""
        with patch('pyaudio.PyAudio'):
            stream = MicrophoneStream()
            reason = stream._rejection_reason(
                duration=2.0, active_ratio=0.6, max_amplitude=6000, threshold=500)
            assert reason is None

    def test_rejection_reason_rejects_too_short(self):
        with patch('pyaudio.PyAudio'):
            stream = MicrophoneStream()
            reason = stream._rejection_reason(
                duration=0.2, active_ratio=0.9, max_amplitude=6000, threshold=500)
            assert reason is not None and "too short" in reason

    def test_rejection_reason_rejects_low_activity(self):
        with patch('pyaudio.PyAudio'):
            stream = MicrophoneStream()
            reason = stream._rejection_reason(
                duration=2.0, active_ratio=0.02, max_amplitude=6000, threshold=500)
            assert reason is not None and "activity ratio" in reason

    def test_rejection_reason_rejects_insufficient_active_audio(self):
        """A brief blip: high ratio over a short window but little real speech.

        This is the "thank you" hallucination case — passes the ratio and
        duration floors but has too little actual active audio.
        """
        with patch('pyaudio.PyAudio'):
            stream = MicrophoneStream()
            # 0.5s clip, 20% active -> only 0.1s active, below the 0.25s floor.
            reason = stream._rejection_reason(
                duration=0.5, active_ratio=0.2, max_amplitude=6000, threshold=500)
            assert reason is not None and "active audio" in reason

    def test_rejection_reason_rejects_too_quiet(self):
        """A clip that barely crosses the threshold is rejected as ambient noise."""
        with patch('pyaudio.PyAudio'):
            stream = MicrophoneStream()
            # max_amp only 1.05x threshold, below the 1.2x margin.
            reason = stream._rejection_reason(
                duration=2.0, active_ratio=0.6, max_amplitude=525, threshold=500)
            assert reason is not None and "too quiet" in reason

    def test_rejection_reason_respects_config(self):
        """Loosening the config accepts a clip the defaults would reject."""
        with patch('pyaudio.PyAudio'):
            stream = MicrophoneStream()
            args = dict(duration=0.5, active_ratio=0.2, max_amplitude=525, threshold=500)
            # Defaults reject (insufficient active audio / too quiet)...
            assert stream._rejection_reason(**args) is not None
            # ...but a permissive config accepts it.
            with patch('xvoice2.config.MIN_SPEECH_DURATION', 0.05), \
                 patch('xvoice2.config.SPEECH_MARGIN_FACTOR', 1.0):
                assert stream._rejection_reason(**args) is None

    def test_voiced_seconds_detects_vowel_like_tone(self):
        """A low-frequency tone (like a vowel) has a low ZCR and counts as voiced."""
        with patch('pyaudio.PyAudio'):
            stream = MicrophoneStream()
            stream.chunk_size = 1024
            stream.sample_rate = 16000
            t = np.arange(16000)  # 1 second
            tone = (8000 * np.sin(2 * np.pi * 150 * t / 16000)).astype(np.int16)
            voiced = stream._voiced_seconds(tone, threshold=500)
            assert voiced > 0.8  # nearly the whole second is voiced

    def test_voiced_seconds_rejects_keyboard_like_noise(self):
        """A loud broadband/high-ZCR signal (like key clicks) is not voiced."""
        with patch('pyaudio.PyAudio'):
            stream = MicrophoneStream()
            stream.chunk_size = 1024
            stream.sample_rate = 16000
            # Alternating sign every sample -> maximal ZCR: loud but not voiced.
            noise = np.zeros(16000, dtype=np.int16)
            noise[::2] = 8000
            noise[1::2] = -8000
            voiced = stream._voiced_seconds(noise, threshold=500)
            assert voiced < 0.05

    def test_rejection_reason_rejects_unvoiced_keyboard_clatter(self):
        """Loud, long, active audio with ~no voiced content is rejected."""
        with patch('pyaudio.PyAudio'):
            stream = MicrophoneStream()
            reason = stream._rejection_reason(
                duration=2.0, active_ratio=0.6, max_amplitude=8000, threshold=500,
                voiced_seconds=0.03)
            assert reason is not None and "voiced" in reason

    def test_rejection_reason_accepts_voiced_speech(self):
        with patch('pyaudio.PyAudio'):
            stream = MicrophoneStream()
            reason = stream._rejection_reason(
                duration=2.0, active_ratio=0.6, max_amplitude=8000, threshold=500,
                voiced_seconds=0.8)
            assert reason is None

    def test_require_voiced_can_be_disabled(self):
        """With REQUIRE_VOICED off, an unvoiced-but-otherwise-valid clip passes."""
        with patch('pyaudio.PyAudio'):
            stream = MicrophoneStream()
            args = dict(duration=2.0, active_ratio=0.6, max_amplitude=8000,
                        threshold=500, voiced_seconds=0.0)
            assert stream._rejection_reason(**args) is not None
            with patch('xvoice2.config.REQUIRE_VOICED', False):
                assert stream._rejection_reason(**args) is None

    def test_effective_threshold_falls_back_when_uncalibrated(self):
        """effective_threshold() returns the static threshold when uncalibrated."""
        with patch('pyaudio.PyAudio'):
            stream = MicrophoneStream()
            assert stream.adaptive_threshold is None
            assert stream.effective_threshold() == config.SILENCE_THRESHOLD

            stream.adaptive_threshold = 1234
            assert stream.effective_threshold() == 1234

    def test_recalibrate_if_needed_uncalibrated_no_crash(self):
        """Regression: false-trigger recalibration must not multiply None."""
        with patch('pyaudio.PyAudio'):
            stream = MicrophoneStream()
            assert stream.adaptive_threshold is None

            stream.recalibrate_if_needed(false_trigger_count=1)
            assert stream.adaptive_threshold is not None
            assert stream.adaptive_threshold > config.SILENCE_THRESHOLD

    @patch('tempfile.mkdtemp')
    def test_close_is_idempotent(self, mock_mkdtemp):
        """Regression: close() must be safe to call more than once."""
        mock_mkdtemp.return_value = "/tmp/mock_dir"
        with patch('pyaudio.PyAudio'):
            with patch('os.listdir', return_value=[]):
                with patch('os.rmdir') as mock_rmdir:
                    stream = MicrophoneStream()
                    stream.close()
                    stream.close()  # must not raise
                    mock_rmdir.assert_called_once_with("/tmp/mock_dir")

    @patch('tempfile.mkdtemp')
    def test_context_manager(self, mock_mkdtemp):
        """Test that context manager properly initializes and cleans up."""
        mock_mkdtemp.return_value = "/tmp/mock_dir"
        
        with patch('pyaudio.PyAudio'):
            with patch('os.listdir', return_value=[]):
                with patch('os.rmdir') as mock_rmdir:
                    with MicrophoneStream() as stream:
                        assert isinstance(stream, MicrophoneStream)
                    
                    # Check cleanup was called
                    mock_rmdir.assert_called_once_with("/tmp/mock_dir")
    
    @patch('wave.open')
    @patch('os.path.join')
    @patch('time.time')
    @patch('tempfile.mkdtemp')
    def test_capture_chunk_with_speech(self, mock_mkdtemp, mock_time, mock_join, mock_wave, mock_audio_data_speech):
        """Test capturing an audio chunk with speech."""
        mock_mkdtemp.return_value = "/tmp/test_dir"
        mock_time.return_value = 12345.67
        mock_join.return_value = "/tmp/test_dir/chunk_12345.67.wav"
        
        with patch('pyaudio.PyAudio') as mock_pyaudio:
            # Mock the audio stream
            mock_stream = MagicMock()
            mock_stream.read.return_value = b'mock_audio_data'
            
            mock_instance = MagicMock()
            mock_pyaudio.return_value = mock_instance
            mock_instance.open.return_value = mock_stream
            
            # Disable calibration for testing
            with patch.object(config, 'CALIBRATION_ENABLED', False):
                # Mock numpy array conversion to detect speech
                with patch('numpy.frombuffer', return_value=mock_audio_data_speech):
                    stream = MicrophoneStream()
                    # Set a fixed adaptive threshold for testing
                    stream.adaptive_threshold = 500
                    stream.auto_calibration_complete = True
                    stream.stream = mock_stream  # Set the mocked stream
                    
                    filepath, speech_detected = stream.capture_chunk()
                    
                    assert speech_detected is True
                    assert filepath == "/tmp/test_dir/chunk_12345.67.wav"
    
    @patch('time.sleep')  # Mock sleep to speed up the test
    def test_listen_continuous(self, mock_sleep):
        """Test the continuous listening generator."""
        with patch('pyaudio.PyAudio'):
            stream = MicrophoneStream()
            
            # Mock capture_chunk to return some predetermined values
            mock_return_values = [
                ("/tmp/chunk1.wav", True),  # First chunk has speech
                ("/tmp/chunk2.wav", False),  # Second chunk has no speech
                ("", False),                # Third chunk has error
                Exception("Test exception")  # Fourth call raises exception to exit
            ]
            
            stream.start_stream = MagicMock()  # Mock start_stream
            stream.capture_chunk = MagicMock(side_effect=mock_return_values)
            stream.close = MagicMock()  # Mock close
            
            # Call the generator and collect results
            results = []
            try:
                for file_path in stream.listen_continuous():
                    results.append(file_path)
                    if len(results) >= 1:  # Only get the first result to exit the loop
                        break
            except Exception:
                pass  # Expected exception to terminate the loop
            
            assert results == ["/tmp/chunk1.wav"]  # Only the chunk with speech
            stream.start_stream.assert_called_once()
            stream.close.assert_called_once()