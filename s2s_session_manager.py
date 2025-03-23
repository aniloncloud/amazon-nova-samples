from bedrock_runtime.client import (
    BedrockRuntime,
    InvokeModelWithBidirectionalStreamInput,
    InvokeModelWithBidirectionalStreamOutput
)
from bedrock_runtime.models import InvokeModelWithBidiStreamInputChunk, BidiInputPayloadPart
from bedrock_runtime.config import Config
from smithy_aws_core.credentials_resolvers.environment import EnvironmentCredentialsResolver
from bedrock_runtime.config import HTTPAuthSchemeResolver, SigV4AuthScheme

import asyncio
import base64
import json
import uuid
import time
from datetime import datetime
from s2s_events import S2sEvent
import boto3
import kb
import logging


'''
# S2sManager initialization input schema
'''
class S2sSessionManager:
  chunk_size = 1024
  reponse_content = {}
  
  region = "us-east-1"
  model_id = "ermis"

  # S2S configuration
  inference_config = None
  system_prompt = None
  audio_input_config = None
  audio_output_config = None
  tool_config = None

  text_content_name = None
  audio_content_name = None
  tool_content_name = None
  session = None
  is_connected = False

  def __init__(self, model_id=None, region=None, inference_config=None, system_prompt=None, audio_input_config=None, audio_output_config=None, tool_config=None):
    if model_id:
      self.model_id = model_id
    if region:
      self.region = region

    self.inference_config = inference_config if inference_config else S2sEvent.DEFAULT_INFER_CONFIG
    self.system_prompt = system_prompt if system_prompt else S2sEvent.DEFAULT_SYSTEM_PROMPT
    self.audio_input_config = audio_input_config if audio_input_config else S2sEvent.DEFAULT_AUDIO_INPUT_CONFIG
    self.audio_output_config = audio_output_config if audio_output_config else S2sEvent.DEFAULT_AUDIO_OUTPUT_CONFIG
    self.tool_config = tool_config if tool_config else S2sEvent.DEFAULT_TOOL_CONFIG

    self.prompt_name = str(uuid.uuid4()) 
    self.text_content_name = str(uuid.uuid4())
    self.audio_content_name = str(uuid.uuid4())
    self.tool_content_name = str(uuid.uuid4())
    # self.prompt_name = "126680f5-5859-4d15-ae70-488de4146484"
    # self.text_content_name = "a6431ef2-e23c-4f8c-a552-3f308629d3c3"
    # self.audio_content_name = "b3917935-2398-4889-94a8-e677f6c3e351"
    # self.tool_content_name = "b3917935-2398-4889-94a8-e677f6c3e351"
    
    self.bedrock = BedrockRuntime(config=Config(
        endpoint_uri=f"https://bedrock-runtime.{self.region}.amazonaws.com",
        region=self.region,
        aws_credentials_identity_resolver=EnvironmentCredentialsResolver(),
        http_auth_scheme_resolver=HTTPAuthSchemeResolver(),
        http_auth_schemes={"aws.auth#sigv4": SigV4AuthScheme()}
    ))
    self.bedrock_agent = boto3.client('bedrock-agent-runtime',region_name=self.region) 
      
  async def session_start(self):
    logging.debug("Session starting")
    try:
      # Connect to S2S
      self.session = await self.bedrock.invoke_model_with_bidirectional_stream(
          InvokeModelWithBidirectionalStreamInput(model_id=self.model_id)
      )
      # Send init events
      start_events = [
          S2sEvent.session_start(self.inference_config), 
          S2sEvent.prompt_start(self.prompt_name, self.audio_output_config, self.tool_config),
          S2sEvent.content_start_text(self.prompt_name, content_name=self.text_content_name),
          S2sEvent.text_input(self.prompt_name, self.text_content_name, self.system_prompt),
          S2sEvent.content_end(self.prompt_name, self.text_content_name),
        ]
      for event in start_events:
        await self.send_raw_event(event)
      self.is_connected = True
    except Exception as ex:
       logging.error("Exception",ex)
       return False
    logging.info(f"Session started")
    return True

  async def listener(self):
      while self.is_connected:
        response = await self.session.await_output()
        for chunk in response:
          if isinstance(chunk, InvokeModelWithBidirectionalStreamOutput):
              continue
          
          event = None
          try:
            ebytes = await chunk.receive()
            event_str = ebytes.value.bytes_.decode("utf-8")
            event = json.loads(event_str)
            logging.debug(f'\033[33m{event}')
          except Exception as ex:
            logging.debug(f"\033[31m{ex}") # Red
            continue

          # Return textOutput, contentStart/contentEnd for audio, audioOutput
          if "event" in event:
            evt = event["event"]
            evt["timestamp"] = datetime.now().timestamp()
            if "contentStart" in evt:
               yield evt
            elif "contentEnd" in evt:
               yield evt
            elif "textOutput" in evt:
               yield evt
            elif "audioOutput" in evt:
               yield evt
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
                      await self.send_raw_event(event)

  def __handle_tool_use(self, tool_name, input):
    return kb.retrieve_and_generation(input)

  async def session_end(self):
      stop_events = [
         S2sEvent.content_end(self.prompt_name, self.audio_content_name), 
         S2sEvent.prompt_end(self.prompt_name),
         S2sEvent.session_end()
        ]
      for event in stop_events:
        await self.send_raw_event(event)
    
      self.session = None
      self.is_connected = False

  async def send_raw_event(self, event):
    if "audioInput" not in event["event"]:
      logging.debug(json.dumps(event))
    else:
      logging.debug(json.dumps(event)[0:150])
    await self.session.input_stream.send(InvokeModelWithBidiStreamInputChunk(
              value=BidiInputPayloadPart(bytes_=json.dumps(event).encode('utf-8'))
          ))

  async def audio_start(self):
    logging.debug("Audio starting")
    await self.send_raw_event(S2sEvent.content_start_audio(self.prompt_name, self.audio_content_name, self.audio_input_config))
    logging.info(f"Audio started")

  async def audio_end(self):
    logging.debug("Audio ending")
    await self.send_raw_event(S2sEvent.content_end(self.prompt_name, self.audio_content_name))
    logging.info(f"Audio ended")

  async def send_audio_chunk(self, chunk):
      blob = base64.b64encode(chunk)
      audio_event = S2sEvent.audio_input(self.prompt_name, self.audio_content_name, blob.decode('utf-8'))
      await self.send_raw_event(audio_event)
      