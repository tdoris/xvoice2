# XVoice 2.0 Test Suite

This directory contains tests for the XVoice 2.0 voice dictation application.

## Test Structure

- `unit/`: Unit tests for individual modules
  - `test_mic_stream.py`: Tests for audio capture functionality
  - `test_transcriber.py`: Tests for speech-to-text transcription
  - `test_text_injector.py`: Tests for text injection on different platforms
  - `test_formatter.py`: Tests for optional LLM text formatting
  
- `integration/`: Integration tests that verify component interactions
  - `test_end_to_end.py`: Tests for the complete audio processing pipeline

- `conftest.py`: Shared pytest fixtures used across tests

## Running Tests

```bash
# Install test dependencies
pip install pytest pytest-mock pytest-cov

# Run all tests
pytest

# Run with coverage report
pytest --cov=. tests/

# Run specific test file
pytest tests/unit/test_transcriber.py

# Run specific test function
pytest tests/unit/test_formatter.py::TestTextFormatter::test_format_text_success
```

## Testing Approach

- Unit tests use mocks to isolate functionality and prevent hardware dependencies
- Both Linux and macOS code paths are tested using platform detection mocks
- Integration tests verify that components work together correctly
- Tests run without requiring actual hardware or external services

## Adding New Tests

When adding new tests:

1. Follow the existing naming conventions
2. Use the appropriate fixtures from `conftest.py`
3. Mock external dependencies (hardware, APIs, etc.)
4. Test both success and failure cases
5. Test platform-specific behavior
6. Add docstrings explaining what is being tested