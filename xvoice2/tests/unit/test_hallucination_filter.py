"""
Unit tests for Whisper hallucination filtering in the transcriber module.
"""

from unittest.mock import patch

from xvoice2.transcriber import clean_transcription, is_hallucination


class TestHallucinationFilter:
    """Whole-utterance hallucination phrases are dropped; real speech is kept."""

    def test_bare_thank_you_is_dropped(self):
        assert clean_transcription("Thank you.") == ""
        assert clean_transcription("thank you") == ""

    def test_thanks_for_watching_is_dropped(self):
        assert clean_transcription("Thanks for watching!") == ""

    def test_case_and_punctuation_insensitive(self):
        assert is_hallucination("THANK YOU!!!") is True
        assert is_hallucination("  you  ") is True

    def test_phrase_inside_sentence_is_kept(self):
        """A hallucination phrase used within a longer sentence is preserved."""
        text = "thank you for reviewing the pull request"
        assert clean_transcription(text) == text

    def test_normal_speech_is_untouched(self):
        text = "def parse the config file"
        assert clean_transcription(text) == text

    def test_blank_audio_still_stripped(self):
        assert clean_transcription("[BLANK_AUDIO]") == ""

    def test_filter_can_be_disabled(self):
        with patch("xvoice2.config.FILTER_HALLUCINATIONS", False):
            assert clean_transcription("Thank you.") == "Thank you."
            assert is_hallucination("thank you") is False

    def test_custom_phrase_list(self):
        with patch("xvoice2.config.HALLUCINATION_PHRASES", ["foobar baz"]):
            assert is_hallucination("Foobar, baz!") is True
            # Default phrases no longer apply when the list is overridden.
            assert is_hallucination("thank you") is False

    def test_empty_input(self):
        assert is_hallucination("") is False
        assert clean_transcription("") == ""
