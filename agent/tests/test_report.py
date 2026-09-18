"""Report generator and live-state tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from qaagent.live import LiveState
from qaagent.models import Evidence, Finding, FindingCategory, Report, Severity
from qaagent.report.generator import (
    render_html,
    render_markdown,
    render_testio_bug,
    save_report,
    save_report_csv,
    save_report_html,
    save_report_json,
    save_report_testio,
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


def _testio_report() -> Report:
    now = datetime.now(timezone.utc)
    finding = Finding(
        title="Reflected XSS in /search",
        severity=Severity.HIGH,
        category=FindingCategory.SECURITY,
        description="Payload '<script>alert(1)</script>' is echoed back unescaped.",
        url="http://x.test/search?q=<script>",
        remediation="Escape all user input when rendering.",
        evidence=[
            Evidence(kind="http_response", detail="payload reflected in 200 response"),
            Evidence(kind="screenshot", file="shot.png"),
        ],
        detected_at=now,
    )
    report = Report(target="http://x.test", started_at=now, finished_at=now, findings=[finding])
    report.summary = report.build_summary()
    return report


def test_testio_bug_has_all_required_fields():
    text = render_testio_bug(_testio_report(), _testio_report().findings[0])
    for field in (
        "**Feature:**",
        "**Severity:** High",
        "**Title:**",
        "**URL:**",
        "## Steps to reproduce",
        "## Actual result",
        "## Expected result",
        "## Attachment",
        "## Used environment",
    ):
        assert field in text, f"missing {field!r}"


def test_testio_bug_step1_opens_target():
    """Test IO requires step 1 to be opening the site root."""
    report = _testio_report()
    text = render_testio_bug(report, report.findings[0])
    assert "1. Open http://x.test" in text


def test_testio_severity_mapping():
    """Only Low/High/Critical exist in Test IO; info/medium/low map to Low."""
    from qaagent.report.generator import _TESTIO_SEVERITY

    assert _TESTIO_SEVERITY["critical"] == "Critical"
    assert _TESTIO_SEVERITY["high"] == "High"
    assert _TESTIO_SEVERITY["medium"] == "Low"
    assert _TESTIO_SEVERITY["info"] == "Low"


def test_save_report_testio_writes_per_finding_files():
    import tempfile
    from pathlib import Path

    report = _testio_report()
    with tempfile.TemporaryDirectory() as tmp:
        bug_dir = save_report_testio(report, tmp)
        files = sorted(Path(bug_dir).glob("*.md"))
        # one per finding + the index
        assert len(files) == 2
        assert (Path(bug_dir) / "00-INDEX.md").exists()
        per_finding = [f for f in files if f.name != "00-INDEX.md"][0]
        content = per_finding.read_text(encoding="utf-8")
        assert "Test IO format" in content
        assert "high" in per_finding.name  # severity in the filename


def test_render_html_ranks_by_severity():
    html = render_html(_report())
    assert html.index("CRITICAL") < html.index("LOW")
    assert "<html" in html
    assert "No findings" not in html


def test_render_html_empty():
    report = Report(target="http://x.test")
    assert "No findings" in render_html(report)


def test_render_html_shows_content_type():
    report = Report(
        target="http://x.test",
        findings=[
            Finding(
                title="Sensitive file",
                severity=Severity.MEDIUM,
                category=FindingCategory.SECURITY,
                content_type="application/sql",
            )
        ],
    )
    html = render_html(report)
    assert "application/sql" in html


def test_render_html_escapes_special_chars():
    report = Report(
        target="http://x.test",
        findings=[
            Finding(
                title="XSS <script>alert(1)</script>",
                severity=Severity.HIGH,
                category=FindingCategory.SECURITY,
                description="Uses \"quotes\" and <tags>",
            )
        ],
    )
    html = render_html(report)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_save_html_and_csv(tmp_path):
    report = _report()
    html_path = save_report_html(report, tmp_path)
    csv_path = save_report_csv(report, tmp_path)
    assert html_path.exists()
    assert csv_path.exists()
    assert html_path.suffix == ".html"
    assert csv_path.suffix == ".csv"
    assert html_path.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    non_empty = [l for l in lines if l.strip()]
    assert len(non_empty) == 3  # header + 2 findings
    assert non_empty[0].startswith("id,severity")


def test_csv_content_type_present(tmp_path):
    report = Report(
        target="http://x.test",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        findings=[
            Finding(
                title="Sensitive file",
                severity=Severity.MEDIUM,
                category=FindingCategory.SECURITY,
                content_type="application/json",
            )
        ],
    )
    report.summary = report.build_summary()
    csv_path = save_report_csv(report, tmp_path)
    text = csv_path.read_text(encoding="utf-8")
    assert "application/json" in text


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
