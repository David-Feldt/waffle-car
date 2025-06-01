#!/bin/bash

# Robot Controller Startup Script
# This script runs on boot to start the robot controller

# Configuration
SCRIPT_DIR="/home/david/waffle"
VENV_DIR="$SCRIPT_DIR/venv"
PYTHON_SCRIPT="controller_control.py"
LOG_FILE="/var/log/robot_controller.log"

# Function to log messages
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Function to wait for Bluetooth to be ready
wait_for_bluetooth() {
    log_message "Waiting for Bluetooth service to be ready..."
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if systemctl is-active --quiet bluetooth; then
            log_message "Bluetooth service is active"
            return 0
        fi
        sleep 2
        attempt=$((attempt + 1))
        log_message "Waiting for Bluetooth... attempt $attempt/$max_attempts"
    done
    
    log_message "ERROR: Bluetooth service not ready after $max_attempts attempts"
    return 1
}

# Function to connect controller
connect_controller() {
    log_message "Attempting to connect controller..."
    cd "$SCRIPT_DIR"
    
    # Run the controller connection script
    if ./connect_controller.sh >> "$LOG_FILE" 2>&1; then
        log_message "Controller connection script completed"
        return 0
    else
        log_message "Controller connection script failed"
        return 1
    fi
}

# Main startup function
main() {
    log_message "=== Robot Controller Startup ==="
    log_message "Script directory: $SCRIPT_DIR"
    log_message "Virtual environment: $VENV_DIR"
    log_message "Python script: $PYTHON_SCRIPT"
    
    # Change to script directory
    cd "$SCRIPT_DIR" || {
        log_message "ERROR: Cannot change to directory $SCRIPT_DIR"
        exit 1
    }
    
    # Check if virtual environment exists
    if [ ! -d "$VENV_DIR" ]; then
        log_message "ERROR: Virtual environment not found at $VENV_DIR"
        exit 1
    fi
    
    # Check if Python script exists
    if [ ! -f "$PYTHON_SCRIPT" ]; then
        log_message "ERROR: Python script not found: $PYTHON_SCRIPT"
        exit 1
    fi
    
    # Wait for Bluetooth to be ready
    if ! wait_for_bluetooth; then
        log_message "ERROR: Bluetooth not ready, cannot start robot controller"
        exit 1
    fi
    
    # Wait a bit more for system to stabilize
    log_message "Waiting for system to stabilize..."
    sleep 10
    
    # Connect controller
    connect_controller
    
    # Activate virtual environment
    log_message "Activating virtual environment..."
    source "$VENV_DIR/bin/activate" || {
        log_message "ERROR: Failed to activate virtual environment"
        exit 1
    }
    
    # Wait for controller to be ready
    log_message "Waiting for controller to be ready..."
    sleep 5
    
    # Start the robot controller
    log_message "Starting robot controller: $PYTHON_SCRIPT"
    log_message "=== Controller Output ==="
    
    # Run the Python script with output to log
    python3 "$PYTHON_SCRIPT" 2>&1 | while IFS= read -r line; do
        log_message "CONTROLLER: $line"
    done
    
    # If we get here, the script has exited
    log_message "Robot controller has stopped"
}

# Create log file if it doesn't exist
sudo touch "$LOG_FILE"
sudo chmod 666 "$LOG_FILE"

# Run main function
main 