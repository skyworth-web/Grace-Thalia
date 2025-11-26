# app/app.py

import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow
from utils.hotkeys import Hotkeys
import threading

def main():
    app = QApplication(sys.argv)

    with open("ui/styles.qss", "r") as f:
        app.setStyleSheet(f.read())

    window = MainWindow()
    window.show()

    # Register hotkeys
    hot = Hotkeys(window.start_captions, window.stop_captions)
    threading.Thread(target=hot.listen, daemon=True).start()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
