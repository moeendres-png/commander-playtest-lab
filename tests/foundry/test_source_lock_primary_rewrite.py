"""WS239 P1: the primary verify()/bootstrap identity gate fails closed on rewrites.

No live network. Real local Git fixtures carry a canonical-looking
``remote.origin.url`` whose effective transport is redirected to an unrelated
local repository via local, global, or ``GIT_CONFIG_COUNT`` environment
``url.*.insteadOf`` configuration. The no-probe ``verify()``/``main()``/
``bootstrap()`` path must fail closed (``EFFECTIVE_URL_REWRITE``) instead of
reporting a false PASS. Rewrite presence is inspected by exit status only;
config values are never read into diagnostics.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
TOOLS = ROOT / "tools" / "foundry"

sys.path.insert(0, str(ROOT / "tools"))

from foundry import bootstrap as bootstrap_mod  # noqa: E402
from foundry import source_lock as lock  # noqa: E402

SLUG = lock.CANONICAL_SLUG
NOMINAL = f"https://github.com/{SLUG}.git"
BRANCH = "ws239-rewrite-topic"


@pytest.fixture()
def hermetic_git_env(tmp_path, monkeypatch):
    """Sandbox HOME/global/system config plus environment config overrides.

    Each test then observes exactly the rewrite configuration it installs,
    independent of ambient machine state.
    """
    home = tmp_path / "home"
    home.mkdir()
    empty_global = home / "empty-global"
    empty_global.write_text("", encoding="utf-8")
    empty_system = home / "empty-system"
    empty_system.write_text("", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty_global))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(empty_system))
    monkeypatch.delenv("GIT_CONFIG_COUNT", raising=False)
    for index in range(10):
        monkeypatch.delenv(f"GIT_CONFIG_KEY_{index}", raising=False)
        monkeypatch.delenv(f"GIT_CONFIG_VALUE_{index}", raising=False)
    return {"home": home, "global": empty_global, "system": empty_system}


def _git(args, cwd):
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"git {args}: {proc.stderr}"
    return proc.stdout.strip()


@pytest.fixture()
def redirected(tmp_path):
    """Fixture repo with canonical literal origin plus an unrelated target."""
    work = tmp_path / "work"
    other = tmp_path / "other"
    work.mkdir()
    other.mkdir()
    _git(["init", "-b", BRANCH], work)
    _git(
        [
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "--allow-empty",
            "-m",
            "fixture",
        ],
        work,
    )
    _git(["remote", "add", "origin", NOMINAL], work)
    _git(["init", "-b", BRANCH], other)
    _git(
        [
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "--allow-empty",
            "-m",
            "other",
        ],
        other,
    )
    head = _git(["rev-parse", "HEAD"], work)
    return {"work": work, "other": other, "head": head}


def _apply_rewrite(kind, paths, monkeypatch):
    work, other = paths["work"], paths["other"]
    if kind == "local":
        _git(["config", "url." + str(other) + ".insteadOf", NOMINAL], work)
    elif kind == "environment":
        monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
        monkeypatch.setenv("GIT_CONFIG_KEY_0", "url." + str(other) + ".insteadOf")
        monkeypatch.setenv("GIT_CONFIG_VALUE_0", NOMINAL)
    elif kind == "global":
        global_file = work.parent / "injected-global"
        global_file.write_text(f'[url "{other}"]\n\tinsteadOf = {NOMINAL}\n', encoding="utf-8")
        monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_file))
    else:
        raise AssertionError(kind)


def _effective_url(work):
    proc = subprocess.run(
        ["git", "ls-remote", "--get-url", "origin"],
        cwd=work,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


@pytest.mark.parametrize("kind", ["local", "environment", "global"])
def test_effective_url_differs_from_literal(kind, redirected, hermetic_git_env, monkeypatch):
    """The attack premise: literal origin reads canonical, transport does not."""
    _apply_rewrite(kind, redirected, monkeypatch)
    literal = _git(["config", "--get", "remote.origin.url"], redirected["work"])
    assert SLUG in literal
    assert _effective_url(redirected["work"]) != NOMINAL


@pytest.mark.parametrize("kind", ["local", "environment", "global"])
def test_primary_verify_rejects_rewrite(kind, redirected, hermetic_git_env, monkeypatch):
    _apply_rewrite(kind, redirected, monkeypatch)
    reasons = lock.verify(SLUG, BRANCH, redirected["head"], str(redirected["work"]))
    assert any("EFFECTIVE_URL_REWRITE" in r for r in reasons), reasons


@pytest.mark.parametrize("kind", ["local", "environment", "global"])
def test_primary_main_no_probe_fails_closed(
    kind, redirected, hermetic_git_env, monkeypatch, capsys
):
    _apply_rewrite(kind, redirected, monkeypatch)
    rc = lock.main(
        [
            "--repo",
            SLUG,
            "--branch",
            BRANCH,
            "--audit-base-sha",
            redirected["head"],
            "--workdir",
            str(redirected["work"]),
        ]
    )
    out_err = capsys.readouterr()
    assert rc == 1
    assert "LOCK_OK" not in out_err.out
    assert "EFFECTIVE_URL_REWRITE" in out_err.err


def test_primary_verify_control_passes_without_rewrite(redirected, hermetic_git_env):
    reasons = lock.verify(SLUG, BRANCH, redirected["head"], str(redirected["work"]))
    assert reasons == []


def test_primary_verify_unreadable_rewrite_config_fails_closed(
    redirected, hermetic_git_env, monkeypatch
):
    monkeypatch.setattr(
        lock,
        "_no_url_rewrites",
        lambda *a: (_ for _ in ()).throw(subprocess.TimeoutExpired("git", 30)),
    )
    reasons = lock.verify(SLUG, BRANCH, redirected["head"], str(redirected["work"]))
    assert any("EFFECTIVE_URL_REWRITE" in r for r in reasons), reasons


def test_primary_verify_rewrite_present_status_fails_closed(
    redirected, hermetic_git_env, monkeypatch
):
    monkeypatch.setattr(lock, "_no_url_rewrites", lambda *a: False)
    reasons = lock.verify(SLUG, BRANCH, redirected["head"], str(redirected["work"]))
    assert any("EFFECTIVE_URL_REWRITE" in r for r in reasons), reasons


def test_primary_verify_guard_never_echoes_credentials(redirected, hermetic_git_env):
    _git(
        ["config", "url.https://USER:SECRET-TOKEN@example.invalid/.insteadOf", NOMINAL],
        redirected["work"],
    )
    reasons = lock.verify(SLUG, BRANCH, redirected["head"], str(redirected["work"]))
    assert any("EFFECTIVE_URL_REWRITE" in r for r in reasons), reasons
    assert "SECRET-TOKEN" not in str(reasons)


def test_bootstrap_source_lock_gate_rejects_rewrite(
    redirected, hermetic_git_env, monkeypatch, tmp_path
):
    """End-to-end P1: bootstrap() step 1 fails closed under an active rewrite."""
    _apply_rewrite("local", redirected, monkeypatch)
    work = redirected["work"]
    (work / "AGENTS.md").write_text("# canonical policy\n", encoding="utf-8")
    state = {
        "schema_version": "2.0",
        "repository": SLUG,
        "worktree": str(work),
        "branch": BRANCH,
        "audit_base_sha": redirected["head"],
        "audit_base_tree": "0" * 40,
        "state_written_against_head": redirected["head"],
        "validated_head": None,
        "objective": "WS239 P1 bootstrap negative control",
        "in_scope": [],
        "out_of_scope": [],
        "ownership": "WS239-TEST",
        "status": "ACTIVE",
        "exact_next_action": "fail closed",
    }
    state_path = tmp_path / "state.yaml"
    state_path.write_text(yaml.safe_dump(state), encoding="utf-8")
    result = bootstrap_mod.bootstrap(
        str(work),
        "WS239-TEST",
        BRANCH,
        redirected["head"],
        str(state_path),
        "cpl",
        str(ROOT / ".foundry" / "repo-profiles"),
        "",
        False,
        False,
        None,
        {os.path.realpath(str(work)): str(state_path)},
    )
    assert result["verdict"] == "BOOTSTRAP_FAIL", result
    assert any(
        f.startswith("source lock") and "EFFECTIVE_URL_REWRITE" in f for f in result["failures"]
    ), result["failures"]


def test_bootstrap_control_passes_without_rewrite(redirected, hermetic_git_env, tmp_path):
    work = redirected["work"]
    (work / "AGENTS.md").write_text("# canonical policy\n", encoding="utf-8")
    state = {
        "schema_version": "2.0",
        "repository": SLUG,
        "worktree": str(work),
        "branch": BRANCH,
        "audit_base_sha": redirected["head"],
        "audit_base_tree": "0" * 40,
        "state_written_against_head": redirected["head"],
        "validated_head": None,
        "objective": "WS239 P1 bootstrap positive control",
        "in_scope": [],
        "out_of_scope": [],
        "ownership": "WS239-TEST",
        "status": "ACTIVE",
        "exact_next_action": "pass",
    }
    state_path = tmp_path / "state.yaml"
    state_path.write_text(yaml.safe_dump(state), encoding="utf-8")
    result = bootstrap_mod.bootstrap(
        str(work),
        "WS239-TEST",
        BRANCH,
        redirected["head"],
        str(state_path),
        "cpl",
        str(ROOT / ".foundry" / "repo-profiles"),
        "",
        False,
        False,
        None,
        {os.path.realpath(str(work)): str(state_path)},
    )
    assert not any(f.startswith("source lock") for f in result["failures"]), result
