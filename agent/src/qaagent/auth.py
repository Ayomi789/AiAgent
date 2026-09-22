"""User accounts for the hosted dashboard.

Local single-user mode needs only the bootstrap token; a hosted multi-user
deployment needs real accounts. This module provides the smallest correct
version of that:

- User store on SQLite (same DB-file pattern as reports/live state), or on
  free Postgres (Neon/Supabase) when DATABASE_URL is set - so accounts
  survive redeploys on hosts with ephemeral disks
- Password hashing with Werkzeug's scrypt (already a dependency)
- Per-IP sliding-window rate limiting for login/signup (brute-force defense)
- CSRF tokens for all state-changing forms
- Server-side sessions via a signed Flask cookie

The bootstrap dashboard token still works: it is the admin/API mechanism
(CI, scripts, break-glass access). Accounts are the human front door.
"""

from __future__ import annotations

import os
import secrets
import sqlite3
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

from flask import session
from werkzeug.security import check_password_hash, generate_password_hash


def _pg_url() -> str:
    """Postgres connection string, or "" for the SQLite default."""
    return os.environ.get("DATABASE_URL", "").strip()


def _pg_conn():
    """One Postgres connection (autocommit; short-lived, like _conn)."""
    import psycopg
    from psycopg.rows import dict_row

    conn = psycopg.connect(_pg_url(), row_factory=dict_row)
    conn.autocommit = True
    return conn


_PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    created_at TEXT NOT NULL DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
    suspended INTEGER NOT NULL DEFAULT 0,
    suspended_at TEXT,
    suspend_reason TEXT
);
CREATE TABLE IF NOT EXISTS invites (
    code TEXT PRIMARY KEY,
    created_by INTEGER,
    used_by INTEGER,
    used_at TEXT,
    created_at TEXT NOT NULL DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
);
CREATE TABLE IF NOT EXISTS terms_acceptances (
    user_id INTEGER PRIMARY KEY,
    version TEXT NOT NULL,
    accepted_at TEXT NOT NULL DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
    ip TEXT
);
"""

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    suspended INTEGER NOT NULL DEFAULT 0,
    suspended_at TEXT,
    suspend_reason TEXT
);

-- Pre-suspension user stores: add the columns if an older db lacks them.
ALTER TABLE users ADD COLUMN suspended INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN suspended_at TEXT;
ALTER TABLE users ADD COLUMN suspend_reason TEXT;
"""


class UserStore:
    """User accounts on SQLite (default) or Postgres (DATABASE_URL set)."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._conn() as conn:
            self._migrate(conn)

    @staticmethod
    def _pg() -> bool:
        # Read dynamically (not at import) so tests and deploys can flip
        # backends without a restart of the interpreter.
        return bool(_pg_url())

    def _conn(self):
        if self._pg():
            return _pg_conn()
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _execute(self, conn, sql: str, params: tuple = ()):
        """`?` placeholders work on SQLite; Postgres wants `%s`."""
        return conn.execute(self._q(sql), params)

    def _q(self, sql: str) -> str:
        return sql.replace("?", "%s") if self._pg() else sql

    def _migrate(self, conn) -> None:
        """Create the schema, then tolerate pre-existing older databases:
        every ALTER fails silently if the column already exists."""
        if self._pg():
            for stmt in (s for s in _PG_SCHEMA.split(";") if s.strip()):
                conn.execute(stmt)
            return
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS invites (
                code TEXT PRIMARY KEY,
                created_by INTEGER,
                used_by INTEGER,
                used_at TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS terms_acceptances (
                user_id INTEGER PRIMARY KEY,
                version TEXT NOT NULL,
                accepted_at TEXT NOT NULL DEFAULT (datetime('now')),
                ip TEXT
            );
        """)
        for stmt in (
            "ALTER TABLE users ADD COLUMN suspended INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN suspended_at TEXT",
            "ALTER TABLE users ADD COLUMN suspend_reason TEXT",
        ):
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass  # column already exists

    def _now(self) -> str:
        """Timestamp expression matching the SQLite text format on both backends."""
        if self._pg():
            return "to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')"
        return "datetime('now')"

    def create_user(self, email: str, password: str, role: str = "user") -> int | None:
        """Create a user; returns the id, or None if the email is taken."""
        email = email.strip().lower()
        if not email or "@" not in email:
            raise ValueError("a valid email is required")
        if len(password) < 8:
            raise ValueError("password must be at least 8 characters")
        with self._lock, self._conn() as conn:
            existing = self._execute(
                conn, "SELECT id FROM users WHERE email = ?", (email,)
            ).fetchone()
            if existing:
                return None
            if self._pg():
                row = self._execute(
                    conn,
                    "INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?) "
                    "RETURNING id",
                    (email, generate_password_hash(password), role),
                ).fetchone()
                return int(row["id"])
            cur = self._execute(
                conn,
                "INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?)",
                (email, generate_password_hash(password), role),
            )
            return int(cur.lastrowid)

    def verify(self, email: str, password: str):
        """Return the user row if the credentials are valid and the account
        is not suspended, else None."""
        email = email.strip().lower()
        with self._lock, self._conn() as conn:
            row = self._execute(
                conn, "SELECT * FROM users WHERE email = ?", (email,)
            ).fetchone()
        if row is None or row["suspended"]:
            return None
        if check_password_hash(row["password_hash"], password):
            return row
        return None

    def get(self, user_id: int):
        with self._lock, self._conn() as conn:
            return self._execute(
                conn,
                "SELECT id, email, role, created_at, suspended, suspended_at, "
                "suspend_reason FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()

    # --- Terms acceptance (Phase 3: legal layer) -----------------------------

    def accept_terms(self, user_id: int, version: str, ip: str = "") -> None:
        """Record (or re-record) the user's acceptance of the given version."""
        with self._lock, self._conn() as conn:
            self._execute(
                conn,
                f"INSERT INTO terms_acceptances (user_id, version, accepted_at, ip) "
                f"VALUES (?, ?, {self._now()}, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET version = excluded.version, "
                "accepted_at = excluded.accepted_at, ip = excluded.ip",
                (user_id, version, ip),
            )

    def terms_accepted_version(self, user_id: int) -> str | None:
        """The terms version this user last accepted, or None."""
        with self._lock, self._conn() as conn:
            row = self._execute(
                conn,
                "SELECT version FROM terms_acceptances WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return row["version"] if row else None

    def count(self) -> int:
        with self._lock, self._conn() as conn:
            return int(self._execute(conn, "SELECT COUNT(*) FROM users").fetchone()[0])

    # --- Moderation (Phase 3: admin console) ----------------------------------

    def list_users(self) -> list:
        """Every account, for the admin console (small deployments: fine)."""
        with self._lock, self._conn() as conn:
            return self._execute(
                conn,
                "SELECT id, email, role, created_at, suspended, suspended_at, "
                "suspend_reason FROM users ORDER BY id",
            ).fetchall()

    def set_suspended(self, user_id: int, suspended: bool, reason: str = "") -> bool:
        """Suspend or reinstate an account. Returns True if a row changed."""
        with self._lock, self._conn() as conn:
            cur = self._execute(
                conn,
                f"UPDATE users SET suspended = ?, suspended_at = CASE WHEN ? "
                f"THEN {self._now()} ELSE NULL END, suspend_reason = ? WHERE id = ?",
                (1 if suspended else 0, 1 if suspended else 0,
                 reason if suspended else None, user_id),
            )
            return cur.rowcount == 1

    # --- Invite codes (Phase 3: closed signup) -------------------------------

    def create_invite(self, created_by: int | None = None) -> str:
        """Mint a single-use signup code (URL-safe, unguessable)."""
        code = secrets.token_urlsafe(12)
        with self._lock, self._conn() as conn:
            self._execute(
                conn,
                "INSERT INTO invites (code, created_by) VALUES (?, ?)",
                (code, created_by),
            )
        return code

    def use_invite(self, code: str) -> bool:
        """Consume a code atomically; True only if it existed and was unused."""
        if not code:
            return False
        with self._lock, self._conn() as conn:
            cur = self._execute(
                conn,
                f"UPDATE invites SET used_by = -1, used_at = {self._now()} "
                "WHERE code = ? AND used_by IS NULL",
                (code.strip(),),
            )
            return cur.rowcount == 1

    def list_invites(self) -> list:
        with self._lock, self._conn() as conn:
            return self._execute(
                conn,
                "SELECT code, created_by, used_by, used_at, created_at "
                "FROM invites ORDER BY created_at DESC LIMIT 100",
            ).fetchall()


# --- Signup policy (Phase 3) ---------------------------------------------------

def signup_policy(user_count: int) -> str:
    """Who may create an account on this instance right now.

    Returns one of:
    - "bootstrap" — no users yet: signup requires the dashboard token, so only
      the operator (who printed the tokened URL) can claim the admin account.
      This holds even with open signup configured — it closes the window where
      a stranger claims admin on a fresh instance before the operator does.
    - "invite"    — default: signup requires a single-use admin-minted code.
    - "open"      — SENTINEL_OPEN_SIGNUP=1: anyone may sign up (private or
      firewalled deployments only).
    """
    open_env = os.environ.get("SENTINEL_OPEN_SIGNUP", "").strip().lower() in (
        "1", "true", "yes",
    )
    if user_count == 0:
        return "bootstrap"
    return "open" if open_env else "invite"


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
