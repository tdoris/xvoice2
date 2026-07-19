"""
Unit tests for the wake_word module.
"""

import pytest

from xvoice2.wake_word import WakeWordController, WakeResult


class TestSessionMode:
    """Session model: wake phrase arms, sleep phrase pauses."""

    def _controller(self, **kwargs):
        defaults = dict(
            mode="session",
            wake_phrase="start dictation",
            sleep_phrase="stop dictation",
            wake_prefix="computer",
            start_armed=False,
        )
        defaults.update(kwargs)
        return WakeWordController(**defaults)

    def test_starts_sleeping_and_ignores_speech(self):
        """While sleeping, ordinary speech is not injected."""
        c = self._controller()
        result = c.evaluate("hello there how are you")
        assert result.should_inject is False
        assert result.armed is False
        assert result.state_changed is False

    def test_wake_phrase_arms_but_is_not_typed(self):
        """The wake phrase arms dictation and is never itself injected."""
        c = self._controller()
        result = c.evaluate("start dictation")
        assert result.armed is True
        assert result.state_changed is True
        assert result.should_inject is False

    def test_injects_after_arming(self):
        """Once armed, ordinary speech is injected verbatim."""
        c = self._controller()
        c.evaluate("start dictation")
        result = c.evaluate("def parse the config file")
        assert result.should_inject is True
        assert result.text == "def parse the config file"
        assert result.armed is True
        assert result.state_changed is False

    def test_sleep_phrase_pauses_and_is_not_typed(self):
        """The sleep phrase pauses dictation and is not injected."""
        c = self._controller()
        c.evaluate("start dictation")
        result = c.evaluate("stop dictation")
        assert result.armed is False
        assert result.state_changed is True
        assert result.should_inject is False

    def test_ignores_speech_after_pausing(self):
        """After pausing, speech is ignored again until the next wake phrase."""
        c = self._controller()
        c.evaluate("start dictation")
        c.evaluate("stop dictation")
        result = c.evaluate("this should not be typed")
        assert result.should_inject is False
        assert result.armed is False

    def test_wake_phrase_matches_with_surrounding_filler(self):
        """Wake phrase is detected even amid filler words and punctuation."""
        c = self._controller()
        result = c.evaluate("Okay, start dictation please.")
        assert result.armed is True
        assert result.should_inject is False

    def test_wake_phrase_is_case_and_punctuation_insensitive(self):
        """Matching is normalized for case and punctuation."""
        c = self._controller()
        result = c.evaluate("START, DICTATION!")
        assert result.armed is True

    def test_start_armed(self):
        """start_armed begins in the armed state."""
        c = self._controller(start_armed=True)
        assert c.armed is True
        result = c.evaluate("already typing")
        assert result.should_inject is True
        assert result.text == "already typing"

    def test_wake_phrase_not_matched_as_substring_of_word(self):
        """A phrase must match on word boundaries, not inside another word."""
        c = self._controller(wake_phrase="go", sleep_phrase="stop dictation")
        # "going" should not trigger the "go" wake phrase
        result = c.evaluate("going to the store")
        assert result.armed is False


class TestPrefixMode:
    """Prefix model: only utterances beginning with the prefix are injected."""

    def _controller(self, **kwargs):
        defaults = dict(mode="prefix", wake_prefix="computer")
        defaults.update(kwargs)
        return WakeWordController(**defaults)

    def test_prefix_utterance_is_injected_with_prefix_stripped(self):
        c = self._controller()
        result = c.evaluate("computer open the file")
        assert result.should_inject is True
        assert result.text == "open the file"

    def test_non_prefixed_utterance_is_ignored(self):
        c = self._controller()
        result = c.evaluate("open the file")
        assert result.should_inject is False
        assert result.text is None

    def test_prefix_only_injects_nothing(self):
        """Saying just the prefix with no content injects nothing."""
        c = self._controller()
        result = c.evaluate("computer")
        assert result.should_inject is False

    def test_prefix_preserves_inner_capitalization(self):
        """Stripping the prefix preserves the rest of the raw transcript."""
        c = self._controller()
        result = c.evaluate("Computer, Send the Report Now")
        assert result.should_inject is True
        assert result.text == "Send the Report Now"

    def test_multi_word_prefix(self):
        c = self._controller(wake_prefix="hey computer")
        result = c.evaluate("hey computer what time is it")
        assert result.should_inject is True
        assert result.text == "what time is it"

    def test_prefix_mode_never_persists_armed_state(self):
        c = self._controller()
        c.evaluate("computer type this")
        # Next non-prefixed utterance is still ignored.
        result = c.evaluate("but not this")
        assert result.should_inject is False


class TestGeneral:
    """Cross-cutting behavior."""

    def test_empty_transcript_is_noop(self):
        c = WakeWordController(mode="session", wake_phrase="start", sleep_phrase="stop")
        for text in ("", "   ", None):
            result = c.evaluate(text)
            assert result.should_inject is False
            assert result.state_changed is False

    def test_status_strings(self):
        session = WakeWordController(mode="session", wake_phrase="a", sleep_phrase="b")
        assert session.status() == "SLEEPING"
        session.armed = True
        assert session.status() == "ARMED"
        prefix = WakeWordController(mode="prefix", wake_prefix="x")
        assert prefix.status() == "PREFIX"

    def test_normalize(self):
        assert WakeWordController._normalize("Hello, World!") == "hello world"
        assert WakeWordController._normalize("  multiple   spaces  ") == "multiple spaces"
        assert WakeWordController._normalize("") == ""
