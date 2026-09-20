import { useState } from "react";
import { Link } from "react-router-dom";
import { FolderSearch, ShieldCheck } from "lucide-react";
import { PanelHeader, SeverityBadge, StatusBadge } from "../components/ui";
import { EvidenceViewer } from "../components/EvidenceViewer";
import { useLiveState } from "../lib/useLive";
import { toFinding } from "../lib/api";

export function Evidence() {
  const live = useLiveState();
  const list = (live.findings || []).map((f) => toFinding(f, "live"));
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = list.find((f) => f.id === selectedId) ?? list[0] ?? null;

  return (
    <div className="px-4 py-5 sm:px-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-[18px] font-semibold tracking-[-0.012em] text-ink">Evidence</h1>
          <p className="mt-1 max-w-[640px] text-[11.5px] leading-relaxed text-muted">
            Capture of everything the agent observed for the current run. Full per-run evidence
            bundles ship with the downloadable report (HTML / JSON / TestIO).
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1.5 rounded-[4px] border border-[rgba(70,167,88,0.28)] bg-[rgba(70,167,88,0.08)] px-2.5 py-[6px]">
            <ShieldCheck size={11} className="text-[#66c07a]" />
            <span className="font-mono text-[8.5px] uppercase tracking-[0.13em] text-[#66c07a]">
              {live.status === "running" ? "run active" : (live.status || "idle")}
            </span>
          </div>
        </div>
      </div>

      {selected ? (
        <div className="mt-5 grid grid-cols-1 gap-4 xl:grid-cols-12">
          <div className="xl:col-span-4">
            <div className="overflow-hidden rounded-[6px] border border-line bg-app-850">
              <PanelHeader
                title="Evidence bundles"
                subtitle="Grouped by finding · current run"
                icon={<FolderSearch size={13} />}
                action={
                  <span className="font-mono text-[8.5px] text-faint">{list.length} bundles</span>
                }
              />
              <div className="max-h-[620px] overflow-y-auto">
                {list.map((f) => (
                  <button
                    key={f.id}
                    onClick={() => setSelectedId(f.id)}
                    className="block w-full border-b border-line-soft px-4 py-3 text-left transition-colors last:border-0"
                    style={{
                      backgroundColor: selected.id === f.id ? "#1a1e23" : "transparent",
                      boxShadow: selected.id === f.id ? "inset 2px 0 0 #4c8dff" : "none",
                    }}
                  >
                    <div className="flex items-center gap-2">
                      <SeverityBadge severity={f.severity} />
                      <StatusBadge status={f.status} />
                      <span className="ml-auto font-mono text-[8px] text-faint">{f.id}</span>
                    </div>
                    <div className="mt-1.5 truncate text-[11px] text-ink-soft">{f.title}</div>
                    <div className="mt-1 flex items-center gap-2 font-mono text-[8.5px] text-faint">
                      <span className="truncate">
                        {f.target}
                        {f.path}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="xl:col-span-8">
            <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1.5">
              <h2 className="text-[13px] font-semibold text-ink">{selected.title}</h2>
              <Link
                to={`/app/findings/${selected.id}?run=live`}
                className="font-mono text-[9.5px] text-[#7fa9f0] hover:underline"
              >
                open finding →
              </Link>
            </div>

            <EvidenceViewer evidence={selected.evidence} findingId={selected.id} />
          </div>
        </div>
      ) : (
        <div className="mt-5 rounded-[6px] border border-line bg-app-850 px-6 py-12 text-center">
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-soft">
            No evidence yet
          </p>
          <p className="mx-auto mt-1.5 max-w-[380px] text-[11px] leading-relaxed text-dim">
            Evidence appears here while a scan runs. Past runs keep theirs in the downloadable
            report bundle.
          </p>
        </div>
      )}
    </div>
  );
}
