#!/bin/bash
# Workshop setup script for speech-to-speech Python server

# Exit on error
set -e

echo "Starting Speech-to-Speech workshop setup..."

# Check Python version
python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
echo "Detected Python version: $python_version"
required_version="3.9"

if [[ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]]; then
    echo "Error: Python version must be at least $required_version"
    exit 1
fi

# Set AWS profile to nova
export AWS_PROFILE=nova
echo "Using AWS profile: $AWS_PROFILE"

# Check if AWS CLI is installed and configured
if ! command -v aws &> /dev/null; then
    echo "Error: AWS CLI is not installed. Please install it first."
    exit 1
fi

# Verify AWS credentials
echo "Verifying AWS credentials..."
if ! aws sts get-caller-identity &> /dev/null; then
    echo "Error: AWS credentials not configured. Please run 'aws configure' first."
    exit 1
fi

# Start virtual environment
echo "Setting up Python virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Set up .env file with default values
echo "Setting up environment variables..."
cat > .env << EOF
# AWS Configuration
AWS_REGION=us-east-1
AWS_PROFILE=nova

# Server Configuration
HOST=0.0.0.0
WS_PORT=8081
HEALTH_PORT=8082

# Logging Configuration
LOG_LEVEL=INFO

# Other defaults will be set by setup_booking_resources.sh
EOF

echo "Environment configuration created in .env file"

# Run booking resources setup
echo "Setting up booking resources..."
./setup_booking_resources.sh

# Final instructions
echo ""
echo "Setup complete! You can now run:"
echo "  - ./run_inline_agent.sh - To test the inline agent with a query"
echo "  - python server.py - To start the websocket server"
echo ""
echo "Note: Always activate the virtual environment with 'source .venv/bin/activate' before running scripts."
