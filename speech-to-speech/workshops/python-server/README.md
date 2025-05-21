# Speech-to-Speech Booking System

This repository contains a serverless booking system that leverages AWS Bedrock for natural language processing and DynamoDB for data storage. The system allows users to create, query, update, and delete bookings through a conversational interface.

## Architecture

The system consists of the following components:

1. **Bedrock Agent with Inline Orchestration** - Processes natural language requests and orchestrates interactions with the Lambda function
2. **Lambda Function** - Handles booking operations and interfaces with DynamoDB
3. **DynamoDB** - Stores booking data
4. **WebSocket Server** - Provides real-time communication for the speech interface
5. **Strands Agent Integration** - Added support for Strands-based agents as an alternative to the MCP client
6. **Knowledge Base Integration** - Supports retrieving information from Bedrock Knowledge Base

### Components

- `inline_agent.py` - Inline agent orchestrator using Claude/Bedrock
- `booking/booking_lambda.py` - Lambda function handler for booking operations
- `booking/booking_db.py` - DynamoDB data access layer
- `booking/booking_openapi.json` - OpenAPI schema for the booking API
- `server.py` - WebSocket server for real-time communication with Strands and MCP integration
- `setup_booking_resources.sh` - Script to set up AWS resources
- `run_inline_agent.sh` - Script to run the inline agent
- `workshop-setup.sh` - Setup script for the workshop
- `bedrock_knowledge_bases.py` - Knowledge base integration

## Prerequisites

- Python 3.9+
- AWS CLI installed and configured
- AWS Bedrock access
- AWS Lambda and DynamoDB permissions

## Setup

1. Clone the repository
2. Run the setup script:

```bash
./workshop-setup.sh
```

This will:
- Create a Python virtual environment
- Install dependencies
- Set up environment variables
- Create AWS resources (Lambda function, DynamoDB table, etc.)

3. Set up AWS credentials:

```bash
# Option 1: Set environment variables directly
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_SESSION_TOKEN=your_session_token  # if using temporary credentials

# Option 2: Use AWS CLI to configure credentials
aws configure

# Option 3: Add to your .env file
echo "AWS_ACCESS_KEY_ID=your_access_key" >> .env
echo "AWS_SECRET_ACCESS_KEY=your_secret_key" >> .env
echo "AWS_SESSION_TOKEN=your_session_token" >> .env  # if needed
```

## Knowledge Base Setup

To set up and use a knowledge base with the system:

1. Create a knowledge base in AWS Bedrock:

```bash
# Create a knowledge base using AWS CLI
aws bedrock create-knowledge-base \
  --name "BookingKnowledgeBase" \
  --description "Knowledge base for booking information" \
  --storage-configuration "type=OPENSEARCH"
```

2. Configure the knowledge base in your .env file:

```bash
echo "KNOWLEDGE_BASE_ID=your_knowledge_base_id" >> .env
echo "KNOWLEDGE_BASE_DATA_SOURCE_ID=your_data_source_id" >> .env
```

3. Add documents to your knowledge base:

```bash
# Upload documents to S3
aws s3 cp ./knowledge_docs/ s3://your-bucket/knowledge_docs/ --recursive

# Create a data source that points to your S3 location
aws bedrock create-data-source \
  --knowledge-base-id your_knowledge_base_id \
  --name "BookingDataSource" \
  --description "Data source for booking knowledge" \
  --data-source-configuration "type=S3,s3Configuration={bucketName=your-bucket,prefix=knowledge_docs/}"
```

## Environment Variables

The following environment variables are used:

| Variable | Description | Default |
|----------|-------------|---------|
| AWS_REGION | AWS Region | us-east-1 |
| AWS_PROFILE | AWS CLI profile | set in environment |
| AWS_ACCESS_KEY_ID | AWS access key | required |
| AWS_SECRET_ACCESS_KEY | AWS secret key | required |
| AWS_SESSION_TOKEN | AWS session token | required, for Nova Sonic integration |
| BOOKING_LAMBDA_ARN | ARN of the booking Lambda function | Set by setup_booking_resources.sh |
| TABLE_NAME | DynamoDB table name | Bookings |
| FOUNDATION_MODEL | Bedrock foundation model to use | amazon.nova-lite-v1:0 |
| HOST | WebSocket server host | 0.0.0.0 |
| WS_PORT | WebSocket server port | 8081 |
| HEALTH_PORT | Health check port | 8082 |
| LOG_LEVEL | Logging level | INFO |
| KNOWLEDGE_BASE_ID | ID of the Bedrock Knowledge Base | required for KB features |
| KNOWLEDGE_BASE_DATA_SOURCE_ID | ID of the KB data source | required for KB features |

## Usage

### Running the WebSocket Server

To start the WebSocket server:

```bash
source .venv/bin/activate
python server.py
```

For agent integration, use the `--agent` flag:
```bash
# To enable MCP client
python server.py --agent mcp

# To enable Strands agent
python server.py --agent strands
```

### Testing the Inline Agent

To test the agent with a query:

```bash
source .venv/bin/activate
./run_inline_agent.sh
```

Example queries:
- "Create a booking for John Doe tomorrow at 3pm for examination"
- "When is John's booking?"
- "Cancel John's booking"
- "What are your cancellation policies?" (uses Knowledge Base)

### Direct API Operations

You can interact with the system programmatically:

```python
from inline_agent import InlineAgentOrchestrator

agent = InlineAgentOrchestrator()
response = agent.invoke("Create a booking for Sarah on Tuesday at 2pm")
print(response)
```

## Booking API

The Booking API supports the following operations:

- `getBooking` - Get a booking by ID
- `createBooking` - Create a new booking
- `updateBooking` - Update an existing booking
- `deleteBooking` - Delete a booking
- `listBookings` - List all bookings
- `findBookingsByCustomer` - Find bookings by customer name

## Troubleshooting

### Common Issues

- **Authentication errors**: Ensure AWS credentials are configured correctly with `aws configure`
- **Missing Lambda ARN**: Run `setup_booking_resources.sh` to create and configure the Lambda function
- **Environment variable issues**: Ensure the `.env` file is properly sourced in your shell
- **Agent selection errors**: Make sure to use `--agent mcp` or `--agent strands` when using those integrations
- **AWS credential errors**: Check that AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are set correctly
- **Knowledge Base errors**: Verify your knowledge base is correctly set up and the IDs are properly configured in your environment

### Logs

- Lambda logs are available in CloudWatch Logs under `/aws/lambda/BookingFunction`
- Bedrock logs can be found in CloudWatch Logs under `bedrock-logs`

## Development

### Adding New Features

1. Update the OpenAPI schema in `booking/booking_openapi.json`
2. Add corresponding handler methods in `booking/booking_lambda.py`
3. Implement any necessary database operations in `booking/booking_db.py`

### Testing

Run the Lambda function locally:

```bash
python -c "from booking.booking_lambda import lambda_handler; print(lambda_handler({'apiPath': '/listBookings'}, {}))"
```

## Security Considerations

- AWS credentials should be kept secure and not hardcoded
- Use the principle of least privilege for IAM roles
- Consider encrypting sensitive data at rest in DynamoDB

## License

This project is licensed under the MIT License - see the LICENSE file for details. 