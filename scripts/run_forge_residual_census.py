#!/usr/bin/env python3
"""Forge AF06/AF08 residual census (#459).

Classifies every micro-rules, pilot-decision and WS05 row of the effective
FULL107 denominator by its first missing Forge mechanism and writes the matrix
to ``docs/forge_af06_af08_residuals_20261003/FORGE_RESIDUAL_MATRIX.json``.

The classification is static: it reads the Forge scenario lane's own model and
the record's obligation tokens. It executes no row and writes no receipt.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from commander_lab.qualification.current_boundary import (  # noqa: E402
    forge_residuals as forge_residuals_mod,
)
from commander_lab.qualification.current_boundary.materialization import (  # noqa: E402
    load_effective_materialization,
)

DEFAULT_OUT = (
    REPO_ROOT / "docs" / "forge_af06_af08_residuals_20261003" / "FORGE_RESIDUAL_MATRIX.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    materialization = load_effective_materialization(REPO_ROOT)
    records = {record["fixture_id"]: record for record in materialization.denominator_records()}
    scope = sorted(fixture for fixture in records if forge_residuals_mod.in_scope(fixture))
    matrix = forge_residuals_mod.build_matrix(records, scope)
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
