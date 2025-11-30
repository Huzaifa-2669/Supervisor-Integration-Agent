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
                
                # Special handling for budget_tracker_agent response format
                if agent_meta.name == "budget_tracker_agent":
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
                        import logging
                        logger = logging.getLogger(__name__)
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
