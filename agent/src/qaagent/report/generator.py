"""Render and persist reports from the report schema."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from qaagent.models import MachineSummary, Report, SEVERITY_ORDER


def _stamp(report: Report) -> str:
    return report.started_at.strftime("%Y%m%d-%H%M%S")


def render_markdown(report: Report) -> str:
    """Render a full report as Markdown, findings ranked by severity."""
    lines: list[str] = []
    lines.append(f"# QA Agent report — {report.target}")
    lines.append("")
    lines.append(f"- status: **{report.status}**")
    lines.append(f"- started: {report.started_at.isoformat()}")
    if report.finished_at:
        lines.append(f"- finished: {report.finished_at.isoformat()}")
    if report.summary:
        counts = ", ".join(
            f"{sev.value}={report.summary.by_severity.get(sev.value, 0)}"
            for sev in SEVERITY_ORDER
        )
        lines.append(f"- findings: {report.summary.total} ({counts})")
    lines.append("")
    lines.append("## Findings")
    lines.append("")

    if not report.findings:
        lines.append("_No findings._")
    else:
        ordered = sorted(
            report.findings,
            key=lambda f: (SEVERITY_ORDER.index(f.severity), f.detected_at),
        )
        for finding in ordered:
            lines.append(f"### [{finding.severity.value.upper()}] {finding.title}")
            lines.append("")
            lines.append(f"- category: {finding.category.value}")
            lines.append(f"- detected: {finding.detected_at.isoformat()}")
            if finding.url:
                lines.append(f"- url: {finding.url}")
            if finding.description:
                lines.append("")
                lines.append(finding.description)
            if finding.remediation:
                lines.append("")
                lines.append(f"**Remediation:** {finding.remediation}")
            if finding.evidence:
                lines.append("")
                lines.append("Evidence:")
                for ev in finding.evidence:
                    detail = ev.detail or ev.url or ev.file or ""
                    lines.append(f"- {ev.kind}: {detail}")
            lines.append("")
    return "\n".join(lines)


def save_report(report: Report, output_dir: str | Path) -> Path:
    """Write the report to output_dir as Markdown and return its path."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"report-{_stamp(report)}.md"
    path.write_text(render_markdown(report), encoding="utf-8")
    return path


def save_report_json(report: Report, output_dir: str | Path) -> Path:
    """Write the full report as JSON (Pydantic schema) and return its path."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"report-{_stamp(report)}.json"
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return path


def render_html(report: Report) -> str:
    """Render a full report as a self-contained HTML page."""
    severity_colors = {
        "critical": "#dc2626",
        "high": "#ea580c",
        "medium": "#d97706",
        "low": "#2563eb",
        "info": "#6b7280",
    }
    counts = {}
    for f in report.findings:
        counts[f.severity.value] = counts.get(f.severity.value, 0) + 1
    summary_line = " ".join(
        f"<span style='color:{severity_colors.get(s, '#888')};font-weight:700'>{s.upper()}: {counts.get(s, 0)}</span>"
        for s in ["critical", "high", "medium", "low", "info"]
    )
    findings_html = ""
    ordered = sorted(
        report.findings,
        key=lambda f: (SEVERITY_ORDER.index(f.severity), f.detected_at),
    )
    for finding in ordered:
        color = severity_colors.get(finding.severity.value, "#888")
        evidence_items = ""
        for ev in finding.evidence:
            detail = ev.detail or ev.url or ev.file or ""
            evidence_items += f"<li><code>{ev.kind}</code>: {_esc(detail)}</li>"
        evidence_block = f"<ul class='evidence'>{evidence_items}</ul>" if evidence_items else ""
        ct_line = f"<div class='mime'>Content-Type: {_esc(finding.content_type)}</div>" if finding.content_type else ""
        url_line = f"<div class='url'>{_esc(finding.url)}</div>" if finding.url else ""
        rem_line = f"<div class='remediation'><strong>Remediation:</strong> {_esc(finding.remediation)}</div>" if finding.remediation else ""
        findings_html += f"""
        <div class='finding'>
          <div class='finding-header'>
            <span class='badge' style='background:{color}'>{finding.severity.value.upper()}</span>
            <span class='finding-title'>{_esc(finding.title)}</span>
          </div>
          {url_line}
          {ct_line}
          <div class='description'>{_esc(finding.description)}</div>
          {rem_line}
          {evidence_block}
        </div>
        """
    status_color = "#16a34a" if report.status == "completed" else "#dc2626"
    elapsed = ""
    if report.started_at and report.finished_at:
        secs = int((report.finished_at - report.started_at).total_seconds())
        elapsed = f"<span style='color:#6b7280;margin-left:12px'>{secs}s</span>"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>QA Agent Report — {_esc(report.target)}</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: #0f172a; color: #e2e8f0; line-height: 1.6; padding: 24px; }}
  .container {{ max-width: 900px; margin: 0 auto; }}
  h1 {{ font-size: 1.5rem; margin-bottom: 8px; }}
  .meta {{ color: #94a3b8; margin-bottom: 20px; font-size: 0.9rem; }}
  .summary {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 24px; }}
  .summary span {{ font-size: 1.1rem; }}
  .finding {{ background: #1e293b; border-radius: 8px; padding: 16px; margin-bottom: 12px;
              border-left: 4px solid #334155; }}
  .finding-header {{ display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem;
            font-weight: 700; color: #fff; text-transform: uppercase; }}
  .finding-title {{ font-size: 1.05rem; font-weight: 600; }}
  .url {{ color: #60a5fa; font-size: 0.85rem; word-break: break-all; }}
  .mime {{ color: #a78bfa; font-size: 0.8rem; font-family: monospace; margin-top: 2px; }}
  .description {{ color: #cbd5e1; font-size: 0.9rem; margin-top: 6px; }}
  .remediation {{ color: #86efac; font-size: 0.85rem; margin-top: 8px; }}
  .evidence {{ color: #94a3b8; font-size: 0.8rem; margin-top: 6px; padding-left: 18px; }}
  .evidence code {{ background: #334155; padding: 1px 5px; border-radius: 3px; }}
  .empty {{ color: #475569; font-style: italic; padding: 16px; text-align: center; }}
</style>
</head>
<body>
<div class='container'>
  <h1>QA Agent Report</h1>
  <div class='meta'>
    <span>Target: {_esc(report.target)}</span>
    <span style='color:{status_color};margin-left:12px'>● {_esc(report.status.upper())}</span>
    {elapsed}
  </div>
  <div class='summary'>{summary_line}</div>
  <h2 style='font-size:1.1rem;margin-bottom:12px'>Findings ({len(report.findings)})</h2>
  {findings_html if findings_html else '<div class="empty">No findings.</div>'}
</div>
</body>
</html>"""


def _esc(text: str) -> str:
    """Minimal HTML escaping for report content."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\"", "&quot;")
    )


def save_report_html(report: Report, output_dir: str | Path) -> Path:
    """Write the report as a styled HTML file and return its path."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"report-{_stamp(report)}.html"
    path.write_text(render_html(report), encoding="utf-8")
    return path


def save_report_csv(report: Report, output_dir: str | Path) -> Path:
    """Write the report as a CSV file and return its path."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"report-{_stamp(report)}.csv"
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "id", "severity", "category", "title", "url",
        "content_type", "description", "remediation", "detected_at",
    ])
    ordered = sorted(
        report.findings,
        key=lambda f: (SEVERITY_ORDER.index(f.severity), f.detected_at),
    )
    for f in ordered:
        writer.writerow([
            f.id,
            f.severity.value,
            f.category.value,
            f.title,
            f.url or "",
            f.content_type or "",
            f.description,
            f.remediation or "",
            f.detected_at.isoformat(),
        ])
    path.write_text(buf.getvalue(), encoding="utf-8")
    return path


def save_summary(
    report: Report,
    output_dir: str | Path,
    markdown_path: Path | str,
    json_path: Path | str,
) -> Path:
    """Write the stable machine-readable summary to latest.json (overwrites)."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary = MachineSummary.from_report(
        report, report_markdown=str(markdown_path), report_json=str(json_path)
    )
    path = out / "latest.json"
    path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
    return path
