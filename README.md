---
title: Sentinel
emoji: 🛡️
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# Sentinel

AI agent that autonomously tests websites for **vulnerabilities**, **bugs**, and **broken functionality** — browsing like a user, probing like a scanner, delivering severity-ranked reports with evidence.

- **Console:** React workbench (runs, findings, evidence, reports, admin) served by Flask at `/console`
- **Engine:** observe → think → act → verify loop (Playwright + deterministic probes + LLM)
- **Reports:** Markdown / JSON / HTML / CSV / TestIO, with new-vs-fixed baseline diffing
- **Accounts:** invite-only signup, suspension, per-user quotas, Terms-stamped authorization

The engine lives in `agent/` (see `agent/README.md`); the console source in `frontend-src/`. Deploys to Render (`render.yaml`), Docker Compose (`compose.yaml`), or Hugging Face Spaces (this file's frontmatter + `Dockerfile`).
