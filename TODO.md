# TODO (aligned with PLAN.md)

## Planner & Scope Control
- Harden LLM planner JSON parsing/validation; enforce registry agent/intents and return empty plans on parse/safety failure.
- Expand deterministic heuristics coverage and add unit tests for out-of-scope handling.

## Execution & Contracts
- Add structured request/step logging (request_id, conversation_id, agent, intent, status, latency).
- Classify HTTP errors consistently (http_error, network_error, config_error) with PII redaction.
- Add size limits on query/payload and guardrails on output length before rendering.
- Harden file uploads: validate MIME/size, strip dangerous content, and ensure base64 payloads are bounded before forwarding to agents.

## Conversation Memory
- Add TTL/size limits to in-memory history; design a Redis/DB-backed store for multi-instance deployment.

## Observability & Health
- Add supervisor `/health` enrichments and optional worker health checks surfaced in UI.
- Add metrics hooks (request rate, planner failures, agent call success/error, latency percentiles).

## Security & Config
- Provide `.env.example` and config docs (OPENAI_API_KEY, timeouts, CORS, log level, file upload limits).
- Enforce CORS allowlist and HTTPS assumptions for production.

## Testing
- Unit: planner heuristics/LLM fallback, agent_caller error paths, executor input resolution, file upload validation.
- Integration: `/api/query` flow with monkeypatched planner/agent_caller; include KnowledgeBaseBuilderAgent path and file upload paths.
- UI smoke tests (dashboard render, agent list, query submit with mocked API).

## Frontend/UX
- Add explicit “choose agent” path alongside free-form queries; keep accessibility (labels/focus).
- Improve debug panel and loading states per agent call; show per-call errors.
- Add file upload UX polish (progress/validation messaging) and render markdown results safely.

## Tooling & Delivery
- Add `.gitignore` (e.g., `__pycache__`, `node_modules`, env files) and formatting/lint targets (ruff/black).
- Add CI (GitHub Actions) to run lint/tests; add Dockerfile and run docs.

## Registry
- Keep current agent names/endpoints; add health status visualization and timeout tuning per agent.
