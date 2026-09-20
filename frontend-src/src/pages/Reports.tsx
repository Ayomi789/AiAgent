import { useEffect, useState } from "react";
import { FileJson, FileText, FileDown, Download, Clock } from "lucide-react";
import { PanelHeader, KeyValue } from "../components/ui";
import { SeverityStack } from "../components/Charts";
import { useHistory } from "../lib/useLive";
import { downloadUrl, fetchReportFindings, countBySeverity } from "../lib/api";
import { SEVERITY_ORDER, SEVERITY_META } from "../lib/types";

export function Reports() {
  const { runs } = useHistory();
  const [stamp, setStamp] = useState<string>("");
  const [counts, setCounts] = useState({ critical: 0, high: 0, medium: 0, low: 0, info: 0 });
  const [total, setTotal] = useState(0);

  const selected = runs.find((r) => r.stamp === stamp) ?? runs[0] ?? null;
  const activeStamp = selected?.stamp || "";

  useEffect(() => {
    if (!activeStamp) return;
    let alive = true;
    fetchReportFindings(activeStamp)
      .then((f) => {
        if (!alive) return;
        setCounts(countBySeverity(f));
        setTotal(f.length);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [activeStamp]);

  const formats = [
    {
      id: "html",
      name: "HTML",
      icon: <FileText size={13} />,
      description: "Formatted human-readable report for stakeholders and records.",
    },
    {
      id: "json",
      name: "JSON",
      icon: <FileJson size={13} />,
      description: "Machine-readable output for pipelines and ticketing automation.",
    },
    {
      id: "md",
      name: "Markdown",
      icon: <FileText size={13} />,
      description: "Structured text for repositories and engineering documentation.",
    },
    {
      id: "csv",
      name: "CSV",
      icon: <FileDown size={13} />,
      description: "Tabular findings for spreadsheets and triage.",
    },
  ];

  return (
    <div className="px-4 py-5 sm:px-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-[18px] font-semibold tracking-[-0.012em] text-ink">Reports</h1>
          <p className="mt-1 max-w-[640px] text-[11.5px] leading-relaxed text-muted">
            Assessment output generated directly from verified findings — every figure traces back
            to a recorded observation.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Clock size={12} className="text-faint" />
          <select
            className="field w-auto py-[6px] text-[11px]"
            value={activeStamp}
            onChange={(e) => setStamp(e.target.value)}
            aria-label="Select report"
          >
            {runs.map((r) => (
              <option key={r.stamp} value={r.stamp}>
                {(r.started_at || "").slice(0, 16).replace("T", " ")} · {r.target}
              </option>
            ))}
          </select>
        </div>
      </div>

      {selected ? (
        <>
          {/* Report header card */}
          <div className="mt-4 overflow-hidden rounded-[6px] border border-line bg-app-850">
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-line px-4 py-3">
              <div>
                <div className="text-[8px] font-semibold uppercase tracking-[0.13em] text-faint">
                  Assessment
                </div>
                <div className="mt-0.5 text-[12px] font-medium text-ink">{selected.target}</div>
              </div>
              <div className="h-8 w-px bg-line" />
              <KeyValue label="Started" value={(selected.started_at || "").slice(0, 16).replace("T", " ")} mono />
              <KeyValue label="Status" value={selected.status || "—"} mono />
              <KeyValue label="Findings" value={String(total)} mono />
              {selected.owner_email ? (
                <KeyValue label="Owner" value={selected.owner_email} mono />
              ) : null}
            </div>

            {/* Severity distribution */}
            <div className="bg-app-850 p-4">
              <div className="text-[8.5px] font-semibold uppercase tracking-[0.13em] text-faint">
                Severity distribution
              </div>
              <div className="mt-3">
                <SeverityStack
                  height={8}
                  segments={SEVERITY_ORDER.map((s) => ({
                    label: s,
                    value: counts[s],
                    color: SEVERITY_META[s].color,
                  }))}
                />
              </div>
              <div className="mt-3 grid grid-cols-5 gap-2">
                {SEVERITY_ORDER.map((s) => (
                  <div key={s}>
                    <div className="flex items-center gap-1.5">
                      <span
                        className="h-[5px] w-[5px] rounded-[1px]"
                        style={{ backgroundColor: SEVERITY_META[s].color }}
                      />
                      <span className="text-[8px] font-semibold uppercase tracking-[0.11em] text-faint">
                        {SEVERITY_META[s].label}
                      </span>
                    </div>
                    <div
                      className="mt-1 font-mono text-[15px]"
                      style={{ color: SEVERITY_META[s].text }}
                    >
                      {counts[s]}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Downloads */}
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {formats.map((f) => (
              <a
                key={f.id}
                href={downloadUrl(activeStamp, f.id)}
                className="block rounded-[6px] border border-line bg-app-850 p-4 transition-colors hover:border-line-strong hover:bg-app-800"
              >
                <div className="flex items-center gap-2 text-ink-soft">
                  {f.icon}
                  <span className="text-[12px] font-semibold">{f.name}</span>
                  <Download size={11} className="ml-auto text-faint" />
                </div>
                <p className="mt-1.5 text-[10.5px] leading-relaxed text-dim">{f.description}</p>
              </a>
            ))}
          </div>

          {selected.has_testio ? (
            <a
              href={downloadUrl(activeStamp, "testio")}
              className="btn-secondary mt-4"
            >
              <Download size={12} />
              Download TestIO bundle (.zip)
            </a>
          ) : null}
        </>
      ) : (
        <div className="mt-4 rounded-[6px] border border-line bg-app-850 px-6 py-12 text-center">
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-soft">
            No reports yet
          </p>
          <p className="mx-auto mt-1.5 max-w-[380px] text-[11px] leading-relaxed text-dim">
            Completed scans seal a report here with HTML, JSON, Markdown and CSV artifacts.
          </p>
        </div>
      )}
    </div>
  );
}
