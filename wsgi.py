"""Production WSGI entrypoint for the Sentinel dashboard.

Served by gunicorn behind a TLS-terminating reverse proxy:

    gunicorn -w 2 -b 127.0.0.1:8000 wsgi:app

Configuration comes from the environment (see docs/DEPLOYMENT.md):
- SENTINEL_DATA_DIR   root for reports/ state (default: alongside the package)
- SENTINEL_TOKEN      bootstrap token (default: reports/.dashboard-token)
- NVIDIA_API_KEY      LLM key, loaded from the environment or project .env

The local `sentinel dashboard` command is unchanged; this module exists for
hosted deployments only.
"""

from __future__ import annotations

import os
from pathlib import Path

from qaagent.cli import _load_env

_load_env()

_DATA_ROOT = Path(os.environ.get("SENTINEL_DATA_DIR", Path(__file__).resolve().parent / "agent"))
_REPORTS = _DATA_ROOT / "reports"
_REPORTS.mkdir(parents=True, exist_ok=True)
# Dashboard-created site configs must survive container rebuilds - keep them
# on the persistent volume (the CLI's config resolver reads this too).
os.environ.setdefault("SENTINEL_CONFIG_DIR", str(_DATA_ROOT / "configs"))

from qaagent.dashboard import build_app_for_serving, load_or_create_token  # noqa: E402

app = build_app_for_serving(
    _REPORTS / "live.json",
    _REPORTS,
    project_root=_DATA_ROOT,
    auth_token=os.environ.get("SENTINEL_TOKEN") or load_or_create_token(_REPORTS),
)

if __name__ == "__main__":  # pragma: no cover - convenience only
    app.run(host="127.0.0.1", port=8000, debug=False, use_reloader=False)
