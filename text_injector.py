"""
Text injection module using wtype for Wayland.
"""

import subprocess
import shlex
import time
from typing import Optional
import config

class TextInjector:
    """Handles injecting text into the active application using wtype."""
    
    def __init__(self):
        """Initialize the text injector with configuration settings."""
        self.wtype_executable = config.WTYPE_EXECUTABLE
        self.typing_delay = config.TYPING_DELAY
        
    def inject_text(self, text: str) -> bool:
        """
        Inject text into the currently active window using wtype.
        
        Args:
            text: The text to inject
            
        Returns:
            True if text injection was successful, False otherwise
        """
        if not text:
            return True  # Nothing to inject
            
        try:
            # Escape the text to ensure it works properly with the shell
            escaped_text = shlex.quote(text)
            
            # Use echo to pipe the text into wtype
            command = f"echo {escaped_text} | {self.wtype_executable}"
            
            # If typing delay is specified, use a different approach to simulate typing
            if self.typing_delay > 0:
                for char in text:
                    # Use wtype directly for each character
                    char_command = f"{self.wtype_executable} {shlex.quote(char)}"
                    subprocess.run(char_command, shell=True, check=True)
                    time.sleep(self.typing_delay / 1000.0)  # Convert ms to seconds
                return True
                
            # Standard approach - pipe the whole text at once
            subprocess.run(command, shell=True, check=True)
            return True
            
        except subprocess.SubprocessError as e:
            print(f"Error injecting text: {e}")
            return False
            
    def is_available(self) -> bool:
        """
        Check if wtype is available and working.
        
        Returns:
            True if wtype is available, False otherwise
        """
        try:
            # Try to run wtype with --help or -h to check if it's available
            subprocess.run(
                [self.wtype_executable, "--help"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    def inject_keypress(self, key: str) -> bool:
        """
        Inject a special keypress using wtype.
        
        Args:
            key: Key to press (e.g., "Return", "BackSpace", "Tab")
            
        Returns:
            True if keypress injection was successful, False otherwise
        """
        try:
            # wtype has special syntax for key events: -k for key
            command = f"{self.wtype_executable} -k {key}"
            subprocess.run(command, shell=True, check=True)
            return True
        except subprocess.SubprocessError as e:
            print(f"Error injecting keypress: {e}")
            return False
