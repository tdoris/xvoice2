#!/usr/bin/env python3
"""
Voice Dictation Application - Main Entry Point

This application captures microphone input, performs speech-to-text transcription
using whisper.cpp, and injects the transcribed text into the active application.
"""

import os
import sys
import time
import signal
import argparse
import platform
from typing import NoReturn

import config
from mic_stream import MicrophoneStream
from transcriber import Transcriber
from text_injector import TextInjector
from formatter import TextFormatter

class VoiceDictationApp:
    """Main voice dictation application class."""
    
    def __init__(self, mode: str = config.DEFAULT_MODE):
        """
        Initialize the voice dictation application.
        
        Args:
            mode: Dictation mode (e.g., "general", "email", "command")
        """
        self.mode = mode
        self.running = False
        self.is_macos = platform.system() == "Darwin"
        
        # Initialize components
        self.transcriber = Transcriber()
        self.text_injector = TextInjector()
        self.formatter = TextFormatter()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, sig, frame) -> NoReturn:
        """Handle termination signals for graceful shutdown."""
        print("\nShutting down voice dictation...")
        self.running = False
        sys.exit(0)
        
    def check_dependencies(self) -> bool:
        """
        Check if all required dependencies are available.
        
        Returns:
            True if all dependencies are available, False otherwise
        """
        # Check for whisper.cpp
        if not self.transcriber.is_available():
            print(f"Error: whisper.cpp executable '{config.WHISPER_EXECUTABLE}' not found or not working")
            if self.is_macos:
                print("Make sure whisper.cpp is installed via Homebrew or in your PATH")
                print("  brew install whisper.cpp")
                print("  or download and build from: https://github.com/ggerganov/whisper.cpp")
            else:
                print("Please make sure whisper.cpp is installed and in your PATH")
            return False
            
        # Check for text injector (wtype on Linux, AppleScript on macOS)
        if not self.text_injector.is_available():
            if self.is_macos:
                print("Error: Text injection is unavailable.")
                print("Make sure Terminal has Accessibility permissions:")
                print("System Preferences → Security & Privacy → Privacy → Accessibility")
            else:
                print(f"Error: wtype executable '{config.TEXT_INJECTOR_EXECUTABLE}' not found or not working")
                print("Please make sure wtype is installed and in your PATH")
            return False
            
        return True
        
    def run(self) -> None:
        """Run the voice dictation application."""
        if not self.check_dependencies():
            return
            
        print(f"Starting voice dictation in '{self.mode}' mode...")
        print("Speak into your microphone. Press Ctrl+C to exit.")
        
        self.running = True
        
        with MicrophoneStream() as stream:
            # Main application loop
            for audio_file in stream.listen_continuous():
                if not self.running:
                    break
                    
                # Skip if no audio file was generated
                if not audio_file:
                    continue
                    
                # Process the audio file
                self._process_audio(audio_file)
                
                # Remove the temporary audio file
                try:
                    os.remove(audio_file)
                except OSError:
                    pass
    
    def _process_audio(self, audio_file: str) -> None:
        """
        Process a single audio file through the transcription pipeline.
        
        Args:
            audio_file: Path to the audio file to process
        """
        # Step 1: Transcribe the audio
        print("Transcribing...", end="", flush=True)
        transcription = self.transcriber.transcribe(audio_file)
        
        if not transcription:
            print(" No speech detected")
            return
            
        print(f" Done: '{transcription}'")
        
        # Step 2: Format the text if enabled
        if config.USE_LLM:
            print("Formatting with LLM...", end="", flush=True)
            formatted_text = self.formatter.format_text(transcription, self.mode)
            print(" Done")
        else:
            formatted_text = transcription
            
        # Step 3: Inject the text into the active window
        print("Injecting text...", end="", flush=True)
        success = self.text_injector.inject_text(formatted_text)
        print(" Done" if success else " Failed")


def main():
    """Parse command line arguments and start the application."""
    parser = argparse.ArgumentParser(
        description="Voice Dictation Application for " + 
                   ("macOS" if platform.system() == "Darwin" else "Linux")
    )
    
    parser.add_argument(
        "--mode", 
        choices=config.AVAILABLE_MODES,
        default=config.DEFAULT_MODE,
        help="Dictation mode (default: %(default)s)"
    )
    
    parser.add_argument(
        "--model",
        help=f"Whisper model to use (default: {config.WHISPER_MODEL})"
    )
    
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Enable LLM formatting (requires API key in config.py)"
    )
    
    args = parser.parse_args()
    
    # Override config settings from command line
    if args.model:
        config.WHISPER_MODEL = args.model
        
    if args.use_llm:
        config.USE_LLM = True
        
    # Create and run the application
    app = VoiceDictationApp(mode=args.mode)
    app.run()


if __name__ == "__main__":
    main()
