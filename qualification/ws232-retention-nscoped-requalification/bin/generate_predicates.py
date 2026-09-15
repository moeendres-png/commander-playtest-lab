#!/usr/bin/env python3
"""WS232 predicate generator: build the 47 machine-checkable retention
predicates mechanically from WORKLOAD_DERIVATION.json + current-tree blobs.

A predicate binds the semantic premise retention rests on. Every bind names
the path that OWNS the semantics (owns_semantics); a hash alone is never
the proof. Expected blob hashes are recorded from the current WS229-descendant
tree so retention survives future repins (S8 mission_value); the checker
(bin/check_predicates.py) re-verifies them mechanically.

Static binds CANNOT by themselves discharge behavior: each predicate also
declares n_scoped_rerun_required=[2,3,5]; the results artifact joins each
predicate to its current rerun pointers (or explicit UNKNOWN).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
NS = REPO_ROOT / "qualification/ws232-retention-nscoped-requalification"

ENGINE_COMMIT = "db134b9737e951367d65ef5806ad986319cc73ab"
ENGINE_VERSION = "1.4.61"
PROTOCOL_VERSION = "2.0.0"
TAPE_SCHEMA = "semantic-replay-tape/1.0.0"
SEED = 424242

LAB_DISPATCH = "src/commander_lab/engine/rules/full_game.py"
LAB_PILOTS = "src/commander_lab/agents/pilots.py"
BRIDGE_CONTROLLER = "engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGameDecisionController.java"
BRIDGE_PROJECTION = "engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGameActionProjection.java"
BRIDGE_PLAYER = "engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGamePlayer.java"
BRIDGE_SESSION = "engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGameSession.java"
BRIDGE_JSONL = "engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGameJsonlBridge.java"
BRIDGE_PROVIDER = "engine-bridge/src/main/java/org/commanderlab/xmage/XmageProvider.java"
REPLAY_TAPE = "src/commander_lab/semantic_replay/tape.py"
REPLAY_RECORDER = "src/commander_lab/semantic_replay/recorder.py"
REPLAY_CONSUMER = "src/commander_lab/semantic_replay/consumer.py"
REPLAY_CANON = "src/commander_lab/semantic_replay/canonicalization.py"
REPLAY_FPRINT = "src/commander_lab/semantic_replay/fingerprint.py"
REPLAY_SOURCE_LOCK = "src/commander_lab/semantic_replay/source_lock.py"
REPLAY_CAPABILITY = "src/commander_lab/semantic_replay/capability.py"
CARD_DOMAIN = "qualification/manifests/ACTUAL_CARD_DOMAIN_v1.json"
AUTHORITY_LOCK = "qualification/manifests/AUTHORITY_LOCK_v2.json"
MANIFEST = "qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json"


def sha(path: str) -> str:
    return hashlib.sha256((REPO_ROOT / path).read_bytes()).hexdigest()


def blob(path: str, owns: str) -> dict:
    return {"kind": "path_blob_sha256", "path": path,
            "expected_sha256": sha(path), "owns_semantics": owns}


def fixture_bytes(fixture_id: str, row: dict) -> dict:
    canon = json.dumps(row, sort_keys=True, separators=(",", ":")).encode()
    return {"kind": "fixture_bytes_sha256",
            "path": MANIFEST + "#" + fixture_id,
            "expected_sha256": hashlib.sha256(canon).hexdigest(),
            "owns_semantics": "fixture identity (card/seed/count/requirements) pinned by the sole manifest"}


def main() -> int:
    deriv = json.loads((NS / "WORKLOAD_DERIVATION.json").read_text())
    manifest = json.loads((REPO_ROOT / MANIFEST).read_text())
    manifest_rows = {f["fixture_id"]: f for f in manifest["fixtures"]}

    common_engine_binds = [
        {"kind": "engine_commit", "path": "config/rules_engines.json#primary_engine.commit",
         "expected_sha256": None, "expected_value": ENGINE_COMMIT,
         "owns_semantics": "Rules Core identity: sole authority for legality, costs, mana, stack, targets, RNG"},
        {"kind": "provider_identity", "path": BRIDGE_PROVIDER,
         "expected_sha256": sha(BRIDGE_PROVIDER),
         "owns_semantics": "runtime-reported ENGINE_VERSION/ENGINE_COMMIT/PROTOCOL_VERSION binding"},
        {"kind": "protocol_version", "path": "config/rules_engines.json#protocol_version",
         "expected_sha256": None, "expected_value": PROTOCOL_VERSION,
         "owns_semantics": "bridge protocol envelope; version drift invalidates recorded option streams"},
        {"kind": "rules_authority", "path": AUTHORITY_LOCK,
         "expected_sha256": sha(AUTHORITY_LOCK),
         "owns_semantics": "G01 Oracle/Rules authority identity inherited through WS226/WS229"},
        {"kind": "seed", "path": MANIFEST + "#seed",
         "expected_sha256": None, "expected_value": SEED,
         "owns_semantics": "deterministic seed authority for every retained fixture"},
        blob(BRIDGE_SESSION, "N-scoped game construction (setNumPlayers, rules-seed binding, lifecycle)"),
        blob(BRIDGE_JSONL, "one-game-per-process enforcement + JSONL transport envelope"),
    ]

    predicates = []
    for row in deriv["retained_rows"]:
        fid = row["fixture_id"]
        cat = row["category"]
        mrow = manifest_rows[fid]
        binds = list(common_engine_binds)
        binds.append(fixture_bytes(fid, mrow))
        if cat == "actual_card":
            premise = (
                "Card behavior is owned exclusively by the pinned XMage Rules Core "
                "card implementation (engine commit unchanged); the Lab decision path "
                "and pilots may only select among engine-authorized options and may not "
                "inject outcomes. Retention holds iff the engine pin, the fixture bytes, "
                "the card-domain denominator entry, and the owning Lab/bridge decision "
                "blobs match, AND current N-scoped behavior reruns (or explicit UNKNOWN) "
                "exist per required count."
            )
            binds += [
                {"kind": "card_identity", "path": MANIFEST + "#" + fid + ".card_identity",
                 "expected_sha256": None, "expected_value": mrow.get("card_identity"),
                 "owns_semantics": "frozen regression identity of the actual card under test"},
                {"kind": "card_domain_entry", "path": CARD_DOMAIN,
                 "expected_sha256": sha(CARD_DOMAIN),
                 "owns_semantics": "29-card frozen denominator membership (universe 1385)"},
                blob(LAB_DISPATCH, "Lab decision dispatch: routes engine options to pilots, never computes legality"),
                blob(LAB_PILOTS, "pilot strategies: selection among offered options only; numeric fail-closed"),
                blob(BRIDGE_CONTROLLER, "native option transport incl numeric gates; isGoodValues projection"),
                blob(BRIDGE_PROJECTION, "action projection incl requiresNumeric + schema projection"),
            ]
        elif cat == "micro_rules":
            premise = (
                "Micro-rule mechanism (costs/mana/priority/stack/targets/modes/triggers/"
                "replacement/prevention/continuous/layers/SBA/zones/copy/control/combat/RNG) "
                "is owned exclusively by the pinned XMage Rules Core; Lab paths only "
                "project and observe. 'XMage owns it' alone is not runtime proof: retention "
                "holds iff the engine pin and owning projection/observation blobs match, "
                "AND the mechanism is provoked through the authoritative runtime seam at "
                "each required count (or the cell stays explicitly UNKNOWN)."
            )
            binds += [
                blob(LAB_DISPATCH, "Lab observation/projection seam for engine-owned mechanisms"),
                blob(BRIDGE_PROJECTION, "engine-to-Lab action/observation projection"),
                blob(BRIDGE_PLAYER, "engine callback emitters incl numeric + target_amount companion paths"),
            ]
        elif cat == "replay_rng":
            premise = (
                "Replay/RNG determinism rests on tape schema 1.0.0 + source/domain locks + "
                "Rules-Core RNG regeneration (require_explicit_seed + rules_seed_binding) + "
                "semantic option matching + fresh-process isolation. Retention holds iff the "
                "schema, recorder/consumer/canonicalization/digest blobs, RNG authority flags, "
                "and semantic allowlists match, AND current N-scoped record+independent-replay "
                "evidence exists (or the cell stays explicitly UNKNOWN)."
            )
            binds += [
                {"kind": "replay_schema", "path": REPLAY_TAPE + "#TAPE_SCHEMA_VERSION",
                 "expected_sha256": None, "expected_value": TAPE_SCHEMA,
                 "owns_semantics": "normative tape version; WS229 vector extension stayed on 1.0.0"},
                blob(REPLAY_TAPE, "tape model + numeric coherence validators"),
                blob(REPLAY_RECORDER, "record path: fresh-process production lane, atomic seal, no injection"),
                blob(REPLAY_CONSUMER, "14-step replay algorithm: locks, exactly-one matching, divergence taxonomy"),
                blob(REPLAY_CANON, "semantic canonicalization contract"),
                blob(REPLAY_FPRINT, "option/state digest identity incl numeric binding"),
                blob(REPLAY_SOURCE_LOCK, "source/domain lock verification"),
                blob(REPLAY_CAPABILITY, "capability truth (supported counts, tamper matrix)"),
                {"kind": "rng_authority", "path": BRIDGE_SESSION + "#rules-seed-binding",
                 "expected_sha256": None, "expected_value": "setRulesSeed+setRequireExplicitSeed(true)+getRulesRandomCalls",
                 "owns_semantics": "all Rules randomness originates in the Rules Core with explicit seed authority"},
            ]
        else:
            raise AssertionError(cat)
        predicates.append({
            "predicate_id": "PRED-" + fid,
            "fixture_id": fid,
            "category": cat,
            "semantic_premise": premise,
            "binds": binds,
            "n_scoped_rerun_required": [2, 3, 5],
            "evaluation_rule": "STATIC_PASS iff every bind matches current tree; "
                               "RETAINED iff STATIC_PASS and (current rerun pointer per required N cell "
                               "or explicit UNKNOWN with sealed cause). Predicate failure => rerun, never weaken.",
        })

    schema = {
        "schema_version": "ws232-retention-predicate-1.0.0",
        "predicate_kinds": ["engine_commit", "provider_identity", "protocol_version",
                            "rules_authority", "seed", "path_blob_sha256", "fixture_bytes_sha256",
                            "card_identity", "card_domain_entry", "replay_schema", "rng_authority"],
        "verdicts": ["STATIC_PASS", "STATIC_FAIL"],
        "retention_rule": "RETAINED iff STATIC_PASS and every required N cell has a current rerun pointer or explicit UNKNOWN",
        "forbidden": ["existence-only predicates", "grandfathering by age/seal", "weakening a predicate to obtain green"],
    }
    (NS / "RETENTION_PREDICATE_SCHEMA.json").write_text(json.dumps(schema, indent=1, sort_keys=True) + "\n")
    (NS / "RETENTION_PREDICATES.json").write_text(
        json.dumps({"schema_version": "ws232-retention-predicate-1.0.0",
                    "predicate_count": len(predicates),
                    "predicates": predicates}, indent=1, sort_keys=True) + "\n")
    print(f"predicates={len(predicates)} "
          f"actual={sum(1 for p in predicates if p['category']=='actual_card')} "
          f"micro={sum(1 for p in predicates if p['category']=='micro_rules')} "
          f"replay={sum(1 for p in predicates if p['category']=='replay_rng')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
