"""
Tests for TimerStore — group/category management and session logging.
All tests use a temporary SQLite database.
Behavior verified through public interfaces only.
"""
import pytest
from cbosa.core.timer_store import TimerStore


@pytest.fixture
def store(tmp_path):
    return TimerStore(tmp_path / "timer.db")


# ---------------------------------------------------------------------------
# Groups — tracer bullet
# ---------------------------------------------------------------------------

def test_add_group_returns_id(store):
    """Adding a group returns a positive integer id."""
    gid = store.add_group("Academics")
    assert isinstance(gid, int) and gid > 0


def test_list_groups_returns_added_group(store):
    """A group added to the store appears in list_groups."""
    store.add_group("Work")
    names = [g["name"] for g in store.list_groups()]
    assert "Work" in names


def test_list_groups_is_empty_initially(store):
    """A fresh store has no groups."""
    assert store.list_groups() == []


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

def test_add_category_returns_id(store):
    """Adding a category under a group returns a positive integer id."""
    gid = store.add_group("Academics")
    cid = store.add_category(gid, "CS101")
    assert isinstance(cid, int) and cid > 0


def test_list_categories_scoped_to_group(store):
    """list_categories only returns categories belonging to the given group."""
    g1 = store.add_group("Academics")
    g2 = store.add_group("Work")
    store.add_category(g1, "CS101")
    store.add_category(g2, "Project X")
    names = [c["name"] for c in store.list_categories(g1)]
    assert "CS101" in names
    assert "Project X" not in names


def test_add_category_invalid_group_raises(store):
    """Adding a category to a non-existent group raises GroupNotFoundError."""
    from cbosa.core.timer_store import GroupNotFoundError
    with pytest.raises(GroupNotFoundError):
        store.add_category(999, "Ghost")


# ---------------------------------------------------------------------------
# Sessions — log and list
# ---------------------------------------------------------------------------

def test_log_session_returns_id(store):
    """Logging a session returns a positive integer id."""
    gid = store.add_group("Work")
    cid = store.add_category(gid, "Deep Work")
    sid = store.log_session(cid, "2026-05-25T10:00:00", "2026-05-25T10:25:00")
    assert isinstance(sid, int) and sid > 0


def test_list_sessions_returns_logged_session(store):
    """A logged session appears in list_sessions with group/category names."""
    gid = store.add_group("Academics")
    cid = store.add_category(gid, "CS101")
    store.log_session(cid, "2026-05-25T09:00:00", "2026-05-25T09:50:00")
    sessions = store.list_sessions()
    assert len(sessions) == 1
    s = sessions[0]
    assert s["group_name"] == "Academics"
    assert s["category_name"] == "CS101"
    assert s["duration_seconds"] == 50 * 60


def test_list_sessions_filters_by_date_range(store):
    """list_sessions with start_date/end_date excludes sessions outside the range."""
    gid = store.add_group("Work")
    cid = store.add_category(gid, "Research")
    store.log_session(cid, "2026-05-01T10:00:00", "2026-05-01T10:30:00")
    store.log_session(cid, "2026-05-20T10:00:00", "2026-05-20T10:30:00")
    results = store.list_sessions(start_date="2026-05-15", end_date="2026-05-31")
    assert len(results) == 1
    assert results[0]["start_time"].startswith("2026-05-20")


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------

def test_category_totals_sums_duration_correctly(store):
    """category_totals returns the correct total seconds per category."""
    gid = store.add_group("Academics")
    cid = store.add_category(gid, "CS101")
    store.log_session(cid, "2026-05-25T10:00:00", "2026-05-25T10:25:00")  # 25 min
    store.log_session(cid, "2026-05-25T14:00:00", "2026-05-25T14:50:00")  # 50 min
    totals = store.category_totals()
    assert len(totals) == 1
    assert totals[0]["category_name"] == "CS101"
    assert totals[0]["total_seconds"] == 75 * 60


def test_category_totals_filters_by_date(store):
    """category_totals respects date range filtering."""
    gid = store.add_group("Work")
    cid = store.add_category(gid, "Project X")
    store.log_session(cid, "2026-04-01T10:00:00", "2026-04-01T11:00:00")  # out of range
    store.log_session(cid, "2026-05-25T10:00:00", "2026-05-25T10:30:00")  # in range
    totals = store.category_totals(start_date="2026-05-01")
    assert totals[0]["total_seconds"] == 30 * 60


# ---------------------------------------------------------------------------
# Delete and error handling
# ---------------------------------------------------------------------------

def test_delete_group_removes_it(store):
    """Deleting a group removes it from list_groups."""
    gid = store.add_group("Temp")
    store.delete_group(gid)
    assert all(g["id"] != gid for g in store.list_groups())


def test_delete_group_cascades_to_categories(store):
    """Deleting a group also removes its child categories."""
    gid = store.add_group("Academics")
    store.add_category(gid, "CS101")
    store.delete_group(gid)
    assert store.list_categories(gid) == []


def test_duplicate_group_name_raises(store):
    """Adding a group with a name that already exists raises DuplicateGroupError."""
    from cbosa.core.timer_store import DuplicateGroupError
    store.add_group("Work")
    with pytest.raises(DuplicateGroupError):
        store.add_group("Work")
