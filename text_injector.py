"""
Text injection module for various platforms.
Uses wtype for Wayland on Linux and AppleScript on macOS.
"""

import subprocess
import shlex
import time
import platform
from typing import Optional
import config

class TextInjector:
    """Handles injecting text into the active application using the platform-appropriate method."""
    
    def __init__(self):
        """Initialize the text injector with configuration settings."""
        self.executable = config.TEXT_INJECTOR_EXECUTABLE
        self.typing_delay = config.TYPING_DELAY
        self.is_macos = platform.system() == "Darwin"
        
    def inject_text(self, text: str) -> bool:
        """
        Inject text into the currently active window using the appropriate method for this platform.
        
        Args:
            text: The text to inject
            
        Returns:
            True if text injection was successful, False otherwise
        """
        if not text:
            return True  # Nothing to inject
        
        if self.is_macos:
            return self._inject_text_macos(text)
        else:
            return self._inject_text_linux(text)
    
    def _inject_text_macos(self, text: str) -> bool:
        """
        Inject text using AppleScript on macOS.
        
        Args:
            text: The text to inject
            
        Returns:
            True if text injection was successful, False otherwise
        """
        try:
            # Escape the text for AppleScript
            escaped_text = text.replace('"', '\\"')
            
            # Use AppleScript to type the text
            applescript = f'tell application "System Events" to keystroke "{escaped_text}"'
            
            if self.typing_delay > 0:
                # Simulate typing with delay for each character
                for char in text:
                    char_escaped = char.replace('"', '\\"')
                    char_script = f'tell application "System Events" to keystroke "{char_escaped}"'
                    subprocess.run(["osascript", "-e", char_script], check=True)
                    time.sleep(self.typing_delay / 1000.0)  # Convert ms to seconds
                return True
            else:
                # Type all at once
                subprocess.run(["osascript", "-e", applescript], check=True)
                return True
                
        except subprocess.SubprocessError as e:
            print(f"Error injecting text on macOS: {e}")
            return False
    
    def _inject_text_linux(self, text: str) -> bool:
        """
        Inject text using wtype on Linux.
        
        Args:
            text: The text to inject
            
        Returns:
            True if text injection was successful, False otherwise
        """
        try:
            # Escape the text to ensure it works properly with the shell
            escaped_text = shlex.quote(text)
            
            # Use echo to pipe the text into wtype
            command = f"echo {escaped_text} | {self.executable}"
            
            # If typing delay is specified, use a different approach to simulate typing
            if self.typing_delay > 0:
                for char in text:
                    # Use wtype directly for each character
                    char_command = f"{self.executable} {shlex.quote(char)}"
                    subprocess.run(char_command, shell=True, check=True)
                    time.sleep(self.typing_delay / 1000.0)  # Convert ms to seconds
                return True
                
            # Standard approach - pipe the whole text at once
            subprocess.run(command, shell=True, check=True)
            return True
            
        except subprocess.SubprocessError as e:
            print(f"Error injecting text on Linux: {e}")
            return False
            
    def is_available(self) -> bool:
        """
        Check if the text injection tool is available and working.
        
        Returns:
            True if the tool is available, False otherwise
        """
        if self.is_macos:
            try:
                # Check if we can run a simple AppleScript command
                subprocess.run(
                    ["osascript", "-e", 'return "test"'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True
                )
                return True
            except (subprocess.SubprocessError, FileNotFoundError):
                return False
        else:
            try:
                # Try to run wtype with --help to check if it's available
                subprocess.run(
                    [self.executable, "--help"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                return True
            except (subprocess.SubprocessError, FileNotFoundError):
                return False
    
    def inject_keypress(self, key: str) -> bool:
        """
        Inject a special keypress using the appropriate method.
        
        Args:
            key: Key to press (e.g., "Return", "BackSpace", "Tab")
            
        Returns:
            True if keypress injection was successful, False otherwise
        """
        if self.is_macos:
            try:
                # Convert key name to macOS AppleScript key code if needed
                key_map = {
                    "Return": "return",
                    "BackSpace": "delete",
                    "Tab": "tab",
                    "space": "space",
                    "Escape": "escape",
                    # Add more key mappings as needed
                }
                
                applescript_key = key_map.get(key, key)
                applescript = f'tell application "System Events" to key code {{{applescript_key}}}'
                
                subprocess.run(["osascript", "-e", applescript], check=True)
                return True
            except subprocess.SubprocessError as e:
                print(f"Error injecting keypress on macOS: {e}")
                return False
        else:
            try:
                # wtype has special syntax for key events: -k for key
                command = f"{self.executable} -k {key}"
                subprocess.run(command, shell=True, check=True)
                return True
            except subprocess.SubprocessError as e:
                print(f"Error injecting keypress on Linux: {e}")
                return False
