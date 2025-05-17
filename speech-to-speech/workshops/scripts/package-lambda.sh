#!/bin/bash

# package-lambda.sh
# This script packages the Lambda code and uploads it to S3

set -e  # Exit on error

# Configuration
S3_BUCKET="nova-sonic-deploy-bucket"  # Replace with your bucket name
S3_KEY="booking-lambda/lambda_package.zip"

# Require AWS_PROFILE and AWS_REGION to be set
if [ -z "$AWS_PROFILE" ]; then
  echo "Error: AWS_PROFILE environment variable is not set."
  exit 1
fi
if [ -z "$AWS_REGION" ]; then
  echo "Error: AWS_REGION environment variable is not set."
  exit 1
fi

export AWS_PROFILE
export AWS_REGION

echo "Using AWS profile: $AWS_PROFILE"
echo "Using AWS region: $AWS_REGION"

# Package Lambda code
echo "Packaging Lambda code..."
cd "$(dirname "$0")/.."  # Change to the parent directory of the script
mkdir -p ./build
cp -r python-server/booking ./build/
cd build
zip -r ../lambda_package.zip .
cd ..
echo "Lambda package created"

# Upload to S3
echo "Uploading Lambda package to S3..."
aws s3 cp lambda_package.zip s3://$S3_BUCKET/$S3_KEY --region $AWS_REGION

# Clean up
echo "Cleaning up..."
rm -rf build lambda_package.zip

echo "Lambda code packaged and uploaded successfully!"
echo "S3 Location: s3://$S3_BUCKET/$S3_KEY"
