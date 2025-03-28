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
import logging
import datetime
import streamlit as st
import streamlit.utils as utils
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Set the logging level
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("nova_s2s_simple.log"),  # Log to a file
        logging.StreamHandler()  # Log to the console
    ]
)

# Audio configuration
SAMPLE_RATE = 16000
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK_SIZE = 1024

class SimpleNovaS2S:
    def __init__(self, model_id='ermis', region='us-east-1'):
        self.model_id = model_id
        self.region = region
        self.client = None
        self.stream = None
        self.is_active = False
        self.prompt_name = str(uuid.uuid4())
        self.content_name = str(uuid.uuid4())
        self.audio_content_name = str(uuid.uuid4())
        self.audio_queue = asyncio.Queue()
        
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
    
    async def send_event(self, event_json):
        """Send an event to the stream."""
        event = InvokeModelWithBidiStreamInputChunk(
            value=BidiInputPayloadPart(bytes_=event_json.encode('utf-8'))
        )
        await self.stream.input_stream.send(event)
        #if "audioInput" not in event_json:
        #    logging.debug(">>>>>" + json.dumps(json.loads(event_json)))
    
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
        session_start = """
        {
          "event": {
            "sessionStart": {
              "inferenceConfiguration": {
                "maxTokens": 1024,
                "topP": 0.95,
                "temperature": 0.7
              }
            }
          }
        }
        """
        await self.send_event(session_start)
        
        # Send prompt start event
        prompt_start = f"""
        {{
          "event": {{
            "promptStart": {{
              "promptName": "{self.prompt_name}",
              "textOutputConfiguration": {{
                "mediaType": "text/plain"
              }},
              "audioOutputConfiguration": {{
                "mediaType": "audio/lpcm",
                "sampleRateHertz": 24000,
                "sampleSizeBits": 16,
                "channelCount": 1,
                "voiceId": "en_us_matthew",
                "encoding": "base64",
                "audioType": "SPEECH"
              }}
            }}
          }}
        }}
        """
        await self.send_event(prompt_start)
        
        # Send system prompt
        text_content_start = f"""
        {{
            "event": {{
                "contentStart": {{
                    "promptName": "{self.prompt_name}",
                    "contentName": "{self.content_name}",
                    "type": "TEXT",
                    "interactive": true,
                    "textInputConfiguration": {{
                        "mediaType": "text/plain"
                    }}
                }}
            }}
        }}
        """
        await self.send_event(text_content_start)
        
        system_prompt = "You are a helpful assistant. Keep responses brief and conversational."
        text_input = f"""
        {{
            "event": {{
                "textInput": {{
                    "promptName": "{self.prompt_name}",
                    "contentName": "{self.content_name}",
                    "content": "{system_prompt}",
                    "role": "SYSTEM"
                }}
            }}
        }}
        """
        await self.send_event(text_input)
        
        text_content_end = f"""
        {{
            "event": {{
                "contentEnd": {{
                    "promptName": "{self.prompt_name}",
                    "contentName": "{self.content_name}"
                }}
            }}
        }}
        """
        await self.send_event(text_content_end)
        
        # Start processing responses
        asyncio.create_task(self._process_responses())
        logging.debug("Session started")
    
    async def start_audio_input(self):
        """Start audio input stream."""
        audio_content_start = f"""
        {{
            "event": {{
                "contentStart": {{
                    "promptName": "{self.prompt_name}",
                    "contentName": "{self.audio_content_name}",
                    "type": "AUDIO",
                    "interactive": true,
                    "audioInputConfiguration": {{
                        "mediaType": "audio/lpcm",
                        "sampleRateHertz": 16000,
                        "sampleSizeBits": 16,
                        "channelCount": 1,
                        "audioType": "SPEECH",
                        "encoding": "base64"
                    }}
                }}
            }}
        }}
        """
        await self.send_event(audio_content_start)
    
    async def send_audio_chunk(self, audio_bytes):
        """Send an audio chunk to the stream."""
        if not self.is_active:
            return
            
        blob = base64.b64encode(audio_bytes)
        audio_event = f"""
        {{
            "event": {{
                "audioInput": {{
                    "promptName": "{self.prompt_name}",
                    "contentName": "{self.audio_content_name}",
                    "content": "{blob.decode('utf-8')}",
                    "role": "USER"
                }}
            }}
        }}
        """
        await self.send_event(audio_event)
    
    async def end_audio_input(self):
        """End audio input stream."""
        audio_content_end = f"""
        {{
            "event": {{
                "contentEnd": {{
                    "promptName": "{self.prompt_name}",
                    "contentName": "{self.audio_content_name}"
                }}
            }}
        }}
        """
        await self.send_event(audio_content_end)
    
    async def end_session(self):
        """End the session."""
        if not self.is_active:
            return
            
        prompt_end = f"""
        {{
            "event": {{
                "promptEnd": {{
                    "promptName": "{self.prompt_name}"
                }}
            }}
        }}
        """
        await self.send_event(prompt_end)
        
        session_end = """
        {
            "event": {
                "sessionEnd": {}
            }
        }
        """
        await self.send_event(session_end)
        
        self.is_active = False
        await self.stream.input_stream.close()
    
    async def _process_responses(self):
        """Process responses from the stream."""
        try:
            while self.is_active:
                output = await self.stream.await_output()
                result = await output[1].receive()
                
                if result.value and result.value.bytes_:
                    response_data = result.value.bytes_.decode('utf-8')
                    json_data = json.loads(response_data)
                    logging.debug("<<<<<<<" + json.dumps(json.loads(response_data)))
                    
                    if 'event' in json_data:
                        # Handle text output
                        if 'textOutput' in json_data['event']:
                            text = json_data['event']['textOutput']['content']
                            role = json_data['event']['textOutput']['role']
                            if role == "ASSISTANT":
                                print(f"Assistant: {text}")
                            elif role == "USER":
                                print(f"User: {text}")
                        
                        # Handle audio output
                        if 'audioOutput' in json_data['event']:
                            audio_content = json_data['event']['audioOutput']['content']
                            audio_bytes = base64.b64decode(audio_content)
                            await self.audio_queue.put(audio_bytes)
        except Exception as e:
            print(f"Error processing responses: {e}")
    
    async def play_audio(self):
        while self.is_active:
            audio_data = await self.audio_queue.get()
            print(">>>>>", audio_data)

async def main():
    # Create Nova S2S client
    nova_client = SimpleNovaS2S()
    
    # Start session
    await nova_client.start_session()
    
    # Start audio capture task
    audio_value = st.audio_input("Click the record icon to start recording, and stop it to send your voice to Nova.")
    if audio_value:
        percent_complete = 0

        progress_text = "Sending audio chunks"
        sent_audio = st.progress(0, text=progress_text)
        for percent_complete in range(100):
            time.sleep(0.01)
            sent_audio.progress(percent_complete + 1, text=progress_text)
        time.sleep(1)

        # Convert the audio to S2S required format
        converted_audio = utils.audio_wav_to_raw(audio_value.read())

        # Convert audio to bytes chunks each up to 1024 bytes
        chunks = [converted_audio[i:i + CHUNK_SIZE] for i in range(0, len(converted_audio), CHUNK_SIZE)]
        # Send chunks
        counter = 0

        await nova_client.start_audio_input()
        #asyncio.sleep(1)
        for chunk in chunks:
            counter += 1
            #base64_str = base64.b64encode(chunk).decode('utf-8')
            await nova_client.send_audio_chunk(chunk)
            await asyncio.sleep(0.01)

            percent_complete = counter/len(chunks)

    
    # Start audio playback task
    playback_task = asyncio.create_task(nova_client.play_audio())

    # Wait for user to press Enter to stop
    #await asyncio.get_event_loop().run_in_executor(None, input)
    
    if st.button("Close session"):
        # End session
        nova_client.is_active = False
        await nova_client.end_session()
        
        # Cancel tasks
        playback_task.cancel()
    
    #print("Session ended")


if __name__ == "__main__":
   st.title("Amazon Nova Sonic (speech to speech)")
 
   asyncio.run(main())