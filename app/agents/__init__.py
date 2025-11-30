"""
Agent service modules for the Supervisor system.

This package contains HTTP service wrappers for agents that need to be
deployed alongside the Supervisor. Each service implements the Supervisor
handshake contract (SupervisorRequest/SupervisorResponse).
"""

from .focus_enforcer_service import app as focus_enforcer_app

__all__ = [
    "focus_enforcer_app",
]
