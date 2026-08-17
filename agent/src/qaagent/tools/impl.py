"""The agent's tool surface: deterministic actions the LLM can call.

Tools are the only way the model can affect the outside world. Each tool
stays inside the scope guard, returns structured text for the model, and
feeds deterministic checks (console errors, reflected input) into the
collector so genuine findings appear even when the model is imperfect.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse

from qaagent.browser.driver import Browser
from qaagent.config import RunConfig
from qaagent.models import Evidence, FindingCategory, Severity
from qaagent.report.collector import Collector
from qaagent.tools.registry import Tool, ToolSpec, ToolRegistry


@dataclass
class RunState:
    """Mutable state shared by the tools across the run."""

    last_filled: dict[str, str] = field(default_factory=dict)
    console_seen: set[str] = field(default_factory=set)
    request_seen: set[tuple[str, str]] = field(default_factory=set)
    reflect_seen: set[str] = field(default_factory=set)
    finished: bool = False
    summary: str = ""


def _in_scope(url: str, config: RunConfig) -> bool:
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    allowed = {o.rstrip("/").lower() for o in config.scope.allowed_origins}
    if not allowed:
        # Empty scope = auto-scope to the configured target (handy for CI,
        # where the target is only known at run time).
        t = urlparse(config.target)
        allowed = {f"{t.scheme}://{t.netloc}".lower()}
    return origin.lower() in allowed


def _drain_browser_issues(browser: Browser, collector: Collector, state: RunState) -> None:
    for error in browser.console_errors:
        if error not in state.console_seen:
            state.console_seen.add(error)
            collector.add(
                title="JavaScript console error on page",
                severity=Severity.MEDIUM,
                category=FindingCategory.BUG,
                description=error,
                url=browser.page.url if browser.page else None,
                remediation="Investigate and fix the reported JavaScript error.",
                evidence=[Evidence(kind="console", detail=error)],
            )
    for url, failure in browser.request_failures:
        key = (url, failure)
        if key not in state.request_seen:
            state.request_seen.add(key)
            collector.add(
                title="Failed network request",
                severity=Severity.LOW,
                category=FindingCategory.BUG,
                description=f"{url} failed: {failure}",
                url=url,
                evidence=[Evidence(kind="http_response", url=url, detail=failure)],
            )


def _check_reflection(snap_text: str, browser: Browser, collector: Collector, state: RunState) -> None:
    # Only care about values carrying injection-relevant characters: a plain
    # word echoed back (e.g. a username greeting) is expected behaviour, not XSS.
    interesting = lambda v: any(ch in v for ch in "<>'\"{};&=`")
    for value in state.last_filled.values():
        if (
            value
            and interesting(value)
            and value in snap_text
            and value not in state.reflect_seen
        ):
            state.reflect_seen.add(value)
            collector.add(
                title="User input reflected unescaped in response (possible XSS)",
                severity=Severity.LOW,
                category=FindingCategory.SECURITY,
                description=(
                    f"Submitted value '{value}' appears verbatim in the response HTML. "
                    "If it is not escaped, script payloads will execute (reflected XSS)."
                ),
                url=browser.page.url if browser.page else None,
                remediation="Escape all user input when rendering, and add a Content-Security-Policy.",
                evidence=[Evidence(kind="dom_snapshot", detail=f"value '{value}' present in response")],
            )


def build_tool_specs() -> list[dict]:
    """JSON Schema tool definitions sent to the model."""
    string_arg = {"type": "string"}
    return [
        {
            "type": "function",
            "function": {
                "name": "navigate",
                "description": "Navigate the browser to a URL. Only origins in scope are allowed.",
                "parameters": {"type": "object", "properties": {"url": string_arg}, "required": ["url"]},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_page",
                "description": "Read the current page: URL, title, visible text, links, inputs, buttons.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "click",
                "description": "Click a link or button by its visible text.",
                "parameters": {"type": "object", "properties": {"target": string_arg}, "required": ["target"]},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "fill",
                "description": "Fill an input field. Use the name, label text, id, or placeholder shown by read_page.",
                "parameters": {
                    "type": "object",
                    "properties": {"field": string_arg, "value": string_arg},
                    "required": ["field", "value"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "submit",
                "description": "Submit the first form on the current page.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "screenshot",
                "description": "Save a screenshot of the current page to the evidence folder.",
                "parameters": {"type": "object", "properties": {"name": string_arg}, "required": ["name"]},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "report_finding",
                "description": (
                    "Record a finding you have observed. severity: critical/high/medium/low/info; "
                    "category: security/functional/bug/info. Only report what you actually observed."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": string_arg,
                        "severity": {"type": "string", "enum": [s.value for s in Severity]},
                        "category": {"type": "string", "enum": [c.value for c in FindingCategory]},
                        "description": string_arg,
                        "url": string_arg,
                        "remediation": string_arg,
                    },
                    "required": ["title", "severity", "category"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "finish",
                "description": "End the test session with a one-line summary of what you found.",
                "parameters": {"type": "object", "properties": {"summary": string_arg}, "required": ["summary"]},
            },
        },
    ]


def build_registry(
    browser: Browser,
    collector: Collector,
    config: RunConfig,
    state: RunState,
) -> ToolRegistry:
    """Wire the tools to the live browser, collector, and run state."""

    async def _navigate(url: str) -> str:
        if not _in_scope(url, config):
            return (
                f"BLOCKED by scope guard: {url} is not in allowed origins "
                f"{config.scope.allowed_origins}. Stay on the target."
            )
        snap = await browser.navigate(url)
        _drain_browser_issues(browser, collector, state)
        return snap.summarize()

    async def _read_page() -> str:
        snap = await browser.snapshot()
        return snap.summarize()

    async def _click(target: str) -> str:
        try:
            await browser.click(target)
        except ValueError as exc:
            return f"ERROR: {exc}"
        _drain_browser_issues(browser, collector, state)
        return (await browser.snapshot()).summarize()

    async def _fill(field: str, value: str) -> str:
        try:
            await browser.fill(field, value)
        except ValueError as exc:
            return f"ERROR: {exc}"
        state.last_filled[field] = value
        return f"filled field '{field}' with '{value}'"

    async def _submit() -> str:
        snap = await browser.submit()
        _drain_browser_issues(browser, collector, state)
        _check_reflection(snap.text, browser, collector, state)
        return snap.summarize()

    async def _screenshot(name: str) -> str:
        evidence_dir = config.output_dir / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%H%M%S")
        path = evidence_dir / f"{name}-{stamp}.png"
        await browser.screenshot(str(path))
        return f"screenshot saved to {path}"

    async def _report_finding(
        title: str,
        severity: str,
        category: str,
        description: str = "",
        url: str | None = None,
        remediation: str | None = None,
    ) -> str:
        try:
            sev = Severity(severity)
            cat = FindingCategory(category)
        except ValueError:
            return (
                f"ERROR: invalid severity or category. severity must be one of "
                f"{[s.value for s in Severity]}; category one of {[c.value for c in FindingCategory]}"
            )
        collector.add(
            title=title,
            severity=sev,
            category=cat,
            description=description,
            url=url or (browser.page.url if browser.page else None),
            remediation=remediation,
            evidence=[Evidence(kind="note", detail="reported by the agent")],
        )
        return f"finding recorded: [{sev.value.upper()}] {title}"

    async def _finish(summary: str) -> str:
        state.finished = True
        state.summary = summary
        return "session finished"

    registry = ToolRegistry()
    registry.register(Tool(ToolSpec(name="navigate", description="Navigate to a URL (scope-guarded).", parameters={}), _navigate))
    registry.register(Tool(ToolSpec(name="read_page", description="Read the current page state.", parameters={}), _read_page))
    registry.register(Tool(ToolSpec(name="click", description="Click a link or button by text.", parameters={}), _click))
    registry.register(Tool(ToolSpec(name="fill", description="Fill an input field.", parameters={}), _fill))
    registry.register(Tool(ToolSpec(name="submit", description="Submit the first form.", parameters={}), _submit))
    registry.register(Tool(ToolSpec(name="screenshot", description="Save a screenshot.", parameters={}), _screenshot))
    registry.register(Tool(ToolSpec(name="report_finding", description="Record an observed finding.", parameters={}), _report_finding))
    registry.register(Tool(ToolSpec(name="finish", description="End the session.", parameters={}), _finish))
    return registry


def system_prompt(config: RunConfig) -> str:
    origins = ", ".join(config.scope.allowed_origins)
    creds = (
        f"username: {config.credentials.username}, password: {config.credentials.password}"
        if config.credentials
        else "none provided"
    )
    return f"""You are an autonomous QA agent testing a website for security vulnerabilities, bugs, and broken functionality.

TARGET: {config.target}
SCOPE: only these origins are allowed: {origins}. Never navigate off them.
TEST CREDENTIALS: {creds}

You act ONLY by calling tools. Read the page before acting. When you observe a real problem, record it with report_finding (severity: critical/high/medium/low/info; category: security/functional/bug/info). Do not invent issues - only report what you actually observe.

Deterministic passive checks (security headers, cookie flags, server banner) already ran - do not duplicate them.

Suggested approach:
1. Read the home page, note all links (they show the exact URL after '->'), forms, and endpoints.
2. CLICK links from the LINKS list rather than guessing URLs - guessing causes 404s.
3. Explore each interesting page: search, login, profile, admin, debug, anything unusual.
4. Test forms and search with injection-style input (single quotes, HTML tags like <b>x</b>, {{7*7}}, semicolons) and observe what comes back unescaped or changes behaviour.
5. Verify expected functionality works; record broken behaviour as a bug finding.
6. Screenshot anything noteworthy.

Navigation rules:
- Navigate only to the base target URL or to hrefs shown in the LINKS list.
- If HTTP STATUS is 404, you used a wrong URL - go back (click a link) and use the correct path.
- A 404 caused by your own wrong URL is NOT a bug in the site. Only report what you observe.

You have a limited number of tool calls - prioritise. When done, call finish with a one-line summary."""


def initial_user_message(config: RunConfig, home_summary: str) -> str:
    return (
        f"Begin testing {config.target}. You have up to {config.max_steps} tool calls.\n"
        "The home page has already been loaded:\n" + home_summary
    )
