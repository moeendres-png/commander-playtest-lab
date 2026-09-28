"""Each clustered failure must remain uniquely attributable to its evidence."""

import copy
import itertools
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from foundry import cluster_failures as subject


def record(identity="R1", message="timeout at /a/test.py:12"):
    return {"id": identity, "message": message, "evidence": "logs/run.txt", "verdict": "FAIL"}


def test_duplicate_identity_rejected():
    with pytest.raises(ValueError):
        subject.cluster([record(), record(message="different failure")])


@pytest.mark.parametrize(
    "value", [None, {}, {"id": "R1"}, {"id": "R1", "message": None, "evidence": "log"}]
)
def test_unattributable_record_rejected(value):
    with pytest.raises(ValueError):
        subject.cluster([value])


def test_permutations_have_identical_output():
    records = [record("R2"), record("R1"), record("R3", "different")]
    assert subject.cluster(records) == subject.cluster(list(reversed(records)))


def test_valid_control():
    result = subject.cluster([record("R1"), record("R2")])
    assert len(result) == 1 and result[0]["count"] == 2
    assert [r["id"] for r in result[0]["members"]] == ["R1", "R2"]


def test_partition_preserves_every_reference_and_verdict_without_mutation():
    records = [record("A"), record("B"), record("C", "other cause")]
    records[0]["evidence"] = "opaque://logs/a file#frag"
    records[0]["verdict"] = "PARTIAL"
    del records[1]["verdict"]
    before = copy.deepcopy(records)
    for permutation in itertools.permutations(records):
        result = subject.cluster(list(permutation))
        assert result == subject.cluster(records)
        members = [member for group in result for member in group["members"]]
        assert sum(group["count"] for group in result) == len(records)
        assert len({member["id"] for member in members}) == len(records)
        for source in records:
            member = next(member for member in members if member["id"] == source["id"])
            assert member == {
                "id": source["id"],
                "evidence": source["evidence"],
                "verdict": source.get("verdict", "UNKNOWN"),
            }
    assert records == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", " R1"),
        ("id", True),
        ("message", []),
        ("evidence", None),
        ("evidence", {"private": "PRIVATE_SENTINEL"}),
        ("verdict", None),
        ("verdict", " "),
    ],
)
def test_invalid_fields_fail_without_values_in_errors(field, value):
    bad = record()
    bad[field] = value
    with pytest.raises(ValueError) as error:
        subject.cluster([bad])
    assert "PRIVATE_SENTINEL" not in str(error.value)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"PRIVATE_SENTINEL":',
        b"PRIVATE_SENTINEL\xff",
        b'[{"id":"A","id":"B","message":"x","evidence":"log"}]',
        b"[NaN]",
        b"[" * 2000,
    ],
)
def test_unreadable_cli_input_keeps_previous_report(tmp_path, capsys, raw):
    source = tmp_path / "input.json"
    source.write_bytes(raw)
    output = tmp_path / "output.json"
    output.write_text("previous report")
    assert subject.main(["--input", str(source), "--output", str(output)]) == 1
    captured = capsys.readouterr()
    assert not captured.out and "CLUSTER_INVALID" in captured.err
    assert "PRIVATE_SENTINEL" not in captured.err
    assert output.read_text() == "previous report"


def test_late_duplicate_publishes_no_partial_output(tmp_path, capsys):
    source = tmp_path / "input.json"
    source.write_text(json.dumps([record("A"), record("B"), record("A", "different")]))
    output = tmp_path / "output.json"
    assert subject.main(["--input", str(source), "--output", str(output)]) == 1
    assert not output.exists()
    assert not capsys.readouterr().out


def test_empty_input_and_valid_cli(tmp_path, capsys):
    assert subject.cluster([]) == []
    source = tmp_path / "input.json"
    source.write_text(json.dumps([record("A"), record("B")]))
    assert subject.main(["--input", str(source)]) == 0
    assert json.loads(capsys.readouterr().out)["clusters"][0]["count"] == 2


def test_output_does_not_destroy_input(tmp_path):
    source = tmp_path / "input.json"
    source.write_text(json.dumps([record()]))
    original = source.read_bytes()
    assert subject.main(["--input", str(source), "--output", str(source)]) == 1
    assert source.read_bytes() == original


def test_output_failure_is_structured(tmp_path, capsys):
    source = tmp_path / "input.json"
    source.write_text(json.dumps([record()]))
    assert subject.main(["--input", str(source), "--output", str(tmp_path / "missing/out")]) == 1
    captured = capsys.readouterr()
    assert not captured.out and "CLUSTER_INVALID" in captured.err


@pytest.mark.parametrize("link", ["hard", "symbolic"])
def test_input_alias_protection(tmp_path, link):
    source = tmp_path / "input.json"
    source.write_text(json.dumps([record()]))
    alias = tmp_path / "alias.json"
    try:
        if link == "hard":
            os.link(source, alias)
        else:
            alias.symlink_to(source)
    except OSError:
        pytest.skip("filesystem link support unavailable")
    before = source.read_bytes()
    assert subject.main(["--input", str(source), "--output", str(alias)]) == 1
    assert source.read_bytes() == before


def test_atomic_publication_failure_preserves_report(tmp_path, monkeypatch, capsys):
    source = tmp_path / "input.json"
    source.write_text(json.dumps([record()]))
    output = tmp_path / "output.json"
    output.write_text("old report")

    def fail(*args):
        raise OSError("PRIVATE_SENTINEL")

    monkeypatch.setattr(subject.os, "replace", fail)
    assert subject.main(["--input", str(source), "--output", str(output)]) == 1
    assert output.read_text() == "old report"
    assert not list(tmp_path.glob(".failure-clusters-*"))
    assert "PRIVATE_SENTINEL" not in capsys.readouterr().err


def test_successful_file_publication(tmp_path):
    source = tmp_path / "input.json"
    source.write_text(json.dumps([record("B"), record("A")]))
    output = tmp_path / "output.json"
    assert subject.main(["--input", str(source), "--output", str(output)]) == 0
    assert json.loads(output.read_text())["clusters"] == subject.cluster([record("A"), record("B")])
    assert not list(tmp_path.glob(".failure-clusters-*"))
