"""
Unit tests for the Parakeet backend and the Transcriber engine dispatch.

onnx_asr is mocked so these tests are fast and never load the real model.
"""

import sys
from unittest.mock import MagicMock, patch

from xvoice2.parakeet_backend import ParakeetTranscriber
from xvoice2.transcriber import Transcriber


def _mock_onnx_asr(recognize_return="hello world"):
    """Build a fake onnx_asr module whose model.recognize returns given text."""
    mock_model = MagicMock()
    mock_model.recognize.return_value = recognize_return
    mock_module = MagicMock()
    mock_module.load_model.return_value = mock_model
    return mock_module, mock_model


class TestParakeetBackend:
    """Tests for ParakeetTranscriber."""

    def test_is_available_true_when_importable(self):
        mod, _ = _mock_onnx_asr()
        with patch.dict(sys.modules, {"onnx_asr": mod}):
            assert ParakeetTranscriber().is_available() is True

    def test_is_available_false_when_missing(self):
        # A None entry in sys.modules makes `import onnx_asr` raise ImportError.
        with patch.dict(sys.modules, {"onnx_asr": None}):
            assert ParakeetTranscriber().is_available() is False

    def test_transcribe_returns_recognized_text(self):
        mod, model = _mock_onnx_asr("And so my fellow Americans")
        with patch.dict(sys.modules, {"onnx_asr": mod}), \
             patch("os.path.exists", return_value=True):
            t = ParakeetTranscriber()
            assert t.transcribe("clip.wav") == "And so my fellow Americans"
            model.recognize.assert_called_once_with("clip.wav")

    def test_model_is_loaded_only_once(self):
        """The model must stay resident across calls, not reload each time."""
        mod, _ = _mock_onnx_asr()
        with patch.dict(sys.modules, {"onnx_asr": mod}), \
             patch("os.path.exists", return_value=True):
            t = ParakeetTranscriber()
            t.transcribe("a.wav")
            t.transcribe("b.wav")
            mod.load_model.assert_called_once()

    def test_uses_configured_model_name(self):
        mod, _ = _mock_onnx_asr()
        with patch.dict(sys.modules, {"onnx_asr": mod}), \
             patch("os.path.exists", return_value=True):
            ParakeetTranscriber(model_name="nemo-parakeet-tdt-0.6b-v3").transcribe("a.wav")
            mod.load_model.assert_called_once_with("nemo-parakeet-tdt-0.6b-v3")

    def test_missing_file_returns_none(self):
        mod, _ = _mock_onnx_asr()
        with patch.dict(sys.modules, {"onnx_asr": mod}), \
             patch("os.path.exists", return_value=False):
            assert ParakeetTranscriber().transcribe("nope.wav") is None

    def test_recognize_exception_returns_none(self):
        mod, model = _mock_onnx_asr()
        model.recognize.side_effect = RuntimeError("boom")
        with patch.dict(sys.modules, {"onnx_asr": mod}), \
             patch("os.path.exists", return_value=True):
            assert ParakeetTranscriber().transcribe("a.wav") is None

    def test_empty_result_returns_none(self):
        mod, _ = _mock_onnx_asr("")
        with patch.dict(sys.modules, {"onnx_asr": mod}), \
             patch("os.path.exists", return_value=True):
            assert ParakeetTranscriber().transcribe("a.wav") is None


class TestTranscriberEngineDispatch:
    """The Transcriber should route to Parakeet when the engine is selected."""

    def test_dispatches_to_parakeet(self):
        with patch("xvoice2.config.TRANSCRIPTION_ENGINE", "parakeet"):
            t = Transcriber()
            assert t.engine == "parakeet"
            backend = MagicMock()
            backend.transcribe.return_value = "hello world"
            with patch.object(t, "_get_parakeet_backend", return_value=backend), \
                 patch("os.path.exists", return_value=True):
                assert t.transcribe("clip.wav") == "hello world"
            backend.transcribe.assert_called_once_with("clip.wav")

    def test_parakeet_output_runs_through_hallucination_filter(self):
        """Parakeet output is cleaned/filtered like the Whisper paths."""
        with patch("xvoice2.config.TRANSCRIPTION_ENGINE", "parakeet"):
            t = Transcriber()
            backend = MagicMock()
            backend.transcribe.return_value = "Thank you."
            with patch.object(t, "_get_parakeet_backend", return_value=backend), \
                 patch("os.path.exists", return_value=True):
                assert not t.transcribe("clip.wav")  # dropped as a hallucination

    def test_is_available_uses_parakeet_backend(self):
        with patch("xvoice2.config.TRANSCRIPTION_ENGINE", "parakeet"):
            t = Transcriber()
            backend = MagicMock()
            backend.is_available.return_value = True
            with patch.object(t, "_get_parakeet_backend", return_value=backend):
                assert t.is_available() is True
                backend.is_available.assert_called_once()

    def test_is_model_available_true_for_parakeet(self):
        with patch("xvoice2.config.TRANSCRIPTION_ENGINE", "parakeet"):
            assert Transcriber().is_model_available() is True
