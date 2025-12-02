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
        
        # Auto-reconciliation system (Windows Live Caption style)
        self.transcript_buffer = []  # List of (timestamp, text) tuples
        self.reconciled_text = ""  # Current reconciled/merged text
        self.buffer_window = 3.0  # Keep transcripts from last 3 seconds for reconciliation
        self.reconciliation_timer = QTimer()
        self.reconciliation_timer.timeout.connect(self._reconcile_and_update)
        self.reconciliation_timer.setInterval(100)  # Reconcile every 100ms
        
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
        """
        Add new transcript to buffer for reconciliation.
        Windows Live Caption style: buffer transcripts and reconcile overlapping chunks.
        """
        if not text or not text.strip():
            return
        
        import time
        current_time = time.time()
        
        new_text = text.strip()
        logging.debug(f"📝 Adding transcript to buffer: '{new_text[:50]}...'")
        
        # Update status
        self.status_label.setText("🟢 Live captions active - receiving audio...")
        self.status_label.setStyleSheet("font-size: 12px; color: #00ff95; padding: 4px;")
        
        # Add to buffer with timestamp
        self.transcript_buffer.append((current_time, new_text))
        
        # Clean old transcripts (older than buffer_window)
        cutoff_time = current_time - self.buffer_window
        self.transcript_buffer = [(ts, txt) for ts, txt in self.transcript_buffer if ts >= cutoff_time]
        
        # Start reconciliation timer if not already running
        if not self.reconciliation_timer.isActive():
            self.reconciliation_timer.start()
        
        # Trigger immediate reconciliation for real-time feel
        self._reconcile_and_update()
    
    def _reconcile_and_update(self):
        """
        Reconcile overlapping transcripts and update display.
        Windows Live Caption style: merge overlapping chunks, update previous words.
        """
        import time
        current_time = time.time()
        
        if not self.transcript_buffer:
            return
        
        # Clean old transcripts
        cutoff_time = current_time - self.buffer_window
        self.transcript_buffer = [(ts, txt) for ts, txt in self.transcript_buffer if ts >= cutoff_time]
        
        if not self.transcript_buffer:
            return
        
        # Sort by timestamp
        sorted_buffer = sorted(self.transcript_buffer, key=lambda x: x[0])
        
        # Reconcile: merge overlapping transcripts intelligently (Windows Live Caption style)
        # Use a sliding window approach: keep the best/most recent version of overlapping text
        reconciled_words = []
        word_timestamps = {}  # Track when each word was last seen (for freshness)
        
        for ts, text in sorted_buffer:
            words = text.split()
            
            if not reconciled_words:
                # First transcript
                reconciled_words = words
                # Initialize timestamps
                for i, word in enumerate(words):
                    word_timestamps[i] = ts
                continue
            
            # Find the best overlap point using word-level alignment
            best_overlap = self._find_best_overlap(reconciled_words, words)
            
            if best_overlap > 0:
                # Found overlap - merge intelligently
                # Keep the newer version of overlapping words (they're more accurate)
                overlap_start = len(reconciled_words) - best_overlap
                
                # Replace overlapping words with newer version (they may be corrections)
                for i, new_word in enumerate(words[:best_overlap]):
                    word_idx = overlap_start + i
                    if word_idx < len(reconciled_words):
                        # Update with newer word (might be a correction)
                        reconciled_words[word_idx] = new_word
                        word_timestamps[word_idx] = ts
                
                # Add new words after overlap
                if best_overlap < len(words):
                    new_words = words[best_overlap:]
                    start_idx = len(reconciled_words)
                    reconciled_words.extend(new_words)
                    # Update timestamps for new words
                    for i, word in enumerate(new_words):
                        word_timestamps[start_idx + i] = ts
            else:
                # No overlap found - check if it's a correction of recent words
                if len(words) > 0 and len(reconciled_words) > 0:
                    # Check if new text starts with a word that appears in last 8 words
                    first_new_word_clean = words[0].lower().strip(".,!?;:")
                    last_words_clean = [w.lower().strip(".,!?;:") for w in reconciled_words[-8:]]
                    
                    if first_new_word_clean in last_words_clean:
                        # Likely a correction - replace from that point
                        idx = last_words_clean.index(first_new_word_clean)
                        replace_start = len(reconciled_words) - (len(last_words_clean) - idx)
                        # Replace with new text (assume it's more accurate)
                        reconciled_words = reconciled_words[:replace_start] + words
                        # Update timestamps
                        for i, word in enumerate(words):
                            word_timestamps[replace_start + i] = ts
                    else:
                        # Genuinely new text - append
                        start_idx = len(reconciled_words)
                        reconciled_words.extend(words)
                        for i, word in enumerate(words):
                            word_timestamps[start_idx + i] = ts
                else:
                    # First words or empty - just add
                    start_idx = len(reconciled_words)
                    reconciled_words.extend(words)
                    for i, word in enumerate(words):
                        word_timestamps[start_idx + i] = ts
        
        # Clean up: remove very old words that are likely outdated (older than 5 seconds)
        if word_timestamps:
            oldest_allowed = current_time - 5.0
            words_to_keep = []
            for i, word in enumerate(reconciled_words):
                if i in word_timestamps and word_timestamps[i] >= oldest_allowed:
                    words_to_keep.append((i, word))
                elif i not in word_timestamps:
                    # Keep words without timestamps (shouldn't happen, but be safe)
                    words_to_keep.append((i, word))
            
            if words_to_keep:
                # Rebuild reconciled_words keeping only recent words
                reconciled_words = [word for _, word in words_to_keep]
                # Rebuild timestamps
                new_timestamps = {}
                for new_idx, (old_idx, _) in enumerate(words_to_keep):
                    if old_idx in word_timestamps:
                        new_timestamps[new_idx] = word_timestamps[old_idx]
                word_timestamps = new_timestamps
        
        # Update reconciled text
        self.reconciled_text = " ".join(reconciled_words)
        
        # Update full transcript (for answer generation)
        self.full_transcript = self.reconciled_text
        
        # Display: Show last 60 words (Windows Live Caption style)
        display_words = reconciled_words[-60:] if len(reconciled_words) > 60 else reconciled_words
        display_text = " ".join(display_words)
        
        # Update display
        self.caption_text_edit.setPlainText(display_text)
        
        # Auto-scroll to end
        cursor = self.caption_text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.caption_text_edit.setTextCursor(cursor)
        
        self.last_update_time = current_time
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison (remove punctuation, lowercase, normalize spaces)."""
        import re
        # Remove punctuation, lowercase, normalize spaces
        normalized = re.sub(r'[^\w\s]', '', text.lower())
        normalized = ' '.join(normalized.split())
        return normalized
    
    def _normalize_word(self, word: str) -> str:
        """Normalize a single word for comparison."""
        return word.lower().strip(".,!?;:\"'()[]{}")
    
    def _find_best_overlap(self, existing_words: list, new_words: list) -> int:
        """
        Find the best overlap point between existing and new words.
        Returns the number of overlapping words (0 if no good overlap found).
        """
        if not existing_words or not new_words:
            return 0
        
        max_overlap = min(len(existing_words), len(new_words), 12)  # Check up to 12 words
        
        # Try to find the longest matching suffix-prefix
        for overlap_len in range(max_overlap, 0, -1):
            existing_suffix = existing_words[-overlap_len:]
            new_prefix = new_words[:overlap_len]
            
            # Normalize words for comparison
            existing_normalized = [self._normalize_word(w) for w in existing_suffix]
            new_normalized = [self._normalize_word(w) for w in new_prefix]
            
            # Check if they match (allowing for minor differences)
            matches = sum(1 for e, n in zip(existing_normalized, new_normalized) if e == n)
            match_ratio = matches / overlap_len if overlap_len > 0 else 0
            
            # Require at least 80% match for a valid overlap
            if match_ratio >= 0.8:
                return overlap_len
        
        return 0
    
    def _texts_similar(self, text1: str, text2: str) -> bool:
        """
        Check if two text strings are similar (for overlap detection).
        """
        if not text1 or not text2:
            return False
        
        # Check if one contains the other (for partial matches)
        if len(text1) > len(text2):
            return text2 in text1 or text1.startswith(text2[:min(len(text2), len(text1)//2)])
        else:
            return text1 in text2 or text2.startswith(text1[:min(len(text1), len(text2)//2)])

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press for window dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Get global position and window position
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move for window dragging."""
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position:
            # Move window to new position
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def clear_text(self):
        """Clear all caption text, reset transcript buffer, and start fresh."""
        import time
        
        # Clear display
        self.caption_text_edit.clear()
        self.answer_text_edit.setPlainText("AI answers will appear here...")
        
        # Reset all transcript-related state
        self.caption_history = []
        self.full_transcript = ""
        self.reconciled_text = ""
        self.transcript_buffer = []  # Clear the reconciliation buffer - this is key!
        
        # Reset timestamps
        self.last_update_time = 0
        
        # Clear chat history and current state
        self.chat_history = []
        self.current_question = ""
        self.current_answer = ""
        
        # Update status to show we're ready for new audio
        self.status_label.setText("🟢 Ready - waiting for new audio...")
        self.status_label.setStyleSheet("font-size: 12px; color: #00ff95; padding: 4px;")
        
        logging.info("🧹 Cleared all captions and reset transcript buffer - ready for new audio from this point")

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
        
        # Start streaming in background thread with chat history and full interview context
        full_context = self.full_transcript or self.reconciled_text or ""
        threading.Thread(
            target=self._stream_answer_background,
            args=(transcript, self.chat_history.copy(), full_context),  # Pass chat history and full context
            daemon=True
        ).start()
        
        # Start timer to process answer chunks
        if not self.answer_timer.isActive():
            self.answer_timer.start()
    
    def _stream_answer_background(self, transcript: str, chat_history: list, full_interview_context: str = ""):
        """Background thread for streaming answer from API."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            async def stream():
                try:
                    async for chunk in self.api.stream_answer(transcript, chat_history, full_interview_context):
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
