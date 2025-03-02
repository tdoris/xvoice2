"""
Configuration settings for the voice dictation application.
"""

# Whisper model settings
WHISPER_MODEL = "small"  # Options: "tiny", "base", "small", "medium", "large"
WHISPER_EXECUTABLE = "/Users/tomdoris/whisper.cpp/build/bin/whisper-cli"  # Path to whisper.cpp executable

# PortAudio settings
SAMPLE_RATE = 16000  # Sample rate in Hz
FRAMES_PER_BUFFER = 1024
CHANNELS = 1  # Mono
FORMAT = "int16"  # Audio format

# Audio processing settings
CHUNK_DURATION = 2  # Duration of audio chunks in seconds
MAX_SENTENCE_DURATION = 20  # Maximum duration in seconds for a single sentence
SILENCE_THRESHOLD = 1000  # Threshold to detect silence (adjusted to match audio scale)
SILENCE_DURATION = 1.5  # Duration of silence to trigger end of speech in seconds

# Text injection settings
WTYPE_EXECUTABLE = "wtype"  # Path to wtype executable
TYPING_DELAY = 0  # Delay between characters in milliseconds (0 for no delay)

# LLM API settings
USE_LLM = False  # Enable/disable LLM formatting
LLM_API_KEY = ""  # Your API key
LLM_MODEL = "gpt-3.5-turbo"  # Model to use for formatting
LLM_PROMPT = "Fix grammar and punctuation only in the following text, maintain original meaning and style: "

# Dictation mode settings
DEFAULT_MODE = "general"  # Default dictation mode
AVAILABLE_MODES = ["general", "command", "email"]  # Available modes
