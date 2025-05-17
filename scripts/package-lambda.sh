#!/bin/bash

# package-lambda.sh
# This script packages the Lambda code and uploads it to S3

set -e  # Exit on error

# Configuration
S3_BUCKET="your-lambda-code-bucket"  # Replace with your bucket name
S3_KEY="booking-lambda/lambda_package.zip"
REGION=${AWS_REGION:-"us-east-1"}
PROFILE=${AWS_PROFILE:-"nova"}

# Set AWS profile
export AWS_PROFILE=$PROFILE
echo "Using AWS profile: $AWS_PROFILE"

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
aws s3 cp lambda_package.zip s3://$S3_BUCKET/$S3_KEY --region $REGION

# Clean up
echo "Cleaning up..."
rm -rf build lambda_package.zip

echo "Lambda code packaged and uploaded successfully!"
echo "S3 Location: s3://$S3_BUCKET/$S3_KEY"
