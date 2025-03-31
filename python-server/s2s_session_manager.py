import asyncio
import websockets
import json
import base64
import warnings
import uuid
from s2s_events import S2sEvent
import argparse
import websockets
import bedrock_knowledge_bases as kb
import time
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


class S2sSessionManager:
    """Manages bidirectional streaming with AWS Bedrock using asyncio"""
    
    def __init__(self, model_id='ermis', region='us-east-1'):
        """Initialize the stream manager."""
        self.model_id = model_id
        self.region = region
        
        # Audio and output queues
        self.audio_input_queue = asyncio.Queue()
        self.output_queue = asyncio.Queue()
        
        self.response_task = None
        self.stream_response = None
        self.is_active = False
        self.bedrock_client = None
        
        # Session information
        self.prompt_name = None  # Will be set from frontend
        self.content_name = None  # Will be set from frontend
        self.audio_content_name = None  # Will be set from frontend
        self.toolUseContent = ""
        self.toolUseId = ""
        self.toolName = ""

    def _initialize_client(self):
        """Initialize the Bedrock client."""
        config = Config(
            endpoint_uri=f"https://bedrock-runtime.{self.region}.amazonaws.com",
            region=self.region,
            aws_credentials_identity_resolver=EnvironmentCredentialsResolver(),
            http_auth_scheme_resolver=HTTPAuthSchemeResolver(),
            http_auth_schemes={"aws.auth#sigv4": SigV4AuthScheme()}
        )
        self.bedrock_client = BedrockRuntime(config=config)
    
    async def initialize_stream(self):
        """Initialize the bidirectional stream with Bedrock."""
        try:
            if not self.bedrock_client:
                self._initialize_client()
        except Exception as ex:
            self.is_active = False
            print(f"Failed to initialize Bedrock client: {str(e)}")
            raise

        try:
            self.stream_response = await self.bedrock_client.invoke_model_with_bidirectional_stream(
                InvokeModelWithBidirectionalStreamInput(model_id=self.model_id)
            )
            self.is_active = True
            
            # Start listening for responses
            self.response_task = asyncio.create_task(self._process_responses())
            
            # Start processing audio input
            asyncio.create_task(self._process_audio_input())
            
            # Wait a bit to ensure everything is set up
            await asyncio.sleep(0.1)
            
            debug_print("Stream initialized successfully")
            return self
        except Exception as e:
            self.is_active = False
            print(f"Failed to initialize stream: {str(e)}")
            raise
    
    async def send_raw_event(self, event_data):
        try:
            """Send a raw event to the Bedrock stream."""
            if not self.stream_response or not self.is_active:
                debug_print("Stream not initialized or closed")
                return
            
            # Convert to JSON string if it's a dict
            if isinstance(event_data, dict):
                event_json = json.dumps(event_data)
            else:
                event_json = event_data
            
            # Create the event chunk
            event = InvokeModelWithBidiStreamInputChunk(
                value=BidiInputPayloadPart(bytes_=event_json.encode('utf-8'))
            )
        
            await self.stream_response.input_stream.send(event)
            if DEBUG:
                if len(event_json) > 200:
                    if isinstance(event_data, dict):
                        event_type = list(event_data.get("event", {}).keys())
                    else:
                        event_type = list(json.loads(event_json).get("event", {}).keys())
                    debug_print(f"Sent event type: {event_type}")
                else:
                    debug_print(f"Sent event: {event_json}")
        except Exception as e:
            debug_print(f"Error sending event: {str(e)}")
            if DEBUG:
                import traceback
                traceback.print_exc()
    
    async def _process_audio_input(self):
        """Process audio input from the queue and send to Bedrock."""
        while self.is_active:
            try:
                # Get audio data from the queue
                data = await self.audio_input_queue.get()
                
                # Extract data from the queue item
                prompt_name = data.get('prompt_name')
                content_name = data.get('content_name')
                audio_bytes = data.get('audio_bytes')
                
                if not audio_bytes or not prompt_name or not content_name:
                    debug_print("Missing required audio data properties")
                    continue

                # Create the audio input event
                audio_event = S2sEvent.audio_input(prompt_name, content_name, audio_bytes.decode('utf-8') if isinstance(audio_bytes, bytes) else audio_bytes)
                
                # Send the event
                await self.send_raw_event(audio_event)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                debug_print(f"Error processing audio: {e}")
                if DEBUG:
                    import traceback
                    traceback.print_exc()
    
    def add_audio_chunk(self, prompt_name, content_name, audio_data):
        """Add an audio chunk to the queue."""
        # The audio_data is already a base64 string from the frontend
        self.audio_input_queue.put_nowait({
            'prompt_name': prompt_name,
            'content_name': content_name,
            'audio_bytes': audio_data
        })
    
    async def _process_responses(self):
        """Process incoming responses from Bedrock."""
        try:            
            while self.is_active:
                try:
                    output = await self.stream_response.await_output()
                    result = await output[1].receive()
                    if result.value and result.value.bytes_:
                        try:
                            response_data = result.value.bytes_.decode('utf-8')
                            json_data = json.loads(response_data)
                            json_data["timestamp"] = int(time.time() * 1000)  # Milliseconds since epoch
                            
                            # Handle different response types
                            if 'event' in json_data:
                                # Handle tool use detection
                                if 'toolUse' in json_data['event']:
                                    self.toolUseContent = json_data['event']['toolUse']
                                    self.toolName = json_data['event']['toolUse']['toolName']
                                    self.toolUseId = json_data['event']['toolUse']['toolUseId']
                                    debug_print(f"Tool use detected: {self.toolName}, ID: {self.toolUseId}, "+ json.dumps(json_data['event']))
                                
                                # Process tool use when content ends
                                elif 'contentEnd' in json_data['event'] and json_data['event'].get('contentEnd', {}).get('type') == 'TOOL':
                                    debug_print("Processing tool use and sending result")
                                    toolResult = await self.processToolUse(self.toolName, self.toolUseContent)
                                    
                                    # Send tool start event
                                    toolContent = str(uuid.uuid4())
                                    tool_start_event = S2sEvent.content_start_tool(self.prompt_name, toolContent, self.toolUseId)
                                    await self.send_raw_event(tool_start_event)
                                    
                                    # Send tool result event
                                    if isinstance(toolResult, dict):
                                        content_json_string = json.dumps(toolResult)
                                    else:
                                        content_json_string = toolResult

                                    tool_result_event = S2sEvent.text_input_tool(self.prompt_name, toolContent, content_json_string)
                                    await self.send_raw_event(tool_result_event)
                                    
                                    # Send tool content end event
                                    tool_content_end_event = S2sEvent.content_end(self.prompt_name, toolContent)
                                    await self.send_raw_event(tool_content_end_event)
                            
                            # Put the response in the output queue for forwarding to the frontend
                            await self.output_queue.put(json_data)
                        except json.JSONDecodeError:
                            await self.output_queue.put({"raw_data": response_data})
                except StopAsyncIteration:
                    # Stream has ended
                    break
                except Exception as e:
                   # Handle ValidationException properly
                    if "ValidationException" in str(e):
                        error_message = str(e)
                        print(f"Validation error: {error_message}")
                    else:
                        print(f"Error receiving response: {e}")
                    break
                    
        except Exception as e:
            print(f"Response processing error: {e}")
        finally:
            self.is_active = False

    async def processToolUse(self, toolName, toolUseContent):
        """Return the tool result"""
        print(f"Tool Use Content: {toolUseContent}")

        query = None
        if 'content' in toolUseContent:
            # Parse the JSON string in the content field
            query_json = json.loads(toolUseContent.get("content"))
            query = query_json.get("query", "")
            print(f"Extracted query: {query}")
        
        if toolName == "getKbTool":
            results = kb.retrieve_kb(query)
            #print("///",results)
            return { "result": results}
        if toolName == "getDateTool":
            from datetime import datetime, timezone
            return {"result":  datetime.now(timezone.utc).strftime('%A, %Y-%m-%d')}
        
        if toolName == "getTravelPolicyTool":
            return {"result": "Travel with pet is not allowed at the XYZ airline."}

        return {}
    
    async def close(self):
        """Close the stream properly."""
        if not self.is_active:
            return
            
        self.is_active = False
        
        if self.stream_response:
            await self.stream_response.input_stream.close()
        
        if self.response_task and not self.response_task.done():
            self.response_task.cancel()
            try:
                await self.response_task
            except asyncio.CancelledError:
                pass
