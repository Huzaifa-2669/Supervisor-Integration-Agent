# Supervisor Multi-Agent Web App

A FastAPI + React demo where a supervisor LLM plans and orchestrates worker agents, combines their outputs, and returns a unified answer. Conversation history is summarized before use, and multi-intent queries are handled by running multiple agents then LLM-combining the results.

## Why this project exists
- Users often ask for more than one action in a single query (e.g., prioritize emails and check deadline risks). We detect multi-intent cases, run the needed agents, and synthesize a combined answer instead of stopping after the first tool.
- Conversations can get long; we auto-summarize recent turns and pass the summary instead of the full transcript to keep context lean.
- The UI surfaces agent calls and intermediate payloads so you can see what happened behind the scenes.

## Capabilities
- LLM planner with heuristics + OpenRouter fallback to select agents and intents.
- Multi-agent execution: when multiple distinct agents are planned, all are called and an LLM combines their outputs; partial failures are noted.
- History summarization before planning/answering; summary is also forwarded to agents via context.
- Agent registry with HTTP endpoints, timeouts, and health checks.
- Debuggable UI: chat view, agent timeline, intermediate payloads, file attachment support, and a badge on combined multi-agent answers.
- Task visualizations: `/agents` orbit view and `/tasks` dashboard (pulls from KnowledgeBaseBuilder backend).

## Architecture (high level)
- Backend: FastAPI (see `main.py`, `app/server.py`), modular app package (`planner`, `executor`, `agent_caller`, `answer`, `combine`, `registry`, `models`, `web`).
- Frontend: React via CDN, served from `/` (see `app/web.py`).
- LLM: OpenRouter API (default model `google/gemini-2.5-flash-lite`) via `OPENROUTER_API_KEY`.
- Data: in-memory conversation history and registry; no DB required for supervisor.

## Data contracts
- Frontend → Supervisor (`POST /api/query`): `{ query, user_id?, conversation_id?, options { debug }, file_uploads? }`.
- Supervisor → Worker: `{ request_id, agent_name, intent, input { text, metadata }, context { user_id, conversation_id, timestamp, history_summary, file_uploads? } }`.
- Worker → Supervisor success: `{ status: "success", output { result, confidence?, details? }, error: null }`; error mirrors shape.
- Supervisor → Frontend: `{ answer, used_agents[{ name, intent, status }], intermediate_results { step_n: full worker response }, error }`.

## Running the app

### Prerequisites
- Python 3.10+ (ensure `python`/`pip` are available)
- Recommended: virtual environment

### Install dependencies
```bash
pip install -r requirements.txt
```

### Configure environment
Set your OpenRouter key (and optional model override):
```bash
export OPENROUTER_API_KEY="sk-or-v1-your-api-key"
export OPENROUTER_MODEL="google/gemini-2.5-flash-lite"  # optional
```

### Start the server
```bash
uvicorn main:app --reload
```
Open http://localhost:8000/ for the chat UI. Debug toggle shows agent calls and payloads; `/agents` lists the registry; `/tasks` shows the knowledge-base tasks view.

## How it works (flow)
1) Receive user query + optional files.  
2) Summarize recent conversation turns.  
3) Planner selects plan steps (heuristics first, then LLM if needed).  
4) Executor runs each agent step, capturing outputs and structured errors.  
5) If multiple distinct agents ran, an LLM combines their outputs; otherwise standard answer synthesis runs.  
6) Response returns answer, used agents, and intermediate payloads to the UI.

## Notes for developers
- Add agents in `app/registry.py` (name, intents, endpoint, timeout).  
- Planner lives in `app/planner.py` (heuristics + OpenRouter).  
- Agent calls and error handling live in `app/agent_caller.py`.  
- Multi-agent combining is in `app/combine.py`; executor wires it in.  
- History summarization is in `app/history.py`.  
- UI tweaks live in `app/web.py`.

## Testing
- Preferred: `pytest` (see `tests/` for planner and dependency formatting tests).  
- You can monkeypatch `call_agent`/`plan_tools_with_llm` in tests to avoid live calls.

## Setup and Running

### 1. Install Dependencies

```bash
pip install fastapi uvicorn openai httpx
```

### 2. Configure Environment Variables

Copy the example environment file and add your API key:

```bash
cp .env.example .env
```

Edit `.env` and set your OpenRouter API key:

```
OPENROUTER_API_KEY=sk-or-v1-your-api-key-here
OPENROUTER_MODEL=google/gemini-2.5-flash-lite
```

Get your OpenRouter API key from: https://openrouter.ai/keys

### 3. Run the Application

```bash
uvicorn main:app --reload
```

Open http://localhost:8000/ in your browser.

### 4. Alternative: Export Environment Variables Directly

```bash
export OPENROUTER_API_KEY="your-api-key-here"
uvicorn main:app --reload
```

## Running Screenshot

<img width="2058" height="3168" alt="Supervisor Frontend" src="https://github.com/user-attachments/assets/f879d1ba-9cc2-49fe-8825-cbeba037e25c" />
