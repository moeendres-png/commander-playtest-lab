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
    texts["bootstrap"] += "".join(f'x.has("{name}");\n' for name in sorted(fh.BOOTSTRAP_FIELDS))
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
    """A Lab gap alone is LAB_ADAPTER_GAP; no gap at all is never classified."""
    row = fh.HiddenRowClassification(fixture_id="HIDDEN_01", obligation_kind="opponent_hand")
    with pytest.raises(ValueError, match="no gap found"):
        row.classification  # noqa: B018
    row.lab_gaps.append({"dimension": "decision_execution.priority.semantic_action"})
    assert row.classification == fh.LAB_ADAPTER_GAP
    row.missing_channels.append("event_log")
    assert row.classification == fh.PROVIDER_ADAPTER_GAP


def test_an_unmapped_lane_dimension_fails_closed(records, monkeypatch) -> None:
    """A lane finding with no channel or Lab mapping refuses, never defaults to a class."""
    monkeypatch.delitem(fh._PROVIDER_DIMENSIONS, "knowledge_state")
    with pytest.raises(ValueError, match="no channel or Lab mapping"):
        fh.classify_row(records["HIDDEN_03"])
    row = fh.HiddenRowClassification(fixture_id="HIDDEN_01", obligation_kind="opponent_hand")
    row.missing_channels.append("event_log")
    row.other_unsupported.append({"dimension": "unknown"})
    with pytest.raises(ValueError, match="unclassified"):
        row.classification  # noqa: B018


def test_cost_state_follows_the_lane_construction_finding(records) -> None:
    """The lane files mid-cast cost state as a missing bootstrap field; so does this module."""
    row = fh.classify_row(records["HIDDEN_07"])
    gaps = {gap["dimension"]: gap for gap in row.provider_gaps}
    assert gaps["action_cost_state"]["channel"] == "cost_state_construction"
    assert "no bootstrap field" in gaps["action_cost_state"]["detail"]
    assert all(not gap["dimension"].startswith("action_cost_state") for gap in row.lab_gaps)


def test_a_fragment_only_in_a_comment_is_drift() -> None:
    """Fragments are matched on code: a gate that survives only in a comment is gone."""
    texts = _texts()
    gate = fh.CHANNELS_BY_NAME["face_down_redaction"].present[0]
    texts["projection"] = texts["projection"].replace(gate, "/* " + gate + " */ shown = true;")
    with pytest.raises(fh.HiddenChannelDrift):
        fh.assert_channels(texts)
    texts = _texts()
    texts["projection"] = texts["projection"].replace(gate, "// " + gate + "\nshown = true;")
    with pytest.raises(fh.HiddenChannelDrift):
        fh.assert_channels(texts)


@pytest.mark.parametrize(
    ("source", "addition"),
    [
        ("projection", 'zones.add("library", libraryFor(player, observer));'),
        ("bootstrap", 'if (neutral.has("libraries")) { }'),
        ("bootstrap", 'if (entry.has("hidden_face")) { }'),
        ("bootstrap", 'final String order = optString(entry, "order", "");'),
        ("engine", 'caps.addProperty("replay_supported", true);'),
        ("controller", "public void reveal(CardView card) { session.publish(card); }"),
        ("controller", "auditReveal(1, zone);"),
    ],
)
def test_a_new_capability_is_drift(source, addition) -> None:
    """Wrong-reason controls: each bypass the reviewer found now breaks the channel table."""
    texts = _texts()
    texts[source] += addition + "\n"
    with pytest.raises(fh.HiddenChannelDrift):
        fh.assert_channels(texts)


def test_a_lost_bootstrap_field_is_drift() -> None:
    texts = _texts()
    texts["bootstrap"] = texts["bootstrap"].replace('x.has("hands");', "")
    with pytest.raises(fh.HiddenChannelDrift, match="lost fields"):
        fh.assert_channels(texts)


def test_the_channel_table_is_bound_to_the_canonical_bridge(records, monkeypatch) -> None:
    """A moved canonical Forge pin invalidates the table until it is re-asserted."""
    from commander_lab.qualification.current_boundary.bridge_launcher import (
        canonical_forge_authority,
    )

    assert canonical_forge_authority()["bridge_commit"] == fh.ASSERTED_BRIDGE_COMMIT
    monkeypatch.setattr(fh, "canonical_forge_authority", lambda: {"bridge_commit": "0" * 40})
    with pytest.raises(fh.HiddenChannelDrift):
        fh.row_reason(records["HIDDEN_07"])
    with pytest.raises(fh.HiddenChannelDrift):
        fh.build_matrix(records, REPO_ROOT, "0" * 40)


def _runner(monkeypatch):
    import importlib.util
    import sys

    monkeypatch.delenv("FORGE_WORKSPACE", raising=False)
    path = REPO_ROOT / "scripts" / "run_current_boundary_qualification.py"
    spec = importlib.util.spec_from_file_location("fh_runner_under_test", path)
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, runner)
    spec.loader.exec_module(runner)
    return runner


def test_the_runner_uses_the_exact_reason_for_forge_only(records, monkeypatch) -> None:
    """Forge HIDDEN rows carry row_reason and stay UNKNOWN; XMage keeps its projection route."""
    runner = _runner(monkeypatch)
    materialization = runner.load_effective_materialization(REPO_ROOT)
    identity = {"starting_state_injection_supported": True}
    rows = {
        candidate: {
            row.fixture_id: row
            for row in runner.classify_remaining(
                materialization, set(), candidate=candidate, identity=identity
            )
        }
        for candidate in ("forge", "xmage")
    }
    for fixture in knowledge_projection.ROWS:
        forge = rows["forge"][fixture]
        assert forge.outcome == "UNKNOWN", fixture
        assert forge.reason.endswith(fh.row_reason(records[fixture])), fixture
        xmage = rows["xmage"][fixture]
        assert xmage.outcome == "UNKNOWN", fixture
        assert "Forge AF05" not in xmage.reason, fixture
    for fixture, row in rows["forge"].items():
        if fixture not in knowledge_projection.ROWS:
            assert "Forge AF05" not in row.reason, fixture


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
