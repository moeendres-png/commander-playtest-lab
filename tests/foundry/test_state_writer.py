"""Tests for the canonical Foundry state-write path (WS58).

End-to-end CLI/API coverage: the writer must make malformed YAML structurally
impossible through its normal API, refuse schema-invalid state before
replacing the on-disk file, preserve prior bytes on every failure, protect
source-lock identity, never fabricate validation credit, and persist
atomically. Every negative asserts the prior file is byte-identical.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO_ROOT / "tools"))

from foundry import state as state_mod  # noqa: E402


def _git(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


@pytest.fixture()
def history(tmp_path: Path) -> Path:
    """Three-commit linear history: base -> validated -> checkpoint."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-b", "main"], repo)
    _git(["config", "user.email", "test@example.com"], repo)
    _git(["config", "user.name", "Test"], repo)
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    _git(["add", "."], repo)
    _git(["commit", "-m", "base"], repo)
    (repo / "b.txt").write_text("b\n", encoding="utf-8")
    _git(["add", "."], repo)
    _git(["commit", "-m", "validated"], repo)
    (repo / "c.txt").write_text("c\n", encoding="utf-8")
    _git(["add", "."], repo)
    _git(["commit", "-m", "checkpoint"], repo)
    return repo


def _shas(repo: Path) -> tuple[str, str, str]:
    return (
        _git(["rev-parse", "HEAD~2"], repo),
        _git(["rev-parse", "HEAD~1"], repo),
        _git(["rev-parse", "HEAD"], repo),
    )


def _doc(base: str, live: str, validated: str | None) -> dict:
    return {
        "schema_version": "2.0",
        "repository": "moeendres-png/commander-playtest-lab",
        "worktree": "/tmp/wt",
        "branch": "project/x",
        "audit_base_sha": base,
        "audit_base_tree": "0" * 40,
        "state_written_against_head": live,
        "validated_head": validated,
        "objective": "x",
        "in_scope": [],
        "out_of_scope": [],
        "ownership": "tester",
        "status": "ACTIVE",
        "exact_next_action": "next",
    }


def _seed(path: Path, doc: dict) -> bytes:
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")
    return path.read_bytes()


# --- Reproduction A: colon scalar -------------------------------------------
# WS54 shape: hand-concatenated `key: free text: with colon` is unloadable.


def test_hand_concatenated_colon_scalar_is_unloadable() -> None:
    bad = "schema_version: '2.0'\nexact_next_action: Coordinator decision: authorize push\n"
    with pytest.raises(yaml.YAMLError, match="mapping values are not allowed"):
        yaml.safe_load(bad)


def test_writer_round_trips_colon_scalar(tmp_path: Path) -> None:
    path = tmp_path / "S.yaml"
    tricky = "Coordinator decision: authorize push: step 2: verify"
    state_mod.write_state(str(path), _doc("a" * 40, "b" * 40, None) | {"exact_next_action": tricky})
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["exact_next_action"] == tricky


# --- Positive tests ----------------------------------------------------------


def test_positive_multiple_colons_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "S.yaml"
    value = 'a: b: c: d # not a comment "quoted" [brackets] {braces}'
    state_mod.write_state(str(path), _doc("a" * 40, "b" * 40, None) | {"exact_next_action": value})
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["exact_next_action"] == value


def test_positive_multiline_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "S.yaml"
    value = "line one: with colon\nline two # hash\n  indented 'quotes'\n\ntrailing\n"
    state_mod.write_state(str(path), _doc("a" * 40, "b" * 40, None) | {"exact_next_action": value})
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["exact_next_action"] == value


def test_positive_unicode_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "S.yaml"
    value = "café ☃ naïve — em dash: colon ✓"
    state_mod.write_state(str(path), _doc("a" * 40, "b" * 40, None) | {"exact_next_action": value})
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["exact_next_action"] == value


def test_positive_valid_engine_defect_persists(tmp_path: Path) -> None:
    path = tmp_path / "S.yaml"
    state_mod.write_state(
        str(path), _doc("a" * 40, "b" * 40, None) | {"failure_class": "ENGINE_DEFECT"}
    )
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["failure_class"] == "ENGINE_DEFECT"


def test_positive_validated_head_null_persists(tmp_path: Path) -> None:
    path = tmp_path / "S.yaml"
    state_mod.write_state(str(path), _doc("a" * 40, "b" * 40, None))
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["validated_head"] is None


def test_positive_explicit_valid_validated_head_persists(history: Path, tmp_path: Path) -> None:
    base, validated, live = _shas(history)
    path = tmp_path / "S.yaml"
    _seed(path, _doc(base, live, None))
    state_mod.update_state(
        str(path), {"status": "WAITING"}, workdir=str(history), validated_head=validated
    )
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["validated_head"] == validated


def test_positive_required_fields_survive_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "S.yaml"
    original = _doc("a" * 40, "b" * 40, None)
    _seed(path, original)
    state_mod.update_state(str(path), {"status": "WAITING"})
    reread = yaml.safe_load(path.read_text(encoding="utf-8"))
    for field in (
        "schema_version",
        "repository",
        "worktree",
        "branch",
        "audit_base_sha",
        "audit_base_tree",
        "state_written_against_head",
        "objective",
        "in_scope",
        "out_of_scope",
        "ownership",
        "exact_next_action",
    ):
        assert reread[field] == original[field], field


def test_positive_identity_fields_survive_checkpoint(tmp_path: Path) -> None:
    path = tmp_path / "S.yaml"
    original = _doc("a" * 40, "b" * 40, None)
    _seed(path, original)
    state_mod.update_state(str(path), {"status": "BLOCKED", "current_failure": "x"})
    reread = yaml.safe_load(path.read_text(encoding="utf-8"))
    for field in state_mod.IMMUTABLE_IDENTITY_FIELDS:
        assert reread[field] == original[field], field


def test_positive_output_reparses_and_validates(tmp_path: Path) -> None:
    path = tmp_path / "S.yaml"
    state_mod.write_state(str(path), _doc("a" * 40, "b" * 40, None))
    assert state_mod.validate(yaml.safe_load(path.read_text(encoding="utf-8"))) == []


def test_positive_atomic_replace_leaves_no_partial(tmp_path: Path) -> None:
    path = tmp_path / "S.yaml"
    _seed(path, _doc("a" * 40, "b" * 40, None))
    state_mod.update_state(str(path), {"status": "WAITING"})
    leftovers = [p for p in tmp_path.iterdir() if p.name != "S.yaml"]
    assert leftovers == []
    reread = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert reread["status"] == "WAITING"
    assert state_mod.validate(reread) == []


def test_positive_no_auto_promote_validated_head(tmp_path: Path) -> None:
    path = tmp_path / "S.yaml"
    _seed(path, _doc("a" * 40, "b" * 40, None))
    state_mod.update_state(str(path), {"status": "WAITING"})
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["validated_head"] is None


# --- Negative tests (every one proves byte-identical preservation) -----------


def test_negative_invalid_failure_class_rejected(tmp_path: Path) -> None:
    path = tmp_path / "S.yaml"
    before = _seed(path, _doc("a" * 40, "b" * 40, None))
    with pytest.raises(state_mod.StateWriteError, match="failure_class"):
        state_mod.update_state(str(path), {"failure_class": "MAYBE_ENGINE"})
    assert path.read_bytes() == before


def test_negative_candidate_prefixed_failure_class_rejected(tmp_path: Path) -> None:
    path = tmp_path / "S.yaml"
    before = _seed(path, _doc("a" * 40, "b" * 40, None))
    with pytest.raises(state_mod.StateWriteError, match="failure_class"):
        state_mod.update_state(str(path), {"failure_class": "ARGENTUM_ENGINE_DEFECT"})
    assert path.read_bytes() == before


def test_negative_invalid_root_cause_class_rejected(tmp_path: Path) -> None:
    path = tmp_path / "S.yaml"
    before = _seed(path, _doc("a" * 40, "b" * 40, None))
    with pytest.raises(state_mod.StateWriteError, match="root_cause_class"):
        state_mod.update_state(
            str(path),
            {"root_cause_class": "ARGENTUM_ENGINE_DEFECT (view-layer masking omission)"},
        )
    assert path.read_bytes() == before


def test_negative_bad_sha_rejected(tmp_path: Path) -> None:
    path = tmp_path / "S.yaml"
    before = _seed(path, _doc("a" * 40, "b" * 40, None))
    with pytest.raises(state_mod.StateWriteError, match="state_written_against_head"):
        state_mod.update_state(str(path), {"state_written_against_head": "xyz"})
    assert path.read_bytes() == before


def test_negative_missing_required_field_rejected(tmp_path: Path) -> None:
    path = tmp_path / "S.yaml"
    before = _seed(path, _doc("a" * 40, "b" * 40, None))
    with pytest.raises(state_mod.StateWriteError, match="objective"):
        state_mod.update_state(str(path), {"objective": ""})
    assert path.read_bytes() == before
    bad = _doc("a" * 40, "b" * 40, None)
    del bad["objective"]
    with pytest.raises(state_mod.StateWriteError, match="objective"):
        state_mod.write_state(str(path), bad)
    assert path.read_bytes() == before


def test_negative_wrong_list_type_rejected(tmp_path: Path) -> None:
    path = tmp_path / "S.yaml"
    before = _seed(path, _doc("a" * 40, "b" * 40, None))
    with pytest.raises(state_mod.StateWriteError, match="must be a list"):
        state_mod.update_state(str(path), {"in_scope": "not-a-list"})
    assert path.read_bytes() == before


def test_negative_identity_mutation_rejected(tmp_path: Path) -> None:
    path = tmp_path / "S.yaml"
    before = _seed(path, _doc("a" * 40, "b" * 40, None))
    with pytest.raises(state_mod.StateWriteError, match="immutable source-lock"):
        state_mod.update_state(str(path), {"audit_base_sha": "f" * 40})
    assert path.read_bytes() == before


def test_negative_all_identity_fields_guarded(tmp_path: Path) -> None:
    path = tmp_path / "S.yaml"
    before = _seed(path, _doc("a" * 40, "b" * 40, None))
    for field in state_mod.IMMUTABLE_IDENTITY_FIELDS:
        with pytest.raises(state_mod.StateWriteError, match="immutable source-lock"):
            state_mod.update_state(str(path), {field: "changed"})
        assert path.read_bytes() == before, field


def test_negative_fabricated_validated_head_rejected(history: Path, tmp_path: Path) -> None:
    _base, _validated, live = _shas(history)
    path = tmp_path / "S.yaml"
    before = _seed(path, _doc("f" * 40, live, None))
    with pytest.raises(state_mod.StateWriteError, match="VALIDATED_OUTSIDE_LOCK"):
        state_mod.update_state(
            str(path), {"status": "WAITING"}, workdir=str(history), validated_head=_validated
        )
    assert path.read_bytes() == before


def test_negative_rewritten_validated_head_rejected(history: Path, tmp_path: Path) -> None:
    base, validated, _live = _shas(history)
    _git(["reset", "--hard", "HEAD~2"], history)
    live = _git(["rev-parse", "HEAD"], history)
    assert live == base
    path = tmp_path / "S.yaml"
    before = _seed(path, _doc(base, live, None))
    with pytest.raises(state_mod.StateWriteError, match="VALIDATED_REWRITTEN"):
        state_mod.update_state(
            str(path), {"status": "WAITING"}, workdir=str(history), validated_head=validated
        )
    assert path.read_bytes() == before


def test_negative_validated_head_in_patch_rejected(tmp_path: Path) -> None:
    path = tmp_path / "S.yaml"
    before = _seed(path, _doc("a" * 40, "b" * 40, None))
    with pytest.raises(state_mod.StateWriteError, match="explicit validated_head"):
        state_mod.update_state(str(path), {"validated_head": "a" * 40})
    assert path.read_bytes() == before


def test_negative_serializer_failure_preserves_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "S.yaml"
    before = _seed(path, _doc("a" * 40, "b" * 40, None))

    def _boom(_doc: dict) -> str:
        raise RuntimeError("simulated serializer failure")

    monkeypatch.setattr(state_mod, "dump_state", _boom)
    with pytest.raises(RuntimeError, match="simulated serializer"):
        state_mod.write_state(str(path), _doc("a" * 40, "b" * 40, None))
    assert path.read_bytes() == before


def test_negative_replace_failure_preserves_bytes_and_cleans_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os as _os

    path = tmp_path / "S.yaml"
    before = _seed(path, _doc("a" * 40, "b" * 40, None))

    def _boom(_src: str, _dst: str) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(_os, "replace", _boom)
    with pytest.raises(OSError, match="simulated replace"):
        state_mod.write_state(str(path), _doc("a" * 40, "b" * 40, None) | {"status": "WAITING"})
    assert path.read_bytes() == before
    assert [p for p in tmp_path.iterdir() if p.name != "S.yaml"] == []


# --- End-to-end CLI ----------------------------------------------------------


def test_cli_update_round_trips_colon_string(tmp_path: Path) -> None:
    path = tmp_path / "S.yaml"
    _seed(path, _doc("a" * 40, "b" * 40, None))
    patch = tmp_path / "patch.json"
    tricky = "Coordinator decision: authorize #1 — café: go"
    patch.write_text(json.dumps({"exact_next_action": tricky}), encoding="utf-8")
    rc = state_mod.main(["--state", str(path), "--patch-file", str(patch)])
    assert rc == 0
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["exact_next_action"] == tricky


def test_cli_rejects_invalid_enum_and_preserves_bytes(tmp_path: Path) -> None:
    path = tmp_path / "S.yaml"
    before = _seed(path, _doc("a" * 40, "b" * 40, None))
    patch = tmp_path / "patch.json"
    patch.write_text(json.dumps({"failure_class": "ARGENTUM_ENGINE_DEFECT"}), encoding="utf-8")
    rc = state_mod.main(["--state", str(path), "--patch-file", str(patch)])
    assert rc != 0
    assert path.read_bytes() == before


def test_cli_rejects_identity_change_without_rebind(tmp_path: Path) -> None:
    path = tmp_path / "S.yaml"
    before = _seed(path, _doc("a" * 40, "b" * 40, None))
    patch = tmp_path / "patch.json"
    patch.write_text(json.dumps({"audit_base_sha": "f" * 40}), encoding="utf-8")
    assert state_mod.main(["--state", str(path), "--patch-file", str(patch)]) != 0
    assert path.read_bytes() == before
    assert (
        state_mod.main(
            ["--state", str(path), "--patch-file", str(patch), "--allow-identity-change"]
        )
        == 0
    )
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["audit_base_sha"] == "f" * 40


def test_cli_validated_head_lifecycle(history: Path, tmp_path: Path) -> None:
    base, validated, live = _shas(history)
    path = tmp_path / "S.yaml"
    _seed(path, _doc(base, live, None))
    patch = tmp_path / "patch.json"
    patch.write_text(json.dumps({"status": "WAITING"}), encoding="utf-8")
    rc = state_mod.main(
        [
            "--state",
            str(path),
            "--patch-file",
            str(patch),
            "--set-validated-head",
            validated,
            "--workdir",
            str(history),
        ]
    )
    assert rc == 0
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["validated_head"] == validated
    rc = state_mod.main(
        [
            "--state",
            str(path),
            "--patch-file",
            str(patch),
            "--clear-validated-head",
            "--workdir",
            str(history),
        ]
    )
    assert rc == 0
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["validated_head"] is None


def test_cli_fabricated_validated_head_rejected(history: Path, tmp_path: Path) -> None:
    _base, validated, live = _shas(history)
    path = tmp_path / "S.yaml"
    before = _seed(path, _doc("f" * 40, live, None))
    patch = tmp_path / "patch.json"
    patch.write_text(json.dumps({"status": "WAITING"}), encoding="utf-8")
    rc = state_mod.main(
        [
            "--state",
            str(path),
            "--patch-file",
            str(patch),
            "--set-validated-head",
            validated,
            "--workdir",
            str(history),
        ]
    )
    assert rc != 0
    assert path.read_bytes() == before


def test_cli_stamp_head(history: Path, tmp_path: Path) -> None:
    base, _validated, live = _shas(history)
    path = tmp_path / "S.yaml"
    _seed(path, _doc(base, "0" * 40, None))
    patch = tmp_path / "patch.json"
    patch.write_text(json.dumps({"status": "WAITING"}), encoding="utf-8")
    rc = state_mod.main(
        [
            "--state",
            str(path),
            "--patch-file",
            str(patch),
            "--stamp-head",
            "--workdir",
            str(history),
        ]
    )
    assert rc == 0
    reread = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert reread["state_written_against_head"] == live
    assert reread["validated_head"] is None


def test_cli_write_from_full_document(tmp_path: Path) -> None:
    path = tmp_path / "S.yaml"
    _seed(path, _doc("a" * 40, "b" * 40, None))
    incoming = tmp_path / "incoming.json"
    incoming.write_text(
        json.dumps(_doc("a" * 40, "b" * 40, None) | {"status": "BLOCKED"}), encoding="utf-8"
    )
    assert state_mod.main(["--state", str(path), "--write-from", str(incoming)]) == 0
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["status"] == "BLOCKED"


def test_cli_write_from_invalid_rejected(tmp_path: Path) -> None:
    path = tmp_path / "S.yaml"
    before = _seed(path, _doc("a" * 40, "b" * 40, None))
    incoming = tmp_path / "incoming.json"
    incoming.write_text(
        json.dumps(_doc("a" * 40, "b" * 40, None) | {"status": "DONE"}), encoding="utf-8"
    )
    assert state_mod.main(["--state", str(path), "--write-from", str(incoming)]) != 0
    assert path.read_bytes() == before


def test_cli_migrate_in_place_is_atomic_and_valid(tmp_path: Path) -> None:
    legacy = _doc("a" * 40, "a" * 40, None)
    legacy["schema_version"] = "1.0"
    legacy["current_head"] = legacy.pop("state_written_against_head")
    del legacy["validated_head"]
    path = tmp_path / "S.yaml"
    path.write_text(yaml.safe_dump(legacy), encoding="utf-8")
    assert state_mod.main(["--state", str(path), "--migrate", "--in-place"]) == 0
    reread = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert reread["schema_version"] == "2.0"
    assert reread["validated_head"] is None
    assert state_mod.validate(reread) == []
    assert [p for p in tmp_path.iterdir() if p.name != "S.yaml"] == []


def test_bootstrap_init_state_uses_canonical_writer(tmp_path: Path) -> None:
    sys.path.insert(0, str(REPO_ROOT / "tools"))
    from foundry import bootstrap as bootstrap_mod

    wt = tmp_path / "wt"
    wt.mkdir()
    _git(["init", "-b", "main"], wt)
    _git(["config", "user.email", "test@example.com"], wt)
    _git(["config", "user.name", "Test"], wt)
    (wt / "f.txt").write_text("x\n", encoding="utf-8")
    _git(["add", "."], wt)
    _git(["commit", "-m", "init"], wt)
    base = _git(["rev-parse", "HEAD"], wt)
    doc = bootstrap_mod.init_state(str(wt), "TEST-WS", "project/test", base, "0" * 40, "r")
    target = tmp_path / "STATE.yaml"
    bootstrap_mod.state_mod.write_state(str(target), doc, workdir=str(wt))
    assert state_mod.validate(yaml.safe_load(target.read_text(encoding="utf-8"))) == []


# --- PR #178 review remediation: P1 (validation credit requires workdir) ---


def test_p1_api_write_state_nonnull_without_workdir_rejected(history: Path, tmp_path: Path) -> None:
    """Gate 1: even ancestry-valid credit without workdir fails closed (API)."""
    base, validated, live = _shas(history)
    path = tmp_path / "S.yaml"
    before = _seed(path, _doc(base, live, None))
    with pytest.raises(state_mod.StateWriteError, match="no workdir"):
        state_mod.write_state(str(path), _doc(base, live, validated))
    assert path.read_bytes() == before


def test_p1_api_update_state_set_without_workdir_rejected(history: Path, tmp_path: Path) -> None:
    """Gate 1b: update_state setting credit without workdir fails closed."""
    base, validated, live = _shas(history)
    path = tmp_path / "S.yaml"
    before = _seed(path, _doc(base, live, None))
    with pytest.raises(state_mod.StateWriteError, match="no workdir"):
        state_mod.update_state(str(path), {"status": "WAITING"}, validated_head=validated)
    assert path.read_bytes() == before


def test_p1_api_update_state_preserve_without_workdir_rejected(
    history: Path, tmp_path: Path
) -> None:
    """Preserving stored non-null credit without workdir fails closed (API)."""
    base, validated, live = _shas(history)
    path = tmp_path / "S.yaml"
    before = _seed(path, _doc(base, live, validated))
    with pytest.raises(state_mod.StateWriteError, match="no workdir"):
        state_mod.update_state(str(path), {"status": "WAITING"})
    assert path.read_bytes() == before


def test_p1_api_clear_without_workdir_allowed(history: Path, tmp_path: Path) -> None:
    """Clearing credit to null remains possible without a workdir."""
    base, validated, live = _shas(history)
    path = tmp_path / "S.yaml"
    _seed(path, _doc(base, live, validated))
    state_mod.update_state(str(path), {"status": "WAITING"}, validated_head=None)
    reread = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert reread["validated_head"] is None
    assert reread["status"] == "WAITING"


def test_p1_cli_set_patch_without_workdir_rejected(history: Path, tmp_path: Path) -> None:
    """Gate 2: CLI --set-validated-head + patch without --workdir rejects."""
    base, validated, live = _shas(history)
    path = tmp_path / "S.yaml"
    before = _seed(path, _doc(base, live, None))
    patch = tmp_path / "patch.json"
    patch.write_text(json.dumps({"status": "WAITING"}), encoding="utf-8")
    rc = state_mod.main(
        [
            "--state",
            str(path),
            "--patch-file",
            str(patch),
            "--set-validated-head",
            validated,
        ]
    )
    assert rc != 0
    assert path.read_bytes() == before


def test_p1_cli_write_from_nonnull_without_workdir_rejected(history: Path, tmp_path: Path) -> None:
    """Gate 3: --write-from carrying non-null credit without --workdir rejects."""
    base, validated, live = _shas(history)
    path = tmp_path / "S.yaml"
    before = _seed(path, _doc(base, live, None))
    incoming = tmp_path / "incoming.json"
    incoming.write_text(json.dumps(_doc(base, live, validated)), encoding="utf-8")
    assert state_mod.main(["--state", str(path), "--write-from", str(incoming)]) != 0
    assert path.read_bytes() == before


def test_p1_cli_write_from_nonnull_with_workdir_allowed(history: Path, tmp_path: Path) -> None:
    """Gate 12b: same --write-from with --workdir and valid ancestry succeeds."""
    base, validated, live = _shas(history)
    path = tmp_path / "S.yaml"
    _seed(path, _doc(base, live, None))
    incoming = tmp_path / "incoming.json"
    incoming.write_text(json.dumps(_doc(base, live, validated)), encoding="utf-8")
    assert (
        state_mod.main(
            ["--state", str(path), "--write-from", str(incoming), "--workdir", str(history)]
        )
        == 0
    )
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["validated_head"] == validated


def test_p1_cli_write_from_null_without_workdir_allowed(tmp_path: Path) -> None:
    """Null credit stays valid without a workdir (bootstrap/migration shape)."""
    path = tmp_path / "S.yaml"
    _seed(path, _doc("a" * 40, "b" * 40, None))
    incoming = tmp_path / "incoming.json"
    incoming.write_text(
        json.dumps(_doc("a" * 40, "b" * 40, None) | {"status": "WAITING"}),
        encoding="utf-8",
    )
    assert state_mod.main(["--state", str(path), "--write-from", str(incoming)]) == 0
    reread = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert reread["validated_head"] is None
    assert reread["status"] == "WAITING"


def test_p1_cli_rewritten_validated_head_rejected(history: Path, tmp_path: Path) -> None:
    """Gate 5 (CLI): credit not ancestor of live HEAD rejects, bytes preserved."""
    base, validated, _live = _shas(history)
    _git(["reset", "--hard", "HEAD~2"], history)
    live = _git(["rev-parse", "HEAD"], history)
    assert live == base
    path = tmp_path / "S.yaml"
    before = _seed(path, _doc(base, live, None))
    patch = tmp_path / "patch.json"
    patch.write_text(json.dumps({"status": "WAITING"}), encoding="utf-8")
    rc = state_mod.main(
        [
            "--state",
            str(path),
            "--patch-file",
            str(patch),
            "--set-validated-head",
            validated,
            "--workdir",
            str(history),
        ]
    )
    assert rc != 0
    assert path.read_bytes() == before


# --- PR #178 review remediation: P2 (no silent write-intent no-op) ---


def test_p2_set_without_write_mode_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Gate 6: --set-validated-head without a write mode rejects (no STATE_OK)."""
    path = tmp_path / "S.yaml"
    before = _seed(path, _doc("a" * 40, "b" * 40, None))
    rc = state_mod.main(["--state", str(path), "--set-validated-head", "a" * 40])
    assert rc != 0
    assert path.read_bytes() == before
    captured = capsys.readouterr()
    assert "STATE_REJECT" in captured.err
    assert "STATE_OK" not in captured.out


def test_p2_clear_without_write_mode_rejected(tmp_path: Path) -> None:
    """Gate 7: --clear-validated-head without a write mode rejects."""
    path = tmp_path / "S.yaml"
    before = _seed(path, _doc("a" * 40, "b" * 40, None))
    assert state_mod.main(["--state", str(path), "--clear-validated-head"]) != 0
    assert path.read_bytes() == before


def test_p2_stamp_without_write_mode_rejected(tmp_path: Path) -> None:
    """Gate 8: --stamp-head without a write mode rejects."""
    path = tmp_path / "S.yaml"
    before = _seed(path, _doc("a" * 40, "b" * 40, None))
    assert state_mod.main(["--state", str(path), "--stamp-head"]) != 0
    assert path.read_bytes() == before


def test_p2_allow_without_write_mode_rejected(tmp_path: Path) -> None:
    """Gate 9: meaningless --allow-identity-change without a write op rejects."""
    path = tmp_path / "S.yaml"
    before = _seed(path, _doc("a" * 40, "b" * 40, None))
    assert state_mod.main(["--state", str(path), "--allow-identity-change"]) != 0
    assert path.read_bytes() == before


def test_p2_in_place_without_migrate_rejected(tmp_path: Path) -> None:
    """Other write-only flag: --in-place without --migrate rejects."""
    path = tmp_path / "S.yaml"
    before = _seed(path, _doc("a" * 40, "b" * 40, None))
    assert state_mod.main(["--state", str(path), "--in-place"]) != 0
    assert path.read_bytes() == before


def test_p2_migrate_with_patch_file_rejected(tmp_path: Path) -> None:
    """Conflicting modes: --migrate with --patch-file rejects (no silent drop)."""
    path = tmp_path / "S.yaml"
    before = _seed(path, _doc("a" * 40, "b" * 40, None))
    patch = tmp_path / "patch.json"
    patch.write_text(json.dumps({"status": "WAITING"}), encoding="utf-8")
    assert state_mod.main(["--state", str(path), "--migrate", "--patch-file", str(patch)]) != 0
    assert path.read_bytes() == before


def test_p2_read_only_remains_ok(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Gate 13: ordinary read-only validation stays STATE_OK."""
    path = tmp_path / "S.yaml"
    _seed(path, _doc("a" * 40, "b" * 40, None))
    assert state_mod.main(["--state", str(path)]) == 0
    captured = capsys.readouterr()
    assert "STATE_OK" in captured.out


def test_p2_clear_with_patch_without_workdir_allowed(tmp_path: Path) -> None:
    """Clearing via a real write mode stays green without a workdir (gate 11)."""
    path = tmp_path / "S.yaml"
    _seed(path, _doc("a" * 40, "b" * 40, None))
    patch = tmp_path / "patch.json"
    patch.write_text(json.dumps({"status": "WAITING"}), encoding="utf-8")
    assert (
        state_mod.main(["--state", str(path), "--patch-file", str(patch), "--clear-validated-head"])
        == 0
    )
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["validated_head"] is None
