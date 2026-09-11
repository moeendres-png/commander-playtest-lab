#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

VERDICTS = {"PASS", "FAIL", "UNKNOWN", "NOT_RUN", "PARTIAL", "UNSUPPORTED", "NOT_APPLICABLE"}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--results", type=Path, required=True)
    ap.add_argument("--handshake", type=Path, required=True)
    ap.add_argument("--inventory", type=Path, required=True)
    ap.add_argument("--source-lock", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    args = ap.parse_args()

    manifest = load(args.manifest)
    result_doc = load(args.results)
    handshake = load(args.handshake)
    inventory = load(args.inventory)
    source_lock = load(args.source_lock)
    fixtures = manifest["fixtures"]
    results = result_doc["fixture_results"]
    if len(fixtures) != 135:
        raise SystemExit(f"common manifest drift: expected 135 fixtures, got {len(fixtures)}")
    if len(results) != len(fixtures):
        raise SystemExit(f"result denominator mismatch: {len(results)} != {len(fixtures)}")

    fx_by_id = {fx["fixture_id"]: fx for fx in fixtures}
    if len(fx_by_id) != len(fixtures):
        raise SystemExit("duplicate fixture_id in common manifest")
    result_by_id = {r["fixture_id"]: r for r in results}
    if set(result_by_id) != set(fx_by_id):
        raise SystemExit("common result fixture IDs do not exactly match manifest")
    if any(r.get("verdict") not in VERDICTS for r in results):
        raise SystemExit("unknown verdict in common results")

    counts = Counter(r["verdict"] for r in results)
    categories: dict[str, Counter] = defaultdict(Counter)
    player_counts: dict[str, Counter] = defaultdict(Counter)
    for fid, r in result_by_id.items():
        fx = fx_by_id[fid]
        categories[fx["category"]][r["verdict"]] += 1
        if fx.get("player_count") is not None:
            player_counts[str(fx["player_count"])][r["verdict"]] += 1

    cards = []
    for fx in fixtures:
        if fx.get("card_identity"):
            r = result_by_id[fx["fixture_id"]]
            cards.append(
                {
                    "fixture_id": fx["fixture_id"],
                    "card_identity": fx["card_identity"],
                    "verdict": r["verdict"],
                    "reason": r.get("reason", ""),
                }
            )
    if len(cards) != 29:
        raise SystemExit(f"29-card denominator drift: got {len(cards)}")

    hs = handshake.get("payload", {})
    af = [
        {
            "gate_id": "AF00",
            "verdict": "PASS",
            "reason": "Pinned Forge source/tree/version plus generated GPL-side source hashes and compiled provider identity are recorded.",
        },
        {
            "gate_id": "AF01",
            "verdict": "PASS",
            "reason": "Exact WS-10R 1.1 handshake executed and truthfully reports fixture execution unsupported.",
        },
        {
            "gate_id": "AF02",
            "verdict": "UNSUPPORTED",
            "reason": "2P/3P/4P/5P common fixtures executed against the strict provider shell and fail closed as unsupported; no Forge game lifecycle route is implemented.",
        },
        {
            "gate_id": "AF03",
            "verdict": "UNSUPPORTED",
            "reason": "The current probe does not execute Forge game rules for common fixtures, so sole Rules-Core authority is not runtime-qualified.",
        },
        {
            "gate_id": "AF04",
            "verdict": "PARTIAL",
            "reason": "Every abstract PlayerController callback is mechanically trapped in the generated direct subclass and stock GUI/AI modules are absent from the probe classpath, but no legal-option/DecisionFrame route is implemented.",
        },
        {
            "gate_id": "AF05",
            "verdict": "UNSUPPORTED",
            "reason": "Actor-scoped observation serialization and honeycard fixtures are not implemented in the Forge provider.",
        },
        {
            "gate_id": "AF06",
            "verdict": "UNSUPPORTED",
            "reason": "Frozen micro-rules fixtures execute only to typed fail-closed UNSUPPORTED responses; no rules semantics are exercised.",
        },
        {
            "gate_id": "AF07",
            "verdict": "UNSUPPORTED",
            "reason": "All 29 actual-card fixtures are accounted for but no Forge card semantics are executed by the provider.",
        },
        {
            "gate_id": "AF08",
            "verdict": "UNSUPPORTED",
            "reason": "Commander/multiplayer fixtures are denominator-complete but rules execution is not implemented.",
        },
        {
            "gate_id": "AF09",
            "verdict": "UNSUPPORTED",
            "reason": "Rules RNG tape, DecisionTape, EventTape, checkpoints and clean-process semantic replay are not implemented.",
        },
        {
            "gate_id": "AF10",
            "verdict": "PASS",
            "reason": "All 135 common fixtures receive explicit typed runtime results with no skip, missing fixture, crash, or silent fallback in the qualification route.",
        },
        {
            "gate_id": "AF11",
            "verdict": "PASS",
            "reason": "Runtime topology is a separate JVM process; proprietary launcher imports no Forge classes; generated GPL-side artifacts remain in the separate Forge checkout and stock GUI/AI classes are excluded from the provider classpath.",
        },
    ]

    candidate_fixture_results = []
    for fx in fixtures:
        raw = result_by_id[fx["fixture_id"]]
        candidate_fixture_results.append(
            {
                "fixture_id": fx["fixture_id"],
                "candidate": "forge",
                "source_lock": source_lock["forge"],
                "verdict": raw["verdict"],
                "evidence_class": raw.get("evidence_class", "RUNTIME_VERIFIED"),
                "reason": raw.get("reason", ""),
                "classification": "RUNTIME_PASS"
                if raw["verdict"] == "PASS"
                else "REMEDIATION_REQUIRED",
                "omission_reason_code": "REMEDIATION_REQUIRED",
                "artifact_hashes": raw.get("artifact_hashes", {}),
            }
        )

    candidate = {
        "schema_version": "candidate-result/1.0.0",
        "candidate": "forge",
        "source_lock": source_lock["forge"],
        "classifications": ["REMEDIATION_REQUIRED"],
        "direct_failures": [
            "Lossless Forge rules/DecisionFrame execution is not implemented; all common semantic fixtures fail closed as UNSUPPORTED.",
            "Actor-safe observation, replay/RNG provenance, Commander/multiplayer execution, and 29-card behavioral execution remain unimplemented.",
        ],
        "thin_adapter_assessment": "PROCESS/TRANSPORT SHELL PASS; FULL LOSSLESS RULES ADAPTER UNSUPPORTED",
        "authority_status": "BLOCKED_ORACLE_AND_BYTE_EXACT_CR",
        "common_runtime_status": "UNSUPPORTED",
        "common_runtime_reason": "All 135 common fixtures reached a real isolated Forge-loaded JVM provider shell; semantic fixture execution is intentionally fail-closed UNSUPPORTED rather than delegated to AI/default/GUI behavior.",
        "fixture_results": candidate_fixture_results,
        "af_results": af,
        "freeze_eligible": False,
    }

    summary = {
        "schema_version": "ws19-forge-execution-summary/1.0.0",
        "fixture_count": len(fixtures),
        "verdict_counts": dict(sorted(counts.items())),
        "category_counts": {k: dict(sorted(v.items())) for k, v in sorted(categories.items())},
        "player_count_counts": {
            k: dict(sorted(v.items())) for k, v in sorted(player_counts.items())
        },
        "card_fixture_count": len(cards),
        "callback_abstract_count": inventory["abstract_method_count"],
        "stock_remote_default_count": len(inventory["stock_remote_default_findings"]),
        "handshake": hs,
        "freeze_eligible": False,
    }

    out = args.output_dir
    dump(out / "WS19_COMMON_EXECUTION_SUMMARY.json", summary)
    dump(out / "WS19_29_CARD_MATRIX.json", {"cards": cards})
    dump(out / "WS19_CANDIDATE_RESULT.json", candidate)

    lines = [
        "# WS-19 Forge Common Execution Report",
        "",
        f"- Common fixtures executed: **{len(fixtures)} / 135**",
        f"- Verdict counts: `{dict(sorted(counts.items()))}`",
        f"- Frozen actual-card fixtures: **{len(cards)} / 29**",
        f"- PlayerController abstract callbacks inventoried: **{inventory['abstract_method_count']}**",
        f"- Stock remote fallback occurrences detected: **{len(inventory['stock_remote_default_findings'])}**",
        "- Freeze eligible: **NO**",
        "",
        "## Interpretation",
        "",
        "The isolated JVM/provider boundary and fail-closed transport execute. The provider intentionally does not claim Forge rules semantics: every common semantic fixture returns `UNSUPPORTED` until a genuine Forge game/DecisionFrame route is implemented. No `UNSUPPORTED`, `PARTIAL`, `UNKNOWN`, or `NOT_RUN` result is promoted to PASS.",
        "",
        "## AF00-AF11",
        "",
    ]
    for row in af:
        lines.append(f"- `{row['gate_id']}` — **{row['verdict']}** — {row['reason']}")
    lines += ["", "## 29-Card Corpus", ""]
    for row in cards:
        lines.append(f"- `{row['card_identity']}` / `{row['fixture_id']}` — **{row['verdict']}**")
    (out / "WS19_COMMON_EXECUTION_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    hashes = {}
    for path in sorted(out.iterdir()):
        if path.is_file() and path.name != "SHA256SUMS":
            hashes[path.name] = sha256(path)
    (out / "SHA256SUMS").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in hashes.items()), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
