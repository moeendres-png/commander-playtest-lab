"""Shared helpers for Q6 scaffolding tests (test-only support code).

These helpers drive the pipeline over the committed bounded fixture sample.
They contain no legality, no expected outcomes, and no behavior judgments:
fixtures are real card scripts used as parser/classifier inputs only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from q6_scaffolding import cli  # noqa: E402

FIXTURES = REPO_ROOT / "tests" / "q6_scaffolding" / "fixtures"
INPUTS_SPEC = FIXTURES / "inputs.json"
CARDS_DIR = FIXTURES / "cards"


def run_pipeline(tmp_path: Path, manifest_id: str = "q6-test"):
    """Run the full CLI pipeline over the fixture sample into tmp_path."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    intake_p = tmp_path / "intake.json"
    classified_p = tmp_path / "classified.json"
    skel_p = tmp_path / "skel.json"
    queues_p = tmp_path / "queues.json"
    manifest_p = tmp_path / "manifest.json"
    assert (
        cli.main(
            [
                "intake",
                "--inputs",
                str(INPUTS_SPEC),
                "--corpus-root",
                str(REPO_ROOT),
                "--out",
                str(intake_p),
            ]
        )
        == 0
    )
    assert cli.main(["classify", "--in", str(intake_p), "--out", str(classified_p)]) == 0
    assert cli.main(["generate-skeletons", "--in", str(classified_p), "--out", str(skel_p)]) == 0
    assert cli.main(["build-review-queues", "--in", str(skel_p), "--out", str(queues_p)]) == 0
    assert (
        cli.main(
            [
                "build-manifest",
                "--in",
                str(skel_p),
                "--queues",
                str(queues_p),
                "--manifest-id",
                manifest_id,
                "--out",
                str(manifest_p),
            ]
        )
        == 0
    )
    assert cli.main(["validate", "--manifest", str(manifest_p), "--queues", str(queues_p)]) == 0
    return {
        "intake": json.loads(intake_p.read_text()),
        "classified": json.loads(classified_p.read_text()),
        "skeletons": json.loads(skel_p.read_text()),
        "queues": json.loads(queues_p.read_text()),
        "manifest": json.loads(manifest_p.read_text()),
    }


def by_name(records, name):
    for record in records:
        if record.get("card_name_hint") == name:
            return record
    raise AssertionError(f"card not found in records: {name}")
