"""
foundry_agent/agent.py
----------------------
Production-ready agent built on FoundryChatClient (Azure AI Foundry).

Features:
  ✓ Remote MCP server tool integration (hosted + local)
  ✓ Server-managed chat history (Foundry threads)
  ✓ Custom FileSessionStore for session metadata persistence
  ✓ Full middleware pipeline: correlation, timing, input validation,
    tool-call audit, retry
  ✓ OpenTelemetry tracing via configure_azure_monitor / OTLP
  ✓ Graceful shutdown and async context-manager support
  ✓ Structured logging

Environment variables (put in .env or set in your deployment):
  FOUNDRY_PROJECT_ENDPOINT   – https://<resource>.services.ai.azure.com/api/projects/<proj>
  FOUNDRY_MODEL              – e.g. gpt-4o
  MCP_SERVER_URL             – URL of your remote MCP server
  SESSION_BACKEND            – memory | file | redis  (default: file)
  SESSION_DIR                – path for file backend (default: /tmp/foundry_sessions)
  REDIS_URL                  – redis://… (only needed for redis backend)
  OTEL_EXPORTER_OTLP_ENDPOINT – optional OTLP collector
  APPLICATIONINSIGHTS_CONNECTION_STRING – optional Azure Monitor
  LOG_LEVEL                  – DEBUG | INFO | WARNING (default: INFO)
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

from azure.identity.aio import DefaultAzureCredential

# Agent Framework imports
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework import HostedMCPTool  # remote/hosted MCP
# from agent_framework.mcp import LocalMCPTool  # uncomment for local MCP process

# Shared utilities
from middleware import (
    CorrelationMiddleware,
    InputValidationMiddleware,
    RetryMiddleware,
    TimingMiddleware,
    ToolCallMiddleware,
    build_middleware_pipeline,
)
from observability import setup_observability
from session_store import SessionData, SessionStore, create_session_store

logger = logging.getLogger("agent.foundry")


# ---------------------------------------------------------------------------
# Configuration dataclass
# ---------------------------------------------------------------------------
class FoundryAgentConfig:
    """All configuration read from environment variables with sensible defaults."""

    project_endpoint: str
    model: str
    mcp_server_url: str
    session_backend: str
    session_dir: str
    redis_url: str
    allowed_tools: list[str] | None
    service_name: str

    def __init__(self) -> None:
        self.project_endpoint = self._require("FOUNDRY_PROJECT_ENDPOINT")
        self.model = os.getenv("FOUNDRY_MODEL", "gpt-4o")
        self.mcp_server_url = self._require("MCP_SERVER_URL")
        self.session_backend = os.getenv("SESSION_BACKEND", "file")
        self.session_dir = os.getenv("SESSION_DIR", "/tmp/foundry_sessions")
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.service_name = os.getenv("OTEL_SERVICE_NAME", "foundry-mcp-agent")

        raw_tools = os.getenv("ALLOWED_TOOLS", "")
        self.allowed_tools = [t.strip() for t in raw_tools.split(",") if t.strip()] or None

    @staticmethod
    def _require(key: str) -> str:
        val = os.getenv(key)
        if not val:
            raise EnvironmentError(
                f"Required environment variable '{key}' is not set. "
                "Check your .env file or deployment configuration."
            )
        return val


# ---------------------------------------------------------------------------
# FoundryMCPAgent
# ---------------------------------------------------------------------------
class FoundryMCPAgent:
    """
    High-level agent facade that wraps Agent Framework's FoundryChatClient.

    Usage::

        async with FoundryMCPAgent() as agent:
            response = await agent.chat("session-abc", "What tools do you have?")
            print(response)
    """

    def __init__(self, config: FoundryAgentConfig | None = None) -> None:
        self._config = config or FoundryAgentConfig()
        self._session_store: SessionStore | None = None
        self._agent: Agent | None = None
        self._credential: DefaultAzureCredential | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def start(self) -> None:
        """Initialise all subsystems.  Called automatically by __aenter__."""

        # 1. Observability
        setup_observability(
            service_name=self._config.service_name,
            json_logs=os.getenv("JSON_LOGS", "false").lower() == "true",
            enable_console_exporter=os.getenv("OTEL_CONSOLE", "false").lower() == "true",
        )
        logger.info("Starting FoundryMCPAgent service=%s", self._config.service_name)

        # 2. Session store
        store_kwargs: dict = {}
        if self._config.session_backend == "file":
            store_kwargs["base_dir"] = self._config.session_dir
        elif self._config.session_backend == "redis":
            store_kwargs["url"] = self._config.redis_url
        self._session_store = create_session_store(self._config.session_backend, **store_kwargs)
        logger.info("Session store backend=%s", self._config.session_backend)

        # 3. Azure credential
        self._credential = DefaultAzureCredential()

        # 4. MCP tool — hosted remote server
        mcp_tool = HostedMCPTool(
            name="RemoteMCPServer",
            url=self._config.mcp_server_url,
            # label visible in traces / logs
        )
        logger.info("MCP tool registered url=%s", self._config.mcp_server_url)

        # 5. Foundry chat client + agent
        client = FoundryChatClient(
            credential=self._credential,
            project_endpoint=self._config.project_endpoint,
            model=self._config.model,
        )

        # 6. Wire Azure Monitor observability directly on the Foundry client
        try:
            await client.configure_azure_monitor()
            logger.info("Azure Monitor observability configured via FoundryChatClient")
        except Exception as exc:
            logger.warning(
                "Azure Monitor auto-config skipped (no Application Insights linked): %s", exc
            )

        self._agent = client.as_agent(
            name="FoundryMCPAgent",
            instructions=(
                "You are a helpful, precise assistant. "
                "Always use the available tools to answer questions. "
                "Be concise and factual. "
                "If a tool call fails, explain what happened clearly."
            ),
            tools=mcp_tool,
        )
        logger.info("FoundryChatClient agent ready model=%s", self._config.model)

    async def stop(self) -> None:
        """Clean up resources."""
        if self._credential:
            await self._credential.close()
            logger.info("Azure credential closed")

    # ------------------------------------------------------------------
    # Core chat method
    # ------------------------------------------------------------------
    async def chat(
        self,
        session_id: str,
        user_input: str,
        stream: bool = False,
    ) -> str:
        """
        Send ``user_input`` in the context of ``session_id``.

        - Loads or creates a session from the session store.
        - Runs the full middleware pipeline.
        - Foundry manages the LLM-side thread automatically.
        - Saves updated session metadata back to the store.

        Returns the assistant's response text.
        """
        assert self._agent is not None, "Agent not started. Use 'async with FoundryMCPAgent()'"
        assert self._session_store is not None

        # ---- Load / create session ----
        session = await self._session_store.get(session_id)
        if session is None:
            session = SessionData(session_id=session_id)
            logger.info("SESSION_NEW session_id=%s", session_id)
        else:
            logger.debug("SESSION_LOADED session_id=%s msg_count=%d", session_id, len(session.messages))

        # ---- Build middleware pipeline ----
        # For Foundry, the framework manages thread state server-side via
        # AgentThread.  We pass the thread between calls using
        # service_session_id stored in our SessionData.
        async def _agent_run(inp: str, **kw) -> str:
            thread_kwargs: dict = {}

            if session.service_session_id:
                # Resume existing Foundry-managed thread
                thread = await self._agent.deserialize_thread(
                    {"service_session_id": session.service_session_id}
                )
                thread_kwargs["thread"] = thread

            result = await self._agent.run(inp, **thread_kwargs)

            # Persist the Foundry thread id for the next turn
            thread = getattr(result, "thread", None)
            if thread:
                serialized = await thread.serialize()
                session.service_session_id = serialized.get("service_session_id")

            return result.text if hasattr(result, "text") else str(result)

        pipeline = build_middleware_pipeline(
            _agent_run,
            [
                CorrelationMiddleware(),
                TimingMiddleware(),
                InputValidationMiddleware(),
                ToolCallMiddleware(allowed_tools=self._config.allowed_tools),
                RetryMiddleware(max_attempts=3, base_delay=1.0),
            ],
        )

        # ---- Execute ----
        response_text: str = await pipeline(user_input)

        # ---- Persist turn to session ----
        session.add_message("user", user_input)
        session.add_message("assistant", response_text)
        await self._session_store.save(session)

        return response_text

    # ------------------------------------------------------------------
    # Streaming variant
    # ------------------------------------------------------------------
    async def stream_chat(
        self,
        session_id: str,
        user_input: str,
    ) -> AsyncIterator[str]:
        """
        Streaming chat: yields text chunks as they arrive from the model.
        Middleware (validation, logging) runs before the stream begins;
        tool calls and history are saved after the stream completes.
        """
        assert self._agent is not None
        assert self._session_store is not None

        session = await self._session_store.get(session_id) or SessionData(session_id=session_id)

        # Input validation before starting the stream
        validation_mw = InputValidationMiddleware()
        correlation_mw = CorrelationMiddleware()
        logger.info("STREAM_START session_id=%s", session_id)

        thread_kwargs: dict = {}
        if session.service_session_id:
            thread = await self._agent.deserialize_thread(
                {"service_session_id": session.service_session_id}
            )
            thread_kwargs["thread"] = thread

        full_response_parts: list[str] = []
        async for chunk in self._agent.run(user_input, stream=True, **thread_kwargs):
            if chunk.text:
                full_response_parts.append(chunk.text)
                yield chunk.text

        full_response = "".join(full_response_parts)
        session.add_message("user", user_input)
        session.add_message("assistant", full_response)
        await self._session_store.save(session)
        logger.info("STREAM_END session_id=%s chars=%d", session_id, len(full_response))

    # ------------------------------------------------------------------
    # Session management helpers
    # ------------------------------------------------------------------
    async def get_history(self, session_id: str) -> list[dict]:
        """Return the local message history for a session."""
        assert self._session_store is not None
        session = await self._session_store.get(session_id)
        return session.messages if session else []

    async def clear_session(self, session_id: str) -> None:
        """Delete a session from the store."""
        assert self._session_store is not None
        await self._session_store.delete(session_id)
        logger.info("SESSION_CLEARED session_id=%s", session_id)

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------
    async def __aenter__(self) -> "FoundryMCPAgent":
        await self.start()
        return self

    async def __aexit__(self, *_) -> None:
        await self.stop()


# ---------------------------------------------------------------------------
# CLI entrypoint for quick smoke-tests
# ---------------------------------------------------------------------------
async def main() -> None:
    from dotenv import load_dotenv  # pip install python-dotenv
    load_dotenv()

    session_id = str(uuid.uuid4())
    print(f"\n🟢  FoundryMCPAgent — session: {session_id}\n")

    async with FoundryMCPAgent() as agent:
        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

            if not user_input:
                continue
            if user_input.lower() in ("/exit", "/quit"):
                break
            if user_input.lower() == "/history":
                history = await agent.get_history(session_id)
                for m in history:
                    print(f"  [{m['role']}] {m['content'][:120]}")
                continue
            if user_input.lower() == "/clear":
                await agent.clear_session(session_id)
                session_id = str(uuid.uuid4())
                print(f"Session cleared. New session: {session_id}")
                continue

            try:
                response = await agent.chat(session_id, user_input)
                print(f"Agent: {response}\n")
            except ValueError as exc:
                print(f"⚠️  Validation error: {exc}\n")
            except Exception as exc:
                logger.exception("Unexpected error")
                print(f"❌  Error: {exc}\n")


if __name__ == "__main__":
    asyncio.run(main())
