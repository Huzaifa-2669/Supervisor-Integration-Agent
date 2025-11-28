"""
Agent caller abstraction. Supports HTTP calls when configured, and otherwise
simulates responses so the end-to-end supervisor flow still works offline.
"""
from __future__ import annotations

from typing import Any, Dict
import uuid

try:
    import httpx  # type: ignore
except ImportError:
    httpx = None

from .models import AgentMetadata, AgentRequest, AgentResponse, ErrorModel, OutputModel


async def call_agent(
    agent_meta: AgentMetadata,
    intent: str,
    text: str,
    context: Dict[str, Any],
) -> AgentResponse:
    """
    Build handshake request and invoke the worker. When endpoints are not real,
    we fall back to simulated results that mirror the contract.
    """

    request_id = str(uuid.uuid4())
    handshake = AgentRequest(
        request_id=request_id,
        agent_name=agent_meta.name,
        intent=intent,
        input={"text": text, "metadata": {"language": "en", "extra": {}}},
        context=context,
    )

    if agent_meta.type == "http" and agent_meta.endpoint and httpx is not None:
        try:
            async with httpx.AsyncClient(timeout=agent_meta.timeout_ms / 1000) as client:
                resp = await client.post(agent_meta.endpoint, json=handshake.dict())
                if resp.status_code != 200:
                    return AgentResponse(
                        request_id=request_id,
                        agent_name=agent_meta.name,
                        status="error",
                        error=ErrorModel(
                            type="http_error",
                            message=f"HTTP {resp.status_code} calling {agent_meta.endpoint}",
                        ),
                    )
                return AgentResponse(**resp.json())
        except Exception as exc:
            return AgentResponse(
                request_id=request_id,
                agent_name=agent_meta.name,
                status="error",
                error=ErrorModel(type="network_error", message=str(exc)),
            )

    simulated_output = simulate_agent_output(agent_meta.name, text)
    return AgentResponse(
        request_id=request_id,
        agent_name=agent_meta.name,
        status="success",
        output=OutputModel(**simulated_output),
    )


def simulate_agent_output(agent_name: str, text: str) -> Dict[str, Any]:
    """Lightweight simulations for demo purposes."""
    if agent_name == "document_summarizer_agent":
        return {
            "result": f"Summary: {text[:150]}...",
            "confidence": 0.92,
            "details": "Simulated concise summary",
        }
    if agent_name == "deadline_guardian_agent":
        return {
            "result": "No immediate risks. Next check in 3 days.",
            "confidence": 0.85,
            "details": "Based on provided dates and milestones",
        }
    if agent_name == "email_priority_agent":
        return {
            "result": "High priority if sender is leadership; otherwise medium.",
            "confidence": 0.7,
            "details": "Heuristic priority assessment",
        }
    if agent_name == "meeting_followup_agent":
        return {
            "result": "Actions: share minutes, schedule retro, assign owners.",
            "confidence": 0.9,
            "details": "Generated follow-up checklist",
        }
    if agent_name == "progress_accountability_agent":
        return {
            "result": "2/3 goals on track; consider daily standups for momentum.",
            "confidence": 0.8,
            "details": "Progress check against stated goals",
        }
    if agent_name == "onboarding_buddy_agent":
        return {
            "result": "Complete security training, meet mentor, ship first PR.",
            "confidence": 0.88,
            "details": "Onboarding next steps",
        }
    if agent_name == "KnowledgeBaseBuilderAgent":
        return {
            "result": "Task created successfully",
            "confidence": 0.95,
            "details": {
                "task_id": "AUTO-GEN-001",
                "task_name": "Parsed from input",
                "task_status": "todo",
            },
        }
    if agent_name == "task_dependency_agent":
        return {
            "result": "Task B depends on Task A; unblock by clarifying API spec.",
            "confidence": 0.82,
            "details": "Dependency graph check",
        }
    return {"result": f"Processed by {agent_name}", "confidence": 0.5}
