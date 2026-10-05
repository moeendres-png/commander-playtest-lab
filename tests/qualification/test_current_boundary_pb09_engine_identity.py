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
import os
import subprocess
from pathlib import Path

import pytest

from commander_lab.qualification.current_boundary import source_lock as sl
from commander_lab.qualification.current_boundary.receipts import verify_candidate_identity

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "config/rules_engines.json"
READINESS = REPO / "docs/architecture_freeze_readiness_20260927/FORGE_FREEZE_READINESS.json"
SUCCESSOR_LOCK = (
    REPO / "qualification/forge-r1-candidate-authority-20260930/SUCCESSOR_SOURCE_LOCK.json"
)

REQUIRE_REFERENCE_ENV = "PB09_REQUIRE_FORGE_REFERENCE"

# Historical path of the Forge reference checkout this file was written against.
DEFAULT_FORGE_REFERENCE = Path("/home/moeen/code/ws-forge-full107-cdq-20260926")


def _git_has_commit(repo: Path, sha: str) -> bool:
    proc = subprocess.run(
        ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0


def _require_forge_reference(*commits: str) -> Path:
    """Locate a Forge checkout that actually contains the pinned commits.

    Resolution follows FORGE_SOURCE_DIR, the convention already documented for
    the Forge checkout in tests/integration/test_forge_bridge_h4f_live.py:25,
    with the historical hardcoded path as fallback so behaviour on the machine
    this file was written against is unchanged.

    The two preconditions are kept separate because they mean different things:

    * no checkout at all -- a property of this machine. Nothing changed, there is
      nothing to re-adjudicate, and the response is to point FORGE_SOURCE_DIR at
      a checkout.
    * a checkout that exists but lacks a pinned commit -- these tests compare
      *specific* pinned commits, so no other checkout can establish them. An
      arbitrary Forge source tree is not a substitute, and substituting one would
      turn a correct skip into a wrong failure.
    """
    raw = os.environ.get("FORGE_SOURCE_DIR", "").strip()
    forge = Path(raw) if raw else DEFAULT_FORGE_REFERENCE
    # B6 (#487): the required infrastructure lane materializes the reference and
    # sets PB09_REQUIRE_FORGE_REFERENCE=1, so there a missing checkout or commit
    # fails instead of producing a skip-based green signal.
    unavailable = pytest.fail if os.environ.get(REQUIRE_REFERENCE_ENV) == "1" else pytest.skip
    if not (forge / ".git").exists():
        unavailable(
            f"no Forge checkout at {forge}: this test compares pinned commits, so it cannot run "
            "without one. Set FORGE_SOURCE_DIR to a checkout of moeendres-png/forge to enable it."
        )
    missing = [sha for sha in commits if not _git_has_commit(forge, sha)]
    if missing:
        unavailable(
            f"the Forge checkout at {forge} does not contain {missing}. These tests compare "
            "specific pinned commits, so any other checkout cannot establish them -- a different "
            "condition from having no checkout at all."
        )
    return forge


FORK = "ef958ee91ac6c9ce0152189f2654bf6e05abf273"
UPSTREAM = "a37a865a53280dd8ad6fad3384d69611e8c5a42f"
TIP = "18bba95a4528f6ab5910633f1f87f603b8c4ddf8"
BRIDGE = "4753bb7c72ea60d653121e0bab989077b4009f9c"
BRIDGE_HEAD = "e15f37d6b2b5c0ad682948f86f037e07b6aaded5"
BRIDGE_TREE = "a1d4d4a8fe421e57b919e8e0bd9fda7d9deb0d3b"
CURRENT_CANDIDATE = "bb0a740d2bef725194798383c2452213ecdd0b37"
CURRENT_CANDIDATE_TREE = "4989b5bb35b8279e82f79c1ca99dc698d63d093a"
CURRENT_BRIDGE = "4ed8992de4bd7bd120c3920c0362533c7c65d822"
CURRENT_BRIDGE_TREE = "31f70b510116bddfbf9e6a7fa7faa08cb54c9142"
# The bridge source before forge#16 (#11 + #13), historical.
R1_BRIDGE = "e8b8aec60720aee218338754224721597b8c6ec5"
R1_BRIDGE_TREE = "6c49f100fe61d1b2a71dd46a7347a2ff0f0da4ea"
# forge#16, the bridge source before forge#22 and forge#25, historical.
R5_BRIDGE = "20e3e1f7ff8e6195b95ed0dc14e0d4c87f1bcf4c"
R5_BRIDGE_TREE = "000066890decca5ed7b1b889be0ea46d77903aee"
R5_BRIDGE_LOCK = (
    REPO / "qualification/forge-bridge-r5-integrated-20261001/SUCCESSOR_SOURCE_LOCK.json"
)
BRIDGE_SUCCESSOR_LOCK = (
    REPO / "qualification/forge-bridge-constructed-state-20261005/SUCCESSOR_SOURCE_LOCK.json"
)


def test_the_four_forge_commits_are_all_distinct() -> None:
    assert len({FORK, UPSTREAM, TIP, BRIDGE}) == 4


def test_source_lock_names_all_four_identities() -> None:
    identity = sl.boundary_receipt()["candidates"]["forge"]["engine_identity_pb09"]
    assert identity["executing_engine"]["commit"] == FORK
    assert identity["upstream_baseline"]["commit"] == UPSTREAM
    assert identity["wsr20_evidence_tip"]["commit"] == TIP
    assert identity["bridge_source_commit"]["commit"] == BRIDGE


def test_the_fork_is_never_labelled_pristine_upstream() -> None:
    identity = sl.boundary_receipt()["candidates"]["forge"]["engine_identity_pb09"]
    assert identity["executing_engine"]["is_pristine_upstream"] is False
    assert identity["upstream_baseline"]["verified_pristine"] is False
    assert identity["upstream_baseline"]["upstream_behaviour_observed"] is False


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


def _config() -> dict:
    loaded: dict = json.loads(CONFIG.read_text(encoding="utf-8"))
    return loaded


def test_config_records_r1_current_authority_without_rewriting_history() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    secondary = config["secondary_engine"]
    identity = secondary["engine_identity_pb09"]

    assert secondary["repository"] == "https://github.com/moeendres-png/forge.git"
    assert secondary["commit"] == CURRENT_CANDIDATE
    assert secondary["source_archive"].endswith(f"/{CURRENT_CANDIDATE}.tar.gz")
    assert secondary["bridge_source"]["commit"] == CURRENT_BRIDGE
    assert secondary["bridge_source"]["rules_core_base_commit"] == CURRENT_CANDIDATE

    assert identity["pb09_status"].startswith("RESOLVED_BY_OWNER_R1")
    assert identity["current_candidate"]["commit"] == CURRENT_CANDIDATE
    assert identity["current_candidate"]["tree"] == CURRENT_CANDIDATE_TREE
    assert identity["qualification_lineage_base"]["commit"] == FORK
    assert identity["bridge_source"]["commit"] == CURRENT_BRIDGE
    assert identity["bridge_source"]["tree"] == CURRENT_BRIDGE_TREE
    assert identity["bridge_source"]["rules_core_base_commit"] == CURRENT_CANDIDATE
    assert identity["upstream_baseline"]["commit"] == UPSTREAM

    assert config["provider_decision"] == "NO_PROVIDER_READY"
    assert config["current_runtime"]["provider_selected"] is False
    assert config["current_runtime"]["production_provider"] is None


def test_historical_readiness_remains_source_bound_and_open_after_r1() -> None:
    document = json.loads(READINESS.read_text(encoding="utf-8"))
    identity = document["engine_identity_pb09"]

    assert identity["executing_engine"]["commit"] == FORK
    assert identity["upstream_baseline"]["commit"] == UPSTREAM
    assert identity["pb09_status"].startswith("OPEN")
    assert CURRENT_CANDIDATE not in json.dumps(document)
    assert CURRENT_BRIDGE not in json.dumps(document)


def test_r1_successor_source_lock_matches_live_authority_and_preserves_wsr22() -> None:
    successor = json.loads(SUCCESSOR_LOCK.read_text(encoding="utf-8"))
    secondary = _config()["secondary_engine"]

    assert successor["authority"]["owner_rulings"] == ["R-1", "R-2", "R-3", "R-4"]
    assert successor["authority"]["production_provider"] == "NOT_SELECTED"
    assert successor["authority"]["architecture_freeze"] == "NOT_CLAIMED"

    current = successor["current_forge_authority"]
    assert current["candidate_commit"] == secondary["commit"] == CURRENT_CANDIDATE
    assert current["candidate_tree"] == CURRENT_CANDIDATE_TREE
    # #446 updated the R-1 lock to the forge#16 bridge source; forge#22 + forge#25
    # supersede it through their own lock, and Rules-Core is unchanged.
    assert current["bridge_commit"] == R5_BRIDGE != secondary["bridge_source"]["commit"]
    assert current["bridge_tree"] == R5_BRIDGE_TREE
    assert (
        current["bridge_rules_core_base_commit"]
        == secondary["bridge_source"]["rules_core_base_commit"]
        == CURRENT_CANDIDATE
    )
    assert current["lineage_base_commit"] == FORK
    assert current["upstream_reference_commit"] == UPSTREAM

    assert successor["evidence_transfer"]["historical_receipts_relabelled"] is False
    assert successor["frozen_wsr22"]["forge_candidate_commit"] == FORK
    assert successor["frozen_wsr22"]["source_lock_git_blob"] == (
        "dd4af484bd6ae33540a130caaa3ecd9edeb1ac70"
    )
    # WSR22 remains historical/frozen; current authority lives in this successor
    # lock plus config/rules_engines.json rather than by rewriting source_lock.py.
    assert sl.FORGE_CANDIDATE_COMMIT == FORK
    assert sl.FORGE_CANDIDATE_COMMIT != CURRENT_CANDIDATE


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
    forge = _require_forge_reference(FORK, TIP)
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


def test_forge_pr5_head_is_rules_core_equivalent_to_the_fork_head() -> None:
    """The real PB-05/WSR30 fact: the bridge repair changed zero Rules-Core source."""
    forge = _require_forge_reference(FORK, BRIDGE_HEAD)
    from commander_lab.qualification.current_boundary.receipts import verify_engine_identity

    proof = verify_engine_identity(forge, FORK, BRIDGE_HEAD, recorded_label="forge PR5")
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
    assert head["pull_request"] == 5
    assert head["is_draft"] is True, "Forge PR #5 must stay Draft"
    assert head["changes_rules_core"] is False
    # Distinct from the Rules Core and from the historical bridge pin.
    assert head["commit"] != identity["executing_engine"]["commit"]
    assert head["commit"] != identity["bridge_source_commit"]["commit"]


def test_pb05_credit_rule_is_recorded_with_the_identities() -> None:
    identity = sl.boundary_receipt()["candidates"]["forge"]["engine_identity_pb09"]
    assert identity["pb05_provenance_consumed"] == list(sl.FORGE_PB05_PROVENANCE_FIELDS)
    assert "no AF00 or PB-05 credit" in identity["pb05_credit_rule"]


def test_bridge_successor_lock_binds_the_live_bridge_without_moving_rules_core() -> None:
    lock = json.loads(BRIDGE_SUCCESSOR_LOCK.read_text(encoding="utf-8"))
    secondary = _config()["secondary_engine"]

    assert lock["new_bridge_source"]["commit"] == secondary["bridge_source"]["commit"]
    assert lock["new_bridge_source"]["commit"] == CURRENT_BRIDGE
    assert lock["new_bridge_source"]["tree"] == CURRENT_BRIDGE_TREE
    assert lock["prior_bridge_source"]["commit"] == R5_BRIDGE
    assert lock["prior_bridge_source"]["tree"] == R5_BRIDGE_TREE
    # Two roles, never mixed: Rules-Core authority stays the R-1 candidate.
    assert lock["rules_core_authority"]["commit"] == secondary["commit"] == CURRENT_CANDIDATE
    assert secondary["bridge_source"]["rules_core_base_commit"] == CURRENT_CANDIDATE
    assert CURRENT_BRIDGE != CURRENT_CANDIDATE
    qual = lock["exact_head_qualification"]
    assert qual["commit"] == CURRENT_BRIDGE
    assert all(r["java17"] == r["java21"] == "success" for r in qual["github_test_build"])
    assert qual["local_forge_bridge_suite"]["failures"] == 0
    assert set(lock["not_a"]) >= {"PRODUCTION_PROVIDER_SELECTION", "RULES_CORE_AUTHORITY_CHANGE"}
    assert lock["evidence_transfer"]["historical_receipts_relabelled"] is False
    # The PR head the local suite ran on has the merged source's tree.
    assert qual["local_forge_bridge_suite"]["tree_equal_to_new_bridge_source"] is True


def test_the_r5_bridge_lock_stays_historical() -> None:
    """forge#16's lock keeps its own identity after forge#22 and forge#25 moved the pin."""
    lock = json.loads(R5_BRIDGE_LOCK.read_text(encoding="utf-8"))
    assert lock["new_bridge_source"]["commit"] == R5_BRIDGE
    assert lock["new_bridge_source"]["tree"] == R5_BRIDGE_TREE
    assert lock["prior_bridge_source"]["commit"] == R1_BRIDGE
    assert _config()["secondary_engine"]["bridge_source"]["commit"] != R5_BRIDGE


def test_a_required_lane_fails_instead_of_skipping(monkeypatch, tmp_path) -> None:
    """B6: with the requirement set, a missing reference is a failure, never a skip."""
    monkeypatch.setenv(REQUIRE_REFERENCE_ENV, "1")
    monkeypatch.setenv("FORGE_SOURCE_DIR", str(tmp_path / "absent"))
    with pytest.raises(pytest.fail.Exception, match="no Forge checkout"):
        _require_forge_reference(FORK)
    monkeypatch.delenv(REQUIRE_REFERENCE_ENV)
    with pytest.raises(pytest.skip.Exception, match="no Forge checkout"):
        _require_forge_reference(FORK)


def test_the_infrastructure_lane_materializes_the_reference() -> None:
    """B6: the required lane provides the checkout and demands it."""
    import yaml

    workflow = yaml.safe_load(
        (REPO / ".github/workflows/production-qualification.yml").read_text(encoding="utf-8")
    )
    steps = workflow["jobs"]["infrastructure"]["steps"]
    names = [step.get("name") for step in steps]
    materialize = names.index("Materialize the pinned Forge reference for PB09 identity tests")
    qualification = names.index("Validate WS-17 qualification infrastructure")
    assert materialize < qualification
    env = steps[qualification].get("env") or {}
    assert env.get(REQUIRE_REFERENCE_ENV) == "1"
    assert env.get("FORGE_SOURCE_DIR")
    script = steps[materialize]["run"]
    for sha in (FORK, TIP, BRIDGE_HEAD):
        assert sha in script, sha
