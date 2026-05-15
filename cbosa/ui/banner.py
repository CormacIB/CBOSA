"""
BannerWidget — fixed top bar with ASCII art logo and system info.

Layout:
  [ username · theme ]     [ CBOSA ASCII ART ]     [ Thu 2026-05-15  14:32:07 ]
"""
from __future__ import annotations

import os
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from cbosa import config

_ASCII_ART = r"""
  ██████╗██████╗  ██████╗ ███████╗ █████╗
 ██╔════╝██╔══██╗██╔═══██╗██╔════╝██╔══██╗
 ██║     ██████╔╝██║   ██║███████╗███████║
 ██║     ██╔══██╗██║   ██║╚════██║██╔══██║
 ╚██████╗██████╔╝╚██████╔╝███████║██║  ██║
  ╚═════╝╚═════╝  ╚═════╝ ╚══════╝╚═╝  ╚═╝
""".strip("\n")


def _theme_short_name(rel_path: str) -> str:
    stem = rel_path.split("/")[-1].replace(".toml", "").replace("_", " ")
    return stem.title()


class BannerWidget(QWidget):
    """Horizontal banner: left meta | center ASCII art | right clock."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("banner_widget")
        self._build_ui()
        self._start_clock()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(0)

        try:
            username = os.getlogin()
        except OSError:
            username = os.environ.get("USERNAME", os.environ.get("USER", "user"))

        theme_rel = config.get("theme", "themes/obsidian_dark.toml")
        theme_name = _theme_short_name(theme_rel)

        self._meta_label = QLabel(f"{username}  ·  {theme_name}")
        self._meta_label.setObjectName("banner_meta")
        self._meta_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        art_label = QLabel(_ASCII_ART)
        art_label.setObjectName("banner_art")
        art_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)

        self._clock_label = QLabel()
        self._clock_label.setObjectName("banner_clock")
        self._clock_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._tick()

        layout.addWidget(self._meta_label, stretch=1)
        layout.addWidget(art_label, stretch=0)
        layout.addWidget(self._clock_label, stretch=1)

    def _start_clock(self) -> None:
        timer = QTimer(self)
        timer.setInterval(1000)
        timer.timeout.connect(self._tick)
        timer.start()

    def _tick(self) -> None:
        self._clock_label.setText(datetime.now().strftime("%a %Y-%m-%d  %H:%M:%S"))

    def update_theme_name(self, rel_path: str) -> None:
        """Refresh the theme name shown in the left section."""
        try:
            username = os.getlogin()
        except OSError:
            username = os.environ.get("USERNAME", os.environ.get("USER", "user"))
        self._meta_label.setText(f"{username}  ·  {_theme_short_name(rel_path)}")
