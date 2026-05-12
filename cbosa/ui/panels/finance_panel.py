"""
FinancePanel — dockable panel for the personal finance ledger.

Layout (top to bottom):
  ┌─────────────────────────────────────────────────────┐
  │  Time period filter: [dropdown]  Category: [combo]  │
  ├───────────────────────────┬─────────────────────────┤
  │  Transaction table        │  Category totals         │
  │  (sortable)               │  (label list)            │
  ├───────────────────────────┴─────────────────────────┤
  │  [Add]  [Edit]  [Delete]  ║  [Manage Categories]     │
  └─────────────────────────────────────────────────────┘
"""
from __future__ import annotations

from datetime import date, timedelta

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from cbosa.core.ledger import Ledger, LedgerError, TransactionNotFoundError
from cbosa.ui.panels import BasePanel

# Time-period presets
_PERIOD_ALL = "All time"
_PERIOD_THIS_MONTH = "This month"
_PERIOD_LAST_3 = "Last 3 months"
_PERIOD_LAST_6 = "Last 6 months"
_PERIOD_THIS_YEAR = "This year"
_PERIODS = [_PERIOD_ALL, _PERIOD_THIS_MONTH, _PERIOD_LAST_3, _PERIOD_LAST_6, _PERIOD_THIS_YEAR]

# Transaction table column indices
_COL_DATE = 0
_COL_AMOUNT = 1
_COL_DESCRIPTION = 2
_COL_CATEGORY = 3
_COL_ID = 4  # hidden — stores the DB row id


class FinancePanel(BasePanel):
    """Finance ledger panel — transaction table, add/edit form, category summary."""

    transaction_changed = pyqtSignal()

    def __init__(self, ledger: Ledger, title: str = "Finance", parent=None) -> None:
        super().__init__(title, parent)
        self._ledger = ledger
        self._build_ui()
        self._refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(6)

        # ---- Filter bar ----
        filter_bar = QHBoxLayout()
        filter_bar.addWidget(QLabel("Period:"))
        self._period_combo = QComboBox()
        self._period_combo.addItems(_PERIODS)
        self._period_combo.setObjectName("period_combo")
        self._period_combo.currentTextChanged.connect(self._refresh)
        filter_bar.addWidget(self._period_combo)

        filter_bar.addSpacing(12)
        filter_bar.addWidget(QLabel("Category:"))
        self._cat_filter_combo = QComboBox()
        self._cat_filter_combo.setObjectName("cat_filter_combo")
        self._cat_filter_combo.addItem("All categories", userData=None)
        self._cat_filter_combo.currentIndexChanged.connect(self._refresh)
        filter_bar.addWidget(self._cat_filter_combo)
        filter_bar.addStretch()
        root_layout.addLayout(filter_bar)

        # ---- Splitter: table | totals ----
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Transaction table
        self._table = QTableWidget()
        self._table.setObjectName("transaction_table")
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["Date", "Amount", "Description", "Category", "id"])
        self._table.setColumnHidden(_COL_ID, True)
        self._table.horizontalHeader().setSectionResizeMode(
            _COL_DESCRIPTION, QHeaderView.ResizeMode.Stretch
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSortingEnabled(True)
        self._table.verticalHeader().setVisible(False)
        splitter.addWidget(self._table)

        # Totals panel
        totals_widget = QWidget()
        totals_layout = QVBoxLayout(totals_widget)
        totals_layout.setContentsMargins(4, 0, 4, 0)
        totals_layout.addWidget(QLabel("<b>Category Totals</b>"))
        self._totals_list = QListWidget()
        self._totals_list.setObjectName("totals_list")
        totals_layout.addWidget(self._totals_list)
        splitter.addWidget(totals_widget)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        root_layout.addWidget(splitter)

        # ---- Action buttons ----
        btn_bar = QHBoxLayout()
        self._add_btn = QPushButton("Add")
        self._add_btn.setObjectName("add_btn")
        self._edit_btn = QPushButton("Edit")
        self._edit_btn.setObjectName("edit_btn")
        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setObjectName("delete_btn")
        self._manage_cats_btn = QPushButton("Manage Categories")
        self._manage_cats_btn.setObjectName("manage_cats_btn")

        self._add_btn.clicked.connect(self._on_add)
        self._edit_btn.clicked.connect(self._on_edit)
        self._delete_btn.clicked.connect(self._on_delete)
        self._manage_cats_btn.clicked.connect(self._on_manage_categories)

        btn_bar.addWidget(self._add_btn)
        btn_bar.addWidget(self._edit_btn)
        btn_bar.addWidget(self._delete_btn)
        btn_bar.addStretch()
        btn_bar.addWidget(self._manage_cats_btn)
        root_layout.addLayout(btn_bar)

        self.setWidget(root)

    # ------------------------------------------------------------------
    # Refresh / data loading
    # ------------------------------------------------------------------

    def _current_date_range(self) -> tuple[str | None, str | None]:
        """Return (start_date, end_date) strings based on the period combo."""
        period = self._period_combo.currentText()
        today = date.today()

        if period == _PERIOD_ALL:
            return None, None
        elif period == _PERIOD_THIS_MONTH:
            start = today.replace(day=1)
            return start.isoformat(), today.isoformat()
        elif period == _PERIOD_LAST_3:
            start = (today - timedelta(days=90)).replace(day=1)
            return start.isoformat(), today.isoformat()
        elif period == _PERIOD_LAST_6:
            start = (today - timedelta(days=180)).replace(day=1)
            return start.isoformat(), today.isoformat()
        elif period == _PERIOD_THIS_YEAR:
            start = today.replace(month=1, day=1)
            return start.isoformat(), today.isoformat()
        return None, None

    def _current_category_filter(self) -> str | None:
        return self._cat_filter_combo.currentData()  # None means "all"

    def _refresh(self) -> None:
        """Reload transactions and totals from the ledger."""
        start, end = self._current_date_range()
        cat_filter = self._current_category_filter()

        self._refresh_table(start, end, cat_filter)
        self._refresh_totals(start, end)
        self._refresh_cat_filter_combo()

    def _refresh_table(self, start, end, cat_filter) -> None:
        txs = self._ledger.list_transactions(
            start_date=start, end_date=end, category=cat_filter
        )
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(txs))
        for row, tx in enumerate(txs):
            self._table.setItem(row, _COL_DATE, QTableWidgetItem(tx["date"]))
            amount_item = QTableWidgetItem(f"{tx['amount']:.2f}")
            amount_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._table.setItem(row, _COL_AMOUNT, amount_item)
            self._table.setItem(row, _COL_DESCRIPTION, QTableWidgetItem(tx["description"]))
            self._table.setItem(row, _COL_CATEGORY, QTableWidgetItem(tx["category"]))
            self._table.setItem(row, _COL_ID, QTableWidgetItem(str(tx["id"])))
        self._table.setSortingEnabled(True)

    def _refresh_totals(self, start, end) -> None:
        totals = self._ledger.category_totals(start_date=start, end_date=end)
        self._totals_list.clear()
        for cat, total in sorted(totals.items()):
            self._totals_list.addItem(QListWidgetItem(f"{cat}: {total:+.2f}"))

    def _refresh_cat_filter_combo(self) -> None:
        """Sync the category filter combo with current categories."""
        current = self._cat_filter_combo.currentData()
        self._cat_filter_combo.blockSignals(True)
        self._cat_filter_combo.clear()
        self._cat_filter_combo.addItem("All categories", userData=None)
        for cat in self._ledger.list_categories():
            self._cat_filter_combo.addItem(cat["name"], userData=cat["name"])
        for i in range(self._cat_filter_combo.count()):
            if self._cat_filter_combo.itemData(i) == current:
                self._cat_filter_combo.setCurrentIndex(i)
                break
        self._cat_filter_combo.blockSignals(False)

    # ------------------------------------------------------------------
    # Selected transaction id helper
    # ------------------------------------------------------------------

    def _selected_tx_id(self) -> int | None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        item = self._table.item(row, _COL_ID)
        if item is None:
            return None
        return int(item.text())

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _on_add(self) -> None:
        dlg = _TransactionDialog(self._ledger, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            try:
                self._ledger.add_transaction(
                    data["date"], data["amount"], data["description"], data["category"]
                )
                self._refresh()
                self.transaction_changed.emit()
            except LedgerError as exc:
                QMessageBox.warning(self, "Invalid transaction", str(exc))

    def _on_edit(self) -> None:
        tx_id = self._selected_tx_id()
        if tx_id is None:
            QMessageBox.information(self, "Edit", "Select a transaction to edit.")
            return
        try:
            tx = self._ledger.get_transaction(tx_id)
        except TransactionNotFoundError:
            self._refresh()
            return
        dlg = _TransactionDialog(self._ledger, tx=tx, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            try:
                self._ledger.edit_transaction(
                    tx_id,
                    date=data["date"],
                    amount=data["amount"],
                    description=data["description"],
                    category=data["category"],
                )
                self._refresh()
                self.transaction_changed.emit()
            except LedgerError as exc:
                QMessageBox.warning(self, "Invalid transaction", str(exc))

    def _on_delete(self) -> None:
        tx_id = self._selected_tx_id()
        if tx_id is None:
            QMessageBox.information(self, "Delete", "Select a transaction to delete.")
            return
        reply = QMessageBox.question(
            self, "Delete transaction",
            "Delete the selected transaction?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._ledger.delete_transaction(tx_id)
                self._refresh()
                self.transaction_changed.emit()
            except TransactionNotFoundError:
                self._refresh()

    def _on_manage_categories(self) -> None:
        dlg = _CategoryDialog(self._ledger, parent=self)
        dlg.exec()
        self._refresh()


# ---------------------------------------------------------------------------
# Transaction add/edit dialog
# ---------------------------------------------------------------------------

class _TransactionDialog(QDialog):
    """Modal dialog for adding or editing a transaction."""

    def __init__(self, ledger: Ledger, tx: dict | None = None, parent=None) -> None:
        super().__init__(parent)
        self._ledger = ledger
        self._tx = tx
        self.setWindowTitle("Edit Transaction" if tx else "Add Transaction")
        self._build_ui()
        if tx:
            self._populate(tx)

    def _build_ui(self) -> None:
        layout = QFormLayout(self)

        self._date_edit = QLineEdit()
        self._date_edit.setObjectName("tx_date_edit")
        self._date_edit.setPlaceholderText("YYYY-MM-DD")
        layout.addRow("Date:", self._date_edit)

        self._amount_spin = QDoubleSpinBox()
        self._amount_spin.setObjectName("tx_amount_spin")
        self._amount_spin.setRange(-1_000_000, 1_000_000)
        self._amount_spin.setDecimals(2)
        self._amount_spin.setSingleStep(1.00)
        layout.addRow("Amount:", self._amount_spin)

        self._desc_edit = QLineEdit()
        self._desc_edit.setObjectName("tx_desc_edit")
        layout.addRow("Description:", self._desc_edit)

        self._cat_combo = QComboBox()
        self._cat_combo.setObjectName("tx_cat_combo")
        self._cat_combo.setEditable(True)
        for cat in self._ledger.list_categories():
            self._cat_combo.addItem(cat["name"])
        layout.addRow("Category:", self._cat_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        if not self._tx:
            self._date_edit.setText(date.today().isoformat())

    def _populate(self, tx: dict) -> None:
        self._date_edit.setText(tx["date"])
        self._amount_spin.setValue(tx["amount"])
        self._desc_edit.setText(tx["description"])
        idx = self._cat_combo.findText(tx["category"])
        if idx >= 0:
            self._cat_combo.setCurrentIndex(idx)
        else:
            self._cat_combo.setEditText(tx["category"])

    def get_data(self) -> dict:
        return {
            "date": self._date_edit.text().strip(),
            "amount": self._amount_spin.value(),
            "description": self._desc_edit.text().strip(),
            "category": self._cat_combo.currentText().strip(),
        }


# ---------------------------------------------------------------------------
# Category management dialog
# ---------------------------------------------------------------------------

class _CategoryDialog(QDialog):
    """Modal dialog for creating and deleting spending categories."""

    def __init__(self, ledger: Ledger, parent=None) -> None:
        super().__init__(parent)
        self._ledger = ledger
        self.setWindowTitle("Manage Categories")
        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self._list = QListWidget()
        self._list.setObjectName("category_list")
        layout.addWidget(self._list)

        btn_bar = QHBoxLayout()
        self._add_btn = QPushButton("Add")
        self._add_btn.setObjectName("cat_add_btn")
        self._del_btn = QPushButton("Delete")
        self._del_btn.setObjectName("cat_del_btn")
        self._add_btn.clicked.connect(self._on_add)
        self._del_btn.clicked.connect(self._on_delete)
        btn_bar.addWidget(self._add_btn)
        btn_bar.addWidget(self._del_btn)
        btn_bar.addStretch()
        layout.addLayout(btn_bar)

        close_btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_btn.rejected.connect(self.reject)
        layout.addWidget(close_btn)

    def _refresh(self) -> None:
        self._list.clear()
        for cat in self._ledger.list_categories():
            item = QListWidgetItem(cat["name"])
            item.setData(Qt.ItemDataRole.UserRole, cat["id"])
            self._list.addItem(item)

    def _on_add(self) -> None:
        name, ok = QInputDialog.getText(self, "Add Category", "Category name:")
        if ok and name.strip():
            try:
                self._ledger.add_category(name.strip())
                self._refresh()
            except LedgerError as exc:
                QMessageBox.warning(self, "Error", str(exc))

    def _on_delete(self) -> None:
        item = self._list.currentItem()
        if not item:
            return
        cat_id = item.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(
            self, "Delete category",
            f"Delete category '{item.text()}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._ledger.delete_category(cat_id)
                self._refresh()
            except LedgerError as exc:
                QMessageBox.warning(self, "Error", str(exc))
