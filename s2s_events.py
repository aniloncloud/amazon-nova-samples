import json

class S2sEvent:
  # Default configuration values
  DEFAULT_INFER_CONFIG = {
        "maxTokens": 1024,
        "topP": 0.95,
        "temperature": 0.7
    }
  DEFAULT_SYSTEM_PROMPT = "You are a friend. The user and you will engage in a spoken dialog " \
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
          "voiceId": "en_us_matthew",
          "encoding": "base64",
          "audioType": "SPEECH"
        }
  DEFAULT_TOOL_CONFIG = {
          "tools": [{
                      "toolSpec": {
                          "name": "getTimeTool",
                          "description": "get information about the current time",
                          "inputSchema": {
                              "json": json.dumps({
                                "\$schema": "http://json-schema.org/draft-07/schema#",
                                "type": "object",
                                "properties": {},
                                "required": []
                            })
                          }
                      }
                  }
                ]
        }

  @staticmethod
  def session_start(inference_config=DEFAULT_INFER_CONFIG): 
    return {"event":{"sessionStart":{"inferenceConfiguration":inference_config}}}

  @staticmethod
  def prompt_start(prompt_name, audio_output_config=DEFAULT_AUDIO_OUTPUT_CONFIG, tool_config=DEFAULT_TOOL_CONFIG):
    return {
          "event": {
            "promptStart": {
              "promptName": prompt_name,
              "textOutputConfiguration": {
                "mediaType": "text/plain"
              },
              "audioOutputConfiguration": audio_output_config,
              "toolUseOutputConfiguration": {
                "mediaType": "application/json"
              },
              "toolConfiguration": tool_config
            }
          }
        }

  @staticmethod
  def content_start_text(prompt_name, content_name):
    return {
        "event":{
        "contentStart":{
          "promptName":prompt_name,
          "contentName":content_name,
          "type":"TEXT",
          "interactive":True,
          "textInputConfiguration":{
            "mediaType":"text/plain"
            }
          }
        }
      }
    
  @staticmethod
  def text_input(prompt_name, content_name, system_prompt=DEFAULT_SYSTEM_PROMPT):
    return {
      "event":{
        "textInput":{
          "promptName":prompt_name,
          "contentName":content_name,
          "content":system_prompt,
          "role":"SYSTEM"
        }
      }
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
  def content_start_audio(prompt_name, content_name, audio_input_config=DEFAULT_AUDIO_INPUT_CONFIG):
    return {
      "event":{
        "contentStart":{
          "promptName":prompt_name,
          "contentName":content_name,
          "type":"AUDIO",
          "interactive":True,
          "audioInputConfiguration":audio_input_config
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
          "role": "USER"
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
        "textInput": {
          "promptName": prompt_name,
          "contentName": content_name,
          "content": content,
          "role": "TOOL"
        }
      }
    }
  
  @staticmethod
  def prompt_end(prompt_name):
    return {
      "event": {
        "promptEnd": {
          "promptName": prompt_name
        }
      }
    }
  
  @staticmethod
  def session_end():
    return  {
      "event": {
        "sessionEnd": {}
      }
    }