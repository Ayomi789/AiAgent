"""Finding collector — the one place findings are recorded during a run.

Deduplicates findings by exact (title, url) and by fuzzy matching: when the
LLM reports an issue the deterministic probes already found (e.g. "Broken
Access Control" vs "Sensitive endpoint exposed: /admin"), the LLM finding
merges into the existing one so runs and diffs stay clean.
"""

from __future__ import annotations

import difflib
import re
from urllib.parse import urlparse

from qaagent.models import Evidence, Finding, FindingCategory, Severity

# Security concepts matched from finding titles (first rule wins, so a title
# gets exactly one concept).
_CONCEPT_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("ssti", ("template", "ssti")),
    ("xss", ("xss", "cross-site", "cross site", "script")),
    ("sqli", ("sql", "injection")),
    (
        "access_control",
        ("admin", "access control", "authorization", "unauthor", "privilege", "broken access"),
    ),
    ("cookie", ("cookie", "httponly", "session")),
    (
        "headers",
        ("header", "csp", "content-security", "frame", "strict-transport", "hsts", "nosniff", "referrer"),
    ),
    ("idor", ("idor", "object", "enumerat")),
    ("disclosure", ("disclos", "debug", "banner")),
    ("redirect", ("redirect",)),
    ("login", ("login", "authentication", "auth")),
]

# Words too generic to signal "same issue" in a title.
_STOPWORDS = {
    "missing", "header", "found", "page", "site", "application", "endpoint",
    "search", "injection", "security", "content", "the", "on", "at", "in",
    "of", "a", "an", "for", "with", "and", "or", "to", "from", "is", "are",
    "not", "no", "user", "value", "response", "server", "error", "console",
    "against", "form",
}

_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")


def _normalize_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc.lower()}{parsed.path.rstrip('/')}"


def _concept(title: str) -> str | None:
    lowered = title.lower()
    for concept, keywords in _CONCEPT_RULES:
        if any(keyword in lowered for keyword in keywords):
            return concept
    return None


def _tokens(title: str) -> set[str]:
    return {
        token.lower()
        for token in _TOKEN_RE.findall(title)
        if len(token) >= 4 and token.lower() not in _STOPWORDS
    }


def _same_issue(existing: Finding, title: str, url: str | None) -> bool:
    """Whether a candidate finding is the same issue as an existing one."""
    if not (url and existing.url):
        # No usable URLs: only near-verbatim titles count as the same issue.
        return difflib.SequenceMatcher(None, title.lower(), existing.title.lower()).ratio() >= 0.85
    if _normalize_url(url) != _normalize_url(existing.url):
        return False
    left, right = _concept(existing.title), _concept(title)
    if "headers" in (left, right):
        # Each header is its own distinct finding; exact match only.
        return False
    if left and left == right:
        return True
    return bool(_tokens(existing.title) & _tokens(title))


class Collector:
    """Accumulates findings, deduping exact and fuzzy-equivalent ones."""

    def __init__(self) -> None:
        self.findings: list[Finding] = []
        self._seen: set[tuple[str, str | None]] = set()

    def add(
        self,
        *,
        title: str,
        severity: Severity,
        category: FindingCategory,
        description: str = "",
        url: str | None = None,
        remediation: str | None = None,
        content_type: str | None = None,
        evidence: list[Evidence] | None = None,
    ) -> Finding:
        key = (title, url)
        if key in self._seen:
            existing = next(f for f in self.findings if (f.title, f.url) == key)
            if evidence:
                existing.evidence.extend(evidence)
            return existing

        for existing in self.findings:
            if _same_issue(existing, title, url):
                self._seen.add(key)
                if evidence:
                    existing.evidence.extend(evidence)
                if title != existing.title:
                    existing.evidence.append(
                        Evidence(kind="note", detail=f"also reported as: {title}")
                    )
                return existing

        self._seen.add(key)
        finding = Finding(
            title=title,
            severity=severity,
            category=category,
            description=description,
            url=url,
            remediation=remediation,
            content_type=content_type,
            evidence=evidence or [],
        )
        self.findings.append(finding)
        return finding
