"""Deliberately vulnerable demo app — the QA agent's first safe test target.

Run:  python app.py        (serves on http://127.0.0.1:5001)

Every endpoint below contains at least one intentional flaw. The README lists
them all with test payloads. Nothing here should ever be copied into
production code — it exists so the agent has a target it is allowed to break.
"""

from __future__ import annotations

import os
import sqlite3
from hashlib import md5

from flask import Flask, g, redirect, render_template_string, request, session

app = Flask(__name__)

# Intentional flaw: hardcoded secret key shipped in source.
app.secret_key = "vuln-app-dev-secret-please-change"

# Intentional flaw: session cookies readable by JavaScript and sent over HTTP.
app.config.update(
    SESSION_COOKIE_HTTPONLY=False,
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_SAMESITE=None,
)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vuln.db")


def _port() -> int:
    """Resolve the listen port. Uses VULN_PORT (not PORT, which some shells
    set to 0 meaning 'ephemeral') and falls back to 5001."""
    raw = os.environ.get("VULN_PORT", "5001")
    try:
        port = int(raw)
    except ValueError:
        port = 0
    return port if 1024 <= port <= 65535 else 5001


PORT = _port()


def page(title: str, body: str) -> str:
    """Wrap body in the shared page chrome. Body is intentionally NOT escaped."""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    body {{ font-family: sans-serif; max-width: 720px; margin: 2rem auto; padding: 0 1rem; }}
    nav {{ border-bottom: 1px solid #ccc; padding-bottom: .5rem; margin-bottom: 1.5rem; }}
    nav a {{ margin-right: 1rem; }}
    input, button {{ padding: .4rem .6rem; margin: .2rem 0; }}
    table {{ border-collapse: collapse; }}
    td, th {{ border: 1px solid #ccc; padding: .3rem .6rem; font-size: .9rem; }}
    .err {{ color: #a11; }}
  </style>
</head>
<body>
  <nav>
    <a href="/">Home</a>
    <a href="/search">Search</a>
    <a href="/login">Login</a>
    <a href="/admin">Admin</a>
    <a href="/debug">Debug</a>
  </nav>
  {body}
</body>
</html>"""


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc: BaseException | None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def seed() -> None:
    """Create schema and demo rows. Resets on every start — fine for a toy."""
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        DROP TABLE IF EXISTS users;
        DROP TABLE IF EXISTS notes;
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            password_hash TEXT,
            role TEXT,
            email TEXT
        );
        CREATE TABLE notes (
            id INTEGER PRIMARY KEY,
            title TEXT,
            body TEXT
        );
        """
    )
    # Intentional flaw: unsalted MD5 password hashes.
    db.execute(
        "INSERT INTO users (username, password_hash, role, email) VALUES (?, ?, ?, ?)",
        ("alice", md5(b"alice123").hexdigest(), "user", "alice@example.test"),
    )
    db.execute(
        "INSERT INTO users (username, password_hash, role, email) VALUES (?, ?, ?, ?)",
        ("admin", md5(b"admin123").hexdigest(), "admin", "admin@example.test"),
    )
    notes = [
        ("Roadmap", "Build the QA agent, fix the search page, ship."),
        ("Passwords", "Remember: never store plaintext. See /admin for the current state."),
        ("Meeting", "Quarterly review moved to Thursday."),
    ]
    db.executemany("INSERT INTO notes (title, body) VALUES (?, ?)", notes)
    db.commit()
    db.close()


@app.get("/")
def home() -> str:
    body = (
        "<h1>Welcome to the vulnerable demo app</h1>"
        "<p>Every page here has at least one intentional flaw. Try the nav links. "
        "The README lists all the bugs and test payloads.</p>"
        "<ul>"
        "<li><a href='/search'>Search</a> — echoes input (XSS / SSTI) and queries "
        "with string-built SQL (injection)</li>"
        "<li><a href='/login'>Login</a> — SQL injection in the auth query</li>"
        "<li><a href='/profile?id=1'>Profile</a> — no auth required (IDOR)</li>"
        "<li><a href='/admin'>Admin</a> — no auth required (broken access control)</li>"
        "<li><a href='/debug'>Debug</a> — dumps env + secret key (info disclosure)</li>"
        "<li><a href='/redirect?next=https://example.com'>Redirect</a> — open redirect</li>"
        "</ul>"
    )
    return page("Vulnerable demo", body)


@app.route("/login", methods=["GET", "POST"])
def login() -> str:
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        # Intentional flaw: string-built SQL -> login SQL injection.
        # e.g. username `admin' -- ` with any password logs in as admin.
        db = get_db()
        row = db.execute(
            f"SELECT * FROM users WHERE username = '{username}' "
            f"AND password_hash = '{md5(password.encode()).hexdigest()}'"
        ).fetchone()
        if row:
            session["user_id"] = row["id"]
            session["username"] = row["username"]
            session["role"] = row["role"]
            return redirect("/dashboard")
        # Intentional flaw: reflected error message -> XSS.
        return page(
            "Login",
            f"<p class='err'>Invalid credentials for {username}.</p>"
            f"<p><a href='/login'>Try again</a></p>",
        )
    return page(
        "Login",
        "<h2>Log in</h2>"
        "<form method='post'>"
        "<label>Username <input name='username' autocomplete='username'></label><br>"
        "<label>Password <input type='password' name='password' autocomplete='current-password'></label><br>"
        "<button type='submit'>Log in</button>"
        "</form>"
        "<p>Demo users: <code>alice/alice123</code>, <code>admin/admin123</code></p>",
    )


@app.get("/logout")
def logout() -> str:
    session.clear()
    return redirect("/")


@app.get("/dashboard")
def dashboard() -> str:
    username = session.get("username")
    if not username:
        return redirect("/login")
    return page(
        "Dashboard",
        f"<h2>Welcome, {username}!</h2>"
        f"<p>You are logged in as <b>{session.get('role')}</b>.</p>"
        f"<p><a href='/logout'>Log out</a></p>",
    )


@app.get("/search")
def search() -> str:
    q = request.args.get("q", "")
    if not q:
        return page(
            "Search",
            "<h2>Search the notes</h2>"
            "<form method='get'><input name='q' placeholder='e.g. meeting'>"
            "<button type='submit'>Search</button></form>",
        )
    # Intentional flaws:
    # 1. q is echoed raw into the HTML -> reflected XSS (and, because the page
    #    goes through Jinja, `{{ ... }}` input is evaluated -> SSTI).
    # 2. String-built SQL -> injection (e.g. q = ' OR 1=1 -- ).
    db = get_db()
    rows = db.execute(
        f"SELECT title, body FROM notes "
        f"WHERE title LIKE '%{q}%' OR body LIKE '%{q}%'"
    ).fetchall()
    results = "".join(
        f"<li><b>{r['title']}</b>: {r['body']}</li>" for r in rows
    ) or "<li>no matches</li>"
    body = (
        f"<h2>Results for '{q}'</h2>"
        f"<ul>{results}</ul>"
        "<form method='get'><input name='q' placeholder='search again'>"
        "<button type='submit'>Search</button></form>"
    )
    return render_template_string(page("Search", body))


@app.get("/profile")
def profile() -> str:
    uid = request.args.get("id", "")
    if not uid:
        return redirect("/")
    # Intentional flaws: no auth check (IDOR) and string-built SQL.
    # e.g. /profile?id=1 OR 1=1 returns every user.
    db = get_db()
    rows = db.execute(
        f"SELECT id, username, email, role FROM users WHERE id = {uid}"
    ).fetchall()
    if not rows:
        return page("Profile", "<p>User not found.</p>")
    cards = "".join(
        f"<li><b>{r['username']}</b> — {r['email']} ({r['role']})</li>" for r in rows
    )
    return page("Profile", f"<h2>User profile</h2><ul>{cards}</ul>")


@app.get("/admin")
def admin() -> str:
    # Intentional flaw: broken access control — no authentication required.
    db = get_db()
    rows = db.execute(
        "SELECT id, username, password_hash, role FROM users"
    ).fetchall()
    table = "".join(
        f"<tr><td>{r['id']}</td><td>{r['username']}</td>"
        f"<td><code>{r['password_hash']}</code></td><td>{r['role']}</td></tr>"
        for r in rows
    )
    return page(
        "Admin",
        "<h2>Admin panel</h2>"
        "<p class='err'>No authentication required — intentional flaw.</p>"
        f"<table><tr><th>id</th><th>username</th><th>password hash (md5)</th>"
        f"<th>role</th></tr>{table}</table>",
    )


@app.get("/debug")
def debug() -> str:
    # Intentional flaw: information disclosure — dumps environment and config.
    env = "".join(
        f"<tr><td>{k}</td><td>{v}</td></tr>"
        for k, v in sorted(os.environ.items())[:40]
    )
    return page(
        "Debug",
        f"<h2>Environment</h2><table>{env}</table>"
        f"<h2>Secret key</h2><code>{app.secret_key}</code>",
    )


@app.get("/redirect")
def redirect_target() -> str:
    # Intentional flaw: open redirect — `next` is not validated.
    nxt = request.args.get("next", "/")
    return redirect(nxt)


@app.get("/favicon.ico")
def favicon() -> tuple[str, int]:
    # Silence the browser's 404 console noise for the missing favicon.
    return "", 204


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    seed()
    print(f"Vulnerable demo app on http://127.0.0.1:{PORT} — flaws are intentional.")
    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)
