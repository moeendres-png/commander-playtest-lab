"""Published contracts are generated from their sources of truth, never hand-kept.

The architecture scenario schema said ``player_count: const 4`` while its model
had accepted 2..6 since the six-player parity change, and the full-game
invariant report hard-coded 2..5 while the runner runs 2..6. These tests fail
the moment a published contract drifts from the model or constants it states.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules.full_game import XmageFullGameRunner

ROOT = Path(__file__).resolve().parents[2]


def _script(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name", sorted(_script("generate_architecture_schemas").SCHEMAS))
def test_every_published_architecture_schema_equals_its_model(name: str) -> None:
    published = json.loads((ROOT / "artifacts" / "architecture" / name).read_text(encoding="utf-8"))
    assert published == _script("generate_architecture_schemas").schemas()[name], (
        f"{name} drifted from its model; run scripts/generate_architecture_schemas.py"
    )


def test_the_published_scenario_schema_accepts_every_count_the_runner_runs() -> None:
    published = json.loads(
        (ROOT / "artifacts/architecture/FUTURE_XMAGE_SCENARIO_SCHEMA.json").read_text(
            encoding="utf-8"
        )
    )
    player_count = published["properties"]["player_count"]
    assert player_count.get("minimum") == XmageFullGameRunner.MIN_PLAYERS
    assert player_count.get("maximum") == XmageFullGameRunner.MAX_PLAYERS
    assert FutureXmageScenario.model_json_schema()["properties"]["player_count"] == player_count


def test_the_invariant_report_states_the_runner_range() -> None:
    report = _script("generate_full_game_contract_artifacts").invariant_report()
    assert report["min_players"] == XmageFullGameRunner.MIN_PLAYERS
    assert report["max_players"] == XmageFullGameRunner.MAX_PLAYERS
    assert report["operational_pod_sizes"] == list(
        range(XmageFullGameRunner.MIN_PLAYERS, XmageFullGameRunner.MAX_PLAYERS + 1)
    )
    assert report["primary_decision_pod_size"] == 4
    assert {2, 3, 4, 5} <= set(report["operational_pod_sizes"]), "2-5P conformance is the floor"
