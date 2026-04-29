"""
shared/session_store.py
-----------------------
Pluggable session / chat-history storage layer.

Provides three backends:
  - InMemorySessionStore  – dev / testing
  - RedisSessionStore     – production (requires ``redis`` package)
  - FileSessionStore      – lightweight persistence without extra services

All stores implement ``SessionStore`` protocol so you can swap them without
touching agent code.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("agent.session")


def _json_safe(value: Any) -> Any:
    """Convert SDK/model objects into plain JSON-compatible values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _json_safe(model_dump(mode="json"))

    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _json_safe(to_dict())

    return str(value)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class SessionData:
    session_id: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # For Foundry-backed agents the remote thread/conversation id is stored here
    service_session_id: str | None = None

    def add_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content, "ts": time.time()})
        # Keep only the last 3 messages
        if len(self.messages) > 3:
            self.messages = self.messages[-3:]
        self.updated_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        return _json_safe({
            "session_id": self.session_id,
            "messages": self.messages,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "service_session_id": self.service_session_id,
        })

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionData":
        obj = cls(session_id=data["session_id"])
        obj.messages = data.get("messages", [])
        obj.metadata = data.get("metadata", {})
        obj.created_at = data.get("created_at", time.time())
        obj.updated_at = data.get("updated_at", time.time())
        obj.service_session_id = data.get("service_session_id")
        return obj


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------
class SessionStore(ABC):
    @abstractmethod
    async def get(self, session_id: str) -> SessionData | None: ...

    @abstractmethod
    async def save(self, session: SessionData) -> None: ...

    @abstractmethod
    async def delete(self, session_id: str) -> None: ...

    @abstractmethod
    async def list_sessions(self) -> list[str]: ...


# ---------------------------------------------------------------------------
# 1. In-memory (development / unit tests)
# ---------------------------------------------------------------------------
class InMemorySessionStore(SessionStore):
    """Thread-safe in-process store backed by a plain dict + asyncio.Lock."""

    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._store: dict[str, SessionData] = {}
        self._lock = asyncio.Lock()
        self._ttl = ttl_seconds

    async def get(self, session_id: str) -> SessionData | None:
        async with self._lock:
            session = self._store.get(session_id)
            if session is None:
                return None
            # TTL eviction
            if time.time() - session.updated_at > self._ttl:
                del self._store[session_id]
                logger.debug("SESSION_EXPIRED session_id=%s", session_id)
                return None
            return session

    async def save(self, session: SessionData) -> None:
        async with self._lock:
            session.updated_at = time.time()
            self._store[session.session_id] = session
            logger.debug("SESSION_SAVED session_id=%s msg_count=%d", session.session_id, len(session.messages))

    async def delete(self, session_id: str) -> None:
        async with self._lock:
            self._store.pop(session_id, None)

    async def list_sessions(self) -> list[str]:
        async with self._lock:
            return list(self._store.keys())


# ---------------------------------------------------------------------------
# 2. File-based (lightweight persistence, no extra service needed)
# ---------------------------------------------------------------------------
class FileSessionStore(SessionStore):
    """Persist each session as a JSON file under ``base_dir``."""

    def __init__(self, base_dir: str = "/tmp/agent_sessions", ttl_seconds: int = 86400) -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)
        self._ttl = ttl_seconds
        self._lock = asyncio.Lock()

    def _path(self, session_id: str) -> Path:
        # Sanitise id to safe filename
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)
        return self._base / f"{safe}.json"

    async def get(self, session_id: str) -> SessionData | None:
        async with self._lock:
            p = self._path(session_id)
            if not p.exists():
                return None
            data = json.loads(p.read_text())
            session = SessionData.from_dict(data)
            if time.time() - session.updated_at > self._ttl:
                p.unlink(missing_ok=True)
                return None
            return session

    async def save(self, session: SessionData) -> None:
        async with self._lock:
            session.updated_at = time.time()
            self._path(session.session_id).write_text(json.dumps(session.to_dict(), indent=2))

    async def delete(self, session_id: str) -> None:
        async with self._lock:
            self._path(session_id).unlink(missing_ok=True)

    async def list_sessions(self) -> list[str]:
        return [p.stem for p in self._base.glob("*.json")]


# ---------------------------------------------------------------------------
# 3. Redis (production)
# ---------------------------------------------------------------------------
class RedisSessionStore(SessionStore):
    """
    Redis-backed store.  Requires ``redis[asyncio]`` to be installed:
        pip install redis[asyncio]
    """

    def __init__(
        self,
        url: str = "redis://localhost:6379",
        ttl_seconds: int = 3600,
        key_prefix: str = "agent:session:",
    ) -> None:
        try:
            import redis.asyncio as aioredis  # type: ignore
        except ImportError as exc:
            raise ImportError("Install 'redis[asyncio]' to use RedisSessionStore.") from exc

        self._redis = aioredis.from_url(url, decode_responses=True)
        self._ttl = ttl_seconds
        self._prefix = key_prefix

    def _key(self, session_id: str) -> str:
        return f"{self._prefix}{session_id}"

    async def get(self, session_id: str) -> SessionData | None:
        raw = await self._redis.get(self._key(session_id))
        if raw is None:
            return None
        return SessionData.from_dict(json.loads(raw))

    async def save(self, session: SessionData) -> None:
        session.updated_at = time.time()
        await self._redis.setex(
            self._key(session.session_id),
            self._ttl,
            json.dumps(session.to_dict()),
        )

    async def delete(self, session_id: str) -> None:
        await self._redis.delete(self._key(session_id))

    async def list_sessions(self) -> list[str]:
        keys = await self._redis.keys(f"{self._prefix}*")
        return [k[len(self._prefix):] for k in keys]


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------
def create_session_store(backend: str = "memory", **kwargs: Any) -> SessionStore:
    """
    Factory.  ``backend`` choices: "memory" | "file" | "redis".

    Examples::

        store = create_session_store("memory", ttl_seconds=1800)
        store = create_session_store("file", base_dir="/var/agent_sessions")
        store = create_session_store("redis", url="redis://myhost:6379")
    """
    match backend.lower():
        case "memory":
            return InMemorySessionStore(**kwargs)
        case "file":
            return FileSessionStore(**kwargs)
        case "redis":
            return RedisSessionStore(**kwargs)
        case _:
            raise ValueError(f"Unknown session backend: {backend!r}. Choose memory | file | redis")
