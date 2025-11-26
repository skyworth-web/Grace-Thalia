import pyaudio
import wave

# Parameters for recording
FORMAT = pyaudio.paInt16
CHANNELS = 2
RATE = 44100
CHUNK = 1024
MIC_DEVICE_INDEX = 1  # Your physical microphone device index
SPEAKER_DEVICE_INDEX = 2  # Your VB-Cable device index (for system audio)

# Initialize PyAudio
p = pyaudio.PyAudio()

# Open streams for both microphone and system audio (VB-Cable)
mic_stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    input_device_index=MIC_DEVICE_INDEX,
                    frames_per_buffer=CHUNK)

speaker_stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        input_device_index=SPEAKER_DEVICE_INDEX,
                        frames_per_buffer=CHUNK)

print("Recording...")

# Output file to save recorded audio
output_file = "recorded_audio.wav"
frames = []

try:
    while True:
        mic_data = mic_stream.read(CHUNK)  # Record from microphone
        speaker_data = speaker_stream.read(CHUNK)  # Record from system audio

        frames.append(mic_data)  # Append both microphone and speaker data
        frames.append(speaker_data)

except KeyboardInterrupt:
    print("\nRecording stopped by user.")

# Stop the recording
mic_stream.stop_stream()
mic_stream.close()
speaker_stream.stop_stream()
speaker_stream.close()
p.terminate()

# Save the recorded data to a WAV file
with wave.open(output_file, 'wb') as wf:
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))

print(f"Recording saved to {output_file}")
