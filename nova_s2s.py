import os
import asyncio
import base64
import json
import uuid
import warnings
import pyaudio
from rx.subject import Subject
from rx import operators as ops
from rx.scheduler.eventloop import AsyncIOScheduler
from bedrock_runtime.client import BedrockRuntime, InvokeModelWithBidirectionalStreamInput
from bedrock_runtime.models import InvokeModelWithBidiStreamInputChunk, BidiInputPayloadPart
from bedrock_runtime.config import Config, HTTPAuthSchemeResolver, SigV4AuthScheme
from smithy_aws_core.credentials_resolvers.environment import EnvironmentCredentialsResolver

# Suppress warnings
warnings.filterwarnings("ignore")

# Audio configuration
SAMPLE_RATE = 16000
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK_SIZE = 1024  # Number of frames per buffer

# Debug mode flag
DEBUG = False

def debug_print(message):
    """Print only if debug mode is enabled"""
    if DEBUG:
        print(message)

class BedrockStreamManager:
    """Manages bidirectional streaming with AWS Bedrock using RxPy for event processing"""
    
    # Event templates
    START_SESSION_EVENT = """
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
    
    START_PROMPT_EVENT = """
        {
          "event": {
            "promptStart": {
              "promptName": "%s",
              "textOutputConfiguration": {
                "mediaType": "text/plain"
              },
              "audioOutputConfiguration": {
                "mediaType": "audio/lpcm",
                "sampleRateHertz": 24000,
                "sampleSizeBits": 16,
                "channelCount": 1,
                "voiceId": "en_us_matthew",
                "encoding": "base64",
                "audioType": "SPEECH"
              },
              "toolUseOutputConfiguration": {
                "mediaType": "application/json"
              },
              "toolConfiguration": {
                "tools": []
              }
            }
          }
        }
    """
    
    CONTENT_START_EVENT = """
    {
        "event": {
            "contentStart": {
                "promptName": "%s",
                "contentName": "%s",
                "type": "AUDIO",
                "interactive": true,
                "audioInputConfiguration": {
                    "mediaType": "audio/lpcm",
                    "sampleRateHertz": 16000,
                    "sampleSizeBits": 16,
                    "channelCount": 1,
                    "audioType": "SPEECH",
                    "encoding": "base64"
                }
            }
        }
    }
    """
    
    AUDIO_EVENT_TEMPLATE = """
      {
        "event": {
          "audioInput": {
            "promptName": "%s",
            "contentName": "%s",
            "content": "%s",
            "role": "USER"
          }
        }
      }
    """
    
    TEXT_CONTENT_START_EVENT = """
    {
        "event": {
            "contentStart": {
                "promptName": "%s",
                "contentName": "%s",
                "type": "TEXT",
                "interactive": true,
                "textInputConfiguration": {
                    "mediaType": "text/plain"
                }
            }
        }
    }
    """
    
    TEXT_INPUT_EVENT = """
    {
        "event": {
            "textInput": {
                "promptName": "%s",
                "contentName": "%s",
                "content": "%s",
                "role": "%s"
            }
        }
    }
    """
    
    CONTENT_END_EVENT = """
    {
        "event": {
            "contentEnd": {
                "promptName": "%s",
                "contentName": "%s"
            }
        }
    }
    """

    PROMPT_END_EVENT = """
    {
        "event": {
            "promptEnd": {
                "promptName": "%s"
            }
        }
    }
    """

    SESSION_END_EVENT = """
    {
        "event": {
            "sessionEnd": {}
        }
    }
    """

    def __init__(self, model_id='ermis', region='us-east-1'):
        """Initialize the stream manager."""
        self.model_id = model_id
        self.region = region
        self.input_subject = Subject()
        self.output_subject = Subject()
        self.audio_subject = Subject()
        
        self.response_task = None
        self.stream_response = None
        self.is_active = False
        self.bedrock_client = None
        self.scheduler = None
        
        # Audio playback components
        self.audio_output_queue = asyncio.Queue()
        self.audio_player = None
        
        # Session information
        self.prompt_name = str(uuid.uuid4())
        self.content_name = str(uuid.uuid4())
        self.audio_content_name = str(uuid.uuid4())
    
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
        if not self.bedrock_client:
            self._initialize_client()
        
        self.scheduler = AsyncIOScheduler(asyncio.get_event_loop())      
        try:
            self.stream_response = await self.bedrock_client.invoke_model_with_bidirectional_stream(
                InvokeModelWithBidirectionalStreamInput(model_id=self.model_id)
            )
            self.is_active = True
            default_system_prompt = "You are a friendly assistant. The user and you will engage in a spoken dialog " \
            "exchanging the transcripts of a natural real-time conversation. Keep your responses short, " \
            "generally two or three sentences for chatty scenarios."
            
            # Send initialization events
            prompt_event = self.START_PROMPT_EVENT % self.prompt_name
            text_content_start = self.TEXT_CONTENT_START_EVENT % (self.prompt_name, self.content_name)
            text_content = self.TEXT_INPUT_EVENT % (self.prompt_name, self.content_name, default_system_prompt, "SYSTEM")
            text_content_end = self.CONTENT_END_EVENT % (self.prompt_name, self.content_name)
            
            init_events = [self.START_SESSION_EVENT, prompt_event, text_content_start, text_content, text_content_end]
            
            for event in init_events:
                await self.send_raw_event(event)
                # Small delay between init events
                await asyncio.sleep(0.1)
            
            # Start listening for responses
            self.response_task = asyncio.create_task(self._process_responses())
            
            # Set up subscription for input events
            self.input_subject.pipe(
                ops.subscribe_on(self.scheduler)
            ).subscribe(
                on_next=lambda event: asyncio.create_task(self.send_raw_event(event)),
                on_error=lambda e: debug_print(f"Input stream error: {e}")
            )
            
            # Set up subscription for audio chunks
            self.audio_subject.pipe(
                ops.subscribe_on(self.scheduler)
            ).subscribe(
                on_next=lambda audio_data: asyncio.create_task(self._handle_audio_input(audio_data)),
                on_error=lambda e: debug_print(f"Audio stream error: {e}")
            )
            
            # Wait a bit to ensure everything is set up
            await asyncio.sleep(0.1)
            
            debug_print("Stream initialized successfully")
            return self
        except Exception as e:
            self.is_active = False
            print(f"Failed to initialize stream: {str(e)}")
            raise
    
    async def send_raw_event(self, event_json):
        """Send a raw event JSON to the Bedrock stream."""
        if not self.stream_response or not self.is_active:
            debug_print("Stream not initialized or closed")
            return
        
        event = InvokeModelWithBidiStreamInputChunk(
            value=BidiInputPayloadPart(bytes_=event_json.encode('utf-8'))
        )
        
        try:
            await self.stream_response.input_stream.send(event)
            # For debugging large events, you might want to log just the type
            if DEBUG:
                if len(event_json) > 200:
                    event_type = json.loads(event_json).get("event", {}).keys()
                    debug_print(f"Sent event type: {list(event_type)}")
                else:
                    debug_print(f"Sent event: {event_json}")
        except Exception as e:
            debug_print(f"Error sending event: {str(e)}")
            if DEBUG:
                import traceback
                traceback.print_exc()
            self.input_subject.on_error(e)
    
    async def send_audio_content_start_event(self):
        """Send a content start event to the Bedrock stream."""
        content_start_event = self.CONTENT_START_EVENT % (self.prompt_name, self.audio_content_name)
        await self.send_raw_event(content_start_event)
    
    async def _handle_audio_input(self, data):
        """Process audio input before sending it to the stream."""
        audio_bytes = data.get('audio_bytes')
        if not audio_bytes:
            debug_print("No audio bytes received")
            return
        
        try:
            # Ensure the audio is properly formatted
            debug_print(f"Processing audio chunk of size {len(audio_bytes)} bytes")
            
            # Base64 encode the audio data
            blob = base64.b64encode(audio_bytes)
            audio_event = self.AUDIO_EVENT_TEMPLATE % (self.prompt_name, self.audio_content_name, blob.decode('utf-8'))
            
            # Send the event directly
            await self.send_raw_event(audio_event)
        except Exception as e:
            debug_print(f"Error processing audio: {e}")
            if DEBUG:
                import traceback
                traceback.print_exc()
    
    def add_audio_chunk(self, audio_bytes):
        """Add an audio chunk to the stream."""
        self.audio_subject.on_next({
            'audio_bytes': audio_bytes,
            'prompt_name': self.prompt_name,
            'content_name': self.audio_content_name
        })
    
    async def send_audio_content_end_event(self):
        """Send a content end event to the Bedrock stream."""
        if not self.is_active:
            debug_print("Stream is not active")
            return
        
        content_end_event = self.CONTENT_END_EVENT % (self.prompt_name, self.audio_content_name)
        await self.send_raw_event(content_end_event)
        debug_print("Audio ended")
    
    async def send_prompt_end_event(self):
        """Close the stream and clean up resources."""
        if not self.is_active:
            debug_print("Stream is not active")
            return
        
        prompt_end_event = self.PROMPT_END_EVENT % (self.prompt_name)
        await self.send_raw_event(prompt_end_event)
        debug_print("Prompt ended")
        
    async def send_session_end_event(self):
        """Send a session end event to the Bedrock stream."""
        if not self.is_active:
            debug_print("Stream is not active")
            return

        await self.send_raw_event(self.SESSION_END_EVENT)
        self.is_active = False
        debug_print("Session ended")
    
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
                            
                            # Handle different response types
                            if 'event' in json_data:
                                if 'textOutput' in json_data['event']:
                                    text_content = json_data['event']['textOutput']['content']
                                    role = json_data['event']['textOutput']['role']
                                    if (role == "ASSISTANT" and text_content.lower().startswith("speculative")):
                                        text_content = text_content.lower().split("speculative:")[1].strip()
                                        print(f"Assistant: {text_content}")
                                    elif (role == "USER"):
                                        print(f"User: {text_content}")
                                
                                if 'audioOutput' in json_data['event']:
                                    audio_content = json_data['event']['audioOutput']['content']
                                    audio_bytes = base64.b64decode(audio_content)
                                    await self.audio_output_queue.put(audio_bytes)
                            
                            self.output_subject.on_next(json_data)
                        except json.JSONDecodeError:
                            self.output_subject.on_next({"raw_data": response_data})
                except StopAsyncIteration:
                    # Stream has ended
                    break
                except Exception as e:
                    debug_print(f"Error receiving response: {e}")
                    self.output_subject.on_error(e)
                    break
        except Exception as e:
            debug_print(f"Response processing error: {e}")
            self.output_subject.on_error(e)
        finally:
            if self.is_active:  
                self.output_subject.on_completed()
    
    async def play_audio_responses(self):
        """Play audio responses as they come in."""
        p = pyaudio.PyAudio()
        
        # Open a stream for audio playback (24kHz, 16-bit, 1 channel)
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=24000,  # Nova S2S output is 24kHz
            output=True
        )
        
        try:
            while self.is_active:
                try:
                    # Get audio data from the queue
                    audio_data = await self.audio_output_queue.get()
                    
                    # Play the audio
                    stream.write(audio_data)
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    debug_print(f"Error playing audio: {e}")
        finally:
            # Clean up
            stream.stop_stream()
            stream.close()
            p.terminate()
    
    async def close(self):
        """Close the stream properly."""
        if not self.is_active:
            return
            
        self.is_active = False
        
        # Complete the subjects
        self.input_subject.on_completed()
        self.audio_subject.on_completed()
        
        self.send_audio_content_end_event()
        if self.stream_response:
            await self.stream_response.input_stream.close()
        
        if self.response_task:
            await self.response_task


class AudioStreamer:
    """Handles microphone input and streaming to Bedrock."""
    
    def __init__(self, stream_manager):
        self.stream_manager = stream_manager
        self.is_streaming = False
        self.audio_task = None
        
    async def start_streaming(self):
        """Start streaming audio from the microphone."""
        if self.is_streaming:
            return
            
        # Initialize PyAudio
        p = pyaudio.PyAudio()
        
        # Open stream
        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE
        )
        
        print("Starting audio streaming. Speak into your microphone...")
        print("Press Enter to stop streaming...")
        
        # Send audio content start event
        await self.stream_manager.send_audio_content_start_event()
        
        self.is_streaming = True
        
        try:
            while self.is_streaming:
                # Read audio data from microphone
                audio_data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                
                # Send to stream manager
                self.stream_manager.add_audio_chunk(audio_data)
                
                # Small delay to prevent overwhelming the stream
                await asyncio.sleep(0.01)
                
        except Exception as e:
            debug_print(f"Error in audio streaming: {e}")
        finally:
            # Clean up
            stream.stop_stream()
            stream.close()
            p.terminate()
            debug_print("Audio streaming stopped")
    
    async def stop_streaming(self):
        """Stop streaming audio."""
        if not self.is_streaming:
            return
            
        self.is_streaming = False
        
        # Send content end event
        await self.stream_manager.send_audio_content_end_event()
        await self.stream_manager.send_prompt_end_event()
        await self.stream_manager.send_session_end_event()
        
        if self.audio_task and not self.audio_task.done():
            self.audio_task.cancel()
            try:
                await self.audio_task
            except asyncio.CancelledError:
                pass


async def main(debug=False):
    """Main function to run the application."""
    global DEBUG
    DEBUG = debug
    
    # Create stream manager
    stream_manager = BedrockStreamManager(model_id='ermis', region='us-east-1')
    
    # Initialize the stream
    await stream_manager.initialize_stream()
    
    # Create audio streamer
    audio_streamer = AudioStreamer(stream_manager)
    
    # Start audio playback task
    playback_task = asyncio.create_task(stream_manager.play_audio_responses())
    
    try:
        # Start streaming audio
        audio_task = asyncio.create_task(audio_streamer.start_streaming())
        
        # Wait for user to press Enter to stop
        await asyncio.get_event_loop().run_in_executor(None, input)
        
        # Stop streaming
        await audio_streamer.stop_streaming()
        
        # Wait for any pending responses
        print("Waiting for final responses...")
        await asyncio.sleep(2)
        
    except KeyboardInterrupt:
        print("Interrupted by user")
    finally:
        # Clean up
        await stream_manager.close()
        
        # Cancel playback task
        if not playback_task.done():
            playback_task.cancel()
            try:
                await playback_task
            except asyncio.CancelledError:
                pass


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Nova Sonic Python Streaming')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()
    # Set your AWS credentials here or use environment variables
    # os.environ['AWS_ACCESS_KEY_ID'] = "AWS_ACCESS_KEY_ID"
    # os.environ['AWS_SECRET_ACCESS_KEY'] = "AWS_SECRET_ACCESS_KEY"
    # os.environ['AWS_DEFAULT_REGION'] = "us-east-1"
    # Run the main function
    try:
        asyncio.run(main(debug=args.debug))
    except Exception as e:
        print(f"Application error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()