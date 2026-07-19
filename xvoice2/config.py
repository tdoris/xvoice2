"""
Configuration settings for the voice dictation application.

This file contains default configuration values. Users can override these 
by creating a config_local.py file with their own settings.
"""

import os
import platform
import importlib.util
import sys

# Detect operating system
IS_MACOS = platform.system() == "Darwin"

# --- Transcription engine ---
# "whisper"  = whisper.cpp / OpenAI Whisper API (the default).
# "parakeet" = NVIDIA Parakeet via onnx-asr (fully local, ONNX Runtime).
# Parakeet produces punctuated, capitalized text and, being a transducer, does
# not hallucinate stock phrases ("thank you") on silence/noise the way Whisper
# does. Requires: pip install onnx-asr onnxruntime huggingface_hub
#   (or: pip install -e .[parakeet])
TRANSCRIPTION_ENGINE = "whisper"
# onnx-asr model id used when TRANSCRIPTION_ENGINE == "parakeet".
# "nemo-parakeet-tdt-0.6b-v2" is English; "-v3" is multilingual (~25 languages).
PARAKEET_MODEL = "nemo-parakeet-tdt-0.6b-v2"

# Whisper model settings
WHISPER_MODEL = "base"  # Options: "tiny", "base", "small", "medium", "large"

# Whisper installation root path.
# Neutral default so a fresh clone works out of the box: honor the WHISPER_ROOT
# environment variable if set, otherwise fall back to ~/whisper.cpp. Override in
# config_local.py for machine-specific installs.
WHISPER_ROOT = os.environ.get("WHISPER_ROOT", os.path.expanduser("~/whisper.cpp"))

# Whisper paths relative to root
WHISPER_EXECUTABLE = os.path.join(WHISPER_ROOT, "build/bin/whisper-cli")
WHISPER_SERVER_EXECUTABLE = os.path.join(WHISPER_ROOT, "build/bin/whisper-server")
WHISPER_MODELS_DIR = os.path.join(WHISPER_ROOT, "models")

# Text injection settings based on OS
if IS_MACOS:
    # For Mac we use osascript for text injection
    TEXT_INJECTOR_TYPE = "applescript"
    TEXT_INJECTOR_EXECUTABLE = "osascript"
else:
    # Default to wtype (Wayland), but we'll detect X11 in text_injector.py
    TEXT_INJECTOR_TYPE = "wtype"
    TEXT_INJECTOR_EXECUTABLE = "wtype"

# Whisper API settings
USE_WHISPER_API = False  # Enable/disable OpenAI Whisper API for transcription
WHISPER_API_KEY = os.environ.get("OPENAI_API_KEY", "")  # Reuse OpenAI key or set separately
WHISPER_API_MODEL = "whisper-1"  # OpenAI Whisper model to use
WHISPER_API_LANGUAGE = "en"  # Language hint for API (optional)
WHISPER_API_TIMEOUT = 30  # Timeout (seconds) for Whisper API audio uploads

# PortAudio settings
SAMPLE_RATE = 16000  # Sample rate in Hz
FRAMES_PER_BUFFER = 1024
CHANNELS = 1  # Mono
FORMAT = "int16"  # Audio format

# Audio processing settings
CHUNK_DURATION = 2  # Duration of audio chunks in seconds
MAX_SENTENCE_DURATION = 20  # Maximum duration in seconds for a single sentence
SILENCE_THRESHOLD = 1000  # Silence threshold on the int16 amplitude scale (fallback when auto-calibration is disabled)
SILENCE_DURATION = 1.0  # Duration of silence to trigger end of speech in seconds
THRESHOLD_ADJUSTMENT_FACTOR = 1.0  # Multiplier for auto-calibrated threshold (>1 = less sensitive, <1 = more sensitive)
CALIBRATION_ENABLED = True  # Whether to use auto-calibration for silence detection
# --- Non-speech clip rejection (VAD gating) ---
# These decide whether a captured clip is real speech BEFORE it is sent to
# Whisper. Whisper hallucinates stock phrases ("thank you") on near-silent
# clips, so a stricter gate here is the cheapest way to cut those down.
# Tighten to reduce hallucinations; loosen if genuine short/quiet utterances
# (including the wake word) get rejected. Watch the "Rejected/Accepted ... clip"
# debug lines to see which criterion is firing when you tune.
#
# Minimum fraction of frames that must cross the threshold for a captured clip
# to count as real speech (rejects stray clicks/pops without discarding genuine
# utterances that contain gaps/trailing silence). Lower = more permissive.
MIN_VOICE_ACTIVITY_RATIO = 0.10
# Minimum seconds of ACTUAL voiced audio (active_ratio x clip length). A brief
# blip in a sea of silence has a high ratio over a short window but very little
# real voiced audio, so this catches the clips Whisper turns into "thank you".
MIN_SPEECH_DURATION = 0.25
# The clip's peak amplitude must exceed the silence threshold by at least this
# factor. Rejects quiet ambient noise that barely crosses the threshold. Raise
# toward 1.5 if quiet room noise still triggers; lower toward 1.0 if a soft
# speaker gets cut off.
SPEECH_MARGIN_FACTOR = 1.2
# Require sustained VOICED audio (vowels) in a clip. This is what separates
# speech from keyboard clicks and other impulsive noise: voiced speech has a low
# zero-crossing rate (ZCR), while key clicks are broadband transients with a
# high ZCR. Keyboard clatter is loud and long enough to pass the gates above but
# contains almost no voiced audio, so this is the key defense against spurious
# transcriptions while you type. Disable (set False) if you dictate in a whisper
# (whispered speech is unvoiced) or this rejects genuine speech.
REQUIRE_VOICED = True
# A frame counts as "voiced" if its zero-crossing rate is below this. Voiced
# speech typically sits around 0.02-0.10; key clicks / fricatives run higher.
MAX_VOICED_ZCR = 0.20
# Minimum seconds of voiced audio for a clip to count as speech. A real word has
# at least one vowel (well over this); keyboard clatter has ~none.
MIN_VOICED_DURATION = 0.12

# Text injection settings
# Append a trailing space after each dictated utterance so consecutive sentences
# don't run together ("First.Second"). Not applied in command mode.
APPEND_TRAILING_SPACE = True
TYPING_DELAY = 0  # Delay between characters in milliseconds (0 for no delay)
# Delay (seconds) before the first keystroke on macOS. Gives the target app time
# to be ready so the first character/word isn't dropped by System Events. Set to
# 0 to disable.
INJECTION_START_DELAY = 0.15

# LLM API settings
USE_LLM = False  # Enable/disable LLM formatting
# Check environment variable first, then fall back to empty string
LLM_API_KEY = os.environ.get("OPENAI_API_KEY", "")  # Get API key from environment or use empty string
LLM_MODEL = "gpt-3.5-turbo"  # Model to use for formatting
LLM_PROMPT = "Fix grammar and punctuation only in the following text, maintain original meaning and style: "
# Timeout (seconds) for LLM formatting requests (OpenAI and Ollama). Needs to be
# generous enough for larger models / slower networks to avoid silent fallbacks.
LLM_REQUEST_TIMEOUT = 30

# Local LLM settings (Ollama)
USE_LOCAL_LLM = False  # Enable/disable local LLM formatting
OLLAMA_MODEL = "llama3"  # Default Ollama model to use
OLLAMA_URL = "http://localhost:11434/api/generate"  # Ollama API URL

# Performance settings
USE_PERSISTENT_WHISPER = False  # Keep whisper.cpp loaded for faster transcription

# Whisper hallucination filtering
#
# On (near-)silent or non-speech audio, Whisper reliably emits stock phrases
# from its training data (it was trained heavily on video captions): "thank
# you", "thanks for watching", "you", etc. With an always-on mic these get typed
# during pauses while dictation is armed. When enabled, any utterance whose
# ENTIRE text (after normalization) matches one of these phrases is dropped.
# Only whole-utterance matches are filtered, so "thank you for the help" is still
# typed normally. Edit HALLUCINATION_PHRASES to taste.
FILTER_HALLUCINATIONS = True
HALLUCINATION_PHRASES = [
    "thank you",
    "thank you very much",
    "thanks for watching",
    "thanks for watching!",
    "thank you for watching",
    "thanks",
    "you",
    "bye",
    "please subscribe",
    "subscribe",
]

# Wake-word activation settings
#
# XVoice2 keeps the mic always on. Wake-word gating stops it from typing
# everything you say: text is only injected while dictation is "armed". This
# also means there is NO global hotkey, which is exactly what makes XVoice2
# usable over remote desktop sessions (RDP/VNC) where a client would otherwise
# swallow the hotkey. See wake_word.py for details.
WAKE_WORD_ENABLED = True  # Gate dictation behind a wake word (set False for the old always-typing behavior)
# Interaction model:
#   "session" = say WAKE_PHRASE to start typing, SLEEP_PHRASE to pause.
#   "prefix"  = say WAKE_PREFIX immediately before each phrase you want typed.
WAKE_MODE = "session"
WAKE_PHRASE = "start dictation"  # Arms dictation in session mode
SLEEP_PHRASE = "stop dictation"  # Pauses dictation in session mode
WAKE_PREFIX = "computer"  # Prefix word(s) before each phrase in prefix mode
START_ARMED = False  # In session mode, begin already armed (skip the initial wake phrase)
WAKE_NOTIFICATIONS = True  # Desktop notification on arm/pause state changes

# Dictation mode settings
DEFAULT_MODE = "general"  # Default dictation mode
AVAILABLE_MODES = ["general", "command", "email"]

# In command mode, should the Enter key be pressed after injecting text?
# This will execute the command in a terminal.
#
# SAFETY: command mode converts speech into a shell command via an LLM and types
# it into the active window. Auto-pressing Enter would execute whatever the LLM
# produced (including transcription errors / hallucinations) with no review, so
# this defaults to False: the command is typed but NOT executed until you press
# Enter yourself. Set to True only if you understand the risk.
EXECUTE_COMMANDS = False  # Set to True to automatically execute typed commands

# When EXECUTE_COMMANDS is True, require an interactive confirmation in the
# XVoice terminal before the command is injected/executed.
CONFIRM_COMMANDS = True

# Mode-specific LLM prompts
MODE_PROMPTS = {
    "general": LLM_PROMPT,  # Use general prompt defined above
    "email": "Format the following text as professional email content with proper grammar and punctuation:",
    "command": None  # This is handled dynamically in the formatter to be platform-specific
}

# Load local config overrides if present.
#
# Resolve the file by absolute path rather than by module name so it loads
# reliably regardless of the current working directory / sys.path. The
# canonical location is config_local.py next to this file (see
# config_local.py.example); a repo-root config_local.py is also honored for
# backward compatibility. The first one found wins.
def _load_local_config() -> None:
    # A packaged (frozen) app must never load a bundled developer config_local.py
    # — it hardcodes the developer's machine paths. The frozen GUI sets its own
    # defaults instead.
    if getattr(sys, "frozen", False):
        return
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "config_local.py"),               # xvoice2/config_local.py (canonical)
        os.path.join(here, os.pardir, "config_local.py"),    # repo-root/config_local.py (legacy)
    ]
    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            spec = importlib.util.spec_from_file_location("xvoice2._config_local", path)
            local = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(local)

            current_module = sys.modules[__name__]
            for attr in dir(local):
                if not attr.startswith("_"):
                    setattr(current_module, attr, getattr(local, attr))

            print(f"Loaded configuration from {os.path.normpath(path)}")
        except Exception as e:
            print(f"Warning: Could not load {os.path.normpath(path)}: {e}")
            print("Using default configuration")
        return


_load_local_config()
