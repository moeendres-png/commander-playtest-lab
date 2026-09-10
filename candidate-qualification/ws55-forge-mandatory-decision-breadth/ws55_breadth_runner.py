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
    "target": ("target", "target_done"),
    "order_zone": ("order_zone",),
})


def ws55_dec_label(label: str) -> dict[str, str]:
    """Parse WS48:, WS55:, and prefix-less ws40 Core-view labels."""
    if label.startswith("WS55:"):
        return base.dec_label("WS48:" + label[len("WS55:"):])
    if label.startswith("WS48:"):
        return base.dec_label(label)
    if "|" in label:
        # ws40 Core-view style: KIND|k=v|k=v (raw values, may contain ':').
        out: dict[str, str] = {}
        head, *segs = label.split("|")
        out["_kind"] = head
        for seg in segs:
            if "=" in seg:
                k, v = seg.split("=", 1)
                out[k] = v
            else:
                out[seg] = ""
        return out
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


def answer_target_done(drv: Any, actor: str, opts: list[dict[str, Any]],
                       phase: Any, turn: Any) -> str:
    d = _pop_due(drv, ("target_done",), actor, phase, turn, "target")
    for i, o in enumerate(opts):
        if o.get("kind", "") == "WS48:TARGET:DONE":
            drv.consumed.append(d)
            return str(o["option_id"])
    drv.script.insert(0, d)
    raise base.Blocked("target", "DONE not offered")


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


def _ws55_seq_match(want: list[str], seq_texts: list[str],
                    seq_hids: list[str]) -> bool:
    """One scripted element matches by native hid (MINTED-xxx pattern) or by
    case-insensitive text substring. All positions must match; exactly one
    label may match overall (enforced by caller)."""
    if len(want) != len(seq_texts):
        return False
    for w, text, hid in zip(want, seq_texts, seq_hids):
        if w.startswith("minted-"):
            hid_id = (base.ref_identity(hid) or hid or "").lower()
            if w != hid_id:
                return False
        elif w not in (text or "").lower():
            return False
    return True


def answer_order_zone(drv: Any, actor: str, opts: list[dict[str, Any]],
                      labels: list[dict[str, str]], phase: Any,
                      turn: Any) -> str:
    if getattr(drv, "ws55_diag_accept_order_zone", False):
        # DIAGNOSTIC ONLY (never evidence): accept o0 to reveal the engine's
        # full move sequence in the journal.
        return str(opts[0]["option_id"])
    d = _pop_due(drv, ("order_zone",), actor, phase, turn, "order_zone")
    sv = d["selection"]["semantic_value"]
    # All options in one insertion frame concern the same engine card.
    cards = {base.ref_identity(lb.get("card", "")) for lb in labels}
    if len(cards) != 1:
        drv.script.insert(0, d)
        raise base.Blocked("order_zone", f"mixed-card insertion frame: {sorted(cards)}")
    want_card = sv["card"]
    if want_card not in cards:
        drv.script.insert(0, d)
        raise base.Blocked("order_zone", f"card {want_card} not offered (offered {sorted(cards)})")
    hits = [i for i, lb in enumerate(labels)
            if lb.get("_kind") == "ZONEORDER"
            and str(lb.get("pos", "")) == str(sv["pos"])]
    if len(hits) != 1:
        drv.script.insert(0, d)
        raise base.Blocked("order_zone", f"pos {sv['pos']}: {len(hits)} matches of {len(opts)}")
    drv.consumed.append(d)
    return str(opts[hits[0]]["option_id"])


def answer_replacement(drv: Any, actor: str, opts: list[dict[str, Any]],
                       labels: list[dict[str, str]], phase: Any,
                       turn: Any) -> str:
    # WS55 extension: boolean apply (confirmReplacementEffect) passes through
    # to the base mechanism; multi-replacer ordering (chooseSingleReplacement-
    # Effect, WS48:REPL:src= labels) matches an engine-identity substring.
    peek = [e for e in drv.script if e.get("decision_family") == "replacement_effect"
            and e.get("actor") == actor]
    if peek and isinstance((peek[0].get("selection") or {}).get("semantic_value"), dict):
        d = _pop_due(drv, ("replacement_effect",), actor, phase, turn,
                     "replacement_effect")
        sv = d["selection"]["semantic_value"]
        if isinstance(sv, dict) and "order_pick" in sv:
            hits = [i for i, lb in enumerate(labels)
                    if lb.get("_kind") == "REPL" and "src" in lb
                    and sv["order_pick"] in lb.get("src", "")]
            if len(hits) != 1:
                drv.script.insert(0, d)
                raise base.Blocked("replacement_effect",
                                   f"order_pick {sv['order_pick']}: {len(hits)} matches of {len(opts)}")
            drv.consumed.append(d)
            return str(opts[hits[0]]["option_id"])
        drv.script.insert(0, d)
        raise base.Blocked("replacement_effect", f"unknown replacement semantic {sv}")
    return base.answer_replacement(drv, actor, opts, labels)


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
        if "first" in lb or "second" in lb:
            # Size-2 legacy labels: the [first,second] segments ARE the result
            # sequence for BOTH permutations (o0:[SA0,SA1], o1:[SA1,SA0] with
            # segs bound to the returned order). Match the sequence only.
            if len(want) != 2:
                continue
            seq = [lb.get("first", "").lower(), lb.get("second", "").lower()]
            seq_hids = [lb.get("hidfirst", ""), lb.get("hidsecond", "")]
            if _ws55_seq_match(want, seq, seq_hids):
                hits.append(i)
            continue
        seq = [lb.get(f"m{k}", "").lower() for k in range(len(want))]
        seq_hids = [lb.get(f"h{k}", "") for k in range(len(want))]
        if _ws55_seq_match(want, seq, seq_hids):
            # mK holds the K-th element of this permutation's sequence, so a
            # matched label is the witness for exactly the scripted sequence
            # (labels enumerate all perms).
            hits.append(i)
    if len(hits) != 1:
        drv.script.insert(0, d)
        raise base.Blocked("trigger_order", f"order {want}: {len(hits)} matches of {len(opts)}")
    drv.consumed.append(d)
    return str(opts[hits[0]]["option_id"])


_ORIG_WS53_ANSWER = ws53.ws53_answer
_ORIG_CLASSIFY = ws53.classify
_ORIG_SELECTED_IDENTITY = ws53.selected_identity


def answer_ranged_number(drv: Any, actor: str, opts: list[dict[str, Any]],
                         labels: list[dict[str, str]], phase: Any,
                         turn: Any) -> str:
    """Ranged integer frame: single NUMRANGE descriptor; submit by value."""
    d = _pop_due(drv, ("announce_x",), actor, phase, turn, "announce_x")
    want = str(int(d["selection"]["semantic_value"]))
    if len(opts) != 1 or (labels[0].get("_kind") != "NUMRANGE"):
        drv.script.insert(0, d)
        raise base.Blocked("announce_x", "ranged answer on non-ranged frame")
    lo, hi = labels[0].get("min", ""), labels[0].get("max", "")
    drv.consumed.append(d)
    _ws55_pending_value[0] = want
    return str(opts[0]["option_id"])

#: Slot for a ranged integer submission set by answer_number (single-threaded
#: driver: set during answer, consumed by submit + identity in the same frame).
_ws55_pending_value: list[str | None] = [None]


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
    if kind == "target":
        # Multi-target DONE discipline: regular target entries take precedence;
        # target_done entries close targeting once no pick remains due.
        due_pick = [e for e in drv.script if e.get("decision_family") == "target"
                    and e.get("actor") == actor
                    and (e.get("phases") is None or phase in (e.get("phases") or []))
                    and (e.get("turns") is None or turn in (e.get("turns") or []))]
        if not due_pick:
            due_done = [e for e in drv.script if e.get("decision_family") == "target_done"
                        and e.get("actor") == actor
                        and (e.get("phases") is None or phase in (e.get("phases") or []))
                        and (e.get("turns") is None or turn in (e.get("turns") or []))]
            if due_done and any(o.get("kind", "") == "WS48:TARGET:DONE" for o in opts):
                return answer_target_done(drv, actor, opts, phase, turn)
    if kind == "announce_x":
        if len(opts) == 1 and labels55 and labels55[0].get("_kind") == "NUMRANGE":
            return answer_ranged_number(drv, actor, opts, labels55, phase, turn)
        # Enumerated NUM path stays on the WS53 mechanism.
    if kind == "replacement_effect":
        return answer_replacement(drv, actor, opts, labels55, phase, turn)
    if kind == "order_zone":
        return answer_order_zone(drv, actor, opts, labels55, phase, turn)
    if kind == "mana_payment":
        # Fold scripted mana sources into cost_state once (record ships none).
        if not getattr(drv, "ws55_mana_folded", False):
            drv.ws55_mana_folded = True
            for e in list(drv.script):
                if e.get("decision_family") == "mana_payment":
                    drv.script.remove(e)
                    drv.cost_state.append({
                        "actor": e.get("actor", actor),
                        "explicit_payment_sources": list(
                            (e.get("selection") or {}).get("semantic_value", {}).get("sources", [])),
                    })
                    drv.consumed.append(e)
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
                     "order_costs", "order_combat", "confirm", "order_zone"):
            reason = str(out.get("reason", ""))
            if "unscripted" in reason or "kind-family binding" in reason:
                return {"class": "HARNESS",
                        "note": f"intent gap at transported surface {where}; provider frame well-formed"}
            return {"class": "ADAPTER_BINDING",
                    "note": f"binding gap at {where}: {reason[:300]}"}
    return _ORIG_CLASSIFY(out)


ws53.ws53_answer = ws55_answer  # type: ignore[assignment]
ws53.classify = ws55_classify  # type: ignore[assignment]


def ws55_run_scenario(record: dict[str, Any], transport: Any,
                      intent: list[dict[str, Any]], scenario_id: str,
                      per_record_timeout: int = 600,
                      structural_cap: int = 256,
                      neg_stale: bool = False,
                      diag_accept_order_zone: bool = False) -> dict[str, Any]:
    """WS55-owned scenario loop (copied from the WS53 converged runner, which
    is imported but never modified). Differences: SUBMIT carries an optional
    by-value integer for WS55:NUMRANGE frames; journal selection identities
    record the submitted value; --neg-stale duplicate-submit probe."""
    import os as _os
    import selectors as _selectors
    import tempfile as _tempfile
    import time as _time
    drv = ws53.WS53Driver(record, intent, structural_cap)
    drv.ws55_diag_accept_order_zone = diag_accept_order_zone
    sent = ws53.sentinel_names(record, "")
    out: dict[str, Any] = {
        "schema_version": "commander-lab.ws55-decision-breadth/1.0.0",
        "evidence_class": "DECISION_SEQUENCE",
        "grants_behavior_credit": False,
        "behavior_credit": "0/107",
        "credited_path": True,
        "diagnostic_only": False,
        "scenario_id": scenario_id,
        "fixture_id": record["fixture_id"],
        "execution_entry_mode": record["execution_entry_mode"],
        "forge": {"commit": FORGE_COMMIT, "tree": FORGE_TREE},
        "seed": ((record.get("rules_randomness") or {}).get("rules_seed")),
        "seed_binding": WS55_SEED_BINDING,
        "intent": intent,
    }
    deadline = _time.monotonic() + per_record_timeout
    proc: Any = None
    stop_reason: str | None = None
    snapshot: Any = None
    answered = 0
    violations: list[str] = []
    lifecycle: Any = None
    try:
        with _tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as err:
            p = base.subprocess.Popen(base.command(), stdin=base.subprocess.PIPE,
                                      stdout=base.subprocess.PIPE, stderr=err,
                                      text=True,
                                      env=base.behavior_env(record, transport), bufsize=1)
            proc = p
            assert p.stdin is not None and p.stdout is not None
            bindup = _os.dup(p.stdout.fileno())
            try:
                sel = _selectors.DefaultSelector()
                sel.register(bindup, _selectors.EVENT_READ)
            except Exception:
                sel = None
            buf = b""

            def next_line() -> str | None:
                nonlocal buf
                while True:
                    if b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        return (line + b"\n").decode("utf-8", errors="replace")
                    if p.poll() is not None:
                        try:
                            chunk = _os.read(bindup, 65536)
                        except OSError:
                            chunk = b""
                        if chunk:
                            buf += chunk
                            continue
                        if buf:
                            rest, buf = buf, b""
                            return rest.decode("utf-8", errors="replace")
                        return None
                    remaining = deadline - _time.monotonic()
                    if remaining <= 0:
                        raise base.Blocked("TIMEOUT",
                                           f"no session result within {per_record_timeout}s")
                    if sel is not None:
                        ready = sel.select(timeout=min(5.0, remaining))
                        if not ready:
                            continue
                    else:
                        _time.sleep(0.05)
                    try:
                        chunk = _os.read(bindup, 65536)
                    except OSError:
                        chunk = b""
                    if not chunk:
                        if p.poll() is not None:
                            continue
                        continue
                    buf += chunk

            def submit(frame: dict[str, Any], oid: str,
                       value: str | None = None) -> None:
                payload: dict[str, Any] = {"decision_id": frame["payload"]["decision_id"],
                                           "option_id": oid}
                if value is not None:
                    payload["value"] = value
                p.stdin.write(json.dumps({
                    "protocol": PROTOCOL, "message_type": "SUBMIT_DECISION",
                    "request_id": "ws55-reply-" + frame["payload"]["decision_id"],
                    "session_id": frame.get("session_id"),
                    "payload": payload}, separators=(",", ":")) + "\n")
                p.stdin.flush()

            def drain_to_result() -> None:
                nonlocal stop_reason, snapshot
                try:
                    p.stdin.close()
                except Exception:
                    pass
                for _ in range(4096):
                    line = next_line()
                    if not line:
                        break
                    try:
                        m = json.loads(line)
                    except Exception:
                        continue
                    if m.get("message_type") == "SESSION_RESULT":
                        stop_reason = (m.get("payload") or {}).get("stop_reason")
                        snapshot = (m.get("payload") or {}).get("snapshot")
                        drv.result_seen = True
                        break
                    if m.get("message_type") == "NATIVE_EVENT":
                        drv.events.append({"event": (m.get("payload") or {}).get("event"),
                                           "facts": (m.get("payload") or {}).get("facts")})

            def close_and_collect() -> tuple[int, str]:
                try:
                    p.stdin.close()
                except Exception:
                    pass
                try:
                    rc = p.wait(timeout=60)
                except Exception:
                    p.kill()
                    rc = 124
                err.seek(0)
                return rc, err.read()[-6000:]

            is_negative = any(d["selection"]["selector_kind"] == "fail_closed_probe"
                              for d in drv.script)
            p.stdin.write(json.dumps({
                "protocol": PROTOCOL, "message_type": "CREATE_SESSION",
                "request_id": "ws55-" + scenario_id,
                "payload": {"fixture_id": record["fixture_id"]}},
                separators=(",", ":")) + "\n")
            p.stdin.flush()
            exit_rc: Any = None
            stderr_tail = ""
            stale_sent = False
            for _ in range(4096):
                line = next_line()
                if not line:
                    break
                if len(drv.raw_lines) < 200:
                    drv.raw_lines.append(line[:500])
                try:
                    m = json.loads(line)
                except Exception:
                    drv.decode_errors += 1
                    if drv.decode_errors > 16:
                        raise base.Blocked("PROTOCOL", "too many undecodable lines")
                    continue
                typ = m.get("message_type")
                if typ == "SESSION_CREATED":
                    out["session_created_snapshot"] = (m.get("payload") or {}).get("snapshot")
                    continue
                if typ == "QUALIFICATION_STATE":
                    payload = m.get("payload") or {}
                    if payload.get("stage") == "after_native_setup_validation":
                        drv.setup_stage_seen = True
                    if payload.get("stage") == "native_post_mulligan_pre_main_loop":
                        lifecycle = payload.get("raw_native")
                    continue
                if typ == "NATIVE_EVENT":
                    drv.events.append({"event": (m.get("payload") or {}).get("event"),
                                       "facts": (m.get("payload") or {}).get("facts")})
                    continue
                if typ == "SESSION_RESULT":
                    stop_reason = (m.get("payload") or {}).get("stop_reason")
                    snapshot = (m.get("payload") or {}).get("snapshot")
                    drv.result_seen = True
                    break
                if typ != "DECISION_FRAME":
                    raise base.Blocked("PROTOCOL", f"unexpected message {typ}")
                pay = m["payload"]
                kind = pay.get("decision_kind")
                actor = drv.actor_pid(m)
                opts = drv.options(m)
                labels = [base.dec_label(o.get("kind", "")) for o in opts]
                frame_no = len(drv.journal) + 1
                obs = pay.get("observations") or []
                violations.extend(ws53.audit_observations(frame_no, actor, obs, sent))
                if pay.get("state_snapshot") in (None, "null"):
                    violations.append(
                        f"frame {frame_no}: null state_snapshot on credited path")
                entry: dict[str, Any] = {
                    "seq": frame_no,
                    "engine_frame_id": pay.get("decision_id"),
                    "engine_frame_seq": pay.get("frame_seq"),
                    "revision": m.get("state_revision"),
                    "actor": actor,
                    "raw_actor": m.get("actor_id"),
                    "kind": kind,
                    "cancel_offered": pay.get("cancel_offered"),
                    "rng": pay.get("rng"),
                    "state_fingerprint": pay.get("state_fingerprint"),
                    "state_snapshot": pay.get("state_snapshot"),
                    "observation_fingerprints": {o.get("viewer"): o.get("fingerprint")
                                                 for o in obs},
                    "observations": obs,
                    "option_count": len(opts),
                    "offered_identities": sorted(o.get("kind", "") for o in opts),
                    "offered_options": [{"id": o.get("option_id"), "kind": o.get("kind", "")}
                                        for o in opts],
                }
                if len(drv.journal) >= 1024:
                    raise base.Blocked("PROTOCOL", "journal budget exceeded")
                if is_negative:
                    entry["selection"] = None
                    entry["engine_response"] = "NEGATIVE_DRAIN"
                    drv.journal.append(entry)
                    drain_to_result()
                    rc, tail = close_and_collect()
                    out.update({"stop_after_eof_rc": rc, "stderr_tail": tail})
                    break
                try:
                    oid = ws53.ws53_answer(drv, kind, actor, opts, labels, record,
                                           ws53.frame_phase(pay), ws53.frame_turn(pay))
                except base.Blocked as b:
                    entry["selection"] = None
                    entry["block"] = {"where": b.where, "detail": b.detail[:2000]}
                    entry["engine_response"] = "HARNESS_FAIL_CLOSED"
                    drv.journal.append(entry)
                    raise
                value = _ws55_pending_value[0]
                _ws55_pending_value[0] = None
                if oid == "__TERMINATE__":
                    entry["selection"] = None
                    entry["engine_response"] = "HARNESS_SCRIPT_EXHAUSTION_TERMINATE"
                    drv.journal.append(entry)
                    drain_to_result()
                    rc, tail = close_and_collect()
                    out.update({"terminate_rc": rc, "stderr_tail": tail})
                    break
                submit(m, oid, value)
                answered += 1
                ident = ws53.selected_identity(kind, oid, opts)
                if value is not None:
                    ident += ":value=" + str(value)
                entry["selection"] = {"option_id": oid, "identity": ident}
                entry["engine_response"] = "ACCEPTED_CONTINUED"
                drv.journal.append(entry)
                drv.frames.append({"kind": kind, "actor": actor,
                                   "option_count": len(opts),
                                   "options": [o.get("kind", "") for o in opts][:16]})
                if neg_stale and not stale_sent:
                    # Duplicate-submit probe: resend this frame's submit verbatim.
                    # The provider has advanced past this decision id and must
                    # fail closed with WS23_STALE_OR_WRONG_DECISION_ID.
                    stale_sent = True
                    submit(m, oid, value)
            else:
                exit_rc, stderr_tail = close_and_collect()
                out.update({"verdict": "PROBE_FAIL", "reason": "FRAME_BUDGET_EXHAUSTED",
                            "terminal_class": "HARNESS_FRAME_BUDGET",
                            "exit_rc": exit_rc, "stderr_tail": stderr_tail})
                return ws53.finish_ws53(out, drv, stop_reason, snapshot, answered,
                                        violations, lifecycle)
            if is_negative and stop_reason is not None:
                exit_rc, stderr_tail = close_and_collect()
                out.update({"exit_rc": exit_rc, "stderr_tail": stderr_tail})
                return ws53.finish_negative_ws53(out, drv, record, stop_reason, violations)
            if stop_reason is None and "terminate_rc" not in out:
                exit_rc, stderr_tail = close_and_collect()
                out.update({"exit_rc": exit_rc, "stderr_tail": stderr_tail})
            return ws53.finish_ws53(out, drv, stop_reason, snapshot, answered,
                                    violations, lifecycle)
    except base.Blocked as b:
        try:
            if proc is not None:
                proc.kill()
        except Exception:
            pass
        out.update({"verdict": f"BLOCKED_AT:{b.where}", "reason": b.detail[:4000],
                    "terminal_class": "HARNESS_INTENT_GAP"})
        return ws53.finish_ws53(out, drv, None, None, 0, violations, lifecycle)
    except Exception as ex:
        try:
            if proc is not None:
                proc.kill()
        except Exception:
            pass
        out.update({"verdict": "PROBE_FAIL",
                    "reason": f"{type(ex).__name__}:{ex}"[:4000],
                    "terminal_class": "HARNESS_PROBE_ERROR"})
        return ws53.finish_ws53(out, drv, None, None, 0, violations, lifecycle)


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
    ap.add_argument("--order-combatants", default=None)
    ap.add_argument("--neg-bad-option", default=None)
    ap.add_argument("--neg-stale", action="store_true")
    ap.add_argument("--diag-accept-order-zone", action="store_true")
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
    if a.order_combatants:
        import os as _os
        _os.environ["COMMANDER_LAB_FORGE_ORDER_COMBATANTS"] = a.order_combatants

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
        if journal.get("ws55_order_combatants"):
            _os.environ["COMMANDER_LAB_FORGE_ORDER_COMBATANTS"] = journal["ws55_order_combatants"]
        rerun = ws55_run_scenario(record, transport, intent, scenario + ":REPLAY",
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
    result = ws55_run_scenario(record, transport, intent, a.scenario,
                               structural_cap=a.structural_cap,
                               neg_stale=a.neg_stale,
                               diag_accept_order_zone=a.diag_accept_order_zone)
    if a.diag_accept_order_zone:
        result["diagnostic_only"] = True
        result["credited_path"] = False
    result["schema_version"] = "commander-lab.ws55-decision-breadth/1.0.0"
    result["ws55_deck"] = {"main": a.deck_main, "commander": a.deck_commander}
    result["ws55_order_combatants"] = a.order_combatants
    if a.neg_stale:
        v = str(result.get("verdict", ""))
        sr = str(result.get("stop_reason", ""))
        ok = "WS23_STALE_OR_WRONG_DECISION_ID" in v or "WS23_STALE_OR_WRONG_DECISION_ID" in sr
        result["neg_test"] = {"name": "stale_duplicate_submit",
                              "expected": "fail-closed WS23_STALE_OR_WRONG_DECISION_ID",
                              "neg_verdict": "PASS" if ok else "FAIL"}
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
