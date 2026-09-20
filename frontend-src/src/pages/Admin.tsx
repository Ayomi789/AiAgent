import { useCallback, useEffect, useState } from "react";
import { ShieldCheck, Users, KeyRound, Activity, Copy, Check } from "lucide-react";
import { PanelHeader, StatusBadge } from "../components/ui";
import { ApiError, api, type AdminOverview } from "../lib/api";

export function Admin() {
  const [data, setData] = useState<AdminOverview | null>(null);
  const [denied, setDenied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reason, setReason] = useState<Record<number, string>>({});
  const [copied, setCopied] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setData(await api.adminOverview());
      setDenied(false);
    } catch (e) {
      if (e instanceof ApiError && (e.status === 403 || e.status === 401)) setDenied(true);
      else setError("Could not load admin data — is the server awake?");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const suspend = async (id: number, suspendIt: boolean) => {
    setBusy(`user-${id}`);
    setError(null);
    try {
      await api.suspendUser(id, suspendIt, reason[id] || "");
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Action failed.");
    } finally {
      setBusy(null);
    }
  };

  const invite = async () => {
    setBusy("invite");
    setError(null);
    try {
      const { code } = await api.createInvite();
      await refresh();
      await navigator.clipboard.writeText(code).catch(() => {});
      setCopied(code);
      window.setTimeout(() => setCopied(null), 4000);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not mint invite.");
    } finally {
      setBusy(null);
    }
  };

  if (denied) {
    return (
      <div className="px-4 py-5 sm:px-6">
        <div className="max-w-[520px] rounded-[6px] border border-line bg-app-850 p-6">
          <h1 className="text-[15px] font-semibold text-ink">Admin only</h1>
          <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted">
            This console is restricted to instance admins. If you run this server, sign in with
            the admin account.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="px-4 py-5 sm:px-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck size={15} className="text-[#7fa9f0]" />
            <h1 className="text-[18px] font-semibold tracking-[-0.012em] text-ink">
              Admin console
            </h1>
          </div>
          <p className="mt-1 max-w-[620px] text-[11.5px] leading-relaxed text-muted">
            Accounts, suspension, running scan, and invite codes in one view. Suspension takes
            effect on the user's very next request; their reports stay retained.
          </p>
        </div>
      </div>

      {error ? (
        <div className="mt-4 rounded-[6px] border border-[rgba(229,72,77,0.35)] bg-[rgba(229,72,77,0.08)] px-3.5 py-2.5 text-[11.5px] text-[#f28286]">
          {error}
        </div>
      ) : null}
      {copied ? (
        <div className="mt-4 flex items-center gap-2 rounded-[6px] border border-[rgba(70,167,88,0.3)] bg-[rgba(70,167,88,0.08)] px-3.5 py-2.5">
          <Check size={12} className="shrink-0 text-[#66c07a]" />
          <span className="text-[11.5px] text-[#66c07a]">
            Invite minted and copied: <span className="font-mono">{copied}</span>
          </span>
        </div>
      ) : null}

      {/* Running scan */}
      <div className="mt-5 overflow-hidden rounded-[6px] border border-line bg-app-850">
        <PanelHeader title="Running scan" icon={<Activity size={13} />} />
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 p-4 font-mono text-[10px] text-muted">
          {data ? (
            data.scan.running ? (
              <>
                <StatusBadge status="running" pulse />
                <span>
                  config: <span className="text-ink-soft">{data.scan.config || "—"}</span>
                </span>
                <span>
                  started:{" "}
                  <span className="text-ink-soft">
                    {(data.scan.started || "").slice(0, 16).replace("T", " ")}
                  </span>
                </span>
                <span>
                  by: <span className="text-ink-soft">{data.scan.owner_email || "token"}</span>
                </span>
              </>
            ) : (
              <>
                <StatusBadge status="completed" />
                <span className="text-faint">
                  idle
                  {data.scan.returncode !== null && data.scan.returncode !== undefined
                    ? ` · last exit: ${data.scan.returncode}`
                    : ""}
                  {data.scan.config ? ` · last config: ${data.scan.config}` : ""}
                </span>
              </>
            )
          ) : (
            <span className="text-faint">Loading…</span>
          )}
        </div>
      </div>

      {/* Accounts */}
      <div className="mt-4 overflow-hidden rounded-[6px] border border-line bg-app-850">
        <PanelHeader
          title="Accounts"
          subtitle={data ? `${data.users.length} account(s) on this instance` : "Loading…"}
          icon={<Users size={13} />}
        />
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b border-line">
                {["ID", "Email", "Status", "Detail", "Action"].map((h) => (
                  <th
                    key={h}
                    className="whitespace-nowrap px-4 py-2.5 text-left text-[8.5px] font-semibold uppercase tracking-[0.13em] text-faint"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(data?.users || []).map((u) => (
                <tr
                  key={u.id}
                  className="border-b border-line-soft transition-colors last:border-0 hover:bg-app-800"
                >
                  <td className="px-4 py-3 font-mono text-[10px] text-faint">#{u.id}</td>
                  <td className="px-4 py-3 font-mono text-[11px] text-ink-soft">{u.email}</td>
                  <td className="px-4 py-3">
                    <StatusBadge
                      status={
                        u.suspended ? "failed" : u.role === "admin" ? "verified" : "triaged"
                      }
                    />
                    <span className="ml-2 text-[9.5px] text-dim">
                      {u.suspended ? "suspended" : u.role}
                    </span>
                  </td>
                  <td className="max-w-[240px] truncate px-4 py-3 text-[10.5px] text-dim">
                    {u.suspended ? u.suspend_reason || "suspended" : `created ${u.created_at || "—"}`}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <input
                        className="field w-[150px] !py-[5px] text-[10px]"
                        placeholder="reason (optional)"
                        maxLength={200}
                        value={reason[u.id] || ""}
                        onChange={(e) => setReason((r) => ({ ...r, [u.id]: e.target.value }))}
                        aria-label={`Suspension reason for ${u.email}`}
                      />
                      {u.suspended ? (
                        <button
                          className="btn-secondary !py-[5px] !text-[10px]"
                          disabled={busy === `user-${u.id}`}
                          onClick={() => suspend(u.id, false)}
                        >
                          Reinstate
                        </button>
                      ) : (
                        <button
                          className="btn-danger !py-[5px] !text-[10px]"
                          disabled={busy === `user-${u.id}`}
                          onClick={() => suspend(u.id, true)}
                        >
                          Suspend
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Invites */}
      <div className="mt-4 overflow-hidden rounded-[6px] border border-line bg-app-850">
        <PanelHeader
          title="Invite codes"
          subtitle="Single-use · each code works exactly once"
          icon={<KeyRound size={13} />}
          action={
            <button
              className="btn-secondary !py-[5px] !text-[10px]"
              disabled={busy === "invite"}
              onClick={invite}
            >
              Generate invite code
            </button>
          }
        />
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b border-line">
                {["Code", "Created", "Status", "Used"].map((h) => (
                  <th
                    key={h}
                    className="whitespace-nowrap px-4 py-2.5 text-left text-[8.5px] font-semibold uppercase tracking-[0.13em] text-faint"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(data?.invites || []).map((inv) => (
                <tr
                  key={inv.code}
                  className="border-b border-line-soft transition-colors last:border-0 hover:bg-app-800"
                >
                  <td className="px-4 py-3">
                    <button
                      className="flex items-center gap-1.5 font-mono text-[11px] text-ink-soft hover:text-[#7fa9f0]"
                      onClick={() => {
                        navigator.clipboard.writeText(inv.code).catch(() => {});
                        setCopied(inv.code);
                        window.setTimeout(() => setCopied(null), 4000);
                      }}
                      title="Copy code"
                    >
                      <Copy size={10} className="text-faint" />
                      {inv.code}
                    </button>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 font-mono text-[10px] text-muted">
                    {(inv.created_at || "").slice(0, 16).replace("T", " ")}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={inv.used ? "stopped" : "completed"} />
                    <span className="ml-2 text-[9.5px] text-dim">
                      {inv.used ? "used" : "open"}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 font-mono text-[10px] text-faint">
                    {(inv.used_at || "").slice(0, 16).replace("T", " ") || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {(data?.invites || []).length === 0 ? (
            <div className="px-6 py-10 text-center">
              <p className="text-[11px] text-dim">No invites yet — generate the first one.</p>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
