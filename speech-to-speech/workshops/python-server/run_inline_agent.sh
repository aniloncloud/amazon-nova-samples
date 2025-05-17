#!/bin/bash

# Set AWS profile if not already set by the user
if [ -z "$AWS_PROFILE" ]; then
  export AWS_PROFILE=112
  echo "Using default AWS profile: $AWS_PROFILE (override with AWS_PROFILE environment variable)"
else
  echo "Using AWS profile: $AWS_PROFILE"
fi

# Source environment variables
if [ -f .env ]; then
  # Export BOOKING_LAMBDA_ARN explicitly from .env
  export BOOKING_LAMBDA_ARN=$(grep "^BOOKING_LAMBDA_ARN=" .env | head -n 1 | cut -d '=' -f 2)
  echo "Using Lambda ARN: $BOOKING_LAMBDA_ARN"
  
  # Source the rest of the environment variables
  set -a
  source .env
  set +a
fi

# Check for booking_openapi.json before running the agent
if [ ! -f booking/booking_openapi.json ]; then
  echo "Error: booking/booking_openapi.json not found!"
  exit 1
fi

# Run the inline agent script
python3 inline_agent.py
