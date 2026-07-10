"""
Shared logging helper for the voice dictation application.

Provides a single timestamped ``debug_log`` implementation used across all
modules, replacing the copies that previously lived in each file.
"""

import datetime
from typing import Optional


def debug_log(message: str, end: Optional[str] = None) -> None:
    """
    Print a debug message with a millisecond-precision timestamp.

    Args:
        message: The message to print
        end: Optional ending character (default is newline)
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    if end is not None:
        print(f"[{timestamp}] {message}", end=end, flush=True)
    else:
        print(f"[{timestamp}] {message}")
