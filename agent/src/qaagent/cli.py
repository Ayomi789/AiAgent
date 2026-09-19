"""qaagent CLI — entry points for running the agent against a target."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from qaagent.agent.core import Agent
from qaagent.config import DEFAULT_LLM_MODEL, RunConfig, ScopeConfig
from qaagent.models import SEVERITY_ORDER, Report, Severity
from qaagent.report.diff import compare_reports, previous_report
from qaagent.report.generator import save_report

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

app = typer.Typer(
    name="Sentinel",
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
  model: nvidia/nemotron-3-super-120b-a12b   # keep in sync with DEFAULT_LLM_MODEL (qaagent.config)
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


def _config_dir() -> Path:
    """Where site configs live: SENTINEL_CONFIG_DIR if set, else the project root.

    Local installs keep configs in agent/ next to the code. Hosted deployments
    set SENTINEL_CONFIG_DIR to a persistent volume path so dashboard-created
    configs survive container rebuilds.
    """
    env_dir = os.environ.get("SENTINEL_CONFIG_DIR")
    if env_dir:
        return Path(env_dir)
    return Path(__file__).resolve().parents[2]


def _resolve_config(path: Path) -> Path:
    """Resolve a config path with shorthand aliases.

    Given "solnew" tries (in order):
      1. solnew          (exact path as given)
      2. config.solnew.yml
      3. solnew.yml
      4. config.solnew
    If none of those exist in the current directory, the config directory
    (project root, or SENTINEL_CONFIG_DIR) is searched the same way, so
    `sentinel run --config solnew` works from anywhere on the machine.
    Raises FileNotFoundError with a helpful message if none match.
    """
    candidates = [path, Path(f"config.{path}.yml"), Path(f"{path}.yml"), Path(f"config.{path}")]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    # Fall back to the config directory (where the CLI ships), so the
    # command works from any working directory once `sentinel` is on PATH.
    config_dir = _config_dir()
    for candidate in candidates:
        rooted = config_dir / candidate
        if rooted.exists():
            return rooted
    tried = ", ".join(str(p) for p in candidates)
    raise FileNotFoundError(
        f"Config file not found. Tried (cwd + {config_dir}): {tried}"
    )


def _derive_target(name: str) -> str | None:
    """Derive a target URL from a bare site name, or None if it isn't one.

    "stylesbytiwa.netlify.app" -> "https://stylesbytiwa.netlify.app"
    "https://x.io/path"        -> "https://x.io/path"
    "solnew"                   -> None (no dot - not a domain)
    "config.yml" / "config.x"  -> None (already a config name)
    """
    low = name.lower()
    if low.startswith(("http://", "https://")):
        return name.rstrip("/")
    if low.endswith((".yml", ".yaml")) or low.startswith("config."):
        return None
    if "." in name and "/" not in name:
        return f"https://{name}".rstrip("/")
    return None


_AUTO_CONFIG_TEMPLATE = """\
# Sentinel config for {target} (auto-generated - edit freely).
# Add test credentials or extra sensitive_files here if you have them.

target: {target}
# (browser_channel omitted - BROWSER_CHANNEL env or the msedge default applies)

scope:
  allowed_origins: []        # empty = auto-scope to the target's origin
  excluded_paths: []
  max_requests_per_minute: 30
  timeout_seconds: 30

llm:
  model: nvidia/nemotron-3-super-120b-a12b
  api_key_env: NVIDIA_API_KEY
  api_base: https://integrate.api.nvidia.com/v1
  temperature: 0.0
  max_tokens: 1024

agent:
  max_steps: 25
  headless: true
  output_dir: reports
"""


def _anchor_output_dir(cfg: RunConfig, config_path: Path | None, project_root: Path) -> None:
    """Anchor a relative output_dir to stable ground - never the current directory.

    With a config, reports land next to that config; without one, in the
    project's reports folder. This keeps `sentinel run` and `sentinel
    dashboard` writing to one place no matter which directory they are
    launched from (the home-dir trap that stranded reports in ~/reports).
    """
    if cfg.output_dir.is_absolute():
        return
    base = config_path.parent if config_path is not None else project_root
    cfg.output_dir = base / cfg.output_dir


def _auto_create_config(name: str, target: str) -> Path:
    """Write a per-site config for a bare site name and return its path."""
    path = _config_dir() / f"config.{name}.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _AUTO_CONFIG_TEMPLATE.format(target=target), encoding="utf-8"
    )
    return path


@app.command()
def init_config(
    path: Path = typer.Option(
        Path("config.yml"), "--path", "-o", help="Where to write the example config."
    ),
    name: str | None = typer.Option(
        None, "--name", help="Site name: writes config.<name>.yml (e.g. --name solnew)."
    ),
    target: str | None = typer.Option(
        None, "--target", "-t", help="Target URL for the new config."
    ),
) -> None:
    """Write an example config file to get started.

    With --name (and optionally --target) this writes a per-site config:
    `sentinel init-config --name solnew --target https://sol.new`.
    """
    if name is not None:
        path = Path(f"config.{name}.yml")
        site_target = target or _derive_target(name)
        if site_target is None:
            console.print(
                f"[red]Cannot derive a URL from '{name}'. "
                f"Pass --target <url> too.[/red]"
            )
            raise typer.Exit(code=2)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_AUTO_CONFIG_TEMPLATE.format(target=site_target), encoding="utf-8")
        console.print(
            f"[green]Wrote per-site config to[/green] [cyan]{path}[/cyan] "
            f"(target: {site_target})"
        )
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(EXAMPLE_CONFIG, encoding="utf-8")
    console.print(f"[green]Wrote example config to[/green] [cyan]{path}[/cyan]")


@app.command()
def dashboard(
    port: int = typer.Option(
        5050, "--port", "-p", help="Port to serve the dashboard on."
    ),
    state: Path | None = typer.Option(
        None, "--state", help="Live state file to watch (default: <project>/reports/live.json)."
    ),
    reports: Path | None = typer.Option(
        None, "--reports", help="Directory containing report-*.md files (default: <project>/reports)."
    ),
) -> None:
    """Serve the live dashboard (http://127.0.0.1:<port>).

    Defaults are anchored to the project folder, not the current directory,
    so accounts, the access token, sessions, and reports are the same no
    matter where `sentinel dashboard` is launched from.
    """
    from qaagent.dashboard import load_or_create_token, run_dashboard

    project_root = Path(__file__).resolve().parents[2]
    reports = reports or (project_root / "reports")
    state = state or (reports / "live.json")
    reports.mkdir(parents=True, exist_ok=True)
    token = load_or_create_token(reports)
    url = f"http://127.0.0.1:{port}/?token={token}"
    console.print(
        f"[green]Dashboard:[/green] [cyan]{url}[/cyan]\n"
        f"[dim]The URL includes the access token (also saved in "
        f"{reports / '.dashboard-token'}). Open it in a browser; the token "
        "is remembered via cookie. Ctrl+C to stop.[/dim]"
    )
    run_dashboard(state, reports, port, project_root=project_root, auth_token=token)


@app.command()
def doctor(
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Also deep-check this config (its model + target)."
    ),
    target: str | None = typer.Option(
        None, "--target", "-t", help="Also probe this URL for reachability."
    ),
    skip_llm: bool = typer.Option(
        False, "--skip-llm", help="Skip the live LLM probe (offline-safe)."
    ),
) -> None:
    """Verify data paths, config health, and the LLM before you trust a scan.

    Catches the silent failures that ruin runs: retired LLM models, configs
    that no longer parse, a missing API key, and unreachable targets.
    Exit code is 1 when any check fails, so it works in scripts and CI.
    """
    import time

    from qaagent import doctor

    project_root = Path(__file__).resolve().parents[2]
    reports_dir = project_root / "reports"
    resolved: Path | None = None
    if config is not None:
        try:
            resolved = _resolve_config(config)
        except FileNotFoundError:
            console.print(f"[red]Config not found:[/red] {config}")
            raise typer.Exit(code=1) from None

    console.print(
        Panel.fit(
            f"project:  {project_root}\n"
            f"reports:  {reports_dir}"
            + (f"\nconfig:   {resolved}" if resolved else ""),
            title="Sentinel doctor",
        )
    )

    _load_env()
    started = time.time()
    checks = doctor.run_checks(
        project_root,
        reports_dir,
        config_path=resolved,
        target=target,
        probe_model=not skip_llm,
    )

    icon = {"ok": "[green]OK [/green]", "warn": "[yellow]WARN[/yellow]", "fail": "[red]FAIL[/red]"}
    for c in checks:
        console.print(f" {icon[c.status]} {c.name:<10} {c.detail}")

    n_fail = doctor.failed(checks)
    n_warn = sum(1 for c in checks if c.status == "warn")
    elapsed = time.time() - started
    if n_fail:
        console.print(f"\n[red]{n_fail} check(s) failed[/red]" + (f", {n_warn} warning(s)" if n_warn else "") + f" in {elapsed:.1f}s")
        raise typer.Exit(code=1)
    console.print(
        f"\n[green]All checks passed[/green]"
        + (f" with {n_warn} warning(s)" if n_warn else "")
        + f" in {elapsed:.1f}s - ready to scan."
    )


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
    config_path: Path | None = None
    try:
        config_path = _resolve_config(config)
    except FileNotFoundError:
        config_path = None

    if config_path is not None:
        try:
            cfg = RunConfig.from_yaml(config_path)
        except ValueError as exc:
            console.print(f"[red]Config error:[/red] {exc}")
            raise typer.Exit(code=1) from exc
    elif target is not None:
        # No config file at all, but an explicit target: run with defaults
        # (empty scope auto-targets the target's origin).
        console.print(
            "[yellow]No config file found - using defaults with auto-scope.\n"
            f"Create one with: sentinel init-config --name <site> --target {target}[/yellow]"
        )
        cfg = RunConfig(target=target, scope=ScopeConfig(allowed_origins=[]))
    else:
        # Bare site name with no config: auto-create one, e.g.
        # `sentinel run --config stylesbytiwa.netlify.app`.
        derived = _derive_target(str(config))
        if derived is not None:
            created = _auto_create_config(str(config), derived)
            console.print(
                f"[green]Created config [cyan]{created}[/cyan] for {derived} "
                "(edit it to add credentials/sensitive_files).[/green]"
            )
            cfg = RunConfig.from_yaml(created)
            config_path = created
        else:
            console.print(
                f"[red]No config file for '{config}'.[/red]\n"
                f"  - Scan directly: sentinel run --target <url> --skip-llm\n"
                f"  - Save a config: sentinel init-config --name {config} --target <url>"
            )
            raise typer.Exit(code=1)

    # Reports go next to the config file (or in the project when no config
    # exists), so scans write to the same place no matter where they run from.
    project_root = Path(__file__).resolve().parents[2]
    _anchor_output_dir(cfg, config_path, project_root)

    overrides: dict = {}
    if target is not None:
        overrides["target"] = target
    if output_dir is not None:
        overrides["output_dir"] = output_dir
    if max_steps is not None:
        overrides["max_steps"] = max_steps
    if skip_llm:
        overrides["skip_llm"] = True
    # Scan ownership: the dashboard passes the logged-in starter via env vars
    # when spawning this process, so each account's scans stay isolated.
    env_owner_id = os.environ.get("SENTINEL_OWNER_ID")
    if env_owner_id and env_owner_id.isdigit():
        overrides["owner_id"] = int(env_owner_id)
        overrides["owner_email"] = os.environ.get("SENTINEL_OWNER_EMAIL") or None
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
