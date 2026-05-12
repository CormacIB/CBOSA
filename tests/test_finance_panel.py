"""
Tests for Issue #8 — Finance Ledger + Panel.

Behaviors verified through public interfaces only.
All tests use an in-memory Ledger (no disk I/O).
"""
from __future__ import annotations

import pytest

from cbosa.core.ledger import Ledger
from cbosa.ui.panels import BasePanel
from cbosa.ui.panels.finance_panel import (
    FinancePanel,
    _COL_DATE,
    _COL_AMOUNT,
    _COL_DESCRIPTION,
    _COL_CATEGORY,
    _COL_ID,
    _PERIODS,
    _PERIOD_ALL,
    _PERIOD_THIS_MONTH,
    _PERIOD_LAST_3,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ledger():
    db = Ledger(":memory:")
    yield db
    db.close()


@pytest.fixture
def panel(qapp, ledger):
    return FinancePanel(ledger)


# ---------------------------------------------------------------------------
# Slice 1 — tracer bullet: FinancePanel is a BasePanel
# ---------------------------------------------------------------------------


def test_is_base_panel(panel):
    assert isinstance(panel, BasePanel)


# ---------------------------------------------------------------------------
# Slice 2 — empty ledger shows no rows on init
# ---------------------------------------------------------------------------


def test_empty_ledger_shows_no_rows(panel):
    assert panel._table.rowCount() == 0


def test_empty_ledger_shows_no_totals(panel):
    assert panel._totals_list.count() == 0


# ---------------------------------------------------------------------------
# Slice 3 — transactions appear in the table on init
# ---------------------------------------------------------------------------


def test_shows_transactions_on_init(qapp, ledger):
    ledger.add_transaction("2026-05-01", -42.50, "Supermarket", "Groceries")
    ledger.add_transaction("2026-05-02", -10.00, "Bus", "Transport")
    panel = FinancePanel(ledger)
    assert panel._table.rowCount() == 2


def test_table_shows_correct_date(qapp, ledger):
    ledger.add_transaction("2026-05-01", -42.50, "Supermarket", "Groceries")
    panel = FinancePanel(ledger)
    assert panel._table.item(0, _COL_DATE).text() == "2026-05-01"


def test_table_shows_correct_amount(qapp, ledger):
    ledger.add_transaction("2026-05-01", -42.50, "Supermarket", "Groceries")
    panel = FinancePanel(ledger)
    assert "-42.50" in panel._table.item(0, _COL_AMOUNT).text()


def test_table_shows_correct_description(qapp, ledger):
    ledger.add_transaction("2026-05-01", -42.50, "Supermarket", "Groceries")
    panel = FinancePanel(ledger)
    assert panel._table.item(0, _COL_DESCRIPTION).text() == "Supermarket"


def test_table_shows_correct_category(qapp, ledger):
    ledger.add_transaction("2026-05-01", -42.50, "Supermarket", "Groceries")
    panel = FinancePanel(ledger)
    assert panel._table.item(0, _COL_CATEGORY).text() == "Groceries"


# ---------------------------------------------------------------------------
# Slice 4 — id column is hidden
# ---------------------------------------------------------------------------


def test_id_column_is_hidden(panel):
    assert panel._table.isColumnHidden(_COL_ID)


# ---------------------------------------------------------------------------
# Slice 5 — table is sortable
# ---------------------------------------------------------------------------


def test_table_is_sortable(panel):
    assert panel._table.isSortingEnabled()


# ---------------------------------------------------------------------------
# Slice 6 — period combo has all expected options
# ---------------------------------------------------------------------------


def test_period_combo_has_all_options(panel):
    items = [panel._period_combo.itemText(i) for i in range(panel._period_combo.count())]
    for period in _PERIODS:
        assert period in items


# ---------------------------------------------------------------------------
# Slice 7 — category filter combo has "All categories" as first option
# ---------------------------------------------------------------------------


def test_category_filter_has_all_option(panel):
    assert panel._cat_filter_combo.itemText(0) == "All categories"


def test_category_filter_all_option_has_none_data(panel):
    assert panel._cat_filter_combo.itemData(0) is None


# ---------------------------------------------------------------------------
# Slice 8 — category filter combo reflects ledger categories
# ---------------------------------------------------------------------------


def test_category_filter_lists_categories(qapp, ledger):
    ledger.add_category("Groceries")
    ledger.add_category("Transport")
    panel = FinancePanel(ledger)
    items = [panel._cat_filter_combo.itemText(i) for i in range(panel._cat_filter_combo.count())]
    assert "Groceries" in items
    assert "Transport" in items


# ---------------------------------------------------------------------------
# Slice 9 — _refresh() updates table after ledger change
# ---------------------------------------------------------------------------


def test_refresh_updates_table_after_add(panel, ledger):
    assert panel._table.rowCount() == 0
    ledger.add_transaction("2026-05-01", -5.00, "Coffee", "Dining")
    panel._refresh()
    assert panel._table.rowCount() == 1


def test_refresh_updates_table_after_delete(qapp, ledger):
    tx_id = ledger.add_transaction("2026-05-01", -5.00, "Coffee", "Dining")
    panel = FinancePanel(ledger)
    assert panel._table.rowCount() == 1
    ledger.delete_transaction(tx_id)
    panel._refresh()
    assert panel._table.rowCount() == 0


def test_refresh_updates_table_after_edit(qapp, ledger):
    tx_id = ledger.add_transaction("2026-05-01", -5.00, "Coffee", "Dining")
    panel = FinancePanel(ledger)
    ledger.edit_transaction(tx_id, date="2026-05-02", amount=-8.00,
                            description="Latte", category="Dining")
    panel._refresh()
    assert panel._table.item(0, _COL_DESCRIPTION).text() == "Latte"
    assert "-8.00" in panel._table.item(0, _COL_AMOUNT).text()


# ---------------------------------------------------------------------------
# Slice 10 — _refresh() updates category totals
# ---------------------------------------------------------------------------


def test_refresh_shows_category_total(panel, ledger):
    ledger.add_transaction("2026-05-01", -30.00, "Shop", "Groceries")
    panel._refresh()
    items = [panel._totals_list.item(i).text() for i in range(panel._totals_list.count())]
    assert any("Groceries" in it for it in items)
    assert any("-30.00" in it for it in items)


def test_totals_cleared_after_all_deleted(qapp, ledger):
    tx_id = ledger.add_transaction("2026-05-01", -30.00, "Shop", "Groceries")
    panel = FinancePanel(ledger)
    assert panel._totals_list.count() == 1
    ledger.delete_transaction(tx_id)
    panel._refresh()
    assert panel._totals_list.count() == 0


def test_totals_show_multiple_categories(panel, ledger):
    ledger.add_transaction("2026-05-01", -30.00, "Shop", "Groceries")
    ledger.add_transaction("2026-05-02", -15.00, "Bus", "Transport")
    panel._refresh()
    items = [panel._totals_list.item(i).text() for i in range(panel._totals_list.count())]
    assert any("Groceries" in it for it in items)
    assert any("Transport" in it for it in items)


# ---------------------------------------------------------------------------
# Slice 11 — transaction_changed signal
# ---------------------------------------------------------------------------


def test_transaction_changed_signal_connectable(panel):
    received = []
    panel.transaction_changed.connect(lambda: received.append(1))
    panel.transaction_changed.emit()
    assert received == [1]


# ---------------------------------------------------------------------------
# Slice 12 — _selected_tx_id helper
# ---------------------------------------------------------------------------


def test_selected_tx_id_none_when_nothing_selected(panel):
    assert panel._selected_tx_id() is None


def test_selected_tx_id_returns_correct_id(qapp, ledger):
    tx_id = ledger.add_transaction("2026-05-01", -5.00, "Coffee", "Dining")
    panel = FinancePanel(ledger)
    panel._table.selectRow(0)
    assert panel._selected_tx_id() == tx_id


def test_selected_tx_id_correct_after_multiple_rows(qapp, ledger):
    ledger.add_transaction("2026-05-01", -5.00, "Coffee", "Dining")
    tx_id2 = ledger.add_transaction("2026-05-02", -10.00, "Lunch", "Dining")
    panel = FinancePanel(ledger)
    # Table is sorted date DESC — row 0 is the most recent (tx_id2)
    panel._table.selectRow(0)
    assert panel._selected_tx_id() == tx_id2


# ---------------------------------------------------------------------------
# Slice 13 — _on_delete and _on_edit with no selection do not crash
# ---------------------------------------------------------------------------


def test_on_delete_no_selection_does_not_crash(panel):
    panel._on_delete()  # must not raise


def test_on_edit_no_selection_does_not_crash(panel):
    panel._on_edit()  # must not raise


# ---------------------------------------------------------------------------
# Slice 14 — period filter "All time" shows all transactions
# ---------------------------------------------------------------------------


def test_period_all_shows_all_transactions(qapp, ledger):
    ledger.add_transaction("2020-01-01", -10.00, "Old tx", "A")
    ledger.add_transaction("2026-05-01", -20.00, "New tx", "A")
    panel = FinancePanel(ledger)
    panel._period_combo.setCurrentText(_PERIOD_ALL)
    assert panel._table.rowCount() == 2


# ---------------------------------------------------------------------------
# Slice 15 — category filter narrows table rows
# ---------------------------------------------------------------------------


def test_category_filter_narrows_to_selected_category(qapp, ledger):
    ledger.add_category("Groceries")
    ledger.add_category("Transport")
    ledger.add_transaction("2026-05-01", -10.00, "Supermarket", "Groceries")
    ledger.add_transaction("2026-05-02", -5.00, "Bus", "Transport")
    panel = FinancePanel(ledger)

    idx = panel._cat_filter_combo.findData("Groceries")
    panel._cat_filter_combo.setCurrentIndex(idx)

    assert panel._table.rowCount() == 1
    assert panel._table.item(0, _COL_DESCRIPTION).text() == "Supermarket"


def test_category_filter_all_shows_all_rows(qapp, ledger):
    ledger.add_category("Groceries")
    ledger.add_category("Transport")
    ledger.add_transaction("2026-05-01", -10.00, "Supermarket", "Groceries")
    ledger.add_transaction("2026-05-02", -5.00, "Bus", "Transport")
    panel = FinancePanel(ledger)

    # Select a specific category then revert to all
    idx = panel._cat_filter_combo.findData("Groceries")
    panel._cat_filter_combo.setCurrentIndex(idx)
    panel._cat_filter_combo.setCurrentIndex(0)  # back to "All categories"

    assert panel._table.rowCount() == 2


# ---------------------------------------------------------------------------
# Slice 16 — category filter combo stays consistent after _refresh
# ---------------------------------------------------------------------------


def test_manage_categories_refresh_reflects_new_category(qapp, ledger):
    panel = FinancePanel(ledger)
    assert panel._cat_filter_combo.count() == 1  # only "All categories"

    ledger.add_category("Housing")
    panel._refresh()

    items = [panel._cat_filter_combo.itemText(i) for i in range(panel._cat_filter_combo.count())]
    assert "Housing" in items


def test_manage_categories_refresh_reflects_deleted_category(qapp, ledger):
    cat_id = ledger.add_category("Housing")
    panel = FinancePanel(ledger)
    items = [panel._cat_filter_combo.itemText(i) for i in range(panel._cat_filter_combo.count())]
    assert "Housing" in items

    ledger.delete_category(cat_id)
    panel._refresh()

    items = [panel._cat_filter_combo.itemText(i) for i in range(panel._cat_filter_combo.count())]
    assert "Housing" not in items


# ---------------------------------------------------------------------------
# Slice 17 — income (positive amounts) display correctly
# ---------------------------------------------------------------------------


def test_positive_amount_displays_correctly(qapp, ledger):
    ledger.add_transaction("2026-05-01", 1500.00, "Salary", "Income")
    panel = FinancePanel(ledger)
    assert "1500.00" in panel._table.item(0, _COL_AMOUNT).text()


def test_category_totals_show_income_positive(panel, ledger):
    ledger.add_transaction("2026-05-01", 1000.00, "Salary", "Income")
    panel._refresh()
    items = [panel._totals_list.item(i).text() for i in range(panel._totals_list.count())]
    assert any("+1000.00" in it for it in items)


# ---------------------------------------------------------------------------
# Slice 18 — amount column is right-aligned
# ---------------------------------------------------------------------------


def test_amount_column_is_right_aligned(qapp, ledger):
    from PyQt6.QtCore import Qt
    ledger.add_transaction("2026-05-01", -5.00, "Coffee", "Dining")
    panel = FinancePanel(ledger)
    item = panel._table.item(0, _COL_AMOUNT)
    assert item.textAlignment() & int(Qt.AlignmentFlag.AlignRight)


# ---------------------------------------------------------------------------
# Slice 19 — table has 5 columns (4 visible + 1 hidden id)
# ---------------------------------------------------------------------------


def test_table_has_five_columns(panel):
    assert panel._table.columnCount() == 5


# ---------------------------------------------------------------------------
# Slice 20 — period filter "This month" excludes old transactions
# ---------------------------------------------------------------------------


def test_period_this_month_excludes_old_transactions(qapp, ledger):
    """Transactions from years ago must not appear under 'This month'."""
    ledger.add_transaction("2020-01-15", -100.00, "Old expense", "A")
    panel = FinancePanel(ledger)
    panel._period_combo.setCurrentText(_PERIOD_THIS_MONTH)
    descriptions = [
        panel._table.item(r, _COL_DESCRIPTION).text()
        for r in range(panel._table.rowCount())
    ]
    assert "Old expense" not in descriptions
