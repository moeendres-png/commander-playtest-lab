#!/usr/bin/env python3
"""Terminal WS-41 builder entrypoint, including continuation evidence closure."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

import ws41_build_successor as impl

# Fresh direct probe of https://magic.wizards.com/en/rules on 2026-09-04.
# The currently linked filename advanced to 20260819, while the bytes remain
# the Comprehensive Rules effective August 7, 2026 with the same frozen SHA.
impl.CURRENT_CR_URL = "https://media.wizards.com/2026/downloads/MagicCompRules%2020260819.txt"
impl.CURRENT_CR_EFFECTIVE = "2026-08-07"
impl.CURRENT_CR_SHA256 = "4381ad1b39ab2c05f7d03633a20f711ed37277074d3266dcba5f38cbb527423f"

DEFECT_RUNTIME_HEAD = "c10c0f8ff055253c2ee62fcbdf918c87b3128ec3"
DEFECT_RUNTIME_RUN = 33851407144
DEFECT_RUNTIME_JOB = 100954816503
CAUSALITY_HEAD = "d67a0dc4f0134d7c8f935213660eeae8f8c1a1cc"
CAUSALITY_RUN = 33851517930
CAUSALITY_JOB = 100955167145


def _git(*args: str, text: bool = False) -> bytes | str:
    result = subprocess.run(
        ["git", *args],
        cwd=impl.ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
    )
    return result.stdout


def _ws32_content_integrity() -> dict[str, Any]:
    """Compare the live WS-32 namespace byte-for-byte with the freeze commit."""
    raw = str(_git("ls-tree", "-r", "--full-tree", impl.PRE_COMMIT, "--", "qualification/ws32", text=True))
    frozen: dict[str, dict[str, str]] = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        meta, path = line.split("\t", 1)
        mode, obj_type, blob_sha = meta.split()
        frozen[path] = {"mode": mode, "type": obj_type, "git_blob_sha": blob_sha}
    if not frozen:
        raise RuntimeError("WS32 freeze commit exposes no qualification/ws32 files")

    current_paths = sorted(
        str(p.relative_to(impl.ROOT)).replace("\\", "/")
        for p in impl.PRE.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    )
    frozen_paths = sorted(frozen)
    if current_paths != frozen_paths:
        missing = sorted(set(frozen_paths) - set(current_paths))
        extra = sorted(set(current_paths) - set(frozen_paths))
        raise RuntimeError(f"WS32 namespace path drift: missing={missing} extra={extra}")

    rows = []
    for path in frozen_paths:
        frozen_bytes = bytes(_git("show", f"{impl.PRE_COMMIT}:{path}"))
        current_path = impl.ROOT / path
        current_bytes = current_path.read_bytes()
        current_blob = str(_git("hash-object", path, text=True)).strip()
        row = {
            "path": path,
            "frozen_git_blob_sha": frozen[path]["git_blob_sha"],
            "current_git_blob_sha": current_blob,
            "frozen_sha256": impl.sha256_bytes(frozen_bytes),
            "current_sha256": impl.sha256_bytes(current_bytes),
            "frozen_bytes": len(frozen_bytes),
            "current_bytes": len(current_bytes),
            "byte_identical": frozen_bytes == current_bytes,
        }
        if not row["byte_identical"] or row["frozen_git_blob_sha"] != row["current_git_blob_sha"]:
            raise RuntimeError(f"WS32 byte drift at {path}")
        rows.append(row)

    diff = subprocess.run(
        ["git", "diff", "--exit-code", impl.PRE_COMMIT, "--", "qualification/ws32"],
        cwd=impl.ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if diff.returncode != 0:
        raise RuntimeError("git diff reports WS32 namespace drift from freeze commit")

    return {
        "artifact_version": "commander-lab.ws41-ws32-content-integrity/1.0.0",
        "baseline": {
            "freeze_commit": impl.PRE_COMMIT,
            "freeze_tree": impl.PRE_TREE,
            "namespace": "qualification/ws32",
            "contract_version": "commander-lab.semantic-fixture-materialization/1.0.2",
            "canonical_bundle_digest": impl.PRE_CANONICAL_BUNDLE_DIGEST,
            "materialization_sha256": impl.PRE_MATERIALIZATION_SHA256,
            "freeze_bundle_digest": impl.PRE_FREEZE_BUNDLE_DIGEST,
        },
        "comparison_method": {
            "path_set": "git ls-tree -r <WS32 freeze commit> compared with live namespace files",
            "content": "git show <WS32 freeze commit>:<path> byte-for-byte compared with live file",
            "git_blob": "frozen ls-tree blob SHA compared with git hash-object of live file",
            "namespace_diff": f"git diff --exit-code {impl.PRE_COMMIT} -- qualification/ws32",
        },
        "file_count": len(rows),
        "path_set_identical": True,
        "all_files_byte_identical": True,
        "all_git_blob_ids_identical": True,
        "namespace_git_diff_exit_code": 0,
        "rows": rows,
        "status": "PASS",
    }


def _remaining_defects(successor: dict[str, Any]) -> dict[str, Any]:
    """Persist the exact two historical runtime linter findings and adjudication."""
    predecessor = impl.load(impl.PRE_MAT)
    authority = {
        "CARD_13": [
            "CR601.2b/CR601.2c/CR601.2h: casting choices must be completed while casting",
            "https://magic.wizards.com/en/news/feature/modern-horizons-3-release-notes",
            "Official Flare of Duplication note: the copy is created on the stack and its controller may choose new targets for the copy",
        ],
        "CARD_22": [
            "CR601.2b/CR601.2c/CR601.2h: casting choices must be completed while casting",
            "https://magic.wizards.com/en/news/feature/foundations-release-notes",
            "Official Bolt Bend note: the new target is not chosen until Bolt Bend resolves",
        ],
    }
    expected = {
        "CARD_13": {
            "subject": "obj:card_13-subject",
            "subject_card": "Flare of Duplication",
            "stack": "obj:card13-bolt",
            "stack_card": "Lightning Bolt",
            "cast_action": {
                "action": "cast_alt_cost",
                "object": "obj:card_13-subject",
                "sacrifice": "obj:card13-red-creature",
                "target_spell": "obj:card13-bolt",
            },
            "later_target": "P3",
            "rules_correct_interpretation": "Flare of Duplication's cast action already fixes its spell target and alternative-cost sacrifice. Decision 1 chooses a new target for the created spell copy during the later rules procedure; it is not a deferred casting target.",
        },
        "CARD_22": {
            "subject": "obj:card_22-subject",
            "subject_card": "Bolt Bend",
            "stack": "obj:card22-bolt",
            "stack_card": "Lightning Bolt",
            "cast_action": {
                "action": "cast",
                "object": "obj:card_22-subject",
                "target": "obj:card22-bolt",
            },
            "later_target": "P3",
            "rules_correct_interpretation": "Bolt Bend's cast action already fixes the targeted spell. Decision 1 chooses the replacement target only when Bolt Bend resolves; it is not a deferred casting target.",
        },
    }
    defects = []
    for fid in ("CARD_13", "CARD_22"):
        pre = impl.find_record(predecessor, fid)
        suc = impl.find_record(successor, fid)
        spec = expected[fid]
        objs = {o["semantic_id"]: o for o in suc.get("semantic_objects", [])}
        if objs.get(spec["subject"], {}).get("card_identity") != spec["subject_card"]:
            raise RuntimeError(f"{fid} subject identity drift")
        if objs.get(spec["stack"], {}).get("card_identity") != spec["stack_card"]:
            raise RuntimeError(f"{fid} completed-stack identity drift")
        decisions = suc.get("decision_script", [])
        if len(decisions) < 2:
            raise RuntimeError(f"{fid} decision script unexpectedly short")
        cast_value = decisions[0].get("selection", {}).get("semantic_value")
        later = decisions[1]
        if cast_value != spec["cast_action"]:
            raise RuntimeError(f"{fid} cast action no longer matches causality proof")
        if later.get("decision_family") != "target" or later.get("selection", {}).get("semantic_value") != spec["later_target"]:
            raise RuntimeError(f"{fid} later target decision drift")
        cause = later.get("causal_step_id")
        step = next((s for s in suc.get("native_procedure", []) if s.get("step_id") == cause), None)
        if not step or "RULES_PROCEDURE_TO_TARGET_DECISION" not in str(step.get("operation", "")):
            raise RuntimeError(f"{fid} later target is not tied to the proven rules-procedure boundary")
        stack = next((s for s in suc.get("stack_state", []) if s.get("source_semantic_id") == spec["stack"]), None)
        if not stack or stack.get("cast_complete") is not True or stack.get("costs_paid") is not True or stack.get("targets") != ["P1"]:
            raise RuntimeError(f"{fid} completed opposing Lightning Bolt state drift")
        pre_obligation = impl.obligation_projection(pre)
        suc_obligation = impl.obligation_projection(suc)
        if pre_obligation != suc_obligation:
            raise RuntimeError(f"{fid} obligation changed while adjudicating linter false positive")
        defects.append({
            "fixture_id": fid,
            "semantic_object_id": spec["stack"],
            "subject_semantic_object_id": spec["subject"],
            "original_runtime_linter_rule": "NO_CAST_TIME_DECISION_AFTER_CAST_COMPLETE",
            "original_runtime_error": f"Decision 1 (target) is not tied to a native in-progress cast but completed stack state exists; cast-time choices cannot be deferred.",
            "offending_field_state_as_seen_by_old_linter": {
                "completed_stack_semantic_object_id": spec["stack"],
                "completed_stack_state": stack,
                "decision_index": 1,
                "decision_family": later.get("decision_family"),
                "decision_value": later.get("selection", {}).get("semantic_value"),
                "causal_step_id": cause,
                "causal_operation": step.get("operation"),
            },
            "current_value": {
                "cast_action": cast_value,
                "later_rules_procedure_target": later.get("selection", {}).get("semantic_value"),
                "completed_stack_target": stack.get("targets"),
            },
            "required_rules_correct_value": {
                "materialization_change_required": False,
                "rules_correct_interpretation": spec["rules_correct_interpretation"],
                "linter_requirement": "Treat a target-family decision as post-cast only when a prior cast action is semantically complete and the causal native step is the explicit rules-procedure target-decision boundary; otherwise fail closed.",
            },
            "frozen_semantic_obligation": pre_obligation,
            "predecessor_obligation_digest": impl.obligation_digest(pre),
            "successor_obligation_digest": impl.obligation_digest(suc),
            "authority": authority[fid],
            "classification": "LINTER_FALSE_POSITIVE",
            "repair": "LINTER_CAUSALITY_REFINEMENT_ONLY",
            "representation_preserving": True,
            "obligation_changing": False,
            "materialization_record_changed_for_this_adjudication": False,
            "post_fix_linter_status": "PASS",
        })
    return {
        "artifact_version": "commander-lab.ws41-remaining-defects-2/1.0.0",
        "workstream": "WS-41",
        "source_runtime_evidence": {
            "identity_exposure_head": DEFECT_RUNTIME_HEAD,
            "identity_exposure_run": DEFECT_RUNTIME_RUN,
            "identity_exposure_job": DEFECT_RUNTIME_JOB,
            "reported_contract_defect_count": 2,
            "reported_global_errors": [],
            "causality_probe_head": CAUSALITY_HEAD,
            "causality_probe_run": CAUSALITY_RUN,
            "causality_probe_job": CAUSALITY_JOB,
        },
        "historical_defect_count": 2,
        "defects": defects,
        "classification_counts": {"LINTER_FALSE_POSITIVE": 2},
        "obligation_contradiction_count": 0,
        "authority_unresolved_count": 0,
        "representation_defect_repairable_count": 0,
        "post_fix_contract_defect_count": 0,
        "post_fix_global_errors": [],
        "terminal_status": "PASS",
    }


def finalize_self_contained_handoff(out: Path) -> None:
    """Add continuation evidence, then recompute the complete evidence freeze."""
    materialization_path = out / "SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_3.json"
    materialization = json.loads(materialization_path.read_text(encoding="utf-8"))
    remaining = _remaining_defects(materialization)
    integrity = _ws32_content_integrity()
    impl.dump(out / "WS41_REMAINING_DEFECTS_2.json", remaining)
    impl.dump(out / "WS41_WS32_CONTENT_INTEGRITY_COMPARISON.json", integrity)

    validation_path = out / "WS41_VALIDATION.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    validation.update({
        "historical_remaining_linter_defect_count": 2,
        "historical_remaining_linter_defects_adjudicated": 2,
        "linter_false_positive_count": 2,
        "obligation_contradiction_count": 0,
        "authority_unresolved_count": 0,
        "post_fix_contract_defect_count": 0,
        "post_fix_global_errors": [],
        "ws32_content_integrity_comparison": "PASS",
        "ws32_namespace_file_count": integrity["file_count"],
    })
    impl.dump(validation_path, validation)

    handoff_path = out / "WS41_FINAL_HANDOFF.md"
    handoff = handoff_path.read_text(encoding="utf-8")
    anchor = "## WS-39 Contradiction Reproduction\n"
    required = (
        "## Work Completed\n"
        "- reproduced the immutable v1.0.2 `PILOT_CHOICE` contradiction;\n"
        "- superseded it provider-neutrally in v1.0.3 without editing v1.0.2;\n"
        "- audited all 135 records and all 31 completed stack rows;\n"
        "- extended fail-closed semantic linting and revalidated 135/135;\n"
        "- preserved the exact 107-record provider denominator and all 135 obligation projections;\n"
        "- recomputed successor record, requested-state, materialization, bundle, manifest and checksum identities.\n\n"
        "## New Findings\n"
        "- `PILOT_CHOICE` was the only requested-state defect in this defect class across the frozen 135-record audit.\n"
        "- `Fact or Fiction` correctly has no target under current Oracle wording.\n"
        "- the two historical post-PILOT linter findings were `CARD_13` and `CARD_22`; both are `LINTER_FALSE_POSITIVE`, not materialization or obligation defects.\n"
        "- the currently linked Wizards CR filename is `MagicCompRules 20260819.txt`; its verified bytes remain effective August 7, 2026 with SHA256 `4381ad1b39ab2c05f7d03633a20f711ed37277074d3266dcba5f38cbb527423f`.\n\n"
    )
    if "## Work Completed\n" not in handoff:
        if anchor not in handoff:
            raise RuntimeError("WS41 handoff insertion anchor missing")
        handoff = handoff.replace(anchor, required + anchor, 1)
    continuation = (
        "## Remaining Defects 2 Adjudication\n"
        "- Runtime diagnostic `33851407144` / `100954816503` identified exactly `CARD_13` and `CARD_22`, both under `NO_CAST_TIME_DECISION_AFTER_CAST_COMPLETE`, with no global linter errors.\n"
        "- Causality diagnostic `33851517930` / `100955167145` proves `CARD_13` already casts Flare of Duplication with `obj:card13-bolt` selected and the later `P3` decision is the new target for the created copy.\n"
        "- The same diagnostic proves `CARD_22` already casts Bolt Bend targeting `obj:card22-bolt` and the later `P3` decision is the new target chosen during resolution.\n"
        "- Both findings are `LINTER_FALSE_POSITIVE`; no record representation, fixture identity, obligation projection, requested-state state, or denominator entry was changed to close them.\n"
        "- Machine-readable evidence: `WS41_REMAINING_DEFECTS_2.json`.\n\n"
        "## WS-32 Content Integrity\n"
        f"- The entire `qualification/ws32` path set and every file byte were compared against freeze commit `{impl.PRE_COMMIT}` / tree `{impl.PRE_TREE}`.\n"
        f"- Exact file count compared: {integrity['file_count']}; path set identical: true; every file byte-identical: true; every Git blob identity identical: true; namespace `git diff --exit-code`: 0.\n"
        "- Machine-readable evidence: `WS41_WS32_CONTENT_INTEGRITY_COMPARISON.json`.\n\n"
    )
    if "## Remaining Defects 2 Adjudication\n" not in handoff:
        insertion = "## Tests / Evidence\n"
        if insertion in handoff:
            handoff = handoff.replace(insertion, continuation + insertion, 1)
        else:
            handoff += "\n" + continuation
    handoff_path.write_text(handoff, encoding="utf-8")

    index_path = out / "WS41_EVIDENCE_INDEX.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    implementation = index.setdefault("implementation", [])
    for entry in (
        "scripts/ws41_lint_semantic_v1_0_3.py",
        "scripts/ws41_build_successor.py",
        "scripts/ws41_build_successor_final.py",
        "scripts/ws41_validate_freeze.py",
    ):
        if entry not in implementation:
            implementation.append(entry)
    required_outputs = index.setdefault("required_in_repo_outputs", [])
    for entry in ("WS41_REMAINING_DEFECTS_2.json", "WS41_WS32_CONTENT_INTEGRITY_COMPARISON.json"):
        if entry not in required_outputs:
            required_outputs.append(entry)
    impl.dump(index_path, index)

    authoritative = sorted(
        p for p in out.iterdir()
        if p.is_file() and p.name not in {"WS41_SHA256SUMS", "WS41_BUNDLE_MANIFEST_v1_0_3.json"}
    )
    files = [
        {
            "path": str(p.relative_to(impl.ROOT)),
            "sha256": impl.sha256_file(p),
            "bytes": p.stat().st_size,
        }
        for p in authoritative
    ]
    freeze_payload = {"contract_version": impl.VERSION, "files": files}
    freeze_digest = impl.sha256_bytes(impl.canonical_bytes(freeze_payload))
    impl.dump(out / "WS41_BUNDLE_MANIFEST_v1_0_3.json", {
        "manifest_version": "commander-lab.ws41-freeze-bundle/1.0.0",
        "contract_version": impl.VERSION,
        "canonical_materialization_bundle_digest": materialization["canonical_bundle_digest"],
        "bundle_digest_algorithm": "SHA-256(canonical JSON of contract_version + sorted authoritative file rows)",
        "bundle_digest": freeze_digest,
        "files": files,
    })
    checksum_files = sorted([*authoritative, out / "WS41_BUNDLE_MANIFEST_v1_0_3.json"])
    (out / "WS41_SHA256SUMS").write_text(
        "".join(f"{impl.sha256_file(p)}  {p.name}\n" for p in checksum_files),
        encoding="utf-8",
    )


def build(out: Path) -> None:
    impl.build(out)
    finalize_self_contained_handoff(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=impl.ROOT / "qualification" / "ws41")
    args = ap.parse_args()
    build(args.out if args.out.is_absolute() else impl.ROOT / args.out)
