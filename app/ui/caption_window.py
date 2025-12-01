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

        # Status label
        self.status_label = QLabel("🔴 Waiting for audio...")
        self.status_label.setStyleSheet("font-size: 12px; color: #ffaa00; padding: 4px;")
        layout.addWidget(self.status_label)

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
        
        # Show initial message
        self.caption_text_edit.setPlainText("Waiting for audio... Speak into your microphone.")

    def set_recording_status(self, is_recording: bool):
        """Update status label based on recording state."""
        if is_recording:
            self.status_label.setText("🟢 Recording... Listening for audio...")
            self.status_label.setStyleSheet("font-size: 12px; color: #00ff95; padding: 4px;")
        else:
            self.status_label.setText("🔴 Recording stopped")
            self.status_label.setStyleSheet("font-size: 12px; color: #ff4444; padding: 4px;")

    def update_caption(self, text: str):
        """Append new transcript chunk to the live caption view with smart merging (Windows Live Caption style)."""
        logging.info(f"📝 CaptionWindow.update_caption called with: {text!r}")
        
        if not text or not text.strip():
            logging.warning("⚠️ Empty text in update_caption")
            return

        import time
        current_time = time.time()
        
        # Update status to show we're receiving updates
        self.status_label.setText("🟢 Live captions active - receiving audio...")
        self.status_label.setStyleSheet("font-size: 12px; color: #00ff95; padding: 4px;")
        
        # Add new text to full transcript
        new_text = text.strip()
        
        # Windows Live Caption style: simple append with basic deduplication
        if self.full_transcript:
            # Get last few words for overlap detection
            last_words_list = self.full_transcript.split()[-8:]  # Last 8 words
            last_words = " ".join(last_words_list).lower()
            new_text_lower = new_text.lower()
            
            # Check for exact duplicate
            if new_text_lower == last_words:
                return
            
            # Check if new text starts with words we already have (overlap)
            # Find how many words overlap
            new_words = new_text.split()
            overlap_found = False
            
            for i in range(min(len(new_words), len(last_words_list)), 0, -1):
                new_prefix = " ".join(new_words[:i]).lower()
                if last_words.endswith(new_prefix):
                    # Found overlap, add only the new part
                    if i < len(new_words):
                        remaining_words = new_words[i:]
                        self.full_transcript += " " + " ".join(remaining_words)
                        overlap_found = True
                    break
            
            # No overlap found, just append
            if not overlap_found:
                self.full_transcript += " " + new_text
        else:
            # First chunk
            self.full_transcript = new_text

        # Windows Live Caption style: Show recent text (last 2-3 lines, ~50-80 words)
        # This gives the real-time streaming feel
        all_words = self.full_transcript.split()
        # Show last 60 words for better readability (like Windows Live Caption)
        display_words = all_words[-60:] if len(all_words) > 60 else all_words
        display_text = " ".join(display_words)
        
        # Update the display immediately (must be called from GUI thread)
        logging.info(f"📺 Setting caption text ({len(display_words)} words): {display_text[:100]}...")
        
        # Use setPlainText which is thread-safe when called from GUI thread
        self.caption_text_edit.setPlainText(display_text)

        # Auto-scroll to end for real-time feel
        cursor = self.caption_text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.caption_text_edit.setTextCursor(cursor)
        
        # Update the widget (no repaint needed - Qt handles it)
        
        self.last_update_time = current_time
        logging.debug(f"✅ Caption display updated at {current_time}")

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
