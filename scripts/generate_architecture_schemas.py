#!/usr/bin/env python3
"""Publish the architecture contract schemas from their models.

``artifacts/architecture/*_SCHEMA.json`` are the published JSON Schemas of the
candidate/simulation-admission models. They are generated here, never edited by
hand; ``tests/unit/test_contract_truth.py`` fails when a committed schema no
longer equals its model.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from commander_lab.candidates.models import (
    CandidateValidationReport,
    DeckCandidateSet,
    FutureXmageScenario,
    SimulationCandidateQueue,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "architecture"

SCHEMAS: dict[str, type[BaseModel]] = {
    "CANDIDATE_SET_SCHEMA.json": DeckCandidateSet,
    "CANDIDATE_VALIDATION_REPORT_SCHEMA.json": CandidateValidationReport,
    "FUTURE_XMAGE_SCENARIO_SCHEMA.json": FutureXmageScenario,
    "SIMULATION_CANDIDATE_QUEUE_SCHEMA.json": SimulationCandidateQueue,
}


def schemas() -> dict[str, dict[str, Any]]:
    return {name: model.model_json_schema() for name, model in SCHEMAS.items()}


def main() -> None:
    """Rewrite a published schema only when its content differs from the model."""
    OUT.mkdir(parents=True, exist_ok=True)
    for name, schema in schemas().items():
        path = OUT / name
        if path.is_file() and json.loads(path.read_text(encoding="utf-8")) == schema:
            continue
        path.write_text(json.dumps(schema, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
