"""Tool surface: deterministic actions the LLM may call.

Tools are the only way the model can affect the outside world. Each tool must
validate its inputs, stay inside the scope guard, and return structured results
that feed the observe/verify steps of the loop.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from pydantic import BaseModel, Field


class ToolSpec(BaseModel):
    """Public contract for a tool, used to build the LLM's tool schema."""

    name: str
    description: str
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="JSON Schema for the tool arguments."
    )


class Tool:
    """A single deterministic action exposed to the agent."""

    def __init__(
        self, spec: ToolSpec, handler: Callable[..., Awaitable[dict[str, Any]]]
    ) -> None:
        self.spec = spec
        self.handler = handler

    async def __call__(self, **kwargs: Any) -> dict[str, Any]:
        return await self.handler(**kwargs)


class ToolRegistry:
    """Registry of every tool available to the agent in a run."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.spec.name in self._tools:
            raise ValueError(f"tool already registered: {tool.spec.name}")
        self._tools[tool.spec.name] = tool

    def get(self, name: str) -> Tool:
        return self._tools[name]

    def list(self) -> list[ToolSpec]:
        return [tool.spec for tool in self._tools.values()]
