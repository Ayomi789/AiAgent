"""Sentinel — user-facing entry point for the QA agent.

The engine lives in the ``qaagent`` package; this tiny module gives the
CLI its brand name so it can be invoked as ``python -m sentinel`` or
``sentinel``.
"""

from qaagent.cli import app

__all__ = ["app"]
