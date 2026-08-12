from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Any

from commander_lab.models import WorkflowReport, WorkflowRequest
from commander_lab.tools import CommanderToolService, ToolRegistry

from .guardrails import (
    GuardrailViolation,
    WorkflowBudgetTracker,
    flatten_agent_input,
    forbidden_state_terms,
    validate_tool_output,
    validate_user_goal,
    validate_workflow_report,
)
from .tracing import LocalAgentTraceRecorder


class AgentsSdkUnavailable(RuntimeError):
    pass


@dataclass(slots=True)
class AgentRuntime:
    orchestrator: Any
    deck_analyst: Any
    simulation_analyst: Any
    red_team_reviewer: Any
    session: Any


def _load_sdk() -> dict[str, Any]:
    try:
        from agents import (
            Agent,
            GuardrailFunctionOutput,
            InputGuardrail,
            ModelSettings,
            OutputGuardrail,
            RunConfig,
            RunHooks,
            Runner,
            SQLiteSession,
            function_tool,
        )
        from openai.types.shared import Reasoning
    except ImportError as exc:
        raise AgentsSdkUnavailable(
            "Install the optional dependency with: pip install 'commander-playtest-lab[openai]'"
        ) from exc
    return {
        "Agent": Agent,
        "GuardrailFunctionOutput": GuardrailFunctionOutput,
        "InputGuardrail": InputGuardrail,
        "ModelSettings": ModelSettings,
        "OutputGuardrail": OutputGuardrail,
        "Reasoning": Reasoning,
        "RunConfig": RunConfig,
        "RunHooks": RunHooks,
        "Runner": Runner,
        "SQLiteSession": SQLiteSession,
        "function_tool": function_tool,
    }


def _sdk_tools(registry: ToolRegistry, function_tool: Any) -> list[Any]:
    tools: list[Any] = []
    for definition in registry.definitions:
        input_model = definition.input_model
        tool_name = definition.name
        description = definition.description

        def make_invoke(name: str, model: type[Any]) -> Any:
            async def invoke_tool(payload: Any) -> dict[str, Any]:
                validated = model.model_validate(payload)
                response = registry.invoke(name, validated.model_dump(mode="json"))
                validate_tool_output(response)
                return response.model_dump(mode="json")

            invoke_tool.__annotations__ = {"payload": model, "return": dict[str, Any]}
            return invoke_tool

        tool_callable = make_invoke(tool_name, input_model)
        tool_callable.__name__ = tool_name
        tool_callable.__doc__ = description
        tools.append(
            function_tool(
                tool_callable,
                name_override=tool_name,
                description_override=description,
                strict_mode=True,
            )
        )
    return tools


def _agent_guardrails(sdk: dict[str, Any]) -> tuple[Any, Any]:
    async def no_direct_state_mutation(_context: Any, _agent: Any, user_input: Any) -> Any:
        forbidden = forbidden_state_terms(flatten_agent_input(user_input))
        return sdk["GuardrailFunctionOutput"](
            output_info={"forbidden_terms": forbidden},
            tripwire_triggered=bool(forbidden),
        )

    async def structural_output_only(_context: Any, _agent: Any, output: Any) -> Any:
        try:
            report = (
                output
                if isinstance(output, WorkflowReport)
                else WorkflowReport.model_validate(output)
            )
            validate_workflow_report(report)
        except (ValueError, GuardrailViolation) as exc:
            return sdk["GuardrailFunctionOutput"](
                output_info={"error": str(exc)},
                tripwire_triggered=True,
            )
        return sdk["GuardrailFunctionOutput"](
            output_info={"estimate_type": report.estimate_type},
            tripwire_triggered=False,
        )

    input_guardrail = sdk["InputGuardrail"](
        guardrail_function=no_direct_state_mutation,
        name="no_direct_game_state_mutation",
        run_in_parallel=False,
    )
    output_guardrail = sdk["OutputGuardrail"](
        guardrail_function=structural_output_only,
        name="structural_estimate_output_only",
    )
    return input_guardrail, output_guardrail


def _reasoning_settings(sdk: dict[str, Any], request: WorkflowRequest) -> Any:
    effort = request.reasoning_effort.casefold()
    if effort not in {"none", "low", "medium", "high", "max"}:
        raise ValueError(f"unsupported reasoning effort: {request.reasoning_effort}")
    return sdk["ModelSettings"](
        tool_choice="required",
        parallel_tool_calls=False,
        max_tokens=request.budget.max_output_tokens_per_call,
        reasoning=sdk["Reasoning"](effort=effort),
        verbosity="low",
    )


def _budget_hooks(
    sdk: dict[str, Any],
    tracker: WorkflowBudgetTracker,
    trace: LocalAgentTraceRecorder,
) -> Any:
    class BudgetHookMethods:
        def __init__(self) -> None:
            self.started_calls = 0

        @staticmethod
        def _usage(context: Any) -> tuple[int, int, int]:
            usage = context.usage
            return (
                int(getattr(usage, "requests", 0) or 0),
                int(getattr(usage, "input_tokens", 0) or 0),
                int(getattr(usage, "output_tokens", 0) or 0),
            )

        async def on_llm_start(
            self,
            context: Any,
            agent: Any,
            system_prompt: str | None,
            input_items: list[Any],
        ) -> None:
            del system_prompt, input_items
            requests, input_tokens, output_tokens = self._usage(context)
            current_cost = (
                input_tokens / 1_000_000 * tracker.limits.input_cost_per_million_usd
                + output_tokens / 1_000_000 * tracker.limits.output_cost_per_million_usd
            )
            if self.started_calls >= tracker.limits.max_model_calls:
                raise GuardrailViolation("maximum model calls exceeded before next call")
            if input_tokens + output_tokens >= tracker.limits.max_total_tokens:
                raise GuardrailViolation("maximum token budget reached before next call")
            if current_cost >= tracker.limits.max_estimated_cost_usd:
                raise GuardrailViolation("maximum estimated API cost reached before next call")
            self.started_calls += 1
            trace.emit(
                "llm_started",
                {
                    "agent": getattr(agent, "name", type(agent).__name__),
                    "call_index": self.started_calls,
                    "usage_requests_before_call": requests,
                    "tokens_before_call": input_tokens + output_tokens,
                },
            )

        async def on_llm_end(self, context: Any, agent: Any, response: Any) -> None:
            del response
            requests, input_tokens, output_tokens = self._usage(context)
            trace.emit(
                "llm_completed",
                {
                    "agent": getattr(agent, "name", type(agent).__name__),
                    "requests": requests,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                },
            )
            if input_tokens + output_tokens > tracker.limits.max_total_tokens:
                raise GuardrailViolation("maximum total token budget exceeded")

        async def on_tool_start(self, context: Any, agent: Any, tool: Any) -> None:
            trace.emit(
                "tool_started",
                {
                    "agent": getattr(agent, "name", type(agent).__name__),
                    "tool": getattr(tool, "name", type(tool).__name__),
                    "tool_call_id": getattr(context, "tool_call_id", None),
                },
            )

        async def on_tool_end(self, context: Any, agent: Any, tool: Any, result: object) -> None:
            trace.emit(
                "tool_completed",
                {
                    "agent": getattr(agent, "name", type(agent).__name__),
                    "tool": getattr(tool, "name", type(tool).__name__),
                    "tool_call_id": getattr(context, "tool_call_id", None),
                    "result_type": type(result).__name__,
                },
            )

    run_hooks_base = sdk["RunHooks"]
    budget_hooks_type = type(
        "BudgetHooks",
        (run_hooks_base,),
        {
            "__init__": BudgetHookMethods.__init__,
            "_usage": staticmethod(BudgetHookMethods._usage),
            "on_llm_start": BudgetHookMethods.on_llm_start,
            "on_llm_end": BudgetHookMethods.on_llm_end,
            "on_tool_start": BudgetHookMethods.on_tool_start,
            "on_tool_end": BudgetHookMethods.on_tool_end,
        },
    )
    return budget_hooks_type()


def build_agent_runtime(
    service: CommanderToolService,
    *,
    request: WorkflowRequest,
) -> AgentRuntime:
    sdk = _load_sdk()
    registry = ToolRegistry(service)
    tools = _sdk_tools(registry, sdk["function_tool"])
    input_guardrail, output_guardrail = _agent_guardrails(sdk)
    specialist_common = (
        "You are a specialist in the Commander Playtest Lab. You may obtain evidence only by "
        "calling supplied structured tools. Never invent or mutate game state. Never describe "
        "structural_model_estimates as empirical win rates. Manual real-playtest ingestion and "
        "calibration are not part of the active product. Never call Tactical Oracle an external "
        "rules engine, and never claim XMage or Forge passed without a real provider execution. "
        "Include invocation identifiers or tool "
        "names in tool_invocations, and return WorkflowReport structured output."
    )
    settings = _reasoning_settings(sdk, request)
    deck_analyst = sdk["Agent"](
        name="Deck Analyst",
        model=request.model,
        instructions=(
            specialist_common + " Evaluate roles, weaknesses, cuts and upgrade candidates. "
            "Do not confirm a candidate "
            "without paired validation."
        ),
        tools=tools,
        model_settings=settings,
        output_type=WorkflowReport,
        output_guardrails=[output_guardrail],
    )
    simulation_analyst = sdk["Agent"](
        name="Simulation Analyst",
        model=request.model,
        instructions=(
            specialist_common
            + " Select scenarios, paired seeds and bounded run sizes; inspect uncertainty, aborts "
            "and model failures."
        ),
        tools=tools,
        model_settings=settings,
        output_type=WorkflowReport,
        output_guardrails=[output_guardrail],
    )
    red_team = sdk["Agent"](
        name="Red-Team Reviewer",
        model=request.model,
        instructions=(
            specialist_common
            + " Seek overfitting, weak cuts, role losses, alternative explanations and holdout "
            "failures before accepting a conclusion."
        ),
        tools=tools,
        model_settings=settings,
        output_type=WorkflowReport,
        output_guardrails=[output_guardrail],
    )
    orchestrator = sdk["Agent"](
        name="Orchestrator Agent",
        model=request.model,
        instructions=(
            specialist_common
            + " Understand the user goal, create a bounded validation plan, call local tools, use "
            "build_optimization_context first, choose the smallest "
            "suitable run profile, use the Deck "
            "Analyst, Simulation Analyst and Red-Team Reviewer when relevant, and summarize "
            "only evidence returned by tools. Agents may never alter deterministic game state."
        ),
        tools=[
            *tools,
            deck_analyst.as_tool(
                tool_name="deck_analyst",
                tool_description="Analyze deck roles, weaknesses, cuts and candidate upgrades.",
            ),
            simulation_analyst.as_tool(
                tool_name="simulation_analyst",
                tool_description="Design and review bounded structural simulation evidence.",
            ),
            red_team.as_tool(
                tool_name="red_team_reviewer",
                tool_description=(
                    "Challenge conclusions for overfitting and alternative explanations."
                ),
            ),
        ],
        model_settings=settings,
        output_type=WorkflowReport,
        input_guardrails=[input_guardrail],
        output_guardrails=[output_guardrail],
    )
    session_db = service.root / "data/runs/openai_sessions.sqlite"
    session = sdk["SQLiteSession"](request.session_id, str(session_db))
    return AgentRuntime(orchestrator, deck_analyst, simulation_analyst, red_team, session)


async def run_openai_workflow(
    service: CommanderToolService,
    request: WorkflowRequest,
) -> WorkflowReport:
    validate_user_goal(request.user_goal)
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required for live agent workflows")
    workflow_id = f"workflow-{uuid.uuid4().hex[:12]}"
    trace = LocalAgentTraceRecorder(service.trace_dir, workflow_id)
    trace.emit(
        "workflow_started",
        {
            "goal": request.user_goal,
            "session_id": request.session_id,
            "model": request.model,
            "budget": request.budget.model_dump(mode="json"),
        },
    )
    runtime = build_agent_runtime(service, request=request)
    sdk = _load_sdk()
    tracker = WorkflowBudgetTracker(request.budget)
    hooks = _budget_hooks(sdk, tracker, trace)
    try:
        result = await sdk["Runner"].run(
            runtime.orchestrator,
            request.user_goal,
            session=runtime.session,
            max_turns=request.budget.max_model_calls,
            hooks=hooks,
            run_config=sdk["RunConfig"](
                workflow_name="Commander Playtest Lab",
                trace_include_sensitive_data=False,
                trace_metadata={
                    "workflow_id": workflow_id,
                    "evidence_policy": "structural_empirical_separated",
                },
            ),
        )
        usage = result.context_wrapper.usage
        tracker.register_model_usage(
            calls=int(getattr(usage, "requests", 0) or 0),
            input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
        )
        output = result.final_output
        if not isinstance(output, WorkflowReport):
            output = WorkflowReport.model_validate(output)
        output = output.model_copy(
            update={
                "workflow_id": workflow_id,
                "goal": request.user_goal,
                "model_calls": tracker.model_calls,
                "total_tokens": tracker.total_tokens,
                "estimated_cost_usd": tracker.estimated_cost_usd,
            }
        )
        validate_workflow_report(output)
        trace.emit("workflow_completed", output.model_dump(mode="json"))
        return output
    except Exception as exc:
        trace.emit("workflow_failed", {"error": f"{type(exc).__name__}: {exc}"})
        raise
