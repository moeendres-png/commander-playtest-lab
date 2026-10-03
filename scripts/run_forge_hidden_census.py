#!/usr/bin/env python3
"""Forge AF05 hidden-information census (#458).

Classifies every mandatory AF05 HIDDEN row of the effective FULL107
denominator against the pinned Forge bridge and writes the matrix to
``docs/forge_af05_hidden_20261003/FORGE_AF05_MATRIX.json``.

The bridge source is read from git blobs at the canonical bridge commit
(``bridge_launcher.canonical_forge_authority``), never from a working tree, so
the census is bound to exactly the bytes the lane runs. Any asserted channel
that no longer matches those blobs aborts the census (``HiddenChannelDrift``).

This executes no row and writes no receipt: a classified row earns no credit.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from commander_lab.qualification.current_boundary import (  # noqa: E402
    forge_hidden_information as forge_hidden_mod,
)
from commander_lab.qualification.current_boundary.bridge_launcher import (  # noqa: E402
    canonical_forge_authority,
)
from commander_lab.qualification.current_boundary.materialization import (  # noqa: E402
    load_effective_materialization,
)

DEFAULT_OUT = REPO_ROOT / "docs" / "forge_af05_hidden_20261003" / "FORGE_AF05_MATRIX.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--forge-root",
        type=Path,
        default=os.environ.get("FORGE_WORKSPACE"),
        help="a Forge git repository holding the pinned bridge commit (no ambient default)",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    if args.forge_root is None:
        print(
            "--forge-root (or FORGE_WORKSPACE) is required: the census reads the pinned "
            "bridge blobs from an explicit Forge repository",
            file=sys.stderr,
        )
        return 2

    bridge_commit = canonical_forge_authority()["bridge_commit"]
    materialization = load_effective_materialization(REPO_ROOT)
    records = {record["fixture_id"]: record for record in materialization.denominator_records()}
    matrix = forge_hidden_mod.build_matrix(records, Path(args.forge_root), bridge_commit)
    identity = materialization.receipt()
    matrix["contract_id"] = identity["contract_id"]
    matrix["canonical_bundle_digest"] = identity["canonical_bundle_digest"]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(matrix, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(matrix["summary"], sort_keys=True))
    print("matrix written to", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
