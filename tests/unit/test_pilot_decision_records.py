"""Disk-backed reports retain the semantics of in-memory decision records."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts.pilot_decision_records import DiskRecords, IndexedRecords

from tests.unit.test_pilot_decision_report_cancelled_casts import _cancel, _cast, pdr


def test_summary_parity_with_interleaved_cancellation_and_snapshot(tmp_path: Path) -> None:
    records = [_cast("Lightning Bolt"), _cast("Counterspell", seat=1), _cancel()]
    expected = pdr.summarize(records, 4)
    with DiskRecords(tmp_path / "records.sqlite") as disk:
        for record in records:
            disk.append(record)
        records[0]["request"]["decision_class"] = "changed after append"
        assert pdr.summarize(disk, 4) == expected
        assert pdr._cancelled_cast_attempts(disk) == {2: 0}
        view = IndexedRecords(disk, [0, 2])
        assert pdr._cancelled_cast_attempts(view) == {1: 0}
        assert expected["by_seat"]["1"]["mana_payments_cancelled"] == 1


def test_close_commits_final_partial_batch(tmp_path: Path) -> None:
    path = tmp_path / "records.sqlite"
    with DiskRecords(path, batch_size=2) as disk:
        for i in range(3):
            disk.append({"number": i})
    with DiskRecords(path) as reopened:
        assert list(reopened) == [{"number": 0}, {"number": 1}, {"number": 2}]
        reopened.append({"number": 3})
        assert reopened[-1] == {"number": 3}
        with pytest.raises(IndexError):
            _ = reopened[4]


def test_indexed_view_reads_only_requested_record() -> None:
    class GuardedSequence:
        def __len__(self):
            return 10000

        def __getitem__(self, index):
            assert index == 9999
            return {"index": index}

    view = IndexedRecords(GuardedSequence(), [9999])
    assert view[0] == {"index": 9999}


def test_failed_game_summarizes_and_removes_store(tmp_path: Path, monkeypatch) -> None:
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))

    class Runner:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, **kwargs):
            pdr.ExternalPilotDecisionPolicy.decide(None, _cast("Lightning Bolt")["request"])
            raise RuntimeError("game failure")

    monkeypatch.setattr(pdr, "XmageFullGameRunner", Runner)
    monkeypatch.setattr(
        pdr.ExternalPilotDecisionPolicy,
        "decide",
        lambda self, request: {"selected_option_ids": ["spell"]},
    )
    scenario = SimpleNamespace(model_copy=lambda update: SimpleNamespace(**update))
    row = pdr._play(("java",), "pod", (scenario, ("a", "b"), ()), 1)
    assert row["status"] == "failed"
    assert row["decisions"] == 1
    assert list(tmp_path.iterdir()) == []
