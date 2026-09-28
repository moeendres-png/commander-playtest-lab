"""Hermetic guards for prepared four-model OpenCode Go Foundry execution."""

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
        "muse": ("opencode-go/muse-spark-1.3-contributor", "xhigh"),
        "glm": ("opencode-go/glm-5.3", "max"),
        "space-bunny": ("opencode-go/space-bunny-free", "max"),
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
    assert doc["status"] == "PREPARED_NOT_RUNTIME_ACTIVE"
    assert doc["current_runtime_default"] == "space-bunny"
    assert doc["profiles"]["deepseek"]["runtime_status"] == "BLOCKED_ON_LAUNCHER_INTEGRATION"
    assert doc["profiles"]["glm"]["runtime_status"] == "BLOCKED_ON_LAUNCHER_INTEGRATION"
    assert doc["profiles"]["muse"]["runtime_status"] == "ACTIVE"
    assert doc["profiles"]["space-bunny"]["runtime_status"] == "ACTIVE"


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
    assert set(props["execution_profile"]["enum"]) == {
        "deepseek",
        "muse",
        "glm",
        "space-bunny",
        "muse-free-zen",
        None,
    }
    assert set(props["native_variant"]["enum"]) == {"xhigh", "max", None}
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
