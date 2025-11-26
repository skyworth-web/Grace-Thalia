# app/ui/caption_window.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCursor
from services.api_client import APIClient
import logging

logging.basicConfig(level=logging.INFO)


class CaptionWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Live Captions")
        self.setGeometry(100, 100, 600, 200)
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.api = APIClient()

        layout = QVBoxLayout()

        # Caption area (scrolling, like Chrome/Windows captions)
        self.caption_text_edit = QTextEdit()
        self.caption_text_edit.setStyleSheet("font-size: 20px; color: #00ff95;")
        self.caption_text_edit.setReadOnly(True)
        self.caption_text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.caption_text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.caption_text_edit)

        # Answer area (optional GPT answer)
        self.answer_label = QLabel("")
        self.answer_label.setStyleSheet("font-size: 18px; color: #ffffff;")
        self.answer_label.setWordWrap(True)
        layout.addWidget(self.answer_label)

        # Buttons
        button_layout = QHBoxLayout()
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_text)
        self.generate_button = QPushButton("Generate")
        self.generate_button.clicked.connect(self.generate_answer)
        button_layout.addWidget(self.clear_button)
        button_layout.addWidget(self.generate_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    # ------------------------------------------------------------------ #
    # Public API: called from MainWindow.on_transcript_ui
    # ------------------------------------------------------------------ #
    def update_caption(self, text: str):
        """Append new caption line and scroll to the bottom."""
        logging.info(f"[CaptionWindow] Updating caption with text: {text!r}")

        current = self.caption_text_edit.toPlainText().strip()
        if current:
            new_text = current + "\n" + text
        else:
            new_text = text

        self.caption_text_edit.setPlainText(new_text)

        # Auto-scroll to bottom
        cursor = self.caption_text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.caption_text_edit.setTextCursor(cursor)

    def clear_text(self):
        self.caption_text_edit.clear()
        self.answer_label.setText("")

    def generate_answer(self):
        """Send all caption text to /generate and display the answer."""
        transcript = self.caption_text_edit.toPlainText().strip()
        if not transcript:
            self.answer_label.setText("⚠️ No text to generate an answer.")
            return

        try:
            response = self.api.generate(transcript)
            answer = response.get("answer", "⚠️ No answer received.")
            self.answer_label.setText(answer)
        except Exception as e:
            self.answer_label.setText(f"⚠️ Error: {str(e)}")
