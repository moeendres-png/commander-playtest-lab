"""R-1 / PB-09: current Forge candidate identity after owner adjudication.

R-1 (2026-09-30) admits the Commander-Lab-maintained Forge fork for
exact-source qualification. Historical source locks and freeze-readiness
artifacts remain historical and are not rewritten. Current role identity remains
explicit: candidate/source, Rules-Core lineage base, bridge/materialization
role, upstream reference baseline and historical evidence tip are not
interchangeable merely because some roles share a Git commit.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

from commander_lab.qualification.current_boundary import source_lock as sl
from commander_lab.qualification.current_boundary.receipts import (
    ReceiptError,
    verify_candidate_identity,
    verify_engine_identity,
)

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "config/rules_engines.json"
HISTORICAL_READINESS = (
    REPO / "docs/architecture_freeze_readiness_20260927/FORGE_FREEZE_READINESS.json"
)

CANDIDATE = "e22c424adde043e23892e4bb59aaeb4d2fb089d9"
CANDIDATE_TREE = "6c49f100fe61d1b2a71dd46a7347a2ff0f0da4ea"
LINEAGE_BASE = "ef958ee91ac6c9ce0152189f2654bf6e05abf273"
UPSTREAM_REFERENCE = "a37a865a53280dd8ad6fad3384d69611e8c5a42f"
HISTORICAL_WSR20 = "18bba95a4528f6ab5910633f1f87f603b8c4ddf8"


def _config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def test_r1_current_machine_authority_is_the_maintained_fork() -> None:
    secondary = _config()["secondary_engine"]
    assert secondary["repository"] == "https://github.com/moeendres-png/forge.git"
    assert secondary["commit"] == CANDIDATE
    assert secondary["source_archive"].endswith(f"/{CANDIDATE}.tar.gz")
    assert "R-1" in secondary["commit_meaning"]
    assert "Production Provider" in secondary["commit_meaning"]


def test_current_candidate_and_bridge_roles_share_exact_source_intentionally() -> None:
    secondary = _config()["secondary_engine"]
    bridge = secondary["bridge_source"]
    assert bridge["repository"] == secondary["repository"]
    assert bridge["commit"] == secondary["commit"] == CANDIDATE
    assert bridge["rules_core_base_commit"] == CANDIDATE
    assert bridge["qualification_lineage_base_commit"] == LINEAGE_BASE
    assert "Same SHA" in bridge["role"]


def test_pb09_is_resolved_for_current_qualification_without_selecting_provider() -> None:
    config = _config()
    identity = config["secondary_engine"]["engine_identity_pb09"]
    assert identity["pb09_status"].startswith("RESOLVED_BY_OWNER_R1")
    assert identity["current_candidate"]["commit"] == CANDIDATE
    assert identity["current_candidate"]["tree"] == CANDIDATE_TREE
    assert identity["qualification_lineage_base"]["commit"] == LINEAGE_BASE
    assert identity["upstream_baseline"]["commit"] == UPSTREAM_REFERENCE
    assert identity["historical_native_suite_execution_root"]["commit"] == HISTORICAL_WSR20
    assert config["provider_decision"] == "NO_PROVIDER_READY"
    assert config["current_runtime"]["provider_selected"] is False
    assert config["current_runtime"]["production_provider"] is None


def test_active_source_lock_matches_current_machine_authority() -> None:
    receipt = sl.boundary_receipt()["candidates"]["forge"]
    identity = receipt["engine_identity_pb09"]
    assert sl.FORGE_CANDIDATE_COMMIT == CANDIDATE
    assert sl.FORGE_CANDIDATE_TREE == CANDIDATE_TREE
    assert receipt["candidate_commit"] == CANDIDATE
    assert identity["executing_engine"]["commit"] == CANDIDATE
    assert identity["bridge_source_commit"]["commit"] == CANDIDATE
    assert identity["qualification_lineage_base"]["commit"] == LINEAGE_BASE
    assert identity["upstream_baseline"]["commit"] == UPSTREAM_REFERENCE
    assert identity["wsr20_evidence_tip"]["commit"] == HISTORICAL_WSR20
    assert identity["pb09_status"].startswith("RESOLVED_BY_OWNER_R1")


def test_historical_readiness_is_not_rewritten_by_r1() -> None:
    document = json.loads(HISTORICAL_READINESS.read_text(encoding="utf-8"))
    identity = document["engine_identity_pb09"]
    assert identity["executing_engine"]["commit"] == LINEAGE_BASE
    assert identity["upstream_baseline"]["commit"] == UPSTREAM_REFERENCE
    assert identity["pb09_status"].startswith("OPEN")
    assert CANDIDATE not in json.dumps(document)


def test_upstream_reference_is_not_current_candidate_identity() -> None:
    with pytest.raises(ReceiptError, match="CANDIDATE_IDENTITY_DIVERGENCE"):
        verify_candidate_identity(
            recorded_commit=CANDIDATE,
            actual_commit=UPSTREAM_REFERENCE,
            recorded_label="forge current candidate",
        )


def _commit(repo: Path, message: str) -> str:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", message],
        cwd=repo,
        check=True,
    )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


def test_bridge_only_descendant_can_be_rules_core_equivalent() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        (repo / "forge-game/src/main/java").mkdir(parents=True)
        (repo / "forge-game/src/main/java/Engine.java").write_text("class Engine {}\n")
        (repo / "forge-protocol2-bridge/src/main/java").mkdir(parents=True)
        (repo / "forge-protocol2-bridge/src/main/java/Bridge.java").write_text("class Bridge {}\n")
        base = _commit(repo, "candidate")

        (repo / "forge-protocol2-bridge/src/main/java/Bridge.java").write_text(
            "class Bridge { int revision; }\n"
        )
        descendant = _commit(repo, "bridge only")

        proof = verify_engine_identity(repo, base, descendant, recorded_label="forge")
        assert proof["engine_equivalent"] is True
        assert proof["differing_modules"] == []


def test_rules_core_drift_still_fails_closed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        (repo / "forge-game/src/main/java").mkdir(parents=True)
        (repo / "forge-game/src/main/java/Engine.java").write_text("class Engine {}\n")
        base = _commit(repo, "candidate")

        (repo / "forge-game/src/main/java/Engine.java").write_text("class Engine { int x; }\n")
        descendant = _commit(repo, "rules drift")

        with pytest.raises(ReceiptError, match="CANDIDATE_IDENTITY_DIVERGENCE"):
            verify_engine_identity(repo, base, descendant, recorded_label="forge")
