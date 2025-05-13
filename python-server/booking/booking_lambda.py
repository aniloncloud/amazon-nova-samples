import json
import logging
import uuid
import os
import traceback
from http import HTTPStatus
from booking.booking_db import get_booking_db  # Assume this exists

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# NOTE: Environment variables are loaded from the .env file in the root of python-server.

class BookingLambda:
    """
    Handler for booking operations in AWS Lambda.
    Provides an interface between Bedrock Agent API and the booking database.
    """
    
    def __init__(self):
        """Initialize the BookingLambda with a database connection."""
        self.db = get_booking_db()
        
    def handle_request(self, event):
        """
        Main entry point for Lambda handler. Processes incoming events from Bedrock.
        
        Args:
            event (dict): The Lambda event containing the Bedrock agent request.
            
        Returns:
            dict: Response formatted for Bedrock agent.
        """
        try:
            logger.info(f"Received event: {json.dumps(event)}")
            
            # Extract action group, function name, and HTTP method
            action_group = event.get('actionGroup')
            http_method = event.get('httpMethod')
            
            # Extract function name from apiPath (remove leading slash)
            api_path = event.get('apiPath', '')
            function = api_path.lstrip('/') if api_path else None
            
            # If function is still None, try to get it from the function field
            if not function:
                function = event.get('function')
                
            # Get parameters from both the top-level parameters array and the requestBody
            parameters = self._extract_parameters(event)
            
            logger.info(f"Action Group: {action_group}, Function: {function}, HTTP Method: {http_method}, Params: {parameters}")
            
            if not function:
                return self._error_response("No function or apiPath specified in the request")
            
            # Map function name to method
            handler = getattr(self, function, None)
            if not handler:
                return self._error_response(f"Unsupported function: {function}")
            
            # Call the handler and log the result
            logger.info(f"Calling handler for function: {function}")
            result = handler(parameters)
            logger.info(f"Handler result before formatting: {json.dumps(result) if isinstance(result, dict) else result}")
            
            # Format the response for Bedrock agent
            response = self._format_response(action_group, function, result, http_method)
            return response
            
        except Exception as e:
            logger.error(f"Error handling request: {str(e)}", exc_info=True)
            return self._error_response(str(e), HTTPStatus.INTERNAL_SERVER_ERROR)

    def _extract_parameters(self, event):
        """
        Extract parameters from both the top-level parameters array and the requestBody.
        
        Args:
            event (dict): The Lambda event.
            
        Returns:
            list: Combined parameters.
        """
        parameters = event.get('parameters', [])
        
        # Extract parameters from requestBody if present
        if 'requestBody' in event and 'content' in event['requestBody']:
            content = event['requestBody']['content']
            if 'application/json' in content and 'properties' in content['application/json']:
                request_body_params = content['application/json']['properties']
                # Merge parameters from requestBody with top-level parameters
                parameters.extend(request_body_params)
                
        return parameters

    # BOOKING API OPERATION HANDLERS
    # Each handler must match an OpenAPI operationId exactly
    
    def getBooking(self, parameters):
        """
        Get details for a specific booking by ID.
        
        Args:
            parameters (list): List of parameter objects, must include booking_id.
            
        Returns:
            dict: Booking details or error.
        """
        booking_id = self._get_param(parameters, 'booking_id')
        if not booking_id:
            return {'error': "Missing required parameter: booking_id"}
            
        return self.db.get_booking(booking_id)
        
    def findBookingsByCustomer(self, parameters):
        """
        Find bookings by customer name (case-insensitive substring match).
        
        Args:
            parameters (list): List of parameter objects, must include customer_name.
            
        Returns:
            dict: List of matching bookings or error.
        """
        customer_name = self._get_param(parameters, 'customer_name')
        logger.info(f"Finding bookings for customer: '{customer_name}'")
        
        if not customer_name:
            logger.warning("Missing required parameter: customer_name")
            return {'error': "Missing required parameter: customer_name"}
            
        result = self.db.find_bookings_by_customer(customer_name)
        logger.info(f"Find bookings result: {json.dumps(result)}")
        
        # Always return the full result object (bookings, count, scanned_count)
        return result

    def createBooking(self, parameters):
        """
        Create a new booking. Only customer_name is required; other fields are optional.
        """
        customer_name = self._get_param(parameters, 'customer_name')
        if not customer_name:
            return {'error': "Missing required parameter: customer_name"}
        booking_date = self._get_param(parameters, 'booking_date', '')
        service_type = self._get_param(parameters, 'service_type', '')
        status = self._get_param(parameters, 'status', 'pending')
        notes = self._get_param(parameters, 'notes', '')
        return self.db.create_booking({
            'customer_name': customer_name,
            'booking_date': booking_date,
            'service_type': service_type,
            'status': status,
            'notes': notes
        })

    def updateBooking(self, parameters):
        """
        Update an existing booking by customer name (preferred) or booking_id.
        If multiple bookings exist for the customer, return them for clarification.
        """
        booking_id = self._get_param(parameters, 'booking_id')
        customer_name = self._get_param(parameters, 'customer_name')
        updates = {p['name']: p['value'] for p in parameters if p['name'] not in ['booking_id', 'customer_name']}
        
        if booking_id:
            return self.db.update_booking(booking_id, updates)
        elif customer_name:
            bookings = self.db.find_bookings_by_customer(customer_name).get('bookings', [])
            if not bookings:
                return {'error': f"No bookings found for {customer_name}"}
            if len(bookings) > 1:
                return {'error': f"Multiple bookings found for {customer_name}. Please specify more details.", 'bookings': bookings}
            return self.db.update_booking(bookings[0]['booking_id'], updates)
        else:
            return {'error': "Missing required parameter: booking_id or customer_name"}

    def deleteBooking(self, parameters):
        """
        Delete a booking by customer name (preferred) or booking_id.
        If multiple bookings exist for the customer, return them for clarification.
        """
        booking_id = self._get_param(parameters, 'booking_id')
        customer_name = self._get_param(parameters, 'customer_name')
        if booking_id:
            return self.db.delete_booking(booking_id)
        elif customer_name:
            bookings = self.db.find_bookings_by_customer(customer_name).get('bookings', [])
            if not bookings:
                return {'error': f"No bookings found for {customer_name}"}
            if len(bookings) > 1:
                return {'error': f"Multiple bookings found for {customer_name}. Please specify more details.", 'bookings': bookings}
            return self.db.delete_booking(bookings[0]['booking_id'])
        else:
            return {'error': "Missing required parameter: booking_id or customer_name"}

    def listBookings(self, parameters):
        """
        List all bookings with optional limit.
        
        Args:
            parameters (list): List of parameter objects, may include limit.
            
        Returns:
            dict: List of bookings or error.
        """
        limit = int(self._get_param(parameters, 'limit', 10))
        logger.info(f"Listing all bookings with limit: {limit}")
        
        result = self.db.list_bookings(limit)
        logger.info(f"List bookings result: {json.dumps(result)}")
        
        return result

    # HELPER METHODS
    
    def _get_param(self, parameters, name, default=None):
        """
        Get parameter value by name from parameters list.
        
        Args:
            parameters (list): List of parameter objects.
            name (str): Name of parameter to find.
            default: Default value if parameter not found.
            
        Returns:
            Value of parameter or default.
        """
        return next((p['value'] for p in parameters if p['name'] == name), default)

    def _format_response(self, action_group, function, result, http_method):
        """
        Format the response for Bedrock agent.
        
        Args:
            action_group (str): Action group name.
            function (str): Function name.
            result (dict/str): Result from handler.
            http_method (str): HTTP method.
            
        Returns:
            dict: Formatted response.
        """
        # Generate a trace ID for debugging
        trace_id = f"trace-{function}-{uuid.uuid4().hex[:8]}"
        logger.info(f"[{trace_id}] Formatting response for function: {function}")
        logger.info(f"[{trace_id}] Raw result from handler: {json.dumps(result) if isinstance(result, dict) else result}")
        
        # Format according to Bedrock agent's expectations
        if isinstance(result, dict):
            body = json.dumps(result)
        else:
            body = result
            
        # Create response in the exact format Bedrock expects
        response = {
            "messageVersion": "1.0",
            "response": {
                "actionGroup": action_group,
                "apiPath": f"/{function}",
                "httpMethod": http_method,
                "httpStatusCode": 200,
                "responseBody": {
                    "application/json": {
                        "body": body
                    }
                }
            }
        }
            
        logger.info(f"[{trace_id}] Final formatted response: {json.dumps(response)}")
        logger.info(f"[{trace_id}] Final response body: {body}")
        return response

    def _error_response(self, message, code=HTTPStatus.BAD_REQUEST):
        """
        Create an error response.
        
        Args:
            message (str): Error message.
            code (HTTPStatus): HTTP status code.
            
        Returns:
            dict: Error response.
        """
        error_id = uuid.uuid4().hex[:8]
        logger.error(f"[error-{error_id}] {message}")
        
        return {
            'statusCode': code,
            'body': json.dumps({'error': message, 'error_id': error_id})
        }


# Singleton instance
booking_lambda = BookingLambda()

def lambda_handler(event, context):
    """
    Lambda handler function.
    
    Args:
        event (dict): Lambda event.
        context (LambdaContext): Lambda context.
        
    Returns:
        dict: Response for Bedrock agent.
    """
    try:
        return booking_lambda.handle_request(event)
    except Exception as e:
        logger.error(f"Unhandled exception in lambda_handler: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal server error',
                'error_id': uuid.uuid4().hex[:8],
                'message': str(e)
            })
        }
