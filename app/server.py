"""
FastAPI application wiring: routes for home page, query handling, agents listing,
and health. The heavy lifting lives in other modules to keep concerns separated.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict

from fastapi import FastAPI, HTTPException
import logging

logger = logging.getLogger(__name__)

try:
    import httpx  # type: ignore
except ImportError:
    httpx = None

from .answer import compose_final_answer
from .conversation import append_turn, get_history
from .executor import execute_plan
from .general import handle_general_query
from .file_utils import normalize_file_uploads
from .models import FrontendRequest, SupervisorResponse
from .planner import plan_tools_with_llm
from .registry import load_registry
from .web import render_home, render_agents_page, render_query_page, render_tasks_page


def build_app() -> FastAPI:
    # Basic logging setup for planner debugging; in production replace with structured logging.
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO)
    app = FastAPI(title="Supervisor Agent Demo")

    @app.get("/")
    async def home():
        return render_home()

    @app.get("/agents")
    async def view_agents():
        return render_agents_page(load_registry())

    @app.get("/query")
    async def view_query():
        return render_query_page()

    @app.get("/tasks")
    async def view_tasks():
        return render_tasks_page()

    @app.get("/api/agents")
    async def list_agents():
        return [agent.dict() for agent in load_registry()]

    @app.get("/api/tasks")
    async def list_tasks():
        if httpx is None:
            raise HTTPException(status_code=503, detail="httpx not installed to fetch tasks")
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get("http://vps.zaim-abbasi.tech/knowledge-builder/tasks")
                resp.raise_for_status()
                data = resp.json()
                tasks = data.get("tasks") if isinstance(data, dict) else data
                if not isinstance(tasks, list):
                    tasks = []
                return {"tasks": tasks, "count": len(tasks), "status": data.get("status") if isinstance(data, dict) else None}
        except httpx.HTTPStatusError as exc:
            logger.error("Tasks fetch failed with status %s", exc.response.status_code)
            raise HTTPException(status_code=502, detail="Failed to fetch tasks from knowledge base")
        except Exception as exc:
            logger.error("Tasks fetch failed: %s", exc)
            raise HTTPException(status_code=502, detail="Failed to fetch tasks from knowledge base")

    @app.post("/api/query", response_model=SupervisorResponse)
    async def handle_query(payload: FrontendRequest) -> SupervisorResponse:
        if not payload.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        registry = load_registry()
        conversation_id = payload.conversation_id or str(uuid.uuid4())
        history = get_history(conversation_id)

        # Normalize file uploads: prefer structured field, fallback to query text parsing
        structured_uploads = None
        if payload.file_uploads:
            # Convert Pydantic models to dicts for utility function
            structured_uploads = [
                {
                    'base64_data': fu.base64_data,
                    'filename': fu.filename,
                    'mime_type': fu.mime_type
                }
                for fu in payload.file_uploads
            ]
        
        query_text, file_uploads = normalize_file_uploads(structured_uploads, payload.query)
        
        # Debug: Log file uploads if present
        if file_uploads:
            logger.info(f"File uploads detected: {len(file_uploads)} file(s)")
            for i, fu in enumerate(file_uploads):
                logger.info(f"  File {i+1}: {fu.get('filename', 'unknown')} ({fu.get('mime_type', 'unknown')}), size: {len(fu.get('base64_data', ''))} chars")

        general = handle_general_query(query_text)
        if general["kind"] in {"blocked", "general"}:
            answer = general["answer"] or ""
            intermediate_results: Dict[str, str] = {}
            append_turn(conversation_id, "user", payload.query)
            append_turn(conversation_id, "assistant", answer)
            return SupervisorResponse(
                answer=answer,
                used_agents=[],
                intermediate_results=intermediate_results,
                error=None,
            )

        plan = plan_tools_with_llm(query_text, registry, history=history)

        # Normalize context values to strings to satisfy downstream agents.
        context = {
            "user_id": str(payload.user_id) if payload.user_id is not None else "anonymous",
            "conversation_id": conversation_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "file_uploads": file_uploads,  # Pass file uploads to executor
        }

        step_outputs, used_agents = await execute_plan(query_text, plan, registry, context)
        answer = compose_final_answer(payload.query, step_outputs, history=history)

        intermediate_results = {f"step_{sid}": step_outputs[sid].dict() for sid in step_outputs}

        append_turn(conversation_id, "user", payload.query)
        append_turn(conversation_id, "assistant", answer)

        return SupervisorResponse(
            answer=answer,
            used_agents=used_agents,
            intermediate_results=intermediate_results,
            error=None,
        )

    @app.get("/health")
    async def health() -> Dict[str, str]:
        return {"status": "ok", "message": "Supervisor is running"}

    return app


app = build_app()
