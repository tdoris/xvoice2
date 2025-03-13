# XVoice2

A cross-platform voice dictation application that captures microphone input, transcribes speech to text, and injects the text into the active application. Supports both Linux and macOS.

## Features

- Real-time microphone input capture using PortAudio
- Speech-to-text transcription using whisper.cpp
- Text injection into the active application (using wtype on Linux, AppleScript on macOS)
- Optional grammar and punctuation correction using LLM (supports both OpenAI API and local Ollama models)
- Modular architecture for easy extensions

## Requirements

### Common Requirements
- Python 3.7+
- PortAudio
- whisper.cpp
- (Optional) Ollama for local LLM support

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

# Standard CPU-only build
make

# OR build with CUDA support for NVIDIA GPUs (recommended for faster processing)
cmake -B build -DGGML_CUDA=1
cmake --build build -j --config Release

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

# Standard CPU-only build
make

# OR build with CUDA support if you have an NVIDIA GPU (recommended for faster processing)
cmake -B build -DGGML_CUDA=1
cmake --build build -j --config Release

# Download a model (e.g., base)
bash ./models/download-ggml-model.sh base
# Copy to a location in your PATH or update config.py
sudo cp build/bin/whisper-cli /opt/homebrew/bin/
```

3. **Critical: Grant Accessibility Permissions**
   - Go to System Preferences → Security & Privacy → Privacy → Accessibility
   - Add Terminal (or your application) to the list
   - This permission is required for text injection to work

4. (Optional) Install Ollama for local LLM support:

```bash
# Linux
curl -fsSL https://ollama.com/install.sh | sh

# macOS
brew install ollama

# Start the Ollama server
ollama serve

# In a new terminal, pull a model
ollama pull llama3
```

5. Install XVoice2:

```bash
# Clone the repository
git clone https://github.com/tdoris/xvoice2.git
cd xvoice2

# Install in development mode
pip install -e .

# Or install just the dependencies if you don't want to install the package
pip install -r requirements.txt
```

## Configuration

The package comes with sensible defaults, but you can customize settings by creating a `config_local.py` file:

```bash
# Copy the example configuration file
cp xvoice2/config_local.py.example xvoice2/config_local.py

# Edit with your preferred editor
nano xvoice2/config_local.py
```

Key settings to customize:
- Whisper model and executable path
- Audio capture parameters
- Text injection settings
- LLM configuration (OpenAI API or local Ollama)
- Dictation modes

The application will automatically detect your operating system and use the appropriate settings.

## Usage

Once installed, you can run XVoice2 as a command-line application:

```bash
# Basic usage
xvoice2

# With specific mode
xvoice2 --mode email

# With specific Whisper model
xvoice2 --model medium

# Enable OpenAI LLM formatting (requires API key in config_local.py)
xvoice2 --use-llm

# Use local Ollama for text formatting
xvoice2 --use-local-llm

# Specify which Ollama model to use
xvoice2 --use-local-llm --ollama-model llama3

# List available Whisper models
xvoice2 --list-models

# List available Ollama models
xvoice2 --list-ollama-models
```

You can also run it as a Python module if you prefer:

```bash
python -m xvoice2 --help
```

## Project Structure

The project is now structured as a proper Python package:

```
xvoice2/
├── xvoice2/                 # Main package code
│   ├── __init__.py          # Package initialization
│   ├── __main__.py          # Entry point for python -m xvoice2
│   ├── main.py              # Main application 
│   ├── mic_stream.py        # Microphone input handling
│   ├── transcriber.py       # Whisper.cpp integration
│   ├── text_injector.py     # Text injection (wtype or AppleScript)
│   ├── formatter.py         # Optional LLM integration
│   ├── config.py            # Configuration settings
│   ├── config_local.py      # Local config overrides (user-specific)
│   └── tests/               # Test modules
├── setup.py                 # Package setup script
├── pyproject.toml           # PEP 517/518 build system specification
├── MANIFEST.in              # Package data specification
└── README.md                # This file
```

## Troubleshooting

If you encounter issues, please check the `troubleshooting.md` file for platform-specific solutions.

## Development

To run tests:

```bash
# Install test dependencies
pip install -e .[test]

# Run all tests
pytest

# Run with coverage
pytest --cov=xvoice2 tests/
```

## License

MIT
