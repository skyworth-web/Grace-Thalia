# app/ui/caption_window.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QTextCursor, QMouseEvent
from services.api_client import APIClient
from ui.components.caption_ui import (
    create_header_layout, create_answer_area, create_caption_area
)
from ui.components.answer_streaming import AnswerStreamer
from ui.utils.text_utils import normalize_text
from queue import Queue
from PyQt6.QtWidgets import QLabel, QPushButton
import logging

logging.basicConfig(level=logging.INFO)


class CaptionWindow(QWidget):
    """Main caption window for displaying live captions and AI answers."""
    
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
        self.full_transcript = ""
        self.reconciled_text = ""
        self.last_update_time = 0
        
        # For streaming answers
        self.answer_queue = Queue()
        self.answer_timer = QTimer()
        self.answer_timer.setInterval(50)  # Update every 50ms for smooth streaming
        
        # Initialize answer streamer
        self.answer_streamer = AnswerStreamer(self.api, self.answer_queue, self.answer_timer)
        self.answer_timer.timeout.connect(lambda: self.answer_streamer.process_queue(self.answer_text_edit))
        
        # Initialize UI
        self.init_ui()
    
    def init_ui(self):
        """Initialize the UI components."""
        # Main container with rounded corners and shadow
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # Header bar (for dragging and status)
        self.status_label = QLabel("🔴 Waiting for audio...")
        self.clear_button = QPushButton("🗑️ Clear")
        self.clear_button.clicked.connect(self.clear_text)
        
        self.generate_button = QPushButton("✨ Generate Answer")
        self.generate_button.clicked.connect(self.generate_answer)
        
        header_layout = create_header_layout(
            self.status_label, self.clear_button, self.generate_button
        )
        main_layout.addLayout(header_layout)

        # Answer area (moved to top)
        answer_label, self.answer_text_edit = create_answer_area()
        main_layout.addWidget(answer_label)
        main_layout.addWidget(self.answer_text_edit)

        # Question/Caption area (moved to bottom)
        question_label, self.caption_text_edit = create_caption_area()
        main_layout.addWidget(question_label)
        main_layout.addWidget(self.caption_text_edit)

        # Add stretch to push content to top
        main_layout.addStretch()

        # Set main layout with background
        container = QWidget()
        container.setLayout(main_layout)
        container.setStyleSheet("""
            QWidget {
                background-color: rgba(20, 20, 30, 30);
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
    
    def update_caption(self, text: str, full_transcript: str = None):
        """
        Update caption with backend-reconciled transcript.
        Backend handles reconciliation, frontend just displays.
        """
        if not text or not text.strip():
            return
        
        # Backend sends reconciled text, so we just display it
        display_text = text.strip()
        
        # Update full transcript if provided (for answer generation)
        if full_transcript:
            self.full_transcript = full_transcript.strip()
            self.reconciled_text = full_transcript.strip()
        else:
            # If no full transcript, use display text
            self.full_transcript = display_text
            self.reconciled_text = display_text
        
        logging.debug(f"📝 Updating caption: '{display_text[:50]}...'")
        
        # Update status
        self.status_label.setText("🟢 Live captions active - receiving audio...")
        self.status_label.setStyleSheet("font-size: 12px; color: #00ff95; padding: 4px;")
        
        # Check if this is a duplicate of current display
        current_display = self.caption_text_edit.toPlainText().strip()
        if current_display and display_text.strip():
            current_normalized = normalize_text(current_display)
            new_normalized = normalize_text(display_text)
            
            # If new text is just a repeat of current, skip update
            if new_normalized == current_normalized or \
               (len(new_normalized) > 0 and len(current_normalized) > 0 and 
                new_normalized in current_normalized and len(new_normalized) < len(current_normalized) * 0.8):
                logging.debug(f"🔄 Skipping duplicate display update")
                return
        
        # Update display
        self.caption_text_edit.setPlainText(display_text)
        
        # Auto-scroll to end
        cursor = self.caption_text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.caption_text_edit.setTextCursor(cursor)
    
    def clear_text(self):
        """Clear all caption text, reset transcript buffer, and start fresh."""
        # Clear backend buffer first
        try:
            result = self.api.clear_transcripts()
            if result.get("status") == "ok":
                logging.info("✅ Backend transcript buffer cleared")
            else:
                logging.warning(f"⚠️ Backend clear returned: {result}")
        except Exception as e:
            logging.error(f"❌ Error clearing backend buffer: {e}")
        
        # Clear display
        self.caption_text_edit.clear()
        self.answer_text_edit.setPlainText("AI answers will appear here...")
        
        # Reset all transcript-related state
        self.caption_history = []
        self.full_transcript = ""
        self.reconciled_text = ""
        
        # Clear chat history and current state
        self.answer_streamer.chat_history = []
        self.answer_streamer.current_question = ""
        self.answer_streamer.current_answer = ""
        
        # Update status to show we're ready for new audio
        self.status_label.setText("🟢 Ready - waiting for new audio...")
        self.status_label.setStyleSheet("font-size: 12px; color: #00ff95; padding: 4px;")
        
        logging.info("🧹 Cleared all captions and reset transcript buffer - ready for new audio from this point")
    
    def generate_answer(self):
        """Generate an answer based on the current transcript."""
        transcript = self.full_transcript.strip() if self.full_transcript else self.caption_text_edit.toPlainText().strip()
        
        if not transcript:
            self.answer_text_edit.setPlainText("⚠️ No text to generate an answer. Please start live captions first.")
            logging.warning("⚠️ Generate button clicked but no transcript available")
            return

        # Don't start new stream if one is already running
        if self.answer_streamer.is_streaming:
            logging.warning("⚠️ Stream already in progress, ignoring request")
            return

        logging.info(f"🔄 Starting streaming answer for transcript: {transcript[:100]}...")
        logging.info(f"📜 Using chat history: {len(self.answer_streamer.chat_history)} previous exchanges")
        self.answer_text_edit.setPlainText("⏳ Generating answer... Please wait...")
        
        # Get full context
        full_context = self.full_transcript or self.reconciled_text or ""
        
        # Start streaming
        self.answer_streamer.start_streaming(
            transcript, 
            self.answer_streamer.chat_history.copy(), 
            full_context
        )
    
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press for window dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move for window dragging."""
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
