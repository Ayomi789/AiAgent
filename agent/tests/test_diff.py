"""Diff tests: new/fixed/unchanged categorization and baseline selection."""

from __future__ import annotations

import json

from qaagent.report.diff import compare_reports, finding_key, previous_report


def _report(started_at: str, findings: list[dict]) -> dict:
    return {"started_at": started_at, "findings": findings}


def _f(title: str, url: str, severity: str = "high") -> dict:
    return {"title": title, "url": url, "severity": severity, "category": "security"}


def test_compare_reports_categorizes():
    prev = _report(
        "2026-08-17T00:00:00Z",
        [_f("A", "/a"), _f("B", "/b"), _f("C", "/c")],
    )
    latest = _report(
        "2026-08-17T01:00:00Z",
        [_f("A", "/a"), _f("C", "/c"), _f("D", "/d")],
    )
    diff = compare_reports(latest, prev)
    assert diff.counts == {"new": 1, "fixed": 1, "unchanged": 2}
    assert [f["title"] for f in diff.new] == ["D"]
    assert [f["title"] for f in diff.fixed] == ["B"]
    assert [f["title"] for f in diff.unchanged] == ["A", "C"]


def test_first_run_has_no_fixed():
    diff = compare_reports(_report("t", [_f("A", "/a")]), None)
    assert diff.counts == {"new": 1, "fixed": 0, "unchanged": 0}


def test_previous_report_handles_z_and_offset_timestamps(tmp_path):
    """'Z' and '+00:00' must be treated as the same instant (regression test)."""
    a = _report("2026-08-17T00:00:00Z", [])
    b = _report("2026-08-17T01:00:00Z", [])
    (tmp_path / "report-1.json").write_text(json.dumps(a))
    (tmp_path / "report-2.json").write_text(json.dumps(b))
    prev = previous_report(tmp_path, exclude_started_at="2026-08-17T01:00:00+00:00")
    assert prev is not None
    assert prev["started_at"] == "2026-08-17T00:00:00Z"


def test_previous_report_returns_none_when_empty(tmp_path):
    assert previous_report(tmp_path) is None


def test_finding_key_stable():
    assert finding_key({"title": "X", "url": "/a"}) == finding_key(
        {"title": "X", "url": "/a"}
    )
    assert finding_key({"title": "X", "url": "/a"}) != finding_key(
        {"title": "Y", "url": "/a"}
    )
