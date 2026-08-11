from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from commander_lab import __version__
from commander_lab.acceptance import run_phase10_acceptance
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
        version=__version__,
        description=(
            "Local structured tool server. All simulation numbers are structural_model_estimates."
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

    @app.post("/v1/demos/phase10")
    def run_phase10_demo(
        iterations: int = 4, seed: int = 20260805, workers: int = 1
    ) -> dict[str, object]:
        if iterations < 1 or iterations > 100:
            raise HTTPException(status_code=422, detail="demo iterations must be between 1 and 100")
        return run_phase10_acceptance(
            root,
            iterations=iterations,
            seed=seed,
            workers=workers,
            output_directory=Path(root) / "data/runs/phase10_api_demo",
            include_api_self_test=True,
        )

    app.state.commander_service = service
    app.state.tool_registry = registry
    return app
