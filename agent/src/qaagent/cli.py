"""qaagent CLI — entry points for running the agent against a target."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from qaagent.agent.core import Agent
from qaagent.config import RunConfig
from qaagent.models import SEVERITY_ORDER, Report, Severity
from qaagent.report.diff import compare_reports, previous_report
from qaagent.report.generator import save_report

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

app = typer.Typer(
    name="qaagent",
    help="AI agent that tests websites and apps for vulnerabilities, bugs, and functionality.",
    no_args_is_help=True,
)
console = Console()

EXAMPLE_CONFIG = """\
# QA Agent configuration
# Copy to config.yml and adjust. The example targets the local vulnerable app
# that ships in targets/vulnerable_app (see its README).

# Target to test. The scope below must match its origin.
target: http://127.0.0.1:5001

scope:
  # Origins the agent may visit. The scope guard hard-blocks anything else.
  allowed_origins:
    - http://127.0.0.1:5001
  excluded_paths: []          # e.g. ["/logout"]
  max_requests_per_minute: 30 # polite default; raise for real targets
  timeout_seconds: 30

llm:
  model: meta/llama-3.3-70b-instruct   # any model on your OpenAI-compatible API
  api_key_env: NVIDIA_API_KEY          # env var (or agent/.env) holding the key
  api_base: https://integrate.api.nvidia.com/v1
  temperature: 0.0
  max_tokens: 1024

credentials:
  # Optional test credentials the agent may use for auth flows.
  username: alice
  password: alice123

agent:
  max_steps: 25               # cap on observe/think/act/verify iterations
  headless: true
  browser_channel: msedge     # msedge = system Edge (no download); chromium = playwright's
  output_dir: reports
"""


def _load_env() -> None:
    """Load .env from the project root (agent/) if present."""
    if load_dotenv is None:
        return
    project_root = Path(__file__).resolve().parents[2]
    load_dotenv(project_root / ".env", override=False)
    load_dotenv(override=False)


@app.command()
def init_config(
    path: Path = typer.Option(
        Path("config.yml"), "--path", "-o", help="Where to write the example config."
    ),
) -> None:
    """Write an example config file to get started."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(EXAMPLE_CONFIG, encoding="utf-8")
    console.print(f"[green]Wrote example config to[/green] [cyan]{path}[/cyan]")


@app.command()
def dashboard(
    port: int = typer.Option(
        5050, "--port", "-p", help="Port to serve the dashboard on."
    ),
    state: Path = typer.Option(
        Path("reports/live.json"), "--state", help="Live state file to watch."
    ),
    reports: Path = typer.Option(
        Path("reports"), "--reports", help="Directory containing report-*.md files."
    ),
) -> None:
    """Serve the live dashboard (http://127.0.0.1:<port>)."""
    from qaagent.dashboard import run_dashboard

    console.print(
        f"[green]Dashboard:[/green] [cyan]http://127.0.0.1:{port}[/cyan] "
        "(Ctrl+C to stop)"
    )
    run_dashboard(state, reports, port)


@app.command()
def run(
    target: str | None = typer.Option(
        None, "--target", "-t", help="Target URL. Overrides the config file."
    ),
    config: Path = typer.Option(
        Path("config.yml"), "--config", "-c", help="Path to the config file."
    ),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", "-o", help="Where to write reports (overrides config)."
    ),
    max_steps: int | None = typer.Option(
        None, "--max-steps", help="Cap on agent steps (overrides config)."
    ),
    fail_on: str | None = typer.Option(
        None,
        "--fail-on",
        help="Exit 1 if any finding is at this severity or higher: critical|high|medium|low|info.",
    ),
    baseline_on: str | None = typer.Option(
        None,
        "--baseline-on",
        help="Exit 3 if NEW findings vs the previous run are at or above this severity: critical|high|medium|low|info.",
    ),
    baseline: Path | None = typer.Option(
        None,
        "--baseline",
        help="Baseline report JSON to diff against (default: the previous run's report).",
    ),
    skip_llm: bool = typer.Option(
        False,
        "--skip-llm",
        help="Deterministic probes only - no LLM calls, no browser. Fast, quota-free tuning runs.",
    ),
) -> None:
    """Run the agent against a target and write a report."""
    _load_env()
    try:
        cfg = RunConfig.from_yaml(config)
    except ValueError as exc:
        console.print(f"[red]Config error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    overrides: dict = {}
    if target is not None:
        overrides["target"] = target
    if output_dir is not None:
        overrides["output_dir"] = output_dir
    if max_steps is not None:
        overrides["max_steps"] = max_steps
    if skip_llm:
        overrides["skip_llm"] = True
    if overrides:
        cfg = RunConfig.model_validate({**cfg.model_dump(), **overrides})

    console.print(
        Panel(
            "\n".join(
                [
                    f"target:     {cfg.target}",
                    f"scope:      {', '.join(cfg.scope.allowed_origins)}",
                    f"llm:        {cfg.llm.model} via {cfg.llm.api_base}",
                    f"max steps:  {cfg.max_steps}",
                    f"output dir: {cfg.output_dir}",
                    f"llm loop:   {'skipped (--skip-llm)' if cfg.skip_llm else 'enabled'}",
                ]
            ),
            title="Agent run",
            border_style="blue",
        )
    )

    agent = Agent(cfg)
    report = asyncio.run(agent.run())

    # CI gates: --fail-on (current findings) and --baseline-on (regressions:
    # new findings vs the previous run). Exit codes: 0 pass, 1 fail-on, 3 baseline.
    exit_code = 0
    threshold: Severity | None = None
    if fail_on is not None:
        try:
            threshold = Severity(fail_on.lower())
        except ValueError:
            console.print(
                f"[red]Invalid --fail-on value {fail_on!r}: "
                f"use one of {[s.value for s in Severity]}[/red]"
            )
            raise typer.Exit(code=2) from None
        threshold_idx = SEVERITY_ORDER.index(threshold)
        worst = min(
            (SEVERITY_ORDER.index(f.severity) for f in report.findings),
            default=None,
        )
        if worst is not None and worst <= threshold_idx:
            exit_code = 1

    diff = None
    new_at_or_above: list[dict] = []
    if baseline_on is not None:
        try:
            bsev = Severity(baseline_on.lower())
        except ValueError:
            console.print(
                f"[red]Invalid --baseline-on value {baseline_on!r}: "
                f"use one of {[s.value for s in Severity]}[/red]"
            )
            raise typer.Exit(code=2) from None
        bthr = SEVERITY_ORDER.index(bsev)
        previous = None
        if baseline is not None:
            try:
                previous = json.loads(Path(baseline).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                console.print(f"[red]Cannot read baseline {baseline}: {exc}[/red]")
                raise typer.Exit(code=2) from exc
        else:
            previous = previous_report(
                cfg.output_dir, exclude_started_at=report.started_at.isoformat()
            )
        diff = compare_reports(report.model_dump(mode="json"), previous)
        new_at_or_above = [
            f for f in diff.new if SEVERITY_ORDER.index(Severity(f["severity"])) <= bthr
        ]
        if new_at_or_above:
            exit_code = 3

    counts = ", ".join(
        f"{sev.value}={report.summary.by_severity.get(sev.value, 0)}"
        for sev in SEVERITY_ORDER
    ) if report.summary else "n/a"
    console.print(f"[green]Run finished:[/green] {len(report.findings)} findings ({counts})")
    for finding in sorted(
        report.findings, key=lambda f: (SEVERITY_ORDER.index(f.severity), f.detected_at)
    ):
        console.print(f"  [{finding.severity.value.upper()}] {finding.title}")
    path = agent.report_path or str(save_report(report, cfg.output_dir))
    json_path = agent.report_json_path
    console.print(f"[green]Report (Markdown):[/green] [cyan]{path}[/cyan]")
    if json_path:
        console.print(f"[green]Report (JSON):[/green] [cyan]{json_path}[/cyan]")
    console.print(f"[green]Machine summary:[/green] [cyan]{cfg.output_dir / 'latest.json'}[/cyan]")
    if fail_on is not None and threshold is not None:
        code = 1 if exit_code == 1 else 0
        console.print(
            f"[{'red' if code else 'green'}]--fail-on {threshold.value} -> "
            f"exit code {code}[/{'red' if code else 'green'}]"
        )
    if baseline_on is not None and bsev is not None:
        if diff is None or diff.previous_run is None:
            console.print(
                "[yellow]No previous run to diff against - baseline not "
                "established (exit 0).[/yellow]"
            )
        else:
            code = 3 if new_at_or_above else 0
            console.print(
                f"[blue]New findings vs baseline:[/blue] {len(diff.new)} "
                f"(at/above {bsev.value}: {len(new_at_or_above)})"
            )
            for f in new_at_or_above:
                console.print(f"  [[red]{f['severity'].upper()}[/red]] {f['title']}")
            console.print(
                f"[{'red' if code else 'green'}]--baseline-on {bsev.value} -> "
                f"exit code {code}[/{'red' if code else 'green'}]"
            )
    if exit_code:
        raise typer.Exit(code=exit_code)


if __name__ == "__main__":
    app()
