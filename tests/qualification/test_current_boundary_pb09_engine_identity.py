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
BRIDGE_HEAD = "d5bd22d1bf3c5cf7f98f768fdbb59f0ba841c3fa"
BRIDGE_TREE = "575cbbd6de274036944ea7bd8d5c6ccb7fd55fc9"


def test_the_four_forge_commits_are_all_distinct() -> None:
    assert len({FORK, UPSTREAM, TIP, BRIDGE}) == 4


def test_source_lock_names_all_five_identities() -> None:
    """FIVE distinct Forge identities, each named under its own key.

    The convergence added a fifth: the fork-side bridge/evidence head is a
    different bridge from the one that materialized the pinned core, so counting
    four would leave a real identity unnamed and therefore conflable.
    """
    identity = sl.boundary_receipt()["candidates"]["forge"]["engine_identity_pb09"]
    assert identity["executing_engine"]["commit"] == UPSTREAM
    assert identity["fork_head"]["commit"] == FORK
    assert identity["upstream_baseline"]["commit"] == UPSTREAM
    assert identity["wsr20_evidence_tip"]["commit"] == TIP
    assert identity["bridge_source_commit"]["commit"] == BRIDGE
    assert identity["bridge_evidence_head"]["commit"] == BRIDGE_HEAD
    named = {
        identity["executing_engine"]["commit"],
        identity["fork_head"]["commit"],
        identity["wsr20_evidence_tip"]["commit"],
        identity["bridge_source_commit"]["commit"],
        identity["bridge_evidence_head"]["commit"],
    }
    assert len(named) == 5, "the five Forge identities must be five distinct commits"


def test_the_fork_is_never_labelled_pristine_upstream() -> None:
    """The fork is Lab-modified Rules Core and is never called pristine.

    The convergence moved the EXECUTING engine to the pinned upstream, which IS
    pristine and IS observed. That must not weaken this guard: the fork keeps its
    own block and is still never labelled pristine, and it is never the candidate.
    """
    identity = sl.boundary_receipt()["candidates"]["forge"]["engine_identity_pb09"]
    assert identity["fork_head"]["is_pristine_upstream"] is False
    assert identity["fork_head"]["commit"] == FORK
    assert sl.FORGE_CANDIDATE_COMMIT != FORK
    # The pristine claim belongs to the pin, and the pin is genuinely observed.
    assert identity["executing_engine"]["is_pristine_upstream"] is True
    assert identity["upstream_baseline"]["verified_pristine"] is True
    assert identity["upstream_baseline"]["upstream_behaviour_observed"] is True


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
    # The config and the readiness packet must agree on the SAME converged model:
    # the pinned upstream is what executes, it is pristine, and it has been
    # observed. Disagreement between these two files is exactly the conflation
    # this whole guard exists to prevent, so it is checked in both directions.
    assert identity["executing_engine"]["commit"] == UPSTREAM
    assert identity["executing_engine"]["is_pristine_upstream"] is True
    assert identity["fork_head"]["commit"] == FORK
    assert identity["fork_head"]["is_pristine_upstream"] is False
    assert identity["upstream_baseline"]["commit"] == UPSTREAM
    assert identity["upstream_baseline"]["verified_pristine"] is True
    assert identity["upstream_baseline"]["upstream_behaviour_observed"] is True
    # The two bridges stay separately named, so a result from one can never be
    # reported for the other.
    assert identity["bridge_source_commit"]["commit"] == BRIDGE
    assert identity["bridge_evidence_head"]["commit"] == BRIDGE_HEAD
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
    # The provider decision and the freeze stay Coordinator-owned and unclaimed.
    assert "COORDINATOR" in meaning
    assert "PRODUCTION_PROVIDER" in meaning
    assert "ARCHITECTURE_FREEZE" in meaning
    # It must never repin the field to the fork to make evidence agree.
    assert secondary["commit"] == UPSTREAM
    assert secondary["commit"] != FORK
    status = secondary["engine_identity_pb09"]["pb09_status"]
    assert "COORDINATOR" in status.upper()


def test_identity_blocks_declare_pb09_open_rather_than_resolved() -> None:
    for path in (CONFIG, READINESS):
        document = json.loads(path.read_text(encoding="utf-8"))
        identity = (
            document["secondary_engine"]["engine_identity_pb09"]
            if "secondary_engine" in document
            else document["engine_identity_pb09"]
        )
        status = identity["pb09_status"]
        # PB-09's factual half is resolved by execution: the pinned upstream was
        # built, proven pristine and run live. Its DECISION half is not, and must
        # not be: provider selection and the architecture freeze are the
        # Coordinator's, so the status must say so and claim neither.
        assert "RESOLVED_BY_EXECUTION" in status.upper(), path.name
        assert "COORDINATOR" in status.upper(), path.name
        assert "NOT CLAIMED" in status.upper(), path.name


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
    assert proof["justification"] == "RULES_CORE_MAIN_SOURCE_TREES_IDENTICAL"
    assert proof["differing_modules"] == []
    # Six Rules-Core modules. forge-protocol2-bridge is excluded and bound
    # separately, because it is transport/provenance, not Magic legality.
    assert len(proof["modules"]) == 6
    assert "forge-game" in proof["modules"]
    assert "forge-protocol2-bridge" not in proof["modules"]
    assert set(proof["compared_module_roots"]) == {
        "forge-game",
        "forge-core",
        "forge-ai",
        "forge-gui",
        "forge-gui-desktop",
        "adventure-editor",
    }


# --- the bridge is a separate identity, never collapsed into the Rules Core --- #


def test_bridge_module_is_excluded_from_the_rules_core_comparison() -> None:
    """PB-05 changed the bridge and no Rules-Core source. The check must pass."""
    from commander_lab.qualification.current_boundary import receipts as R

    assert "forge-protocol2-bridge" not in R.FORGE_RULES_CORE_MODULE_ROOTS
    assert R.FORGE_BRIDGE_MODULE_ROOTS == ("forge-protocol2-bridge",)
    assert "forge-game" in R.FORGE_RULES_CORE_MODULE_ROOTS


def test_forge_pr4_head_is_rules_core_equivalent_to_the_fork_head() -> None:
    """The real PB-05 fact: the bridge repair changed zero Rules-Core source."""
    forge = Path("/home/moeen/code/ws-forge-full107-cdq-20260926")
    if not (forge / ".git").exists():
        pytest.skip("the Forge reference checkout is not present in this environment")
    from commander_lab.qualification.current_boundary.receipts import verify_engine_identity

    proof = verify_engine_identity(forge, FORK, BRIDGE_HEAD, recorded_label="forge PR4")
    assert proof["engine_equivalent"] is True
    assert proof["differing_modules"] == []
    assert proof["justification"] == "RULES_CORE_MAIN_SOURCE_TREES_IDENTICAL"


def test_rules_core_drift_still_fails_closed() -> None:
    """Excluding the bridge must not weaken the drift guard for real engine code."""
    import subprocess
    import tempfile

    from commander_lab.qualification.current_boundary.receipts import verify_engine_identity

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        for module in ("forge-game", "forge-protocol2-bridge"):
            (repo / module / "src/main/java").mkdir(parents=True)
            (repo / module / "src/main/java/E.java").write_text("class E {}\n")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "head"],
            cwd=repo,
            check=True,
        )
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
        ).stdout.strip()
        # A forge-game change is Rules-Core drift and must be refused.
        (repo / "forge-game/src/main/java/E.java").write_text("class E { int x; }\n")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "engine"],
            cwd=repo,
            check=True,
        )
        tip = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
        ).stdout.strip()
        with pytest.raises(Exception, match="CANDIDATE_IDENTITY_DIVERGENCE"):
            verify_engine_identity(repo, head, tip, recorded_label="forge")


def test_bridge_and_evidence_head_is_bound_separately() -> None:
    identity = sl.boundary_receipt()["candidates"]["forge"]["engine_identity_pb09"]
    head = identity["bridge_evidence_head"]
    assert head["commit"] == BRIDGE_HEAD
    assert head["tree"] == BRIDGE_TREE
    assert head["pull_request"] == 4
    assert head["is_draft"] is True, "Forge PR #4 must stay Draft"
    assert head["changes_rules_core"] is False
    # Distinct from the Rules Core and from the historical bridge pin.
    assert head["commit"] != identity["executing_engine"]["commit"]
    assert head["commit"] != identity["bridge_source_commit"]["commit"]


def test_pb05_credit_rule_is_recorded_with_the_identities() -> None:
    identity = sl.boundary_receipt()["candidates"]["forge"]["engine_identity_pb09"]
    assert identity["pb05_provenance_consumed"] == list(sl.FORGE_PB05_PROVENANCE_FIELDS)
    assert "no AF00 or PB-05 credit" in identity["pb05_credit_rule"]


# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# CONVERGENCE GUARDS (SB independent baseline). The converged source lock executes
# the PINNED UPSTREAM core and demotes the Lab fork to non-candidate, so these pin
# that stronger invariant. They are ADDITIONAL to main's four-commits-distinct,
# never-labelled-pristine and bridge-head guards, which still hold unchanged: a
# fork result stays valid evidence ABOUT THE FORK and is simply never evidence
# about the pin.
# ---------------------------------------------------------------------------


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
