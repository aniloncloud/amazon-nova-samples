import streamlit as st
import sounddevice as sd
import numpy as np
import asyncio
import threading
import io
from scipy.io.wavfile import write
import base64
import json
import time
from s2s_session_manager import S2sSessionManager
import utils

st.title("🎤 Nova speech to speech")

# Audio settings
SAMPLE_RATE = 16000  # Sample rate in Hz
CHANNELS = 1         # Mono audio
CHUNK_DURATION = 1   # Each chunk is 1 second

st.session_state["s2s_session_manager"] = S2sSessionManager()
st.session_state["items"] = ["1","2"]

# Function to send audio data to WebSocket
async def send_audio_to_s2s(audio_bytes):
    s2s = S2sSessionManager()
    await s2s.session_start()
    await s2s.audio_start()

    # Convert audio to bytes chunks each up to 1024 bytes
    chunks = [audio_bytes[i:i + s2s.chunk_size] for i in range(0, len(audio_bytes), s2s.chunk_size)]
    for chunk in chunks:
        await s2s.send_audio_chunk(chunk)
        st.caption("chunk[0:10]")

    await s2s.audio_end()

    async for value in s2s.listener():
        if "type" in value and value["type"] == "TEXT":
            st.caption(f'[{value["role"]}] {value["content"]}')
        elif "type" in value and value["type"] == "AUDIO":
            response_audio = utils.audio_raw_base64_to_wav(value["content"])
            if response_audio:
                st.audio(response_audio, format="audio/wav", autoplay=True)
    
    await s2s.session_end()
    
# Callback function for streaming
def audio_callback(indata, frames, time, status):
    """ Captures live audio and sends it to WebSocket """
    if status:
        st.error(f"Audio input error: {status}")
    else:
        wav_buffer = io.BytesIO()
        write(wav_buffer, SAMPLE_RATE, indata)  # Convert to WAV format
        audio_data = wav_buffer.getvalue()
        st.audio(audio_data)
        #print("!!!!!", type(audio_data))
        #converted_audio = utils.audio_wav_to_raw(audio_data)

        # Send audio asynchronously
        asyncio.run(send_audio_to_s2s(audio_data))

    
# Start/Stop Streaming
if st.button("Start Streaming"):
    st.info("Streaming audio to WebSocket...")
    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, callback=audio_callback)
    stream.start()

    # Keep the stream running in the background
    st.session_state["stream"] = stream

if st.button("Stop Streaming"):
    if "stream" in st.session_state:
        st.session_state["stream"].stop()
        st.success("Audio streaming stopped.")
