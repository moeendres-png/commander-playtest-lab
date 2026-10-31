"""``scripts/pilot_dump_reach.py`` counts decisions per open pilot item on a full dump.

The recorded fixture (2 real-pod games, ``pilot_request_corpus.py record``) is the input: the
counts are those of the recorded rows, so a change of the counting rules shows up here. The
fixture is a sample, not a full dump, so the tests wrap its rows in the header a full dump has.
"""

from __future__ import annotations

import gzip
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/pilot_real_requests/real_pod_v1.jsonl.gz"


def _module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "pilot_dump_reach", ROOT / "scripts/pilot_dump_reach.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path: Path, header: dict[str, Any], rows: list[dict[str, Any]]) -> Path:
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for item in (header, *rows):
            handle.write(json.dumps(item) + "\n")
    return path


def _full_slice(path: Path, rows: list[dict[str, Any]], **header: Any) -> Path:
    """A full-dump file the way ``record --all`` writes it, holding ``rows``."""
    head = {
        "corpus_version": 1,
        "kind": "full",
        "pod": "real",
        "seeds": sorted({int(r["seed"]) for r in rows}),
        "games_decisions": len(rows),
        "jar_sha256": "a" * 64,
        **header,
    }
    return _write(path, head, rows)


def test_counts_on_the_recorded_fixture(tmp_path: Path) -> None:
    module = _module()
    _, fixture_rows = module.load_dump(FIXTURE)
    full = _full_slice(tmp_path / "full.jsonl.gz", fixture_rows)
    _, rows, size = module.load_slices([full])
    result = module.analyze(rows, size)
    assert result["games"] == 2 and result["decisions"] == 399
    assert result["classes"]["priority"] == 80 and result["classes"]["mana_payment"] == 60
    reach = result["reach"]
    assert reach["P0-2_threat_ladder"]["target_total"] == 40
    assert reach["P0-2_threat_ladder"]["target_multi_option"] == 26
    assert reach["P0-3_trigger_order"]["trigger_multi_option"] == 7
    assert reach["P1-2_timing_remainder"]["precombat_noninstant_casts"] == 11
    assert reach["P3_costed_may_remainder"]["choose_use_costed_prompt"] == 4
    assert reach["P4_fast_path"]["share_pct"] == 15.0
    assert result["phase4a"]["instant_casts_total"] == 1
    # what a dump cannot count is named, never zero
    assert "NOT_COUNTABLE" in reach["P6_instrumentation"]["rule"]
    assert "NOT_COUNTABLE" in reach["mana_hold"]["rule"]


def test_slices_of_one_run_count_like_the_whole(tmp_path: Path) -> None:
    module = _module()
    _, rows = module.load_dump(FIXTURE)
    first = _full_slice(tmp_path / "a.jsonl.gz", [r for r in rows if int(r["seed"]) == 1])
    second = _full_slice(tmp_path / "b.jsonl.gz", [r for r in rows if int(r["seed"]) == 2])
    _, whole, size = module.load_slices([_full_slice(tmp_path / "whole.jsonl.gz", rows)])
    _, sliced, sliced_size = module.load_slices([first, second])
    whole_result = module.analyze(whole, size)
    sliced_result = module.analyze(sliced, sliced_size)
    for key in ("games", "decisions", "classes", "phase4a", "seeds"):
        assert sliced_result[key] == whole_result[key]
    assert sliced_result["reach"]["P4_fast_path"] == whole_result["reach"]["P4_fast_path"]


def test_slices_of_different_jars_are_refused(tmp_path: Path) -> None:
    module = _module()
    _, rows = module.load_dump(FIXTURE)
    first = _full_slice(tmp_path / "a.jsonl.gz", [r for r in rows if int(r["seed"]) == 1])
    second = _full_slice(
        tmp_path / "b.jsonl.gz", [r for r in rows if int(r["seed"]) == 2], jar_sha256="0" * 64
    )
    with pytest.raises(ValueError, match="another jar"):
        module.load_slices([first, second])
    assert module.main([str(first), str(second)]) == 2


def test_a_sample_is_refused_as_a_dump() -> None:
    """The recorded fixture is a sample (header says 5253 decisions, 424 rows follow)."""
    module = _module()
    with pytest.raises(ValueError, match="not a full dump"):
        module.load_slices([FIXTURE])
    assert module.main([str(FIXTURE)]) == 2


def test_the_same_slice_twice_is_refused(tmp_path: Path) -> None:
    module = _module()
    _, rows = module.load_dump(FIXTURE)
    one = _full_slice(tmp_path / "a.jsonl.gz", [r for r in rows if int(r["seed"]) == 1])
    with pytest.raises(ValueError, match="seed 1 is in both"):
        module.load_slices([one, one])
    copy = tmp_path / "copy.jsonl.gz"
    copy.write_bytes(one.read_bytes())
    with pytest.raises(ValueError, match="seed 1 is in both"):
        module.load_slices([one, copy])
    assert module.main([str(one), str(copy)]) == 2


def test_a_row_count_that_differs_from_the_header_is_refused(tmp_path: Path) -> None:
    module = _module()
    _, rows = module.load_dump(FIXTURE)
    seed1 = [r for r in rows if int(r["seed"]) == 1]
    truncated = _full_slice(tmp_path / "t.jsonl.gz", seed1[:-1], games_decisions=len(seed1))
    with pytest.raises(ValueError, match="rows but its header says"):
        module.load_slices([truncated])


def test_disjoint_full_slices_add_up(tmp_path: Path) -> None:
    module = _module()
    _, rows = module.load_dump(FIXTURE)
    first = _full_slice(tmp_path / "a.jsonl.gz", [r for r in rows if int(r["seed"]) == 1])
    second = _full_slice(tmp_path / "b.jsonl.gz", [r for r in rows if int(r["seed"]) == 2])
    _, sliced, _ = module.load_slices([first, second])
    assert len(sliced) == len(rows)
