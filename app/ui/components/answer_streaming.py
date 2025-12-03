# app/ui/components/answer_streaming.py

import asyncio
import threading
import logging
from queue import Queue
from services.api_client import APIClient

logger = logging.getLogger(__name__)


class AnswerStreamer:
    """Handles streaming of AI-generated answers."""
    
    def __init__(self, api_client: APIClient, answer_queue: Queue, answer_timer):
        self.api = api_client
        self.answer_queue = answer_queue
        self.answer_timer = answer_timer
        self.is_streaming = False
        self.current_answer = ""
        self.current_question = ""
        self.chat_history = []
    
    def start_streaming(self, transcript: str, chat_history: list, full_interview_context: str = ""):
        """Start streaming answer in background thread."""
        if self.is_streaming:
            logging.warning("⚠️ Stream already in progress, ignoring request")
            return
        
        self.is_streaming = True
        self.current_answer = ""
        self.current_question = transcript
        
        # Start streaming in background thread
        threading.Thread(
            target=self._stream_answer_background,
            args=(transcript, chat_history.copy(), full_interview_context),
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
    
    def process_queue(self, answer_text_edit):
        """Process answer chunks from queue and update GUI."""
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
                            logging.info(f"✅ Added to chat history ({len(self.chat_history)} exchanges)")
                        
                        self.is_streaming = False
                        self.current_question = ""
                        self.answer_timer.stop()
                        logging.info("✅ Answer streaming complete")
                        break
                    
                    # Append chunk to current answer
                    self.current_answer += chunk
                    
                    # Update display
                    answer_text_edit.setPlainText(self.current_answer)
                    
                    # Auto-resize answer area based on content
                    doc = answer_text_edit.document()
                    doc.setTextWidth(answer_text_edit.viewport().width())
                    height = int(doc.size().height()) + 30  # Add padding
                    answer_text_edit.setMinimumHeight(min(height, 400))  # Max 400px
                    
                    # Auto-scroll to end
                    from PyQt6.QtGui import QTextCursor
                    cursor = answer_text_edit.textCursor()
                    cursor.movePosition(QTextCursor.MoveOperation.End)
                    answer_text_edit.setTextCursor(cursor)
                    
                    logging.debug(f"📺 Updated answer display ({len(self.current_answer)} chars)")
                    
                except:
                    break  # Queue empty
                    
        except Exception as e:
            logging.error(f"❌ Error processing answer queue: {e}", exc_info=True)
            self.answer_timer.stop()
            self.is_streaming = False

