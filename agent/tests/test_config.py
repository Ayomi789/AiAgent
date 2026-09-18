"""Config tests: YAML loading, the nested agent section, validation, auto-scope."""

from __future__ import annotations

from pathlib import Path

import pytest

from qaagent.cli import _derive_target, _resolve_config
from qaagent.config import RunConfig, ScopeConfig
from qaagent.tools.impl import _in_scope

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_anchor_output_dir_never_uses_cwd(tmp_path):
    """Reports must land next to the config (or in the project), not in CWD.

    The home-dir trap: running `sentinel dashboard` / `sentinel run` from
    ~/ silently created ~/reports with its own token, users.db, and reports.
    """
    from qaagent.cli import _anchor_output_dir

    project = tmp_path / "project"
    project.mkdir()
    cfg_dir = tmp_path / "elsewhere"
    cfg_dir.mkdir()

    # With a config: anchored next to the config file (its parent folder).
    cfg = RunConfig(target="https://x.test", scope=ScopeConfig(allowed_origins=[]))
    _anchor_output_dir(cfg, cfg_dir / "config.x.yml", project)
    assert cfg.output_dir == cfg_dir / "reports"

    # Without a config: anchored to the project.
    cfg2 = RunConfig(target="https://x.test", scope=ScopeConfig(allowed_origins=[]))
    _anchor_output_dir(cfg2, None, project)
    assert cfg2.output_dir == project / "reports"

    # Explicit absolute paths are respected untouched.
    absolute = tmp_path / "custom"
    cfg3 = RunConfig(
        target="https://x.test", scope=ScopeConfig(allowed_origins=[]), output_dir=absolute
    )
    _anchor_output_dir(cfg3, cfg_dir / "config.x.yml", project)
    assert cfg3.output_dir == absolute


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


def test_default_model_is_not_retired():
    """Guard against shipping a model that the LLM provider has end-of-life'd.

    Twice-burned: the llama-3.3-70b default outlived a model swap so every
    newly auto-created config scanned with a dead model ('LLM API error 410'),
    and z-ai/glm-5.3-flash stopped routing overnight ('LLM API error 404').
    Any model confirmed dead goes on RETIRED_LLM_MODELS.
    """
    from qaagent.config import DEFAULT_LLM_MODEL, RETIRED_LLM_MODELS

    for retired in RETIRED_LLM_MODELS:
        assert retired not in DEFAULT_LLM_MODEL


def test_no_config_ships_a_retired_model():
    """No shipped config may reference a retired model, even commented out."""
    from qaagent.config import RETIRED_LLM_MODELS

    shipped = sorted(PROJECT_ROOT.glob("config*.yml"))
    assert shipped, "expected at least one shipped config"
    for path in shipped:
        text = path.read_text(encoding="utf-8")
        for retired in RETIRED_LLM_MODELS:
            assert retired not in text, (
                f"{path.name} still references retired model {retired!r}"
            )


def test_auto_created_config_uses_live_model():
    """Auto-created configs must stamp the current default model, not a stale one."""
    import yaml

    from qaagent.cli import _auto_create_config
    from qaagent.config import DEFAULT_LLM_MODEL

    path = _auto_create_config("newsite.example", "https://newsite.example")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert "llama-3.3-70b-instruct" not in data["llm"]["model"]
        assert data["llm"]["model"] == DEFAULT_LLM_MODEL
    finally:
        path.unlink(missing_ok=True)


def test_config_shorthand_resolves(tmp_path, monkeypatch):
    (tmp_path / "config.solnew.yml").write_text("target: http://x.test", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert _resolve_config(Path("solnew")).resolve() == (tmp_path / "config.solnew.yml").resolve()


def test_config_shorthand_plain_name(tmp_path, monkeypatch):
    (tmp_path / "solnew.yml").write_text("target: http://x.test", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert _resolve_config(Path("solnew")).resolve() == (tmp_path / "solnew.yml").resolve()


def test_config_shorthand_exact_path_wins(tmp_path, monkeypatch):
    (tmp_path / "myconfig.yml").write_text("target: http://x.test", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert _resolve_config(Path("myconfig.yml")).resolve() == (tmp_path / "myconfig.yml").resolve()


def test_config_shorthand_missing_raises(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        _resolve_config(Path("doesnotexist"))


def test_derive_target_from_bare_domain():
    assert _derive_target("stylesbytiwa.netlify.app") == "https://stylesbytiwa.netlify.app"
    assert _derive_target("mysite.io") == "https://mysite.io"


def test_derive_target_keeps_full_url():
    assert _derive_target("https://x.io/path") == "https://x.io/path"


def test_derive_target_rejects_non_domains():
    assert _derive_target("solnew") is None
    assert _derive_target("config.yml") is None
    assert _derive_target("config.foo") is None
    assert _derive_target("my site") is None
