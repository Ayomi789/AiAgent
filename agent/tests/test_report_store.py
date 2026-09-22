"""Archive/rehydrate path: files rebuilt from stored rows (no Postgres needed)."""

from __future__ import annotations

import json

from qaagent.models import Report
from qaagent.report import store as _store


def _blob(target="https://x.test"):
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    return {
        "target": target,
        "status": "completed",
        "started_at": now,
        "finished_at": now,
        "summary": {
            "total": 0,
            "by_severity": {},
            "by_category": {},
        },
        "findings": [],
    }


def test_rehydrate_restores_missing_artifacts(tmp_path, monkeypatch):
    blob = _blob()
    stamp = blob["started_at"].replace("-", "").replace(":", "")[:15].replace("T", "-")
    monkeypatch.setattr(_store, "enabled", lambda: True)
    monkeypatch.setattr(_store, "list_records", lambda: [(stamp, blob)])
    n = _store.rehydrate_reports(tmp_path)
    assert n == 1
    assert (tmp_path / f"report-{stamp}.json").exists()
    assert (tmp_path / f"report-{stamp}.md").exists()
    assert (tmp_path / f"report-{stamp}.html").exists()
    assert (tmp_path / f"report-{stamp}.csv").exists()
    assert (tmp_path / "latest.json").exists()
    # Second pass restores nothing (idempotent).
    assert _store.rehydrate_reports(tmp_path) == 0


def test_rehydrate_skips_invalid_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(_store, "enabled", lambda: True)
    monkeypatch.setattr(
        _store, "list_records", lambda: [("bad", {"nope": True}), ("alsobad", "junk")]
    )
    assert _store.rehydrate_reports(tmp_path) == 0


def test_save_record_noop_without_database_url(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    _store.save_record("x", _blob())  # must not raise, must not write
    assert list(tmp_path.glob("*")) == []


def test_report_model_roundtrip_for_archive():
    blob = _blob()
    report = Report.model_validate(blob)
    assert report.target == "https://x.test"
    assert json.loads(json.dumps(blob))["status"] == "completed"
