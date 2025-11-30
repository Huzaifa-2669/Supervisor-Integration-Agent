"""
Agent registry: the supervisor uses this to (a) brief the planner on available
capabilities and (b) look up connection details when calling a worker.
"""
from __future__ import annotations

from typing import List

from .models import AgentMetadata


def load_registry() -> List[AgentMetadata]:
    """Return the known worker agents. Replace endpoints/commands with real ones."""
    return [
        AgentMetadata(
            name="progress_accountability_agent",
            description="Tracks goals, tasks, and progress to provide accountability insights.",
            intents=["progress.track"],
            type="http",
            endpoint="https://example.com/progress/handle",
            healthcheck="https://example.com/progress/health",
        ),
        AgentMetadata(
            name="email_priority_agent",
            description="Classifies email-like text into priority levels (high/medium/low) and returns explanations.",
            intents=["email.priority.classify"],
            type="http",
            endpoint="https://spm-email-priority-agent.onrender.com/handle",
            healthcheck="https://spm-email-priority-agent.onrender.com/health",
            timeout_ms=40000,
        ),
        AgentMetadata(
            name="document_summarizer_agent",
            description="Summarizes documents or text into concise summaries. Supports PDF, DOCX, TXT, and Markdown formats. Can extract key points, identify risks, and extract action items.",
            intents=["summary.create", "summarize_document", "summarize_text", "extract_key_points", "identify_risks", "extract_action_items"],
            type="http",
            endpoint="http://5.161.59.136:8000/api/agent/execute",
            healthcheck="http://5.161.59.136:8000/health",
            timeout_ms=30000,
        ),
        AgentMetadata(
            name="meeting_followup_agent",
            description="ONLY for meeting transcripts: extracts action items (with assignees and deadlines), generates meeting summaries, identifies follow-up tasks. Use ONLY when query mentions meetings, transcripts, standups, action items, or follow-ups.",
            intents=["meeting.followup", "meeting.process", "meeting.analyze", "action_items.extract"],
            type="http",
            endpoint="https://meeting-minutes-backend-spm-production.up.railway.app/agents/supervisor/meeting-followup",
            healthcheck="https://meeting-minutes-backend-spm-production.up.railway.app/agents/supervisor/health",
            timeout_ms=30000,
        ),
        AgentMetadata(
            name="onboarding_buddy_agent",
            description="Automates employee onboarding by collecting information, setting up access credentials (email, username, password), monitoring profile completion, and sending welcome emails. Creates company email accounts via MailSlurp, generates system credentials, and provides complete access setup details. Handles creating new employees, updating employee information, and checking onboarding progress.",
            intents=[
                "onboarding.create",
                "onboarding.update", 
                "onboarding.check_progress",
                "employee.create",
                "employee.update",
                "employee.check_status"
            ],
            type="http",
            endpoint="https://onboardingbuddyagent-production.up.railway.app/execute",
            healthcheck="https://onboardingbuddyagent-production.up.railway.app/health",
            timeout_ms=100000,
        ),
        AgentMetadata(
            name="KnowledgeBaseBuilderAgent",
            description="Creates and manages tasks from plain English input. Uses LLM to parse task information (task_id, task_name, task_description, task_deadline) from any input format and stores tasks in MongoDB with default status 'todo'.",
            intents=["create_task", "add_task", "task.create", "task.add"],
            type="http",
            endpoint="http://vps.zaim-abbasi.tech/knowledge-builder/message",
            healthcheck="http://vps.zaim-abbasi.tech/knowledge-builder/health",
            timeout_ms=30000,
        ),
        AgentMetadata(
            name="task_dependency_agent",
            description="Analyzes task dependencies using LLM inference. Automatically retrieves tasks from MongoDB, infers dependencies between them, calculates execution order, and updates the database. Triggered after KnowledgeBaseBuilderAgent creates tasks.",
            intents=["task.resolve_dependencies"],
            type="http",
            endpoint="https://task-dependency-agent.vercel.app/task",
            healthcheck="https://task-dependency-agent.vercel.app/health",
            timeout_ms=30000,
        ),
        AgentMetadata(
            name="productivity_agent",
            description="Analyzes reflections, tracks goals, generates insights, detects trends, and produces productivity reports.",
            intents=[
                "productivity.analyze",       # /analysis
                "productivity.report",        # /report
                "goal.create",                # /goals (POST)
                "goal.update",                # /goals/<id>/progress
                "reflection.add",             # /reflections
                "productivity.insights",      # /insights
                "productivity.accountability" # /accountability
            ],
            type="http",
            endpoint="https://spm-agent-api-production.up.railway.app/agent/json",
            healthcheck="https://spm-agent-api-production.up.railway.app/health",
            timeout_ms=30000,
        ),

        AgentMetadata(
            name="deadline_guardian_agent",
            description="AI-powered deadline monitoring with dependency analysis. Identifies cascading risks, bottlenecks, and blocked tasks using Google Gemini Flash 2.0. Provides strategic recommendations for clearing bottlenecks and managing overdue tasks.",
            intents=["deadline.monitor"],
            type="http",
            endpoint="https://deadlinegaurdianagent-production.up.railway.app/handle",
            healthcheck="https://deadlinegaurdianagent-production.up.railway.app/health",
            timeout_ms=30000,
        ),
        AgentMetadata(
            name="focus_enforcer_agent",
            description="Monitors user focus and productivity by analyzing window activity. Uses LLM to calculate focus scores based on productive vs distraction keywords, determines if user is FOCUSED or DISTRACTED, and generates supervisor commands for interventions (notifications or strict popups). Requires activity history data with window titles.",
            intents=[
                "focus.analyze",
                "focus.start_monitoring", 
                "focus.stop_monitoring",
                "focus.check_status",
                "productivity.assess"
            ],
            type="http",
            endpoint="http://localhost:8001/handle",  # Local endpoint for Focus Enforcer service
            healthcheck="http://localhost:8001/health",
            timeout_ms=60000,  # 60 seconds timeout for LLM analysis
        ),
    ]


def find_agent_by_name(name: str, registry: List[AgentMetadata]) -> AgentMetadata:
    for agent in registry:
        if agent.name == name:
            return agent
    raise KeyError(f"Agent {name} not found in registry")
