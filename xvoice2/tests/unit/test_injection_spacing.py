"""
Tests for trailing-space handling between dictated utterances (main._process_audio).
"""

from unittest.mock import patch

from xvoice2.transcriber import Transcriber
from xvoice2.text_injector import TextInjector
from xvoice2.main import VoiceDictationApp


def _inject_for(transcript, mode="general", append=True):
    """Run _process_audio with mocks and return the text passed to inject_text."""
    captured = {}
    with patch.object(Transcriber, "is_available", return_value=True), \
         patch.object(TextInjector, "is_available", return_value=True), \
         patch.object(Transcriber, "transcribe", return_value=transcript), \
         patch.object(TextInjector, "inject_text",
                      side_effect=lambda t: captured.setdefault("t", t) or True), \
         patch("xvoice2.config.WAKE_WORD_ENABLED", False), \
         patch("xvoice2.config.USE_LLM", False), \
         patch("xvoice2.config.USE_LOCAL_LLM", False), \
         patch("xvoice2.config.APPEND_TRAILING_SPACE", append), \
         patch("os.path.exists", return_value=True):
        app = VoiceDictationApp(mode=mode)
        app._process_audio("clip.wav")
    return captured.get("t")


class TestInjectionSpacing:
    def test_trailing_space_appended_for_dictation(self):
        assert _inject_for("This is a test.") == "This is a test. "

    def test_consecutive_sentences_are_separated(self):
        """Two utterances injected back-to-back get a separating space each."""
        first = _inject_for("First sentence.")
        second = _inject_for("Second sentence.")
        # Concatenation of what actually reaches the target window.
        assert first + second == "First sentence. Second sentence. "

    def test_no_double_space_when_already_spaced(self):
        assert _inject_for("Already spaced ") == "Already spaced "

    def test_command_mode_gets_no_trailing_space(self):
        assert _inject_for("ls -la", mode="command") == "ls -la"

    def test_can_be_disabled(self):
        assert _inject_for("No space please.", append=False) == "No space please."
