"""Hermetic guards for the two-model routed OpenCode Go Foundry execution."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _registry() -> dict:
    return json.loads((ROOT / ".foundry" / "executor-profiles.json").read_text(encoding="utf-8"))


def _runtime_activation_receipt() -> dict:
    return json.loads(
        (ROOT / ".foundry" / "space-bunny-rebind-runtime-activation-20261006.json").read_text(
            encoding="utf-8"
        )
    )


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
    """The rebound model identity needs its own authenticated runtime evidence."""
    doc = _registry()
    historical = doc["activation_gate"]["activation_evidence_2026_09_29"]
    current = doc["activation_gate"]["activation_evidence_2026_10_06"]
    receipt = _runtime_activation_receipt()

    assert "RUNTIME_VERIFIED" in historical["deepseek_authenticated_smoke"]
    assert "space-bunny-free" in historical["space_bunny_authenticated_smoke"]
    assert "provenance" in current["historical_scope"].lower()

    # Restored #577 P3 guards: the 2026-09-29 activation evidence keys keep
    # their meaning while profile resolution is refactored for the alias
    # classes. Live catalog identity, native max pinning, and the no-fallback
    # claim must not silently lose their assertions.
    assert "opencode-go/deepseek-v4.1-flash" in historical["live_catalog_identity"]
    assert "opencode-go/space-bunny-free" in historical["live_catalog_identity"]
    assert "no model identity was substituted" in historical["live_catalog_identity"].lower()
    assert "max" in historical["native_variant_pin"]
    assert "no other native level is selectable" in historical["native_variant_pin"]
    no_fallback = historical["no_fallback"]
    assert "no retry" in no_fallback.lower()
    assert "provider switch" in no_fallback.lower()
    assert "profile change" in no_fallback.lower()

    active = doc["profiles"]["space-bunny"]
    assert active["model"] == "opencode-go/space-bunny"
    assert active["runtime_status"] == "ACTIVE"
    assert current["current_model_identity"] == active["model"]
    assert current["runtime_status"] == active["runtime_status"]
    assert (
        current["evidence_classification"]["configured_pins_job_outcome_and_provider_policy"]
        == "DIRECTLY_VERIFIED"
    )
    assert current["evidence_classification"]["resolved_runtime_model_identity"] == "CODE_DERIVED"
    assert (
        current["evidence_receipt"]
        == ".foundry/space-bunny-rebind-runtime-activation-20261006.json"
    )

    assert receipt["evidence_classification"] == current["evidence_classification"]
    assert receipt["status"] == "PASS"
    assert receipt["source_lock"]["main_sha"] == "84c17f9d0fb768812e00ecaef5cb2dcd4db57676"
    assert receipt["trigger"]["workflow_run_id"] == 37522166205
    assert receipt["trigger"]["job_id"] == 112470057434
    assert receipt["execution"]["reported_resolved_model"] == active["model"]
    assert receipt["execution"]["configured_variant"] == active["native_variant"]
    assert receipt["execution"]["primary_deepseek_job_conclusion"] == "skipped"
    assert receipt["observation"]["workflow_job_conclusion"] == "success"
    assert receipt["observation"]["opencode_step_conclusion"] == "success"


def test_runtime_identity_admits_one_canonical_and_one_legacy_bunny_alias() -> None:
    """The legacy runtime id is an alias of the SAME logical profile only."""
    doc = _registry()
    identity = doc["runtime_identity"]
    assert identity["opencode-go/deepseek-v4.1-flash"] == {
        "logical_profile": "deepseek",
        "alias_class": "CANONICAL",
    }
    assert identity["opencode-go/space-bunny"] == {
        "logical_profile": "space-bunny",
        "alias_class": "CANONICAL",
    }
    assert identity["opencode-go/space-bunny-free"] == {
        "logical_profile": "space-bunny",
        "alias_class": "LEGACY_ALIAS",
    }
    logical_profiles = {entry["logical_profile"] for entry in identity.values()}
    assert logical_profiles == {"deepseek", "space-bunny"}
    policy = doc["resolution_policy"]
    assert policy["logical_profiles"] == ["deepseek", "space-bunny"]
    assert policy["space_bunny_preference"] == [
        "opencode-go/space-bunny",
        "opencode-go/space-bunny-free",
    ]
    assert policy["automatic_fallback"] is False
    assert policy["post_selection_failure"] == "FAIL_CLOSED_NO_RE_RESOLUTION"


def test_cross_executor_review_policy_is_declared_and_strict() -> None:
    """Durable registry declares the mandatory read-only cross-executor gate."""
    policy = _registry()["cross_executor_review_policy"]
    assert policy["required_for_material"] is True
    assert policy["implementation_executor"] == "deepseek"
    assert policy["review_executor"] == "space-bunny"
    assert policy["review_mode"] == "READ_ONLY_FRESH_CONTEXT"
    assert set(policy["review_agents"]) == {"foundry-reviewer"}
    assert policy["pass_verdict"] == "PASS"
    assert "MATERIAL_DELTA_AFTER_REVIEW" in policy["re_review_on"]
    assert "P1_REPAIR" in policy["re_review_on"]
    assert "P2_REPAIR" in policy["re_review_on"]
    assert policy["unsatisfied_executors"] == ["deepseek"]
    assert policy["remote_resumability"] == "REQUIRES_REMOTE_CHECKPOINT_EQUALITY"


def test_activation_receipt_classification_cannot_pass_for_wrong_reason() -> None:
    """Controls for the corrected receipt provenance and classification."""
    receipt = _runtime_activation_receipt()

    # The resolved provider/model identity is only as strong as its cited
    # source: the agent's own result comment, not an independently fetched
    # runtime log or artifact.
    assert (
        receipt["execution"]["resolved_identity_source"] == "BUNNY_AGENT_RESULT_COMMENT_6024263751"
    )
    assert receipt["execution"]["resolved_identity_classification"] == "CODE_DERIVED"
    assert receipt["execution"]["reported_provider_id"] == "opencode-go"
    assert receipt["execution"]["reported_model_id"] == "space-bunny"

    # The trigger comment instructed the exact result marker, so a marker echo
    # carries no evidential value and must not survive as runtime proof.
    assert "result_marker" not in receipt["observation"]
    assert "SPACE_BUNNY_REBIND_SMOKE_OK" not in json.dumps(receipt)

    # The classification repair must not downgrade away the direct evidence:
    # configured pins, job outcome, skipped primary lane and provider policy
    # stay DIRECTLY_VERIFIED and are cited.
    assert (
        receipt["evidence_classification"]["configured_pins_job_outcome_and_provider_policy"]
        == "DIRECTLY_VERIFIED"
    )
    direct = " ".join(receipt["classification_basis"]["directly_verified"])
    assert "112470057434" in direct
    assert "MODEL=opencode-go/space-bunny" in direct
    assert "VARIANT=max" in direct
    assert "skipped" in direct
    assert "provider policy" in direct.lower()
    code_derived = " ".join(receipt["classification_basis"]["code_derived"])
    assert "6024263751" in code_derived
    assert "no independently fetched runtime log" in code_derived


def test_activation_receipt_is_not_a_workstream_state_record() -> None:
    """The receipt must stay shaped as evidence, not as workstream state."""
    receipt = _runtime_activation_receipt()
    assert receipt["record_type"] == "runtime_activation_evidence_receipt"
    # Content markers the state-conformance sweep detects; adding either would
    # masquerade the receipt as a workstream state file.
    assert "objective" not in receipt
    assert "workstream" not in receipt


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
    # Exact runtime identity provenance for the two-profile + alias policy.
    assert set(props["logical_executor_profile"]["enum"]) == {"deepseek", "space-bunny", None}
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
