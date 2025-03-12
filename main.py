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
import requests
import datetime
from typing import NoReturn, Optional

import config
from mic_stream import MicrophoneStream
from transcriber import Transcriber
from text_injector import TextInjector
from formatter import TextFormatter

def debug_log(message: str, end: Optional[str] = None) -> None:
    """
    Print a debug message with a timestamp.
    
    Args:
        message: The message to print
        end: Optional ending character (default is newline)
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    if end is not None:
        print(f"[{timestamp}] {message}", end=end, flush=True)
    else:
        print(f"[{timestamp}] {message}")

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
        self.text_injector.set_mode(mode)  # Pass the mode to the text injector
        self.formatter = TextFormatter()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, sig, frame) -> NoReturn:
        """Handle termination signals for graceful shutdown."""
        print("\nShutting down voice dictation...")
        self.running = False
        # Exit for compatibility with tests
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
        
        # Check if the selected model is available
        if not self.transcriber.is_model_available():
            print(f"Error: Selected Whisper model '{self.transcriber.model}' not found")
            print(self.transcriber.get_model_installation_instructions())
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
            
        # Check for Ollama if local LLM is enabled
        if config.USE_LOCAL_LLM:
            try:
                response = requests.get("http://localhost:11434/api/version", timeout=3)
                if response.status_code != 200:
                    print(f"Error: Ollama server is not responding correctly (status {response.status_code})")
                    print("Make sure Ollama is running with: ollama serve")
                    return False
                    
                # Check if the requested model is available
                model_response = requests.get("http://localhost:11434/api/tags", timeout=3)
                if model_response.status_code == 200:
                    models = model_response.json().get("models", [])
                    model_names = [model["name"] for model in models]
                    if config.OLLAMA_MODEL not in model_names:
                        print(f"Error: Ollama model '{config.OLLAMA_MODEL}' not found")
                        print(f"Available models: {', '.join(model_names)}")
                        print(f"To install the model, run: ollama pull {config.OLLAMA_MODEL}")
                        return False
                else:
                    print("Warning: Could not verify Ollama model availability")
            except requests.RequestException as e:
                print(f"Error connecting to Ollama server: {e}")
                print("Make sure Ollama is installed and running with: ollama serve")
                return False
            
        print("All dependencies found!")
        return True
        
    def run(self) -> None:
        """Run the voice dictation application."""
        if not self.check_dependencies():
            return
            
        debug_log(f"Starting voice dictation in '{self.mode}' mode...")
        debug_log("Speak into your microphone. Press Ctrl+C to exit.")
        
        self.running = True
        
        try:
            with MicrophoneStream() as stream:
                # Main application loop
                for audio_file in stream.listen_continuous():
                    if not self.running:
                        debug_log("Stopping voice dictation loop...")
                        break
                        
                    # Skip if no audio file was generated
                    if not audio_file:
                        continue
                    
                    # Record the start time of audio processing
                    process_start_time = datetime.datetime.now()
                    
                    # Process the audio file
                    self._process_audio(audio_file)
                    
                    # Calculate and log the total processing time
                    process_end_time = datetime.datetime.now()
                    total_processing_time = (process_end_time - process_start_time).total_seconds()
                    debug_log(f"Total audio processing time: {total_processing_time:.3f}s")
                    
                    # Calculate time from speech end to text injection if available
                    if hasattr(stream, 'speech_end_time') and stream.speech_end_time:
                        speech_to_text_time = (process_end_time - stream.speech_end_time).total_seconds()
                        debug_log(f"Time from speech end to text injection: {speech_to_text_time:.3f}s")
                    
                    # Remove the temporary audio file
                    try:
                        os.remove(audio_file)
                    except OSError:
                        pass
        except KeyboardInterrupt:
            # Handle Ctrl+C gracefully
            debug_log("\nShutting down voice dictation...")
            self.running = False
        except Exception as e:
            debug_log(f"Unexpected error in main loop: {e}")
        finally:
            # Clean up resources
            debug_log("Cleaning up resources...")
            self.transcriber.cleanup()
            debug_log("Voice dictation application closed.")
    
    def _process_audio(self, audio_file: str) -> None:
        """
        Process a single audio file through the transcription pipeline.
        
        Args:
            audio_file: Path to the audio file to process
        """
        # Step 1: Transcribe the audio
        debug_log("Transcribing...", end="")
        transcription = self.transcriber.transcribe(audio_file)
        
        if not transcription:
            print(" No speech detected")
            debug_log("Check if whisper.cpp is working correctly. Try running:")
            debug_log("python3 test_transcribe.py")
            return
            
        print(f" Done")
        debug_log(f"Raw transcription from Whisper: '{transcription}'")
        
        # Step 2: Format the text if either LLM option is enabled
        if config.USE_LLM or config.USE_LOCAL_LLM:
            llm_type = "Ollama" if config.USE_LOCAL_LLM else "OpenAI"
            debug_log(f"LLM formatting IS enabled ({llm_type})")
            debug_log(f"Formatting with {llm_type}...", end="")
            formatted_text = self.formatter.format_text(transcription, self.mode)
            print(" Done")
            debug_log(f"Formatted text from {llm_type}: '{formatted_text}'")
        else:
            debug_log(f"LLM formatting is NOT enabled")
            formatted_text = transcription
            
        # Step 3: Inject the text into the active window
        debug_log("Injecting text...", end="")
        success = self.text_injector.inject_text(formatted_text)
        print(" Done" if success else " Failed")
        debug_log(f"Final text injected: '{formatted_text}'")


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
    
    # Initialize transcriber just for model listing
    available_models_for_choices = Transcriber().get_available_models()
    
    parser.add_argument(
        "--model",
        choices=available_models_for_choices if available_models_for_choices else ["tiny", "base", "small", "medium", "large"],
        help=f"Whisper model to use (default: {config.WHISPER_MODEL})"
    )
    
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List available installed models and exit"
    )
    
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Enable LLM formatting (requires API key in config.py)"
    )
    
    parser.add_argument(
        "--use-local-llm",
        action="store_true",
        help="Use local Ollama LLM for formatting instead of OpenAI"
    )
    
    parser.add_argument(
        "--ollama-model",
        help=f"Ollama model to use (default: {config.OLLAMA_MODEL})"
    )
    
    parser.add_argument(
        "--list-ollama-models",
        action="store_true",
        help="List available Ollama models and exit"
    )
    
    parser.add_argument(
        "--use-whisper-api",
        action="store_true",
        help="Use OpenAI Whisper API for transcription instead of local whisper.cpp"
    )
    
    parser.add_argument(
        "--no-persistent-whisper",
        action="store_true",
        help="Disable persistent whisper.cpp process (may be slower but uses less memory)"
    )
    
    args = parser.parse_args()
    
    # Initialize transcriber just for model checking
    transcriber = Transcriber()
    
    # List whisper models and exit if requested
    if args.list_models:
        available_models = transcriber.get_available_models()
        if available_models:
            print("Installed Whisper models:")
            for model in available_models:
                print(f"  - {model}")
        else:
            print("No Whisper models found. You need to install at least one model.")
            print("For installation instructions, run: python main.py --model base")
        return
    
    # List Ollama models and exit if requested
    if args.list_ollama_models:
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                if models:
                    print("Available Ollama models:")
                    for model in models:
                        print(f"  - {model['name']}")
                else:
                    print("No Ollama models found.")
                    print("To install models, run: ollama pull llama3")
            else:
                print("Failed to list Ollama models. Is Ollama running?")
                print("Start Ollama with 'ollama serve' and try again.")
        except Exception as e:
            print(f"Error connecting to Ollama: {e}")
            print("Make sure Ollama is installed and running on localhost:11434")
        return
    
    # Override config settings from command line
    if args.model:
        config.WHISPER_MODEL = args.model
        # Reinitialize with new model
        transcriber = Transcriber()
    
    # Whisper persistence setting
    if args.no_persistent_whisper:
        config.USE_PERSISTENT_WHISPER = False
        print("Persistent whisper.cpp process disabled")
        
    # LLM configuration
    if args.use_llm:
        config.USE_LLM = True
        # Print debug info about API key
        if config.LLM_API_KEY:
            print(f"Using OpenAI API key from {'environment variable' if os.environ.get('OPENAI_API_KEY') else 'config file'}")
        else:
            print("Warning: OpenAI API key not found. Set OPENAI_API_KEY environment variable or update config_local.py")
    
    if args.use_local_llm:
        config.USE_LOCAL_LLM = True
        # When using local LLM, disable OpenAI to avoid confusion
        if config.USE_LLM and not args.use_llm:
            config.USE_LLM = False
            
    if args.ollama_model:
        config.OLLAMA_MODEL = args.ollama_model
        
    # Whisper API configuration
    if args.use_whisper_api:
        config.USE_WHISPER_API = True
        # Print debug info about API key
        if config.WHISPER_API_KEY:
            print(f"Using Whisper API with {'environment variable' if os.environ.get('OPENAI_API_KEY') else 'config file'} API key")
        else:
            print("Warning: OpenAI API key not found. Set OPENAI_API_KEY environment variable or update config_local.py")
        
    # If we're in command mode, print a note about command execution
    if args.mode == "command":
        execution_status = "enabled" if config.EXECUTE_COMMANDS else "disabled"
        print(f"Command mode active. Command execution is {execution_status}.")
        print("Commands will be typed into the active terminal window" + 
              (" and automatically executed" if config.EXECUTE_COMMANDS else "") + ".")
    
    # Create and run the application
    app = VoiceDictationApp(mode=args.mode)
    app.run()


if __name__ == "__main__":
    main()
