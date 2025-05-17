# Booking Resources Deployment Scripts

This directory contains scripts and templates for deploying the booking system resources using AWS CloudFormation.

## Files

- `booking-resources.yaml`: CloudFormation template that defines all the AWS resources needed for the booking system
- `package-lambda.sh`: Script to package the Lambda code and upload it to S3
- `deploy-booking-resources.sh`: Script to deploy the CloudFormation stack and update environment files

## Prerequisites

1. AWS CLI installed and configured
2. AWS profile with appropriate permissions
3. S3 bucket for storing Lambda code

## Usage

### Step 1: Update Configuration

Edit both scripts to set your S3 bucket name:

```bash
# In package-lambda.sh and deploy-booking-resources.sh
S3_BUCKET="your-lambda-code-bucket"  # Replace with your bucket name
```

### Step 2: Package and Upload Lambda Code

```bash
./package-lambda.sh
```

This script will:
- Package the Lambda code from the `python-server/booking` directory
- Upload it to the specified S3 bucket
- Clean up temporary files

### Step 3: Deploy CloudFormation Stack

```bash
./deploy-booking-resources.sh
```

This script will:
- Deploy the CloudFormation stack with all required resources
- Retrieve the Lambda ARN from the stack outputs
- Update the environment files with the Lambda ARN

## Resources Created

The CloudFormation template creates the following resources:

1. DynamoDB Table (Bookings)
2. IAM Role for Lambda (BookingLambdaRole)
3. Lambda Function (BookingFunction)
4. Lambda Permission for Bedrock
5. Bedrock Execution Role (BedrockExecutionRole)

## Environment Updates

The deployment script updates the following files with the Lambda ARN:

- `python-server/.env`
- `python-server/.env.lambda`
