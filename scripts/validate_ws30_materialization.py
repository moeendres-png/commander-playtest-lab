#!/usr/bin/env python3
import argparse
import hashlib
import json
import pathlib
import re
from collections import Counter

from jsonschema import Draft202012Validator

SCHEMA_ID = "commander-lab.semantic-fixture-materialization/1.0.0"
RSP = "commander-lab.rules-service/1.1.0"
COMMON_SHA = "e7f34ea4b2543132440e7e5fdb47c6cb4d4908f05fb49f6fa59f3e0592ca3bd4"
EXPECTED_FAMILIES = {
    "player_count": 4,
    "pilot_boundary": 17,
    "pilot_boundary_negative": 7,
    "hidden_information": 20,
    "replay_rng": 5,
    "micro_rules": 17,
    "actual_card": 29,
    "multiplayer_commander": 36,
}
STARTER18 = [
    "PLAYER_COUNT_2P",
    "PLAYER_COUNT_3P",
    "PLAYER_COUNT_4P",
    "PLAYER_COUNT_5P",
    "PILOT_MULLIGAN",
    "PILOT_PRIORITY",
    "PILOT_TARGET",
    "HIDDEN_01",
    "HIDDEN_02",
    "MICRO_STACK",
    "MICRO_REPLACEMENT",
    "WS05-MP-COMBAT-4",
    "RNG_RULES_TAPE",
    "REPLAY_DECISION_TAPE",
    "REPLAY_EVENT_TAPE",
    "REPLAY_CLEAN_PROCESS",
    "REPLAY_STATE_HASHES",
    "CARD_02",
]
FORGE_ONLY = [
    "MICRO_COMBAT",
    "MICRO_COSTS",
    "MICRO_MANA_PAYMENT",
    "MICRO_PREVENTION",
    "MICRO_PRIORITY",
    "MICRO_RULES_RANDOMNESS",
    "MICRO_TARGETS",
    "MICRO_TRIGGERS",
    "MICRO_ZONE_CHANGES",
    "PILOT_DECLARE_ATTACKER",
    "PILOT_DECLARE_BLOCKER",
    "PILOT_MANA_PAYMENT",
    "PILOT_REPLACEMENT_EFFECT",
    "PILOT_TRIGGER_ORDER",
    "WS05-CMD-ZONE-HAND-YES",
    "WS05-MP-BLOCK-4",
]
XMAGE_ONLY = [
    "CARD_04",
    "CARD_24",
    "HIDDEN_03",
    "HIDDEN_14",
    "HIDDEN_15",
    "HIDDEN_16",
    "HIDDEN_18",
    "HIDDEN_19",
    "HIDDEN_HONEYCARD_SENTINEL",
    "MICRO_CONTINUOUS_EFFECTS",
    "NEGATIVE_PARENT_CLASS_FALLBACK",
    "PILOT_CHOICE",
    "PILOT_CHOOSE_OBJECT",
    "PILOT_CHOOSE_USE",
    "WS05-CMD-TAX-4",
    "WS05-MP-TRIG-3",
]
UNION50 = STARTER18 + FORGE_ONLY + XMAGE_ONLY


class V:
    def __init__(self):
        self.errors = []
        self.checks = []

    def ok(self, cond, msg):
        self.checks.append((msg, bool(cond)))
        if not cond:
            self.errors.append(msg)


def load(p):
    return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))


def rawsha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def canonical_sha(x):
    return hashlib.sha256(
        json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def walk_strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from walk_strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from walk_strings(v)


def manifest_records(m):
    if isinstance(m, dict) and isinstance(m.get("fixtures"), list):
        return m["fixtures"]
    if isinstance(m, list):
        return m
    raise ValueError("unrecognized common manifest structure")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=str(pathlib.Path(__file__).resolve().parents[1]))
    ap.add_argument("--skip-source-lock", action="store_true")
    args = ap.parse_args()
    root = pathlib.Path(args.repo_root)
    mat = root / "qualification/materialization"
    v = V()
    schema = load(mat / "SEMANTIC_FIXTURE_SCHEMA_v1.json")
    corpus = load(mat / "SEMANTIC_FIXTURE_MATERIALIZATION_v1.json")
    blockers = load(mat / "MATERIALIZATION_BLOCKERS.json")
    authmap = load(mat / "MATERIALIZATION_AUTHORITY_MAP.json")
    starter = load(mat / "DIFFERENTIAL_STARTER_18.json")
    union = load(mat / "KNOWN_PASS_UNION_50.json")
    Draft202012Validator.check_schema(schema)
    errs = list(Draft202012Validator(schema).iter_errors(corpus))
    v.ok(not errs, "JSON Schema validation")
    if errs:
        for e in errs[:20]:
            v.errors.append(f"schema:{list(e.path)}:{e.message}")
    recs = corpus["records"]
    ids = [r["fixture_id"] for r in recs]
    byid = {r["fixture_id"]: r for r in recs}
    v.ok(
        corpus["schema_version"] == SCHEMA_ID and corpus["protocol"] == RSP,
        "schema/protocol identity",
    )
    v.ok(len(recs) == 135, "exactly 135 records")
    v.ok(len(set(ids)) == 135, "135 unique fixture IDs")
    v.ok(
        Counter(r["fixture_family"] for r in recs) == Counter(EXPECTED_FAMILIES),
        "family distribution 4/17/7/20/5/17/29/36",
    )
    bad = []
    for r in recs:
        z = dict(r)
        got = z.pop("materialization_digest")
        exp = canonical_sha(z)
        if got != exp:
            bad.append(r["fixture_id"])
    v.ok(not bad, "all per-record materialization digests recompute")
    z = dict(corpus)
    got = z.pop("canonical_bundle_digest")
    v.ok(got == canonical_sha(z), "canonical bundle digest recomputes")
    v.ok(
        all(
            r["frozen_contract_binding"]
            == {
                "af_mapping": "INHERIT_BY_REFERENCE_NO_REDEFINITION",
                "manifest_fixture_id": r["fixture_id"],
                "manifest_sha256": COMMON_SHA,
            }
            for r in recs
        ),
        "AF mapping inherited by exact frozen-manifest reference",
    )
    provider_leaks = []
    internal_leaks = []
    for r in recs:
        norm = dict(r)
        norm.pop("authority_provenance", None)
        txt = json.dumps(norm, ensure_ascii=False).lower()
        if "forge" in txt or "xmage" in txt:
            provider_leaks.append(r["fixture_id"])
        if re.search(r"\b(mageobjectreference|gameentityview|forgegame|magicgameid)\b", txt):
            internal_leaks.append(r["fixture_id"])
    v.ok(not provider_leaks, "no provider names in normative scenario state")
    v.ok(not internal_leaks, "no candidate-internal IDs/types in normative state")
    for r in recs:
        oids = [o["semantic_id"] for o in r["semantic_objects"]]
        v.ok(len(oids) == len(set(oids)), f"{r['fixture_id']}: unique semantic object IDs")
        seats = [p["seat"] for p in r["players"]]
        pids = [p["player_id"] for p in r["players"]]
        v.ok(
            seats == list(range(1, len(r["players"]) + 1)) and pids == [f"P{i}" for i in seats],
            f"{r['fixture_id']}: stable player IDs/seats",
        )
        sv = r["setup_validation"]
        v.ok(
            sv.get("construct_inside_rules_process") is True
            and sv.get("native_structural_validation_required") is True
            and sv.get("on_mismatch") == "FAIL_CLOSED",
            f"{r['fixture_id']}: native setup validation fail-closed",
        )
        for d in r["decision_script"]:
            sel = d["selection"]
            v.ok(
                sel["matches_only_provider_offered_legal_options"] is True
                and sel["on_zero_match"] == "FAIL_CLOSED"
                and sel["on_multiple_match"] == "FAIL_CLOSED",
                f"{r['fixture_id']}: selector fail-closed",
            )
            st = json.dumps(sel, ensure_ascii=False).lower()
            v.ok(
                not any(
                    x in st
                    for x in [
                        "first_option",
                        "random_option",
                        "default_yes_no",
                        "internal_ai",
                        "gui_default",
                        "silent_skip",
                        "parent_class_fallback",
                        "option #",
                        "option_index",
                    ]
                ),
                f"{r['fixture_id']}: selector has no forbidden fallback semantics",
            )
    hidden = [r for r in recs if r["fixture_family"] == "hidden_information"]
    v.ok(len(hidden) == 20, "20 hidden-information records")
    for r in hidden:
        states = r["knowledge_state"].get("viewer_states", [])
        v.ok(
            states and all(s.get("viewer") for s in states),
            f"{r['fixture_id']}: explicit viewer state",
        )
        v.ok(
            all("channels_under_test" in s and s["channels_under_test"] for s in states),
            f"{r['fixture_id']}: explicit leakage channels",
        )
    replay = [r for r in recs if r["fixture_family"] == "replay_rng"]
    v.ok(len(replay) == 5, "5 replay/RNG records")
    for r in replay:
        rc = r.get("replay_contract", {})
        v.ok(
            r["rules_randomness"].get("rules_seed") == 424242
            and rc.get("checkpoints")
            and rc.get("event_normalization"),
            f"{r['fixture_id']}: seed + normalization + checkpoints",
        )
        v.ok(
            r["rules_randomness"].get("pilot_randomness_prohibited") is True,
            f"{r['fixture_id']}: pilot randomness excluded from Rules RNG",
        )
    cards = [r for r in recs if r["fixture_family"] == "actual_card"]
    v.ok(
        len(cards) == 29 and all(len(r["players"]) == 4 for r in cards), "CARD_01-29 are exactly 4P"
    )
    v.ok(
        set(r["fixture_id"] for r in cards) == {f"CARD_{i:02d}" for i in range(1, 30)},
        "complete CARD_01-29 ID set",
    )
    bad_unresolved = []
    for r in recs:
        text = "\n".join(walk_strings(r))
        if re.search(r"\b(TODO|TBD|FIXME|UNRESOLVED_FIELD|DEFAULT_ME|PLACEHOLDER)\b", text, re.I):
            bad_unresolved.append(r["fixture_id"])
    v.ok(not bad_unresolved, "no unresolved field silently defaulted")
    v.ok(
        starter["fixture_count"] == 18
        and starter["fixture_ids"] == STARTER18
        and [r["fixture_id"] for r in starter["records"]] == STARTER18,
        "exact differential starter 18",
    )
    v.ok(
        union["fixture_count"] == 50
        and union["fixture_ids"] == UNION50
        and len(set(union["fixture_ids"])) == 50,
        "exact known-PASS union 50",
    )
    v.ok(
        all(
            starter["records"][i]["materialization_digest"] == byid[fid]["materialization_digest"]
            for i, fid in enumerate(STARTER18)
        ),
        "starter records byte-semantic identity by digest",
    )
    v.ok(
        all(
            union["records"][i]["materialization_digest"] == byid[fid]["materialization_digest"]
            for i, fid in enumerate(UNION50)
        ),
        "union records byte-semantic identity by digest",
    )
    blocked = [
        r["fixture_id"]
        for r in recs
        if r["materialization_status"] == "MATERIALIZATION_BLOCKED_CONTRACT_AMBIGUITY"
    ]
    v.ok(
        blockers["blocker_count"] == len(blocked) == len(blockers["records"]),
        "blocker register matches materialization statuses",
    )
    sha_line = (mat / "SEMANTIC_FIXTURE_MATERIALIZATION_v1.sha256").read_text().strip().split()[0]
    v.ok(
        sha_line == rawsha(mat / "SEMANTIC_FIXTURE_MATERIALIZATION_v1.json"),
        "materialization .sha256 matches bytes",
    )
    sums = {}
    for line in (mat / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        sums[name] = digest
    v.ok(
        all(
            (mat / name).is_file() and rawsha(mat / name) == digest for name, digest in sums.items()
        ),
        "SHA256SUMS verifies",
    )
    if not args.skip_source_lock:
        manifest_path = root / "qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json"
        v.ok(manifest_path.is_file(), "frozen common manifest exists")
        if manifest_path.is_file():
            v.ok(rawsha(manifest_path) == COMMON_SHA, "frozen common manifest SHA256 exact")
            m = load(manifest_path)
            mrows = manifest_records(m)
            mids = [x["fixture_id"] for x in mrows]
            v.ok(
                set(mids) == set(ids) and len(mids) == 135,
                "materialization IDs exactly equal frozen common manifest",
            )
            mp = {x["fixture_id"]: x for x in mrows}
            for r in recs:
                v.ok(
                    len(r["players"]) == mp[r["fixture_id"]]["player_count"],
                    f"{r['fixture_id']}: player count equals frozen manifest",
                )
        ws29_path = root / "qualification/ws29/PROVIDER_NEUTRAL_EXPECTED_SEMANTICS.json"
        v.ok(ws29_path.is_file(), "WS-29 provider-neutral card authority exists")
        if ws29_path.is_file():
            w = load(ws29_path)
            wr = {x["fixture_id"]: x for x in w["records"]}
            v.ok(
                set(wr) == {f"CARD_{i:02d}" for i in range(1, 30)},
                "WS-29 authority has exact 29 card IDs",
            )
            for r in cards:
                a = wr[r["fixture_id"]]
                b = r["card_authority_binding"]
                v.ok(
                    b["card_identity"] == a["card_identity"],
                    f"{r['fixture_id']}: exact WS-29 card identity",
                )
                v.ok(
                    set(r["authority_provenance"]["cr_rule_references"])
                    == set(a["cr_rule_references"]),
                    f"{r['fixture_id']}: exact WS-29 CR reference set",
                )
                v.ok(
                    a["player_count"] == 4
                    and a["authority_classification"] == "FULL_CURRENT_ORACLE_LOCK"
                    and a["discriminator_authority"] == "DISCRIMINATOR_AUTHORITY_PASS",
                    f"{r['fixture_id']}: WS-29 authority classification remains locked",
                )
    for n in range(2, 6):
        r = byid[f"PLAYER_COUNT_{n}P"]
        v.ok(
            all(p["starting_life"] == 40 for p in r["players"])
            and len(r.get("deck_state", [])) == n
            and all(
                d["library_template"] == {"card_identity": "Mountain", "count": 99}
                for d in r["deck_state"]
            ),
            f"PLAYER_COUNT_{n}P: canonical Commander lifecycle explicit",
        )
    review = (mat / "CRITICAL_18_MANUAL_REVIEW.md").read_text(encoding="utf-8")
    v.ok(all(f"`{fid}`" in review for fid in STARTER18), "manual review covers all critical 18")
    v.ok(set(authmap["fixture_authority"]) == set(ids), "authority map covers all 135 fixtures")
    print(
        json.dumps(
            {
                "status": "PASS" if not v.errors else "FAIL",
                "checks": len(v.checks),
                "errors": v.errors,
            },
            indent=2,
        )
    )
    return 0 if not v.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
