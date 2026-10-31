"""Counts on a full dump of whole games: how many decisions does each open pilot item reach?

A full dump comes from ``pilot_request_corpus.py record --all``. This script answers, per open
finding of the pilot game mining (#989, #1029), how many recorded decisions it touches, so the
next pilot phase is chosen from data. Every number has an explicit counting rule; what a dump
cannot count is reported as ``NOT_COUNTABLE`` and never as zero.

Instant-speed and oracle text come from the repository card catalog
(``data/cards/pilot_card_knowledge.json`` via ``card_facts``), not from pilot decisions, so the
counts are not circular.

    python scripts/pilot_dump_reach.py dump.jsonl.gz
    python scripts/pilot_dump_reach.py slice1.jsonl.gz slice2.jsonl.gz ...   # slices of one run

Several files are read as slices of one dump: same jar, same corpus version, rows appended.
The output is JSON on stdout.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_COSTED_PROMPT = re.compile(r"pay|life|sacrifice", re.IGNORECASE)


def load_dump(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        lines = [json.loads(line) for line in handle if line.strip()]
    return lines[0], lines[1:]


def load_slices(paths: Sequence[Path]) -> tuple[dict[str, Any], list[dict[str, Any]], int]:
    """Rows of all slices of one full dump.

    Refuses a file that is not a full dump (a sample from ``record`` without ``--all`` would be
    counted as if it were whole games), a file whose row count differs from the header's
    ``games_decisions`` (truncated or hand-edited), slices of different jars or corpus versions,
    and a seed that appears in more than one slice (the same slice given twice would double
    every number).
    """
    header: dict[str, Any] | None = None
    rows: list[dict[str, Any]] = []
    size = 0
    seed_files: dict[int, Path] = {}
    for path in paths:
        head, body = load_dump(path)
        if head.get("kind") != "full":
            raise ValueError(
                f"{path} is not a full dump (kind {head.get('kind')!r}); record it with --all"
            )
        if head.get("games_decisions") != len(body):
            raise ValueError(
                f"{path} has {len(body)} rows but its header says "
                f"{head.get('games_decisions')} decisions"
            )
        if header is None:
            header = head
        elif (head.get("corpus_version"), head.get("jar_sha256")) != (
            header.get("corpus_version"),
            header.get("jar_sha256"),
        ):
            raise ValueError(f"{path} was recorded with another jar or corpus version")
        for seed in {int(row["seed"]) for row in body}:
            if seed in seed_files:
                raise ValueError(f"seed {seed} is in both {seed_files[seed]} and {path}")
            seed_files[seed] = path
        rows.extend(body)
        size += path.stat().st_size
    if header is None:
        raise ValueError("no dump given")
    return header, rows, size


def _chosen_option(request: dict[str, Any], answer: dict[str, Any]) -> dict[str, Any] | None:
    selected = answer.get("selected_option_ids") or []
    if not selected:
        return None
    by_id = {o.get("option_id"): o for o in request.get("legal_options") or []}
    chosen = by_id.get(selected[0])
    return chosen if isinstance(chosen, dict) else None


def _is_spell(option: dict[str, Any] | None) -> bool:
    return option is not None and (option.get("metadata") or {}).get("ability_type") == "spell"


def _is_pass(option: dict[str, Any] | None) -> bool:
    return option is not None and option.get("option_type") == "pass_priority"


def _source_name(option: dict[str, Any] | None) -> str | None:
    name = ((option or {}).get("metadata") or {}).get("source_name")
    return name if isinstance(name, str) else None


def _multi(row: dict[str, Any]) -> bool:
    return len(row["request"].get("legal_options") or []) >= 2


def analyze(rows: Sequence[dict[str, Any]], size_bytes: int) -> dict[str, Any]:
    from commander_lab.agents.card_knowledge import card_facts

    total = len(rows)
    classes = Counter(r["request"]["decision_class"] for r in rows)
    seeds = sorted({int(r["seed"]) for r in rows})
    games = max(len(seeds), 1)
    per_game = round(total / games, 1)

    # Phase 4a window table: instants cast in the own upkeep or draw step.
    instant_casts = instant_early = unknown_type = 0
    # Timing remainder: sorcery-speed spells chosen in the own precombat main, wipes offered.
    precombat_noninstant = wipes_offered = 0
    # Interaction discipline: passes on an opponent's turn although an instant was offered.
    opp_turn_pass_with_instant = 0
    for row in rows:
        request, answer = row["request"], row["answer"]
        if request["decision_class"] != "priority":
            continue
        state = request.get("pilot_state") or {}
        own_turn = state.get("active_player_id") == state.get("actor_id")
        chosen = _chosen_option(request, answer)
        if _is_spell(chosen):
            facts = card_facts(_source_name(chosen))
            if facts is None:
                unknown_type += 1
            elif facts.is_instant_speed:
                instant_casts += 1
                if state.get("step") in ("upkeep", "draw") and own_turn:
                    instant_early += 1
            elif state.get("step") == "precombat_main" and own_turn:
                precombat_noninstant += 1
        options = request.get("legal_options") or []
        spells = [o for o in options if (o.get("metadata") or {}).get("ability_type") == "spell"]
        for option in spells:
            facts = card_facts(_source_name(option))
            text = (facts.oracle_text if facts else "").casefold()
            if "destroy all" in text or "exile all" in text:
                wipes_offered += 1
                break
        if not own_turn and _is_pass(chosen):
            for option in spells:
                facts = card_facts(_source_name(option))
                if facts is not None and facts.is_instant_speed:
                    opp_turn_pass_with_instant += 1
                    break

    def of(name: str) -> int:
        return classes.get(name, 0)

    def where(name: str, keep: Any) -> int:
        return sum(1 for r in rows if r["request"]["decision_class"] == name and keep(r))

    announce_positive = where(
        "announce_x",
        lambda r: (
            isinstance(r["answer"].get("numeric_choice"), (int, float))
            and r["answer"]["numeric_choice"] > 0
        ),
    )
    opponent_board = sum(
        1
        for r in rows
        if r["request"]["decision_class"] == "priority"
        and any(
            (not p.get("is_actor")) and len(p.get("battlefield") or []) > 0
            for p in (r["request"].get("pilot_state") or {}).get("players", [])
        )
    )
    costed = where(
        "choose_use", lambda r: bool(_COSTED_PROMPT.search(r["request"].get("prompt") or ""))
    )
    not_countable = "NOT_COUNTABLE"
    return {
        "games": len(seeds),
        "seeds": seeds,
        "decisions": total,
        "decisions_per_game": per_game,
        "classes": dict(sorted(classes.items())),
        "size_mb": round(size_bytes / 1_000_000, 2),
        "phase4a": {
            "rule": "chosen spell option with is_instant_speed (catalog); early = step upkeep or "
            "draw and actor == active player; unknown card types counted apart and left out",
            "instant_casts_total": instant_casts,
            "instant_casts_own_upkeep_draw": instant_early,
            "instant_casts_unknown_type": unknown_type,
            "early_share_pct": round(100 * instant_early / instant_casts, 1)
            if instant_casts
            else None,
        },
        "reach": {
            "P0-2_threat_ladder": {
                "rule": "target decisions, and those with >= 2 options",
                "target_total": of("target"),
                "target_multi_option": where("target", _multi),
            },
            "P0-3_trigger_order": {
                "rule": "trigger_order decisions, and those with >= 2 options",
                "trigger_total": of("trigger_order"),
                "trigger_multi_option": where("trigger_order", _multi),
            },
            "P1-1_combo_recognition": {
                "rule": f"{not_countable} directly (needs a package match); proxy: priority "
                "decisions with an opponent permanent on the board",
                "proxy_opponent_board_nonempty": opponent_board,
            },
            "P1-2_timing_remainder": {
                "rule": "postcombat candidates: non-instant spells chosen in the own precombat "
                "main; wipes: offered spells whose oracle text has 'destroy all' or 'exile all'",
                "precombat_noninstant_casts": precombat_noninstant,
                "wipe_options_offered": wipes_offered,
            },
            "P1-3_interaction_discipline": {
                "rule": "opponent turns on which the actor passes although an instant-speed "
                "spell was offered (the P2 remainder shares these windows)",
                "opp_turn_pass_with_instant_offered": opp_turn_pass_with_instant,
            },
            "P1-4_P10_x_breakpoints": {
                "rule": "announce_x and multi_amount decisions; announce_x with X > 0",
                "announce_x": of("announce_x"),
                "multi_amount": of("multi_amount"),
                "announce_x_positive": announce_positive,
            },
            "P1-5_P11_mulligan_devscore": {
                "rule": "mulligan decisions",
                "mulligan": of("mulligan"),
            },
            "P1-6_noise": {
                "rule": f"{not_countable} directly (relative model); proxy: declare_attacker",
                "declare_attacker": of("declare_attacker"),
            },
            "P2-1_roles": {"rule": f"{not_countable} (meta policy, no decision class)"},
            "P2-2_external_priors": {"rule": f"{not_countable} (deck-building time)"},
            "P2-3_risk_quantification": {"rule": f"{not_countable} directly (model inputs)"},
            "P4_fast_path": {
                "rule": "mana_payment decisions (volume a fixed rule would not evaluate)",
                "mana_payment": of("mana_payment"),
                "share_pct": round(100 * of("mana_payment") / max(total, 1), 1),
            },
            "P5_profiling": {
                "rule": f"{not_countable} from a dump (no wall time per decision); size as proxy",
                "size_mb": round(size_bytes / 1_000_000, 2),
                "decisions_per_game": per_game,
            },
            "P6_instrumentation": {"rule": f"{not_countable} (future runs)"},
            "P7_transcript_schema": {
                "rule": "bytes per decision of the dump as the transcript volume",
                "bytes_per_decision": round(size_bytes / max(total, 1), 1),
                "decisions_per_game": per_game,
            },
            "P8_combat_remainder": {
                "rule": "declare_attacker and declare_blocker decisions (an upper bound)",
                "declare_attacker": of("declare_attacker"),
                "declare_blocker": of("declare_blocker"),
            },
            "P9_replication_remainder": {
                "rule": f"{not_countable} from one dump (needs duplicate keys across runs)"
            },
            "P3_costed_may_remainder": {
                "rule": "choose_use decisions whose prompt has pay, life or sacrifice",
                "choose_use_total": of("choose_use"),
                "choose_use_costed_prompt": costed,
            },
            "P0-1_remainder": {
                "rule": f"{not_countable} directly (the unset inputs are missing by definition)"
            },
            "mana_hold": {
                "rule": f"{not_countable} (hand contents are not in the dump, only hand_count)"
            },
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dump", nargs="+", type=Path, help="full dump(s) of one run")
    args = parser.parse_args(argv)
    try:
        _, rows, size = load_slices(args.dump)
    except (OSError, ValueError) as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    print(json.dumps(analyze(rows, size), indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
