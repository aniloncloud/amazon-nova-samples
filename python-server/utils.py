import base64
import numpy as np
import wave
import io
from scipy.signal import resample_poly

def audio_raw_base64_to_wav(base64_str):
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

    duration_s = 0
    with wave.open(io.BytesIO(wav_audio), 'rb') as wav_file:
        duration_s =  wav_file.getnframes()/float(wav_file.getframerate())

    return wav_audio, duration_s

def audio_wav_to_raw(audio_bytes):
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