"""Semantic guards for the current operating policy, never historical PASS."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "foundry"))
import launcher  # noqa: E402
import state  # noqa: E402


def test_config_ci_agents_and_durable_state_agree():
    config = json.loads((ROOT / "opencode.json").read_text())
    models = config["provider"][launcher.CANONICAL_PROVIDER]["models"]
    schema = json.loads((ROOT / ".foundry/WORKSTREAM_STATE.schema.json").read_text())
    for profile in launcher.EXECUTION_PROFILES:
        model = launcher.SPACE_BUNNY_MODEL if profile == "space-bunny" else launcher.ALTERNATE_MODEL
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
    step = next(
        s for s in workflow["jobs"]["opencode"]["steps"] if s.get("run") == "opencode github run"
    )
    assert step["env"]["MODEL"] == config["model"]
    assert (
        step["env"]["VARIANT"]
        == models[config["model"].split("/", 1)[1]]["options"]["reasoningEffort"]
    )
    for path in (ROOT / ".opencode/agents").glob("*.md"):
        front = yaml.safe_load(path.read_text().split("---", 2)[1])
        short = front["model"].split("/", 1)[1]
        assert front["variant"] == models[short]["options"]["reasoningEffort"]


def test_launcher_native_pair_gap_has_an_explicit_foreign_owner():
    deferred = json.loads(
        (ROOT / "docs/project_integrity_20260928/OWNERSHIP_DEFERRALS.json").read_text()
    )
    assert deferred["disposition"] == "FOREIGN_ACTIVE_DO_NOT_EDIT"
    assert "tools/foundry/launcher.py" in deferred["paths"]
    assert deferred["observed_head"] and deferred["exact_next_action"]


def test_documented_native_pairs_match_policy_not_runtime_claims():
    doc = (ROOT / "docs/foundry-execution/EXECUTION_PROVIDER_OVERRIDE.md").read_text()
    pairs = re.findall(r"--execution-profile (space-bunny|muse) --effort (\w+)", doc)
    assert set(pairs) == {("space-bunny", "max"), ("muse", "xhigh")}
    for profile, effort in pairs:
        model = launcher.SPACE_BUNNY_MODEL if profile == "space-bunny" else launcher.ALTERNATE_MODEL
        assert launcher.AUTHORIZED_NATIVE_VARIANT[model.split("/", 1)[1]] == effort
    # A narrow guard for the actual contradictory positive instructions found in
    # this audit; historical reports and explicit prohibitions remain readable.
    for name in ("README.md", "EXECUTION_PROVIDER_OVERRIDE.md"):
        text = (ROOT / "docs/foundry-execution" / name).read_text()
        assert "Muse-only by default" not in text
        assert "Primary long-running worker (HIGH)" not in text
    authority = (ROOT / "docs/COORDINATOR_EXECUTION_AUTHORITY_2026-09-27.md").read_text()
    assert "- HIGH for ordinary bounded engineering" not in authority


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
    for donor in receipts:
        assert set(donor["ported_paths"]) == set(donor["source_blobs"])
        for name, expected in donor["source_blobs"].items():
            # Git text content is LF; Windows checkout conversion is not drift.
            actual = (ROOT / name).read_text(encoding="utf-8").encode("utf-8")
            assert hashlib.sha256(actual).hexdigest() == expected, (
                f"{name}: recovered donor content changed; adjudicate and update "
                "the receipt instead of retaining a false exact-port claim"
            )
