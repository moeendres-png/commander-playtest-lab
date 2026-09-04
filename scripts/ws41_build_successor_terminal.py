#!/usr/bin/env python3
"""Terminal WS-41 evidence builder that binds the immutable downstream source lock."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import ws41_build_successor_final as final

impl = final.impl
SUCCESSOR_SOURCE_LOCK_COMMIT = "24152acf36b5a560c23ccacfed3f31d3039537eb"
SUCCESSOR_SOURCE_LOCK_TREE = "428bbe58b2ea7b869200521092a8768108029b47"
# Terminal owner-authored CI trigger: source-only comment; generated freeze bytes must not change.


def finalize_source_lock(out: Path) -> None:
    materialization = json.loads((out / "SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_3.json").read_text(encoding="utf-8"))

    validation_path = out / "WS41_VALIDATION.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    validation["successor_contract_source_lock"] = {
        "repository": "moeendres-png/commander-playtest-lab",
        "branch": "ws41/successor-contract-v1.0.3-freeze",
        "commit": SUCCESSOR_SOURCE_LOCK_COMMIT,
        "tree": SUCCESSOR_SOURCE_LOCK_TREE,
        "namespace": "qualification/ws41",
        "contract_version": impl.VERSION,
        "canonical_materialization_bundle_digest": materialization["canonical_bundle_digest"],
        "materialization_sha256": impl.sha256_file(out / "SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_3.json"),
        "provider_denominator": 107,
        "downstream_instruction": "WS-40 and fresh XMage successor qualification must consume this exact Git source lock; terminal WS-41 attestation commits after it may not alter canonical semantic materialization bytes.",
    }
    impl.dump(validation_path, validation)

    handoff_path = out / "WS41_FINAL_HANDOFF.md"
    handoff = handoff_path.read_text(encoding="utf-8")
    section = (
        "## Successor Contract Source Lock\n"
        f"- repository: `moeendres-png/commander-playtest-lab`\n"
        f"- branch: `ws41/successor-contract-v1.0.3-freeze`\n"
        f"- immutable downstream source-lock commit: `{SUCCESSOR_SOURCE_LOCK_COMMIT}`\n"
        f"- source-lock tree: `{SUCCESSOR_SOURCE_LOCK_TREE}`\n"
        f"- namespace: `qualification/ws41`\n"
        f"- contract: `{impl.VERSION}`\n"
        f"- canonical materialization bundle digest: `{materialization['canonical_bundle_digest']}`\n"
        f"- materialization SHA256: `{impl.sha256_file(out / 'SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_3.json')}`\n"
        "- provider successor denominator: `107`\n"
        "- WS-40 and the fresh XMage successor qualification must consume this exact commit/tree. Later WS-41 terminal-attestation commits are evidence-only and must reproduce identical canonical semantic materialization bytes.\n\n"
    )
    if "## Successor Contract Source Lock\n" not in handoff:
        marker = "## Work Completed\n"
        if marker not in handoff:
            raise RuntimeError("WS41 handoff Work Completed anchor missing")
        handoff = handoff.replace(marker, section + marker, 1)
        handoff_path.write_text(handoff, encoding="utf-8")

    index_path = out / "WS41_EVIDENCE_INDEX.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    terminal_builder = "scripts/ws41_build_successor_terminal.py"
    implementation = index.setdefault("implementation", [])
    if terminal_builder not in implementation:
        implementation.append(terminal_builder)
    impl.dump(index_path, index)

    authoritative = sorted(
        p for p in out.iterdir()
        if p.is_file() and p.name not in {"WS41_SHA256SUMS", "WS41_BUNDLE_MANIFEST_v1_0_3.json"}
    )
    files = [
        {"path": str(p.relative_to(impl.ROOT)), "sha256": impl.sha256_file(p), "bytes": p.stat().st_size}
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
    final.build(out)
    finalize_source_lock(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=impl.ROOT / "qualification" / "ws41")
    args = ap.parse_args()
    build(args.out if args.out.is_absolute() else impl.ROOT / args.out)
