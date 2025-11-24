from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit, QFileDialog
)

from backend.api_client import APIClient
from audio.mic_stream import MicrophoneStreamer
from ui.caption_window import CaptionWindow
import asyncio
import threading

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.api = APIClient()
        self.caption_window = CaptionWindow()
        self.streamer = MicrophoneStreamer(self.handle_transcript)

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Interview Co-Pilot+ (Desktop)")
        self.setGeometry(200, 200, 700, 600)

        layout = QVBoxLayout()

        title = QLabel("🧠 Interview Co-Pilot+")
        title.setStyleSheet("font-size: 28px; font-weight: bold;")
        layout.addWidget(title)

        # Resume Input
        layout.addWidget(QLabel("Paste Resume:"))
        self.resume_box = QTextEdit()
        layout.addWidget(self.resume_box)

        # JD Input
        layout.addWidget(QLabel("Paste Job Description:"))
        self.jd_box = QTextEdit()
        layout.addWidget(self.jd_box)

        self.ingest_btn = QPushButton("Ingest Resume & JD")
        self.ingest_btn.clicked.connect(self.ingest)
        layout.addWidget(self.ingest_btn)

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

    def ingest(self):
        resume = self.resume_box.toPlainText()
        jd = self.jd_box.toPlainText()

        r = self.api.ingest(resume, jd)
        self.answer_box.setText(str(r))

    def start_captions(self):
        self.caption_window.show()
        self.streamer.start()

    def stop_captions(self):
        self.streamer.stop()

    def handle_transcript(self, text):
        self.caption_window.update_caption(text)

        # stream GPT answer
        threading.Thread(target=self.get_answer, args=(text,), daemon=True).start()

    def get_answer(self, transcript):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def stream():
            async for chunk in self.api.stream_answer(transcript):
                current = self.answer_box.toPlainText()
                self.answer_box.setPlainText(current + chunk)

        loop.run_until_complete(stream())
