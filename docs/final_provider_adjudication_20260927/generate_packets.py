#!/usr/bin/env python3
"""FINAL-PROVIDER-CDQ-20260927 deterministic packet generator.

Reads Lab source truth (no engine execution, no network) and emits:
  XMAGE_FULL107_REFRESH.json
  COMMON_FIXTURE_NORMALIZATION.json
  TARGETED_RUNTIME_RESULTS.json
  DIVERGENCE_PACKET.json
  PROVIDER_READINESS_PACKET.json

Run from the repository root:
  python3 docs/final_provider_adjudication_20260927/generate_packets.py

All promotions follow the exact-obligation rule: DIRECTLY_VERIFIED /
TECHNICALLY_CONFORMANT only on exact fixture-obligation match. Nothing here
executes an engine or fabricates Forge evidence.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent

FROZEN_SOURCE = "5a2e4f462fd45bba25f2271153212aab9faf09f5"
MATERIALIZATION = "commander-lab.semantic-fixture-materialization/1.0.5"
LAB_HEAD = "58e8fca430651207a87a8f3e9f41d8c6527dd4cd"
XMAGE_CANDIDATE = "b19596980f2734496ea1896504253e1bdd2756dd"
XMAGE_RUNTIME = "593326713faeddb8c90df2fdc5e5bafbe1fccf1b"
FORGE_CANDIDATE = "ef958ee91ac6c9ce0152189f2654bf6e05abf273"
FORGE_WSR20 = "18bba95a4528f6ab5910633f1f87f603b8c4ddf8"

# Coordinator-listed Forge residual seams (§14): excluded from the 101 common
# set; preserved explicitly, never fixed here.
SEAMS = {
    "HIDDEN_05": "UNKNOWN",
    "HIDDEN_06": "UNKNOWN",
    "HIDDEN_11": "UNKNOWN",
    "HIDDEN_08": "NOT_RUN_BLOCKED",
    "HIDDEN_12": "NOT_RUN_BLOCKED",
    "WS05-CMD-MULL-2": "NOT_RUN_BLOCKED",
}

SEAM_REASONS = {
    "HIDDEN_05": "face-down exile permission persistence",
    "HIDDEN_06": "face-down exile invalidation on zone change",
    "HIDDEN_11": "shuffle/order-knowledge invalidation",
    "HIDDEN_08": "look-audience seam",
    "HIDDEN_12": "controlled-player decision seam",
    "WS05-CMD-MULL-2": "London bottom-card choice seam",
}

NON_COMPARABLE_FIELDS = [
    "UUIDs",
    "object IDs",
    "revision counters",
    "internal option IDs",
    "engine-specific event IDs",
    "internal serialization details",
]

L_LAYER = {
    "L2_commander_damage": "8/8 CommanderDamage suite (20-vs-21 SBA loss, per-commander/Partner independence, 3P/4P/5P, MDFC binding, decoy-copy isolation, fresh-session reproducibility); native CommanderInfoWatcher.restoreDamageStateForGameLoad only",
    "L3_temporal": "7/7 basic + 6/6 advanced temporal progression (upkeep/draw/precombat/combat/postcombat checkpoints, real attack/block flow, skip-combat via real effect, extra-turn ordering, simultaneous beginning-trigger ordering); fail-closed unscripted targets",
    "L4_stack": "5/5 reconstruction + 7/7 mechanics (Lightning Bolt 3P/4P/5P, modal Burn Down the House, nested Counterspell, activated/triggered/copy incl. Flare of Duplication, Morph face-down, fizzle, counter, leaver cleanup); same-seed replay",
    "L5_control": "7/7 control divergence (Control Magic persistent + controller-leaves cleanup, owner-leaves-while-controlled, Act of Treason EOT expiry, overlapping timestamps, Switcheroo exchange, stolen genuine Commander, Unsummon zone-change cleanup)",
    "L6_elimination": "21/21 elimination (14 live causal cells: lethal, Commander damage, active-player loss, winner/draw, cleanup, priority-ring/turn recomputation at 2P/3P/4P/5P + 7 discard-authority adversarial unit tests); poison/deck-out causation retained UNKNOWN; no Lab lost/left/winner mutation",
    "L7_hidden_replay": "9/9 hidden/replay (lossless complete-library restore, typed single face-down restore, controller-only private visibility, opponent/global non-oracle proofs, public/private hash separation, transcript hygiene, same-seed public semantic replay); 6-path prevalidation atomicity battery (zero-mutation rejects)",
    "replay_4p": "4P seeded semantic replay, 4476 decisions, semantic match true (reconciled bytes)",
    "lanes": "bounded live 2P/3P/5P/6P PASS; 7P FAIL_CLOSED; Real 4P technical smoke PASS; H4 XMage/Forge materialization PASS",
}


def load_json(rel):
    with open(REPO / rel, encoding="utf-8") as fh:
        return json.load(fh)


def norm(status):
    return {"DIRECT": "DIRECTLY_VERIFIED"}.get(status, status)


def later_evidence_note(fid, cat, old):
    """Why post-mapping L1-L7 evidence does or does not satisfy the frozen
    fixture obligation. Conservative: mechanism/family/lane evidence never
    promotes to fixture-exact credit."""
    if old == "DIRECT":
        return (
            "Retained: fixture-corresponding run with EXACT identity-register "
            "verdict and constructed requested_state_digest equality; later "
            "L1-L7 work adds corroborating mechanism coverage but is not "
            "needed for this row."
        )
    if old == "NOT_RUN_BLOCKED":
        return (
            "Retained blocked: bridge reports "
            "starting_state_injection_supported=false (contract-locked). Later "
            "L1-L7 causal reconstruction uses genuine transactions plus bounded "
            "initial configuration, not the generic starting-state injection "
            "this frozen fixture requires; no injection capability was added."
        )
    if cat == "player_count":
        return (
            "Retained SUPPORTING: per-count live lanes (Isamaru+Plains technical "
            "decks at cardinality seeds, PASS, replay MATCH) plus cumulative "
            "%s and %s do not rerun the bound Rograkh+Mountain/seed-424242 "
            "fixture and assert none of its required events." % (L_LAYER["lanes"], L_LAYER["replay_4p"])
        )
    if fid in ("PILOT_CHOICE", "PILOT_PILE", "PILOT_ANNOUNCE_X",
               "PILOT_MULTI_AMOUNT", "PILOT_CHOOSE_ABILITY"):
        return (
            "Retained UNKNOWN: decision family never observed in sealed live "
            "gates and no fixture-corresponding live run exists; no L1-L7 suite "
            "exercises this exact family against this fixture's obligation "
            "(nearest suites: %s; %s)." % (L_LAYER["L4_stack"], L_LAYER["L3_temporal"])
        )
    if fid == "PILOT_TRIGGER_ORDER":
        return (
            "Retained UNKNOWN: L3 orders simultaneous beginning triggers "
            "(Phyrexian Arena + Mystic Remora via trigger_order) and TRIG-3/5 "
            "prove Soul Warden APNAP at 3P/5P, but neither is a "
            "fixture-corresponding 4P/seed-424242 run with this fixture's "
            "required events and digest equality."
        )
    if fid == "PILOT_REPLACEMENT_EFFECT":
        return (
            "Retained UNKNOWN: RG-08 replacement-timing qualification is "
            "candidate-level (engine pin), and L5/L6 use native cleanup paths, "
            "but no fixture-corresponding run with digest equality exists for "
            "this exact replacement-effect obligation."
        )
    if fid.startswith("PILOT_"):
        return (
            "Retained SUPPORTING: projection unit coverage plus live-observed "
            "class in 2/3/4/5P gates; adjacent L-layer mechanism suites prove "
            "neighboring families at other decks/scopes, not this fixture's "
            "exact obligation with required events and digest."
        )
    if fid.startswith("NEGATIVE_"):
        return (
            "Retained UNKNOWN: no dedicated live fixture rerun for this "
            "prohibited shortcut. Adjacent negative evidence (L6 7 adversarial "
            "discard-authority unit tests; L7 6-path prevalidation atomicity "
            "battery with zero-mutation asserts; invalid-payload and "
            "stale-decision rejection) targets different obligations and "
            "cannot be transferred."
        )
    if fid.startswith("HIDDEN_"):
        return (
            "Retained UNKNOWN: L7 qualifies principal-scoped hiding generically "
            "(%s) plus HIDDEN_INFORMATION_BOUNDARY_REPORT, but no per-scenario "
            "exact rerun exists for this fixture's actor/principal, zone "
            "movement, invalidation, and replay-boundary semantics." % L_LAYER["L7_hidden_replay"]
        )
    if fid.startswith("RNG_") or fid.startswith("REPLAY_"):
        return (
            "Retained UNKNOWN: %s and per-count replay MATCH in sealed gates "
            "are other-scope evidence; no N-scoped replay-match rerun exists "
            "for this fixture's tape/operation scope." % L_LAYER["replay_4p"]
        )
    micro = {
        "MICRO_COSTS": "TAX-2/4 prove engine-owned {4} commander-tax payment (commander-tax scope), not general costs",
        "MICRO_MANA_PAYMENT": "same tax-payment pipeline evidence is commander-tax scope, not the general mana-payment obligation",
        "MICRO_PRIORITY": "L3 temporal checkpoints prove progression mechanics, not this fixture's exact priority obligation with digest",
        "MICRO_STACK": "L4 reconstruction/mechanics prove stack mechanics at other decks/scopes, not this 4P fixture obligation with digest",
        "MICRO_MODES": "PILOT_CHOOSE_MODE proves Devil-mode selection in PILOT scope, not this MICRO obligation",
        "MICRO_TRIGGERS": "TRIG-3/5 prove Soul Warden APNAP at 3P/5P, not this 4P MICRO obligation with digest",
        "MICRO_REPLACEMENT": "RG-08 is candidate-level; no fixture-corresponding digest run for this obligation",
        "MICRO_PREVENTION": "no exact prevention-mechanism run against this fixture obligation",
        "MICRO_CONTINUOUS_EFFECTS": "Humility/Glorious Anthem/Bears native facts are LAYERS-scope evidence, not this obligation",
        "MICRO_STATE_BASED_ACTIONS": "20/21 loss and zone-choice characterization are other-scope, not this 4P obligation with digest",
        "MICRO_ZONE_CHANGES": "Unsummon/control-leaves zone cleanup is other-scope, not this obligation with digest",
        "MICRO_COPY": "Flare of Duplication mechanics are other-scope, not this obligation with digest",
        "MICRO_CONTROL": "L5 7/7 divergence suite proves control mechanics under other fixtures' obligations, not this one",
        "MICRO_COMBAT": "real attack/block flow, skip-combat and extra-turn are temporal-scope, not this obligation with digest",
        "MICRO_RULES_RANDOMNESS": "seed binding plus replay MATCH are other-scope, not this obligation with digest",
    }
    if fid in micro:
        return "Retained UNKNOWN: %s." % micro[fid]
    return "Retained %s: no later evidence exactly satisfies the frozen obligation." % old


def runtime_identity_for(entry):
    fid = entry["fixture_id"]
    if fid in ("WS05-CMD-DMG-SPLIT", "WS05-CMD-PARTNER-DMG", "WS05-CMD-START-3"):
        return XMAGE_RUNTIME + " (requalified on reconciled bytes; 3/3 green)"
    if entry["status"] == "DIRECT":
        return (
            "original qualification pre-reconciliation (DR-CLOSURE-01 / PR "
            "#213/#220/#224/#231 lineage); retained-valid on current main via "
            "merged-main Conformance SUCCESS and exact-main gate SUCCESS on "
            + LAB_HEAD[:8] + " (see impact adjudication)"
        )
    return "n/a (no runtime credit claimed)"


def impact_for(entry):
    if entry["status"] == "DIRECT":
        return (
            "Publisher reintegration (PR #253 safe_push effective-target "
            "hardening) is Lab orchestration push-target identity only; it "
            "touches no XMage engine bytes, bridge Rules path, fixture decks, "
            "seeds, or digest computation. Exact-main workflows on "
            + LAB_HEAD[:8] + " (CI/Production Qualification/Exact Main "
            "Recovery/Windows Hygiene/Release Artifacts, all SUCCESS) plus "
            "merged-main Conformance SUCCESS show no semantic delta to "
            "credited engine behavior. Promotion state preserved, not "
            "re-derived from the publisher change."
        )
    return "none (no disposition change; no credit transferred)"


def build_refresh(mapping, verdicts):
    verdict_by_fid = {v["fixture_id"]: v for v in verdicts}
    rows = []
    for e in mapping["entries"]:
        fid = e["fixture_id"]
        old = e["status"]
        new = old  # Gate B outcome: zero promotions warranted (see notes)
        rows.append({
            "fixture_id": fid,
            "old_status": norm(old),
            "new_status": norm(new),
            "changed": False,
            "exact_evidence_pointer": e.get("pointer"),
            "identity_register_verdict": (verdict_by_fid.get(fid) or {}).get("verdict"),
            "why_promotion_is_valid_or_why_retained": later_evidence_note(
                fid, manifest_cat.get(fid, ""), old),
            "mapping_reason_preserved": e.get("reason"),
            "runtime_identity": runtime_identity_for(e),
            "impact_adjudication": impact_for(e),
        })
    counts_old = mapping["counts"]
    counts_new = {"DIRECTLY_VERIFIED": 0, "TECHNICALLY_CONFORMANT": 0,
                  "SUPPORTING": 0, "CODE_DERIVED": 0,
                  "EXTERNALLY_RULE_VALIDATED": 0, "UNKNOWN": 0,
                  "NOT_RUN_BLOCKED": 0}
    for r in rows:
        counts_new[r["new_status"]] += 1
    return {
        "schema_version": "final-provider-xmage-refresh-1.0.0",
        "denominator_identity": {
            "frozen_source": FROZEN_SOURCE,
            "materialization": MATERIALIZATION,
            "total_items": 107,
        },
        "mapping_provenance": {
            "mapping_counts": counts_old,
            "mapping_entries": len(rows),
        },
        "xmage_identities": {
            "engine_candidate": XMAGE_CANDIDATE,
            "lab_runtime_authority": XMAGE_RUNTIME,
        },
        "promotion_rule": (
            "DIRECTLY_VERIFIED/TECHNICALLY_CONFORMANT only on exact "
            "obligation match across behavior, card/scenario semantics, player "
            "count, decision class, visibility, principal, RNG, replay, state "
            "transition, runtime identity, and absence of prohibited fallback. "
            "No CODE_DERIVED to runtime PASS; no construction to behavior; no "
            "family to exact fixture; no 4P to 5P; no similarity to DIRECT."
        ),
        "result_counts": counts_new,
        "promotions_applied": 0,
        "rows": rows,
    }


def build_normalization(refresh, manifest_records):
    by_fid = {r["fixture_id"]: r for r in refresh["rows"]}
    man_by_fid = {m["fixture_id"]: m for m in manifest_records}
    excluded = sorted(SEAMS)
    common_ids = [fid for fid in by_fid if fid not in SEAMS]
    assert len(by_fid) == 107, len(by_fid)
    assert len(common_ids) == 101, len(common_ids)
    fixtures = []
    for fid in sorted(common_ids):
        xr = by_fid[fid]
        man = man_by_fid.get(fid, {})
        cat = man.get("category", manifest_cat.get(fid, ""))
        fixtures.append({
            "fixture_id": fid,
            "denominator_identity": {
                "frozen_source": FROZEN_SOURCE,
                "materialization": MATERIALIZATION,
            },
            "player_count": man.get("player_count"),
            "category": cat,
            "description": man.get("description"),
            "decision_families": [cat] if cat else [],
            "externally_supplied_discretionary_decisions": (
                "fixture-scoped discretionary selections only; harness supplies "
                "no Rules outcomes"
            ),
            "seed_request": man.get("seed", 424242),
            "seed_truthfully_comparable": (
                "UNKNOWN: cross-engine Rules-RNG binding parity requires the "
                "WSR20 RNG packet, which is absent from Lab source truth; no "
                "parity asserted"
            ),
            "public_state": "denominator-defined public facts only (counts, zones, phases as applicable)",
            "principal_observations": "principal-scoped; exact per-fixture visibility requires both engines' redaction evidence",
            "semantic_events": "denominator-required events; engine observation requires packet ingest",
            "rng_operations": "Rules-owned; binding parity unproven cross-engine",
            "terminal_facts": "denominator terminal postconditions",
            "engine_local_non_comparable_fields": NON_COMPARABLE_FIELDS,
            "xmage_evidence": {
                "status": xr["new_status"],
                "pointer": xr["exact_evidence_pointer"],
                "runtime_identity": xr["runtime_identity"],
            },
            "forge_evidence": {
                "status": "UNKNOWN",
                "pointer": None,
                "reason": (
                    "WSR20 packet (FULL107_FORGE_MAPPING.json and companions) "
                    "absent from Lab source truth in this worktree; claimed "
                    "WSR20 counts (84/17/3/3/0) recorded as CONTRACT_CLAIMED, "
                    "never as verified evidence."
                ),
            },
            "comparison_disposition": "NON_COMPARABLE",
            "comparison_reason": (
                "Cross-engine semantic comparison requires both engines' "
                "fixture-corresponding evidence; Forge side is absent locally, "
                "so no SAME_SEMANTICS, ENGINE_CAPABILITY_GAP, or "
                "UNKNOWN_PENDING_RULES_ADJUDICATION is assertable for this "
                "fixture. Pending WSR20 packet ingest (outcome B)."
            ),
        })
    counts = {"SAME_SEMANTICS": 0, "NON_COMPARABLE": 0,
              "ENGINE_CAPABILITY_GAP": 0,
              "UNKNOWN_PENDING_RULES_ADJUDICATION": 0}
    for f in fixtures:
        counts[f["comparison_disposition"]] += 1
    return {
        "schema_version": "final-provider-common-normalization-1.0.0",
        "denominator_identity": {
            "frozen_source": FROZEN_SOURCE,
            "materialization": MATERIALIZATION,
        },
        "derivation": (
            "Common set = 107-item denominator minus the 6 Coordinator-listed "
            "Forge residual seams (HIDDEN_05, HIDDEN_06, HIDDEN_11, HIDDEN_08, "
            "HIDDEN_12, WS05-CMD-MULL-2). The WSR20 "
            "COMMON_FIXTURE_SUCCESSOR_PACKET.json starting point is absent "
            "from Lab source truth, so the set is derived transparently here "
            "instead of regenerated opaquely."
        ),
        "excluded_seams": [
            {"fixture_id": fid, "forge_contract_status": SEAMS[fid],
             "reason": SEAM_REASONS[fid],
             "note": "preserved explicitly per §14; remediation not authorized here"}
            for fid in excluded
        ],
        "meaningless_byte_equality_excluded": NON_COMPARABLE_FIELDS,
        "ranking_disclaimer": (
            "No provider ranking of any kind is output anywhere in this "
            "packet: no winner, no preferred provider, no better-engine claim, "
            "and no disguised equivalent."
        ),
        "comparison_counts": counts,
        "fixture_count": len(fixtures),
        "fixtures": fixtures,
    }


GAP_PRIORITIES = [
    ("rules_authority", ["PILOT_CHOICE", "PILOT_PILE", "PILOT_ANNOUNCE_X",
                         "PILOT_MULTI_AMOUNT", "PILOT_REPLACEMENT_EFFECT",
                         "PILOT_TRIGGER_ORDER", "PILOT_CHOOSE_ABILITY"]),
    ("forbidden_fallback", ["NEGATIVE_FIRST_OPTION", "NEGATIVE_RANDOM_OPTION",
                            "NEGATIVE_DEFAULT_YES_NO", "NEGATIVE_INTERNAL_AI",
                            "NEGATIVE_GUI_DEFAULT", "NEGATIVE_SILENT_SKIP",
                            "NEGATIVE_PARENT_CLASS_FALLBACK"]),
    ("hidden_information", ["HIDDEN_01", "HIDDEN_02", "HIDDEN_03", "HIDDEN_04",
                            "HIDDEN_07", "HIDDEN_09", "HIDDEN_10", "HIDDEN_13",
                            "HIDDEN_14", "HIDDEN_15", "HIDDEN_16", "HIDDEN_17",
                            "HIDDEN_18", "HIDDEN_19",
                            "HIDDEN_HONEYCARD_SENTINEL"]),
    ("rng_replay", ["RNG_RULES_TAPE", "REPLAY_DECISION_TAPE",
                    "REPLAY_EVENT_TAPE", "REPLAY_CLEAN_PROCESS",
                    "REPLAY_STATE_HASHES"]),
    ("costs_mana_targets_modes", ["MICRO_COSTS", "MICRO_MANA_PAYMENT",
                                  "MICRO_MODES"]),
    ("priority_stack", ["MICRO_PRIORITY", "MICRO_STACK"]),
    ("triggers", ["MICRO_TRIGGERS"]),
    ("replacement_prevention", ["MICRO_REPLACEMENT", "MICRO_PREVENTION"]),
    ("layers_continuous", ["MICRO_CONTINUOUS_EFFECTS"]),
    ("sbas", ["MICRO_STATE_BASED_ACTIONS"]),
    ("zones_copy_control", ["MICRO_ZONE_CHANGES", "MICRO_COPY",
                            "MICRO_CONTROL"]),
    ("combat", ["MICRO_COMBAT"]),
    ("commander_blocked", ["WS05-CMD-ZONE-GY-YES", "WS05-CMD-ZONE-GY-NO",
                           "WS05-CMD-ZONE-EXILE-YES",
                           "WS05-CMD-ZONE-EXILE-NO",
                           "WS05-CMD-ZONE-HAND-YES", "WS05-CMD-ZONE-HAND-NO",
                           "WS05-CMD-ZONE-LIB-YES", "WS05-CMD-ZONE-LIB-NO",
                           "WS05-CMD-DMG-SAME-21", "WS05-CMD-DMG-CONTROL",
                           "WS05-CMD-START-2", "WS05-CMD-ELIM-4"]),
    ("multiplayer_blocked", ["WS05-MP-PRIO-3", "WS05-MP-PRIO-5",
                             "WS05-MP-COMBAT-4", "WS05-MP-COMBAT-5",
                             "WS05-MP-BLOCK-4", "WS05-MP-TURN-3",
                             "WS05-MP-TURN-5", "WS05-MP-ELIM-OWNED-3",
                             "WS05-MP-ELIM-CONTROL-3",
                             "WS05-MP-ELIM-STACK-3", "WS05-MP-ELIM-PRIO-3",
                             "WS05-MP-ELIM-TURN-3", "WS05-MP-ELIM-5"]),
]


def build_targeted(refresh):
    by_fid = {r["fixture_id"]: r for r in refresh["rows"]}
    gaps = [{
        "rank": 0,
        "priority_dimension": "forge_packet_ingest (blocking all cross-engine comparison)",
        "fixture_ids": ["ALL-101-COMMON"],
        "what_missing": "WSR20 packet ingest into Lab source truth",
        "why_decision_critical": "Every Gate C comparison is NON_COMPARABLE without the Forge side; no divergence or gap can be adjudicated.",
        "proposed_minimal_runtime": "Ingest-only workstream: verify WSR20 tip bytes, import the 8 packet files with source lock, reconcile counts, then run Gate D matrix below.",
        "player_counts": [4],
        "seed": 424242,
    }]
    for i, (dim, fids) in enumerate(GAP_PRIORITIES, start=1):
        present = [f for f in fids if f in by_fid]
        gaps.append({
            "rank": i,
            "priority_dimension": dim,
            "fixture_ids": present,
            "what_missing": "fixture-corresponding runtime with digest equality (XMage) + Forge counterpart (WSR20 ingest)",
            "why_decision_critical": "per §10 priority order",
            "proposed_minimal_runtime": (
                "4P primary at seed 424242 with same decks/cards, same "
                "requested seed where both engines expose a real Rules-RNG "
                "binding, same externally supplied discretionary choices, same "
                "semantic stopping condition; 2P/3P/5P conformance for "
                "promoted rows; bounded 6P secondary; 7P explicit FAIL_CLOSED. "
                "No manual outcome injection; no harness Rules engine."
            ),
            "player_counts": sorted({man_counts.get(f, 4) for f in present}),
            "seed": 424242,
        })
    return {
        "schema_version": "final-provider-targeted-runtime-1.0.0",
        "methodology": (
            "Reuse-first: no already-valid evidence rerun. Gaps ordered per "
            "§10 (Rules-authority surfaces first). 4P primary; 2-5P technical "
            "conformance; bounded 6P secondary; 7P FAIL_CLOSED acceptable."
        ),
        "engine_executions_performed_in_this_worktree": [],
        "engine_execution_note": (
            "No new engine execution performed here: XMage credited rows are "
            "already qualified (Gate B) and rerunning them would violate "
            "reuse-first; missing rows and all Forge rows require the WSR20 "
            "ingest plus engine builds outside this worktree's declared "
            "reference scope. Local validation executed instead: packet "
            "schema/count reconciliation, correspondence guard, and the new "
            "packet-validation test (see VALIDATION.md)."
        ),
        "comparison_rule": (
            "Same player count, same deck/card identities where possible, same "
            "requested seed where both engines expose a real Rules-RNG "
            "binding, same externally supplied discretionary choices, same "
            "semantic stopping condition. Never fake RNG parity or inject "
            "expected outcomes; never use a harness as a second Rules engine."
        ),
        "gaps": gaps,
    }


def build_divergence():
    return {
        "schema_version": "final-provider-divergence-1.0.0",
        "note": (
            "No XMage-vs-Forge Rules-visible behavioral delta is proven in Lab "
            "source truth: the Forge comparison side is absent (WSR20 packet "
            "not ingested), so no divergence is assertable and none is "
            "fabricated. This packet stays compact and empty by evidence, not "
            "by assumption."
        ),
        "divergences": [],
        "divergence_count": 0,
    }


READINESS_DIMS = [
    ("rules_authority_separation", "SUPPORTING", "UNKNOWN",
     ["engine-bridge decision controller + redactor + prevalidation battery (L7)", "B4-D legal-action handoff surface"],
     "Forge side requires WSR20 ingest; no Lab Forge authority evidence beyond H4 materialization."),
    ("legal_action_completeness", "SUPPORTING", "UNKNOWN",
     ["bounded current-priority enumeration (B4-D)", "projection coverage + live-observed classes"],
     "Globally complete enumeration unproven on both sides in Lab truth."),
    ("action_submission_completeness", "SUPPORTING", "UNKNOWN",
     ["bounded targetless/nonmodal submission + Rograkh cast (B4-D)", "stale-decision rejection"],
     "Target/mode/choice/combat submission classes incomplete per manifest truth_boundary."),
    ("costs", "SUPPORTING", "UNKNOWN",
     ["WS05-CMD-TAX-2/4 DIRECT (engine-owned {4} tax payment)", "per-commander tax figures (Partner)"],
     None),
    ("mana", "SUPPORTING", "UNKNOWN",
     ["engine-owned payment pipeline via TAX fixtures", "live-observed mana_payment class"],
     None),
    ("priority", "SUPPORTING", "UNKNOWN",
     ["L3 temporal driver checkpoints", "live-observed priority class 2-5P"],
     None),
    ("stack", "TECHNICALLY_CONFORMANT", "UNKNOWN",
     ["L4 5/5 reconstruction + 7/7 mechanics (Bolt/modal/nested/counter/fizzle)", "MICRO_TARGETS DIRECT"],
     None),
    ("targets", "TECHNICALLY_CONFORMANT", "UNKNOWN",
     ["MICRO_TARGETS DIRECT (exact P2 target, 3 damage)", "RG-07 exact-N offering (candidate)", "Switcheroo 2-target exchange (L5)"],
     None),
    ("modes", "TECHNICALLY_CONFORMANT", "UNKNOWN",
     ["PILOT_CHOOSE_MODE DIRECT (two-mode Devil selection)"],
     None),
    ("choices", "SUPPORTING", "UNKNOWN",
     ["live-observed choose_object/choose_use classes", "MICRO_MODES fixture UNKNOWN"],
     None),
    ("triggers", "TECHNICALLY_CONFORMANT", "UNKNOWN",
     ["WS05-MP-TRIG-3/5 DIRECT (Soul Warden APNAP)", "L3 simultaneous-trigger ordering"],
     None),
    ("replacement_effects", "SUPPORTING", "UNKNOWN",
     ["RG-08 replacement timing (candidate-level)", "native cleanup paths (L5/L6)"],
     "No fixture-corresponding digest run on either side in Lab truth."),
    ("prevention_effects", "UNKNOWN", "UNKNOWN",
     ["none exact in Lab truth"],
     "MICRO_PREVENTION UNKNOWN both sides (Forge side absent)."),
    ("continuous_effects", "SUPPORTING", "UNKNOWN",
     ["Humility/Anthem/Bears native layer facts (LAYERS scope)", "overlapping Control Magic timestamps (L5)"],
     None),
    ("layers", "TECHNICALLY_CONFORMANT", "UNKNOWN",
     ["MICRO_LAYERS DIRECT (layer 6/7b/7c native facts)"],
     None),
    ("sbas", "SUPPORTING", "UNKNOWN",
     ["20-vs-21 SBA loss (L2)", "command-zone choice characterization (blocked fixtures)"],
     None),
    ("zones", "SUPPORTING", "UNKNOWN",
     ["Unsummon/control-leaves zone cleanup (L5)", "zone-choice seams blocked (injection)"],
     None),
    ("copy", "SUPPORTING", "UNKNOWN",
     ["Flare of Duplication mechanics (L4)", "decoy-copy isolation (L2)"],
     None),
    ("control", "TECHNICALLY_CONFORMANT", "UNKNOWN",
     ["L5 7/7 divergence suite", "WS05-CMD-DMG-CONTROL blocked (injection)"],
     None),
    ("combat", "SUPPORTING", "UNKNOWN",
     ["real attack/block flow + skip-combat + extra-turn (L3)", "combat-damage test surface"],
     "MICRO_COMBAT + MP combat/block fixtures need exact runs."),
    ("commander_tax", "DIRECT", "UNKNOWN",
     ["WS05-CMD-TAX-2/4 DIRECT", "WS05-CMD-PARTNER-TAX DIRECT (per-commander figures)"],
     None),
    ("commander_zone_replacement", "SUPPORTING", "UNKNOWN",
     ["native replacement paths (L5/L6)", "8 zone-choice fixtures NOT_RUN_BLOCKED (injection)"],
     None),
    ("commander_damage", "DIRECT", "UNKNOWN",
     ["WS05-CMD-DMG-SPLIT + WS05-CMD-PARTNER-DMG DIRECT (independent edges, no aggregation)", "L2 8/8 suite incl. 20/21"],
     None),
    ("partner", "DIRECT", "UNKNOWN",
     ["WS05-CMD-PARTNER-TAX/ZONE/DMG DIRECT", "Partner legality engine-proven at import"],
     None),
    ("mulligan", "DIRECT", "BLOCKED",
     ["WS05-CMD-MULL-2/4 DIRECT (XMage London counts 93/6, 92/7)"],
     "Forge WS05-CMD-MULL-2 contract-claimed NOT_RUN_BLOCKED (London bottom-card seam); remediation not authorized here."),
    ("starting_player_semantics", "TECHNICALLY_CONFORMANT", "UNKNOWN",
     ["WS05-CMD-START-3 DIRECT (3P first-turn draw 8/7/7)", "2P/3P/4P/5P lane gates"],
     "START-2 blocked (injection) + draw-assertion contradiction retained UNKNOWN."),
    ("player_count_2p", "SUPPORTING", "UNKNOWN",
     ["2P lane gate PASS + replay MATCH", "MULL-2/TAX-2 DIRECT", "L6 2P terminal cell"],
     "Exact Rograkh/424242 fixture reruns absent."),
    ("player_count_3p", "SUPPORTING", "UNKNOWN",
     ["3P lane gate PASS", "TRIG-3 + START-3 DIRECT", "L6 3P x8 cells"],
     "Exact fixture reruns absent for gates."),
    ("player_count_4p", "TECHNICALLY_CONFORMANT", "UNKNOWN",
     ["4P 4476-decision semantic replay MATCH", "11 DIRECT fixtures at 4P", "Real 4P smoke PASS"],
     None),
    ("player_count_5p", "SUPPORTING", "UNKNOWN",
     ["5P lane gate PASS", "TRIG-5 DIRECT", "L6 5P middle-seat cell"],
     None),
    ("bounded_6p", "SUPPORTING", "UNKNOWN",
     ["bounded 6P smoke PASS (general surface only, not mechanism-specific)"],
     "Per-handoff: no 6P mechanism-specific elimination claim."),
    ("fail_closed_7p", "TECHNICALLY_CONFORMANT", "UNKNOWN",
     ["7P explicit FAIL_CLOSED (reconciled bytes)"],
     "FAIL_CLOSED is the acceptable terminal per §10."),
    ("hidden_information", "TECHNICALLY_CONFORMANT", "UNKNOWN",
     ["L7 9/9 + boundary report + hash separation + transcript hygiene", "per-scenario exact reruns absent (Gate B)"],
     "Forge HIDDEN_05/06/11 UNKNOWN + HIDDEN_08/12 NOT_RUN_BLOCKED (contract-claimed seams); Forge H4 materialization is technical only."),
    ("rules_rng", "SUPPORTING", "UNKNOWN",
     ["Rules-seed binding + same-seed replay MATCH", "RNG tape unit suites"],
     "RNG_RULES_TAPE exact rerun absent; cross-engine binding parity unproven."),
    ("semantic_replay", "TECHNICALLY_CONFORMANT", "UNKNOWN",
     ["same-seed public semantic replay (4P 4476 MATCH; per-count MATCH)", "atomicity battery"],
     "N-scoped fixture replay reruns absent."),
    ("process_isolation", "SUPPORTING", "SUPPORTING",
     ["H4 XMage materialization PASS", "per-game lifecycle cleanup/reuse"],
     ["H4 Forge materialization PASS (technical only, artifacts 10907027320-era)"]),
    ("actual_card_runtime_coverage", "SUPPORTING", "UNKNOWN",
     ["16 named cards qualified across L2-L5 + real-deck E2E gate docs", "Rograkh cast to stack (B4-D)"],
     "Coverage is card-listed, not win-rate; broad card universe unproven."),
    ("unsupported_path_failure_behavior", "TECHNICALLY_CONFORMANT", "UNKNOWN",
     ["prevalidation zero-mutation rejects", "invalid-payload + stale-decision rejection", "7P FAIL_CLOSED", "incomplete-library fail-before-mutation"],
     None),
]


def build_readiness():
    dims = []
    for name, xs, fs, xpts, fnotes in READINESS_DIMS:
        fpts = ["WSR20 packet absent locally; claimed counts CONTRACT_CLAIMED only"]
        if isinstance(fnotes, list):
            fpts = fnotes + fpts
        elif isinstance(fnotes, str):
            fpts = [fnotes] + fpts
        dims.append({
            "dimension": name,
            "xmage": {"status": xs, "evidence_pointers": xpts,
                      "runtime_identity": XMAGE_RUNTIME if xs in ("DIRECT", "TECHNICALLY_CONFORMANT") else "mixed lane/mechanism heads (see Gate B rows)"},
            "forge": {"status": fs, "evidence_pointers": fpts,
                      "runtime_identity": FORGE_WSR20 + " (EVIDENCE_ONLY, packet absent locally)"},
        })
    return {
        "schema_version": "final-provider-readiness-1.0.0",
        "identities": {
            "lab_head": LAB_HEAD,
            "frozen_source": FROZEN_SOURCE,
            "xmage_candidate": XMAGE_CANDIDATE,
            "xmage_runtime_authority": XMAGE_RUNTIME,
            "forge_candidate": FORGE_CANDIDATE,
            "forge_wsr20_tip": FORGE_WSR20,
        },
        "scoring_disclaimer": (
            "No provider score, overall winner, or ranking is computed or "
            "implied. The Coordinator adjudicates from this evidence."
        ),
        "terminal_states": {
            "ARCHITECTURE_FREEZE": "NOT CLAIMED",
            "PRODUCTION_PROVIDER": "NOT SELECTED",
        },
        "dimensions": dims,
    }


def main():
    mapping = load_json("docs/workstream_full107_definition_20260921/FULL107_MAPPING.json")
    register = load_json("docs/workstream_full107_fixture_identity_20260922/FIXTURE_IDENTITY_REGISTER.json")
    manifest = load_json("qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json")
    denominator = load_json("qualification/ws47/WS47_PROVIDER_DENOMINATOR_107.json")

    global manifest_cat, man_counts
    manifest_cat = {m["fixture_id"]: m.get("category", "") for m in manifest["fixtures"]}
    man_counts = {m["fixture_id"]: m.get("player_count", 4) for m in manifest["fixtures"]}
    verdicts = register["verdicts"] if isinstance(register, dict) else register

    assert len(mapping["entries"]) == 107, len(mapping["entries"])
    assert len(denominator["fixture_ids"]) == 107
    assert {e["fixture_id"] for e in mapping["entries"]} == set(denominator["fixture_ids"]), "mapping/denominator mismatch"

    refresh = build_refresh(mapping, verdicts)
    normalization = build_normalization(refresh, manifest["fixtures"])
    targeted = build_targeted(refresh)
    divergence = build_divergence()
    readiness = build_readiness()

    outputs = {
        "XMAGE_FULL107_REFRESH.json": refresh,
        "COMMON_FIXTURE_NORMALIZATION.json": normalization,
        "TARGETED_RUNTIME_RESULTS.json": targeted,
        "DIVERGENCE_PACKET.json": divergence,
        "PROVIDER_READINESS_PACKET.json": readiness,
    }
    for name, obj in outputs.items():
        path = OUT / name
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=1)
            fh.write("\n")
        print("wrote %s (%d bytes)" % (path, path.stat().st_size))

    print("refresh counts:", refresh["result_counts"])
    print("comparison counts:", normalization["comparison_counts"])
    print("targeted gaps:", len(targeted["gaps"]))
    print("divergences:", divergence["divergence_count"])
    print("readiness dimensions:", len(readiness["dimensions"]))


if __name__ == "__main__":
    sys.exit(main())
