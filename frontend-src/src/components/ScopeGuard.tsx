import { ShieldCheck, Lock, Globe, Ban, Gauge, AlertTriangle } from "lucide-react";

export function ScopeGuard({
  target = "https://app.example.com",
  origins = ["app.example.com", "assets.example.com", "staging.example.com"],
  excluded = ["/admin/delete", "/payments/*", "/api/v1/internal/*"],
  rateLimit = "2 req/sec",
  used = 1284,
  budget = 5000,
  compact = false,
}: {
  target?: string;
  origins?: string[];
  excluded?: string[];
  rateLimit?: string;
  used?: number;
  budget?: number;
  compact?: boolean;
}) {
  return (
    <div className="overflow-hidden rounded-[6px] border border-line bg-app-850">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3 border-b border-line bg-app-880 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span className="flex h-[22px] w-[22px] items-center justify-center rounded-[4px] border border-[rgba(70,167,88,0.32)] bg-[rgba(70,167,88,0.12)]">
            <ShieldCheck size={12} className="text-[#66c07a]" />
          </span>
          <h2 className="text-[10.5px] font-semibold uppercase tracking-[0.11em] text-ink-soft">
            Scope protection
          </h2>
        </div>

        <div className="flex items-center gap-1.5 rounded-[4px] border border-[rgba(70,167,88,0.3)] bg-[rgba(70,167,88,0.1)] px-2 py-[3px]">
          <Lock size={10} className="text-[#66c07a]" />
          <span className="font-mono text-[9px] font-semibold uppercase tracking-[0.13em] text-[#66c07a]">
            Enforced
          </span>
        </div>

        <div className="ml-auto flex items-center gap-4 font-mono text-[9px] text-faint">
          <span>policy: strict</span>
          <span>violations: 0</span>
          <span>last check: 09:42:52</span>
        </div>
      </div>

      {/* Body */}
      <div className={`grid gap-px bg-line ${compact ? "grid-cols-1 sm:grid-cols-2" : "grid-cols-1 sm:grid-cols-2 lg:grid-cols-4"}`}>
        <ScopeCell icon={<Globe size={12} />} label="Authorized target">
          <div className="font-mono text-[11px] text-ink">{target}</div>
          <div className="mt-1.5 text-[10px] leading-relaxed text-dim">
            All outbound requests are validated against this origin before dispatch.
          </div>
        </ScopeCell>

        <ScopeCell icon={<ShieldCheck size={12} />} label="Allowed origins">
          <ul className="space-y-1">
            {origins.map((o) => (
              <li key={o} className="flex items-center gap-1.5 font-mono text-[10px] text-ink-soft">
                <span className="h-[4px] w-[4px] rounded-[1px] bg-[#46a758]" />
                {o}
              </li>
            ))}
          </ul>
        </ScopeCell>

        <ScopeCell icon={<Ban size={12} />} label="Excluded paths">
          <ul className="space-y-1">
            {excluded.map((p) => (
              <li key={p} className="flex items-center gap-1.5 font-mono text-[10px] text-[#f0b95c]">
                <span className="h-[4px] w-[4px] rounded-[1px] bg-[#f5a623]" />
                {p}
              </li>
            ))}
          </ul>
          <div className="mt-2 text-[9.5px] text-faint">Matching requests are aborted before send.</div>
        </ScopeCell>

        <ScopeCell icon={<Gauge size={12} />} label="Rate limit & budget">
          <div className="font-mono text-[11px] text-ink">{rateLimit}</div>
          <div className="mt-2">
            <div className="flex items-center justify-between font-mono text-[9px] text-faint">
              <span>request budget</span>
              <span>
                {used.toLocaleString()} / {budget.toLocaleString()}
              </span>
            </div>
            <div className="mt-1 h-[5px] w-full overflow-hidden rounded-[2px] bg-app-750">
              <div
                className="h-full rounded-[2px] bg-[#4c8dff]"
                style={{ width: `${Math.min(100, (used / budget) * 100)}%` }}
              />
            </div>
            <div className="mt-1.5 text-[9.5px] text-faint">
              {Math.round((used / budget) * 100)}% consumed · hard stop at limit
            </div>
          </div>
        </ScopeCell>
      </div>

      {/* Enforcement strip */}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-line bg-app-880 px-4 py-2.5">
        {[
          "Origin validation on every request",
          "Redirects followed only within scope",
          "Out-of-scope discovery reported, never executed",
          "Automatic abort on policy violation",
        ].map((item) => (
          <div key={item} className="flex items-center gap-1.5">
            <ShieldCheck size={10} className="text-[#66c07a]" />
            <span className="text-[9.5px] text-muted">{item}</span>
          </div>
        ))}
        <div className="ml-auto flex items-center gap-1.5">
          <AlertTriangle size={10} className="text-faint" />
          <span className="font-mono text-[9px] text-faint">
            scope changes require run restart
          </span>
        </div>
      </div>
    </div>
  );
}

function ScopeCell({
  icon,
  label,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-app-850 p-4">
      <div className="flex items-center gap-1.5">
        <span className="text-dim">{icon}</span>
        <span className="text-[9px] font-semibold uppercase tracking-[0.12em] text-faint">{label}</span>
      </div>
      <div className="mt-2.5">{children}</div>
    </div>
  );
}
