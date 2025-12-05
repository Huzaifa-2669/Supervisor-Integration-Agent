# Project Summary

- Architecture: FastAPI backend with modular `app/` (server, planner, executor, agent caller, answer synthesis, registry, models, React UI renderer) and slim `main.py` entrypoint.
- Frontend: Chat-style React UI with multi-turn history, debug toggle, loader state, file attachment UX (name shown, cleared after send), auto-scrolling feed, and per-turn agent/intermediate visibility. UI spacing/polish improved; agents orbit visualization lives at `/agents`; tasks view linked from dashboard.
- Task views: `/api/tasks` proxy to KnowledgeBaseBuilder endpoint and `/tasks` page with card-based display, metadata chips (order, dependencies, deadlines), and client-side sorting (ID, due date, execution order).
- Task dependencies: Server rewrites dependency agent output by fetching task names from the knowledge base and returning bullet lists of execution-order tasks and tasks with dependencies instead of raw JSON.
- Routing/guardrails: Lightweight general-query handling (greetings/date/time) and abusive text refusal before planning; planner/answer LLM fallbacks allow running without OpenAI credentials; agent calls surface structured errors when endpoints/httpx missing.
- Repo hygiene: `AGENTS.md` documents practices; git initialized with `.gitignore`, remote set to `https://github.com/Huzaifa-2669/Supervisor-Integration-Agent.git`, merge history resolved.
