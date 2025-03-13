#!/usr/bin/env python3
"""
System Test for XVoice2

This script performs end-to-end testing of the XVoice2 application with
various command line configurations. It guides the user through a series
of test scenarios, logging all results for later analysis.

Note: XVoice2 is only supported on Linux and macOS platforms.

Usage:
    python system_test.py [--log-file LOG_FILE]
"""

import os
import sys
import time
import platform
import argparse
import subprocess
import logging
import datetime
import psutil
import pkg_resources

# Add the parent directory to sys.path to allow direct import of the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import xvoice2 configuration for checking available models
from xvoice2 import config
from xvoice2.transcriber import Transcriber

def setup_logging(log_file=None):
    """Configure logging to both console and file."""
    if log_file is None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = f"system_test_{timestamp}.log"
    
    # Create a logger
    logger = logging.getLogger("xvoice2_system_test")
    logger.setLevel(logging.DEBUG)
    
    # Create handlers
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Create formatters
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_formatter = logging.Formatter('%(message)s')
    
    # Add formatters to handlers
    file_handler.setFormatter(file_formatter)
    console_handler.setFormatter(console_formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger, log_file

def get_system_info():
    """Gather detailed system information."""
    info = {
        "os": platform.system(),
        "os_version": platform.version(),
        "os_release": platform.release(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "memory": f"{psutil.virtual_memory().total / (1024**3):.2f} GB",
        "cpu_count": psutil.cpu_count(logical=False),
        "logical_cpu_count": psutil.cpu_count(logical=True),
    }
    
    # Add package versions
    packages = ["pyaudio", "requests", "openai"]
    for package in packages:
        try:
            info[f"{package}_version"] = pkg_resources.get_distribution(package).version
        except pkg_resources.DistributionNotFound:
            info[f"{package}_version"] = "Not installed"
    
    return info

def wait_for_keypress(message="Press Enter to continue..."):
    """Wait for the user to press Enter."""
    input(message)

def run_test(logger, test_name, command, test_phrase):
    """Run a single test case."""
    # Log header with system information
    logger.info("\n" + "="*80)
    logger.info(f"TEST: {test_name}")
    logger.info("="*80)
    
    system_info = get_system_info()
    logger.info("SYSTEM INFORMATION:")
    for key, value in system_info.items():
        logger.info(f"  {key}: {value}")
    logger.info("-"*80)
    
    # Log the command to be executed
    logger.info(f"COMMAND: {command}")
    logger.info("-"*80)
    
    # Prepare user for the test
    print("\n" + "="*80)
    print(f"PREPARING TO RUN TEST: {test_name}")
    print("="*80)
    print(f"\nCommand: {command}")
    print(f"\nTest phrase to speak: \"{test_phrase}\"")
    print("\nThis test will run XVoice2 with the specified configuration.")
    
    # Add specialized instructions for certain tests
    if "email" in test_name.lower() or "command" in test_name.lower():
        mode_type = "email" if "email" in test_name.lower() else "command"
        
        if "--use-llm" in command:
            print(f"\nNOTE: This {mode_type} mode test requires a valid OpenAI API key in your config.")
            print("If you don't have one, this test may fail.")
        elif "--use-local-llm" in command:
            print(f"\nNOTE: This {mode_type} mode test requires Ollama running with a valid model.")
            print("If Ollama is not running, this test may fail.")
        else:
            print(f"\nNOTE: {mode_type.capitalize()} mode requires LLM formatting to work properly.")
            print("This test should include either --use-llm or --use-local-llm.")
            
        if "command" in test_name.lower():
            print("\nPlease make sure a terminal window is active/focused when the application")
            print("injects the command, so it can be properly executed.")
    
    print("\nWhen the app starts, speak the test phrase clearly into your microphone.")
    print("The app will run for approximately 30 seconds or until you press Ctrl+C.")
    wait_for_keypress("\nPress Enter when you're ready to begin the test...")
    
    # Execute the command
    logger.info("TEST EXECUTION STARTED")
    try:
        # Start the process
        process = subprocess.Popen(
            command.split(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Set a timeout for the test (30 seconds)
        max_duration = 30
        start_time = time.time()
        
        print(f"\nTest running... (will timeout after {max_duration} seconds)")
        print("Speak your test phrase now.")
        print("Press Ctrl+C when finished or wait for timeout.")
        
        # Read and log output in real-time
        while True:
            # Check if we've exceeded the timeout
            if time.time() - start_time > max_duration:
                logger.info(f"Test timed out after {max_duration} seconds")
                process.terminate()
                break
            
            # Read a line of output (if available)
            output = process.stdout.readline()
            if output:
                logger.info(f"OUTPUT: {output.strip()}")
                print(f"  {output.strip()}")
            
            # Check if process has ended
            if process.poll() is not None:
                # Read any remaining output
                for line in process.stdout.readlines():
                    logger.info(f"OUTPUT: {line.strip()}")
                    print(f"  {line.strip()}")
                break
            
            # Small delay to prevent CPU spinning
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        logger.info("Test manually interrupted with Ctrl+C")
        print("\nTest manually interrupted.")
        try:
            process.terminate()
        except:
            pass
    except Exception as e:
        logger.error(f"Error during test execution: {str(e)}")
        print(f"\nError during test: {str(e)}")
    
    # Ensure the process is terminated
    try:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
    except:
        pass
    
    logger.info("TEST EXECUTION COMPLETED")
    
    # Get user feedback
    print("\nTest completed.")
    result = input("Did the test pass? (y/n): ").strip().lower()
    notes = input("Additional notes (optional): ").strip()
    
    logger.info(f"TEST RESULT: {'PASS' if result.startswith('y') else 'FAIL'}")
    if notes:
        logger.info(f"USER NOTES: {notes}")
    
    logger.info("-"*80 + "\n")
    return result.startswith('y')

def main():
    """Main test orchestration function."""
    # Check if running on a supported platform
    if platform.system() not in ["Linux", "Darwin"]:
        print("Error: XVoice2 is only supported on Linux and macOS platforms.")
        print(f"Current platform: {platform.system()}")
        return 1
        
    parser = argparse.ArgumentParser(description="Run system tests for XVoice2")
    parser.add_argument("--log-file", help="Path to log file (default: system_test_TIMESTAMP.log)")
    args = parser.parse_args()
    
    # Setup logging
    logger, log_file = setup_logging(args.log_file)
    logger.info(f"System test started at {datetime.datetime.now().isoformat()}")
    logger.info(f"Log file: {os.path.abspath(log_file)}")
    
    # Welcome message
    print("\nXVoice2 System Test")
    print("==================\n")
    print("This program will run XVoice2 with various configurations to test functionality.")
    print("You will be prompted to speak test phrases for each configuration.")
    print(f"Results will be logged to: {os.path.abspath(log_file)}")
    print("\nBefore starting:")
    print("1. Make sure your microphone is connected and working")
    print("2. Have a text editor open to verify text injection")
    print("3. For command mode tests, have a terminal window open and active")
    
    wait_for_keypress("\nPress Enter to begin testing...")
    
    # Get available Whisper models
    transcriber = Transcriber()
    available_models = transcriber.get_available_models()
    
    # Check if Ollama is available for local LLM tests
    ollama_available = False
    try:
        import requests
        response = requests.get("http://localhost:11434/api/version", timeout=2)
        if response.status_code == 200:
            ollama_available = True
            logger.info("Ollama is available, will include local LLM tests")
        else:
            logger.info(f"Ollama returned status code {response.status_code}, skipping local LLM tests")
    except Exception as e:
        logger.info(f"Ollama not available ({str(e)}), skipping local LLM tests")
    
    # Define test scenarios
    test_scenarios = [
        {
            "name": "Basic Operation (Default Mode)",
            "command": "python -m xvoice2",
            "phrase": "This is a test of the basic voice dictation system."
        },
        {
            "name": "Email Mode with LLM",
            "command": "python -m xvoice2 --mode email --use-llm",
            "phrase": "Dear team, I'm testing the voice dictation system in email mode. Best regards."
        }
    ]
    
    # Add model-specific tests if multiple models are available
    if len(available_models) > 1:
        for model in available_models:
            # Skip the model already tested in basic operation
            if model == config.WHISPER_MODEL:
                continue
                
            test_scenarios.append({
                "name": f"Alternative Model ({model})",
                "command": f"python -m xvoice2 --model {model}",
                "phrase": f"This is a test using the {model} model for transcription."
            })
    
    # Add command mode with OpenAI LLM
    test_scenarios.append({
        "name": "Command Mode with LLM",
        "command": "python -m xvoice2 --mode command --use-llm",
        "phrase": "echo Hello from voice command"
    })
    
    # Add Ollama-based tests if available
    if ollama_available:
        # Command mode with Ollama
        test_scenarios.append({
            "name": "Command Mode with Local LLM (Ollama)",
            "command": "python -m xvoice2 --mode command --use-local-llm",
            "phrase": "list all files in the current directory"
        })
        
        # General mode with Ollama
        test_scenarios.append({
            "name": "General Mode with Local LLM (Ollama)",
            "command": "python -m xvoice2 --use-local-llm",
            "phrase": "testing voice dictation with local llm formatting provided by ollama"
        })
        
        # Email mode with Ollama
        test_scenarios.append({
            "name": "Email Mode with Local LLM (Ollama)",
            "command": "python -m xvoice2 --mode email --use-local-llm",
            "phrase": "dear team i am testing the email mode with ollama for formatting thanks"
        })
    
    # Run the tests
    results = []
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\nTest {i} of {len(test_scenarios)}")
        result = run_test(
            logger, 
            scenario["name"], 
            scenario["command"], 
            scenario["phrase"]
        )
        results.append((scenario["name"], result))
        
        # Short break between tests
        if i < len(test_scenarios):
            wait_for_keypress("\nPress Enter to continue to the next test...")
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{name}: {status}")
    
    print("-"*80)
    print(f"Tests passed: {passed}/{total} ({passed/total*100:.1f}%)")
    print("-"*80)
    
    logger.info("\n" + "="*80)
    logger.info("TEST SUMMARY")
    logger.info("="*80)
    
    for name, result in results:
        logger.info(f"{name}: {'PASS' if result else 'FAIL'}")
    
    logger.info("-"*80)
    logger.info(f"Tests passed: {passed}/{total} ({passed/total*100:.1f}%)")
    logger.info(f"System test completed at {datetime.datetime.now().isoformat()}")
    
    print(f"\nFull test results have been saved to: {os.path.abspath(log_file)}")

if __name__ == "__main__":
    sys.exit(main() or 0)