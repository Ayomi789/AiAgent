# QA Agent

AI agent that tests websites and apps for **vulnerabilities**, **bugs**, and
**broken functionality**. See `ARCHITECTURE.md` at the repo root for the full
design; this project is the implementation.

## Layout

```
agent/
  pyproject.toml            # package metadata + dependencies
  config.example.yml        # example run configuration
  src/qaagent/
    cli.py                  # qaagent CLI (run, init-config)
    config.py               # Pydantic run config + YAML loading
    models.py               # finding/report schemas (single source of truth)
    agent/core.py           # observe -> think -> act -> verify loop (skeleton)
    tools/registry.py       # deterministic tool surface for the LLM
    browser/                # Playwright driver (next milestone)
    probe/                  # HTTP-level security checks (next milestone)
    report/generator.py     # findings -> Markdown report
  targets/vulnerable_app/   # deliberately-vulnerable local test target
```

## Quick start

```bash
cd agent
python -m venv .venv
.venv/Scripts/pip install -e ".[dev,targets]"
.venv/Scripts/qaagent --help
```

> On Linux/macOS the venv binaries live in `.venv/bin/` instead of `.venv/Scripts/`.

## API key

The agent talks to an OpenAI-compatible LLM API (NVIDIA build.nvidia.com by
default). Set your key in an environment variable named by `llm.api_key_env`
(`NVIDIA_API_KEY`), or create `agent/.env`:

```
NVIDIA_API_KEY=nvapi-...
```

## Run the local test target

```bash
.venv/Scripts/python targets/vulnerable_app/app.py
# serves on http://127.0.0.1:5001
```

Then run the agent against it:

```bash
.venv/Scripts/qaagent init-config
.venv/Scripts/qaagent run --config config.yml
```

### Per-site configs and shorthand names

Keep one config per site (e.g. `config.solnew.yml`) and pass a short name —
the CLI resolves `solnew` → `config.solnew.yml`, then `solnew.yml`:

```bash
.venv/Scripts/qaagent run --config solnew            # finds config.solnew.yml
.venv/Scripts/qaagent run --config solnew --skip-llm
.venv/Scripts/qaagent run --config config.solnew.yml  # full path still works
```

## Quick start

The CLI is called **Sentinel**. Once the venv's `Scripts` folder is on your
PATH (it is, if `sentinel --help` works in a fresh terminal), you can run it
from any directory:

```bash
sentinel run --config solnew --skip-llm   # global command
qaagent run --config solnew --skip-llm    # internal alias (used by CI)
python -m sentinel run --config solnew    # module form
```

Reports always land in the same place regardless of the working directory:
`output_dir` is resolved relative to the **config file's** folder (so the
project's `reports/`), not the terminal's cwd.

**New site? No config needed** — pass the bare domain and Sentinel creates
`config.<domain>.yml` for you and scans it:

```bash
sentinel run --config stylesbytiwa.netlify.app --skip-llm
# -> creates config.stylesbytiwa.netlify.app.yml (auto-scoped to the site)
```

Or create it explicitly (then edit in credentials / sensitive files):

```bash
sentinel init-config --name stylesbytiwa --target https://stylesbytiwa.netlify.app
```

## Watch a run live (dashboard)

Start the dashboard in one terminal, then run the agent in another:

```bash
.venv/Scripts/qaagent dashboard            # http://127.0.0.1:5050
.venv/Scripts/qaagent run --config config.yml
```

The dashboard shows the current stage, recent tool actions, and findings as
they are discovered (polling `reports/live.json`), then the full report when
the run finishes. It also shows a **findings diff vs the previous run**
(new / fixed / unchanged, matched by title+URL across the JSON reports).
Flags: `--port`, `--state`, `--reports` (must match where the agent writes,
e.g. if you set a custom `output_dir`).

## Tuning runs (deterministic only)

Iterating on probe settings costs LLM quota, so tuning runs can skip the
model and the browser entirely — just the deterministic probes (passive
headers/cookies + active XSS/SQLi/SSTI/login-bypass/IDOR/open-redirect/
sensitive-path probes), in seconds:

```bash
.venv/Scripts/qaagent run --config config.yml --skip-llm
```

No API key needed, no browser launch, and findings land in the same report
format (so `--fail-on` / `--baseline-on` and the dashboard diff all work on
tuning runs too). Set `skip_llm: true` in the config instead of the flag to
make it the default for a target.

## Tracking findings across releases

The baseline gate is designed to catch **newly introduced** vulnerabilities
between releases, not just the current state. The loop mirrors what the CI
workflow does with its cache (previous run's report = baseline):

```bash
# Release 1: establish the baseline (first run has no previous report -> passes)
qaagent run --config config.yml --skip-llm --baseline-on medium
# -> exit 0

# Release 2: a regression ships (e.g. /backup.sql appears in the web root)
qaagent run --config config.yml --skip-llm --baseline-on medium
# -> exit 3, "New findings vs baseline: 1 ... Sensitive file exposed: /backup.sql"

# Release 3: the regression is fixed
qaagent run --config config.yml --skip-llm --baseline-on medium
# -> exit 0; the dashboard /api/diff shows the finding as FIXED
```

The sensitive-file probe (`backup.sql`, `dump.sql`, `db.sqlite3`, `.env.bak`,
`private_key.pem`, ... ~60 names) exists specifically so this comparison
catches *classes* of newly-shipped files, not just known endpoints. It
confirms content before reporting: a plain 200 is not enough — the response
must match the expected kind by magic bytes (SQLite/zip/gzip/rar/7z/tar),
SQL markers, env-var pairs, or a PEM header, and must not be HTML (so an SPA
catch-all that serves `index.html` for `/backup.sql` is ignored). Bodies are
capped at 64 KiB so backups are never downloaded whole. The wordlist is
configurable: add site-specific artifact names under `agent.sensitive_files`
in `config.yml`, each mapped to a validation kind (`sql|sqlite|archive|env|key|git|text`):

```yaml
agent:
  sensitive_files:
    /secrets.tar.gz: archive   # added to the ~60 built-in names
    /deploy.key: key
```

The sensitive-endpoint
probe validates its responses the same way: HTML panels (`/admin`, `/debug`)
must differ from the site's own homepage (an SPA serves the same index.html
for any path — a fallback, not an exposed panel), text artifacts (`/.git/config`,
`/.env`) must actually match their content, and a 200 that is merely a login
form or an empty body is expected, not an exposure.

Sensitive-path discovery is not limited to the web root: the crawl records
which pages actually loaded, derives their directory prefixes (up to 2 levels,
capped at 6 directories), and probes each one for the same artifact classes
— `.env` / `.git/config` / `backup.sql` / `db.sqlite3` / `private_key.pem`
etc., plus `admin` and `debug` panels. All the same content validation
applies, so an SPA catch-all that serves index.html under a subdirectory is
still ignored. Config-supplied `sensitive_files` names are probed under
subdirectories too.

## Tests

Smoke-test suite in `agent/tests/` covering the probes (run against the
vulnerable demo app on a random port), diff logic, config, collector
deduplication, and the report/live-state writers:

```bash
.venv/Scripts/pip install -e "agent[dev]"
.venv/Scripts/python -m pytest agent/tests -q
```

## CI integration

Each run writes three artifacts into `reports/`:

| File | Contents |
|---|---|
| `report-<timestamp>.md` | Human-readable report |
| `report-<timestamp>.json` | Full report (Pydantic schema) |
| `latest.json` | Stable machine-readable summary (always this path) |

Use `--fail-on` to gate a pipeline on findings — the exit code is non-zero
when any finding is at or above the given severity. Use `--baseline-on` to
gate on **regressions** — new findings versus the previous run:

```bash
.venv/Scripts/qaagent run --config config.yml --fail-on high
code=$?   # 0 = pass, 1 = critical/high findings, 2 = bad arguments

.venv/Scripts/qaagent run --config config.yml --baseline-on medium
code=$?   # 0 = pass, 3 = new findings at/above medium vs the previous run
cat reports/latest.json   # consume in CI/dashboards
```

Exit codes: `0` pass, `1` findings at/above `--fail-on`, `2` bad arguments,
`3` regressions at/above `--baseline-on`. To diff against a pinned baseline
instead of the previous run, pass `--baseline path/to/report-....json`.
The first run (no previous report) always passes the baseline check.

### GitHub Actions

`.github/workflows/qa-agent.yml` runs the agent on push/PR (when `agent/**`
changes) and on `workflow_dispatch`. It gates on both `--fail-on high` and
`--baseline-on high`, carries the baseline between runs via the action cache,
and posts the findings + diff as a PR comment. Setup required in the repo:

- Secret `NVIDIA_API_KEY` (the LLM key)
- Variable `QA_TARGET_URL` (the target to scan) — or pass a `target` input
  via workflow_dispatch
- Optional secrets `QA_USERNAME` / `QA_PASSWORD` for login flows

CI uses `agent/config.ci.yml` (empty scope = auto-scope to the target;
`browser_channel: chromium` since GitHub runners have no Edge).

`latest.json` contains target, status, elapsed seconds, counts by severity and
category, paths of the full artifacts, and a compact list of findings
(severity, category, title, url).

## Notes

- The browser driver uses the system Edge (`browser_channel: msedge`) so no
  browser download is needed. To use Playwright's own Chromium instead, run
  `playwright install chromium` and set `browser_channel: chromium`.
- Reports are written to `reports/` as Markdown, with screenshots in
  `reports/evidence/` (JSON export is a planned next step).
