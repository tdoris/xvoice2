"""
Parakeet speech-to-text backend using onnx-asr (ONNX Runtime).

NVIDIA Parakeet is a transducer ASR model. Unlike Whisper (an autoregressive
model trained on captions, which hallucinates stock phrases on silence),
Parakeet only emits tokens when there is acoustic evidence of speech, and it
outputs punctuated, capitalized text directly. This backend runs it fully
locally via the lightweight `onnx-asr` package.

The model is large and slow to load, so it is loaded lazily on first use and
kept resident for the lifetime of the process. onnx-asr accepts a 16 kHz mono
WAV path directly, which is exactly what MicrophoneStream writes, so no audio
conversion is needed here.
"""

import os
from typing import Optional

from xvoice2 import config
from xvoice2.logging_util import debug_log


class ParakeetTranscriber:
    """Local Parakeet transcription via onnx-asr, with a lazily-loaded model."""

    def __init__(self, model_name: Optional[str] = None):
        """Initialize the backend.

        Args:
            model_name: onnx-asr model id. Defaults to config.PARAKEET_MODEL.
        """
        self.model_name = model_name or getattr(
            config, "PARAKEET_MODEL", "nemo-parakeet-tdt-0.6b-v2")
        self._model = None  # Loaded on first transcribe()

    def is_available(self) -> bool:
        """Return True if the onnx-asr runtime is importable."""
        try:
            import onnx_asr  # noqa: F401
            return True
        except ImportError:
            return False

    def warm_up(self) -> None:
        """Pre-load the model so the first transcription isn't delayed."""
        self._ensure_loaded()

    def _ensure_loaded(self):
        """Load and cache the Parakeet model on first use."""
        if self._model is None:
            import onnx_asr
            debug_log(
                f"Loading Parakeet model '{self.model_name}' "
                f"(first run downloads it and may take a while)...")
            self._model = onnx_asr.load_model(self.model_name)
            debug_log("Parakeet model loaded.")
        return self._model

    def transcribe(self, audio_file: str) -> Optional[str]:
        """Transcribe a 16 kHz mono WAV file to raw text.

        Args:
            audio_file: Path to the audio file.

        Returns:
            Raw transcribed text (Parakeet already includes punctuation and
            capitalization), or None on error / no file. Cleaning and any
            hallucination filtering are applied by the caller.
        """
        if not os.path.exists(audio_file):
            debug_log(f"Audio file not found: {audio_file}")
            return None
        try:
            model = self._ensure_loaded()
            text = model.recognize(audio_file)
        except Exception as e:
            debug_log(f"Parakeet transcription error: {e}")
            return None
        return text or None
