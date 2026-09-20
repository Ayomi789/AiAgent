import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Play, Globe, ShieldCheck, CheckCircle2, AlertTriangle } from "lucide-react";
import { Toggle, PanelHeader } from "../components/ui";
import { ApiError, api, type ConfigEntry } from "../lib/api";

export function NewRun() {
  const navigate = useNavigate();
  const [target, setTarget] = useState("");
  const [configs, setConfigs] = useState<ConfigEntry[]>([]);
  const [selectedConfig, setSelectedConfig] = useState("");
  const [skipLlm, setSkipLlm] = useState(true);
  const [authorized, setAuthorized] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .configs()
      .then((d) => setConfigs(d.configs || []))
      .catch(() => setConfigs([]));
  }, []);

  const effectiveTarget = target.trim() || selectedConfig;

  const handleStart = async () => {
    if (!effectiveTarget) {
      setError("Enter a target domain or pick a saved config.");
      return;
    }
    if (!authorized) {
      setError("Confirm you own the site or have permission to test it.");
      return;
    }
    setStarting(true);
    setError(null);
    try {
      // A bare domain auto-creates a config server-side, mirroring the CLI.
      await api.startScan(target.trim() || selectedConfig, skipLlm, true);
      navigate("/app");
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.status === 409) setError("A scan is already running — wait for it to finish.");
        else if (e.status === 429) setError(e.message);
        else if (e.status === 403)
          setError(
            e.code === "terms_required"
              ? "Accept the Terms of Service first (see /terms), then start the scan."
              : e.message
          );
        else setError(e.message);
      } else {
        setError("Could not start the scan — is the server awake?");
      }
      setStarting(false);
    }
  };

  return (
    <div className="px-4 py-5 sm:px-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-[18px] font-semibold tracking-[-0.012em] text-ink">New test run</h1>
            <span className="rounded-[4px] border border-line px-2 py-[2px] font-mono text-[8.5px] uppercase tracking-[0.13em] text-faint">
              configuration
            </span>
          </div>
          <p className="mt-1 max-w-[620px] text-[11.5px] leading-relaxed text-muted">
            Configure the target and scan mode. The agent will not dispatch a single request
            outside the authorized scope.
          </p>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-4 xl:grid-cols-12">
        <div className="space-y-4 xl:col-span-8">
          {/* Target */}
          <div className="rounded-[6px] border border-line bg-app-850">
            <PanelHeader title="Target" icon={<Globe size={13} />} />
            <div className="grid grid-cols-1 gap-4 p-4 sm:grid-cols-2">
              <div>
                <label className="mb-1.5 block text-[9px] font-semibold uppercase tracking-[0.13em] text-faint">
                  Target domain
                </label>
                <input
                  className="field font-mono text-[11.5px]"
                  value={target}
                  onChange={(e) => {
                    setTarget(e.target.value);
                    setSelectedConfig("");
                  }}
                  placeholder="example.com"
                />
                <p className="mt-1.5 text-[9.5px] leading-relaxed text-faint">
                  A bare domain auto-creates a scoped config. Must be a host you are authorized
                  to test.
                </p>
              </div>

              <div>
                <label className="mb-1.5 block text-[9px] font-semibold uppercase tracking-[0.13em] text-faint">
                  Or saved config
                </label>
                <select
                  className="field appearance-none text-[11.5px]"
                  value={selectedConfig}
                  onChange={(e) => {
                    setSelectedConfig(e.target.value);
                    setTarget("");
                  }}
                >
                  <option value="">— pick a config —</option>
                  {configs.map((c) => (
                    <option key={c.file} value={c.name}>
                      {c.name} · {c.target || "no target"}
                    </option>
                  ))}
                </select>
                <p className="mt-1.5 text-[9.5px] leading-relaxed text-faint">
                  {configs.length
                    ? `${configs.length} saved config(s) on this instance.`
                    : "No saved configs yet — a domain above creates one."}
                </p>
              </div>
            </div>
          </div>

          {/* Scan mode */}
          <div className="rounded-[6px] border border-line bg-app-850">
            <PanelHeader
              title="Scan mode"
              subtitle="Deterministic probes always run; the LLM loop adds browser exploration"
            />
            <div className="divide-y divide-line-soft px-4">
              <Toggle
                label="Deterministic-only scan"
                description="Passive checks (headers, cookies, banners) plus active probes (XSS, SSTI, SQLi, login bypass, IDOR, open redirect, sensitive files). Seconds, no API key, no browser — fits small instances."
                checked={skipLlm}
                onChange={setSkipLlm}
              />
              <div className="flex items-start justify-between gap-4 py-2.5">
                <div className="min-w-0">
                  <div className="text-[12.5px] font-medium text-ink">Full scan (LLM + browser)</div>
                  <div className="mt-0.5 text-[11px] leading-relaxed text-dim">
                    Adds the observe → think → act → verify loop with real browser interaction.
                    Needs ~2 GB RAM and a working LLM key.
                  </div>
                </div>
                <span className="shrink-0 font-mono text-[9px] uppercase tracking-[0.12em] text-faint">
                  {!skipLlm ? "selected" : "off"}
                </span>
              </div>
            </div>
          </div>

          {/* Authorization */}
          <div className="rounded-[6px] border border-line bg-app-850">
            <PanelHeader title="Authorization" icon={<ShieldCheck size={13} />} />
            <div className="p-4">
              <label className="flex cursor-pointer items-start gap-2.5">
                <input
                  type="checkbox"
                  className="mt-[3px]"
                  checked={authorized}
                  onChange={(e) => setAuthorized(e.target.checked)}
                />
                <span className="text-[11.5px] leading-relaxed text-ink-soft">
                  I own <span className="font-mono">{effectiveTarget || "this target"}</span> or
                  have explicit permission to test it. This declaration is stamped onto every
                  report the run writes.
                </span>
              </label>
            </div>
          </div>

          {error ? (
            <div className="flex items-start gap-2 rounded-[6px] border border-[rgba(229,72,77,0.35)] bg-[rgba(229,72,77,0.08)] p-3">
              <AlertTriangle size={13} className="mt-[1px] shrink-0 text-[#f28286]" />
              <p className="text-[11.5px] leading-relaxed text-[#f28286]">{error}</p>
            </div>
          ) : null}
        </div>

        {/* Summary rail */}
        <div className="space-y-4 xl:col-span-4">
          <div className="rounded-[6px] border border-line bg-app-850">
            <PanelHeader title="Run summary" />
            <div className="space-y-3 p-4">
              {[
                ["Target", effectiveTarget || "—"],
                ["Mode", skipLlm ? "Deterministic only" : "Full (LLM + browser)"],
                ["Scope enforcement", "Strict"],
                ["Authorization", authorized ? "Confirmed" : "Required"],
              ].map(([k, v]) => (
                <div key={k} className="flex items-start justify-between gap-3">
                  <span className="shrink-0 text-[9.5px] text-faint">{k}</span>
                  <span className="truncate text-right font-mono text-[10px] text-ink-soft">
                    {v}
                  </span>
                </div>
              ))}
            </div>

            <div className="border-t border-line p-4">
              <button
                className="btn-primary w-full !py-[9px]"
                onClick={handleStart}
                disabled={starting}
              >
                <Play size={13} />
                {starting ? "Starting…" : "Start test run"}
              </button>

              <div className="mt-3 space-y-2">
                {[
                  "Scope policy checked before the first request",
                  "Private/internal targets refused on public instances",
                  "One scan at a time per instance",
                ].map((label) => (
                  <div key={label} className="flex items-center gap-2">
                    <CheckCircle2 size={10} className="shrink-0 text-[#46a758]" />
                    <span className="text-[9.5px] text-muted">{label}</span>
                  </div>
                ))}
              </div>

              <p className="mt-2.5 text-[8.5px] leading-relaxed text-faint">
                Starting a run dispatches live requests to the target. Only test systems you own
                or have explicit written authorization to assess.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
