"""Pre-flight checks for a Sentinel installation.

`sentinel doctor` runs these before you trust a scan:

- Data paths: reports dir, live state, user store, dashboard token
- Config health: every config*.yml parses; none references a retired model
- LLM: API key present, configured model actually answers AND makes tool calls
  (the exact failure mode that silently broke runs twice: listed-but-dead models)
- Target: the configured site resolves and answers over HTTP

Exit code is 0 when no check fails, 1 otherwise - usable in CI or scripts.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

from qaagent.config import DEFAULT_LLM_MODEL, RETIRED_LLM_MODELS, LLMConfig, RunConfig


@dataclass
class Check:
    """One doctor result: ok / warn / fail plus a human detail line."""

    name: str
    status: str  # "ok" | "warn" | "fail"
    detail: str


def check_data_paths(project_root: Path, reports_dir: Path) -> list[Check]:
    """Reports directory and the state living inside it."""
    checks: list[Check] = []
    reports_dir = Path(reports_dir)
    if not reports_dir.is_dir():
        checks.append(
            Check(
                "data paths",
                "warn",
                f"{reports_dir} does not exist yet - created on first run/scan",
            )
        )
        return checks

    n_reports = len(list(reports_dir.glob("report-*.json")))
    extras: list[str] = []
    if (reports_dir / "live.json").exists():
        extras.append("live state")
    users_db = reports_dir / "users.db"
    if users_db.exists():
        try:
            import sqlite3

            con = sqlite3.connect(users_db)
            try:
                n_users = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            finally:
                con.close()
            extras.append(f"{n_users} account(s)")
        except Exception:
            extras.append("user store (unreadable)")
    if (reports_dir / ".dashboard-token").exists():
        extras.append("dashboard token")
    checks.append(
        Check(
            "data paths",
            "ok",
            f"reports dir {reports_dir} ({n_reports} run(s)"
            + (f"; {', '.join(extras)}" if extras else "")
            + ")",
        )
    )
    return checks


def check_configs(project_root: Path, deep_path: Path | None = None) -> list[Check]:
    """Parse every config*.yml in the project; fail on retired models."""
    checks: list[Check] = []
    paths = sorted(Path(project_root).glob("config*.yml"))
    if deep_path is not None:
        deep_resolved = Path(deep_path).resolve()
        if deep_resolved not in {p.resolve() for p in paths}:
            paths.append(Path(deep_path))
    if not paths:
        checks.append(
            Check("configs", "warn", "no config*.yml files - runs need --config or a site name")
        )
        return checks

    broken = 0
    stale = 0
    details: list[str] = []
    for path in paths:
        try:
            cfg = RunConfig.from_yaml(path)
        except Exception as exc:
            broken += 1
            details.append(f"{path.name}: {str(exc)[:80]}")
            continue
        model = cfg.llm.model if cfg.llm else DEFAULT_LLM_MODEL
        if any(retired in model for retired in RETIRED_LLM_MODELS):
            stale += 1
            details.append(f"{path.name}: retired model {model!r}")
    if broken or stale:
        checks.append(
            Check(
                "configs",
                "fail",
                f"{len(paths) - broken - stale}/{len(paths)} healthy"
                + (f"; {'; '.join(details)}" if details else ""),
            )
        )
    else:
        checks.append(
            Check("configs", "ok", f"{len(paths)} config(s) parse clean, no retired models")
        )
    return checks


def probe_llm(cfg: LLMConfig | None = None) -> Check:
    """Live probe: does the configured model answer AND make a tool call?

    A plain chat answer is not enough - the agent loop lives on tool calls,
    and both model incidents (410 llama, 404 glm) passed casual checks
    until a tool call was attempted.
    """
    cfg = cfg or LLMConfig()
    key = os.environ.get(cfg.api_key_env) if cfg.api_key_env else None
    if not key:
        return Check(
            "llm",
            "fail",
            f"no API key in ${cfg.api_key_env} (agent/.env or environment)",
        )
    url = f"{cfg.api_base.rstrip('/')}/chat/completions"
    payload = {
        "model": cfg.model,
        "messages": [
            {"role": "user", "content": "Use the tool to fetch https://example.com"}
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_page",
                    "description": "Fetch a page by URL",
                    "parameters": {
                        "type": "object",
                        "properties": {"url": {"type": "string"}},
                        "required": ["url"],
                    },
                },
            }
        ],
        "tool_choice": "auto",
        "max_tokens": 128,
        "temperature": 0,
    }
    headers = {"Authorization": f"Bearer {key}"}
    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=30)
    except httpx.TimeoutException:
        return Check("llm", "fail", f"{cfg.model} timed out after 30s")
    except httpx.HTTPError as exc:
        return Check("llm", "fail", f"{cfg.api_base} unreachable: {str(exc)[:120]}")

    if resp.status_code == 404:
        return Check(
            "llm",
            "fail",
            f"{cfg.model} is not routable (404) - retired or not enabled on this account",
        )
    if resp.status_code in (401, 403):
        return Check("llm", "fail", f"API key rejected ({resp.status_code})")
    if resp.status_code >= 400:
        return Check("llm", "fail", f"HTTP {resp.status_code}: {resp.text[:140]}")
    try:
        msg = resp.json()["choices"][0]["message"]
    except Exception:
        return Check("llm", "fail", "unexpected response shape from the API")
    if msg.get("tool_calls"):
        return Check("llm", "ok", f"{cfg.model} reachable, tool-calling works")
    content = (msg.get("content") or "").strip()[:40]
    return Check(
        "llm",
        "warn",
        f"{cfg.model} answered but made no tool call (content: {content!r}) - "
        "the agent loop needs tool-calling",
    )


def check_target(url: str) -> Check:
    """Can we reach the target at all? Any HTTP response counts as reachable."""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return Check("target", "fail", f"{url!r} is not a valid http(s) URL")
    try:
        resp = httpx.get(
            url if "://" in url else f"https://{url}",
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": "sentinel-doctor/1.0"},
        )
    except httpx.ConnectError as exc:
        return Check("target", "fail", f"{parsed.hostname} unreachable: {str(exc)[:100]}")
    except httpx.TimeoutException:
        return Check("target", "fail", f"{parsed.hostname} timed out after 15s")
    except httpx.HTTPError as exc:
        return Check("target", "fail", f"{str(exc)[:120]}")
    if resp.status_code >= 400:
        return Check(
            "target",
            "warn",
            f"{parsed.hostname} reachable but returned HTTP {resp.status_code}",
        )
    return Check("target", "ok", f"{parsed.hostname} answers HTTP {resp.status_code}")


def run_checks(
    project_root: Path,
    reports_dir: Path,
    config_path: Path | None = None,
    target: str | None = None,
    probe_model: bool = True,
) -> list[Check]:
    """Run every check; return the list for the CLI to render."""
    checks: list[Check] = []
    checks.extend(check_data_paths(project_root, reports_dir))
    checks.extend(check_configs(project_root, deep_path=config_path))

    llm_cfg: LLMConfig | None = None
    if config_path is not None:
        try:
            llm_cfg = RunConfig.from_yaml(Path(config_path)).llm
        except Exception:
            llm_cfg = None  # parse errors are already reported by check_configs
    if probe_model:
        checks.append(probe_llm(llm_cfg))
    else:
        checks.append(Check("llm", "ok", "skipped (--skip-llm)"))

    target_url = target
    if target_url is None and config_path is not None:
        try:
            target_url = RunConfig.from_yaml(Path(config_path)).target
        except Exception:
            target_url = None
    if target_url:
        checks.append(check_target(target_url))
    return checks


def failed(checks: list[Check]) -> int:
    """Number of failed checks - the CLI's exit code."""
    return sum(1 for c in checks if c.status == "fail")
