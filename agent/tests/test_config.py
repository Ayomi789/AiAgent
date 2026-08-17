"""Config tests: YAML loading, the nested agent section, validation, auto-scope."""

from __future__ import annotations

from pathlib import Path

import pytest

from qaagent.config import RunConfig, ScopeConfig
from qaagent.tools.impl import _in_scope

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_example_config_loads():
    cfg = RunConfig.from_yaml(PROJECT_ROOT / "config.example.yml")
    assert cfg.target == "http://127.0.0.1:5001"
    assert cfg.browser_channel == "msedge"
    assert cfg.credentials is not None
    assert cfg.credentials.username == "alice"


def test_ci_config_loads_with_chromium_and_empty_scope():
    cfg = RunConfig.from_yaml(PROJECT_ROOT / "config.ci.yml")
    assert cfg.browser_channel == "chromium"
    assert cfg.scope.allowed_origins == []


def test_nested_agent_section_is_flattened():
    cfg = RunConfig.model_validate(
        {
            "target": "http://x.test",
            "scope": {"allowed_origins": ["http://x.test"]},
            "agent": {
                "max_steps": 7,
                "browser_channel": "chromium",
                "headless": False,
                "output_dir": "tmp-out",
            },
        }
    )
    assert cfg.max_steps == 7
    assert cfg.browser_channel == "chromium"
    assert cfg.headless is False
    assert cfg.output_dir == Path("tmp-out")


def test_top_level_overrides_nested_agent():
    cfg = RunConfig.model_validate(
        {
            "target": "http://x.test",
            "scope": {"allowed_origins": ["http://x.test"]},
            "agent": {"max_steps": 7},
            "max_steps": 3,
        }
    )
    assert cfg.max_steps == 3


def test_invalid_target_rejected():
    with pytest.raises(ValueError):
        RunConfig.model_validate(
            {"target": "ftp://x.test", "scope": {"allowed_origins": []}}
        )


def test_missing_config_file_raises():
    with pytest.raises(ValueError):
        RunConfig.from_yaml("/nonexistent/config.yml")


def test_empty_scope_auto_targets():
    cfg = RunConfig(target="https://example.com/", scope=ScopeConfig(allowed_origins=[]))
    assert _in_scope("https://example.com/page", cfg)
    assert not _in_scope("https://evil.com/", cfg)
    assert not _in_scope("http://example.com/", cfg)  # scheme must match


def test_explicit_scope_enforced():
    cfg = RunConfig(
        target="https://example.com/",
        scope=ScopeConfig(allowed_origins=["https://example.com"]),
    )
    assert _in_scope("https://example.com/a", cfg)
    assert not _in_scope("https://other.com/", cfg)


def test_sensitive_files_accepted_and_flattened():
    cfg = RunConfig.model_validate(
        {
            "target": "http://x.test",
            "scope": {"allowed_origins": ["http://x.test"]},
            "agent": {
                "sensitive_files": {"/secrets.tar.gz": "archive", "/deploy.key": "key"}
            },
        }
    )
    assert cfg.sensitive_files == {
        "/secrets.tar.gz": "archive",
        "/deploy.key": "key",
    }


def test_sensitive_files_invalid_kind_rejected():
    with pytest.raises(ValueError):
        RunConfig.model_validate(
            {
                "target": "http://x.test",
                "scope": {"allowed_origins": ["http://x.test"]},
                "sensitive_files": {"/x.zip": "bogus"},
            }
        )


def test_sensitive_files_path_must_start_with_slash():
    with pytest.raises(ValueError):
        RunConfig.model_validate(
            {
                "target": "http://x.test",
                "scope": {"allowed_origins": ["http://x.test"]},
                "sensitive_files": {"secrets.tar.gz": "archive"},
            }
        )
