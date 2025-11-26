# app/audio/mic_stream.py

import pyaudio
import wave
import threading
import logging
import time
import requests
import io

from pycaw.pycaw import AudioUtilities

logging.basicConfig(level=logging.INFO)

# Parameters for recording
FORMAT = pyaudio.paInt16
CHANNELS = 2
RATE = 44100
CHUNK = 1024

# Default device indices (you can still override via self.device_index if you want)
MIC_DEVICE_INDEX = 1       # Your physical microphone device index
SPEAKER_DEVICE_INDEX = 2   # Your VB-Cable / system-audio device index


class MicStream:
    def __init__(self, stt_url, callback):
        """
        stt_url: backend STT endpoint, e.g. http://localhost:8000/stt
        callback: function(text: str) -> None, called when a transcript is ready
        """
        self.stt_url = stt_url
        self.callback = callback

        self.device_index = None  # Optional: main input device index from UI
        self.running = False

        # PyAudio object
        self.p = pyaudio.PyAudio()

        # Streams
        self.mic_stream = None
        self.speaker_stream = None

        # For saving full session audio if you want
        self.frames = []

        # For STT chunking: only mic audio goes here
        self.buffer_chunks = []

        # Threads
        self.recording_thread = None
        self.logging_thread = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def start_recording(self):
        """Start recording from microphone + speaker, and sending chunks to STT."""
        if self.running:
            return

        self.running = True

        mic_index = self.device_index if self.device_index is not None else MIC_DEVICE_INDEX

        self.mic_stream = self.p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            input_device_index=mic_index,
            frames_per_buffer=CHUNK,
        )

        self.speaker_stream = self.p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            input_device_index=SPEAKER_DEVICE_INDEX,
            frames_per_buffer=CHUNK,
        )

        logging.info("Recording...")

        self.recording_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.recording_thread.start()

        self.logging_thread = threading.Thread(target=self._log_audio_status, daemon=True)
        self.logging_thread.start()

    def stop_recording(self):
        """Stop recording and close streams."""
        if not self.running:
            return

        self.running = False

        try:
            if self.mic_stream is not None:
                self.mic_stream.stop_stream()
                self.mic_stream.close()
        except Exception as e:
            logging.error(f"Error stopping mic stream: {e}")

        try:
            if self.speaker_stream is not None:
                self.speaker_stream.stop_stream()
                self.speaker_stream.close()
        except Exception as e:
            logging.error(f"Error stopping speaker stream: {e}")

        try:
            self.p.terminate()
        except Exception as e:
            logging.error(f"Error terminating PyAudio: {e}")

        logging.info("Recording stopped")

        # Optionally save full session audio
        # self._save_audio()

    # Alias so your old self.streamer.stop() won't explode (if still used somewhere)
    def stop(self):
        self.stop_recording()

    # ------------------------------------------------------------------ #
    # Internal: recording + status
    # ------------------------------------------------------------------ #
    def _capture_loop(self):
        """Capture loop: reads from microphone and system audio."""
        try:
            while self.running:
                mic_data = self.mic_stream.read(CHUNK, exception_on_overflow=False)
                speaker_data = self.speaker_stream.read(CHUNK, exception_on_overflow=False)

                # For saving full session
                self.frames.append(mic_data)
                self.frames.append(speaker_data)

                # For STT chunking, only use mic audio
                self._send_audio_to_backend(mic_data)

        except Exception as e:
            logging.error(f"❌ Error during recording: {e}")

    def _log_audio_status(self):
        """Periodically log whether any audio is playing (system-wide)."""
        while self.running:
            if self.is_audio_playing():
                logging.info("Audio is currently playing.")
            else:
                logging.info("No audio is playing.")
            time.sleep(1)

    def is_audio_playing(self):
        """Check if any audio session is playing using PyCaw."""
        try:
            sessions = AudioUtilities.GetAllSessions()
            for session in sessions:
                if session.State == 1:  # 1 = active
                    return True
            return False
        except Exception as e:
            logging.error(f"Error checking audio sessions: {e}")
            return False

    # ------------------------------------------------------------------ #
    # Internal: STT
    # ------------------------------------------------------------------ #
    def _send_audio_to_backend(self, audio_data: bytes):
        """Accumulate mic audio and periodically send ~5s to the STT backend."""
        try:
            self.buffer_chunks.append(audio_data)

            # Duration of buffered audio (seconds)
            duration_sec = len(self.buffer_chunks) * CHUNK / RATE

            # Only send when we have at least ~5 seconds
            if duration_sec < 5.0:
                return

            # Convert buffer_chunks to WAV
            with io.BytesIO() as wav_buffer:
                with wave.open(wav_buffer, "wb") as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(self.p.get_sample_size(FORMAT))
                    wf.setframerate(RATE)
                    wf.writeframes(b"".join(self.buffer_chunks))

                wav_bytes = wav_buffer.getvalue()

            logging.info(f"🎤 Sending audio to backend with {len(wav_bytes)} bytes")

            response = requests.post(
                self.stt_url,
                files={"file": ("audio.wav", wav_bytes, "audio/wav")},
                timeout=30,
            )

            if response.status_code == 200:
                text = response.json().get("transcript", "")
                if text.strip():
                    logging.info(f"📝 Transcript: {text}")
                    # Call callback directly; MainWindow will handle Qt thread-safe update
                    self.callback(text)
            else:
                logging.error(f"❌ STT failed with status {response.status_code}: {response.text}")

            # Clear buffer after sending
            self.buffer_chunks = []

        except Exception as e:
            logging.error(f"❌ STT error: {e}")

    # ------------------------------------------------------------------ #
    # Optional: save full session audio (not used right now)
    # ------------------------------------------------------------------ #
    def _save_audio(self, output_file="recorded_audio.wav"):
        try:
            with wave.open(output_file, "wb") as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(self.p.get_sample_size(FORMAT))
                wf.setframerate(RATE)
                wf.writeframes(b"".join(self.frames))
            logging.info(f"Recording saved to {output_file}")
        except Exception as e:
            logging.error(f"Error saving audio: {e}")
