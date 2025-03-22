import streamlit as st
import asyncio
from s2s_session_manager import S2sSessionManager
import utils

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
    converted_audio = utils.audio_wav_to_raw(audio_value.read())

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
                response_audio = utils.audio_raw_base64_to_wav(value["content"])
                if response_audio:
                    st.audio(response_audio, format="audio/wav")
            #print(f'\033[33m{value}')


    asyncio.run(send_audio(converted_audio))#.read()))