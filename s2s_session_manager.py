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

class S2sSessionManager:
  chunk_size = 1024
  reponse_content = {}
  prompt_name = None
  text_content_name = None
  audio_content_name = None
  tool_content_name = None
  connection = None
  is_connected = False

  def __init__(self, system_prompt=None):
    self.bedrock = BedrockRuntime(config=Config(
        endpoint_uri="https://bedrock-runtime.us-east-1.amazonaws.com",
        region="us-east-1",
        aws_credentials_identity_resolver=EnvironmentCredentialsResolver(),
        http_auth_scheme_resolver=HTTPAuthSchemeResolver(),
        http_auth_schemes={
            "aws.auth#sigv4": SigV4AuthScheme(),
        }
    ))
    self.bedrock_agent = boto3.client('bedrock-agent-runtime',region_name='us-west-2') 

    self.prompt_name = str(uuid.uuid4()) 
    self.text_content_name = str(uuid.uuid4())
    self.audio_content_name = str(uuid.uuid4())
    self.tool_content_name = str(uuid.uuid4())
    # self.prompt_name = "126680f5-5859-4d15-ae70-488de4146484"
    # self.text_content_name = "a6431ef2-e23c-4f8c-a552-3f308629d3c3"
    # self.audio_content_name = "b3917935-2398-4889-94a8-e677f6c3e351"
    # self.tool_content_name = "b3917935-2398-4889-94a8-e677f6c3e351"
    if system_prompt:
      self.system_prompt = system_prompt
    
    #asyncio.run(self.start_session())
      
  async def start_session(self):
      # Connect to S2S
      self.connection = await self.bedrock.invoke_model_with_bidirectional_stream(
          InvokeModelWithBidirectionalStreamInput(model_id='ermis')
      )
      self.is_connected = True
      #print("!!!! Started")
      # Send init events
      start_events = [
         S2sEvent.session_start(), 
         S2sEvent.prompt_start(self.prompt_name),
         S2sEvent.content_start_text(self.prompt_name, content_name=self.text_content_name),
         S2sEvent.text_input(self.prompt_name, self.text_content_name),
         S2sEvent.content_end(self.prompt_name, self.text_content_name),
        ]
      await self.send_raw_events(start_events)
          
  async def listener(self):
      while self.is_connected:
        response = await self.connection.await_output()
        for chunk in response:
          if isinstance(chunk, InvokeModelWithBidirectionalStreamOutput):
              continue
          
          event = None
          try:
            ebytes = await chunk.receive()
            event_str = ebytes.value.bytes_.decode("utf-8")
            event = json.loads(event_str)
            #print(f'\033[33m{event}')
          except Exception as ex:
            print(f"\033[31m{ex}") # Red
            continue

          #if "audioOutput" not in event["event"]:
            #print(f"\033[36m!!!! {json.dumps(event)}") # Cyan
          #else:
            #print(f"\033[36m!!!! {json.dumps(event)[0:150]}") # Cyan
          if "contentStart" in event["event"]:
              content_id = event["event"]["contentStart"].get("contentId")
              self.reponse_content[content_id] = event["event"]["contentStart"]
              self.reponse_content[content_id]["content"] = ""
              self.reponse_content[content_id]["timestamp"] = datetime.now().timestamp()
              #print("contentStart", content_id)

          elif "textOutput" in event["event"]:
              content_id = event["event"]["textOutput"].get("contentId")
              if content_id in self.reponse_content:
                self.reponse_content[content_id]["content"] = event["event"]["textOutput"]["content"]
                self.reponse_content[content_id]["role"] = event["event"]["textOutput"]["role"]
                #print("textOutput",content_id)
                #print(event["event"]["textOutput"]["content"])

          elif "audioOutput" in event["event"]:
              content_id = event["event"]["audioOutput"].get("contentId")
              if content_id in self.reponse_content:
                self.reponse_content[content_id]["content"] += event["event"]["audioOutput"]["content"]
                self.reponse_content[content_id]["role"] = event["event"]["audioOutput"]["role"]
                self.reponse_content[content_id]["timestamp"] = datetime.now().timestamp()
                #print("audioOutput",content_id)
                #print(event["event"]["audioOutput"]["content"][0:20])

          elif "contentEnd" in event["event"]:
              content_id = event["event"]["contentEnd"].get("contentId")
              if content_id in self.reponse_content:
                if event["event"]["contentEnd"]["type"] == "AUDIO":
                   # return audio
                   yield self.reponse_content[content_id]
                if event["event"]["contentEnd"]["type"] == "TEXT":
                   yield self.reponse_content[content_id]

          elif "toolUse" in event["event"]:
              content_id = event["event"]["toolUse"].get("contentId")
              tool_name = event["event"]["toolUse"].get("toolName")
              tool_use_id = event["event"]["toolUse"].get("toolUseId")
              content = json.loads(event["event"]["toolUse"].get("content"))
              #print("!!!!",content)

              if tool_use_id:
                # Get history
                #print(self.reponse_content[content_id])

                content = self.__handle_tool_use(tool_name, "What are the scaling laws?")
                if content:
                  tool_input = S2sEvent.text_input_tool(self.prompt_name, self.tool_content_name, '\n'.join(content))
                  events = [
                    S2sEvent.content_start_tool(self.prompt_name, self.tool_content_name, tool_use_id),
                    tool_input,
                    S2sEvent.content_end(self.prompt_name, self.tool_content_name)
                  ]

                  # send event to s2s
                  await self.send_raw_events(events)

  def __handle_tool_use(self, tool_name, input):
    return kb.retrieve_and_generation(input)

  async def stop_session(self):
      stop_events = [
         S2sEvent.content_end(self.prompt_name, self.audio_content_name), 
         S2sEvent.prompt_end(self.prompt_name),
         S2sEvent.session_end()
        ]
      await self.send_raw_events(stop_events)
    
      self.connection = None
      self.is_connected = False

  async def send_raw_events(self, events):
     if events and self.is_connected == True:
        for event in events:
          #print(json.dumps(event)[0:150])
          await self.connection.input_stream.send(InvokeModelWithBidiStreamInputChunk(
                    value=BidiInputPayloadPart(bytes_=json.dumps(event).encode('utf-8'))
                ))

  async def send_audio(self, audio_bytes):
      events = []
      # Audio content start event
      events.append(S2sEvent.content_start_audio(self.prompt_name, self.audio_content_name))

      # Audio input events: Convert to base64 in chunks of 1024 bytes
      chunks = [audio_bytes[i:i + self.chunk_size] for i in range(0, len(audio_bytes), self.chunk_size)]
      for chunk in chunks:
        blob = base64.b64encode(chunk)
        audio_event = S2sEvent.audio_input(self.prompt_name, self.audio_content_name, blob.decode('utf-8'))
        events.append(audio_event)

      # Audio content end event
      #events.append(S2sEvent.content_end(self.prompt_name, self.audio_content_name))

      await self.send_raw_events(events)
      