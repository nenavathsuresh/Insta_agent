# MCP Agent — Production-Ready Client for FoundryChatClient & OpenAIChatClient

A production-grade Python implementation that connects to your MCP server
using **both** Microsoft Agent Framework clients with full middleware,
session persistence, and observability.

---

## Project Structure

```
agent_mcp/
├── shared/
│   ├── middleware.py        # Middleware pipeline (correlation, timing,
│   │                         validation, tool-call audit, retry)
│   ├── session_store.py     # Session backends: memory | file | redis
│   └── observability.py     # OpenTelemetry + structured logging bootstrap
│
├── foundry_agent/
│   └── agent.py             # FoundryMCPAgent — server-managed history,
│                              hosted MCP, Azure Monitor observability
│
├── openai_agent/
│   └── agent.py             # OpenAIMCPAgent  — client-managed history,
│                              local/SSE MCP, pluggable OTLP observability
│
├── server.py                # FastAPI REST API exposing both agents
├── requirements.txt
└── .env.example             # Copy to .env and fill in
```

---

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env        # then edit .env with your credentials

# CLI — FoundryMCPAgent
python -m foundry_agent.agent

# CLI — OpenAIMCPAgent
python -m openai_agent.agent

# REST API (both agents)
uvicorn server:app --reload --port 8000
```

---

## Feature Matrix

| Feature                        | FoundryChatClient          | OpenAIChatClient            |
|-------------------------------|----------------------------|-----------------------------|
| MCP tool type                 | Hosted (remote, portal)    | Local subprocess / SSE      |
| Chat history location         | Server-side (Foundry)      | Client-side (SessionStore)  |
| Session store                 | FileSessionStore (metadata)| In/File/Redis (full history)|
| Middleware pipeline           | ✅ Full                    | ✅ Full                     |
| Observability                 | Azure Monitor + OTel       | OTLP / Console / Azure      |
| Streaming                     | ✅                         | ✅                          |
| History reducer               | Service-managed            | Max N messages              |
| Allowed-tools enforcement     | ✅                         | ✅                          |
| Retry on transient errors     | ✅ (3×, exp back-off)      | ✅ (3×, exp back-off)       |

---

## Middleware Pipeline (both clients)

```
Request
  │
  ▼
CorrelationMiddleware    ← injects unique request_id
  │
  ▼
TimingMiddleware         ← wall-clock latency + OTel span
  │
  ▼
InputValidationMiddleware← length guard + prompt-injection patterns
  │
  ▼
ToolCallMiddleware       ← allow-list enforcement + audit logging
  │
  ▼
RetryMiddleware          ← 3 attempts, exponential back-off
  │
  ▼
Agent.run()              ← actual LLM + MCP tool execution
```

---

## Session Backends

| Backend  | Use case                            | Config                         |
|----------|-------------------------------------|--------------------------------|
| `memory` | Development / unit tests            | `SESSION_BACKEND=memory`       |
| `file`   | Single-instance, no extra service   | `SESSION_BACKEND=file`         |
| `redis`  | Multi-instance production           | `SESSION_BACKEND=redis`        |

---

## REST API Endpoints

| Method | Path                   | Description                        |
|--------|------------------------|------------------------------------|
| POST   | `/foundry/chat`        | Single-turn chat (Foundry)         |
| POST   | `/foundry/stream`      | SSE streaming (Foundry)            |
| GET    | `/foundry/history`     | Fetch session history              |
| DELETE | `/foundry/session`     | Clear a session                    |
| POST   | `/openai/chat`         | Single-turn chat (OpenAI)          |
| POST   | `/openai/stream`       | SSE streaming (OpenAI)             |
| GET    | `/openai/history`      | Fetch session history              |
| DELETE | `/openai/session`      | Clear a session                    |
| GET    | `/health`              | Liveness probe                     |

### Example request

```bash
curl -X POST http://localhost:8000/openai/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "user-123", "message": "What tools do you have?"}'
```

---

## Observability

- **Azure AI Foundry** (with `FoundryChatClient`): call `client.configure_azure_monitor()`
  to auto-wire Application Insights — traces appear in the Foundry portal dashboard.
- **OTLP** (both clients): set `OTEL_EXPORTER_OTLP_ENDPOINT` to send to
  Jaeger, Grafana Tempo, Datadog, etc.
- **Console** (development): set `OTEL_CONSOLE=true`.

Every `agent.run()` generates:
- A trace span with input length and latency
- Tool-call audit log entries (name + truncated args)
- Correlation request-id propagated through all log lines
