# booking_db.py
# NOTE: Environment variables are loaded from the .env file in the root of python-server.
import boto3
import os
import logging
from botocore.exceptions import ClientError
import random
import string

# Configure logging
logger = logging.getLogger("booking_db")
logger.setLevel(logging.INFO)

class BookingDB:
    """Class to handle DynamoDB operations for booking details."""
    
    def __init__(self, table_name=None, region=None):
        """Initialize the DynamoDB client and table."""
        self.table_name = table_name or os.getenv("TABLE_NAME", "Bookings")
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self.dynamodb = boto3.resource('dynamodb', region_name=self.region)
        self.table = self.dynamodb.Table(self.table_name)
        logger.info(f"Initialized BookingDB with table_name={self.table_name}")
    
    def _generate_booking_id(self):
        """Generate a 5-digit alphanumeric booking ID."""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    
    def get_booking(self, booking_id):
        """Get booking details by booking ID."""
        try:
            response = self.table.get_item(
                Key={'booking_id': booking_id}
            )
            
            if 'Item' in response:
                return response['Item']
            else:
                return {"message": f"No booking found with ID: {booking_id}"}
                
        except ClientError as e:
            logger.error(f"Error getting booking {booking_id}: {str(e)}")
            return {"error": str(e)}
    
    def create_booking(self, booking_details):
        """Create a new booking."""
        try:
            booking_details['booking_id'] = self._generate_booking_id()
            
            self.table.put_item(Item=booking_details)
            
            logger.info(f"Booking created: {booking_details['booking_id']}")
            return {
                "message": "Booking created successfully",
                "booking_id": booking_details['booking_id'],
                "booking": booking_details
            }
                
        except ClientError as e:
            logger.error(f"Error creating booking: {str(e)}")
            return {"error": str(e)}
    
    def update_booking(self, booking_id, update_data):
        """Update an existing booking."""
        try:
            # Verify the booking exists
            existing = self.get_booking(booking_id)
            if "error" in existing or "message" in existing:
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
            
            # Update the item
            response = self.table.update_item(
                Key={'booking_id': booking_id},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_attribute_values,
                ReturnValues="UPDATED_NEW"
            )
            
            logger.info(f"Booking updated: {booking_id}")
            return {
                "message": "Booking updated successfully",
                "booking_id": booking_id,
                "updated_attributes": response.get('Attributes', {})
            }
                
        except ClientError as e:
            logger.error(f"Error updating booking {booking_id}: {str(e)}")
            return {"error": str(e)}
    
    def delete_booking(self, booking_id):
        """Delete a booking."""
        try:
            # Verify the booking exists
            existing = self.get_booking(booking_id)
            if "error" in existing or "message" in existing:
                return {"error": f"Booking with ID {booking_id} not found"}
            
            # Delete the item
            self.table.delete_item(
                Key={'booking_id': booking_id}
            )
            
            logger.info(f"Booking deleted: {booking_id}")
            return {
                "message": f"Booking {booking_id} deleted successfully"
            }
                
        except ClientError as e:
            logger.error(f"Error deleting booking {booking_id}: {str(e)}")
            return {"error": str(e)}
    
    def list_bookings(self, limit=10):
        """List all bookings, with optional limit."""
        try:
            response = self.table.scan(Limit=limit)
            
            result = {
                "bookings": response.get('Items', []),
                "count": len(response.get('Items', [])),
                "scanned_count": response.get('ScannedCount', 0)
            }
            
            logger.info(f"Listed {result['count']} bookings")
            return result
                
        except ClientError as e:
            logger.error(f"Error listing bookings: {str(e)}")
            return {"error": str(e)}
            
    def find_bookings_by_customer(self, customer_name):
        """Find bookings by customer name (case-insensitive substring match)."""
        try:
            # Convert customer name to lowercase for case-insensitive search
            search_name = customer_name.lower()
            
            # Scan all items in the table
            response = self.table.scan()
            all_items = response.get('Items', [])
            
            # Filter items manually for more flexible matching
            matching_bookings = []
            for item in all_items:
                if 'customer_name' in item:
                    db_name = item['customer_name'].lower()
                    if search_name in db_name or db_name in search_name:
                        matching_bookings.append(item)
            
            result = {
                "bookings": matching_bookings,
                "count": len(matching_bookings),
                "scanned_count": response.get('ScannedCount', 0)
            }
            
            logger.info(f"Found {result['count']} bookings matching '{customer_name}'")
            return result
            
        except ClientError as e:
            logger.error(f"Error finding bookings by customer: {str(e)}")
            return {"error": str(e)}

    def get_latest_booking_by_customer(self, customer_name):
        """Get the latest booking for a customer by booking_date (if available)."""
        bookings = self.find_bookings_by_customer(customer_name).get('bookings', [])
        if not bookings:
            return None
        # Sort by booking_date if available, else return the first
        bookings = sorted(bookings, key=lambda b: b.get('booking_date', ''), reverse=True)
        return bookings[0]

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
        
        logger.info(f"Updated {len(results)} bookings for customer '{customer_name}'")
        return {
            "message": f"Updated {len(results)} bookings for customer '{customer_name}'",
            "results": results
        }

    def delete_booking_by_customer(self, customer_name):
        """Delete the latest booking for a customer."""
        booking = self.get_latest_booking_by_customer(customer_name)
        if not booking:
            return {"error": f"No booking found for customer {customer_name}"}
        
        result = self.delete_booking(booking['booking_id'])
        logger.info(f"Deleted latest booking for customer '{customer_name}'")
        return result

    def update_booking_by_customer(self, customer_name, update_data):
        """Update the latest booking for a customer."""
        booking = self.get_latest_booking_by_customer(customer_name)
        if not booking:
            return {"error": f"No booking found for customer {customer_name}"}
        
        result = self.update_booking(booking['booking_id'], update_data)
        logger.info(f"Updated latest booking for customer '{customer_name}'")
        return result

# Singleton instance for reuse
booking_db = None

def get_booking_db():
    """Get the singleton instance of BookingDB."""
    global booking_db
    if booking_db is None:
        booking_db = BookingDB()
    return booking_db
