import { Link } from "react-router-dom";
import { Plus, Activity, Download } from "lucide-react";
import { StatusBadge, PanelHeader, SeverityBadge } from "../components/ui";
import { useHistory, useLiveState, useScanStatus } from "../lib/useLive";
import { countBySeverity, downloadUrl } from "../lib/api";

export function Runs() {
  const live = useLiveState();
  const scan = useScanStatus();
  const { runs } = useHistory();

  const running = live.status === "running" || scan.running;
  const liveCounts = countBySeverity(live.findings || []);

  return (
    <div className="px-4 py-5 sm:px-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-[18px] font-semibold tracking-[-0.012em] text-ink">Runs</h1>
          <p className="mt-1 max-w-[620px] text-[11.5px] leading-relaxed text-muted">
            Every execution is recorded with its findings, severity mix, and downloadable report
            artifacts.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link to="/app/runs/new" className="btn-primary">
            <Plus size={12} />
            New test run
          </Link>
        </div>
      </div>

      {/* Active run */}
      <div className="mt-4 overflow-hidden rounded-[6px] border border-[rgba(76,141,255,0.24)] bg-app-850">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-b border-line bg-[rgba(76,141,255,0.05)] px-4 py-3">
          <div className="flex items-center gap-2">
            <Activity size={13} className="text-[#4c8dff]" />
            <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.13em] text-[#7fa9f0]">
              Active run
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-x-5 gap-y-1 font-mono text-[9.5px] text-dim">
            <span>
              target: <span className="text-ink-soft">{live.target || "—"}</span>
            </span>
            <span>
              stage: <span className="text-ink-soft">{live.stage || "—"}</span>
            </span>
            <span>
              config: <span className="text-ink-soft">{scan.config || "—"}</span>
            </span>
            <span>
              findings: <span className="text-ink-soft">{(live.findings || []).length}</span>
            </span>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <StatusBadge status={running ? "running" : "idle"} pulse={running} />
            <Link to="/app" className="btn-secondary !py-[5px] !text-[10px]">
              Open workspace
            </Link>
          </div>
        </div>

        <div className="max-h-[220px] overflow-y-auto p-4 font-mono text-[10.5px] leading-relaxed text-muted">
          {(scan.log_tail || []).length ? (
            (scan.log_tail || []).map((line, i) => (
              <div key={i} className="whitespace-pre-wrap break-all">
                {line}
              </div>
            ))
          ) : (
            <div className="text-faint">
              {running
                ? "Scan started — output streams here as the agent works."
                : "No active scan. Start one from New test run."}
            </div>
          )}
        </div>
      </div>

      {/* Run history */}
      <div className="mt-5 overflow-hidden rounded-[6px] border border-line bg-app-850">
        <PanelHeader
          title="Run history"
          subtitle={`${runs.length} recorded executions`}
          action={
            <div className="flex items-center gap-1.5 font-mono text-[8.5px] text-faint">
              <span>newest first</span>
            </div>
          }
        />

        {runs.length ? (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="border-b border-line">
                  {["Started", "Target", "Status", "Severity mix", "Findings", "Downloads"].map(
                    (h) => (
                      <th
                        key={h}
                        className="whitespace-nowrap px-4 py-2.5 text-left text-[8.5px] font-semibold uppercase tracking-[0.13em] text-faint"
                      >
                        {h}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => {
                  const s = r.summary || { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
                  return (
                    <tr
                      key={r.stamp}
                      className="border-b border-line-soft transition-colors last:border-0 hover:bg-app-800"
                    >
                      <td className="whitespace-nowrap px-4 py-3 font-mono text-[10px] text-muted">
                        {(r.started_at || "").slice(0, 16).replace("T", " ")}
                      </td>
                      <td className="max-w-[280px] truncate px-4 py-3 font-mono text-[10px] text-ink-soft">
                        {r.target}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={r.status === "completed" ? "completed" : "failed"} />
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1">
                          {(["critical", "high", "medium", "low", "info"] as const).map((sev) =>
                            (s[sev] || 0) > 0 ? (
                              <SeverityBadge key={sev} severity={sev} />
                            ) : null
                          )}
                          {r.finding_count === 0 ? (
                            <span className="font-mono text-[9px] text-faint">clean</span>
                          ) : null}
                        </div>
                      </td>
                      <td className="px-4 py-3 font-mono text-[10px] text-muted">
                        {r.finding_count}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-x-3 gap-y-1">
                          {(["html", "json", "csv"] as const).map((f) => (
                            <a
                              key={f}
                              className="inline-flex items-center gap-1 font-mono text-[9.5px] text-[#7fa9f0] hover:underline"
                              href={downloadUrl(r.stamp, f)}
                            >
                              <Download size={9} />
                              {f}
                            </a>
                          ))}
                          {r.has_testio ? (
                            <a
                              className="inline-flex items-center gap-1 font-mono text-[9.5px] text-[#7fa9f0] hover:underline"
                              href={downloadUrl(r.stamp, "testio")}
                            >
                              <Download size={9} />
                              testio
                            </a>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="px-6 py-12 text-center">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-soft">
              No runs yet
            </p>
            <p className="mx-auto mt-1.5 max-w-[380px] text-[11px] leading-relaxed text-dim">
              Scans you start will appear here with their severity mix and report downloads.
            </p>
          </div>
        )}
      </div>

      {/* Live severity mix */}
      {liveCounts && (live.findings || []).length > 0 ? (
        <p className="mt-3 font-mono text-[9px] text-faint">
          live mix — critical {liveCounts.critical} · high {liveCounts.high} · medium{" "}
          {liveCounts.medium} · low {liveCounts.low} · info {liveCounts.info}
        </p>
      ) : null}
    </div>
  );
}
