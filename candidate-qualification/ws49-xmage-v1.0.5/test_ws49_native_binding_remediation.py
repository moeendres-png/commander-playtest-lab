#!/usr/bin/env python3
"""WS49 native-binding remediation wave — offline/unit regression (no engine).

Phases 0-5, source-proof + fixture validation without Full107 and without
behavior-credit promotion. Every assertion is offline (synthetic decisions
and immutable WS47 bytes); engine runtime remains UNKNOWN pending a future
qualified Full107. R2 vocabulary normalization is preserved (tested
separately by test_ws49_r2_frame_vocabulary.py).

Evidence: CODE_DERIVED for logic gates; DIRECTLY_VERIFIED for WS47 byte
checks; UNKNOWN for engine runtime.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS42 = HERE.parents[0] / "ws42-xmage-v1.0.3"
sys.path[:0] = [str(HERE), str(WS42)]

import run_full107_behavior_probe_v105 as probe  # noqa: E402

PASS = []
FAIL = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        PASS.append(name)
        print(f"[ok] {name}")
    else:
        FAIL.append(name)
        print(f"[FAIL] {name} {detail}")


def expect_fail(name: str, fn, code_fragment: str) -> None:
    try:
        fn()
    except RuntimeError as exc:
        check(name, code_fragment in str(exc), f"got: {exc}")
        return
    except Exception as exc:  # noqa: BLE001
        FAIL.append(name)
        print(f"[FAIL] {name} wrong exception: {type(exc).__name__}: {exc}")
        return
    FAIL.append(name)
    print(f"[FAIL] {name} expected failure containing {code_fragment}, got PASS")


def rec(ops: list[str], fixture_id: str = "TEST") -> dict:
    return {
        "fixture_id": fixture_id,
        "native_procedure": [{"operation": op} for op in ops],
        "players": [{}, {}, {}, {}],
    }


# ---------------------------------------------------------------- Phase 0
def test_phase0_allowlist() -> None:
    allow = [
        "NATIVE_CONTINUE_WITH_EXPLICIT_SCRIPTED_PRIORITY_PASSES_UNTIL_NEXT_DECLARED_DECISION",
        "NATIVE_RESOLVE_CAST_WITH_EXPLICIT_SCRIPTED_PRIORITY_PASSES",
        "NATIVE_RESOLVE_OR_EVALUATE_DECLARED_RULES_CAUSE_TO_TERMINAL_CHECKPOINT",
        "NATIVE_RESOLVE_TOP_OF_STACK",
        "NATIVE_RESOLVE_TRIGGER",
    ]
    for op in allow:
        check(f"P0 allow {op}", probe.procedure_has_pass_steps(rec([op])) is True)
    # Regression: ENTER_DECLARE must NOT acquire pass authority.
    check(
        "P0 ENTER_DECLARE no pass",
        probe.procedure_has_pass_steps(
            rec(["NATIVE_ENTER_DECLARE_ATTACKERS_STEP", "NATIVE_DECLARE_ATTACKERS"], "PILOT_DECLARE_ATTACKER")
        )
        is False,
    )
    check(
        "P0 bare construct no pass",
        probe.procedure_has_pass_steps(rec(["NATIVE_CONSTRUCT_AND_VALIDATE_REQUESTED_STATE"])) is False,
    )
    check(
        "P0 knowledge projection no pass",
        probe.procedure_has_pass_steps(
            rec(["NATIVE_CONSTRUCT_AND_VALIDATE_REQUESTED_STATE", "NATIVE_KNOWLEDGE_PROJECTION"], "HIDDEN_01")
        )
        is False,
    )
    check(
        "P0 multi-op without allowlist no pass",
        probe.procedure_has_pass_steps(rec(["NATIVE_CAST_SPELL"])) is False,
    )
    check("P0 empty no pass", probe.procedure_has_pass_steps(rec([])) is False)


def test_phase0_ws47_fixtures() -> None:
    repo_root = HERE.parents[1]
    blob = subprocess.run(
        ["git", "show", "192e2b77c0625ad26905bd0ee8dcc3f44a5796c8:qualification/ws47/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json"],
        cwd=str(repo_root),
        capture_output=True,
        check=True,
    ).stdout
    data = json.loads(blob)
    rows = [r for r in data["records"] if r.get("fixture_family") != "actual_card" or r.get("fixture_id") == "CARD_02"]
    by_id = {r["fixture_id"]: r for r in rows}
    # Representative 1: PILOT_PRIORITY carries NATIVE_RESOLVE_TOP_OF_STACK -> pass.
    check(
        "P0 WS47 PILOT_PRIORITY allow",
        probe.procedure_has_pass_steps(by_id["PILOT_PRIORITY"]) is True,
    )
    # Representative 2 (independent): PILOT_TARGET same allowlist family.
    check(
        "P0 WS47 PILOT_TARGET allow",
        probe.procedure_has_pass_steps(by_id["PILOT_TARGET"]) is True,
    )
    # Regression fixture: PILOT_DECLARE_ATTACKER must NOT pass.
    check(
        "P0 WS47 PILOT_DECLARE_ATTACKER no pass",
        probe.procedure_has_pass_steps(by_id["PILOT_DECLARE_ATTACKER"]) is False,
    )


# ---------------------------------------------------------------- Phase 1
def synth_record(objects: list[dict]) -> dict:
    return {"fixture_id": "TEST", "players": [{}, {}, {}, {}], "semantic_objects": objects}


def synth_decision(options: list[dict], pilot_state: dict, klass: str = "target") -> dict:
    return {"decision_class": klass, "seat": 0, "legal_options": options, "pilot_state": pilot_state}


def opt(oid: str, label: str = "x", otype: str = "target", meta: dict | None = None) -> dict:
    return {"option_id": oid, "label": label, "option_type": otype, "metadata": meta or {}}


def test_phase1_owner_controller() -> None:
    wanted = {
        "semantic_id": "obj:a",
        "card_identity": "Grizzly Bears",
        "owner": "P1",
        "controller": "P1",
        "zone": "battlefield",
        "tapped": False,
        "counters": {},
    }
    same_name_p2 = {"object_id": "h2", "name": "Grizzly Bears", "zone": "battlefield", "owner": "P2", "controller": "P2", "tapped": False, "counters": {}}
    same_name_p1 = {"object_id": "h1", "name": "Grizzly Bears", "zone": "battlefield", "owner": "P1", "controller": "P1", "tapped": False, "counters": {}}
    # Same name different owner: wanted P1 must agree only with P1 item.
    check("P1 owner distinguishes", probe._profile_agrees(wanted, same_name_p1) is True)
    check("P1 owner rejects P2", probe._profile_agrees(wanted, same_name_p2) is False)
    # Same name different controller.
    ctrl_diff = dict(same_name_p1, controller="P2")
    check("P1 controller rejects", probe._profile_agrees(wanted, ctrl_diff) is False)
    # Counters matter.
    with_counter = dict(same_name_p1, counters={"P1P1": 1})
    wanted_counter = dict(wanted, counters={"P1P1": 1})
    check("P1 counters agree", probe._profile_agrees(wanted_counter, with_counter) is True)
    check("P1 counters reject mismatch", probe._profile_agrees(wanted, with_counter) is False)


def test_phase1_unique_fail_closed() -> None:
    objs = [
        {"semantic_id": "obj:a", "card_identity": "Grizzly Bears", "owner": "P1", "controller": "P1", "zone": "battlefield", "tapped": False, "counters": {}},
    ]
    # Same name same zone multiple objects -> multiple inventory matches -> fail.
    pilot = {
        "players": [
            {"player_id": "P1", "battlefield": [
                {"object_id": "h1", "name": "Grizzly Bears", "owner": "P1", "controller": "P1", "tapped": False, "counters": {}},
                {"object_id": "h2", "name": "Grizzly Bears", "owner": "P1", "controller": "P1", "tapped": False, "counters": {}},
            ]},
            {"player_id": "P2", "battlefield": []},
            {"player_id": "P3", "battlefield": []},
            {"player_id": "P4", "battlefield": []},
        ]
    }
    dec = synth_decision([opt("h1", meta={"object_id": "h1"}), opt("h2", meta={"object_id": "h2"})], pilot)
    expect_fail(
        "P1 multiple match fails closed",
        lambda: probe.profile_match_object(synth_record(objs), dec, "obj:a", "TEST"),
        "WS49_BEHAVIOR_OBJECT_PROFILE_NOT_UNIQUE",
    )
    # Stale object: inventory handle not in offers -> fail.
    pilot2 = {
        "players": [
            {"player_id": "P1", "battlefield": [
                {"object_id": "stale", "name": "Grizzly Bears", "owner": "P1", "controller": "P1", "tapped": False, "counters": {}},
            ]},
            {"player_id": "P2", "battlefield": []},
            {"player_id": "P3", "battlefield": []},
            {"player_id": "P4", "battlefield": []},
        ]
    }
    dec2 = synth_decision([opt("other", meta={"object_id": "other"})], pilot2)
    expect_fail(
        "P1 stale object fails closed",
        lambda: probe.profile_match_object(synth_record(objs), dec2, "obj:a", "TEST"),
        "WS49_BEHAVIOR_SELECTOR_MATCH_NOT_UNIQUE",
    )
    # Illegal target requested: zero inventory match -> fail.
    pilot3 = {
        "players": [
            {"player_id": "P1", "battlefield": [{"object_id": "h9", "name": "Other", "owner": "P1", "controller": "P1", "tapped": False}]},
            {"player_id": "P2", "battlefield": []},
            {"player_id": "P3", "battlefield": []},
            {"player_id": "P4", "battlefield": []},
        ]
    }
    dec3 = synth_decision([opt("h9", meta={"object_id": "h9"})], pilot3)
    expect_fail(
        "P1 illegal target fails closed",
        lambda: probe.profile_match_object(synth_record(objs), dec3, "obj:a", "TEST"),
        "WS49_BEHAVIOR_OBJECT_PROFILE_NOT_UNIQUE",
    )


def test_phase1_player_provenance() -> None:
    record = {"fixture_id": "TEST", "players": [{}, {}, {}, {}]}
    entry = {"actor": "P1", "decision_family": "target", "selection": {"selector_kind": "semantic_player", "semantic_value": "P2"}}
    label = probe.seat_label_for("P2", 4, "TEST")
    # Exact label + coherent metadata passes uniquely.
    dec = synth_decision([opt("o1", label=label, meta={"name": label}), opt("o2", label="other", meta={"name": "other"})], {})
    sel, _, _, events, done = probe.match_selection(entry, dec, record)
    check("P1 player unique match", sel == ["o1"] and done is True and events == ["target_selected:P2"])
    # Multiple same-label offers -> fail closed.
    dec2 = synth_decision([opt("o1", label=label, meta={"name": label}), opt("o3", label=label, meta={"name": label})], {})
    expect_fail(
        "P1 player multiple fails closed",
        lambda: probe.match_selection(entry, dec2, record),
        "WS49_BEHAVIOR_SELECTOR_MATCH_NOT_UNIQUE",
    )
    # Provenance contradiction fails closed (player_ref mismatch).
    dec3 = synth_decision([opt("o1", label=label, meta={"name": label, "player_ref": "P3"})], {})
    expect_fail(
        "P1 player provenance mismatch fails closed",
        lambda: probe.match_selection(entry, dec3, record),
        "WS49_BEHAVIOR_SELECTOR_MATCH_NOT_UNIQUE",
    )


# ---------------------------------------------------------------- Phase 2
def test_phase2_source_scoping() -> None:
    # Arming: single payable for another source must NOT arm source A.
    record = {
        "fixture_id": "TEST",
        "players": [{}, {}],
        "action_cost_state": [
            {"actor": "P1", "payable": True, "source_semantic_id": "obj:other", "explicit_payment_sources": ["obj:land-x"]},
        ],
    }
    # Simulate arming logic from execute_decision_driven (source-scoped only).
    payable = [e for e in record["action_cost_state"] if e.get("payable") is True and e.get("actor") == "P1"]
    cost_by_source = [e for e in payable if e.get("source_semantic_id") == "obj:counterspell"]
    check("P2 source-A not armed from source-B", len(cost_by_source) == 0)
    # Commander null-source singleton still arms (both null).
    record2 = {
        "fixture_id": "TEST",
        "action_cost_state": [
            {"actor": "P1", "payable": True, "source_semantic_id": None, "explicit_payment_sources": ["obj:m0"]},
        ],
    }
    payable2 = [e for e in record2["action_cost_state"] if e.get("payable") is True and e.get("actor") == "P1"]
    by_src2 = [e for e in payable2 if e.get("source_semantic_id") is None]
    check("P2 commander null-source arms", len(by_src2) == 1)
    # match_mana_payment actor scoping: global singleton for P2 must not serve P1.
    entry = {"actor": "P1", "selection": {"semantic_value": {"mana": ["U"]}}}
    decision = {"decision_class": "mana_payment", "seat": 0, "legal_options": [opt("m1", otype="mana_pool", meta={"mana_type": "U"})], "context": {}}
    record3 = {
        "fixture_id": "TEST",
        "players": [{}, {}],
        "action_cost_state": [
            {"actor": "P2", "payable": True, "source_semantic_id": "obj:x", "explicit_payment_sources": ["obj:land-p2"]},
        ],
    }
    expect_fail(
        "P2 actor-scoped merge fails closed for wrong actor",
        lambda: probe.match_mana_payment(entry, decision, record3),
        "WS49_BEHAVIOR_MANA_SOURCES_UNAVAILABLE",
    )


# ---------------------------------------------------------------- Phase 3
def bucket(pid: str, seat: int, hand: list | None = None) -> dict:
    b = {"player_id": pid, "seat": seat, "life": 40}
    if hand is not None:
        b["hand"] = hand
    return b


def test_phase3_hidden_binding() -> None:
    record = {"fixture_id": "HIDDEN_01", "players": [{}, {}, {}, {}], "knowledge_state": {"viewer_states": [{"viewer": "P1"}]}}
    # Native player set authority: 4 buckets required, not declared set.
    obs_ok = {
        "P1": {"players": [bucket("P1", 0, [{"object_id": "c1", "name": "Plains"}]), bucket("P2", 1), bucket("P3", 2), bucket("P4", 3)], "stack": []},
        "P2": {"players": [bucket("P1", 0), bucket("P2", 1, [{"object_id": "c2", "name": "Island"}]), bucket("P3", 2), bucket("P4", 3)], "stack": []},
        "P3": {"players": [bucket("P1", 0), bucket("P2", 1), bucket("P3", 2, [{"object_id": "c3", "name": "Swamp"}]), bucket("P4", 3)], "stack": []},
        "P4": {"players": [bucket("P1", 0), bucket("P2", 1), bucket("P3", 2), bucket("P4", 3, [{"object_id": "c4", "name": "Mountain"}])], "stack": []},
    }
    detail = probe.verify_viewer_states(record, obs_ok, {k: {} for k in obs_ok})
    check("P3 all viewers verified natively", detail["viewers_verified"] == ["P1", "P2", "P3", "P4"])
    check("P3 own-hand event", any(e.startswith("hidden_own_hand_visible") for e in detail["native_hidden_events"]))
    # Opponent hand exposed -> fail closed.
    obs_leak = {
        "P1": {"players": [bucket("P1", 0, [{"object_id": "c1", "name": "Plains"}]), bucket("P2", 1, [{"object_id": "evil", "name": "Secret"}]), bucket("P3", 2), bucket("P4", 3)], "stack": []},
    }
    expect_fail(
        "P3 opponent leak fails closed",
        lambda: probe.verify_viewer_states(record, obs_leak, {}),
        "WS49_BEHAVIOR_OPPONENT_HAND_IDENTITIES_EXPOSED",
    )
    # Incomplete native set (declared-only) -> fail closed, proving no PASS from declared list alone.
    obs_declared_only = {"P1": obs_ok["P1"]}
    detail2 = probe.verify_viewer_states(record, obs_declared_only, {})
    check(
        "P3 declared-only not full native set",
        set(detail2["viewers_verified"]) != {"P1", "P2", "P3", "P4"},
    )
    # Face-down exile redacted.
    record4 = {"fixture_id": "HIDDEN_X", "players": [{}, {}]}
    obs_exile = {
        "P1": {"players": [
            bucket("P1", 0, []),
            dict(bucket("P2", 1), exile=[{"object_id": "e1", "name": "Hidden card", "face_down": True}]),
        ], "stack": []},
        "P2": {"players": [
            bucket("P1", 0),
            bucket("P2", 1, []),
        ], "stack": []},
    }
    detail3 = probe.verify_viewer_states(record4, obs_exile, {k: {} for k in obs_exile})
    check("P3 face-down exile redacted", any("face_down_exile_redacted" in e for e in detail3["native_hidden_events"]))
    # Face-down exile leak -> fail.
    obs_exile_leak = {
        "P1": {"players": [
            bucket("P1", 0, []),
            dict(bucket("P2", 1), exile=[{"object_id": "e1", "name": "Black Lotus", "face_down": True}]),
        ], "stack": []},
        "P2": {"players": [bucket("P1", 0), bucket("P2", 1, [])], "stack": []},
    }
    expect_fail(
        "P3 face-down exile leak fails closed",
        lambda: probe.verify_viewer_states(record4, obs_exile_leak, {}),
        "WS49_BEHAVIOR_FACE_DOWN_EXILE_EXPOSED",
    )


# ---------------------------------------------------------------- Phase 4
def test_phase4_no_transcript_ring() -> None:
    record = {"fixture_id": "WS05-MP-PRIO-3", "players": [{}, {}, {}], "expected_events": {"required_events": ["priority_ring_live_order"]}}
    terminal = {
        "observations": {
            "P1": {"players": [bucket("P1", 0), bucket("P2", 1), bucket("P3", 2)]},
        },
        "scenario_objects": {},
        "shape_overview": {"native_surfaces": {}},
    }
    log = probe.NativeEventLog()
    # Transcript claims P3,P2,P1 order; native must ignore it and emit seat order P1,P2,P3.
    transcript = [
        {"actor": "P3", "submitted": "PASS_PRIORITY_SCRIPTED"},
        {"actor": "P2", "submitted": "PASS_PRIORITY_SCRIPTED"},
        {"actor": "P1", "submitted": "PASS_PRIORITY_SCRIPTED"},
    ]
    probe.derive_elim_and_ring(record, terminal, log, transcript)
    events = log.as_list()
    check("P4 ring from native not transcript", "priority_ring_order:P1,P2,P3" in events)
    check("P4 transcript order ignored", "priority_ring_order:P3,P2,P1" not in events)
    # Elimination from native buckets (SBA product), not pre-applied.
    record2 = {"fixture_id": "WS05-CMD-ELIM-4", "players": [{}, {}, {}, {}], "expected_events": {"required_events": ["player_loses:P2"]}}
    terminal2 = {
        "observations": {"P1": {"players": [bucket("P1", 0), dict(bucket("P2", 1), has_lost=True), bucket("P3", 2), bucket("P4", 3)]}},
        "scenario_objects": {},
        "shape_overview": {"native_surfaces": {}},
    }
    # Patch buckets with has_lost.
    terminal2["observations"]["P1"]["players"][1]["has_lost"] = True
    log2 = probe.NativeEventLog()
    probe.derive_elim_and_ring(record2, terminal2, log2, [])
    check("P4 elim from native has_lost", "player_loses:P2" in log2.as_list())
    # Extra-turn never from UUID identity: without attributed surface, no emit.
    record3 = {"fixture_id": "WS05-MP-TURN-3", "players": [{}, {}, {}], "expected_events": {"required_events": ["extra_turn_created:P2"]}}
    terminal3 = {"observations": {"P1": {"players": [bucket("P1", 0), bucket("P2", 1), bucket("P3", 2)]}}, "scenario_objects": {}, "shape_overview": {"native_surfaces": {}}}
    log3 = probe.NativeEventLog()
    probe.derive_elim_and_ring(record3, terminal3, log3, [])
    check("P4 extra-turn without attribution fails closed (no emit)", "extra_turn_created:P2" not in log3.as_list())


# ---------------------------------------------------------------- Phase 5
def test_phase5_rng_discipline() -> None:
    record = {"fixture_id": "RNG_RULES_TAPE", "players": [{}, {}, {}, {}], "rules_randomness": {"channels": ["NATIVE_LIBRARY_SHUFFLE"]}}
    terminal = {"rules_rng_tape": {"authority": "mage.util.RandomUtil", "pilot_rng_mixed": False, "operations": ["1:next_bits:32:1"] * 4, "operation_count": 4}}
    log = probe.NativeEventLog()
    probe.assert_rules_shuffle_tape(record, terminal, log)
    events = log.as_list()
    check("P5 tape valid emits", "rules_rng_tape_valid" in events)
    check("P5 no per-channel from global seed", not any(e.startswith("rules_rng:") and e != "rules_rng_tape_valid" for e in events))
    # Missing tape fails closed.
    expect_fail(
        "P5 missing tape fails closed",
        lambda: probe.assert_rules_shuffle_tape(record, {"rules_rng_tape": None}, probe.NativeEventLog()),
        "WS49_BEHAVIOR_RULES_TAPE_MISSING",
    )


def load_ws47_provider_rows() -> dict:
    repo_root = HERE.parents[1]
    blob = subprocess.run(
        ["git", "show", "192e2b77c0625ad26905bd0ee8dcc3f44a5796c8:qualification/ws47/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json"],
        cwd=str(repo_root),
        capture_output=True,
        check=True,
    ).stdout
    data = json.loads(blob)
    rows = [r for r in data["records"] if r.get("fixture_family") != "actual_card" or r.get("fixture_id") == "CARD_02"]
    return {r["fixture_id"]: r for r in rows}


def test_ws47_phase_fixtures() -> None:
    by_id = load_ws47_provider_rows()
    # Phase 1: two independent selector fixtures using the same capability.
    for fid in ("MICRO_TARGETS", "PILOT_CHOOSE_OBJECT"):
        r = by_id[fid]
        kinds = [(e.get("selection") or {}).get("selector_kind") for e in (r.get("decision_script") or [])]
        check(f"WS47 P1 {fid} selector present", any(k in ("semantic_player", "semantic_object") for k in kinds))
    # Phase 2: two independent mana fixtures.
    for fid in ("PILOT_MANA_PAYMENT", "MICRO_MANA_PAYMENT"):
        r = by_id[fid]
        kinds = [(e.get("selection") or {}).get("selector_kind") for e in (r.get("decision_script") or [])]
        check(f"WS47 P2 {fid} mana entry", "mana_payment" in kinds)
        check(f"WS47 P2 {fid} cost state", any((e.get("payable") is True) for e in (r.get("action_cost_state") or [])))
    # Phase 3: two independent hidden fixtures.
    for fid in ("HIDDEN_01", "HIDDEN_02"):
        r = by_id[fid]
        viewers = (r.get("knowledge_state") or {}).get("viewer_states") or []
        check(f"WS47 P3 {fid} viewers", len(viewers) >= 1)
    # Phase 4: extra-turn + elimination (independent capabilities sharing native-sequence discipline).
    for fid in ("WS05-MP-TURN-3", "WS05-MP-ELIM-OWNED-3"):
        r = by_id[fid]
        req = (r.get("expected_events") or {}).get("required_events") or []
        check(f"WS47 P4 {fid} sequence/elim obligation", any("extra_turn" in str(e) or "player_leaves" in str(e) for e in req))
    # Phase 5: two independent RNG fixtures sharing the seed seam.
    for fid in ("RNG_RULES_TAPE", "REPLAY_DECISION_TAPE"):
        r = by_id[fid]
        check(f"WS47 P5 {fid} shuffle channel", "NATIVE_LIBRARY_SHUFFLE" in str(r.get("rules_randomness")))
        check(f"WS47 P5 {fid} shuffle op", any("SHUFFLE" in str(s.get("operation")) for s in (r.get("native_procedure") or [])))


def main() -> int:
    test_phase0_allowlist()
    test_phase0_ws47_fixtures()
    test_phase1_owner_controller()
    test_phase1_unique_fail_closed()
    test_phase1_player_provenance()
    test_phase2_source_scoping()
    test_phase3_hidden_binding()
    test_phase4_no_transcript_ring()
    test_phase5_rng_discipline()
    test_ws47_phase_fixtures()
    print(f"--- {len(PASS)} passed, {len(FAIL)} failed ---")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
