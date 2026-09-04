#!/usr/bin/env python3
"""Terminal WS-41 builder entrypoint bound to the freshly reverified Wizards rules link."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import ws41_build_successor as impl

# Fresh direct probe of https://magic.wizards.com/en/rules on 2026-09-04.
# The currently linked filename advanced to 20260819, while the bytes remain
# the Comprehensive Rules effective August 7, 2026 with the same frozen SHA.
impl.CURRENT_CR_URL = "https://media.wizards.com/2026/downloads/MagicCompRules%2020260819.txt"
impl.CURRENT_CR_EFFECTIVE = "2026-08-07"
impl.CURRENT_CR_SHA256 = "4381ad1b39ab2c05f7d03633a20f711ed37277074d3266dcba5f38cbb527423f"


def finalize_self_contained_handoff(out: Path) -> None:
    """Add project-mandated handoff headings and bind the final wrapper in evidence.

    The semantic materialization is untouched. Because the handoff/evidence
    index are themselves frozen evidence files, recompute the WS41 evidence
    manifest and checksum set after these deterministic documentation changes.
    """
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
        "- `CARD_13` and `CARD_22` later `target` decisions are rules-procedure choices after complete cast actions, not deferred cast-time targets; the linter distinguishes these shapes causally rather than allowing a generic fallback.\n"
        "- the currently linked Wizards CR filename is `MagicCompRules 20260819.txt`; its verified bytes remain effective August 7, 2026 with SHA256 `4381ad1b39ab2c05f7d03633a20f711ed37277074d3266dcba5f38cbb527423f`.\n\n"
    )
    if "## Work Completed\n" not in handoff:
        if anchor not in handoff:
            raise RuntimeError("WS41 handoff insertion anchor missing")
        handoff = handoff.replace(anchor, required + anchor, 1)
        handoff_path.write_text(handoff, encoding="utf-8")

    index_path = out / "WS41_EVIDENCE_INDEX.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    implementation = index.setdefault("implementation", [])
    wrapper = "scripts/ws41_build_successor_final.py"
    if wrapper not in implementation:
        implementation.append(wrapper)
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
    materialization = json.loads((out / "SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_3.json").read_text(encoding="utf-8"))
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
