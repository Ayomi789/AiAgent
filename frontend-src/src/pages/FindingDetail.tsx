import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, Target, ExternalLink } from "lucide-react";
import { EvidenceViewer } from "../components/EvidenceViewer";
import { SeverityBadge, StatusBadge, PanelHeader } from "../components/ui";
import { useLiveState } from "../lib/useLive";
import { fetchReportFindings, toFinding } from "../lib/api";
import type { Finding } from "../lib/types";

export function FindingDetail() {
  const { id } = useParams();
  const [search] = useSearchParams();
  const run = search.get("run") || "live";
  const live = useLiveState();
  const [finding, setFinding] = useState<Finding | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoaded(false);
    const fromLive = (live.findings || []).find(
      (f) => f.id.toLowerCase() === (id || "").toLowerCase()
    );
    if (run === "live" || fromLive) {
      if (fromLive) setFinding(toFinding(fromLive, run));
      else setFinding(null);
      setLoaded(true);
      return;
    }
    fetchReportFindings(run)
      .then((list) => {
        if (!alive) return;
        const hit = list.find((f) => f.id.toLowerCase() === (id || "").toLowerCase());
        setFinding(hit ? toFinding(hit, run) : null);
        setLoaded(true);
      })
      .catch(() => {
        if (alive) {
          setFinding(null);
          setLoaded(true);
        }
      });
    return () => {
      alive = false;
    };
  }, [id, run, live]);

  if (!loaded) {
    return (
      <div className="px-4 py-5 sm:px-6">
        <p className="font-mono text-[11px] text-faint">Loading finding…</p>
      </div>
    );
  }

  if (!finding) {
    return (
      <div className="px-4 py-5 sm:px-6">
        <Link to="/app/findings" className="flex items-center gap-1.5 text-[10px] text-dim hover:text-ink-soft">
          <ArrowLeft size={11} />
          Findings
        </Link>
        <div className="mt-6 max-w-[520px] rounded-[6px] border border-line bg-app-850 p-6">
          <h1 className="text-[15px] font-semibold text-ink">Finding not found</h1>
          <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted">
            No finding with id <span className="font-mono">{id}</span> in run{" "}
            <span className="font-mono">{run}</span>. It may belong to an older run — pick the
            run in the Findings list first.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="px-4 py-5 sm:px-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-[10px]">
        <Link to="/app/findings" className="flex items-center gap-1.5 text-dim hover:text-ink-soft">
          <ArrowLeft size={11} />
          Findings
        </Link>
        <span className="text-faint">/</span>
        <span className="font-mono text-faint">{finding.id}</span>
        <span className="text-faint">/</span>
        <span className="text-muted">{finding.category}</span>
      </div>

      {/* Header */}
      <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 max-w-[760px]">
          <div className="flex flex-wrap items-center gap-2">
            <SeverityBadge severity={finding.severity} size="md" />
            <StatusBadge status={finding.status} />
          </div>

          <h1 className="mt-2.5 text-[21px] font-semibold leading-[1.25] tracking-[-0.018em] text-ink">
            {finding.title}
          </h1>

          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5">
            <div className="flex items-center gap-1.5">
              <Target size={11} className="text-faint" />
              <span className="font-mono text-[11px] text-[#7fa9f0]">
                {finding.target}
                <span className="text-ink-soft">{finding.path}</span>
              </span>
            </div>
            <span className="font-mono text-[9.5px] text-faint">run {finding.runId}</span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {finding.target && finding.path ? (
            <a
              className="btn-secondary"
              href={`${finding.target}${finding.path}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              <ExternalLink size={11} />
              Open target
            </a>
          ) : null}
        </div>
      </div>

      {/* Summary */}
      <div className="mt-5 overflow-hidden rounded-[6px] border border-line bg-app-850">
        <PanelHeader title="Summary" />
        <p className="p-4 text-[12.5px] leading-relaxed text-ink-soft">
          {finding.summary || "No description recorded for this finding."}
        </p>
      </div>

      {/* Verification */}
      <div className="mt-4 overflow-hidden rounded-[6px] border border-line bg-app-850">
        <PanelHeader title="Verification" subtitle={finding.verification} />
        <div className="grid grid-cols-1 gap-px bg-line sm:grid-cols-2">
          <div className="bg-app-850 p-4">
            <div className="text-[9px] font-semibold uppercase tracking-[0.13em] text-faint">
              Impact
            </div>
            <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted">{finding.impact}</p>
          </div>
          <div className="bg-app-850 p-4">
            <div className="text-[9px] font-semibold uppercase tracking-[0.13em] text-faint">
              Recommendation
            </div>
            <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted">
              {finding.recommendation}
            </p>
          </div>
        </div>
      </div>

      {/* Evidence */}
      <div className="mt-4 overflow-hidden rounded-[6px] border border-line bg-app-850">
        <PanelHeader
          title="Evidence"
          subtitle="Captured request, response, DOM and console output at detection time"
        />
        <div className="p-4">
          {finding.evidence.request ||
          finding.evidence.response ||
          finding.evidence.dom ||
          finding.evidence.console ? (
            <EvidenceViewer evidence={finding.evidence} findingId={finding.id} />
          ) : (
            <p className="text-[11.5px] leading-relaxed text-dim">
              Full evidence artifacts ship with the downloadable report bundle (HTML / JSON /
              TestIO). This finding carries its summary inline.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
