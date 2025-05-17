#!/bin/bash

# cleanup_booking_resources.sh
# This script deletes the AWS resources created by setup_booking_resources.sh:
# - Lambda function
# - DynamoDB table
# - IAM roles and policies
# - Environment variable entries

set -e  # Exit on error

# Configuration
REGION=${AWS_REGION:-"us-east-1"}
ROLE_NAME="BookingLambdaRole"
TABLE_NAME="Bookings"
LAMBDA_NAME="BookingFunction"
BEDROCK_ROLE_NAME="BedrockExecutionRole"

# Set AWS profile to nova
export AWS_PROFILE=112

echo "Starting cleanup of booking resources in region: $REGION"

# Delete Lambda function (if exists)
echo "Deleting Lambda function: $LAMBDA_NAME (if it exists)..."
if aws lambda get-function --function-name $LAMBDA_NAME --region $REGION &> /dev/null; then
    aws lambda delete-function --function-name $LAMBDA_NAME --region $REGION
    echo "Lambda function deleted."
else
    echo "Lambda function does not exist. Skipping."
fi

# Delete DynamoDB table (if exists)
echo "Deleting DynamoDB table: $TABLE_NAME (if it exists)..."
if aws dynamodb describe-table --table-name $TABLE_NAME --region $REGION &> /dev/null; then
    aws dynamodb delete-table --table-name $TABLE_NAME --region $REGION
    echo "Waiting for DynamoDB table to be deleted..."
    aws dynamodb wait table-not-exists --table-name $TABLE_NAME --region $REGION
    echo "DynamoDB table deleted."
else
    echo "DynamoDB table does not exist. Skipping."
fi

# Detach and delete inline policy from Lambda role (if exists)
echo "Deleting inline policy from IAM role: $ROLE_NAME (if it exists)..."
if aws iam get-role --role-name $ROLE_NAME &> /dev/null; then
    if aws iam get-role-policy --role-name $ROLE_NAME --policy-name "DynamoDBAccess" &> /dev/null; then
        aws iam delete-role-policy --role-name $ROLE_NAME --policy-name "DynamoDBAccess"
        echo "Inline policy deleted."
    else
        echo "Inline policy does not exist. Skipping."
    fi
    # Detach managed policy
    aws iam detach-role-policy --role-name $ROLE_NAME --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole || true
    # Delete role
    aws iam delete-role --role-name $ROLE_NAME
    echo "IAM role deleted."
else
    echo "IAM role does not exist. Skipping."
fi

# Delete Bedrock execution role and its policy (if exists)
echo "Deleting Bedrock execution role: $BEDROCK_ROLE_NAME (if it exists)..."
if aws iam get-role --role-name $BEDROCK_ROLE_NAME &> /dev/null; then
    if aws iam get-role-policy --role-name $BEDROCK_ROLE_NAME --policy-name "LambdaInvokeAccess" &> /dev/null; then
        aws iam delete-role-policy --role-name $BEDROCK_ROLE_NAME --policy-name "LambdaInvokeAccess"
        echo "Bedrock role inline policy deleted."
    else
        echo "Bedrock role inline policy does not exist. Skipping."
    fi
    aws iam delete-role --role-name $BEDROCK_ROLE_NAME
    echo "Bedrock execution role deleted."
else
    echo "Bedrock execution role does not exist. Skipping."
fi

# Remove BOOKING_LAMBDA_ARN from .env and .env.lambda
echo "Cleaning up environment files..."
if [ -f .env ]; then
    sed -i.bak '/^BOOKING_LAMBDA_ARN=/d' .env && rm -f .env.bak
    echo ".env cleaned."
fi
if [ -f .env.lambda ]; then
    rm -f .env.lambda
    echo ".env.lambda removed."
fi

echo "Cleanup completed successfully!" 