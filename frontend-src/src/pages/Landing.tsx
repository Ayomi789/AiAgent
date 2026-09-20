import { Link } from "react-router-dom";
import {
  ArrowRight,
  ShieldCheck,
  Activity,
  Camera,
  FileText,
  Globe,
  Terminal,
  Workflow,
  CheckCircle2,
  Lock,
  Layers,
  Database,
  Cpu,
} from "lucide-react";
import { BrowserPanel } from "../components/BrowserPanel";
import { ScopeGuard } from "../components/ScopeGuard";
import { EvidenceViewer } from "../components/EvidenceViewer";
import { SeverityBadge, StatusBadge, PanelHeader, ProgressBar } from "../components/ui";
import { findings, timeline, coverageByCategory, severityCounts } from "../lib/data";

const NAV_LINKS = [
  ["Overview", "#overview"],
  ["How it works", "#how"],
  ["Browser testing", "#browser"],
  ["Evidence", "#evidence"],
  ["Scope protection", "#scope"],
  ["Reporting", "#reporting"],
  ["Architecture", "#architecture"],
];

export function Landing() {
  const counts = severityCounts();

  return (
    <div className="min-h-screen bg-app-900">
      {/* Header */}
      <header className="sticky top-0 z-40 border-b border-line bg-app-900/95 backdrop-blur-[2px]">
        <div className="mx-auto flex h-[56px] max-w-[1240px] items-center gap-3 px-5">
          <Link to="/" className="flex items-center gap-2.5">
            <span className="flex h-[28px] w-[28px] items-center justify-center rounded-[5px] border border-line-strong bg-app-800">
              <ShieldCheck size={15} className="text-ink" />
            </span>
            <span className="text-[12.5px] font-semibold tracking-[-0.01em] text-ink">
              AI Testing Agent
            </span>
          </Link>

          <nav className="ml-6 hidden items-center gap-5 lg:flex">
            {NAV_LINKS.map(([label, href]) => (
              <a
                key={href}
                href={href}
                className="text-[11px] text-muted transition-colors hover:text-ink"
              >
                {label}
              </a>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-2">
            <Link to="/login" className="font-mono text-[10.5px] text-muted hover:text-ink">
              Sign in
            </Link>
            <a href="#reporting" className="btn-secondary !py-[6px] !text-[11px]">
              View sample report
            </a>
            <Link to="/app" className="btn-primary !py-[6px] !text-[11px]">
              Open workspace
              <ArrowRight size={11} />
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="border-b border-line">
        <div className="mx-auto max-w-[1240px] px-5 py-14 lg:py-20">
          <div className="grid grid-cols-1 gap-10 lg:grid-cols-12">
            <div className="lg:col-span-5">
              <div className="flex items-center gap-2">
                <span className="h-[6px] w-[6px] rounded-[1px] bg-[#4c8dff]" />
                <span className="font-mono text-[9px] font-semibold uppercase tracking-[0.17em] text-dim">
                  Autonomous web application testing
                </span>
              </div>

              <h1 className="mt-5 text-[34px] font-semibold leading-[1.1] tracking-[-0.028em] text-ink lg:text-[42px]">
                Autonomous testing for real web applications.
              </h1>

              <p className="mt-5 max-w-[460px] text-[14px] leading-[1.75] text-muted">
                AI-driven exploration backed by deterministic security and functional testing. The
                agent browses authorized targets like a real user, verifies what it finds, and
                attaches evidence to every result.
              </p>

              <div className="mt-7 flex flex-wrap items-center gap-2.5">
                <Link to="/app" className="btn-primary !px-5 !py-[10px] !text-[12.5px]">
                  Open the workspace
                  <ArrowRight size={13} />
                </Link>
                <a href="#how" className="btn-secondary !px-4 !py-[10px] !text-[12px]">
                  See how it works
                </a>
              </div>

              <div className="mt-8 grid grid-cols-2 gap-x-6 gap-y-4 border-t border-line pt-6 sm:grid-cols-4 lg:grid-cols-2">
                {[
                  ["Deterministic verification", "No probabilistic assertions"],
                  ["Evidence-first output", "Reports in HTML, JSON, CSV, Markdown"],
                  ["Strict scope enforcement", "Zero out-of-scope requests"],
                  ["Baseline tracking", "New vs fixed findings per run"],
                ].map(([title, sub]) => (
                  <div key={title}>
                    <div className="flex items-center gap-1.5">
                      <CheckCircle2 size={11} className="text-[#66c07a]" />
                      <span className="text-[10.5px] font-medium text-ink-soft">{title}</span>
                    </div>
                    <div className="mt-1 font-mono text-[8.5px] text-faint">{sub}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Product UI preview */}
            <div className="lg:col-span-7">
              <div className="overflow-hidden rounded-[8px] border border-line bg-app-880">
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 border-b border-line px-4 py-2.5">
                  <div className="flex items-center gap-2">
                    <span className="h-[6px] w-[6px] rounded-full bg-[#4c8dff] animate-pulse-dot" />
                    <span className="font-mono text-[8.5px] font-semibold uppercase tracking-[0.14em] text-[#7fa9f0]">
                      Run active
                    </span>
                  </div>
                  <span className="font-mono text-[8.5px] text-faint">
                    target: https://app.example.com
                  </span>
                  <span className="font-mono text-[8.5px] text-faint">run_8f31c2</span>
                  <div className="ml-auto flex items-center gap-1.5">
                    <span className="rounded-[3px] border border-line px-1.5 py-[1px] font-mono text-[8px] text-dim">
                      147 tests
                    </span>
                    <span className="rounded-[3px] border border-line px-1.5 py-[1px] font-mono text-[8px] text-dim">
                      1,284 requests
                    </span>
                    <span className="rounded-[3px] border border-[rgba(229,72,77,0.3)] bg-[rgba(229,72,77,0.1)] px-1.5 py-[1px] font-mono text-[8px] text-[#f28286]">
                      1 critical
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-px bg-line lg:grid-cols-2">
                  <div className="bg-app-880 p-3">
                    <div className="mb-2 px-1 text-[8px] font-semibold uppercase tracking-[0.13em] text-faint">
                      Agent activity
                    </div>
                    <div className="space-y-[3px]">
                      {timeline.slice(0, 8).map((e, i) => (
                        <div key={i} className="flex items-start gap-2 rounded-[3px] px-1.5 py-[3px]">
                          <span className="shrink-0 font-mono text-[8px] text-faint">{e.time}</span>
                          <span
                            className="shrink-0 rounded-[2px] px-1 font-mono text-[7px] font-semibold tracking-[0.1em]"
                            style={{
                              color:
                                e.phase === "ACT"
                                  ? "#7fa9f0"
                                  : e.phase === "VERIFY"
                                    ? "#f0b95c"
                                    : e.phase === "CAPTURE"
                                      ? "#66c07a"
                                      : "#98a1ab",
                            }}
                          >
                            {e.phase}
                          </span>
                          <span className="truncate text-[8.5px] text-muted">{e.description}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="bg-app-880 p-3">
                    <div className="mb-2 px-1 text-[8px] font-semibold uppercase tracking-[0.13em] text-faint">
                      Findings by severity
                    </div>
                    <div className="space-y-2">
                      {[
                        ["Critical", counts.critical, "#e5484d"],
                        ["High", counts.high, "#f76b15"],
                        ["Medium", counts.medium, "#f5a623"],
                        ["Low", counts.low, "#6c8fb3"],
                        ["Info", counts.info, "#7d8794"],
                      ].map(([label, value, color]) => (
                        <div key={label as string} className="flex items-center gap-2">
                          <span className="w-[52px] shrink-0 text-[8px] text-faint">{label as string}</span>
                          <div className="h-[5px] flex-1 overflow-hidden rounded-[2px] bg-app-750">
                            <div
                              className="h-full rounded-[2px]"
                              style={{
                                width: `${((value as number) / 9) * 100}%`,
                                backgroundColor: color as string,
                              }}
                            />
                          </div>
                          <span className="w-[16px] shrink-0 text-right font-mono text-[8px] text-muted">
                            {value as number}
                          </span>
                        </div>
                      ))}
                    </div>

                    <div className="mt-3 border-t border-line pt-2.5">
                      <div className="flex items-center justify-between">
                        <span className="text-[8px] text-faint">Run progress</span>
                        <span className="font-mono text-[8px] text-muted">72%</span>
                      </div>
                      <div className="mt-1.5">
                        <ProgressBar value={72} color="#4c8dff" height={3} />
                      </div>
                      <div className="mt-2 font-mono text-[7.5px] text-faint">
                        current: sec.sqli.probe · queue 12 checks
                      </div>
                    </div>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line px-4 py-2 font-mono text-[7.5px] text-faint">
                  <span>scope: enforced</span>
                  <span>rate: 2.0 req/sec</span>
                  <span>evidence: capturing</span>
                  <span>browser: chromium-129</span>
                  <span className="ml-auto text-[#66c07a]">all systems operational</span>
                </div>
              </div>

              <div className="mt-3 grid grid-cols-2 gap-px overflow-hidden rounded-[6px] border border-line bg-line sm:grid-cols-4">
                {[
                  ["Tests executed", "147"],
                  ["Requests", "1,284"],
                  ["Verified findings", "24"],
                  ["Scope violations", "0"],
                ].map(([k, v]) => (
                  <div key={k} className="bg-app-880 px-3 py-2.5">
                    <div className="font-mono text-[15px] leading-none text-ink">{v}</div>
                    <div className="mt-1 text-[7.5px] uppercase tracking-[0.13em] text-faint">{k}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 1 · Product overview */}
      <section id="overview" className="border-b border-line">
        <div className="mx-auto max-w-[1240px] px-5 py-16">
          <SectionHeader
            eyebrow="01 · Product overview"
            title="Serious software for testing real applications."
            description="AI Testing Agent combines autonomous browser exploration with deterministic security and functional verification. It is built for engineering teams that need reproducible results, not probabilistic guesses."
          />

          <div className="mt-9 grid grid-cols-1 gap-px overflow-hidden rounded-[6px] border border-line bg-line md:grid-cols-2 lg:grid-cols-3">
            {[
              [
                <Workflow key="1" size={14} />,
                "Autonomous exploration",
                "The agent navigates the application like a user — reading the accessibility tree, filling forms, following routes, and building a map of the reachable surface.",
              ],
              [
                <ShieldCheck key="2" size={14} />,
                "Deterministic security checks",
                "Injection, authentication, authorization, configuration, and transport checks run from a versioned catalogue with repeatable, non-destructive probes.",
              ],
              [
                <Activity key="3" size={14} />,
                "Functional verification",
                "Forms submit, flows complete, and data round-trips correctly. Functional regressions are recorded with the same evidence standard as security findings.",
              ],
              [
                <Camera key="4" size={14} />,
                "Evidence capture",
                "Screenshots, HTTP requests and responses, DOM snapshots, console output, and network traces are captured at the moment of observation.",
              ],
              [
                <Lock key="5" size={14} />,
                "Scope protection",
                "Every outbound request is validated against the authorized scope. Out-of-scope discoveries are reported, never executed.",
              ],
              [
                <FileText key="6" size={14} />,
                "Assessment reporting",
                "Export professional JSON, Markdown, or PDF reports with severity ranking, reproduction steps, and remediation guidance.",
              ],
            ].map(([icon, title, body]) => (
              <div key={title as string} className="bg-app-880 p-6">
                <span className="flex h-[28px] w-[28px] items-center justify-center rounded-[5px] border border-line bg-app-800 text-[#7fa9f0]">
                  {icon as React.ReactNode}
                </span>
                <h3 className="mt-4 text-[12.5px] font-semibold text-ink">{title as string}</h3>
                <p className="mt-2 text-[11px] leading-[1.8] text-muted">{body as string}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 2 · How the agent works */}
      <section id="how" className="border-b border-line bg-app-880">
        <div className="mx-auto max-w-[1240px] px-5 py-16">
          <SectionHeader
            eyebrow="02 · How the agent works"
            title="Observe, decide, act, verify — with a full audit trail."
            description="Every action the agent takes is recorded as an observable event. The decision log shows what was done and why, without exposing hidden reasoning."
          />

          <div className="mt-9 grid grid-cols-1 gap-8 lg:grid-cols-12">
            <div className="lg:col-span-5">
              <div className="space-y-0">
                {[
                  ["Observe", "Read the accessibility tree, network state, and DOM to understand the current application state."],
                  ["Decide", "Select the next test from the versioned catalogue based on the discovered surface and coverage targets."],
                  ["Act", "Dispatch a scoped request or browser interaction — always rate-limited, always logged."],
                  ["Verify", "Re-test suspected issues with control requests to eliminate false positives before recording."],
                  ["Capture", "Store the complete evidence bundle: request, response, DOM, console, network, screenshot."],
                  ["Report", "Rank findings by severity and assemble reproducible output for engineering teams."],
                ].map(([title, body], i) => (
                  <div key={title} className="flex gap-4 border-b border-line py-4 last:border-0">
                    <span className="flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-[4px] border border-line bg-app-800 font-mono text-[8.5px] text-dim">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <div>
                      <h3 className="text-[11.5px] font-semibold text-ink">{title}</h3>
                      <p className="mt-1.5 text-[10.5px] leading-[1.8] text-muted">{body}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="lg:col-span-7">
              <div className="overflow-hidden rounded-[6px] border border-line bg-app-850">
                <PanelHeader
                  title="Observable decision log"
                  subtitle="Auditable timeline · chain-of-thought is never exposed"
                  icon={<Terminal size={13} />}
                  action={
                    <div className="flex items-center gap-1.5">
                      <span className="h-[5px] w-[5px] rounded-full bg-[#4c8dff] animate-pulse-dot" />
                      <span className="font-mono text-[8px] uppercase tracking-[0.13em] text-[#7fa9f0]">
                        streaming
                      </span>
                    </div>
                  }
                />
                <div className="divide-y divide-line-soft">
                  {timeline.map((e, i) => (
                    <div key={i} className="flex items-start gap-3 px-4 py-2.5">
                      <span className="shrink-0 font-mono text-[9px] text-faint">{e.time}</span>
                      <span
                        className="shrink-0 rounded-[3px] border px-1.5 py-[1px] font-mono text-[7.5px] font-semibold tracking-[0.11em]"
                        style={{
                          color:
                            e.phase === "ACT"
                              ? "#7fa9f0"
                              : e.phase === "VERIFY"
                                ? "#f0b95c"
                                : e.phase === "ASSERT"
                                  ? "#f28286"
                                  : e.phase === "CAPTURE"
                                    ? "#66c07a"
                                    : e.phase === "SCOPE"
                                      ? "#66c07a"
                                      : "#98a1ab",
                          borderColor:
                            e.phase === "ACT"
                              ? "rgba(76,141,255,0.28)"
                              : e.phase === "VERIFY"
                                ? "rgba(245,166,35,0.28)"
                                : e.phase === "ASSERT"
                                  ? "rgba(229,72,77,0.28)"
                                  : "#22262c",
                        }}
                      >
                        {e.phase}
                      </span>
                      <div className="min-w-0">
                        <div className="text-[10.5px] text-ink-soft">{e.description}</div>
                        {e.detail ? (
                          <div className="mt-[2px] truncate font-mono text-[8.5px] text-faint">
                            {e.detail}
                          </div>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </div>
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line px-4 py-2 font-mono text-[8px] text-faint">
                  <span>events retained: full run</span>
                  <span>exportable: JSON / CSV</span>
                  <span>immutable: yes</span>
                  <span className="ml-auto text-[#66c07a]">audit log enabled</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 3 · Browser + security testing */}
      <section id="browser" className="border-b border-line">
        <div className="mx-auto max-w-[1240px] px-5 py-16">
          <SectionHeader
            eyebrow="03 · Browser + security testing"
            title="A controlled testing environment, not a consumer browser."
            description="The agent operates a instrumented browser session: current URL, page title, viewport, interaction state, console status, and network activity are always visible and always recorded."
          />

          <div className="mt-9">
            <BrowserPanel />
          </div>

          <div className="mt-6 grid grid-cols-1 gap-px overflow-hidden rounded-[6px] border border-line bg-line md:grid-cols-2 lg:grid-cols-4">
            {[
              [<Globe key="1" size={13} />, "Full-fidelity rendering", "Real Chromium execution with JavaScript, cookies, storage, and redirects — the same conditions a user experiences."],
              [<Terminal key="2" size={13} />, "Console instrumentation", "Errors, warnings, and DOM mutations are captured as they happen and attached to the relevant finding."],
              [<Layers key="3" size={13} />, "Network transparency", "Every request and response is recorded with timing, size, and status — including blocked and failed calls."],
              [<Cpu key="4" size={13} />, "Deterministic replay", "Sessions can be replayed with identical parameters to reproduce a finding weeks after discovery."],
            ].map(([icon, title, body]) => (
              <div key={title as string} className="bg-app-880 p-5">
                <span className="text-[#7fa9f0]">{icon as React.ReactNode}</span>
                <h3 className="mt-3 text-[11px] font-semibold text-ink">{title as string}</h3>
                <p className="mt-1.5 text-[10px] leading-[1.8] text-muted">{body as string}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 4 · Evidence-backed findings */}
      <section id="evidence" className="border-b border-line bg-app-880">
        <div className="mx-auto max-w-[1240px] px-5 py-16">
          <SectionHeader
            eyebrow="04 · Evidence-backed findings"
            title="Know exactly why a finding exists."
            description="Findings are only recorded after deterministic verification. Each one ships with a complete evidence bundle so an engineer can reproduce the issue without re-running the agent."
          />

          <div className="mt-9 grid grid-cols-1 gap-6 lg:grid-cols-12">
            <div className="lg:col-span-5">
              <div className="overflow-hidden rounded-[6px] border border-line bg-app-850">
                <PanelHeader
                  title="Verified findings"
                  subtitle="Ranked by severity · evidence attached"
                  action={<StatusBadge status="confirmed" />}
                />
                <div className="divide-y divide-line-soft">
                  {findings.slice(0, 6).map((f) => (
                    <div key={f.id} className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <SeverityBadge severity={f.severity} />
                        <StatusBadge status={f.status} />
                        <span className="ml-auto font-mono text-[8px] text-faint">{f.id}</span>
                      </div>
                      <div className="mt-2 text-[11px] font-medium leading-snug text-ink">
                        {f.title}
                      </div>
                      <div className="mt-1 font-mono text-[8.5px] text-faint">
                        {f.target}
                        {f.path} · {f.cwe} · CVSS {f.cvss}
                      </div>
                      <div className="mt-2 flex items-center gap-1.5">
                        {[0, 1, 2].slice(0, Math.min(3, f.evidenceCount)).map((i) => (
                          <span
                            key={i}
                            className="h-[14px] w-[14px] rounded-[3px] border border-line bg-app-800"
                          />
                        ))}
                        <span className="font-mono text-[8px] text-faint">
                          {f.evidenceCount} evidence artifacts
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="mt-4 rounded-[6px] border border-line bg-app-850 p-4">
                <div className="text-[8px] font-semibold uppercase tracking-[0.13em] text-faint">
                  Verification standard
                </div>
                <div className="mt-3 space-y-2.5">
                  {[
                    ["Reproducible", "3 / 3 attempts"],
                    ["Control requests", "always included"],
                    ["False-positive review", "automated + manual"],
                    ["Evidence completeness", "5 artifact types"],
                  ].map(([k, v]) => (
                    <div key={k} className="flex items-center justify-between">
                      <span className="flex items-center gap-1.5 text-[9.5px] text-muted">
                        <CheckCircle2 size={9} className="text-[#66c07a]" />
                        {k}
                      </span>
                      <span className="font-mono text-[8.5px] text-ink-soft">{v}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="lg:col-span-7">
              <EvidenceViewer evidence={findings[1].evidence} findingId={findings[1].id} />

              <div className="mt-4 grid grid-cols-1 gap-px overflow-hidden rounded-[6px] border border-line bg-line sm:grid-cols-3">
                {[
                  ["Request capture", "Headers, cookies, payloads, and scope verification for every dispatched call."],
                  ["Response analysis", "Status, headers, body, and the exact delta that triggered the finding."],
                  ["DOM & console", "Rendered state, mutation observations, and runtime errors at capture time."],
                ].map(([title, body]) => (
                  <div key={title} className="bg-app-850 p-4">
                    <h3 className="text-[10px] font-semibold uppercase tracking-[0.11em] text-ink-soft">
                      {title}
                    </h3>
                    <p className="mt-1.5 text-[9.5px] leading-[1.8] text-dim">{body}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 5 · Scope protection */}
      <section id="scope" className="border-b border-line">
        <div className="mx-auto max-w-[1240px] px-5 py-16">
          <SectionHeader
            eyebrow="05 · Scope protection"
            title="The agent cannot leave the authorized target."
            description="Scope is not a guideline — it is an enforced boundary. Origins, paths, methods, rate limits, and request budgets are validated before every single request."
          />

          <div className="mt-9">
            <ScopeGuard />
          </div>

          <div className="mt-6 grid grid-cols-1 gap-px overflow-hidden rounded-[6px] border border-line bg-line md:grid-cols-3">
            {[
              ["Origin validation", "Every request is checked against the allowed origin list. Redirects that leave the scope are followed no further and recorded as blocked."],
              ["Path exclusions", "Excluded paths are matched before dispatch — including wildcard patterns — and violations abort the run immediately."],
              ["Rate & budget limits", "Request-per-second limits and hard request budgets protect the target from load, with exponential backoff on error thresholds."],
            ].map(([title, body]) => (
              <div key={title} className="bg-app-880 p-5">
                <div className="flex items-center gap-2">
                  <Lock size={12} className="text-[#66c07a]" />
                  <h3 className="text-[10.5px] font-semibold uppercase tracking-[0.11em] text-ink-soft">
                    {title}
                  </h3>
                </div>
                <p className="mt-2.5 text-[10px] leading-[1.85] text-muted">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 6 · Reporting */}
      <section id="reporting" className="border-b border-line bg-app-880">
        <div className="mx-auto max-w-[1240px] px-5 py-16">
          <SectionHeader
            eyebrow="06 · Reporting"
            title="Assessment output that stands up to scrutiny."
            description="Reports are generated from verified findings and captured evidence — structured for engineers, readable for stakeholders, and exportable to the systems your team already uses."
          />

          <div className="mt-9 grid grid-cols-1 gap-6 lg:grid-cols-12">
            <div className="lg:col-span-7">
              <div className="overflow-hidden rounded-[6px] border border-line bg-app-850">
                <div className="flex items-center gap-3 border-b border-line px-4 py-2.5">
                  <FileText size={13} className="text-dim" />
                  <span className="text-[10px] font-semibold uppercase tracking-[0.11em] text-ink-soft">
                    assessment-run_8f31c2.pdf
                  </span>
                  <span className="ml-auto font-mono text-[8px] text-faint">34 pages · signed</span>
                </div>

                <div className="p-5">
                  <div className="font-mono text-[7.5px] uppercase tracking-[0.16em] text-faint">
                    Confidential · Authorized security assessment
                  </div>
                  <h3 className="mt-2 text-[15px] font-semibold leading-tight tracking-[-0.015em] text-ink">
                    Web Application Security Assessment Report
                  </h3>
                  <div className="mt-1.5 font-mono text-[9px] text-muted">
                    Target: https://app.example.com · Run: run_8f31c2 · Date: 2026-09-19
                  </div>

                  <div className="mt-4 border-t border-line pt-4">
                    <div className="text-[9px] font-semibold uppercase tracking-[0.11em] text-ink-soft">
                      1 · Executive summary
                    </div>
                    <p className="mt-2 text-[10px] leading-[1.9] text-muted">
                      The autonomous assessment executed 147 tests and 1,284 HTTP requests against
                      the authorized target over a 27-minute window. Twenty-four findings were
                      recorded after deterministic verification, of which one is rated critical and
                      three are rated high. All findings are supported by captured evidence,
                      including request and response pairs, DOM state, and console output.
                    </p>
                  </div>

                  <div className="mt-4 border-t border-line pt-4">
                    <div className="text-[9px] font-semibold uppercase tracking-[0.11em] text-ink-soft">
                      3 · Findings summary
                    </div>
                    <div className="mt-2.5 overflow-hidden rounded-[4px] border border-line">
                      <table className="w-full border-collapse">
                        <thead>
                          <tr className="border-b border-line bg-app-880">
                            {["ID", "Severity", "Finding", "Status", "CVSS"].map((h) => (
                              <th
                                key={h}
                                className="px-2.5 py-1.5 text-left text-[7.5px] font-semibold uppercase tracking-[0.12em] text-faint"
                              >
                                {h}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {findings.slice(0, 5).map((f) => (
                            <tr key={f.id} className="border-b border-line-soft last:border-0">
                              <td className="px-2.5 py-1.5 font-mono text-[7.5px] text-faint">{f.id}</td>
                              <td className="px-2.5 py-1.5">
                                <SeverityBadge severity={f.severity} />
                              </td>
                              <td className="max-w-[190px] truncate px-2.5 py-1.5 text-[8.5px] text-ink-soft">
                                {f.title}
                              </td>
                              <td className="px-2.5 py-1.5 text-[7.5px] capitalize text-muted">
                                {f.status}
                              </td>
                              <td className="px-2.5 py-1.5 font-mono text-[7.5px] text-muted">
                                {f.cvss}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line px-4 py-2 font-mono text-[7.5px] text-faint">
                  <span>generated by AI Testing Agent v2.4.1</span>
                  <span>report hash: 7c21…9e4f</span>
                  <span className="ml-auto">digitally signed</span>
                </div>
              </div>
            </div>

            <div className="lg:col-span-5">
              <div className="space-y-px overflow-hidden rounded-[6px] border border-line bg-line">
                {[
                  ["JSON", "Machine-readable output for pipelines, SIEM ingestion, and ticketing automation.", "ata-report.schema v3"],
                  ["Markdown", "Structured text for repositories, pull requests, and engineering documentation.", "CommonMark"],
                  ["PDF", "Formatted assessment document for stakeholders, auditors, and compliance records.", "A4 · signed"],
                ].map(([format, description, meta]) => (
                  <div key={format} className="bg-app-850 p-5">
                    <div className="flex items-center gap-2">
                      <FileText size={12} className="text-[#7fa9f0]" />
                      <h3 className="text-[11px] font-semibold text-ink">{format}</h3>
                      <span className="ml-auto font-mono text-[8px] text-faint">{meta}</span>
                    </div>
                    <p className="mt-2 text-[10px] leading-[1.8] text-muted">{description}</p>
                  </div>
                ))}
              </div>

              <div className="mt-4 rounded-[6px] border border-line bg-app-850 p-5">
                <div className="text-[8px] font-semibold uppercase tracking-[0.13em] text-faint">
                  Coverage matrix included in every report
                </div>
                <div className="mt-4 space-y-3">
                  {coverageByCategory.slice(0, 5).map((c) => (
                    <div key={c.category} className="flex items-center gap-3">
                      <span className="w-[104px] shrink-0 text-[9px] text-muted">{c.category}</span>
                      <div className="h-[5px] flex-1 overflow-hidden rounded-[2px] bg-app-750">
                        <div
                          className="h-full rounded-[2px]"
                          style={{
                            width: `${c.coverage}%`,
                            backgroundColor: c.coverage >= 90 ? "#46a758" : "#4c8dff",
                          }}
                        />
                      </div>
                      <span className="w-[30px] shrink-0 text-right font-mono text-[8.5px] text-ink-soft">
                        {c.coverage}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 7 · Architecture */}
      <section id="architecture" className="border-b border-line">
        <div className="mx-auto max-w-[1240px] px-5 py-16">
          <SectionHeader
            eyebrow="07 · Technical architecture"
            title="Built like infrastructure, not a wrapper."
            description="A modular execution pipeline designed for reproducibility, observability, and safe operation against production systems."
          />

          <div className="mt-9 overflow-hidden rounded-[6px] border border-line">
            <div className="grid grid-cols-1 gap-px bg-line lg:grid-cols-5">
              {[
                [<Workflow key="1" size={14} />, "Orchestrator", "Run planning, coverage targets, scheduling, and state management across the execution lifecycle."],
                [<Cpu key="2" size={14} />, "Browser runtime", "Instrumented Chromium sessions with DOM access, network interception, and console capture."],
                [<ShieldCheck key="3" size={14} />, "Verification engine", "Deterministic probe execution, control comparisons, and statistical response analysis."],
                [<Database key="4" size={14} />, "Evidence store", "Immutable, hashed artifact storage with chain-of-custody tracking and retention policy."],
                [<FileText key="5" size={14} />, "Reporting layer", "Severity ranking, remediation guidance, and export to JSON, Markdown, and PDF."],
              ].map(([icon, title, body]) => (
                <div key={title as string} className="bg-app-880 p-5">
                  <span className="flex h-[26px] w-[26px] items-center justify-center rounded-[5px] border border-line bg-app-800 text-[#7fa9f0]">
                    {icon as React.ReactNode}
                  </span>
                  <h3 className="mt-3 text-[10.5px] font-semibold uppercase tracking-[0.11em] text-ink-soft">
                    {title as string}
                  </h3>
                  <p className="mt-2 text-[9.5px] leading-[1.85] text-muted">{body as string}</p>
                </div>
              ))}
            </div>

            <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-line bg-app-880 px-5 py-3">
              {[
                "stateless execution",
                "horizontal scaling",
                "signed evidence manifests",
                "deterministic replay",
                "rate-limit aware",
                "audit logging",
              ].map((item) => (
                <span key={item} className="flex items-center gap-1.5">
                  <CheckCircle2 size={9} className="text-[#66c07a]" />
                  <span className="font-mono text-[8.5px] text-dim">{item}</span>
                </span>
              ))}
            </div>
          </div>

          <div className="mt-6 grid grid-cols-1 gap-px overflow-hidden rounded-[6px] border border-line bg-line md:grid-cols-3">
            {[
              ["Deployment", "Runs as a managed service or self-hosted within your own infrastructure, with the same execution guarantees."],
              ["Integrations", "Native delivery to Jira, Slack, GitHub, Splunk, ServiceNow, and any HTTP endpoint via signed webhooks."],
              ["Compliance", "Evidence retention policies, audit exports, and report signing support SOC 2, ISO 27001, and PCI DSS workflows."],
            ].map(([title, body]) => (
              <div key={title} className="bg-app-880 p-5">
                <h3 className="text-[10px] font-semibold uppercase tracking-[0.11em] text-ink-soft">
                  {title}
                </h3>
                <p className="mt-2 text-[9.5px] leading-[1.85] text-muted">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-b border-line bg-app-880">
        <div className="mx-auto flex max-w-[1240px] flex-col items-start gap-6 px-5 py-16 lg:flex-row lg:items-center">
          <div className="max-w-[620px]">
            <h2 className="text-[24px] font-semibold leading-[1.2] tracking-[-0.022em] text-ink">
              Put the agent to work on a real application.
            </h2>
            <p className="mt-3 text-[12.5px] leading-[1.8] text-muted">
              Open the workspace, configure an authorized target, and watch the agent explore,
              verify, and document what it finds — with evidence for every conclusion.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5 lg:ml-auto">
            <Link to="/app" className="btn-primary !px-5 !py-[10px] !text-[12px]">
              Open the workspace
              <ArrowRight size={13} />
            </Link>
            <Link to="/app/runs/new" className="btn-secondary !px-4 !py-[10px] !text-[11.5px]">
              Configure a test run
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer>
        <div className="mx-auto max-w-[1240px] px-5 py-10">
          <div className="grid grid-cols-2 gap-8 md:grid-cols-4">
            <div className="col-span-2 md:col-span-1">
              <div className="flex items-center gap-2.5">
                <span className="flex h-[26px] w-[26px] items-center justify-center rounded-[5px] border border-line-strong bg-app-800">
                  <ShieldCheck size={13} className="text-ink" />
                </span>
                <span className="text-[11.5px] font-semibold text-ink">AI Testing Agent</span>
              </div>
              <p className="mt-3 max-w-[240px] text-[9.5px] leading-[1.9] text-faint">
                Autonomous web application security and functional testing with evidence-backed
                findings and enforced scope protection.
              </p>
            </div>

            {[
              ["Product", ["Overview", "How it works", "Browser testing", "Evidence", "Reporting"]],
              ["Platform", ["Architecture", "Integrations", "Security", "API access", "Changelog"]],
              ["Resources", ["Documentation", "Methodology", "OWASP mapping", "Sample report", "Status"]],
            ].map(([title, items]) => (
              <div key={title as string}>
                <h4 className="text-[8px] font-semibold uppercase tracking-[0.15em] text-faint">
                  {title as string}
                </h4>
                <ul className="mt-3 space-y-2">
                  {(items as string[]).map((item) => (
                    <li key={item}>
                      <a href="#overview" className="text-[9.5px] text-dim transition-colors hover:text-muted">
                        {item}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          <div className="mt-10 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-line pt-5">
            <span className="font-mono text-[8px] text-faint">© 2026 AI Testing Agent</span>
            <span className="font-mono text-[8px] text-faint">v2.4.1</span>
            <span className="font-mono text-[8px] text-faint">
              authorized testing only · all activity is logged
            </span>
            <div className="ml-auto flex items-center gap-4">
              {["Privacy", "Terms", "Security", "Contact"].map((l) => (
                <a key={l} href="#overview" className="font-mono text-[8px] text-faint hover:text-muted">
                  {l}
                </a>
              ))}
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

function SectionHeader({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <div className="max-w-[720px]">
      <div className="flex items-center gap-2">
        <span className="h-[5px] w-[5px] rounded-[1px] bg-[#4c8dff]" />
        <span className="font-mono text-[8.5px] font-semibold uppercase tracking-[0.17em] text-dim">
          {eyebrow}
        </span>
      </div>
      <h2 className="mt-4 text-[25px] font-semibold leading-[1.22] tracking-[-0.021em] text-ink">
        {title}
      </h2>
      <p className="mt-3.5 text-[12px] leading-[1.85] text-muted">{description}</p>
    </div>
  );
}
