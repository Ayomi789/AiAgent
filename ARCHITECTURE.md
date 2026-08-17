# AI Testing Agent — Architecture Plan

## Vision
An AI agent that autonomously tests websites and apps for **security vulnerabilities**, **bugs**, and **broken functionality** — browsing like a user, probing like a scanner, and delivering a severity-ranked report with evidence.

## Core Principle
**The LLM is the brain; deterministic tools are the hands.**
The model decides *what* to test and *why* a result matters. Every actual action — clicking, submitting, probing, measuring — is executed by verified, deterministic code the agent calls through a tool interface. No model output ever runs directly against the target.

## Components

| Component | Responsibility |
|---|---|
| **Agent Core** (orchestrator) | Runs the observe→think→act→verify loop; owns the task plan, session state, and memory of findings. |
| **Tool Layer** | The deterministic actions exposed to the LLM: `navigate`, `click`, `fill`, `submit`, `screenshot`, `read_page`, `probe_http`, `check_headers`, `run_injection_test`, `assert_expected`. |
| **Browser Driver** | Playwright: real user-level browsing, DOM/accessibility snapshots, console + network capture, screenshots. |
| **Security Probe** | HTTP-level checks: headers, cookies, TLS, auth flows, injection payloads (XSS/SQLi), exposed endpoints, JS errors. |
| **Functional Verifier** | Assertion utilities the agent uses to confirm expected behavior (element present, text shown, state changed, no error). |
| **Evidence Store** | Screenshots, DOM snapshots, request/response pairs, console errors — attached to each finding for proof. |
| **Report Generator** | Findings → severity-ranked report (JSON + Markdown). |
| **Scope Guard** | Config: allowed origins, excluded paths, rate limits, credentials. Hard blocks the agent from leaving the target. |

## Data Flow

```
target config ──▶ Agent Core ──▶ decide next test
                    │  ▲
                    ▼  │
              Tool Layer ◀── deterministic only
               /        \
    Browser Driver     Security Probe
               \        /
            Evidence Store
                    │
                    ▼
         Report Generator ──▶ findings + severity + evidence
```

## Agent Loop

1. **Observe** — read page snapshot (DOM/a11y tree, console, network), plus probe results.
2. **Think** — LLM picks the highest-value next test within scope.
3. **Act** — call one tool; tool executes deterministically and returns structured results.
4. **Verify** — confirm or refute the hypothesis; on failure, retry, take an alternate path, or record a finding.
5. **Repeat** — until the task plan is exhausted or the budget/scope limit is hit.

## Tech Choices
- **Python 3.12+** — ecosystem fit (Playwright, httpx, security tooling, agent frameworks)
- **Playwright** — browser automation; Python API
- **httpx + asyncio** — HTTP probing and parallel checks
- **Pydantic** — config, tool schemas, finding models (single source of truth for the report schema)
- **LLM backend**: OpenAI-compatible API (NVIDIA build.nvidia.com by default) via a small httpx client, using structured tool calls only

## Safety
- Scope Guard enforces allowed origins and rate limits on every request.
- No destructive actions: nothing is modified permanently; auth-testing uses supplied test credentials only, never brute force.
- Every finding is tied to captured evidence so humans verify before acting.

## First Milestone (MVP)
1. CLI entry point: `agent run --target https://example.com --config config.yml`
2. Agent navigates, clicks through a flow, fills and submits a form, and asserts an expected outcome.
3. Passive security checks run alongside: security headers, cookie flags, TLS config, mixed content, console/JS errors.
4. Active payload probes run alongside: reflected XSS, SSTI, boolean/error-based SQLi, login auth bypass, exposed sensitive endpoints — deterministic, no LLM needed.
5. Findings recorded with severity (critical/high/medium/low/info) + evidence, output as Markdown report.
6. Scope Guard active from day one.

### Out of scope for MVP (next milestones)
- Auth flows beyond supplied credentials
- Mobile/native app targets
- CI/CD integration & regression baselines
