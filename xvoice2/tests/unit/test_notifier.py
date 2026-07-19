"""
Unit tests for the notifier module.
"""

from unittest.mock import patch, MagicMock

from xvoice2 import notifier


class TestNotifier:
    """Tests for best-effort desktop notifications."""

    def test_notify_linux_uses_notify_send(self, mock_platform_linux):
        with patch("subprocess.run") as mock_run:
            result = notifier.notify("XVoice2", "hello")
        assert result is True
        args, _ = mock_run.call_args
        assert args[0][0] == "notify-send"
        assert args[0][1] == "XVoice2"
        assert args[0][2] == "hello"

    def test_notify_macos_uses_osascript(self, mock_platform_macos):
        with patch("subprocess.run") as mock_run:
            result = notifier.notify("XVoice2", "hello")
        assert result is True
        args, _ = mock_run.call_args
        assert args[0][0] == "osascript"
        # The AppleScript should carry the title and message.
        assert "XVoice2" in args[0][2]
        assert "hello" in args[0][2]

    def test_notify_missing_tool_is_swallowed(self, mock_platform_linux):
        """A missing notifier must not raise; it returns False."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = notifier.notify("XVoice2", "hello")
        assert result is False

    def test_notify_escapes_quotes_on_macos(self, mock_platform_macos):
        with patch("subprocess.run") as mock_run:
            notifier.notify('say "hi"', 'a "quote"')
        args, _ = mock_run.call_args
        # Embedded double quotes must be backslash-escaped for AppleScript.
        assert '\\"' in args[0][2]
