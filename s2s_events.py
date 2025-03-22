import json

# Default values
TOOL_CONFIG = {"name":"agi-interactive-console::externalLLM","description":"BYOLLM tool.","inputSchema":{"$schema":"http://json-schema.org/draft-07/schema#","type":"object","properties":{"chatHistory":{"type":"array","items":{"type":"object","properties":{"role":{"type":"string","enum":["SYSTEM","USER","ASSISTANT"]},"content":{"type":"string"},"metadata":{"type":"array","items":{"type":"string"}},"interrupted":{"type":"object","properties":{"status":{"type":"boolean"},"offsetInMilliseconds":{"type":"string"}},"required":["status","offsetInMilliseconds"],"additionalProperties":False}},"required":["role","content"]}}},"required":["chatHistory"]}}
AUDIO_INPUT_CONFIG = {"mediaType":"audio/lpcm","sampleRateHertz":16000,"sampleSizeBits":16,"channelCount":1,"audioType":"SPEECH","encoding":"base64"}
SYSTEM_PROMPT = "You are a friend. The user and you will engage in a spoken dialog " \
            "exchanging the transcripts of a natural real-time conversation. Keep your responses short, " \
            "generally two or three sentences for chatty scenarios."

class S2sEvent:
  @staticmethod
  def session_start(max_tokens=1024, top_p=0.95, temperature=0.7): 
    return {"event":{"sessionStart":{"inferenceConfiguration":{"maxTokens":max_tokens,"topP":top_p,"temperature":temperature}}}}

  @staticmethod
  def prompt_start(prompt_name):
    return {
          "event": {
            "promptStart": {
              "promptName": prompt_name,
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
                "tools": [{
                            "toolSpec": {
                                "name": "getDateTool",
                                "description": "get information about the current date",
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
            }
          }
        }

  @staticmethod
  def content_start_text(prompt_name, content_name):
    return {"event":{"contentStart":{"promptName":prompt_name,"contentName":content_name,"type":"TEXT","interactive":True,"textInputConfiguration":{"mediaType":"text/plain"}}}}
    
  @staticmethod
  def text_input(prompt_name, content_name, system_prompt=SYSTEM_PROMPT):
    return {"event":{"textInput":{"promptName":prompt_name,"contentName":content_name,"content":system_prompt,"role":"SYSTEM"}}}
  
  @staticmethod
  def content_end(prompt_name, content_name):
    return {"event":{"contentEnd":{"promptName":prompt_name,"contentName":content_name}}}

  @staticmethod
  def content_start_audio(prompt_name, content_name, audio_input_config=AUDIO_INPUT_CONFIG):
    return {"event":{"contentStart":{"promptName":prompt_name,"contentName":content_name,"type":"AUDIO","interactive":True,"audioInputConfiguration":audio_input_config}}}
    
  @staticmethod
  def audio_input(prompt_name, content_name, content):
    return {"event": {"audioInput": {"promptName": prompt_name,"contentName": content_name,"content": content,"role": "USER"}}}
  
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
    return {"event": {"textInput": {"promptName": prompt_name,"contentName": content_name,"content": content,"role": "TOOL"}}}
  
  @staticmethod
  def prompt_end(prompt_name):
    return {"event": {"promptEnd": {"promptName": prompt_name}}}
  
  @staticmethod
  def session_end():
    return  {"event": {"sessionEnd": {}}}