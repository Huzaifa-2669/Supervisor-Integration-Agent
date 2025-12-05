"""
Utilities for handling conversation history, including lightweight summarization
to avoid passing full transcripts downstream.
"""
from __future__ import annotations

import json
import os
from typing import List, Dict
import logging

try:
    from openai import OpenAI  # type: ignore
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)

OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash-lite")


def summarize_history(history: List[Dict[str, str]]) -> str:
    """
    Summarize recent conversation turns into a short context string. Uses
    OpenRouter if available; otherwise falls back to a simple concatenation.
    """
    if not history:
        return ""

    # Fallback summary if LLM is unavailable
    def _fallback() -> str:
        # Keep it compact: role: content truncated
        parts = [f"{m.get('role')}: {m.get('content', '')}" for m in history[-6:]]
        joined = " | ".join(parts)
        return f"Conversation summary (fallback): {joined[:500]}"

    api_key = os.getenv("OPENROUTER_API_KEY")
    if OpenAI is None or not api_key:
        return _fallback()

    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
    except Exception as exc:
        logger.error("Failed to init OpenRouter client for history summary: %s", exc)
        return _fallback()

    system_prompt = (
        "Summarize the conversation so far in 2-3 concise sentences. "
        "Capture user goals, key details, and any decisions or constraints. "
        "Do not invent new facts."
    )
    user_prompt = json.dumps({"history": history[-6:]}, indent=2)

    try:
        response = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        if response.choices:
            return response.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("History summarization failed: %s", exc)
        return _fallback()

    return _fallback()
