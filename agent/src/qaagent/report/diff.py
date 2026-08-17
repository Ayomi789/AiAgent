"""Diff findings across runs — shared by the dashboard and the CLI baseline mode.

Findings are matched by (title, url), which is stable across runs (finding ids
are regenerated every run).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class FindingsDiff:
    latest_run: str | None
    previous_run: str | None
    new: list[dict]
    fixed: list[dict]
    unchanged: list[dict]
    counts: dict[str, int] = field(default_factory=dict)


def load_report_files(reports_dir: str | Path) -> list[dict]:
    """All report-*.json files in the directory, oldest first."""
    files = sorted(Path(reports_dir).glob("report-*.json"))
    loaded: list[dict] = []
    for f in files:
        try:
            loaded.append(json.loads(f.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return loaded


def _same_timestamp(a: str | None, b: str | None) -> bool:
    """Compare ISO timestamps regardless of 'Z' vs '+00:00' formatting."""
    if a is None or b is None:
        return a == b
    try:
        return datetime.fromisoformat(a) == datetime.fromisoformat(b)
    except ValueError:
        return a == b


def previous_report(
    reports_dir: str | Path, exclude_started_at: str | None = None
) -> dict | None:
    """The run before the latest, optionally excluding a specific run (e.g. the
    one that just finished)."""
    reports = load_report_files(reports_dir)
    if exclude_started_at:
        reports = [
            r for r in reports if not _same_timestamp(r.get("started_at"), exclude_started_at)
        ]
    return reports[-1] if reports else None


def finding_key(f: dict) -> tuple[str, str]:
    """Stable identity for a finding across runs (title + url)."""
    return (str(f.get("title", "")), str(f.get("url") or ""))


def compact_findings(findings: list[dict]) -> list[dict]:
    return [
        {
            "severity": f.get("severity"),
            "category": f.get("category"),
            "title": f.get("title"),
            "url": f.get("url"),
        }
        for f in findings
    ]


def compare_reports(latest: dict, previous: dict | None) -> FindingsDiff:
    """Categorize the latest run's findings vs the previous run."""
    latest_keys = {finding_key(f) for f in latest.get("findings", [])}
    prev_keys = (
        {finding_key(f) for f in previous.get("findings", [])} if previous else set()
    )
    new = [f for f in latest.get("findings", []) if finding_key(f) not in prev_keys]
    unchanged = [f for f in latest.get("findings", []) if finding_key(f) in prev_keys]
    fixed = (
        [f for f in previous.get("findings", []) if finding_key(f) not in latest_keys]
        if previous
        else []
    )
    return FindingsDiff(
        latest_run=latest.get("started_at"),
        previous_run=previous.get("started_at") if previous else None,
        new=compact_findings(new),
        fixed=compact_findings(fixed),
        unchanged=compact_findings(unchanged),
        counts={"new": len(new), "fixed": len(fixed), "unchanged": len(unchanged)},
    )
