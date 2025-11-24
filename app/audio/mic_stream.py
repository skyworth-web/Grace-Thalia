import sounddevice as sd
import numpy as np
import requests
import threading
import queue
import time
from backend.api_client import APIClient

class MicrophoneStreamer:
    def __init__(self, callback):
        self.running = False
        self.api = APIClient()
        self.callback = callback
        self.q = queue.Queue()

    def _stream_audio(self):
        def audio_callback(indata, frames, time, status):
            self.q.put(indata.copy())

        with sd.InputStream(callback=audio_callback, channels=1, samplerate=16000):
            while self.running:
                if not self.q.empty():
                    audio_chunk = self.q.get()

                    wav_bytes = audio_chunk.astype(np.int16).tobytes()
                    stt = self.api.stt(wav_bytes)
                    transcript = stt.get("transcript", "")

                    if transcript.strip():
                        self.callback(transcript)

                time.sleep(0.15)

    def start(self):
        self.running = True
        threading.Thread(target=self._stream_audio, daemon=True).start()

    def stop(self):
        self.running = False
