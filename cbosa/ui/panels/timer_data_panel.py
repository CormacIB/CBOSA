"""
TimerDataPanel — dockable panel showing time-tracking history.

Tab 1: Bar chart of total time per group/category for a selectable period.
Tab 2: Scrollable session log (date | group | category | duration).

All colours come from the active theme.
"""
from __future__ import annotations

from datetime import date, timedelta

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from cbosa import config
from cbosa.core.timer_store import TimerStore
from cbosa.ui.panels import BasePanel

_PERIOD_TODAY      = "Today"
_PERIOD_THIS_WEEK  = "This week"
_PERIOD_THIS_MONTH = "This month"
_PERIOD_ALL        = "All time"
_PERIODS = [_PERIOD_TODAY, _PERIOD_THIS_WEEK, _PERIOD_THIS_MONTH, _PERIOD_ALL]


def _date_range_for(period: str) -> tuple[str | None, str | None]:
    today = date.today()
    if period == _PERIOD_ALL:
        return None, None
    elif period == _PERIOD_TODAY:
        iso = today.isoformat()
        return iso, iso
    elif period == _PERIOD_THIS_WEEK:
        start = today - timedelta(days=today.weekday())
        return start.isoformat(), today.isoformat()
    elif period == _PERIOD_THIS_MONTH:
        return today.replace(day=1).isoformat(), today.isoformat()
    return None, None


def _fmt_duration(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m {s:02d}s"


# ---------------------------------------------------------------------------
# Bar chart widget (mirrors finance_summary_panel pattern)
# ---------------------------------------------------------------------------

class _TimeBarChart(QWidget):
    BAR_W         = 14
    MARGIN_LEFT   = 52
    MARGIN_RIGHT  = 8
    MARGIN_TOP    = 24
    MARGIN_BOTTOM = 100
    LABEL_FONT_PT = 9

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._labels: list[str] = []
        self._seconds: list[int] = []
        self._bg  = QColor("#1e1e2e")
        self._fg  = QColor("#cdd6f4")
        self._bar = QColor("#45475a")
        self._pen = QColor("#cba6f7")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_data(self, labels: list[str], seconds: list[int]) -> None:
        self._labels = labels
        self._seconds = seconds
        self.update()

    def clear(self) -> None:
        self._labels = []
        self._seconds = []
        self.update()

    def set_colors(self, bg: str, fg: str, bar: str, bar_pen: str) -> None:
        self._bg  = QColor(bg)
        self._fg  = QColor(fg)
        self._bar = QColor(bar)
        self._pen = QColor(bar_pen)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        W, H = self.width(), self.height()
        p.fillRect(0, 0, W, H, self._bg)

        n = len(self._seconds)
        if n == 0:
            p.end()
            return

        ML, MR, MT, MB = self.MARGIN_LEFT, self.MARGIN_RIGHT, self.MARGIN_TOP, self.MARGIN_BOTTOM
        chart_w = W - ML - MR
        chart_h = H - MT - MB
        if chart_w <= 0 or chart_h <= 0:
            p.end()
            return

        y_max = max(self._seconds) * 1.25
        MAX_SLOT_PX = 55
        slot_w = min(MAX_SLOT_PX, chart_w / n)
        bar_w  = min(self.BAR_W, int(slot_w * 0.35))

        font = QFont("Helvetica Neue", self.LABEL_FONT_PT)
        p.setFont(font)
        fm = QFontMetrics(font)

        bars_w = int(slot_w * n)

        # Grid lines + y-axis labels (in hours/minutes)
        NUM_GRID = 4
        grid_color = QColor(self._fg)
        grid_color.setAlpha(40)
        for i in range(NUM_GRID + 1):
            val  = y_max * i / NUM_GRID
            y_px = MT + chart_h - int(val / y_max * chart_h)
            p.setPen(QPen(grid_color, 1))
            p.drawLine(ML, y_px, ML + bars_w, y_px)
            p.setPen(self._fg)
            lbl = _fmt_duration(int(val))
            lw  = fm.horizontalAdvance(lbl)
            p.drawText(ML - lw - 4, y_px + fm.ascent() // 2, lbl)

        # Axis lines
        p.setPen(QPen(self._fg, 1))
        p.drawLine(ML, MT, ML, MT + chart_h)
        p.drawLine(ML, MT + chart_h, ML + bars_w, MT + chart_h)

        # Rotated y-axis label
        p.save()
        p.translate(11, MT + chart_h // 2)
        p.rotate(-90)
        p.setPen(self._fg)
        axis_lbl = "Time"
        aw = fm.horizontalAdvance(axis_lbl)
        p.drawText(-aw // 2, fm.ascent() // 2, axis_lbl)
        p.restore()

        # Bars + labels
        for i, (lbl, secs) in enumerate(zip(self._labels, self._seconds)):
            cx = ML + int(slot_w * i + slot_w / 2)
            bx = cx - bar_w // 2
            bh = int(secs / y_max * chart_h)
            by = MT + chart_h - bh

            p.fillRect(bx, by, bar_w, bh, self._bar)
            p.setPen(QPen(self._pen, 1))
            p.drawRect(bx, by, bar_w, bh)

            # Duration label above bar
            dur = _fmt_duration(secs)
            dw  = fm.horizontalAdvance(dur)
            p.setPen(self._pen)
            p.drawText(cx - dw // 2, by - 4, dur)

            # Category label rotated
            label_start_y = MT + chart_h + 6
            available_h   = max(0, H - label_start_y - 6)
            p.save()
            p.translate(cx, label_start_y)
            p.rotate(90)
            p.setPen(self._fg)
            short = lbl if len(lbl) <= 14 else lbl[:13] + "…"
            p.drawText(2, -fm.height() // 2, available_h, fm.height(),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, short)
            p.restore()

        p.end()


# ---------------------------------------------------------------------------
# TimerDataPanel
# ---------------------------------------------------------------------------

class TimerDataPanel(BasePanel):
    """Time-tracking history: bar chart + session log in tabs."""

    def __init__(self, timer_store: TimerStore, title: str = "Time Tracker", parent=None) -> None:
        super().__init__(title, parent)
        self._store = timer_store
        self._colors: dict = {}
        self._build_ui()
        self._apply_theme()
        self._refresh()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Period selector
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Period:"))
        self._period_combo = QComboBox()
        self._period_combo.setObjectName("timer_period_combo")
        self._period_combo.addItems(_PERIODS)
        self._period_combo.currentTextChanged.connect(self._refresh)
        top_row.addWidget(self._period_combo)
        top_row.addStretch()
        layout.addLayout(top_row)

        # Tabs
        self._tabs = QTabWidget()
        self._tabs.setObjectName("timer_data_tabs")

        # Tab 1: bar chart
        chart_widget = QWidget()
        chart_layout = QVBoxLayout(chart_widget)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        self._chart = _TimeBarChart()
        chart_layout.addWidget(self._chart)
        self._tabs.addTab(chart_widget, "Summary")

        # Tab 2: session log
        self._table = QTableWidget()
        self._table.setObjectName("timer_session_table")
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Date", "Group", "Category", "Duration"])
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._tabs.addTab(self._table, "Sessions")

        layout.addWidget(self._tabs, stretch=1)
        self.setWidget(root)

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        period = self._period_combo.currentText()
        start, end = _date_range_for(period)

        # Bar chart
        totals = self._store.category_totals(start_date=start, end_date=end)
        if totals:
            labels  = [f"{t['group_name']}\n{t['category_name']}" for t in totals]
            seconds = [t["total_seconds"] for t in totals]
            self._chart.set_data(labels, seconds)
        else:
            self._chart.clear()

        # Session log
        sessions = self._store.list_sessions(start_date=start, end_date=end)
        self._table.setRowCount(len(sessions))
        for row, s in enumerate(sessions):
            date_str = s["start_time"][:10]
            self._table.setItem(row, 0, QTableWidgetItem(date_str))
            self._table.setItem(row, 1, QTableWidgetItem(s["group_name"]))
            self._table.setItem(row, 2, QTableWidgetItem(s["category_name"]))
            self._table.setItem(row, 3, QTableWidgetItem(_fmt_duration(s["duration_seconds"])))

    def refresh(self) -> None:
        """Public refresh — call after a session is logged externally."""
        self._refresh()

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _load_theme_colors(self) -> dict:
        from cbosa.ui.theme_engine import ThemeEngine, ThemeLoadError
        try:
            theme_path = str(config.resolve("theme", "themes/dark_default.toml"))
            colors, _ = ThemeEngine().get_colors_and_fonts(theme_path)
            return colors
        except (ThemeLoadError, KeyError):
            return {}

    def _apply_colors(self, colors: dict) -> None:
        self._colors = colors
        self._chart.set_colors(
            colors.get("background", "#1e1e2e"),
            colors.get("text",       "#cdd6f4"),
            colors.get("text_muted", "#6c7086"),
            colors.get("primary",    "#cba6f7"),
        )

    def _apply_theme(self) -> None:
        self._apply_colors(self._load_theme_colors())

    def update_theme(self, theme_path: str) -> None:
        from cbosa.ui.theme_engine import ThemeEngine, ThemeLoadError
        try:
            colors, _ = ThemeEngine().get_colors_and_fonts(theme_path)
            self._apply_colors(colors)
            self._refresh()
        except ThemeLoadError:
            pass
