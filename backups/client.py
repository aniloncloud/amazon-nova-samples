import streamlit as st
import websockets
import time
import streamlit.utils as utils
import base64
import asyncio
from server.s2s_events import S2sEvent
import uuid
import json

CHUNK_SIZE = 1024

prompt_name = str(uuid.uuid4())
content_name_text = str(uuid.uuid4())
content_name_audio = str(uuid.uuid4())

event_sent = []
async def send_event(websocket, event, sent_events_container=None):
    event_str = json.dumps(event, separators=(',', ':'))
    #print(event_str)
    event_sent.append(list(event["event"].keys())[0])
    await websocket.send(event_str)
    await asyncio.sleep(0.01)

    sent_events_container.markdown(
        f"""
        <div style="max-height: 300px; overflow-y: scroll; overflow-x: scroll; border: 1px solid #ccc; padding: 10px;">
            {'\n\n'.join(event_sent[-10:])}
        </div>
        """,
        unsafe_allow_html=True
    )


async def receive_event(websocket, st, received_events_container):
    #st.subheader("Receiving")
    transcript_container = st.empty()  # For sent chunks

    received_transcripts, received_events, response_content = [], {}, []
    while True:
        content_id = None
        try:
            response = await websocket.recv()  # Receive a response
            print(f"Received: {response}")

            event = json.loads(response)
            received_events.append(event)
            received_events_container.markdown(
                f"""
                <div style="max-height: 300px; overflow-y: scroll; overflow-x: scroll; border: 1px solid #ccc; padding: 10px;">
                    {'\n\n'.join(received_events[-10:])}
                </div>
                """,
                unsafe_allow_html=True
            )
            
            value = event["event"]
            if "contentStart" in value:
                content_id = value["contentStart"].get("contentId")
                type = value["contentStart"].get("type")
                if type == "AUDIO":
                    response_content[content_id] = {"content": ""}

            elif "textOutput" in value:
                received_transcripts.append(f'[{value["textOutput"]["role"]}] {value["textOutput"]["content"]}')
                transcript_container.write('\n\n'.join(received_transcripts))

            elif "audioOutput" in value:
                content_id = value["audioOutput"].get("contentId")
                if content_id in response_content:
                    response_content[content_id]["content"] += value["audioOutput"]["content"]
                else:
                    response_content[content_id] = {
                        "content": value["audioOutput"]["content"]
                    }

            elif "contentEnd" in value:
                content_id = value["contentEnd"].get("contentId")
                type = value["contentEnd"].get("type")
                if content_id in response_content and type == "AUDIO":
                    await send_event(websocket, S2sEvent.content_end(prompt_name, content_name_audio))
                    await send_event(websocket, S2sEvent.prompt_end(prompt_name))
                    await send_event(websocket, S2sEvent.session_end())

                    response_audio, duration_s = utils.audio_raw_base64_to_wav(response_content[content_id]["content"])
                    if response_audio:
                        st.audio(response_audio, format="audio/wav", autoplay=True)
                        time.sleep(duration_s)
                    
        except Exception as ex:
            print(ex)
            if websocket:
                await websocket.close()
                print("WebSocket connection closed.")
                    
            break
        

async def main():
    uri = "ws://localhost:8081/interact-s2s"  # Replace with your WebSocket URL
    async with websockets.connect(uri) as websocket:
        print("Connected to server")

        sent_events_container, received_events_container = None, None
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Sent")
            sent_events_container = st.empty()
        with col1:
            st.subheader("Received")
            received_events_container = st.empty()

        # Listen to the websocket connection
        asyncio.create_task(receive_event(websocket, st,received_events_container))

        # Session start
        await send_event(websocket, S2sEvent.session_start(),sent_events_container)
        # Prompt start
        await send_event(websocket, S2sEvent.prompt_start(prompt_name),sent_events_container)
        # Content start text
        await send_event(websocket, S2sEvent.content_start_text(prompt_name, content_name_text),sent_events_container)
        # Text input
        await send_event(websocket, S2sEvent.text_input(prompt_name, content_name_text),sent_events_container)
        # Content end text
        await send_event(websocket, S2sEvent.content_end(prompt_name, content_name_text),sent_events_container)

        if st.button("End session"):
            # prompt end
            await send_event(websocket, S2sEvent.prompt_end(prompt_name), sent_events_container)
            # sesion end
            await send_event(websocket, S2sEvent.session_end(), sent_events_container)
        

        audio_value = st.audio_input("Click the record icon to start recording, and stop it to send your voice to Nova.")
        if audio_value:
            percent_complete = 0

            # Content start audio
            await send_event(websocket, S2sEvent.content_start_audio(prompt_name, content_name_audio),sent_events_container)
            time.sleep(0.01)

            progress_text = "Sending audio chunks"
            sent_audio = st.progress(0, text=progress_text)
            for percent_complete in range(100):
                time.sleep(0.01)
                sent_audio.progress(percent_complete + 1, text=progress_text)

            # Convert the audio to S2S required format
            converted_audio = utils.audio_wav_to_raw(audio_value.read())

            # Convert audio to bytes chunks each up to 1024 bytes
            chunks = [converted_audio[i:i + CHUNK_SIZE] for i in range(0, len(converted_audio), CHUNK_SIZE)]
            # Send chunks
            counter = 0
            for chunk in chunks:
                counter += 1
                base64_str = base64.b64encode(chunk).decode('utf-8')
                await send_event(websocket, S2sEvent.audio_input(prompt_name, content_name_audio, base64_str),sent_events_container)
                time.sleep(0.01)
                percent_complete = counter/len(chunks)

            # Send silence chunk to keep the stream alive
            slilence_time_s = 10
            start_time = time.time()  # Record the start time
            slience_chunk = "BAAAAP7/+v/4//j/+P/6//n/+f/8////AAACAAMABQAGAAgABgAEAAYABQAEAAEAAAAAAAEAAAAAAAIABQAGAAsADAAMAAoABgAEAAEAAAAAAAAA/v/7//r/+f/2//X/9v/2//j/+v/7//v//P//////AAAAAAAAAAD//wAAAAABAAIABAAIAAsADAAMAAkABAABAAQABgAGAAQAAgAAAP///f/7//r/+//7//v/+//7//7/AQAEAAQAAwACAP///v/8//r/+P/1//D/7//t/+z/7//0//r///8GAAsADQAOAA8ADgANAAsABwADAP7/+f/2//b/+f/+/wIABgAJAAwADwAQABAAEQAOAAoABwABAP///P/5//n/+f/5//7///////z/+v/6//n//f8AAAQABQAIAAYAAgAAAP///P/8//v/9//2//f/9//2//n//P///wAAAAAAAAAAAQABAAIAAQACAAYABQADAAIAAAD/////AAAAAAAAAQABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="
            while time.time() - start_time < slilence_time_s: 
                print("slience...")
                await send_event(websocket, S2sEvent.audio_input(prompt_name, content_name_audio, slience_chunk),sent_events_container)
                time.sleep(0.5) 

            # Content end audio
            await send_event(websocket, S2sEvent.content_end(prompt_name, content_name_audio),received_events_container)
            time.sleep(0.01)         



with st.expander("S2S configurations"):
    st.radio("Choose a voice:", ["Mathew", "Ruth"], horizontal=True)
    st.text_area("System prompt:", S2sEvent.DEFAULT_SYSTEM_PROMPT)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.text_area("ToolUse Config:", json.dumps(S2sEvent.DEFAULT_TOOL_CONFIG, indent=2), height=300)
    with col2:
        st.text_area("Input Audio Config:", json.dumps(S2sEvent.DEFAULT_AUDIO_INPUT_CONFIG, indent=2), height=300)
    with col3:
        st.text_area("Output Audio Config:", json.dumps(S2sEvent.DEFAULT_AUDIO_OUTPUT_CONFIG, indent=2), height=300)
asyncio.run(main())
