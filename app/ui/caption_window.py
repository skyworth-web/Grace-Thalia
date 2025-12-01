# app/ui/caption_window.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout, QLabel
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QTextCursor
from services.api_client import APIClient
import logging
import asyncio
import threading
from queue import Queue

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
        
        # For streaming answers
        self.answer_queue = Queue()
        self.answer_timer = QTimer()
        self.answer_timer.timeout.connect(self._process_answer_queue)
        self.answer_timer.setInterval(50)  # Update every 50ms for smooth streaming
        self.is_streaming = False
        self.current_answer = ""

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
            last_words_list = self.full_transcript.split()[-10:]  # Last 10 words
            last_words = " ".join(last_words_list).lower()
            new_text_lower = new_text.lower()
            new_words = new_text.split()
            
            # Aggressive filtering: If new text is a single common word and it appears in last 5 words, skip it
            if len(new_words) == 1:
                common_words = ["you", "uh", "um", "ah", "eh", "oh", "hmm", "mm", "the", "a", "an", "is", "are"]
                if new_words[0].lower() in common_words:
                    # Check if this word appears in the last 5 words
                    recent_words = [w.lower() for w in last_words_list[-5:]]
                    if new_words[0].lower() in recent_words:
                        logging.debug(f"🔇 Skipping duplicate common word: {new_text}")
                        return
            
            # Check for exact duplicate with last few words
            if new_text_lower == last_words or new_text_lower in last_words:
                logging.debug(f"🔇 Skipping exact duplicate: {new_text}")
                return
            
            # Check if new text starts with words we already have (overlap)
            # Find how many words overlap
            overlap_found = False
            
            for i in range(min(len(new_words), len(last_words_list)), 0, -1):
                new_prefix = " ".join(new_words[:i]).lower()
                if last_words.endswith(new_prefix):
                    # Found overlap, add only the new part
                    if i < len(new_words):
                        remaining_words = new_words[i:]
                        self.full_transcript += " " + " ".join(remaining_words)
                        overlap_found = True
                    else:
                        # Complete overlap, skip
                        logging.debug(f"🔇 Skipping complete overlap: {new_text}")
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
        # Use full_transcript instead of displayed text to get complete transcript
        transcript = self.full_transcript.strip() if self.full_transcript else self.caption_text_edit.toPlainText().strip()
        
        if not transcript:
            self.answer_label.setText("⚠️ No text to generate an answer. Please start live captions first.")
            logging.warning("⚠️ Generate button clicked but no transcript available")
            return

        # Don't start new stream if one is already running
        if self.is_streaming:
            logging.warning("⚠️ Stream already in progress, ignoring request")
            return

        logging.info(f"🔄 Starting streaming answer for transcript: {transcript[:100]}...")
        self.answer_label.setText("⏳ Generating answer...")
        self.is_streaming = True
        
        # Clear previous answer chunks
        self.answer_queue = Queue()
        self.current_answer = ""
        
        # Start streaming in background thread
        threading.Thread(
            target=self._stream_answer_background,
            args=(transcript,),
            daemon=True
        ).start()
        
        # Start timer to process answer chunks
        if not self.answer_timer.isActive():
            self.answer_timer.start()
    
    def _stream_answer_background(self, transcript: str):
        """Background thread for streaming answer from API."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            async def stream():
                try:
                    async for chunk in self.api.stream_answer(transcript):
                        if chunk:
                            self.answer_queue.put(chunk)
                            logging.debug(f"📥 Received chunk: {chunk[:50]}...")
                except Exception as e:
                    error_msg = f"❌ Streaming error: {str(e)}"
                    logging.error(error_msg, exc_info=True)
                    self.answer_queue.put(error_msg)
                finally:
                    # Signal end of stream
                    self.answer_queue.put(None)  # None signals end of stream
            
            loop.run_until_complete(stream())
        except Exception as e:
            error_msg = f"❌ Error in stream thread: {str(e)}"
            logging.error(error_msg, exc_info=True)
            self.answer_queue.put(error_msg)
            self.answer_queue.put(None)
        finally:
            loop.close()
    
    def _process_answer_queue(self):
        """Process answer chunks from queue and update GUI (runs on GUI thread)."""
        try:
            # Process all available chunks
            while True:
                try:
                    chunk = self.answer_queue.get_nowait()
                    
                    if chunk is None:
                        # End of stream
                        self.is_streaming = False
                        self.answer_timer.stop()
                        logging.info("✅ Answer streaming completed")
                        break
                    
                    # Append chunk to current answer
                    self.current_answer += chunk
                    self.answer_label.setText(self.current_answer)
                    logging.debug(f"📺 Updated answer display ({len(self.current_answer)} chars)")
                    
                except:
                    break
            
            # Keep timer running if still streaming
            if self.is_streaming and not self.answer_queue.empty():
                if not self.answer_timer.isActive():
                    self.answer_timer.start()
            elif not self.is_streaming:
                self.answer_timer.stop()
                
        except Exception as e:
            logging.error(f"❌ Error processing answer queue: {e}", exc_info=True)
            self.is_streaming = False
            self.answer_timer.stop()
