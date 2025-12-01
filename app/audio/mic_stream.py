# app/audio/mic_stream.py

import pyaudio
import wave
import threading
import logging
import time
import requests
import io
from queue import Queue
from concurrent.futures import ThreadPoolExecutor
from collections import deque

# pycaw is Windows-only, make it optional
try:
    from pycaw.pycaw import AudioUtilities
    PYCAW_AVAILABLE = True
except ImportError:
    PYCAW_AVAILABLE = False
    logging.warning("pycaw not available (Windows-only). Audio status detection disabled.")

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

        # Real-time streaming parameters - smaller chunks with overlap
        self.chunk_duration = 0.8  # seconds per chunk (smaller for lower latency)
        self.overlap_duration = 0.4  # seconds of overlap (50% overlap)
        self.bytes_per_frame = 2 * CHANNELS  # 16-bit = 2 bytes * channels
        self.frames_per_chunk = int(self.chunk_duration * RATE)
        self.bytes_per_chunk = self.frames_per_chunk * self.bytes_per_frame
        self.overlap_bytes = int(self.overlap_duration * RATE * self.bytes_per_frame)
        
        # Sliding window buffer for overlapping chunks
        self.audio_buffer = deque(maxlen=int(3 * RATE * self.bytes_per_frame))  # Keep ~3 seconds max
        
        # Thread pool for concurrent STT processing
        self.executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="STT")
        self.stt_queue = Queue()
        
        # Track last processed position to avoid duplicate processing
        self.last_processed_pos = 0

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
            # Wait for pending STT requests to complete (with timeout)
            self.executor.shutdown(wait=True, timeout=5)
            
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

            # Clear buffers
            self.audio_buffer.clear()
            
            logging.info("Recording stopped")
        except Exception as e:
            logging.error(f"Error while stopping recording: {e}")

    # ---------------- Internal loops ----------------

    def _capture_loop(self):
        """Continuously capture audio from mic + speaker and send overlapping segments to STT."""
        try:
            chunk_interval = self.chunk_duration - self.overlap_duration  # Time between chunk starts
            last_chunk_time = time.time()
            
            while self.running:
                mic_data = self.mic_stream.read(CHUNK, exception_on_overflow=False)
                speaker_data = self.speaker_stream.read(CHUNK, exception_on_overflow=False)

                # Mix mic + speaker audio (simple average for now)
                # Convert to numpy arrays for mixing if needed, or just use mic_data
                # For now, use mic_data for clarity, but you can mix them:
                # mixed = self._mix_audio(mic_data, speaker_data)
                
                # Add to sliding window buffer
                self.audio_buffer.extend(mic_data)

                # Send overlapping chunks at regular intervals (like Windows Live Caption)
                current_time = time.time()
                if current_time - last_chunk_time >= chunk_interval:
                    if len(self.audio_buffer) >= self.bytes_per_chunk:
                        # Extract chunk with overlap from buffer
                        chunk_data = bytes(list(self.audio_buffer)[-self.bytes_per_chunk:])
                        
                        # Submit to thread pool for async processing
                        self.executor.submit(self._send_segment_to_backend, chunk_data)
                        
                        last_chunk_time = current_time
                        logging.debug(
                            f"🎤 Queued {len(chunk_data)} bytes for STT "
                            f"(~{self.chunk_duration:.1f}s chunk)"
                        )

                time.sleep(0.001)  # Very small sleep for real-time responsiveness

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
        """Build WAV from raw PCM bytes and POST to /stt with retry logic."""
        max_retries = 2
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            try:
                with io.BytesIO() as wav_buffer:
                    with wave.open(wav_buffer, "wb") as wf:
                        wf.setnchannels(CHANNELS)
                        wf.setsampwidth(self.p.get_sample_size(FORMAT))
                        wf.setframerate(RATE)
                        wf.writeframes(audio_bytes)

                    wav_data = wav_buffer.getvalue()

                logging.debug(f"🎤 Sending audio to backend ({len(wav_data)} bytes, attempt {attempt + 1})")

                response = requests.post(
                    self.stt_url,
                    files={"file": ("audio.wav", wav_data, "audio/wav")},
                    timeout=10,  # Shorter timeout for real-time
                )

                if response.status_code != 200:
                    logging.warning(
                        f"⚠️ STT failed with status {response.status_code}: {response.text}"
                    )
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
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
                else:
                    logging.debug("Empty transcript received")
                
                return  # Success, exit retry loop

            except requests.exceptions.Timeout:
                logging.warning(f"⚠️ STT timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
            except Exception as e:
                logging.error(f"❌ STT error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return

    # ---------------- Utility ----------------

    def is_audio_playing(self):
        """Check if any audio session is active via PyCaw (Windows only)."""
        if not PYCAW_AVAILABLE:
            return False
        try:
            sessions = AudioUtilities.GetAllSessions()
            for session in sessions:
                if session.State == 1:  # active
                    return True
        except Exception as e:
            logging.error(f"PyCaw error: {e}")
        return False
