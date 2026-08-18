"""The agent loop: observe -> think -> act -> verify.

A single run: passive probe (deterministic), then an LLM-driven loop where
the model plans the next test (think), calls exactly one deterministic tool
(act), and the results feed back (observe/verify). Findings accumulate in a
Collector and are finalized into a Report.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from qaagent.browser.driver import Browser
from qaagent.config import RunConfig
from qaagent.live import LiveState
from qaagent.llm.client import LLMClient, LLMMessage
from qaagent.models import FindingCategory, Report, Severity
from qaagent.probe.active import run_active_probe
from qaagent.probe.passive import run_passive_probe
from qaagent.report.collector import Collector
from qaagent.report.generator import save_report, save_report_csv, save_report_html, save_report_json, save_summary
from qaagent.tools.impl import (
    build_registry,
    build_tool_specs,
    initial_user_message,
    system_prompt,
)
from qaagent.tools.impl import RunState


class Agent:
    """Orchestrator for a single test run against one target."""

    def __init__(self, config: RunConfig) -> None:
        self.config = config
        self.report_path: str | None = None
        self.report_json_path: str | None = None

    async def run(self) -> Report:
        started = datetime.now(timezone.utc)
        report = Report(target=self.config.target, started_at=started, status="running")
        collector = Collector()
        live = LiveState(self.config.output_dir / "live.json")
        live.update(
            status="running",
            stage="Starting",
            target=self.config.target,
            started_at=started.isoformat(),
            max_steps=self.config.max_steps,
        )

        try:
            # Fail fast before launching the browser: no key means no LLM loop.
            if not self.config.skip_llm:
                llm = LLMClient(self.config.llm)
                if not llm.available:
                    raise RuntimeError(
                        f"no API key found in environment variable "
                        f"{self.config.llm.api_key_env} (set it, or add it to agent/.env)"
                    )

            async with Browser(
                headless=self.config.headless,
                channel=self.config.browser_channel,
            ) as browser:
                # 1. Deterministic probes (no LLM needed): passive checks for
                #    headers/cookies, then active payload probes for XSS/SQLi/
                #    SSTI/login bypass/exposed endpoints.
                live.update(stage="Passive security checks")
                await run_passive_probe(
                    self.config.target, self.config.credentials, collector
                )
                live.set_findings(collector.findings)

                live.update(stage="Active payload probes")
                await run_active_probe(self.config, collector)
                live.set_findings(collector.findings)

                # 2. LLM-driven loop (skipped entirely with --skip-llm).
                if not self.config.skip_llm:
                    live.update(stage="Exploring target")
                    home = await browser.navigate(self.config.target)
                    state = RunState()
                    browser_tools = build_registry(browser, collector, self.config, state)
                    tools = build_tool_specs()
                    messages = [
                        LLMMessage(role="system", content=system_prompt(self.config)),
                        LLMMessage(
                            role="user",
                            content=initial_user_message(self.config, home.summarize()),
                        ),
                    ]

                    step = 0
                    while step < self.config.max_steps:
                        step += 1
                        live.update(
                            step=step,
                            current_url=await browser.current_url(),
                            stage="Exploring target",
                        )
                        result = await llm.chat(messages, tools=tools)

                        if result.tool_calls:
                            tool_messages: list[LLMMessage] = []
                            for call in result.tool_calls:
                                fn = call.get("function", {})
                                name = fn.get("name", "")
                                try:
                                    args = json.loads(fn.get("arguments") or "{}")
                                    if not isinstance(args, dict):
                                        args = {}
                                except json.JSONDecodeError:
                                    args = {}
                                brief = " ".join(f"{k}={v}" for k, v in args.items())[:80]
                                live.push_action(f"{name} {brief}".strip())
                                try:
                                    tool = browser_tools.get(name)
                                    output = await tool(**args)
                                except KeyError:
                                    output = f"ERROR: unknown tool '{name}'"
                                except Exception as exc:  # keep the loop alive
                                    output = f"ERROR: {name} failed: {exc}"
                                tool_messages.append(
                                    LLMMessage(
                                        role="tool",
                                        tool_call_id=call.get("id", ""),
                                        content=str(output),
                                    )
                                )
                            messages.append(
                                LLMMessage(role="assistant", tool_calls=result.tool_calls)
                            )
                            messages.extend(tool_messages)
                            live.set_findings(collector.findings)
                            if any(c.get("function", {}).get("name") == "finish" for c in result.tool_calls):
                                break
                        elif result.content:
                            messages.append(LLMMessage(role="assistant", content=result.content))
                            break
                        else:
                            break
        except Exception as exc:  # whole-run failure -> report it
            collector.add(
                title="Agent run failed",
                severity=Severity.HIGH,
                category=FindingCategory.BUG,
                description=f"{type(exc).__name__}: {exc}",
                url=self.config.target,
            )
        finally:
            report.findings = collector.findings
            report.summary = report.build_summary()
            report.finished_at = datetime.now(timezone.utc)
            report.status = "completed"
            self.report_path = str(save_report(report, self.config.output_dir))
            self.report_json_path = str(save_report_json(report, self.config.output_dir))
            save_report_html(report, self.config.output_dir)
            save_report_csv(report, self.config.output_dir)
            save_summary(
                report, self.config.output_dir, self.report_path, self.report_json_path
            )
            live.set_findings(collector.findings)
            live.finish("completed", report_path=self.report_path)
        return report
