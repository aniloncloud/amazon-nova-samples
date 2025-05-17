#!/bin/bash

# deploy-booking-resources.sh
# This script deploys the CloudFormation stack and updates environment files

set -e  # Exit on error

# Configuration
STACK_NAME="BookingResources"
S3_BUCKET="your-lambda-code-bucket"  # Replace with your bucket name
S3_KEY="booking-lambda/lambda_package.zip"
REGION=${AWS_REGION:-"us-east-1"}
PROFILE=${AWS_PROFILE:-"nova"}

# Set AWS profile
export AWS_PROFILE=$PROFILE
echo "Using AWS profile: $AWS_PROFILE"

# Deploy CloudFormation stack
echo "Deploying CloudFormation stack: $STACK_NAME"
aws cloudformation deploy \
  --stack-name $STACK_NAME \
  --template-file "$(dirname "$0")/booking-resources.yaml" \
  --parameter-overrides \
    LambdaCodeS3Bucket=$S3_BUCKET \
    LambdaCodeS3Key=$S3_KEY \
  --capabilities CAPABILITY_NAMED_IAM \
  --region $REGION

# Get Lambda ARN from CloudFormation outputs
echo "Getting Lambda ARN from CloudFormation outputs..."
LAMBDA_ARN=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query "Stacks[0].Outputs[?OutputKey=='BookingLambdaArn'].OutputValue" \
  --output text \
  --region $REGION)

echo "Lambda ARN: $LAMBDA_ARN"

# Change to the parent directory of the script
cd "$(dirname "$0")/.."

# Update .env file
echo "Updating .env file..."
ENV_FILE="python-server/.env"
if grep -q "^BOOKING_LAMBDA_ARN=" "$ENV_FILE"; then
  # Replace existing entry
  sed -i.bak "s|^BOOKING_LAMBDA_ARN=.*|BOOKING_LAMBDA_ARN=$LAMBDA_ARN|" "$ENV_FILE"
  rm -f "$ENV_FILE.bak"
else
  # Add new entry
  echo "BOOKING_LAMBDA_ARN=$LAMBDA_ARN" >> "$ENV_FILE"
fi

# Update .env.lambda file
echo "Updating .env.lambda file..."
ENV_LAMBDA_FILE="python-server/.env.lambda"
echo "export BOOKING_LAMBDA_ARN=$LAMBDA_ARN" > "$ENV_LAMBDA_FILE"

echo "Deployment completed successfully!"
echo "Lambda ARN: $LAMBDA_ARN"
