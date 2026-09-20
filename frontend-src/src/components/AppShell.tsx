import { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  PlayCircle,
  ListChecks,
  FolderSearch,
  FileBarChart2,
  Target,
  Library,
  Settings,
  ShieldCheck,
  ChevronDown,
  ChevronRight,
  Menu,
  X,
  Search,
  Bell,
  Plus,
  Cpu,
  LogOut,
} from "lucide-react";

import { useLiveState } from "../lib/useLive";
import { api } from "../lib/api";

interface NavItem {
  to: string;
  label: string;
  icon: React.ReactNode;
  badge?: string;
  end?: boolean;
}

function navGroups(
  running: boolean,
  findingCount: number
): { title: string; items: NavItem[] }[] {
  return [
    {
      title: "Operate",
      items: [
        { to: "/app", label: "Overview", icon: <LayoutDashboard size={15} />, end: true },
        {
          to: "/app/runs",
          label: "Runs",
          icon: <PlayCircle size={15} />,
          badge: running ? "live" : undefined,
        },
        { to: "/app/runs/new", label: "New test run", icon: <Plus size={15} /> },
      ],
    },
    {
      title: "Analyze",
      items: [
        {
          to: "/app/findings",
          label: "Findings",
          icon: <ListChecks size={15} />,
          badge: findingCount > 0 ? String(findingCount) : undefined,
        },
        { to: "/app/evidence", label: "Evidence", icon: <FolderSearch size={15} /> },
        { to: "/app/reports", label: "Reports", icon: <FileBarChart2 size={15} /> },
      ],
    },
    {
      title: "Configure",
      items: [
        { to: "/app/targets", label: "Targets", icon: <Target size={15} /> },
        { to: "/app/tests", label: "Test library", icon: <Library size={15} /> },
      ],
    },
  ];
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [workspaceOpen, setWorkspaceOpen] = useState(false);
  const location = useLocation();
  const live = useLiveState();
  const running = live.status === "running";
  const findingCount = (live.findings || []).length;

  const NAV_GROUPS = navGroups(running, findingCount);

  return (
    <div className="flex min-h-screen bg-app-900">
      {/* Sidebar — desktop */}
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-[228px] flex-col border-r border-line bg-app-880 lg:flex">
        <SidebarContent
          workspaceOpen={workspaceOpen}
          setWorkspaceOpen={setWorkspaceOpen}
          onNavigate={() => setDrawerOpen(false)}
          live={live}
          running={running}
          findingCount={findingCount}
        />
      </aside>

      {/* Sidebar — mobile drawer */}
      {drawerOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-black/60"
            onClick={() => setDrawerOpen(false)}
            aria-hidden
          />
          <aside className="absolute inset-y-0 left-0 flex w-[248px] flex-col border-r border-line bg-app-880">
            <button
              className="btn-icon absolute right-2 top-2"
              onClick={() => setDrawerOpen(false)}
              aria-label="Close navigation"
            >
              <X size={15} />
            </button>
            <SidebarContent
              workspaceOpen={workspaceOpen}
              setWorkspaceOpen={setWorkspaceOpen}
              onNavigate={() => setDrawerOpen(false)}
              live={live}
              running={running}
              findingCount={findingCount}
            />
          </aside>
        </div>
      ) : null}

      {/* Main */}
      <div className="flex min-w-0 flex-1 flex-col lg:pl-[228px]">
        <header className="sticky top-0 z-30 border-b border-line bg-app-900/95 backdrop-blur-[2px]">
          <div className="flex h-[52px] items-center gap-3 px-4 sm:px-6">
            <button
              className="btn-icon lg:hidden"
              onClick={() => setDrawerOpen(true)}
              aria-label="Open navigation"
            >
              <Menu size={16} />
            </button>

            <div className="flex min-w-0 items-center gap-2 text-[11px]">
              <span className="text-faint">Sentinel</span>
              <ChevronRight size={11} className="text-faint" />
              <span className="truncate font-medium text-ink-soft">
                {breadcrumbFor(location.pathname)}
              </span>
            </div>

            <div className="ml-auto flex items-center gap-2">
              <div className="relative hidden xl:block">
                <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-faint" />
                <input
                  className="field w-[228px] py-[6px] pl-8 text-[11px]"
                  placeholder="Search findings, runs, targets…"
                  aria-label="Search"
                />
                <kbd className="absolute right-2 top-1/2 -translate-y-1/2 rounded-[3px] border border-line px-1.5 py-[1px] font-mono text-[8.5px] text-faint">
                  ⌘K
                </kbd>
              </div>

              <div className="hidden items-center gap-1.5 rounded-[4px] border px-2 py-[5px] sm:flex"
                style={
                  running
                    ? { borderColor: "rgba(76,141,255,0.28)", backgroundColor: "rgba(76,141,255,0.09)" }
                    : { borderColor: "#22262c", backgroundColor: "transparent" }
                }
              >
                <span
                  className={`h-[5px] w-[5px] rounded-full ${running ? "bg-[#4c8dff] animate-pulse-dot" : "bg-[#4d555e]"}`}
                />
                <span
                  className="font-mono text-[8.5px] font-semibold uppercase tracking-[0.13em]"
                  style={{ color: running ? "#7fa9f0" : "#4d555e" }}
                >
                  {running ? "Run active" : "Idle"}
                </span>
              </div>

              <button className="btn-icon relative" aria-label="Notifications">
                <Bell size={14} />
                <span className="absolute right-[5px] top-[5px] h-[5px] w-[5px] rounded-full bg-[#e5484d]" />
              </button>

              <NavLink to="/app/runs/new" className="btn-primary !py-[6px] !text-[11px]">
                <Plus size={12} />
                <span className="hidden sm:inline">New run</span>
              </NavLink>
            </div>
          </div>
        </header>

        <main className="flex-1">{children}</main>

        <footer className="border-t border-line px-6 py-3">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[9px] text-faint">
            <span>Sentinel console · qaagent 0.1.0</span>
            <span>engine: deterministic probes + LLM loop</span>
            <span>browser: chromium (full scans)</span>
            <span className="ml-auto">authorized testing only · all activity is logged</span>
          </div>
        </footer>
      </div>
    </div>
  );
}

function SidebarContent({
  workspaceOpen,
  setWorkspaceOpen,
  onNavigate,
  live,
  running,
  findingCount,
}: {
  workspaceOpen: boolean;
  setWorkspaceOpen: (v: boolean) => void;
  onNavigate: () => void;
  live: ReturnType<typeof useLiveState>;
  running: boolean;
  findingCount: number;
}) {
  const [email, setEmail] = useState<string>("…");
  useEffect(() => {
    api
      .me()
      .then((m) => setEmail(m.email || "token session"))
      .catch(() => setEmail("…"));
  }, []);
  return (
    <>
      {/* Brand */}
      <div className="flex items-center gap-2.5 border-b border-line px-4 py-[13px]">
        <span className="flex h-[28px] w-[28px] shrink-0 items-center justify-center rounded-[5px] border border-line-strong bg-app-800">
          <ShieldCheck size={15} className="text-ink" />
        </span>
        <div className="min-w-0">
          <div className="truncate text-[12.5px] font-semibold leading-tight tracking-[-0.01em] text-ink">
            Sentinel
          </div>
          <div className="font-mono text-[8.5px] uppercase tracking-[0.14em] text-faint">
            Security console
          </div>
        </div>
      </div>

      {/* Workspace selector */}
      <div className="relative border-b border-line px-3 py-2.5">
        <button
          className="flex w-full items-center gap-2 rounded-[5px] border border-line bg-app-850 px-2.5 py-2 text-left transition-colors hover:border-line-strong hover:bg-app-800"
          onClick={() => setWorkspaceOpen(!workspaceOpen)}
          aria-expanded={workspaceOpen}
        >
          <span className="flex h-[22px] w-[22px] items-center justify-center rounded-[4px] border border-line-strong bg-app-750 font-mono text-[9px] font-semibold text-ink-soft">
            SE
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[10.5px] font-medium text-ink-soft">
              Sentinel
            </span>
            <span className="block truncate font-mono text-[8.5px] text-faint">
              default workspace
            </span>
          </span>
          <ChevronDown
            size={12}
            className="shrink-0 text-faint transition-transform"
            style={{ transform: workspaceOpen ? "rotate(180deg)" : "none" }}
          />
        </button>

        {workspaceOpen ? (
          <div className="absolute inset-x-3 top-[62px] z-50 overflow-hidden rounded-[5px] border border-line-strong bg-app-800 shadow-[0_8px_24px_rgba(0,0,0,0.45)]">
            {[ "Default workspace"].map((w, i) => (
              <button
                key={w}
                className="flex w-full items-center gap-2 px-2.5 py-2 text-left text-[10.5px] transition-colors hover:bg-app-750"
                style={{ color: i === 0 ? "#e8ebee" : "#98a1ab" }}
                onClick={() => setWorkspaceOpen(false)}
              >
                {i === 0 ? (
                  <span className="h-[5px] w-[5px] rounded-full bg-[#4c8dff]" />
                ) : (
                  <span className="h-[5px] w-[5px] rounded-full bg-transparent" />
                )}
                {w}
              </button>
            ))}
          </div>
        ) : null}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-2.5 py-3">
        {navGroups(running, findingCount).map((group) => (
          <div key={group.title} className="mb-4">
            <div className="px-2.5 pb-1.5 text-[8.5px] font-semibold uppercase tracking-[0.15em] text-faint">
              {group.title}
            </div>
            <div className="space-y-[2px]">
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  onClick={onNavigate}
                  className={({ isActive }) =>
                    `group flex items-center gap-2.5 rounded-[5px] px-2.5 py-[7px] text-[11.5px] transition-colors ${
                      isActive
                        ? "bg-app-750 font-medium text-ink"
                        : "text-muted hover:bg-app-850 hover:text-ink-soft"
                    }`
                  }
                >
                  {({ isActive }) => (
                    <>
                      <span
                        className="shrink-0 transition-colors"
                        style={{ color: isActive ? "#4c8dff" : "#6b747e" }}
                      >
                        {item.icon}
                      </span>
                      <span className="flex-1 truncate">{item.label}</span>
                      {item.badge ? (
                        <span
                          className="rounded-[3px] border px-1.5 py-[1px] font-mono text-[8px]"
                          style={{
                            color: isActive ? "#7fa9f0" : "#6b747e",
                            borderColor: isActive ? "rgba(76,141,255,0.3)" : "#22262c",
                          }}
                        >
                          {item.badge}
                        </span>
                      ) : null}
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* Agent status */}
      <div className="border-t border-line px-3 py-3">
        <div className="rounded-[5px] border border-line bg-app-850 p-2.5">
          <div className="flex items-center gap-2">
            <Cpu size={12} className="text-[#4c8dff]" />
            <span className="text-[9px] font-semibold uppercase tracking-[0.13em] text-dim">
              Agent status
            </span>
            <span className="ml-auto flex items-center gap-1">
              <span className="h-[5px] w-[5px] rounded-full bg-[#46a758]" />
              <span className="font-mono text-[8px] uppercase tracking-[0.12em] text-[#66c07a]">
                Active
              </span>
            </span>
          </div>

          <div className="mt-2.5 space-y-1.5">
            {[
              ["Mode", live.status === "running" ? "scanning" : live.status || "idle"],
              ["Current stage", live.stage || "—"],
              ["Findings", String(findingCount)],
            ].map(([k, v]) => (
              <div key={k} className="flex items-center justify-between">
                <span className="text-[9px] text-faint">{k}</span>
                <span className="font-mono text-[8.5px] text-muted">{v}</span>
              </div>
            ))}
          </div>

          <div className="mt-2.5 h-[3px] w-full overflow-hidden rounded-full bg-app-750">
            <div
              className="h-full rounded-full bg-[#4c8dff]"
              style={{
                width:
                  live.max_steps && live.max_steps > 0
                    ? `${Math.min(100, ((live.step ?? 0) / live.max_steps) * 100)}%`
                    : running
                      ? "100%"
                      : "0%",
              }}
            />
          </div>
          <div className="mt-1 font-mono text-[8px] text-faint">
            {live.max_steps && live.max_steps > 0
              ? `step ${live.step ?? 0} of ${live.max_steps}`
              : running
                ? "deterministic probes running"
                : "no active run"}
          </div>
        </div>
      </div>

      {/* Settings + profile */}
      <div className="border-t border-line px-2.5 py-2.5">
        <NavLink
          to="/app/settings"
          onClick={onNavigate}
          className={({ isActive }) =>
            `flex items-center gap-2.5 rounded-[5px] px-2.5 py-[7px] text-[11.5px] transition-colors ${
              isActive ? "bg-app-750 text-ink" : "text-muted hover:bg-app-850 hover:text-ink-soft"
            }`
          }
        >
          <Settings size={14} className="shrink-0 text-dim" />
          Settings
        </NavLink>

          <button
            onClick={() => api.logout()}
            title="Sign out"
            className="mt-1 flex w-full items-center gap-2.5 rounded-[5px] px-2.5 py-[7px] text-left transition-colors hover:bg-app-850"
          >
          <span className="flex h-[22px] w-[22px] items-center justify-center rounded-full border border-line-strong bg-app-750 font-mono text-[8.5px] font-semibold text-ink-soft">
            {(email || "?").slice(0, 2).toUpperCase()}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[10.5px] font-medium text-ink-soft">{email}</span>
            <span className="block truncate font-mono text-[8px] text-faint">
              sentinel account
            </span>
          </span>
          <LogOut size={12} className="shrink-0 text-faint" />
        </button>
      </div>
    </>
  );
}

function breadcrumbFor(pathname: string): string {
  const map: Record<string, string> = {
    "/app": "Overview",
    "/app/runs": "Runs",
    "/app/runs/new": "New test run",
    "/app/findings": "Findings",
    "/app/evidence": "Evidence",
    "/app/reports": "Reports",
    "/app/targets": "Targets",
    "/app/tests": "Test library",
    "/app/settings": "Settings",
  };
  if (map[pathname]) return map[pathname];
  if (pathname.startsWith("/app/findings/")) return `Findings · ${pathname.split("/").pop()}`;
  return "Workspace";
}
