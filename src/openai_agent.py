"""
openai_agent/agent.py
---------------------
Production-ready agent built on OpenAIChatClient (direct OpenAI / Azure OpenAI).

Features:
  ✓ Local MCP server tool integration via stdio/SSE process
  ✓ Client-managed chat history with pluggable session store
  ✓ Full middleware pipeline: correlation, timing, input validation,
    tool-call audit, retry
  ✓ OpenTelemetry tracing via OTLP or Azure Monitor
  ✓ InMemoryChatHistoryProvider with configurable message-count reducer
  ✓ Graceful shutdown and async context-manager support
  ✓ Structured logging

Environment variables:
  OPENAI_API_KEY             – your OpenAI key  (or use Azure routing below)
  OPENAI_MODEL               – e.g. gpt-4o-mini  (default: gpt-4o-mini)
  ── Azure OpenAI (optional, takes priority when set) ──────────────────────
  AZURE_OPENAI_ENDPOINT      – https://<resource>.openai.azure.com
  AZURE_OPENAI_CHAT_MODEL    – deployment name
  AZURE_OPENAI_API_VERSION   – e.g. 2025-01-01-preview
  ── MCP ───────────────────────────────────────────────────────────────────
  MCP_SERVER_COMMAND         – command to launch MCP server, e.g. "python mcp_server.py"
                               OR
  MCP_SERVER_URL             – SSE endpoint for a running MCP server
  ── Session ───────────────────────────────────────────────────────────────
  SESSION_BACKEND            – memory | file | redis  (default: memory)
  SESSION_DIR                – path for file backend
  REDIS_URL                  – redis://…
  MAX_HISTORY_MESSAGES       – rolling window size  (default: 40)
  ── Observability ─────────────────────────────────────────────────────────
  OTEL_EXPORTER_OTLP_ENDPOINT
  APPLICATIONINSIGHTS_CONNECTION_STRING
  LOG_LEVEL
"""

from __future__ import annotations

import asyncio
import logging
import os
import shlex
import uuid
from pathlib import Path
from typing import AsyncIterator

# Agent Framework imports
from agent_framework import (
    Agent,
    AgentSession,
    InMemoryHistoryProvider,
    MCPStdioTool,
    MCPStreamableHTTPTool,
    SlidingWindowStrategy,
)
from agent_framework.openai import OpenAIChatClient

# Shared utilities
try:
    from .middleware import (
        CorrelationMiddleware,
        InputValidationMiddleware,
        RetryMiddleware,
        TimingMiddleware,
        ToolCallMiddleware,
        build_middleware_pipeline,
    )
    from .observability import setup_observability
    from .session_store import SessionData, SessionStore, create_session_store
except ImportError:
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

logger = logging.getLogger("agent.openai")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
class OpenAIAgentConfig:
    """All config from env vars."""

    openai_api_key: str | None
    azure_api_key: str | None
    model: str
    azure_endpoint: str | None
    azure_api_version: str | None

    mcp_server_command: str | None 
    mcp_server_url: str | None 

    session_backend: str
    session_dir: str
    redis_url: str
    max_history_messages: int
    allowed_tools: list[str] | None
    service_name: str

    def __init__(self) -> None:
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.azure_api_key = os.getenv("AZURE_OPENAI_API_KEY") or self.openai_api_key
        self.model = os.getenv(
            "AZURE_OPENAI_CHAT_MODEL",
            os.getenv("OPENAI_MODEL", "gpt-4o"),
        )
        self.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "v1")

        self.mcp_server_command = os.getenv("MCP_SERVER_COMMAND") or self._default_mcp_server_command()
        self.mcp_server_url = os.getenv("MCP_SERVER_URL")

        if not self.mcp_server_command and not self.mcp_server_url:
            raise EnvironmentError(
                "Set either MCP_SERVER_COMMAND (subprocess) or MCP_SERVER_URL (SSE) "
                "to specify your MCP server."
            )

        self.session_backend = os.getenv("SESSION_BACKEND", "memory")
        self.session_dir = os.getenv("SESSION_DIR", "/tmp/openai_sessions")
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.max_history_messages = int(os.getenv("MAX_HISTORY_MESSAGES", "40"))
        self.service_name = os.getenv("OTEL_SERVICE_NAME", "openai-mcp-agent")

        raw_tools = os.getenv("ALLOWED_TOOLS", "")
        self.allowed_tools = [t.strip() for t in raw_tools.split(",") if t.strip()] or None

    @staticmethod
    def _default_mcp_server_command() -> str | None:
        """Auto-detect the local FastMCP server entrypoint for local development."""
        for parent in Path(__file__).resolve().parents:
            candidate = parent / "main.py"
            if candidate.exists():
                return f'"{os.sys.executable}" "{candidate}"'
        return None


# ---------------------------------------------------------------------------
# OpenAI MCP Agent
# ---------------------------------------------------------------------------
class OpenAIMCPAgent:
    """
    High-level agent facade using OpenAIChatClient.

    Unlike FoundryMCPAgent, this agent manages chat history **client-side**:
    every conversation turn is stored in the SessionStore and re-injected into
    the model via InMemoryHistoryProvider.

    Usage::

        async with OpenAIMCPAgent() as agent:
            response = await agent.chat("session-abc", "List available tools")
            print(response)
    """

    def __init__(self, config: OpenAIAgentConfig | None = None) -> None:
        self._config = config or OpenAIAgentConfig()
        self._session_store: SessionStore | None = None
        self._agent: Agent | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def start(self) -> None:
        """Initialise all subsystems."""

        # 1. Observability
        setup_observability(
            service_name=self._config.service_name,
            json_logs=os.getenv("JSON_LOGS", "false").lower() == "true",
            enable_console_exporter=os.getenv("OTEL_CONSOLE", "false").lower() == "true",
        )
        logger.info("Starting OpenAIMCPAgent service=%s", self._config.service_name)

        # 2. Session store
        store_kwargs: dict = {}
        if self._config.session_backend == "file":
            store_kwargs["base_dir"] = self._config.session_dir
        elif self._config.session_backend == "redis":
            store_kwargs["url"] = self._config.redis_url
        self._session_store = create_session_store(self._config.session_backend, **store_kwargs)
        logger.info("Session store backend=%s", self._config.session_backend)

        # 3. MCP tool
        mcp_tool = self._build_mcp_tool()

        # 4. OpenAI chat client
        client_kwargs: dict = {"model": self._config.model}
        if self._config.azure_endpoint:
            # Azure OpenAI routing
            if self._config.azure_api_key:
                client_kwargs["base_url"] = (
                    f"{self._config.azure_endpoint.rstrip('/')}/openai/v1/"
                )
                client_kwargs["api_key"] = self._config.azure_api_key
                logger.info(
                    "Using Azure OpenAI base_url=%s with API key auth",
                    client_kwargs["base_url"],
                )
            else:
                from azure.identity.aio import DefaultAzureCredential  # type: ignore

                client_kwargs["azure_endpoint"] = self._config.azure_endpoint
                client_kwargs["api_version"] = self._config.azure_api_version
                client_kwargs["credential"] = DefaultAzureCredential()
                logger.info(
                    "Using Azure OpenAI endpoint=%s with DefaultAzureCredential api_version=%s",
                    self._config.azure_endpoint,
                    self._config.azure_api_version,
                )
        else:
            if not self._config.openai_api_key:
                raise EnvironmentError("OPENAI_API_KEY must be set for direct OpenAI access.")
            client_kwargs["api_key"] = self._config.openai_api_key
            logger.info("Using OpenAI API model=%s", self._config.model)

        client = OpenAIChatClient(**client_kwargs)

        # 5. History provider with rolling-window reducer
        history_provider = InMemoryHistoryProvider(
            "chat_history",
            load_messages=True,
        )

        # 6. Assemble agent
        self._agent = client.as_agent(
            name="OpenAIMCPAgent",
            instructions=(
                "You are a helpful, precise assistant. "
                "Always use the available tools to answer questions. "
                "Be concise and factual. "
                "If a tool call fails, explain what happened clearly."
            ),
            tools=mcp_tool,
            context_providers=[history_provider],
            compaction_strategy=SlidingWindowStrategy(
                keep_last_groups=self._config.max_history_messages
            ),
        )
        logger.info("OpenAIChatClient agent ready model=%s", self._config.model)

    def _build_mcp_tool(self):
        """Return the appropriate MCP tool based on config."""
        if self._config.mcp_server_url:
            logger.info("MCP via SSE url=%s", self._config.mcp_server_url)
            return MCPStreamableHTTPTool(url=self._config.mcp_server_url, name="MCPServer")

        if self._config.mcp_server_command:
            cmd_parts = shlex.split(self._config.mcp_server_command, posix=os.name != "nt")
            logger.info("MCP via subprocess command=%s", cmd_parts)
            return MCPStdioTool(
                command=cmd_parts[0],
                args=cmd_parts[1:],
                name="MCPServer",
                env=dict(os.environ),
            )

        raise EnvironmentError("No MCP server configured.")

    async def stop(self) -> None:
        """Clean up resources."""
        logger.info("OpenAIMCPAgent shutting down")

    def _restore_agent_session(self, session: SessionData) -> AgentSession:
        """Rehydrate the framework-native session from persisted metadata."""
        serialized_session = session.metadata.get("agent_session")
        if isinstance(serialized_session, dict):
            return AgentSession.from_dict(serialized_session)

        if session.service_session_id:
            return self._agent.get_session(  # type: ignore[union-attr]
                session.service_session_id,
                session_id=session.session_id,
            )

        return self._agent.create_session(session_id=session.session_id)  # type: ignore[union-attr]

    def _persist_agent_session(self, session: SessionData, agent_session: AgentSession) -> None:
        """Persist the framework-native session for the next turn."""
        session.service_session_id = agent_session.service_session_id
        session.metadata["agent_session"] = agent_session.to_dict()

    # ------------------------------------------------------------------
    # Core chat method
    # ------------------------------------------------------------------
    async def chat(
        self,
        session_id: str,
        user_input: str,
    ) -> str:
        """
        Send ``user_input`` in the context of ``session_id``.

        Chat history is loaded from the session store, injected into the
        model via InMemoryHistoryProvider, and then the updated history is
        saved back after the response.
        """
        assert self._agent is not None, "Agent not started. Use 'async with OpenAIMCPAgent()'"
        assert self._session_store is not None

        # ---- Load / create session ----
        session = await self._session_store.get(session_id)
        if session is None:
            session = SessionData(session_id=session_id)
            logger.info("SESSION_NEW session_id=%s", session_id)
        else:
            logger.debug("SESSION_LOADED session_id=%s msg_count=%d", session_id, len(session.messages))

        agent_session = self._restore_agent_session(session)

        # ---- Build middleware pipeline ----
        async def _agent_run(inp: str, **kw) -> str:
            result = await self._agent.run(inp, session=agent_session)
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

        # ---- Persist turn ----
        session.add_message("user", user_input)
        session.add_message("assistant", response_text)
        self._persist_agent_session(session, agent_session)
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
        """Yield response chunks as they stream from the model."""
        assert self._agent is not None
        assert self._session_store is not None

        session = await self._session_store.get(session_id) or SessionData(session_id=session_id)

        agent_session = self._restore_agent_session(session)

        # Validate input before streaming
        validation = InputValidationMiddleware()
        await validation(lambda x, **kw: asyncio.sleep(0), user_input)  # raises on bad input

        logger.info("STREAM_START session_id=%s", session_id)
        full_parts: list[str] = []

        async for chunk in self._agent.run(user_input, stream=True, session=agent_session):
            if chunk.text:
                full_parts.append(chunk.text)
                yield chunk.text

        full_response = "".join(full_parts)
        session.add_message("user", user_input)
        session.add_message("assistant", full_response)
        self._persist_agent_session(session, agent_session)
        await self._session_store.save(session)

        logger.info("STREAM_END session_id=%s chars=%d", session_id, len(full_response))

    # ------------------------------------------------------------------
    # Session helpers
    # ------------------------------------------------------------------
    async def get_history(self, session_id: str) -> list[dict]:
        assert self._session_store is not None
        session = await self._session_store.get(session_id)
        return session.messages if session else []

    async def clear_session(self, session_id: str) -> None:
        assert self._session_store is not None
        await self._session_store.delete(session_id)
        logger.info("SESSION_CLEARED session_id=%s", session_id)

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------
    async def __aenter__(self) -> "OpenAIMCPAgent":
        await self.start()
        return self

    async def __aexit__(self, *_) -> None:
        await self.stop()


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------
async def main() -> None:
    from dotenv import load_dotenv
    load_dotenv()

    session_id = str(uuid.uuid4())
    print(f"\n🟢  OpenAIMCPAgent — session: {session_id}\n")

    async with OpenAIMCPAgent() as agent:
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
