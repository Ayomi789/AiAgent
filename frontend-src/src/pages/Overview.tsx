import { Link } from "react-router-dom";
import { Plus, Globe, Clock, Activity, ArrowUpRight, Terminal, GitCompare } from "lucide-react";
import { PanelHeader, SeverityBadge, StatusBadge } from "../components/ui";
import { SeverityStack } from "../components/Charts";
import { useLiveState, useScanStatus, useDiff } from "../lib/useLive";
import { countBySeverity, toFinding } from "../lib/api";

function fmtElapsed(s?: number): string {
  const t = s ?? 0;
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const sec = Math.floor(t % 60);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

export function Overview() {
  const live = useLiveState();
  const scan = useScanStatus();
  const diff = useDiff();

  const running = live.status === "running" || scan.running;
  const counts = countBySeverity(live.findings || []);
  const total = (live.findings || []).length;
  const recent = (live.findings || []).slice(0, 6).map((f) => toFinding(f, ""));

  return (
    <div className="px-4 py-5 sm:px-6">
      {/* Operation header */}
      <section className="animate-fade-up">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2.5">
              <h1 className="text-[19px] font-semibold leading-tight tracking-[-0.015em] text-ink">
                Sentinel Console
              </h1>
              <StatusBadge status={running ? "running" : live.status || "idle"} pulse={running} />
            </div>

            <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-1.5">
              <div className="flex items-center gap-2">
                <Globe size={12} className="text-faint" />
                <span className="text-[9px] font-semibold uppercase tracking-[0.12em] text-faint">
                  Target
                </span>
                <span className="font-mono text-[11.5px] text-[#7fa9f0]">
                  {live.target || "—"}
                </span>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-[9px] font-semibold uppercase tracking-[0.12em] text-faint">
                  Stage
                </span>
                <span className="font-mono text-[11px] text-ink-soft">{live.stage || "—"}</span>
              </div>

              {(live.step || live.max_steps) ? (
                <div className="flex items-center gap-2">
                  <span className="text-[9px] font-semibold uppercase tracking-[0.12em] text-faint">
                    Step
                  </span>
                  <span className="font-mono text-[11px] text-ink-soft">
                    {live.step ?? 0}/{live.max_steps ?? 0}
                  </span>
                </div>
              ) : null}

              <div className="flex items-center gap-1.5">
                <Clock size={11} className="text-faint" />
                <span className="font-mono text-[11px] text-ink-soft">
                  {fmtElapsed(live.elapsed_seconds)}
                </span>
                <span className="text-[9px] text-faint">elapsed</span>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Link to="/app/runs/new" className="btn-primary">
              <Plus size={12} />
              New run
            </Link>
          </div>
        </div>

        {/* Run phase indicator */}
        <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 rounded-[6px] border border-line bg-app-880 px-4 py-2.5">
          <div className="flex items-center gap-2">
            <span
              className={`h-[6px] w-[6px] rounded-full ${running ? "bg-[#4c8dff] animate-pulse-dot" : "bg-[#4d555e]"}`}
            />
            <span className="font-mono text-[9px] font-semibold uppercase tracking-[0.14em] text-[#7fa9f0]">
              {running ? (live.stage || "Scan running") : "No active scan"}
            </span>
          </div>
          <div className="h-3 w-px bg-line" />
          <div className="flex flex-wrap items-center gap-x-5 gap-y-1 font-mono text-[9px] text-faint">
            <span>config: {scan.config || "—"}</span>
            <span>mode: {scan.skip_llm ? "deterministic (no LLM)" : "full (LLM + browser)"}</span>
            {scan.started ? <span>started: {scan.started.slice(0, 16).replace("T", " ")}</span> : null}
          </div>
        </div>
      </section>

      {/* Metric strip */}
      <section className="mt-5 animate-fade-up">
        <div className="grid grid-cols-2 gap-px overflow-hidden rounded-[6px] border border-line bg-line sm:grid-cols-3 lg:grid-cols-6">
          {[
            { label: "Findings", value: total.toString(), accent: "#e8ebee" },
            { label: "Critical", value: counts.critical.toString(), accent: "#e5484d" },
            { label: "High", value: counts.high.toString(), accent: "#f76b15" },
            { label: "Medium", value: counts.medium.toString(), accent: "#f5a623" },
            { label: "Low", value: counts.low.toString(), accent: "#6c8fb3" },
            { label: "Info", value: counts.info.toString(), accent: "#7d8794" },
          ].map((m) => (
            <div key={m.label} className="bg-app-880 px-4 py-3">
              <div className="text-[8.5px] font-semibold uppercase tracking-[0.13em] text-faint">
                {m.label}
              </div>
              <div
                className="mt-1 font-mono text-[19px] font-medium leading-none tracking-[-0.01em]"
                style={{ color: m.accent }}
              >
                {m.value}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Scan log + diff */}
      <section className="mt-5 grid grid-cols-1 gap-4 xl:grid-cols-12">
        <div className="animate-fade-up overflow-hidden rounded-[6px] border border-line bg-app-850 xl:col-span-8">
          <PanelHeader
            title="Agent log"
            subtitle={scan.running ? "Streaming from the running scan" : "Last completed scan output"}
            icon={<Terminal size={13} />}
          />
          <div className="max-h-[320px] overflow-y-auto p-4 font-mono text-[10.5px] leading-relaxed text-muted">
            {(scan.log_tail || []).length ? (
              (scan.log_tail || []).map((line, i) => (
                <div key={i} className="whitespace-pre-wrap break-all">
                  {line}
                </div>
              ))
            ) : (
              <div className="text-faint">
                No output yet — start a run and the agent's log streams here.
              </div>
            )}
          </div>
        </div>

        <div className="animate-fade-up overflow-hidden rounded-[6px] border border-line bg-app-850 xl:col-span-4">
          <PanelHeader
            title="Findings vs previous run"
            subtitle="New / fixed / unchanged"
            icon={<GitCompare size={13} />}
          />
          <div className="space-y-2.5 p-4">
            <SeverityStack
              segments={[
                { label: "Critical", value: counts.critical, color: "#e5484d" },
                { label: "High", value: counts.high, color: "#f76b15" },
                { label: "Medium", value: counts.medium, color: "#f5a623" },
                { label: "Low", value: counts.low, color: "#6c8fb3" },
                { label: "Info", value: counts.info, color: "#4d555e" },
              ]}
              height={8}
            />
            <div className="grid grid-cols-3 gap-2 pt-1">
              {[
                ["New", diff?.counts.new ?? 0, "#e5484d"],
                ["Fixed", diff?.counts.fixed ?? 0, "#46a758"],
                ["Unchanged", diff?.counts.unchanged ?? 0, "#98a1ab"],
              ].map(([label, value, color]) => (
                <div key={label as string} className="rounded-[5px] border border-line bg-app-880 px-3 py-2.5">
                  <div className="text-[8.5px] font-semibold uppercase tracking-[0.13em] text-faint">
                    {label as string}
                  </div>
                  <div className="mt-1 font-mono text-[17px] leading-none" style={{ color: color as string }}>
                    {value as number}
                  </div>
                </div>
              ))}
            </div>
            <p className="text-[9.5px] leading-relaxed text-faint">
              The baseline gate compares each run against the previous sealed report — regressions
              fail CI before they ship.
            </p>
          </div>
        </div>
      </section>

      {/* Recent findings */}
      <section className="mt-5 animate-fade-up">
        <div className="overflow-hidden rounded-[6px] border border-line bg-app-850">
          <PanelHeader
            title="Recent findings"
            subtitle="Ordered by severity · evidence attached to every entry"
            icon={<Activity size={13} />}
            action={
              <Link to="/app/findings" className="btn-secondary !py-[5px] !text-[10.5px]">
                View all findings
                <ArrowUpRight size={11} />
              </Link>
            }
          />
          {recent.length ? (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="border-b border-line">
                    {["Severity", "Finding", "Target", "Category", ""].map((h) => (
                      <th
                        key={h}
                        className="px-4 py-2 text-left text-[8.5px] font-semibold uppercase tracking-[0.13em] text-faint"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {recent.map((f) => (
                    <tr
                      key={f.id}
                      className="border-b border-line-soft transition-colors last:border-0 hover:bg-app-800"
                    >
                      <td className="px-4 py-2.5">
                        <SeverityBadge severity={f.severity} />
                      </td>
                      <td className="max-w-[380px] px-4 py-2.5">
                        <Link
                          to={`/app/findings/${f.id}`}
                          className="block truncate text-[11.5px] text-ink hover:text-[#7fa9f0]"
                        >
                          {f.title}
                        </Link>
                        <div className="mt-[2px] font-mono text-[9px] text-faint">{f.id}</div>
                      </td>
                      <td className="px-4 py-2.5 font-mono text-[10px] text-muted">
                        {f.target}
                        <span className="text-faint">{f.path}</span>
                      </td>
                      <td className="px-4 py-2.5 text-[10px] text-dim">{f.category}</td>
                      <td className="px-4 py-2.5 text-right">
                        <Link
                          to={`/app/findings/${f.id}`}
                          className="font-mono text-[9.5px] text-[#7fa9f0] hover:underline"
                        >
                          inspect
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="px-6 py-12 text-center">
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-soft">
                No findings yet
              </p>
              <p className="mx-auto mt-1.5 max-w-[380px] text-[11px] leading-relaxed text-dim">
                Run your first scan and verified findings will stream in here, ordered by severity.
              </p>
              <Link to="/app/runs/new" className="btn-primary mx-auto mt-4">
                Start a run
              </Link>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-x-5 gap-y-1 border-t border-line px-4 py-2 font-mono text-[8.5px] text-faint">
            <span>
              showing {recent.length} of {total}
            </span>
            <span>sorted by severity desc</span>
          </div>
        </div>
      </section>
    </div>
  );
}
