# Vulnerable demo app

A deliberately-insecure Flask app that serves as the QA agent's first **safe**
test target. It runs locally, seeds its own SQLite database on start, and every
flaw is listed here so we know exactly what the agent should find.

## Run

```bash
# from agent/ (after `pip install -e ".[targets]"`):
.venv/Scripts/python targets/vulnerable_app/app.py
# or: python targets/vulnerable_app/app.py   (if flask is installed)
```

Serves on http://127.0.0.1:5001 (`PORT` env var overrides).

## The flaws and how to trigger them

| # | Flaw | Severity | Where | Trigger |
|---|------|----------|-------|---------|
| 1 | Reflected XSS | high | `/search?q=` | `/search?q=<script>alert(1)</script>` |
| 2 | SSTI (Jinja) | high | `/search?q=` | `/search?q={{7*7}}` shows `49` |
| 3 | SQL injection (search) | high | `/search?q=` | `/search?q=' OR '1'='1` returns all notes |
| 4 | SQL injection (login) | critical | `/login` POST | username `admin' -- ` + any password |
| 5 | IDOR / missing authz | high | `/profile?id=` | `/profile?id=2` without logging in |
| 6 | Broken access control | critical | `/admin` | visit `/admin` without logging in |
| 7 | Information disclosure | medium | `/debug` | visit `/debug` (env + secret key) |
| 8 | Open redirect | medium | `/redirect?next=` | `/redirect?next=https://evil.example` |
| 9 | Weak session cookie | medium | all | `curl -I` — `session=` cookie lacks `HttpOnly`/`Secure`/`SameSite` |
| 10 | Missing security headers | medium | all | no `Content-Security-Policy`, `X-Frame-Options`, `HSTS` |
| 11 | Weak password hashing | high | `/admin` | md5, unsalted, exposed in the admin table |
| 12 | Hardcoded secret key | high | `/debug` | secret key shipped in source + dumped at `/debug` |
| 13 | Reflected XSS (login error) | medium | `/login` POST | username `<img src=x onerror=alert(1)>` fails login |
| 14 | No rate limiting on login | low | `/login` POST | unlimited login attempts |

## Notes for the agent

- The app seeds demo users `alice/alice123` and `admin/admin123` (md5 hashes).
- The whole app is wrapped in a helper that deliberately does **not** escape
  output, so anything reflected is rendered raw.
- Flaws 1–2 come from the same code path: the search page echoes `q` and runs
  it through Jinja.
- Expected findings total ~14 across critical/high/medium/low when all are
  exercised — a good acceptance bar for the agent's first full run.
