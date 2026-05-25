"""
FinanceSummaryPanel — compact dockable panel showing a category bar chart
and a spent-vs-budget summary for a selectable time period.

Uses a custom QPainter-based chart widget so bar width is fixed in pixels
and all n bars always fit the available space without scrolling.
"""
from __future__ import annotations

import csv
from datetime import date, timedelta

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from cbosa import config
from cbosa.core.ledger import Ledger
from cbosa.ui.panels import BasePanel

_PERIOD_ALL        = "All time"
_PERIOD_THIS_MONTH = "This month"
_PERIOD_LAST_3     = "Last 3 months"
_PERIOD_LAST_6     = "Last 6 months"
_PERIOD_THIS_YEAR  = "This year"
_PERIODS = [_PERIOD_THIS_MONTH, _PERIOD_LAST_3, _PERIOD_LAST_6, _PERIOD_THIS_YEAR, _PERIOD_ALL]


def _date_range_for(period: str) -> tuple[str | None, str | None]:
    today = date.today()
    if period == _PERIOD_ALL:
        return None, None
    elif period == _PERIOD_THIS_MONTH:
        return today.replace(day=1).isoformat(), today.isoformat()
    elif period == _PERIOD_LAST_3:
        return (today - timedelta(days=90)).replace(day=1).isoformat(), today.isoformat()
    elif period == _PERIOD_LAST_6:
        return (today - timedelta(days=180)).replace(day=1).isoformat(), today.isoformat()
    elif period == _PERIOD_THIS_YEAR:
        return today.replace(month=1, day=1).isoformat(), today.isoformat()
    return None, None


def _truncate(label: str, maxlen: int = 14) -> str:
    return label if len(label) <= maxlen else label[:maxlen - 1] + "…"


class _BarChart(QWidget):
    """
    Pixel-perfect bar chart drawn with QPainter.

    Bar width is a fixed number of pixels (BAR_W).  Slots (the space
    allocated to each bar including its gap) are calculated as
    chart_width / n, so all n bars always fit without scrolling.
    """

    BAR_W         = 14   # fixed bar width in pixels
    MARGIN_LEFT   = 52   # y-axis labels
    MARGIN_RIGHT  = 8
    MARGIN_TOP    = 24   # dollar labels above bars
    MARGIN_BOTTOM = 100  # reserved for rotated category labels below x-axis
    LABEL_FONT_PT = 9

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._categories: list[str] = []
        self._amounts:    list[float] = []
        self._bg    = QColor("#000000")
        self._fg    = QColor("#33ff66")
        self._bar   = QColor("#1a8033")
        self._pen   = QColor("#33ff66")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    # ------------------------------------------------------------------ public
    def set_data(self, categories: list[str], amounts: list[float]) -> None:
        self._categories = categories
        self._amounts    = amounts
        self.update()

    def clear(self) -> None:
        self._categories = []
        self._amounts    = []
        self.update()

    def set_colors(self, bg: str, fg: str, bar: str, bar_pen: str) -> None:
        self._bg  = QColor(bg)
        self._fg  = QColor(fg)
        self._bar = QColor(bar)
        self._pen = QColor(bar_pen)
        self.update()

    # ------------------------------------------------------------------ paint
    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        W, H = self.width(), self.height()
        p.fillRect(0, 0, W, H, self._bg)

        n = len(self._amounts)
        if n == 0:
            p.end()
            return

        ML = self.MARGIN_LEFT
        MR = self.MARGIN_RIGHT
        MT = self.MARGIN_TOP
        MB = self.MARGIN_BOTTOM

        chart_w = W - ML - MR
        chart_h = H - MT - MB
        if chart_w <= 0 or chart_h <= 0:
            p.end()
            return

        y_max       = max(self._amounts) * 1.25
        # Cap slot width so bars never spread to fill a wide panel.
        # Falls back to chart_w/n when the panel is narrow, guaranteeing
        # all n bars always fit within the visible area.
        MAX_SLOT_PX = 55
        slot_w  = min(MAX_SLOT_PX, chart_w / n)
        bar_w   = min(self.BAR_W, int(slot_w * 0.35))  # never wider than 35% of slot

        font = QFont()
        font.setPointSize(self.LABEL_FONT_PT)
        p.setFont(font)
        fm = QFontMetrics(font)

        bars_w = int(slot_w * n)   # total pixel width occupied by all bars

        # ---- grid lines + y-axis labels -----------------------------------
        NUM_GRID = 4
        grid_color = QColor(self._fg)
        grid_color.setAlpha(40)
        label_color = self._fg

        for i in range(NUM_GRID + 1):
            val  = y_max * i / NUM_GRID
            y_px = MT + chart_h - int(val / y_max * chart_h)
            p.setPen(QPen(grid_color, 1))
            p.drawLine(ML, y_px, ML + bars_w, y_px)
            p.setPen(label_color)
            lbl = f"{val:,.0f}"
            lw  = fm.horizontalAdvance(lbl)
            p.drawText(ML - lw - 4, y_px + fm.ascent() // 2, lbl)

        # ---- axis lines ---------------------------------------------------
        p.setPen(QPen(self._fg, 1))
        p.drawLine(ML, MT, ML, MT + chart_h)
        p.drawLine(ML, MT + chart_h, ML + bars_w, MT + chart_h)

        # ---- "Cost ($)" rotated label ------------------------------------
        p.save()
        p.translate(11, MT + chart_h // 2)
        p.rotate(-90)
        p.setPen(self._fg)
        axis_lbl = "Cost ($)"
        aw = fm.horizontalAdvance(axis_lbl)
        p.drawText(-aw // 2, fm.ascent() // 2, axis_lbl)
        p.restore()

        # ---- bars + labels -----------------------------------------------
        for i, (cat, amt) in enumerate(zip(self._categories, self._amounts)):
            cx   = ML + int(slot_w * i + slot_w / 2)   # slot centre x
            bx   = cx - bar_w // 2
            bh   = int(amt / y_max * chart_h)
            by   = MT + chart_h - bh

            # bar fill
            p.fillRect(bx, by, bar_w, bh, self._bar)
            # bar border
            p.setPen(QPen(self._pen, 1))
            p.drawRect(bx, by, bar_w, bh)

            # dollar label above bar
            dollar = f"${amt:,.0f}"
            dw     = fm.horizontalAdvance(dollar)
            p.setPen(self._pen)
            p.drawText(cx - dw // 2, by - 4, dollar)

            # category label — rotated 90° CW so text reads top → bottom
            # Use actual remaining pixel space (with 6px safety margin from
            # widget bottom) rather than a constant, so labels never clip.
            label_start_y = MT + chart_h + 6
            available_h   = max(0, H - label_start_y - 6)
            p.save()
            p.translate(cx, label_start_y)
            p.rotate(90)
            p.setPen(self._fg)
            p.drawText(2, -fm.height() // 2, available_h, fm.height(),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       _truncate(cat))
            p.restore()

        p.end()


class FinanceSummaryPanel(BasePanel):
    """Compact finance summary: vertical bar chart (categories × cost) + budget summary."""

    def __init__(self, ledger: Ledger, title: str = "Finance Summary", parent=None) -> None:
        super().__init__(title, parent)
        self._ledger    = ledger
        self._bg_color  = "#000000"
        self._fg_color  = "#33ff66"
        self._bar_color = "#1a8033"
        self._bar_pen   = "#33ff66"
        self._build_ui()
        self._apply_plot_theme()
        self._refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(6)

        # Top bar: period selector + summary label + set budget
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Period:"))
        self._period_combo = QComboBox()
        self._period_combo.setObjectName("summary_period_combo")
        self._period_combo.addItems(_PERIODS)
        self._period_combo.currentTextChanged.connect(self._refresh)
        top_row.addWidget(self._period_combo)

        top_row.addSpacing(12)
        self._summary_label = QLabel()
        self._summary_label.setObjectName("finance_summary_label")
        top_row.addWidget(self._summary_label)
        top_row.addStretch()

        budget_btn = QPushButton("Set Budget")
        budget_btn.setObjectName("finance_budget_btn")
        budget_btn.clicked.connect(self._on_set_budget)
        top_row.addWidget(budget_btn)

        export_btn = QPushButton("Export CSV")
        export_btn.setObjectName("finance_export_btn")
        export_btn.clicked.connect(self._on_export_csv)
        top_row.addWidget(export_btn)
        root_layout.addLayout(top_row)

        # Custom pixel-based bar chart
        self._chart = _BarChart()
        self._chart.setObjectName("finance_bar_chart")
        root_layout.addWidget(self._chart, stretch=1)

        self.setWidget(root)

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        period = self._period_combo.currentText()
        start, end = _date_range_for(period)
        totals = self._ledger.category_totals(start_date=start, end_date=end)

        expenses = sorted(
            ((k, abs(v)) for k, v in totals.items() if v != 0),
            key=lambda x: x[1],
            reverse=True,
        )

        total_spent = sum(amt for _, amt in expenses)
        self._update_summary(total_spent)

        if expenses:
            self._chart.set_data(
                [c for c, _ in expenses],
                [a for _, a in expenses],
            )
        else:
            self._chart.clear()

    def _update_summary(self, spent: float) -> None:
        finance_cfg = config.get("finance") or {}
        budget = float(finance_cfg.get("monthly_budget", 0.0))
        if budget > 0:
            self._summary_label.setText(f"Spent:  ${spent:,.2f}  /  ${budget:,.2f}")
        else:
            self._summary_label.setText(f"Spent:  ${spent:,.2f}")

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _load_theme_colors(self, theme_path: str) -> dict:
        from cbosa.ui.theme_engine import ThemeEngine, ThemeLoadError
        try:
            colors, _ = ThemeEngine().get_colors_and_fonts(theme_path)
            return colors
        except ThemeLoadError:
            return {}

    def _apply_colors(self, colors: dict) -> None:
        self._bg_color  = colors.get("background", "#000000")
        self._fg_color  = colors.get("text",        "#ffffff")
        self._bar_color = colors.get("text_muted",  "#888888")
        self._bar_pen   = colors.get("accent",      self._fg_color)
        self._chart.set_colors(
            self._bg_color, self._fg_color, self._bar_color, self._bar_pen
        )

    def _apply_plot_theme(self) -> None:
        try:
            theme_path = str(config.resolve("theme", "themes/obsidian_dark.toml"))
        except KeyError:
            return
        self._apply_colors(self._load_theme_colors(theme_path))

    def update_theme(self, theme_path: str) -> None:
        """Called by MainWindow when the user switches themes."""
        self._apply_colors(self._load_theme_colors(theme_path))
        self._refresh()

    # ------------------------------------------------------------------
    # Budget dialog
    # ------------------------------------------------------------------

    def _on_set_budget(self) -> None:
        finance_cfg = config.get("finance") or {}
        current = float(finance_cfg.get("monthly_budget", 0.0))
        dlg = _BudgetDialog(current, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            config.save_finance_budget(dlg.value())
            self._refresh()

    def _on_export_csv(self) -> None:
        period = self._period_combo.currentText()
        start, end = _date_range_for(period)
        transactions = self._ledger.list_transactions(start_date=start, end_date=end)

        default_name = f"finances_{period.lower().replace(' ', '_')}.csv"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Transactions", default_name, "CSV files (*.csv)"
        )
        if not path:
            return

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["id", "date", "amount", "description", "category"])
            writer.writeheader()
            writer.writerows(transactions)


class _BudgetDialog(QDialog):
    def __init__(self, current: float, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Set Monthly Budget")
        layout = QFormLayout(self)

        self._spin = QDoubleSpinBox()
        self._spin.setObjectName("budget_spin")
        self._spin.setRange(0, 1_000_000)
        self._spin.setDecimals(2)
        self._spin.setSingleStep(50.0)
        self._spin.setValue(current)
        self._spin.setPrefix("$ ")
        layout.addRow("Monthly budget:", self._spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def value(self) -> float:
        return self._spin.value()
