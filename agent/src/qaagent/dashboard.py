"""Dashboard web app: live run progress + final report.

Served by `qaagent dashboard` (default http://127.0.0.1:5050). Reads the live
state file the agent writes during a run and the latest report Markdown.
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, redirect, request, session, url_for

from qaagent.auth import (
    RateLimiter,
    UserStore,
    csrf_token,
    csrf_valid,
    current_user,
    login_user,
    logout_user,
)
from qaagent.report.diff import compare_reports, load_report_files

# Single-flight scan state: one agent run at a time, started from the UI.
_scan = {
    "proc": None,
    "config": None,
    "skip_llm": False,
    "started": None,
    "log_path": None,
    "returncode": None,
    "owner_id": None,
    "owner_email": None,
}

_COOKIE = "sentinel_token"

_LOGIN_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sentinel - Sign in</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: "Segoe UI", system-ui, sans-serif; background: #07080b; color: #e8edf4;
         min-height: 100vh; display: grid; place-items: center; padding: 20px; }}
  .card {{ width: 100%; max-width: 380px; background: #10131a; border: 1px solid rgba(232,237,244,0.1);
          border-radius: 14px; padding: 28px; box-shadow: 0 24px 60px -28px rgba(0,0,0,0.72); }}
  .brand {{ display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }}
  .mark {{ width: 34px; height: 34px; border-radius: 9px; background: #0e1218;
          border: 1px solid rgba(46,230,166,0.28); display: grid; place-items: center; }}
  h1 {{ font-size: 17px; letter-spacing: 0.14em; text-transform: uppercase; font-weight: 650; }}
  .sub {{ color: #8b93a7; font-size: 12.5px; margin: 10px 0 20px; line-height: 1.5; }}
  label {{ display: block; font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase;
          color: #5a6276; font-weight: 600; margin: 12px 0 6px; }}
  input[type=email], input[type=password] {{ width: 100%; height: 38px; background: #161b24;
          border: 1px solid rgba(232,237,244,0.12); border-radius: 8px; color: #e8edf4;
          padding: 0 12px; font-size: 14px; }}
  input:focus {{ outline: 1px solid rgba(46,230,166,0.4); border-color: rgba(46,230,166,0.35); }}
  button {{ width: 100%; height: 40px; margin-top: 18px; border-radius: 8px; cursor: pointer;
           border: 1px solid rgba(46,230,166,0.35); color: #2ee6a6; font-weight: 700;
           background: linear-gradient(180deg, rgba(46,230,166,0.16), rgba(46,230,166,0.08));
           font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase;
           font-family: inherit; }}
  button:hover {{ background: rgba(46,230,166,0.22); }}
  .alt {{ text-align: center; margin-top: 16px; font-size: 12.5px; color: #8b93a7; }}
  .alt a {{ color: #2ee6a6; text-decoration: none; }}
  .flash {{ background: rgba(255,59,92,0.1); border: 1px solid rgba(255,59,92,0.35); color: #ff3b5c;
           border-radius: 8px; padding: 9px 12px; font-size: 12.5px; margin-bottom: 6px; }}
  .flash-ok {{ background: rgba(46,230,166,0.08); border: 1px solid rgba(46,230,166,0.35); color: #2ee6a6; }}
  .tokenline {{ margin-top: 18px; padding-top: 14px; border-top: 1px solid rgba(232,237,244,0.08);
               font-size: 12px; color: #8b93a7; text-align: center; }}
  .tokenline a {{ color: #4d9fff; text-decoration: none; }}
</style>
</head>
<body>
  <div class="card">
    <div class="brand">
      <div class="mark"><svg width="18" height="18" viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="7.2" stroke="#2ee6a6" stroke-opacity="0.35"/><circle cx="10" cy="10" r="4.2" stroke="#2ee6a6" stroke-opacity="0.55"/><path d="M10 4.6V10l4.2 2.3" stroke="#2ee6a6" stroke-width="1.4" stroke-linecap="round"/><circle cx="10" cy="10" r="1.3" fill="#2ee6a6"/></svg></div>
      <h1>Sentinel</h1>
    </div>
    <p class="sub">{subtitle}</p>
    {flash}
    <form method="post" action="{action}">
      <input type="hidden" name="csrf_token" value="{csrf}">
      <label for="email">Email</label>
      <input id="email" name="email" type="email" required autocomplete="email" autofocus>
      <label for="password">Password</label>
      <input id="password" name="password" type="password" required minlength="8" autocomplete="{autocomplete}">
      <button type="submit">{button_label}</button>
    </form>
    <div class="alt">{alt}</div>
    <div class="tokenline">Running locally? <a href="/token-login?token={token}">Continue with access token →</a></div>
  </div>
</body>
</html>"""


def load_or_create_token(reports_dir: Path) -> str:
    """Load the dashboard auth token, creating one on first start.

    Stored inside the (gitignored) reports dir so restarts keep the same
    token and the secret never lands in git.
    """
    token_path = Path(reports_dir) / ".dashboard-token"
    if token_path.exists():
        token = token_path.read_text(encoding="utf-8").strip()
        if token:
            return token
    token = secrets.token_urlsafe(24)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(token, encoding="utf-8")
    return token

_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Sentinel - Live QA</title>
  <link rel='icon' type='image/svg+xml' href='data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="7.2" stroke="%232ee6a6" stroke-opacity="0.35"/><circle cx="10" cy="10" r="4.2" stroke="%232ee6a6" stroke-opacity="0.55"/><path d="M10 4.6V10l4.2 2.3" stroke="%232ee6a6" stroke-width="1.4" stroke-linecap="round"/><circle cx="10" cy="10" r="1.3" fill="%232ee6a6"/></svg>' />
  <style>
    :root {
      --bg: #07080b;
      --bg-elev: #0b0d12;
      --surface: #10131a;
      --surface-2: #161b24;
      --surface-3: #1c2230;
      --line: rgba(232, 237, 244, 0.06);
      --line-2: rgba(232, 237, 244, 0.1);
      --text: #e8edf4;
      --muted: #8b93a7;
      --faint: #5a6276;
      --mint: #2ee6a6;
      --mint-2: #1bbf88;
      --crit: #ff3b5c;
      --high: #ff7a2f;
      --med: #e8b84a;
      --low: #4d9fff;
      --info: #8b93a7;
      --ok: #2ee6a6;
      --fixed: #6ea8ff;
      --shadow: 0 24px 60px -28px rgba(0, 0, 0, 0.72);
      --radius: 12px;
      --font: "Segoe UI", "Helvetica Neue", ui-sans-serif, system-ui, sans-serif;
      --mono: "SFMono-Regular", "Cascadia Mono", "Consolas", "Liberation Mono", ui-monospace, monospace;
      --stripe: #2ee6a6;
    }

    * { box-sizing: border-box; }
    html, body { margin: 0; padding: 0; }
    html { color-scheme: dark; }

    body {
      min-height: 100vh;
      font-family: var(--font);
      background: var(--bg);
      color: var(--text);
      -webkit-font-smoothing: antialiased;
      text-rendering: optimizeLegibility;
    }

    body::before {
      content: "";
      position: fixed;
      inset: 0 auto 0 0;
      width: 3px;
      background: var(--stripe);
      box-shadow: 0 0 18px color-mix(in srgb, var(--stripe) 55%, transparent);
      z-index: 40;
      transition: background 0.4s ease, box-shadow 0.4s ease;
    }

    body.is-idle { --stripe: #5a6276; }
    body.is-running { --stripe: #2ee6a6; }
    body.is-completed { --stripe: #4d9fff; }
    body.is-error { --stripe: #ff3b5c; }

    .scanline {
      display: none;
      position: fixed;
      left: 0;
      right: 0;
      height: 120px;
      pointer-events: none;
      z-index: 3;
      background: linear-gradient(180deg, transparent, rgba(46,230,166,0.045), transparent);
      animation: scan 4.8s linear infinite;
    }

    body.is-running .scanline { display: block; }

    body::after {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(255,255,255,0.015) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.015) 1px, transparent 1px);
      background-size: 48px 48px;
      mask-image: radial-gradient(ellipse at 50% 0%, #000 20%, transparent 75%);
      z-index: 0;
    }

    .app {
      position: relative;
      z-index: 1;
      max-width: 1440px;
      margin: 0 auto;
      padding: 18px 22px 40px;
    }

    .top {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 4px 2px 14px;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }

    .mark {
      width: 36px;
      height: 36px;
      flex: 0 0 36px;
      border-radius: 10px;
      background:
        radial-gradient(circle at 30% 25%, rgba(46,230,166,0.22), transparent 55%),
        #0e1218;
      border: 1px solid rgba(46,230,166,0.28);
      display: grid;
      place-items: center;
      box-shadow: 0 0 0 1px rgba(46,230,166,0.06), 0 8px 24px -12px rgba(46,230,166,0.45);
    }

    .wordmark {
      font-size: 15px;
      font-weight: 650;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      line-height: 1.1;
    }

    .tagline {
      margin-top: 3px;
      font-size: 11px;
      color: var(--muted);
      letter-spacing: 0.04em;
    }

    .top-right {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }

    .live-pill {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      height: 28px;
      padding: 0 10px;
      border-radius: 999px;
      border: 1px solid var(--line-2);
      background: var(--surface);
      color: var(--muted);
      font-size: 10px;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      font-family: var(--mono);
    }

    .live-pill .dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--faint);
      box-shadow: 0 0 0 3px rgba(90,98,118,0.18);
    }

    body.is-running .live-pill {
      color: var(--mint);
      border-color: rgba(46,230,166,0.28);
      background: rgba(46,230,166,0.06);
    }

    body.is-running .live-pill .dot {
      background: var(--mint);
      box-shadow: 0 0 0 3px rgba(46,230,166,0.16);
      animation: pulse 1.4s ease-in-out infinite;
    }

    #status {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      height: 28px;
      padding: 0 11px;
      border-radius: 999px;
      border: 1px solid var(--line-2);
      background: var(--surface);
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      font-family: var(--mono);
      color: var(--muted);
    }

    #status[data-state="idle"] { color: var(--muted); }
    #status[data-state="running"] {
      color: var(--mint);
      border-color: rgba(46,230,166,0.3);
      background: rgba(46,230,166,0.08);
    }
    #status[data-state="completed"] {
      color: var(--low);
      border-color: rgba(77,159,255,0.3);
      background: rgba(77,159,255,0.08);
    }
    #status[data-state="error"] {
      color: var(--crit);
      border-color: rgba(255,59,92,0.35);
      background: rgba(255,59,92,0.08);
    }

    #status .sdot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: currentColor;
    }

    body.is-running #status .sdot { animation: pulse 1.4s ease-in-out infinite; }

    .progress-wrap {
      position: relative;
      height: 3px;
      border-radius: 99px;
      background: rgba(255,255,255,0.04);
      overflow: hidden;
      margin-bottom: 14px;
    }

    .runbar {
      display: flex;
      align-items: center;
      gap: 14px;
      flex-wrap: wrap;
      background: linear-gradient(180deg, rgba(255,255,255,0.02), transparent 40%), var(--surface);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 10px 14px;
      margin-bottom: 14px;
    }

    .runfield { display: flex; flex-direction: column; gap: 5px; min-width: 240px; flex: 0 1 340px; }

    #run-config {
      height: 32px;
      background: var(--surface-2);
      color: var(--text);
      border: 1px solid var(--line-2);
      border-radius: 8px;
      padding: 0 10px;
      font-family: var(--mono);
      font-size: 12px;
    }

    #run-config::placeholder { color: var(--faint); }
    #run-config:focus { outline: 1px solid rgba(46,230,166,0.4); border-color: rgba(46,230,166,0.35); }

    .runtoggle { display: inline-flex; align-items: center; gap: 8px; cursor: pointer; user-select: none; margin-top: 14px; }
    .runtoggle input { display: none; }
    .runtoggle .tg {
      width: 30px; height: 17px; border-radius: 99px;
      background: var(--surface-3); border: 1px solid var(--line-2);
      position: relative; transition: background .2s, border-color .2s;
    }
    .runtoggle .tg::after {
      content: ""; position: absolute; top: 2px; left: 2px;
      width: 11px; height: 11px; border-radius: 50%;
      background: var(--muted); transition: transform .2s, background .2s;
    }
    .runtoggle input:checked + .tg { background: rgba(46,230,166,0.18); border-color: rgba(46,230,166,0.4); }
    .runtoggle input:checked + .tg::after { transform: translateX(13px); background: var(--mint); }
    .runtoggle .tlabel { font-family: var(--mono); font-size: 11px; color: var(--muted); letter-spacing: 0.06em; }

    #run-btn {
      appearance: none;
      height: 34px;
      margin-top: 14px;
      padding: 0 18px;
      border-radius: 8px;
      border: 1px solid rgba(46,230,166,0.35);
      background: linear-gradient(180deg, rgba(46,230,166,0.16), rgba(46,230,166,0.08));
      color: var(--mint);
      font-family: var(--mono);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      cursor: pointer;
      transition: background .15s, border-color .15s, color .15s, opacity .15s;
    }

    #run-btn:hover:not(:disabled) { background: rgba(46,230,166,0.22); border-color: rgba(46,230,166,0.55); }
    #run-btn:disabled { opacity: 0.45; cursor: not-allowed; }
    #run-btn.running {
      border-color: rgba(255,59,92,0.4);
      background: rgba(255,59,92,0.1);
      color: var(--crit);
    }

    .runstate {
      flex: 1;
      min-width: 200px;
      font-family: var(--mono);
      font-size: 11px;
      color: var(--muted);
      text-align: right;
      word-break: break-all;
      margin-top: 16px;
    }
    .runstate.ok { color: var(--mint); }
    .runstate.err { color: var(--crit); }

    #progress-fill {
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, var(--mint-2), var(--mint));
      box-shadow: 0 0 12px rgba(46,230,166,0.45);
      transition: width 0.6s cubic-bezier(.22,1,.36,1);
    }

    body.is-running .progress-wrap::after {
      content: "";
      position: absolute;
      inset: 0 auto 0 0;
      width: 28%;
      background: linear-gradient(90deg, transparent, rgba(255,255,255,0.35), transparent);
      animation: sweep 2.2s linear infinite;
    }

    .command {
      display: grid;
      grid-template-columns: 1.4fr 0.9fr 1.1fr;
      gap: 12px;
      margin-bottom: 14px;
    }

    .tile {
      position: relative;
      background: linear-gradient(180deg, rgba(255,255,255,0.02), transparent 40%), var(--surface);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      min-width: 0;
    }

    .tile::before {
      content: "";
      position: absolute;
      inset: 8px;
      pointer-events: none;
      opacity: 0.22;
      background:
        linear-gradient(var(--mint), var(--mint)) top left / 9px 1px no-repeat,
        linear-gradient(var(--mint), var(--mint)) top left / 1px 9px no-repeat,
        linear-gradient(var(--mint), var(--mint)) top right / 9px 1px no-repeat,
        linear-gradient(var(--mint), var(--mint)) top right / 1px 9px no-repeat,
        linear-gradient(var(--mint), var(--mint)) bottom left / 9px 1px no-repeat,
        linear-gradient(var(--mint), var(--mint)) bottom left / 1px 9px no-repeat,
        linear-gradient(var(--mint), var(--mint)) bottom right / 9px 1px no-repeat,
        linear-gradient(var(--mint), var(--mint)) bottom right / 1px 9px no-repeat;
    }

    #meta, #stage, #counts {
      padding: 14px 16px 13px;
    }

    .k {
      display: block;
      font-size: 10px;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: var(--faint);
      font-weight: 600;
      margin-bottom: 7px;
    }

    .v {
      font-family: var(--mono);
      font-size: 13px;
      color: var(--text);
      word-break: break-all;
      line-height: 1.4;
    }

    .meta-row {
      display: grid;
      grid-template-columns: 1fr auto auto;
      gap: 16px;
      align-items: end;
    }

    .meta-cell { min-width: 0; }

    .num {
      font-variant-numeric: tabular-nums;
      font-family: var(--mono);
      font-size: 20px;
      letter-spacing: -0.03em;
      line-height: 1.1;
    }

    .num span { color: var(--faint); font-size: 13px; }

    .stage-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }

    .stage-name {
      font-family: var(--mono);
      font-size: 15px;
      color: var(--mint);
      letter-spacing: 0.04em;
    }

    body:not(.is-running) .stage-name { color: var(--text); }

    .step-rail {
      display: flex;
      gap: 3px;
      margin-top: 10px;
    }

    .tick {
      flex: 1;
      height: 4px;
      border-radius: 99px;
      background: rgba(255,255,255,0.06);
    }

    .tick.on { background: rgba(46,230,166,0.55); }
    .tick.cur {
      background: var(--mint);
      box-shadow: 0 0 8px rgba(46,230,166,0.55);
    }

    .sev-meter {
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 8px;
    }

    .sev {
      min-width: 0;
    }

    .sev b {
      display: block;
      font-family: var(--mono);
      font-size: 18px;
      font-variant-numeric: tabular-nums;
      line-height: 1;
      margin-bottom: 4px;
    }

    .sev em {
      font-style: normal;
      font-size: 10px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--faint);
    }

    .sev.critical b { color: var(--crit); }
    .sev.high b { color: var(--high); }
    .sev.medium b { color: var(--med); }
    .sev.low b { color: var(--low); }
    .sev.info b { color: var(--info); }

    .grid {
      display: grid;
      grid-template-columns: minmax(0, 1.35fr) minmax(280px, 0.9fr);
      grid-template-areas:
        "findings diff"
        "findings actions"
        "report report";
      gap: 12px;
    }

    .findings-panel { grid-area: findings; }
    .diff-panel { grid-area: diff; }
    .actions-panel { grid-area: actions; }
    .report-panel { grid-area: report; }

    .panel {
      position: relative;
      background: linear-gradient(180deg, rgba(255,255,255,0.018), transparent 28%), var(--surface);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      min-width: 0;
      display: flex;
      flex-direction: column;
    }

    body.is-running .findings-panel {
      border-color: rgba(46,230,166,0.16);
      box-shadow: var(--shadow), 0 0 0 1px rgba(46,230,166,0.05) inset;
    }

    .panel-head {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      min-height: 48px;
    }

    .panel-head h2 {
      margin: 0;
      font-size: 11px;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      font-weight: 650;
      color: var(--muted);
    }

    .chip {
      font-family: var(--mono);
      font-size: 10px;
      letter-spacing: 0.08em;
      padding: 3px 7px;
      border-radius: 999px;
      border: 1px solid var(--line-2);
      color: var(--muted);
      background: rgba(255,255,255,0.02);
    }

    #finding-count, #diff-count { }

    .filters {
      margin-left: auto;
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
      justify-content: flex-end;
    }

    .filters button {
      appearance: none;
      border: 1px solid var(--line);
      background: transparent;
      color: var(--muted);
      font-family: var(--mono);
      font-size: 10px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      padding: 4px 7px;
      border-radius: 7px;
      cursor: pointer;
      transition: background .15s, border-color .15s, color .15s;
    }

    .filters button:hover { border-color: var(--line-2); color: var(--text); }
    .filters button.on {
      background: rgba(46,230,166,0.1);
      border-color: rgba(46,230,166,0.28);
      color: var(--mint);
    }

    .filters button.on.critical { background: rgba(255,59,92,0.1); border-color: rgba(255,59,92,0.3); color: var(--crit); }
    .filters button.on.high { background: rgba(255,122,47,0.1); border-color: rgba(255,122,47,0.3); color: var(--high); }
    .filters button.on.medium { background: rgba(232,184,74,0.1); border-color: rgba(232,184,74,0.3); color: var(--med); }
    .filters button.on.low { background: rgba(77,159,255,0.1); border-color: rgba(77,159,255,0.3); color: var(--low); }
    .filters button.on.info { background: rgba(139,147,167,0.1); border-color: rgba(139,147,167,0.3); color: var(--info); }

    #findings, #diff, #actions {
      padding: 10px;
      overflow: auto;
    }

    #findings { max-height: 760px; }
    #diff { max-height: 340px; }
    #actions { max-height: 360px; }

    .group {
      margin-bottom: 8px;
    }

    .group-h {
      position: sticky;
      top: 0;
      z-index: 2;
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 6px 6px 7px;
      background: color-mix(in srgb, var(--surface) 92%, transparent);
      backdrop-filter: blur(8px);
      font-size: 10px;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--muted);
      font-weight: 650;
    }

    .group-h .n {
      font-family: var(--mono);
      color: var(--faint);
      letter-spacing: 0;
    }

    .card {
      position: relative;
      background: var(--surface-2);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 11px 12px 11px 14px;
      margin-bottom: 7px;
      overflow: hidden;
    }

    .card::before {
      content: "";
      position: absolute;
      left: 0; top: 0; bottom: 0;
      width: 3px;
      background: var(--sev, var(--faint));
    }

    .card.critical { --sev: var(--crit); }
    .card.high { --sev: var(--high); }
    .card.medium { --sev: var(--med); }
    .card.low { --sev: var(--low); }
    .card.info { --sev: var(--info); }

    .card.enter {
      animation: enter .45s cubic-bezier(.22,1,.36,1);
    }

    .card-top {
      display: flex;
      align-items: flex-start;
      gap: 8px;
    }

    .glyph {
      flex: 0 0 auto;
      width: 16px;
      height: 16px;
      margin-top: 1px;
      color: var(--sev);
    }

    .card h3 {
      margin: 0;
      font-size: 13.5px;
      font-weight: 600;
      letter-spacing: -0.01em;
      line-height: 1.35;
      flex: 1;
    }

    .sev-badge {
      flex: 0 0 auto;
      font-family: var(--mono);
      font-size: 9px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      padding: 3px 6px;
      border-radius: 5px;
      color: var(--sev);
      background: color-mix(in srgb, var(--sev) 12%, transparent);
      border: 1px solid color-mix(in srgb, var(--sev) 28%, transparent);
    }

    .url {
      display: block;
      margin: 7px 0 0 24px;
      font-family: var(--mono);
      font-size: 11.5px;
      color: var(--low);
      word-break: break-all;
      text-decoration: none;
    }

    .url:hover { text-decoration: underline; }

    .meta-line {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin: 8px 0 0 24px;
    }

    .pill {
      font-family: var(--mono);
      font-size: 10px;
      color: var(--muted);
      background: rgba(255,255,255,0.03);
      border: 1px solid var(--line);
      padding: 2px 6px;
      border-radius: 5px;
    }

    .desc {
      margin: 8px 0 0 24px;
      font-size: 12.5px;
      line-height: 1.5;
      color: var(--muted);
    }

    .empty {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      text-align: center;
      gap: 8px;
      padding: 36px 18px;
      color: var(--muted);
    }

    .empty .icon {
      width: 36px;
      height: 36px;
      border-radius: 10px;
      display: grid;
      place-items: center;
      border: 1px solid var(--line-2);
      background: var(--surface-2);
      color: var(--faint);
    }

    .empty strong {
      display: block;
      color: var(--text);
      font-size: 13px;
      font-weight: 600;
    }

    .empty p {
      margin: 0;
      font-size: 12px;
      color: var(--faint);
      max-width: 280px;
      line-height: 1.5;
    }

    .diff-group { margin-bottom: 10px; }

    .diff-h {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 4px 4px 8px;
      font-size: 10px;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      font-weight: 650;
    }

    .diff-h.new { color: var(--mint); }
    .diff-h.fixed { color: var(--fixed); }
    .diff-h.unchanged { color: var(--muted); }

    .diff-item {
      display: grid;
      grid-template-columns: 16px 1fr auto;
      gap: 8px;
      align-items: start;
      padding: 8px 8px;
      border-radius: 8px;
      border: 1px solid var(--line);
      background: var(--surface-2);
      margin-bottom: 6px;
    }

    .diff-item .t {
      font-size: 12.5px;
      font-weight: 550;
      line-height: 1.35;
    }

    .diff-item .u {
      display: block;
      margin-top: 3px;
      font-family: var(--mono);
      font-size: 10.5px;
      color: var(--faint);
      word-break: break-all;
    }

    .log-row {
      display: grid;
      grid-template-columns: 64px 1fr;
      gap: 10px;
      padding: 7px 6px;
      border-bottom: 1px solid var(--line);
      font-size: 12px;
    }

    .log-row:last-child { border-bottom: 0; }

    .log-row .t {
      font-family: var(--mono);
      font-size: 10px;
      color: var(--faint);
      letter-spacing: 0.04em;
      padding-top: 2px;
    }

    .log-row .tx {
      color: var(--text);
      line-height: 1.45;
    }

    body.is-running #actions .log-row:last-child .tx {
      color: var(--mint);
    }

    #report {
      margin: 0;
      padding: 16px 18px 20px;
      font-family: var(--mono);
      font-size: 12px;
      line-height: 1.65;
      white-space: pre-wrap;
      word-break: break-word;
      color: #c6cdd8;
      max-height: 420px;
      overflow: auto;
      background:
        linear-gradient(90deg, rgba(46,230,166,0.05) 0, transparent 12px),
        var(--bg-elev);
      border-radius: 0 0 var(--radius) var(--radius);
    }

    #report:empty + .report-empty,
    #report.empty {
      display: none;
    }

    .foot {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
      margin-top: 16px;
      padding: 0 4px;
      color: var(--faint);
      font-size: 11px;
      letter-spacing: 0.04em;
    }

    .foot span { font-family: var(--mono); }

    .user-chip {{
      display: inline-flex; align-items: center; gap: 9px;
      height: 34px; padding: 0 6px 0 7px; border-radius: 999px;
      border: 1px solid var(--line-2);
      background: linear-gradient(180deg, var(--surface-2), var(--surface));
      box-shadow: inset 0 1px 0 rgba(232, 237, 244, 0.04);
      transition: border-color .18s ease, box-shadow .18s ease;
    }}
    .user-chip:hover {{
      border-color: rgba(46, 230, 166, 0.28);
      box-shadow: inset 0 1px 0 rgba(232, 237, 244, 0.04), 0 0 0 3px rgba(46, 230, 166, 0.05);
    }}
    .user-chip .avatar {{
      width: 22px; height: 22px; border-radius: 50%; flex: none;
      display: inline-flex; align-items: center; justify-content: center;
      font-family: var(--mono); font-size: 10px; font-weight: 700;
      color: var(--mint); text-transform: uppercase;
      background: radial-gradient(circle at 30% 30%, rgba(46,230,166,0.28), rgba(46,230,166,0.07));
      border: 1px solid rgba(46, 230, 166, 0.35);
    }}
    .user-chip .u {{
      font-size: 11px; color: var(--text); font-family: var(--mono);
      max-width: 210px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }}
    .user-chip .role {{
      flex: none; font-size: 8.5px; letter-spacing: 0.14em; text-transform: uppercase;
      font-family: var(--mono); color: var(--mint);
      border: 1px solid rgba(46, 230, 166, 0.35); background: rgba(46, 230, 166, 0.08);
      padding: 2.5px 8px; border-radius: 999px;
    }}
    .user-chip form {{ display: inline-flex; margin: 0; }}
    .user-chip button {{
      appearance: none; display: inline-flex; align-items: center; gap: 6px;
      height: 22px; padding: 0 11px; border-radius: 999px; cursor: pointer;
      border: 1px solid var(--line-2); background: transparent;
      color: var(--muted); font-family: var(--mono); font-size: 9.5px;
      letter-spacing: 0.1em; text-transform: uppercase;
      transition: color .16s ease, border-color .16s ease, background .16s ease,
                  box-shadow .16s ease, transform .1s ease;
    }}
    .user-chip button svg {{ opacity: 0.75; flex: none; transition: opacity .16s ease; }}
    .user-chip button:hover {{
      color: #ff5c76; border-color: rgba(255, 59, 92, 0.45);
      background: rgba(255, 59, 92, 0.09);
      box-shadow: 0 0 0 3px rgba(255, 59, 92, 0.07);
    }}
    .user-chip button:hover svg {{ opacity: 1; }}
    .user-chip button:active {{ transform: translateY(1px) scale(0.98); }}
    .user-chip button:focus-visible {{
      outline: 2px solid rgba(255, 59, 92, 0.5); outline-offset: 2px;
    }}

    @media (max-width: 640px) {{
      .user-chip {{ height: 30px; gap: 7px; }}
      .user-chip .u, .user-chip .role {{ display: none; }}
    }}

    @keyframes scan {
      0% { top: -140px; }
      100% { top: 110%; }
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.45; transform: scale(0.82); }
    }

    @keyframes sweep {
      0% { transform: translateX(-40%); }
      100% { transform: translateX(380%); }
    }

    @keyframes enter {
      from { opacity: 0; transform: translateY(6px); }
      to { opacity: 1; transform: none; }
    }

    @keyframes tickpop {
      from { transform: translateY(4px); opacity: 0.4; }
      to { transform: none; opacity: 1; }
    }

    .pop { animation: tickpop .35s ease; }

    @media (max-width: 980px) {
      .runbar { gap: 10px; }
      .runstate { text-align: left; width: 100%; margin-top: 0; }
      .command { grid-template-columns: 1fr; }
      .grid {
        grid-template-columns: 1fr;
        grid-template-areas:
          "findings"
          "diff"
          "actions"
          "report";
      }
      #findings, #diff, #actions, #report { max-height: 420px; }
      .meta-row { grid-template-columns: 1fr; gap: 10px; }
    }

    @media (max-width: 560px) {
      .app { padding: 12px 12px 28px; }
      .top { align-items: flex-start; flex-direction: column; }
      .sev-meter { grid-template-columns: repeat(5, minmax(0,1fr)); gap: 4px; }
      .sev b { font-size: 15px; }
      .filters { width: 100%; margin-left: 0; }
      .panel-head { flex-wrap: wrap; }
      .url, .desc, .meta-line { margin-left: 0; }
      .card-top { flex-wrap: wrap; }
    }

    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after {
        animation: none !important;
        transition: none !important;
      }
    }
  </style>
  
  
</head>
<body class="is-idle">
  <div class="scanline" aria-hidden="true"></div>
  <div class="app">
    <header class="top">
      <div class="brand">
        <div class="mark" aria-hidden="true">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <circle cx="10" cy="10" r="7.2" stroke="#2ee6a6" stroke-opacity="0.35"/>
            <circle cx="10" cy="10" r="4.2" stroke="#2ee6a6" stroke-opacity="0.55"/>
            <path d="M10 4.6V10l4.2 2.3" stroke="#2ee6a6" stroke-width="1.4" stroke-linecap="round"/>
            <circle cx="10" cy="10" r="1.3" fill="#2ee6a6"/>
          </svg>
        </div>
        <div>
          <div class="wordmark">Sentinel</div>
          <div class="tagline">Website security-testing agent</div>
        </div>
      </div>
      <div class="top-right">
        <div class="live-pill" id="live-pill"><span class="dot"></span><span id="live-label">Standby</span></div>
        <div id="status" data-state="idle">Idle</div>
        {user_chip}
      </div>
    </header>

    <div class="progress-wrap" id="progress-track"><div id="progress-fill"></div></div>

    <section class="runbar" id="runbar">
      <div class="runfield">
        <span class="k">Target - pick a config or type a new site</span>
        <input id="run-config" list="config-list" placeholder="example.com or config name" spellcheck="false" autocomplete="off" />
        <datalist id="config-list"></datalist>
      </div>
      <label class="runtoggle" title="Deterministic probes only - no LLM calls, no browser. Fast and quota-free.">
        <input type="checkbox" id="run-skipllm" />
        <span class="tg"></span>
        <span class="tlabel">skip LLM</span>
      </label>
      <button id="run-btn" type="button">Run scan</button>
      <div class="runstate" id="run-state"></div>
    </section>

    <section class="command">
      <div class="tile" id="meta">
        <div class="meta-row">
          <div class="meta-cell"><span class="k">Target</span><span class="v">-</span></div>
          <div class="meta-cell"><span class="k">Elapsed</span><div class="num">00:00</div></div>
          <div class="meta-cell"><span class="k">Step</span><div class="num">0<span>/25</span></div></div>
        </div>
      </div>
      <div class="tile" id="stage">
        <span class="k">Stage</span>
        <div class="stage-row"><div class="stage-name">connecting</div></div>
      </div>
      <div class="tile" id="counts">
        <span class="k">Severity mix</span>
        <div class="sev-meter">
          <div class="sev critical"><b>0</b><em>CRIT</em></div>
          <div class="sev high"><b>0</b><em>HIGH</em></div>
          <div class="sev medium"><b>0</b><em>MED</em></div>
          <div class="sev low"><b>0</b><em>LOW</em></div>
          <div class="sev info"><b>0</b><em>INFO</em></div>
        </div>
      </div>
    </section>

    <main class="grid">
      <section class="panel findings-panel">
        <div class="panel-head">
          <h2>Live findings</h2>
          <span class="chip" id="finding-count">0</span>
          <div class="filters" id="finding-filters"></div>
        </div>
        <div id="findings"></div>
      </section>

      <section class="panel diff-panel">
        <div class="panel-head">
          <h2>Diff vs previous</h2>
          <span class="chip" id="diff-count">-</span>
        </div>
        <div id="diff"></div>
      </section>

      <section class="panel actions-panel">
        <div class="panel-head">
          <h2>Agent log</h2>
        </div>
        <div id="actions"></div>
      </section>

      <section class="panel report-panel">
        <div class="panel-head">
          <h2>Final report</h2>
        </div>
        <div id="report"></div>
      </section>
    </main>

    <footer class="foot">
      <span>SENTINEL / QA MONITOR</span>
      <span id="source-label">polling /api · 1.5s</span>
    </footer>
  </div>

  <script>
    (function () {
      "use strict";

      var POLL_MS = 1500;
      var TARGET_DEFAULT = "https://shop.northstar-labs.com";
      var MAX_STEPS = 25;
      var CYCLE_MS = 120000;
      var IDLE_MS = 6000;
      var RUN_MS = 90000;
      var SEV_ORDER = ["critical", "high", "medium", "low", "info"];
      var SEV_LABEL = { critical: "Critical", high: "High", medium: "Medium", low: "Low", info: "Info" };
      var SEV_SHORT = { critical: "CRIT", high: "HIGH", medium: "MED", low: "LOW", info: "INFO" };

      function simulate() {
        return {
          state: { status: "idle", stage: "idle", target: "", elapsed_seconds: 0, step: 0, max_steps: MAX_STEPS, findings: [], recent_actions: [] },
          diff: null,
          report: { markdown: "" }
        };
      }

      var $ = function (id) { return document.getElementById(id); };
      var els = {
        status: $("status"),
        meta: $("meta"),
        stage: $("stage"),
        counts: $("counts"),
        actions: $("actions"),
        findings: $("findings"),
        findingCount: $("finding-count"),
        diff: $("diff"),
        diffCount: $("diff-count"),
        report: $("report"),
        progress: $("progress-fill"),
        liveLabel: $("live-label"),
        source: $("source-label"),
        filters: $("finding-filters")
      };

      var scanPolling = false;
      var scanRunning = false;

      function setRunState(msg, cls) {
        var el = document.getElementById("run-state");
        if (!el) return;
        el.textContent = msg || "";
        el.className = "runstate" + (cls ? " " + cls : "");
      }

      function setRunBtn() {
        var btn = document.getElementById("run-btn");
        if (!btn) return;
        if (scanRunning) {
          btn.textContent = "Scan running…";
          btn.disabled = true;
          btn.classList.add("running");
        } else {
          btn.textContent = "Run scan";
          btn.disabled = false;
          btn.classList.remove("running");
        }
      }

      async function loadConfigs() {
        try {
          var res = await fetch("/api/configs", { cache: "no-store" });
          if (!res.ok) return;
          var data = await res.json();
          var dl = document.getElementById("config-list");
          if (!dl || !data.configs || !data.configs.length) return;
          dl.innerHTML = data.configs.map(function (c) {
            return '<option value="' + esc(c.name) + '">' + esc(c.target || "") + "</option>";
          }).join("");
        } catch (e) { /* controls stay empty; CLI still works */ }
      }

      function pollScanStatus() {
        if (scanPolling) return;
        scanPolling = true;
        fetch("/api/scan/status", { cache: "no-store" })
          .then(function (r) { return r.ok ? r.json() : null; })
          .then(function (s) {
            scanPolling = false;
            if (!s) return;
            var wasRunning = scanRunning;
            scanRunning = !!s.running;
            if (scanRunning) {
              var lines = s.log_tail || [];
              var last = lines.length ? lines[lines.length - 1] : "starting…";
              setRunState((s.config || "") + (s.skip_llm ? " (skip-llm)" : "") + " · " + last);
            } else if (wasRunning && s.returncode != null) {
              var ok = s.returncode === 0;
              setRunState("scan finished · exit " + s.returncode, ok ? "ok" : "err");
            }
            if (wasRunning !== scanRunning) setRunBtn();
          })
          .catch(function () { scanPolling = false; });
      }

      async function startScan() {
        var sel = document.getElementById("run-config");
        var skip = document.getElementById("run-skipllm");
        var cfg = sel ? sel.value : "";
        if (!cfg) { setRunState("no config selected", "err"); return; }
        try {
          var res = await fetch("/api/scan", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ config: cfg, skip_llm: !!(skip && skip.checked) }),
          });
          var data = await res.json();
          if (!res.ok) {
            setRunState(data.error || "failed to start", "err");
            return;
          }
          scanRunning = true;
          setRunBtn();
          var note = data.created ? "config created · " : "";
          setRunState(
            note + (data.config || cfg) + (data.skip_llm ? " (skip-llm)" : "") + " · starting…"
          );
          pollScanStatus();
        } catch (e) {
          setRunState("failed to reach dashboard API", "err");
        }
      }

      var filterSev = "all";
      var seenFindings = {};
      var lastStatus = "";
      var lastStage = "";
      var lastFindingSig = "";
      var lastDiffSig = "";
      var lastActionSig = "";
      var lastReport = null;
      var lastCounts = "";
      var usingSim = false;

      function esc(s) {
        return String(s == null ? "" : s)
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;");
      }

      function glyph(sev) {
        if (sev === "critical") {
          return '<svg class="glyph" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M8 1.6 14.4 13H1.6L8 1.6Z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/><path d="M8 6.2v3.2M8 11.4h.01" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>';
        }
        if (sev === "high") {
          return '<svg class="glyph" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M8 2.2 13.8 8 8 13.8 2.2 8 8 2.2Z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/><path d="M8 5.4v3.1M8 10.5h.01" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>';
        }
        if (sev === "medium") {
          return '<svg class="glyph" viewBox="0 0 16 16" fill="none" aria-hidden="true"><rect x="2.2" y="2.2" width="11.6" height="11.6" rx="1.4" stroke="currentColor" stroke-width="1.4"/><path d="M8 5.2v3.2M8 10.6h.01" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>';
        }
        if (sev === "low") {
          return '<svg class="glyph" viewBox="0 0 16 16" fill="none" aria-hidden="true"><circle cx="8" cy="8" r="5.6" stroke="currentColor" stroke-width="1.4"/><path d="M5.6 8.2 7.2 9.8l3.4-3.6" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>';
        }
        return '<svg class="glyph" viewBox="0 0 16 16" fill="none" aria-hidden="true"><circle cx="8" cy="8" r="5.6" stroke="currentColor" stroke-width="1.4"/><path d="M8 7.2v4M8 5.2h.01" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>';
      }

      function formatElapsed(sec) {
        sec = Math.max(0, Math.floor(Number(sec) || 0));
        var m = Math.floor(sec / 60);
        var s = sec % 60;
        return String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
      }

      function countBySev(list) {
        var c = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
        (list || []).forEach(function (f) {
          var k = String(f.severity || "info").toLowerCase();
          if (c[k] == null) c.info++;
          else c[k]++;
        });
        return c;
      }

      function setStatus(status) {
        var s = String(status || "idle").toLowerCase();
        if (["idle", "running", "completed", "error"].indexOf(s) === -1) s = "idle";
        els.status.setAttribute("data-state", s);
        els.status.innerHTML = '<span class="sdot"></span>' + esc(s);
        document.body.classList.remove("is-idle", "is-running", "is-completed", "is-error");
        document.body.classList.add("is-" + s);
        if (s === "running") els.liveLabel.textContent = "Live scan";
        else if (s === "completed") els.liveLabel.textContent = "Sealed";
        else if (s === "error") els.liveLabel.textContent = "Fault";
        else els.liveLabel.textContent = "Standby";
        if (s !== lastStatus) {
          els.status.classList.remove("pop");
          void els.status.offsetWidth;
          els.status.classList.add("pop");
          if (s === "running" && lastStatus && lastStatus !== "running") {
            seenFindings = {};
            lastFindingSig = "";
            lastDiffSig = "";
            lastActionSig = "";
            lastReport = null;
          }
          lastStatus = s;
        }
      }

      function renderMeta(state) {
        var target = state.target || "-";
        var elapsed = formatElapsed(state.elapsed_seconds);
        var step = Number(state.step) || 0;
        var max = Number(state.max_steps) || MAX_STEPS;
        els.meta.innerHTML =
          '<div class="meta-row">' +
            '<div class="meta-cell"><span class="k">Target</span><span class="v">' + esc(target) + "</span></div>" +
            '<div class="meta-cell"><span class="k">Elapsed</span><div class="num">' + esc(elapsed) + "</div></div>" +
            '<div class="meta-cell"><span class="k">Step</span><div class="num">' + step + "<span>/" + max + "</span></div></div>" +
          "</div>";
      }

      function renderStage(state) {
        var stage = state.stage || "idle";
        var step = Number(state.step) || 0;
        var max = Number(state.max_steps) || MAX_STEPS;
        var ticks = "";
        for (var i = 1; i <= max; i++) {
          var cls = "tick";
          if (i < step) cls += " on";
          else if (i === step && state.status === "running") cls += " cur";
          else if (i <= step && state.status !== "idle") cls += " on";
          ticks += '<i class="' + cls + '"></i>';
        }
        var changed = stage !== lastStage;
        lastStage = stage;
        els.stage.innerHTML =
          '<span class="k">Stage</span>' +
          '<div class="stage-row"><div class="stage-name' + (changed ? " pop" : "") + '">' + esc(stage) + "</div></div>" +
          '<div class="step-rail" aria-hidden="true">' + ticks + "</div>";
        var pct = 0;
        if (state.status === "completed") pct = 100;
        else if (state.status === "running") pct = Math.max(2, Math.min(100, (step / max) * 100));
        else if (state.status === "idle") pct = 0;
        else pct = Math.min(100, (step / max) * 100);
        els.progress.style.width = pct + "%";
      }

      function renderCounts(findings) {
        var c = countBySev(findings);
        var html = '<span class="k">Severity mix</span><div class="sev-meter">';
        SEV_ORDER.forEach(function (k) {
          html += '<div class="sev ' + k + '"><b>' + c[k] + "</b><em>" + SEV_SHORT[k] + "</em></div>";
        });
        html += "</div>";
        var sig = SEV_ORDER.map(function (k) { return c[k]; }).join(",");
        if (sig !== lastCounts) {
          els.counts.innerHTML = html;
          lastCounts = sig;
        } else if (!els.counts.innerHTML) {
          els.counts.innerHTML = html;
        }
      }

      function renderFilters(findings) {
        var c = countBySev(findings);
        var total = (findings || []).length;
        var bits = [{ id: "all", label: "All", n: total, cls: "" }].concat(
          SEV_ORDER.map(function (k) { return { id: k, label: SEV_SHORT[k], n: c[k], cls: k }; })
        );
        els.filters.innerHTML = bits.map(function (b) {
          var on = filterSev === b.id ? " on" : "";
          return '<button type="button" class="' + b.cls + on + '" data-sev="' + b.id + '">' + b.label + " " + b.n + "</button>";
        }).join("");
      }

      function findingCard(f, isNew) {
        var sev = String(f.severity || "info").toLowerCase();
        if (SEV_ORDER.indexOf(sev) === -1) sev = "info";
        var href = f.url ? esc(f.url) : "";
        return (
          '<article class="card ' + sev + (isNew ? " enter" : "") + '">' +
            '<div class="card-top">' +
              glyph(sev) +
              "<h3>" + esc(f.title || "Untitled finding") + "</h3>" +
              '<span class="sev-badge">' + esc(SEV_LABEL[sev]) + "</span>" +
            "</div>" +
            (href ? '<a class="url" href="' + href + '" target="_blank" rel="noopener">' + href + "</a>" : "") +
            '<div class="meta-line">' +
              '<span class="pill">' + esc(f.content_type || "unknown") + "</span>" +
            "</div>" +
            (f.description ? '<p class="desc">' + esc(f.description) + "</p>" : "") +
          "</article>"
        );
      }

      function emptyState(title, body) {
        return (
          '<div class="empty">' +
            '<div class="icon"><svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="5.5" stroke="currentColor"/><path d="M8 5v3.2M8 10.4h.01" stroke="currentColor" stroke-linecap="round"/></svg></div>' +
            "<div><strong>" + esc(title) + "</strong><p>" + esc(body) + "</p></div>" +
          "</div>"
        );
      }

      function renderFindings(findings, status) {
        var list = findings || [];
        els.findingCount.textContent = String(list.length);
        renderFilters(list);
        var filtered = filterSev === "all" ? list : list.filter(function (f) {
          return String(f.severity || "").toLowerCase() === filterSev;
        });
        if (!list.length) {
          lastFindingSig = "empty";
          els.findings.innerHTML = emptyState(
            status === "running" ? "Sweeping the surface" : "No findings yet",
            status === "running"
              ? "Sentinel is mapping routes, headers, and forms. Issues will land here as they confirm."
              : "When a run starts, confirmed issues will group here by severity."
          );
          return;
        }
        if (!filtered.length) {
          els.findings.innerHTML = emptyState("No " + filterSev + " findings", "Try another severity filter.");
          return;
        }
        var groups = {};
        SEV_ORDER.forEach(function (k) { groups[k] = []; });
        filtered.forEach(function (f) {
          var k = String(f.severity || "info").toLowerCase();
          if (!groups[k]) groups.info.push(f);
          else groups[k].push(f);
        });
        var html = "";
        SEV_ORDER.forEach(function (k) {
          var items = groups[k];
          if (!items.length) return;
          html += '<div class="group"><div class="group-h">' + glyph(k) + SEV_LABEL[k] + ' <span class="n">' + items.length + "</span></div>";
          items.forEach(function (f) {
            var key = (f.severity || "") + "|" + (f.title || "") + "|" + (f.url || "");
            var isNew = !seenFindings[key];
            html += findingCard(f, isNew);
          });
          html += "</div>";
        });
        var sig = filtered.map(function (f) { return (f.title || "") + (f.severity || ""); }).join("|") + "|" + filterSev;
        if (sig !== lastFindingSig) {
          els.findings.innerHTML = html;
          lastFindingSig = sig;
          filtered.forEach(function (f) {
            seenFindings[(f.severity || "") + "|" + (f.title || "") + "|" + (f.url || "")] = 1;
          });
        }
      }

      function diffItem(f, kind) {
        var sev = String(f.severity || "info").toLowerCase();
        return (
          '<div class="diff-item">' +
            glyph(sev) +
            '<div><div class="t">' + esc(f.title || "Untitled") + '</div><span class="u">' + esc(f.url || "") + "</span></div>" +
            '<span class="sev-badge" style="--sev: var(--' + (sev === "medium" ? "med" : sev === "info" ? "info" : sev) + ')">' + esc(SEV_SHORT[sev] || sev) + "</span>" +
          "</div>"
        );
      }

      function renderDiff(diff) {
        if (!diff) {
          els.diffCount.textContent = "-";
          els.diff.innerHTML = emptyState("Waiting on baseline", "Diff appears once this run can be compared to the previous sealed report.");
          return;
        }
        var neu = diff.new || [];
        var fixed = diff.fixed || [];
        var unchanged = diff.unchanged || [];
        var counts = diff.counts || {};
        var nNew = counts.new != null ? counts.new : neu.length;
        var nFixed = counts.fixed != null ? counts.fixed : fixed.length;
        var nUn = counts.unchanged != null ? counts.unchanged : unchanged.length;
        els.diffCount.textContent = "+" + nNew + " / −" + nFixed + " / =" + nUn;
        var sig = nNew + "," + nFixed + "," + nUn + "," + neu.map(function (f) { return f.title; }).join("|");
        if (sig === lastDiffSig && els.diff.innerHTML) return;
        lastDiffSig = sig;
        if (!neu.length && !fixed.length && !unchanged.length) {
          els.diff.innerHTML = emptyState("No delta yet", "New, fixed, and unchanged issues versus the last run will group here.");
          return;
        }
        var html = "";
        html += '<div class="diff-group"><div class="diff-h new">New · ' + nNew + "</div>";
        html += neu.length ? neu.map(function (f) { return diffItem(f, "new"); }).join("") : '<div class="empty" style="padding:12px"><p>No new findings versus previous run.</p></div>';
        html += "</div>";
        html += '<div class="diff-group"><div class="diff-h fixed">Fixed · ' + nFixed + "</div>";
        html += fixed.length ? fixed.map(function (f) { return diffItem(f, "fixed"); }).join("") : '<div class="empty" style="padding:12px"><p>No remediations confirmed yet.</p></div>';
        html += "</div>";
        html += '<div class="diff-group"><div class="diff-h unchanged">Unchanged · ' + nUn + "</div>";
        html += unchanged.length ? unchanged.map(function (f) { return diffItem(f, "unchanged"); }).join("") : '<div class="empty" style="padding:12px"><p>No overlapping findings.</p></div>';
        html += "</div>";
        els.diff.innerHTML = html;
      }

      function renderActions(actions) {
        var list = actions || [];
        var sig = list.map(function (a) { return typeof a === "string" ? a : ((a.t || "") + (a.text || a.action || "")); }).join("|");
        if (sig === lastActionSig && els.actions.innerHTML) return;
        lastActionSig = sig;
        if (!list.length) {
          els.actions.innerHTML = emptyState("Quiet", "Agent actions will stream here as the run progresses.");
          return;
        }
        els.actions.innerHTML = list.map(function (a) {
          var t = typeof a === "string" ? "·" : (a.t || a.time || a.step || "·");
          var text = typeof a === "string" ? a : (a.text || a.action || a.message || JSON.stringify(a));
          return '<div class="log-row"><div class="t">' + esc(t) + '</div><div class="tx">' + esc(text) + "</div></div>";
        }).join("");
        els.actions.scrollTop = els.actions.scrollHeight;
      }

      function renderReport(report) {
        var md = report && (report.markdown || report.text || "");
        if (md === lastReport) return;
        lastReport = md;
        if (!md) {
          els.report.textContent = "";
          els.report.innerHTML = emptyState(
            "Report not sealed",
            "The full markdown report lands here when the agent finishes verifying and writes the run."
          );
          return;
        }
        els.report.textContent = md;
      }

      function render(state, diff, report) {
        state = state || {};
        setStatus(state.status);
        renderMeta(state);
        renderStage(state);
        renderCounts(state.findings || []);
        renderFindings(state.findings || [], state.status);
        renderDiff(diff);
        renderActions(state.recent_actions || []);
        renderReport(report);
      }

      els.filters.addEventListener("click", function (e) {
        var btn = e.target.closest("button[data-sev]");
        if (!btn) return;
        filterSev = btn.getAttribute("data-sev") || "all";
        lastFindingSig = "";
        var buttons = els.filters.querySelectorAll("button");
        buttons.forEach(function (b) {
          b.classList.toggle("on", b.getAttribute("data-sev") === filterSev);
        });
        if (window.__lastState) renderFindings(window.__lastState.findings || [], window.__lastState.status);
      });

      function setSource(kind) {
        usingSim = kind === "sim";
        els.source.textContent = usingSim ? "local simulator · 1.5s" : "polling /api · 1.5s";
      }

      async function poll() {
        try {
          var res = await Promise.all([
            fetch("/api/state", { cache: "no-store" }),
            fetch("/api/diff", { cache: "no-store" }),
            fetch("/api/report", { cache: "no-store" })
          ]);
          if (!res[0].ok || !res[1].ok || !res[2].ok) throw new Error("bad status");
          var state = await res[0].json();
          var diff = await res[1].json();
          var report = await res[2].json();
          window.__lastState = state;
          setSource("live");
          render(state, diff, report);
        } catch (err) {
          var sim = simulate();
          window.__lastState = sim.state;
          setSource("sim");
          render(sim.state, sim.diff, sim.report);
        }
      }

      var runBtn = document.getElementById("run-btn");
      if (runBtn) runBtn.addEventListener("click", startScan);

      loadConfigs();
      setInterval(loadConfigs, 15000);
      pollScanStatus();
      setInterval(pollScanStatus, 2000);

      poll();
      setInterval(poll, POLL_MS);
    })();
  </script>
</body>
</html>

"""


def create_app(
    state_path: Path,
    reports_dir: Path,
    project_root: Path | None = None,
    auth_token: str | None = None,
    users_db: Path | None = None,
    secret_key: str | None = None,
) -> Flask:
    app = Flask(__name__)
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[2]
    token = auth_token or load_or_create_token(reports_dir)
    app.secret_key = secret_key or secrets.token_hex(32)
    users = UserStore(users_db or (Path(reports_dir) / "users.db"))
    limiter = RateLimiter(max_attempts=5, window_seconds=300)

    def _user():
        return current_user(users)

    def _client_ip() -> str:
        return request.headers.get("X-Forwarded-For", request.remote_addr or "?").split(",")[0].strip()

    def _viewer_is_admin() -> bool:
        """Admins and bootstrap-token callers see every report; users see their own."""
        u = _user()
        if u is None:
            return True  # token-authenticated (the gate already rejected anonymous)
        return u["role"] == "admin"

    def _owns_report(rep: dict) -> bool:
        """True if the current viewer may see this report."""
        if _viewer_is_admin():
            return True
        u = _user()
        return u is not None and rep.get("owner_id") == u["id"]

    def _own_reports(reports: list[dict]) -> list[dict]:
        return [r for r in reports if _owns_report(r)]

    @app.before_request
    def _gate():
        # Auth gate: session user OR bootstrap token (admin/API).
        # Token auth (header / query / cookie) - also the API mechanism.
        provided = (
            request.headers.get("X-Sentinel-Token")
            or request.args.get("token")
            or request.cookies.get(_COOKIE)
        )
        if provided and secrets.compare_digest(provided, token):
            return None
        # Logged-in human?
        if _user() is not None:
            return None
        # Auth routes are the exception - that's how you get in.
        if request.path in ("/login", "/signup", "/token-login"):
            return None
        # Static assets and favicon don't need auth.
        if request.path == "/favicon.ico" or request.path.startswith("/static/"):
            return None
        if request.path.startswith("/api/"):
            return jsonify({"error": "unauthorized"}), 401
        return redirect(url_for("login", next=request.path))

    @app.after_request
    def _remember_token(resp):
        """Visits via the tokened URL hand the browser a cookie so later
        UI fetches (and plain reloads) authenticate seamlessly."""
        provided = request.args.get("token")
        if provided and secrets.compare_digest(provided, token):
            resp.set_cookie(_COOKIE, token, httponly=True, samesite="Lax")
        return resp

    @app.context_processor
    def _inject_user():
        return {"user": _user()}

    # --- Auth routes ---------------------------------------------------------

    def _auth_page(mode: str, subtitle: str, flash: str = "", flash_ok: bool = False):
        if mode == "signup":
            action, button = "/signup", "Create account"
            alt = 'Already registered? <a href="/login">Sign in</a>'
        else:
            action, button = "/login", "Sign in"
            alt = 'No account yet? <a href="/signup">Create one</a>'
        flash_cls = "flash flash-ok" if flash_ok and flash else "flash"
        return _LOGIN_PAGE.format(
            subtitle=subtitle,
            flash=f'<div class="{flash_cls}">{flash}</div>' if flash else "",
            action=action,
            csrf=csrf_token(),
            autocomplete="new-password" if mode == "signup" else "current-password",
            button_label=button,
            alt=alt,
            token=token,
        )

    @app.get("/login")
    def login():
        if _user() is not None:
            return redirect("/")
        if request.args.get("out") == "1":
            return _auth_page(
                "login", "Sign in to run scans and view reports.",
                "You are signed out. See you next scan.", flash_ok=True,
            )
        return _auth_page("login", "Sign in to run scans and view reports.")

    @app.post("/login")
    def login_post():
        ip = _client_ip()
        if not limiter.check(f"login:{ip}"):
            return _auth_page(
                "login", "Sign in to run scans and view reports.",
                "Too many attempts - wait 5 minutes and try again.",
            )
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        if not csrf_valid(request.form):
            return _auth_page("login", "Sign in to run scans and view reports.", "Invalid or expired form - try again."), 400
        row = users.verify(email, password)
        if row is None:
            limiter.hit(f"login:{ip}")
            return _auth_page("login", "Sign in to run scans and view reports.", "Wrong email or password.")
        limiter.reset(f"login:{ip}")
        login_user(int(row["id"]))
        dest = request.args.get("next") or "/"
        if not dest.startswith("/"):  # open-redirect guard
            dest = "/"
        return redirect(dest)

    @app.get("/signup")
    def signup():
        if _user() is not None:
            return redirect("/")
        first = users.count() == 0
        subtitle = (
            "Create the admin account - the first user owns this Sentinel."
            if first
            else "Create an account to run scans and view reports."
        )
        return _auth_page("signup", subtitle)

    @app.post("/signup")
    def signup_post():
        ip = _client_ip()
        if not limiter.check(f"signup:{ip}"):
            return _auth_page(
                "signup", "Create an account to run scans and view reports.",
                "Too many attempts - wait 5 minutes and try again.",
            )
        if not csrf_valid(request.form):
            return _auth_page("signup", "Create an account to run scans and view reports.", "Invalid or expired form - try again."), 400
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        first = users.count() == 0
        try:
            uid = users.create_user(email, password, role="admin" if first else "user")
        except ValueError as exc:
            return _auth_page("signup", "Create an account to run scans and view reports.", str(exc))
        if uid is None:
            return _auth_page("signup", "Create an account to run scans and view reports.", "That email is already registered - sign in instead.")
        limiter.reset(f"signup:{ip}")
        login_user(uid)
        return redirect("/")

    @app.get("/token-login")
    def token_login_page():
        """Local users arrive via the tokened URL - explain and honor it."""
        provided = request.args.get("token", "")
        if provided and secrets.compare_digest(provided, token):
            resp = redirect("/")
            resp.set_cookie(_COOKIE, provided, httponly=True, samesite="Lax")
            return resp
        return _auth_page(
            "login",
            "Sign in to run scans and view reports.",
            "Access token missing or wrong - use the full URL printed by `sentinel dashboard`.",
        )

    @app.post("/logout")
    def logout():
        if not csrf_valid(request.form):
            return redirect("/")
        logout_user()
        return redirect("/login?out=1")

    @app.get("/")
    def index() -> str:
        u = _user()
        if u is not None:
            import html as _html

            email = u["email"] or ""
            initial = (email[:1] or "?").upper()
            role_badge = (
                '<span class="role" title="This account manages this Sentinel instance">'
                "admin</span>"
                if u["role"] == "admin"
                else ""
            )
            chip = (
                '<div class="user-chip" title="Signed in as '
                + _html.escape(email, quote=True)
                + '">'
                + '<span class="avatar" aria-hidden="true">' + _html.escape(initial) + '</span>'
                + '<span class="u">' + _html.escape(email) + '</span>'
                + role_badge
                + '<form method="post" action="/logout">'
                + '<input type="hidden" name="csrf_token" value="' + csrf_token() + '">'
                + '<button type="submit" aria-label="Log out of Sentinel">'
                + '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" aria-hidden="true">'
                + '<path d="M15 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h8" '
                + 'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
                + '<path d="M16 17l5-5-5-5M21 12H9" '
                + 'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
                + '</svg>'
                + 'Log out</button></form></div>'
            )
        else:
            chip = ""
        return _PAGE.replace("{user_chip}", chip)

    @app.get("/api/configs")
    def api_configs():
        """List available scan configs (name + target) for the run controls."""
        import yaml

        configs = []
        for path in sorted(root.glob("config*.yml")):
            name = path.stem
            if name.startswith("config."):
                name = name[len("config.") :]
            target = None
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                target = data.get("target")
            except Exception:
                target = None
            configs.append({"name": name, "target": target, "file": path.name})
        return jsonify({"configs": configs})

    @app.post("/api/scan")
    def api_scan():
        # Start a scan as a background process: {config, skip_llm}.
        # `config` may be an existing config name or a bare domain;
        # unknown domains get a config auto-created, matching the
        # `sentinel run --config somesite.com` CLI behavior.
        body = request.get_json(silent=True) or {}
        name = str(body.get("config", "")).strip().rstrip("/")
        skip_llm = bool(body.get("skip_llm"))
        if not name or len(name) > 200 or any(c in name for c in '\\/:*?"<>|'):
            return jsonify({"error": "invalid config name"}), 400

        # Resolve/auto-create the config exactly like the CLI does.
        from qaagent.cli import _auto_create_config, _derive_target

        created = False
        probe = Path(name)
        exists = any(
            (root / cand).exists()
            for cand in (
                probe,
                Path(f"config.{name}.yml"),
                Path(f"{name}.yml"),
                Path(f"config.{name}"),
            )
        )
        if not exists:
            target = _derive_target(name)
            if target is None:
                return jsonify(
                    {
                        "error": f"no config for '{name}' and it is not a domain - "
                        "type a site like example.com, or create a config first"
                    }
                ), 400
            _auto_create_config(name, target)
            created = True

        proc = _scan["proc"]
        if proc is not None and proc.poll() is None:
            return jsonify({"error": "a scan is already running"}), 409
        reports_dir.mkdir(parents=True, exist_ok=True)
        log_path = reports_dir / "scan-ui.log"
        args = [sys.executable, "-m", "qaagent", "run", "--config", name]
        if skip_llm:
            args.append("--skip-llm")
        # Ownership: the scan belongs to whoever clicked Run. The subprocess
        # reads SENTINEL_OWNER_* and stamps every report it writes with it.
        u = _user()
        env = os.environ.copy()
        if u is not None:
            env["SENTINEL_OWNER_ID"] = str(u["id"])
            env["SENTINEL_OWNER_EMAIL"] = u["email"] or ""
        else:
            env.pop("SENTINEL_OWNER_ID", None)
            env.pop("SENTINEL_OWNER_EMAIL", None)
        log_fh = open(log_path, "w", encoding="utf-8")
        try:
            proc = subprocess.Popen(
                args,
                cwd=str(root),
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                env=env,
            )
        finally:
            log_fh.close()
        _scan.update(
            proc=proc,
            config=name,
            skip_llm=skip_llm,
            started=datetime.now(timezone.utc).isoformat(),
            log_path=str(log_path),
            returncode=None,
            owner_id=(u["id"] if u is not None else None),
            owner_email=(u["email"] if u is not None else None),
        )
        return jsonify(
            {"started": True, "config": name, "skip_llm": skip_llm, "created": created}
        )

    @app.get("/api/scan/status")
    def api_scan_status():
        """Is a UI-started scan running, and what has it printed so far?"""
        proc = _scan["proc"]
        running = proc is not None and proc.poll() is None
        if proc is not None and not running and _scan["returncode"] is None:
            _scan["returncode"] = proc.returncode
        tail: list[str] = []
        if _scan["log_path"]:
            log = Path(_scan["log_path"])
            if log.exists():
                tail = log.read_text(encoding="utf-8", errors="replace").splitlines()[-25:]
        return jsonify(
            {
                "running": running,
                "config": _scan["config"],
                "skip_llm": _scan["skip_llm"],
                "started": _scan["started"],
                "returncode": _scan["returncode"],
                "log_tail": tail,
            }
        )

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
        # Isolation: the live view shows only the viewer's own scan. A running
        # or just-finished scan tracks its starter in _scan; older scans with a
        # different owner (or pre-ownership runs) show as idle for others.
        if not _viewer_is_admin():
            u = _user()
            owner = _scan.get("owner_id")
            if owner is None or (u is not None and owner != u["id"]):
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
        reports = _own_reports(load_report_files(reports_dir))
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
        # Walk newest-first until the first report the viewer owns.
        latest = None
        json_path = None
        for f in reversed(files):
            stamp = f.stem[len("report-") :]
            jf = reports_dir / f"report-{stamp}.json"
            try:
                rep = json.loads(jf.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if _owns_report(rep):
                latest = f
                json_path = str(jf) if jf.exists() else None
                break
        if latest is None:
            return jsonify(
                {"path": None, "json_path": None, "markdown": "No report yet."}
            )
        return jsonify(
            {
                "path": str(latest),
                "json_path": json_path,
                "markdown": latest.read_text(encoding="utf-8"),
            }
        )

    return app


def run_dashboard(
    state_path: Path,
    reports_dir: Path,
    port: int,
    project_root: Path | None = None,
    auth_token: str | None = None,
) -> None:
    """Serve the dashboard until interrupted."""
    # Persistent session-signing key: logins survive dashboard restarts.
    key_path = Path(reports_dir) / ".dashboard-secret"
    if key_path.exists():
        secret = key_path.read_text(encoding="utf-8").strip()
    else:
        secret = secrets.token_hex(32)
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text(secret, encoding="utf-8")
    create_app(
        state_path,
        reports_dir,
        project_root=project_root,
        auth_token=auth_token,
        secret_key=secret,
    ).run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
