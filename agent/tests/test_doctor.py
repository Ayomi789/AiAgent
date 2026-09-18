"""Doctor tests: data-path, config-health, LLM-probe, and target checks.

All external effects are faked - no network, no real project directory.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from qaagent import doctor
from qaagent.config import LLMConfig, RunConfig, ScopeConfig


def _make_config(tmp_path: Path, name: str = "config.test.yml", model: str | None = None) -> Path:
    model_line = f"  model: {model}\n" if model else ""
    path = tmp_path / name
    path.write_text(
        "target: https://x.test\n"
        "scope:\n"
        "  allowed_origins: []\n"
        "llm:\n"
        f"{model_line}"
        "  api_key_env: NVIDIA_API_KEY\n",
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------- data paths


def test_check_data_paths_missing_dir_warns(tmp_path):
    checks = doctor.check_data_paths(tmp_path, tmp_path / "reports")
    assert checks[0].status == "warn"


def test_check_data_paths_counts_and_flags(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "report-20260101-000000.json").write_text("{}", encoding="utf-8")
    (reports / "report-20260101-000001.json").write_text("{}", encoding="utf-8")
    (reports / "live.json").write_text("{}", encoding="utf-8")
    (reports / ".dashboard-token").write_text("t", encoding="utf-8")
    checks = doctor.check_data_paths(tmp_path, reports)
    assert checks[0].status == "ok"
    assert "2 run(s)" in checks[0].detail
    assert "live state" in checks[0].detail
    assert "dashboard token" in checks[0].detail


# ------------------------------------------------------------------- configs


def test_check_configs_all_healthy(tmp_path):
    _make_config(tmp_path, "config.a.yml")
    _make_config(tmp_path, "config.b.yml")
    checks = doctor.check_configs(tmp_path)
    assert checks[0].status == "ok"
    assert "2 config(s)" in checks[0].detail


def test_check_configs_flags_retired_model(tmp_path):
    _make_config(tmp_path, "config.stale.yml", model="z-ai/glm-5.3-flash")
    checks = doctor.check_configs(tmp_path)
    assert checks[0].status == "fail"
    assert "retired model" in checks[0].detail


def test_check_configs_flags_broken_yaml(tmp_path):
    (tmp_path / "config.broken.yml").write_text(
        "target: [unclosed\n  scope: {", encoding="utf-8"
    )
    checks = doctor.check_configs(tmp_path)
    assert checks[0].status == "fail"
    assert "config.broken.yml" in checks[0].detail


def test_check_configs_empty_dir_warns(tmp_path):
    checks = doctor.check_configs(tmp_path)
    assert checks[0].status == "warn"


# ----------------------------------------------------------------- llm probe


def _llm_response(status_code: int, body: dict | str) -> httpx.Response:
    return httpx.Response(status_code=status_code, json=body) if isinstance(body, dict) else httpx.Response(status_code=status_code, text=body)


def test_probe_llm_no_key_fails(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    check = doctor.probe_llm(LLMConfig(api_key_env="NVIDIA_API_KEY"))
    assert check.status == "fail"
    assert "no API key" in check.detail


def test_probe_llm_tool_call_ok(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "k")
    body = {
        "choices": [
            {
                "message": {
                    "content": None,
                    "tool_calls": [
                        {"id": "1", "type": "function", "function": {"name": "get_page", "arguments": "{}"}}
                    ],
                }
            }
        ]
    }
    with patch.object(httpx, "post", return_value=_llm_response(200, body)):
        check = doctor.probe_llm(LLMConfig(api_key_env="NVIDIA_API_KEY"))
    assert check.status == "ok"
    assert "tool-calling works" in check.detail


def test_probe_llm_404_reports_retired(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "k")
    with patch.object(httpx, "post", return_value=_llm_response(404, {"detail": "nope"})):
        check = doctor.probe_llm(LLMConfig(api_key_env="NVIDIA_API_KEY"))
    assert check.status == "fail"
    assert "not routable" in check.detail


def test_probe_llm_answer_without_tools_warns(monkeypatch):
    """Chat-only answers are a warning: the agent loop needs tool calls."""
    monkeypatch.setenv("NVIDIA_API_KEY", "k")
    body = {"choices": [{"message": {"content": "I cannot use tools."}}]}
    with patch.object(httpx, "post", return_value=_llm_response(200, body)):
        check = doctor.probe_llm(LLMConfig(api_key_env="NVIDIA_API_KEY"))
    assert check.status == "warn"
    assert "no tool call" in check.detail


def test_probe_llm_timeout_fails(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "k")
    with patch.object(httpx, "post", side_effect=httpx.TimeoutException("t")):
        check = doctor.probe_llm(LLMConfig(api_key_env="NVIDIA_API_KEY"))
    assert check.status == "fail"
    assert "timed out" in check.detail


def test_probe_llm_bad_key_fails(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "k")
    with patch.object(httpx, "post", return_value=_llm_response(401, {"detail": "no"})):
        check = doctor.probe_llm(LLMConfig(api_key_env="NVIDIA_API_KEY"))
    assert check.status == "fail"
    assert "rejected" in check.detail


# -------------------------------------------------------------------- target


def test_check_target_reachable(monkeypatch):
    with patch.object(httpx, "get", return_value=_llm_response(200, {"ok": True})):
        check = doctor.check_target("https://x.test")
    assert check.status == "ok"


def test_check_target_5xx_warns(monkeypatch):
    with patch.object(httpx, "get", return_value=_llm_response(503, {})):
        check = doctor.check_target("https://x.test")
    assert check.status == "warn"


def test_check_target_unreachable_fails(monkeypatch):
    with patch.object(httpx, "get", side_effect=httpx.ConnectError("nope")):
        check = doctor.check_target("https://down.test")
    assert check.status == "fail"


def test_check_target_invalid_url_fails():
    check = doctor.check_target("not a url at all")
    assert check.status == "fail"


# ---------------------------------------------------------------- run_checks


def test_run_checks_skips_llm_when_asked(tmp_path):
    checks = doctor.run_checks(
        tmp_path, tmp_path / "reports", probe_model=False, target=None
    )
    llm = [c for c in checks if c.name == "llm"]
    assert llm and "skipped" in llm[0].detail


def test_run_checks_uses_config_model_and_target(tmp_path):
    cfg_path = _make_config(tmp_path, "config.deep.yml", model="nvidia/nemotron-3-super-120b-a12b")
    captured: dict = {}

    def fake_probe(cfg):
        captured["model"] = cfg.model
        return doctor.Check("llm", "ok", "probed")

    def fake_target(url):
        captured["target"] = url
        return doctor.Check("target", "ok", "probed")

    with patch.object(doctor, "probe_llm", fake_probe), patch.object(doctor, "check_target", fake_target):
        doctor.run_checks(tmp_path, tmp_path / "reports", config_path=cfg_path, target=None, probe_model=True)
    assert captured["model"] == "nvidia/nemotron-3-super-120b-a12b"
    assert captured["target"] == "https://x.test"


def test_failed_counts_only_failures():
    checks = [
        doctor.Check("a", "ok", ""),
        doctor.Check("b", "warn", ""),
        doctor.Check("c", "fail", ""),
    ]
    assert doctor.failed(checks) == 1
