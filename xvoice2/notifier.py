"""
Best-effort desktop notifications, cross-platform.

Used to surface XVoice2's dictation state (armed/paused) outside the terminal,
which matters for hands-free use where the user isn't watching the console.
Uses `notify-send` on Linux and `osascript` on macOS. All failures are
swallowed: a missing notifier must never interrupt dictation.
"""

import platform
import subprocess

from xvoice2.logging_util import debug_log


def notify(title: str, message: str) -> bool:
    """Show a desktop notification. Best-effort; never raises.

    Args:
        title: Notification title.
        message: Notification body.

    Returns:
        True if the notification command was dispatched, False otherwise.
    """
    is_macos = platform.system() == "Darwin"
    try:
        if is_macos:
            safe_title = title.replace('"', '\\"')
            safe_message = message.replace('"', '\\"')
            script = f'display notification "{safe_message}" with title "{safe_title}"'
            subprocess.run(
                ["osascript", "-e", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            subprocess.run(
                ["notify-send", title, message],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        return True
    except (FileNotFoundError, OSError, subprocess.SubprocessError) as e:
        debug_log(f"Desktop notification unavailable: {e}")
        return False
