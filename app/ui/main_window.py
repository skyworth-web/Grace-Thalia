# app/ui/main_window.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QComboBox,
    QTextEdit, QFileDialog
)
from PyQt6.QtCore import pyqtSignal, QTimer, pyqtSlot
import threading
from services.api_client import APIClient
from audio.mic_stream import MicStream
from ui.caption_window import CaptionWindow
import asyncio
import threading
import sounddevice as sd
import os
import logging
import time

logging.basicConfig(level=logging.INFO)


class MainWindow(QWidget):
    # Signal that carries transcript text safely to the GUI thread
    transcript_received = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        self.api = APIClient()
        self.caption_window = CaptionWindow()

        # Use a thread-safe queue for transcript updates
        # Process directly in timer callback (GUI thread) - no signals to avoid thread issues
        from queue import Queue
        self.transcript_queue = Queue()
        self.transcript_timer = QTimer()
        self.transcript_timer.timeout.connect(self._process_transcript_queue)
        self.transcript_timer.setSingleShot(False)
        self.transcript_timer.setInterval(20)  # Process every 20ms for real-time feel
        
        # Filtering for false positives (STT hallucinations)
        self.recent_transcripts = []  # Track recent transcripts to filter duplicates
        self.last_transcript_time = {}  # Track when we last saw each transcript
        self.filter_window = 2.0  # Ignore same transcript if seen within 2 seconds

        # MicStream callback - PyQt signals are thread-safe, emit directly
        # But we'll use queue for batching multiple transcripts
        self.streamer = MicStream(
            stt_url="http://localhost:8000/stt",
            callback=self._on_transcript_received
        )

        # Initialize UI
        self.init_ui()
    
    def _on_transcript_received(self, text: str, full_transcript: str = None):
        """Called from worker thread when transcript is received."""
        if text and text.strip():
            # Add to queue as tuple (text, full_transcript)
            self.transcript_queue.put((text.strip(), full_transcript.strip() if full_transcript else None))
            logging.info(f"📥 Queued transcript: {text[:50]}...")
            # Start timer to process queue (safe to call from any thread via singleShot)
            if not self.transcript_timer.isActive():
                QTimer.singleShot(0, self.transcript_timer.start)
    
    def _should_filter_transcript(self, text: str) -> bool:
        """Filter out false positives and hallucinations from STT."""
        text_lower = text.strip().lower()
        
        # Filter empty or very short transcripts (likely noise)
        if len(text_lower) < 2:
            logging.debug(f"🔇 Filtered: too short ({text_lower})")
            return True
        
        # Filter common single-word hallucinations that appear during silence
        common_hallucinations = ["you", "uh", "um", "ah", "eh", "oh", "hmm", "mm"]
        words = text_lower.split()
        if len(words) == 1 and words[0] in common_hallucinations:
            # Check if we've seen this recently (within filter_window seconds)
            current_time = time.time()
            last_seen = self.last_transcript_time.get(text_lower, 0)
            
            if current_time - last_seen < self.filter_window:
                logging.debug(f"🔇 Filtered: duplicate hallucination '{text_lower}' (seen {current_time - last_seen:.1f}s ago)")
                return True
            
            # Update last seen time
            self.last_transcript_time[text_lower] = current_time
        
        # Filter if same transcript appears too frequently
        current_time = time.time()
        if text_lower in self.last_transcript_time:
            time_since_last = current_time - self.last_transcript_time[text_lower]
            if time_since_last < self.filter_window:
                logging.debug(f"🔇 Filtered: duplicate transcript '{text_lower}' (seen {time_since_last:.1f}s ago)")
                return True
        
        # Update tracking
        self.last_transcript_time[text_lower] = current_time
        
        # Keep recent transcripts list small (last 20)
        if len(self.recent_transcripts) > 20:
            self.recent_transcripts.pop(0)
        self.recent_transcripts.append((text_lower, current_time))
        
        return False
    
    def _process_transcript_queue(self):
        """Process queued transcripts on GUI thread."""
        try:
            # Process all available transcripts
            processed_count = 0
            filtered_count = 0
            texts_to_process = []
            
            # Collect all texts first
            while True:
                try:
                    item = self.transcript_queue.get_nowait()
                    texts_to_process.append(item)
                except:
                    break
            
            # Process them all - this ensures we're on GUI thread
            for item in texts_to_process:
                try:
                    # Unpack tuple (text, full_transcript) or handle string
                    if isinstance(item, tuple):
                        text, full_transcript = item
                    else:
                        text = item
                        full_transcript = None
                    
                    # Filter out false positives and hallucinations
                    if self._should_filter_transcript(text):
                        filtered_count += 1
                        continue
                    
                    logging.info(f"📤 Processing transcript: {text[:50]}...")
                    # Directly update caption window (we're on GUI thread)
                    self.caption_window.update_caption(text, full_transcript)
                    processed_count += 1
                except Exception as e:
                    logging.error(f"❌ Error processing transcript '{text[:50]}...': {e}", exc_info=True)
            
            if filtered_count > 0:
                logging.debug(f"🔇 Filtered {filtered_count} false positive transcripts")
            logging.debug(f"✅ Processed {processed_count} transcripts from queue")
            
            # Keep timer running if there's more in queue
            if self.transcript_queue.empty():
                self.transcript_timer.stop()
            else:
                # More items, keep timer running
                if not self.transcript_timer.isActive():
                    self.transcript_timer.start()
        except Exception as e:
            logging.error(f"❌ Error processing transcript queue: {e}", exc_info=True)
            self.transcript_timer.stop()

    def init_ui(self):
        self.setWindowTitle("Interview Co-Pilot+ (Desktop)")
        self.setGeometry(200, 200, 700, 600)

        layout = QVBoxLayout()

        title = QLabel("🧠 Interview Co-Pilot+")
        title.setStyleSheet("font-size: 28px; font-weight: bold;")
        layout.addWidget(title)

        # Resume Input
        layout.addWidget(QLabel("Upload Resume (PDF/DOC):"))
        self.resume_path = QLabel("No file selected")
        self.resume_path.setStyleSheet("font-size: 12px; color: gray;")
        layout.addWidget(self.resume_path)

        self.upload_resume_btn = QPushButton("Upload Resume")
        self.upload_resume_btn.clicked.connect(self.upload_resume)
        layout.addWidget(self.upload_resume_btn)

        # JD Input
        layout.addWidget(QLabel("Paste Job Description (Optional):"))
        self.jd_box = QTextEdit()
        layout.addWidget(self.jd_box)

        self.ingest_btn = QPushButton("Ingest Resume & JD")
        self.ingest_btn.clicked.connect(self.ingest)
        layout.addWidget(self.ingest_btn)

        # Device Selection ComboBox
        layout.addWidget(QLabel("Select Audio Device:"))
        self.device_combo = QComboBox()
        self.device_combo.currentIndexChanged.connect(self.select_device)
        layout.addWidget(self.device_combo)

        # Live transcription
        self.start_btn = QPushButton("🎤 Start Live Captions")
        self.start_btn.clicked.connect(self.start_captions)
        layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("🛑 Stop Live Captions")
        self.stop_btn.clicked.connect(self.stop_captions)
        layout.addWidget(self.stop_btn)

        # AI Answer
        layout.addWidget(QLabel("GPT Answer:"))
        self.answer_box = QTextEdit()
        layout.addWidget(self.answer_box)

        self.setLayout(layout)

        # List available devices
        self.list_devices()

    def list_devices(self):
        """List all available input devices and add to combo box."""
        devices = sd.query_devices()
        self.device_combo.clear()
        for i, device in enumerate(devices):
            if device["max_input_channels"] > 0:
                self.device_combo.addItem(device["name"], i)

        logging.info("Available input devices:")
        for i in range(self.device_combo.count()):
            logging.info(f"Device {i}: {self.device_combo.itemText(i)}")

    def select_device(self, index: int):
        """Handle device selection from combo box."""
        device_index = self.device_combo.currentData()
        if device_index is None:
            return

        device_info = sd.query_devices(device_index)

        if device_info["max_input_channels"] == 0:
            logging.error(
                f"❌ Selected device '{device_info['name']}' does not support input channels."
            )
            self.answer_box.setText(
                f"❌ Device '{device_info['name']}' does not support input channels."
            )
            return

        self.streamer.device_index = device_index
        logging.info(
            f"Selected device: {self.device_combo.currentText()} (index {device_index})"
        )

    def upload_resume(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Resume", "", "Documents (*.pdf *.doc *.docx)"
        )
        if file_path:
            self.resume_path.setText(os.path.basename(file_path))
            self.resume_file_path = file_path

    def ingest(self):
        try:
            resume = getattr(self, "resume_file_path", None)
            if not resume:
                self.answer_box.setText("⚠️ Please upload a resume file.")
                return

            jd = self.jd_box.toPlainText() or None

            response = self.api.ingest(resume, jd)
            self.answer_box.setText(str(response))
        except Exception as e:
            self.answer_box.setText(f"⚠️ Error: {str(e)}")

    def start_captions(self):
        self.caption_window.show()
        self.caption_window.set_recording_status(True)
        try:
            self.streamer.start_recording()
            logging.info("✅ Recording started successfully")
        except Exception as e:
            logging.error(f"❌ Failed to start recording: {e}")
            self.caption_window.set_recording_status(False)
            self.caption_window.caption_text_edit.setPlainText(f"❌ Error starting recording: {e}\n\nPlease check:\n1. Microphone is connected\n2. Correct audio device is selected\n3. Server is running at http://localhost:8000")

    def stop_captions(self):
        self.streamer.stop_recording()
        self.caption_window.set_recording_status(False)

    # --------- Called in the GUI thread via signal ---------


        # (optional) Start GPT answer streaming in background
        threading.Thread(
            target=self.get_answer,
            args=(text,),
            daemon=True,
        ).start()

    def get_answer(self, transcript: str):
        """Background thread for streaming GPT output."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def stream():
            async for chunk in self.api.stream_answer(transcript):
                current = self.answer_box.toPlainText()
                self.answer_box.setPlainText(current + chunk)

        loop.run_until_complete(stream())
        loop.close()
