"""Finding and report schemas — the single source of truth for agent output.

Everything the agent reports flows through these models, so the report format
stays stable whether it is rendered as Markdown, JSON, or fed to CI later.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# Display/ranking order, most severe first.
SEVERITY_ORDER = [
    Severity.CRITICAL,
    Severity.HIGH,
    Severity.MEDIUM,
    Severity.LOW,
    Severity.INFO,
]


class FindingCategory(str, Enum):
    SECURITY = "security"
    FUNCTIONAL = "functional"
    BUG = "bug"
    INFO = "info"


class Evidence(BaseModel):
    """Proof attached to a finding: screenshot, DOM snapshot, HTTP response, note."""

    kind: str = Field(description="screenshot | dom_snapshot | http_response | console | note")
    url: str | None = None
    file: str | None = None
    detail: str | None = None


class Finding(BaseModel):
    """A single observed issue: security vulnerability, bug, or broken function."""

    title: str
    severity: Severity
    category: FindingCategory
    description: str = ""
    url: str | None = None
    remediation: str | None = None
    content_type: str | None = Field(
        default=None,
        description="Observed Content-Type of the response that triggered the finding (e.g. application/sql).",
    )
    evidence: list[Evidence] = Field(default_factory=list)
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:10])
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReportSummary(BaseModel):
    total: int = 0
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)


class FindingSummary(BaseModel):
    """Compact machine-readable view of one finding."""

    id: str
    severity: Severity
    category: FindingCategory
    title: str
    url: str | None = None


class MachineSummary(BaseModel):
    """Stable, machine-readable summary of a run, written to latest.json.

    Intended for CI and dashboards: always at a known path, with counts and
    the paths of the full artifacts.
    """

    target: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    elapsed_seconds: int | None = None
    findings_total: int = 0
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    report_markdown: str | None = None
    report_json: str | None = None
    findings: list[FindingSummary] = Field(default_factory=list)

    @classmethod
    def from_report(
        cls,
        report: "Report",
        report_markdown: str | None = None,
        report_json: str | None = None,
    ) -> "MachineSummary":
        elapsed = None
        if report.started_at and report.finished_at:
            elapsed = round((report.finished_at - report.started_at).total_seconds())
        summary = report.summary or report.build_summary()
        return cls(
            target=report.target,
            status=report.status,
            started_at=report.started_at,
            finished_at=report.finished_at,
            elapsed_seconds=elapsed,
            findings_total=summary.total,
            by_severity=summary.by_severity,
            by_category=summary.by_category,
            report_markdown=report_markdown,
            report_json=report_json,
            findings=[
                FindingSummary(
                    id=f.id,
                    severity=f.severity,
                    category=f.category,
                    title=f.title,
                    url=f.url,
                )
                for f in report.findings
            ],
        )


class Report(BaseModel):
    """The complete output of one agent run against one target."""

    target: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    status: str = "completed"  # running | completed | error
    findings: list[Finding] = Field(default_factory=list)
    summary: ReportSummary | None = None

    def build_summary(self) -> ReportSummary:
        by_severity = {sev.value: 0 for sev in SEVERITY_ORDER}
        by_category: dict[str, int] = {}
        for finding in self.findings:
            by_severity[finding.severity.value] += 1
            by_category[finding.category.value] = by_category.get(finding.category.value, 0) + 1
        return ReportSummary(
            total=len(self.findings),
            by_severity=by_severity,
            by_category=by_category,
        )
