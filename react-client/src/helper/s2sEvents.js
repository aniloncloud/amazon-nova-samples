class S2sEvent {
    static DEFAULT_INFER_CONFIG = {
      maxTokens: 1024,
      topP: 0.95,
      temperature: 0.7
    };
  
    static DEFAULT_SYSTEM_PROMPT = "You are a friend. The user and you will engage in a spoken dialog exchanging the transcripts of a natural real-time conversation. Keep your responses short, generally two or three sentences for chatty scenarios.";
  
    static DEFAULT_AUDIO_INPUT_CONFIG = {
      mediaType: "audio/lpcm",
      sampleRateHertz: 16000,
      sampleSizeBits: 16,
      channelCount: 1,
      audioType: "SPEECH",
      encoding: "base64"
    };
  
    static DEFAULT_AUDIO_OUTPUT_CONFIG = {
      mediaType: "audio/lpcm",
      sampleRateHertz: 24000,
      sampleSizeBits: 16,
      channelCount: 1,
      voiceId: "matthew",
      encoding: "base64",
      audioType: "SPEECH"
    };
  
    static DEFAULT_TOOL_CONFIG = {
      tools: [{
        toolSpec: {
          name: "getDateTool",
          description: "get information about the current day",
          inputSchema: {
            json: JSON.stringify({
              "$schema": "http://json-schema.org/draft-07/schema#",
              type: "object",
              properties: {},
              required: []
            })
          }
        }
      },
      {
        toolSpec: {
          name: "getKbTool",
          description: "get information about the Amazon policy",
          inputSchema: {
            json: JSON.stringify({
              "$schema": "http://json-schema.org/draft-07/schema#",
              type: "object",
              properties: {
                query: {
                  type: "string",
                  description: "the query to search"
                }
              },
              required: []
            })
          }
        }
      },
      {
        toolSpec: {
          name: "getTravelPolicyTool",
          description: "get information about the travel with pet policy",
          inputSchema: {
            json: JSON.stringify({
              "$schema": "http://json-schema.org/draft-07/schema#",
              type: "object",
              properties: {
                query: {
                  type: "string",
                  description: "the query to search"
                }
              },
              required: []
            })
          }
        }
      }
    ]
    };
  
    static BYOLLM_TOOL_CONFIG = {
      tools: [{
        toolSpec: {
          name: "lookup",
          description: "Runs query against a knowledge base to retrieve information.",
          inputSchema: {
            json: JSON.stringify({
              "$schema": "http://json-schema.org/draft-07/schema#",
              type: "object",
              properties: {
                query: {
                  type: "string",
                  description: "the query to search"
                }
              },
              required: ["query"]
            })
          }
        }
      }]
    };
  
    static sessionStart(inferenceConfig = S2sEvent.DEFAULT_INFER_CONFIG) {
      return { event: { sessionStart: { inferenceConfiguration: inferenceConfig } } };
    }
  
    static promptStart(promptName, audioOutputConfig = S2sEvent.DEFAULT_AUDIO_OUTPUT_CONFIG, toolConfig = S2sEvent.DEFAULT_TOOL_CONFIG) {
      return {
        event: {
          promptStart: {
            promptName,
            textOutputConfiguration: { mediaType: "text/plain" },
            audioOutputConfiguration: audioOutputConfig,
            toolUseOutputConfiguration: { mediaType: "application/json" },
            toolConfiguration: toolConfig
          }
        }
      };
    }
  
    static contentStartText(promptName, contentName) {
      return {
        event: {
          contentStart: {
            promptName,
            contentName,
            type: "TEXT",
            interactive: true,
            textInputConfiguration: { mediaType: "text/plain" }
          }
        }
      };
    }
  
    static textInput(promptName, contentName, systemPrompt = S2sEvent.DEFAULT_SYSTEM_PROMPT) {
      return {
        event: {
          textInput: {
            promptName,
            contentName,
            content: systemPrompt,
            role: "SYSTEM"
          }
        }
      };
    }
  
    static contentEnd(promptName, contentName) {
      return {
        event: {
          contentEnd: {
            promptName,
            contentName
          }
        }
      };
    }
  
    static contentStartAudio(promptName, contentName, audioInputConfig = S2sEvent.DEFAULT_AUDIO_INPUT_CONFIG) {
      return {
        event: {
          contentStart: {
            promptName,
            contentName,
            type: "AUDIO",
            interactive: true,
            audioInputConfiguration: audioInputConfig
          }
        }
      };
    }
  
    static audioInput(promptName, contentName, content) {
      return {
        event: {
          audioInput: {
            promptName,
            contentName,
            content,
            role: "USER"
          }
        }
      };
    }
  
    static contentStartTool(promptName, contentName, toolUseId) {
      return {
        event: {
          contentStart: {
            promptName,
            contentName,
            interactive: false,
            type: "TOOL",
            toolResultInputConfiguration: {
              toolUseId,
              type: "TEXT",
              textInputConfiguration: { mediaType: "text/plain" }
            }
          }
        }
      };
    }
  
    static textInputTool(promptName, contentName, content) {
      return {
        event: {
          textInput: {
            promptName,
            contentName,
            content,
            role: "TOOL"
          }
        }
      };
    }
  
    static promptEnd(promptName) {
      return {
        event: {
          promptEnd: {
            promptName
          }
        }
      };
    }
  
    static sessionEnd() {
      return { event: { sessionEnd: {} } };
    }
  }
  export default S2sEvent;