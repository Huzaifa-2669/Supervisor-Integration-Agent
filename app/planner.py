"""
LLM-based planner that selects which agents to call. Includes deterministic
heuristics, strict validation of LLM output, and an out-of-scope guard to avoid
calling agents for unsupported requests.
"""
from __future__ import annotations

import json
import os
from typing import List, Optional
import logging

try:
    from openai import OpenAI  # type: ignore
except ImportError:
    OpenAI = None  # optional; planner will fall back to heuristics

from .models import AgentMetadata, Plan, PlanStep

logger = logging.getLogger(__name__)


def _validate_steps(raw_steps: List[dict], registry: List[AgentMetadata]) -> List[PlanStep]:
    """Validate LLM-produced steps against the registry and schema."""
    valid_steps: List[PlanStep] = []
    registry_map = {a.name: a for a in registry}

    for step in raw_steps:
        try:
            step_obj = PlanStep(**step)
        except Exception as exc:  # invalid shape or missing fields
            logger.warning("Planner step rejected (schema): %s", exc)
            continue

        agent_meta = registry_map.get(step_obj.agent)
        if not agent_meta:
            logger.warning("Planner step rejected (unknown agent): %s", step_obj.agent)
            continue
        if step_obj.intent not in agent_meta.intents:
            logger.warning(
                "Planner step rejected (intent mismatch): agent=%s intent=%s allowed=%s",
                step_obj.agent,
                step_obj.intent,
                agent_meta.intents,
            )
            continue
        valid_steps.append(step_obj)
    return valid_steps


def _get_openrouter_client():
    """Return a configured OpenRouter client or None if unavailable."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if OpenAI is None or not api_key:
        return None
    try:
        return OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
    except Exception as exc:
        logger.error("Failed to configure OpenRouter client: %s", exc)
        return None


OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash-lite")


def plan_tools_with_llm(query: str, registry: List[AgentMetadata], history: Optional[List] = None) -> Plan:
    """Ask an LLM to propose a tool plan; fall back to a safe default or out-of-scope."""

    # Heuristic routing for clear intents to reduce misclassification and avoid
    # calling unrelated agents. If none of the heuristics match and the LLM is
    # unavailable, we declare out of scope (no steps).
    lower_q = query.lower()
    
    if any(keyword in lower_q for keyword in [
        "start focus mode", "turn on focus", "enable focus", "focus mode on",
        "start monitoring", "start focus", "begin monitoring", "track my focus",
        "monitor my activity", "watch my productivity"
    ]):
        return Plan(
            steps=[
                PlanStep(
                    step_id=0,
                    agent="deadline_guardian_agent",
                    intent="deadline.monitor",
                    input_source="user_query",
                ),
                PlanStep(
                    step_id=1,
                    agent="focus_enforcer_agent",
                    intent="focus.start_monitoring",
                    input_source="step:0.output.result",  # Pass deadline data to focus enforcer
                ),
            ]
        )
    
    if any(keyword in lower_q for keyword in [
        "focus", "distracted", "distraction", "productivity", "procrastinating",
        "am i focused", "check my focus", "analyze focus", "focus score",
        "how productive", "staying on task", "off task"
    ]):
        return Plan(
            steps=[
                PlanStep(
                    step_id=0,
                    agent="deadline_guardian_agent",
                    intent="deadline.monitor",
                    input_source="user_query",
                ),
                PlanStep(
                    step_id=1,
                    agent="focus_enforcer_agent",
                    intent="focus.analyze",
                    input_source="step:0.output.result",  # Pass deadline data
                ),
            ]
        )
    
    # Stop focus monitoring session (no deadline needed)
    if any(keyword in lower_q for keyword in [
        "stop monitoring", "stop focus", "end monitoring", "stop tracking",
        "turn off focus", "disable focus", "focus mode off"
    ]):
        return Plan(
            steps=[
                PlanStep(
                    step_id=0,
                    agent="focus_enforcer_agent",
                    intent="focus.stop_monitoring",
                    input_source="user_query",
                )
            ]
        )
    
    # Check focus status (no deadline needed - just status check)
    if any(keyword in lower_q for keyword in [
        "focus status", "monitoring status", "is focus on", "focus running"
    ]):
        return Plan(
            steps=[
                PlanStep(
                    step_id=0,
                    agent="focus_enforcer_agent",
                    intent="focus.check_status",
                    input_source="user_query",
                )
            ]
        )
    
    # Onboarding agent heuristics - check for all intents
    if any(keyword in lower_q for keyword in [
        "onboard", "onboarding", "new hire", "new employee", 
        "employee setup", "hire someone", "add employee"
    ]):
        return Plan(
            steps=[
                PlanStep(
                    step_id=0,
                    agent="onboarding_buddy_agent",
                    intent="onboarding.create",
                    input_source="user_query",
                )
            ]
        )
    
    # Update employee information
    if any(keyword in lower_q for keyword in [
        "update employee", "change employee", "modify employee",
        "edit employee", "update onboarding"
    ]):
        return Plan(
            steps=[
                PlanStep(
                    step_id=0,
                    agent="onboarding_buddy_agent",
                    intent="onboarding.update",
                    input_source="user_query",
                )
            ]
        )
    
    # Check employee progress/status
    if any(keyword in lower_q for keyword in [
        "employee progress", "onboarding progress", "employee status",
        "check employee", "employee completion", "profile completion",
        "onboarding status"
    ]):
        return Plan(
            steps=[
                PlanStep(
                    step_id=0,
                    agent="onboarding_buddy_agent",
                    intent="onboarding.check_progress",
                    input_source="user_query",
                )
            ]
        )
    
    # Task creation heuristics
    if any(keyword in lower_q for keyword in ["create task", "new task", "add task", "task:", "i need to", "implement", "fix bug"]):
        return Plan(
            steps=[
                PlanStep(
                    step_id=0,
                    agent="KnowledgeBaseBuilderAgent",
                    intent="create_task",
                    input_source="user_query",
                )
            ]
        )
    
    # Check for summarization BEFORE deadline/risk to avoid misrouting
    if any(keyword in lower_q for keyword in ["summary", "summarize", "condense"]):
        return Plan(
            steps=[
                PlanStep(
                    step_id=0,
                    agent="document_summarizer_agent",
                    intent="summary.create",
                    input_source="user_query",
                )
            ]
        )
    
    # Deadline monitoring
    if any(keyword in lower_q for keyword in ["deadline", "due date", "risk", "slip"]):
        return Plan(
            steps=[
                PlanStep(
                    step_id=0,
                    agent="deadline_guardian_agent",
                    intent="deadline.monitor",
                    input_source="user_query",
                )
            ]
        )
    
    # Meeting follow-up
    if any(keyword in lower_q for keyword in ["follow-up", "followup", "action item", "minutes"]):
        return Plan(
            steps=[
                PlanStep(
                    step_id=0,
                    agent="meeting_followup_agent",
                    intent="meeting.followup",
                    input_source="user_query",
                )
            ]
        )
    
    # Task dependencies
    if any(keyword in lower_q for keyword in ["dependency", "depends on", "blocked by", "analyze dependencies"]):
        return Plan(
            steps=[
                PlanStep(
                    step_id=0,
                    agent="task_dependency_agent",
                    intent="task.resolve_dependencies",
                    input_source="user_query",
                )
            ]
        )
    
    # Email priority
    if any(keyword in lower_q for keyword in ["email", "inbox", "priority"]):
        return Plan(
            steps=[
                PlanStep(
                    step_id=0,
                    agent="email_priority_agent",
                    intent="email.prioritize",
                    input_source="user_query",
                )
            ]
        )
    
    # Progress tracking
    if any(keyword in lower_q for keyword in ["progress", "goal", "task status"]):
        return Plan(
            steps=[
                PlanStep(
                    step_id=0,
                    agent="progress_accountability_agent",
                    intent="progress.track",
                    input_source="user_query",
                )
            ]
        )
    
    # Productivity agent – detailed routing
    # Create goal
    if any(k in lower_q for k in ["create goal", "new goal", "add goal"]):
        return Plan(
            steps=[
                PlanStep(
                    step_id=0,
                    agent="productivity_agent",
                    intent="goal.create",
                    input_source="user_query",
                )
            ]
        )

    # Update goal progress
    if any(k in lower_q for k in ["update goal", "goal progress", "progress update"]):
        return Plan(
            steps=[
                PlanStep(
                    step_id=0,
                    agent="productivity_agent",
                    intent="goal.update",
                    input_source="user_query",
                )
            ]
        )

    # Add reflection / journaling
    if any(k in lower_q for k in ["add reflection", "journal", "daily log", "reflection", "wrote"]):
        return Plan(
            steps=[
                PlanStep(
                    step_id=0,
                    agent="productivity_agent",
                    intent="reflection.add",
                    input_source="user_query",
                )
            ]
        )

    # Insights
    if "insight" in lower_q:
        return Plan(
            steps=[
                PlanStep(
                    step_id=0,
                    agent="productivity_agent",
                    intent="productivity.insights",
                    input_source="user_query",
                )
            ]
        )

    # Accountability
    if "accountability" in lower_q:
        return Plan(
            steps=[
                PlanStep(
                    step_id=0,
                    agent="productivity_agent",
                    intent="productivity.accountability",
                    input_source="user_query",
                )
            ]
        )

    # General analysis (default intent)
    if any(k in lower_q for k in ["analysis", "analyze", "trend", "pattern"]):
        return Plan(
            steps=[
                PlanStep(
                    step_id=0,
                    agent="productivity_agent",
                    intent="productivity.analyze",
                    input_source="user_query",
                )
            ]
        )

    # Report generation
    if "report" in lower_q:
        return Plan(
            steps=[
                PlanStep(
                    step_id=0,
                    agent="productivity_agent",
                    intent="productivity.report",
                    input_source="user_query",
                )
            ]
        )

    
    

    client = _get_openrouter_client()
    if client is None:
        # No LLM available and heuristics could not map the query: out of scope.
        return Plan(steps=[])
    
    agents_summary = [
        {"name": a.name, "description": a.description, "intents": a.intents}
        for a in registry
    ]

    system_prompt = (
        "You are a planner that selects worker agents to satisfy a user query. "
        'Return ONLY JSON with the shape {"steps":[{"step_id":0,"agent":...,"intent":...,"input_source":...},...]}. '
        "input_source is either 'user_query' or 'step:X.output.result'. "
        "If the request is outside the available agents\' scope, return {\"steps\":[]} (empty list) to signal out-of-scope. "
        "Strictly match agent intents to the user need; avoid generic summarizers unless summarization is explicitly requested. "
        "\n\nFor onboarding_buddy_agent:\n"
        "- Use \'onboarding.create\' or \'employee.create\' for creating new employees\n"
        "- Use \'onboarding.update\' or \'employee.update\' for updating employee information\n"
        "- Use \'onboarding.check_progress\' or \'employee.check_status\' for checking employee status or profile completion"
    )
    user_payload = {
        "user_query": query,
        "available_agents": agents_summary,
    }
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
        content = response.choices[0].message.content.strip() if response.choices else ""
    except Exception as exc:
        logger.error("Planner LLM call failed: %s", exc)
        return Plan(steps=[])

    logger.info("Planner LLM raw response: %s", content)
    try:
        plan_json = json.loads(content)
        raw_steps = plan_json.get("steps", [])
        validated = _validate_steps(raw_steps, registry)
        return Plan(steps=validated)
    except Exception as exc:
        logger.error("Planner failed to parse/validate LLM output: %s", exc)
        return Plan(steps=[])
