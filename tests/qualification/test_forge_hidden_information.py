"""Forge AF05 per-row classification (#458): exact gaps, never credit."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from commander_lab.qualification.current_boundary import forge_hidden_information as fh
from commander_lab.qualification.current_boundary import gate_derivations, knowledge_projection
from commander_lab.qualification.current_boundary.materialization import (
    load_effective_materialization,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def records() -> dict[str, dict]:
    materialization = load_effective_materialization(REPO_ROOT)
    return {record["fixture_id"]: record for record in materialization.denominator_records()}


def _texts() -> dict[str, str]:
    """Source texts that satisfy every channel assertion exactly."""
    texts = {key: "" for key in fh.SOURCES}
    for channel in fh.CHANNELS:
        texts[channel.source] += "\n".join(channel.present) + "\n"
    return texts


def test_every_mandatory_hidden_row_is_classified(records) -> None:
    hidden = sorted(fixture for fixture in records if fixture.startswith("HIDDEN_"))
    assert hidden == sorted(knowledge_projection.ROWS)
    for fixture in hidden:
        row = fh.classify_row(records[fixture])
        assert row.obligation_kind == knowledge_projection.ROWS[fixture]
        assert row.classification == fh.PROVIDER_ADAPTER_GAP, fixture
        document = row.to_document()
        assert document["af05_effect"] == "UNKNOWN"
        assert document["reason"] == fh.row_reason(records[fixture])


def test_construction_gaps_are_the_lane_model_findings(records) -> None:
    """Every row requests a face-down permanent and an exact library order."""
    for fixture in knowledge_projection.ROWS:
        row = fh.classify_row(records[fixture])
        channels = {gap["channel"] for gap in row.provider_gaps}
        assert "face_down_construction" in channels, fixture
        assert "library_construction" in channels, fixture
        dimensions = {gap["dimension"] for gap in row.provider_gaps}
        assert dimensions <= set(fh._PROVIDER_DIMENSIONS), fixture
        assert not row.other_unsupported, (fixture, row.other_unsupported)


def test_event_rows_name_the_absent_principal_channel(records) -> None:
    expected = {
        "HIDDEN_07": {"reveal_look_audience", "event_log"},
        "HIDDEN_08": {"reveal_look_audience", "event_log"},
        "HIDDEN_10": {"library_contents", "event_log"},
        "HIDDEN_11": {"library_contents", "event_log"},
        "HIDDEN_18": {"replay_transcript", "event_log"},
    }
    for fixture, channels in expected.items():
        assert set(fh.classify_row(records[fixture]).missing_channels) == channels, fixture
    # A pure projection row needs only the principal-scoped state, which exists.
    assert fh.classify_row(records["HIDDEN_01"]).missing_channels == []


def test_scripted_rows_record_the_lab_execution_gap(records) -> None:
    row = fh.classify_row(records["HIDDEN_13"])
    assert any(gap["dimension"] == "decision_execution.pile.pile_label" for gap in row.lab_gaps)
    assert "Lab Forge lane has no execution" in row.reason()
    assert not fh.classify_row(records["HIDDEN_01"]).lab_gaps


def test_the_classification_follows_the_record_not_the_row_id(records) -> None:
    """Wrong-reason control: the classification follows the record, not the row id."""
    record = copy.deepcopy(records["HIDDEN_01"])
    for obj in record["semantic_objects"]:
        obj.pop("face_down", None)
    row = fh.classify_row(record)
    channels = {gap["channel"] for gap in row.provider_gaps}
    assert "face_down_construction" not in channels


def test_non_hidden_row_is_refused(records) -> None:
    with pytest.raises(ValueError):
        fh.classify_row(records["MICRO_COMBAT"])


def test_channel_assertions_hold_on_matching_source() -> None:
    asserted = fh.assert_channels(_texts())
    assert [entry["channel"] for entry in asserted] == [c.name for c in fh.CHANNELS]


@pytest.mark.parametrize("channel", [c for c in fh.CHANNELS if c.present], ids=lambda c: c.name)
def test_a_removed_fragment_is_drift(channel) -> None:
    texts = _texts()
    texts[channel.source] = texts[channel.source].replace(channel.present[0], "")
    with pytest.raises(fh.HiddenChannelDrift):
        fh.assert_channels(texts)


@pytest.mark.parametrize("channel", [c for c in fh.CHANNELS if c.absent], ids=lambda c: c.name)
def test_a_new_construction_field_is_drift(channel) -> None:
    """A bootstrap that gains the field must be re-reviewed, not silently classified."""
    texts = _texts()
    texts[channel.source] += channel.absent[0]
    with pytest.raises(fh.HiddenChannelDrift):
        fh.assert_channels(texts)


def test_classification_never_promotes_the_gate(records) -> None:
    """Construction-only or classified rows leave Forge AF05 UNKNOWN, never PASS or FAIL."""
    rows = {
        fixture: {"exit_state": "UNKNOWN", "reason": fh.row_reason(records[fixture])}
        for fixture in knowledge_projection.ROWS
    }
    hidden_document = {"verdict": "PRINCIPAL_SCOPED", "credible_as_principal_scoped_evidence": True}
    verdict = gate_derivations.af05_hidden_information("forge", rows, hidden_document)
    assert verdict["verdict"] == "UNKNOWN"


def test_module_writes_no_receipt() -> None:
    assert not hasattr(fh, "positive_receipt")
    assert not hasattr(fh, "execute_and_persist")


def test_the_reason_names_every_gap(records) -> None:
    """The runner reason carries every construction gap and every absent channel."""
    for fixture in knowledge_projection.ROWS:
        row = fh.classify_row(records[fixture])
        reason = row.reason()
        for gap in row.provider_gaps:
            assert gap["dimension"] in reason and gap["channel"] in reason, fixture
        for channel in row.missing_channels:
            assert channel in reason, fixture
        assert "PASS" not in reason
        assert "AF05 effect UNKNOWN" in reason


def test_the_channel_table_drives_the_missing_channels(records, monkeypatch) -> None:
    """Wrong-reason control: a channel the bridge supported would leave the list."""
    before = fh.classify_row(records["HIDDEN_07"]).missing_channels
    assert "event_log" in before
    supported = fh.Channel("event_log", fh.CHANNEL_SUPPORTED, "engine")
    monkeypatch.setitem(fh.CHANNELS_BY_NAME, "event_log", supported)
    after = fh.classify_row(records["HIDDEN_07"]).missing_channels
    assert "event_log" not in after
    assert set(before) - set(after) == {"event_log"}


def test_a_lab_only_row_is_never_a_provider_gap() -> None:
    """With no provider gap and no absent channel the row is a Lab gap, not a provider one."""
    row = fh.HiddenRowClassification(fixture_id="HIDDEN_01", obligation_kind="opponent_hand")
    assert row.classification == fh.LAB_ADAPTER_GAP
    row.lab_gaps.append({"dimension": "decision_execution.priority.semantic_action"})
    assert row.classification == fh.LAB_ADAPTER_GAP
    row.missing_channels.append("event_log")
    assert row.classification == fh.PROVIDER_ADAPTER_GAP


def test_the_runner_uses_the_exact_reason_for_forge_only() -> None:
    """The runner's Forge HIDDEN branch reports row_reason; XMage keeps its projection route."""
    source = (REPO_ROOT / "scripts" / "run_current_boundary_qualification.py").read_text(
        encoding="utf-8"
    )
    branch = source.index('candidate == "forge" and fixture_id in knowledge_projection_mod.ROWS')
    xmage = source.index('candidate == "xmage" and fixture_id in knowledge_projection_mod.ROWS')
    generic = source.index("the effective obligation is a per-scenario hidden-information probe")
    assert xmage < branch < generic
    assert "forge_hidden_information_mod.row_reason(record)" in source[branch:generic]
    assert 'outcome="UNKNOWN"' in source[branch:generic]


def test_the_committed_matrix_is_current(records) -> None:
    """Stale-evidence control: the committed matrix is bound to the current contract and bridge."""
    import json

    from commander_lab.qualification.current_boundary.bridge_launcher import (
        canonical_forge_authority,
    )

    path = REPO_ROOT / "docs" / "forge_af05_hidden_20261003" / "FORGE_AF05_MATRIX.json"
    matrix = json.loads(path.read_text(encoding="utf-8"))
    identity = load_effective_materialization(REPO_ROOT).receipt()
    assert matrix["contract_id"] == identity["contract_id"]
    assert matrix["canonical_bundle_digest"] == identity["canonical_bundle_digest"]
    assert matrix["bridge_commit"] == canonical_forge_authority()["bridge_commit"]
    fresh = [
        fh.classify_row(records[fixture]).to_document()
        for fixture in sorted(knowledge_projection.ROWS)
    ]
    assert matrix["rows"] == fresh
    assert matrix["summary"]["pass"] == 0
    assert matrix["summary"]["af05_forge"] == "UNKNOWN"
