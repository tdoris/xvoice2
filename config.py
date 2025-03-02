"""
Configuration settings for the voice dictation application.
"""

import os
import platform

# Detect operating system
IS_MACOS = platform.system() == "Darwin"

# Whisper model settings
WHISPER_MODEL = "base"  # Options: "tiny", "base", "small", "medium", "large"

# Set appropriate paths based on OS
if IS_MACOS:
    # macOS typically uses Homebrew paths
    WHISPER_EXECUTABLE = "/Users/tomdoris/whisper.cpp/build/bin/whisper-cli" 
    # For Mac we use osascript for text injection
    TEXT_INJECTOR_TYPE = "applescript"
    TEXT_INJECTOR_EXECUTABLE = "osascript"
else:
    # Linux paths
    WHISPER_EXECUTABLE = "/home/tdoris/repos/whisper.cpp/build/bin/whisper-cli"
    TEXT_INJECTOR_TYPE = "wtype"
    TEXT_INJECTOR_EXECUTABLE = "wtype"

# PortAudio settings
SAMPLE_RATE = 16000  # Sample rate in Hz
FRAMES_PER_BUFFER = 1024
CHANNELS = 1  # Mono
FORMAT = "int16"  # Audio format

# Audio processing settings
CHUNK_DURATION = 2  # Duration of audio chunks in seconds
SILENCE_THRESHOLD = 0.03  # Threshold to detect silence
SILENCE_DURATION = 1.0  # Duration of silence to trigger end of speech in seconds

# Text injection settings
TYPING_DELAY = 0  # Delay between characters in milliseconds (0 for no delay)

# LLM API settings
USE_LLM = False  # Enable/disable LLM formatting
# Check environment variable first, then fall back to empty string
LLM_API_KEY = os.environ.get("OPENAI_API_KEY", "")  # Get API key from environment or use empty string
LLM_MODEL = "gpt-3.5-turbo"  # Model to use for formatting
LLM_PROMPT = "Fix grammar and punctuation only in the following text, maintain original meaning and style: "

# Local LLM settings (Ollama)
USE_LOCAL_LLM = False  # Enable/disable local LLM formatting
OLLAMA_MODEL = "llama3"  # Default Ollama model to use
OLLAMA_URL = "http://localhost:11434/api/generate"  # Ollama API URL

# Dictation mode settings
DEFAULT_MODE = "general"  # Default dictation mode
AVAILABLE_MODES = ["general", "command", "email"]
