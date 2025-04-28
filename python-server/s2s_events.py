import json

class S2sEvent:
  
  # Default configuration values
  DEFAULT_INFER_CONFIG = {
        "maxTokens": 1024,
        "topP": 0.95,
        "temperature": 0.7
    }
  
  DEFAULT_SYSTEM_PROMPT = "You are a friendly assistant. The user and you will engage in a spoken dialog " \
    "exchanging the transcripts of a natural real-time conversation. Keep your responses short, " \
    "generally two or three sentences for chatty scenarios."

  DEFAULT_AUDIO_INPUT_CONFIG = {
        "mediaType":"audio/lpcm",
        "sampleRateHertz":16000,
        "sampleSizeBits":16,
        "channelCount":1,
        "audioType":"SPEECH","encoding":"base64"
      }
  DEFAULT_AUDIO_OUTPUT_CONFIG = {
          "mediaType": "audio/lpcm",
          "sampleRateHertz": 24000,
          "sampleSizeBits": 16,
          "channelCount": 1,
          "voiceId": "matthew",
          "encoding": "base64",
          "audioType": "SPEECH"
        }
  DEFAULT_TOOL_CONFIG = {
          "tools": [{
                      "toolSpec": {
                          "name": "getDateTool",
                          "description": "get information about the current day",
                          "inputSchema": {
                              "json": '''{
                                "$schema": "http://json-schema.org/draft-07/schema#",
                                "type": "object",
                                "properties": {},
                                "required": []
                            }'''
                          }
                      }
                  }
                ]
        }

  @staticmethod
  def content_end(prompt_name, content_name):
    return {
      "event":{
        "contentEnd":{
          "promptName":prompt_name,
          "contentName":content_name
        }
      }
    }

    
  @staticmethod
  def audio_input(prompt_name, content_name, content):
    return {
      "event": {
        "audioInput": {
          "promptName": prompt_name,
          "contentName": content_name,
          "content": content,
        }
      }
    }
  
  @staticmethod
  def content_start_tool(prompt_name, content_name, tool_use_id):
    return {
        "event": {
          "contentStart": {
            "promptName": prompt_name,
            "contentName": content_name,
            "interactive": False,
            "type": "TOOL",
            "role": "TOOL",
            "toolResultInputConfiguration": {
              "toolUseId": tool_use_id,
              "type": "TEXT",
              "textInputConfiguration": {
                "mediaType": "text/plain"
              }
            }
          }
        }
      }
  
  @staticmethod
  def text_input_tool(prompt_name, content_name, content):
    return {
      "event": {
        "toolResult": {
          "promptName": prompt_name,
          "contentName": content_name,
          "content": content,
          #"role": "TOOL"
        }
      }
    }
  
  # Customized event for client app
  @staticmethod
  def client_custom(content_name, data):
    return {
      "client": {
        "contentName": content_name,
        "content": data,
        "role": "ASSISTANT"
      }
    }
