"""
Lightweight handling for small-talk/general queries and a simple abuse guard.
Used by the supervisor to short-circuit planning when no tools are needed.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal, Optional, TypedDict


class GeneralOutcome(TypedDict):
    kind: Literal["blocked", "general", "none"]
    answer: Optional[str]


ABUSE_PATTERNS = [
    r"\bkill\b",
    r"\bhate\b",
    r"\bstupid\b",
    r"\bfuck\b",
    r"\bshit\b",
    r"\basshole\b",
    r"\bidiot\b",
    r"\bviolence\b",
    r"\bmurder\b",
]


def _contains_abuse(text: str) -> bool:
    lower = text.lower()
    return any(re.search(pattern, lower) for pattern in ABUSE_PATTERNS)


def handle_general_query(query: str) -> GeneralOutcome:
    """
    Handle greetings, well-being checks, date/time questions, and abusive text.
    Returns a structured outcome to let the server short-circuit agent calls.
    """
    normalized = query.strip()
    lower = normalized.lower()

    if not normalized:
        return {"kind": "none", "answer": None}

    if _contains_abuse(lower):
        return {"kind": "blocked", "answer": "I can't help with that."}

    greetings = [r"\bhi\b", r"\bhello\b", r"\bhey\b", r"\bgood (morning|afternoon|evening)\b"]
    if any(re.search(pat, lower) for pat in greetings):
        return {"kind": "general", "answer": "Hello! I'm here to help with your requests."}

    if "how are you" in lower or "how are u" in lower or "how's it going" in lower:
        return {"kind": "general", "answer": "I'm doing great, thank you for asking! How can I assist you today?"}

    if "who are you" in lower or "who r u" in lower or "what are you" in lower:
        return {"kind": "general", "answer": "I'm a supervisor agent that coordinates specialized worker agents to help you with various tasks like knowledge retrieval, scheduling, email management, and more."}

    if ("date" in lower or "day" in lower) and ("today" in lower or "current" in lower or "what" in lower):
        today = datetime.now(timezone.utc).date().isoformat()
        return {"kind": "general", "answer": f"Today's date (UTC) is {today}."}

    if "time" in lower and ("now" in lower or "current" in lower or "what" in lower):
        current_time = datetime.now(timezone.utc).strftime("%H:%M UTC")
        return {"kind": "general", "answer": f"The current time is {current_time}."}

    return {"kind": "none", "answer": None}
