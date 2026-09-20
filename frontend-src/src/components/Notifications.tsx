import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Bell } from "lucide-react";
import { useDiff, useLiveState, useScanStatus } from "../lib/useLive";
import { normalizeSeverity } from "../lib/api";
import { SEVERITY_META } from "../lib/types";

interface Notice {
  id: string;
  color: string;
  title: string;
  detail: string;
  to: string;
}

const SEEN_KEY = "sentinel-seen-notifs";

function loadSeen(): Set<string> {
  try {
    const raw = localStorage.getItem(SEEN_KEY);
    return new Set(raw ? (JSON.parse(raw) as string[]) : []);
  } catch {
    return new Set();
  }
}

export function NotificationBell() {
  const live = useLiveState();
  const scan = useScanStatus();
  const diff = useDiff();
  const [open, setOpen] = useState(false);
  const [seen, setSeen] = useState<Set<string>>(loadSeen);
  const boxRef = useRef<HTMLDivElement>(null);

  const notices: Notice[] = useMemo(() => {
    const list: Notice[] = [];
    // Critical/high findings in the current run — worst first.
    (live.findings || [])
      .filter((f) => {
        const s = normalizeSeverity(f.severity);
        return s === "critical" || s === "high";
      })
      .slice(0, 8)
      .forEach((f) => {
        const sev = normalizeSeverity(f.severity);
        list.push({
          id: `finding-${f.id}`,
          color: SEVERITY_META[sev].color,
          title: f.title,
          detail: `${sev} · current run`,
          to: `/app/findings/${f.id}?run=live`,
        });
      });
    // New regressions vs the previous sealed report.
    const fresh = (diff?.new || []).filter((f) => {
      const s = normalizeSeverity(f.severity);
      return s === "critical" || s === "high";
    });
    if (fresh.length > 0) {
      list.unshift({
        id: `regressions-${diff?.latest_run || "latest"}`,
        color: "#e5484d",
        title: `${fresh.length} new ${fresh.length === 1 ? "regression" : "regressions"} vs previous run`,
        detail: "baseline diff",
        to: "/app",
      });
    }
    // Terminal scan state.
    if (!scan.running && live.status === "completed") {
      list.unshift({
        id: `done-${live.report_path || live.target || "run"}`,
        color: "#46a758",
        title: `Scan finished — ${(live.findings || []).length} findings`,
        detail: live.target || "",
        to: "/app/reports",
      });
    } else if (!scan.running && live.status === "failed") {
      list.unshift({
        id: `failed-${live.target || "run"}`,
        color: "#e5484d",
        title: "Scan failed — check the agent log",
        detail: live.target || "",
        to: "/app",
      });
    }
    return list;
  }, [live, scan, diff]);

  const unread = notices.filter((n) => !seen.has(n.id));

  useEffect(() => {
    if (!open) return;
    setSeen((prev) => {
      const next = new Set(prev);
      notices.forEach((n) => next.add(n.id));
      try {
        localStorage.setItem(SEEN_KEY, JSON.stringify([...next].slice(-200)));
      } catch {
        /* private mode — unread dot simply persists */
      }
      return next;
    });
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    const onClick = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open ]);

  return (
    <div className="relative" ref={boxRef}>
      <button
        className="btn-icon relative"
        aria-label={unread.length ? `${unread.length} unread notifications` : "Notifications"}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <Bell size={14} />
        {unread.length > 0 ? (
          <span className="absolute right-[5px] top-[5px] h-[5px] w-[5px] rounded-full bg-[#e5484d]" />
        ) : null}
      </button>

      {open ? (
        <div className="absolute right-0 top-[34px] z-50 w-[320px] overflow-hidden rounded-[6px] border border-line-strong bg-app-800 shadow-[0_8px_24px_rgba(0,0,0,0.45)]">
          <div className="border-b border-line px-3.5 py-2.5 text-[9px] font-semibold uppercase tracking-[0.13em] text-faint">
            Notifications
            <span className="ml-2 font-mono normal-case tracking-normal">
              {unread.length ? `${unread.length} unread` : "all caught up"}
            </span>
          </div>
          <div className="max-h-[320px] overflow-y-auto">
            {notices.length ? (
              notices.map((n) => (
                <Link
                  key={n.id}
                  to={n.to}
                  onClick={() => setOpen(false)}
                  className="flex items-start gap-2.5 border-b border-line-soft px-3.5 py-2.5 transition-colors last:border-0 hover:bg-app-750"
                >
                  <span
                    className="mt-[4px] h-[6px] w-[6px] shrink-0 rounded-[1px]"
                    style={{ backgroundColor: n.color }}
                  />
                  <span className="min-w-0">
                    <span className="block truncate text-[11px] font-medium text-ink-soft">
                      {n.title}
                    </span>
                    <span className="mt-[2px] block truncate font-mono text-[8.5px] text-faint">
                      {n.detail}
                    </span>
                  </span>
                  {!seen.has(n.id) ? (
                    <span className="ml-auto mt-[5px] h-[5px] w-[5px] shrink-0 rounded-full bg-[#4c8dff]" />
                  ) : null}
                </Link>
              ))
            ) : (
              <div className="px-3.5 py-8 text-center">
                <p className="text-[11px] font-medium text-ink-soft">Nothing needs you</p>
                <p className="mx-auto mt-1 max-w-[220px] text-[10px] leading-relaxed text-dim">
                  Critical and high findings from the current run will land here the moment
                  they verify.
                </p>
              </div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
