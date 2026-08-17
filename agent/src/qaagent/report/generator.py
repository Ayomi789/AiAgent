"""Render and persist reports from the report schema."""

from __future__ import annotations

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
