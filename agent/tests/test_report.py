"""Report generator and live-state tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from qaagent.live import LiveState
from qaagent.models import Finding, FindingCategory, Report, Severity
from qaagent.report.generator import (
    render_markdown,
    save_report,
    save_report_json,
    save_summary,
)


def _report() -> Report:
    now = datetime.now(timezone.utc)
    report = Report(
        target="http://x.test",
        started_at=now,
        finished_at=now,
        findings=[
            Finding(title="Low thing", severity=Severity.LOW, category=FindingCategory.SECURITY),
            Finding(title="Critical thing", severity=Severity.CRITICAL, category=FindingCategory.SECURITY),
        ],
    )
    report.summary = report.build_summary()
    return report


def test_render_markdown_ranks_by_severity():
    md = render_markdown(_report())
    assert md.index("[CRITICAL]") < md.index("[LOW]")
    assert "No findings" not in md


def test_render_markdown_empty():
    report = Report(target="http://x.test")
    assert "No findings" in render_markdown(report)


def test_save_artifacts(tmp_path):
    report = _report()
    md = save_report(report, tmp_path)
    js = save_report_json(report, tmp_path)
    summary = save_summary(report, tmp_path, md, js)
    assert md.exists() and js.exists() and summary.exists()

    data = json.loads(summary.read_text(encoding="utf-8"))
    assert data["findings_total"] == 2
    assert data["by_severity"]["critical"] == 1
    assert data["report_json"] == str(js)
    assert data["report_markdown"] == str(md)
    assert len(data["findings"]) == 2

    full = json.loads(js.read_text(encoding="utf-8"))
    assert len(full["findings"]) == 2


def test_content_type_roundtrips_through_artifacts(tmp_path):
    now = datetime.now(timezone.utc)
    report = Report(
        target="http://x.test",
        started_at=now,
        finished_at=now,
        findings=[
            Finding(
                title="Sensitive file exposed: /backup.sql",
                severity=Severity.MEDIUM,
                category=FindingCategory.SECURITY,
                content_type="application/sql",
            )
        ],
    )
    report.summary = report.build_summary()

    js = save_report_json(report, tmp_path)
    full = json.loads(js.read_text(encoding="utf-8"))
    assert full["findings"][0]["content_type"] == "application/sql"

    # Old reports without the field still parse (backward compatible).
    js.write_text(
        json.dumps({"target": "http://x.test", "findings": [{"title": "t", "severity": "low", "category": "security"}]}),
        encoding="utf-8",
    )
    from qaagent.report.diff import load_report_files

    loaded = load_report_files(tmp_path)
    assert loaded and loaded[-1]["findings"][0].get("content_type") is None


def test_live_state_roundtrip(tmp_path):
    live = LiveState(tmp_path / "live.json")
    live.update(status="running", stage="Probes", target="http://x.test")
    live.push_action("click Login")
    live.finish("completed", report_path="reports/x.md")
    data = json.loads((tmp_path / "live.json").read_text(encoding="utf-8"))
    assert data["status"] == "completed"
    assert data["stage"] == "Finished"
    assert data["recent_actions"] == ["click Login"]
    assert data["target"] == "http://x.test"
    assert data["report_path"] == "reports/x.md"
