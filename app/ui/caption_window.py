# app/ui/caption_window.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout, QLabel, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QTextCursor, QMouseEvent
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
        self.setGeometry(100, 100, 1000, 700)

        # Always on top, frameless, draggable
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Drag functionality
        self.drag_position = None

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
        self.current_question = ""  # Track current question for chat history
        
        # Chat history for context-aware answers
        self.chat_history = []  # List of {"question": str, "answer": str}

        # Main container with rounded corners and shadow
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # Header bar (for dragging and status)
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(10, 8, 10, 8)
        
        self.status_label = QLabel("🔴 Waiting for audio...")
        self.status_label.setStyleSheet("""
            font-size: 12px; 
            color: #ffaa00; 
            font-weight: bold;
            background: transparent;
        """)
        header_layout.addWidget(self.status_label)
        
        header_layout.addStretch()
        
        # Control buttons in header
        self.clear_button = QPushButton("🗑️ Clear")
        self.clear_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 68, 68, 150);
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(255, 68, 68, 200);
            }
            QPushButton:pressed {
                background-color: rgba(255, 68, 68, 255);
            }
        """)
        self.clear_button.clicked.connect(self.clear_text)
        header_layout.addWidget(self.clear_button)

        self.generate_button = QPushButton("✨ Generate Answer")
        self.generate_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 255, 149, 150);
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(0, 255, 149, 200);
            }
            QPushButton:pressed {
                background-color: rgba(0, 255, 149, 255);
            }
        """)
        self.generate_button.clicked.connect(self.generate_answer)
        header_layout.addWidget(self.generate_button)

        main_layout.addLayout(header_layout)

        # Question/Caption area
        question_label = QLabel("📝 Question (Live Caption):")
        question_label.setStyleSheet("""
            font-size: 13px; 
            color: #00ff95; 
            font-weight: bold;
            background: transparent;
            margin-bottom: 5px;
        """)
        main_layout.addWidget(question_label)

        self.caption_text_edit = QTextEdit()
        self.caption_text_edit.setReadOnly(True)
        self.caption_text_edit.setStyleSheet("""
            QTextEdit {
                font-size: 20px;
                color: #00ff95;
                background-color: rgba(0, 0, 0, 220);
                border: 2px solid rgba(0, 255, 149, 100);
                border-radius: 10px;
                padding: 15px;
                min-height: 150px;
                max-height: 300px;
            }
        """)
        self.caption_text_edit.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.caption_text_edit.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        main_layout.addWidget(self.caption_text_edit)

        # Answer area
        answer_label = QLabel("💬 AI Answer:")
        answer_label.setStyleSheet("""
            font-size: 13px; 
            color: #4da6ff; 
            font-weight: bold;
            background: transparent;
            margin-top: 10px;
            margin-bottom: 5px;
        """)
        main_layout.addWidget(answer_label)

        self.answer_text_edit = QTextEdit()
        self.answer_text_edit.setReadOnly(True)
        self.answer_text_edit.setStyleSheet("""
            QTextEdit {
                font-size: 20px;
                color: #4da6ff;
                background-color: rgba(0, 0, 0, 220);
                border: 2px solid rgba(77, 166, 255, 100);
                border-radius: 10px;
                padding: 15px;
                min-height: 100px;
            }
        """)
        self.answer_text_edit.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.answer_text_edit.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        # Auto-resize based on content
        self.answer_text_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred
        )
        main_layout.addWidget(self.answer_text_edit)

        # Add stretch to push content to top
        main_layout.addStretch()

        # Set main layout with background
        container = QWidget()
        container.setLayout(main_layout)
        container.setStyleSheet("""
            QWidget {
                background-color: rgba(20, 20, 30, 240);
                border-radius: 15px;
                border: 2px solid rgba(255, 255, 255, 30);
            }
        """)

        final_layout = QVBoxLayout()
        final_layout.setContentsMargins(0, 0, 0, 0)
        final_layout.addWidget(container)
        self.setLayout(final_layout)
        
        # Show initial message
        self.caption_text_edit.setPlainText("Waiting for audio... Speak into your microphone.")
        self.answer_text_edit.setPlainText("AI answers will appear here...")

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

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press for window dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Get global position and window position
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move for window dragging."""
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position:
            # Move window to new position
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def clear_text(self):
        self.caption_history = []
        self.full_transcript = ""
        self.caption_text_edit.clear()
        self.answer_text_edit.setPlainText("AI answers will appear here...")
        self.chat_history = []  # Clear chat history when clearing captions
        logging.info("🧹 Cleared chat history")

    def generate_answer(self):
        # Use full_transcript instead of displayed text to get complete transcript
        transcript = self.full_transcript.strip() if self.full_transcript else self.caption_text_edit.toPlainText().strip()
        
        if not transcript:
            self.answer_text_edit.setPlainText("⚠️ No text to generate an answer. Please start live captions first.")
            logging.warning("⚠️ Generate button clicked but no transcript available")
            return

        # Don't start new stream if one is already running
        if self.is_streaming:
            logging.warning("⚠️ Stream already in progress, ignoring request")
            return

        logging.info(f"🔄 Starting streaming answer for transcript: {transcript[:100]}...")
        logging.info(f"📜 Using chat history: {len(self.chat_history)} previous exchanges")
        self.answer_text_edit.setPlainText("⏳ Generating answer... Please wait...")
        self.is_streaming = True
        
        # Clear previous answer chunks
        self.answer_queue = Queue()
        self.current_answer = ""
        self.current_question = transcript  # Store current question for chat history
        
        # Start streaming in background thread with chat history
        threading.Thread(
            target=self._stream_answer_background,
            args=(transcript, self.chat_history.copy()),  # Pass copy of chat history
            daemon=True
        ).start()
        
        # Start timer to process answer chunks
        if not self.answer_timer.isActive():
            self.answer_timer.start()
    
    def _stream_answer_background(self, transcript: str, chat_history: list):
        """Background thread for streaming answer from API."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            async def stream():
                try:
                    async for chunk in self.api.stream_answer(transcript, chat_history):
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
                        # End of stream - add to chat history
                        if self.current_question and self.current_answer:
                            self.chat_history.append({
                                "question": self.current_question,
                                "answer": self.current_answer
                            })
                            # Keep only last 10 exchanges to avoid token bloat
                            if len(self.chat_history) > 10:
                                self.chat_history = self.chat_history[-10:]
                            logging.info(f"✅ Added to chat history. Total exchanges: {len(self.chat_history)}")
                        
                        self.is_streaming = False
                        self.answer_timer.stop()
                        self.current_question = ""  # Clear current question
                        logging.info("✅ Answer streaming completed")
                        break
                    
                    # Append chunk to current answer
                    self.current_answer += chunk
                    self.answer_text_edit.setPlainText(self.current_answer)
                    
                    # Auto-resize answer area based on content
                    doc = self.answer_text_edit.document()
                    doc.setTextWidth(self.answer_text_edit.viewport().width())
                    height = int(doc.size().height()) + 30  # Add padding
                    self.answer_text_edit.setMinimumHeight(min(height, 400))  # Max 400px
                    
                    # Auto-scroll to end
                    cursor = self.answer_text_edit.textCursor()
                    cursor.movePosition(QTextCursor.MoveOperation.End)
                    self.answer_text_edit.setTextCursor(cursor)
                    
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
