"""
Wake-word activation gating for always-on dictation.

XVoice2 keeps the microphone always listening, but continuously typing
everything the user says is impractical (it injects stray speech into whatever
window is focused). This module adds a control layer between transcription and
injection: the mic stays on, every clip is still transcribed, but text is only
injected when dictation is "armed".

Two interaction models are supported (config.WAKE_MODE):
  - "session": say the wake phrase to arm, then everything is typed until the
    sleep phrase is heard. Best for continuous dictation / coding.
  - "prefix":  say a short prefix word immediately before each phrase you want
    typed. No persistent state; safer against accidental injection.

Detection reuses the existing Whisper transcript (no extra dependencies): the
control phrases are matched against the normalized transcription text.
"""

import re
from dataclasses import dataclass
from typing import Optional

from xvoice2 import config


@dataclass
class WakeResult:
    """Outcome of evaluating one transcript against the wake-word gate.

    Attributes:
        should_inject: Whether the (possibly rewritten) text should be typed.
        text: The text to inject, or None when nothing should be typed. In
            "prefix" mode this has the prefix word(s) stripped off.
        state_changed: True if this utterance toggled the armed state.
        armed: The armed state after evaluation.
    """

    should_inject: bool
    text: Optional[str]
    state_changed: bool
    armed: bool


class WakeWordController:
    """Gates dictation behind spoken wake/sleep phrases.

    The controller is fed the raw Whisper transcript of each utterance and
    decides whether to arm/disarm dictation and whether the utterance should be
    injected into the focused window.
    """

    def __init__(
        self,
        mode: Optional[str] = None,
        wake_phrase: Optional[str] = None,
        sleep_phrase: Optional[str] = None,
        wake_prefix: Optional[str] = None,
        start_armed: Optional[bool] = None,
    ):
        """Initialize the controller.

        Args:
            mode: "session" or "prefix". Defaults to config.WAKE_MODE.
            wake_phrase: Phrase that arms dictation in session mode.
            sleep_phrase: Phrase that pauses dictation in session mode.
            wake_prefix: Prefix word(s) that precede each phrase in prefix mode.
            start_armed: Whether session mode begins already armed.
        """
        self.mode = (mode if mode is not None else getattr(config, "WAKE_MODE", "session")).lower()

        wake_phrase = wake_phrase if wake_phrase is not None else getattr(config, "WAKE_PHRASE", "")
        sleep_phrase = sleep_phrase if sleep_phrase is not None else getattr(config, "SLEEP_PHRASE", "")
        wake_prefix = wake_prefix if wake_prefix is not None else getattr(config, "WAKE_PREFIX", "")

        self.wake_phrase = self._normalize(wake_phrase)
        self.sleep_phrase = self._normalize(sleep_phrase)
        self.wake_prefix = self._normalize(wake_prefix)

        if start_armed is None:
            start_armed = getattr(config, "START_ARMED", False)
        # Prefix mode has no persistent armed state; each utterance is gated by
        # its own prefix, so "armed" only tracks session mode.
        self.armed = bool(start_armed) if self.mode == "session" else False

    @staticmethod
    def _normalize(text: str) -> str:
        """Lowercase, strip punctuation, and collapse whitespace for matching."""
        if not text:
            return ""
        cleaned = re.sub(r"[^\w\s]", " ", text.lower())
        return re.sub(r"\s+", " ", cleaned).strip()

    def evaluate(self, transcript: str) -> WakeResult:
        """Decide what to do with one transcribed utterance.

        Args:
            transcript: The raw Whisper transcription of the utterance.

        Returns:
            A WakeResult describing whether/what to inject and any state change.
        """
        if not transcript or not transcript.strip():
            return WakeResult(False, None, False, self.armed)

        if self.mode == "prefix":
            return self._evaluate_prefix(transcript)
        return self._evaluate_session(transcript)

    def _evaluate_session(self, transcript: str) -> WakeResult:
        """Session model: wake phrase arms, sleep phrase pauses."""
        norm = self._normalize(transcript)

        if not self.armed:
            if self.wake_phrase and self._contains(norm, self.wake_phrase):
                self.armed = True
                return WakeResult(False, None, True, True)
            return WakeResult(False, None, False, False)

        # Armed: a sleep phrase pauses dictation and is not itself typed.
        if self.sleep_phrase and self._contains(norm, self.sleep_phrase):
            self.armed = False
            return WakeResult(False, None, True, False)
        return WakeResult(True, transcript, False, True)

    def _evaluate_prefix(self, transcript: str) -> WakeResult:
        """Prefix model: only inject utterances that start with the prefix."""
        norm = self._normalize(transcript)
        if self.wake_prefix and self._starts_with_word(norm, self.wake_prefix):
            remainder = self._strip_prefix(transcript)
            if remainder:
                return WakeResult(True, remainder, False, False)
            # Just the prefix with nothing after it: nothing to inject.
            return WakeResult(False, None, False, False)
        return WakeResult(False, None, False, False)

    @staticmethod
    def _contains(haystack: str, needle: str) -> bool:
        """Whole-word containment check on already-normalized strings."""
        if not needle:
            return False
        return re.search(rf"(?:^| ){re.escape(needle)}(?: |$)", haystack) is not None

    @staticmethod
    def _starts_with_word(haystack: str, prefix: str) -> bool:
        """True if haystack begins with prefix on a word boundary."""
        if not prefix:
            return False
        return haystack == prefix or haystack.startswith(prefix + " ")

    def _strip_prefix(self, transcript: str) -> str:
        """Remove the leading prefix word(s) from the raw transcript.

        Works on the raw (un-normalized) transcript so capitalization and inner
        punctuation of the dictated content are preserved.
        """
        prefix_words = self.wake_prefix.split()
        words = transcript.split()
        i = 0
        for pw in prefix_words:
            if i < len(words) and self._normalize(words[i]) == pw:
                i += 1
            else:
                break
        return " ".join(words[i:]).strip()

    def status(self) -> str:
        """Human-readable current state for logging/UI."""
        if self.mode == "prefix":
            return "PREFIX"
        return "ARMED" if self.armed else "SLEEPING"
