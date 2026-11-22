"""Pins the committed results of wave 2 of the second rating of H (Refs #1404).

The report ``docs/analysis-reports/rating_full_second_run_20261122.md`` quotes numbers from the
committed ``result.json``; the data folder carries two checksum lists. This test checks the files
against both lists and the core numbers of the report against ``result.json``, so a changed file or
a changed number in the report turns red.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "research" / "chulane_rubric_v2_20261118" / "second_run_full_20261122"
REPORT = ROOT / "docs" / "analysis-reports" / "rating_full_second_run_20261122.md"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sums(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, name = line.split(maxsplit=1)
            out[name.lstrip("*")] = digest
    return out


def _result() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((DATA / "result.json").read_text(encoding="utf-8"))
    return data


def _de(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}".replace(".", ",").replace("-", "\u2212")


@pytest.mark.parametrize("listing", ["results_sha256.txt", "rater/output_sha256.txt"])
def test_committed_files_match_their_checksum_list(listing: str) -> None:
    path = DATA / listing
    sums = _sums(path)
    assert sums
    for name, digest in sums.items():
        assert _sha256(path.parent / name) == digest, name


def test_checksum_lists_cover_results_and_outputs() -> None:
    results = _sums(DATA / "results_sha256.txt")
    for name in ("result.json", "pooled.jsonl", "hits.json", "klassifikation.json"):
        assert name in results
    outputs = _sums(DATA / "rater" / "output_sha256.txt")
    assert sorted(outputs) == [f"rr2_output_{k}.jsonl" for k in range(1, 9)]
    # the posted SHA-256 of the evaluation result (#1404 comment 7085556215)
    assert results["result.json"].startswith("3f17940e")
    assert results["pooled.jsonl"].startswith("3e6d82d0")
    assert results["hits.json"].startswith("edd99934")


def test_core_numbers_of_the_report_come_from_result_json() -> None:
    r = _result()
    text = REPORT.read_text(encoding="utf-8")
    spells = r["spells_test"]
    assert spells["verdict"] == "bestaetigt"
    lo, hi = spells["ci95_cluster"]
    assert f"b = **{_de(spells['b_W2'])} [{_de(lo)}; {_de(hi)}]**" in text
    assert f"b < 0 in **{spells['chunks_negative']} von {spells['m']}** Chargen" in text
    pairs = r["paare"]
    assert f"**{pairs['n']} von {pairs['N']}**" in text
    devs = r["abweichungen_ge15"]
    n30 = sum(1 for d in devs if abs(d["H_R2"] - d["H_F1"]) >= 30)
    assert f"**{len(devs)} von {pairs['N']}**" in text
    assert f"davon |d| ≥ 30: {n30}." in text
    assert f"Die {n30} Karten mit |d| ≥ 30" in text
    assert r["gueltige_chargen"]["m"] == 7
    assert "7 von 7 Chargen gültig (m = 7)" in text
    claims = r["regelclaims"]
    assert (
        claims["welle2"]["offensichtlich_falsch"] == 0
        and claims["F1"]["offensichtlich_falsch"] == 0
    )
    assert r["B2_G1"]["urteil"].startswith("unbelegt")
