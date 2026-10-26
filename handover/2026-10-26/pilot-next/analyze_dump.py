"""Zaehlungen auf einem Full-Dump (pilot_request_corpus.py record --all).

Jede Zahl hat eine explizite Zaehlregel; was sich aus dem Dump nicht
zaehlen laesst, steht als NOT_COUNTABLE im Ergebnis statt als Null.
Karten-Typen (instant-speed) kommen aus dem Repo-Katalog
(data/cards/pilot_card_knowledge.json) via CardFacts.is_instant_speed(),
nicht aus Pilot-Entscheidungen (keine Zirkularitaet).

Verwendung:
    PYTHONPATH=<worktree>/src python3 analyze_dump.py dump.jsonl.gz
"""

from __future__ import annotations

import gzip
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def load_dump(path: Path) -> tuple[dict, list[dict]]:
    lines = [json.loads(line) for line in gzip.open(path, "rt", encoding="utf-8") if line.strip()]
    return lines[0], lines[1:]


def _chosen_option(request: dict, answer: dict) -> dict | None:
    selected = answer.get("selected_option_ids") or []
    if not selected:
        return None
    by_id = {o.get("option_id"): o for o in request.get("legal_options") or []}
    return by_id.get(selected[0])


def _is_spell(option: dict | None) -> bool:
    return bool(option) and (option.get("metadata") or {}).get("ability_type") == "spell"


def _is_pass(option: dict | None) -> bool:
    return bool(option) and option.get("option_type") == "pass_priority"


def analyze(path: Path) -> dict:
    from commander_lab.agents.card_knowledge import card_facts

    header, rows = load_dump(path)
    classes = Counter(r["request"]["decision_class"] for r in rows)
    seeds = sorted({int(r["seed"]) for r in rows})
    out: dict = {
        "dump": str(path),
        "games": len(seeds),
        "seeds": seeds,
        "decisions": len(rows),
        "decisions_per_game": round(len(rows) / max(len(seeds), 1), 1),
        "classes": dict(sorted(classes.items())),
        "size_mb": round(path.stat().st_size / 1_000_000, 2),
    }

    # --- Phase-4a-Fenster-Tabelle (Instants, eigene Upkeep/Draw) ---
    instant_casts = instant_early = unknown_type = 0
    for r in rows:
        req, ans = r["request"], r["answer"]
        if req["decision_class"] != "priority":
            continue
        opt = _chosen_option(req, ans)
        if not _is_spell(opt):
            continue
        facts = card_facts((opt.get("metadata") or {}).get("source_name"))
        if facts is None:
            unknown_type += 1
            continue
        if not facts.is_instant_speed:
            continue
        instant_casts += 1
        ps = req.get("pilot_state") or {}
        if ps.get("step") in ("upkeep", "draw") and ps.get("active_player_id") == ps.get("actor_id"):
            instant_early += 1
    out["phase4a"] = {
        "rule": "gewaehlte Spell-Option mit is_instant_speed (Katalog); early = step upkeep/draw und Akteur == aktiver Spieler",
        "instant_casts_total": instant_casts,
        "instant_casts_own_upkeep_draw": instant_early,
        "instant_casts_unknown_type": unknown_type,
        "early_share_pct": round(100 * instant_early / instant_casts, 1) if instant_casts else None,
    }

    # --- Reichweiten-Proxys je offener Zeile ---
    reach: dict = {}
    reach["P0-2_threat_ladder"] = {
        "rule": "target-Entscheidungen (Leiter wirkt auf Ziel-Score) + davon mit >=2 Optionen",
        "target_total": classes.get("target", 0),
        "target_multi_option": sum(
            1
            for r in rows
            if r["request"]["decision_class"] == "target" and len(r["request"].get("legal_options") or []) >= 2
        ),
    }
    reach["P0-3_trigger_order"] = {
        "rule": "trigger_order-Entscheidungen + davon mit >=2 Optionen",
        "trigger_total": classes.get("trigger_order", 0),
        "trigger_multi_option": sum(
            1
            for r in rows
            if r["request"]["decision_class"] == "trigger_order"
            and len(r["request"].get("legal_options") or []) >= 2
        ),
    }
    reach["P1-1_combo_recognition"] = {
        "rule": "NOT_COUNTABLE direkt (Combo-Teil-Erkennung braucht Paket-Abgleich); Proxy: priority-Entscheidungen mit >=1 gegnerischem Permanent auf dem Board",
        "proxy_opponent_board_nonempty": sum(
            1
            for r in rows
            if r["request"]["decision_class"] == "priority"
            and any(
                (not p.get("is_actor")) and len(p.get("battlefield") or []) > 0
                for p in (r["request"].get("pilot_state") or {}).get("players", [])
            )
        ),
    }
    reach["P1-2_timing_remainder"] = {
        "rule": "postcombat-Kandidaten: in eigener precombat_main gewaehlte Spells ohne instant-speed; Wipe-Heuristik: angebotene Spells, deren Oracle-Text 'destroy all'/'exile all' enthaelt",
        "precombat_noninstant_casts": 0,
        "wipe_options_offered": 0,
    }
    for r in rows:
        req, ans = r["request"], r["answer"]
        if req["decision_class"] != "priority":
            continue
        ps = req.get("pilot_state") or {}
        opt = _chosen_option(req, ans)
        if (
            ps.get("step") == "precombat_main"
            and ps.get("active_player_id") == ps.get("actor_id")
            and _is_spell(opt)
        ):
            facts = card_facts((opt.get("metadata") or {}).get("source_name"))
            if facts is not None and not facts.is_instant_speed:
                reach["P1-2_timing_remainder"]["precombat_noninstant_casts"] += 1
        for o in req.get("legal_options") or []:
            if (o.get("metadata") or {}).get("ability_type") != "spell":
                continue
            facts = card_facts((o.get("metadata") or {}).get("source_name"))
            text = (facts.oracle_text if facts else "").casefold()
            if "destroy all" in text or "exile all" in text:
                reach["P1-2_timing_remainder"]["wipe_options_offered"] += 1
                break
    reach["P1-3_interaction_discipline"] = {
        "rule": "gegnerische Zuege, in denen der Akteur passt, obwohl ein instant-speed Spell angeboten wurde",
        "opp_turn_pass_with_instant_offered": 0,
    }
    reach["P2_foreign_turn_pass"] = {
        "rule": "wie P1-3 (gleiche Fenster; P2-Rest und P1-3 teilen sich diese Reichweite)",
        "same_as_P1-3": True,
    }
    for r in rows:
        req, ans = r["request"], r["answer"]
        if req["decision_class"] != "priority":
            continue
        ps = req.get("pilot_state") or {}
        if ps.get("active_player_id") == ps.get("actor_id"):
            continue
        if not _is_pass(_chosen_option(req, ans)):
            continue
        for o in req.get("legal_options") or []:
            if (o.get("metadata") or {}).get("ability_type") != "spell":
                continue
            facts = card_facts((o.get("metadata") or {}).get("source_name"))
            if facts is not None and facts.is_instant_speed:
                reach["P1-3_interaction_discipline"]["opp_turn_pass_with_instant_offered"] += 1
                break
    reach["P1-4_P10_x_breakpoints"] = {
        "rule": "announce_x- + multi_amount-Entscheidungen; davon mit X>0 (numeric_choice)",
        "announce_x": classes.get("announce_x", 0),
        "multi_amount": classes.get("multi_amount", 0),
        "announce_x_positive": sum(
            1
            for r in rows
            if r["request"]["decision_class"] == "announce_x"
            and isinstance(r["answer"].get("numeric_choice"), (int, float))
            and r["answer"]["numeric_choice"] > 0
        ),
    }
    reach["P1-5_P11_mulligan_devscore"] = {
        "rule": "mulligan-Entscheidungen",
        "mulligan": classes.get("mulligan", 0),
    }
    reach["P1-6_noise"] = {
        "rule": "NOT_COUNTABLE direkt (relatives Modell); Proxy: declare_attacker-Entscheidungen (Fokus-Wahl)",
        "declare_attacker": classes.get("declare_attacker", 0),
    }
    reach["P2-1_roles"] = {"rule": "NOT_COUNTABLE (Meta-Policy, keine Entscheidungsklasse)"}
    reach["P2-2_external_priors"] = {"rule": "NOT_COUNTABLE (Deckbau-Zeit, keine Spiel-Entscheidung)"}
    reach["P2-3_risk_quantification"] = {"rule": "NOT_COUNTABLE direkt (Modell-Inputs, keine eigene Klasse)"}
    reach["P4_fast_path"] = {
        "rule": "mana_payment-Entscheidungen (Volumen, das der Fast-Path nicht mehr bewerten wuerde)",
        "mana_payment": classes.get("mana_payment", 0),
        "share_pct": round(100 * classes.get("mana_payment", 0) / max(len(rows), 1), 1),
    }
    reach["P5_profiling"] = {
        "rule": "NOT_COUNTABLE aus dem Dump (keine Wandzeit je Entscheidung); Dump-Groesse als Ersatz",
        "size_mb": out["size_mb"],
        "decisions_per_game": out["decisions_per_game"],
    }
    reach["P6_instrumentation"] = {"rule": "NOT_COUNTABLE (kuenftige Laeufe)"}
    reach["P7_transcript_schema"] = {
        "rule": "Dump-Groesse je Spiel als Mass fuer das Transkript-Volumen",
        "bytes_per_decision": round(path.stat().st_size / max(len(rows), 1), 1),
        "decisions_per_game": out["decisions_per_game"],
    }
    reach["P9_replication_remainder"] = {"rule": "NOT_COUNTABLE aus einem einzelnen Dump (braucht Duplikat-Keys ueber Laeufe)"}
    reach["P8_combat_remainder"] = {
        "rule": "declare_attacker- + declare_blocker-Entscheidungen (Angriffs-Entscheid ob ueberhaupt + Block-Schwellen jenseits der Runden-Regel)",
        "declare_attacker": classes.get("declare_attacker", 0),
        "declare_blocker": classes.get("declare_blocker", 0),
    }
    reach["P3_costed_may_remainder"] = {
        "rule": "choose_use-Entscheidungen, deren Prompt Kostenwoerter traegt (pay/life/sacrifice)",
        "choose_use_total": classes.get("choose_use", 0),
        "choose_use_costed_prompt": sum(
            1
            for r in rows
            if r["request"]["decision_class"] == "choose_use"
            and re.search(r"pay|life|sacrifice", (r["request"].get("prompt") or ""), re.IGNORECASE)
        ),
    }
    reach["P0-1_remainder"] = {
        "rule": "NOT_COUNTABLE direkt (die ungesetzten Inputs fehlen per Definition); gesetzt ist nur commander_damage_pressure (#1022)",
    }
    reach["phase4a-2_hold_mana"] = {
        "rule": "NOT_COUNTABLE (Handinhalt steht nicht im Dump; nur hand_count sichtbar)",
    }
    out["reach"] = reach
    return out


if __name__ == "__main__":
    result = analyze(Path(sys.argv[1]))
    print(json.dumps(result, indent=1, ensure_ascii=False))
