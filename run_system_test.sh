#!/bin/bash
#
# Run XVoice2 System Test
#
# This script runs the system test for XVoice2, ensuring the virtual environment
# is activated and all dependencies are installed.

set -e  # Exit immediately if a command exits with a non-zero status

# Function to print colorful messages
print_header() {
    echo -e "\033[1;34m==== $1 ====\033[0m"
}

print_info() {
    echo -e "\033[0;32m$1\033[0m"
}

print_warning() {
    echo -e "\033[0;33m$1\033[0m"
}

print_error() {
    echo -e "\033[0;31m$1\033[0m"
}

# Check if running in virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    print_warning "Virtual environment not activated. Attempting to activate it..."
    
    # Check if the venv directory exists
    if [ -d "venv" ]; then
        source venv/bin/activate
        print_info "Virtual environment activated."
    else
        print_error "Virtual environment 'venv' not found. Please create and activate it first."
        print_info "You can create it with: python -m venv venv"
        print_info "And activate it with: source venv/bin/activate"
        exit 1
    fi
fi

# Check for psutil installation (needed for system tests)
if ! python -c "import psutil" &> /dev/null; then
    print_warning "psutil not found. Installing required test dependencies..."
    pip install -r requirements.txt
    print_info "Dependencies installed."
fi

# Create a timestamp for the log file
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="system_test_${TIMESTAMP}.log"

print_header "XVoice2 System Test"
print_info "Starting system test. Results will be logged to: $LOG_FILE"
print_info ""
print_info "Make sure you have:"
print_info "1. A working microphone connected"
print_info "2. A text editor open to verify text injection"
print_info "3. A terminal window open for command mode tests"
print_info ""

# Run the system test
python tests/system_test.py --log-file "$LOG_FILE"

# Check if the test script ran successfully
if [ $? -eq 0 ]; then
    print_header "Test Completed"
    print_info "The system test has completed. Results are saved in: $LOG_FILE"
else
    print_error "The system test encountered an error. Please check the output above."
fi