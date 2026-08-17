"""Live run state, published as JSON for the dashboard to poll.

The agent updates this file during a run (stage, current action, findings as
they are discovered); `qaagent dashboard` serves it over HTTP.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from qaagent.models import Finding


def _finding_dict(finding: Finding) -> dict:
    return {
        "id": finding.id,
        "severity": finding.severity.value,
        "category": finding.category.value,
        "title": finding.title,
        "url": finding.url,
        "description": finding.description,
        "content_type": finding.content_type,
    }


class LiveState:
    """Writes a small JSON file the dashboard polls for live progress."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.state: dict = {
            "status": "idle",
            "stage": "",
            "target": "",
            "started_at": None,
            "elapsed_seconds": None,
            "current_url": "",
            "last_action": "",
            "recent_actions": [],
            "step": 0,
            "max_steps": 0,
            "findings": [],
            "report_path": None,
        }

    def update(self, **fields: object) -> None:
        self.state.update(fields)
        self._refresh_elapsed()
        self._write()

    def push_action(self, action: str) -> None:
        actions = self.state["recent_actions"]
        actions.append(action)
        self.state["recent_actions"] = actions[-12:]
        self.state["last_action"] = action
        self._refresh_elapsed()
        self._write()

    def set_findings(self, findings: list[Finding]) -> None:
        self.state["findings"] = [_finding_dict(f) for f in findings]
        self._refresh_elapsed()
        self._write()

    def finish(self, status: str, report_path: str | None = None) -> None:
        self.update(
            status=status,
            stage="Finished" if status == "completed" else "Failed",
            report_path=report_path,
        )

    def _refresh_elapsed(self) -> None:
        started = self.state.get("started_at")
        if started and self.state["status"] != "idle":
            try:
                start = datetime.fromisoformat(started)
                self.state["elapsed_seconds"] = round(
                    (datetime.now(timezone.utc) - start).total_seconds()
                )
            except ValueError:
                pass

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=2), encoding="utf-8")
        # Windows: antivirus / the dashboard's poller can briefly lock the
        # destination; retry a few times rather than killing the whole run.
        for attempt in range(4):
            try:
                tmp.replace(self.path)
                return
            except PermissionError:
                if attempt == 3:
                    raise
                time.sleep(0.25 * (attempt + 1))
