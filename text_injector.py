"""
Text injection module for various platforms.
Uses wtype for Wayland, xdotool for X11, and AppleScript on macOS.
"""

import subprocess
import shlex
import time
import platform
import os
from typing import Optional
import config

class TextInjector:
    """Handles injecting text into the active application using the platform-appropriate method."""
    
    def __init__(self):
        """Initialize the text injector with configuration settings."""
        self.typing_delay = config.TYPING_DELAY
        self.is_macos = platform.system() == "Darwin"
        self.current_mode = config.DEFAULT_MODE  # Track the current mode
        
        # Default to config value
        self.executable = config.TEXT_INJECTOR_EXECUTABLE
        
        # For Linux, detect if we're on X11 or Wayland
        if not self.is_macos:
            self.is_wayland = os.environ.get('XDG_SESSION_TYPE') == 'wayland'
            self.is_x11 = os.environ.get('XDG_SESSION_TYPE') == 'x11'
            
            # If we're on X11, use xdotool instead of wtype
            if self.is_x11:
                self.executable = "xdotool"
        
    def set_mode(self, mode: str) -> None:
        """
        Set the current dictation mode.
        
        Args:
            mode: The dictation mode to use (e.g., "general", "email", "command")
        """
        self.current_mode = mode
    
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
            
            # Check if we should execute the command in terminal mode
            # This is a special case for command mode where we want to execute the command
            if self.current_mode == "command" and hasattr(config, 'EXECUTE_COMMANDS') and config.EXECUTE_COMMANDS:
                print("[DEBUG] Command mode with execution enabled. Adding Return keystroke.")
                applescript = f'tell application "System Events" to keystroke "{escaped_text}"\n' + \
                             'tell application "System Events" to keystroke return'
            
            if self.typing_delay > 0:
                # Simulate typing with delay for each character
                for char in text:
                    char_escaped = char.replace('"', '\\"')
                    char_script = f'tell application "System Events" to keystroke "{char_escaped}"'
                    subprocess.run(["osascript", "-e", char_script], check=True)
                    time.sleep(self.typing_delay / 1000.0)  # Convert ms to seconds
                
                # Add Return keystroke if in command execution mode
                if self.current_mode == "command" and hasattr(config, 'EXECUTE_COMMANDS') and config.EXECUTE_COMMANDS:
                    subprocess.run(["osascript", "-e", 'tell application "System Events" to keystroke return'], check=True)
                
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
        Inject text using wtype (Wayland) or xdotool (X11) on Linux.
        
        Args:
            text: The text to inject
            
        Returns:
            True if text injection was successful, False otherwise
        """
        try:
            # Escape the text to ensure it works properly with the shell
            escaped_text = shlex.quote(text)
            
            # Check if we should execute the command in terminal mode
            # Only execute if we're in command mode AND the execute flag is enabled
            execute_command = (self.current_mode == "command" and 
                              hasattr(config, 'EXECUTE_COMMANDS') and 
                              config.EXECUTE_COMMANDS)
            
            # If we're on X11 with xdotool
            if self.is_x11:
                if self.typing_delay > 0:
                    # For X11 with typing delay, type each character individually
                    for char in text:
                        char_escaped = shlex.quote(char)
                        subprocess.run(f"{self.executable} type {char_escaped}", shell=True, check=True)
                        time.sleep(self.typing_delay / 1000.0)  # Convert ms to seconds
                    
                    # Add Enter keystroke if in command execution mode
                    if execute_command:
                        print("[DEBUG] Command mode with execution enabled. Adding Return keystroke.")
                        subprocess.run(f"{self.executable} key Return", shell=True, check=True)
                    
                    return True
                
                # Standard approach - type all at once with xdotool
                subprocess.run(f"{self.executable} type {escaped_text}", shell=True, check=True)
                
                # Add Enter keystroke if in command execution mode
                if execute_command:
                    print("[DEBUG] Command mode with execution enabled. Adding Return keystroke.")
                    subprocess.run(f"{self.executable} key Return", shell=True, check=True)
                
                return True
            
            # If we're on Wayland with wtype
            else:
                # If typing delay is specified, use a different approach to simulate typing
                if self.typing_delay > 0:
                    for char in text:
                        # Use wtype directly for each character
                        char_command = f"{self.executable} {shlex.quote(char)}"
                        subprocess.run(char_command, shell=True, check=True)
                        time.sleep(self.typing_delay / 1000.0)  # Convert ms to seconds
                    
                    # Add Enter keystroke if in command execution mode
                    if execute_command:
                        print("[DEBUG] Command mode with execution enabled. Adding Return keystroke.")
                        subprocess.run(f"{self.executable} -k Return", shell=True, check=True)
                    
                    return True
                    
                # Standard approach - pass text as command line argument to wtype
                command = f"{self.executable} {escaped_text}"
                subprocess.run(command, shell=True, check=True)
                
                # Add Enter keystroke if in command execution mode
                if execute_command:
                    print("[DEBUG] Command mode with execution enabled. Adding Return keystroke.")
                    subprocess.run(f"{self.executable} -k Return", shell=True, check=True)
                
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
        elif self.is_x11:
            try:
                # Try to run xdotool with --help to check if it's available
                subprocess.run(
                    [self.executable, "--help"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                return True
            except (subprocess.SubprocessError, FileNotFoundError):
                print(f"Error: xdotool not found. Please install it with: sudo apt-get install xdotool")
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
                print(f"Error: wtype not found. Please install it for Wayland text injection.")
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
        elif self.is_x11:
            try:
                # xdotool uses 'key' command for key events
                command = f"{self.executable} key {key}"
                subprocess.run(command, shell=True, check=True)
                return True
            except subprocess.SubprocessError as e:
                print(f"Error injecting keypress on Linux (X11): {e}")
                return False
        else:
            try:
                # wtype has special syntax for key events: -k for key
                command = f"{self.executable} -k {key}"
                subprocess.run(command, shell=True, check=True)
                return True
            except subprocess.SubprocessError as e:
                print(f"Error injecting keypress on Linux (Wayland): {e}")
                return False
