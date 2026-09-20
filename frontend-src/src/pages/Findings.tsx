import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Search, ArrowUpRight, FileSearch } from "lucide-react";
import { SeverityBadge, StatusBadge, PanelHeader } from "../components/ui";
import { SeverityStack } from "../components/Charts";
import { useHistory, useLiveState } from "../lib/useLive";
import {
  countBySeverity,
  fetchReportFindings,
  toFinding,
  type ApiFinding,
} from "../lib/api";
import { SEVERITY_ORDER, SEVERITY_META } from "../lib/types";
import type { Severity } from "../lib/types";

export function Findings() {
  const live = useLiveState();
  const { runs } = useHistory();
  const [stamp, setStamp] = useState<string>("live");
  const [reportFindings, setReportFindings] = useState<ApiFinding[] | null>(null);
  const [severityFilter, setSeverityFilter] = useState<Severity | "all">("all");
  const [query, setQuery] = useState("");

  const liveList: ApiFinding[] = live.findings || [];
  const running = live.status === "running";

  useEffect(() => {
    if (stamp === "live") {
      setReportFindings(null);
      return;
    }
    let alive = true;
    fetchReportFindings(stamp)
      .then((f) => {
        if (alive) setReportFindings(f);
      })
      .catch(() => {
        if (alive) setReportFindings([]);
      });
    return () => {
      alive = false;
    };
  }, [stamp]);

  const source: ApiFinding[] = stamp === "live" ? liveList : (reportFindings ?? []);
  const runLabel =
    stamp === "live" ? "current run" : runs.find((r) => r.stamp === stamp)?.target || stamp;
  const list = useMemo(
    () => source.map((f) => toFinding(f, stamp === "live" ? "live" : stamp)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [source, stamp]
  );
  const counts = useMemo(() => countBySeverity(source), [source]);

  const filtered = useMemo(() => {
    return list.filter((f) => {
      if (severityFilter !== "all" && f.severity !== severityFilter) return false;
      if (query.trim()) {
        const q = query.toLowerCase();
        return (
          f.title.toLowerCase().includes(q) ||
          f.path.toLowerCase().includes(q) ||
          f.target.toLowerCase().includes(q) ||
          f.id.toLowerCase().includes(q) ||
          f.category.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [list, severityFilter, query]);

  return (
    <div className="px-4 py-5 sm:px-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-[18px] font-semibold tracking-[-0.012em] text-ink">Findings</h1>
          <p className="mt-1 max-w-[620px] text-[11.5px] leading-relaxed text-muted">
            Every entry is backed by captured evidence. Findings are only recorded after
            deterministic verification.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-faint" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Filter by title, path, target…"
              className="field w-[268px] py-[6px] pl-8 text-[11px]"
              aria-label="Filter findings"
            />
          </div>
          <select
            className="field w-auto py-[6px] text-[11px]"
            value={stamp}
            onChange={(e) => setStamp(e.target.value)}
            aria-label="Select run"
          >
            <option value="live">Current run{running ? " (live)" : ""}</option>
            {runs.map((r) => (
              <option key={r.stamp} value={r.stamp}>
                {(r.started_at || "").slice(0, 16).replace("T", " ")} · {r.target} ·{" "}
                {r.finding_count}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Severity summary */}
      <div className="mt-4 overflow-hidden rounded-[6px] border border-line bg-app-850">
        <div className="grid grid-cols-2 gap-px bg-line sm:grid-cols-3 lg:grid-cols-6">
          <button
            onClick={() => setSeverityFilter("all")}
            className="bg-app-850 px-4 py-3 text-left transition-colors hover:bg-app-800"
            style={severityFilter === "all" ? { backgroundColor: "#1a1e23" } : undefined}
          >
            <div className="text-[8.5px] font-semibold uppercase tracking-[0.13em] text-faint">
              All severities
            </div>
            <div className="mt-1 font-mono text-[19px] leading-none text-ink">{list.length}</div>
            <div className="mt-2">
              <SeverityStack
                height={5}
                segments={SEVERITY_ORDER.map((s) => ({
                  label: s,
                  value: counts[s],
                  color: SEVERITY_META[s].color,
                }))}
              />
            </div>
          </button>

          {SEVERITY_ORDER.map((s) => (
            <button
              key={s}
              onClick={() => setSeverityFilter(severityFilter === s ? "all" : s)}
              className="bg-app-850 px-4 py-3 text-left transition-colors hover:bg-app-800"
              style={severityFilter === s ? { backgroundColor: "#1a1e23" } : undefined}
            >
              <div className="flex items-center gap-1.5">
                <span
                  className="h-[5px] w-[5px] rounded-[1px]"
                  style={{ backgroundColor: SEVERITY_META[s].color }}
                />
                <span className="text-[8.5px] font-semibold uppercase tracking-[0.13em] text-faint">
                  {SEVERITY_META[s].label}
                </span>
              </div>
              <div
                className="mt-1 font-mono text-[19px] leading-none"
                style={{ color: SEVERITY_META[s].text }}
              >
                {counts[s]}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="mt-4 overflow-hidden rounded-[6px] border border-line bg-app-850">
        <PanelHeader
          title={runLabel}
          subtitle={`${filtered.length} of ${list.length} findings`}
        />
        {filtered.length ? (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="border-b border-line">
                  {["Severity", "Finding", "Target", "Category", "Status", ""].map((h) => (
                    <th
                      key={h}
                      className="whitespace-nowrap px-4 py-2.5 text-left text-[8.5px] font-semibold uppercase tracking-[0.13em] text-faint"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((f) => (
                  <tr
                    key={f.id}
                    className="group border-b border-line-soft transition-colors last:border-0 hover:bg-app-800"
                  >
                    <td className="px-4 py-3 align-top">
                      <SeverityBadge severity={f.severity} />
                    </td>
                    <td className="max-w-[420px] px-4 py-3 align-top">
                      <Link
                        to={`/app/findings/${f.id}?run=${stamp}`}
                        className="block text-[11.5px] font-medium leading-snug text-ink hover:text-[#7fa9f0]"
                      >
                        {f.title}
                      </Link>
                      <div className="mt-1 flex items-center gap-2">
                        <span className="font-mono text-[9px] text-faint">{f.id}</span>
                        <span className="h-[3px] w-[3px] rounded-full bg-line-strong" />
                        <span className="truncate font-mono text-[9px] text-dim">
                          {f.target}
                          {f.path}
                        </span>
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 align-top font-mono text-[10px] text-muted">
                      {f.target}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 align-top text-[10px] text-dim">
                      {f.category}
                    </td>
                    <td className="px-4 py-3 align-top">
                      <StatusBadge status={f.status} />
                    </td>
                    <td className="px-4 py-3 text-right align-top">
                      <Link
                        to={`/app/findings/${f.id}?run=${stamp}`}
                        className="inline-flex items-center gap-1 font-mono text-[9.5px] text-[#7fa9f0] opacity-70 transition-opacity group-hover:opacity-100 hover:underline"
                      >
                        investigate
                        <ArrowUpRight size={10} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center gap-2 px-6 py-16">
            <div className="flex h-[38px] w-[38px] items-center justify-center rounded-[6px] border border-line bg-app-800">
              <FileSearch size={16} className="text-dim" />
            </div>
            <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-soft">
              No findings here
            </h3>
            <p className="max-w-[360px] text-center text-[11px] leading-relaxed text-dim">
              {list.length === 0
                ? "This run recorded no findings — or no scan has completed yet. Start a run to populate this list."
                : "No recorded issues match the current filter combination."}
            </p>
            <button
              className="btn-secondary mt-1"
              onClick={() => {
                setSeverityFilter("all");
                setQuery("");
              }}
            >
              Reset filters
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
