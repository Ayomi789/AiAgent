import { useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  RotateCw,
  Lock,
  ChevronDown,
  Crosshair,
  Maximize2,
  CircleDot,
  MousePointer2,
} from "lucide-react";

type View = "rendered" | "dom" | "console" | "network";

const VIEWS: { id: View; label: string }[] = [
  { id: "rendered", label: "Rendered" },
  { id: "dom", label: "DOM" },
  { id: "console", label: "Console" },
  { id: "network", label: "Network" },
];

const domSnapshot = `<body class="theme-dark">
  <div id="app-root">
    <header class="top-nav">
      <a class="brand" href="/">Example Platform</a>
      <nav class="primary-nav">
        <a href="/products">Products</a>
        <a href="/docs">Documentation</a>
        <a href="/pricing">Pricing</a>
      </nav>
      <button class="account-menu" aria-expanded="false">Account</button>
    </header>

    <main id="search-results" class="layout-main">
      <section class="search-panel">
        <form id="search-form" action="/search" method="GET">
          <label for="search-input" class="visually-hidden">Search</label>
          <input
            id="search-input"
            name="q"
            type="search"
            value="<script>/*probe*/</script>"
            autocomplete="off"
          />
          <button type="submit">Search</button>
        </form>
      </section>

      <header class="results-header">
        <h1 id="result-heading"><script>/*probe*/</script></h1>
        <p class="query-echo">Showing results for: <script>/*probe*/</script></p>
      </header>

      <ul class="result-list">
        <li class="result-item"><a href="/docs/getting-started">Getting started</a></li>
        <li class="result-item"><a href="/docs/authentication">Authentication</a></li>
        <li class="result-item"><a href="/docs/api">API reference</a></li>
      </ul>
    </main>
  </div>
</body>

<!-- agent markers -->
<!-- [observed] 142 nodes, 6 interactive controls -->
<!-- [observed] innerHTML sink: #result-heading (render-utils.js:64) -->
<!-- [observed] reflection points: 2 -->`;

const consoleLines = [
  { level: "info", time: "09:42:11.204", text: "application bootstrap complete" },
  { level: "info", time: "09:42:11.318", text: "route matched -> /search" },
  { level: "warn", time: "09:42:12.061", text: "third-party script blocked by CSP: cdn.metrics-collect.io" },
  { level: "error", time: "09:42:12.318", text: "uncaught SyntaxError: Unexpected token '<' (render-utils.js:64)" },
  { level: "info", time: "09:42:12.402", text: "GET /api/v1/search?q=%3Cscript%3E 200 (71ms)" },
  { level: "warn", time: "09:42:12.517", text: "innerHTML write detected on #result-heading" },
  { level: "info", time: "09:42:12.602", text: "render cycle complete (118ms)" },
];

const networkRows = [
  { method: "GET", path: "/search?q=%3Cscript%3E…", status: 200, type: "document", size: "18.4 kB", time: "112 ms" },
  { method: "GET", path: "/assets/app.bundle.js", status: 200, type: "script", size: "412 kB", time: "84 ms" },
  { method: "GET", path: "/assets/app.styles.css", status: 200, type: "stylesheet", size: "28.1 kB", time: "31 ms" },
  { method: "GET", path: "/api/v1/config", status: 200, type: "fetch", size: "1.2 kB", time: "38 ms" },
  { method: "GET", path: "/api/v1/search?q=%3Cscript%3E", status: 200, type: "fetch", size: "4.8 kB", time: "71 ms" },
  { method: "POST", path: "/api/v1/telemetry", status: 403, type: "fetch", size: "214 B", time: "19 ms" },
  { method: "GET", path: "/assets/logo.svg", status: 304, type: "image", size: "0.4 kB", time: "8 ms" },
];

export function BrowserPanel({
  url = "https://app.example.com/search?q=%3Cscript%3E",
  compact = false,
}: {
  url?: string;
  compact?: boolean;
}) {
  const [view, setView] = useState<View>("rendered");
  const [inspectMode, setInspectMode] = useState(true);

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-[6px] border border-line bg-app-880">
      {/* Toolbar */}
      <div className="flex items-center gap-2 border-b border-line bg-app-850 px-3 py-2">
        <div className="flex items-center gap-0.5">
          <button className="btn-icon" aria-label="Back" title="Back">
            <ArrowLeft size={14} />
          </button>
          <button className="btn-icon opacity-40" aria-label="Forward" title="Forward">
            <ArrowRight size={14} />
          </button>
          <button className="btn-icon" aria-label="Reload" title="Reload">
            <RotateCw size={13} />
          </button>
        </div>

        <div className="flex min-w-0 flex-1 items-center gap-2 rounded-[5px] border border-line-strong bg-app-900 px-2.5 py-[5px]">
          <Lock size={11} className="shrink-0 text-pass" />
          <span className="shrink-0 font-mono text-[9.5px] font-semibold uppercase tracking-wider text-dim">
            HTTPS
          </span>
          <div className="h-3 w-px shrink-0 bg-line-strong" />
          <span className="truncate font-mono text-[11px] text-ink-soft">{url}</span>
          <div className="ml-auto flex shrink-0 items-center gap-1.5">
            <span className="rounded-[3px] border border-active/30 bg-active/10 px-1.5 py-[1px] font-mono text-[8.5px] font-semibold uppercase tracking-wider text-[#7fa9f0]">
              GET
            </span>
            <ChevronDown size={11} className="text-faint" />
          </div>
        </div>

        <div className="flex items-center gap-1">
          <button
            className={`btn-icon ${inspectMode ? "border-active/40 bg-active/10 text-[#7fa9f0]" : ""}`}
            aria-label="Element inspector"
            title="Element inspector"
            onClick={() => setInspectMode((v) => !v)}
          >
            <Crosshair size={13} />
          </button>
          <button className="btn-icon" aria-label="Fullscreen" title="Fullscreen">
            <Maximize2 size={12} />
          </button>
        </div>
      </div>

      {/* Status strip */}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 border-b border-line bg-app-880 px-3 py-2">
        <StatusItem label="Page title" value="Search results for <script>/*probe*/</script>" />
        <StatusItem label="Viewport" value="1440 × 900 · DPR 1" mono />
        <StatusItem
          label="Interaction"
          value="Observing DOM mutations"
          accent="#7fa9f0"
          icon={<MousePointer2 size={10} />}
        />
        <StatusItem label="Console" value="2 warnings · 1 error" accent="#f0b95c" />
        <StatusItem label="Network" value="7 requests · 0 blocked by scope" accent="#66c07a" />
      </div>

      {/* View switcher */}
      <div className="flex items-center gap-0 border-b border-line bg-app-850 px-3">
        {VIEWS.map((v) => (
          <button
            key={v.id}
            onClick={() => setView(v.id)}
            className="relative px-3 py-2 text-[10.5px] font-semibold uppercase tracking-[0.08em] transition-colors"
            style={{
              color: view === v.id ? "#e8ebee" : "#6b747e",
            }}
          >
            {v.label}
            {view === v.id ? (
              <span className="absolute inset-x-2 -bottom-px h-[2px] rounded-full bg-[#4c8dff]" />
            ) : null}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-1.5 py-1">
          <CircleDot size={10} className="animate-pulse-dot text-[#4c8dff]" />
          <span className="font-mono text-[9.5px] uppercase tracking-[0.12em] text-dim">
            Live session
          </span>
        </div>
      </div>

      {/* Content */}
      <div className={`relative flex-1 overflow-auto bg-app-900 ${compact ? "" : "min-h-[320px]"}`}>
        {view === "rendered" ? (
          <RenderedPage inspectMode={inspectMode} />
        ) : null}

        {view === "dom" ? (
          <pre className="h-full overflow-auto p-4 font-mono text-[11px] leading-[1.75] text-[#9fb4c9]">
            {domSnapshot}
          </pre>
        ) : null}

        {view === "console" ? (
          <div className="divide-y divide-line-soft">
            {consoleLines.map((line, i) => (
              <div key={i} className="flex items-start gap-3 px-4 py-[7px] font-mono text-[11px]">
                <span className="shrink-0 text-faint">{line.time}</span>
                <span
                  className="shrink-0 uppercase"
                  style={{
                    color:
                      line.level === "error"
                        ? "#e5484d"
                        : line.level === "warn"
                          ? "#f5a623"
                          : "#6b747e",
                  }}
                >
                  {line.level}
                </span>
                <span className="text-[#9fb4c9]">{line.text}</span>
              </div>
            ))}
          </div>
        ) : null}

        {view === "network" ? (
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b border-line">
                {["Method", "Resource", "Status", "Type", "Size", "Time"].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-2 text-left text-[9.5px] font-semibold uppercase tracking-[0.1em] text-faint"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {networkRows.map((row, i) => (
                <tr key={i} className="border-b border-line-soft hover:bg-app-850">
                  <td className="px-4 py-[7px] font-mono text-[10.5px] text-[#7fa9f0]">{row.method}</td>
                  <td className="max-w-[280px] truncate px-4 py-[7px] font-mono text-[10.5px] text-ink-soft">
                    {row.path}
                  </td>
                  <td
                    className="px-4 py-[7px] font-mono text-[10.5px]"
                    style={{ color: row.status >= 400 ? "#e5484d" : row.status >= 300 ? "#f5a623" : "#66c07a" }}
                  >
                    {row.status}
                  </td>
                  <td className="px-4 py-[7px] text-[10.5px] text-dim">{row.type}</td>
                  <td className="px-4 py-[7px] font-mono text-[10.5px] text-dim">{row.size}</td>
                  <td className="px-4 py-[7px] font-mono text-[10.5px] text-dim">{row.time}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </div>

      {/* Footer */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line bg-app-850 px-3 py-1.5 font-mono text-[9.5px] text-faint">
        <span>session: sess_9f2c1a7e</span>
        <span>viewport: 1440×900</span>
        <span>ua: ATA-Headless/2.4</span>
        <span>tls: 1.3 · AES_256_GCM</span>
        <span className="ml-auto text-[#66c07a]">scope: enforced</span>
      </div>
    </div>
  );
}

function StatusItem({
  label,
  value,
  mono = false,
  accent,
  icon,
}: {
  label: string;
  value: string;
  mono?: boolean;
  accent?: string;
  icon?: React.ReactNode;
}) {
  return (
    <div className="flex items-baseline gap-1.5">
      <span className="text-[9px] font-semibold uppercase tracking-[0.11em] text-faint">{label}</span>
      <span
        className={`flex items-center gap-1 text-[10.5px] ${mono ? "font-mono" : ""}`}
        style={{ color: accent ?? "#98a1ab" }}
      >
        {icon}
        {value}
      </span>
    </div>
  );
}

function RenderedPage({ inspectMode }: { inspectMode: boolean }) {
  return (
    <div className="relative min-h-full bg-[#0c0e11] p-6">
      {/* Target application mock */}
      <div className="mx-auto max-w-[820px] overflow-hidden rounded-[6px] border border-[#22262c] bg-[#121417]">
        <div className="flex items-center gap-4 border-b border-[#22262c] px-5 py-3">
          <div className="text-[12px] font-semibold text-[#e8ebee]">Example Platform</div>
          <div className="flex items-center gap-3 text-[10.5px] text-[#6b747e]">
            <span>Products</span>
            <span>Documentation</span>
            <span>Pricing</span>
          </div>
          <div className="ml-auto rounded-[4px] border border-[#2c3138] px-2.5 py-1 text-[10px] text-[#98a1ab]">
            Account
          </div>
        </div>

        <div className="px-5 py-5">
          <div className="flex items-center gap-2">
            <div className="flex-1 rounded-[4px] border border-[#2c3138] bg-[#0e1013] px-3 py-2 font-mono text-[10.5px] text-[#c3c9d0]">
              &lt;script&gt;/*probe*/&lt;/script&gt;
            </div>
            <div className="rounded-[4px] bg-[#2f6bd8] px-3.5 py-2 text-[10.5px] font-medium text-white">
              Search
            </div>
          </div>

          <div className="mt-5">
            <div className="text-[15px] font-semibold text-[#e8ebee]">
              &lt;script&gt;/*probe*/&lt;/script&gt;
            </div>
            <div className="mt-1 text-[11px] text-[#6b747e]">
              Showing results for: &lt;script&gt;/*probe*/&lt;/script&gt;
            </div>
          </div>

          <div className="mt-4 divide-y divide-[#1c2025] border-t border-[#1c2025]">
            {[
              ["Getting started", "Updated 2 days ago"],
              ["Authentication", "Updated 6 days ago"],
              ["API reference", "Updated 2 weeks ago"],
            ].map(([title, meta], i) => (
              <div key={i} className="flex items-center justify-between py-2.5">
                <div className="text-[11.5px] text-[#7fa9f0]">{title}</div>
                <div className="text-[9.5px] text-[#4d555e]">{meta}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Agent inspection overlay */}
      {inspectMode ? (
        <div className="pointer-events-none absolute inset-x-6 top-[122px] mx-auto max-w-[820px]">
          <div className="relative">
            <div className="rounded-[4px] border-2 border-[#4c8dff]" style={{ height: 46 }} />
            <div className="absolute -top-[9px] left-0 rounded-[3px] bg-[#2f6bd8] px-2 py-[2px] font-mono text-[8.5px] font-semibold text-white">
              h1#result-heading · innerHTML sink
            </div>
            <div className="absolute -right-2 top-[52px] flex items-center gap-1.5 rounded-[3px] border border-[#2f6bd8]/40 bg-[#101c2e] px-2 py-1">
              <span className="h-1.5 w-1.5 rounded-full bg-[#4c8dff]" />
              <span className="font-mono text-[8.5px] text-[#7fa9f0]">
                mutation observed · 2 reflection points
              </span>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
