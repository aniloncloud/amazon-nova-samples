import streamlit as st
import asyncio
import base64
import json
import time
from s2s_session_manager import S2sSessionManager
import numpy as np
import wave
from io import BytesIO
import io
from scipy.signal import resample_poly

def base64_to_wav(base64_str):
    # Decode base64 to raw LPCM bytes
    audio_bytes = base64.b64decode(base64_str)

    # Convert LPCM to WAV (since Streamlit supports WAV playback)
    wav_header = (
        b"RIFF" +
        (len(audio_bytes) + 36).to_bytes(4, "little") +
        b"WAVEfmt " +
        (16).to_bytes(4, "little") +
        (1).to_bytes(2, "little") +  # PCM format
        (1).to_bytes(2, "little") +  # Mono channel
        (24000).to_bytes(4, "little") +  # Sample rate (24kHz)
        (24000 * 2).to_bytes(4, "little") +  # Byte rate (SampleRate * NumChannels * BitsPerSample/8)
        (2).to_bytes(2, "little") +  # Block align (NumChannels * BitsPerSample/8)
        (16).to_bytes(2, "little") +  # Bits per sample
        b"data" +
        len(audio_bytes).to_bytes(4, "little")
    )
    # Combine WAV header with LPCM data
    wav_audio = wav_header + audio_bytes
    return wav_audio

def convert_to_16khz(audio_bytes):
    # Read the audio data from the bytes
    with wave.open(io.BytesIO(audio_bytes), 'rb') as wav_file:
        sample_rate = wav_file.getframerate()
        channels = wav_file.getnchannels()
        n_frames = wav_file.getnframes()
        audio_data = wav_file.readframes(n_frames)
        
    # Convert to numpy array
    audio_array = np.frombuffer(audio_data, dtype=np.int16)
    
    # Convert to mono if needed
    if channels > 1:
        audio_array = audio_array.reshape(-1, channels)
        audio_array = np.mean(audio_array, axis=1, dtype=np.int16)
    
    # Resample to 16000Hz if needed
    if sample_rate != 16000:
        # Calculate resampling parameters
        gcd = np.gcd(sample_rate, 16000)
        audio_array = resample_poly(audio_array, 16000 // gcd, sample_rate // gcd)
        audio_array = audio_array.astype(np.int16)
    
    # Create new WAV file with 16kHz
    output_buffer = io.BytesIO()
    with wave.open(output_buffer, 'wb') as out_wav:
        out_wav.setnchannels(1)  # mono
        out_wav.setsampwidth(2)  # 16-bit
        out_wav.setframerate(16000)  # 16kHz
        out_wav.writeframes(audio_array.tobytes())
    
    return output_buffer.getvalue()

# Streamlit App
st.title("Amazon Nova Sonic (speech to speech)")


st.header("Record an audio")
audio_value = st.audio_input("Record a voice message")

# init S2S session
s2s = S2sSessionManager()
if s2s.is_connected:
    st.caption("Connected to S2S")

#with open("./japan16k.raw", 'rb') as f:
    #converted_audio = f.read()
if audio_value:
    st.caption("Sending audio to Nova")
    received_messages = []

    col1, col2 = st.columns(2)
    with col1:
        # Create empty placeholders to update the UI dynamically
        st.subheader("Receiving")
        display_received = st.empty()  # For sent chunks
    with col2:
        st.subheader("Sending")    
        display_sent = st.empty()

    # Convert the audio
    converted_audio = convert_to_16khz(audio_value.read())

    async def send_audio(audio_value):
        await s2s.start_session()
        await s2s.send_audio(audio_value)
        async for value in s2s.listener():
            if "type" in value and value["type"] == "TEXT":
                received_messages.append(f'[{value["role"]}] {value["content"]}')
                if value["role"] == "USER":
                    display_received.write('\n\n'.join(received_messages))
                else:
                    st.caption(f'[{value["role"]}] {value["content"]}')
            elif "type" in value and value["type"] == "AUDIO":
                #print(f'\033[32m{value["content"]}')
                response_audio = base64_to_wav(value["content"])
                if response_audio:
                    st.audio(response_audio, format="audio/wav")
            #print(f'\033[33m{value}')


    asyncio.run(send_audio(converted_audio))#.read()))