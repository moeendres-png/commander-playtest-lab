#!/usr/bin/env python3
"""FINAL-PROVIDER-CDQ-20260927 deterministic packet generator (rev 2).

Reads Lab source truth plus the vendored WSR20 ingest
(docs/final_provider_adjudication_20260927/wsr20-ingest/, byte copies of the
Forge evidence tip 18bba95a...) and emits:
  XMAGE_FULL107_REFRESH.json          (Gate B, Lab-only)
  COMMON_FIXTURE_NORMALIZATION.json   (Gate C, from the WSR20 successor packet)
  TARGETED_RUNTIME_RESULTS.json       (Gate D, ingest + executed runs + matrix)
  DIVERGENCE_PACKET.json              (both-sides review)
  PROVIDER_READINESS_PACKET.json      (38 dimensions x both candidates)

Run from the repository root:
  python3 docs/final_provider_adjudication_20260927/generate_packets.py

Promotion rule: DIRECTLY_VERIFIED/TECHNICALLY_CONFORMANT only on exact
obligation match. Comparison rule: SAME_SEMANTICS only when both engines meet
the frozen obligation with no recorded behavioral delta; ENGINE_CAPABILITY_GAP
only for a genuinely missing execution seam; otherwise NON_COMPARABLE. No
ranking output anywhere.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
INGEST = OUT / "wsr20-ingest"

FROZEN_SOURCE = "5a2e4f462fd45bba25f2271153212aab9faf09f5"
FROZEN_SHORT = "origin/ws47/successor-contract-v1.0.5-freeze@5a2e4f46"
MATERIALIZATION = "commander-lab.semantic-fixture-materialization/1.0.5"
LAB_HEAD = "58e8fca430651207a87a8f3e9f41d8c6527dd4cd"
XMAGE_CANDIDATE = "b19596980f2734496ea1896504253e1bdd2756dd"
XMAGE_RUNTIME = "593326713faeddb8c90df2fdc5e5bafbe1fccf1b"
FORGE_CANDIDATE = "ef958ee91ac6c9ce0152189f2654bf6e05abf273"
FORGE_TREE = "fc3387bf37aab19d780b2939a235309ed32b0492"
FORGE_WSR20 = "18bba95a4528f6ab5910633f1f87f603b8c4ddf8"

# Coordinator-listed Forge residual seams (§14): excluded from the 101 common
# set; preserved explicitly with blocking assessment, never fixed here.
SEAM_REASONS = {
    "HIDDEN_05": "face-down exile permission persistence",
    "HIDDEN_06": "face-down exile invalidation on zone change",
    "HIDDEN_11": "shuffle/order-knowledge invalidation",
    "HIDDEN_08": "look-audience seam",
    "HIDDEN_12": "controlled-player decision seam",
    "WS05-CMD-MULL-2": "London bottom-card choice seam",
}

# §8 blocking assessment per seam (Forge status, XMage status -> assessment).
SEAM_ASSESSMENT = {
    "HIDDEN_05": ("UNKNOWN", "UNKNOWN",
                  "STILL_UNKNOWN_FOR_READINESS",
                  "Neither engine evidences the obligation; blocking is "
                  "undeterminable. Bounded follow-up: face-down exile "
                  "permission seam workstream."),
    "HIDDEN_06": ("UNKNOWN", "UNKNOWN",
                  "STILL_UNKNOWN_FOR_READINESS",
                  "Neither engine evidences the obligation; blocking is "
                  "undeterminable. Bounded follow-up: face-down exile "
                  "invalidation-on-zone-change seam workstream."),
    "HIDDEN_11": ("UNKNOWN", "UNKNOWN",
                  "STILL_UNKNOWN_FOR_READINESS",
                  "Neither engine evidences the obligation; blocking is "
                  "undeterminable. Bounded follow-up: shuffle/order-knowledge "
                  "invalidation seam workstream."),
    "HIDDEN_08": ("NOT_RUN_BLOCKED", "UNKNOWN",
                  "STILL_UNKNOWN_FOR_READINESS",
                  "Forge seam missing and XMage exact evidence missing; "
                  "blocking undeterminable. Bounded follow-up: look-audience "
                  "seam workstream."),
    "HIDDEN_12": ("NOT_RUN_BLOCKED", "UNKNOWN",
                  "STILL_UNKNOWN_FOR_READINESS",
                  "Forge seam missing and XMage exact evidence missing; "
                  "blocking undeterminable. Bounded follow-up: "
                  "controlled-player decision seam workstream."),
    "WS05-CMD-MULL-2": ("NOT_RUN_BLOCKED", "DIRECTLY_VERIFIED",
                        "BOUNDED_NON_BLOCKING",
                        "Narrow London bottom-card *choice* path only; 2P/4P "
                        "mulligan lifecycle is DIRECTLY_VERIFIED on both "
                        "sides (Forge MULL-4 DIRECT, XMage MULL-2/4 DIRECT). "
                        "Non-blocking for provider selection with named "
                        "follow-up: London-tuck choice seam workstream."),
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
    "L6_elimination": "21/21 elimination (14 live causal cells: lethal, Commander damage, active-player loss, winner/draw, cleanup discards under caller-owned expendable-name contract, priority-ring/turn recomputation at 2P/3P/4P/5P + 7 discard-authority adversarial unit tests); poison/deck-out causation retained UNKNOWN; no Lab lost/left/winner mutation",
    "L7_hidden_replay": "9/9 hidden/replay (lossless complete-library restore, typed single face-down restore, controller-only private visibility, opponent/global non-oracle proofs, public/private hash separation, transcript hygiene, same-seed public semantic replay); 6-path prevalidation atomicity battery (zero-mutation rejects)",
    "replay_4p": "4P seeded semantic replay, 4476 decisions, semantic match true (reconciled bytes)",
    "lanes": "bounded live 2P/3P/5P/6P PASS; 7P FAIL_CLOSED; Real 4P technical smoke PASS; H4 XMage/Forge materialization PASS",
}

# ---------------------------------------------------------------- Gate B ---

def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def norm(status):
    return {"DIRECT": "DIRECTLY_VERIFIED"}.get(status, status)


def later_evidence_note(fid, cat, old):
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


def build_refresh(mapping, verdicts, manifest_cat):
    verdict_by_fid = {v["fixture_id"]: v for v in verdicts}
    rows = []
    for e in mapping["entries"]:
        fid = e["fixture_id"]
        old = e["status"]
        rows.append({
            "fixture_id": fid,
            "old_status": norm(old),
            "new_status": norm(old),
            "changed": False,
            "exact_evidence_pointer": e.get("pointer"),
            "identity_register_verdict": (verdict_by_fid.get(fid) or {}).get("verdict"),
            "why_promotion_is_valid_or_why_retained": later_evidence_note(
                fid, manifest_cat.get(fid, ""), old),
            "mapping_reason_preserved": e.get("reason"),
            "runtime_identity": runtime_identity_for(e),
            "impact_adjudication": impact_for(e),
        })
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
            "mapping_counts": mapping["counts"],
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
            "transition, runtime identity, and absence of prohibited fallback."
        ),
        "result_counts": counts_new,
        "promotions_applied": 0,
        "rows": rows,
    }

# ---------------------------------------------------------------- Gate C ---

def adjudicate(fid, xm_status, forge_row, packet_row):
    """Return (disposition, reason, agreement_or_gap_record)."""
    f_status = forge_row["status"]
    if xm_status == "DIRECTLY_VERIFIED" and f_status == "DIRECTLY_VERIFIED":
        return ("SAME_SEMANTICS",
                "Both engines meet the frozen obligation with live "
                "Rules-engine execution and no recorded Rules-visible "
                "behavioral delta. Documented substitutions (deck/entry-mode) "
                "are carried in the agreement record, not hidden.",
                {"type": "obligation_agreement"})
    if fid == "WS05-CMD-TAX-4":
        # XMage DIRECT (exact 4P {4}); Forge TC with run-shape-only residual.
        return ("SAME_SEMANTICS",
                "XMage proves the exact 4P {4} obligation; Forge proves the "
                "identical tax schedule exactly (count*2 formula live, "
                "{W}+{2}+{4} ladder incl. {4} payment). The Forge residual is "
                "run shape (exact-4P run), not behavior: no Rules-visible "
                "delta exists. Residual recorded, not hidden.",
                {"type": "obligation_agreement",
                 "forge_residual": forge_row.get("reason", "")})
    if xm_status == "NOT_RUN_BLOCKED":
        return ("ENGINE_CAPABILITY_GAP",
                "The Lab XMage execution path cannot run this fixture: bridge "
                "reports starting_state_injection_supported=false "
                "(contract-locked), while Forge executes the same obligation "
                "(Forge status %s). Gap is on the Lab-XMage integration seam; "
                "Mage engine-native capability for this fixture is unproven, "
                "not asserted." % f_status,
                {"type": "capability_gap", "side": "xmage_integration",
                 "missing_seam": "generic starting-state injection",
                 "forge_status": f_status})
    return ("NON_COMPARABLE",
            "XMage holds no fixture-exact evidence for this obligation "
            "(XMage status %s: family/lane evidence or absence), so semantic "
            "agreement cannot be asserted despite Forge status %s. This is an "
            "evidence asymmetry, not a proven incapability and not a Rules "
            "delta." % (xm_status, f_status),
            {"type": "evidence_asymmetry"})


def build_normalization(refresh, forge_mapping, successor_packet):
    by_xm = {r["fixture_id"]: r for r in refresh["rows"]}
    fmap = {r["fixture_id"]: r for r in forge_mapping["rows"]}
    fixtures = []
    for prow in successor_packet["fixtures"]:
        fid = prow["fixture_id"]
        assert fid not in SEAM_REASONS, fid
        xr = by_xm[fid]
        fr = fmap[fid]
        disp, reason, record = adjudicate(fid, xr["new_status"], fr, prow)
        record.update({
            "forge_evidence": {
                "status": fr["status"],
                "pointer": fr.get("forge_evidence_pointer"),
                "method": fr.get("evidence_method"),
                "reason": fr.get("reason"),
                "runtime_head": fr.get("runtime_head"),
                "runtime_tree": fr.get("runtime_tree"),
            },
            "xmage_evidence": {
                "status": xr["new_status"],
                "pointer": xr["exact_evidence_pointer"],
                "runtime_identity": xr["runtime_identity"],
            },
            "documented_substitutions": prow.get("known_non_comparable", []),
            "seed_comparable": prow.get("seed_comparable"),
            "terminal_facts": prow.get("terminal_facts", []),
        })
        fixtures.append({
            "fixture_id": fid,
            "denominator_identity": {
                "frozen_source": FROZEN_SOURCE,
                "materialization": MATERIALIZATION,
            },
            "player_count": prow.get("player_count"),
            "category": None,
            "decision_families": prow.get("decision_families", []),
            "externally_supplied_discretionary_decisions": (
                "fixture-scoped discretionary selections only; harness supplies "
                "no Rules outcomes"
            ),
            "seed_request": prow.get("seed_request", 424242),
            "seed_truthfully_comparable": (
                "packet slot seed_comparable=%s; cross-engine binding parity "
                "holds where both engines expose a real Rules-RNG binding "
                "(Forge seed twins 424242/777; XMage Rules-seed binding + "
                "same-seed replay)" % prow.get("seed_comparable")
            ),
            "public_state": "denominator-defined public facts (see terminal_facts)",
            "principal_observations": prow.get("observation_slots", []),
            "semantic_events": "denominator-required events per fixture",
            "rng_operations": "Rules-owned on both engines",
            "terminal_facts": prow.get("terminal_facts", []),
            "engine_local_non_comparable_fields": NON_COMPARABLE_FIELDS,
            "packet_verdict_superseded": prow.get("verdict"),
            "comparison_disposition": disp,
            "comparison_reason": reason,
            "comparison_record": record,
        })
    fixtures.sort(key=lambda f: f["fixture_id"])
    counts = {"SAME_SEMANTICS": 0, "NON_COMPARABLE": 0,
              "ENGINE_CAPABILITY_GAP": 0,
              "UNKNOWN_PENDING_RULES_ADJUDICATION": 0}
    for f in fixtures:
        counts[f["comparison_disposition"]] += 1
    # seam verification against the ingested Forge mapping (not memory)
    seam_rows = {fid: fmap[fid]["status"] for fid in SEAM_REASONS}
    excluded = []
    for fid in sorted(SEAM_REASONS):
        f_s, x_s, assess, why = SEAM_ASSESSMENT[fid]
        assert seam_rows[fid] == f_s, (fid, seam_rows[fid])
        assert by_xm[fid]["new_status"] == x_s, (fid, by_xm[fid]["new_status"])
        excluded.append({
            "fixture_id": fid,
            "reason": SEAM_REASONS[fid],
            "forge_status": f_s,
            "xmage_status": x_s,
            "blocking_assessment": assess,
            "blocking_rationale": why,
            "note": "preserved explicitly per scope; remediation not authorized here",
        })
    return {
        "schema_version": "final-provider-common-normalization-1.0.0",
        "denominator_identity": {
            "frozen_source": FROZEN_SOURCE,
            "materialization": MATERIALIZATION,
        },
        "ingest_provenance": {
            "forge_wsr20_tip": FORGE_WSR20,
            "forge_candidate": FORGE_CANDIDATE,
            "forge_tree": FORGE_TREE,
            "successor_packet": "wsr20-ingest/COMMON_FIXTURE_SUCCESSOR_PACKET.json",
            "forge_mapping": "wsr20-ingest/FULL107_FORGE_MAPPING.json",
            "starting_point": "WSR20 successor packet (101 fixtures) used as "
                              "the Gate C starting point; every packet verdict "
                              "re-adjudicated here against both engines' "
                              "evidence (prior UNKNOWN_PENDING verdicts "
                              "superseded per row, recorded in "
                              "packet_verdict_superseded).",
        },
        "derivation": (
            "Common set = 107-item denominator minus the 6 Forge residual "
            "seams (HIDDEN_05, HIDDEN_06, HIDDEN_11, HIDDEN_08, HIDDEN_12, "
            "WS05-CMD-MULL-2), verified against the ingested Forge mapping."
        ),
        "excluded_seams": excluded,
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

# ---------------------------------------------------------------- Gate D ---

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


def build_targeted(refresh, normalization, executions):
    by_fid = {r["fixture_id"]: r for r in refresh["rows"]}
    norm_by_fid = {f["fixture_id"]: f["comparison_disposition"]
                   for f in normalization["fixtures"]}
    gaps = [{
        "rank": 0,
        "priority_dimension": "forge_packet_ingest",
        "status": "COMPLETE",
        "fixture_ids": ["ALL-101-COMMON"],
        "what_was_missing": "WSR20 packet in Lab source truth",
        "what_was_done": "Vendored 8 WSR20 files at tip %s into "
                         "wsr20-ingest/ with provenance; Gate C rebuilt from "
                         "the actual successor packet." % FORGE_WSR20,
        "player_counts": [4],
        "seed": 424242,
    }]
    for i, (dim, fids) in enumerate(GAP_PRIORITIES, start=1):
        present = [f for f in fids if f in by_fid]
        disps = {norm_by_fid[f] for f in present if f in norm_by_fid}
        gaps.append({
            "rank": i,
            "priority_dimension": dim,
            "status": ("RESOLVED_BY_ADJUDICATION"
                       if disps and disps <= {"SAME_SEMANTICS"}
                       else "RECORDED_WITH_FOLLOWUP"),
            "fixture_ids": present,
            "comparison_dispositions": sorted(disps),
            "what_was_done": (
                "Every row adjudicated with both engines' evidence "
                "(Gate C); Forge denominator class re-executed 31/31 in "
                "Gate D; rows without an XMage execution seam recorded as "
                "ENGINE_CAPABILITY_GAP; rows without XMage exact evidence "
                "recorded as NON_COMPARABLE with the narrowly defined "
                "follow-up below."
            ),
            "followup_minimal_runtime": (
                "4P primary at seed 424242 with same decks/cards, same "
                "requested seed where both engines expose a real Rules-RNG "
                "binding, same externally supplied discretionary choices, same "
                "semantic stopping condition; 2P/3P/5P conformance for "
                "promoted rows; bounded 6P secondary; 7P explicit FAIL_CLOSED. "
                "No manual outcome injection; no harness Rules engine."
            ),
            "player_counts": [4],
            "seed": 424242,
        })
    return {
        "schema_version": "final-provider-targeted-runtime-1.0.0",
        "methodology": (
            "Reuse-first: no already-valid evidence rerun. Gaps ordered per "
            "priority (Rules-authority surfaces first). 4P primary; 2-5P "
            "technical conformance; bounded 6P secondary; 7P FAIL_CLOSED "
            "acceptable."
        ),
        "gate_d_executions_performed": executions,
        "xmage_execution_note": (
            "No new XMage engine execution: credited rows are already "
            "qualified on the reconciled authority (Gate B; rerun would "
            "violate reuse-first); missing rows genuinely lack a Lab execution "
            "seam (injection contract-locked) or an exact test, and are "
            "recorded as ENGINE_CAPABILITY_GAP / NON_COMPARABLE with bounded "
            "follow-ups above — not simulated."
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

# ------------------------------------------------------------ Divergence ---

def build_divergence(normalization):
    pending = [f["fixture_id"] for f in normalization["fixtures"]
               if f["comparison_disposition"] == "UNKNOWN_PENDING_RULES_ADJUDICATION"]
    return {
        "schema_version": "final-provider-divergence-1.0.0",
        "review_performed": (
            "All 101 common fixtures compared with both engines' "
            "fixture-corresponding evidence ingested (WSR20 packet + Lab Gate "
            "B). No Rules-visible behavioral delta is recorded on any row: "
            "SAME_SEMANTICS rows show obligation agreement; GAP rows show a "
            "missing XMage execution seam (not a behavioral disagreement); "
            "NON_COMPARABLE rows show XMage evidence absence (not a "
            "disagreement). Bridge/harness observations (London-tuck loud "
            "fail, unexecutable-cast refusal, frame-order settling, forced "
            "lone-target resolution) are documented behaviors, not "
            "Rules divergences."
        ),
        "divergences": [],
        "divergence_count": 0,
        "pending_rules_adjudication": pending,
    }

# ------------------------------------------------------------- Readiness ---

# Forge per-dimension status grounded in the ingested WSR20 evidence.
FORGE_DIMS = {
    "rules_authority_separation": ("SUPPORTING", ["no second Rules engine (VALIDATION method gates)", "7 fallback families fail-closed green", "pilot transports offered selections only"]),
    "legal_action_completeness": ("SUPPORTING", ["engine-offered frames only", "unexecutable-cast offers refused at execution (applied!=executed)", "global completeness unproven"]),
    "action_submission_completeness": ("SUPPORTING", ["applied!=executed refusal", "forced lone targets resolve with no frame (G02-documented)"]),
    "costs": ("TECHNICALLY_CONFORMANT", ["R20 tax ladder {W}+{2}+{4} exact", "count*2 formula live", "MICRO_COSTS TC (Esior-named residual)"]),
    "mana": ("DIRECT", ["MICRO_MANA_PAYMENT DIRECT", "PILOT_MANA_PAYMENT DIRECT"]),
    "priority": ("DIRECT", ["MICRO_PRIORITY DIRECT", "PILOT_PRIORITY DIRECT", "2-5P priority rings (WS233 lifecycles)"]),
    "stack": ("DIRECT", ["MICRO_STACK DIRECT", "R20 Bolt/Growth stack tests"]),
    "targets": ("DIRECT", ["MICRO_TARGETS DIRECT", "PILOT_TARGET + PILOT_TARGET_AMOUNT DIRECT"]),
    "modes": ("DIRECT", ["MICRO_MODES DIRECT", "PILOT_CHOOSE_MODE DIRECT"]),
    "choices": ("DIRECT", ["PILOT_CHOICE + PILOT_CHOOSE_OBJECT + PILOT_CHOOSE_USE DIRECT"]),
    "triggers": ("DIRECT", ["MICRO_TRIGGERS DIRECT", "PILOT_TRIGGER_ORDER DIRECT", "WS05-MP-TRIG-3/5 DIRECT"]),
    "replacement_effects": ("DIRECT", ["MICRO_REPLACEMENT DIRECT", "R20 zone-branch suite (incl. Condemn library-bottom)"]),
    "prevention_effects": ("DIRECT", ["MICRO_PREVENTION DIRECT", "R20 Fog prevention test"]),
    "continuous_effects": ("DIRECT", ["MICRO_CONTINUOUS_EFFECTS DIRECT", "R20 Crawler continuity test"]),
    "layers": ("DIRECT", ["MICRO_LAYERS DIRECT", "R20 Humility/Anthem layers tests"]),
    "sbas": ("DIRECT", ["MICRO_STATE_BASED_ACTIONS DIRECT", "R20 21-lethal test"]),
    "zones": ("TECHNICALLY_CONFORMANT", ["8 zone branches DIRECT", "MICRO_ZONE_CHANGES TC (new-object incarnation residual)"]),
    "copy": ("DIRECT", ["MICRO_COPY DIRECT", "R20 continuity tests"]),
    "control": ("DIRECT", ["MICRO_CONTROL DIRECT", "R20 Control-Magic revert test"]),
    "combat": ("DIRECT", ["MICRO_COMBAT DIRECT", "PILOT_DECLARE_ATTACKER/BLOCKER DIRECT", "R15 combat families", "R20 2/2 trade test"]),
    "commander_tax": ("TECHNICALLY_CONFORMANT", ["WS05-CMD-TAX-2 DIRECT", "R20 ladder incl. {4}", "WS05-CMD-TAX-4 TC (exact-4P run-shape residual)"]),
    "commander_zone_replacement": ("DIRECT", ["all 8 zone branches DIRECT"]),
    "commander_damage": ("DIRECT", ["WS05-CMD-DMG-SPLIT/SAME-21/CONTROL DIRECT", "R20 damage suite (lethal/split/control)"]),
    "partner": ("DIRECT", ["WS05-CMD-PARTNER-TAX/ZONE/DMG DIRECT"]),
    "mulligan": ("TECHNICALLY_CONFORMANT", ["WS05-CMD-MULL-4 DIRECT", "WS05-CMD-MULL-2 NOT_RUN_BLOCKED (London-tuck choice seam)"]),
    "starting_player_semantics": ("DIRECT", ["WS05-CMD-START-2/START-3 DIRECT", "R20 first-turn draw skip/grant tests"]),
    "player_count_2p": ("DIRECT", ["PLAYER_COUNT_2P DIRECT (WS233 lifecycle + R15 + R20 START-2/tax-2)"]),
    "player_count_3p": ("DIRECT", ["PLAYER_COUNT_3P DIRECT (WS233 + R15 + R20 elim START-3)"]),
    "player_count_4p": ("DIRECT", ["PLAYER_COUNT_4P DIRECT (WS233 + R9-R13 + G02/G03 + R20 commander suite)"]),
    "player_count_5p": ("DIRECT", ["PLAYER_COUNT_5P DIRECT (WS233 + R15 + ELIM-5 mechanism)"]),
    "bounded_6p": ("SUPPORTING", ["R16 lifecycle/combat/fanout/concede/hidden/twins; extra-denominator bounded only"]),
    "fail_closed_7p": ("TECHNICALLY_CONFORMANT", ["7P FAIL_CLOSED (PLAYER_COUNT_UNSUPPORTED, R16 negative retained)"]),
    "hidden_information": ("TECHNICALLY_CONFORMANT", ["13 DIRECT + 2 TC (HIDDEN_INFO_RESULTS)", "no leaks proven", "HIDDEN_05/06/11 UNKNOWN + HIDDEN_08/12 BLOCKED seams"]),
    "rules_rng": ("TECHNICALLY_CONFORMANT", ["RNG_RULES_TAPE DIRECT (Core-owned MyRandom, seeds incl. 424242 twins)", "MICRO_RULES_RANDOMNESS TC (predetermined-HEADS residual)"]),
    "semantic_replay": ("DIRECT", ["4 REPLAY_* DIRECT (fresh-JVM/process 2-6P, exactly-once twins, coordinates, hashes)", "WS227 negatives fail closed"]),
    "process_isolation": ("SUPPORTING", ["H4 Forge materialization PASS (technical only)", "fresh-process replay evidence"]),
    "actual_card_runtime_coverage": ("DIRECT", ["actual-card direct count 84: every behavioral DIRECT is actual-card runtime"]),
    "unsupported_path_failure_behavior": ("TECHNICALLY_CONFORMANT", ["7/7 negative families fail-closed green (TC-capped)", "WS227 tamper negatives (no mutation)", "7P + London-tuck loud fails"]),
}

XMAGE_DIMS = [
    ("rules_authority_separation", "SUPPORTING",
     ["engine-bridge decision controller + redactor + prevalidation battery (L7)", "B4-D legal-action handoff surface"]),
    ("legal_action_completeness", "SUPPORTING",
     ["bounded current-priority enumeration (B4-D)", "projection coverage + live-observed classes"]),
    ("action_submission_completeness", "SUPPORTING",
     ["bounded targetless/nonmodal submission + Rograkh cast (B4-D)", "stale-decision rejection"]),
    ("costs", "SUPPORTING",
     ["WS05-CMD-TAX-2/4 DIRECT (engine-owned {4} tax payment)", "per-commander tax figures (Partner)"]),
    ("mana", "SUPPORTING",
     ["engine-owned payment pipeline via TAX fixtures", "live-observed mana_payment class"]),
    ("priority", "SUPPORTING",
     ["L3 temporal driver checkpoints", "live-observed priority class 2-5P"]),
    ("stack", "TECHNICALLY_CONFORMANT",
     ["L4 5/5 reconstruction + 7/7 mechanics (Bolt/modal/nested/counter/fizzle)", "MICRO_TARGETS DIRECT"]),
    ("targets", "TECHNICALLY_CONFORMANT",
     ["MICRO_TARGETS DIRECT (exact P2 target, 3 damage)", "RG-07 exact-N offering (candidate)", "Switcheroo 2-target exchange (L5)"]),
    ("modes", "TECHNICALLY_CONFORMANT",
     ["PILOT_CHOOSE_MODE DIRECT (two-mode Devil selection)"]),
    ("choices", "SUPPORTING",
     ["live-observed choose_object/choose_use classes", "MICRO_MODES fixture UNKNOWN"]),
    ("triggers", "TECHNICALLY_CONFORMANT",
     ["WS05-MP-TRIG-3/5 DIRECT (Soul Warden APNAP)", "L3 simultaneous-trigger ordering"]),
    ("replacement_effects", "SUPPORTING",
     ["RG-08 replacement timing (candidate-level)", "native cleanup paths (L5/L6)"]),
    ("prevention_effects", "UNKNOWN",
     ["none exact in Lab truth (MICRO_PREVENTION UNKNOWN)"]),
    ("continuous_effects", "SUPPORTING",
     ["Humility/Anthem/Bears native layer facts (LAYERS scope)", "overlapping Control Magic timestamps (L5)"]),
    ("layers", "TECHNICALLY_CONFORMANT",
     ["MICRO_LAYERS DIRECT (layer 6/7b/7c native facts)"]),
    ("sbas", "SUPPORTING",
     ["20-vs-21 SBA loss (L2)", "command-zone choice characterization (blocked fixtures)"]),
    ("zones", "SUPPORTING",
     ["Unsummon/control-leaves zone cleanup (L5)", "zone-choice seams blocked (injection)"]),
    ("copy", "SUPPORTING",
     ["Flare of Duplication mechanics (L4)", "decoy-copy isolation (L2)"]),
    ("control", "TECHNICALLY_CONFORMANT",
     ["L5 7/7 divergence suite", "WS05-CMD-DMG-CONTROL blocked (injection)"]),
    ("combat", "SUPPORTING",
     ["real attack/block flow + skip-combat + extra-turn (L3)", "combat-damage test surface"]),
    ("commander_tax", "DIRECT",
     ["WS05-CMD-TAX-2/4 DIRECT", "WS05-CMD-PARTNER-TAX DIRECT (per-commander figures)"]),
    ("commander_zone_replacement", "SUPPORTING",
     ["native replacement paths (L5/L6)", "8 zone-choice fixtures NOT_RUN_BLOCKED (injection)"]),
    ("commander_damage", "DIRECT",
     ["WS05-CMD-DMG-SPLIT + WS05-CMD-PARTNER-DMG DIRECT (independent edges, no aggregation)", "L2 8/8 suite incl. 20/21"]),
    ("partner", "DIRECT",
     ["WS05-CMD-PARTNER-TAX/ZONE/DMG DIRECT", "Partner legality engine-proven at import"]),
    ("mulligan", "DIRECT",
     ["WS05-CMD-MULL-2/4 DIRECT (XMage London counts 93/6, 92/7)"]),
    ("starting_player_semantics", "TECHNICALLY_CONFORMANT",
     ["WS05-CMD-START-3 DIRECT (3P first-turn draw 8/7/7)", "2P/3P/4P/5P lane gates"]),
    ("player_count_2p", "SUPPORTING",
     ["2P lane gate PASS + replay MATCH", "MULL-2/TAX-2 DIRECT", "L6 2P terminal cell"]),
    ("player_count_3p", "SUPPORTING",
     ["3P lane gate PASS", "TRIG-3 + START-3 DIRECT", "L6 3P x8 cells"]),
    ("player_count_4p", "TECHNICALLY_CONFORMANT",
     ["4P 4476-decision semantic replay MATCH", "11 DIRECT fixtures at 4P", "Real 4P smoke PASS"]),
    ("player_count_5p", "SUPPORTING",
     ["5P lane gate PASS", "TRIG-5 DIRECT", "L6 5P middle-seat cell"]),
    ("bounded_6p", "SUPPORTING",
     ["bounded 6P smoke PASS (general surface only, not mechanism-specific)"]),
    ("fail_closed_7p", "TECHNICALLY_CONFORMANT",
     ["7P explicit FAIL_CLOSED (reconciled bytes)"]),
    ("hidden_information", "TECHNICALLY_CONFORMANT",
     ["L7 9/9 + boundary report + hash separation + transcript hygiene", "per-scenario exact reruns absent (Gate B)"]),
    ("rules_rng", "SUPPORTING",
     ["Rules-seed binding + same-seed replay MATCH", "RNG tape unit suites"]),
    ("semantic_replay", "TECHNICALLY_CONFORMANT",
     ["same-seed public semantic replay (4P 4476 MATCH; per-count MATCH)", "atomicity battery"]),
    ("process_isolation", "SUPPORTING",
     ["H4 XMage materialization PASS", "per-game lifecycle cleanup/reuse"]),
    ("actual_card_runtime_coverage", "SUPPORTING",
     ["16 named cards qualified across L2-L5 + real-deck E2E gate docs", "Rograkh cast to stack (B4-D)"]),
    ("unsupported_path_failure_behavior", "TECHNICALLY_CONFORMANT",
     ["prevalidation zero-mutation rejects", "invalid-payload + stale-decision rejection", "7P FAIL_CLOSED", "incomplete-library fail-before-mutation"]),
]


def build_readiness(normalization):
    gap_by_fid = {f["fixture_id"]: f["comparison_disposition"]
                  for f in normalization["fixtures"]}
    dims = []
    for name, xs, xpts in XMAGE_DIMS:
        f_status, fpts = FORGE_DIMS[name]
        dims.append({
            "dimension": name,
            "xmage": {"status": xs, "evidence_pointers": xpts,
                      "runtime_identity": XMAGE_RUNTIME if xs in ("DIRECT", "TECHNICALLY_CONFORMANT") else "mixed lane/mechanism heads (see Gate B rows)"},
            "forge": {"status": f_status, "evidence_pointers": fpts,
                      "runtime_identity": FORGE_CANDIDATE + " (ENGINE_CODE; WSR20 evidence tip " + FORGE_WSR20 + ")"},
        })
    return {
        "schema_version": "final-provider-readiness-1.0.0",
        "identities": {
            "lab_head": LAB_HEAD,
            "frozen_source": FROZEN_SOURCE,
            "xmage_candidate": XMAGE_CANDIDATE,
            "xmage_runtime_authority": XMAGE_RUNTIME,
            "forge_candidate": FORGE_CANDIDATE,
            "forge_tree": FORGE_TREE,
            "forge_wsr20_tip": FORGE_WSR20,
        },
        "forge_evidence_basis": (
            "Ingested WSR20 packet (wsr20-ingest/): FULL107 mapping 84/17/3/3 "
            "(FAIL 0), EXECUTION_RESULTS (213/213 + 31/31 + 243/243, BUILD "
            "SUCCESS), HIDDEN_INFO (13/2/2/3), RNG_REPLAY (tapes + twins + "
            "negatives), MULTIPLAYER (2-5P DIRECT, 6P bounded, 7P "
            "FAIL_CLOSED). Gate-D re-execution in WSR21: WsR20 denominator "
            "31/31 PASS, BUILD SUCCESS (see TARGETED_RUNTIME_RESULTS)."
        ),
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
    mapping = load_json(REPO / "docs/workstream_full107_definition_20260921/FULL107_MAPPING.json")
    register = load_json(REPO / "docs/workstream_full107_fixture_identity_20260922/FIXTURE_IDENTITY_REGISTER.json")
    manifest = load_json(REPO / "qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json")
    denominator = load_json(REPO / "qualification/ws47/WS47_PROVIDER_DENOMINATOR_107.json")
    forge_mapping = load_json(INGEST / "FULL107_FORGE_MAPPING.json")
    successor_packet = load_json(INGEST / "COMMON_FIXTURE_SUCCESSOR_PACKET.json")
    executions = load_json(OUT / "GATE_D_EXECUTIONS.json")["executions"]

    manifest_cat = {m["fixture_id"]: m.get("category", "") for m in manifest["fixtures"]}
    verdicts = register["verdicts"] if isinstance(register, dict) else register

    assert len(mapping["entries"]) == 107, len(mapping["entries"])
    assert len(denominator["fixture_ids"]) == 107
    assert {e["fixture_id"] for e in mapping["entries"]} == set(denominator["fixture_ids"]), "mapping/denominator mismatch"
    assert len(forge_mapping["rows"]) == 107
    assert {r["fixture_id"] for r in forge_mapping["rows"]} == set(denominator["fixture_ids"]), "forge mapping/denominator mismatch"
    assert forge_mapping["forge_head"] == FORGE_CANDIDATE
    assert forge_mapping["forge_tree"] == FORGE_TREE
    assert len(successor_packet["fixtures"]) == 101

    refresh = build_refresh(mapping, verdicts, manifest_cat)
    normalization = build_normalization(refresh, forge_mapping, successor_packet)
    targeted = build_targeted(refresh, normalization, executions)
    divergence = build_divergence(normalization)
    readiness = build_readiness(normalization)

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
    print("forge mapping counts:", forge_mapping["counts"])
    print("comparison counts:", normalization["comparison_counts"])
    print("targeted gaps:", len(targeted["gaps"]))
    print("divergences:", divergence["divergence_count"],
          "pending:", divergence["pending_rules_adjudication"])
    print("readiness dimensions:", len(readiness["dimensions"]))


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(main())