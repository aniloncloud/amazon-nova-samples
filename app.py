import streamlit as st
import asyncio
from s2s_session_manager import S2sSessionManager
import utils
import time
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set the logging level
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("s2s-session-manager.log"),  # Log to a file
        logging.StreamHandler()  # Log to the console
    ]
)

# Streamlit App
st.title("Amazon Nova Sonic (speech to speech)")
st.session_state["response_content"] = {}

async def main():
    s2s = S2sSessionManager()
    started = await s2s.session_start()
    if st.button("Disconnect"):
        await s2s.session_end()
    if started:
        st.success("S2S session started", icon="✅")
        placeholder = st.empty()
        with placeholder.container():
            st.header("Record an audio")
            audio_value = st.audio_input("Click the record icon to start recording, and stop it to send your voice to Nova.")
            if audio_value:
                received_messages, percent_complete, response_content = [], 0, {}
        
                progress_text = "Sending audio chunks"
                sent_audio = st.progress(0, text=progress_text)
                for percent_complete in range(100):
                    time.sleep(0.01)
                    sent_audio.progress(percent_complete + 1, text=progress_text)
                time.sleep(1)
                sent_audio.empty()

                # Create empty placeholders to update the UI dynamically
                st.subheader("Receiving")
                display_received = st.empty()  # For sent chunks

                # Convert the audio to S2S required format
                converted_audio = utils.audio_wav_to_raw(audio_value.read())

                await s2s.audio_start()

                # Convert audio to bytes chunks each up to 1024 bytes
                chunks = [converted_audio[i:i + s2s.chunk_size] for i in range(0, len(converted_audio), s2s.chunk_size)]
                # Send chunks
                counter = 0
                for chunk in chunks:
                    counter += 1
                    await s2s.send_audio_chunk(chunk)
                    percent_complete = counter/len(chunks)

                await s2s.audio_end()

                async for value in s2s.listener():
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




asyncio.run(main())