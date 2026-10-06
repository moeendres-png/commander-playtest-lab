"""Hermetic guards for the two-model routed OpenCode Go Foundry execution."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _registry() -> dict:
    return json.loads((ROOT / ".foundry" / "executor-profiles.json").read_text(encoding="utf-8"))


def test_selected_profiles_and_highest_native_efforts_are_exact() -> None:
    doc = _registry()
    expected = {
        "deepseek": ("opencode-go/deepseek-v4.1-flash", "max"),
        "space-bunny": ("opencode-go/space-bunny", "max"),
    }
    actual = {
        name: (spec["model"], spec["native_variant"]) for name, spec in doc["profiles"].items()
    }
    assert actual == expected
    assert doc["policy"]["highest_supported_effort_only"] is True
    assert doc["policy"]["automatic_fallback"] is False


def test_registry_does_not_prescribe_task_routing_or_model_preference() -> None:
    doc = _registry()
    assert doc["policy"]["repository_prescribes_task_routing"] is False
    for forbidden in (
        "preferred_future_workhorse_candidate",
        "preferred_model",
        "recommended_model",
        "default_task_model",
    ):
        assert forbidden not in doc

    for profile in doc["profiles"].values():
        for forbidden in (
            "intended_role",
            "intended_frequency",
            "task_role",
            "task_classes",
            "recommended_for",
            "preferred_for",
        ):
            assert forbidden not in profile


def test_prepared_profiles_do_not_falsely_claim_runtime_activation() -> None:
    doc = _registry()
    assert doc["status"] == "ACTIVE"
    assert doc["current_runtime_default"] == "deepseek"
    assert doc["profiles"]["deepseek"]["runtime_status"] == "ACTIVE"
    assert doc["profiles"]["space-bunny"]["runtime_status"] == "ACTIVE"
    assert set(doc["profiles"]) == {"deepseek", "space-bunny"}


def test_routing_policy_is_stable_and_fallback_free() -> None:
    doc = _registry()
    routing = doc["routing_policy"]
    assert routing["primary"] == "deepseek"
    assert routing["secondary"] == "space-bunny"
    assert "inactive" not in routing
    assert routing["automatic_fallback"] is False
    assert doc["policy"]["automatic_fallback"] is False
    # Durable policy only: no volatile price/quota/availability *data* anywhere in
    # the registry. Key names and prose disclaiming them are allowed.
    blob = json.dumps(doc).lower()
    for forbidden in (
        "price_per_million",
        "usd_per",
        "cost_per",
        "quota_remaining",
        "tokens_per_",
        "rate_limit",
        "context_limit",
        "1m_tokens",
    ):
        assert forbidden not in blob, forbidden
    for profile in doc["profiles"].values():
        assert set(profile) == {"model", "native_variant", "runtime_status"}, profile


def test_activation_evidence_records_authenticated_runtime_verification() -> None:
    """runtime_status=ACTIVE must be backed by real runtime evidence, not config parsing."""
    evidence = _registry()["activation_gate"]["activation_evidence_2026_09_29"]
    for key in (
        "live_catalog_identity",
        "deepseek_authenticated_smoke",
        "space_bunny_authenticated_smoke",
        "native_variant_pin",
        "no_fallback",
    ):
        assert key in evidence, key
    assert "deepseek-v4.1-flash" in evidence["live_catalog_identity"]
    assert "RUNTIME_VERIFIED" in evidence["deepseek_authenticated_smoke"]
    assert "RUNTIME_VERIFIED" in evidence["space_bunny_authenticated_smoke"]


def test_activation_gate_requires_atomic_launcher_and_config_change() -> None:
    required = set(_registry()["activation_gate"]["required_surfaces"])
    assert "tools/foundry/launcher.py" in required
    assert "tests/foundry/test_launcher.py" in required
    assert "opencode.json" in required
    assert "AGENTS.md" in required
    validations = set(_registry()["activation_gate"]["required_validation"])
    assert (
        "authenticated bounded smoke for each newly activated profile before marking runtime ACTIVE"
        in validations
    )


def test_state_schema_can_persist_cross_model_execution_provenance() -> None:
    schema = json.loads(
        (ROOT / ".foundry" / "WORKSTREAM_STATE.schema.json").read_text(encoding="utf-8")
    )
    props = schema["properties"]
    assert set(props["execution_profile"]["enum"]) == {"deepseek", "space-bunny", None}
    assert set(props["native_variant"]["enum"]) == {"max", None}
    for key in (
        "executor_model",
        "variant_resolution",
        "executor_handoff_from",
        "executor_handoff_reason",
    ):
        assert key in props


def test_engine_repo_profiles_use_canonical_lab_injection() -> None:
    for name in ("forge", "mage"):
        profile = json.loads(
            (ROOT / ".foundry" / "repo-profiles" / f"{name}.json").read_text(encoding="utf-8")
        )
        assert profile["foundry_policy_mode_2026_09_28"] == (
            "CANONICAL_LAB_INJECTION_NO_FORK_ROOT_CONFIG"
        )
        assert profile["multimodel_policy_source"].endswith(".foundry/executor-profiles.json")
