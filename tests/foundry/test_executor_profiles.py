"""Hermetic guards for the two-profile routed OpenCode Foundry execution."""

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
        "step": ("opencode/step-5-preview-free", "high"),
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
    # Owner directive 2026-10-10: Step 5 Preview HIGH only; DeepSeek is SUSPENDED.
    assert doc["current_runtime_default"] == "step"
    assert doc["profiles"]["deepseek"]["runtime_status"] == "SUSPENDED"
    assert doc["profiles"]["deepseek"]["suspension"]["since"] == "2026-10-10"
    assert doc["profiles"]["step"]["runtime_status"] == "ACTIVE"
    assert set(doc["profiles"]) == {"deepseek", "step"}


def test_routing_policy_is_stable_and_fallback_free() -> None:
    doc = _registry()
    routing = doc["routing_policy"]
    assert routing["primary"] == "step"
    assert routing["suspended"] == ["deepseek"]
    assert "secondary" not in routing
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
        keys = {"model", "native_variant", "runtime_status"}
        if profile["runtime_status"] == "SUSPENDED":
            keys.add("suspension")  # durable reason and Owner authority, no quota data
        assert set(profile) == keys, profile


def test_activation_evidence_records_authenticated_runtime_verification() -> None:
    """Every active profile carries its own authenticated runtime evidence."""
    doc = _registry()
    gate = doc["activation_gate"]
    historical = gate["activation_evidence_2026_09_29"]
    current = gate["activation_evidence_2026_10_12"]

    # The DeepSeek evidence block keeps its meaning: an authenticated smoke that
    # ran, and a no-fallback claim that is spelled out term by term.
    assert "RUNTIME_VERIFIED" in historical["deepseek_authenticated_smoke"]
    no_fallback = historical["no_fallback"]
    assert "no retry" in no_fallback.lower()
    assert "provider switch" in no_fallback.lower()
    assert "profile change" in no_fallback.lower()

    active = doc["profiles"]["step"]
    assert active["model"] == "opencode/step-5-preview-free"
    assert active["runtime_status"] == "ACTIVE"
    # The 2026-10-12 block is the activation evidence for the Zen identity.
    assert current["current_model_identity"] == active["model"]
    assert current["runtime_status"] == active["runtime_status"]
    assert "step-5-preview-free" in current["live_catalog_identity"]
    assert "high" in current["native_variant_choice"]
    # The Zen catalog lists no max variant for this model, so the pin is `high`.
    assert active["native_variant"] == "high"


def test_runtime_identity_admits_only_the_zen_step_id() -> None:
    """Step 5 Preview admits exactly its Zen id; no Go id or legacy alias."""
    doc = _registry()
    identity = doc["runtime_identity"]
    assert identity["opencode-go/deepseek-v4.1-flash"] == {
        "logical_profile": "deepseek",
        "alias_class": "CANONICAL",
    }
    assert identity["opencode/step-5-preview-free"] == {
        "logical_profile": "step",
        "alias_class": "CANONICAL",
    }
    assert "opencode-go/retired" not in identity
    assert "opencode-go/retired-free" not in identity
    assert len(identity) == 2
    logical_profiles = {entry["logical_profile"] for entry in identity.values()}
    assert logical_profiles == {"deepseek", "step"}
    policy = doc["resolution_policy"]
    assert policy["logical_profiles"] == ["deepseek", "step"]
    assert policy["step_preference"] == ["opencode/step-5-preview-free"]
    assert policy["automatic_fallback"] is False
    assert policy["post_selection_failure"] == "FAIL_CLOSED_NO_RE_RESOLUTION"


def test_cross_executor_review_policy_is_declared_and_strict() -> None:
    """Durable registry declares the mandatory read-only cross-executor gate."""
    policy = _registry()["cross_executor_review_policy"]
    assert policy["required_for_material"] is True
    # While DeepSeek is SUSPENDED Step 5 Preview implements and reviews (Owner
    # approval 2026-10-10); the review stays fresh-context and read-only.
    assert policy["implementation_executor"] == "step"
    assert policy["review_independence"] == (
        "FRESH_CONTEXT_SAME_MODEL_WHILE_NO_OTHER_PROFILE_IS_ACTIVE"
    )
    assert policy["review_executor"] == "step"
    assert policy["review_mode"] == "READ_ONLY_FRESH_CONTEXT"
    assert set(policy["review_agents"]) == {"foundry-reviewer"}
    assert policy["pass_verdict"] == "PASS"
    assert "MATERIAL_DELTA_AFTER_REVIEW" in policy["re_review_on"]
    assert "P1_REPAIR" in policy["re_review_on"]
    assert "P2_REPAIR" in policy["re_review_on"]
    assert policy["unsatisfied_executors"] == ["deepseek"]
    assert policy["remote_resumability"] == "REQUIRES_REMOTE_CHECKPOINT_EQUALITY"


def test_unperformed_smoke_cannot_pass_for_runtime_verification() -> None:
    """An activation block must not present an unperformed smoke as proof.

    The 2026-10-12 Step activation names the observation that still has to
    happen; a marker echo or a locally refused run must never read as a PASS.
    """
    doc = _registry()
    current = doc["activation_gate"]["activation_evidence_2026_10_12"]
    smoke = current["authenticated_runtime_smoke"]

    assert smoke.startswith("NOT_RUN")
    assert "RUNTIME_VERIFIED" not in smoke
    assert "exit 0" not in smoke
    assert "Rate limit exceeded" in smoke


def test_activation_evidence_is_not_a_workstream_state_record() -> None:
    """Activation evidence must stay evidence-shaped, not workstream state.

    Content markers the state-conformance sweep detects; adding either would
    masquerade the evidence block as a workstream state record.
    """
    doc = _registry()
    for name, block in doc["activation_gate"].items():
        if not name.startswith("activation_evidence_"):
            continue
        assert "objective" not in block, name
        assert "workstream" not in block, name


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
    assert set(props["execution_profile"]["enum"]) == {"deepseek", "step", None}
    assert set(props["native_variant"]["enum"]) == {"max", None}
    for key in (
        "executor_model",
        "variant_resolution",
        "executor_handoff_from",
        "executor_handoff_reason",
    ):
        assert key in props
    # Exact runtime identity provenance for the two-profile + alias policy.
    assert set(props["logical_executor_profile"]["enum"]) == {"deepseek", "step", None}
    assert set(props["model_alias_class"]["enum"]) == {"CANONICAL", "LEGACY_ALIAS", None}
    assert "resolved_provider" in props
    assert "resolved_model_id" in props


def test_state_schema_can_persist_cross_executor_review_policy() -> None:
    """The durable schema carries the materiality/review/checkpoint contract."""
    schema = json.loads(
        (ROOT / ".foundry" / "WORKSTREAM_STATE.schema.json").read_text(encoding="utf-8")
    )
    props = schema["properties"]
    assert "validated_tree" in props
    assert set(props["materiality"]["enum"]) == {"MATERIAL", "NON_MATERIAL", None}
    mirror = props["cross_executor_review"]
    assert mirror["additionalProperties"] is False
    for key in (
        "required",
        "logical_profile",
        "resolved_model_id",
        "model_alias_class",
        "implementation_executor",
        "review_executor",
        "reviewed_sha",
        "reviewed_tree",
        "verdict",
        "review_record_path",
    ):
        assert key in mirror["properties"], key
    assert set(mirror["properties"]["verdict"]["enum"]) == {
        "PASS",
        "FAIL",
        "PARTIAL",
        "UNKNOWN",
        "BLOCKED",
        "STALE",
    }
    checkpoint = props["remote_checkpoint"]
    assert checkpoint["additionalProperties"] is False
    assert checkpoint["required"] == ["remote", "branch", "sha", "tree"]
    # Historical state compatibility: every new field is optional.
    assert "materiality" not in schema["required"]
    assert "cross_executor_review" not in schema["required"]
    assert "remote_checkpoint" not in schema["required"]
    assert "validated_tree" not in schema["required"]


def test_engine_repo_profiles_use_canonical_lab_injection() -> None:
    for name in ("forge", "mage"):
        profile = json.loads(
            (ROOT / ".foundry" / "repo-profiles" / f"{name}.json").read_text(encoding="utf-8")
        )
        assert profile["foundry_policy_mode_2026_09_28"] == (
            "CANONICAL_LAB_INJECTION_NO_FORK_ROOT_CONFIG"
        )
        assert profile["multimodel_policy_source"].endswith(".foundry/executor-profiles.json")
