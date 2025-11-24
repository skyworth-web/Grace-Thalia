from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

class CaptionWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Live Captions")
        self.setGeometry(100, 100, 600, 120)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)

        layout = QVBoxLayout()
        self.label = QLabel("🎤 Waiting for speech...")
        self.label.setStyleSheet("font-size: 20px; color: #00ff95;")
        layout.addWidget(self.label)

        self.setLayout(layout)

    def update_caption(self, text):
        self.label.setText(text)
