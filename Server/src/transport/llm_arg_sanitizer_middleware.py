"""
Sanitises LLM-generated tool-call arguments before pydantic validation.

Small/local models (Qwen, Llama, Gemma) frequently emit:
  - Wrapped literals:   "\"create\""   (double-escaped string)
  - Single-quoted literals: "'create'"
  - JSON null for required params: null
  - String "null" (typeless models that print instead of emitting null)

Pydantic's Literal validation rejects all of these, and the model then loops
retrying the same shape. Strip these at the middleware layer so tools receive
clean values regardless of which LLM is driving them.
"""
from __future__ import annotations

import logging
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

logger = logging.getLogger("mcp-for-unity-server")


def _sanitize(value: Any) -> Any:
    if value is None:
        return _DROP
    if isinstance(value, str):
        s = value.strip()
        if s.lower() == "null" or s == "":
            return _DROP
        # Strip one layer of matching outer quotes: "\"foo\"" -> "foo", "'foo'" -> "foo"
        if len(s) >= 2 and s[0] in ("\"", "'") and s[-1] == s[0]:
            s = s[1:-1]
        return s
    if isinstance(value, dict):
        cleaned = {}
        for k, v in value.items():
            r = _sanitize(v)
            if r is not _DROP:
                cleaned[k] = r
        return cleaned
    if isinstance(value, list):
        return [r for r in (_sanitize(v) for v in value) if r is not _DROP]
    return value


class _Drop:
    """Sentinel indicating the caller should omit the key entirely."""
    __slots__ = ()


_DROP = _Drop()


class LlmArgSanitizerMiddleware(Middleware):
    """Preprocess tool-call arguments to accommodate loose LLM tool-call JSON."""

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        msg = getattr(context, "message", None)
        args = getattr(msg, "arguments", None)
        if isinstance(args, dict):
            cleaned = {}
            for k, v in args.items():
                r = _sanitize(v)
                if r is not _DROP:
                    cleaned[k] = r
            if cleaned != args:
                try:
                    msg.arguments = cleaned
                except Exception:
                    logger.debug("LlmArgSanitizer: could not mutate message.arguments")
        return await call_next(context)
