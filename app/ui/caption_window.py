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
        self.full_transcript = ""  # Accumulated full transcript
        self.last_update_time = 0

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
        """Append new transcript chunk to the live caption view with smart merging."""
        logging.info(f"CaptionWindow.update_caption: {text!r}")

        if not text or not text.strip():
            return

        import time
        current_time = time.time()
        
        # Add new text to full transcript
        new_text = text.strip()
        
        # Smart merging: avoid duplicates by checking if new text overlaps with recent text
        # This handles overlapping chunks from the audio stream (Windows Live Caption style)
        if self.full_transcript:
            # Get recent words for comparison (last 15 words to catch overlaps)
            recent_text = " ".join(self.full_transcript.split()[-15:]).lower()
            new_text_lower = new_text.lower()
            
            # Simple overlap detection: if new text starts with words we already have
            # Find the longest prefix of new_text that appears in recent_text
            new_words = new_text.split()
            overlap_count = 0
            
            # Check if first few words of new_text match end of recent_text
            for i in range(1, min(len(new_words) + 1, 10)):  # Check up to 10 words
                prefix = " ".join(new_words[:i]).lower()
                if recent_text.endswith(prefix) or prefix in recent_text:
                    overlap_count = i
            
            # Only add non-overlapping words
            if overlap_count > 0 and overlap_count < len(new_words):
                remaining_words = new_words[overlap_count:]
                if remaining_words:
                    self.full_transcript += " " + " ".join(remaining_words)
            elif overlap_count == 0:
                # No overlap, add the whole new text
                self.full_transcript += " " + new_text
            # If overlap_count == len(new_words), the whole text is duplicate, skip it
        else:
            # First chunk
            self.full_transcript = new_text

        # Update display with recent portion (like Windows Live Caption)
        # Show last ~100 words for readability, but keep full transcript for context
        all_words = self.full_transcript.split()
        display_words = all_words[-100:] if len(all_words) > 100 else all_words
        display_text = " ".join(display_words)
        
        self.caption_text_edit.setPlainText(display_text)

        # Scroll to end for real-time feel
        cursor = self.caption_text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.caption_text_edit.setTextCursor(cursor)
        
        self.last_update_time = current_time

    def clear_text(self):
        self.caption_history = []
        self.full_transcript = ""
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
