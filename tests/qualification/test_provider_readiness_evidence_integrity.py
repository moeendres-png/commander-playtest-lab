"""Ambiguous sealed evidence must refuse even when every digest is valid."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
EPOCH = "b1c8f54a999a-2d13b953a82c"
EPOCH_REL = Path("qualification/current-boundary-epochs") / EPOCH


@pytest.fixture(scope="module")
def generator() -> Any:
    spec = importlib.util.spec_from_file_location(
        "provider_readiness_integrity", REPO / "scripts/build_provider_readiness_packet.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def sealed_repo(tmp_path: Path) -> Path:
    """A separate source root with the epoch and its current binding dependencies."""
    shutil.copytree(REPO / EPOCH_REL, tmp_path / EPOCH_REL)
    pointer_rel = Path("qualification/CURRENT_PRE_FREEZE_CONTRACT.json")
    pointer = json.loads((REPO / pointer_rel).read_text(encoding="utf-8"))
    dependencies = (
        "config/rules_engines.json",
        "qualification/xmage-sba-priority-repin-v4-20261003/SUCCESSOR_SOURCE_LOCK.json",
        str(pointer_rel),
        pointer["full107"]["successor_contract"],
        pointer["full107"]["effective_materialization_schema"],
    )
    for relative in dependencies:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / relative, target)
    return tmp_path


def reseal(repo: Path) -> None:
    """Mutation controls deliberately pass the byte-integrity gate."""
    root = repo / EPOCH_REL
    manifest = root / "CURRENT_BOUNDARY_SHA256SUMS"
    entries = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(repo)}\n"
        for path in sorted(root.rglob("*"))
        if path.is_file() and path != manifest
    ]
    manifest.write_text("".join(entries), encoding="utf-8")


def test_unambiguous_copied_epoch_preserves_packet(generator: Any, sealed_repo: Path) -> None:
    assert generator.build_packet(sealed_repo, EPOCH) == generator.build_packet(REPO, EPOCH)


@pytest.mark.parametrize(
    ("artifact", "diagnostic", "conflicting"),
    (
        ("CURRENT_BOUNDARY_COMPARISON.json", "duplicate comparison fixture", False),
        ("CURRENT_BOUNDARY_COMPARISON.json", "duplicate comparison fixture", True),
        ("EFFECTIVE_FULL107_MANIFEST.json", "duplicate effective manifest fixture", False),
        ("EFFECTIVE_FULL107_MANIFEST.json", "duplicate effective manifest fixture", True),
    ),
)
def test_resealed_duplicate_fixture_refuses(
    generator: Any, sealed_repo: Path, artifact: str, diagnostic: str, conflicting: bool
) -> None:
    target = sealed_repo / EPOCH_REL / artifact
    document = json.loads(target.read_text(encoding="utf-8"))
    duplicate = copy.deepcopy(document["rows"][0])
    if conflicting:
        if artifact == "CURRENT_BOUNDARY_COMPARISON.json":
            duplicate["disposition"] = next(
                value
                for value in sorted(generator.FIXTURE_CLASS_VOCABULARY)
                if value != duplicate["disposition"]
            )
        else:
            duplicate["effective_requested_state_digest"] = "0" * 64
    document["rows"].append(duplicate)
    target.write_text(json.dumps(document), encoding="utf-8")
    reseal(sealed_repo)
    receipt = generator.verify_epoch(sealed_repo / EPOCH_REL, sealed_repo)
    assert receipt["verified"] == receipt["entries"]
    with pytest.raises(generator.FailClosed, match=diagnostic):
        generator.build_packet(sealed_repo, EPOCH)


@pytest.mark.parametrize(
    "payload",
    (
        '{"verdict":"FAIL","verdict":"PASS"}',
        '{"gate":{"verdict":"FAIL","verdict":"PASS"}}',
        '{"verdict":"PASS","verdict":"PASS"}',
    ),
)
def test_duplicate_json_keys_refuse(generator: Any, tmp_path: Path, payload: str) -> None:
    target = tmp_path / "evidence.json"
    target.write_text(payload, encoding="utf-8")
    with pytest.raises(generator.FailClosed, match="duplicate JSON key"):
        generator._load_json(target)


def test_sealed_duplicate_json_key_refuses(generator: Any, sealed_repo: Path) -> None:
    target = sealed_repo / EPOCH_REL / "CURRENT_BOUNDARY_COMPARISON.json"
    original = target.read_text(encoding="utf-8")
    # The second rows key would silently replace the first under ordinary json.loads.
    target.write_text('{"rows":[], ' + original.lstrip()[1:], encoding="utf-8")
    reseal(sealed_repo)
    generator.verify_epoch(sealed_repo / EPOCH_REL, sealed_repo)
    with pytest.raises(generator.FailClosed, match="duplicate JSON key"):
        generator.build_packet(sealed_repo, EPOCH)


def test_requested_root_binds_current_pins(generator: Any, sealed_repo: Path) -> None:
    target = sealed_repo / "config/rules_engines.json"
    config = json.loads(target.read_text(encoding="utf-8"))
    changed_commit = "f" * 40
    config["secondary_engine"]["bridge_source"]["commit"] = changed_commit
    config["secondary_engine"]["engine_identity_pb09"]["bridge_source"]["commit"] = changed_commit
    target.write_text(json.dumps(config), encoding="utf-8")
    packet = generator.build_packet(sealed_repo, EPOCH)
    assert packet["source_lock"]["engine_pins"]["forge_bridge_source"]["commit"] == changed_commit
    assert (
        packet["source_lock"]["engine_pins"]["config_sha256"]
        == hashlib.sha256(target.read_bytes()).hexdigest()
    )
    bridge_drift = next(
        record
        for record in packet["source_lock"]["drift_records"]
        if record["subject"] == "forge bridge/materialization commit"
    )
    assert bridge_drift["pin"] == changed_commit
    assert bridge_drift["verdict"] == "DIFFERS"


def test_requested_root_rejects_inconsistent_pins(generator: Any, sealed_repo: Path) -> None:
    target = sealed_repo / "config/rules_engines.json"
    config = json.loads(target.read_text(encoding="utf-8"))
    config["secondary_engine"]["bridge_source"]["commit"] = "f" * 40
    target.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(generator.FailClosed, match="two different Forge bridge commits"):
        generator.build_packet(sealed_repo, EPOCH)


def test_requested_root_binds_contract(generator: Any, sealed_repo: Path) -> None:
    pointer = json.loads(
        (sealed_repo / "qualification/CURRENT_PRE_FREEZE_CONTRACT.json").read_text(encoding="utf-8")
    )
    target = sealed_repo / pointer["full107"]["successor_contract"]
    successor = json.loads(target.read_text(encoding="utf-8"))
    successor["contract_id"] = "source-root-mutation-control"
    target.write_text(json.dumps(successor), encoding="utf-8")
    binding = generator.build_packet(sealed_repo, EPOCH)["source_lock"]["effective_contract"]
    assert binding["successor_id"] == successor["contract_id"]
    assert binding["successor_sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()


def test_requested_root_rejects_inconsistent_xmage_lock(generator: Any, sealed_repo: Path) -> None:
    target = (
        sealed_repo
        / "qualification/xmage-sba-priority-repin-v4-20261003/SUCCESSOR_SOURCE_LOCK.json"
    )
    lock = json.loads(target.read_text(encoding="utf-8"))
    lock["lineage"]["final_integrated_candidate"]["commit"] = "f" * 40
    target.write_text(json.dumps(lock), encoding="utf-8")
    with pytest.raises(generator.FailClosed, match="source lock disagrees"):
        generator.build_packet(sealed_repo, EPOCH)
