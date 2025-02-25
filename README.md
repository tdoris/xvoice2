# Linux Voice Dictation Application

A self-contained Linux voice dictation application that captures microphone input, transcribes speech to text, and injects the text into the active application.

## Features

- Real-time microphone input capture using PortAudio
- Speech-to-text transcription using whisper.cpp
- Text injection into the active application using wtype (Wayland)
- Optional grammar and punctuation correction using LLM API
- Modular architecture for easy extensions

## Requirements

- Wayland-based Linux system
- PortAudio
- whisper.cpp
- wtype
- Python 3.7+

## Installation

1. Install system dependencies:

```bash
# Debian/Ubuntu
sudo apt-get install portaudio19-dev python3-dev wtype

# Arch Linux
sudo pacman -S portaudio python wtype
```

2. Install whisper.cpp:

```bash
git clone https://github.com/ggerganov/whisper.cpp.git
cd whisper.cpp
make
# Download a model (e.g., base)
bash ./models/download-ggml-model.sh base
# Add whisper.cpp to your PATH or adjust the path in config.py
```

3. Install Python dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

Edit `config.py` to customize settings:

- Whisper model and executable path
- Audio capture parameters
- Text injection settings
- LLM API configuration (optional)
- Dictation modes

## Usage

```bash
# Basic usage
python main.py

# With specific mode
python main.py --mode email

# With specific Whisper model
python main.py --model medium

# Enable LLM formatting
python main.py --use-llm
```

## Project Structure

- `main.py`: Application entry point
- `mic_stream.py`: Microphone input handling
- `transcriber.py`: Whisper.cpp integration
- `text_injector.py`: Text injection via wtype
- `formatter.py`: Optional LLM integration
- `config.py`: Configuration settings

## Extending the Application

The modular architecture allows for easy extensions:

1. Add new dictation modes in `config.py`
2. Implement mode-specific processing in `formatter.py`
3. Add new command-line options in `main.py`

## License

MIT
