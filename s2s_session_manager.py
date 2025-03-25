import os
import asyncio
import base64
import json
import uuid
import pyaudio
from bedrock_runtime.client import BedrockRuntime, InvokeModelWithBidirectionalStreamInput
from bedrock_runtime.models import InvokeModelWithBidiStreamInputChunk, BidiInputPayloadPart
from bedrock_runtime.config import Config, HTTPAuthSchemeResolver, SigV4AuthScheme
from smithy_aws_core.credentials_resolvers.environment import EnvironmentCredentialsResolver
from s2s_events import S2sEvent
from datetime import datetime 
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set the logging level
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("s2s-session-manager.log"),  # Log to a file
        logging.StreamHandler()  # Log to the console
    ]
)

# Audio configuration
SAMPLE_RATE = 16000
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK_SIZE = 1024

class S2sSessionManager:
    def __init__(self, model_id='ermis', region='us-east-1'):
        self.model_id = model_id
        self.region = region
        self.client = None
        self.stream = None
        self.is_active = False
        self.prompt_name = str(uuid.uuid4())
        self.content_name = str(uuid.uuid4())
        self.audio_content_name = str(uuid.uuid4())
        self.response_event_queue = asyncio.Queue()
        
    def _initialize_client(self):
        """Initialize the Bedrock client."""
        config = Config(
            endpoint_uri=f"https://bedrock-runtime.{self.region}.amazonaws.com",
            region=self.region,
            aws_credentials_identity_resolver=EnvironmentCredentialsResolver(),
            http_auth_scheme_resolver=HTTPAuthSchemeResolver(),
            http_auth_schemes={"aws.auth#sigv4": SigV4AuthScheme()}
        )
        self.client = BedrockRuntime(config=config)
    
    async def send_event(self, evt):
        """Send an event to the stream."""
        event = InvokeModelWithBidiStreamInputChunk(
            value=BidiInputPayloadPart(bytes_=json.dumps(evt).encode('utf-8'))
        )
        await self.stream.input_stream.send(event)
        logging.debug(">>>>>>" + json.dumps(evt))
    
    async def start_session(self):
        """Start a new session with Nova S2S."""
        if not self.client:
            self._initialize_client()
            
        # Initialize the stream
        self.stream = await self.client.invoke_model_with_bidirectional_stream(
            InvokeModelWithBidirectionalStreamInput(model_id=self.model_id)
        )
        self.is_active = True
        
        # Send session start event
        await self.send_event(S2sEvent.session_start())
        
        # Send prompt start event
        await self.send_event(S2sEvent.prompt_start(self.prompt_name))
        
        # Send system prompt
        await self.send_event(S2sEvent.content_start_text(self.prompt_name, self.content_name))
        
        system_prompt = "You are a helpful assistant. Keep responses brief and conversational."
        await self.send_event(S2sEvent.text_input(self.prompt_name, self.content_name, system_prompt))
        
        await self.send_event(S2sEvent.content_end(self.prompt_name, self.content_name))
        
        # Start processing responses
        asyncio.create_task(self._process_responses())
        logging.debug("Session started")
    
    async def start_audio_input(self):
        """Start audio input stream."""
        await self.send_event(S2sEvent.content_start_audio(self.prompt_name, self.audio_content_name))
    
    async def send_audio_chunk(self, audio_base64):
        """Send an audio chunk to the stream."""
        if not self.is_active:
            return
            
        event = S2sEvent.audio_input(self.prompt_name, self.audio_content_name, audio_base64)
        await self.send_event(event)
    
    async def end_audio_input(self):
        """End audio input stream."""
        await self.send_event(S2sEvent.content_end(self.prompt_name, self.audio_content_name))
    
    async def end_session(self):
        """End the session."""
        if not self.is_active:
            return
            
        await self.send_event(S2sEvent.prompt_end(self.prompt_name))
        await self.send_event(S2sEvent.session_end())
        
        self.is_active = False
        await self.stream.input_stream.close()
    
    async def _process_responses(self):
        logging.debug("start receiving")
        """Process responses from the stream."""
        try:
            while self.is_active:
                output = await self.stream.await_output()
                result = await output[1].receive()
                
                if result.value and result.value.bytes_:
                    response_data = result.value.bytes_.decode('utf-8')
                    event = json.loads(response_data)
                    logging.debug("<<<<<<" + json.dumps(event))
                    
                    if "event" in event:
                        evt = event["event"]
                        evt["timestamp"] = datetime.now().timestamp()
                        if "contentStart" in evt:
                            await self.response_event_queue.put(evt)
                        elif "contentEnd" in evt:
                            await self.response_event_queue.put(evt)
                        elif "textOutput" in evt:
                            await self.response_event_queue.put(evt)
                        elif "audioOutput" in evt:
                            await self.response_event_queue.put(evt)
                        elif "toolUse" in evt:
                            content_id = evt["toolUse"].get("contentId")
                            tool_name = evt["toolUse"].get("toolName")
                            tool_use_id = evt["toolUse"].get("toolUseId")
                            content = json.loads(evt["toolUse"].get("content"))
                            #logging.debug("!!!!",content)
                            if tool_use_id:
                                # Get history
                                #logging.debug(self.reponse_content[content_id])
                                content = self.__handle_tool_use(tool_name, "What are the scaling laws?")
                                if content:
                                    tool_input = S2sEvent.text_input_tool(self.prompt_name, self.tool_content_name, '\n'.join(content))
                                    events = [
                                    S2sEvent.content_start_tool(self.prompt_name, self.tool_content_name, tool_use_id),
                                    tool_input,
                                    S2sEvent.content_end(self.prompt_name, self.tool_content_name)
                                    ]
                                    # send event back to s2s
                                    for event in events:
                                        await self.send_event(event)
        except Exception as e:
            print(f"Error processing responses: {e}")
