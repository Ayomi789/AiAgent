import type { ReactNode } from "react";
import { SEVERITY_META, type Severity, type FindingStatus } from "../lib/types";

export function SeverityBadge({
  severity,
  size = "sm",
}: {
  severity: Severity;
  size?: "sm" | "md";
}) {
  const meta = SEVERITY_META[severity];
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-[4px] border font-semibold uppercase tracking-[0.07em]"
      style={{
        backgroundColor: meta.bg,
        borderColor: meta.border,
        color: meta.text,
        fontSize: size === "sm" ? 9.5 : 11,
        padding: size === "sm" ? "2px 6px" : "3px 8px",
      }}
    >
      <span
        className="inline-block rounded-[2px]"
        style={{ width: 5, height: 5, backgroundColor: meta.color }}
      />
      {meta.label}
    </span>
  );
}

export function SeverityDot({ severity }: { severity: Severity }) {
  const meta = SEVERITY_META[severity];
  return (
    <span
      className="inline-block rounded-[2px]"
      style={{ width: 6, height: 6, backgroundColor: meta.color }}
      aria-hidden
    />
  );
}

const STATUS_STYLES: Record<string, { fg: string; bg: string; bd: string; label: string }> = {
  confirmed: { fg: "#f28286", bg: "rgba(229,72,77,0.11)", bd: "rgba(229,72,77,0.3)", label: "Confirmed" },
  verified: { fg: "#66c07a", bg: "rgba(70,167,88,0.11)", bd: "rgba(70,167,88,0.3)", label: "Verified" },
  triaged: { fg: "#98a1ab", bg: "rgba(125,135,148,0.1)", bd: "rgba(125,135,148,0.26)", label: "Triaged" },
  "in-review": { fg: "#7fa9f0", bg: "rgba(76,141,255,0.1)", bd: "rgba(76,141,255,0.28)", label: "In review" },
  running: { fg: "#7fa9f0", bg: "rgba(76,141,255,0.1)", bd: "rgba(76,141,255,0.28)", label: "Running" },
  completed: { fg: "#66c07a", bg: "rgba(70,167,88,0.11)", bd: "rgba(70,167,88,0.3)", label: "Completed" },
  stopped: { fg: "#98a1ab", bg: "rgba(125,135,148,0.1)", bd: "rgba(125,135,148,0.26)", label: "Stopped" },
  failed: { fg: "#f28286", bg: "rgba(229,72,77,0.11)", bd: "rgba(229,72,77,0.3)", label: "Failed" },
  queued: { fg: "#f0b95c", bg: "rgba(245,166,35,0.1)", bd: "rgba(245,166,35,0.28)", label: "Queued" },
  protected: { fg: "#66c07a", bg: "rgba(70,167,88,0.11)", bd: "rgba(70,167,88,0.3)", label: "Protected" },
};

export function StatusBadge({ status, pulse = false }: { status: string; pulse?: boolean }) {
  const style = STATUS_STYLES[status] ?? STATUS_STYLES.triaged;
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-[4px] border font-medium"
      style={{
        backgroundColor: style.bg,
        borderColor: style.bd,
        color: style.fg,
        fontSize: 10.5,
        padding: "2px 7px",
      }}
    >
      {pulse ? (
        <span
          className="inline-block rounded-full animate-pulse-dot"
          style={{ width: 5, height: 5, backgroundColor: style.fg }}
        />
      ) : (
        <span
          className="inline-block rounded-[2px]"
          style={{ width: 5, height: 5, backgroundColor: style.fg }}
        />
      )}
      {style.label}
    </span>
  );
}

export function FindingStatusBadge({ status }: { status: FindingStatus }) {
  return <StatusBadge status={status} />;
}

export function PanelHeader({
  title,
  subtitle,
  action,
  icon,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-line px-4 py-2.5">
      <div className="flex items-center gap-2.5 min-w-0">
        {icon ? <span className="text-dim shrink-0">{icon}</span> : null}
        <div className="min-w-0">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.09em] text-ink-soft truncate">
            {title}
          </h2>
          {subtitle ? <p className="text-[11px] text-dim truncate mt-0.5">{subtitle}</p> : null}
        </div>
      </div>
      {action ? <div className="flex items-center gap-2 shrink-0">{action}</div> : null}
    </div>
  );
}

export function Toggle({
  checked,
  onChange,
  label,
  description,
  disabled = false,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
  description?: string;
  disabled?: boolean;
}) {
  return (
    <div
      className={`flex items-start justify-between gap-4 py-2.5 ${
        disabled ? "opacity-50" : ""
      }`}
    >
      <div className="min-w-0">
        <div className="text-[12.5px] text-ink font-medium">{label}</div>
        {description ? (
          <div className="text-[11px] text-dim mt-0.5 leading-relaxed">{description}</div>
        ) : null}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className="relative shrink-0 rounded-full border transition-colors duration-150"
        style={{
          width: 34,
          height: 19,
          backgroundColor: checked ? "#2f6bd8" : "#22262c",
          borderColor: checked ? "#3f7ce8" : "#2c3138",
        }}
      >
        <span
          className="absolute rounded-full transition-transform duration-150"
          style={{
            width: 13,
            height: 13,
            top: 2,
            left: 2,
            backgroundColor: checked ? "#ffffff" : "#79828c",
            transform: checked ? "translateX(15px)" : "translateX(0)",
          }}
        />
      </button>
    </div>
  );
}

export function ProgressBar({
  value,
  max = 100,
  color = "#4c8dff",
  height = 4,
}: {
  value: number;
  max?: number;
  color?: string;
  height?: number;
}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div
      className="w-full overflow-hidden rounded-full bg-app-700"
      style={{ height }}
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
    >
      <div
        className="h-full rounded-full transition-[width] duration-300"
        style={{ width: `${pct}%`, backgroundColor: color }}
      />
    </div>
  );
}

export function KeyValue({
  label,
  value,
  mono = false,
  accent,
}: {
  label: string;
  value: ReactNode;
  mono?: boolean;
  accent?: string;
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[9.5px] font-semibold uppercase tracking-[0.1em] text-faint">
        {label}
      </span>
      <span
        className={`text-[12px] ${mono ? "font-mono" : ""} text-ink-soft`}
        style={accent ? { color: accent } : undefined}
      >
        {value}
      </span>
    </div>
  );
}

export function Divider() {
  return <div className="h-px w-full bg-line" />;
}
