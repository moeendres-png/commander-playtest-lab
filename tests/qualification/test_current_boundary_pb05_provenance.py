"""PB-05: provider build provenance is consumed fail-closed, not trusted.

PB-05 previously accepted an operator-supplied environment variable as the
commit-to-build binding, which is not build-proven. Forge PR #5 (continuing the
PR #4 repair) records the build's own git commit, tree, dirty state and source
and fails closed on every error path.

The Lab must not undo that repair by trusting a claim. These tests pin the
Lab-side consumer independently of the provider's own self-assessment: a missing,
malformed, unknown, dirty or unverified value earns no AF00/PB-05 credit, and
`unknown` is never treated as clean.
"""

from __future__ import annotations

import pytest

from commander_lab.qualification.current_boundary.receipts import verify_pb05_provenance

CANDIDATE_SOURCE = "201cad9576d004b71fd9af260ab4c981f606eb19"
CANDIDATE_TREE = "345ff8cddda9888f3414dc3fb91132694aa3cc8a"
OTHER = "a37a865a53280dd8ad6fad3384d69611e8c5a42f"


def _good() -> dict:
    return {
        "engine_build_commit": CANDIDATE_SOURCE,
        "engine_build_tree": CANDIDATE_TREE,
        "engine_build_dirty": "false",
        "engine_build_source": "native-git",
        "engine_commit_verified": True,
    }


def _check(identity: dict) -> dict:
    return verify_pb05_provenance(
        identity, expected_source_commit=CANDIDATE_SOURCE, expected_tree=CANDIDATE_TREE
    )


def test_complete_clean_provenance_earns_credit() -> None:
    result = _check(_good())
    assert result["pb05_credit"] is True
    assert result["af00_credit"] is True
    assert result["findings"] == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("engine_build_dirty", "unknown"),
        ("engine_build_dirty", "true"),
        ("engine_build_dirty", True),
        ("engine_build_dirty", None),
        ("engine_commit_verified", False),
        ("engine_commit_verified", None),
        ("engine_commit_verified", "true"),
        ("engine_build_commit", "deadbeef"),
        ("engine_build_commit", None),
        ("engine_build_tree", "not-a-sha"),
        ("engine_build_tree", ""),
        ("engine_build_source", None),
        ("engine_build_source", ""),
    ],
)
def test_bad_provenance_earns_no_credit(field: str, value: object) -> None:
    identity = _good()
    identity[field] = value
    result = _check(identity)
    assert result["pb05_credit"] is False
    assert result["af00_credit"] is False
    assert result["findings"]


def test_unknown_dirty_is_never_treated_as_clean() -> None:
    """The specific fail-open this closes: an unavailable status becoming clean."""
    identity = _good()
    identity["engine_build_dirty"] = "unknown"
    result = _check(identity)
    assert result["pb05_credit"] is False
    assert any("not clean" in finding for finding in result["findings"])


def test_claimed_commit_that_is_not_the_rules_core_is_refused() -> None:
    identity = _good()
    identity["engine_build_commit"] = OTHER
    result = _check(identity)
    assert result["pb05_credit"] is False
    assert any("is not the expected candidate source" in f for f in result["findings"])


def test_wrong_tree_is_refused() -> None:
    identity = _good()
    identity["engine_build_tree"] = "0" * 40
    result = _check(identity)
    assert result["pb05_credit"] is False
    assert any("not the expected candidate source tree" in f for f in result["findings"])


def test_verified_true_alone_is_not_enough() -> None:
    """A provider self-asserting verified while dirty still earns nothing."""
    identity = _good()
    identity["engine_build_dirty"] = "true"
    identity["engine_commit_verified"] = True
    assert _check(identity)["pb05_credit"] is False


def test_empty_identity_earns_no_credit() -> None:
    result = _check({})
    assert result["pb05_credit"] is False
    assert len(result["findings"]) >= 4


def test_legacy_env_variable_claim_is_not_provenance() -> None:
    """The pre-repair shape: a claim with no build-derived fields earns nothing."""
    result = _check({"engine_commit": CANDIDATE_SOURCE, "engine_commit_source": "env:FORGE_ENGINE_SHA"})
    assert result["pb05_credit"] is False
    assert any("engine_build_commit" in f for f in result["findings"])


def test_every_repaired_field_is_actually_consumed() -> None:
    """Each PB-05 repaired field must be read, or a repair could be ignored."""
    base = _good()
    for field in (
        "engine_build_commit",
        "engine_build_tree",
        "engine_build_dirty",
        "engine_build_source",
        "engine_commit_verified",
    ):
        identity = dict(base)
        identity[field] = None
        assert _check(identity)["pb05_credit"] is False, field
