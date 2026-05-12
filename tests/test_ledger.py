"""
Tests for the Ledger finance module.
All tests use in-memory SQLite (db_path=":memory:").
Behavior verified through public interfaces only.
"""
import pytest
from cbosa.core.ledger import (
    Ledger,
    LedgerError,
    CategoryNotFoundError,
    TransactionNotFoundError,
    DuplicateCategoryError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ledger():
    db = Ledger(":memory:")
    yield db
    db.close()


# ---------------------------------------------------------------------------
# Tracer bullet — add and retrieve a transaction
# ---------------------------------------------------------------------------

def test_add_transaction_and_list(ledger):
    """Adding a transaction makes it appear in list_transactions."""
    tx_id = ledger.add_transaction("2026-05-01", -42.50, "Supermarket", "Groceries")
    txs = ledger.list_transactions()
    assert len(txs) == 1
    assert txs[0]["id"] == tx_id
    assert txs[0]["date"] == "2026-05-01"
    assert txs[0]["amount"] == -42.50
    assert txs[0]["description"] == "Supermarket"
    assert txs[0]["category"] == "Groceries"


# ---------------------------------------------------------------------------
# Transactions — edit
# ---------------------------------------------------------------------------

def test_edit_transaction_updates_fields(ledger):
    """Editing a transaction replaces all its fields."""
    tx_id = ledger.add_transaction("2026-05-01", -10.00, "Coffee", "Dining")
    ledger.edit_transaction(tx_id, date="2026-05-02", amount=-12.50,
                            description="Lunch", category="Food")
    tx = ledger.get_transaction(tx_id)
    assert tx["date"] == "2026-05-02"
    assert tx["amount"] == -12.50
    assert tx["description"] == "Lunch"
    assert tx["category"] == "Food"


def test_edit_nonexistent_transaction_raises(ledger):
    """Editing a transaction that doesn't exist raises TransactionNotFoundError."""
    with pytest.raises(TransactionNotFoundError):
        ledger.edit_transaction(999, date="2026-01-01", amount=0.0,
                                description="x", category="y")


# ---------------------------------------------------------------------------
# Transactions — delete
# ---------------------------------------------------------------------------

def test_delete_transaction_removes_it(ledger):
    """Deleting a transaction removes it from list_transactions."""
    tx_id = ledger.add_transaction("2026-05-01", -5.00, "Bus fare", "Transport")
    ledger.delete_transaction(tx_id)
    assert ledger.list_transactions() == []


def test_delete_nonexistent_transaction_raises(ledger):
    """Deleting a transaction that doesn't exist raises TransactionNotFoundError."""
    with pytest.raises(TransactionNotFoundError):
        ledger.delete_transaction(999)


# ---------------------------------------------------------------------------
# Transactions — date validation
# ---------------------------------------------------------------------------

def test_add_transaction_invalid_date_raises(ledger):
    """Adding a transaction with a malformed date raises LedgerError."""
    with pytest.raises(LedgerError):
        ledger.add_transaction("01-05-2026", -1.00, "Bad date", "X")


def test_add_transaction_bad_month_raises(ledger):
    """Adding a transaction with month > 12 raises LedgerError."""
    with pytest.raises(LedgerError):
        ledger.add_transaction("2026-13-01", -1.00, "Bad month", "X")


# ---------------------------------------------------------------------------
# Transactions — date range filter
# ---------------------------------------------------------------------------

def test_list_transactions_date_range(ledger):
    """list_transactions filters by start_date and end_date inclusively."""
    ledger.add_transaction("2026-04-01", -10.00, "April tx", "A")
    ledger.add_transaction("2026-05-01", -20.00, "May tx", "A")
    ledger.add_transaction("2026-06-01", -30.00, "June tx", "A")

    results = ledger.list_transactions(start_date="2026-05-01", end_date="2026-05-31")
    assert len(results) == 1
    assert results[0]["description"] == "May tx"


def test_list_transactions_category_filter(ledger):
    """list_transactions filters by category."""
    ledger.add_transaction("2026-05-01", -10.00, "Groceries tx", "Groceries")
    ledger.add_transaction("2026-05-02", -5.00, "Bus tx", "Transport")

    results = ledger.list_transactions(category="Transport")
    assert len(results) == 1
    assert results[0]["description"] == "Bus tx"


def test_list_transactions_ordered_most_recent_first(ledger):
    """list_transactions returns newest transactions first."""
    ledger.add_transaction("2026-04-01", -1.00, "Old", "X")
    ledger.add_transaction("2026-05-10", -2.00, "Recent", "X")
    ledger.add_transaction("2026-05-05", -3.00, "Middle", "X")

    results = ledger.list_transactions()
    dates = [tx["date"] for tx in results]
    assert dates == sorted(dates, reverse=True)


# ---------------------------------------------------------------------------
# Categories — add and list
# ---------------------------------------------------------------------------

def test_add_category_and_list(ledger):
    """Adding categories makes them appear in list_categories."""
    ledger.add_category("Groceries")
    ledger.add_category("Transport")
    cats = ledger.list_categories()
    names = [c["name"] for c in cats]
    assert "Groceries" in names
    assert "Transport" in names


def test_add_duplicate_category_raises(ledger):
    """Adding a category with a name that already exists raises DuplicateCategoryError."""
    ledger.add_category("Groceries")
    with pytest.raises(DuplicateCategoryError):
        ledger.add_category("Groceries")


def test_add_empty_category_raises(ledger):
    """Adding a category with an empty name raises LedgerError."""
    with pytest.raises(LedgerError):
        ledger.add_category("   ")


# ---------------------------------------------------------------------------
# Categories — delete
# ---------------------------------------------------------------------------

def test_delete_category_removes_it(ledger):
    """Deleting a category removes it from list_categories."""
    cat_id = ledger.add_category("Dining")
    ledger.delete_category(cat_id)
    names = [c["name"] for c in ledger.list_categories()]
    assert "Dining" not in names


def test_delete_nonexistent_category_raises(ledger):
    """Deleting a category that doesn't exist raises CategoryNotFoundError."""
    with pytest.raises(CategoryNotFoundError):
        ledger.delete_category(9999)


# ---------------------------------------------------------------------------
# Category totals
# ---------------------------------------------------------------------------

def test_category_totals_sums_correctly(ledger):
    """category_totals sums amounts per category correctly."""
    ledger.add_transaction("2026-05-01", -30.00, "Shop", "Groceries")
    ledger.add_transaction("2026-05-02", -20.00, "Shop2", "Groceries")
    ledger.add_transaction("2026-05-03", -15.00, "Bus", "Transport")

    totals = ledger.category_totals()
    assert totals["Groceries"] == -50.00
    assert totals["Transport"] == -15.00


def test_category_totals_date_range(ledger):
    """category_totals respects the date range filter."""
    ledger.add_transaction("2026-04-01", -100.00, "April spend", "Groceries")
    ledger.add_transaction("2026-05-01", -50.00, "May spend", "Groceries")

    totals = ledger.category_totals(start_date="2026-05-01", end_date="2026-05-31")
    assert totals.get("Groceries") == -50.00


def test_category_totals_mixed_sign(ledger):
    """category_totals handles both income (positive) and expenses (negative)."""
    ledger.add_transaction("2026-05-01", 1000.00, "Salary", "Income")
    ledger.add_transaction("2026-05-02", -200.00, "Rent", "Housing")

    totals = ledger.category_totals()
    assert totals["Income"] == 1000.00
    assert totals["Housing"] == -200.00


def test_category_totals_empty_ledger(ledger):
    """category_totals returns an empty dict when no transactions exist."""
    assert ledger.category_totals() == {}
