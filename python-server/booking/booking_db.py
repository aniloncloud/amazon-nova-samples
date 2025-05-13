# booking_db.py
# NOTE: Environment variables are loaded from the .env file in the root of python-server.
import boto3
import os
import logging
from botocore.exceptions import ClientError
import json
import uuid
import time
import random
import string

# Configure logging
logger = logging.getLogger("booking_db")
logger.setLevel(logging.INFO)

class BookingDB:
    """Class to handle DynamoDB operations for booking details."""
    
    def __init__(self, table_name=None, region=None):
        """
        Initialize the DynamoDB client and table.
        
        Args:
            table_name (str, optional): Name of the DynamoDB table. Defaults to env var TABLE_NAME or 'Bookings'.
            region (str, optional): AWS region. Defaults to env var AWS_REGION or 'us-east-1'.
        """
        self.table_name = table_name or os.getenv("TABLE_NAME", "Bookings")
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self.dynamodb = boto3.resource('dynamodb', region_name=self.region)
        self.client = boto3.client('dynamodb', region_name=self.region)
        self.table = None
        self.max_retries = int(os.getenv("DYNAMODB_MAX_RETRIES", "3"))
        
        logger.info(f"Initialized BookingDB with table_name={self.table_name}, region={self.region}")
        
    def ensure_table_exists(self):
        """
        Ensure the DynamoDB table exists, create it if it doesn't.
        
        Returns:
            bool: True if table exists or was created successfully, False otherwise.
        """
        if self.table:
            return True
            
        try:
            # Check if table exists
            trace_id = f"ensure-table-{uuid.uuid4().hex[:8]}"
            logger.info(f"[{trace_id}] Checking if table {self.table_name} exists")
            
            tables = self.client.list_tables()
            
            if self.table_name not in tables.get('TableNames', []):
                logger.info(f"[{trace_id}] Creating DynamoDB table: {self.table_name}")
                
                # Create the table
                table = self.dynamodb.create_table(
                    TableName=self.table_name,
                    KeySchema=[
                        {
                            'AttributeName': 'booking_id',
                            'KeyType': 'HASH'  # Partition key
                        }
                    ],
                    AttributeDefinitions=[
                        {
                            'AttributeName': 'booking_id',
                            'AttributeType': 'S'
                        }
                    ],
                    ProvisionedThroughput={
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                )
                
                # Wait for the table to be created
                logger.info(f"[{trace_id}] Waiting for table {self.table_name} to be created")
                table.meta.client.get_waiter('table_exists').wait(TableName=self.table_name)
                logger.info(f"[{trace_id}] Table {self.table_name} created successfully")
            else:
                logger.info(f"[{trace_id}] Table {self.table_name} already exists")
            
            # Get the table reference
            self.table = self.dynamodb.Table(self.table_name)
            return True
            
        except ClientError as e:
            logger.error(f"[{trace_id}] Error ensuring table exists: {str(e)}", exc_info=True)
            return False
    
    def get_booking(self, booking_id):
        """
        Get booking details by booking ID.
        
        Args:
            booking_id (str): The ID of the booking to retrieve.
            
        Returns:
            dict: Booking details or error message.
        """
        trace_id = f"get-booking-{uuid.uuid4().hex[:8]}"
        logger.info(f"[{trace_id}] Getting booking with ID: {booking_id}")
        
        if not self.table:
            if not self.ensure_table_exists():
                return {"error": "Failed to ensure table exists"}
        
        try:
            for attempt in range(self.max_retries):
                try:
                    response = self.table.get_item(
                        Key={
                            'booking_id': booking_id
                        }
                    )
                    
                    if 'Item' in response:
                        logger.info(f"[{trace_id}] Found booking with ID: {booking_id}")
                        return response['Item']
                    else:
                        logger.info(f"[{trace_id}] No booking found with ID: {booking_id}")
                        return {"message": f"No booking found with ID: {booking_id}"}
                        
                except ClientError as e:
                    if attempt < self.max_retries - 1 and self._is_retryable_error(e):
                        wait_time = (2 ** attempt) * 0.1  # Exponential backoff
                        logger.warning(f"[{trace_id}] Retryable error getting booking, attempt {attempt+1}/{self.max_retries}: {str(e)}")
                        time.sleep(wait_time)
                    else:
                        raise
                        
        except Exception as e:
            logger.error(f"[{trace_id}] Error getting booking: {str(e)}", exc_info=True)
            return {"error": str(e)}
    
    def _generate_booking_id(self):
        """Generate a 5-digit alphanumeric booking ID."""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    
    def create_booking(self, booking_details):
        """
        Create a new booking.
        
        Args:
            booking_details (dict): Details of the booking to create.
            
        Returns:
            dict: Success message with booking ID or error message.
        """
        trace_id = f"create-booking-{uuid.uuid4().hex[:8]}"
        logger.info(f"[{trace_id}] Creating new booking")
        
        if not self.table:
            if not self.ensure_table_exists():
                return {"error": "Failed to ensure table exists"}
        
        try:
            # Always generate a new booking ID for new bookings
            booking_details['booking_id'] = self._generate_booking_id()
            
            logger.info(f"[{trace_id}] Creating booking with ID: {booking_details['booking_id']}")
            
            # Put the item in the table
            self.table.put_item(Item=booking_details)
            
            logger.info(f"[{trace_id}] Booking created successfully: {booking_details['booking_id']}")
            return {
                "message": "Booking created successfully",
                "booking_id": booking_details['booking_id'],
                "booking": booking_details
            }
                
        except ClientError as e:
            logger.error(f"[{trace_id}] Error creating booking: {str(e)}", exc_info=True)
            return {"error": str(e)}
    
    def update_booking(self, booking_id, update_data):
        """
        Update an existing booking.
        
        Args:
            booking_id (str): The ID of the booking to update.
            update_data (dict): The data to update.
            
        Returns:
            dict: Success message with updated attributes or error message.
        """
        trace_id = f"update-booking-{uuid.uuid4().hex[:8]}"
        logger.info(f"[{trace_id}] Updating booking with ID: {booking_id}")
        
        if not self.table:
            if not self.ensure_table_exists():
                return {"error": "Failed to ensure table exists"}
        
        try:
            # Verify the booking exists
            existing = self.get_booking(booking_id)
            if "error" in existing or "message" in existing:
                logger.warning(f"[{trace_id}] Cannot update non-existent booking: {booking_id}")
                return {"error": f"Booking with ID {booking_id} not found"}
            
            # Build the update expression and attribute values
            update_expression = "SET "
            expression_attribute_values = {}
            
            for key, value in update_data.items():
                if key != 'booking_id':  # Skip the primary key
                    update_expression += f"{key} = :{key}, "
                    expression_attribute_values[f":{key}"] = value
            
            # Remove the trailing comma and space
            update_expression = update_expression[:-2]
            
            logger.info(f"[{trace_id}] Update expression: {update_expression}")
            logger.info(f"[{trace_id}] Expression attribute values: {json.dumps(expression_attribute_values)}")
            
            # Update the item
            response = self.table.update_item(
                Key={
                    'booking_id': booking_id
                },
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_attribute_values,
                ReturnValues="UPDATED_NEW"
            )
            
            logger.info(f"[{trace_id}] Booking updated successfully: {booking_id}")
            return {
                "message": "Booking updated successfully",
                "booking_id": booking_id,
                "updated_attributes": response.get('Attributes', {})
            }
                
        except ClientError as e:
            logger.error(f"[{trace_id}] Error updating booking: {str(e)}", exc_info=True)
            return {"error": str(e)}
    
    def delete_booking(self, booking_id):
        """
        Delete a booking.
        
        Args:
            booking_id (str): The ID of the booking to delete.
            
        Returns:
            dict: Success message or error message.
        """
        trace_id = f"delete-booking-{uuid.uuid4().hex[:8]}"
        logger.info(f"[{trace_id}] Deleting booking with ID: {booking_id}")
        
        if not self.table:
            if not self.ensure_table_exists():
                return {"error": "Failed to ensure table exists"}
        
        try:
            # Verify the booking exists
            existing = self.get_booking(booking_id)
            if "error" in existing or "message" in existing:
                logger.warning(f"[{trace_id}] Cannot delete non-existent booking: {booking_id}")
                return {"error": f"Booking with ID {booking_id} not found"}
            
            # Delete the item
            self.table.delete_item(
                Key={
                    'booking_id': booking_id
                }
            )
            
            logger.info(f"[{trace_id}] Booking deleted successfully: {booking_id}")
            return {
                "message": f"Booking {booking_id} deleted successfully"
            }
                
        except ClientError as e:
            logger.error(f"[{trace_id}] Error deleting booking: {str(e)}", exc_info=True)
            return {"error": str(e)}
    
    def list_bookings(self, limit=10):
        """
        List all bookings, with optional limit.
        
        Args:
            limit (int, optional): Maximum number of bookings to return. Defaults to 10.
            
        Returns:
            dict: List of bookings, count, and scanned count or error message.
        """
        trace_id = f"list-bookings-{uuid.uuid4().hex[:8]}"
        logger.info(f"[{trace_id}] Listing bookings with limit: {limit}")
        
        if not self.table:
            if not self.ensure_table_exists():
                return {"error": "Failed to ensure table exists"}
        
        try:
            response = self.table.scan(Limit=limit)
            
            result = {
                "bookings": response.get('Items', []),
                "count": len(response.get('Items', [])),
                "scanned_count": response.get('ScannedCount', 0)
            }
            
            logger.info(f"[{trace_id}] Found {result['count']} bookings")
            return result
                
        except ClientError as e:
            logger.error(f"[{trace_id}] Error listing bookings: {str(e)}", exc_info=True)
            return {"error": str(e)}
            
    def find_bookings_by_customer(self, customer_name):
        """
        Find bookings by customer name (case-insensitive substring match).
        
        Args:
            customer_name (str): The customer name to search for.
            
        Returns:
            dict: List of matching bookings, count, and scanned count or error message.
        """
        trace_id = f"find-bookings-{uuid.uuid4().hex[:8]}"
        logger.info(f"[{trace_id}] Searching for bookings with customer name: '{customer_name}'")
        
        if not self.table:
            if not self.ensure_table_exists():
                return {"error": "Failed to ensure table exists"}
        try:
            # Convert customer name to lowercase for case-insensitive search
            search_name = customer_name.lower()
            
            # Scan all items in the table
            response = self.table.scan()
            all_items = response.get('Items', [])
            
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"[{trace_id}] All bookings in table: {json.dumps(all_items, indent=2)}")
            
            # Filter items manually for more flexible matching
            matching_bookings = []
            for item in all_items:
                if 'customer_name' in item:
                    db_name = item['customer_name'].lower()
                    if search_name in db_name or db_name in search_name:
                        matching_bookings.append(item)
                        logger.info(f"[{trace_id}] Found matching booking: {item['booking_id']} for {item['customer_name']}")
            
            result = {
                "bookings": matching_bookings,
                "count": len(matching_bookings),
                "scanned_count": response.get('ScannedCount', 0)
            }
            
            logger.info(f"[{trace_id}] Found {result['count']} bookings matching '{customer_name}'")
            return result
            
        except ClientError as e:
            logger.error(f"[{trace_id}] Error finding bookings by customer: {str(e)}", exc_info=True)
            return {"error": str(e)}
    
    def _is_retryable_error(self, error):
        """
        Check if an error is retryable.
        
        Args:
            error (Exception): The error to check.
            
        Returns:
            bool: True if the error is retryable, False otherwise.
        """
        error_code = getattr(error, 'response', {}).get('Error', {}).get('Code', '')
        return error_code in [
            'ProvisionedThroughputExceededException',
            'ThrottlingException',
            'RequestLimitExceeded',
            'InternalServerError'
        ]

    def update_bookings_by_customer(self, customer_name, update_data):
        """
        Update all bookings for a given customer name.
        Args:
            customer_name (str): The customer name to search for.
            update_data (dict): The data to update in each booking.
        Returns:
            dict: Summary of updates performed.
        """
        bookings = self.find_bookings_by_customer(customer_name).get('bookings', [])
        results = []
        for booking in bookings:
            booking_id = booking['booking_id']
            result = self.update_booking(booking_id, update_data)
            results.append(result)
        return {
            "message": f"Updated {len(results)} bookings for customer '{customer_name}'",
            "results": results
        }

    def get_latest_booking_by_customer(self, customer_name):
        """Get the latest booking for a customer by booking_date (if available)."""
        bookings = self.find_bookings_by_customer(customer_name).get('bookings', [])
        if not bookings:
            return None
        # Sort by booking_date if available, else return the first
        bookings = sorted(bookings, key=lambda b: b.get('booking_date', ''), reverse=True)
        return bookings[0]

    def delete_booking_by_customer(self, customer_name):
        """Delete the latest booking for a customer."""
        booking = self.get_latest_booking_by_customer(customer_name)
        if not booking:
            return {"error": f"No booking found for customer {customer_name}"}
        return self.delete_booking(booking['booking_id'])

    def update_booking_by_customer(self, customer_name, update_data):
        """Update the latest booking for a customer."""
        booking = self.get_latest_booking_by_customer(customer_name)
        if not booking:
            return {"error": f"No booking found for customer {customer_name}"}
        return self.update_booking(booking['booking_id'], update_data)

# Singleton instance for reuse
booking_db = None

def get_booking_db():
    """
    Get the singleton instance of BookingDB.
    
    Returns:
        BookingDB: A singleton instance of the BookingDB class.
    """
    global booking_db
    if booking_db is None:
        booking_db = BookingDB()
    return booking_db
