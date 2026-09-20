import { useState } from "react";
import { Copy, Check, Camera, FileText, Braces, Terminal, Network, Code2 } from "lucide-react";
import type { Evidence } from "../lib/types";

type TabId = "screenshot" | "request" | "response" | "dom" | "console" | "network";

const TABS: { id: TabId; label: string; icon: React.ReactNode }[] = [
  { id: "screenshot", label: "Screenshot", icon: <Camera size={11} /> },
  { id: "request", label: "Request", icon: <FileText size={11} /> },
  { id: "response", label: "Response", icon: <FileText size={11} /> },
  { id: "dom", label: "DOM", icon: <Code2 size={11} /> },
  { id: "console", label: "Console", icon: <Terminal size={11} /> },
  { id: "network", label: "Network", icon: <Network size={11} /> },
];

function highlightLine(line: string, kind: "http" | "code"): React.ReactNode {
  const trimmed = line.trim();

  if (trimmed.startsWith("#") || trimmed.startsWith("//")) {
    return <span className="text-[#4d555e] italic">{line}</span>;
  }

  if (kind === "http") {
    const statusMatch = line.match(/^(HTTP\/[\d.]+)\s+(\d{3})\s*(.*)$/);
    if (statusMatch) {
      const code = Number(statusMatch[2]);
      const color = code >= 500 ? "#e5484d" : code >= 400 ? "#f76b15" : code >= 300 ? "#f5a623" : "#46a758";
      return (
        <span>
          <span className="text-[#7fa9f0]">{statusMatch[1]}</span>{" "}
          <span className="font-semibold" style={{ color }}>
            {statusMatch[2]}
          </span>{" "}
          <span className="text-[#98a1ab]">{statusMatch[3]}</span>
        </span>
      );
    }

    const methodMatch = line.match(/^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(\S+)\s*(.*)$/);
    if (methodMatch) {
      return (
        <span>
          <span className="font-semibold text-[#46a758]">{methodMatch[1]}</span>{" "}
          <span className="text-[#c3c9d0]">{methodMatch[2]}</span>{" "}
          <span className="text-[#6b747e]">{methodMatch[3]}</span>
        </span>
      );
    }

    const headerMatch = line.match(/^([a-zA-Z0-9-]+):\s*(.*)$/);
    if (headerMatch) {
      return (
        <span>
          <span className="text-[#8fa6c4]">{headerMatch[1]}:</span>{" "}
          <span className="text-[#b6bec7]">{headerMatch[2]}</span>
        </span>
      );
    }
  }

  const tagMatch = line.match(/(<\/?[a-zA-Z][\w-]*)/);
  if (tagMatch) {
    const parts = line.split(/(<\/?[a-zA-Z][\w-]*|>)/);
    return (
      <span>
        {parts.map((part, i) => {
          if (/^<\/?[a-zA-Z]/.test(part)) return <span key={i} className="text-[#7fa9f0]">{part}</span>;
          if (part === ">") return <span key={i} className="text-[#6b747e]">{part}</span>;
          return <span key={i} className="text-[#b6bec7]">{part}</span>;
        })}
      </span>
    );
  }

  return <span className="text-[#b6bec7]">{line}</span>;
}

function CodeBlock({ content, kind }: { content: string; kind: "http" | "code" }) {
  return (
    <div className="overflow-auto bg-app-900">
      <table className="w-full border-collapse">
        <tbody>
          {content.split("\n").map((line, i) => (
            <tr key={i} className="align-top">
              <td className="w-[38px] select-none border-r border-line-soft px-2 py-[1px] text-right font-mono text-[9.5px] leading-[1.75] text-[#2f353c]">
                {i + 1}
              </td>
              <td className="whitespace-pre px-3 py-[1px] font-mono text-[10.5px] leading-[1.75]">
                {highlightLine(line, kind)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function EvidenceViewer({ evidence, findingId }: { evidence: Evidence; findingId: string }) {
  const [tab, setTab] = useState<TabId>("request");
  const [copied, setCopied] = useState(false);

  const activeContent =
    tab === "request"
      ? evidence.request
      : tab === "response"
        ? evidence.response
        : tab === "dom"
          ? evidence.dom
          : tab === "console"
            ? evidence.console
            : "";

  const handleCopy = async () => {
    if (!activeContent) return;
    try {
      await navigator.clipboard.writeText(activeContent);
    } catch {
      /* clipboard unavailable in preview iframe */
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  };

  return (
    <div className="flex flex-col overflow-hidden rounded-[6px] border border-line bg-app-850">
      {/* Tabs */}
      <div className="flex flex-wrap items-center gap-0 border-b border-line bg-app-880 px-1.5">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className="relative flex items-center gap-1.5 px-3 py-2.5 text-[10px] font-semibold uppercase tracking-[0.09em] transition-colors"
            style={{ color: tab === t.id ? "#e8ebee" : "#6b747e" }}
          >
            <span style={{ color: tab === t.id ? "#4c8dff" : "#4d555e" }}>{t.icon}</span>
            {t.label}
            {tab === t.id ? (
              <span className="absolute inset-x-2 -bottom-px h-[2px] rounded-full bg-[#4c8dff]" />
            ) : null}
          </button>
        ))}

        <div className="ml-auto flex items-center gap-2 px-2">
          <span className="hidden font-mono text-[9px] text-faint sm:inline">
            {findingId.toLowerCase()}_{tab}.txt
          </span>
          {activeContent ? (
            <button className="btn-icon" title="Copy to clipboard" onClick={handleCopy}>
              {copied ? <Check size={12} className="text-pass" /> : <Copy size={11} />}
            </button>
          ) : null}
        </div>
      </div>

      {/* Metadata strip */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-line bg-app-880 px-3 py-1.5 font-mono text-[9px] text-faint">
        <span>captured: 2026-09-19 09:42:19.412 UTC</span>
        <span>sha256: 3f9c8a71…b21e</span>
        <span>tool: ata-browser/2.4</span>
        <span>verified: yes</span>
        <span className="ml-auto text-[#66c07a]">integrity: intact</span>
      </div>

      {/* Body */}
      <div className="min-h-[280px]">
        {tab === "screenshot" ? <ScreenshotEvidence /> : null}
        {tab === "network" ? <NetworkEvidence entries={evidence.network} /> : null}
        {activeContent && tab !== "screenshot" && tab !== "network" ? (
          <CodeBlock content={activeContent} kind={tab === "console" || tab === "dom" ? "code" : "http"} />
        ) : null}
      </div>

      <div className="flex items-center gap-3 border-t border-line bg-app-880 px-3 py-1.5 font-mono text-[9px] text-faint">
        <span className="flex items-center gap-1.5">
          <Braces size={10} />
          evidence bundle v3 · immutable
        </span>
        <span className="ml-auto">chain of custody: 4 entries</span>
      </div>
    </div>
  );
}

function NetworkEvidence({
  entries,
}: {
  entries: { method: string; path: string; status: number; type: string; size: string; time: string; state: string }[];
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        <thead>
          <tr className="border-b border-line">
            {["#", "Method", "Resource", "Status", "Type", "Size", "Time", "State"].map((h) => (
              <th
                key={h}
                className="px-3 py-2 text-left text-[9px] font-semibold uppercase tracking-[0.11em] text-faint"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {entries.map((e, i) => (
            <tr key={i} className="border-b border-line-soft transition-colors hover:bg-app-800">
              <td className="px-3 py-[7px] font-mono text-[9.5px] text-faint">{i + 1}</td>
              <td className="px-3 py-[7px] font-mono text-[10px] font-medium text-[#7fa9f0]">{e.method}</td>
              <td className="max-w-[340px] truncate px-3 py-[7px] font-mono text-[10px] text-ink-soft">
                {e.path}
              </td>
              <td
                className="px-3 py-[7px] font-mono text-[10px]"
                style={{ color: e.status >= 400 ? "#e5484d" : e.status >= 300 ? "#f5a623" : "#66c07a" }}
              >
                {e.status}
              </td>
              <td className="px-3 py-[7px] text-[10px] text-dim">{e.type}</td>
              <td className="px-3 py-[7px] font-mono text-[10px] text-dim">{e.size}</td>
              <td className="px-3 py-[7px] font-mono text-[10px] text-dim">{e.time}</td>
              <td className="px-3 py-[7px]">
                <span
                  className="rounded-[3px] border px-1.5 py-[1px] font-mono text-[8.5px] uppercase tracking-wider"
                  style={{
                    color: e.state === "ok" ? "#66c07a" : e.state === "blocked" ? "#f5a623" : e.state === "error" ? "#e5484d" : "#98a1ab",
                    borderColor: e.state === "ok" ? "rgba(70,167,88,0.3)" : e.state === "blocked" ? "rgba(245,166,35,0.3)" : e.state === "error" ? "rgba(229,72,77,0.3)" : "rgba(125,135,148,0.26)",
                    backgroundColor: e.state === "ok" ? "rgba(70,167,88,0.08)" : e.state === "blocked" ? "rgba(245,166,35,0.08)" : e.state === "error" ? "rgba(229,72,77,0.08)" : "rgba(125,135,148,0.08)",
                  }}
                >
                  {e.state}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ScreenshotEvidence() {
  return (
    <div className="bg-app-900 p-5">
      <div className="mx-auto max-w-[720px] overflow-hidden rounded-[5px] border border-line-strong">
        {/* Browser chrome */}
        <div className="flex items-center gap-2 border-b border-line-strong bg-app-800 px-3 py-2">
          <div className="flex gap-1.5">
            <span className="h-[7px] w-[7px] rounded-full bg-[#2c3138]" />
            <span className="h-[7px] w-[7px] rounded-full bg-[#2c3138]" />
            <span className="h-[7px] w-[7px] rounded-full bg-[#2c3138]" />
          </div>
          <div className="ml-2 flex-1 truncate rounded-[3px] border border-line bg-app-900 px-2 py-[3px] font-mono text-[8.5px] text-dim">
            https://app.example.com/search?q=%3Cscript%3E
          </div>
          <span className="font-mono text-[8px] uppercase tracking-[0.12em] text-[#66c07a]">
            captured
          </span>
        </div>

        {/* Page content */}
        <div className="relative bg-[#0c0e11] p-5">
          <div className="flex items-center gap-3 border-b border-[#1c2025] pb-3">
            <div className="text-[10.5px] font-semibold text-[#e8ebee]">Example Platform</div>
            <div className="flex gap-2.5 text-[8.5px] text-[#4d555e]">
              <span>Products</span>
              <span>Documentation</span>
              <span>Pricing</span>
            </div>
          </div>

          <div className="mt-4 rounded-[4px] border border-[#2c3138] bg-[#0e1013] px-3 py-2 font-mono text-[9px] text-[#c3c9d0]">
            &lt;script&gt;/*probe*/&lt;/script&gt;
          </div>

          <div className="relative mt-4">
            <div className="rounded-[3px] border-2 border-[#e5484d] px-2 py-1">
              <div className="text-[11px] font-semibold text-[#e8ebee]">
                &lt;script&gt;/*probe*/&lt;/script&gt;
              </div>
            </div>
            <div className="absolute -top-[9px] right-0 rounded-[3px] bg-[#a83237] px-1.5 py-[1px] font-mono text-[7.5px] font-semibold text-white">
              annotation 1 · unencoded reflection
            </div>
          </div>

          <div className="mt-2 text-[9px] text-[#6b747e]">
            Showing results for: &lt;script&gt;/*probe*/&lt;/script&gt;
          </div>

          <div className="mt-4 space-y-2 border-t border-[#1c2025] pt-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex items-center justify-between">
                <div className="h-[7px] w-[140px] rounded-[2px] bg-[#1c2025]" />
                <div className="h-[6px] w-[52px] rounded-[2px] bg-[#16191d]" />
              </div>
            ))}
          </div>
        </div>

        {/* Footer metadata */}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line-strong bg-app-800 px-3 py-1.5 font-mono text-[8px] text-faint">
          <span>viewport 1440×900</span>
          <span>full page: false</span>
          <span>annotations: 1</span>
          <span>format: png</span>
          <span className="ml-auto">sha256 9d2c…41af</span>
        </div>
      </div>
    </div>
  );
}
