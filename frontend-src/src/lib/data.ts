import type { Finding, Severity } from "./types";
import { findingsCore } from "./findings-core";
import { findingsMore } from "./findings-more";

export * from "./types";

export const findings: Finding[] = [...findingsCore, ...findingsMore];

export const getFinding = (id: string): Finding | undefined =>
  findings.find((f) => f.id.toLowerCase() === id.toLowerCase());

export const severityCounts = (list: Finding[] = findings) => {
  const counts: Record<Severity, number> = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
  list.forEach((f) => {
    counts[f.severity] += 1;
  });
  return counts;
};

export type Phase = "OBSERVE" | "THINK" | "ACT" | "VERIFY" | "ASSERT" | "CAPTURE" | "SCOPE";

export interface TimelineEvent {
  time: string;
  phase: Phase;
  description: string;
  detail?: string;
  status: "ok" | "info" | "warn" | "fail" | "pass";
}

export const timeline: TimelineEvent[] = [
  {
    time: "09:42:11",
    phase: "SCOPE",
    description: "Origin verified against allowed scope",
    detail: "app.example.com · /search · GET",
    status: "ok",
  },
  {
    time: "09:42:11",
    phase: "OBSERVE",
    description: "Read accessibility tree",
    detail: "142 nodes · 6 interactive controls",
    status: "info",
  },
  {
    time: "09:42:12",
    phase: "THINK",
    description: "Search input identified as primary entry point",
    detail: "selector #search-input[name=q]",
    status: "info",
  },
  {
    time: "09:42:13",
    phase: "ACT",
    description: "Submitting reflected-input probe to /search",
    detail: "GET /search?q=<script>/*probe*/</script>",
    status: "ok",
  },
  {
    time: "09:42:14",
    phase: "VERIFY",
    description: "Response contains unencoded user input",
    detail: "2 reflection points detected",
    status: "warn",
  },
  {
    time: "09:42:15",
    phase: "ASSERT",
    description: "innerHTML write confirmed at render-utils.js:64",
    status: "warn",
  },
  {
    time: "09:42:16",
    phase: "CAPTURE",
    description: "Evidence bundle recorded for FND-1043",
    detail: "screenshot · request · response · dom · console",
    status: "ok",
  },
  {
    time: "09:42:18",
    phase: "SCOPE",
    description: "Rate limiter: 2 req/sec · token bucket 1.4 available",
    status: "ok",
  },
  {
    time: "09:42:19",
    phase: "OBSERVE",
    description: "Reading page structure for next test case",
    detail: "coverage: 41 / 68 checks complete",
    status: "info",
  },
];

export const liveTimelineFeed: TimelineEvent[] = [
  {
    time: "09:42:21",
    phase: "ACT",
    description: "Submitting SQL predicate probe to /api/v1/accounts",
    detail: "probe 4/6 · boolean-based",
    status: "ok",
  },
  {
    time: "09:42:23",
    phase: "VERIFY",
    description: "Response length delta within expected range",
    detail: "1224 B → 4812 B",
    status: "warn",
  },
  {
    time: "09:42:25",
    phase: "ASSERT",
    description: "Injection signal confidence 0.97",
    status: "warn",
  },
  {
    time: "09:42:26",
    phase: "CAPTURE",
    description: "Capturing response body for evidence bundle",
    detail: "4.7 kB · sha256 3f9c…a71b",
    status: "ok",
  },
  {
    time: "09:42:28",
    phase: "SCOPE",
    description: "Origin verified against allowed scope",
    detail: "app.example.com · GET /api/v1/accounts",
    status: "ok",
  },
  {
    time: "09:42:30",
    phase: "OBSERVE",
    description: "Reading pagination links from response",
    detail: "3 pages discovered",
    status: "info",
  },
  {
    time: "09:42:32",
    phase: "THINK",
    description: "Selecting next check: object-level authorization",
    detail: "test idor.invoice.download",
    status: "info",
  },
  {
    time: "09:42:34",
    phase: "ACT",
    description: "Requesting invoice resource with viewer principal",
    detail: "GET /api/v1/invoices/8824",
    status: "ok",
  },
  {
    time: "09:42:35",
    phase: "VERIFY",
    description: "Authorization decision mismatch detected",
    detail: "expected deny · observed allow",
    status: "fail",
  },
  {
    time: "09:42:36",
    phase: "CAPTURE",
    description: "Finding FND-1045 recorded with 3 evidence artifacts",
    status: "ok",
  },
  {
    time: "09:42:38",
    phase: "ACT",
    description: "Navigating to /account/settings for functional check",
    status: "ok",
  },
  {
    time: "09:42:40",
    phase: "OBSERVE",
    description: "Read accessibility tree",
    detail: "88 nodes · 12 interactive controls",
    status: "info",
  },
  {
    time: "09:42:41",
    phase: "ACT",
    description: "Submitting profile form with valid test payload",
    status: "ok",
  },
  {
    time: "09:42:43",
    phase: "VERIFY",
    description: "Form submission persisted and re-rendered correctly",
    status: "pass",
  },
  {
    time: "09:42:44",
    phase: "CAPTURE",
    description: "Functional test result recorded (pass)",
    status: "ok",
  },
  {
    time: "09:42:46",
    phase: "SCOPE",
    description: "Request budget: 1284 / 5000 used",
    status: "ok",
  },
  {
    time: "09:42:48",
    phase: "THINK",
    description: "Selecting next check: security header baseline",
    detail: "test config.headers.baseline",
    status: "info",
  },
  {
    time: "09:42:50",
    phase: "ACT",
    description: "Collecting response headers from 6 discovered routes",
    status: "ok",
  },
  {
    time: "09:42:52",
    phase: "VERIFY",
    description: "Permissions-Policy header absent on 6 of 6 routes",
    status: "warn",
  },
  {
    time: "09:42:53",
    phase: "CAPTURE",
    description: "Header matrix stored for report generation",
    status: "ok",
  },
];

export interface Run {
  id: string;
  target: string;
  profile: string;
  status: "running" | "completed" | "stopped" | "failed" | "queued";
  started: string;
  duration: string;
  tests: number;
  requests: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  info: number;
  coverage: number;
}

export const runs: Run[] = [
  {
    id: "run_8f31c2",
    target: "https://app.example.com",
    profile: "Full Web Application Assessment",
    status: "running",
    started: "2026-09-19 09:36:12",
    duration: "00:27:41",
    tests: 147,
    requests: 1284,
    critical: 1,
    high: 3,
    medium: 7,
    low: 4,
    info: 9,
    coverage: 72,
  },
  {
    id: "run_7c92aa",
    target: "https://app.example.com",
    profile: "Passive Security Review",
    status: "completed",
    started: "2026-09-18 22:14:03",
    duration: "00:41:18",
    tests: 212,
    requests: 2140,
    critical: 0,
    high: 2,
    medium: 5,
    low: 6,
    info: 11,
    coverage: 91,
  },
  {
    id: "run_6b18de",
    target: "https://staging.example.com",
    profile: "Full Web Application Assessment",
    status: "completed",
    started: "2026-09-18 14:02:51",
    duration: "01:12:44",
    tests: 341,
    requests: 4822,
    critical: 2,
    high: 6,
    medium: 12,
    low: 9,
    info: 18,
    coverage: 96,
  },
  {
    id: "run_5a44c1",
    target: "https://api.example.com",
    profile: "API Endpoint Assessment",
    status: "completed",
    started: "2026-09-17 19:48:22",
    duration: "00:22:09",
    tests: 96,
    requests: 812,
    critical: 0,
    high: 1,
    medium: 3,
    low: 2,
    info: 6,
    coverage: 64,
  },
  {
    id: "run_4e77b0",
    target: "https://app.example.com",
    profile: "Regression Suite",
    status: "stopped",
    started: "2026-09-17 11:20:44",
    duration: "00:08:52",
    tests: 34,
    requests: 268,
    critical: 0,
    high: 0,
    medium: 1,
    low: 1,
    info: 2,
    coverage: 22,
  },
  {
    id: "run_3d12f9",
    target: "https://docs.example.com",
    profile: "Passive Security Review",
    status: "completed",
    started: "2026-09-16 08:11:02",
    duration: "00:14:37",
    tests: 78,
    requests: 496,
    critical: 0,
    high: 0,
    medium: 2,
    low: 3,
    info: 8,
    coverage: 88,
  },
  {
    id: "run_2c88ae",
    target: "https://app.example.com",
    profile: "Authentication Flow Test",
    status: "failed",
    started: "2026-09-15 16:44:19",
    duration: "00:02:11",
    tests: 6,
    requests: 22,
    critical: 0,
    high: 0,
    medium: 0,
    low: 0,
    info: 1,
    coverage: 4,
  },
];

export interface TestSuite {
  id: string;
  name: string;
  category: string;
  type: "security" | "functional" | "configuration";
  enabled: boolean;
  checks: number;
  description: string;
  lastRun: string;
  passRate: number;
}

export const testLibrary: TestSuite[] = [
  {
    id: "sec.headers",
    name: "Security Header Analysis",
    category: "Configuration",
    type: "configuration",
    enabled: true,
    checks: 18,
    description:
      "Evaluates HTTP response headers including CSP, HSTS, X-Frame-Options, Referrer-Policy, Permissions-Policy, and cookie attributes across all discovered routes.",
    lastRun: "2026-09-19 09:38:04",
    passRate: 72,
  },
  {
    id: "sec.xss",
    name: "Cross-Site Scripting Detection",
    category: "Injection",
    type: "security",
    enabled: true,
    checks: 24,
    description:
      "Reflected, stored, and DOM-based XSS detection using context-aware payloads. Includes output-encoding verification and sink analysis via the DOM snapshot.",
    lastRun: "2026-09-19 09:42:19",
    passRate: 83,
  },
  {
    id: "sec.sqli",
    name: "SQL Injection Testing",
    category: "Injection",
    type: "security",
    enabled: true,
    checks: 21,
    description:
      "Boolean-based, error-based, and time-based injection probes against all parameterised inputs with statistical response analysis and rate-limit awareness.",
    lastRun: "2026-09-19 09:44:02",
    passRate: 90,
  },
  {
    id: "sec.auth",
    name: "Authentication & Session Controls",
    category: "Authentication",
    type: "security",
    enabled: true,
    checks: 26,
    description:
      "Credential policy enforcement, session lifecycle, token validation, logout invalidation, MFA flow integrity, and brute-force protection verification.",
    lastRun: "2026-09-19 09:41:07",
    passRate: 68,
  },
  {
    id: "sec.access",
    name: "Access Control Verification",
    category: "Authorization",
    type: "security",
    enabled: true,
    checks: 19,
    description:
      "Object-level and function-level authorization testing using supplied principals, including horizontal and vertical privilege-escalation checks.",
    lastRun: "2026-09-19 09:47:31",
    passRate: 79,
  },
  {
    id: "sec.tls",
    name: "TLS & Transport Security",
    category: "Configuration",
    type: "configuration",
    enabled: true,
    checks: 12,
    description:
      "Protocol version negotiation, cipher suite evaluation, certificate chain validation, HSTS configuration, and redirect behaviour analysis.",
    lastRun: "2026-09-19 09:36:44",
    passRate: 100,
  },
  {
    id: "func.forms",
    name: "Form Submission & Validation",
    category: "Functional",
    type: "functional",
    enabled: true,
    checks: 32,
    description:
      "Deterministic interaction with all discovered forms: validation messaging, error states, successful submission, and round-trip data integrity.",
    lastRun: "2026-09-19 09:52:11",
    passRate: 94,
  },
  {
    id: "func.navigation",
    name: "Navigation & Routing",
    category: "Functional",
    type: "functional",
    enabled: true,
    checks: 28,
    description:
      "Crawls the application graph, validates link integrity, checks for broken routes, verifies redirect chains, and confirms expected page rendering.",
    lastRun: "2026-09-19 10:02:44",
    passRate: 98,
  },
  {
    id: "func.authflow",
    name: "Authentication Flow",
    category: "Functional",
    type: "functional",
    enabled: true,
    checks: 16,
    description:
      "Exercises login, logout, registration, password reset, and session persistence using the supplied test credentials.",
    lastRun: "2026-09-19 09:49:02",
    passRate: 100,
  },
  {
    id: "sec.discovery",
    name: "Endpoint & Resource Discovery",
    category: "Reconnaissance",
    type: "security",
    enabled: true,
    checks: 14,
    description:
      "Sitemap parsing, robots directives, JavaScript route extraction, common-path verification, and API schema discovery within the authorised scope.",
    lastRun: "2026-09-19 09:37:18",
    passRate: 100,
  },
  {
    id: "sec.upload",
    name: "File Upload Handling",
    category: "Input Validation",
    type: "security",
    enabled: false,
    checks: 11,
    description:
      "Validates file type enforcement, size limits, filename sanitisation, storage isolation, and retrieval controls for upload endpoints.",
    lastRun: "—",
    passRate: 0,
  },
  {
    id: "sec.rate",
    name: "Rate Limiting & Throttling",
    category: "Abuse Resistance",
    type: "security",
    enabled: true,
    checks: 9,
    description:
      "Measures request throttling behaviour, backoff signalling, and lockout thresholds across authentication and high-value endpoints.",
    lastRun: "2026-09-19 09:53:02",
    passRate: 55,
  },
];

export const coverageByCategory = [
  { category: "Configuration", coverage: 96, checks: 30, passed: 29, failed: 1 },
  { category: "Injection", coverage: 88, checks: 45, passed: 38, failed: 7 },
  { category: "Authentication", coverage: 81, checks: 42, passed: 33, failed: 9 },
  { category: "Authorization", coverage: 74, checks: 19, passed: 14, failed: 5 },
  { category: "Functional", coverage: 92, checks: 76, passed: 72, failed: 4 },
  { category: "Reconnaissance", coverage: 100, checks: 14, passed: 14, failed: 0 },
];

export const requestVolume = [
  { time: "09:36", requests: 42, findings: 0 },
  { time: "09:38", requests: 118, findings: 2 },
  { time: "09:40", requests: 164, findings: 1 },
  { time: "09:42", requests: 208, findings: 3 },
  { time: "09:44", requests: 186, findings: 2 },
  { time: "09:46", requests: 172, findings: 1 },
  { time: "09:48", requests: 148, findings: 2 },
  { time: "09:50", requests: 132, findings: 1 },
  { time: "09:52", requests: 114, findings: 1 },
  { time: "09:54", requests: 96, findings: 1 },
  { time: "09:56", requests: 88, findings: 0 },
  { time: "09:58", requests: 74, findings: 1 },
];

export const testsOverTime = [
  { time: "09:36", executed: 8, cumulative: 8 },
  { time: "09:38", executed: 22, cumulative: 30 },
  { time: "09:40", executed: 26, cumulative: 56 },
  { time: "09:42", executed: 24, cumulative: 80 },
  { time: "09:44", executed: 19, cumulative: 99 },
  { time: "09:46", executed: 16, cumulative: 115 },
  { time: "09:48", executed: 12, cumulative: 127 },
  { time: "09:50", executed: 9, cumulative: 136 },
  { time: "09:52", executed: 6, cumulative: 142 },
  { time: "09:54", executed: 3, cumulative: 145 },
  { time: "09:56", executed: 2, cumulative: 147 },
  { time: "09:58", executed: 0, cumulative: 147 },
];
