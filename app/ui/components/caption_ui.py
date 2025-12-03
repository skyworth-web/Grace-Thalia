# app/ui/components/caption_ui.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout, QLabel, QSizePolicy
)
from PyQt6.QtCore import Qt


def create_header_layout(status_label, clear_button, generate_button):
    """Create the header layout with status and buttons."""
    header_layout = QHBoxLayout()
    header_layout.setContentsMargins(10, 8, 10, 8)
    
    status_label.setStyleSheet("""
        font-size: 12px; 
        color: #ffaa00; 
        font-weight: bold;
        background: transparent;
    """)
    header_layout.addWidget(status_label)
    
    header_layout.addStretch()
    
    # Clear button
    clear_button.setStyleSheet("""
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
    header_layout.addWidget(clear_button)
    
    # Generate button
    generate_button.setStyleSheet("""
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
    header_layout.addWidget(generate_button)
    
    return header_layout


def create_answer_area():
    """Create the answer text area."""
    answer_label = QLabel("💬 AI Answer:")
    answer_label.setStyleSheet("""
        font-size: 13px; 
        color: #4da6ff; 
        font-weight: bold;
        background: transparent;
        margin-top: 10px;
        margin-bottom: 5px;
    """)
    
    answer_text_edit = QTextEdit()
    answer_text_edit.setReadOnly(True)
    answer_text_edit.setStyleSheet("""
        QTextEdit {
            font-size: 20px;
            color: #4da6ff;
            background-color: rgba(0, 0, 0, 40);
            border: 2px solid rgba(77, 166, 255, 10);
            border-radius: 10px;
            padding: 15px;
            min-height: 100px;
        }
    """)
    answer_text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    answer_text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    answer_text_edit.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Preferred
    )
    
    return answer_label, answer_text_edit


def create_caption_area():
    """Create the caption text area."""
    question_label = QLabel("📝 Question (Live Caption):")
    question_label.setStyleSheet("""
        font-size: 13px; 
        color: #00ff95; 
        font-weight: bold;
        background: transparent;
        margin-top: 10px;
        margin-bottom: 5px;
    """)
    
    caption_text_edit = QTextEdit()
    caption_text_edit.setReadOnly(True)
    caption_text_edit.setStyleSheet("""
        QTextEdit {
            font-size: 20px;
            color: #00ff95;
            background-color: rgba(0, 0, 0, 30);
            border: 2px solid rgba(0, 255, 149, 10);
            border-radius: 10px;
            padding: 15px;
            min-height: 150px;
            max-height: 300px;
        }
    """)
    caption_text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    caption_text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    
    return question_label, caption_text_edit

