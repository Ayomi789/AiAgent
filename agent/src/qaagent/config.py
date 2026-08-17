"""Run configuration for the QA agent, loaded from a YAML file."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class ScopeConfig(BaseModel):
    """Hard boundary on what the agent is allowed to touch."""

    allowed_origins: list[str] = Field(
        description="Origins the agent may visit, as scheme://host[:port]."
    )
    excluded_paths: list[str] = Field(default_factory=list)
    max_requests_per_minute: int = Field(default=30, ge=1)
    timeout_seconds: int = Field(default=30, ge=1)


class LLMConfig(BaseModel):
    """LLM settings for any OpenAI-compatible API (NVIDIA by default)."""

    model: str = "meta/llama-3.3-70b-instruct"
    api_key_env: str = "NVIDIA_API_KEY"
    api_base: str = "https://integrate.api.nvidia.com/v1"
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=64)
    max_retries: int = Field(default=4, ge=0, description="Retries on rate-limit (429/503/5xx) errors.")
    retry_delay_seconds: float = Field(default=15, ge=0, description="Base backoff between retries.")


_SENSITIVE_FILE_KINDS = {"sql", "sqlite", "archive", "env", "key", "git", "text"}


class CredentialsConfig(BaseModel):
    """Optional test credentials the agent may use for auth flows."""

    username: str
    password: str


class RunConfig(BaseModel):
    """Everything needed to run one agent session against one target."""

    target: str
    scope: ScopeConfig
    llm: LLMConfig = Field(default_factory=LLMConfig)
    credentials: CredentialsConfig | None = None
    max_steps: int = Field(default=25, ge=1, le=500)
    headless: bool = True
    browser_channel: str = Field(
        default="msedge",
        description="Playwright channel: 'msedge' uses the system Edge (no download); 'chromium' needs `playwright install`.",
    )
    output_dir: Path = Path("reports")
    skip_llm: bool = Field(
        default=False,
        description="Deterministic probes only: skip the LLM-driven exploration loop.",
    )
    sensitive_files: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Extra sensitive artifact names to probe, mapped to a content kind "
            "(sql|sqlite|archive|env|key|git|text). Added to the built-in wordlist; "
            "e.g. {'/secrets.tar.gz': 'archive', '/deploy.key': 'key'}."
        ),
    )

    @field_validator("sensitive_files")
    @classmethod
    def _validate_sensitive_files(
        cls, v: dict[str, str]
    ) -> dict[str, str]:
        for path, kind in v.items():
            if not path.startswith("/"):
                raise ValueError(
                    f"sensitive_files key {path!r} must be a path starting with '/'"
                )
            if kind not in _SENSITIVE_FILE_KINDS:
                raise ValueError(
                    f"sensitive_files[{path!r}] kind {kind!r} not in "
                    f"{sorted(_SENSITIVE_FILE_KINDS)}"
                )
        return v

    @field_validator("target")
    @classmethod
    def _target_must_be_http(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("target must start with http:// or https://")
        return v.rstrip("/")

    @model_validator(mode="before")
    @classmethod
    def _flatten_agent_section(cls, data: object) -> object:
        """Accept settings nested under an `agent:` block (as the example configs
        document them), flattened into the top level. Explicit top-level values
        win over the nested ones."""
        if isinstance(data, dict) and isinstance(data.get("agent"), dict):
            merged = dict(data)
            for key, value in merged.pop("agent").items():
                merged.setdefault(key, value)
            return merged
        return data

    @classmethod
    def from_yaml(cls, path: str | Path) -> "RunConfig":
        config_path = Path(path)
        if not config_path.is_file():
            raise ValueError(f"config file not found: {config_path}")
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"config file {config_path} must contain a YAML mapping")
        return cls.model_validate(data)
