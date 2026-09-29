"""PB-09: the pristine candidate lane is evidence about pristine upstream, or it is nothing.

The current-boundary evidence was produced against the Commander-Lab Forge fork
at ``ef958ee9``. PB-09 established a second lane against the *pinned* candidate of
record: pristine upstream ``forge-2.0.14`` at ``a37a865a``, materialised with the
manifest's own pinned bridge source.

These tests pin the properties that make that lane admissible and stop it from
silently becoming fork evidence:

* the pristine lane names the pinned commit, never the fork, and never both;
* the evidence is only about the pinned candidate because the executing
  checkout's Rules Core is byte-identical to it;
* no PB-09 artifact may repin the manifest or resolve PB-09, which is the
  Coordinator's decision;
* the lane's headline results are recorded with their honest, unfavourable
  verdicts rather than being softened;
* a result observed on one Forge identity is never re-exported as a result for
  another.
"""

from __future__ import annotations

import json
from pathlib import Path

from commander_lab.qualification.current_boundary import receipts as receipt_mod

REPO = Path(__file__).resolve().parents[2]
PB09 = REPO / "qualification" / "pb09-pristine-upstream-20260929"
DOCS = REPO / "docs" / "pb09_pristine_upstream_forge_20260929"
CONFIG = REPO / "config" / "rules_engines.json"

PIN = "a37a865a53280dd8ad6fad3384d69611e8c5a42f"
BRIDGE_PIN = "4753bb7c72ea60d653121e0bab989077b4009f9c"
BRIDGE_HEAD = "e15f37d6b2b5c0ad682948f86f037e07b6aaded5"
FORK = "ef958ee91ac6c9ce0152189f2654bf6e05abf273"


def load(name: str) -> dict:
    return json.loads((PB09 / name).read_text(encoding="utf-8"))


def test_the_four_forge_identities_remain_distinct() -> None:
    assert len({PIN, BRIDGE_PIN, BRIDGE_HEAD, FORK}) == 4


def test_pristine_lane_is_bound_to_the_pin_and_never_to_the_fork() -> None:
    results = load("FULL107_PRISTINE_PIN_RESULTS.json")
    identity = results["runtime_identity"]
    assert identity["engine_candidate_commit"] == PIN
    assert identity["engine_candidate_commit"] != FORK
    assert identity["engine_identity_class"] == "PRISTINE_UPSTREAM_CANDIDATE_OF_RECORD"
    # The adapter is the pinned bridge, which is a separate identity and is
    # reported separately: attributing a row to the bridge commit would be the
    # same conflation PB-09 exists to prevent.
    assert identity["adapter_commit"] == BRIDGE_PIN
    assert identity["lab_fork_reference_not_executed"] == FORK


def test_pristine_evidence_requires_rules_core_byte_identity() -> None:
    """The lane is about the pin only because the engine proves equivalent."""
    identity_doc = load("PRISTINE_ENGINE_IDENTITY_PIN.json")
    equivalence = identity_doc["rules_core_equivalence"]
    assert equivalence["justification"] == "RULES_CORE_MAIN_SOURCE_TREES_IDENTICAL"
    assert equivalence["differing_modules"] == []
    assert equivalence["one_sided_modules"] == []
    assert identity_doc["pinned_candidate"]["commit"] == PIN
    # The bridge module is excluded from the engine comparison and bound on its
    # own; a comparison that included it would conflate the two identities.
    assert "forge-protocol2-bridge" not in equivalence["compared_module_roots"]


def test_engine_identity_check_fails_closed_on_real_rules_core_drift() -> None:
    """The equivalence the lane depends on must reject an engine change."""
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        (repo / "forge-game" / "src" / "main" / "java").mkdir(parents=True)
        (repo / "forge-game" / "src" / "main" / "java" / "E.java").write_text("class E {}\n")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "pin"],
            cwd=repo,
            check=True,
        )
        pin = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
        ).stdout.strip()
        (repo / "forge-game" / "src" / "main" / "java" / "E.java").write_text(
            "class E { int x; }\n"
        )
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "drift"],
            cwd=repo,
            check=True,
        )
        drift = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
        ).stdout.strip()
        with pytest_raises_receipt_error():
            receipt_mod.verify_engine_identity(
                repo, pin, drift, recorded_label="pb09 pristine lane"
            )


def pytest_raises_receipt_error():
    import pytest

    return pytest.raises(receipt_mod.ReceiptError, match="CANDIDATE_IDENTITY_DIVERGENCE")


def test_denominator_is_107_and_never_reduced() -> None:
    results = load("FULL107_PRISTINE_PIN_RESULTS.json")
    assert results["total"] == 107
    assert len(results["rows"]) == 107
    assert results["denominator_decreased_to_bypass_blocker"] is False
    assert sum(results["counts"].values()) == 107
    # Every row carries one of the contract's terminal vocabularies.
    allowed = {
        "PASS",
        "FAIL",
        "UNKNOWN",
        "BLOCKED",
        "CRASH",
        "TIMEOUT",
        "PROTOCOL_FAILURE",
    }
    assert {row["exit_state"] for row in results["rows"]} <= allowed


def test_native_receipt_is_bound_to_the_pin_and_green() -> None:
    receipts, rejected = receipt_mod.collect_receipts(PB09 / "receipts")
    assert not rejected, rejected
    assert receipts, "no PB-09 native receipt is present"
    receipt = receipts[0]
    assert receipt["candidate_commit"] == PIN
    assert receipt["returncode"] == 0
    assert receipt["failed"] == 0 and receipt["errors"] == 0
    assert receipt["tests"] > 0, "a receipt with no tests earns no credit"
    assert (
        receipt["engine_identity_proof"]["justification"]
        == "RULES_CORE_MAIN_SOURCE_TREES_IDENTICAL"
    )
    # The bridge is the adapter, not the engine: its commit is recorded as what
    # executed, and the engine equivalence is the proof that still makes it
    # evidence about the pin.
    assert receipt["executed_commit"] == BRIDGE_PIN


def test_headline_results_keep_their_unfavourable_verdicts() -> None:
    """The honest findings must not be softened by later editing."""
    af03 = load("AF03_PIN.json")
    assert af03["verdict"] == "FAIL"
    accepted = {p["probe"] for p in af03["probes"] if p["verdict"] == "FAIL"}
    assert accepted == {"commander_not_in_pool", "colour_identity_violation"}
    # A legal control imported, so the acceptance is a legality finding and not
    # a broken import path.
    assert af03["legal_control"]["response"]["success"] is True

    matrix = load("AF00_AF11_PRISTINE_PIN.json")
    verdicts = matrix["gate_verdict_summary"]
    assert verdicts["AF03"] == "FAIL", "pristine accepts an illegal Commander deck"
    assert verdicts["AF11"] == "FAIL", "GPL-3.0 is incompatible with proprietary distribution"
    # The gate that the fork lane establishes must not be claimed here.
    for gate in ("AF02", "AF04", "AF05", "AF06", "AF07", "AF08", "AF09"):
        assert verdicts[gate] == "UNKNOWN", gate


def test_falsification_records_established_candidate_defects() -> None:
    falsification = load("WRONG_REASON_FALSIFICATION.json")
    defects = falsification["classification"]["candidate_defects_established_by_this_campaign"]
    assert defects, "the falsification campaign established no candidate property"
    assert "Commander deck legality" in defects[0]["defect"]
    did_not_survive = falsification["classification"]["does_not_survive"]
    # The requester-binding gap is recorded as unestablished evidence rather than
    # being promoted to a pass.
    assert any("REQUESTER_BINDING" in item["attack"] for item in did_not_survive)
    # The positive claims that did survive are named explicitly.
    assert (
        "EVERY_CHOSEN_OPTION_WAS_OFFERED"
        in falsification["classification"]["survives_adversarial_falsification"]
    )


def test_rng_credit_is_absent_without_an_engine_acknowledgement() -> None:
    rng = load("RNG_REPLAY_PIN.json")
    binding = rng["rules_rng_binding"]
    assert binding["classification"] == "UNCONTROLLED_ENGINE_RNG"
    assert binding["controlled"] is False
    assert binding["rng_credit"] is False
    assert binding["acknowledged_seed"] is None
    assert rng["harness_injected_outcomes"] is False


def test_delta_does_not_rank_providers_or_compare_counts_naively() -> None:
    delta = load("PRISTINE_VS_FORK_DELTA_PIN.json")
    assert "no_ranking" in delta
    # The prohibition is on RANKING claims. A disclaimer that names the
    # forbidden words in order to exclude them is the opposite of a ranking, so
    # the text is checked for ranking assertions rather than for the words.
    text = json.dumps(delta).lower()
    for forbidden in ("winner", "better engine", "outperforms", "recommend"):
        assert forbidden not in text, forbidden
    assert "no preferred provider" in text or "no_ranking" in delta
    # The comparison must be by classified dimension, and the headline fork
    # finding must be present rather than averaged away.
    classifications = delta["counts_by_classification"]
    assert classifications.get("BRIDGE_DIFFERENCE", 0) > 0
    assert classifications.get("LAB_FORK_REGRESSION_OR_REPAIR_ABSENT_ON_PRISTINE", 0) > 0, (
        "the AF03 legality difference must be recorded, not smoothed out"
    )


def test_pb09_does_not_repin_the_manifest_or_resolve_the_decision() -> None:
    secondary = json.loads(CONFIG.read_text(encoding="utf-8"))["secondary_engine"]
    assert secondary["commit"] == PIN, "PB-09 must not move the Forge candidate pin"
    assert secondary["bridge_source"]["commit"] == BRIDGE_PIN
    identity = secondary["engine_identity_pb09"]
    assert identity["pb09_status"].startswith("OPEN")
    # The pristine verification is recorded in the PB-09 evidence tree, not by
    # rewriting the fork lane's identity block: that block describes what the
    # fork-lane evidence is about, and the two lanes must stay distinguishable.
    assert identity["upstream_baseline"]["verified_pristine"] is False


def test_lane_b_records_the_current_bridge_cannot_build_on_pristine() -> None:
    lane_b = json.loads((DOCS / "LANE_B_CURRENT_BRIDGE_RECEIPT.json").read_text(encoding="utf-8"))
    assert lane_b["build_result"]["rc"] == 1
    assert lane_b["classification"].startswith("MISSING_ENGINE_CAPABILITY")
    symbols = {
        entry["symbol"].split("#")[0].split("(")[0] for entry in lane_b["missing_rules_core_apis"]
    }
    assert "forge.game.combat.CombatDamageSelection" in symbols
    assert "forge.game.player.DividedAllocationDecision" in symbols
    # The receipt must record that the missing APIs were NOT ported into the
    # pristine candidate; a lane that "fixed" the build by importing Lab Rules
    # code would no longer be evidence about pristine upstream.
    forbidden = lane_b["materialization"]["forbidden_repairs_not_applied"]
    assert any("NOT ported" in entry for entry in forbidden)
    assert any("Rules semantic patch" in entry for entry in forbidden)


def test_candidate_receipt_claims_pristine_only_with_proof() -> None:
    receipt = json.loads((DOCS / "PRISTINE_CANDIDATE_RECEIPT.json").read_text(encoding="utf-8"))
    assert receipt["PRISTINE_SOURCE_IDENTITY"] == "DIRECTLY_VERIFIED"
    assert receipt["candidate"]["commit"] == PIN
    # Pristine means the upstream remote actually serves this commit, verified
    # from two independent remotes, and that the tree carries no Lab module.
    assert receipt["remote_identity_proof"]["cross_remote_check"]["tree_identical_across_remotes"]
    assert receipt["workspace"]["contains_forge_protocol2_bridge"] is False
    # Every Rules-Core module is byte-identical between the pin and the bridge
    # source that will execute it; that is what makes the lane about the pin.
    modules = receipt["rules_core_byte_identity"]["modules"]
    assert len(modules) == 6
    assert all(entry["identical"] for entry in modules.values())
