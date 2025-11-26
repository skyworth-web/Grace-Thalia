import keyboard

class Hotkeys:
    def __init__(self, start_cb, stop_cb):
        self.start_cb = start_cb
        self.stop_cb = stop_cb

    def listen(self):
        keyboard.add_hotkey("ctrl+shift+s", self.start_cb)
        keyboard.add_hotkey("ctrl+shift+x", self.stop_cb)
