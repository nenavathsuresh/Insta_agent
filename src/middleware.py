"""
shared/middleware.py
--------------------
Reusable middleware pipeline: logging, tool-call validation, timing, and
error-boundary.  Works with any Agent Framework client that accepts
middleware hooks (FoundryChatClient & OpenAIChatClient both go through the
same Agent / ChatAgent wrapper, so the middleware chain is identical).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Awaitable, Callable

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

logger = logging.getLogger("agent.middleware")
tracer = trace.get_tracer("agent.middleware")

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
AgentRunFn = Callable[..., Awaitable[Any]]


# ---------------------------------------------------------------------------
# Base middleware interface
# ---------------------------------------------------------------------------
class BaseMiddleware:
    """
    Wrap an agent's ``run()`` coroutine.  Subclass and override
    ``__call__`` to add pre/post processing.
    """

    async def __call__(
        self,
        next_fn: AgentRunFn,
        user_input: str,
        **kwargs: Any,
    ) -> Any:
        return await next_fn(user_input, **kwargs)


# ---------------------------------------------------------------------------
# 1. Correlation / request-id injection
# ---------------------------------------------------------------------------
class CorrelationMiddleware(BaseMiddleware):
    """Attach a unique request-id to every run for end-to-end tracing."""

    async def __call__(
        self,
        next_fn: AgentRunFn,
        user_input: str,
        **kwargs: Any,
    ) -> Any:
        request_id = str(uuid.uuid4())
        kwargs.setdefault("metadata", {})["request_id"] = request_id
        logger.info("REQUEST_START request_id=%s input_len=%d", request_id, len(user_input))
        try:
            result = await next_fn(user_input, **kwargs)
            logger.info("REQUEST_END request_id=%s status=ok", request_id)
            return result
        except Exception as exc:
            logger.error("REQUEST_END request_id=%s status=error error=%s", request_id, exc)
            raise


# ---------------------------------------------------------------------------
# 2. Timing / latency
# ---------------------------------------------------------------------------
class TimingMiddleware(BaseMiddleware):
    """Log wall-clock latency and emit an OpenTelemetry span."""

    async def __call__(
        self,
        next_fn: AgentRunFn,
        user_input: str,
        **kwargs: Any,
    ) -> Any:
        with tracer.start_as_current_span("agent.run") as span:
            span.set_attribute("input.length", len(user_input))
            t0 = time.perf_counter()
            try:
                result = await next_fn(user_input, **kwargs)
                elapsed = time.perf_counter() - t0
                span.set_attribute("latency_ms", round(elapsed * 1000, 2))
                span.set_status(Status(StatusCode.OK))
                logger.info("TIMING latency_ms=%.2f", elapsed * 1000)
                return result
            except Exception as exc:
                elapsed = time.perf_counter() - t0
                span.set_attribute("latency_ms", round(elapsed * 1000, 2))
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                raise


# ---------------------------------------------------------------------------
# 3. Input validation
# ---------------------------------------------------------------------------
class InputValidationMiddleware(BaseMiddleware):
    """
    Reject obviously malicious or oversized inputs before they reach the LLM.
    Extend ``BLOCKED_PATTERNS`` to add domain-specific rules.
    """

    MAX_INPUT_LEN: int = 8_000
    BLOCKED_PATTERNS: list[str] = [
        "ignore previous instructions",
        "ignore all previous",
        "disregard the above",
        "act as dan",
        "<script>",
        "javascript:",
    ]

    async def __call__(
        self,
        next_fn: AgentRunFn,
        user_input: str,
        **kwargs: Any,
    ) -> Any:
        # Length guard
        if len(user_input) > self.MAX_INPUT_LEN:
            raise ValueError(
                f"Input exceeds maximum allowed length of {self.MAX_INPUT_LEN} characters."
            )

        # Prompt-injection / jailbreak guard
        lower = user_input.lower()
        for pattern in self.BLOCKED_PATTERNS:
            if pattern in lower:
                logger.warning("BLOCKED_INPUT pattern=%r", pattern)
                raise ValueError(f"Input contains a blocked pattern: '{pattern}'")

        return await next_fn(user_input, **kwargs)


# ---------------------------------------------------------------------------
# 4. Tool-call logging & validation middleware
# ---------------------------------------------------------------------------
class ToolCallMiddleware(BaseMiddleware):
    """
    Intercepts the agent result after execution to log every tool call
    that was made, validate tool names against an allow-list, and audit-log
    arguments.  Works at the *response* level because Agent Framework
    executes tool calls internally before returning.
    """

    def __init__(self, allowed_tools: list[str] | None = None) -> None:
        # None means "all tools allowed"
        self.allowed_tools: set[str] | None = set(allowed_tools) if allowed_tools else None

    async def __call__(
        self,
        next_fn: AgentRunFn,
        user_input: str,
        **kwargs: Any,
    ) -> Any:
        result = await next_fn(user_input, **kwargs)

        # Agent Framework response objects expose tool_calls on the result
        tool_calls = getattr(result, "tool_calls", None) or []
        for tc in tool_calls:
            name = getattr(tc, "name", "unknown")
            args = getattr(tc, "arguments", {})

            # Allow-list enforcement
            if self.allowed_tools and name not in self.allowed_tools:
                logger.error("TOOL_BLOCKED tool=%s", name)
                raise PermissionError(f"Tool '{name}' is not in the allowed-tools list.")

            # Audit log
            logger.info(
                "TOOL_CALL tool=%s args=%s",
                name,
                json.dumps(args, default=str)[:500],  # truncate huge payloads
            )

        return result


# ---------------------------------------------------------------------------
# 5. Retry middleware (transient error resilience)
# ---------------------------------------------------------------------------
class RetryMiddleware(BaseMiddleware):
    """
    Retries the downstream call on transient errors with exponential back-off.
    """

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        retryable_exceptions: tuple[type[Exception], ...] = (TimeoutError, ConnectionError),
    ) -> None:
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.retryable_exceptions = retryable_exceptions

    async def __call__(
        self,
        next_fn: AgentRunFn,
        user_input: str,
        **kwargs: Any,
    ) -> Any:
        last_exc: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return await next_fn(user_input, **kwargs)
            except self.retryable_exceptions as exc:
                last_exc = exc
                delay = self.base_delay * (2 ** (attempt - 1))
                logger.warning(
                    "RETRY attempt=%d/%d delay=%.1fs error=%s",
                    attempt,
                    self.max_attempts,
                    delay,
                    exc,
                )
                if attempt < self.max_attempts:
                    await asyncio.sleep(delay)
        raise RuntimeError(f"All {self.max_attempts} retry attempts failed.") from last_exc


# ---------------------------------------------------------------------------
# Middleware pipeline builder
# ---------------------------------------------------------------------------
def build_middleware_pipeline(
    base_fn: AgentRunFn,
    middlewares: list[BaseMiddleware],
) -> AgentRunFn:
    """
    Compose a list of middleware into a single callable wrapping ``base_fn``.
    First middleware in the list is outermost (runs first / last).

    Usage::

        pipeline = build_middleware_pipeline(agent.run, [
            CorrelationMiddleware(),
            TimingMiddleware(),
            InputValidationMiddleware(),
            ToolCallMiddleware(allowed_tools=["get_weather", "search"]),
            RetryMiddleware(),
        ])
        result = await pipeline("Hello!")
    """
    fn = base_fn
    for mw in reversed(middlewares):
        # Close over current fn and mw
        _mw, _fn = mw, fn

        async def _wrapped(
            user_input: str,
            *,
            _m: BaseMiddleware = _mw,
            _f: AgentRunFn = _fn,
            **kw: Any,
        ) -> Any:
            return await _m(_f, user_input, **kw)

        fn = _wrapped
    return fn
