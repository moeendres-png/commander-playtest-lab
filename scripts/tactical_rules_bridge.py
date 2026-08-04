#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from commander_lab.engine.rules import TacticalRulesAdapter  # noqa: E402
from commander_lab.models import (  # noqa: E402
    ActionProposal,
    BridgeRequest,
    RulesDeckInput,
    RulesGameRequest,
    TacticalScenario,
)


def success(request_id: str, result: dict) -> None:
    print(json.dumps({"request_id": request_id, "ok": True, "result": result}), flush=True)


def failure(request_id: str, exc: Exception) -> None:
    print(
        json.dumps(
            {
                "request_id": request_id,
                "ok": False,
                "error": {"code": type(exc).__name__, "message": str(exc)},
            }
        ),
        flush=True,
    )


def main() -> int:
    adapter = TacticalRulesAdapter()
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        request_id = "unknown"
        try:
            request = BridgeRequest.model_validate_json(raw)
            request_id = request.request_id
            method = request.method
            params = request.params
            if method == "probe":
                result = adapter.probe().model_dump(mode="json")
            elif method == "load_deck":
                result = adapter.load_deck(RulesDeckInput.model_validate(params["deck"])).model_dump(mode="json")
            elif method == "start_commander_game":
                result = adapter.start_commander_game(
                    RulesGameRequest.model_validate(params["request"])
                ).model_dump(mode="json")
            elif method == "create_scenario":
                result = adapter.create_scenario(
                    TacticalScenario.model_validate(params["scenario"])
                ).model_dump(mode="json")
            elif method == "get_state":
                result = {"state": adapter.get_state(params["session_id"]).model_dump(mode="json")}
            elif method == "get_legal_actions":
                result = {
                    "actions": [
                        item.model_dump(mode="json")
                        for item in adapter.get_legal_actions(params["session_id"])
                    ]
                }
            elif method == "submit_action":
                state = adapter.submit_action(
                    params["session_id"], ActionProposal.model_validate(params["proposal"])
                )
                result = {"state": state.model_dump(mode="json")}
            elif method == "get_logs":
                result = adapter.get_logs(params["session_id"]).model_dump(mode="json")
            elif method == "get_result":
                result = adapter.get_result(params["session_id"]).model_dump(mode="json")
            elif method == "shutdown":
                success(request_id, {"shutdown": True})
                return 0
            else:
                raise ValueError(f"unknown bridge method: {method}")
            success(request_id, result)
        except Exception as exc:
            failure(request_id, exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
