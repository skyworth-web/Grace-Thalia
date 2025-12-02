# app/audio/mic_stream.py

import pyaudio
import wave
import threading
import logging
import time
import requests
import io
import numpy as np
from queue import Queue
from concurrent.futures import ThreadPoolExecutor
from collections import deque
import platform

# sounddevice for WASAPI loopback (Windows system audio capture)
try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False
    logging.warning("sounddevice not available. System audio capture may be limited.")

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
MIC_DEVICE_INDEX = None  # Will use default if None
USE_WASAPI_LOOPBACK = True  # Use WASAPI loopback for system audio (Windows only)

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
        self.speaker_stream_sd = None  # sounddevice stream for WASAPI loopback
        self.speaker_queue = Queue()  # Queue for system audio from sounddevice
        self.is_windows = platform.system() == "Windows"

        # Real-time streaming parameters - smaller chunks with overlap
        self.chunk_duration = 0.8  # seconds per chunk (smaller for lower latency)
        self.overlap_duration = 0.4  # seconds of overlap (50% overlap)
        self.bytes_per_frame = 2 * CHANNELS  # 16-bit = 2 bytes * channels
        self.frames_per_chunk = int(self.chunk_duration * RATE)
        self.bytes_per_chunk = self.frames_per_chunk * self.bytes_per_frame
        self.overlap_bytes = int(self.overlap_duration * RATE * self.bytes_per_frame)
        
        # Sliding window buffer for overlapping chunks
        self.audio_buffer = deque(maxlen=int(3 * RATE * self.bytes_per_frame))  # Keep ~3 seconds max
        
        # Thread pool for concurrent STT processing (reduced to prevent overload)
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="STT")
        self.stt_queue = Queue()
        
        # Request throttling - track last request time
        self.last_request_time = 0
        self.min_request_interval = 0.5  # Minimum 0.5 seconds between requests
        
        # Track last processed position to avoid duplicate processing
        self.last_processed_pos = 0
        self.pending_requests = 0  # Track number of pending requests

    # ---------------- Recording control ----------------

    def start_recording(self):
        """Start recording from microphone and speaker."""
        if self.running:
            logging.warning("Recording already started")
            return

        # Decide which device index to use for mic
        mic_index = self.device_index if self.device_index is not None else MIC_DEVICE_INDEX

        self.running = True

        try:
            # Mic stream
            logging.info(f"Opening mic stream with device index {mic_index}")
            try:
                self.mic_stream = self.p.open(
                    format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    input_device_index=mic_index,
                    frames_per_buffer=CHUNK,
                )
                logging.info(f"✅ Mic stream opened successfully with device {mic_index}")
            except Exception as e:
                # Fallback to default device (None) if specified device fails
                if mic_index is not None:
                    logging.warning(f"⚠️ Failed to open device {mic_index}: {e}. Trying default device...")
                    try:
                        self.mic_stream = self.p.open(
                            format=FORMAT,
                            channels=CHANNELS,
                            rate=RATE,
                            input=True,
                            input_device_index=None,  # Use default device
                            frames_per_buffer=CHUNK,
                        )
                        logging.info("✅ Mic stream opened successfully with default device")
                    except Exception as e2:
                        logging.error(f"❌ Failed to open default device: {e2}")
                        self.running = False
                        raise
                else:
                    raise
        except Exception as e:
            logging.error(f"❌ Failed to open mic stream: {e}")
            self.running = False
            raise

        # System audio capture - use WASAPI loopback on Windows (doesn't interfere with playback)
        if USE_WASAPI_LOOPBACK and self.is_windows and SOUNDDEVICE_AVAILABLE:
            try:
                logging.info("Attempting to open WASAPI loopback stream for system audio...")
                # List all devices to help debug
                try:
                    all_devices = sd.query_devices()
                    logging.info("📋 Available audio devices:")
                    for i, dev in enumerate(all_devices):
                        if dev['max_output_channels'] > 0:
                            logging.info(f"  Output {i}: {dev['name']} (hostapi: {dev.get('hostapi_name', 'unknown')})")
                    
                    # Find default output device for loopback
                    default_output = sd.query_devices(kind='output')
                    if default_output:
                        device_id = default_output['index']
                        device_name = default_output['name']
                        hostapi_name = default_output.get('hostapi_name', 'unknown')
                        logging.info(f"🎯 Selected output device {device_id}: {device_name} (hostapi: {hostapi_name})")
                        
                        # Start a background thread to capture system audio via WASAPI loopback
                        self.speaker_capture_thread = threading.Thread(
                            target=self._capture_system_audio_loopback,
                            args=(device_id,),
                            daemon=True
                        )
                        self.speaker_capture_thread.start()
                        logging.info("✅ WASAPI loopback thread started")
                    else:
                        raise Exception("No default output device found")
                except Exception as e:
                    logging.warning(f"⚠️ Could not find default output device: {e}. Trying fallback method...")
                    self._try_fallback_speaker_stream()
            except Exception as e:
                logging.warning(f"⚠️ WASAPI loopback not available: {e}. Trying fallback method...")
                self._try_fallback_speaker_stream()
        else:
            if not self.is_windows:
                logging.info("⚠️ WASAPI loopback is Windows-only. Using fallback method.")
            if not SOUNDDEVICE_AVAILABLE:
                logging.warning("⚠️ sounddevice not available. Using fallback method.")
            self._try_fallback_speaker_stream()

        logging.info("🎤 Recording started - Live captions active")

        # Start threads
        self.recording_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.recording_thread.start()
        logging.info("✅ Recording thread started")

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
            
            if self.speaker_stream_sd is not None:
                self.speaker_stream_sd.stop()
                self.speaker_stream_sd = None

            if self.p is not None:
                self.p.terminate()
                self.p = None

            # Clear buffers
            self.audio_buffer.clear()
            
            logging.info("Recording stopped")
        except Exception as e:
            logging.error(f"Error while stopping recording: {e}")

    # ---------------- Internal loops ----------------
    
    def _try_fallback_speaker_stream(self):
        """Fallback to PyAudio for system audio (may interfere with playback)."""
        try:
            # Try to find a "Stereo Mix" or similar device
            devices = []
            for i in range(self.p.get_device_count()):
                info = self.p.get_device_info_by_index(i)
                if info['maxInputChannels'] > 0:
                    devices.append((i, info['name']))
                    # Look for "Stereo Mix", "What U Hear", or similar
                    if any(keyword in info['name'].lower() for keyword in ['stereo mix', 'what u hear', 'loopback']):
                        logging.info(f"Found system audio device: {info['name']} (index {i})")
                        try:
                            self.speaker_stream = self.p.open(
                                format=FORMAT,
                                channels=CHANNELS,
                                rate=RATE,
                                input=True,
                                input_device_index=i,
                                frames_per_buffer=CHUNK,
                            )
                            logging.info("✅ Fallback speaker stream opened successfully")
                            return
                        except Exception as e:
                            logging.warning(f"⚠️ Failed to open device {i}: {e}")
            
            logging.warning("⚠️ No suitable system audio device found. Continuing with mic only.")
            self.speaker_stream = None
        except Exception as e:
            logging.warning(f"⚠️ Error setting up fallback speaker stream: {e}")
            self.speaker_stream = None
    
    def _capture_system_audio_loopback(self, device_id):
        """Capture system audio using WASAPI loopback (runs in background thread)."""
        callback_count = 0
        try:
            def audio_callback(indata, frames, time_info, status):
                """Callback for sounddevice to capture system audio."""
                nonlocal callback_count
                callback_count += 1
                if status:
                    logging.warning(f"⚠️ Audio callback status: {status}")
                
                # Log periodically to confirm callback is working
                if callback_count % 100 == 0:
                    logging.debug(f"🔊 WASAPI loopback callback #{callback_count}, frames: {frames}, shape: {indata.shape}")
                
                # Convert float32 to int16 and queue for mixing
                # Handle both mono and stereo
                if indata.ndim == 1:
                    # Mono - duplicate to stereo
                    indata = np.column_stack((indata, indata))
                elif indata.shape[1] != CHANNELS:
                    # Ensure correct channel count
                    if indata.shape[1] == 1:
                        indata = np.column_stack((indata[:, 0], indata[:, 0]))
                    else:
                        indata = indata[:, :CHANNELS]
                
                # Convert to int16
                audio_int16 = (indata * 32767).astype(np.int16)
                audio_bytes = audio_int16.tobytes()
                
                # Put in queue (non-blocking, drop if queue is full to prevent lag)
                try:
                    self.speaker_queue.put_nowait(audio_bytes)
                except:
                    # Queue full, drop this chunk to prevent lag
                    if callback_count % 500 == 0:
                        logging.warning("⚠️ Speaker queue full, dropping audio chunks")
            
            # List all devices to find the right one
            logging.info("🔍 Listing available audio devices for loopback...")
            devices = sd.query_devices()
            for i, dev in enumerate(devices):
                if dev['max_output_channels'] > 0:
                    logging.info(f"  Output device {i}: {dev['name']} (hostapi: {dev['hostapi']})")
            
            # Try to use WASAPI backend explicitly
            # On Windows, opening an InputStream on an output device should enable loopback
            # But we need to make sure we're using the WASAPI hostapi
            wasapi_devices = [i for i, dev in enumerate(devices) 
                            if dev['max_output_channels'] > 0 and 'wasapi' in dev.get('hostapi_name', '').lower()]
            
            if wasapi_devices:
                # Prefer WASAPI devices
                loopback_device = wasapi_devices[0] if device_id not in wasapi_devices else device_id
                logging.info(f"🎯 Using WASAPI device {loopback_device}: {devices[loopback_device]['name']}")
            else:
                loopback_device = device_id
                logging.info(f"🎯 Using device {loopback_device}: {devices[loopback_device]['name']}")
            
            # Open WASAPI loopback stream on output device
            # On Windows with WASAPI, opening InputStream on output device enables loopback
            # Try to explicitly use WASAPI backend
            try:
                # Set default host API to WASAPI if available
                hostapis = sd.query_hostapis()
                wasapi_hostapi = None
                for hostapi in hostapis:
                    if 'wasapi' in hostapi['name'].lower():
                        wasapi_hostapi = hostapi['index']
                        logging.info(f"🎯 Found WASAPI host API: {hostapi['name']} (index {wasapi_hostapi})")
                        break
                
                # Open stream - sounddevice should automatically enable loopback when opening
                # an InputStream on an output device with WASAPI
                self.speaker_stream_sd = sd.InputStream(
                    device=loopback_device,
                    channels=CHANNELS,
                    samplerate=RATE,
                    dtype='float32',
                    blocksize=CHUNK,
                    callback=audio_callback,
                    latency='low'
                )
                self.speaker_stream_sd.start()
                logging.info(f"✅ WASAPI loopback stream started (device {loopback_device})")
                
                # Wait a moment to see if callback starts
                time.sleep(0.5)
                if callback_count == 0:
                    logging.warning("⚠️ WASAPI callback not being called - loopback may not be working")
            except Exception as stream_error:
                logging.error(f"❌ Failed to start WASAPI loopback stream: {stream_error}")
                raise
            
            # Keep thread alive while running and monitor
            last_log_time = time.time()
            while self.running:
                if self.speaker_stream_sd.active:
                    # Log queue status periodically
                    current_time = time.time()
                    if current_time - last_log_time > 5.0:  # Every 5 seconds
                        queue_size = self.speaker_queue.qsize()
                        logging.info(f"🔊 WASAPI loopback active: callbacks={callback_count}, queue_size={queue_size}")
                        last_log_time = current_time
                else:
                    logging.error("❌ WASAPI loopback stream became inactive!")
                    break
                time.sleep(0.1)
        except Exception as e:
            logging.error(f"❌ Error in WASAPI loopback capture: {e}", exc_info=True)
            self.speaker_stream_sd = None

    def _capture_loop(self):
        """Continuously capture audio from mic + speaker and send overlapping segments to STT."""
        try:
            chunk_interval = self.chunk_duration - self.overlap_duration  # Time between chunk starts
            last_chunk_time = time.time()
            chunk_count = 0
            
            logging.info(f"🎤 Capture loop started (chunk interval: {chunk_interval:.2f}s)")
            
            while self.running:
                try:
                    mic_data = self.mic_stream.read(CHUNK, exception_on_overflow=False)
                    
                    # Get system audio from WASAPI loopback (if available) or fallback
                    speaker_data = None
                    if self.speaker_stream_sd is not None and self.speaker_stream_sd.active:
                        # Try to get audio from WASAPI loopback queue (non-blocking)
                        # Get the most recent chunk if multiple are queued (to avoid lag)
                        latest_chunk = None
                        try:
                            while True:
                                latest_chunk = self.speaker_queue.get_nowait()
                        except:
                            speaker_data = latest_chunk  # Use the last chunk we got, or None if queue was empty
                        
                        # Debug: log if we're not getting speaker data
                        if speaker_data is None and chunk_count % 100 == 0:
                            queue_size = self.speaker_queue.qsize()
                            logging.warning(f"⚠️ No speaker data available (queue_size={queue_size}, active={self.speaker_stream_sd.active})")
                    elif self.speaker_stream is not None:
                        # Fallback: read from PyAudio stream
                        try:
                            speaker_data = self.speaker_stream.read(CHUNK, exception_on_overflow=False)
                        except Exception as e:
                            logging.warning(f"⚠️ Error reading speaker stream: {e}")
                    
                    # Mix mic + speaker audio if available
                    if speaker_data:
                        mixed_audio = self._mix_audio(mic_data, speaker_data)
                    else:
                        mixed_audio = mic_data
                    
                    # Add mixed audio to sliding window buffer
                    self.audio_buffer.extend(mixed_audio)

                    # Send overlapping chunks at regular intervals (like Windows Live Caption)
                    current_time = time.time()
                    if current_time - last_chunk_time >= chunk_interval:
                        buffer_size = len(self.audio_buffer)
                        if buffer_size >= self.bytes_per_chunk:
                            # Throttle requests to prevent backend overload
                            time_since_last = current_time - self.last_request_time
                            if time_since_last >= self.min_request_interval and self.pending_requests < 2:
                                # Extract chunk with overlap from buffer
                                chunk_data = bytes(list(self.audio_buffer)[-self.bytes_per_chunk:])
                                
                                # Submit to thread pool for async processing
                                self.pending_requests += 1
                                self.executor.submit(self._send_segment_to_backend, chunk_data)
                                
                                chunk_count += 1
                                last_chunk_time = current_time
                                self.last_request_time = current_time
                                logging.info(
                                    f"🎤 Queued chunk #{chunk_count}: {len(chunk_data)} bytes for STT "
                                    f"(buffer: {buffer_size} bytes, pending: {self.pending_requests})"
                                )
                            else:
                                logging.debug(
                                    f"⏸️ Request throttled (interval: {time_since_last:.2f}s, "
                                    f"pending: {self.pending_requests})"
                                )
                        else:
                            logging.debug(
                                f"⚠️ Buffer not ready: {buffer_size}/{self.bytes_per_chunk} bytes "
                                f"(need {self.bytes_per_chunk - buffer_size} more)"
                            )

                    time.sleep(0.001)  # Very small sleep for real-time responsiveness
                    
                except Exception as e:
                    logging.error(f"❌ Error reading audio in capture loop: {e}")
                    if not self.running:
                        break
                    time.sleep(0.1)  # Brief pause before retrying

        except Exception as e:
            logging.error(f"❌ Fatal error in capture loop: {e}", exc_info=True)
            self.running = False

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
        max_retries = 1  # Reduced retries to prevent backlog
        retry_delay = 0.1
        
        try:
            for attempt in range(max_retries):
                try:
                    with io.BytesIO() as wav_buffer:
                        with wave.open(wav_buffer, "wb") as wf:
                            wf.setnchannels(CHANNELS)
                            wf.setsampwidth(self.p.get_sample_size(FORMAT))
                            wf.setframerate(RATE)
                            wf.writeframes(audio_bytes)

                        wav_data = wav_buffer.getvalue()

                    logging.info(f"🎤 Sending audio to backend ({len(wav_data)} bytes, attempt {attempt + 1})")

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
                    error_msg = json_data.get("error", "")

                    if error_msg:
                        logging.error(f"❌ STT error from backend: {error_msg}")
                        return

                    if text:
                        logging.info(f"📝 Transcript received: {text}")
                        # IMPORTANT: this callback will be a Qt signal emitter,
                        # so calling it from this thread is SAFE.
                        try:
                            self.callback(text)
                            logging.debug(f"✅ Callback executed successfully")
                        except Exception as cb_err:
                            logging.error(f"❌ Error in callback: {cb_err}", exc_info=True)
                    else:
                        logging.debug("⚠️ Empty transcript received from STT (no speech detected)")
                    
                    return  # Success, exit retry loop

                except requests.exceptions.Timeout:
                    logging.warning(f"⚠️ STT timeout (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                except requests.exceptions.ConnectionError as e:
                    logging.error(f"❌ STT connection error: {e}. Is the server running at {self.stt_url}?")
                    return  # Don't retry connection errors
                except Exception as e:
                    logging.error(f"❌ STT error: {e}", exc_info=True)
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    return
        finally:
            # Always decrement pending requests counter
            self.pending_requests = max(0, self.pending_requests - 1)

    # ---------------- Audio Processing ----------------

    def _mix_audio(self, mic_data: bytes, speaker_data: bytes) -> bytes:
        """Mix microphone and speaker audio streams."""
        try:
            # Convert bytes to numpy arrays
            mic_array = np.frombuffer(mic_data, dtype=np.int16)
            speaker_array = np.frombuffer(speaker_data, dtype=np.int16)
            
            # Ensure same length (should be same, but safety check)
            min_len = min(len(mic_array), len(speaker_array))
            if min_len < len(mic_array) or min_len < len(speaker_array):
                mic_array = mic_array[:min_len]
                speaker_array = speaker_array[:min_len]
            
            # Mix audio: average of both signals (can be adjusted)
            # Using 50/50 mix, but you can weight them differently
            mixed = (mic_array.astype(np.int32) + speaker_array.astype(np.int32)) // 2
            
            # Clip to prevent overflow
            mixed = np.clip(mixed, -32768, 32767).astype(np.int16)
            
            # Convert back to bytes
            return mixed.tobytes()
        except Exception as e:
            logging.warning(f"⚠️ Error mixing audio: {e}, using mic only")
            return mic_data

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
