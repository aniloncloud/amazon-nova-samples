import asyncio
import websockets
import json
import base64
import warnings
import uuid
from s2s_events import S2sEvent
from s2s_session_manager import S2sSessionManager
import argparse

from bedrock_runtime.client import BedrockRuntime, InvokeModelWithBidirectionalStreamInput
from bedrock_runtime.models import InvokeModelWithBidiStreamInputChunk, BidiInputPayloadPart
from bedrock_runtime.config import Config, HTTPAuthSchemeResolver, SigV4AuthScheme
from smithy_aws_core.credentials_resolvers.environment import EnvironmentCredentialsResolver


# Suppress warnings
warnings.filterwarnings("ignore")

DEBUG = False

def debug_print(message):
    """Print only if debug mode is enabled"""
    if DEBUG:
        print(message)


async def websocket_handler(websocket):
    """Handle WebSocket connections from the frontend."""
    # Create a new stream manager for this connection
    stream_manager = S2sSessionManager(model_id='ermis', region='us-east-1')
    
    # Initialize the Bedrock stream
    await stream_manager.initialize_stream()
    
    # Start a task to forward responses from Bedrock to the WebSocket
    forward_task = asyncio.create_task(forward_responses(websocket, stream_manager))
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                if 'body' in data:
                    data = json.loads(data["body"])
                if 'event' in data:
                    event_type = list(data['event'].keys())[0]
                    if event_type == "audioInput":
                        debug_print(message[0:180])
                    else:
                        debug_print(message)

                    # Store prompt name and content names if provided
                    if event_type == 'promptStart':
                        stream_manager.prompt_name = data['event']['promptStart']['promptName']
                    elif event_type == 'contentStart' and data['event']['contentStart'].get('type') == 'AUDIO':
                        stream_manager.audio_content_name = data['event']['contentStart']['contentName']
                    
                    # Handle audio input separately
                    if event_type == 'audioInput':
                        # Extract audio data
                        prompt_name = data['event']['audioInput']['promptName']
                        content_name = data['event']['audioInput']['contentName']
                        audio_base64 = data['event']['audioInput']['content']
                        
                        # Add to the audio queue
                        stream_manager.add_audio_chunk(prompt_name, content_name, audio_base64)
                    else:
                        # Send other events directly to Bedrock
                        await stream_manager.send_raw_event(data)
            except json.JSONDecodeError:
                print("Invalid JSON received from WebSocket")
            except Exception as e:
                print(f"Error processing WebSocket message: {e}")
                if DEBUG:
                    import traceback
                    traceback.print_exc()
    except websockets.exceptions.ConnectionClosed:
        print("WebSocket connection closed")
    finally:
        # Clean up
        forward_task.cancel()
        if websocket:
            websocket.close()
        await stream_manager.close()


async def forward_responses(websocket, stream_manager):
    """Forward responses from Bedrock to the WebSocket."""
    try:
        while True:
            # Get next response from the output queue
            response = await stream_manager.output_queue.get()
            
            # Send to WebSocket
            try:
                event = json.dumps(response)
                await websocket.send(event)
            except websockets.exceptions.ConnectionClosed:
                break
    except asyncio.CancelledError:
        # Task was cancelled
        pass
    except Exception as e:
        print(f"Error forwarding responses: {e}")
        # Close connection
        websocket.close()
        stream_manager.close()


async def main(host="localhost", port=8081, debug=False):
    """Main function to run the WebSocket server."""
    global DEBUG
    DEBUG = debug
    
    try:
        # Start WebSocket server
        async with websockets.serve(websocket_handler, host, port):
            print(f"WebSocket server started at ws://{host}:{port}")
            
            # Keep the server running forever
            await asyncio.Future()
    except Exception as ex:
        print("!!!!",ex)
        

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Nova S2S WebSocket Server')
    parser.add_argument('--host', type=str, help='Host name, default localhost')
    parser.add_argument('--port', type=int, help='Host port, default 8081')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()
    
    # Run the main function
    try:
        asyncio.run(main(host=args.host, port=args.port, debug=args.debug))
    except KeyboardInterrupt:
        print("Server stopped by user")
    except Exception as e:
        print(f"Server error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()