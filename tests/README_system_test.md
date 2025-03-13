# XVoice2 System Test

This directory contains a system test script that helps validate the end-to-end functionality of XVoice2 across different configurations.

## Prerequisites

Before running the system test, ensure:

1. XVoice2 is properly installed
2. Your microphone is connected and working
3. The required test dependencies are installed:
   ```
   pip install -r requirements.txt
   ```
4. You have a text editor open to verify text injection
5. For command mode tests, you have a terminal window open and active

## Running the System Test

To run the system test:

```bash
# Activate your virtual environment
source venv/bin/activate

# Run the system test
python tests/system_test.py
```

You can also specify a custom log file path:

```bash
python tests/system_test.py --log-file my_test_results.log
```

## What the Test Does

The system test:

1. Runs XVoice2 with various command-line configurations
2. Captures detailed system information for each test
3. Guides you through speaking test phrases
4. Logs all application output for analysis
5. Records test results based on your feedback
6. Generates a summary of test results

## Test Scenarios

The test includes the following scenarios:

1. Basic operation with default settings
2. Email mode with LLM formatting (requires OpenAI API key)
3. Command mode with LLM formatting for executing shell commands (requires OpenAI API key)
4. Command mode with local LLM formatting (if Ollama is available)
5. Tests with different Whisper models (if multiple models are available)
6. General mode with local LLM formatting via Ollama (if available)
7. Email mode with local LLM formatting via Ollama (if available)

**Note:** Both email mode and command mode require either `--use-llm` (OpenAI) or `--use-local-llm` (Ollama) to properly format the text. Without these flags, only basic transcription will be performed without specialized formatting.

## Analyzing Results

After running the tests, a log file is generated with:

- Detailed system information
- Command-line arguments used
- Application output
- Test results and user feedback

This log file can be helpful for:
- Troubleshooting issues
- Comparing behavior across different environments
- Verifying that updates haven't broken existing functionality