from pathlib import Path

from fastapi.testclient import TestClient

from commander_lab.api import create_app

ROOT = Path(__file__).resolve().parents[2]


def test_function_tool_server_lists_and_invokes_tools() -> None:
    with TestClient(create_app(ROOT)) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["tool_count"] == 4
        tools = client.get("/v1/tools")
        assert tools.status_code == 200
        response = client.post(
            "/v1/tools/deck_decision_diagnose:invoke",
            json={"arguments": {"comparison": {"status": "rejected"}}},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        expert = client.get("/v1/expert/tools")
        assert len(expert.json()["tools"]) == 100


def test_live_workflow_endpoint_requires_openai_runtime(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with TestClient(create_app(ROOT)) as client:
        response = client.post(
            "/v1/workflows:run",
            json={"user_goal": "Inspect RogShai using structured local tools."},
        )
        assert response.status_code == 503
        assert "OPENAI_API_KEY" in response.json()["detail"]
