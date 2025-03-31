import React from 'react';
import './s2s.css'
import { Icon, Alert, Button, Modal, Box, SpaceBetween, Container, ColumnLayout, Header, FormField, Select, Textarea } from '@cloudscape-design/components';
import S2sEvent from './helper/s2sEvents';
import {base64LPCM, AudioQueue} from './helper/audioHelper';

class S2sChatBot extends React.Component {

    constructor(props) {
        super(props);
        this.state = {
            status: "loading", // null, loading, loaded
            alert: null,
            sessionStarted: false,
            showEventJson: false,
            showConfig: false,
            selectedEvent: null,

            chatMessages: {},
            events: [],
            audioResponse: [],
            eventsByContentName: [],
            audioChunks: [],
            audioInputIndex: 0,

            promptName: null,
            textContentName: null,
            audioContentName: null,

            // S2S config items
            configAudioInput: null,
            configSystemPrompt: "You are a friend. The user and you will engage in a spoken dialog exchanging the transcripts of a natural real-time conversation. Keep your responses short, generally two or three sentences for chatty scenarios.",
            configAudioOutput: {
                "mediaType": "audio/lpcm",
                "sampleRateHertz": 24000,
                "sampleSizeBits": 16,
                "channelCount": 1,
                "voiceId": "matthew",
                "encoding": "base64",
                "audioType": "SPEECH"
              },
            configVoiceIdOption: { label: "Matthew", value: "matthew" },
            configToolUse: JSON.stringify({
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
              }, null, 2)
        };
        this.socket = null;
        this.mediaRecorder = null;
        this.audioQueue = new AudioQueue();
        this.chatMessagesEndRef = React.createRef();
    }

    componentDidMount() {
        //this.connectWebSocket();
    }

    componentDidUpdate(prevProps, prevState) {
        if (prevState.chatMessages.length !== this.state.chatMessages.length) {
            this.chatMessagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }
    }
    
    sendEvent(event) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify(event));
            event.timestamp = Date.now();
            this.displayEvent(event, "out");
        }
    }
    
    handleIncomingMessage (message) {
        const eventType = Object.keys(message?.event)[0];
        const role = message.event[eventType]["role"];
        const content = message.event[eventType]["content"];
        const contentId = message.event[eventType].contentId;
        let stopReason = message.event[eventType].stopReason;
        const contentType = message.event[eventType].type;

        switch(eventType) {
            case "textOutput": 
                //const prefix = "Speculative: ";
                // Detect interruption
                if (role === "ASSISTANT" && content.startsWith("{")) {
                    const evt = JSON.parse(content);
                    if (evt.interrupted === true) {
                        stopReason = "END_TURN"
                        this.audioQueue.cancel();
                        //break;
                    }
                }

                var chatMessages = this.state.chatMessages;
                if (chatMessages.hasOwnProperty(contentId)) {
                    chatMessages[contentId].content = content;
                    chatMessages[contentId].role = role;
                    if (chatMessages[contentId].raw === undefined)
                        chatMessages[contentId].raw = [];
                    chatMessages[contentId].raw.push(message);
                }
                this.setState({chatMessages: chatMessages});
                break;
            case "audioOutput":
                this.state.audioResponse[contentId] += message.event[eventType].content;
                break;
            case "contentStart":
                if (contentType === "AUDIO") {
                    this.state.audioResponse[contentId] = "";
                }
                else if (contentType === "TEXT") {
                    var chatMessages = this.state.chatMessages;
                    chatMessages[contentId] =  {
                        "content": "", 
                        "role": role,
                        "raw": [],
                    };
                    chatMessages[contentId].raw.push(message);
                    this.setState({chatMessages: chatMessages});
                }
                break;
            case "contentEnd":
                if (contentType === "AUDIO") {
                    var audioUrl = base64LPCM(this.state.audioResponse[contentId]);
                    
                    this.audioQueue.enqueue(audioUrl);
                }
                else if (contentType === "TEXT"){
                    var chatMessages = this.state.chatMessages;
                    if (chatMessages.hasOwnProperty(contentId)) {
                        if (chatMessages[contentId].raw === undefined)
                            chatMessages[contentId].raw = [];
                        chatMessages[contentId].raw.push(message);
                        chatMessages[contentId].stopReason = stopReason;
                    }
                    this.setState({chatMessages: chatMessages});

                }

        }

        this.displayEvent(message, "in");
    }

    displayEvent(event, type) {
        if (event && event.event) {
            const eventName = Object.keys(event?.event)[0];
            let key = null;
            let ts = Date.now();
            if (eventName === "audioOutput") {
                const contentId = event.event[eventName].contentId;
                key = `${eventName}-${contentId.substr(0,8)}`;
            }
            else if (eventName === "audioInput") {
                const contentName = event.event[eventName].contentName;
                key = `${eventName}-${contentName.substr(0,8)}-${this.state.audioInputIndex}`;
            }
            else if (eventName === "contentStart") {
                const contentType = event.event[eventName].type;
                key = `${eventName}-${contentType}-${ts}`;
                if (type === "in" && event.event[eventName].type === "AUDIO") {
                    this.setState({audioInputIndex: this.state.audioInputIndex + 1});
                }
            }
            else if(eventName === "textOutput") {
                const role = event.event[eventName].role;
                const content = event.event[eventName].content;
                if (role === "ASSISTANT" && content.startsWith("{")) {
                    const evt = JSON.parse(content);
                    if (evt.interrupted === true) {
                        event.interrupted = true;
                    }
                }
                key = `${eventName}-${ts}`;
            }
            else {
                key = `${eventName}-${ts}`;
            }

            let eventsByContentName = this.state.eventsByContentName;
            if (eventsByContentName === null)
                eventsByContentName = [];

            let exists = false;
            for(var i=0;i<eventsByContentName.length;i++) {
                var item = eventsByContentName[i];
                if (item.key == key && item.type == type) {
                    item.events.push(event);
                    exists = true;
                    break;
                }
            }
            if (!exists) {
                eventsByContentName.unshift({
                    key: key, 
                    name: eventName, 
                    type: type, 
                    events: [event], 
                    ts: ts,
                    interrupted: event.interrupted !== undefined?event.interrupted: null
                })
            }
            this.setState({eventsByContentName, eventsByContentName});
        }
    }

    handleSessionChange = e => {
        if (this.state.sessionStarted) {
            // End session
            this.endSession();
        }
        else {
            this.setState({chatMessages:[], events: [], eventsByContentName: []});
            this.startSession();
        }
        this.setState({sessionStarted: !this.state.sessionStarted});
    }

    connectWebSocket() {
        // Connect to the S2S WebSocket server
        if (this.socket === null || this.socket.readyState !== WebSocket.OPEN) {
            this.socket = new WebSocket(process.env.REACT_APP_WEBSOCKET_URL);
        
            this.socket.onopen = () => {
                console.log("WebSocket connected!");
                const promptName = crypto.randomUUID();
                const textContentName = crypto.randomUUID();
                const audioContentName = crypto.randomUUID();
                this.setState({
                    promptName: promptName,
                    textContentName: textContentName,
                    audioContentName: audioContentName
                })
    
                // Start session events
                this.sendEvent(S2sEvent.sessionStart());

                var audioConfig = S2sEvent.DEFAULT_AUDIO_OUTPUT_CONFIG;
                audioConfig.voiceId = this.state.configVoiceIdOption.value;
                var toolConfig = this.state.configToolUse?JSON.parse(this.state.configToolUse):S2sEvent.DEFAULT_TOOL_CONFIG;
                this.sendEvent(S2sEvent.promptStart(promptName, audioConfig, toolConfig));

                this.sendEvent(S2sEvent.contentStartText(promptName, textContentName));

                this.sendEvent(S2sEvent.textInput(promptName, textContentName, this.state.configSystemPrompt));
                this.sendEvent(S2sEvent.contentEnd(promptName, textContentName));
                this.sendEvent(S2sEvent.contentStartAudio(promptName, audioContentName));
              };

            // Handle incoming messages
            this.socket.onmessage = (message) => {
                const event = JSON.parse(message.data);
                this.handleIncomingMessage(event);
            };
        
            // Handle errors
            this.socket.onerror = (error) => {
                this.setState({alert: "WebSocket Error: ", error});
                console.error("WebSocket Error: ", error);
            };
        
            // Handle connection close
            this.socket.onclose = () => {
                console.log("WebSocket Disconnected");
            };
        }
    }

    startSession() {
        // Init S2sSessionManager
        try {
            if (this.socket === null || this.socket.readyState !== WebSocket.OPEN) {
                this.connectWebSocket();
            }

            // Start microphone 
            this.startMicrophone();
        } catch (error) {
            console.error('Error accessing microphone: ', error);
        }
    }
      
    async startMicrophone() {    
        try {
            
            // Start microphone
            const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                    channelCount: 1,           // Mono
                    sampleRate: 16000,         // 16kHz
                    sampleSize: 16,            // 16-bit
                    echoCancellation: true,    // Enable echo cancellation
                    noiseSuppression: true,    // Enable noise suppression
                    autoGainControl: true      // Enable automatic gain control
                }
            });

            // Create AudioContext for processing
            const audioContext = new AudioContext({
                sampleRate: 16000,
                latencyHint: 'interactive'
            });

            // Create MediaStreamSource
            const source = audioContext.createMediaStreamSource(stream);

            // Create ScriptProcessor for raw PCM data
            const processor = audioContext.createScriptProcessor(512, 1, 1);

            source.connect(processor);
            processor.connect(audioContext.destination);

            processor.onaudioprocess = (e) => {
                if (this.state.sessionStarted) {
                    const inputData = e.inputBuffer.getChannelData(0);

                    const buffer = new ArrayBuffer(inputData.length * 2);
                    const pcmData = new DataView(buffer);
                    for (let i = 0; i < inputData.length; i++) {
                        const int16 = Math.max(-32768, Math.min(32767, Math.round(inputData[i] * 32767)));
                        pcmData.setInt16(i * 2, int16, true);
                    }
                    // Binary data string
                    let data = "";
                    for (let i = 0; i < pcmData.byteLength; i++) {
                        data += String.fromCharCode(pcmData.getUint8(i));
                    }

                    // Send to WebSocket
                    const event = S2sEvent.audioInput(this.state.promptName, this.state.audioContentName, btoa(data));
                    this.sendEvent(event);
                }
            };

            // Store cleanup functions
            window.audioCleanup = () => {
                processor.disconnect();
                source.disconnect();
                stream.getTracks().forEach(track => track.stop());
            };

            this.mediaRecorder = new MediaRecorder(stream);
            this.mediaRecorder.ondataavailable = (event) => {
                this.state.audioChunks.push(event.data);
            };
            this.mediaRecorder.onstop = () => {
                const audioBlob = new Blob(this.state.audioChunks, { type: 'audio/wav' });

                // Send to WebSocket
                this.sendEvent(S2sEvent.audioInput(this.state.promptName, this.state.audioContentName, btoa(audioBlob)));
                this.setState({audioChunks: []});
            };

            this.mediaRecorder.start();
            this.setState({sessionStarted: true});
            console.log('Microphone recording started');
        } catch (error) {
            console.error('Error accessing microphone: ', error);
        }

    }

    endSession() {
        if (this.socket) {
            // Close microphone
            if (this.mediaRecorder && this.state.sessionStarted) {
                this.mediaRecorder.stop();
                console.log('Microphone recording stopped');
            }

            // Close S2sSessionManager
            this.sendEvent(S2sEvent.contentEnd(this.state.promptName, this.state.audioContentName));
            this.sendEvent(S2sEvent.promptEnd(this.state.promptName));
            this.sendEvent(S2sEvent.sessionEnd());

            // Close websocket
            this.socket.close();

            this.setState({sessionStarted: false});
        }
  
    }
    render() {
        return (
            <div className="s2s">
                {this.state.alert !== null && this.state.alert.length > 0?
                <Alert statusIconAriaLabel="Warning" type="warning">
                {this.state.alert}
                </Alert>:<div/>}
                <div className='top'>
                    <div className='action'>
                        <Button variant='primary' onClick={this.handleSessionChange}>
                            <Icon name={this.state.sessionStarted?"microphone-off":"microphone"} />&nbsp;&nbsp;
                            {this.state.sessionStarted?"End Conversation":"Start Conversation"}
                        </Button>
                    </div>
                    <div className='setting'>
                        <Button onClick={()=> 
                            this.setState({
                                showConfig: true, 
                            })
                        }>
                            <Icon name="settings"/>
                        </Button>
                        
                    </div>
                </div>
                <br/>
                <ColumnLayout columns={2}>
                    <Container header={
                        <Header variant="h2">Conversation</Header>
                    }>
                    <div className="chatarea">
                        {Object.keys(this.state.chatMessages).map((key,index) => {
                            const msg = this.state.chatMessages[key];
                            //if (msg.stopReason === "END_TURN" || msg.role === "USER")
                                return <div className='item'>
                                    <div className={msg.role === "USER"?"user":"bot"} onClick={()=> 
                                            this.setState({
                                                showEventJson: true, 
                                                selectedEvent: {events:msg.raw}
                                            })
                                        }>
                                        <Icon name={msg.role === "USER"?"user-profile":"gen-ai"} />&nbsp;&nbsp;
                                        {msg.content}
                                    </div>
                                </div>
                            // else if(index === this.state.chatMessages.length-1 && msg.role === "ASSISTANT" && msg.stopReason !== "END_TURN") {
                            //     return <div class="loading-bubble">
                            //                 <div class="loading-dots">
                            //                     <span></span>
                            //                     <span></span>
                            //                     <span></span>
                            //                 </div>
                            //             </div>
                            // }
                        })}
                        <div className='endbar' ref={this.chatMessagesEndRef}></div>
                    </div>
                    </Container>
                    <Container header={
                        <Header variant="h2">Events</Header>
                    }>
                    <div className='events'>
                        {this.state.eventsByContentName.map(event=>{
                            return <div className={
                                    event.name === "toolUse"? "event-tool": 
                                    event.type === "in"?"event-in":
                                    event.interrupted === true?"event-int":"event-out"
                                } 
                                onClick={() => {
                                    this.setState({selectedEvent: event, showEventJson: true});
                                }}
                                >
                                <Icon name={event.type === "in"? "arrow-down": "arrow-up"} />&nbsp;&nbsp;
                                {event.name}
                                {event.events.length > 1? ` (${event.events.length})`: ""}
                                <div class="tooltip">
                                    <pre id="jsonDisplay">{event.events.map(e=>{
                                        return JSON.stringify(e,null,2);
                                    })
                                }</pre>
                                </div>
                            </div>
                        })}
                        <Modal
                            onDismiss={() => this.setState({showEventJson: false})}
                            visible={this.state.showEventJson}
                            header="Event details"
                            size='medium'
                            footer={
                                <Box float="right">
                                <SpaceBetween direction="horizontal" size="xs">
                                    <Button variant="link" onClick={() => this.setState({showEventJson: false})}>Close</Button>
                                </SpaceBetween>
                                </Box>
                            }
                        >
                            <div className='eventdetail'>
                            <pre id="jsonDisplay">
                                {this.state.selectedEvent && this.state.selectedEvent.events.map(e=>{
                                    const eventType = Object.keys(e?.event)[0];
                                    if (eventType === "audioInput" || eventType === "audioOutput")
                                        e.event[eventType].content = e.event[eventType].content.substr(0,10) + "...";
                                    const ts = new Date(e.timestamp).toLocaleString(undefined, {
                                        year: "numeric",
                                        month: "2-digit",
                                        day: "2-digit",
                                        hour: "2-digit",
                                        minute: "2-digit",
                                        second: "2-digit",
                                        fractionalSecondDigits: 3, // Show milliseconds
                                        hour12: false // 24-hour format
                                    });
                                    var displayJson = { ...e };
                                    delete displayJson.timestamp;
                                    return ts + "\n" + JSON.stringify(displayJson,null,2) + "\n";
                                })}
                            </pre>
                            </div>
                        </Modal>
                        <Modal
                            onDismiss={() => this.setState({showConfig: false})}
                            visible={this.state.showConfig}
                            header="Nova S2S settings"
                            size='large'
                            footer={
                                <Box float="right">
                                <SpaceBetween direction="horizontal" size="xs">
                                    <Button variant="link" onClick={() => this.setState({showConfig: false})}>Close</Button>
                                </SpaceBetween>
                                </Box>
                            }
                        >
                            <div className='config'>
                                <FormField
                                    label="Voice Id"
                                    stretch={true}
                                >
                                    <Select
                                        selectedOption={this.state.configVoiceIdOption}
                                        onChange={({ detail }) =>
                                            this.setState({configVoiceIdOption: detail.selectedOption})
                                        }
                                        options={[
                                            { label: "Matthew", value: "matthew" },
                                            { label: "Ruth", value: "ruth" }
                                        ]}
                                        />
                                </FormField>
                                <br/>
                                <FormField
                                    label="System prompt"
                                    description="For the speech model"
                                    stretch={true}
                                >
                                    <Textarea
                                        onChange={({ detail }) => this.setState({configSystemPrompt: detail.value})}
                                        value={this.state.configSystemPrompt}
                                        placeholder="Speech system prompt"
                                    />
                                </FormField>
                                <br/>
                                <FormField
                                    label="Tool use configuration"
                                    description="For external integration such as RAG and Agents"
                                    stretch={true}
                                >
                                    <Textarea
                                        onChange={({ detail }) => this.setState({configToolUse: detail.value})}
                                        value={this.state.configToolUse}
                                        rows={10}
                                        placeholder="{}"
                                    />
                                </FormField>
                            </div>
                        </Modal>
                    </div>
                    </Container>
                </ColumnLayout>
            </div>
        );
    }
}

export default S2sChatBot;