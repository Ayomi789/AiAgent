"""Dashboard web app: live run progress + final report.

Served by `qaagent dashboard` (default http://127.0.0.1:5050). Reads the live
state file the agent writes during a run and the latest report Markdown.
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, redirect, request, send_file, session

from qaagent.auth import (
    signup_policy,
    RateLimiter,
    UserStore,
    csrf_token,
    csrf_valid,
    current_user,
    login_user,
    logout_user,
)
from qaagent.report.diff import compare_reports, load_report_files

# Single-flight scan state: one agent run at a time, started from the UI.
_scan = {
    "proc": None,
    "config": None,
    "skip_llm": False,
    "started": None,
    "log_path": None,
    "returncode": None,
    "owner_id": None,
    "owner_email": None,
}

_COOKIE = "sentinel_token"

_LOGIN_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sentinel - Sign in</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  :focus-visible {{ outline: 2px solid #4c8dff; outline-offset: 1px; }}
  ::selection {{ background: #234066; color: #e8ebee; }}
  @media (prefers-reduced-motion: reduce) {{
    *, *::before, *::after {{ animation-duration: 0.001ms !important; transition-duration: 0.001ms !important; }}
  }}
  body {{ font-family: "Inter", "Segoe UI", system-ui, sans-serif; background: #0b0d10; color: #e8ebee;
         min-height: 100vh; display: grid; place-items: center; padding: 20px;
         -webkit-font-smoothing: antialiased; }}
  .card {{ width: 100%; max-width: 380px; background: #121417; border: 1px solid #22262c;
          border-radius: 6px; padding: 28px; box-shadow: 0 24px 60px -28px rgba(0,0,0,0.72); }}
  .brand {{ display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }}
  .mark {{ width: 34px; height: 34px; border-radius: 6px; background: #16191d;
          border: 1px solid #2c3138; display: grid; place-items: center; }}
  h1 {{ font-size: 17px; letter-spacing: 0.14em; text-transform: uppercase; font-weight: 650; }}
  .sub {{ color: #98a1ab; font-size: 12.5px; margin: 10px 0 20px; line-height: 1.5; }}
  label {{ display: block; font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase;
          color: #6b747e; font-weight: 600; margin: 12px 0 6px; }}
  input[type=email], input[type=password], input[type=text] {{ width: 100%; height: 38px; background: #0b0d10;
          border: 1px solid #2c3138; border-radius: 5px; color: #e8ebee;
          padding: 0 12px; font-size: 14px; font-family: inherit; }}
  input:hover {{ border-color: #3a414a; }}
  input:focus {{ outline: none; border-color: #4c8dff; background: #0e1013; }}
  input::placeholder {{ color: #4d555e; }}
  button {{ width: 100%; height: 40px; margin-top: 18px; border-radius: 5px; cursor: pointer;
           border: 1px solid #e8ebee; color: #0b0d10; font-weight: 600;
           background: #e8ebee; font-size: 12.5px; letter-spacing: 0.01em;
           font-family: inherit; transition: background-color 120ms ease; }}
  button:hover {{ background: #ffffff; border-color: #ffffff; }}
  .alt {{ text-align: center; margin-top: 16px; font-size: 12.5px; color: #98a1ab; }}
  .alt a {{ color: #7fa9f0; text-decoration: none; }}
  .alt a:hover {{ text-decoration: underline; }}
  .flash {{ background: rgba(229,72,77,0.12); border: 1px solid rgba(229,72,77,0.34); color: #f28286;
           border-radius: 5px; padding: 9px 12px; font-size: 12.5px; margin-bottom: 6px; }}
  .flash-ok {{ background: rgba(70,167,88,0.11); border: 1px solid rgba(70,167,88,0.3); color: #66c07a; }}
  .tokenline {{ margin-top: 18px; padding-top: 14px; border-top: 1px solid #22262c;
               font-size: 12px; color: #98a1ab; text-align: center; }}
  label.consent {{ display: flex; gap: 8px; align-items: flex-start; font-size: 12px;
                  color: #98a1ab; margin-top: 14px; text-transform: none; letter-spacing: 0;
                  font-weight: 400; }}
  label.consent input {{ margin-top: 2px; accent-color: #4c8dff; }}
  label.consent a {{ color: #7fa9f0; }}
  .tokenline a {{ color: #7fa9f0; text-decoration: none; }}
  .tokenline a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
  <div class="card">
    <div class="brand">
      <div class="mark"><svg width="18" height="18" viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="7.2" stroke="#4c8dff" stroke-opacity="0.35"/><circle cx="10" cy="10" r="4.2" stroke="#4c8dff" stroke-opacity="0.55"/><path d="M10 4.6V10l4.2 2.3" stroke="#4c8dff" stroke-width="1.4" stroke-linecap="round"/><circle cx="10" cy="10" r="1.3" fill="#4c8dff"/></svg></div>
      <h1>Sentinel</h1>
    </div>
    <p class="sub">{subtitle}</p>
    {flash}
    <form method="post" action="{action}">
      <input type="hidden" name="csrf_token" value="{csrf}">
      <label for="email">Email</label>
      <input id="email" name="email" type="email" required autocomplete="email" autofocus>
      <label for="password">Password</label>
      <input id="password" name="password" type="password" required minlength="8" autocomplete="{autocomplete}">
      {extra_field}
      <label class="consent"><input type="checkbox" name="accept_terms" value="1" required>
        I agree to the <a href="/terms" target="_blank">Terms of Service</a> —
        authorized testing only.</label>
      <button type="submit">{button_label}</button>
    </form>
    <div class="alt">{alt}</div>
    <div class="tokenline">Running locally? <a href="/token-login?token={token}">Continue with access token →</a></div>
  </div>
</body>
</html>"""


def load_or_create_token(reports_dir: Path) -> str:
    """Load the dashboard auth token, creating one on first start.

    Stored inside the (gitignored) reports dir so restarts keep the same
    token and the secret never lands in git.
    """
    token_path = Path(reports_dir) / ".dashboard-token"
    if token_path.exists():
        token = token_path.read_text(encoding="utf-8").strip()
        if token:
            return token
    token = secrets.token_urlsafe(24)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(token, encoding="utf-8")
    return token

_LEGAL_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sentinel - {title}</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: "Segoe UI", system-ui, sans-serif; background: #07080b; color: #e8edf4;
         min-height: 100vh; padding: 36px 20px; line-height: 1.65; }
  .wrap { max-width: 720px; margin: 0 auto; }
  h1 { font-size: 17px; letter-spacing: 0.14em; text-transform: uppercase; font-weight: 650;
       margin-bottom: 18px; }
  h2 { font-size: 13px; letter-spacing: 0.1em; text-transform: uppercase; color: #2ee6a6;
       margin: 22px 0 6px; }
  p { color: #b9c1d4; font-size: 14px; margin: 8px 0; }
  p.fine { font-size: 12.5px; color: #8b93a7; margin-top: 26px; }
  p.none { color: #ff3b5c; }
  a { color: #4d9fff; text-decoration: none; }
  code { color: #2ee6a6; font-size: 12.5px; background: #10131a; padding: 2px 7px;
         border-radius: 6px; border: 1px solid rgba(232,237,244,0.1); }
</style>
</head>
<body>
  <div class="wrap">
    {body}
    <p class="fine"><a href="/console/app">&#8592; Back</a></p>
  </div>
</body>
</html>"""

_ADMIN_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sentinel - Admin</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: "Segoe UI", system-ui, sans-serif; background: #07080b; color: #e8edf4;
         min-height: 100vh; padding: 32px 20px; }
  .wrap { max-width: 860px; margin: 0 auto; }
  h1 { font-size: 17px; letter-spacing: 0.14em; text-transform: uppercase; font-weight: 650; }
  .sub { color: #8b93a7; font-size: 12.5px; margin: 8px 0 24px; line-height: 1.5; }
  h2 { font-size: 12px; letter-spacing: 0.12em; text-transform: uppercase; color: #2ee6a6;
       margin: 26px 0 10px; }
  table { width: 100%; border-collapse: collapse; background: #10131a;
          border: 1px solid rgba(232,237,244,0.1); border-radius: 12px; overflow: hidden; }
  th { text-align: left; font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase;
       color: #5a6276; padding: 10px 12px; border-bottom: 1px solid rgba(232,237,244,0.08); }
  td { padding: 10px 12px; font-size: 13px; border-bottom: 1px solid rgba(232,237,244,0.05);
       color: #b9c1d4; vertical-align: middle; }
  tr:last-child td { border-bottom: none; }
  td code { color: #2ee6a6; font-size: 12px; }
  td.none { text-align: center; color: #5a6276; padding: 22px; }
  td.detail { color: #8b93a7; font-size: 12px; }
  td.act form { display: flex; gap: 6px; align-items: center; }
  td.act input[type=text] { height: 28px; background: #161b24; color: #e8edf4;
          border: 1px solid rgba(232,237,244,0.12); border-radius: 6px; padding: 0 8px;
          font-size: 11.5px; width: 150px; }
  .mini { height: 28px; padding: 0 12px; border-radius: 6px; cursor: pointer; font-weight: 700;
          font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; font-family: inherit; }
  .mini.ok { border: 1px solid rgba(46,230,166,0.35); color: #2ee6a6; background: rgba(46,230,166,0.08); }
  .mini.bad { border: 1px solid rgba(255,59,92,0.35); color: #ff3b5c; background: rgba(255,59,92,0.08); }
  .mini:hover { filter: brightness(1.25); }
  .selfnote { color: #5a6276; font-size: 11.5px; }
  .st { font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; font-weight: 700;
        border-radius: 20px; padding: 3px 9px; white-space: nowrap; }
  .st.open { background: rgba(46,230,166,0.12); color: #2ee6a6; border: 1px solid rgba(46,230,166,0.3); }
  .st.used { background: rgba(255,59,92,0.1); color: #ff3b5c; border: 1px solid rgba(255,59,92,0.3); }
  .st.admin { background: rgba(77,159,255,0.12); color: #4d9fff; border: 1px solid rgba(77,159,255,0.3); }
  .scanline { background: #10131a; border: 1px solid rgba(232,237,244,0.1); border-radius: 12px;
              padding: 14px 16px; font-size: 13px; color: #b9c1d4; }
  a.back { color: #4d9fff; text-decoration: none; font-size: 12.5px; }
</style>
</head>
<body>
  <div class="wrap">
    <h1>Admin console</h1>
    <p class="sub">{user_count} account(s) on this instance. Suspension takes effect on the
    user's very next request; their reports stay retained for investigation.
    <a class="back" href="/console/app">&#8592; Back to console</a></p>

    <h2>Running scan</h2>
    <div class="scanline">{scan_state}</div>

    <h2>Accounts</h2>
    <table>
      <tr><th>Id</th><th>Email</th><th>Status</th><th>Detail</th><th>Action</th></tr>
      {user_rows}
    </table>

    <h2>Invite codes</h2>
    <form method="post" action="/invites" style="margin-bottom:12px">
      <input type="hidden" name="csrf_token" value="{csrf}">
      <button type="submit" class="mini ok">Generate invite code</button>
    </form>
    <table>
      <tr><th>Code</th><th>Created</th><th>Status</th><th>Used</th></tr>
      {invite_rows}
    </table>
  </div>
</body>
</html>"""

_INVITES_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sentinel - Invites</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: "Segoe UI", system-ui, sans-serif; background: #07080b; color: #e8edf4;
         min-height: 100vh; padding: 32px 20px; }
  .wrap { max-width: 760px; margin: 0 auto; }
  h1 { font-size: 17px; letter-spacing: 0.14em; text-transform: uppercase; font-weight: 650; }
  .sub { color: #8b93a7; font-size: 12.5px; margin: 8px 0 22px; line-height: 1.5; }
  form.gen { display: flex; gap: 10px; margin-bottom: 24px; }
  form.gen button { height: 38px; padding: 0 18px; border-radius: 8px; cursor: pointer;
           border: 1px solid rgba(46,230,166,0.35); color: #2ee6a6; font-weight: 700;
           background: linear-gradient(180deg, rgba(46,230,166,0.16), rgba(46,230,166,0.08));
           font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; font-family: inherit; }
  form.gen button:hover { background: rgba(46,230,166,0.22); }
  table { width: 100%; border-collapse: collapse; background: #10131a;
          border: 1px solid rgba(232,237,244,0.1); border-radius: 12px; overflow: hidden; }
  th { text-align: left; font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase;
       color: #5a6276; padding: 10px 14px; border-bottom: 1px solid rgba(232,237,244,0.08); }
  td { padding: 10px 14px; font-size: 13px; border-bottom: 1px solid rgba(232,237,244,0.05);
       color: #b9c1d4; }
  tr:last-child td { border-bottom: none; }
  td code { color: #2ee6a6; font-size: 12.5px; }
  td.none { text-align: center; color: #5a6276; padding: 22px; }
  .st { font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; font-weight: 700;
        border-radius: 20px; padding: 3px 9px; }
  .st.open { background: rgba(46,230,166,0.12); color: #2ee6a6; border: 1px solid rgba(46,230,166,0.3); }
  .st.used { background: rgba(139,147,167,0.1); color: #8b93a7; border: 1px solid rgba(139,147,167,0.25); }
  a.back { color: #4d9fff; text-decoration: none; font-size: 12.5px; }
</style>
</head>
<body>
  <div class="wrap">
    <h1>Invite codes</h1>
    <p class="sub">Signup is by invitation. Each code works exactly once - share it with
    someone you trust to scan their own sites. <a class="back" href="/console/app">&#8592; Back to console</a></p>
    <form class="gen" method="post" action="/invites">
      <input type="hidden" name="csrf_token" value="{csrf}">
      <button type="submit">Generate invite code</button>
    </form>
    <table>
      <tr><th>Code</th><th>Created</th><th>Status</th><th>Used</th></tr>
      {rows}
    </table>
  </div>
</body>
</html>"""



def create_app(
    state_path: Path,
    reports_dir: Path,
    project_root: Path | None = None,
    auth_token: str | None = None,
    users_db: Path | None = None,
    secret_key: str | None = None,
) -> Flask:
    app = Flask(__name__)
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[2]
    token = auth_token or load_or_create_token(reports_dir)
    app.secret_key = secret_key or secrets.token_hex(32)
    # Phase 3: public mode blocks private/loopback/metadata scan targets and
    # enforces the per-user daily quota. Local dev stays unrestricted by default.
    public_mode = os.environ.get("SENTINEL_PUBLIC_MODE", "").strip().lower() in (
        "1", "true", "yes",
    )
    daily_limit = int(os.environ.get("SENTINEL_DAILY_SCAN_LIMIT", "20") or "20")

    # Production posture: behind a TLS-terminating reverse proxy (see
    # docs/DEPLOYMENT.md). Cookies are Secure whenever the request arrived
    # over https (via ProxyFix), so plain-HTTP local use keeps working.
    from werkzeug.middleware.proxy_fix import ProxyFix

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_NAME="sentinel_session",
        SESSION_COOKIE_SECURE=True,  # only honored when scheme is https
    )

    users = UserStore(users_db or (Path(reports_dir) / "users.db"))
    limiter = RateLimiter(max_attempts=5, window_seconds=300)

    def _cookie_kwargs() -> dict:
        """Cookie flags for the dashboard token cookie, Secure on https."""
        return {
            "httponly": True,
            "samesite": "Lax",
            "secure": request.scheme == "https",
        }

    def _user():
        row = current_user(users)
        # Suspended accounts lose their session immediately (Phase 3
        # moderation): the very next request behaves as logged-out.
        if row is not None and row["suspended"]:
            logout_user()
            return None
        return row

    def _client_ip() -> str:
        return request.headers.get("X-Forwarded-For", request.remote_addr or "?").split(",")[0].strip()

    def _viewer_is_admin() -> bool:
        """Admins and bootstrap-token callers see every report; users see their own."""
        u = _user()
        if u is None:
            return True  # token-authenticated (the gate already rejected anonymous)
        return u["role"] == "admin"

    def _owns_report(rep: dict) -> bool:
        """True if the current viewer may see this report."""
        if _viewer_is_admin():
            return True
        u = _user()
        return u is not None and rep.get("owner_id") == u["id"]

    def _own_reports(reports: list[dict]) -> list[dict]:
        return [r for r in reports if _owns_report(r)]

    @app.before_request
    def _gate():
        # Auth gate: session user OR bootstrap token (admin/API).
        # Token auth (header / query / cookie) - also the API mechanism.
        provided = (
            request.headers.get("X-Sentinel-Token")
            or request.args.get("token")
            or request.cookies.get(_COOKIE)
        )
        if provided and secrets.compare_digest(provided, token):
            return None
        # Logged-in human?
        if _user() is not None:
            return None
        # Health check is public (uptime monitors, the reverse proxy).
        if request.path == "/healthz":
            return None
        # The site root and the console landing are public - logged-out
        # visitors get marketing + Sign in; the index route forwards
        # signed-in users into the console.
        if request.path in ("/", "/console/"):
            return None
        # Legal pages are public - hosts, targets, and prospective users
        # must be able to read the terms and find the abuse contact
        # without an account.
        if request.path in ("/terms", "/abuse"):
            return None
        # Auth routes are the exception - that's how you get in.
        if request.path in ("/login", "/signup", "/token-login"):
            return None
        # Static assets and favicon don't need auth.
        if request.path == "/favicon.ico" or request.path.startswith("/static/"):
            return None
        # The React console's auth screens + their bundle must load pre-login.
        if request.path in ("/console/login", "/console/signup"):
            return None
        if request.path.startswith("/console/assets/") or request.path in (
            "/console/favicon.svg",
            "/console/vite.svg",
        ):
            return None
        # Public JSON auth endpoints (CSRF token, policy, login, signup).
        if request.path in (
            "/api/auth/csrf",
            "/api/auth/policy",
            "/api/auth/login",
            "/api/auth/signup",
        ):
            return None
        if request.path.startswith("/api/"):
            return jsonify({"error": "unauthorized"}), 401
        from urllib.parse import quote as _quote

        return redirect(f"/console/login?next={_quote(request.path, safe='')}")

    @app.after_request
    def _remember_token(resp):
        """Visits via the tokened URL hand the browser a cookie so later
        UI fetches (and plain reloads) authenticate seamlessly."""
        provided = request.args.get("token")
        if provided and secrets.compare_digest(provided, token):
            resp.set_cookie(_COOKIE, token, path="/", **_cookie_kwargs())
        return resp

    @app.get("/healthz")
    def healthz():
        """Public liveness probe for the reverse proxy and uptime monitors."""
        return jsonify({"ok": True})

    @app.get("/api/me")
    def api_me():
        """Who is viewing: own email + admin flag (drives the console header)."""
        u = _user()
        if u is None:
            return jsonify({"email": None, "admin": True})  # bootstrap-token caller
        return jsonify({"email": u["email"], "admin": u["role"] == "admin"})

    @app.get("/api/csrf")
    def api_csrf():
        """Session CSRF token for console mutations (logout, invites)."""
        return jsonify({"csrf_token": csrf_token()})

    # --- JSON auth (React console login/signup) -------------------------------
    # Same rules as the form handlers below, JSON in/out. CSRF still enforced:
    # anonymous callers fetch a session-bound token from /api/auth/csrf first.

    @app.get("/api/auth/csrf")
    def api_auth_csrf():
        return jsonify({"csrf_token": csrf_token()})

    @app.get("/api/auth/policy")
    def api_auth_policy():
        return jsonify({"policy": signup_policy(users.count())})

    def _auth_body() -> dict:
        body = request.get_json(silent=True)
        return body if isinstance(body, dict) else {}

    @app.post("/api/auth/login")
    def api_auth_login():
        body = _auth_body()
        ip = _client_ip()
        if not limiter.check(f"login:{ip}"):
            return jsonify({"error": "Too many attempts - wait 5 minutes and try again."}), 429
        if not csrf_valid(body):
            return jsonify({"error": "Invalid or expired form - try again."}), 400
        row = users.verify(str(body.get("email", "")), str(body.get("password", "")))
        if row is None:
            limiter.hit(f"login:{ip}")
            return jsonify({"error": "Wrong email or password."}), 401
        limiter.reset(f"login:{ip}")
        login_user(int(row["id"]))
        return jsonify({"ok": True, "redirect": "/console/app"})

    @app.post("/api/auth/signup")
    def api_auth_signup():
        body = _auth_body()
        ip = _client_ip()
        if not limiter.check(f"signup:{ip}"):
            return jsonify({"error": "Too many attempts - wait 5 minutes and try again."}), 429
        if not csrf_valid(body):
            return jsonify({"error": "Invalid or expired form - try again."}), 400
        first = users.count() == 0
        policy = signup_policy(users.count())
        if policy == "bootstrap":
            if not secrets.compare_digest(str(body.get("bootstrap_token", "")), token):
                limiter.hit(f"signup:{ip}")
                return jsonify(
                    {"error": "Access token missing or wrong - the first account is reserved for the server operator."}
                ), 403
        elif policy == "invite":
            if not users.use_invite(str(body.get("invite_code", ""))):
                limiter.hit(f"signup:{ip}")
                return jsonify(
                    {"error": "That invite code is not valid (or already used) - ask an admin for a fresh one."}
                ), 403
        if not body.get("accept_terms"):
            return jsonify({"error": "You must accept the Terms of Service to create an account."}), 400
        try:
            uid = users.create_user(
                str(body.get("email", "")), str(body.get("password", "")), role="admin" if first else "user"
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        if uid is None:
            return jsonify({"error": "That email is already registered - sign in instead."}), 409
        limiter.reset(f"signup:{ip}")
        from qaagent.terms import TERMS_VERSION

        users.accept_terms(uid, TERMS_VERSION, ip=ip)
        login_user(uid)
        return jsonify({"ok": True, "redirect": "/console/app"})

    _UI_DIR = Path(__file__).resolve().parent / "ui"

    def _home() -> str:
        """Where signed-in users land: the React console when its bundle is
        installed, otherwise the classic dashboard."""
        if _UI_DIR.is_dir() and (_UI_DIR / "index.html").exists():
            return "/console/app"
        return "/"

    @app.get("/console")
    @app.get("/console/", defaults={"subpath": ""})
    @app.get("/console/<path:subpath>")
    def console(subpath: str = ""):
        """Serve the React console (same origin, so session cookies just work).

        Anonymous visitors fall through to the auth gate's login redirect;
        only the built bundle's files are served, everything else is the
        SPA fallback (index.html) so client-side routes resolve.
        """
        if not _UI_DIR.is_dir():
            return jsonify({"error": "console not installed in this build"}), 404
        if subpath:
            candidate = (_UI_DIR / subpath).resolve()
            try:
                candidate.relative_to(_UI_DIR.resolve())
            except ValueError:
                return jsonify({"error": "not found"}), 404
            if candidate.is_file():
                return send_file(candidate)
        return send_file(_UI_DIR / "index.html")

    # --- Public legal pages (Phase 3) -----------------------------------------

    @app.get("/terms")
    def terms_page():
        from qaagent import terms as _terms

        return _LEGAL_PAGE.replace("{title}", "Terms of Service").replace(
            "{body}", _terms.terms_html()
        )

    @app.get("/abuse")
    def abuse_page():
        from qaagent import terms as _terms

        email, url = _terms.abuse_contact()
        lines = [
            "<p>Report misuse of this Sentinel deployment (unauthorized "
            "scanning, abusive traffic, illegal content): a report channel "
            "is listed below. Reports are reviewed promptly and offending "
            "accounts are suspended.</p>",
            "<h2>Contact</h2>",
        ]
        if email:
            import html as _html

            lines.append(
                f'<p>Email: <a href="mailto:{_html.escape(email, quote=True)}">'
                f'{_html.escape(email)}</a></p>'
            )
        if url:
            import html as _html

            lines.append(
                f'<p>Web form: <a href="{_html.escape(url, quote=True)}" rel="nofollow noopener">'
                f'{_html.escape(url)}</a></p>'
            )
        if not email and not url:
            lines.append(
                '<p class="none">No dedicated abuse contact is configured for '
                "this deployment yet - the operator should set "
                "<code>SENTINEL_ABUSE_EMAIL</code>.</p>"
            )
        lines.append(
            '<p class="fine">Please include the target domain, timestamps, and '
            "any source identifiers you can see - it makes investigation faster. "
            'See also the <a href="/terms">Terms of Service</a>.</p>'
        )
        return _LEGAL_PAGE.replace("{title}", "Report abuse").replace(
            "{body}", "\n".join(lines)
        )

    @app.context_processor
    def _inject_user():
        return {"user": _user()}

    # --- Auth routes ---------------------------------------------------------

    def _auth_page(mode: str, subtitle: str, flash: str = "", flash_ok: bool = False, policy: str = ""):
        if mode == "signup":
            action, button = "/signup", "Create account"
            alt = 'Already registered? <a href="/console/login">Sign in</a>'
            if policy == "bootstrap":
                extra_field = (
                    '<label for="bootstrap_token">Access token</label>'
                    '<input id="bootstrap_token" name="bootstrap_token" type="password" '
                    'required autocomplete="off">'
                )
            elif policy == "invite":
                extra_field = (
                    '<label for="invite_code">Invite code</label>'
                    '<input id="invite_code" name="invite_code" type="text" required '
                    'autocomplete="off" placeholder="XXXXX-XXXXX-XXXXX">'
                )
            else:
                extra_field = ""
        else:
            action, button = "/login", "Sign in"
            alt = 'No account yet? <a href="/console/signup">Create one</a>'
            extra_field = ""
        flash_cls = "flash flash-ok" if flash_ok and flash else "flash"
        return _LOGIN_PAGE.format(
            subtitle=subtitle,
            flash=f'<div class="{flash_cls}">{flash}</div>' if flash else "",
            action=action,
            csrf=csrf_token(),
            autocomplete="new-password" if mode == "signup" else "current-password",
            button_label=button,
            alt=alt,
            token=token,
            extra_field=extra_field,
        )

    @app.get("/login")
    def login():
        if _user() is not None:
            return redirect(_home())
        if request.args.get("out") == "1":
            return redirect("/console/login?signedout=1")
        return _auth_page("login", "Sign in to run scans and view reports.")

    @app.post("/login")
    def login_post():
        ip = _client_ip()
        if not limiter.check(f"login:{ip}"):
            return _auth_page(
                "login", "Sign in to run scans and view reports.",
                "Too many attempts - wait 5 minutes and try again.",
            )
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        if not csrf_valid(request.form):
            return _auth_page("login", "Sign in to run scans and view reports.", "Invalid or expired form - try again."), 400
        row = users.verify(email, password)
        if row is None:
            limiter.hit(f"login:{ip}")
            return _auth_page("login", "Sign in to run scans and view reports.", "Wrong email or password.")
        limiter.reset(f"login:{ip}")
        login_user(int(row["id"]))  # suspended accounts never verify (store-level)
        dest = request.args.get("next") or _home()
        if not dest.startswith("/"):  # open-redirect guard
            dest = _home()
        return redirect(dest)

    @app.get("/signup")
    def signup():
        if _user() is not None:
            return redirect(_home())
        policy = signup_policy(users.count())
        if policy == "bootstrap":
            subtitle = (
                "Create the admin account - paste the access token from the "
                "URL printed by `sentinel dashboard` to prove you own this server."
            )
        elif policy == "open":
            subtitle = "Create an account to run scans and view reports."
        else:
            subtitle = (
                "Signup is by invitation. Enter the invite code you were "
                "given, or ask an admin for one."
            )
        return _auth_page("signup", subtitle, policy=policy)

    @app.post("/signup")
    def signup_post():
        ip = _client_ip()
        if not limiter.check(f"signup:{ip}"):
            return _auth_page(
                "signup", "Create an account to run scans and view reports.",
                "Too many attempts - wait 5 minutes and try again.",
            )
        if not csrf_valid(request.form):
            return _auth_page("signup", "Create an account to run scans and view reports.", "Invalid or expired form - try again."), 400
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        first = users.count() == 0
        policy = signup_policy(users.count())
        # Phase 3 gate: closed signup. The first (admin) account must present
        # the dashboard bootstrap token; later accounts need a single-use
        # invite code minted by an admin. Open signup is an explicit env opt-in.
        if policy == "bootstrap":
            provided = request.form.get("bootstrap_token", "")
            if not secrets.compare_digest(provided, token):
                limiter.hit(f"signup:{ip}")
                return _auth_page(
                    "signup",
                    "Create the admin account - paste the access token from the "
                    "URL printed by `sentinel dashboard` to prove you own this server.",
                    "Access token missing or wrong - the first account is "
                    "reserved for the server operator.",
                    policy="bootstrap",
                )
        elif policy == "invite":
            code = request.form.get("invite_code", "")
            if not users.use_invite(code):
                limiter.hit(f"signup:{ip}")
                return _auth_page(
                    "signup",
                    "Signup is by invitation. Enter the invite code you were "
                    "given, or ask an admin for one.",
                    "That invite code is not valid (or already used) - ask an "
                    "admin for a fresh one.",
                    policy="invite",
                )
        # Phase 3 legal layer: consent must be explicit (the checkbox is also
        # required in the form, but never trust the client alone).
        if not request.form.get("accept_terms"):
            return _auth_page(
                "signup",
                "Create an account to run scans and view reports.",
                "You must accept the Terms of Service to create an account.",
                policy=policy,
            )
        try:
            uid = users.create_user(email, password, role="admin" if first else "user")
        except ValueError as exc:
            return _auth_page("signup", "Create an account to run scans and view reports.", str(exc), policy=policy)
        if uid is None:
            return _auth_page("signup", "Create an account to run scans and view reports.", "That email is already registered - sign in instead.", policy=policy)
        limiter.reset(f"signup:{ip}")
        # Record the acceptance that came with the signup (same version the
        # form linked to; re-accepted on version bumps via /terms/accept).
        from qaagent.terms import TERMS_VERSION

        users.accept_terms(uid, TERMS_VERSION, ip=ip)
        login_user(uid)
        return redirect(_home())

    @app.get("/token-login")
    def token_login_page():
        """Local users arrive via the tokened URL - explain and honor it."""
        provided = request.args.get("token", "")
        if provided and secrets.compare_digest(provided, token):
            resp = redirect(_home())
            resp.set_cookie(_COOKIE, provided, path="/", **_cookie_kwargs())
            return resp
        return _auth_page(
            "login",
            "Sign in to run scans and view reports.",
            "Access token missing or wrong - use the full URL printed by `sentinel dashboard`.",
        )

    @app.post("/logout")
    def logout():
        if not csrf_valid(request.form):
            return redirect(_home())
        logout_user()
        resp = redirect("/login?out=1")
        # Token-cookie holders (token-login URL) have no session to clear -
        # without this the cookie re-authenticates them on the next request
        # and logout appears to do nothing. Both paths: current cookies are
        # scoped site-wide, legacy ones may be scoped to /console/.
        resp.delete_cookie(_COOKIE, path="/")
        resp.delete_cookie(_COOKIE, path="/console/")
        resp.delete_cookie(_COOKIE, path="/console")
        return resp

    # --- Admin: invite codes (Phase 3 closed signup) -------------------------

    def _invite_rows() -> str:
        """Rendered invite table rows, shared by /invites and /admin."""
        import html as _html

        rows = ""
        for inv in users.list_invites():
            status = (
                '<span class="st used">used</span>'
                if inv["used_by"] is not None
                else '<span class="st open">open</span>'
            )
            rows += (
                '<tr><td><code>' + _html.escape(inv["code"]) + '</code></td>'
                '<td>' + (inv["created_at"] or "") + '</td>'
                '<td>' + status + '</td>'
                '<td>' + ((inv["used_at"] or "") if inv["used_by"] is not None else "")
                + '</td></tr>'
            )
        return (
            rows
            or '<tr><td colspan="4" class="none">No invites yet - generate the first one.</td></tr>'
        )

    @app.get("/invites")
    def invites_page():
        u = _user()
        if u is None or u["role"] != "admin":
            return redirect(_home())
        return _INVITES_PAGE.replace("{rows}", _invite_rows()).replace(
            "{csrf}", csrf_token()
        )

    @app.post("/invites")
    def invites_create():
        u = _user()
        if u is None or u["role"] != "admin" or not csrf_valid(request.form):
            return redirect("/invites")
        users.create_invite(created_by=int(u["id"]))
        return redirect("/invites")

    # --- Admin console (Phase 3 moderation) -----------------------------------

    def _admin_user_rows(viewer_id: int) -> str:
        import html as _html

        rows = ""
        for row in users.list_users():
            if row["suspended"]:
                state = '<span class="st used">suspended</span>'
                action = (
                    '<form method="post" action="/admin/suspend">'
                    '<input type="hidden" name="csrf_token" value="{csrf}">'
                    '<input type="hidden" name="user_id" value="%d">'
                    '<input type="hidden" name="suspended" value="0">'
                    '<button type="submit" class="mini ok">Reinstate</button></form>'
                ) % row["id"]
                detail = (
                    _html.escape(row["suspend_reason"] or "")
                    + (" &middot; " + (row["suspended_at"] or "") if row["suspended_at"] else "")
                )
            else:
                state = (
                    '<span class="st open">active</span>'
                    if row["role"] != "admin"
                    else '<span class="st admin">admin</span>'
                )
                if row["id"] == viewer_id:
                    action = '<span class="selfnote">that is you</span>'
                    detail = ""
                else:
                    action = (
                        '<form method="post" action="/admin/suspend">'
                        '<input type="hidden" name="csrf_token" value="{csrf}">'
                        '<input type="hidden" name="user_id" value="%d">'
                        '<input type="hidden" name="suspended" value="1">'
                        '<input type="text" name="reason" placeholder="reason (optional)" maxlength="200">'
                        '<button type="submit" class="mini bad">Suspend</button></form>'
                    ) % row["id"]
                    detail = "joined " + (row["created_at"] or "")
            rows += (
                '<tr><td>#' + str(row["id"]) + '</td>'
                '<td>' + _html.escape(row["email"] or "") + '</td>'
                '<td>' + state + '</td>'
                '<td class="detail">' + detail + '</td>'
                '<td class="act">' + action + '</td></tr>'
            )
        return rows

    @app.get("/admin")
    def admin_page():
        u = _user()
        # Bootstrap-token callers administer the instance without an account
        # (the token is the admin/API mechanism, same as report visibility).
        token_caller = False
        if u is None:
            provided = (
                request.headers.get("X-Sentinel-Token")
                or request.args.get("token")
                or request.cookies.get(_COOKIE)
            )
            if not (provided and secrets.compare_digest(provided, token)):
                return redirect(_home())
            token_caller = True
        elif u["role"] != "admin":
            return redirect(_home())
        viewer_id = -1 if token_caller else int(u["id"])  # no "that is you" row
        import html as _html

        # Running scan card: global truth (scans are instance-wide), but the
        # owner's email is shown only to admins - which is everyone here.
        proc = _scan.get("proc")
        running = proc is not None and proc.poll() is None
        if running:
            scan_state = (
                '<span class="st admin">running</span> <code>'
                + _html.escape(str(_scan.get("config") or "")) + '</code>'
                + " started " + _html.escape(str(_scan.get("started") or ""))
                + " by " + _html.escape(str(_scan.get("owner_email") or "token"))
            )
        else:
            rc = proc.returncode if proc is not None else None
            last = _scan.get("config")
            scan_state = (
                '<span class="st used">idle</span> last exit: '
                + (_html.escape(str(rc)) if rc is not None else "n/a")
                + (" &middot; last config: <code>" + _html.escape(str(last)) + "</code>" if last else "")
            )
        body = _ADMIN_PAGE.replace("{user_rows}", _admin_user_rows(viewer_id))
        body = body.replace("{invite_rows}", _invite_rows())
        body = body.replace("{scan_state}", scan_state)
        body = body.replace("{csrf}", csrf_token())
        body = body.replace("{user_count}", str(users.count()))
        return body

    @app.post("/admin/suspend")
    def admin_suspend():
        u = _user()
        if u is None or u["role"] != "admin" or not csrf_valid(request.form):
            return redirect("/admin")
        raw = request.form.get("user_id", "")
        if not raw.isdigit():
            return redirect("/admin")
        target_id = int(raw)
        if target_id == int(u["id"]):
            return redirect("/admin")  # never lock yourself out
        suspend = request.form.get("suspended") == "1"
        reason = request.form.get("reason", "").strip()[:200]
        if suspend:
            users.set_suspended(target_id, True, reason or "suspended by admin")
        else:
            users.set_suspended(target_id, False)
        return redirect("/admin")

    # --- Terms acceptance (Phase 3 legal layer) -------------------------------

    def _terms_current(u) -> bool:
        """True if this account has accepted the current terms version."""
        if u is None:
            return True  # token callers are the operator, not a terms party
        from qaagent.terms import TERMS_VERSION

        return users.terms_accepted_version(int(u["id"])) == TERMS_VERSION

    @app.post("/terms/accept")
    def terms_accept():
        u = _user()
        if u is None or not csrf_valid(request.form):
            return redirect("/terms")
        from qaagent.terms import TERMS_VERSION

        users.accept_terms(int(u["id"]), TERMS_VERSION, ip=_client_ip())
        dest = request.args.get("next") or _home()
        if not dest.startswith("/"):  # open-redirect guard
            dest = _home()
        return redirect(dest)

    @app.get("/")
    def index():
        # The classic dashboard is retired: the root only routes.
        # Signed-in users go straight into the console; everyone else
        # gets the public console landing (marketing + Sign in).
        if _user() is not None:
            return redirect("/console/app")
        return redirect("/console/")

    @app.get("/api/configs")
    def api_configs():
        """List available scan configs (name + target) for the run controls."""
        import yaml

        from qaagent.cli import _config_dir

        configs = []
        for path in sorted(_config_dir().glob("config*.yml")):
            name = path.stem
            if name.startswith("config."):
                name = name[len("config.") :]
            target = None
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                target = data.get("target")
            except Exception:
                target = None
            configs.append({"name": name, "target": target, "file": path.name})
        return jsonify({"configs": configs})

    @app.post("/api/scan")
    def api_scan():
        # Start a scan as a background process: {config, skip_llm, authorized}.
        # `config` may be an existing config name or a bare domain;
        # unknown domains get a config auto-created, matching the
        # `sentinel run --config somesite.com` CLI behavior.
        body = request.get_json(silent=True) or {}
        name = str(body.get("config", "")).strip().rstrip("/")
        skip_llm = bool(body.get("skip_llm"))
        if not name or len(name) > 200 or any(c in name for c in '\\/:*?"<>|'):
            return jsonify({"error": "invalid config name"}), 400

        # Phase 3 authorization: the starter asserts they may test this target;
        # the declaration is stamped onto every report the run writes.
        if not body.get("authorized"):
            return jsonify(
                {
                    "error": "authorization required - confirm you own the site "
                    "or have permission to test it"
                }
            ), 403

        # Phase 3 legal layer: logged-in starters must have accepted the
        # current Terms of Service (signup consent or later re-acceptance).
        u_terms = _user()
        if u_terms is not None and not _terms_current(u_terms):
            return jsonify(
                {
                    "error": "terms acceptance required - review and accept the "
                    "current Terms of Service (see /terms) before scanning",
                    "code": "terms_required",
                }
            ), 403

        # Resolve the config exactly like the CLI does - same directory the
        # run subprocess will search (SENTINEL_CONFIG_DIR) - but do not create
        # anything yet: the policy check must gate before files are written.
        from qaagent.cli import _auto_create_config, _config_dir, _derive_target

        created = False
        probe = Path(name)
        config_dir = _config_dir()
        config_path = None
        for cand in (
            probe,
            Path(f"config.{name}.yml"),
            Path(f"{name}.yml"),
            Path(f"config.{name}"),
        ):
            if (config_dir / cand).exists():
                config_path = config_dir / cand
                break
        if config_path is not None:
            # The policy applies to the configured target, not the name.
            import yaml as _yaml

            try:
                target = (_yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}).get("target")
            except Exception:
                target = None
            target = target or _derive_target(name)
        else:
            target = _derive_target(name)
            if target is None:
                return jsonify(
                    {
                        "error": f"no config for '{name}' and it is not a domain - "
                        "type a site like example.com, or create a config first"
                    }
                ), 400

        # Phase 3 target policy: public deployments must never scan internal
        # networks (SSRF-style pivots) — check before creating or spawning.
        from qaagent.netpolicy import target_is_allowed

        allowed, reason = target_is_allowed(target or name, public_mode=public_mode)
        if not allowed:
            return jsonify({"error": f"target refused: {reason}"}), 403

        # Phase 3 quota: per-user daily cap (token callers count separately).
        u0 = _user()
        if u0 is not None and daily_limit > 0:
            from datetime import date

            today = date.today().isoformat()
            mine = [
                r
                for r in _own_reports(load_report_files(reports_dir))
                if (r.get("started_at") or "")[:10] == today
            ]
            if len(mine) >= daily_limit:
                return jsonify(
                    {"error": f"daily scan limit reached ({daily_limit}/day) - resets at midnight UTC"}
                ), 429

        if config_path is None:
            _auto_create_config(name, target)
            created = True

        proc = _scan["proc"]
        if proc is not None and proc.poll() is None:
            return jsonify({"error": "a scan is already running"}), 409
        reports_dir.mkdir(parents=True, exist_ok=True)
        log_path = reports_dir / "scan-ui.log"
        args = [sys.executable, "-u", "-m", "qaagent", "run", "--config", name]
        if skip_llm:
            args.append("--skip-llm")
        # Ownership: the scan belongs to whoever clicked Run. The subprocess
        # reads SENTINEL_OWNER_* and stamps every report it writes with it,
        # plus the Phase 3 authorization declaration (who, when, from where).
        u = _user()
        env = os.environ.copy()
        if u is not None:
            env["SENTINEL_OWNER_ID"] = str(u["id"])
            env["SENTINEL_OWNER_EMAIL"] = u["email"] or ""
        else:
            env.pop("SENTINEL_OWNER_ID", None)
            env.pop("SENTINEL_OWNER_EMAIL", None)
        env["SENTINEL_AUTHORIZED"] = "1"
        env["SENTINEL_AUTHORIZED_AT"] = datetime.now(timezone.utc).isoformat()
        env["SENTINEL_AUTHORIZED_BY"] = (u["email"] if u is not None else "bootstrap-token")
        env["SENTINEL_AUTHORIZED_IP"] = _client_ip()
        log_fh = open(log_path, "w", encoding="utf-8")
        try:
            proc = subprocess.Popen(
                args,
                cwd=str(root),
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                env=env,
            )
        finally:
            log_fh.close()
        _scan.update(
            proc=proc,
            config=name,
            skip_llm=skip_llm,
            started=datetime.now(timezone.utc).isoformat(),
            log_path=str(log_path),
            returncode=None,
            owner_id=(u["id"] if u is not None else None),
            owner_email=(u["email"] if u is not None else None),
        )
        return jsonify(
            {"started": True, "config": name, "skip_llm": skip_llm, "created": created}
        )

    @app.get("/api/scan/status")
    def api_scan_status():
        """Is a UI-started scan running, and what has it printed so far?"""
        proc = _scan["proc"]
        running = proc is not None and proc.poll() is None
        if proc is not None and not running and _scan["returncode"] is None:
            _scan["returncode"] = proc.returncode
        tail: list[str] = []
        if _scan["log_path"]:
            log = Path(_scan["log_path"])
            if log.exists():
                tail = log.read_text(encoding="utf-8", errors="replace").splitlines()[-25:]
        return jsonify(
            {
                "running": running,
                "config": _scan["config"],
                "skip_llm": _scan["skip_llm"],
                "started": _scan["started"],
                "returncode": _scan["returncode"],
                "log_tail": tail,
            }
        )

    @app.get("/api/state")
    def api_state():
        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            data = {
                "status": "idle",
                "stage": "No run yet",
                "target": "",
                "findings": [],
                "recent_actions": [],
                "step": 0,
                "max_steps": 0,
            }
        # Isolation: the live view shows only the viewer's own scan. A running
        # or just-finished scan tracks its starter in _scan; older scans with a
        # different owner (or pre-ownership runs) show as idle for others.
        if not _viewer_is_admin():
            u = _user()
            owner = _scan.get("owner_id")
            if owner is None or (u is not None and owner != u["id"]):
                data = {
                    "status": "idle",
                    "stage": "No run yet",
                    "target": "",
                    "findings": [],
                    "recent_actions": [],
                    "step": 0,
                    "max_steps": 0,
                }
        return jsonify(data)

    @app.get("/api/diff")
    def api_diff():
        """Compare the two most recent runs: new / fixed / unchanged findings."""
        reports = _own_reports(load_report_files(reports_dir))
        if not reports:
            return jsonify(
                {
                    "latest_run": None,
                    "previous_run": None,
                    "new": [],
                    "fixed": [],
                    "unchanged": [],
                    "counts": {"new": 0, "fixed": 0, "unchanged": 0},
                }
            )
        latest = reports[-1]
        previous = reports[-2] if len(reports) >= 2 else None
        diff = compare_reports(latest, previous)
        return jsonify(
            {
                "latest_run": diff.latest_run,
                "previous_run": diff.previous_run,
                "new": diff.new,
                "fixed": diff.fixed,
                "unchanged": diff.unchanged,
                "counts": diff.counts,
            }
        )

    _REPORT_DOWNLOADS = {
        "md": ("report-{stamp}.md", "text/markdown; charset=utf-8"),
        "json": ("report-{stamp}.json", "application/json"),
        "csv": ("report-{stamp}.csv", "text/csv; charset=utf-8"),
        "html": ("report-{stamp}.html", "text/html; charset=utf-8"),
    }

    @app.get("/api/history")
    def api_history():
        """Past runs the viewer owns, newest first, with per-run downloads info."""
        reports = list(reversed(_own_reports(load_report_files(reports_dir))))
        out = []
        for rep in reports[:50]:
            stamp = ""
            try:
                started = datetime.fromisoformat(str(rep.get("started_at") or ""))
                stamp = started.strftime("%Y%m%d-%H%M%S")
            except ValueError:
                stamp = ""
            out.append(
                {
                    "stamp": stamp,
                    "target": rep.get("target", ""),
                    "started_at": rep.get("started_at"),
                    "finished_at": rep.get("finished_at"),
                    "status": rep.get("status"),
                    "owner_email": rep.get("owner_email"),
                    "summary": rep.get("summary")
                    or rep.get("counts")
                    or {
                        "critical": sum(1 for f in rep.get("findings", []) if f.get("severity") == "critical"),
                        "high": sum(1 for f in rep.get("findings", []) if f.get("severity") == "high"),
                        "medium": sum(1 for f in rep.get("findings", []) if f.get("severity") == "medium"),
                        "low": sum(1 for f in rep.get("findings", []) if f.get("severity") == "low"),
                        "info": sum(1 for f in rep.get("findings", []) if f.get("severity") == "info"),
                    },
                    "finding_count": len(rep.get("findings", [])),
                    "has_testio": (reports_dir / f"testio-{stamp}").is_dir() if stamp else False,
                }
            )
        return jsonify({"runs": out})

    @app.get("/api/report/<stamp>/<fmt>")
    def api_report_download(stamp: str, fmt: str):
        """Download one artifact of one run - HTML, MD, CSV, JSON, or Test IO zip.

        Strict stamp validation (hex digits only) doubles as the path-traversal
        guard; ownership is enforced before any byte leaves the server.
        """
        import re as _re

        if not _re.fullmatch(r"[0-9a-fA-F-]{10,20}", stamp):
            return jsonify({"error": "invalid report id"}), 400
        fmt = fmt.lower()
        if fmt == "testio":
            bug_dir = reports_dir / f"testio-{stamp}"
            if not bug_dir.is_dir():
                return jsonify({"error": "Test IO bundle not found for this run"}), 404
            rep_path = reports_dir / f"report-{stamp}.json"
            try:
                rep = json.loads(rep_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return jsonify({"error": "report metadata missing"}), 404
            if not _owns_report(rep):
                return jsonify({"error": "forbidden"}), 403
            import io
            import zipfile

            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for child in sorted(bug_dir.rglob("*")):
                    if child.is_file():
                        zf.write(child, child.relative_to(bug_dir))
            buf.seek(0)
            return send_file(
                buf,
                mimetype="application/zip",
                as_attachment=True,
                download_name=f"testio-{stamp}.zip",
            )
        if fmt not in _REPORT_DOWNLOADS:
            return jsonify({"error": "unknown format"}), 404
        filename, mimetype = _REPORT_DOWNLOADS[fmt]
        path = reports_dir / filename.format(stamp=stamp)
        if not path.is_file():
            return jsonify({"error": "file not found"}), 404
        try:
            rep = json.loads((reports_dir / f"report-{stamp}.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return jsonify({"error": "report metadata missing"}), 404
        if not _owns_report(rep):
            return jsonify({"error": "forbidden"}), 403
        return send_file(path, mimetype=mimetype, as_attachment=True, download_name=path.name)

    @app.get("/api/report")
    def api_report():
        files = sorted(reports_dir.glob("report-*.md"))
        if not files:
            return jsonify(
                {"path": None, "json_path": None, "markdown": "No report yet."}
            )
        # Walk newest-first until the first report the viewer owns.
        latest = None
        json_path = None
        for f in reversed(files):
            stamp = f.stem[len("report-") :]
            jf = reports_dir / f"report-{stamp}.json"
            try:
                rep = json.loads(jf.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if _owns_report(rep):
                latest = f
                json_path = str(jf) if jf.exists() else None
                break
        if latest is None:
            return jsonify(
                {"path": None, "json_path": None, "markdown": "No report yet."}
            )
        return jsonify(
            {
                "path": str(latest),
                "json_path": json_path,
                "markdown": latest.read_text(encoding="utf-8"),
            }
        )

    return app


def build_app_for_serving(
    state_path: Path,
    reports_dir: Path,
    project_root: Path | None = None,
    auth_token: str | None = None,
) -> Flask:
    """Create the dashboard app with the persisted session-signing key.

    Used by both the local dev server (run_dashboard) and the production
    WSGI entrypoint (wsgi.py), so logins survive restarts in both modes.
    Also pins the shared config directory (SENTINEL_CONFIG_DIR or the project
    root) so run/config listing/auto-create agree no matter the cwd — the
    hosted case keeps dashboard-created configs on the persistent volume.
    """
    os.environ.setdefault(
        "SENTINEL_CONFIG_DIR",
        str(Path(project_root) if project_root else Path(__file__).resolve().parents[2]),
    )
    key_path = Path(reports_dir) / ".dashboard-secret"
    if key_path.exists():
        secret = key_path.read_text(encoding="utf-8").strip()
    else:
        secret = secrets.token_hex(32)
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text(secret, encoding="utf-8")
    return create_app(
        state_path,
        reports_dir,
        project_root=project_root,
        auth_token=auth_token,
        secret_key=secret,
    )


def run_dashboard(
    state_path: Path,
    reports_dir: Path,
    port: int,
    project_root: Path | None = None,
    auth_token: str | None = None,
) -> None:
    """Serve the dashboard with the local dev server until interrupted."""
    app = build_app_for_serving(state_path, reports_dir, project_root, auth_token)
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
