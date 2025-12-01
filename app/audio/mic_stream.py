# app/audio/mic_stream.py

import pyaudio
import wave
import threading
import logging
import time
import requests
import io

from pycaw.pycaw import AudioUtilities

# Parameters for recording
FORMAT = pyaudio.paInt16
CHANNELS = 2
RATE = 44100
CHUNK = 1024

# You can override these via MainWindow if you want later
MIC_DEVICE_INDEX = 1        # physical mic
SPEAKER_DEVICE_INDEX = 2    # VB-Cable / system audio

logging.basicConfig(level=logging.INFO)


class MicStream:
    def __init__(self, stt_url, callback):
        """
        stt_url: e.g. "http://localhost:8000/stt"
        callback: function(text: str) -> None  (will be a Qt signal emitter)
        """
        self.stt_url = stt_url
        self.callback = callback

        self.device_index = None   # optional override for mic device
        self.running = False

        self.p = pyaudio.PyAudio()
        self.mic_stream = None
        self.speaker_stream = None

        # Buffer for building STT segments (~2 seconds)
        self.segment_buffer = bytearray()
        self.segment_duration_target = 2.0  # seconds

    # ---------------- Recording control ----------------

    def start_recording(self):
        """Start recording from microphone and speaker."""
        if self.running:
            return

        # Decide which device index to use for mic
        mic_index = self.device_index if self.device_index is not None else MIC_DEVICE_INDEX

        self.running = True

        # Mic stream
        self.mic_stream = self.p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            input_device_index=mic_index,
            frames_per_buffer=CHUNK,
        )

        # Speaker / VB-Cable stream
        self.speaker_stream = self.p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            input_device_index=SPEAKER_DEVICE_INDEX,
            frames_per_buffer=CHUNK,
        )

        logging.info("Recording...")
        logging.info("Live captions started")

        # Start threads
        self.recording_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.recording_thread.start()

        self.logging_thread = threading.Thread(target=self._log_audio_status, daemon=True)
        self.logging_thread.start()

    def stop_recording(self):
        """Stop the recording and clean up."""
        self.running = False

        try:
            if self.mic_stream is not None:
                self.mic_stream.stop_stream()
                self.mic_stream.close()
                self.mic_stream = None

            if self.speaker_stream is not None:
                self.speaker_stream.stop_stream()
                self.speaker_stream.close()
                self.speaker_stream = None

            if self.p is not None:
                self.p.terminate()
                self.p = None

            logging.info("Recording stopped")
        except Exception as e:
            logging.error(f"Error while stopping recording: {e}")

    # ---------------- Internal loops ----------------

    def _capture_loop(self):
        """Continuously capture audio from mic + speaker and send segments to STT."""
        try:
            bytes_per_frame = 2 * CHANNELS  # 16-bit = 2 bytes * channels
            frames_per_segment = int(self.segment_duration_target * RATE)
            bytes_per_segment = frames_per_segment * bytes_per_frame

            while self.running:
                mic_data = self.mic_stream.read(CHUNK, exception_on_overflow=False)
                speaker_data = self.speaker_stream.read(CHUNK, exception_on_overflow=False)

                # Mix mic + speaker by simple interleaving (or just use mic_data if you want)
                # For now we just use mic_data for clarity:
                self.segment_buffer.extend(mic_data)

                # If buffer has enough for ~2 seconds, send it
                if len(self.segment_buffer) >= bytes_per_segment:
                    segment = bytes(self.segment_buffer[:bytes_per_segment])
                    del self.segment_buffer[:bytes_per_segment]

                    logging.info(
                        f"🎤 Prepared {len(segment)} bytes for STT "
                        f"(~{self.segment_duration_target:.1f}s)"
                    )
                    self._send_segment_to_backend(segment)

                time.sleep(0.01)  # tiny sleep to avoid maxing CPU

        except Exception as e:
            logging.error(f"❌ Error during recording: {e}")

    def _log_audio_status(self):
        """Periodically log whether any system audio is playing."""
        while self.running:
            if self.is_audio_playing():
                logging.info("Audio is currently playing.")
            else:
                logging.info("No audio is playing.")
            time.sleep(1)

    # ---------------- STT ----------------

    def _send_segment_to_backend(self, audio_bytes: bytes):
        """Build WAV from raw PCM bytes and POST to /stt."""
        try:
            with io.BytesIO() as wav_buffer:
                with wave.open(wav_buffer, "wb") as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(self.p.get_sample_size(FORMAT))
                    wf.setframerate(RATE)
                    wf.writeframes(audio_bytes)

                wav_data = wav_buffer.getvalue()

            logging.info(f"🎤 Sending audio to backend with {len(wav_data)} bytes")

            response = requests.post(
                self.stt_url,
                files={"file": ("audio.wav", wav_data, "audio/wav")},
                timeout=30,
            )

            if response.status_code != 200:
                logging.error(
                    f"❌ STT failed with status {response.status_code}: {response.text}"
                )
                return

            json_data = response.json()
            text = json_data.get("transcript", "").strip()

            if text:
                logging.info(f"📝 Transcript: {text}")
                # IMPORTANT: this callback will be a Qt signal emitter,
                # so calling it from this thread is SAFE.
                try:
                    self.callback(text)
                except Exception as cb_err:
                    logging.error(f"❌ Error in callback: {cb_err}")

        except Exception as e:
            logging.error(f"❌ STT error: {e}")

    # ---------------- Utility ----------------

    def is_audio_playing(self):
        """Check if any audio session is active via PyCaw."""
        try:
            sessions = AudioUtilities.GetAllSessions()
            for session in sessions:
                if session.State == 1:  # active
                    return True
        except Exception as e:
            logging.error(f"PyCaw error: {e}")
        return False
