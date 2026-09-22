import type { Finding, Severity } from "./types";

/**
 * Same-origin client for the Sentinel Flask backend. The React bundle is
 * served by Flask itself (see /console), so cookies authenticate every call
 * and no CORS configuration is needed.
 */

export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(status: number, message: string, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

// Last time any API call failed at the network level (server asleep,
// overloaded, or gone). The shell reads this to show "reconnecting"
// instead of silently rendering empty states that look like data loss.
let lastNetFailure = 0;
export function noteNetFailure() {
  lastNetFailure = Date.now();
}
export function serverSilent(now: number = Date.now()): boolean {
  return now - lastNetFailure < 8000;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    // Network-level: asleep, overloaded, or gone. Callers keep last state;
    // the shell surfaces this instead of fake-empty screens.
    noteNetFailure();
    throw new ApiError(0, "Server unreachable.");
  }
  if (res.status === 401) {
    // Session expired (or server slept and lost it) — console sign-in handles it.
    window.location.href = "/console/login";
    throw new ApiError(401, "Session expired — signing in again.");
  }
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  if (!res.ok) {
    const err = (body ?? {}) as { error?: string; code?: string };
    throw new ApiError(res.status, err.error || `Request failed (${res.status})`, err.code);
  }
  return body as T;
}

export const get = <T>(path: string) => req<T>(path);
export const post = <T>(path: string, payload: unknown) =>
  req<T>(path, { method: "POST", body: JSON.stringify(payload) });

/* ------------------------------------------------------------------ */
/* Backend payload shapes                                               */
/* ------------------------------------------------------------------ */

export interface ApiFinding {
  id: string;
  severity: string;
  category?: string;
  title: string;
  url: string;
  description?: string;
  content_type?: string | null;
}

export interface LiveState {
  status: string;
  stage?: string;
  target?: string;
  started_at?: string;
  current_url?: string;
  step?: number;
  max_steps?: number;
  elapsed_seconds?: number;
  findings: ApiFinding[];
  recent_actions?: { action?: string; detail?: string; time?: string }[];
  report_path?: string | null;
}

export interface ScanStatus {
  running: boolean;
  config?: string | null;
  skip_llm?: boolean;
  started?: string | null;
  returncode?: number | null;
  log_tail: string[];
}

export interface SeverityCounts {
  critical: number;
  high: number;
  medium: number;
  low: number;
  info: number;
}

export interface HistoryRun {
  stamp: string;
  target: string;
  started_at?: string;
  finished_at?: string;
  status?: string;
  owner_email?: string;
  summary?: SeverityCounts;
  finding_count: number;
  has_testio?: boolean;
}

export interface DiffData {
  latest_run?: string | null;
  previous_run?: string | null;
  new: ApiFinding[];
  fixed: ApiFinding[];
  unchanged: ApiFinding[];
  counts: { new: number; fixed: number; unchanged: number };
}

export interface ConfigEntry {
  name: string;
  target?: string | null;
  file: string;
}

export interface MeData {
  email: string | null;
  admin: boolean;
}

export interface Capabilities {
  ram_mb: number | null;
  ram_ok: boolean;
  llm_ok: boolean | null;
  llm_message: string;
  full_ok: boolean;
  reasons: string[];
}

export interface AdminUser {
  id: number;
  email: string;
  role: string;
  created_at?: string;
  suspended: boolean;
  suspend_reason?: string | null;
  suspended_at?: string | null;
}

export interface AdminInvite {
  code: string;
  created_at?: string;
  used: boolean;
  used_at?: string | null;
}

export interface AdminOverview {
  users: AdminUser[];
  invites: AdminInvite[];
  scan: {
    running: boolean;
    config?: string | null;
    started?: string | null;
    owner_email?: string | null;
    returncode?: number | null;
  };
}

export interface ReportFile {
  path: string | null;
  json_path: string | null;
  markdown: string;
}

/* ------------------------------------------------------------------ */
/* Adapter: backend finding -> UI finding                               */
/*                                                                     */
/* The backend records what it deterministically verified (title,       */
/* severity, category, URL, description). Fields the UI displays that   */
/* the backend does not produce (CVSS, CWE, confidence …) are filled    */
/* with honest placeholders rather than invented values.                */
/* ------------------------------------------------------------------ */

function splitTarget(url: string): { target: string; path: string } {
  try {
    const u = new URL(url);
    return { target: u.origin, path: u.pathname + u.search || "/" };
  } catch {
    const i = url.indexOf("/", url.indexOf("://") + 3);
    if (i === -1) return { target: url, path: "/" };
    return { target: url.slice(0, i), path: url.slice(i) || "/" };
  }
}

const SEVS: Severity[] = ["critical", "high", "medium", "low", "info"];

export function normalizeSeverity(s: string | undefined): Severity {
  const low = (s || "").toLowerCase();
  return (SEVS as string[]).includes(low) ? (low as Severity) : "info";
}

export function toFinding(f: ApiFinding, runId: string): Finding {
  const { target, path } = splitTarget(f.url || "");
  const desc = f.description || "";
  return {
    id: f.id,
    severity: normalizeSeverity(f.severity),
    title: f.title,
    category: f.category || "unclassified",
    target,
    path,
    status: "in-review",
    confidence: "medium",
    cvss: "—",
    cwe: "—",
    owasp: "—",
    detected: "",
    runId,
    evidenceCount: 0,
    summary: desc,
    verification: "Recorded after deterministic verification by the scan probes.",
    reproduction: [],
    impact: desc,
    recommendation: "See the full report for remediation guidance.",
    evidence: { request: "", response: "", dom: "", console: "", network: [] },
  };
}

export function countBySeverity(list: ApiFinding[]): SeverityCounts {
  const c: SeverityCounts = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
  list.forEach((f) => {
    c[normalizeSeverity(f.severity)] += 1;
  });
  return c;
}

/* ------------------------------------------------------------------ */
/* Report JSON fetching (per-run findings browsing)                     */
/* ------------------------------------------------------------------ */

export interface ReportJson {
  target?: string;
  started_at?: string;
  finished_at?: string;
  status?: string;
  findings: ApiFinding[];
}

export async function fetchReportFindings(stamp: string): Promise<ApiFinding[]> {
  const rep = await get<ReportJson>(`/api/report/${stamp}/json`);
  return rep.findings || [];
}

/* ------------------------------------------------------------------ */
/* Calls                                                                */
/* ------------------------------------------------------------------ */

export const api = {
  me: () => get<MeData>("/api/me"),
  state: () => get<LiveState>("/api/state"),
  scanStatus: () => get<ScanStatus>("/api/scan/status"),
  history: () => get<{ runs: HistoryRun[] }>("/api/history"),
  diff: () => get<DiffData>("/api/diff"),
  configs: () => get<{ configs: ConfigEntry[] }>("/api/configs"),
  capabilities: (config: string) =>
    get<Capabilities>(`/api/scan/capabilities?config=${encodeURIComponent(config)}`),
  report: () => get<ReportFile>("/api/report"),
  startScan: (config: string, skip_llm: boolean, authorized: boolean) =>
    post<{ started: boolean; config: string; skip_llm: boolean; created: boolean }>("/api/scan", {
      config,
      skip_llm,
      authorized,
    }),
  logout: async () => {
    // Flask's logout is a CSRF-guarded form POST — fetch the session token first.
    const { csrf_token } = await get<{ csrf_token: string }>("/api/csrf");
    await fetch("/logout", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ csrf_token }),
    });
    window.location.href = "/console/login";
  },
  adminOverview: () => get<AdminOverview>("/api/admin/overview"),
  suspendUser: async (user_id: number, suspended: boolean, reason: string) => {
    const { csrf_token } = await get<{ csrf_token: string }>("/api/csrf");
    return post<{ ok: boolean }>("/api/admin/suspend", {
      user_id,
      suspended,
      reason,
      csrf_token,
    });
  },
  createInvite: async () => {
    const { csrf_token } = await get<{ csrf_token: string }>("/api/csrf");
    return post<{ code: string }>("/api/admin/invites", { csrf_token });
  },
};

export function downloadUrl(stamp: string, fmt: string): string {
  return `/api/report/${stamp}/${fmt}`;
}
