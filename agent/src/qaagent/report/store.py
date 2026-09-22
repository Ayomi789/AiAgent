"""Persistent scan-report archive on Postgres (Neon/Supabase free tier).

Free hosts wipe local disks on redeploy/sleep, which used to evaporate scan
history. When DATABASE_URL is set, every sealed report is also stored as a
row; on boot, any report missing from the local reports/ directory is
rewritten from the database (JSON artifact verbatim, Markdown/HTML/CSV
regenerated, latest.json repointed). Without DATABASE_URL every function is
a silent no-op and the app behaves exactly as before.

Not archived: live.json (ephemeral by nature) and TestIO bundles/screenshots
(regenerated only when their evidence files exist locally).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scan_reports (
    stamp TEXT PRIMARY KEY,
    target TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL DEFAULT '',
    finished_at TEXT,
    owner_id INTEGER,
    owner_email TEXT,
    report JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


def enabled() -> bool:
    return bool(os.environ.get("DATABASE_URL", "").strip())


def _conn():
    from qaagent.auth import _pg_conn

    return _pg_conn()


def ensure() -> None:
    with _conn() as conn:
        conn.execute(_SCHEMA)


def save_record(stamp: str, report: dict) -> None:
    """Archive one sealed report (best-effort: never fail a scan for this)."""
    if not enabled():
        return
    try:
        ensure()
        with _conn() as conn:
            conn.execute(
                "INSERT INTO scan_reports "
                "(stamp, target, status, started_at, finished_at, "
                "owner_id, owner_email, report) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (stamp) DO NOTHING",
                (
                    stamp,
                    str(report.get("target") or ""),
                    str(report.get("status") or ""),
                    str(report.get("started_at") or ""),
                    str(report.get("finished_at") or ""),
                    report.get("owner_id"),
                    report.get("owner_email"),
                    json.dumps(report),
                ),
            )
    except Exception:
        pass


def list_records() -> list[tuple[str, dict]]:
    """All archived reports as (stamp, report-dict), oldest first."""
    if not enabled():
        return []
    ensure()
    with _conn() as conn:
        rows = conn.execute(
            "SELECT stamp, report FROM scan_reports ORDER BY started_at"
        ).fetchall()
    out: list[tuple[str, dict]] = []
    for row in rows:
        blob = row["report"]
        if isinstance(blob, str):
            try:
                blob = json.loads(blob)
            except ValueError:
                continue
        if isinstance(blob, dict):
            out.append((row["stamp"], blob))
    return out


def rehydrate_reports(reports_dir: Path) -> int:
    """Rewrite missing report artifacts from the archive. Returns count restored."""
    if not enabled():
        print("[sentinel] archive disabled (no DATABASE_URL), skipping restore")
        return 0
    from qaagent.models import Report
    from qaagent.report.generator import (
        _stamp,
        save_report_csv,
        save_report_html,
        save_summary,
    )

    reports_dir = Path(reports_dir)
    try:
        rows = list_records()
    except Exception as exc:
        print(f"[sentinel] archive restore failed: {exc}")
        return 0
    existing = {p.stem[len("report-"):] for p in reports_dir.glob("report-*.json")}
    restored = 0
    newest = None
    for stamp, blob in rows:
        try:
            report = Report.model_validate(blob)
        except Exception:
            continue
        if _stamp(report) != stamp:
            stamp = _stamp(report)
        if stamp in existing:
            continue
        reports_dir.mkdir(parents=True, exist_ok=True)
        json_path = reports_dir / f"report-{stamp}.json"
        json_path.write_text(json.dumps(blob, indent=2), encoding="utf-8")
        from qaagent.report.generator import render_html, render_markdown

        (reports_dir / f"report-{stamp}.md").write_text(
            render_markdown(report), encoding="utf-8"
        )
        try:
            save_report_html(report, reports_dir)
        except Exception:
            pass
        try:
            save_report_csv(report, reports_dir)
        except Exception:
            pass
        existing.add(stamp)
        restored += 1
        newest = report
    if newest is not None:
        try:
            md = reports_dir / f"report-{_stamp(newest)}.md"
            js = reports_dir / f"report-{_stamp(newest)}.json"
            save_summary(newest, reports_dir, md, js)
        except Exception:
            pass
    print(f"[sentinel] archive restore: {restored} report(s) rewritten from Postgres")
    return restored
