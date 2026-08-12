from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from commander_lab.agents import openai_workflow
from commander_lab.models import WorkflowRequest
from commander_lab.tools import CommanderToolService, ToolRegistry

ROOT = Path(__file__).resolve().parents[2]


class FakeAgent:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)

    def as_tool(self, *, tool_name: str, tool_description: str) -> dict[str, str]:
        return {"name": tool_name, "description": tool_description}


class FakeGuardrail:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


class FakeModelSettings:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


class FakeReasoning:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


class FakeSession:
    def __init__(self, session_id: str, db_path: str) -> None:
        self.session_id = session_id
        self.db_path = db_path


def fake_function_tool(func: Any, **kwargs: Any) -> Any:
    return SimpleNamespace(
        name=kwargs["name_override"],
        description=kwargs["description_override"],
        strict=kwargs["strict_mode"],
        signature=inspect.signature(func),
    )


def fake_sdk() -> dict[str, Any]:
    return {
        "Agent": FakeAgent,
        "GuardrailFunctionOutput": lambda **kwargs: SimpleNamespace(**kwargs),
        "InputGuardrail": FakeGuardrail,
        "ModelSettings": FakeModelSettings,
        "OutputGuardrail": FakeGuardrail,
        "Reasoning": FakeReasoning,
        "RunConfig": object,
        "RunHooks": object,
        "Runner": object,
        "SQLiteSession": FakeSession,
        "function_tool": fake_function_tool,
    }


def test_sdk_tool_wrappers_expose_only_the_validated_payload() -> None:
    registry = ToolRegistry(CommanderToolService(ROOT))
    tools = openai_workflow._sdk_tools(registry, fake_function_tool)
    assert len(tools) == 4
    assert all(list(tool.signature.parameters) == ["payload"] for tool in tools)
    assert all(tool.strict for tool in tools)


def test_runtime_is_thin_four_tool_synthesizer_with_session_and_guardrails(monkeypatch) -> None:
    monkeypatch.setattr(openai_workflow, "_load_sdk", fake_sdk)
    service = CommanderToolService(ROOT)
    request = WorkflowRequest(user_goal="Inspect RogShai using structured tools.")
    runtime = openai_workflow.build_agent_runtime(service, request=request)

    assert runtime.orchestrator.name == "Commander Decision Synthesizer"
    assert [tool.name for tool in runtime.orchestrator.tools] == [
        "deck_decision_prepare",
        "deck_decision_run",
        "deck_decision_diagnose",
        "deck_decision_bundle",
    ]
    assert "build_optimization_context" not in runtime.orchestrator.instructions
    assert "expert tool" in runtime.orchestrator.instructions
    assert runtime.orchestrator.output_type.__name__ == "WorkflowReport"
    assert len(runtime.orchestrator.input_guardrails) == 1
    assert len(runtime.orchestrator.output_guardrails) == 1
    assert runtime.session.session_id == request.session_id
    assert runtime.orchestrator.model_settings.reasoning.effort == "high"
    assert (
        runtime.orchestrator.model_settings.max_tokens == request.budget.max_output_tokens_per_call
    )


def test_unsupported_reasoning_effort_fails_before_live_run() -> None:
    request = WorkflowRequest(
        user_goal="Inspect RogShai.",
        reasoning_effort="extreme",
    )
    with pytest.raises(ValueError):
        openai_workflow._reasoning_settings(fake_sdk(), request)


class FakeRunConfig:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


class FakeRunHooks:
    pass


class FakeRunner:
    @staticmethod
    async def run(
        agent: Any,
        user_input: str,
        *,
        session: Any,
        max_turns: int,
        hooks: Any,
        run_config: Any,
    ) -> Any:
        del session, max_turns, run_config
        usage = SimpleNamespace(requests=0, input_tokens=0, output_tokens=0, total_tokens=0)
        context = SimpleNamespace(usage=usage)
        await hooks.on_llm_start(context, agent, None, [user_input])
        usage.requests = 2
        usage.input_tokens = 100
        usage.output_tokens = 50
        usage.total_tokens = 150
        await hooks.on_llm_end(context, agent, SimpleNamespace())
        from commander_lab.models import WorkflowReport

        return SimpleNamespace(
            context_wrapper=context,
            final_output=WorkflowReport(
                workflow_id="model-placeholder",
                goal=user_input,
                conclusion="RogShai was inspected through local tools.",
                evidence=("Validated local tool evidence.",),
                caveats=("Structural estimate only.",),
                tool_invocations=("deck_decision_prepare",),
            ),
        )


@pytest.mark.asyncio
async def test_live_workflow_path_with_fake_sdk(monkeypatch, tmp_path) -> None:
    sdk = fake_sdk()
    sdk.update({"RunConfig": FakeRunConfig, "RunHooks": FakeRunHooks, "Runner": FakeRunner})
    monkeypatch.setattr(openai_workflow, "_load_sdk", lambda: sdk)
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-placeholder")
    service = CommanderToolService(ROOT)
    request = WorkflowRequest(
        user_goal="Inspect RogShai using structured local tools.",
        session_id="phase5-test-session",
        budget={
            "max_model_calls": 4,
            "max_total_tokens": 1000,
            "max_output_tokens_per_call": 500,
            "max_estimated_cost_usd": 1.0,
            "input_cost_per_million_usd": 1.0,
            "output_cost_per_million_usd": 2.0,
        },
    )
    report = await openai_workflow.run_openai_workflow(service, request)
    assert report.model_calls == 2
    assert report.total_tokens == 150
    assert report.estimated_cost_usd == pytest.approx(0.0002)
    assert report.estimate_type == "structural_model_estimates"
    assert report.workflow_id.startswith("workflow-")
    trace_files = list(service.trace_dir.glob(f"{report.workflow_id}.jsonl"))
    assert len(trace_files) == 1
