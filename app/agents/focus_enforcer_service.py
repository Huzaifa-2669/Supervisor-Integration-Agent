"""
Focus Enforcer Agent HTTP Service Wrapper.

Architecture:
- Focus Enforcer receives deadline data FROM THE SUPERVISOR
- Supervisor orchestrates: Deadline Guardian -> Focus Enforcer
- This agent focuses on: window monitoring, LLM analysis, OS-level popups/notifications
"""
from __future__ import annotations

import asyncio
import functools
import json
import logging
import os
import sys
import time
import uuid
import platform
import ctypes
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s (FOCUS_SERVICE): %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---

# Try to import Cohere for LLM analysis
cohere = None
CohereError = Exception

try:
    import cohere
    if hasattr(cohere, 'APIError'):
        CohereError = cohere.APIError
    elif hasattr(cohere, 'CohereAPIError'):
        CohereError = cohere.CohereAPIError
except ImportError:
    logger.warning("Cohere library not installed. Focus analysis will use fallback mode.")

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

COHERE_API_KEY = os.environ.get("COHERE_API_KEY")

# Initialize Cohere Client
co = None
if COHERE_API_KEY and cohere:
    try:
        co = cohere.ClientV2(COHERE_API_KEY)
        logger.info("Cohere Client V2 initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Cohere client: {e}")


# =============================================================================
# PYDANTIC MODELS - SUPERVISOR HANDSHAKE CONTRACT
# =============================================================================

class InputMetadata(BaseModel):
    language: str = "en"
    extra: Dict[str, Any] = Field(default_factory=dict)


class AgentInput(BaseModel):
    text: str
    metadata: InputMetadata = Field(default_factory=InputMetadata)


class AgentContext(BaseModel):
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    timestamp: Optional[str] = None
    file_uploads: Optional[List[Dict[str, Any]]] = None


class SupervisorRequest(BaseModel):
    """Incoming request from the Supervisor."""
    request_id: str
    agent_name: str
    intent: str
    input: AgentInput
    context: AgentContext = Field(default_factory=AgentContext)


class ErrorOutput(BaseModel):
    type: str
    message: str


class SuccessOutput(BaseModel):
    result: Any
    confidence: Optional[float] = None
    details: Optional[str] = None


class SupervisorResponse(BaseModel):
    """Response back to the Supervisor."""
    request_id: str
    agent_name: str
    status: str  # "success" or "error"
    output: Optional[SuccessOutput] = None
    error: Optional[ErrorOutput] = None


# =============================================================================
# PYDANTIC MODELS - LEGACY ENDPOINTS (BACKWARD COMPATIBILITY)
# =============================================================================

class StartFocusRequest(BaseModel):
    user_id: str
    goal: str = "Complete the final WBS architecture design and documentation."
    critical_deadline: str = "End of day Friday (EOD Friyay)"
    target_apps: str = "Jira, VS Code, Google Docs, Figma"


class StopFocusRequest(BaseModel):
    user_id: str


class AgentInputModel(BaseModel):
    agent_input_json: str


# =============================================================================
# IN-MEMORY STATE FOR MONITORING
# =============================================================================

class MonitoringState:
    """Manages the current state of focus monitoring."""
    def __init__(self):
        self.is_running: bool = False
        self.user_id: Optional[str] = None
        self.focus_task: Optional[asyncio.Task] = None
        self.activity_history: List[Dict[str, Any]] = []
        self.hourly_summary: List[Dict[str, Any]] = []
        self.paa_data: Dict[str, Any] = {}  # Project-Activity-App data
        self.dg_data: Dict[str, Any] = {}   # Deadline-Goal data (FROM SUPERVISOR)
        self.last_analysis: Optional[Dict[str, Any]] = None

state = MonitoringState()


# =============================================================================
# OS-LEVEL POPUP/NOTIFICATION FUNCTIONS
# =============================================================================

def _show_windows_popup(title: str, message: str, level: str):
    """
    Displays a native Windows Message Box.
    level: 'info' or 'critical'
    """
    if platform.system() != "Windows":
        logger.warning(f"Skipping popup (Not on Windows): [{level}] {message}")
        return

    MB_OK = 0x00000000
    MB_ICONSTOP = 0x00000010
    MB_ICONINFORMATION = 0x00000040
    MB_SYSTEMMODAL = 0x00001000

    flags = MB_OK | MB_ICONINFORMATION
    if level == 'critical':
        flags = MB_OK | MB_ICONSTOP | MB_SYSTEMMODAL
    
    try:
        # Running strictly in a thread executor to avoid blocking main thread
        ctypes.windll.user32.MessageBoxW(0, message, title, flags)
        logger.info(f"Windows popup displayed: [{level}] {title}")
    except Exception as e:
        logger.error(f"Failed to show Windows popup: {e}")


async def _handle_intervention(command: str):
    """Parses the Agent command and triggers the actual OS-level intervention."""
    if not command:
        return

    loop = asyncio.get_running_loop()

    if command.startswith("STRICT POPUP:"):
        message = command.replace("STRICT POPUP:", "").strip()
        logger.critical(f"EXECUTING STRICT POPUP: {message}")
        # Run blocking UI call in executor
        await loop.run_in_executor(None, _show_windows_popup, "FOCUS ENFORCER - STRICT ALERT", message, "critical")
        
    elif command.startswith("NOTIFY:"):
        message = command.replace("NOTIFY:", "").strip()
        logger.warning(f"EXECUTING NOTIFICATION: {message}")
        await loop.run_in_executor(None, _show_windows_popup, "Focus Enforcer - Reminder", message, "info")
        
    elif command == "CONTINUE MONITORING":
        logger.info("Focus confirmed. No intervention needed.")
    else:
        logger.error(f"Unrecognized Agent command: {command}")


# =============================================================================
# WINDOW MONITORING (pygetwindow)
# =============================================================================

def get_active_window_title() -> str:
    """Get the currently active window title using pygetwindow."""
    try:
        import pygetwindow as gw
        active = gw.getActiveWindow()
        if active:
            return active.title
        return "Unknown Window"
    except ImportError:
        logger.warning("pygetwindow not installed. Using placeholder.")
        return "Unknown Window (pygetwindow not installed)"
    except Exception as e:
        # Often happens if screen is locked or permission denied
        return f"System Idle / Unknown ({str(e)})"


async def monitor_loop():
    """Background loop that monitors window activity and runs analysis."""
    logger.info("Focus monitoring loop started.")
    
    analysis_interval = 60  # Analyze every 60 seconds
    last_analysis_time = time.time()
    
    while state.is_running:
        try:
            # Capture current window
            window_title = get_active_window_title()
            
            # --- LOGGING ADDED HERE ---
            logger.info(f"[🪟 WINDOW CHECK] Active: {window_title}")
            # --------------------------

            state.activity_history.append({
                "timestamp": time.time(),
                "window_title": window_title
            })
            
            # Keep only last 100 entries
            if len(state.activity_history) > 100:
                state.activity_history = state.activity_history[-100:]
            
            # Run analysis every interval
            if time.time() - last_analysis_time >= analysis_interval:
                # IMPORTANT: await the async analysis
                analysis = await analyze_focus({
                    "paa_data": state.paa_data,
                    "dg_data": state.dg_data,
                    "activity_history": state.activity_history,
                    "hourly_summary": state.hourly_summary
                }, execute_intervention=True)
                
                state.last_analysis = analysis
                last_analysis_time = time.time()
                logger.info(f"Analysis complete: {analysis.get('focus_state')} (score: {analysis.get('productivity_score')})")
            
            await asyncio.sleep(5)  # Check window every 5 seconds
            
        except asyncio.CancelledError:
            logger.info("Monitoring loop cancelled.")
            break
        except Exception as e:
            logger.error(f"Error in monitor loop: {e}")
            await asyncio.sleep(5)
    
    logger.info("Focus monitoring loop stopped.")


# =============================================================================
# LLM ANALYSIS LOGIC
# =============================================================================

ANALYSIS_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "is_focused": {"type": "BOOLEAN", "description": "True if F-Score >= 70"},
        "productivity_score": {"type": "INTEGER", "description": "Score 0-100"},
        "productive_keywords": {"type": "ARRAY", "items": {"type": "STRING"}},
        "distraction_keywords": {"type": "ARRAY", "items": {"type": "STRING"}},
        "reasoning": {"type": "STRING"},
        "supervisor_command": {"type": "STRING", "description": "'CONTINUE MONITORING', 'NOTIFY: [msg]', or 'STRICT POPUP: [msg]'"}
    },
    "required": ["is_focused", "productivity_score", "productive_keywords", "distraction_keywords", "reasoning", "supervisor_command"]
}


def create_system_prompt(paa_data: Dict[str, Any], dg_data: Dict[str, Any], 
                         history: List[Dict[str, Any]], hourly_summary: List[Dict[str, Any]]) -> str:
    """Constructs the system prompt for focus analysis with Recency Emphasis."""
    
    task = paa_data.get("goal", "an undefined project task")
    deadline = dg_data.get("critical_deadline", dg_data.get("next_deadline", "TBD"))
    deadline_risk = dg_data.get("deadline_risk", dg_data.get("risk_level", "unknown"))
    target_apps = paa_data.get('target_apps', 'Not specified')
    
    # Format activity log (Last 20 entries are crucial)
    history_subset = history[-20:] if history else []
    history_str = "\n".join([
        f"[{time.strftime('%H:%M:%S', time.localtime(h['timestamp']))}] Window: {h['window_title']}" 
        for h in history_subset
    ]) if history_subset else "No activity recorded yet."
    
    schema_str = json.dumps(ANALYSIS_SCHEMA, indent=2)

    return f"""
    SYSTEM ROLE: You are the Focus Enforcer AI.

    --- RULES FOR ANALYSIS ---
    1. **RECENCY IS KING**: Look at the LAST 5 entries in the "RECENT ACTIVITY" log. 
       - If the user is currently in a Target App (e.g., VS Code), they are FOCUSED, even if previous history was bad.
       - Do NOT trigger a STRICT POPUP if the user has already returned to work.
    2. **Scoring**: 
       - If current window is productive: Score must be > 60.
       - If current window is distraction: Score penalty applies.
    3. **Commands**:
       - "STRICT POPUP": Only if the user is *currently* distracted AND score is low.
       - "CONTINUE MONITORING": If the user is currently working.

    --- CONTEXT ---
    Target Apps: {target_apps}
    Task: {task}
    Deadline: {deadline}
    Risk: {deadline_risk}
    
    RECENT ACTIVITY (Last 20 entries):
    {history_str}
    
    --- OUTPUT SCHEMA ---
    {schema_str}
    
    Respond with ONLY valid JSON matching the schema.
    """


async def analyze_focus(input_data: Dict[str, Any], execute_intervention: bool = False) -> Dict[str, Any]:
    """
    Analyze focus using LLM or fallback logic.
    CRITICAL CHANGE: Now Async to prevent blocking the event loop during network requests.
    """
    
    paa_data = input_data.get("paa_data", state.paa_data)
    dg_data = input_data.get("dg_data", state.dg_data)
    activity_history = input_data.get("activity_history", state.activity_history)
    hourly_summary = input_data.get("hourly_summary", state.hourly_summary)
    
    # --- 1. LLM ANALYSIS ---
    analysis = {}
    
    if not co:
        analysis = get_fallback_analysis("Cohere client not available", activity_history)
    else:
        try:
            system_prompt = create_system_prompt(paa_data, dg_data, activity_history, hourly_summary)
            messages = [{"role": "user", "content": system_prompt}]
            
            # Use run_in_executor to prevent blocking the async loop
            loop = asyncio.get_running_loop()
            
            # MODEL CHANGED: command-r-plus is deprecated -> command-a-03-2025
            chat_func = functools.partial(
                co.chat,
                model='command-a-03-2025', 
                messages=messages, 
                temperature=0.0
            )
            
            response = await loop.run_in_executor(None, chat_func)
            
            if response and response.message and response.message.content:
                raw_text = response.message.content[0].text.strip()
                
                # Cleanup markdown code blocks if present
                if raw_text.startswith('```json'):
                    raw_text = raw_text.split('\n', 1)[1].rsplit('```', 1)[0]
                elif raw_text.startswith('```'):
                    raw_text = raw_text.split('\n', 1)[1].rsplit('```', 1)[0]
                
                llm_result = json.loads(raw_text)
                
                analysis = {
                    "focus_state": "FOCUSED" if llm_result.get('is_focused', False) else "DISTRACTED",
                    "productivity_score": llm_result.get('productivity_score', 0),
                    "intervention_needed": not llm_result.get('is_focused', False),
                    "supervisor_command": llm_result.get('supervisor_command', 'CONTINUE MONITORING'),
                    "reasoning": llm_result.get('reasoning', 'Analysis complete.'),
                    "productive_keywords": llm_result.get('productive_keywords', []),
                    "distraction_keywords": llm_result.get('distraction_keywords', [])
                }
            else:
                analysis = get_fallback_analysis("Empty LLM response", activity_history)
                
        except json.JSONDecodeError as e:
            analysis = get_fallback_analysis(f"JSON parse error: {e}", activity_history)
        except Exception as e:
            logger.error(f"LLM API Error: {e}")
            analysis = get_fallback_analysis(f"LLM error: {str(e)[:50]}...", activity_history)
    
    # --- 2. RECENCY OVERRIDE (Fix for Lag) ---
    if activity_history:
        current_window = activity_history[-1].get('window_title', '').lower()
        target_apps_str = paa_data.get('target_apps', '').lower()
        target_apps = [t.strip() for t in target_apps_str.split(',') if t.strip()]
        
        # Check if the CURRENT window matches any target app
        is_currently_working = any(app in current_window for app in target_apps)
        
        if is_currently_working:
            if "STRICT POPUP" in analysis.get("supervisor_command", ""):
                logger.info(f"Override: User is currently in '{current_window}' (Target). Downgrading strict popup.")
                analysis["supervisor_command"] = "CONTINUE MONITORING"
                analysis["focus_state"] = "RECOVERING"
                analysis["reasoning"] += " [System Override: User returned to target app]"
                analysis["intervention_needed"] = False

    # --- 3. EXECUTE INTERVENTION ---
    if execute_intervention and analysis.get("supervisor_command"):
        await _handle_intervention(analysis["supervisor_command"])
    
    return analysis


def get_fallback_analysis(reason: str, activity_history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Fallback analysis when LLM is unavailable."""
    logger.warning(f"Using fallback analysis: {reason}")
    
    distraction_keywords = ['youtube', 'reddit', 'twitter', 'facebook', 'instagram', 
                            'netflix', 'hulu', 'game', 'discord', 'tiktok', 'friv', 'hianime']
    
    distraction_count = 0
    current_window = ""
    if activity_history:
        current_window = activity_history[-1].get('window_title', '').lower()
        
    for entry in activity_history:
        title = entry.get('window_title', '').lower()
        if any(dk in title for dk in distraction_keywords):
            distraction_count += 1
    
    total_entries = len(activity_history) if activity_history else 1
    distraction_ratio = distraction_count / total_entries
    score = max(0, int(100 - (distraction_ratio * 100)))
    
    is_currently_distracted = any(dk in current_window for dk in distraction_keywords)
    
    if is_currently_distracted:
        if score < 40:
            command = "STRICT POPUP: Your focus has dropped significantly. Please return to your task immediately."
        elif score < 70:
            command = "NOTIFY: You seem distracted. Consider refocusing on your current task."
        else:
            command = "CONTINUE MONITORING"
    else:
        command = "CONTINUE MONITORING"
    
    return {
        "focus_state": "FOCUSED" if not is_currently_distracted else "DISTRACTED",
        "productivity_score": score,
        "intervention_needed": is_currently_distracted,
        "supervisor_command": command,
        "reasoning": f"Fallback analysis ({reason}): {distraction_count}/{total_entries} distraction entries.",
        "productive_keywords": [],
        "distraction_keywords": distraction_keywords[:5]
    }


# =============================================================================
# INTENT HANDLERS
# =============================================================================

def parse_deadline_data_from_input(text: str) -> Dict[str, Any]:
    """Parse deadline data that came from Deadline Guardian via Supervisor."""
    try:
        data = json.loads(text)
        return {
            "critical_deadline": data.get("next_deadline", data.get("critical_deadline", "TBD")),
            "deadline_risk": data.get("risk_level", data.get("deadline_risk", "unknown")),
            "deadlines": data.get("deadlines", [])
        }
    except (json.JSONDecodeError, TypeError):
        return {
            "critical_deadline": text if text else "TBD",
            "deadline_risk": "unknown",
            "deadlines": []
        }


async def handle_start_monitoring(request: SupervisorRequest) -> SupervisorResponse:
    """Start focus monitoring session with deadline data from Supervisor."""
    if state.is_running:
        return SupervisorResponse(
            request_id=request.request_id,
            agent_name="focus_enforcer_agent",
            status="success",
            output=SuccessOutput(
                result={"message": "Monitoring already running", "status": "already_active"},
                confidence=1.0
            )
        )
    
    dg_data = parse_deadline_data_from_input(request.input.text)
    state.dg_data = dg_data
    
    extra = request.input.metadata.extra
    state.paa_data = {
        "goal": extra.get("goal", "Complete current tasks"),
        "target_apps": extra.get("target_apps", "VS Code, Browser, Terminal")
    }
    
    state.is_running = True
    state.user_id = request.context.user_id
    state.activity_history = []
    state.hourly_summary = []
    
    state.focus_task = asyncio.create_task(monitor_loop())
    
    logger.info(f"Focus monitoring started for user {state.user_id}")
    
    return SupervisorResponse(
        request_id=request.request_id,
        agent_name="focus_enforcer_agent",
        status="success",
        output=SuccessOutput(
            result={
                "message": "Focus monitoring started",
                "status": "active",
                "deadline_context": dg_data,
                "monitoring_interval": "5 seconds",
                "analysis_interval": "60 seconds"
            },
            confidence=1.0,
            details=f"Monitoring with deadline: {dg_data.get('critical_deadline', 'TBD')}"
        )
    )


async def handle_stop_monitoring(request: SupervisorRequest) -> SupervisorResponse:
    """Stop focus monitoring session."""
    if not state.is_running:
        return SupervisorResponse(
            request_id=request.request_id,
            agent_name="focus_enforcer_agent",
            status="success",
            output=SuccessOutput(
                result={"message": "Monitoring not running", "status": "inactive"},
                confidence=1.0
            )
        )
    
    state.is_running = False
    if state.focus_task:
        state.focus_task.cancel()
        try:
            await state.focus_task
        except asyncio.CancelledError:
            pass
        state.focus_task = None
    
    summary = {
        "message": "Focus monitoring stopped",
        "status": "stopped",
        "total_entries": len(state.activity_history),
        "last_analysis": state.last_analysis
    }
    
    logger.info("Focus monitoring stopped.")
    
    return SupervisorResponse(
        request_id=request.request_id,
        agent_name="focus_enforcer_agent",
        status="success",
        output=SuccessOutput(result=summary, confidence=1.0)
    )


async def handle_analyze_focus(request: SupervisorRequest) -> SupervisorResponse:
    """Analyze current focus state with deadline context from Supervisor."""
    dg_data = parse_deadline_data_from_input(request.input.text)
    
    analysis = await analyze_focus({
        "paa_data": state.paa_data,
        "dg_data": dg_data,
        "activity_history": state.activity_history,
        "hourly_summary": state.hourly_summary
    }, execute_intervention=True)
    
    state.last_analysis = analysis
    
    return SupervisorResponse(
        request_id=request.request_id,
        agent_name="focus_enforcer_agent",
        status="success",
        output=SuccessOutput(
            result=analysis,
            confidence=analysis.get("productivity_score", 0) / 100.0,
            details=analysis.get("reasoning", "")
        )
    )


async def handle_check_status(request: SupervisorRequest) -> SupervisorResponse:
    """Check current monitoring status."""
    status = {
        "is_monitoring": state.is_running,
        "user_id": state.user_id,
        "activity_entries": len(state.activity_history),
        "deadline_context": state.dg_data,
        "last_analysis": state.last_analysis
    }
    
    return SupervisorResponse(
        request_id=request.request_id,
        agent_name="focus_enforcer_agent",
        status="success",
        output=SuccessOutput(result=status, confidence=1.0)
    )


# =============================================================================
# FASTAPI APPLICATION
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Focus Enforcer Service starting up...")
    yield
    logger.info("Focus Enforcer Service shutting down...")
    if state.is_running:
        state.is_running = False
        if state.focus_task:
            state.focus_task.cancel()


app = FastAPI(
    title="Focus Enforcer Agent",
    description="Monitors user focus and productivity with OS-level interventions",
    version="2.1.2", # Version bump for log change
    lifespan=lifespan
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent": "focus_enforcer_agent",
        "monitoring_active": state.is_running,
        "cohere_available": co is not None,
        "model": "command-a-03-2025"
    }


@app.post("/handle", response_model=SupervisorResponse)
async def handle_supervisor_request(request: SupervisorRequest) -> SupervisorResponse:
    """Main handler for Supervisor requests."""
    logger.info(f"Received intent: {request.intent}")
    
    intent_handlers = {
        "focus.start_monitoring": handle_start_monitoring,
        "focus.stop_monitoring": handle_stop_monitoring,
        "focus.analyze": handle_analyze_focus,
        "focus.check_status": handle_check_status,
        "productivity.assess": handle_analyze_focus,
    }
    
    handler = intent_handlers.get(request.intent)
    if not handler:
        return SupervisorResponse(
            request_id=request.request_id,
            agent_name="focus_enforcer_agent",
            status="error",
            error=ErrorOutput(type="unknown_intent", message=f"Unknown intent: {request.intent}")
        )
    
    try:
        return await handler(request)
    except Exception as e:
        logger.error(f"Handler error: {e}")
        return SupervisorResponse(
            request_id=request.request_id,
            agent_name="focus_enforcer_agent",
            status="error",
            error=ErrorOutput(type="handler_error", message=str(e))
        )


# =============================================================================
# LEGACY ENDPOINTS (BACKWARD COMPATIBILITY)
# =============================================================================

@app.post("/start_focus")
async def legacy_start_focus(request: StartFocusRequest):
    """Legacy endpoint for backward compatibility."""
    state.paa_data = {
        "goal": request.goal,
        "target_apps": request.target_apps
    }
    state.dg_data = {"critical_deadline": request.critical_deadline}
    
    supervisor_req = SupervisorRequest(
        request_id=str(uuid.uuid4()),
        agent_name="focus_enforcer_agent",
        intent="focus.start_monitoring",
        input=AgentInput(text=request.critical_deadline),
        context=AgentContext(user_id=request.user_id, file_uploads=None)
    )
    
    # Manually populate metadata for legacy calls
    supervisor_req.input.metadata.extra = {
        "goal": request.goal,
        "target_apps": request.target_apps
    }
    
    response = await handle_start_monitoring(supervisor_req)
    return {"status": "success" if response.status == "success" else "error", "data": response.output.result if response.output else None}


@app.post("/stop_focus")
async def legacy_stop_focus(request: StopFocusRequest):
    """Legacy endpoint for backward compatibility."""
    supervisor_req = SupervisorRequest(
        request_id=str(uuid.uuid4()),
        agent_name="focus_enforcer_agent",
        intent="focus.stop_monitoring",
        input=AgentInput(text=""),
        context=AgentContext(user_id=request.user_id)
    )
    
    response = await handle_stop_monitoring(supervisor_req)
    return {"status": "success" if response.status == "success" else "error", "data": response.output.result if response.output else None}


@app.post("/agent_test")
async def legacy_agent_test(request: AgentInputModel):
    """Legacy endpoint for testing analysis."""
    try:
        input_data = json.loads(request.agent_input_json)
        analysis = await analyze_focus(input_data, execute_intervention=True)
        return {"status": "success", "analysis": analysis}
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)