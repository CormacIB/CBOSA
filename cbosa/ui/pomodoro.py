"""
Pomodoro timer — permanent banner bar integration.

PomodoroEngine     — state machine, JSON persistence, TimerStore logging
PomodoroMiniWidget — compact banner widget (mini ring + MM:SS + phase tag)
PomodoroDialog     — popup dialog with full gauge, ASCII bar, controls, presets
"""
from __future__ import annotations

import datetime as dt
import json
import math
import subprocess
import sys
import time
from pathlib import Path

from PyQt6.QtCore import QObject, QPointF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from cbosa.core.timer_store import TimerStore, TimerStoreError

# ── Constants ─────────────────────────────────────────────────────────────────

PRESETS: dict[str, dict[str, int]] = {
    "classic": {"focus": 25 * 60, "short":  5 * 60, "long": 15 * 60},
    "short":   {"focus": 15 * 60, "short":  3 * 60, "long": 10 * 60},
    "deep":    {"focus": 50 * 60, "short": 10 * 60, "long": 25 * 60},
}
PER_SET = 4

PHASE_META: dict[str, tuple[str, str]] = {
    "focus": ("FOCUS",       "◉"),
    "short": ("SHORT BREAK", "○"),
    "long":  ("LONG BREAK",  "◍"),
}

# Gauge geometry — matches JSX proportions exactly
_GCX, _GCY, _GR = 94, 94, 70


def _fmt(s: float) -> str:
    s = max(0, round(s))
    return f"{int(s) // 60:02d}:{int(s) % 60:02d}"


def _load_theme_colors() -> dict:
    from cbosa import config
    from cbosa.ui.theme_engine import ThemeEngine, ThemeLoadError
    try:
        path = str(config.resolve("theme", "themes/dark_default.toml"))
        colors, _ = ThemeEngine().get_colors_and_fonts(path)
        return colors
    except Exception:
        return {}


# ── Engine ────────────────────────────────────────────────────────────────────

class PomodoroEngine(QObject):
    state_changed = pyqtSignal()

    def __init__(
        self,
        timer_store: TimerStore,
        state_path: Path | str,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._store = timer_store
        self._state_path = Path(state_path)
        self._cat_id: int | None = None

        self._phase = "focus"
        self._preset = "classic"
        self._total = PRESETS["classic"]["focus"]
        self._remaining: float = float(self._total)
        self._running = False
        self._completed = 0
        self._muted = False
        self._ends_at: float | None = None
        self._session_started: float | None = None

        self._load()

        self._ticker = QTimer(self)
        self._ticker.setInterval(250)
        self._ticker.timeout.connect(self._tick)
        if self._running:
            self._ticker.start()

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def phase(self) -> str:
        return self._phase

    @property
    def remaining(self) -> float:
        return self._remaining

    @property
    def total(self) -> int:
        return self._total

    @property
    def running(self) -> bool:
        return self._running

    @property
    def completed(self) -> int:
        return self._completed

    @property
    def preset(self) -> str:
        return self._preset

    @property
    def muted(self) -> bool:
        return self._muted

    # ── Public API ────────────────────────────────────────────────────────────

    def toggle_run(self) -> None:
        if self._running:
            self._do_pause()
        else:
            self._do_start()

    def reset(self) -> None:
        self._running = False
        self._ticker.stop()
        self._ends_at = None
        self._session_started = None
        self._remaining = float(self._total)
        self._save()
        self.state_changed.emit()

    def skip(self) -> None:
        self._advance(log=False)

    def apply_preset(self, name: str) -> None:
        if name not in PRESETS:
            return
        self._preset = name
        self._running = False
        self._ticker.stop()
        self._ends_at = None
        self._session_started = None
        self._total = PRESETS[name][self._phase]
        self._remaining = float(self._total)
        self._save()
        self.state_changed.emit()

    def set_muted(self, muted: bool) -> None:
        self._muted = muted
        self._save()
        self.state_changed.emit()

    # ── Private — timer ───────────────────────────────────────────────────────

    def _do_start(self) -> None:
        self._ends_at = time.time() + self._remaining
        if self._phase == "focus" and self._session_started is None:
            self._session_started = time.time()
        self._running = True
        self._ticker.start()
        self._save()
        self.state_changed.emit()

    def _do_pause(self) -> None:
        if self._ends_at is not None:
            self._remaining = max(0.0, self._ends_at - time.time())
        self._ends_at = None
        self._running = False
        self._ticker.stop()
        self._save()
        self.state_changed.emit()

    def _tick(self) -> None:
        if self._ends_at is None:
            return
        rem = self._ends_at - time.time()
        if rem <= 0:
            self._remaining = 0.0
            self.state_changed.emit()
            self._advance(log=True)
        else:
            self._remaining = rem
            self.state_changed.emit()

    def _advance(self, log: bool = True) -> None:
        self._running = False
        self._ticker.stop()
        self._ends_at = None

        if self._phase == "focus":
            if log and self._session_started is not None:
                self._log_session(self._session_started, time.time())
            self._session_started = None
            self._completed += 1
            next_phase = "long" if self._completed % PER_SET == 0 else "short"
            self._chime("break")
        else:
            next_phase = "focus"
            self._chime("focus")

        self._phase = next_phase
        self._total = PRESETS[self._preset][next_phase]
        self._remaining = float(self._total)
        self._save()
        self.state_changed.emit()

    # ── Private — store / audio ───────────────────────────────────────────────

    def _log_session(self, started: float, ended: float) -> None:
        if ended - started < 60:
            return
        try:
            cat_id = self._get_cat()
            s = dt.datetime.fromtimestamp(started).strftime("%Y-%m-%dT%H:%M:%S")
            e = dt.datetime.fromtimestamp(ended).strftime("%Y-%m-%dT%H:%M:%S")
            self._store.log_session(cat_id, s, e)
        except TimerStoreError:
            pass

    def _get_cat(self) -> int:
        if self._cat_id is not None:
            return self._cat_id
        groups = self._store.list_groups()
        grp = next((g for g in groups if g["name"] == "Pomodoro"), None)
        gid = grp["id"] if grp else self._store.add_group("Pomodoro")
        cats = self._store.list_categories(gid)
        cat = next((c for c in cats if c["name"] == "Focus Session"), None)
        self._cat_id = cat["id"] if cat else self._store.add_category(gid, "Focus Session")
        return self._cat_id

    def _chime(self, kind: str) -> None:
        if self._muted:
            return
        if sys.platform == "darwin":
            snd = ("/System/Library/Sounds/Glass.aiff" if kind == "break"
                   else "/System/Library/Sounds/Ping.aiff")
            try:
                subprocess.Popen(["afplay", snd],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                pass
        else:
            QApplication.beep()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self) -> None:
        today = dt.date.today().isoformat()
        try:
            raw = json.loads(self._state_path.read_text())
        except (OSError, json.JSONDecodeError):
            return

        self._phase   = raw.get("phase",   "focus")
        self._preset  = raw.get("preset",  "classic")
        self._muted   = bool(raw.get("muted", False))
        self._total   = int(raw.get("total", PRESETS["classic"]["focus"]))
        self._running = bool(raw.get("running", False))
        self._session_started = raw.get("session_started")

        self._completed = (int(raw.get("completed", 0))
                           if raw.get("completed_date") == today else 0)

        ends_at = raw.get("ends_at")
        if self._running and ends_at is not None:
            rem = ends_at - time.time()
            if rem <= 0:
                # Expired while closed — silently advance without logging
                self._running = False
                self._session_started = None
                if self._phase == "focus":
                    self._completed += 1
                    self._phase = "long" if self._completed % PER_SET == 0 else "short"
                else:
                    self._phase = "focus"
                preset = PRESETS.get(self._preset, PRESETS["classic"])
                self._total = preset[self._phase]
                self._remaining = float(self._total)
            else:
                self._ends_at = ends_at
                self._remaining = rem
        else:
            self._running = False
            self._remaining = float(raw.get("remaining") or self._total)

    def _save(self) -> None:
        data = {
            "phase":           self._phase,
            "preset":          self._preset,
            "total":           self._total,
            "remaining":       self._remaining if not self._running else None,
            "running":         self._running,
            "ends_at":         self._ends_at,
            "completed":       self._completed,
            "completed_date":  dt.date.today().isoformat(),
            "muted":           self._muted,
            "session_started": self._session_started,
        }
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            self._state_path.write_text(json.dumps(data))
        except OSError:
            pass


# ── Mini ring (16×16) ─────────────────────────────────────────────────────────

class _MiniRing(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._frac: float = 1.0
        self._arc = QColor("#89b4fa")
        self._track = QColor("#313244")
        self.setFixedSize(16, 16)

    def set_state(self, frac: float, arc: str, track: str) -> None:
        self._frac = max(0.0, min(1.0, frac))
        self._arc = QColor(arc)
        self._track = QColor(track)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self._track, 2)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        p.setPen(pen)
        p.drawArc(2, 2, 12, 12, 0, 360 * 16)
        pen2 = QPen(self._arc, 2)
        pen2.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen2)
        span = -int(self._frac * 360 * 16)
        if span != 0:
            p.drawArc(2, 2, 12, 12, 90 * 16, span)
        p.end()


# ── Banner mini widget ────────────────────────────────────────────────────────

class PomodoroMiniWidget(QWidget):
    """Ring + MM:SS + phase tag — lives in the banner. Click to open dialog."""

    def __init__(self, engine: PomodoroEngine, parent=None) -> None:
        super().__init__(parent)
        self._engine = engine
        self._dialog: PomodoroDialog | None = None
        self._last_hide: float = 0.0
        self._colors: dict = _load_theme_colors()

        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 0, 6, 0)
        lay.setSpacing(5)

        self._ring = _MiniRing()
        lay.addWidget(self._ring)

        self._time_lbl = QLabel()
        self._time_lbl.setObjectName("pomo_mini_time")
        lay.addWidget(self._time_lbl)

        self._phase_lbl = QLabel()
        self._phase_lbl.setObjectName("pomo_mini_phase")
        lay.addWidget(self._phase_lbl)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        engine.state_changed.connect(self._refresh)
        self._refresh()

    def _refresh(self) -> None:
        eng = self._engine
        frac = eng.remaining / eng.total if eng.total > 0 else 0.0
        arc = (self._colors.get("accent", "#89b4fa") if eng.phase == "focus"
               else self._colors.get("text", "#cdd6f4"))
        track = self._colors.get("surface", "#313244")
        self._ring.set_state(frac, arc, track)
        self._time_lbl.setText(_fmt(eng.remaining))
        self._phase_lbl.setText("focus" if eng.phase == "focus" else "break")

    def update_colors(self) -> None:
        self._colors = _load_theme_colors()
        self._refresh()
        if self._dialog is not None:
            self._dialog.update_colors()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if time.time() - self._last_hide < 0.15:
                return
            self._toggle_dialog()

    def _toggle_dialog(self) -> None:
        if self._dialog is None:
            self._dialog = PomodoroDialog(self._engine)
            self._dialog.dialog_hidden.connect(
                lambda: setattr(self, "_last_hide", time.time())
            )

        if self._dialog.isVisible():
            self._dialog.hide()
        else:
            self._dialog.update_colors()
            br = self.mapToGlobal(self.rect().bottomRight())
            w = self._dialog.sizeHint().width()
            self._dialog.move(br.x() - w, br.y() + 4)
            self._dialog.show()


# ── Full gauge widget ─────────────────────────────────────────────────────────

class _GaugeWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._phase = "focus"
        self._remaining: float = PRESETS["classic"]["focus"]
        self._total: int = PRESETS["classic"]["focus"]
        self._colors: dict = {}
        self.setFixedSize(188, 188)

    def set_state(self, phase: str, remaining: float, total: int, colors: dict) -> None:
        self._phase = phase
        self._remaining = remaining
        self._total = total
        self._colors = colors
        self.update()

    def paintEvent(self, _event) -> None:
        if not self._colors:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy, r = _GCX, _GCY, _GR
        bg      = self._colors.get("background", "#1e1e2e")
        surface = self._colors.get("surface",    "#313244")
        text    = self._colors.get("text",       "#cdd6f4")
        muted   = self._colors.get("text_muted", "#6c7086")
        arc_col = (self._colors.get("accent", "#89b4fa") if self._phase == "focus"
                   else self._colors.get("text", "#cdd6f4"))

        p.fillRect(0, 0, 188, 188, QColor(bg))

        # Tick marks
        for i in range(60):
            a = i / 60 * 2 * math.pi - math.pi / 2
            major = i % 5 == 0
            r1 = 80 if major else 83
            x1 = cx + r1 * math.cos(a)
            y1 = cy + r1 * math.sin(a)
            x2 = cx + 87 * math.cos(a)
            y2 = cy + 87 * math.sin(a)
            pen = QPen(QColor(muted), 1.5 if major else 1.0)
            p.setPen(pen)
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        # Track ring
        pen = QPen(QColor(surface), 7)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        p.setPen(pen)
        p.drawArc(cx - r, cy - r, 2 * r, 2 * r, 0, 360 * 16)

        # Progress arc (remaining fraction, clockwise from 12 o'clock)
        frac = self._remaining / self._total if self._total > 0 else 0.0
        pen2 = QPen(QColor(arc_col), 7)
        pen2.setCapStyle(Qt.PenCapStyle.FlatCap)
        p.setPen(pen2)
        span = -int(frac * 360 * 16)
        if span != 0:
            p.drawArc(cx - r, cy - r, 2 * r, 2 * r, 90 * 16, span)

        # Lead dot at arc tip
        if 0.002 < frac < 0.998:
            a = 2 * math.pi * frac - math.pi / 2
            lx = cx + r * math.cos(a)
            ly = cy + r * math.sin(a)
            p.setPen(QPen(QColor(bg), 2))
            p.setBrush(QBrush(QColor(arc_col)))
            p.drawEllipse(QPointF(lx, ly), 4.5, 4.5)
            p.setBrush(QBrush())

        # Phase label (small, above center)
        phase_label = PHASE_META[self._phase][0]
        f_small = QFont("Helvetica Neue", 9)
        p.setFont(f_small)
        p.setPen(QColor(muted))
        pw = QFontMetrics(f_small).horizontalAdvance(phase_label)
        p.drawText(cx - pw // 2, cy - 22, phase_label)

        # Time (large, center)
        time_str = _fmt(self._remaining)
        f_big = QFont("Helvetica Neue", 30)
        f_big.setBold(True)
        p.setFont(f_big)
        p.setPen(QColor(text))
        fm = QFontMetrics(f_big)
        tw = fm.horizontalAdvance(time_str)
        p.drawText(cx - tw // 2, cy + 9, time_str)

        p.end()


# ── Popup dialog ──────────────────────────────────────────────────────────────

class PomodoroDialog(QWidget):
    dialog_hidden = pyqtSignal()

    def __init__(self, engine: PomodoroEngine, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self._engine = engine
        self._colors: dict = {}
        self._preset_btns: dict[str, QPushButton] = {}
        self._pip_labels: list[QLabel] = []
        self._build_ui()
        engine.state_changed.connect(self._on_state)

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self.dialog_hidden.emit()

    def sizeHint(self) -> QSize:
        return QSize(268, 420)

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setFixedWidth(268)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        self._header = QWidget()
        self._header.setObjectName("pomo_header")
        self._header.setFixedHeight(24)
        hlay = QHBoxLayout(self._header)
        hlay.setContentsMargins(8, 0, 4, 0)
        hlay.setSpacing(6)
        self._glyph_lbl = QLabel("◉")
        self._glyph_lbl.setObjectName("pomo_glyph")
        hlay.addWidget(self._glyph_lbl)
        title = QLabel("focus timer")
        title.setObjectName("pomo_title")
        hlay.addWidget(title)
        hlay.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setObjectName("pomo_close")
        close_btn.setFixedSize(20, 20)
        close_btn.setFlat(True)
        close_btn.clicked.connect(self.hide)
        hlay.addWidget(close_btn)
        root.addWidget(self._header)

        # Separator under header
        sep0 = QFrame()
        sep0.setFrameShape(QFrame.Shape.HLine)
        sep0.setObjectName("pomo_sep")
        root.addWidget(sep0)

        # Body
        body = QWidget()
        body.setObjectName("pomo_body")
        blay = QVBoxLayout(body)
        blay.setContentsMargins(14, 14, 14, 12)
        blay.setSpacing(0)

        # Gauge
        self._gauge = _GaugeWidget()
        blay.addWidget(self._gauge, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Session pips
        pip_w = QWidget()
        pip_lay = QHBoxLayout(pip_w)
        pip_lay.setContentsMargins(0, 10, 0, 8)
        pip_lay.setSpacing(7)
        pip_lay.addStretch()
        for _ in range(PER_SET):
            lbl = QLabel("◇")
            lbl.setObjectName("pomo_pip")
            pip_lay.addWidget(lbl)
            self._pip_labels.append(lbl)
        pip_lay.addStretch()
        blay.addWidget(pip_w)

        # ASCII progress bar
        self._ascii_lbl = QLabel()
        self._ascii_lbl.setObjectName("pomo_ascii")
        self._ascii_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        blay.addWidget(self._ascii_lbl)

        # ASCII meta row
        meta_w = QWidget()
        meta_lay = QHBoxLayout(meta_w)
        meta_lay.setContentsMargins(0, 2, 0, 12)
        meta_lay.setSpacing(0)
        self._elapsed_lbl = QLabel()
        self._elapsed_lbl.setObjectName("pomo_meta")
        self._time_meta_lbl = QLabel()
        self._time_meta_lbl.setObjectName("pomo_meta")
        meta_lay.addWidget(self._elapsed_lbl)
        meta_lay.addStretch()
        meta_lay.addWidget(self._time_meta_lbl)
        blay.addWidget(meta_w)

        # Controls
        ctrl_w = QWidget()
        ctrl_lay = QHBoxLayout(ctrl_w)
        ctrl_lay.setContentsMargins(0, 0, 0, 0)
        ctrl_lay.setSpacing(6)
        self._run_btn = QPushButton("▶  start")
        self._run_btn.setObjectName("pomo_primary")
        self._run_btn.clicked.connect(self._engine.toggle_run)
        ctrl_lay.addWidget(self._run_btn)
        reset_btn = QPushButton("↺  reset")
        reset_btn.setObjectName("pomo_btn")
        reset_btn.clicked.connect(self._engine.reset)
        ctrl_lay.addWidget(reset_btn)
        skip_btn = QPushButton("⤼  skip")
        skip_btn.setObjectName("pomo_btn")
        skip_btn.clicked.connect(self._engine.skip)
        ctrl_lay.addWidget(skip_btn)
        blay.addWidget(ctrl_w)

        # Presets
        preset_w = QWidget()
        preset_lay = QHBoxLayout(preset_w)
        preset_lay.setContentsMargins(0, 9, 0, 0)
        preset_lay.setSpacing(5)
        for key, label in [("classic", "25 · 5"), ("short", "15 · 3"), ("deep", "50 · 10")]:
            btn = QPushButton(label)
            btn.setObjectName("pomo_preset")
            btn.clicked.connect(lambda _, k=key: self._engine.apply_preset(k))
            preset_lay.addWidget(btn)
            self._preset_btns[key] = btn
        blay.addWidget(preset_w)

        # Footer separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("pomo_sep")
        blay.addSpacing(11)
        blay.addWidget(sep)
        blay.addSpacing(9)

        # Footer
        foot_w = QWidget()
        foot_lay = QHBoxLayout(foot_w)
        foot_lay.setContentsMargins(0, 0, 0, 0)
        self._sessions_lbl = QLabel()
        self._sessions_lbl.setObjectName("pomo_foot")
        foot_lay.addWidget(self._sessions_lbl)
        foot_lay.addStretch()
        self._mute_btn = QPushButton()
        self._mute_btn.setObjectName("pomo_mute")
        self._mute_btn.setFlat(True)
        self._mute_btn.clicked.connect(
            lambda: self._engine.set_muted(not self._engine.muted)
        )
        foot_lay.addWidget(self._mute_btn)
        blay.addWidget(foot_w)

        root.addWidget(body)

    # ── State sync ────────────────────────────────────────────────────────────

    def _on_state(self) -> None:
        eng = self._engine
        self._gauge.set_state(eng.phase, eng.remaining, eng.total, self._colors)
        self._update_pips()
        self._update_ascii()
        self._update_controls()
        self._update_presets()
        self._update_footer()

    def _update_pips(self) -> None:
        eng = self._engine
        done_in_set = eng.completed % PER_SET
        for i, lbl in enumerate(self._pip_labels):
            if i < done_in_set:
                lbl.setText("◆")
                lbl.setStyleSheet(f"color: {self._colors.get('accent', '#89b4fa')};")
            elif i == done_in_set and eng.phase == "focus":
                lbl.setText("◈")
                lbl.setStyleSheet(f"color: {self._colors.get('text', '#cdd6f4')};")
            else:
                lbl.setText("◇")
                lbl.setStyleSheet(f"color: {self._colors.get('text_muted', '#6c7086')};")

    def _update_ascii(self) -> None:
        eng = self._engine
        CELLS = 22
        elapsed_frac = (1 - eng.remaining / eng.total) if eng.total > 0 else 0.0
        filled = round(elapsed_frac * CELLS)
        accent = self._colors.get("accent", "#89b4fa")
        muted  = self._colors.get("text_muted", "#6c7086")
        bar = (
            f'<span style="color:{muted}">[</span>'
            f'<span style="color:{accent}">{"█" * filled}</span>'
            f'<span style="color:{muted}">{"░" * (CELLS - filled)}]</span>'
        )
        self._ascii_lbl.setText(bar)
        pct = round(elapsed_frac * 100)
        elapsed_s = eng.total - eng.remaining
        dim = self._colors.get("text_muted", "#6c7086")
        fg  = self._colors.get("text", "#cdd6f4")
        self._elapsed_lbl.setText(
            f'<span style="color:{dim}">elapsed </span>'
            f'<b style="color:{fg}">{pct}%</b>'
        )
        self._time_meta_lbl.setText(
            f'<b style="color:{fg}">{_fmt(elapsed_s)}</b>'
            f'<span style="color:{dim}"> / {_fmt(eng.total)}</span>'
        )

    def _update_controls(self) -> None:
        eng = self._engine
        self._run_btn.setText("❚❚  pause" if eng.running else "▶  start")
        ph_label, ph_glyph = PHASE_META[eng.phase]
        self._glyph_lbl.setText(ph_glyph)

    def _update_presets(self) -> None:
        accent = self._colors.get("accent", "#89b4fa")
        border = self._colors.get("border", "#45475a")
        muted  = self._colors.get("text_muted", "#6c7086")
        bg     = self._colors.get("background", "#1e1e2e")
        for key, btn in self._preset_btns.items():
            if key == self._engine.preset:
                btn.setStyleSheet(
                    f"color: {accent}; border: 1px solid {accent}; background: {bg};"
                    f"padding: 3px 0; font-size: 10px;"
                )
            else:
                btn.setStyleSheet(
                    f"color: {muted}; border: 1px solid {border}; background: {bg};"
                    f"padding: 3px 0; font-size: 10px;"
                )

    def _update_footer(self) -> None:
        eng = self._engine
        dim = self._colors.get("text_muted", "#6c7086")
        fg  = self._colors.get("text", "#cdd6f4")
        self._sessions_lbl.setText(
            f'<span style="color:{dim}">today: </span>'
            f'<b style="color:{fg}">{eng.completed}</b>'
            f'<span style="color:{dim}"> sessions</span>'
        )
        accent = self._colors.get("accent", "#89b4fa")
        if eng.muted:
            self._mute_btn.setText("♪ muted")
            self._mute_btn.setStyleSheet(f"color: {dim}; font-size: 10px;")
        else:
            self._mute_btn.setText("♪ chime")
            self._mute_btn.setStyleSheet(f"color: {accent}; font-size: 10px;")

    # ── Colors ────────────────────────────────────────────────────────────────

    def update_colors(self) -> None:
        self._colors = _load_theme_colors()
        self._apply_palette()
        self._on_state()

    def _apply_palette(self) -> None:
        bg      = self._colors.get("background", "#1e1e2e")
        surface = self._colors.get("surface",    "#313244")
        text    = self._colors.get("text",       "#cdd6f4")
        muted   = self._colors.get("text_muted", "#6c7086")
        border  = self._colors.get("border",     "#45475a")
        accent  = self._colors.get("accent",     "#89b4fa")

        self.setStyleSheet(f"""
            QWidget {{
                background: {bg};
                color: {text};
                font-size: 12px;
            }}
            QWidget#pomo_header {{
                background: {surface};
            }}
            QLabel#pomo_glyph {{
                color: {accent};
                font-size: 11px;
            }}
            QLabel#pomo_title {{
                color: {muted};
                font-size: 11px;
                letter-spacing: 2px;
                text-transform: uppercase;
            }}
            QPushButton#pomo_close {{
                color: {muted};
                font-size: 11px;
                background: transparent;
                border: none;
            }}
            QPushButton#pomo_close:hover {{
                color: {text};
            }}
            QFrame#pomo_sep {{
                color: {border};
            }}
            QLabel#pomo_meta {{
                color: {muted};
                font-size: 10px;
            }}
            QPushButton#pomo_primary {{
                color: {accent};
                border: 1px solid {accent};
                background: {surface};
                padding: 5px 0;
                font-size: 12px;
            }}
            QPushButton#pomo_btn {{
                color: {muted};
                border: 1px solid {border};
                background: {surface};
                padding: 5px 0;
                font-size: 12px;
            }}
            QPushButton#pomo_btn:hover {{
                color: {text};
                border-color: {muted};
            }}
            QLabel#pomo_foot {{
                font-size: 10px;
            }}
        """)
