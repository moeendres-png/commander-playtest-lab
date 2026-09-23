from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules.full_game import (
    FULL_GAME_DECISION_PROTOCOL_VERSION,
    FULL_GAME_EVIDENCE_CLASS,
    FullGamePilotBinding,
    XmageFullGameRunner,
)
from commander_lab.importers.opponents import OpponentProfileImporter
from commander_lab.models import (
    CommanderConfiguration,
    Deck,
    DeckEntry,
    DeckZone,
    PilotConfig,
    PilotDecisionMode,
    PilotStrength,
    RulesDeckInput,
)

ROOT = Path(__file__).resolve().parents[1]
XMAGE_COMMIT = "db134b9737e951367d65ef5806ad986319cc73ab"
DEFAULT_SEED = 20260923
DEFAULT_SMOKE_DECISIONS = 35

ROGSHAI_PATH = Path("data/decks/rogshai_current.json")
KAERVEK_PATH = Path("data/decks/opponents/kaervek/current/deck.json")
HOSTS_PATH = Path("data/opponents/hosts_of_mordor_precon.json")
LOREHOLD_PATH = Path("data/opponents/lorehold_spirit_precon.json")
REAL_DECK_PATHS = (ROGSHAI_PATH, KAERVEK_PATH, HOSTS_PATH, LOREHOLD_PATH)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"deck source must be a JSON object: {path}")
    return payload


def _load_current_rogshai(root: Path) -> Deck:
    return Deck.model_validate(_read_json(root / ROGSHAI_PATH))


def _load_current_kaervek(root: Path) -> Deck:
    payload = _read_json(root / KAERVEK_PATH)
    commander = str(payload.get("commander", "")).strip()
    if not commander:
        raise ValueError("Kaervek source has no commander")
    raw_cards = payload.get("cards")
    if not isinstance(raw_cards, list):
        raise ValueError("Kaervek source has no cards list")
    cards = [
        DeckEntry(
            oracle_name=str(row["oracle_name"]),
            quantity=int(row.get("quantity", 1)),
            zone=DeckZone(str(row.get("zone", "main"))),
        )
        for row in raw_cards
        if isinstance(row, dict)
    ]
    return Deck(
        deck_id=str(payload["deck_id"]),
        name=str(payload["name"]),
        commander=CommanderConfiguration(commanders=(commander,), uses_partner=False),
        cards=cards,
        deck_hash=str(payload["deck_hash"]),
        notes="Normalized read-only from current verified Kaervek source for technical XMage smoke.",
    )


def _load_official_precon(root: Path, path: Path) -> Deck:
    profiles = OpponentProfileImporter().import_file(root / path)
    if len(profiles) != 1:
        raise ValueError(f"expected exactly one opponent profile in {path}, got {len(profiles)}")
    profile = profiles[0]
    if profile.deck is None:
        raise ValueError(f"opponent profile has no concrete deck: {path}")
    if profile.deck.total_cards != 100:
        raise ValueError(
            f"opponent profile must contain exactly 100 cards: {path} -> {profile.deck.total_cards}"
        )
    return profile.deck


def _semantic_deck_hash(deck: Deck) -> str:
    if deck.deck_hash is not None:
        return deck.deck_hash
    material = {
        "deck_id": deck.deck_id,
        "commander_names": list(deck.commander.commanders),
        "cards": [
            {
                "oracle_name": entry.oracle_name,
                "quantity": entry.quantity,
                "zone": entry.zone.value,
            }
            for entry in deck.grouped_entries()
            if entry.zone != DeckZone.MAYBEBOARD
        ],
    }
    return hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _to_rules_input(deck: Deck, source_path: Path) -> RulesDeckInput:
    if deck.total_cards != 100:
        raise ValueError(f"{deck.deck_id} is not an exact 100-card Commander deck")
    mainboard: list[str] = []
    sideboard: list[str] = []
    for entry in deck.cards:
        if entry.zone == DeckZone.COMMANDER:
            continue
        if entry.zone == DeckZone.MAIN:
            mainboard.extend([entry.oracle_name] * entry.quantity)
        elif entry.zone == DeckZone.SIDEBOARD:
            sideboard.extend([entry.oracle_name] * entry.quantity)
        elif entry.zone == DeckZone.MAYBEBOARD:
            continue
        else:  # pragma: no cover - enum exhaustiveness guard
            raise ValueError(f"unsupported deck zone: {entry.zone}")
    return RulesDeckInput(
        deck_id=deck.deck_id,
        name=deck.name,
        commander_names=deck.commander.commanders,
        mainboard=tuple(mainboard),
        sideboard=tuple(sideboard),
        deck_hash=_semantic_deck_hash(deck),
        source_path=source_path.as_posix(),
    )


def _binding(seat: int, deck: RulesDeckInput) -> FullGamePilotBinding:
    return FullGamePilotBinding(
        seat=seat,
        deck_id=deck.deck_id,
        strategy="generic",
        commander_names=deck.commander_names,
        config=PilotConfig(
            pilot_name="auto",
            strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
            mode=PilotDecisionMode.DETERMINISTIC,
        ),
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-full-game-policy-1.0.0",
    )


def build_setup(
    root: Path = ROOT,
    *,
    seed: int = DEFAULT_SEED,
) -> tuple[FutureXmageScenario, tuple[RulesDeckInput, ...], tuple[FullGamePilotBinding, ...]]:
    deck_models = (
        _load_current_rogshai(root),
        _load_current_kaervek(root),
        _load_official_precon(root, HOSTS_PATH),
        _load_official_precon(root, LOREHOLD_PATH),
    )
    decks = tuple(
        _to_rules_input(deck, path) for deck, path in zip(deck_models, REAL_DECK_PATHS, strict=True)
    )
    if len({deck.deck_id for deck in decks}) != 4:
        raise ValueError("real 4P smoke requires four distinct deck IDs")
    pilots = tuple(_binding(seat, deck) for seat, deck in enumerate(decks, start=1))
    own = decks[0]
    if own.deck_hash is None:  # pragma: no cover - _to_rules_input always binds it
        raise ValueError("RogShai smoke deck hash is missing")
    scenario = FutureXmageScenario(
        candidate_id=own.deck_id,
        deck_hash=own.deck_hash,
        opponent_deck_ids=tuple(deck.deck_id for deck in decks[1:]),
        player_count=4,
        seat=1,
        scenario_id="real-decks-4p-technical-smoke-v1",
        seed=seed,
        xmage_commit=XMAGE_COMMIT,
        bridge_version="xmage-engine-bridge-0.1.0-SNAPSHOT",
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-full-game-policy-1.0.0",
    )
    return scenario, decks, pilots


def run_smoke(*, smoke_decisions: int = DEFAULT_SMOKE_DECISIONS, seed: int = DEFAULT_SEED) -> dict[str, Any]:
    scenario, decks, pilots = build_setup(seed=seed)
    runner = XmageFullGameRunner(cwd=ROOT, request_timeout_seconds=120.0, max_decisions=50_000)
    smoke = runner.run_smoke(
        scenario=scenario,
        decks=decks,
        pilots=pilots,
        smoke_decision_target=smoke_decisions,
    )
    required = {"mulligan", "priority"}
    observed = set(smoke.observed_decision_classes)
    missing = sorted(required - observed)
    if missing:
        raise SystemExit(
            "real 4P technical smoke did not exercise required decision classes; "
            f"missing={missing} observed={sorted(observed)}"
        )
    result = {
        "schema_version": "real-4p-full-game-smoke/1.0.0",
        "status": "PASS",
        "scenario_id": scenario.scenario_id,
        "seed": scenario.seed,
        "player_count": scenario.player_count,
        "decision_count": smoke.decision_count,
        "smoke_decision_target": smoke.smoke_decision_target,
        "terminal_reached": smoke.terminal_reached,
        "clean_shutdown": smoke.clean_shutdown,
        "observed_decision_classes": list(smoke.observed_decision_classes),
        "engine_version": smoke.engine_version,
        "xmage_commit": smoke.xmage_commit,
        "decision_protocol_version": FULL_GAME_DECISION_PROTOCOL_VERSION,
        "evidence_class": FULL_GAME_EVIDENCE_CLASS,
        "deck_strength_evidence": False,
        "official_campaign_eligible": False,
        "consumed_gameplay_evidence": False,
        "holdout_consumed": False,
        "rules_authority": "xmage",
        "decision_authority": "commander_lab_external_pilots",
        "fallback_used": False,
        "decks": [
            {
                "seat": seat,
                "deck_id": deck.deck_id,
                "commander_names": list(deck.commander_names),
                "card_count": len(deck.mainboard) + len(deck.commander_names),
                "deck_hash": deck.deck_hash,
                "source_path": deck.source_path,
            }
            for seat, deck in enumerate(decks, start=1)
        ],
    }
    out = ROOT / "artifacts" / "xmage-full-game"
    out.mkdir(parents=True, exist_ok=True)
    (out / "REAL_4P_DECK_SMOKE.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a bounded 4P XMage technical smoke using four real 100-card decklists."
    )
    parser.add_argument("--smoke-decisions", type=int, default=DEFAULT_SMOKE_DECISIONS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate and materialize the four RulesDeckInput values without launching XMage.",
    )
    args = parser.parse_args()
    scenario, decks, _pilots = build_setup(seed=args.seed)
    if args.validate_only:
        payload = {
            "status": "PASS",
            "mode": "validate_only",
            "scenario_id": scenario.scenario_id,
            "deck_ids": [deck.deck_id for deck in decks],
            "card_counts": [
                len(deck.mainboard) + len(deck.commander_names) for deck in decks
            ],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    run_smoke(smoke_decisions=args.smoke_decisions, seed=args.seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
