"""Semantic guards for the current operating policy, never historical PASS."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "foundry"))
import launcher  # noqa: E402
import state  # noqa: E402


def test_config_ci_agents_and_durable_state_agree():
    config = json.loads((ROOT / "opencode.json").read_text())
    models = config["provider"][launcher.CANONICAL_PROVIDER]["models"]
    schema = json.loads((ROOT / ".foundry/WORKSTREAM_STATE.schema.json").read_text())
    # Retired ids (Step 5 Preview, the OpenCode Go DeepSeek id) are absent from opencode.json.
    assert set(models) == {"deepseek-v4.1-flash-free"}
    for model in launcher.ADMITTED_RUNTIME_MODELS:
        short = model.split("/", 1)[1]
        native = models[short]["options"]["reasoningEffort"]
        assert launcher.AUTHORIZED_NATIVE_VARIANT[short] == native
        assert native in state.REASONING_TIERS
        assert native in schema["properties"]["current_reasoning_tier"]["enum"]
        assert [v for v, opts in models[short]["variants"].items() if not opts.get("disabled")] == [
            native
        ]
    assert config["model"] == config["small_model"] == launcher.CANONICAL_MODEL
    workflow = yaml.safe_load((ROOT / ".github/workflows/opencode.yml").read_text())
    step = next(s for s in workflow["jobs"]["opencode"]["steps"] if s.get("name") == "Run opencode")
    assert step["env"]["MODEL"] == config["model"]
    assert (
        step["env"]["VARIANT"]
        == models[config["model"].split("/", 1)[1]]["options"]["reasoningEffort"]
    )
    for path in (ROOT / ".opencode/agents").glob("*.md"):
        front = yaml.safe_load(path.read_text().split("---", 2)[1])
        short = front["model"].split("/", 1)[1]
        assert front["variant"] == models[short]["options"]["reasoningEffort"]


def test_launcher_exposes_exactly_the_one_routed_executor():
    """No retired executor may be reachable through the canonical launcher."""
    assert launcher.EXECUTION_PROFILES == ("deepseek",)
    assert launcher.ACTIVE_EXECUTION_PROFILES == ("deepseek",)
    assert launcher.DEFAULT_EXECUTION_PROFILE == "deepseek"
    # The opencode (Zen) whitelist stays single-id.
    assert launcher.ADMITTED_RUNTIME_MODELS == ("opencode/deepseek-v4.1-flash-free",)
    assert launcher.PROFILE_MODELS == {
        "deepseek": "opencode/deepseek-v4.1-flash-free",
    }
    assert not hasattr(launcher, "ZEN_MODEL"), "retired provider override must stay removed"
    for retired in ("step", "glm", "openai", "other"):
        with pytest.raises(ValueError, match="unknown execution profile"):
            launcher.execution_identity(None, "high", retired)
    with pytest.raises(ValueError, match="retired"):
        launcher.execution_identity("zen", "high")


def test_launcher_native_pair_gap_deferral_is_preserved_and_superseded():
    """The 2026-09-28 deferral stays byte-identical provenance; it is no longer a live block."""
    deferred = json.loads(
        (ROOT / "docs/project_integrity_20260928/OWNERSHIP_DEFERRALS.json").read_text()
    )
    # Historical record, unmodified.
    assert deferred["disposition"] == "FOREIGN_ACTIVE_DO_NOT_EDIT"
    assert "tools/foundry/launcher.py" in deferred["paths"]
    assert deferred["observed_head"] and deferred["exact_next_action"]
    # Supersession record, additive.
    resolution = json.loads(
        (
            ROOT / "docs/project_integrity_20260928/OWNERSHIP_DEFERRALS_RESOLUTION_20260929.json"
        ).read_text()
    )
    assert resolution["resolves"].endswith("OWNERSHIP_DEFERRALS.json")
    assert resolution["historical_record_preserved"] is True
    assert resolution["superseded_disposition"] == "FOREIGN_ACTIVE_DO_NOT_EDIT"
    assert set(resolution["paths_released_for_edit"]) == {
        "tools/foundry/launcher.py",
        "tests/foundry/test_launcher.py",
    }
    assert resolution["superseding_authority"]


def test_documented_native_pairs_match_policy_not_runtime_claims():
    doc = (ROOT / "docs/foundry-execution/EXECUTION_PROVIDER_OVERRIDE.md").read_text()
    pairs = re.findall(r"--execution-profile (deepseek-th|deepseek|step) --effort (\w+)", doc)
    # Only the ACTIVE profile has a documented launch pair; the retired Token Harbor
    # pair must not be documented anymore.
    assert set(pairs) == {("deepseek", "high")}
    assert "--execution-profile deepseek-th" not in doc
    assert "--execution-profile step" not in doc
    for profile, effort in pairs:
        model = launcher.PROFILE_MODELS[profile]
        # The documented --effort is project/authority routing, NOT the native variant.
        assert effort in launcher.ALLOWED_EFFORTS, (profile, effort)
        assert launcher.AUTHORIZED_NATIVE_VARIANT[model.split("/", 1)[1]] == "max"
    # The doc must not present a project effort as if it were a native variant.
    assert "--effort max" not in doc
    for profile, model in launcher.PROFILE_MODELS.items():
        assert model in doc, profile
    # A narrow guard for the actual contradictory positive instructions found in
    # this audit; historical reports and explicit prohibitions remain readable.
    for name in ("README.md", "EXECUTION_PROVIDER_OVERRIDE.md"):
        text = (ROOT / "docs/foundry-execution" / name).read_text()
        assert "Primary long-running worker (HIGH)" not in text
    # The current authority names no models (Owner 2026-10-16); the profile set the
    # launcher enforces lives in machine configuration, checked above.
    authority = (ROOT / "docs/CURRENT_EXECUTION_AUTHORITY.md").read_text()
    assert ".foundry/executor-profiles.json" in authority
    assert "no automatic fallback" in authority


def test_current_executor_authority_is_exactly_one_profile():
    """Always-read policy names no models; Owner gates and routing boundaries stay stated."""
    agents = (ROOT / "AGENTS.md").read_text()
    current = (ROOT / "docs/CURRENT_EXECUTION_AUTHORITY.md").read_text()
    routing = (ROOT / "docs/foundry-execution/ROUTING_AND_EFFORT.md").read_text()
    routing_flat = " ".join(routing.split())
    # Owner 2026-10-16: models are selected manually; the always-read policy files carry
    # no model allowlist, so a stale model list cannot drift from the launcher config.
    for model_id in (
        "opencode-go/deepseek-v4.1-flash",
        "opencode/step-5-preview-free",
        "opencode/deepseek-v4.1-flash-free",
    ):
        assert model_id not in agents
        assert model_id not in current
    assert "The Owner selects the tool and model for each session manually" in agents
    assert "there is no automatic fallback between executors" in agents
    assert "CLAUDE_OPUS_COORDINATOR_AUTHORITY = DELEGATED_BY_OWNER" in agents
    owner_gate_wording = (
        "Production Provider selection and Architecture Freeze remain "
        "separate Owner gates, with the other Owner-only items in "
        "`AGENTS.md` §8."
    )
    assert owner_gate_wording in current
    assert "Coordinator tier's decision authority" in routing_flat
    assert "must not generate a" in routing
    assert "routing/governance issue by themselves" in routing
    index = (ROOT / "docs/foundry-execution/README.md").read_text()
    assert "DeepSeek V4.1 Flash MAX only" in index, "Foundry index omits the current only executor"
    assert "Step retired 2026-10-16" in index, "Foundry index omits the Step retirement"
    assert "SUSPENDED" not in index, "Foundry index still names a suspended profile"


def test_external_content_boundary_survives_policy_edits():
    agents = (ROOT / "AGENTS.md").read_text()
    boundary = agents.split("### External-content boundary", 1)[1].split("## 4.", 1)[0]
    for concept in (
        "DATA/EVIDENCE",
        "not instructions",
        "configured permissions",
        "secrets",
        "Workstream",
    ):
        assert concept in boundary


def test_recovered_donor_receipts_bind_the_actual_transplanted_content():
    receipts = json.loads(
        (ROOT / "docs/project_integrity_20260928/LEGACY_PORT_RECEIPTS.json").read_text()
    )
    checked = list(receipts)
    assert checked, "nothing was checked: receipts is empty"
    for donor in checked:
        assert set(donor["ported_paths"]) == set(donor["source_blobs"])
        for name, expected in donor["source_blobs"].items():
            # Git text content is LF; Windows checkout conversion is not drift.
            actual = (ROOT / name).read_text(encoding="utf-8").encode("utf-8")
            assert hashlib.sha256(actual).hexdigest() == expected, (
                f"{name}: recovered donor content changed; adjudicate and update "
                "the receipt instead of retaining a false exact-port claim"
            )


def test_downstream_git_guidance_defers_to_root_boundaries():
    paths = (
        ".opencode/agents/foundry-implementer.md",
        "docs/foundry-execution/FULL_PROJECT_EXECUTION_AUTHORITY_2026-09-27.md",
    )
    checked = list(paths)
    assert checked, "nothing was checked: paths is empty"
    for name in checked:
        text = (ROOT / name).read_text()
        assert "`AGENTS.md` sections 10-11" in text
        assert "no additional rebase, history-rewrite, destructive branch/worktree deletion" in text
        for obsolete in (
            "create/remove worktrees",
            "merge/rebase/cherry-pick",
            "- delete proven-superseded",
        ):
            assert obsolete not in text
