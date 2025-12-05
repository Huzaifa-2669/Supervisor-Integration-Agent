"""
LLM-based combination of multiple agent results for multi-intent queries.
Provides a fallback stitching path when LLM is unavailable.
"""
from __future__ import annotations

import json
import os
from typing import List
import logging

try:
    from openai import OpenAI  # type: ignore
except ImportError:
    OpenAI = None

from .models import CombinedAnswerRequest, CombinedAnswerResponse

logger = logging.getLogger(__name__)

OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash-lite")


def combine_tool_outputs(req: CombinedAnswerRequest) -> CombinedAnswerResponse:
    """Combine multiple tool outputs into a single concise answer."""
    # Fallback stitching: list each agent result with status.
    def _fallback() -> CombinedAnswerResponse:
        lines: List[str] = []
        for entry in req.tool_outputs:
            agent = entry.get("agent")
            status = entry.get("status")
            result = entry.get("result")
            error = entry.get("error")
            if status == "success":
                lines.append(f"{agent}: {result}")
            else:
                lines.append(f"{agent}: failed ({error})")
        stitched = " | ".join(lines) if lines else "No tool outputs available."
        return CombinedAnswerResponse(combined_answer=stitched)

    api_key = os.getenv("OPENROUTER_API_KEY")
    if OpenAI is None or not api_key:
        return _fallback()

    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
    except Exception as exc:
        logger.error("Failed to init OpenRouter client for combine: %s", exc)
        return _fallback()

    system_prompt = (
        "You are a response combiner. Given the user's query and multiple tool outputs, "
        "produce a single concise answer that integrates the results. "
        "If some tools failed, still use the successful outputs and briefly note the failure. "
        "Be direct and avoid repetition."
    )
    user_payload = {
        "user_query": req.user_query,
        "tool_outputs": req.tool_outputs,
    }
    if req.history_summary:
        user_payload["history_summary"] = req.history_summary
    user_prompt = json.dumps(user_payload, indent=2)

    try:
        response = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        if response.choices:
            return CombinedAnswerResponse(
                combined_answer=response.choices[0].message.content.strip()
            )
    except Exception as exc:
        logger.error("Combine LLM failed: %s", exc)
        return _fallback()

    return _fallback()
