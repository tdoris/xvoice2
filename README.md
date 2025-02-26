# Voice Dictation Application

A cross-platform voice dictation application that captures microphone input, transcribes speech to text, and injects the text into the active application. Supports both Linux and macOS.

## Features

- Real-time microphone input capture using PortAudio
- Speech-to-text transcription using whisper.cpp
- Text injection into the active application (using wtype on Linux, AppleScript on macOS)
- Optional grammar and punctuation correction using LLM API
- Modular architecture for easy extensions

## Requirements

### Common Requirements
- Python 3.7+
- PortAudio
- whisper.cpp

### Platform-Specific Requirements
- **Linux**: Wayland and wtype
- **macOS**: Accessibility permissions

## Installation

### Linux Setup

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

### macOS Setup

1. Install dependencies:

```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   
# Install required packages
brew install portaudio
brew install python
```

2. Install whisper.cpp:

```bash
git clone https://github.com/ggerganov/whisper.cpp.git
cd whisper.cpp
make
bash ./models/download-ggml-model.sh base
# Copy to a location in your PATH or update config.py
sudo cp build/bin/whisper-cli /opt/homebrew/bin/
```

3. **Critical: Grant Accessibility Permissions**
   - Go to System Preferences → Security & Privacy → Privacy → Accessibility
   - Add Terminal (or your application) to the list
   - This permission is required for text injection to work

4. Install Python dependencies:

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

The application will automatically detect your operating system and use the appropriate settings.

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
- `text_injector.py`: Text injection (wtype or AppleScript)
- `formatter.py`: Optional LLM integration
- `config.py`: Configuration settings

## Troubleshooting

If you encounter issues, please check the `troubleshooting.md` file for platform-specific solutions.

## License

MIT
