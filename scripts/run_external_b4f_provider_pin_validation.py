from __future__ import annotations

import contextlib
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from commander_lab.engine.rules.bridge import ExternalRulesAdapter
from commander_lab.models import ENGINE_PROTOCOL_VERSION, RulesBackend, RulesEngineAvailability

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts/external-engine"
CONFIG_PATH = ROOT / "config/rules_engines.json"
FIXTURE_PATH = ROOT / "data/evals/differential/rules_cases.json"
BRIDGE_JAR = ROOT / "engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar"
DESCRIPTOR_PATH = ARTIFACTS / "XMAGE_B4F_CAPABILITIES.json"
BINDING_PATH = ARTIFACTS / "XMAGE_B4F_CAPABILITY_BINDING.json"
OUTPUT = ARTIFACTS / "XMAGE_B4F_PROVIDER_PIN_VALIDATION.json"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"B4-F pin prerequisite missing: {path.relative_to(ROOT)}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"B4-F pin prerequisite is not an object: {path.relative_to(ROOT)}")
    return payload


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_json(payload: object) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def main() -> None:
    config = _load_json(CONFIG_PATH)
    descriptor = _load_json(DESCRIPTOR_PATH)
    binding = _load_json(BINDING_PATH)
    if descriptor.get("status") != "passed" or binding.get("status") != "passed":
        raise SystemExit("B4-F capability descriptor/binding has not passed")

    xmage_commit = os.getenv("XMAGE_COMMIT", "").strip()
    primary = config.get("primary_engine")
    if not isinstance(primary, dict):
        raise SystemExit("B4-F rules engine config has no primary_engine object")
    configured_commit = str(primary.get("commit", ""))
    configured_protocol = str(config.get("protocol_version", ""))
    bridge_sha256 = _sha256_file(BRIDGE_JAR)
    fixture_sha256 = _sha256_file(FIXTURE_PATH)
    descriptor_sha256 = _sha256_json(descriptor)

    material = binding.get("binding_material")
    if not isinstance(material, dict):
        raise SystemExit("B4-F capability binding has no binding_material object")
    expected_material = {
        "provider": "xmage",
        "xmage_commit": xmage_commit,
        "bridge_artifact_sha256": bridge_sha256,
        "protocol": configured_protocol,
        "scenario_contract": "provider_state_injection_v1",
        "frozen_fixture_set": str(FIXTURE_PATH.relative_to(ROOT)),
        "frozen_fixture_set_sha256": fixture_sha256,
        "capability_descriptor_sha256": descriptor_sha256,
    }
    if material != expected_material:
        raise SystemExit(
            "B4-F capability binding material does not match the current pinned runtime artifacts"
        )
    expected_capability_hash = _sha256_json(expected_material)
    if binding.get("capability_hash") != expected_capability_hash:
        raise SystemExit("B4-F capability hash cannot be reproduced from binding material")
    if xmage_commit != configured_commit:
        raise SystemExit("B4-F environment XMage commit differs from config pin")
    if configured_protocol != ENGINE_PROTOCOL_VERSION:
        raise SystemExit("B4-F configured protocol differs from Python protocol contract")

    adapter = ExternalRulesAdapter(
        RulesBackend.XMAGE,
        cwd=ROOT,
        request_timeout_seconds=120.0,
    )
    try:
        probe = adapter.probe()
        if probe.availability is not RulesEngineAvailability.AVAILABLE:
            raise SystemExit(
                f"B4-F final live provider probe failed: {probe.model_dump(mode='json')}"
            )
        provider = adapter.get_provider_version()
    finally:
        with contextlib.suppress(Exception):
            adapter.shutdown_engine()
        adapter.close()

    if provider.get("engine") != "xmage":
        raise SystemExit("B4-F final provider pin validation observed a non-XMage engine")
    if provider.get("engine_commit") != xmage_commit:
        raise SystemExit("B4-F final provider commit does not match the pin")
    if provider.get("protocol_version") != configured_protocol:
        raise SystemExit("B4-F final provider protocol does not match the pin")
    if descriptor.get("provider_commit") != xmage_commit:
        raise SystemExit("B4-F capability descriptor provider commit does not match the pin")
    if descriptor.get("protocol") != configured_protocol:
        raise SystemExit("B4-F capability descriptor protocol does not match the pin")

    evidence = {
        "schema_version": "1.0.0",
        "evidence_class": "external_rules_engine",
        "scope": "xmage_b4f_provider_pin_and_capability_hash_validation",
        "provider": provider,
        "workflow_lab_sha": os.getenv("GITHUB_SHA"),
        "checks": {
            "environment_commit_matches_config": True,
            "live_provider_commit_matches_pin": True,
            "live_provider_protocol_matches_config": True,
            "python_protocol_matches_config": True,
            "descriptor_matches_provider_pin": True,
            "bridge_artifact_sha256_matches_binding": True,
            "frozen_fixture_set_sha256_matches_binding": True,
            "capability_descriptor_sha256_matches_binding": True,
            "capability_hash_recomputed": True,
        },
        "xmage_commit": xmage_commit,
        "bridge_artifact_sha256": bridge_sha256,
        "frozen_fixture_set_sha256": fixture_sha256,
        "capability_descriptor_sha256": descriptor_sha256,
        "capability_hash": expected_capability_hash,
        "status": "passed",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(OUTPUT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
