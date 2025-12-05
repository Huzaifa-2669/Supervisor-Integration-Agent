"""
Plan execution: resolve inputs for each step, call the right agent, and collect
outputs for later synthesis or UI debugging.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Tuple

try:
    import httpx  # type: ignore
except ImportError:
    httpx = None

from .agent_caller import call_agent
from .combine import combine_tool_outputs
from .models import AgentMetadata, AgentRequest, AgentResponse, CombinedAnswerRequest, CombinedAnswerResponse, ErrorModel, Plan, UsedAgentEntry
from .registry import find_agent_by_name


def resolve_input(input_source: str, user_query: str, step_outputs: Dict[int, AgentResponse]) -> str:
    """Resolve an input_source directive into text for the worker."""
    if input_source == "user_query":
        return user_query
    if input_source.startswith("step:"):
        parts = input_source.split(":")
        if len(parts) >= 2:
            step_id_str = parts[1].split(".")[0]
            try:
                step_id = int(step_id_str)
                prior = step_outputs.get(step_id)
                if prior and prior.output:
                    return str(prior.output.result)
            except ValueError:
                pass
    return user_query





async def execute_plan(
    query: str,
    plan: Plan,
    registry: List[AgentMetadata],
    context: Dict[str, Any],
) -> Tuple[Dict[int, AgentResponse], List[UsedAgentEntry], CombinedAnswerResponse]:
    """Execute each planned step in order, then combine outputs when multiple agents are used."""
    step_outputs: Dict[int, AgentResponse] = {}
    used_agents: List[UsedAgentEntry] = []

    for step in plan.steps:
        agent_meta = find_agent_by_name(step.agent, registry)
        text = resolve_input(step.input_source, query, step_outputs)
        # Pass file uploads from context to agent caller
        response = await call_agent(agent_meta, step.intent, text, context)
        step_outputs[step.step_id] = response
        used_agents.append(
            UsedAgentEntry(name=agent_meta.name, intent=step.intent, status=response.status)
        )
        
        # Auto-trigger TDA after KnowledgeBaseBuilderAgent successfully creates tasks
        if (step.agent == "KnowledgeBaseBuilderAgent" and 
            response.status == "success" and 
            step.intent == "create_task"):
            try:
                tda_meta = find_agent_by_name("task_dependency_agent", registry)
                # Call TDA with database trigger - it will retrieve tasks from MongoDB
                tda_response = await call_agent(
                    tda_meta,
                    "task.resolve_dependencies",
                    "",  # Empty text since TDA uses trigger
                    context,
                    custom_input={"trigger": "database_update"}  # Signal to retrieve from DB
                )
                # Add TDA to outputs with next step_id
                next_step_id = max(step_outputs.keys()) + 1 if step_outputs else 0
                step_outputs[next_step_id] = tda_response
                used_agents.append(
                    UsedAgentEntry(
                        name=tda_meta.name,
                        intent="task.resolve_dependencies",
                        status=tda_response.status
                    )
                )
            except KeyError:
                # TDA not found in registry, skip auto-trigger
                pass
            except Exception:
                # TDA call failed, continue without blocking
                pass

    # Combine outputs when multiple distinct agents were used
    distinct_agents = {ua.name for ua in used_agents}
    combined = None
    if len(distinct_agents) >= 2:
        tool_outputs = []
        for resp in step_outputs.values():
            entry = {
                "agent": resp.agent_name,
                "status": resp.status,
                "result": resp.output.result if resp.output else None,
                "details": resp.output.details if resp.output else None,
                "error": resp.error.message if resp.error else None,
            }
            tool_outputs.append(entry)
        combine_req = CombinedAnswerRequest(
            user_query=query,
            tool_outputs=tool_outputs,
            history_summary=context.get("history_summary"),
        )
        combined = combine_tool_outputs(combine_req)
    else:
        combined = CombinedAnswerResponse(combined_answer="")

    return step_outputs, used_agents, combined
