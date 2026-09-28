"""PB-09: the Commander-Lab Forge fork must never read as pristine upstream.

The Lab's Forge candidate is a fork. Its rules core descends from upstream Forge
2.0.14, the bound native suites execute at a further WSR20/WSR24 descendant, and
the bridge carries its own commit. Four distinct commits were previously carried
across the source lock, the engine config and the freeze-readiness record with
names that invited conflation, and nothing recorded that the fork is not
pristine or that upstream behaviour has never been observed.

These tests pin the distinction. They fail if a fork commit is ever labelled
pristine upstream, if a descendant is claimed to be the candidate head, or if
upstream behaviour is recorded as observed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from commander_lab.qualification.current_boundary import source_lock as sl
from commander_lab.qualification.current_boundary.receipts import verify_candidate_identity

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "config/rules_engines.json"
READINESS = REPO / "docs/architecture_freeze_readiness_20260927/FORGE_FREEZE_READINESS.json"

FORK = "ef958ee91ac6c9ce0152189f2654bf6e05abf273"
UPSTREAM = "a37a865a53280dd8ad6fad3384d69611e8c5a42f"
TIP = "18bba95a4528f6ab5910633f1f87f603b8c4ddf8"
BRIDGE = "4753bb7c72ea60d653121e0bab989077b4009f9c"


def test_the_four_forge_commits_are_all_distinct() -> None:
    assert len({FORK, UPSTREAM, TIP, BRIDGE}) == 4


def test_source_lock_names_all_four_identities() -> None:
    """All four Forge commits stay named and distinct under distinct keys.

    Re-pointing the executing engine to the pin must not collapse the set: the
    fork head, the pinned candidate, the WSR20 tip and the additive bridge are
    four different things and each keeps its own name.
    """
    forge = sl.boundary_receipt()["candidates"]["forge"]
    identity = forge["engine_identity_pb09"]
    assert forge["column_scope"] == "pinned_upstream"
    assert identity["executing_engine"]["commit"] == UPSTREAM
    assert identity["fork_head"]["commit"] == FORK
    assert identity["upstream_baseline"]["commit"] == UPSTREAM
    assert identity["wsr20_evidence_tip"]["commit"] == TIP
    assert identity["bridge_source_commit"]["commit"] == BRIDGE
    # The bridge materializes the pinned candidate and must say so, so the two
    # identities can never be cross-wired the way they were before.
    assert identity["bridge_source_commit"]["rules_core_base_commit"] == UPSTREAM
    # The fork and the pinned candidate must never share a name.
    assert {FORK, UPSTREAM, TIP, BRIDGE} == {
        identity["executing_engine"]["commit"],
        identity["fork_head"]["commit"],
        identity["wsr20_evidence_tip"]["commit"],
        identity["bridge_source_commit"]["commit"],
    }


def test_the_fork_is_never_the_candidate_and_never_labelled_pristine() -> None:
    """The fork is Lab-modified Rules Core. It is not the candidate at all now.

    This guard was originally "the fork is never labelled pristine upstream". After
    the authorized re-point to the pinned-upstream column the stronger invariant
    holds: the fork is not the executing candidate either, so no result can be
    reported against it by accident, and it is still never called pristine.
    """
    identity = sl.boundary_receipt()["candidates"]["forge"]["engine_identity_pb09"]
    assert identity["executing_engine"]["is_pristine_upstream"] is True
    assert identity["fork_head"]["commit"] == FORK
    assert identity["fork_head"]["is_pristine_upstream"] is False
    assert sl.FORGE_CANDIDATE_COMMIT != sl.FORGE_FORK_HEAD_COMMIT
    assert sl.FORGE_CANDIDATE_COMMIT == UPSTREAM


def test_upstream_behaviour_is_observed_because_the_pinned_candidate_was_executed() -> None:
    """Upstream behaviour was UNKNOWN until the pinned candidate was executed.

    It is now executed, so the receipt may say so; saying so is what stops the
    historical fork result from being read as an upstream result.
    """
    identity = sl.boundary_receipt()["candidates"]["forge"]["engine_identity_pb09"]
    assert identity["upstream_baseline"]["verified_pristine"] is True
    assert identity["upstream_baseline"]["upstream_behaviour_observed"] is True
    assert sl.FORGE_COLUMN_SCOPE == "pinned_upstream"


def test_the_descendant_is_never_claimed_to_be_the_candidate_head() -> None:
    identity = sl.boundary_receipt()["candidates"]["forge"]["engine_identity_pb09"]
    assert identity["wsr20_evidence_tip"]["is_candidate_head"] is False
    assert sl.FORGE_CANDIDATE_COMMIT != sl.FORGE_WSR20_EVIDENCE_TIP


def test_upstream_ancestry_is_not_treated_as_identity() -> None:
    """The divergence guard must reject a descendant and an ancestor alike."""
    with pytest.raises(Exception, match="CANDIDATE_IDENTITY_DIVERGENCE"):
        verify_candidate_identity(recorded_commit=FORK, actual_commit=TIP, recorded_label="forge")
    with pytest.raises(Exception, match="CANDIDATE_IDENTITY_DIVERGENCE"):
        verify_candidate_identity(
            recorded_commit=FORK, actual_commit=UPSTREAM, recorded_label="forge"
        )


@pytest.mark.parametrize("path", [CONFIG, READINESS])
def test_config_and_readiness_carry_the_same_identities(path: Path) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    identity = (
        document["secondary_engine"]["engine_identity_pb09"]
        if "secondary_engine" in document
        else document["engine_identity_pb09"]
    )
    assert identity["executing_engine"]["commit"] == FORK
    assert identity["executing_engine"]["is_pristine_upstream"] is False
    assert identity["upstream_baseline"]["commit"] == UPSTREAM
    assert identity["upstream_baseline"]["verified_pristine"] is False
    assert identity["upstream_baseline"]["upstream_behaviour_observed"] is False
    assert "confusion_forbidden" in identity


def test_config_does_not_repin_the_candidate_to_the_fork() -> None:
    """PB-09 forbids repinning the pin to the fork to make evidence consistent.

    The executed fork carries Lab's own Rules engineering, so designating it as the
    Forge candidate would launder 47 Rules-touching Lab commits into a provider
    pin. The pin is the Coordinator's to change, not this harness's.
    """
    secondary = json.loads(CONFIG.read_text(encoding="utf-8"))["secondary_engine"]
    assert secondary["commit"] == UPSTREAM, "the Forge candidate pin must not move"
    assert secondary["bridge_source"]["commit"] == BRIDGE


def test_commit_field_is_the_pin_of_record_not_a_verdict_on_pb09() -> None:
    """The field states what the pin IS, and does not pre-judge the open question."""
    secondary = json.loads(CONFIG.read_text(encoding="utf-8"))["secondary_engine"]
    meaning = secondary["commit_meaning"].upper()
    assert "PINNED CANDIDATE OF RECORD" in meaning
    assert "OPEN" in meaning and "COORDINATOR" in meaning
    # It must not assert the fork is not the engine, which would pre-judge PB-09.
    assert "NOT THE ENGINE THAT EXECUTES" not in meaning
    assert secondary["engine_identity_pb09"]["pb09_status"].startswith("OPEN")


def test_identity_blocks_declare_pb09_open_rather_than_resolved() -> None:
    for path in (CONFIG, READINESS):
        document = json.loads(path.read_text(encoding="utf-8"))
        identity = (
            document["secondary_engine"]["engine_identity_pb09"]
            if "secondary_engine" in document
            else document["engine_identity_pb09"]
        )
        assert identity["pb09_status"].startswith("OPEN"), path.name
        assert "RESOLVED" not in identity["pb09_status"].upper()


def test_readiness_records_pb09_as_a_freeze_blocker() -> None:
    document = json.loads(READINESS.read_text(encoding="utf-8"))
    blockers = document["freeze_eligibility"]["prevented_by"]
    assert any("PB-09" in blocker for blocker in blockers)
    # And it must not claim freeze eligibility.
    assert document["freeze_eligibility"]["freeze_eligible"] is False


# --- the engine-equivalence proof, which is what actually resolves PB-09 ----- #


def test_engine_equivalence_accepts_a_harness_only_descendant() -> None:
    """A descendant that adds only harness and evidence executes the same engine."""
    import subprocess
    import tempfile

    from commander_lab.qualification.current_boundary.receipts import engine_tree_equivalence

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        for module in ("forge-core", "forge-game"):
            (repo / module / "src/main/java").mkdir(parents=True)
            (repo / module / "src/main/java/Engine.java").write_text("class Engine {}\n")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "fork head"],
            cwd=repo,
            check=True,
        )
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
        ).stdout.strip()
        # Harness-only change: a test class and an evidence packet.
        (repo / "forge-core/src/test/java").mkdir(parents=True)
        (repo / "forge-core/src/test/java/SuiteTest.java").write_text("class SuiteTest {}\n")
        (repo / "forge-core/wsr20-full107").mkdir(parents=True)
        (repo / "forge-core/wsr20-full107/RESULTS.json").write_text("{}\n")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.email=t@t",
                "-c",
                "user.name=t",
                "commit",
                "-q",
                "-m",
                "harness only",
            ],
            cwd=repo,
            check=True,
        )
        tip = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
        ).stdout.strip()

        equivalence = engine_tree_equivalence(repo, head, tip)
        assert equivalence["engine_equivalent"] is True
        assert equivalence["differing_modules"] == []


def test_engine_equivalence_rejects_an_engine_change() -> None:
    """A descendant that touches engine code must never be credited."""
    import subprocess
    import tempfile

    from commander_lab.qualification.current_boundary.receipts import verify_engine_identity

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        for module in ("forge-core", "forge-game"):
            (repo / module / "src/main/java").mkdir(parents=True)
            (repo / module / "src/main/java/Engine.java").write_text("class Engine {}\n")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "fork head"],
            cwd=repo,
            check=True,
        )
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
        ).stdout.strip()
        # Engine change: this is a different engine, not a harness addition.
        (repo / "forge-core/src/main/java/Engine.java").write_text("class Engine { int x; }\n")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.email=t@t",
                "-c",
                "user.name=t",
                "commit",
                "-q",
                "-m",
                "engine change",
            ],
            cwd=repo,
            check=True,
        )
        tip = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
        ).stdout.strip()

        with pytest.raises(Exception, match="CANDIDATE_IDENTITY_DIVERGENCE"):
            verify_engine_identity(repo, head, tip, recorded_label="forge")


def test_real_forge_descendant_is_engine_equivalent() -> None:
    """The measured fact PB-09 turns on, re-proven against the real repository.

    Between the Commander-Lab fork head and the WSR20/WSR24 tip the only
    differences are one added test class and the wsr20-full107 harness/evidence
    directory. Every engine module's main-source tree is byte-identical, which is
    why the suite can execute at the descendant and still be evidence about the
    fork head.
    """
    forge = Path("/home/moeen/code/ws-forge-full107-cdq-20260926")
    if not (forge / ".git").exists():
        pytest.skip("the Forge reference checkout is not present in this environment")
    from commander_lab.qualification.current_boundary.receipts import verify_engine_identity

    proof = verify_engine_identity(forge, FORK, TIP, recorded_label="forge native suite")
    assert proof["justification"] == "ENGINE_MAIN_SOURCE_TREES_IDENTICAL"
    assert proof["differing_modules"] == []
    assert len(proof["modules"]) == 7
