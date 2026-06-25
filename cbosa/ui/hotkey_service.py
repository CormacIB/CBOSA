"""
GlobalHotkeyService — registers a system-wide hotkey and fires a Qt signal.

Uses pynput (runs in a background thread). Bridges to Qt's main thread via
a QObject signal so the capture window can be shown safely.

Usage:
    service = GlobalHotkeyService()
    service.triggered.connect(some_slot)
    service.start()
    ...
    service.stop()
"""
from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal


class GlobalHotkeyService(QObject):
    triggered = pyqtSignal()

    # Cmd+Shift+N on macOS (<cmd> is Key.cmd in pynput)
    _HOTKEY = "<cmd>+<ctrl>+n"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._listener = None

    def start(self) -> None:
        try:
            from pynput import keyboard

            def on_activate():
                self.triggered.emit()

            self._listener = keyboard.GlobalHotKeys({self._HOTKEY: on_activate})
            self._listener.daemon = True
            self._listener.start()
        except Exception as exc:
            print(f"[CBOSA] Global hotkey unavailable: {exc}")

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
