import streamlit as st
import asyncio
from s2s_session_manager import S2sSessionManager
import utils
import time
import base64
from s2s_events import S2sEvent
import json 
import asyncio

CHUNK_SIZE = 1024

# Streamlit App
st.title("Amazon Nova Sonic (speech to speech)")
st.session_state["response_content"] = {}


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

async def main():
    st.success("S2S session started", icon="✅")
    audio_value = st.audio_input("Click the record icon to start recording, and stop it to send your voice to Nova.")
    if audio_value:
        received_messages, sent_events,percent_complete, response_content = [], [], 0, {}

        progress_text = "Sending audio chunks"
        sent_audio = st.progress(0, text=progress_text)
        for percent_complete in range(100):
            time.sleep(0.01)
            sent_audio.progress(percent_complete + 1, text=progress_text)
        time.sleep(1)
        #sent_audio.empty()

        # Create empty placeholders to update the UI dynamically
        st.subheader("Receiving")
        display_received = st.empty()  # For sent chunks

        # Convert the audio to S2S required format
        converted_audio = utils.audio_wav_to_raw(audio_value.read())

        # Convert audio to bytes chunks each up to 1024 bytes
        chunks = [converted_audio[i:i + CHUNK_SIZE] for i in range(0, len(converted_audio), CHUNK_SIZE)]
        # Send chunks
        counter = 0
        s2s = S2sSessionManager()
        await s2s.start_session()
        await s2s.start_audio_input()
        for chunk in chunks:
            counter += 1
            base64_str = base64.b64encode(chunk).decode('utf-8')
            await s2s.send_audio_chunk(base64_str)
            await asyncio.sleep(0.01)

            percent_complete = counter/len(chunks)

        await s2s.end_audio_input()

        while s2s.is_active:
            value = await s2s.response_event_queue.get()
            #async for value in s2s.listener():
            if "contentStart" in value:
                content_id = value["contentStart"].get("contentId")
                type = value["contentStart"].get("type")
                if type == "AUDIO":
                    response_content[content_id] = {"content": ""}

            elif "textOutput" in value:
                received_messages.append(f'[{value["textOutput"]["role"]}] {value["textOutput"]["content"]}')
                display_received.write('\n\n'.join(received_messages))

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
                    response_audio, duration_s = utils.audio_raw_base64_to_wav(response_content[content_id]["content"])
                    if response_audio:
                        st.audio(response_audio, format="audio/wav", autoplay=True)
                        time.sleep(duration_s)

        #await s2s.end_session()



asyncio.run(main())