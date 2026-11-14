"""Per-card evidence behind the tier list (Refs #1185, R3).

Every figure here is a count with its denominator, a missing value is stated as missing and
never as zero, and the evidence layers stay apart: facts and mechanical features, observed
decks, observed games, verified combos and simulated results. Nothing in this module ranks a
card. The tier of every card is ``UNRATED`` until a model with outcome evidence exists (see
``TIER_POLICY``); frequency in source decks, EDHREC inclusion or lift, and counts of any kind
never set a tier on their own.

The Owner's own marks (favorite, excluded, note) are not read here. They are filters and
availability conditions for the Owner's own use, never a strength signal, and
``tests/unit/test_studio_evidence.py`` pins that: changing a mark must not change one byte of
the evidence.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Sequence
from pathlib import Path

from .builder import ALL_DECKS, SMALL_DENOMINATOR, bound_to, pool_cards
from .sources import calculate_card_coverage_record, load_spellbook_combo_cards
from .store import StudioStore

EVIDENCE_SCHEMA = "studio-evidence-1"
MECHANICAL_RULES_VERSION = "mechanical-1"

VIEW_GLOBAL = "global"
VIEW_COMMANDER = "commander"
VIEWS = (VIEW_GLOBAL, VIEW_COMMANDER)

LAYER_FACT = "fact"
LAYER_DECK = "observed_deck"
LAYER_GAME = "observed_game"
LAYER_COMBO = "combo_verified"
LAYER_SIMULATED = "simulated_result"
LAYERS = (LAYER_FACT, LAYER_DECK, LAYER_GAME, LAYER_COMBO, LAYER_SIMULATED)
# The layers the page counts as "present" (its sort key "Anzahl vorhandener Schichten" and
# the coverage list). The simulated layer is shown on its own but is not counted: simulation
# outcomes count in the tier list only through the Owner's adjustable weight of the strength
# index (default 0), never through a sort key or a coverage figure (Owner, 2026-11-12).
COVERAGE_LAYERS = (LAYER_FACT, LAYER_DECK, LAYER_GAME, LAYER_COMBO)

PRESENT = "PRESENT"
# Zero hits in a corpus that is known and non-empty: a real descriptive zero, not weakness.
ABSENT_IN_KNOWN_CORPUS = "ABSENT_IN_KNOWN_CORPUS"
# The source exists and was read, and has no row for this card.
NONE_RECORDED = "NONE_RECORDED"
# No source for this layer has been imported yet; the value is unknown, not zero.
NOT_COLLECTED = "NOT_COLLECTED"
NOT_APPLICABLE = "NOT_APPLICABLE"

UNRATED = "UNRATED"
NO_VALIDATED_MODEL = "NO_VALIDATED_OUTCOME_MODEL"

TIER_POLICY: dict[str, object] = {
    "version": "tier-policy-1",
    "tiers": ["S", "A", "B", "C", "D"],
    "validated_model": None,
    "rule": (
        "A result tier needs a target defined in advance, a calibrated model and out-of-sample "
        "(leave-commander-out) evidence. No such model exists, so every card is UNRATED. "
        "Corpus frequency, EDHREC inclusion or lift, the Owner's marks and counts of any kind "
        "never set a tier on their own. Missing evidence is never a low tier."
    ),
    "never_inputs": ["favorite", "excluded", "note", "corpus_frequency", "edhrec_inclusion"],
}

_COMBOS_PATH = Path(__file__).resolve().parents[3] / "data" / "meta" / "spellbook_combos.json"
_GAME_COHORT_PREFIXES = ("playgroup",)
_ETB = re.compile(r"\b(?:when|whenever)\b[^.\n]*\benters\b", re.IGNORECASE)
_ADD_MANA = re.compile(r"\badd\b[^.\n]*\{", re.IGNORECASE)


def mechanical_features(type_line: str, text: str, produced_mana: str) -> list[dict[str, object]]:
    """Deterministic features read from the type line and the Oracle text.

    Each feature carries the rule that decides it. They state what a card is or says, not how
    good it is, and the rules are versioned (``MECHANICAL_RULES_VERSION``).
    """
    front = type_line.split(" // ")[0]
    return [
        {
            "feature": "creature_spell",
            "holds": "Creature" in front,
            "rule": "the front face is a creature",
        },
        {"feature": "land", "holds": "Land" in front, "rule": "the front face is a land"},
        {
            "feature": "enters_trigger_text",
            "holds": bool(_ETB.search(text)),
            "rule": "the text has a 'when or whenever ... enters' trigger (own or another)",
        },
        {
            "feature": "produces_mana",
            "holds": bool(produced_mana) or bool(_ADD_MANA.search(text)),
            "rule": "Scryfall lists produced mana, or the text says 'Add {...}'",
        },
    ]


def _role_claims(db: sqlite3.Connection) -> dict[str, list[dict[str, object]]]:
    claims: dict[str, list[dict[str, object]]] = {}
    seen: set[tuple[object, ...]] = set()
    for row in db.execute(
        "SELECT oracle_id, role, role_origin, original_tag, mapping_rule FROM card_role_claim "
        "ORDER BY oracle_id, role, role_origin, original_tag, mapping_rule"
    ):
        key = tuple(row)
        if key in seen:
            continue
        seen.add(key)
        claims.setdefault(str(row["oracle_id"]), []).append(
            {
                "role": row["role"],
                "origin": row["role_origin"],
                "original_tag": row["original_tag"],
                "mapping_rule": row["mapping_rule"],
            }
        )
    return claims


def _is_game_cohort(cohort: str) -> bool:
    return cohort.startswith(_GAME_COHORT_PREFIXES)


def _observations(
    db: sqlite3.Connection, name_to_id: dict[str, str], commander_names: Sequence[str]
) -> dict[str, list[dict[str, object]]]:
    """Stored observation rows per card id, keeping numerator, denominator and snapshot.

    Only cohorts bound to the commander; without a commander only cohorts bound to none."""
    rows: dict[str, list[dict[str, object]]] = {}
    if commander_names:
        bound, bound_args = bound_to("observation_cohort", "o.cohort", commander_names)
    else:
        bound, bound_args = (
            " AND NOT EXISTS (SELECT 1 FROM commander_binding cb "
            "WHERE cb.kind = 'observation_cohort' AND cb.key = o.cohort)",
            [],
        )
    for row in db.execute(
        "SELECT o.card_id, o.card_name, o.cohort, o.metric, o.value, o.numerator, "
        f"o.denominator, o.data_class, o.url, o.snapshot FROM observation o WHERE 1{bound} "
        "ORDER BY o.cohort, o.metric, o.denominator DESC",
        bound_args,
    ):
        card_id = row["card_id"] or name_to_id.get(str(row["card_name"]))
        if card_id is None:
            continue
        denominator = row["denominator"]
        snapshot = row["snapshot"] or None
        rows.setdefault(str(card_id), []).append(
            {
                "cohort": row["cohort"],
                "metric": row["metric"],
                "value": row["value"],
                "numerator": row["numerator"],
                "denominator": denominator,
                "denominator_known": denominator is not None,
                "small_denominator": denominator is not None and denominator < SMALL_DENOMINATOR,
                "snapshot": snapshot,
                "snapshot_known": snapshot is not None,
                "data_class": row["data_class"],
                "url": row["url"],
            }
        )
    return rows


def _simulations(
    db: sqlite3.Connection, name_to_id: dict[str, str], commander_names: Sequence[str]
) -> dict[str, dict[str, object]]:
    """Cast totals per card over the simulation runs bound to the commander."""
    totals: dict[str, dict[str, object]] = {}
    bound, bound_args = bound_to("simulation_run", "sc.run_id", commander_names)
    for row in db.execute(
        "SELECT sc.card_id, sc.card_name, sc.run_id, sc.games_offered, "
        f"sc.games_cast_after_offer, sc.cast_count FROM simulation_card sc WHERE 1{bound} "
        "ORDER BY sc.run_id",
        bound_args,
    ):
        card_id = row["card_id"] or name_to_id.get(str(row["card_name"]))
        if card_id is None:
            continue
        entry = totals.setdefault(
            str(card_id),
            {"runs": 0, "games_offered": 0, "games_cast_after_offer": 0, "cast_count": 0},
        )
        entry["runs"] = int(str(entry["runs"])) + 1
        entry["games_offered"] = int(str(entry["games_offered"])) + int(row["games_offered"])
        entry["games_cast_after_offer"] = int(str(entry["games_cast_after_offer"])) + int(
            row["games_cast_after_offer"]
        )
        entry["cast_count"] = int(str(entry["cast_count"])) + int(row["cast_count"])
    return totals


def _edhrec_summary(items: list[dict[str, object]]) -> dict[str, object]:
    """Compact view of the EDHREC rows. Inclusion, lift and synergy stay separate fields."""
    inclusion = [item for item in items if item["metric"] == "inclusion_pct"]
    widest: dict[str, object] | None = None
    for item in inclusion:
        den = item["denominator"]
        if widest is None or (isinstance(den, int) and den > int(str(widest["denominator"] or 0))):
            widest = item
    return {
        "inclusion_views": len(inclusion),
        "lift_views": sum(1 for item in items if item["metric"] == "lift"),
        "synergy_views": sum(1 for item in items if item["metric"] == "synergy_pct"),
        "widest_inclusion": None
        if widest is None
        else {
            key: widest[key]
            for key in (
                "cohort",
                "value",
                "numerator",
                "denominator",
                "small_denominator",
                "snapshot_known",
                "data_class",
            )
        },
        "any_snapshot_unknown": any(not item["snapshot_known"] for item in items),
        "any_small_denominator": any(item["small_denominator"] for item in items),
    }


def _card_evidence(
    card: dict[str, object],
    *,
    view: str,
    cohorts: dict[str, int],
    roles: dict[str, list[dict[str, object]]],
    observations: dict[str, list[dict[str, object]]],
    simulations: dict[str, dict[str, object]],
    combo_cards: set[str],
    atlas_collected: bool,
    detail: bool,
) -> dict[str, object]:
    card_id = str(card["card_id"])
    oracle_id = str(card.get("oracle_id") or "")
    rows = observations.get(card_id, [])
    edhrec_rows = [row for row in rows if not _is_game_cohort(str(row["cohort"]))]
    game_rows = [row for row in rows if _is_game_cohort(str(row["cohort"]))]
    commander_view = view == VIEW_COMMANDER

    # Fact layer: facts and rule-based features. Roles keep their origin.
    claims = roles.get(oracle_id, [])
    fact: dict[str, object] = {
        "status": PRESENT,
        "data_class": "FACT",
        "mana_value": card["mana_value"],
        "colors": card["colors"],
        "type_line": card["type_line"],
        "fact_source": card["fact_source"],
        "rules_version": MECHANICAL_RULES_VERSION,
        "features": mechanical_features(
            str(card["type_line"]), str(card["text"]), str(card["produced_mana"])
        ),
        "roles": claims,
    }

    # Deck layer: only what is bound to the named commander is shown in the commander view.
    deck_items: list[dict[str, object]] = []
    deck_status = NOT_COLLECTED
    edhrec: dict[str, object] | None = None
    if card.get("edhrec_rank") is not None:
        deck_items.append(
            {
                "kind": "edhrec_rank_global",
                "rank": card["edhrec_rank"],
                "denominator_known": False,
                "data_class": "ORIGINAL_SOURCE",
                "note": "global popularity rank from the Scryfall bulk; lower is more popular",
            }
        )
        # The global rank says nothing about this commander: it sets the status only in
        # the global view, never in the commander view.
        if not commander_view:
            deck_status = PRESENT
    if commander_view:
        decks = card.get("decks")
        hits = decks if isinstance(decks, dict) else {}
        for cohort, size in cohorts.items():
            deck_items.append(
                {
                    "kind": "corpus",
                    "cohort": cohort,
                    "decks": int(hits.get(cohort, 0)),
                    "of": size,
                    "small_denominator": size < SMALL_DENOMINATOR,
                    "data_class": "DERIVED_DESCRIPTIVE",
                }
            )
        total = cohorts.get(ALL_DECKS, 0)
        # A stored row without a value is an unknown, not an observation.
        measured = [row for row in edhrec_rows if row["value"] is not None]
        if int(hits.get(ALL_DECKS, 0)) > 0 or measured:
            deck_status = PRESENT
        elif total > 0:
            deck_status = ABSENT_IN_KNOWN_CORPUS
        edhrec = _edhrec_summary(measured)
        edhrec["rows_without_value"] = len(edhrec_rows) - len(measured)
    deck_layer: dict[str, object] = {
        "status": deck_status,
        "items": deck_items,
        "edhrec": edhrec,
        "cohorts_overlap_never_add": True,
    }
    if detail and commander_view:
        deck_layer["edhrec_rows"] = edhrec_rows

    # Game layer: real game events across all commanders (Playgroup card atlas). The figures
    # are observed correlations with their own sample sizes, never a causal card strength.
    atlas = card.get("playgroup")
    atlas_ok = isinstance(atlas, dict) and atlas.get("status") == "OK"
    if atlas_ok or game_rows:
        game_status = PRESENT
    elif atlas_collected:
        game_status = NONE_RECORDED
    else:
        game_status = NOT_COLLECTED
    game_layer: dict[str, object] = {
        "status": game_status,
        "rows": game_rows if detail else len(game_rows),
        "atlas": atlas if isinstance(atlas, dict) else None,
        "population": "all commanders, Playgroup Live games only",
        "data_class": "OBSERVED_GAME",
        "note": "observed correlation with pilot, pod and survivorship bias; not a causal effect"
        if game_status == PRESENT
        else "the game-event source has no usable row for this card"
        if game_status == NONE_RECORDED
        else "no game-event source imported yet (Playgroup card atlas)",
    }

    # Combo layer and simulation layer only make sense for a named commander.
    if commander_view:
        combo_layer: dict[str, object] = {
            "status": (
                NOT_COLLECTED
                if not combo_cards
                else PRESENT
                if str(card["name"]) in combo_cards
                else NONE_RECORDED
            ),
            "data_class": "COMBO_VERIFIED",
            "note": "a listed combo is not proof of strength or of an engine pass",
        }
        sim = simulations.get(card_id)
        sim_layer: dict[str, object] = {
            "status": PRESENT if sim else NONE_RECORDED if simulations else NOT_COLLECTED,
            "data_class": "SIMULATED_RESULT",
            "totals": None
            if sim is None
            else {
                **sim,
                "cast_after_offer_of": sim["games_offered"],
            },
        }
    else:
        combo_layer = {"status": NOT_APPLICABLE, "data_class": "COMBO_VERIFIED"}
        sim_layer = {"status": NOT_APPLICABLE, "data_class": "SIMULATED_RESULT"}

    layers: dict[str, dict[str, object]] = {
        LAYER_FACT: fact,
        LAYER_DECK: deck_layer,
        LAYER_GAME: game_layer,
        LAYER_COMBO: combo_layer,
        LAYER_SIMULATED: sim_layer,
    }
    present = [name for name in COVERAGE_LAYERS if layers[name]["status"] == PRESENT]
    missing = [
        name
        for name in COVERAGE_LAYERS
        if layers[name]["status"] in {NOT_COLLECTED, ABSENT_IN_KNOWN_CORPUS}
    ]

    needs: list[str] = []
    if layers[LAYER_GAME]["status"] != PRESENT:
        needs.append("NO_GAME_EVIDENCE")
    elif isinstance(atlas, dict) and atlas.get("insufficient_sample"):
        needs.append("SMALL_GAME_SAMPLE")
    if layers[LAYER_DECK]["status"] == ABSENT_IN_KNOWN_CORPUS:
        needs.append("NOT_OBSERVED_IN_CORPUS")
    if edhrec is not None and edhrec["any_small_denominator"]:
        needs.append("SMALL_DENOMINATOR")
    if edhrec is not None and edhrec["any_snapshot_unknown"]:
        needs.append("EDHREC_TIME_UNKNOWN")
    if not claims:
        needs.append("NO_ROLE_CLAIM")

    coverage: dict[str, object] = {
        "present": present,
        "missing": missing,
        "needs": needs,
        "gap_grade": None,
        "research_priority": None,
    }
    if commander_view:
        record = calculate_card_coverage_record(
            card, combo_cards, corpus_denominator=cohorts.get(ALL_DECKS, 0)
        )
        coverage["gap_grade"] = record.coverage_grade
        coverage["research_priority"] = {
            "score": record.research_priority_score,
            "data_class": "HEURISTIC_MODEL",
            "long_tail": record.is_long_tail_candidate,
        }

    return {
        "card_id": card_id,
        "name": card["name"],
        "oracle_id": oracle_id,
        "mana_value": card["mana_value"],
        "type_line": card["type_line"],
        "group": card["group"],
        "colors": card["colors"],
        "has_image": card["has_image"],
        "has_back": card["has_back"],
        "available": card["available"],
        "rating": {
            "status": UNRATED,
            "tier": None,
            "reason": NO_VALIDATED_MODEL,
            "model_version": None,
        },
        "layers": layers,
        "coverage": coverage,
    }


def pool_evidence(
    store: StudioStore,
    commander_names: Sequence[str],
    *,
    view: str = VIEW_COMMANDER,
    only_card_id: str | None = None,
    detail: bool = False,
) -> dict[str, object]:
    """Evidence for every pool card (or one), in a deterministic order (by name).

    ``view`` is ``commander`` (everything bound to the named commander) or ``global`` (only
    what does not depend on a commander; there the pool has no colour filter).
    """
    if view not in VIEWS:
        raise ValueError(view)
    names = tuple(commander_names) if view == VIEW_COMMANDER else ()
    pool = pool_cards(store, names)
    db = store.connection
    raw_cards = pool["cards"]
    cohorts = pool["cohorts"]
    if not isinstance(raw_cards, list) or not isinstance(cohorts, dict):
        raise TypeError("pool_cards returned an unexpected shape")
    name_to_id: dict[str, str] = {}
    for row in db.execute("SELECT card_id, oracle_name, engine_name FROM card_fact"):
        name_to_id[str(row["oracle_name"])] = str(row["card_id"])
        name_to_id.setdefault(str(row["engine_name"]), str(row["card_id"]))
    roles = _role_claims(db)
    observations = _observations(db, name_to_id, names)
    simulations = _simulations(db, name_to_id, names)
    combo_cards: set[str] = set()
    for name in names:
        # The combo file names commanders by their short name (the part before the comma).
        combo_cards |= load_spellbook_combo_cards(_COMBOS_PATH, commander=name.split(",")[0])
    atlas_collected = (
        db.execute(
            "SELECT 1 FROM playgroup_card_atlas WHERE fetch_status = 'OK' LIMIT 1"
        ).fetchone()
        is not None
    )
    cards: list[dict[str, object]] = []
    for card in raw_cards:
        if only_card_id is not None and card["card_id"] != only_card_id:
            continue
        cards.append(
            _card_evidence(
                card,
                view=view,
                cohorts={str(k): int(v) for k, v in cohorts.items()},
                roles=roles,
                observations=observations,
                simulations=simulations,
                combo_cards=combo_cards,
                atlas_collected=atlas_collected,
                detail=detail,
            )
        )
    layer_status: dict[str, dict[str, int]] = {name: {} for name in LAYERS}
    for item in cards:
        item_layers = item["layers"]
        if not isinstance(item_layers, dict):
            raise TypeError("layers must be a mapping")
        for name in LAYERS:
            status = str(item_layers[name]["status"])
            layer_status[name][status] = layer_status[name].get(status, 0) + 1
    return {
        "schema": EVIDENCE_SCHEMA,
        "view": view,
        "commander": list(names),
        "tier_policy": TIER_POLICY,
        "cohorts": cohorts,
        "corpus_binding": pool["corpus_binding"],
        "small_denominator": SMALL_DENOMINATOR,
        "summary": {
            "cards": len(cards),
            "unrated": len(cards),
            "layer_status": layer_status,
        },
        "cards": cards,
    }


def card_evidence(
    store: StudioStore,
    card_id: str,
    commander_names: Sequence[str],
    *,
    view: str = VIEW_COMMANDER,
) -> dict[str, object]:
    """Full evidence of one card including every stored observation row."""
    result = pool_evidence(store, commander_names, view=view, only_card_id=card_id, detail=True)
    cards = result["cards"]
    if not isinstance(cards, list) or not cards:
        raise KeyError(card_id)
    card = cards[0]
    return {
        "schema": EVIDENCE_SCHEMA,
        "view": view,
        "commander": result["commander"],
        "tier_policy": TIER_POLICY,
        "cohorts": result["cohorts"],
        "small_denominator": SMALL_DENOMINATOR,
        "card": card,
    }


def role_alternatives(
    store: StudioStore,
    card_id: str,
    commander_names: Sequence[str],
    *,
    in_deck: Sequence[str] = (),
    skip: Sequence[str] = (),
    limit: int = 25,
) -> dict[str, object]:
    """Free pool cards that hold at least one role of ``card_id``: function alternatives.

    This is a comparison of function, not a claim that a swap is better. The order is
    deterministic and descriptive only: more shared roles first, then the smaller difference
    in mana value, then the name. No outcome evidence exists, so ``improvement_claimed`` is
    always false. Marks are not read: the caller names the cards it does not want listed
    (``skip``, for example the ones the Owner excluded), which changes only which candidates
    are listed and never their order or any figure.
    """
    result = pool_evidence(store, commander_names, view=VIEW_COMMANDER)
    cards = result["cards"]
    if not isinstance(cards, list):
        raise TypeError("pool_evidence returned an unexpected shape")

    def roles_of(card: dict[str, object]) -> set[str]:
        layers = card["layers"]
        if not isinstance(layers, dict):
            raise TypeError("layers must be a mapping")
        claims = layers[LAYER_FACT]["roles"]
        return {str(claim["role"]) for claim in claims}

    target = next((card for card in cards if card["card_id"] == card_id), None)
    if target is None:
        raise KeyError(card_id)
    target_roles = roles_of(target)
    target_mv = float(str(target["mana_value"] or 0))
    left_out = {card_id, *in_deck, *skip}
    found: list[tuple[int, float, str, dict[str, object]]] = []
    for card in cards:
        available = card["available"]
        if card["card_id"] in left_out or not isinstance(available, int) or available <= 0:
            continue
        shared = sorted(target_roles & roles_of(card))
        if not shared:
            continue
        delta = float(str(card["mana_value"] or 0)) - target_mv
        found.append(
            (
                -len(shared),
                abs(delta),
                str(card["name"]),
                {
                    "card": card,
                    "shared_roles": shared,
                    "only_candidate_roles": sorted(roles_of(card) - target_roles),
                    "missing_roles": sorted(target_roles - roles_of(card)),
                    "mana_value_delta": delta,
                    "improvement_claimed": False,
                },
            )
        )
    found.sort(key=lambda item: item[:3])
    # ``total`` counts every candidate; the page says how many of them it does not show.
    return {
        "schema": EVIDENCE_SCHEMA,
        "card": target,
        "roles": sorted(target_roles),
        "status": "NO_ROLE_CLAIM" if not target_roles else "OK",
        "order": "shared roles (more first), mana value difference (smaller first), name",
        "basis": "function only; no outcome evidence, so no swap is called an improvement",
        "total": len(found),
        "alternatives": [item[3] for item in found[:limit]],
    }
