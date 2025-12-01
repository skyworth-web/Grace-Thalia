# app/ui/caption_window.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout, QLabel
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCursor
from services.api_client import APIClient
import logging

logging.basicConfig(level=logging.INFO)


class CaptionWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Live Captions")
        self.setGeometry(100, 100, 800, 200)

        # Always on top, frameless
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.api = APIClient()
        self.caption_history = []

        layout = QVBoxLayout()

        # Caption area
        self.caption_text_edit = QTextEdit()
        self.caption_text_edit.setReadOnly(True)
        self.caption_text_edit.setStyleSheet(
            """
            QTextEdit {
                font-size: 20px;
                color: #00ff95;
                background-color: rgba(0, 0, 0, 200);
                border-radius: 8px;
                padding: 8px;
            }
            """
        )
        self.caption_text_edit.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        layout.addWidget(self.caption_text_edit)

        # Answer area (for GPT answer)
        self.answer_label = QLabel("")
        self.answer_label.setStyleSheet("font-size: 16px; color: #ffffff;")
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

    def update_caption(self, text: str):
        """Append new transcript chunk to the live caption view."""
        logging.info(f"CaptionWindow.update_caption: {text!r}")

        if not text or not text.strip():
            return

        self.caption_history.append(text.strip())
        # Keep last few chunks to make it readable like Chrome live captions
        self.caption_history = self.caption_history[-8:]

        joined = " ".join(self.caption_history)
        self.caption_text_edit.setPlainText(joined)

        # Scroll to end
        cursor = self.caption_text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.caption_text_edit.setTextCursor(cursor)

    def clear_text(self):
        self.caption_history = []
        self.caption_text_edit.clear()
        self.answer_label.setText("")

    def generate_answer(self):
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
