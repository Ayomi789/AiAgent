"""Dashboard web app: live run progress + final report.

Served by `qaagent dashboard` (default http://127.0.0.1:5050). Reads the live
state file the agent writes during a run and the latest report Markdown.
"""

from __future__ import annotations

import json
from pathlib import Path

from flask import Flask, jsonify

from qaagent.report.diff import compare_reports, load_report_files

_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>QA Agent Dashboard</title>
<style>
  :root { --bg:#0b0e15; --panel:rgba(255,255,255,.04); --line:rgba(255,255,255,.09); --text:#e9edf5; --muted:#8b94a8; --blue:#6c8cff; }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { font-family:"Segoe UI",system-ui,sans-serif; background:radial-gradient(1000px 500px at 50% -10%, rgba(108,140,255,.15), transparent 60%), var(--bg); color:var(--text); min-height:100vh; padding:28px 20px 60px; }
  .wrap { max-width:980px; margin:0 auto; }
  header { display:flex; align-items:baseline; justify-content:space-between; gap:16px; flex-wrap:wrap; margin-bottom:14px; }
  h1 { font-size:1.5rem; letter-spacing:.14em; }
  h1 span { color:var(--blue); }
  .status { font-size:.8rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; padding:6px 14px; border-radius:999px; border:1px solid var(--line); }
  .status.running { color:#4dd0e1; border-color:rgba(77,208,225,.5); }
  .status.completed { color:#69db7c; border-color:rgba(105,219,124,.5); }
  .status.error { color:#ff6b84; border-color:rgba(255,107,132,.5); }
  .status.idle { color:var(--muted); }
  .meta { color:var(--muted); font-size:.85rem; margin-bottom:20px; }
  .grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
  @media (max-width:800px){ .grid{ grid-template-columns:1fr; } }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:16px 18px; }
  .card h2 { font-size:.75rem; letter-spacing:.12em; text-transform:uppercase; color:var(--muted); margin-bottom:12px; }
  .stage { font-size:1.05rem; font-weight:600; }
  .pill { display:inline-block; padding:2px 8px; border-radius:6px; font-size:.72rem; font-weight:700; text-transform:uppercase; letter-spacing:.05em; margin-right:6px; }
  .sev-critical{ background:rgba(255,84,112,.16); color:#ff5470; }
  .sev-high{ background:rgba(255,143,61,.16); color:#ff8f3d; }
  .sev-medium{ background:rgba(255,209,102,.16); color:#ffd166; }
  .sev-low{ background:rgba(77,208,225,.16); color:#4dd0e1; }
  .sev-info{ background:rgba(139,148,168,.16); color:#8b94a8; }
  .counts { display:flex; gap:8px; flex-wrap:wrap; margin-top:10px; }
  .actions { list-style:none; }
  .actions li { font-size:.82rem; font-family:Consolas,monospace; color:var(--muted); padding:3px 0; border-bottom:1px dashed rgba(255,255,255,.05); }
  .actions li:first-child { color:var(--text); }
  .finding { border:1px solid var(--line); border-radius:10px; padding:10px 12px; margin-bottom:8px; background:rgba(255,255,255,.02); }
  .finding .title { font-size:.9rem; font-weight:600; }
  .finding .url { font-size:.75rem; color:var(--muted); margin-top:2px; word-break:break-all; }
  .finding .mime { font-size:.72rem; color:var(--blue); margin-top:3px; font-family:Consolas,monospace; }
  .finding .desc { font-size:.8rem; color:var(--muted); margin-top:6px; }
  #report { white-space:pre-wrap; font-family:Consolas,monospace; font-size:.8rem; color:var(--text); max-height:520px; overflow:auto; }
  .empty { color:var(--muted); font-size:.85rem; }
  .diff-group { margin-bottom:12px; }
  .diff-group h3 { font-size:.72rem; letter-spacing:.1em; text-transform:uppercase; margin-bottom:6px; }
  .tag-new { color:#ff8f3d; }
  .tag-fixed { color:#69db7c; }
  .tag-unchanged { color:var(--muted); }
  .diff-item { font-size:.8rem; padding:4px 0; border-bottom:1px dashed rgba(255,255,255,.05); }
  .diff-item .t { font-weight:600; }
  .diff-item .u { color:var(--muted); font-size:.72rem; word-break:break-all; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>QA<span>AGENT</span></h1>
    <div class="status" id="status">idle</div>
  </header>
  <div class="meta" id="meta">Waiting for a run...</div>
  <div class="grid">
    <div class="card">
      <h2>Stage</h2>
      <div class="stage" id="stage">-</div>
      <div class="counts" id="counts"></div>
    </div>
    <div class="card">
      <h2>Recent actions</h2>
      <ul class="actions" id="actions"><li class="empty">No actions yet</li></ul>
    </div>
  </div>
  <div class="card" style="margin-top:16px">
    <h2>Findings <span id="finding-count"></span></h2>
    <div id="findings"><div class="empty">No findings yet</div></div>
  </div>
  <div class="card" style="margin-top:16px">
    <h2>Findings diff vs previous run <span id="diff-count"></span></h2>
    <div id="diff"><div class="empty">Available once two runs have completed.</div></div>
  </div>
  <div class="card" style="margin-top:16px">
    <h2>Final report</h2>
    <div id="report" class="empty">Visible when the run completes.</div>
  </div>
</div>
<script>
function escapeHtml(t){ return String(t).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }
const $ = id => document.getElementById(id);
let lastStatus = "";
async function poll(){
  try {
    const r = await fetch("/api/state");
    const s = await r.json();
    $("status").textContent = s.status;
    $("status").className = "status " + s.status;
    $("stage").textContent = s.stage || "-";
    $("meta").textContent = "target: " + (s.target || "-") + "  |  elapsed: " + (s.elapsed_seconds ?? "-") + "s  |  step: " + (s.step ?? 0) + "/" + (s.max_steps ?? "-");
    const counts = {};
    (s.findings || []).forEach(f => counts[f.severity] = (counts[f.severity] || 0) + 1);
    $("counts").innerHTML = Object.entries(counts).map(([k, v]) =>
      '<span class="pill sev-' + k + '">' + k + ' ' + v + '</span>').join("") || '<span class="empty">0 findings</span>';
    const acts = (s.recent_actions || []).slice().reverse();
    $("actions").innerHTML = acts.map(a => "<li>" + escapeHtml(a) + "</li>").join("") || '<li class="empty">No actions yet</li>';
    const findings = s.findings || [];
    $("finding-count").textContent = "(" + findings.length + ")";
    $("findings").innerHTML = findings.map(f =>
      '<div class="finding"><span class="pill sev-' + f.severity + '">' + f.severity + '</span><span class="title">' + escapeHtml(f.title) + '</span>' +
      '<div class="url">' + escapeHtml(f.url || "") + '</div>' +
      (f.content_type ? '<div class="mime">Content-Type: ' + escapeHtml(f.content_type) + '</div>' : '') +
      '<div class="desc">' + escapeHtml((f.description || "").slice(0, 220)) + '</div></div>').join("") || '<div class="empty">No findings yet</div>';
    if (s.status === "completed" && lastStatus !== "completed") { lastStatus = "completed"; loadReport(); loadDiff(); }
    if (s.status !== "completed") lastStatus = s.status;
  } catch (e) { /* server restarting */ }
}
async function loadDiff(){
  try {
    const r = await fetch("/api/diff");
    const d = await r.json();
    const c = d.counts || {new:0, fixed:0, unchanged:0};
    $("diff-count").textContent = "(" + c.new + " new / " + c.fixed + " fixed / " + c.unchanged + " same)";
    if (!d.latest_run) { $("diff").innerHTML = '<div class="empty">No runs yet.</div>'; return; }
    const fmt = ts => String(ts||"-").slice(0,19).replace("T", " ");
    let html = '<div class="empty" style="margin-bottom:8px">latest: ' + fmt(d.latest_run) +
      (d.previous_run ? "  vs  " + fmt(d.previous_run) : "  (first recorded run)") + "</div>";
    const groups = [["New", d.new, "tag-new"], ["Fixed", d.fixed, "tag-fixed"], ["Unchanged", d.unchanged, "tag-unchanged"]];
    groups.forEach(function(g){
      var label = g[0], items = g[1] || [], cls = g[2];
      html += '<div class="diff-group"><h3 class="' + cls + '">' + label + " (" + items.length + ")</h3>";
      if (!items.length) html += '<div class="empty">none</div>';
      items.forEach(function(f){
        html += '<div class="diff-item"><span class="pill sev-' + f.severity + '">' + f.severity + '</span>' +
          '<span class="t">' + escapeHtml(f.title) + '</span> <span class="u">' + escapeHtml(f.url || "") + '</span></div>';
      });
      html += "</div>";
    });
    $("diff").innerHTML = html;
  } catch (e) {}
}
async function loadReport(){
  try {
    const r = await fetch("/api/report");
    const d = await r.json();
    $("report").textContent = d.markdown || "No report.";
    $("report").className = "";
  } catch (e) {}
}
poll();
loadDiff();
setInterval(poll, 1500);
</script>
</body>
</html>
"""


def create_app(state_path: Path, reports_dir: Path) -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index() -> str:
        return _PAGE

    @app.get("/api/state")
    def api_state():
        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            data = {
                "status": "idle",
                "stage": "No run yet",
                "target": "",
                "findings": [],
                "recent_actions": [],
                "step": 0,
                "max_steps": 0,
            }
        return jsonify(data)

    @app.get("/api/diff")
    def api_diff():
        """Compare the two most recent runs: new / fixed / unchanged findings."""
        reports = load_report_files(reports_dir)
        if not reports:
            return jsonify(
                {
                    "latest_run": None,
                    "previous_run": None,
                    "new": [],
                    "fixed": [],
                    "unchanged": [],
                    "counts": {"new": 0, "fixed": 0, "unchanged": 0},
                }
            )
        latest = reports[-1]
        previous = reports[-2] if len(reports) >= 2 else None
        diff = compare_reports(latest, previous)
        return jsonify(
            {
                "latest_run": diff.latest_run,
                "previous_run": diff.previous_run,
                "new": diff.new,
                "fixed": diff.fixed,
                "unchanged": diff.unchanged,
                "counts": diff.counts,
            }
        )

    @app.get("/api/report")
    def api_report():
        files = sorted(reports_dir.glob("report-*.md"))
        if not files:
            return jsonify(
                {"path": None, "json_path": None, "markdown": "No report yet."}
            )
        latest = files[-1]
        json_files = sorted(reports_dir.glob("report-*.json"))
        json_path = str(json_files[-1]) if json_files else None
        return jsonify(
            {
                "path": str(latest),
                "json_path": json_path,
                "markdown": latest.read_text(encoding="utf-8"),
            }
        )

    return app


def run_dashboard(state_path: Path, reports_dir: Path, port: int) -> None:
    """Serve the dashboard until interrupted."""
    create_app(state_path, reports_dir).run(
        host="127.0.0.1", port=port, debug=False, use_reloader=False
    )
