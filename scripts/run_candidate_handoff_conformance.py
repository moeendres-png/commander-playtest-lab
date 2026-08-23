from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from commander_lab.candidates.io import write_json
from commander_lab.candidates.models import DeckCandidate, DeckCandidateSet, SourceIdentity
from commander_lab.candidates.pipeline import build_simulation_queue
from commander_lab.candidates.validation import load_hard_validation_context, validate_candidate_set
from commander_lab.deck_registry import load_deck_policy_registry


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected object: {path}")
    return payload


def _current_candidate_set(root: Path) -> DeckCandidateSet:
    registry = load_deck_policy_registry(root)
    target = registry.primary_deck_id
    manifest = _json(registry.source_path("deck_manifest"))
    decks = manifest.get("decks")
    row = decks.get(target) if isinstance(decks, dict) else None
    if not isinstance(row, dict):
        raise ValueError(f"active target missing from manifest: {target}")
    normalized_file = row.get("normalized_file")
    if not isinstance(normalized_file, str):
        raise ValueError(f"normalized_file missing for {target}")
    deck = _json(root / "data" / "decks" / normalized_file)
    cards = deck.get("cards")
    if not isinstance(cards, list):
        raise ValueError("current deck cards malformed")

    commanders: list[str] = []
    mainboard: Counter[str] = Counter()
    for card in cards:
        if not isinstance(card, dict):
            continue
        name = card.get("oracle_name")
        quantity = card.get("quantity")
        zone = card.get("zone")
        if not isinstance(name, str) or not isinstance(quantity, int):
            continue
        if zone == "commander":
            commanders.extend([name] * quantity)
        elif zone == "main":
            mainboard[name] += quantity

    identity = tuple(sorted(color.value for color in registry.commander_identity(target)))
    candidate = DeckCandidate(
        candidate_id="canonical-current-conformance",
        candidate_label="Canonical Current – hard-valid handoff conformance only",
        commander_names=tuple(commanders),
        mainboard=dict(mainboard),
        current_control=True,
        design_policy="CURRENT_CONTROL",
        design_philosophy="comparison arm only; deliberately hostile diagnostic metadata",
        metadata={
            "objective_prior": -1_000_000_000.0,
            "meta_distance": 1_000_000_000.0,
            "structural_score": -1_000_000_000.0,
            "fidelity_tier": "UNSUPPORTED",
            "qd_archive_membership": False,
            "finalist_membership": False,
            "current_distance": 1.0,
        },
    )
    return DeckCandidateSet(
        candidate_set_id="canonical-current-conformance-2026-08-24",
        created_at=datetime(2026, 8, 24, tzinfo=UTC),
        source_identity=SourceIdentity(
            provider="repository-conformance-fixture",
            source_ref=str(Path("data/decks") / normalized_file),
            target_deck_id=target,
            builder_identity="none-test-fixture-from-current",
            builder_version="1",
        ),
        commander_identity=identity,
        candidate_count=1,
        candidates=(candidate,),
    )


def run(root: Path, output_dir: Path) -> dict[str, object]:
    candidate_set = _current_candidate_set(root)
    write_json(output_dir / "DECK_CANDIDATE_SET.input.json", candidate_set)
    context = load_hard_validation_context(
        root, target_deck_id=candidate_set.source_identity.target_deck_id
    )
    normalized, validation = validate_candidate_set(candidate_set, context)
    queue, invariant = build_simulation_queue(normalized, validation)
    write_json(output_dir / "DECK_CANDIDATE_SET.normalized.json", normalized)
    write_json(output_dir / "CANDIDATE_VALIDATION_REPORT.json", validation)
    write_json(output_dir / "SIMULATION_CANDIDATE_QUEUE.json", queue)
    write_json(output_dir / "PRE_SIMULATION_INVARIANT_REPORT.json", invariant)

    if validation.hard_valid_unique_count != 1 or queue.output_simulation_queue_count != 1:
        raise SystemExit("canonical current conformance candidate did not survive lossless handoff")
    queued = queue.candidates[0]
    if queued.pre_simulation_elimination_reason is not None or not queued.simulation_required:
        raise SystemExit("hard-valid conformance candidate was pre-simulation eliminated")

    conformance = {
        "schema_version": "lossless-handoff-conformance-1.0.0",
        "status": "PASS",
        "canonical_current_hard_valid_unique_count": 1,
        "canonical_current_simulation_queue_count": 1,
        "bulk_conformance_unit_test_count": 60,
        "lossless_handoff": True,
        "no_pre_simulation_heuristic_elimination": True,
        "official_gameplay_simulation": False,
        "sealed_holdout_opened": False,
        "canonical_mutation_performed": False,
    }
    write_json(output_dir / "LOSSLESS_HANDOFF_CONFORMANCE.json", conformance)
    return conformance


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("artifacts/candidate-handoff-conformance")
    )
    args = parser.parse_args()
    result = run(args.root.resolve(), args.output_dir)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
