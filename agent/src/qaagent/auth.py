"""User accounts for the hosted dashboard.

Local single-user mode needs only the bootstrap token; a hosted multi-user
deployment needs real accounts. This module provides the smallest correct
version of that:

- SQLite user store (same DB-file pattern as reports/live state)
- Password hashing with Werkzeug's scrypt (already a dependency)
- Per-IP sliding-window rate limiting for login/signup (brute-force defense)
- CSRF tokens for all state-changing forms
- Server-side sessions via a signed Flask cookie

The bootstrap dashboard token still works: it is the admin/API mechanism
(CI, scripts, break-glass access). Accounts are the human front door.
"""

from __future__ import annotations

import secrets
import sqlite3
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

from flask import session
from werkzeug.security import check_password_hash, generate_password_hash

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class UserStore:
    """SQLite-backed user accounts."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def create_user(self, email: str, password: str, role: str = "user") -> int | None:
        """Create a user; returns the id, or None if the email is taken."""
        email = email.strip().lower()
        if not email or "@" not in email:
            raise ValueError("a valid email is required")
        if len(password) < 8:
            raise ValueError("password must be at least 8 characters")
        with self._lock, self._conn() as conn:
            existing = conn.execute(
                "SELECT id FROM users WHERE email = ?", (email,)
            ).fetchone()
            if existing:
                return None
            cur = conn.execute(
                "INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?)",
                (email, generate_password_hash(password), role),
            )
            return int(cur.lastrowid)

    def verify(self, email: str, password: str) -> sqlite3.Row | None:
        """Return the user row if the credentials are valid, else None."""
        email = email.strip().lower()
        with self._lock, self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE email = ?", (email,)
            ).fetchone()
        if row and check_password_hash(row["password_hash"], password):
            return row
        return None

    def get(self, user_id: int) -> sqlite3.Row | None:
        with self._lock, self._conn() as conn:
            return conn.execute(
                "SELECT id, email, role, created_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()

    def count(self) -> int:
        with self._lock, self._conn() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])


# --- Rate limiting (per-IP sliding window) -----------------------------------

class RateLimiter:
    """Simple in-process sliding-window limiter for login/signup."""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 300) -> None:
        self.max = max_attempts
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> bool:
        """True if the action is allowed under the limit."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            return len(hits) < self.max

    def hit(self, key: str) -> None:
        """Record an attempt (call on failure)."""
        with self._lock:
            self._hits[key].append(time.monotonic())

    def reset(self, key: str) -> None:
        """Clear the window (call on success)."""
        with self._lock:
            self._hits.pop(key, None)


# --- CSRF ---------------------------------------------------------------------

def csrf_token() -> str:
    """Per-session CSRF token (created lazily)."""
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(24)
    return session["_csrf"]


def csrf_valid(form: dict) -> bool:
    """Constant-time comparison of the submitted token against the session's."""
    sent = form.get("csrf_token", "")
    good = session.get("_csrf", "")
    return bool(good) and secrets.compare_digest(sent, good)


# --- Sessions -------------------------------------------------------------------

def login_user(user_id: int) -> None:
    session.clear()
    session["uid"] = user_id


def logout_user() -> None:
    session.clear()


def current_user(store: UserStore):
    """The logged-in user row, or None."""
    uid = session.get("uid")
    if uid is None:
        return None
    return store.get(int(uid))
