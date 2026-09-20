import { useEffect, useState } from "react";
import { User, ShieldCheck, FileText, LogOut, KeyRound } from "lucide-react";
import { PanelHeader } from "../components/ui";
import { api, type MeData } from "../lib/api";

export function Settings() {
  const [me, setMe] = useState<MeData | null>(null);

  useEffect(() => {
    api
      .me()
      .then(setMe)
      .catch(() => setMe(null));
  }, []);

  return (
    <div className="px-4 py-5 sm:px-6">
      <div>
        <h1 className="text-[18px] font-semibold tracking-[-0.012em] text-ink">Settings</h1>
        <p className="mt-1 max-w-[620px] text-[11.5px] leading-relaxed text-muted">
          Account, access, and legal controls for this instance.
        </p>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Account */}
        <div className="rounded-[6px] border border-line bg-app-850">
          <PanelHeader title="Account" icon={<User size={13} />} />
          <div className="space-y-3 p-4">
            <div className="flex items-start justify-between gap-3">
              <span className="shrink-0 text-[9.5px] text-faint">Signed in as</span>
              <span className="truncate text-right font-mono text-[11px] text-ink-soft">
                {me ? (me.email || "bootstrap token") : "…"}
              </span>
            </div>
            <div className="flex items-start justify-between gap-3">
              <span className="shrink-0 text-[9.5px] text-faint">Role</span>
              <span className="font-mono text-[11px] text-ink-soft">
                {me ? (me.admin ? "admin" : "user") : "…"}
              </span>
            </div>
            <div className="border-t border-line pt-3">
              <button className="btn-secondary" onClick={() => api.logout()}>
                <LogOut size={12} />
                Sign out
              </button>
            </div>
          </div>
        </div>

        {/* Access */}
        <div className="rounded-[6px] border border-line bg-app-850">
          <PanelHeader title="Access" icon={<KeyRound size={13} />} />
          <div className="space-y-3 p-4 text-[11px] leading-relaxed text-muted">
            <p>
              Signup is invite-only after the first admin account. Generate single-use invite
              codes on the server-rendered pages:
            </p>
            <div className="flex flex-wrap gap-2">
              <a className="btn-secondary !py-[6px] !text-[10.5px]" href="/invites">
                Invite codes
              </a>
              <a className="btn-secondary !py-[6px] !text-[10.5px]" href="/admin">
                Admin console
              </a>
            </div>
          </div>
        </div>

        {/* Legal */}
        <div className="rounded-[6px] border border-line bg-app-850">
          <PanelHeader title="Legal" icon={<ShieldCheck size={13} />} />
          <div className="space-y-3 p-4 text-[11px] leading-relaxed text-muted">
            <p>
              Authorized testing only. Scanning requires a per-run ownership declaration, and
              every report is stamped with who authorized it, when, and from where.
            </p>
            <div className="flex flex-wrap gap-2">
              <a className="btn-secondary !py-[6px] !text-[10.5px]" href="/terms" target="_blank" rel="noreferrer">
                <FileText size={11} />
                Terms of Service
              </a>
              <a className="btn-secondary !py-[6px] !text-[10.5px]" href="/abuse" target="_blank" rel="noreferrer">
                Report abuse
              </a>
            </div>
          </div>
        </div>

        {/* Backend */}
        <div className="rounded-[6px] border border-line bg-app-850">
          <PanelHeader title="Backend" />
          <div className="space-y-3 p-4">
            {[
              ["Engine", "Sentinel qaagent 0.1.0"],
              ["Probes", "deterministic · passive + active"],
              ["Browser", "Chromium via Playwright"],
              ["Reports", "Markdown · JSON · HTML · CSV · TestIO"],
            ].map(([k, v]) => (
              <div key={k} className="flex items-start justify-between gap-3">
                <span className="shrink-0 text-[9.5px] text-faint">{k}</span>
                <span className="truncate text-right font-mono text-[10px] text-ink-soft">
                  {v}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
