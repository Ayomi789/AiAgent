export type Severity = "critical" | "high" | "medium" | "low" | "info";

export type FindingStatus = "confirmed" | "verified" | "triaged" | "in-review";

export interface NetworkEntry {
  method: string;
  path: string;
  status: number;
  type: string;
  size: string;
  time: string;
  state: "ok" | "redirect" | "blocked" | "error";
}

export interface Evidence {
  request: string;
  response: string;
  dom: string;
  console: string;
  network: NetworkEntry[];
}

export interface Finding {
  id: string;
  severity: Severity;
  title: string;
  category: string;
  target: string;
  path: string;
  parameter?: string;
  status: FindingStatus;
  confidence: "high" | "medium" | "low";
  cvss: string;
  cwe: string;
  owasp: string;
  detected: string;
  runId: string;
  evidenceCount: number;
  summary: string;
  verification: string;
  reproduction: string[];
  impact: string;
  recommendation: string;
  evidence: Evidence;
}

export const SEVERITY_META: Record<
  Severity,
  { label: string; color: string; bg: string; border: string; text: string }
> = {
  critical: {
    label: "Critical",
    color: "#e5484d",
    bg: "rgba(229,72,77,0.12)",
    border: "rgba(229,72,77,0.34)",
    text: "#f28286",
  },
  high: {
    label: "High",
    color: "#f76b15",
    bg: "rgba(247,107,21,0.12)",
    border: "rgba(247,107,21,0.34)",
    text: "#f79457",
  },
  medium: {
    label: "Medium",
    color: "#f5a623",
    bg: "rgba(245,166,35,0.12)",
    border: "rgba(245,166,35,0.32)",
    text: "#f0b95c",
  },
  low: {
    label: "Low",
    color: "#6c8fb3",
    bg: "rgba(108,143,179,0.12)",
    border: "rgba(108,143,179,0.32)",
    text: "#8fb0cf",
  },
  info: {
    label: "Info",
    color: "#7d8794",
    bg: "rgba(125,135,148,0.1)",
    border: "rgba(125,135,148,0.28)",
    text: "#98a1ab",
  },
};

export const SEVERITY_ORDER: Severity[] = ["critical", "high", "medium", "low", "info"];
