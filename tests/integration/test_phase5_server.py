from pathlib import Path

from fastapi.testclient import TestClient

from commander_lab.api import create_app

ROOT = Path(__file__).resolve().parents[2]


def test_function_tool_server_lists_and_invokes_tools() -> None:
    client = TestClient(create_app(ROOT))
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["tool_count"] == 92
    tools = client.get("/v1/tools")
    assert tools.status_code == 200
    response = client.post(
        "/v1/tools/inspect_deck:invoke",
        json={"arguments": {"deck_id": "korvold/current", "include_cards": False}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_live_workflow_endpoint_requires_openai_runtime(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = TestClient(create_app(ROOT))
    response = client.post(
        "/v1/workflows:run",
        json={"user_goal": "Inspect Korvold using structured local tools."},
    )
    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]
