"""
EmailStore — SQLite-backed cache for IMAP email data.

Credentials are read from ~/.cbosa/secrets.toml under [imap]:
    host     = "imap.example.com"
    port     = 993
    username = "user@example.com"
    password = "secret"

All IMAP network I/O is done in a QThread worker (ImapSyncWorker).
EmailStore itself is thread-safe for reads; writes from the worker
are protected by the SQLite WAL journal mode.
"""
from __future__ import annotations

import imaplib
import email as _email_mod
import email.header
import sqlite3
from pathlib import Path
from typing import Callable

try:
    import toml
except ImportError:
    toml = None  # type: ignore[assignment]

from PyQt6.QtCore import QThread, pyqtSignal

_SECRETS_PATH = Path.home() / ".cbosa" / "secrets.toml"


class EmailStoreError(Exception):
    """Base error for EmailStore."""


class CredentialsMissingError(EmailStoreError):
    """Raised when ~/.cbosa/secrets.toml is missing or has no [imap] section."""


class EmailStore:
    """
    Local SQLite cache for emails fetched via IMAP.

    Usage:
        store = EmailStore(":memory:")             # for tests
        store = EmailStore(Path("data/email.db"))  # for production

    Check store.has_credentials before syncing.
    Call store.sync(on_done) to fetch new emails in a background thread.
    """

    def __init__(self, db_path: "str | Path") -> None:
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()
        self._worker: ImapSyncWorker | None = None

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS emails (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                uid     TEXT    NOT NULL UNIQUE,
                subject TEXT    NOT NULL DEFAULT '',
                sender  TEXT    NOT NULL DEFAULT '',
                date    TEXT    NOT NULL DEFAULT '',
                body    TEXT    NOT NULL DEFAULT ''
            );
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Credentials
    # ------------------------------------------------------------------

    @property
    def has_credentials(self) -> bool:
        """Return True if ~/.cbosa/secrets.toml exists and has a valid [imap] section."""
        try:
            creds = self._load_credentials()
            return bool(creds.get("host") and creds.get("username"))
        except CredentialsMissingError:
            return False

    def _load_credentials(self) -> dict:
        """Load IMAP credentials from ~/.cbosa/secrets.toml."""
        if toml is None:
            raise CredentialsMissingError("toml package not available")
        if not _SECRETS_PATH.exists():
            raise CredentialsMissingError(
                f"secrets.toml not found at {_SECRETS_PATH}"
            )
        try:
            data = toml.load(str(_SECRETS_PATH))
        except Exception as exc:
            raise CredentialsMissingError(f"Could not parse secrets.toml: {exc}") from exc
        if "imap" not in data:
            raise CredentialsMissingError("secrets.toml has no [imap] section")
        return data["imap"]

    # ------------------------------------------------------------------
    # Email cache CRUD
    # ------------------------------------------------------------------

    def insert_email(
        self,
        uid: str,
        subject: str,
        sender: str,
        date: str,
        body: str,
    ) -> int:
        """Insert or replace an email in the cache. Returns the row id."""
        cur = self._conn.execute(
            "INSERT OR REPLACE INTO emails (uid, subject, sender, date, body) "
            "VALUES (?, ?, ?, ?, ?)",
            (uid, subject, sender, date, body),
        )
        self._conn.commit()
        return cur.lastrowid

    def list_emails(
        self,
        *,
        keyword: str | None = None,
        sender: str | None = None,
        date: str | None = None,
    ) -> list[dict]:
        """
        Return cached emails ordered by date DESC, id DESC.

        keyword  case-insensitive match on subject or body
        sender   case-insensitive match on sender field
        date     ISO date string — only emails on or after this date
        """
        sql = "SELECT id, uid, subject, sender, date, body FROM emails WHERE 1=1"
        params: list = []
        if keyword:
            sql += " AND (subject LIKE ? OR body LIKE ?)"
            like = f"%{keyword}%"
            params += [like, like]
        if sender:
            sql += " AND sender LIKE ?"
            params.append(f"%{sender}%")
        if date:
            sql += " AND date >= ?"
            params.append(date)
        sql += " ORDER BY date DESC, id DESC"
        rows = self._conn.execute(sql, params).fetchall()
        return [_row_to_dict(r) for r in rows]

    def get_email(self, email_id: int) -> dict | None:
        """Return a single email dict by id, or None if not found."""
        row = self._conn.execute(
            "SELECT id, uid, subject, sender, date, body FROM emails WHERE id = ?",
            (email_id,),
        ).fetchone()
        return _row_to_dict(row) if row else None

    def count(self) -> int:
        """Return total number of cached emails."""
        return self._conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]

    def clear(self) -> None:
        """Delete all cached emails from the local store."""
        self._conn.execute("DELETE FROM emails")
        self._conn.commit()

    # ------------------------------------------------------------------
    # Background IMAP sync
    # ------------------------------------------------------------------

    def sync(self, on_done: "Callable[[int, str], None]") -> None:
        """
        Fetch recent emails from IMAP in a background QThread.

        on_done(count, error_message) is called when done.
        count is the number of new emails fetched; error_message is "" on success.
        """
        try:
            creds = self._load_credentials()
        except CredentialsMissingError as exc:
            on_done(0, str(exc))
            return

        self._worker = ImapSyncWorker(self, creds)
        self._worker.finished.connect(on_done)
        self._worker.start()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._conn.close()


# ---------------------------------------------------------------------------
# IMAP background worker
# ---------------------------------------------------------------------------

class ImapSyncWorker(QThread):
    """Fetches emails from IMAP in a background thread."""

    # emits (count_fetched: int, error_message: str)
    finished = pyqtSignal(int, str)

    def __init__(self, store: EmailStore, creds: dict, parent=None) -> None:
        super().__init__(parent)
        self._store = store
        self._creds = creds

    def run(self) -> None:
        try:
            count = _fetch_imap(self._store, self._creds)
            self.finished.emit(count, "")
        except Exception as exc:  # noqa: BLE001
            self.finished.emit(0, str(exc))


def _fetch_imap(store: EmailStore, creds: dict, max_emails: int = 50) -> int:
    """Connect to IMAP, fetch recent emails, insert into store. Returns count."""
    host = creds["host"]
    port = int(creds.get("port", 993))
    username = creds["username"]
    password = creds["password"]

    with imaplib.IMAP4_SSL(host, port) as imap:
        imap.login(username, password)
        imap.select("INBOX", readonly=False)
        _, data = imap.search(None, "UNSEEN")
        uids = data[0].split()
        recent = uids[-max_emails:] if len(uids) > max_emails else uids
        count = 0
        for uid_bytes in reversed(recent):
            uid = uid_bytes.decode()
            _, msg_data = imap.fetch(uid_bytes, "(RFC822)")
            raw = msg_data[0][1]
            msg = _email_mod.message_from_bytes(raw)
            subject = _decode_header(msg.get("Subject", ""))
            sender = _decode_header(msg.get("From", ""))
            date_str = msg.get("Date", "")[:10]
            body = _extract_body(msg)
            store.insert_email(uid, subject, sender, date_str, body)
            imap.store(uid_bytes, "+FLAGS", "\\Seen")
            count += 1
        return count


def _decode_header(value: str) -> str:
    """Decode an RFC 2047 encoded email header."""
    parts = email.header.decode_header(value)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded)


def _extract_body(msg) -> str:
    """Extract plain-text body from an email.Message."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(
                        part.get_content_charset() or "utf-8", errors="replace"
                    )
        return ""
    payload = msg.get_payload(decode=True)
    if payload:
        return payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
    return ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "uid": row["uid"],
        "subject": row["subject"],
        "sender": row["sender"],
        "date": row["date"],
        "body": row["body"],
    }
