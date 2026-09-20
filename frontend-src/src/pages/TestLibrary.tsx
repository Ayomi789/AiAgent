import { ShieldCheck, Eye, Zap, KeyRound } from "lucide-react";
import { PanelHeader } from "../components/ui";

interface ProbeGroup {
  title: string;
  description: string;
  icon: React.ReactNode;
  items: { name: string; detail: string }[];
}

const GROUPS: ProbeGroup[] = [
  {
    title: "Passive checks",
    description: "Observational — a single GET, no state-changing requests.",
    icon: <Eye size={13} />,
    items: [
      { name: "Security headers", detail: "CSP, X-Frame-Options, HSTS, X-Content-Type-Options, Referrer-Policy." },
      { name: "Cookie flags", detail: "HttpOnly, Secure, SameSite on session cookies." },
      { name: "Server banners", detail: "Version disclosure via Server / X-Powered-By headers." },
    ],
  },
  {
    title: "Active probes",
    description: "Authorized, non-destructive, content-validated before reporting.",
    icon: <Zap size={13} />,
    items: [
      { name: "Reflected XSS", detail: "Payload reflection checks on forms and search inputs." },
      { name: "Template injection", detail: "{{7*37}} → 259 evaluation test." },
      { name: "SQL injection", detail: "Boolean and error-based inference on inputs." },
      { name: "Login bypass", detail: "Authentication-bypass payloads against login forms." },
      { name: "Sensitive files", detail: "~60 backup/secret artifact names, verified by content — never by status code alone." },
      { name: "Sensitive endpoints", detail: "Admin/debug panels, .git/config, .env — SPA fallbacks and login forms excluded." },
      { name: "IDOR enumeration", detail: "Object-reference probing for cross-user data exposure." },
      { name: "Open redirect", detail: "3xx Location validation for off-origin redirects." },
    ],
  },
  {
    title: "Full-scan loop",
    description: "Only when deterministic mode is off.",
    icon: <KeyRound size={13} />,
    items: [
      { name: "Browser exploration", detail: "Observe → think → act → verify with real Chromium interaction." },
      { name: "Scope guard", detail: "Every navigation blocked outside allowed origins." },
      { name: "Evidence capture", detail: "Screenshots, DOM snapshots, console and network attached per finding." },
    ],
  },
];

export function TestLibrary() {
  return (
    <div className="px-4 py-5 sm:px-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-[18px] font-semibold tracking-[-0.012em] text-ink">Test library</h1>
            <span className="rounded-[4px] border border-line px-2 py-[2px] font-mono text-[8.5px] uppercase tracking-[0.13em] text-faint">
              {GROUPS.reduce((n, g) => n + g.items.length, 0)} checks
            </span>
          </div>
          <p className="mt-1 max-w-[640px] text-[11.5px] leading-relaxed text-muted">
            The exact checks every scan runs. Deterministic probes execute on every run; the
            browser loop adds exploration in full-scan mode.
          </p>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-4 xl:grid-cols-3">
        {GROUPS.map((g) => (
          <div key={g.title} className="rounded-[6px] border border-line bg-app-850">
            <PanelHeader title={g.title} subtitle={g.description} icon={g.icon} />
            <div className="divide-y divide-line-soft px-4">
              {g.items.map((item) => (
                <div key={item.name} className="py-2.5">
                  <div className="flex items-center gap-2 text-[12px] font-medium text-ink">
                    <ShieldCheck size={11} className="shrink-0 text-[#66c07a]" />
                    {item.name}
                  </div>
                  <p className="mt-1 text-[10.5px] leading-relaxed text-dim">{item.detail}</p>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
