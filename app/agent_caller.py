"""
Agent caller abstraction. Currently supports real HTTP calls only; if an agent
is not reachable or misconfigured we return a structured error instead of
simulating output. This keeps execution transparent for observability and
alignment with production behavior.
"""
from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict

try:
    import httpx  # type: ignore
except ImportError:
    httpx = None

from .models import AgentMetadata, AgentRequest, AgentResponse, ErrorModel, OutputModel


PROGRESS_AGENT_INTENT_MAP = {
    "progress.track": "accountability",
    "progress.accountability": "accountability",
    "goal.create": "freeform_message",  # Use freeform for natural language goal creation
    "goal.update": "goal",
    "reflection.add": "freeform_message",
    "reflection.analyze": "analyze_reflections",
    "productivity.report": "generate_report",
    "productivity.insights": "get_insights",
    "productivity.freeform": "freeform_message",
}


def format_accountability_response(data: dict) -> str:
    """Format accountability payload into human-readable text."""
    lines = []
    
    # Header
    generated_at = data.get("generated_at", "")
    if generated_at:
        lines.append(f"Accountability Report (Generated: {generated_at})")
        lines.append("-" * 50)
    
    # User info
    user_id = data.get("user_id", "anonymous")
    lines.append(f"User: {user_id}")
    lines.append("")
    
    # Performance Metrics
    metrics = data.get("performance_metrics", {})
    if isinstance(metrics, dict):
        if metrics.get("message"):
            lines.append(f"Performance: {metrics['message']}")
        else:
            lines.append("Performance Metrics:")
            lines.append(f"  - Total Goals: {metrics.get('total_goals', 0)}")
            lines.append(f"  - Completed: {metrics.get('completed_goals', 0)}")
            lines.append(f"  - In Progress: {metrics.get('in_progress_goals', 0)}")
            lines.append(f"  - Missed: {metrics.get('missed_goals', 0)}")
            lines.append(f"  - Completion Rate: {metrics.get('completion_rate', 0):.1%}")
            lines.append(f"  - Productivity Trend: {metrics.get('productivity_trend', 'N/A')}")
    lines.append("")
    
    # Goal Risks
    goal_risks = data.get("goal_risks", {})
    if goal_risks:
        lines.append("Goal Risks:")
        for goal_id, risk_info in goal_risks.items():
            risk_level = risk_info.get("risk", "unknown")
            days = risk_info.get("days_to_deadline", "?")
            eta = risk_info.get("eta", "N/A")
            lines.append(f"  - Goal {goal_id[:8]}...: {risk_level.upper()} risk ({days} days to deadline, ETA: {eta})")
    else:
        lines.append("Goal Risks: None")
    lines.append("")
    
    # Reflection Summary
    reflection = data.get("reflection_summary", {})
    if isinstance(reflection, dict):
        if reflection.get("message"):
            lines.append(f"Reflections: {reflection['message']}")
        else:
            lines.append("Reflection Summary: Available")
    
    return "\n".join(lines)


def format_goal_created_response(data: dict) -> str:
    """Format goal creation response into readable text."""
    lines = []
    lines.append("Goal Created Successfully!")
    lines.append("-" * 30)
    
    goal_id = data.get("goal_id", "unknown")
    lines.append(f"Goal ID: {goal_id}")
    
    used_data = data.get("used_data", {})
    if used_data:
        lines.append(f"Title: {used_data.get('title', 'N/A')}")
        lines.append(f"Category: {used_data.get('category', 'N/A')}")
        lines.append(f"Type: {used_data.get('goal_type', 'N/A')}")
        lines.append(f"Deadline: {used_data.get('deadline', 'N/A')}")
        lines.append(f"Priority: {used_data.get('priority', 'N/A')}")
    
    return "\n".join(lines)


def format_reflection_saved_response(data: dict) -> str:
    """Format reflection saved response into readable text."""
    lines = []
    lines.append("Reflection Saved Successfully!")
    lines.append("-" * 30)
    
    reflection_id = data.get("reflection_id", "")
    if reflection_id:
        lines.append(f"Reflection ID: {reflection_id}")
    
    return "\n".join(lines)


async def call_agent(
    agent_meta: AgentMetadata,
    intent: str,
    text: str,
    context: Dict[str, Any],
    custom_input: Dict[str, Any] = None,
) -> AgentResponse:
    """
    Build handshake request and invoke the worker. When endpoints are not real,
    we fall back to simulated results that mirror the contract.
    
    Args:
        custom_input: Optional dict to override default input structure.
                     If provided, it replaces the entire input payload.
    """

    request_id = str(uuid.uuid4())
    
    # Build metadata with file uploads if available
    metadata: Dict[str, Any] = {"language": "en", "extra": {}}
    file_uploads = context.get("file_uploads", [])
    
    if file_uploads and len(file_uploads) > 0:
        # For document summarizer agent, send first file as base64 in metadata
        # Note: Currently supports single file; can be extended for multiple files
        first_file = file_uploads[0]
        base64_data = first_file.get("base64_data", "")
        if base64_data:  # Only add if not empty
            metadata["file_base64"] = base64_data
            metadata["mime_type"] = first_file.get("mime_type", "application/octet-stream")
            metadata["filename"] = first_file.get("filename", "uploaded_file")
            # Debug logging
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Sending file to {agent_meta.name}: {first_file.get('filename', 'unknown')} ({len(base64_data)} chars base64)")
        else:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"File upload found but base64_data is empty for {agent_meta.name}")
    else:
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"No file uploads in context for {agent_meta.name}")
    
    handshake = AgentRequest(
        request_id=request_id,
        agent_name=agent_meta.name,
        intent=intent,
        input={"text": text, "metadata": metadata},
        context=context,
    )

    # Only live HTTP calls are supported; no simulation fallback.
    if agent_meta.type == "http" and agent_meta.endpoint and httpx is not None:
        try:
            import logging
            logger = logging.getLogger(__name__)
            
            async with httpx.AsyncClient(timeout=agent_meta.timeout_ms / 1000) as client:
                # Special handling for budget_tracker_agent - it expects {"query": "..."} format
                if agent_meta.name == "budget_tracker_agent":
                    payload = {"query": text}
                    logger.info(f"Calling {agent_meta.name} with payload: {payload}")
                elif agent_meta.name == "progress_accountability_agent":
                    user_id = context.get("user_id", "anonymous")
                    
                    # Map intent to task using our mapping
                    task = PROGRESS_AGENT_INTENT_MAP.get(intent, "accountability")
                    
                    # Build params based on intent/task
                    params = {}
                    
                    if task == "freeform_message":
                        params["message"] = text
                    elif task == "goal":
                        # Try to parse goal info from text (the agent handles natural language)
                        params["message"] = text  # Agent's handle_freeform_message can parse goals
                        task = "freeform_message"  # Use freeform for natural language goal creation
                    elif intent == "goal.update" and context.get("goal_id") and context.get("progress"):
                        # Direct progress update if goal_id and progress provided in context
                        params["goal_id"] = context.get("goal_id")
                        params["progress"] = context.get("progress")
                    
                    payload = {
                        "user_id": user_id,
                        "task": task,
                        "params": params
                    }
                    logger.info(f"Calling {agent_meta.name} with intent '{intent}' -> task '{task}', payload: {payload}")
                else:
                    payload = handshake.dict()
                
                resp = await client.post(agent_meta.endpoint, json=payload)
                logger.info(f"{agent_meta.name} response status: {resp.status_code}")
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
                
                if agent_meta.name == "progress_accountability_agent":
                    try:
                        resp_data = resp.json()
                        status = resp_data.get("status", "")
                        
                        # Handle different response formats from the productivity agent
                        if status == "ok":
                            # Standard ok response with payload
                            payload_data = resp_data.get("payload", resp_data.get("analysis", resp_data.get("report", resp_data.get("insights", {}))))
                            # Format the payload nicely
                            if isinstance(payload_data, dict) and "generated_at" in payload_data:
                                result_text = format_accountability_response(payload_data)
                            else:
                                result_text = json.dumps(payload_data, indent=2) if isinstance(payload_data, dict) else str(payload_data)
                            return AgentResponse(
                                request_id=request_id,
                                agent_name=agent_meta.name,
                                status="success",
                                output=OutputModel(
                                    result=result_text,
                                    details=json.dumps(resp_data, indent=2),
                                ),
                                error=None,
                            )
                        elif status == "created":
                            # Goal creation response
                            result_text = format_goal_created_response(resp_data)
                            return AgentResponse(
                                request_id=request_id,
                                agent_name=agent_meta.name,
                                status="success",
                                output=OutputModel(
                                    result=result_text,
                                    details=json.dumps(resp_data, indent=2),
                                ),
                                error=None,
                            )
                        elif status == "saved":
                            # Reflection saved response
                            result_text = format_reflection_saved_response(resp_data)
                            return AgentResponse(
                                request_id=request_id,
                                agent_name=agent_meta.name,
                                status="success",
                                output=OutputModel(
                                    result=result_text,
                                    details=json.dumps(resp_data, indent=2),
                                ),
                                error=None,
                            )
                        elif status == "incomplete":
                            # Missing fields response
                            msg_type = resp_data.get("type", "")
                            missing = resp_data.get("missing_fields", resp_data.get("missing_parts", []))
                            message = resp_data.get("message", "Some information is missing.")
                            result_text = f"{message}\nMissing: {', '.join(missing) if missing else 'unknown'}"
                            return AgentResponse(
                                request_id=request_id,
                                agent_name=agent_meta.name,
                                status="success",
                                output=OutputModel(
                                    result=result_text,
                                    details=json.dumps(resp_data, indent=2),
                                ),
                                error=None,
                            )
                        elif status == "error":
                            # Error response
                            error_msg = resp_data.get("message", "Unknown error from progress_accountability_agent")
                            return AgentResponse(
                                request_id=request_id,
                                agent_name=agent_meta.name,
                                status="error",
                                error=ErrorModel(
                                    type="agent_error",
                                    message=str(error_msg),
                                ),
                            )
                        else:
                            # Check if it looks like an accountability payload
                            if "generated_at" in resp_data or "goal_risks" in resp_data or "performance_metrics" in resp_data:
                                result_text = format_accountability_response(resp_data)
                            elif "reply" in resp_data:
                                result_text = resp_data.get("reply", "")
                            elif "message" in resp_data:
                                result_text = resp_data.get("message", "")
                            else:
                                result_text = json.dumps(resp_data, indent=2)
                            
                            return AgentResponse(
                                request_id=request_id,
                                agent_name=agent_meta.name,
                                status="success",
                                output=OutputModel(
                                    result=result_text,
                                    details=json.dumps(resp_data, indent=2),
                                ),
                                error=None,
                            )
                    except Exception as parse_exc:
                        logger.error(f"Failed to parse progress_accountability_agent response: {parse_exc}, raw: {resp.text[:500]}")
                        return AgentResponse(
                            request_id=request_id,
                            agent_name=agent_meta.name,
                            status="error",
                            error=ErrorModel(
                                type="parse_error",
                                message=f"Failed to parse agent response: {str(parse_exc)}",
                            ),
                        )
                # Special handling for budget_tracker_agent response format
                elif agent_meta.name == "budget_tracker_agent":
                    try:
                        resp_data = resp.json()
                        # Convert budget tracker response to supervisor handshake format
                        if resp_data.get("success", False):
                            # Extract the response text or format the data
                            result_text = resp_data.get("response")
                            if not result_text:
                                # If no "response" field, format the key data into a readable string
                                parts = []
                                if "remaining" in resp_data:
                                    parts.append(f"Remaining: ${resp_data['remaining']:.2f}")
                                if "project_name" in resp_data:
                                    parts.append(f"Project: {resp_data['project_name']}")
                                if "overshoot_risk" in resp_data:
                                    parts.append(f"Overshoot Risk: {resp_data['overshoot_risk']}")
                                if "recommendations" in resp_data and resp_data["recommendations"]:
                                    parts.append(f"Recommendations: {', '.join(resp_data['recommendations'])}")
                                result_text = ". ".join(parts) if parts else str(resp_data)
                            
                            return AgentResponse(
                                request_id=request_id,
                                agent_name=agent_meta.name,
                                status="success",
                                output=OutputModel(
                                    result=result_text,
                                    details=json.dumps(resp_data, indent=2) if resp_data else None,
                                ),
                                error=None,
                            )
                        else:
                            # Budget tracker returned success=false or error
                            error_msg = resp_data.get("error", resp_data.get("message", "Unknown error from budget tracker agent"))
                            return AgentResponse(
                                request_id=request_id,
                                agent_name=agent_meta.name,
                                status="error",
                                error=ErrorModel(
                                    type="agent_error",
                                    message=str(error_msg),
                                ),
                            )
                    except Exception as parse_exc:
                        # If JSON parsing fails, try to return the raw response
                        logger.error(f"Failed to parse budget_tracker_agent response: {parse_exc}, raw: {resp.text[:500]}")
                        return AgentResponse(
                            request_id=request_id,
                            agent_name=agent_meta.name,
                            status="error",
                            error=ErrorModel(
                                type="parse_error",
                                message=f"Failed to parse agent response: {str(parse_exc)}",
                            ),
                        )
                else:
                    return AgentResponse(**resp.json())
        except Exception as exc:
            return AgentResponse(
                request_id=request_id,
                agent_name=agent_meta.name,
                status="error",
                error=ErrorModel(type="network_error", message=str(exc)),
            )
    elif agent_meta.type == "http" and httpx is None:
        return AgentResponse(
            request_id=request_id,
            agent_name=agent_meta.name,
            status="error",
            error=ErrorModel(type="config_error", message="httpx not installed for HTTP agent calls"),
        )
    elif agent_meta.type == "cli":
        return AgentResponse(
            request_id=request_id,
            agent_name=agent_meta.name,
            status="error",
            error=ErrorModel(type="not_implemented", message="CLI agent execution is not implemented"),
        )
    else:
        return AgentResponse(
            request_id=request_id,
            agent_name=agent_meta.name,
            status="error",
            error=ErrorModel(type="config_error", message="Agent endpoint/command not configured"),
        )
