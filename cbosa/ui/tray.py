"""
TrayService — system tray icon for CBOSA.

Menu:
  Show / Hide CBOSA   (toggles main window)
  Quick Capture       (shows the capture window)
  ──────────────────
  Quit

The tray icon is a small programmatic glyph — no external image needed.
"""
from __future__ import annotations

from PyQt6.QtCore import QObject
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QMainWindow, QMenu, QSystemTrayIcon


def _make_tray_icon(size: int = 22) -> QIcon:
    """Draw a minimal 'C' glyph on a dark rounded square."""
    px = QPixmap(size, size)
    px.fill(QColor(0, 0, 0, 0))

    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Background pill
    p.setBrush(QColor("#1e1e2e"))
    p.setPen(QColor("#cba6f7"))
    r = size // 5
    p.drawRoundedRect(1, 1, size - 2, size - 2, r, r)

    # "C" letter
    p.setPen(QColor("#cba6f7"))
    font = p.font()
    font.setPixelSize(int(size * 0.6))
    font.setBold(True)
    p.setFont(font)
    p.drawText(px.rect(), 0x84, "C")  # AlignCenter

    p.end()
    return QIcon(px)


class TrayService(QObject):
    def __init__(self, window: QMainWindow, capture_window, parent=None) -> None:
        super().__init__(parent)
        self._window = window
        self._capture_window = capture_window
        self._tray = QSystemTrayIcon(parent)
        self._tray.setIcon(_make_tray_icon())
        self._tray.setToolTip("CBOSA")
        self._build_menu()
        self._tray.activated.connect(self._on_activated)

    def _build_menu(self) -> None:
        menu = QMenu()

        self._toggle_action = menu.addAction("Hide CBOSA")
        self._toggle_action.triggered.connect(self._toggle_window)

        capture_action = menu.addAction("Quick Capture  ⌘^N")
        capture_action.triggered.connect(self._capture_window.show)

        menu.addSeparator()

        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self._quit)

        self._tray.setContextMenu(menu)

    def show(self) -> None:
        self._tray.show()

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_window()

    def _toggle_window(self) -> None:
        if self._window.isVisible():
            self._window.hide()
            self._toggle_action.setText("Show CBOSA")
        else:
            self._window.show()
            self._window.raise_()
            self._window.activateWindow()
            self._toggle_action.setText("Hide CBOSA")

    def _quit(self) -> None:
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()
