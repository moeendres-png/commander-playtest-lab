from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from commander_lab.engine.structural import ENGINE_VERSION, FIDELITY_ENGINE_VERSION


def test_structural_cyclic_seat_permutations_are_equivariant(
    repo_root: Path, tmp_path: Path
) -> None:
    output = tmp_path / "seat-symmetry"
    subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts/audit_structural_seat_symmetry.py"),
            "--root",
            str(repo_root),
            "--output",
            str(output),
        ],
        cwd=repo_root,
        check=True,
    )
    report = json.loads((output / "SEAT_SYMMETRY_AUDIT.json").read_text(encoding="utf-8"))
    assert ENGINE_VERSION == "structural-0.6.2"
    assert FIDELITY_ENGINE_VERSION == "structural-fidelity-overlay-2026-08-25-v2"
    assert report["seat_symmetry"] == "PASS"
    assert report["comparisons"] == 24
    assert report["equivariant_comparisons"] == 24
    assert report["mismatch_count"] == 0
