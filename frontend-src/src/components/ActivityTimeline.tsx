import { useEffect, useRef, useState } from "react";
import { Activity, Pause, Play, Filter } from "lucide-react";
import { timeline, liveTimelineFeed, type TimelineEvent, type Phase } from "../lib/data";
import { PanelHeader } from "./ui";

const PHASE_COLOR: Record<Phase, string> = {
  OBSERVE: "#7d8794",
  THINK: "#8fa6c4",
  ACT: "#4c8dff",
  VERIFY: "#f5a623",
  ASSERT: "#e5484d",
  CAPTURE: "#46a758",
  SCOPE: "#66c07a",
};

const STATUS_COLOR: Record<TimelineEvent["status"], string> = {
  ok: "#6b747e",
  info: "#4c8dff",
  warn: "#f5a623",
  fail: "#e5484d",
  pass: "#46a758",
};

export function ActivityTimeline({
  live = true,
  maxHeight = 560,
  showHeader = true,
}: {
  live?: boolean;
  maxHeight?: number;
  showHeader?: boolean;
}) {
  const [events, setEvents] = useState<TimelineEvent[]>(timeline);
  const [isLive, setIsLive] = useState(live);
  const [filter, setFilter] = useState<"all" | "findings">("all");
  const feedIndex = useRef(0);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isLive) return;
    const timer = window.setInterval(() => {
      const next = liveTimelineFeed[feedIndex.current % liveTimelineFeed.length];
      feedIndex.current += 1;
      setEvents((prev) => {
        const last = prev[prev.length - 1];
        const shifted: TimelineEvent = {
          ...next,
          time: last ? incrementTime(last.time, 2 + (feedIndex.current % 3)) : next.time,
        };
        return [...prev.slice(-60), shifted];
      });
    }, 3200);
    return () => window.clearInterval(timer);
  }, [isLive]);

  const visible = filter === "all" ? events : events.filter((e) => e.status === "warn" || e.status === "fail");

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-[6px] border border-line bg-app-850">
      {showHeader ? (
        <PanelHeader
          title="Agent activity"
          subtitle="Observable decision log · chain-of-thought is never exposed"
          icon={<Activity size={13} />}
          action={
            <>
              <button
                className="btn-icon"
                title={filter === "all" ? "Show findings only" : "Show all events"}
                onClick={() => setFilter((f) => (f === "all" ? "findings" : "all"))}
              >
                <Filter size={12} />
              </button>
              <button
                className="btn-icon"
                title={isLive ? "Pause stream" : "Resume stream"}
                onClick={() => setIsLive((v) => !v)}
              >
                {isLive ? <Pause size={12} /> : <Play size={12} />}
              </button>
              <div className="flex items-center gap-1.5 rounded-[4px] border border-line px-2 py-[3px]">
                <span
                  className={`h-[5px] w-[5px] rounded-full ${isLive ? "animate-pulse-dot" : ""}`}
                  style={{ backgroundColor: isLive ? "#4c8dff" : "#6b747e" }}
                />
                <span className="font-mono text-[8.5px] uppercase tracking-[0.13em] text-dim">
                  {isLive ? "Streaming" : "Paused"}
                </span>
              </div>
            </>
          }
        />
      ) : null}

      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto px-1.5 py-2"
        style={{ maxHeight }}
        aria-live="polite"
      >
        {visible.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 py-10">
            <div className="section-label">No matching events</div>
            <p className="max-w-[260px] text-center text-[11px] text-dim">
              The current filter excludes all recorded activity for this session.
            </p>
          </div>
        ) : (
          visible.map((event, i) => (
            <div
              key={`${event.time}-${i}`}
              className={`group relative flex gap-3 rounded-[4px] px-2.5 py-[7px] transition-colors hover:bg-app-800 ${
                i === visible.length - 1 && isLive ? "animate-fade-up" : ""
              }`}
            >
              {/* Rail */}
              <div className="relative flex w-[62px] shrink-0 items-start justify-end pt-[3px]">
                <span className="font-mono text-[9.5px] text-faint">{event.time}</span>
              </div>

              <div className="relative flex w-[14px] shrink-0 justify-center">
                <div className="absolute inset-y-0 w-px bg-line" style={{ left: "50%" }} />
                <div
                  className="relative z-10 mt-[6px] h-[7px] w-[7px] rounded-[2px] border"
                  style={{
                    backgroundColor: STATUS_COLOR[event.status],
                    borderColor: "rgba(11,13,16,0.9)",
                  }}
                />
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex items-start gap-2">
                  <span
                    className="mt-[1px] shrink-0 rounded-[3px] border px-1.5 py-[1px] font-mono text-[8px] font-semibold tracking-[0.11em]"
                    style={{
                      color: PHASE_COLOR[event.phase],
                      borderColor: `${PHASE_COLOR[event.phase]}38`,
                      backgroundColor: `${PHASE_COLOR[event.phase]}12`,
                    }}
                  >
                    {event.phase}
                  </span>
                  <div className="min-w-0">
                    <div className="text-[11.5px] leading-[1.5] text-ink-soft">
                      {event.description}
                    </div>
                    {event.detail ? (
                      <div className="mt-[2px] truncate font-mono text-[9.5px] text-faint">
                        {event.detail}
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      <div className="flex items-center gap-3 border-t border-line px-3 py-1.5 font-mono text-[9px] text-faint">
        <span>events: {events.length}</span>
        <span>buffer: 60</span>
        <span>retention: full run</span>
        <span className="ml-auto text-[#66c07a]">audit log: enabled</span>
      </div>
    </div>
  );
}

function incrementTime(time: string, seconds: number) {
  const [h, m, s] = time.split(":").map(Number);
  const total = h * 3600 + m * 60 + s + seconds;
  const hh = Math.floor(total / 3600) % 24;
  const mm = Math.floor((total % 3600) / 60);
  const ss = total % 60;
  return `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
}
