from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from commander_lab.agents.openai_workflow import AgentsSdkUnavailable, run_openai_workflow
from commander_lab.models import WorkflowRequest
from commander_lab.tools import CommanderToolService, ToolRegistry


class InvocationPayload(BaseModel):
    arguments: dict[str, Any]


def create_app(root: str | Path) -> FastAPI:
    service = CommanderToolService(root)
    registry = ToolRegistry(service)
    app = FastAPI(
        title="Commander Playtest Lab Function Tool Server",
        version="0.5.0",
        description=(
            "Local structured tool server. All simulation numbers are "
            "structural_model_estimates."
        ),
    )

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"status": "ok", "tool_count": len(registry.list_schemas())}

    @app.get("/v1/tools")
    def list_tools() -> dict[str, object]:
        return {"tools": registry.list_schemas()}

    @app.post("/v1/tools/{tool_name}:invoke")
    def invoke_tool(tool_name: str, payload: InvocationPayload) -> dict[str, object]:
        try:
            response = registry.invoke(tool_name, payload.arguments)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return response.model_dump(mode="json")

    @app.post("/v1/workflows:run")
    async def run_workflow(payload: WorkflowRequest) -> dict[str, object]:
        try:
            report = await run_openai_workflow(service, payload)
        except AgentsSdkUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return report.model_dump(mode="json")

    app.state.commander_service = service
    app.state.tool_registry = registry
    return app
