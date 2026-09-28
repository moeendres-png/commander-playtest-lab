"""Provider evidence binding: evidence must never speak for a head it did not run.

The failure this guards against is silent. A stale artifact is valid JSON with
unchanged row outcomes and denominators that still add up, so nothing else in
the pipeline notices when it is cited for a newer candidate head. These tests
pin both directions: a real superseding change must mark an artifact stale, and
an unrelated change must not.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from commander_lab.qualification.current_boundary.provider_binding import (
    BOUND,
    STALE,
    UNSUPERSEDED,
    assess_artifact_binding,
    assess_provider_bindings,
)

# The identity actually recorded by the committed Forge artifacts.
FORGE_RULES_CORE = "ef958ee91ac6c9ce0152189f2654bf6e05abf273"
FORGE_ADAPTER = "e15f37d6b2b5c0ad682948f86f037e07b6aaded5"
FORGE_RUNNER = "f5d3197a90503b0ff1e50142a1828c89d83ab752"


def _forge_artifact() -> dict[str, Any]:
    return {
        "runtime_identity": {
            "engine_candidate_commit": FORGE_RULES_CORE,
            "adapter_commit": FORGE_ADAPTER,
            "runner_commit": FORGE_RUNNER,
        }
    }


def _pr6_like_change() -> dict[str, Any]:
    """The shape of Forge PR #6: a Rules Core edit plus bridge edits.

    The change is published on top of the bridge head while rewriting a Rules
    Core forked from the fork point, which is why the two bases are declared
    separately.
    """
    return {
        "head": "6f70e32e81025fd8a6eaf08d475f8282b7f03dc9",
        "base_by_surface": {"rules_core": FORGE_RULES_CORE, "adapter": FORGE_ADAPTER},
        "paths": [
            "forge-game/src/main/java/forge/game/card/Card.java",
            "forge-protocol2-bridge/src/main/java/forge/bridge/BridgeEngine.java",
            "forge-protocol2-bridge/src/test/java/forge/bridge/WsR24Pb07ActualCardPreparationTest.java",
        ],
        "rules_core_paths": ["forge-game/src/main/java/forge/game/card/Card.java"],
        "adapter_paths": ["forge-protocol2-bridge/"],
    }


def test_a_rules_core_change_marks_the_artifact_stale() -> None:
    result = assess_artifact_binding(_forge_artifact(), [_pr6_like_change()])
    assert result["disposition"] == STALE
    surfaces = {entry["surface"] for entry in result["superseding_changes"]}
    assert "rules_core" in surfaces
    assert "adapter" in surfaces


def test_the_recorded_head_is_never_rewritten() -> None:
    """The disposition must report what was consumed, not what is published."""
    result = assess_artifact_binding(_forge_artifact(), [_pr6_like_change()])
    assert result["consumed"]["engine_candidate_commit"] == FORGE_RULES_CORE
    assert result["consumed"]["adapter_commit"] == FORGE_ADAPTER
    # The newer head appears only as the superseding head, never as a consumed one.
    assert "6f70e32e" not in json.dumps(result["consumed"])


def test_relabelling_would_be_named_as_a_false_credit() -> None:
    result = assess_artifact_binding(_forge_artifact(), [_pr6_like_change()])
    assert "false credit" in result["reason"]
    assert "regenerate" in result["required_action"]
    assert "do not relabel" in result["required_action"]


def test_an_unrelated_change_does_not_invalidate_evidence() -> None:
    """A docs-only change must not discard a real run."""
    docs_only = {
        "head": "1111111111111111111111111111111111111111",
        "base_by_surface": {"rules_core": FORGE_RULES_CORE, "adapter": FORGE_ADAPTER},
        "paths": ["README.md", "docs/notes.md"],
        "rules_core_paths": ["forge-game/src/main/java/forge/game/card/Card.java"],
        "adapter_paths": ["forge-protocol2-bridge/"],
    }
    result = assess_artifact_binding(_forge_artifact(), [docs_only])
    assert result["disposition"] == BOUND


def test_a_change_from_an_unrelated_branch_cannot_supersede() -> None:
    """Published on a different base, so it says nothing about this evidence."""
    unrelated = {
        "head": "2222222222222222222222222222222222222222",
        "base_by_surface": {
            "rules_core": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
            "adapter": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
        },
        "paths": ["forge-game/src/main/java/forge/game/card/Card.java"],
        "rules_core_paths": ["forge-game/src/main/java/forge/game/card/Card.java"],
        "adapter_paths": ["forge-protocol2-bridge/"],
    }
    result = assess_artifact_binding(_forge_artifact(), [unrelated])
    assert result["disposition"] == BOUND


def test_no_published_change_leaves_the_artifact_bound() -> None:
    result = assess_artifact_binding(_forge_artifact(), [])
    assert result["disposition"] == BOUND


def test_an_artifact_with_no_candidate_identity_is_flagged_not_credited() -> None:
    result = assess_artifact_binding({"runtime_identity": {}}, [_pr6_like_change()])
    assert result["disposition"] == UNSUPERSEDED


def test_stale_does_not_mean_wrong() -> None:
    """A stale artifact remains true evidence of what it consumed."""
    result = assess_artifact_binding(_forge_artifact(), [_pr6_like_change()])
    assert result["consumed"]["engine_candidate_commit"] == FORGE_RULES_CORE
    assert result["disposition"] == STALE


def test_provider_bindings_classify_every_artifact() -> None:
    out = assess_provider_bindings(
        {
            "forge": {
                "FULL107_FORGE_RESULTS": _forge_artifact(),
                "ACTUAL_CARD_FORGE": _forge_artifact(),
            }
        },
        {"forge": [_pr6_like_change()]},
    )
    assert out["counts"][STALE] == 2
    assert out["counts"][BOUND] == 0
    assert set(out["bindings"]["forge"]) == {"FULL107_FORGE_RESULTS", "ACTUAL_CARD_FORGE"}


def test_staleness_does_not_change_any_gate_verdict() -> None:
    """Binding is descriptive: it must not become a new pass or a new failure."""
    out = assess_provider_bindings(
        {"forge": {"a": _forge_artifact()}}, {"forge": [_pr6_like_change()]}
    )
    assert "not a pass" in out["honesty_note"]


# ---------------------------------------------------------------------------
# The committed artifacts are bound to the heads they recorded. If a future
# change relabels them, this fails rather than silently accepting the drift.
# ---------------------------------------------------------------------------

_COMMITTED = Path("qualification/final-current-boundary-20260927")
_ARTIFACTS = ("FULL107_FORGE_RESULTS", "ACTUAL_CARD_FORGE", "FULL107_XMAGE_RESULTS")


@pytest.mark.parametrize("name", _ARTIFACTS)
def test_committed_artifact_records_a_candidate_identity(name: str) -> None:
    document = json.loads((_COMMITTED / f"{name}.json").read_text(encoding="utf-8"))
    identity = document["runtime_identity"]
    if "FORGE" in name:
        assert identity["adapter_commit"] == FORGE_ADAPTER
        assert identity["engine_candidate_commit"] == FORGE_RULES_CORE
    else:
        assert identity.get("engine_candidate_commit"), "XMage evidence must name its engine commit"


def test_committed_forge_evidence_is_not_claimed_to_be_pr6() -> None:
    """The committed Forge run predates PR #6 and must not say otherwise."""
    for name in ("FULL107_FORGE_RESULTS", "ACTUAL_CARD_FORGE"):
        document = json.loads((_COMMITTED / f"{name}.json").read_text(encoding="utf-8"))
        identity = document["runtime_identity"]
        assert "6f70e32e" not in json.dumps(identity), name


# ---------------------------------------------------------------------------
# The persisted binding artifact is derived from the committed evidence, so it
# must agree with it. A drift here means evidence and its binding record have
# separated, which is exactly the failure being guarded against.
# ---------------------------------------------------------------------------

_BINDING = _COMMITTED / "PROVIDER_EVIDENCE_BINDING.json"


def test_persisted_binding_exists_and_covers_both_candidates() -> None:
    document = json.loads(_BINDING.read_text(encoding="utf-8"))
    assert set(document["bindings"]) == {"forge", "xmage"}
    for entries in document["bindings"].values():
        assert entries, "each candidate must have at least one classified artifact"


def test_persisted_binding_counts_match_the_dispositions() -> None:
    document = json.loads(_BINDING.read_text(encoding="utf-8"))
    counted: dict[str, int] = {}
    for entries in document["bindings"].values():
        for entry in entries.values():
            counted[entry["disposition"]] = counted.get(entry["disposition"], 0) + 1
    assert document["counts"][STALE] == counted.get(STALE, 0)
    assert document["counts"][BOUND] == counted.get(BOUND, 0)


def test_a_stale_artifact_never_claims_the_newer_head() -> None:
    """The core guard: no stale artifact may present the superseding head."""
    document = json.loads(_BINDING.read_text(encoding="utf-8"))
    for entries in document["bindings"].values():
        for name, entry in entries.items():
            if entry["disposition"] != STALE:
                continue
            consumed = json.dumps(entry["consumed"])
            for change in entry["superseding_changes"]:
                assert str(change["head"]) not in consumed, name
                assert change["head"] not in consumed, name


def test_binding_is_never_promoted_into_a_verdict() -> None:
    document = json.loads(_BINDING.read_text(encoding="utf-8"))
    assert "not a pass" in document["honesty_note"]
    # No gate verdict is invented by the binding record.
    assert "verdict" not in json.dumps(document["counts"])
