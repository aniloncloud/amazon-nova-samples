#!/bin/bash

# setup_booking_resources.sh
# This script sets up the necessary AWS resources for the booking system:
# - IAM role for Lambda to access DynamoDB
# - DynamoDB table for bookings
# - Lambda function for booking operations

set -e  # Exit on error

# Configuration
REGION=${AWS_REGION:-"us-east-1"}
ROLE_NAME="BookingLambdaRole"
TABLE_NAME="Bookings"
LAMBDA_NAME="BookingFunction"
LAMBDA_HANDLER="booking.booking_lambda.lambda_handler"
LAMBDA_RUNTIME="python3.9"
LAMBDA_TIMEOUT=30
LAMBDA_MEMORY=256

# Set AWS profile to nova
export AWS_PROFILE=112
echo "Using AWS profile: $AWS_PROFILE"

echo "Setting up booking 
sources in region: $REGION"

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "AWS CLI is not installed. Please install it first."
    exit 1
fi

# Check if AWS credentials are configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo "AWS credentials are not configured. Please run 'aws configure' first."
    exit 1
fi

# Create IAM role for Lambda (idempotent)
echo "Creating IAM role: $ROLE_NAME (if it doesn't exist)..."
ROLE_ARN=$(aws iam get-role --role-name $ROLE_NAME --query 'Role.Arn' --output text 2>/dev/null || echo "")

if [ -z "$ROLE_ARN" ]; then
    # Create trust policy document
    cat > trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    # Create role
    ROLE_ARN=$(aws iam create-role \
        --role-name $ROLE_NAME \
        --assume-role-policy-document file://trust-policy.json \
        --query 'Role.Arn' \
        --output text)
    
    echo "Created IAM role: $ROLE_ARN"
    
    # Attach policies
    echo "Attaching policies to role..."
    aws iam attach-role-policy \
        --role-name $ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
    
    # Create DynamoDB policy document
    cat > dynamodb-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem",
                "dynamodb:Scan",
                "dynamodb:Query",
                "dynamodb:DescribeTable",
                "dynamodb:CreateTable"
            ],
            "Resource": [
                "arn:aws:dynamodb:$REGION:*:table/$TABLE_NAME"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:ListTables"
            ],
            "Resource": "*"
        }
    ]
}
EOF

    # Create and attach DynamoDB policy
    aws iam put-role-policy \
        --role-name $ROLE_NAME \
        --policy-name "DynamoDBAccess" \
        --policy-document file://dynamodb-policy.json
    
    echo "Policies attached to role"
    
    # Wait for role to propagate
    echo "Waiting for role to propagate..."
    sleep 10
else
    echo "IAM role already exists: $ROLE_ARN"
fi

# Create DynamoDB table (idempotent)
echo "Creating DynamoDB table: $TABLE_NAME (if it doesn't exist)..."
TABLE_EXISTS=$(aws dynamodb describe-table --table-name $TABLE_NAME --query 'Table.TableName' --output text 2>/dev/null || echo "")

if [ -z "$TABLE_EXISTS" ]; then
    aws dynamodb create-table \
        --table-name $TABLE_NAME \
        --attribute-definitions AttributeName=booking_id,AttributeType=S \
        --key-schema AttributeName=booking_id,KeyType=HASH \
        --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 \
        --region $REGION
    
    echo "Waiting for table to become active..."
    aws dynamodb wait table-exists --table-name $TABLE_NAME
    echo "DynamoDB table created: $TABLE_NAME"
else
    echo "DynamoDB table already exists: $TABLE_NAME"
fi

# Create Lambda function package
echo "Creating Lambda function package..."
cd "$(dirname "$0")"  # Change to the script's directory
mkdir -p ./build
cp -r booking ./build/
cd build
zip -r ../build/lambda_package.zip .
cd ..
echo "Lambda package created: $(du -h ../build/lambda_package.zip | cut -f1)"

# Create or update Lambda function
echo "Creating/updating Lambda function: $LAMBDA_NAME..."
LAMBDA_EXISTS=$(aws lambda get-function --function-name $LAMBDA_NAME --query 'Configuration.FunctionName' --output text 2>/dev/null || echo "")

# Set AWS CLI timeout
export AWS_CLIENT_TIMEOUT=300

if [ -z "$LAMBDA_EXISTS" ]; then
    # Create new Lambda function
    echo "Creating new Lambda function..."
    LAMBDA_ARN=$(aws lambda create-function \
        --function-name $LAMBDA_NAME \
        --runtime $LAMBDA_RUNTIME \
        --role $ROLE_ARN \
        --handler $LAMBDA_HANDLER \
        --timeout $LAMBDA_TIMEOUT \
        --memory-size $LAMBDA_MEMORY \
        --zip-file fileb://build/lambda_package.zip \
        --environment "Variables={TABLE_NAME=$TABLE_NAME}" \
        --query 'FunctionArn' \
        --output text)
    
    echo "Lambda function created: $LAMBDA_ARN"
else
    # Update existing Lambda function
    echo "Updating existing Lambda function code..."
    # Use S3 for larger packages
    BUCKET_NAME="lambda-deployment-$(date +%s)"
    echo "Creating temporary S3 bucket: $BUCKET_NAME"
    aws s3 mb s3://$BUCKET_NAME --region $REGION
    
    echo "Uploading Lambda package to S3..."
    aws s3 cp build/lambda_package.zip s3://$BUCKET_NAME/
    
    echo "Updating Lambda function from S3..."
    LAMBDA_ARN=$(aws lambda update-function-code \
        --function-name $LAMBDA_NAME \
        --s3-bucket $BUCKET_NAME \
        --s3-key lambda_package.zip \
        --query 'FunctionArn' \
        --output text)
    
    echo "Cleaning up S3 bucket..."
    aws s3 rm s3://$BUCKET_NAME/lambda_package.zip
    aws s3 rb s3://$BUCKET_NAME --force
    
    # Update configuration
    echo "Updating Lambda function configuration..."
    aws lambda update-function-configuration \
        --function-name $LAMBDA_NAME \
        --runtime $LAMBDA_RUNTIME \
        --role $ROLE_ARN \
        --handler $LAMBDA_HANDLER \
        --timeout $LAMBDA_TIMEOUT \
        --memory-size $LAMBDA_MEMORY \
        --environment "Variables={TABLE_NAME=$TABLE_NAME}"
    
    echo "Lambda function updated: $LAMBDA_ARN"
fi

# Add permission for Bedrock to invoke the Lambda function
echo "Adding permission for Bedrock to invoke Lambda function..."
# Check if permission already exists
PERMISSION_EXISTS=$(aws lambda get-policy --function-name $LAMBDA_NAME --query "Policy" --output text 2>/dev/null | grep -c "bedrock-access" || echo "0")

if [ "$PERMISSION_EXISTS" -eq "0" ]; then
    echo "Adding permission for Bedrock to invoke Lambda function..."
    aws lambda add-permission \
        --function-name $LAMBDA_NAME \
        --action lambda:InvokeFunction \
        --principal bedrock.amazonaws.com \
        --statement-id bedrock-access \
        --region $REGION
else
    echo "Permission for Bedrock to invoke Lambda function already exists. Skipping..."
fi

# Create Bedrock execution role (if needed)
BEDROCK_ROLE_NAME="BedrockExecutionRole"
echo "Creating Bedrock execution role: $BEDROCK_ROLE_NAME (if it doesn't exist)..."
BEDROCK_ROLE_ARN=$(aws iam get-role --role-name $BEDROCK_ROLE_NAME --query 'Role.Arn' --output text 2>/dev/null || echo "")

if [ -z "$BEDROCK_ROLE_ARN" ]; then
    # Create trust policy for Bedrock
    cat > bedrock-trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "bedrock.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    # Create Bedrock execution role
    BEDROCK_ROLE_ARN=$(aws iam create-role \
        --role-name $BEDROCK_ROLE_NAME \
        --assume-role-policy-document file://bedrock-trust-policy.json \
        --query 'Role.Arn' \
        --output text)
    
    # Create Lambda invoke policy
    cat > lambda-invoke-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Action": "lambda:InvokeFunction",
        "Resource": "$LAMBDA_ARN"
    }]
}
EOF

    # Attach policy to Bedrock role
    aws iam put-role-policy \
        --role-name $BEDROCK_ROLE_NAME \
        --policy-name "LambdaInvokeAccess" \
        --policy-document file://lambda-invoke-policy.json
    
    echo "Created Bedrock execution role: $BEDROCK_ROLE_ARN"
else
    echo "Bedrock execution role already exists: $BEDROCK_ROLE_ARN"
fi

# Set environment variable for Lambda ARN
# Create .env.lambda for shell script sourcing (if needed in the future)
echo "export BOOKING_LAMBDA_ARN=$LAMBDA_ARN" > .env.lambda

# Update .env file, avoiding duplicates
if grep -q "^BOOKING_LAMBDA_ARN=" .env; then
    # Replace existing entry
    sed -i.bak "s|^BOOKING_LAMBDA_ARN=.*|BOOKING_LAMBDA_ARN=$LAMBDA_ARN|" .env
    rm -f .env.bak
else
    # Add new entry
    echo "BOOKING_LAMBDA_ARN=$LAMBDA_ARN" >> .env
fi

# Clean up temporary files
rm -rf trust-policy.json dynamodb-policy.json bedrock-trust-policy.json lambda-invoke-policy.json build

echo "Setup for InlineAgent completed successfully!"
echo "DynamoDB Table: $TABLE_NAME"
echo "IAM Role: $ROLE_NAME"
echo "Lambda Function: $LAMBDA_ARN"
echo "Environment variable set: BOOKING_LAMBDA_ARN=$LAMBDA_ARN"
