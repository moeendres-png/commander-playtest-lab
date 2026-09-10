#!/usr/bin/env python3
"""WS55 mandatory decision-breadth runner (WS55-owned, qualification-only).

Extends the WS53 converged runner (imported, never modified) with answer
functions for the WS55 provider surfaces, plus confirm scripting and new
negative probes. Grants no behavior credit (BEHAVIOR_CREDIT=0/107).

New broker kinds and their script families:
  combatDamage        -> combat_damage   {"source","recipient","amount"}
  amountDistribution  -> amount_distribution {"recipient","amount"}
  optional_costs      -> optional_costs  {"decision":"take","match":substr}
                                           | {"decision":"done"}
  order_costs         -> order_costs      {"order":[part-substr,...]}
  order_combat        -> order_combat     {"order":[card-ref,...]}
                                           | {"pos":int} (insertion)
  confirm             -> confirm          {"confirm":bool} | {"option":str}
  choose_mode (multi) -> mode_pick        {"mode_pick":substr}
                                           | {"mode_done":true}
  trigger_order (N)   -> trigger_order    {"order":[name-substr,...]} (any N)

Kind-family binding (Q9 harness-side enforcement): each new broker kind is
answered ONLY by its own family; a frame whose kind has no due entry of the
matching family fails closed (never falls through to another family, never
structural-passes a discretionary frame).

Usage:
  ws55_breadth_runner.py --materialization M --scenario WS55-<NAME>
      --intent-json I.json --runners DIR --output J.json
      [--structural-cap N] [--deck-main S --deck-commander S]
      [--neg-bad-option KIND]
  ws55_breadth_runner.py --materialization M --replay J.json --runners DIR
      --output R.json
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import urllib.parse
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "ws53-forge-convergence-native-progression"))
sys.path.insert(0, str(HERE.parent / "ws48-forge-v1.0.5"))
import run_behavior_transcript_probe as base  # noqa: E402
import ws53_sequence_runner as ws53  # noqa: E402

PROTOCOL = base.PROTOCOL
WS47_SCHEMA = base.WS47_SCHEMA
WS47_BUNDLE = base.WS47_BUNDLE
WS47_SHA = base.WS47_SHA
FORGE_COMMIT = base.FORGE_COMMIT
FORGE_TREE = base.FORGE_TREE
WS55_SEED_BINDING = "ws55-forge-mandatory-decision-breadth"

WS55_KINDS = ("combatDamage", "amountDistribution", "optional_costs",
              "order_costs", "order_combat", "confirm")

# Extend WS53 family routing for the new discretionary surfaces (additive;
# WS53-owned mapping object is extended in place for this process only).
ws53.KIND_FAMILIES.update({
    "combatDamage": ("combat_damage",),
    "amountDistribution": ("amount_distribution",),
    "optional_costs": ("optional_costs",),
    "order_costs": ("order_costs",),
    "order_combat": ("order_combat",),
    "confirm": ("confirm",),
    "choose_mode": ("choose_mode", "mode_pick"),
})


def ws55_dec_label(label: str) -> dict[str, str]:
    """Parse WS48: and WS55: labels with the same grammar."""
    if label.startswith("WS55:"):
        return base.dec_label("WS48:" + label[len("WS55:"):])
    return base.dec_label(label)


def _due(drv: Any, families: tuple[str, ...], actor: str,
         phase: str | None, turn: int | None) -> list[dict[str, Any]]:
    due = [e for e in drv.script
           if e.get("decision_family") in families
           and e.get("actor") == actor
           and (e.get("phases") is None or phase in (e.get("phases") or []))
           and (e.get("turns") is None or turn in (e.get("turns") or []))]
    return due


def _pop_due(drv: Any, families: tuple[str, ...], actor: str,
             phase: str | None, turn: int | None,
             where: str) -> dict[str, Any]:
    due = _due(drv, families, actor, phase, turn)
    if not due:
        raise base.Blocked(where, f"unscripted {where} for {actor} "
                                  f"(kind-family binding: no due entry)")
    d = due[0]
    drv.script.remove(d)
    return d


def answer_combat_damage(drv: Any, actor: str, opts: list[dict[str, Any]],
                         labels: list[dict[str, str]], phase: Any,
                         turn: Any) -> str:
    d = _pop_due(drv, ("combat_damage",), actor, phase, turn, "combatDamage")
    sv = d["selection"]["semantic_value"]
    hits = [i for i, lb in enumerate(labels)
            if lb.get("_kind") in ("COMBAT_DAMAGE",)
            and sv["source"] in lb.get("source", "")
            and sv["recipient"] in lb.get("recipient", "")
            and str(lb.get("amount", "")) == str(sv["amount"])]
    if len(hits) != 1:
        drv.script.insert(0, d)
        raise base.Blocked("combatDamage", f"{sv}: {len(hits)} matches of {len(opts)}")
    drv.consumed.append(d)
    return str(opts[hits[0]]["option_id"])


def answer_amount_distribution(drv: Any, actor: str, opts: list[dict[str, Any]],
                               labels: list[dict[str, str]], phase: Any,
                               turn: Any) -> str:
    d = _pop_due(drv, ("amount_distribution",), actor, phase, turn,
                 "amountDistribution")
    sv = d["selection"]["semantic_value"]
    hits = [i for i, lb in enumerate(labels)
            if lb.get("_kind") in ("AMOUNT_DISTRIBUTION",)
            and sv["recipient"] in lb.get("recipient", "")
            and str(lb.get("amount", "")) == str(sv["amount"])]
    if len(hits) != 1:
        drv.script.insert(0, d)
        raise base.Blocked("amountDistribution", f"{sv}: {len(hits)} matches")
    drv.consumed.append(d)
    return str(opts[hits[0]]["option_id"])


def answer_optional_costs(drv: Any, actor: str, opts: list[dict[str, Any]],
                          labels: list[dict[str, str]], phase: Any,
                          turn: Any) -> str:
    d = _pop_due(drv, ("optional_costs",), actor, phase, turn, "optional_costs")
    sv = d["selection"]["semantic_value"]
    if sv.get("decision") == "done":
        for i, lb in enumerate(labels):
            if lb.get("_kind") == "OPT" and opts[i].get("kind", "") == "WS55:OPT:DONE":
                drv.consumed.append(d)
                return str(opts[i]["option_id"])
        drv.script.insert(0, d)
        raise base.Blocked("optional_costs", "DONE not offered")
    if sv.get("decision") == "take":
        hits = [i for i, lb in enumerate(labels)
                if lb.get("_kind") == "OPTCOST" and sv["match"] in lb.get("desc", "")]
        if len(hits) != 1:
            drv.script.insert(0, d)
            raise base.Blocked("optional_costs", f"match {sv['match']}: {len(hits)} matches")
        drv.consumed.append(d)
        return str(opts[hits[0]]["option_id"])
    drv.script.insert(0, d)
    raise base.Blocked("optional_costs", f"unknown decision {sv}")


def answer_order_costs(drv: Any, actor: str, opts: list[dict[str, Any]],
                       labels: list[dict[str, str]], phase: Any,
                       turn: Any) -> str:
    d = _pop_due(drv, ("order_costs",), actor, phase, turn, "order_costs")
    want = [str(x) for x in d["selection"]["semantic_value"]["order"]]
    hits = []
    for i, lb in enumerate(labels):
        if lb.get("_kind") != "COSTORDER":
            continue
        parts = (lb.get("parts", "") or "").split("|")
        if len(parts) == len(want) and all(w in p for w, p in zip(want, parts)):
            hits.append(i)
    if len(hits) != 1:
        drv.script.insert(0, d)
        raise base.Blocked("order_costs", f"order {want}: {len(hits)} matches")
    drv.consumed.append(d)
    return str(opts[hits[0]]["option_id"])


def _order_label_seq(lb: dict[str, str]) -> list[str] | None:
    order = lb.get("order", "")
    if not order:
        return None
    return [s for s in order.split(",") if s]


def answer_order_combat(drv: Any, actor: str, opts: list[dict[str, Any]],
                        labels: list[dict[str, str]], phase: Any,
                        turn: Any) -> str:
    d = _pop_due(drv, ("order_combat",), actor, phase, turn, "order_combat")
    sv = d["selection"]["semantic_value"]
    if "pos" in sv:
        hits = [i for i, lb in enumerate(labels)
                if lb.get("_kind") == "ORDERBLOCKER"
                and str(lb.get("pos", "")) == str(sv["pos"])]
        if len(hits) != 1:
            drv.script.insert(0, d)
            raise base.Blocked("order_combat", f"pos {sv['pos']}: {len(hits)} matches")
        drv.consumed.append(d)
        return str(opts[hits[0]]["option_id"])
    want = [str(x) for x in sv["order"]]
    hits = []
    for i, lb in enumerate(labels):
        if lb.get("_kind") not in ("ORDERBLOCKERS", "ORDERATTACKERS"):
            continue
        seq = _order_label_seq(lb) or []
        ids = [base.ref_identity(urllib.parse.unquote_plus(s)) or s for s in seq]
        if len(ids) == len(want) and all(w == got or w in got for w, got in zip(want, ids)):
            hits.append(i)
    if len(hits) != 1:
        drv.script.insert(0, d)
        raise base.Blocked("order_combat", f"order {want}: {len(hits)} matches")
    drv.consumed.append(d)
    return str(opts[hits[0]]["option_id"])


def answer_confirm(drv: Any, actor: str, opts: list[dict[str, Any]],
                   labels: list[dict[str, str]], phase: Any,
                   turn: Any) -> str:
    d = _pop_due(drv, ("confirm",), actor, phase, turn, "confirm")
    sv = d["selection"]["semantic_value"]
    if isinstance(sv, dict) and "confirm" in sv:
        want = "YES" if sv["confirm"] else "NO"
        hits = [i for i, lb in enumerate(labels)
                if lb.get("_kind") == "CONFIRM"
                and (lb.get("opt", "") or "").upper() == want]
        if len(hits) != 1:
            drv.script.insert(0, d)
            raise base.Blocked("confirm", f"{want}: {len(hits)} matches of {len(opts)}")
        drv.consumed.append(d)
        return str(opts[hits[0]]["option_id"])
    if isinstance(sv, dict) and "option" in sv:
        hits = [i for i, lb in enumerate(labels)
                if lb.get("_kind") == "CONFIRM" and sv["option"] in (lb.get("opt", ""))]
        if len(hits) != 1:
            drv.script.insert(0, d)
            raise base.Blocked("confirm", f"option {sv['option']}: {len(hits)} matches")
        drv.consumed.append(d)
        return str(opts[hits[0]]["option_id"])
    drv.script.insert(0, d)
    raise base.Blocked("confirm", f"unknown confirm semantic {sv}")


def answer_mode_pick(drv: Any, actor: str, opts: list[dict[str, Any]],
                     labels: list[dict[str, str]], phase: Any,
                     turn: Any) -> str:
    # Multi-mode sequential picks: one entry per pick frame + one done entry.
    d = _pop_due(drv, ("mode_pick",), actor, phase, turn, "choose_mode")
    sv = d["selection"]["semantic_value"]
    if isinstance(sv, dict) and sv.get("mode_done") is True:
        for i, lb in enumerate(labels):
            if lb.get("_kind") == "MODE" and opts[i].get("kind", "") == "WS48:MODE:DONE":
                drv.consumed.append(d)
                return str(opts[i]["option_id"])
        drv.script.insert(0, d)
        raise base.Blocked("choose_mode", "DONE not offered")
    key = str(sv.get("mode_pick", sv))
    tokens = [t for t in key.lower().replace("_", " ").split() if t]
    hits = []
    for i, lb in enumerate(labels):
        if lb.get("_kind") != "MODE" or "DONE" in opts[i].get("kind", ""):
            continue
        text = (lb.get("api", "") + " " + lb.get("desc", "")).lower()
        if all(t in text for t in tokens):
            hits.append(i)
    if len(hits) != 1:
        drv.script.insert(0, d)
        raise base.Blocked("choose_mode", f"pick {key}: {len(hits)} matches")
    drv.consumed.append(d)
    return str(opts[hits[0]]["option_id"])


def answer_trigger_order_n(drv: Any, actor: str, opts: list[dict[str, Any]],
                           labels: list[dict[str, str]], phase: Any,
                           turn: Any) -> str:
    d = _pop_due(drv, ("trigger_order",), actor, phase, turn, "trigger_order")
    want = [str(x).lower() for x in d["selection"]["semantic_value"]]
    hits = []
    for i, lb in enumerate(labels):
        if lb.get("_kind") != "ORDER":
            continue
        perm = [s for s in (lb.get("order", "") or "").split(",") if s]
        if len(perm) != len(want):
            continue
        if "first" in lb or "second" in lb:
            seq = [lb.get("first", "").lower(), lb.get("second", "").lower()]
            if len(want) == 2 and want[0] in seq[0] and want[1] in seq[1] and perm == ["0", "1"]:
                hits.append(i)
            if len(want) == 2 and want[0] in seq[1] and want[1] in seq[0] and perm == ["1", "0"]:
                hits.append(i)
            continue
        seq = [lb.get(f"m{k}", "").lower() for k in range(len(want))]
        if all(w in s for w, s in zip(want, seq)):
            # verify the permutation actually realizes this sequence:
            # mK holds the K-th element, so any matched label is the witness
            # for exactly the scripted sequence (labels enumerate all perms).
            hits.append(i)
    if len(hits) != 1:
        drv.script.insert(0, d)
        raise base.Blocked("trigger_order", f"order {want}: {len(hits)} matches of {len(opts)}")
    drv.consumed.append(d)
    return str(opts[hits[0]]["option_id"])


_ORIG_WS53_ANSWER = ws53.ws53_answer
_ORIG_CLASSIFY = ws53.classify


def ws55_answer(drv: Any, kind: str, actor: str, opts: list[dict[str, Any]],
                labels: list[dict[str, str]], record: dict[str, Any],
                phase: str | None = None, turn: int | None = None) -> str:
    # Re-parse WS55 labels (run_scenario parsed WS48-only; WS55 fell to _legacy).
    labels55 = [ws55_dec_label(o.get("kind", "")) for o in opts]
    if kind == "combatDamage":
        return answer_combat_damage(drv, actor, opts, labels55, phase, turn)
    if kind == "amountDistribution":
        return answer_amount_distribution(drv, actor, opts, labels55, phase, turn)
    if kind == "optional_costs":
        return answer_optional_costs(drv, actor, opts, labels55, phase, turn)
    if kind == "order_costs":
        return answer_order_costs(drv, actor, opts, labels55, phase, turn)
    if kind == "order_combat":
        return answer_order_combat(drv, actor, opts, labels55, phase, turn)
    if kind == "confirm":
        return answer_confirm(drv, actor, opts, labels55, phase, turn)
    if kind == "trigger_order":
        # N-general (size-2 legacy handled identically).
        try:
            return answer_trigger_order_n(drv, actor, opts, labels55, phase, turn)
        except base.Blocked:
            raise
    if kind == "choose_mode":
        # Multi-shape frames carry WS48:MODE:DONE; single-shape frames do not.
        if any(o.get("kind", "") == "WS48:MODE:DONE" for o in opts):
            return answer_mode_pick(drv, actor, opts, labels55, phase, turn)
        # Single-shape: mode_pick entries may also serve (exact api match).
        due = [e for e in drv.script if e.get("decision_family") == "mode_pick"
               and e.get("actor") == actor]
        if due:
            return answer_mode_pick(drv, actor, opts, labels55, phase, turn)
    return _ORIG_WS53_ANSWER(drv, kind, actor, opts, labels, record, phase, turn)


def ws55_classify(out: dict[str, Any]) -> dict[str, Any]:
    verdict = str(out.get("verdict", ""))
    if verdict.startswith("BLOCKED_AT:"):
        where = verdict.split("BLOCKED_AT:", 1)[1]
        if where in ("combatDamage", "amountDistribution", "optional_costs",
                     "order_costs", "order_combat", "confirm"):
            reason = str(out.get("reason", ""))
            if "unscripted" in reason or "kind-family binding" in reason:
                return {"class": "HARNESS",
                        "note": f"intent gap at transported surface {where}; provider frame well-formed"}
            return {"class": "ADAPTER_BINDING",
                    "note": f"binding gap at {where}: {reason[:300]}"}
    return _ORIG_CLASSIFY(out)


ws53.ws53_answer = ws55_answer  # type: ignore[assignment]
ws53.classify = ws55_classify  # type: ignore[assignment]


def _entry(family: str, actor: str, selector: str, value: Any,
           phases: list[str] | None = None, turns: list[int] | None = None) -> dict[str, Any]:
    e: dict[str, Any] = {
        "decision_family": family, "actor": actor,
        "selection": {"selector_kind": selector,
                      "semantic_value": value,
                      "matches_only_provider_offered_legal_options": True,
                      "on_multiple_match": "FAIL_CLOSED",
                      "on_zero_match": "FAIL_CLOSED"}}
    if phases is not None:
        e["phases"] = phases
    if turns is not None:
        e["turns"] = turns
    return e


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--materialization", type=Path)
    ap.add_argument("--scenario", default="WS55-SMOKE")
    ap.add_argument("--intent-json", type=Path, default=None)
    ap.add_argument("--replay", type=Path, default=None)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--runners", default=".")
    ap.add_argument("--structural-cap", type=int, default=256)
    ap.add_argument("--deck-main", default=None)
    ap.add_argument("--deck-commander", default=None)
    ap.add_argument("--neg-bad-option", default=None)
    a = ap.parse_args()
    sys.path.insert(0, a.runners)
    import run_strict_no_echo_gate as transport  # noqa: E402
    import hashlib as _hl
    committed = (HERE.parent / "ws48-forge-v1.0.5" / "run_behavior_transcript_probe.py").read_bytes()
    staged = (Path(a.runners) / "run_behavior_transcript_probe.py").read_bytes()
    if _hl.sha256(committed).hexdigest() != _hl.sha256(staged).hexdigest():
        raise SystemExit("runners probe copy diverges from committed source")

    if a.deck_main:
        import os as _os
        _os.environ["COMMANDER_LAB_FORGE_DECK_MAIN"] = a.deck_main
    if a.deck_commander:
        import os as _os
        _os.environ["COMMANDER_LAB_FORGE_DECK_COMMANDER"] = a.deck_commander

    if a.materialization is None:
        raise SystemExit("--materialization required (immutable WS47 identity enforced)")
    raw = a.materialization.read_bytes()
    if hashlib.sha256(raw).hexdigest() != WS47_SHA:
        raise SystemExit("immutable WS47 materialization digest mismatch")
    doc = json.loads(raw)
    if doc["schema_version"] != WS47_SCHEMA or doc["canonical_bundle_digest"] != WS47_BUNDLE:
        raise SystemExit("immutable WS47 identity mismatch")
    by = {r["fixture_id"]: r for r in doc["records"]}

    if a.replay is not None:
        journal = json.loads(a.replay.read_text())
        if journal.get("mutated_for_negative"):
            raise SystemExit("refusing to replay a mutated journal as truth")
        scenario = journal["scenario_id"]
        record = copy.deepcopy(by[journal["fixture_id"]])
        intent = copy.deepcopy(journal["intent"])
        # Deck env must match the original run; replay journals record it.
        import os as _os
        dj = journal.get("ws55_deck") or {}
        if dj.get("main"):
            _os.environ["COMMANDER_LAB_FORGE_DECK_MAIN"] = dj["main"]
        if dj.get("commander"):
            _os.environ["COMMANDER_LAB_FORGE_DECK_COMMANDER"] = dj["commander"]
        rerun = ws53.run_scenario(record, transport, intent, scenario + ":REPLAY",
                                  structural_cap=a.structural_cap)
        cmp = ws53.compare_replay(journal, rerun)
        rerun["replay_of"] = str(a.replay)
        rerun["replay_comparison"] = cmp
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(json.dumps(rerun, indent=2, sort_keys=True) + "\n")
        print(f"WS55 {scenario}:REPLAY -> {cmp['replay_verdict']} divs={len(cmp['divergences'])}")
        for d in cmp["divergences"][:10]:
            print("  DIV:", d)
        return 0 if cmp["replay_verdict"] == "PASS" else 1

    if a.scenario != "WS55-BREADTH":
        raise SystemExit(f"unknown scenario {a.scenario} (WS55-BREADTH only; intents via --intent-json)")
    record = copy.deepcopy(by["PILOT_MULLIGAN"])
    if a.intent_json is None:
        raise SystemExit("--intent-json required for WS55-BREADTH")
    intent = json.loads(a.intent_json.read_text())["intent"]
    if a.neg_bad_option:
        # Bad-option probe: answer the first frame of KIND with an unoffered
        # id; the provider must fail closed with WS23_OPTION_NOT_OFFERED.
        target = a.neg_bad_option
        orig = ws53.ws53_answer

        def poisoned(drv: Any, kind: str, actor: str, opts: list[dict[str, Any]],
                     labels: list[dict[str, str]], record: dict[str, Any],
                     phase: str | None = None, turn: int | None = None) -> str:
            if kind == target and not getattr(drv, "ws55_poisoned", False):
                drv.ws55_poisoned = True
                return "o9999"
            return orig(drv, kind, actor, opts, labels, record, phase, turn)

        ws53.ws53_answer = poisoned  # type: ignore[assignment]
    result = ws53.run_scenario(record, transport, intent, a.scenario,
                               structural_cap=a.structural_cap)
    result["schema_version"] = "commander-lab.ws55-decision-breadth/1.0.0"
    result["ws55_deck"] = {"main": a.deck_main, "commander": a.deck_commander}
    if a.neg_bad_option:
        v = str(result.get("verdict", ""))
        sr = str(result.get("stop_reason", ""))
        ok = "WS23_OPTION_NOT_OFFERED" in v or "WS23_OPTION_NOT_OFFERED" in sr
        result["neg_test"] = {"name": f"bad_option@{a.neg_bad_option}",
                              "expected": "fail-closed WS23_OPTION_NOT_OFFERED",
                              "neg_verdict": "PASS" if ok else "FAIL"}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"WS55 {a.scenario} -> {result.get('verdict')} frames={result.get('frame_count')} "
          f"consumed={result.get('consumed_intent')} hidden={result.get('hidden_info_verdict')} "
          f"class={result.get('failure_class', {}).get('class')} stop={result.get('stop_reason')}")
    if result.get("neg_test"):
        print(f"WS55 NEG -> {result['neg_test']['neg_verdict']}")
        return 0 if result["neg_test"]["neg_verdict"] == "PASS" else 1
    return 0 if result.get("verdict") in ("TRANSCRIPT_COMPLETE",
                                          "EXPECTED_FAIL_CLOSED_PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
