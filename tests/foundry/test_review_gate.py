"""Wrong-reason / regression controls for the cross-executor review gate.

Policy: MATERIAL implementation workstreams cannot claim PR_READY/COMPLETE
without a fresh-context READ-ONLY Space Bunny PASS on the exact validated
implementation SHA and TREE. DeepSeek review, self-review, unauthorized runtime
ids, missing/blocked/unknown/partial/fail/stale review, and any later material
delta all fail closed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from foundry import executor_profiles as executor_mod  # noqa: E402
from foundry import review_evidence as evidence_mod  # noqa: E402
from foundry import review_gate as review_mod  # noqa: E402
from foundry import state as state_mod  # noqa: E402

TRUSTED_REPO = "moeendres-png/commander-playtest-lab"


class _StaticVerifier:
    """Test double for the independently injected review-evidence verifier."""

    def __init__(self, status: str = evidence_mod.SATISFIED) -> None:
        self.status = status
        self.calls = 0

    def __call__(self, record: dict) -> evidence_mod.ReviewEvidenceResult:
        self.calls += 1
        return evidence_mod.ReviewEvidenceResult(self.status, (f"static:{self.status}",))


class _EmptyTransport:
    """All lookups 404: proves the default verifier cannot be bypassed."""

    def request(self, method: str, url: str, headers: dict, timeout: float) -> tuple[int, bytes]:
        return 404, b'{"message":"Not Found"}'


def _satisfied() -> _StaticVerifier:
    return _StaticVerifier()


BUNNY = "opencode-go/space-bunny"
BUNNY_LEGACY = "opencode-go/space-bunny-free"
DEEPSEEK = "opencode-go/deepseek-v4.1-flash"


def _git(args: list[str], cwd: Path) -> str:
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "T",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "T",
            "GIT_COMMITTER_EMAIL": "t@example.com",
            "GIT_CONFIG_NOSYSTEM": "1",
        }
    )
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


@pytest.fixture()
def repo(tmp_path: Path) -> dict:
    root = tmp_path / "repo"
    root.mkdir()
    _git(["init", "-b", "main"], root)
    (root / "README.md").write_text("base\n", encoding="utf-8")
    _git(["add", "."], root)
    _git(["commit", "-m", "base"], root)
    base = _git(["rev-parse", "HEAD"], root)
    (root / "docs").mkdir()
    (root / "docs" / "note.md").write_text("note\n", encoding="utf-8")
    _git(["add", "."], root)
    _git(["commit", "-m", "docs"], root)
    docs = _git(["rev-parse", "HEAD"], root)
    (root / "tools").mkdir()
    (root / "tools" / "impl.py").write_text("x = 1\n", encoding="utf-8")
    _git(["add", "."], root)
    _git(["commit", "-m", "implementation"], root)
    impl = _git(["rev-parse", "HEAD"], root)
    (root / ".foundry").mkdir()
    state_path = root / ".foundry" / "WORKSTREAM_STATE.yaml"
    state_path.write_text(
        yaml.safe_dump(_state_doc(base, impl, root, state_path)), encoding="utf-8"
    )
    _git(["add", "."], root)
    _git(["commit", "-m", "state"], root)
    checkpoint = _git(["rev-parse", "HEAD"], root)
    return {
        "root": root,
        "base": base,
        "impl": impl,
        "docs": docs,
        "checkpoint": checkpoint,
        "state": state_path,
    }


def _tree(root: Path, commit: str) -> str:
    return _git(["rev-parse", f"{commit}^{{tree}}"], root)


def _state_doc(base: str, impl: str, root: Path, state_path: Path, **over) -> dict:
    doc = {
        "schema_version": "2.0",
        "repository": "moeendres-png/commander-playtest-lab",
        "worktree": str(root),
        "branch": "project/test",
        "audit_base_sha": base,
        "audit_base_tree": _tree(root, base),
        "state_written_against_head": impl,
        "validated_head": impl,
        "validated_tree": _tree(root, impl),
        "objective": "review gate fixture",
        "in_scope": [],
        "out_of_scope": [],
        "ownership": "TEST-WS",
        "status": "ACTIVE",
        "materiality": "MATERIAL",
        "cross_executor_review": {
            "required": True,
            "logical_profile": "space-bunny",
            "implementation_executor": "deepseek",
            "review_executor": "space-bunny",
            "resolved_model_id": BUNNY,
            "model_alias_class": "CANONICAL",
            "reviewed_sha": None,
            "reviewed_tree": None,
            "verdict": "UNKNOWN",
            "review_record_path": None,
        },
        "exact_next_action": "dispatch review",
    }
    doc.update(over)
    return doc


def _record(repo: dict, *, reviewed_sha: str | None = None, verdict: str = "PASS", **over) -> dict:
    impl = reviewed_sha or repo["impl"]
    record = {
        "schema_version": "1.0",
        "record_type": "cross_executor_review",
        "required": True,
        "materiality": "MATERIAL",
        "logical_profile": "space-bunny",
        "resolved_provider": "opencode-go",
        "resolved_model_id": BUNNY,
        "model_alias_class": "CANONICAL",
        "native_variant": "max",
        "review_mode": "READ_ONLY_FRESH_CONTEXT",
        "review_agent": "foundry-reviewer",
        "reviewed_sha": impl,
        "reviewed_tree": _tree(repo["root"], impl),
        "verdict": verdict,
        "findings": {"P1": [], "P2": [], "P3": []},
        "implementation_executor": "deepseek",
        "review_executor": "space-bunny",
        "review_evidence": {
            "schema_version": "1.0",
            "carrier": evidence_mod.CARRIER_DIRECT,
            "repository": TRUSTED_REPO,
            "trigger_issue_number": 578,
            "trigger_comment_id": 1,
            "result_comment_id": 2,
            "workflow_run_id": 3,
            "workflow_job_id": 4,
            "workflow_job_name": "opencode-bunny-review",
            "workflow_head_sha": "a" * 40,
            "workflow_path": ".github/workflows/opencode.yml",
            "marker": evidence_mod.MARKER_DIRECT,
        },
    }
    record.update(over)
    return record


def _write_record(repo: dict, record: dict, name: str = "review.json") -> Path:
    path = repo["root"] / ".foundry" / "reviews" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


def _mirror_passed(repo: dict, record: dict, record_path: Path) -> dict:
    return {
        "required": True,
        "logical_profile": "space-bunny",
        "implementation_executor": record["implementation_executor"],
        "review_executor": record["review_executor"],
        "resolved_model_id": record["resolved_model_id"],
        "model_alias_class": record["model_alias_class"],
        "reviewed_sha": record["reviewed_sha"],
        "reviewed_tree": record["reviewed_tree"],
        "verdict": record["verdict"],
        "review_record_path": str(record_path.relative_to(repo["root"])),
    }


# --- record structure -------------------------------------------------------


def test_well_formed_bunny_pass_record_validates(repo: dict) -> None:
    record = _record(repo)
    assert review_mod.validate_review_record(record) == []


def test_deepseek_review_or_self_review_is_never_admitted(repo: dict) -> None:
    record = _record(repo)
    record["resolved_model_id"] = DEEPSEEK
    record["model_alias_class"] = "CANONICAL"
    errors = review_mod.validate_review_record(record)
    assert any("not an admitted space-bunny runtime id" in error for error in errors)

    record = _record(repo)
    record["review_executor"] = "deepseek"
    errors = review_mod.validate_review_record(record)
    assert any("review_executor must be the logical space-bunny" in error for error in errors)

    record = _record(repo)
    record["implementation_executor"] = "space-bunny"
    errors = review_mod.validate_review_record(record)
    assert any("self-review" in error for error in errors)


def test_writable_or_unknown_review_agents_are_rejected(repo: dict) -> None:
    for agent in ("bunny-verifier", "foundry-implementer", "", "bunny-auditor "):
        record = _record(repo)
        record["review_agent"] = agent
        errors = review_mod.validate_review_record(record)
        assert any("structurally read-only reviewer" in error for error in errors), agent


def test_pass_verdict_cannot_carry_blocking_findings(repo: dict) -> None:
    for key in ("P1", "P2"):
        record = _record(repo)
        record["findings"][key] = ["fabricated legal options at engine.py:10"]
        errors = review_mod.validate_review_record(record)
        assert any("blocking findings" in error for error in errors), key


def test_alias_class_must_match_admitted_mapping(repo: dict) -> None:
    record = _record(repo)
    record["resolved_model_id"] = BUNNY_LEGACY
    assert any("model_alias_class" in error for error in review_mod.validate_review_record(record))
    record["model_alias_class"] = "LEGACY_ALIAS"
    assert review_mod.validate_review_record(record) == []


def test_unknown_record_fields_fail_closed(repo: dict) -> None:
    record = _record(repo)
    record["sneaky_override"] = True
    errors = review_mod.validate_review_record(record)
    assert any("unknown fields" in error for error in errors)


# --- gate evaluation --------------------------------------------------------


def test_material_without_review_record_is_unsatisfied(repo: dict) -> None:
    doc = _state_doc(repo["base"], repo["impl"], repo["root"], repo["state"])
    result = review_mod.evaluate_review_gate(doc, workdir=str(repo["root"]))
    assert result.status == "UNSATISFIED"
    assert any("REVIEW_RECORD_MISSING" in reason for reason in result.reasons)


def test_deepseek_implementation_plus_deepseek_review_stays_unsatisfied(repo: dict) -> None:
    record = _record(repo)
    record["resolved_model_id"] = DEEPSEEK
    path = _write_record(repo, record)
    doc = _state_doc(
        repo["base"],
        repo["impl"],
        repo["root"],
        repo["state"],
        cross_executor_review=_mirror_passed(repo, record, path),
        validated_tree=_tree(repo["root"], repo["impl"]),
    )
    result = review_mod.evaluate_review_gate(
        doc, workdir=str(repo["root"]), review_record_path=str(path)
    )
    assert result.status == "UNSATISFIED"
    assert any("REVIEW_RECORD_INVALID" in reason for reason in result.reasons)


def test_deepseek_implementation_plus_bunny_exact_sha_tree_pass_is_satisfied(repo: dict) -> None:
    record = _record(repo)
    path = _write_record(repo, record)
    doc = _state_doc(
        repo["base"],
        repo["impl"],
        repo["root"],
        repo["state"],
        cross_executor_review=_mirror_passed(repo, record, path),
        validated_tree=_tree(repo["root"], repo["impl"]),
    )
    verifier = _satisfied()
    result = review_mod.evaluate_review_gate(
        doc,
        workdir=str(repo["root"]),
        review_record_path=str(path),
        state_path=str(repo["state"].relative_to(repo["root"])),
        evidence_verifier=verifier,
    )
    assert result.status == "SATISFIED", result.reasons
    # The gate only reaches SATISFIED through the independent verifier: a
    # self-asserted PASS record can never skip external evidence.
    assert verifier.calls == 1


def test_self_asserted_pass_without_verifiable_evidence_is_not_satisfied(repo: dict) -> None:
    """A fabricated record with plausible Bunny fields still fails closed."""
    import json as _json

    record = _record(repo)
    record["review_evidence"] = {
        "schema_version": "1.0",
        "carrier": evidence_mod.CARRIER_DIRECT,
        "repository": TRUSTED_REPO,
        "trigger_issue_number": 578,
        "trigger_comment_id": 111,
        "result_comment_id": 222,
        "workflow_run_id": 333,
        "workflow_job_id": 444,
        "workflow_job_name": "opencode-bunny-review",
        "workflow_head_sha": "b" * 40,
        "workflow_path": ".github/workflows/opencode.yml",
        "marker": evidence_mod.MARKER_DIRECT,
    }
    path = repo["root"] / ".foundry" / "reviews" / "fabricated.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json.dumps(record), encoding="utf-8")
    doc = _state_doc(
        repo["base"],
        repo["impl"],
        repo["root"],
        repo["state"],
        cross_executor_review=_mirror_passed(repo, record, path),
        validated_tree=_tree(repo["root"], repo["impl"]),
    )
    result = review_mod.evaluate_review_gate(
        doc,
        workdir=str(repo["root"]),
        review_record_path=str(path),
        state_path=str(repo["state"].relative_to(repo["root"])),
        evidence_transport=_EmptyTransport(),
    )
    assert result.status != "SATISFIED"
    assert any("REVIEW_EVIDENCE" in reason for reason in result.reasons)


def test_reviewed_old_sha_after_material_change_is_stale(repo: dict) -> None:
    record = _record(repo, reviewed_sha=repo["base"])
    path = _write_record(repo, record)
    doc = _state_doc(
        repo["base"],
        repo["impl"],
        repo["root"],
        repo["state"],
        cross_executor_review=_mirror_passed(repo, record, path),
        validated_tree=_tree(repo["root"], repo["impl"]),
    )
    result = review_mod.evaluate_review_gate(
        doc, workdir=str(repo["root"]), review_record_path=str(path)
    )
    assert result.status == "STALE"
    assert any("REVIEW_IDENTITY_MISMATCH" in reason for reason in result.reasons)


def test_p1_repair_after_review_requires_re_review(repo: dict) -> None:
    """A repaired material change after the reviewed identity stales the PASS."""
    record = _record(repo, reviewed_sha=repo["impl"])
    path = _write_record(repo, record)
    (repo["root"] / "tools" / "impl.py").write_text("x = 2\n", encoding="utf-8")
    _git(["add", "."], repo["root"])
    _git(["commit", "-m", "P1 repair"], repo["root"])
    repaired = _git(["rev-parse", "HEAD"], repo["root"])
    doc = _state_doc(
        repo["base"],
        repaired,
        repo["root"],
        repo["state"],
        cross_executor_review=_mirror_passed(repo, record, path),
        validated_tree=_tree(repo["root"], repaired),
    )
    result = review_mod.evaluate_review_gate(
        doc, workdir=str(repo["root"]), review_record_path=str(path)
    )
    assert result.status == "STALE"
    assert any("REVIEW_IDENTITY_MISMATCH" in reason for reason in result.reasons)


def test_generated_state_only_closeout_preserves_review(repo: dict) -> None:
    """A later state-only checkpoint keeps the reviewed implementation identity."""
    record = _record(repo)
    path = _write_record(repo, record)
    doc = _state_doc(
        repo["base"],
        repo["impl"],
        repo["root"],
        repo["state"],
        cross_executor_review=_mirror_passed(repo, record, path),
        validated_tree=_tree(repo["root"], repo["impl"]),
    )
    # Live HEAD is the state checkpoint (and later commits may also be state-only).
    result = review_mod.evaluate_review_gate(
        doc,
        workdir=str(repo["root"]),
        review_record_path=str(path),
        state_path=str(repo["state"].relative_to(repo["root"])),
        evidence_verifier=_satisfied(),
    )
    assert result.status == "SATISFIED", result.reasons


def test_material_delta_after_validated_sha_is_stale(repo: dict) -> None:
    record = _record(repo)
    path = _write_record(repo, record)
    (repo["root"] / "tools" / "impl.py").write_text("x = 3\n", encoding="utf-8")
    _git(["add", "."], repo["root"])
    _git(["commit", "-m", "late material change"], repo["root"])
    doc = _state_doc(
        repo["base"],
        repo["impl"],
        repo["root"],
        repo["state"],
        cross_executor_review=_mirror_passed(repo, record, path),
        validated_tree=_tree(repo["root"], repo["impl"]),
    )
    result = review_mod.evaluate_review_gate(
        doc, workdir=str(repo["root"]), review_record_path=str(path)
    )
    assert result.status == "STALE"
    assert any("REVIEW_STALE_MATERIAL_DELTA" in reason for reason in result.reasons)


def test_mirror_mismatch_is_unsatisfied(repo: dict) -> None:
    record = _record(repo)
    path = _write_record(repo, record)
    mirror = _mirror_passed(repo, record, path)
    mirror["resolved_model_id"] = BUNNY_LEGACY
    doc = _state_doc(
        repo["base"],
        repo["impl"],
        repo["root"],
        repo["state"],
        cross_executor_review=mirror,
        validated_tree=_tree(repo["root"], repo["impl"]),
    )
    result = review_mod.evaluate_review_gate(
        doc, workdir=str(repo["root"]), review_record_path=str(path)
    )
    assert result.status == "UNSATISFIED"
    assert any("REVIEW_MIRROR_MISMATCH" in reason for reason in result.reasons)


def test_material_state_cannot_self_exempt_via_mirror_required_false(repo: dict) -> None:
    record = _record(repo)
    path = _write_record(repo, record)
    mirror = _mirror_passed(repo, record, path)
    mirror["required"] = False
    doc = _state_doc(
        repo["base"],
        repo["impl"],
        repo["root"],
        repo["state"],
        cross_executor_review=mirror,
        validated_tree=_tree(repo["root"], repo["impl"]),
    )
    result = review_mod.evaluate_review_gate(
        doc, workdir=str(repo["root"]), review_record_path=str(path)
    )
    assert result.status == "UNSATISFIED"
    assert any("REVIEW_REQUIREMENT_MISMATCH" in reason for reason in result.reasons)


def test_non_material_underclaim_fails_closed(repo: dict) -> None:
    doc = _state_doc(
        repo["base"],
        repo["impl"],
        repo["root"],
        repo["state"],
        materiality="NON_MATERIAL",
    )
    result = review_mod.evaluate_review_gate(doc, workdir=str(repo["root"]))
    assert result.status == "UNSATISFIED"
    assert any("MATERIALITY_UNDERCLAIM" in reason for reason in result.reasons)


def test_non_material_cannot_self_exempt_by_rebinding_audit_base(repo: dict) -> None:
    """Rebinding audit_base_sha onto validated_head must not hide material work."""
    doc = _state_doc(
        repo["base"],
        repo["base"],
        repo["root"],
        repo["state"],
        materiality="NON_MATERIAL",
        validated_tree=_tree(repo["root"], repo["base"]),
    )
    result = review_mod.evaluate_review_gate(doc, workdir=str(repo["root"]))
    assert result.status == "UNSATISFIED"
    assert any("MATERIALITY_SELF_EXEMPT" in reason for reason in result.reasons)

    # The same bypass without a workdir (offline state validation) is refused.
    result = review_mod.evaluate_review_gate(doc)
    assert result.status == "UNSATISFIED"
    assert any("MATERIALITY_SELF_EXEMPT" in reason for reason in result.reasons)


def test_policy_less_complete_claim_is_not_certifiable(repo: dict) -> None:
    """A fresh policy-less state cannot claim COMPLETE via EXEMPT_HISTORICAL."""
    doc = _state_doc(repo["base"], repo["impl"], repo["root"], repo["state"])
    doc.pop("materiality")
    doc.pop("cross_executor_review")
    assert review_mod.evaluate_review_gate(doc, workdir=str(repo["root"])).ok
    result = review_mod.evaluate_completion_claim(
        doc,
        claim="COMPLETE",
        workdir=str(repo["root"]),
        state_path=str(repo["state"]),
        remote_verdict="SATISFIED",
    )
    assert not result.ok
    assert any("COMPLETION_POLICY_FIELDS_MISSING" in reason for reason in result.reasons)


def test_historical_state_without_policy_fields_is_exempt(repo: dict) -> None:
    doc = _state_doc(repo["base"], repo["impl"], repo["root"], repo["state"])
    doc.pop("materiality")
    doc.pop("cross_executor_review")
    result = review_mod.evaluate_review_gate(doc, workdir=str(repo["root"]))
    assert result.status == "EXEMPT_HISTORICAL"
    assert result.ok


def test_bunny_unavailable_and_no_review_blocks_completion_claim(repo: dict) -> None:
    doc = _state_doc(repo["base"], repo["impl"], repo["root"], repo["state"])
    result = review_mod.evaluate_completion_claim(
        doc,
        claim="COMPLETE",
        workdir=str(repo["root"]),
        remote_verdict="MISSING",
        state_path=str(repo["state"]),
    )
    assert not result.ok
    assert any("REVIEW_RECORD_MISSING" in reason for reason in result.reasons)


def test_completion_claim_without_remote_verdict_fails_closed(repo: dict) -> None:
    record = _record(repo)
    path = _write_record(repo, record)
    doc = _state_doc(
        repo["base"],
        repo["impl"],
        repo["root"],
        repo["state"],
        cross_executor_review=_mirror_passed(repo, record, path),
        validated_tree=_tree(repo["root"], repo["impl"]),
    )
    result = review_mod.evaluate_completion_claim(
        doc,
        claim="PR_READY",
        workdir=str(repo["root"]),
        review_record_path=str(path),
        remote_verdict=None,
        state_path=str(repo["state"]),
        evidence_verifier=_satisfied(),
    )
    assert not result.ok
    assert any("REMOTE_CHECKPOINT_UNVERIFIED" in reason for reason in result.reasons)


def test_completion_claim_requires_satisfied_remote_checkpoint(repo: dict) -> None:
    record = _record(repo)
    path = _write_record(repo, record)
    doc = _state_doc(
        repo["base"],
        repo["impl"],
        repo["root"],
        repo["state"],
        cross_executor_review=_mirror_passed(repo, record, path),
        validated_tree=_tree(repo["root"], repo["impl"]),
    )
    result = review_mod.evaluate_completion_claim(
        doc,
        claim="PR_READY",
        workdir=str(repo["root"]),
        review_record_path=str(path),
        remote_verdict="MISMATCH",
        state_path=str(repo["state"]),
        evidence_verifier=_satisfied(),
    )
    assert not result.ok
    assert any("REMOTE_CHECKPOINT_MISMATCH" in reason for reason in result.reasons)


# --- structurally read-only reviewer agents ---------------------------------


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    return yaml.safe_load(text.split("---", 2)[1])


def test_bunny_reviewer_agents_are_structurally_mutation_denied() -> None:
    reviewer = _frontmatter(REPO_ROOT / ".opencode" / "agents" / "foundry-reviewer.md")
    assert reviewer["model"] == BUNNY
    assert reviewer["variant"] == "max"
    assert reviewer["mode"] == "all"
    assert reviewer["permission"]["edit"] == "deny"
    assert reviewer["permission"]["bash"]["*"] == "deny"
    assert reviewer["permission"]["task"] == "deny"

    auditor = _frontmatter(REPO_ROOT / ".opencode" / "agents" / "bunny-auditor.md")
    assert auditor["model"] == BUNNY
    assert auditor["permission"]["edit"] == "deny"
    assert auditor["permission"]["bash"]["*"] == "deny"
    assert auditor["permission"]["task"] == "deny"

    # The bash allowlist must stay read-only Git inspection: no write, push,
    # edit, package-management or arbitrary-exec prefix may appear.
    read_only_prefixes = (
        "git status*",
        "git diff*",
        "git log*",
        "git show*",
        "git rev-parse*",
        "git ls-files*",
        "git ls-tree*",
        "python3 .claude/skills/lab-ops/scripts/gh_ops.py*",
    )
    for agent in (reviewer, auditor):
        for rule, action in agent["permission"]["bash"].items():
            if rule == "*":
                continue
            assert action == "allow", (agent, rule)
            assert rule in read_only_prefixes, (agent, rule)

    registry = executor_mod.load_registry()
    assert set(registry.review_policy["review_agents"]) == {
        "bunny-auditor",
        "foundry-reviewer",
    }
    assert "bunny-verifier" not in registry.review_policy["review_agents"]


# --- state CLI wiring -------------------------------------------------------


def test_state_cli_review_gate_fails_closed_then_passes(
    repo: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib

    # state.py imports the tool modules by their flat names; inject the test
    # double into the exact module object the CLI review gate resolves.
    top_evidence = importlib.import_module("review_evidence")
    calls: list[str] = []

    def _verifier(record, *, expected_repository=None, transport=None):
        calls.append(str(record.get("reviewed_sha")))
        return evidence_mod.ReviewEvidenceResult(evidence_mod.SATISFIED, ("injected",))

    monkeypatch.setattr(top_evidence, "verify_review_evidence", _verifier)
    doc = _state_doc(repo["base"], repo["impl"], repo["root"], repo["state"])
    repo["state"].write_text(yaml.safe_dump(doc), encoding="utf-8")
    rc = state_mod.main(
        [
            "--state",
            str(repo["state"]),
            "--workdir",
            str(repo["root"]),
            "--check-review-gate",
            "--fail-on-review-gate",
        ]
    )
    assert rc == 1

    record = _record(repo)
    path = _write_record(repo, record)
    doc["cross_executor_review"] = _mirror_passed(repo, record, path)
    repo["state"].write_text(yaml.safe_dump(doc), encoding="utf-8")
    rc = state_mod.main(
        [
            "--state",
            str(repo["state"]),
            "--workdir",
            str(repo["root"]),
            "--check-review-gate",
            "--fail-on-review-gate",
        ]
    )
    assert rc == 0
    assert calls == [repo["impl"]]


def test_material_checkpoint_persists_sha_tree_evidence_next_action(repo: dict) -> None:
    """A material milestone state keeps the exact identities it claims."""
    doc = _state_doc(repo["base"], repo["impl"], repo["root"], repo["state"])
    doc["evidence"] = ["REVIEW_GATE_SATISFIED: pending canonical bunny record"]
    doc["remote_checkpoint"] = {
        "remote": "origin",
        "branch": "project/test",
        "sha": repo["checkpoint"],
        "tree": _tree(repo["root"], repo["checkpoint"]),
    }
    doc["exact_next_action"] = "dispatch independent Space Bunny exact-SHA/TREE review"
    path = repo["root"] / ".foundry" / "POLICY_STATE.yaml"
    state_mod.write_state(str(path), doc, workdir=str(repo["root"]))
    reloaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert state_mod.validate(reloaded) == []
    assert reloaded["validated_head"] == repo["impl"]
    assert reloaded["validated_tree"] == _tree(repo["root"], repo["impl"])
    assert reloaded["remote_checkpoint"]["sha"] == repo["checkpoint"]
    assert reloaded["remote_checkpoint"]["tree"] == _tree(repo["root"], repo["checkpoint"])
    assert reloaded["evidence"]
    assert reloaded["exact_next_action"] == (
        "dispatch independent Space Bunny exact-SHA/TREE review"
    )


def test_historical_state_without_policy_fields_stays_valid(repo: dict) -> None:
    doc = _state_doc(repo["base"], repo["impl"], repo["root"], repo["state"])
    doc.pop("materiality")
    doc.pop("cross_executor_review")
    doc.pop("validated_tree")
    assert state_mod.validate(doc) == []
    result = review_mod.evaluate_review_gate(doc, workdir=str(repo["root"]))
    assert result.status == "EXEMPT_HISTORICAL"


def test_bunny_review_workflow_pins_the_read_only_lane() -> None:
    """The direct carrier must pin Space Bunny MAX + the read-only agent."""
    workflow = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "opencode.yml").read_text(encoding="utf-8")
    )
    job = workflow["jobs"]["opencode-bunny-review"]
    env_steps = [
        step
        for step in job["steps"]
        if isinstance(step.get("env"), dict) and "MODEL" in step["env"]
    ]
    assert len(env_steps) == 1
    env = env_steps[0]["env"]
    assert env["MODEL"] == BUNNY
    assert env["VARIANT"] == "max"
    assert env["AGENT"] == "foundry-reviewer"
    assert job["steps"][0]["name"] == "Refuse fork pull requests as agent targets"
    assert "--jq '.head.repo.full_name'" in job["steps"][0]["run"]
    assert job["permissions"] == {
        "id-token": "write",
        "contents": "read",
        "pull-requests": "read",
        "issues": "read",
    }
