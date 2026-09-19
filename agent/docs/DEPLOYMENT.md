# Deploying Sentinel publicly (HTTPS)

This is the build plan for taking the local dashboard public. Three hard
requirements shape every choice below: **HTTPS is non-negotiable** (sessions and
vulnerability findings cross the wire), **scans must be authorized** (users may
only test sites they own or are permitted to test — the same rule Test IO
enforces via invite-only cycles), and **all state is already one directory**
(`reports/`), which makes containerization straightforward.

## Current state (what's ready, what isn't)

Ready for hosting — built in v1:
- Accounts with scrypt password hashing, CSRF, login rate limiting (5/5min/IP)
- Per-account data isolation (users see only their own scans)
- Auth-gated report downloads and per-account history
- Secret key persisted in `reports/.dashboard-secret` (sessions survive restarts)
- All state in one directory: `reports/` (reports, users.db, tokens, live state)

Gaps to close before launch (each maps to a phase below):
1. Flask **dev server** is serving the app (`dashboard.py` `.run(...)`) — not for production
2. Cookies lack `Secure`; no `SESSION_COOKIE_SECURE`/proxy config
3. **Signup is open** — first visitor could claim admin on a fresh instance
4. **No authorization-to-scan proof** — legally required for a public testing tool
5. Playwright defaults to `msedge` channel — needs bundled Chromium in the container
6. Scans spawn `subprocess`es — needs a container image with the agent installed

## Target architecture

```
                    ┌────────────────────────── VPS (2 vCPU / 4 GB min) ─────────┐
 user ──HTTPS──▶ Caddy (TLS, auto-Let's-Encrypt) ──▶ gunicorn ×2 ──▶ Flask app  │
                    │                              │            │               │
                    │                              │      reports/ volume        │
                    │                              │      (users.db, reports,    │
                    │                              │       tokens, secrets)      │
                    │                              └─ spawns: sentinel run …     │
                    │                                    (scan workers, same    │
                    │                                     container or sibling) │
                    └────────────────────────────────────────────────────────────┘
```

Choices and why:
- **Caddy** over nginx/certbot: TLS certificates issue and renew automatically
  with two lines of config. One less thing to break.
- **gunicorn** over the Flask dev server: concurrency + sane timeouts. 2–4
  workers is plenty for a single-box launch.
- **Single VPS + Docker Compose** over Kubernetes/serverless: scans are
  long-running (minutes) and spawn Playwright browsers — containers, not
  serverless. One box runs the web app and the scan workers; split later.
- **Bind gunicorn to `127.0.0.1` inside the Docker network**; only Caddy
  publishes 443/80.

## Phase 1 — Production server (small code changes)

1. **WSGI entrypoint** (`wsgi.py` at repo root):
   ```python
   from qaagent.cli import _load_env
   from qaagent.dashboard import load_or_create_token, run_dashboard_wsgi
   _load_env()
   # app factory wired to project-root reports/, token from env or disk
   ```
   Add `run_dashboard_wsgi(...)` next to `run_dashboard` that returns the app
   instead of calling `.run()`. `sentinel dashboard` stays exactly as is for
   local use.
2. **Secure cookies behind the proxy** in `create_app`:
   ```python
   app.config.update(
       SESSION_COOKIE_SECURE=True,      # never over plain HTTP
       SESSION_COOKIE_HTTPONLY=True,
       SESSION_COOKIE_SAMESITE="Lax",
       SESSION_COOKIE_NAME="sentinel_session",
   )
   ```
   For the token cookie: `samesite="Lax", secure=True` (keep `httponly`).
   Add `PROXY_FIX`-style handling (or `ProxyFix` from werkzeug) so
   `_client_ip()` and redirect URLs trust exactly one proxy hop.
3. **Dependency**: `gunicorn` added to a new `[project.optional-dependencies]
   prod = ["gunicorn>=21", "werkzeug>=3"]`.
4. **Health endpoint**: `GET /healthz` → `{"ok": true}` without auth, for the
   reverse proxy and uptime checks. (Note: `/_health` may collide with scan
   probing; `healthz` is unambiguous.)

## Phase 2 — Container image + Compose

1. `Dockerfile` (repo root):
   - Base: `mcr.microsoft.com/playwright/python:v1.49.0-jammy` (bundles browser
     deps — the hard part of containerizing Playwright)
   - `pip install -e ".[prod,targets]"` + `playwright install chromium`
   - Non-root user; `ENV BROWSER_CHANNEL=chromium` (config default stays msedge
     for local Windows use)
   - Copy `agent/` sources; volume-mount point `/data/reports`
2. `compose.yaml`:
   ```yaml
   services:
     web:
       build: .
       command: gunicorn -w 2 -t 600 -b 127.0.0.1:8000 wsgi:app
       env_file: .env            # NVIDIA_API_KEY, SENTINEL_PUBLIC_URL
       volumes: ["./data/reports:/data/reports"]
       restart: unless-stopped
     caddy:
       image: caddy:2
       ports: ["80:80", "443:443"]
       volumes:
         - ./Caddyfile:/etc/caddy/Caddyfile
         - caddy_data:/data
   volumes: { caddy_data: {} }
   ```
   `-t 600` because scan-start returns after spawning, but history/download
   requests are quick; the timeout protects stuck workers.
3. `Caddyfile` (whole file):
   ```
   sentinel.example.com {
       reverse_proxy web:8000
   }
   ```
4. `.env` on the server (never committed):
   `NVIDIA_API_KEY=…`, `SENTINEL_PUBLIC_URL=https://sentinel.example.com`

## Phase 3 — Launch safety (required for a public testing tool)

1. **Closed signup with invite codes.** Fresh instance: first account created
   only via a one-time bootstrap code printed by the server on first start
   (same pattern as the local token). After that, signup requires an invite
   code generated by an admin. This closes "random visitor claims admin" and
   "anyone scans anything."
2. **Authorization-to-scan gate.** Before a scan starts, the user must affirm
   ownership: a checked declaration stored with the run (`ownership_declared:
   true`, who, when) on the scan-start form, plus these technical controls:
   - block private/loopback/link-local targets by default
     (`127.0.0.0/8`, `10/8`, `172.16/12`, `192.168/16`, `169.254/16`, `::1`)
   - optional DNS-verify: target's A record must not resolve into those ranges
   - per-user concurrent-scan limit (1) and per-day quota (configurable)
3. **Scan isolation in production:** run each scan as the same container image
   but a **separate one-shot container** (`docker compose run --rm`) or at
   minimum a dedicated subprocess user, so a hostile target can't reach the
   web app's process memory. The dashboard's spawn path already passes config
   by name; extend it to exec `docker compose run` when `SENTINEL_SANDBOX=docker`.
4. **Admin moderation:** an `/admin` view listing users, invites, and running
   scans; admin can suspend a user (immediately blocks new scans and hides
   their reports).
5. **Legal pages:** Terms of Service (authorized testing only, you must own or
   have permission) and a DMCA/abuse contact. This is what keeps the host and
   registrar on your side.

## Phase 4 — Ops

1. **Backups:** nightly `sqlite3 reports/users.db .backup` + tar of `reports/`
   to object storage. The DB is small; reports are the valuable part.
2. **Updates:** `git pull && docker compose build web && docker compose up -d`
   — sessions survive (persisted secret key), in-flight scans finish or die
   with the old container (acceptable for launch).
3. **Monitoring:** `/healthz` on UptimeRobot; log-driven alert if a scan exits
   non-zero more than N times/hour (LLM API key exhaustion is the likely cause).
4. **Cost estimate:** $10–20/mo VPS (Hetzner CX22-class) + domain. NVIDIA API
   usage remains the real variable cost — the dashboard already supports
   `--skip-llm` for quota-free scans.

## Build order (each shippable on its own)

| # | Deliverable | Unblocks |
|---|---|---|
| 1 | `wsgi.py` + gunicorn + `healthz` + secure cookies + ProxyFix | Phase 1 done, deployable behind any TLS proxy |
| 2 | Dockerfile + compose + Caddyfile | A real HTTPS URL |
| 3 | Bootstrap-code signup + invite codes | Public without admin-claim risk |
| 4 | Ownership declaration + private-range block + quotas | Legal to operate |
| 5 | Docker-sandboxed scans + admin view + ToS | Production-grade |
