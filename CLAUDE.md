# XVoice 2.0 Development Guidelines

## Common Commands
- **Run Application**: `python main.py`
- **Run with Options**: `python main.py --mode email --use-llm`
- **Install Dependencies**: `pip install -r requirements.txt`
- **Install Test Dependencies**: `pip install pytest pytest-mock pytest-cov`
- **Run Tests**: `pytest`
- **Run Tests with Coverage**: `pytest --cov=. tests/`
- **Run Specific Test File**: `pytest tests/unit/test_transcriber.py`
- **Run Specific Test Function**: `pytest tests/unit/test_transcriber.py::test_transcribe`
- **Check Mic Devices**: `python -c "import pyaudio; p = pyaudio.PyAudio(); [print(p.get_device_info_by_index(i)) for i in range(p.get_host_api_info_by_index(0).get('deviceCount'))]"`

## Code Style Guidelines
- **Imports**: Standard library first, then third-party, then local modules
- **Type Hints**: Use mypy-compatible type hints for all function parameters and return values
- **Docstrings**: Google style docstrings with Args/Returns sections
- **Error Handling**: Use try/except with specific exception types, provide helpful error messages
- **Variable Naming**: snake_case for variables/functions, PascalCase for classes
- **Line Length**: Maximum 100 characters
- **Platform Detection**: Use `platform.system() == "Darwin"` for macOS checks
- **Subprocess Calls**: Always use `check=True` and handle `subprocess.CalledProcessError`

## Testing Guidelines
- Use pytest for all tests
- Create mocks for external dependencies (PyAudio, subprocess calls, APIs)
- Organize tests in unit/ and integration/ folders
- Test both Linux and macOS code paths using pytest parametrization
- Aim for at least 80% code coverage
- Write test docstrings explaining what is being tested

## Cross-Platform Development
- Test changes on both Linux (Wayland) and macOS
- Use OS-specific conditional logic for platform differences
- Keep platform-specific code isolated to appropriate modules
- Check file paths compatibility for both platforms