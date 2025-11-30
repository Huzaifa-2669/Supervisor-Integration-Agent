from fastapi.testclient import TestClient

from app import server
from app.models import AgentResponse, OutputModel, Plan, PlanStep


def test_dependency_response_formatted(monkeypatch):
    dep_payload = {
        "dependencies": {"1": ["7"], "21": ["1"], "28": ["1"]},
        "execution_order": ["2", "3", "1", "21", "28"],
    }

    async def fake_execute_plan(query, plan, registry, context):
        step_outputs = {
            0: AgentResponse(
                request_id="r1",
                agent_name="task_dependency_agent",
                status="success",
                output=OutputModel(result=dep_payload),
                error=None,
            )
        }
        return step_outputs, []

    def fake_plan_tools(query, registry, history=None):
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

    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "tasks": [
                    {"task_id": "1", "task_name": "Implement Auth"},
                    {"task_id": "7", "task_name": "DB Setup"},
                    {"task_id": "21", "task_name": "Setup Environment"},
                    {"task_id": "28", "task_name": "Configure Database"},
                    {"task_id": "2", "task_name": "Design DB"},
                    {"task_id": "3", "task_name": "APIs"},
                ]
            }

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            return FakeResp()

    fake_httpx = type("FakeHttpx", (), {"AsyncClient": FakeAsyncClient})

    monkeypatch.setattr(server, "execute_plan", fake_execute_plan)
    monkeypatch.setattr(server, "plan_tools_with_llm", fake_plan_tools)
    monkeypatch.setattr(server, "httpx", fake_httpx)

    client = TestClient(server.app)
    resp = client.post(
        "/api/query",
        json={"query": "find dependencies", "user_id": None, "conversation_id": "c1", "options": {"debug": False}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "Execution order tasks" in data["answer"]
    assert "Implement Auth" in data["answer"]
    assert "Tasks with dependencies" in data["answer"]
