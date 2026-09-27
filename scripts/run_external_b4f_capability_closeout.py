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
REPLAY_PATH = ARTIFACTS / "XMAGE_B4F_PHASE6_REPLAY.json"
ILLEGAL_PATH = ARTIFACTS / "XMAGE_B4F_ILLEGAL_ACTION_REJECTION.json"
B4C_PATH = ARTIFACTS / "XMAGE_B4C_ACTION_REGRESSION.json"
DESCRIPTOR_PATH = ARTIFACTS / "XMAGE_B4F_CAPABILITIES.json"
BINDING_PATH = ARTIFACTS / "XMAGE_B4F_CAPABILITY_BINDING.json"
SCENARIO_CONTRACT = "provider_state_injection_v1"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"B4-F required evidence is missing: {path.relative_to(ROOT)}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"B4-F evidence is not an object: {path.relative_to(ROOT)}")
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


def _require_passed(payload: dict[str, Any], label: str) -> None:
    if payload.get("status") != "passed":
        raise SystemExit(f"B4-F prerequisite did not pass: {label}")


def main() -> None:
    config = _load_json(CONFIG_PATH)
    replay = _load_json(REPLAY_PATH)
    illegal = _load_json(ILLEGAL_PATH)
    b4c = _load_json(B4C_PATH)
    _require_passed(replay, "deterministic Phase-6 reconstruction replay")
    _require_passed(illegal, "illegal-action rejection")
    _require_passed(b4c, "B4-C bounded state-bound submission")

    if not BRIDGE_JAR.exists():
        raise SystemExit("B4-F bridge artifact is missing")
    bridge_sha256 = _sha256_file(BRIDGE_JAR)
    fixture_sha256 = _sha256_file(FIXTURE_PATH)
    replay_sha256 = _sha256_file(REPLAY_PATH)
    illegal_sha256 = _sha256_file(ILLEGAL_PATH)
    b4c_sha256 = _sha256_file(B4C_PATH)

    xmage_commit = os.getenv("XMAGE_COMMIT", "").strip()
    primary = config.get("primary_engine")
    if not isinstance(primary, dict):
        raise SystemExit("B4-F rules engine config has no primary_engine object")
    configured_commit = str(primary.get("commit", ""))
    configured_protocol = str(config.get("protocol_version", ""))
    if xmage_commit != configured_commit:
        raise SystemExit(
            f"B4-F XMage pin mismatch: environment={xmage_commit}, config={configured_commit}"
        )
    if configured_protocol != ENGINE_PROTOCOL_VERSION:
        raise SystemExit("B4-F protocol pin mismatch between config and Python protocol contract")
    if replay.get("provider_commit") != xmage_commit:
        raise SystemExit("B4-F replay evidence is bound to a different XMage commit")
    if replay.get("scenario_contract") != SCENARIO_CONTRACT:
        raise SystemExit("B4-F replay evidence uses a different scenario contract")
    if illegal.get("player_count") != 4:
        raise SystemExit("B4-F illegal-action evidence is not four-player Commander evidence")
    if not illegal.get("state_unchanged_after_rejection"):
        raise SystemExit("B4-F illegal-action rejection did not preserve provider state")
    if not illegal.get("decision_unchanged_after_rejection"):
        raise SystemExit("B4-F illegal-action rejection did not preserve the current decision")
    if not b4c.get("stale_pass_rejected") or not b4c.get("stale_submit_rejected"):
        raise SystemExit("B4-F prerequisite stale-action rejection is not proven")

    adapter = ExternalRulesAdapter(
        RulesBackend.XMAGE,
        cwd=ROOT,
        request_timeout_seconds=120.0,
    )
    try:
        probe = adapter.probe()
        if probe.availability is not RulesEngineAvailability.AVAILABLE:
            raise SystemExit(f"B4-F provider pin probe failed: {probe.model_dump(mode='json')}")
        provider = adapter.get_provider_version()
        handshake = adapter.get_capabilities()
    finally:
        with contextlib.suppress(Exception):
            adapter.shutdown_engine()
        adapter.close()

    if provider.get("engine") != "xmage":
        raise SystemExit("B4-F provider identified as a non-XMage engine")
    if provider.get("engine_commit") != xmage_commit:
        raise SystemExit("B4-F live provider commit does not match the configured XMage pin")
    if provider.get("protocol_version") != configured_protocol:
        raise SystemExit("B4-F live provider protocol does not match the configured protocol")

    broad_claims_expected_false = {
        "legal_actions_supported": handshake.legal_actions_supported,
        "action_submission_supported": handshake.action_submission_supported,
        "replay_supported": handshake.replay_supported,
        "seed_supported": handshake.seed_supported,
        "starting_state_injection_supported": handshake.starting_state_injection_supported,
        "scenario_injection_supported": handshake.scenario_injection_supported,
    }
    unexpectedly_broad = sorted(
        name for name, value in broad_claims_expected_false.items() if value
    )
    if unexpectedly_broad:
        raise SystemExit(
            "B4-F unexpectedly widened global provider claims: " + ", ".join(unexpectedly_broad)
        )

    descriptor = {
        "schema_version": "1.0.0",
        "provider": "xmage",
        "provider_version": provider.get("engine_version"),
        "provider_commit": xmage_commit,
        "protocol": configured_protocol,
        "scope": "decision_relevant_four_player_commander_b4f_bounded_capabilities",
        "evidence_class": "external_rules_engine",
        "production_ready": False,
        "provider_selected_for_production": False,
        "scenario_contract": SCENARIO_CONTRACT,
        "bounded_proven_capabilities": {
            "real_four_player_commander_runtime": "PROVEN",
            "frozen_phase6_provider_state_reconstruction": "PROVEN",
            "commander_tax_third_cast_state_and_cost": "PROVEN",
            "commander_damage_state_based_loss_from_separated_injected_watcher_state": "PROVEN",
            "commander_damage_twenty_one_state_based_loss_from_injected_watcher_state": "PROVEN",
            "current_priority_machine_readable_legal_actions": "PROVEN_BOUNDED",
            "state_bound_targetless_nonmodal_submission": "PROVEN_BOUNDED",
            "stale_action_rejection": "PROVEN_BOUNDED",
            "non_enumerated_current_decision_action_rejection": "PROVEN_BOUNDED",
            "phase6_reconstruction_replay_across_fresh_provider_processes": "PROVEN",
        },
        "explicitly_not_proven": {
            "global_legal_action_completeness": "NOT_PROVEN",
            "global_action_submission_completeness": "NOT_PROVEN",
            "arbitrary_starting_state_injection": "NOT_PROVEN",
            "seed_control": "NOT_PROVEN",
            "full_game_deterministic_replay": "NOT_PROVEN",
            "target_mode_choice_and_combat_submission_coverage": "NOT_PROVEN",
            "commander_damage_combat_attribution_per_commander": "NOT_PROVEN",
        },
        "normalization_boundary": {
            "provider_observed": [
                "commander_tax total spell cost after XMage commander-cost modification",
                "player_loses after XMage Commander state-based actions",
            ],
            "adapter_derived": [
                "commander_tax as total-minus-base cost",
                "legal as a fixture-contract validation flag",
                "loss_reason label from frozen fixture scope",
                "maximum_single_commander_damage summary from injected CommanderInfoWatcher state",
            ],
        },
        "global_handshake_preserved": handshake.model_dump(mode="json"),
        "automatic_fidelity_reclassification": False,
        "status": "passed",
    }
    descriptor_sha256 = _sha256_json(descriptor)

    binding_material = {
        "provider": "xmage",
        "xmage_commit": xmage_commit,
        "bridge_artifact_sha256": bridge_sha256,
        "protocol": configured_protocol,
        "scenario_contract": SCENARIO_CONTRACT,
        "frozen_fixture_set": str(FIXTURE_PATH.relative_to(ROOT)),
        "frozen_fixture_set_sha256": fixture_sha256,
        "phase6_replay_evidence_sha256": replay_sha256,
        "illegal_action_evidence_sha256": illegal_sha256,
        "b4c_action_evidence_sha256": b4c_sha256,
        "capability_descriptor_sha256": descriptor_sha256,
    }
    capability_hash = _sha256_json(binding_material)
    binding = {
        "schema_version": "1.0.0",
        "binding_material": binding_material,
        "capability_hash_algorithm": "sha256(canonical_json(binding_material))",
        "capability_hash": capability_hash,
        "status": "passed",
    }

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    DESCRIPTOR_PATH.write_text(
        json.dumps(descriptor, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    BINDING_PATH.write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(DESCRIPTOR_PATH.read_text(encoding="utf-8"))
    print(BINDING_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
