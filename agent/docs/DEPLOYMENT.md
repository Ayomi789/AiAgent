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
1. ~~Flask **dev server** is serving the app~~ → **Phase 1 done:** `wsgi.py` +
   WSGI entrypoint shipped; verified under waitress (cross-platform) and
   designed for gunicorn in the Linux container
2. ~~Cookies lack `Secure`~~ → **Phase 1 done:** `SESSION_COOKIE_*` set; token
   cookie gains `Secure` automatically when the request is https (via ProxyFix)
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
  workers is plenty for a single-box launch. (gunicorn is Unix-only — correct
  for the Linux container; on Windows dev machines, waitress serves the same
  `wsgi:app` and was used to verify this entrypoint.)
- **Single VPS + Docker Compose** over Kubernetes/serverless: scans are
  long-running (minutes) and spawn Playwright browsers — containers, not
  serverless. One box runs the web app and the scan workers; split later.
- **Bind gunicorn to `127.0.0.1` inside the Docker network**; only Caddy
  publishes 443/80.

## Phase 1 — Production server ✅ DONE

Shipped:
1. **WSGI entrypoint** — `wsgi.py` at the repo root. Env-driven config:
   - `SENTINEL_DATA_DIR` — root for `reports/` state (default: repo layout)
   - `SENTINEL_TOKEN` — bootstrap token (default: `reports/.dashboard-token`)
   - `NVIDIA_API_KEY` — loaded from env or project `.env`
   Local `sentinel dashboard` is unchanged; `run_dashboard` now wraps a shared
   `build_app_for_serving` factory so both modes get the persisted session key.
2. **Secure cookies behind the proxy** — `create_app` now sets
   `SESSION_COOKIE_SECURE / HTTPONLY / SAMESITE=Lax` and renames the session
   cookie to `sentinel_session`. `werkzeug.ProxyFix(x_for=1, x_proto=1,
   x_host=1)` is installed so `_client_ip()` and redirect URLs trust exactly
   one proxy hop. The dashboard token cookie is emitted with `secure=True`
   whenever `request.scheme == "https"` — plain-HTTP local use unchanged.
3. **`GET /healthz`** — public (auth-gate allowlisted), returns `{"ok": true}`;
   for Caddy and uptime monitors. Everything else stays gated (tested).
4. **Dependency** — `prod = ["gunicorn>=21"]` extra in `pyproject.toml`.

Verified: 90/90 tests (new `test_phase1_healthz_cookies_proxyfix` covers
public healthz, still-gated everything else, cookie flags, ProxyFix scheme
behavior); live dashboard serves `/healthz` → `{"ok": true}`, root → 302,
tokened root → 200 with `Secure; HttpOnly; SameSite=Lax` cookie under a
forwarded-https request; `wsgi:app` served end-to-end by waitress on :8000.

## Phase 2 — Container image + Compose ✅ built (needs a free disk to run)

Files at the repo root:

1. **`Dockerfile`** — `mcr.microsoft.com/playwright/python:v1.49.0-jammy`
   (bundles browser + OS deps — the hard part of containerizing Playwright).
   Copies `agent/pyproject.toml` + `agent/src` and root `wsgi.py`, installs
   `".[prod,targets]"` and the Chromium build matching the base image, runs as
   the image's non-root `pwuser`, sets `BROWSER_CHANNEL=chromium` and
   `SENTINEL_DATA_DIR=/data` + `SENTINEL_CONFIG_DIR=/data/configs`, exposes
   8000 with an image-level HEALTHCHECK on `/healthz`, and launches
   `gunicorn --workers 2 --threads 4 --timeout 600` (threads so a long scan
   doesn't block logins/report downloads; `-t 600` covers slow scan-starts).
2. **`compose.yaml`** — `web` (built image; single bind mount `./data:/data` so
   reports, users.db, tokens, and configs all persist in one host folder;
   `FORWARDED_ALLOW_IPS: caddy` pins the trusted proxy hop for ProxyFix;
   30s stop grace for running scans) + `caddy` (80/443 + HTTP/3, auto-TLS,
   named volumes for cert store, waits for web's healthcheck). All persistent
   state = one directory to back up: `./data`.
3. **`Caddyfile`** — env-driven domain `{$SENTINEL_DOMAIN}`, `reverse_proxy
   web:8000` with a 600s response-header timeout (scan-start spawns Chromium),
   HSTS + nosniff + DENY-frame + Referrer-Policy headers, `-Server`.
4. **`.env.example` → `.env`** (gitignored): `NVIDIA_API_KEY`,
   `SENTINEL_DOMAIN` (must resolve via DNS before first boot), optional
   `SENTINEL_TOKEN` (auto-generated into `data/reports/.dashboard-token`).
5. **`.dockerignore`** — keeps `.env`, `data/`, local `agent/reports/`, and
   site configs out of the image (configs are user state on the volume).

Supporting code change (required for correctness, tested):
`SENTINEL_CONFIG_DIR` — dashboard config listing, auto-create, and the run
subprocess all resolve site configs through one shared resolver
(`_config_dir()` in `qaagent/cli.py`). Locally it is the project root; in the
container it is `/data/configs` on the volume, so dashboard-created configs
survive rebuilds instead of being baked into the image layer.

**Deploy:** `cp .env.example .env` → fill in → `docker compose up -d --build`.
Caddy obtains and renews the certificate automatically.

Verified so far: `docker compose config` valid (volume, env, healthcheck,
port wiring all as above); 92/92 tests; `wsgi:app` proven under a real WSGI
server in Phase 1. **The image build itself is blocked on this dev machine —
the C: drive is 100% full** (the Playwright base image alone is ~2 GB
downloaded / ~8 GB unpacked). Free space (Downloads alone is 10 GB) or build
on any other machine/VPS — the compose stack is ready either way.

## Phase 3 — Launch safety ✅ built (except item 3: sandboxing)

Shipped (120/120 tests, live-verified):

1. **Closed signup** — `signup_policy()` in `qaagent/auth.py`:
   - fresh instance (0 users): signup requires the **dashboard bootstrap
     token** — only the operator who printed the tokened URL can claim the
     admin account (holds even with open signup configured)
   - after that: signup requires a **single-use invite code** minted at
     `/invites` (admin-only page, CSRF-protected generation, used/open list)
   - `SENTINEL_OPEN_SIGNUP=1` bypasses invites for private/firewalled
     deployments (never for the first account)
2. **Authorization-to-scan gate** — `/api/scan` requires `authorized: true`
   (the runbar's "I own / may test this site" checkbox); the declaration is
   stamped onto every report: `authorized_by` / `authorized_at` /
   `authorized_ip` (env → RunConfig → Report, shown in artifacts).
   Technical controls in `qaagent/netpolicy.py` + scan start:
   - **private-target blocking** in public mode (`SENTINEL_PUBLIC_MODE=1`,
     set in compose): loopback, RFC1918, link-local (cloud metadata), CGNAT,
     reserved, multicast, ULA — checked as IP literals AND via DNS so a
     name resolving private (or a rebinding public+private mix) is blocked;
     existing configs are checked by their configured `target`, not their name
   - **per-user daily quota** (`SENTINEL_DAILY_SCAN_LIMIT`, default 20;
     0 disables; bootstrap-token callers exempt); concurrent-scan limit (1)
     already existed

Still open (by design, pre-launch):

3. **Scan isolation in production:** run each scan as the same container image
   but a **separate one-shot container** (`docker compose run --rm`) or at
   minimum a dedicated subprocess user, so a hostile target can't reach the
   web app's process memory. The dashboard's spawn path already passes config
   by name; extend it to exec `docker compose run` when `SENTINEL_SANDBOX=docker`.
4. **Admin moderation:** an `/admin` view listing users, invites, and running
   scans; admin can suspend a user (immediately blocks new scans and hides
   their reports).
5. **Legal pages ✅** — public `/terms` (versioned ToS: authorized testing
   only, no attacking, rate/scope limits, termination, no warranty) and
   `/abuse` (contact channel from `SENTINEL_ABUSE_EMAIL` / `SENTINEL_ABUSE_URL`,
   with an operator hint if unset). Signup requires an explicit consent
   checkbox (server-enforced, recorded per user with IP); scanning is blocked
   for logged-in users whose acceptance is missing or older than
   `TERMS_VERSION` (403 `terms_required`), with one-click re-acceptance wired
   into the run controls; the dashboard footer links both pages. Token
   callers (operator/CI) are exempt.

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

| # | Deliverable | Status |
|---|---|---|
| 1 | `wsgi.py` + gunicorn + `healthz` + secure cookies + ProxyFix | ✅ done |
| 2 | Dockerfile + compose + Caddyfile | next |
| 3 | Bootstrap-code signup + invite codes | — |
| 4 | Ownership declaration + private-range block + quotas | — |
| 5 | Docker-sandboxed scans + admin view + ToS | — |
