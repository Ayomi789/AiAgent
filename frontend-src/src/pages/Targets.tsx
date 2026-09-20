import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Globe, Plus } from "lucide-react";
import { PanelHeader, StatusBadge } from "../components/ui";
import { api, type ConfigEntry } from "../lib/api";
import { useHistory } from "../lib/useLive";

export function Targets() {
  const [configs, setConfigs] = useState<ConfigEntry[]>([]);
  const [loaded, setLoaded] = useState(false);
  const { runs } = useHistory();

  useEffect(() => {
    api
      .configs()
      .then((d) => setConfigs(d.configs || []))
      .catch(() => setConfigs([]))
      .finally(() => setLoaded(true));
  }, []);

  const lastRunFor = (target?: string | null) =>
    runs.find((r) => r.target === target)?.started_at?.slice(0, 16).replace("T", " ");

  return (
    <div className="px-4 py-5 sm:px-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-[18px] font-semibold tracking-[-0.012em] text-ink">Targets</h1>
          <p className="mt-1 max-w-[620px] text-[11.5px] leading-relaxed text-muted">
            Saved scan configs on this instance. Scope rules are enforced on every outbound
            request — the agent cannot leave the configured boundary.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link to="/app/runs/new" className="btn-primary">
            <Plus size={12} />
            Add target
          </Link>
        </div>
      </div>

      {/* Target list */}
      <div className="mt-4 overflow-hidden rounded-[6px] border border-line bg-app-850">
        <PanelHeader
          title="Saved configs"
          subtitle={
            loaded
              ? `${configs.length} config(s) on this instance`
              : "Loading configs…"
          }
          icon={<Globe size={13} />}
        />
        {configs.length ? (
          <div className="divide-y divide-line-soft">
            {configs.map((c) => (
              <div key={c.file} className="flex flex-wrap items-center gap-x-5 gap-y-2 px-4 py-3">
                <div className="min-w-0">
                  <div className="truncate font-mono text-[11.5px] text-ink">
                    {c.target || c.name}
                  </div>
                  <div className="mt-[3px] font-mono text-[9px] text-faint">
                    config: {c.name} · file: {c.file}
                  </div>
                </div>
                <div className="ml-auto flex items-center gap-3">
                  {lastRunFor(c.target) ? (
                    <span className="font-mono text-[9px] text-faint">
                      last run {lastRunFor(c.target)}
                    </span>
                  ) : (
                    <span className="font-mono text-[9px] text-faint">never scanned</span>
                  )}
                  <StatusBadge status={lastRunFor(c.target) ? "completed" : "queued"} />
                  <Link
                    to={`/app/runs/new`}
                    className="btn-secondary !py-[5px] !text-[10px]"
                  >
                    Scan
                  </Link>
                </div>
              </div>
            ))}
          </div>
        ) : loaded ? (
          <div className="px-6 py-12 text-center">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-soft">
              No saved targets
            </p>
            <p className="mx-auto mt-1.5 max-w-[380px] text-[11px] leading-relaxed text-dim">
              Enter a domain in New test run — Sentinel saves a scoped config for it automatically.
            </p>
            <Link to="/app/runs/new" className="btn-primary mx-auto mt-4">
              <Plus size={12} />
              Add your first target
            </Link>
          </div>
        ) : null}
      </div>

      <p className="mt-3 font-mono text-[9px] leading-relaxed text-faint">
        Configs live server-side and survive restarts on instances with persistent storage. Add
        credentials or extra sensitive-file names by editing the YAML directly.
      </p>
    </div>
  );
}
