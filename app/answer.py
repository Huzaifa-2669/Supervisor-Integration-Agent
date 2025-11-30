"""
Final answer synthesis: combine tool outputs into a user-friendly response.
Falls back to deterministic stitching when OpenRouter is unavailable.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

try:
    from openai import OpenAI  # type: ignore
except ImportError:
    OpenAI = None

from .models import AgentResponse


OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash-lite")


def compose_final_answer(query: str, step_outputs: Dict[int, AgentResponse], history: Optional[List] = None) -> str:
    """Convert tool outputs into a concise answer."""
    # If no steps were executed, treat as out-of-scope.
    if not step_outputs:
        return "This information is not in my scope."

    successful = [s for s in step_outputs.values() if s.is_success()]
    if not successful:
        return "I could not complete your request because every tool failed. Please try again."

    # For document summarizer, return the markdown directly
    stitched = " | ".join(str(s.output.result) for s in successful if s.output)

    # For document reviewer agent, convert JSON to formatted markdown
    for s in successful:
        if s.agent_name == "document_reviewer_agent" and s.output:
            try:
                review_data = json.loads(str(s.output.result))
                markdown_output = format_review_as_markdown(review_data)
                return markdown_output
            except (json.JSONDecodeError, AttributeError):
                pass  # Fall through to default handling.

    api_key = os.getenv("OPENROUTER_API_KEY")
    if OpenAI is None or not api_key:
        return stitched  # Return markdown directly without prefix

    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
    except Exception:
        return f"Based on the tools, here is what I found: {stitched}"
    tool_findings = [
        {
            "agent": s.agent_name,
            "status": s.status,
            "result": s.output.result if s.output else None,
            "details": s.output.details if s.output else None,
        }
        for s in step_outputs.values()
    ]

    system_prompt = (
        "You are a helpful assistant. Given the user's query and tool outputs, "
        "write a concise, actionable answer."
    )
    user_payload = {"user_query": query, "tool_outputs": tool_findings}
    if history:
        user_payload["recent_history"] = history
    user_prompt = json.dumps(user_payload, indent=2)

    try:
        response = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content.strip() if response.choices else stitched
    except Exception:
        return stitched
    

def format_review_as_markdown(review_data: Dict) -> str:
    """Convert document review JSON to formatted markdown."""
    md = []
    
    # Overall score and summary
    score = review_data.get("overall_score", 0.0)
    summary = review_data.get("summary", "")
    md.append(f"## Document Review Summary\n")
    md.append(f"**Overall Score:** {score:.1%}\n")
    if summary:
        md.append(f"{summary}\n")
    
    # Spelling errors
    spelling = review_data.get("spelling_errors", [])
    if spelling:
        md.append(f"\n### Spelling Errors ({len(spelling)})\n")
        for err in spelling:
            md.append(f"- **{err.get('error', 'N/A')}** → {err.get('suggestion', 'N/A')}")
            if err.get('location'):
                md.append(f"  - *Location: {err.get('location')}*")
            md.append("")
    
    # Grammar errors
    grammar = review_data.get("grammar_errors", [])
    if grammar:
        md.append(f"\n### Grammar Errors ({len(grammar)})\n")
        for err in grammar:
            md.append(f"- **{err.get('error', 'N/A')}** → {err.get('suggestion', 'N/A')}")
            if err.get('type'):
                md.append(f"  - *Type: {err.get('type')}*")
            if err.get('location'):
                md.append(f"  - *Location: {err.get('location')}*")
            md.append("")
    
    # Compliance issues
    compliance = review_data.get("compliance_issues", [])
    if compliance:
        md.append(f"\n### Compliance Issues ({len(compliance)})\n")
        for issue in compliance:
            severity = issue.get('severity', 'unknown')
            severity_emoji = "🔴" if severity == "high" else "🟡" if severity == "medium" else "🟢"
            md.append(f"- {severity_emoji} **{severity.upper()}**: {issue.get('issue', 'N/A')}")
            if issue.get('suggestion'):
                md.append(f"  - *Suggestion: {issue.get('suggestion')}*")
            md.append("")
    
    return "\n".join(md)
