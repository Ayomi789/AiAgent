"""Minimal OpenAI-compatible chat client, used for NVIDIA's API and similar.

Speaks the /chat/completions protocol over httpx with tool-call support, so we
do not need a heavyweight SDK or gateway dependency.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any

import httpx

from qaagent.config import LLMConfig

_RETRYABLE = {429, 500, 502, 503, 504}


@dataclass
class LLMMessage:
    """One message in the conversation, OpenAI-style."""

    role: str  # system | user | assistant | tool
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        msg: dict[str, Any] = {"role": self.role}
        if self.content is not None:
            msg["content"] = self.content
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        return msg


@dataclass
class LLMResult:
    content: str | None
    tool_calls: list[dict[str, Any]]
    finish_reason: str | None


class LLMClient:
    """Chat client for any OpenAI-compatible endpoint (tools supported)."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self._key = os.environ.get(config.api_key_env) if config.api_key_env else None

    @property
    def available(self) -> bool:
        return bool(self._key)

    async def chat(
        self, messages: list[LLMMessage], tools: list[dict] | None = None
    ) -> LLMResult:
        if not self.available:
            raise RuntimeError(
                f"no API key found in environment variable {self.config.api_key_env}"
            )
        url = f"{self.config.api_base.rstrip('/')}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [m.as_dict() for m in messages],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if tools:
            payload["tools"] = tools
        headers = {"Authorization": f"Bearer {self._key}"}
        async with httpx.AsyncClient(timeout=120) as client:
            data = await self._post_with_retry(client, url, payload, headers)

        choice = data["choices"][0]
        msg = choice.get("message", {})
        # Keep the raw OpenAI wire format (id, type, function{name, arguments})
        # so tool calls can be echoed back to the API unchanged.
        tool_calls = [dict(tc) for tc in (msg.get("tool_calls") or [])]
        return LLMResult(
            content=msg.get("content"),
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason"),
        )

    async def _post_with_retry(
        self,
        client: httpx.AsyncClient,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        """POST /chat/completions, backing off on rate limits and 5xx errors."""
        for attempt in range(self.config.max_retries + 1):
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code not in _RETRYABLE:
                break
            if attempt >= self.config.max_retries:
                break
            delay = self.config.retry_delay_seconds * (attempt + 1)
            await asyncio.sleep(delay)
        if resp.status_code >= 400:
            raise RuntimeError(f"LLM API error {resp.status_code}: {resp.text[:2000]}")
        return resp.json()
