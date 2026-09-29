"""Tests for tools/foundry/drift_check.py and the repo profiles.

Fixture git repos stand in for engine checkouts; one live read-only test runs
the checker against the real mage worktree to prove the stale-routing finding
is not a fixture artifact.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
PROFILES = ROOT / ".foundry" / "repo-profiles"

sys.path.insert(0, str(ROOT / "tools"))

from foundry import drift_check as drift_mod  # noqa: E402

MAGE_SLUG = "moeendres-png/mage"
CPL_SLUG = "moeendres-png/commander-playtest-lab"

# Live mage checkout used by the one read-only test below. That test is
# machine-local by design: proving the stale-routing finding is not a fixture
# artifact requires a real mage checkout. Resolved from MAGE_WORKTREE so any
# machine -- or CI with a checkout provisioned -- can enable it. The historical
# hardcoded path remains the fallback, so behaviour on the machine it was
# written for is unchanged.
#
# Deliberately NOT ENGINE_SOURCE_PATH: that variable names the engine under test
# (see src/commander_lab/engine/process_manager.py), and this repository carries
# more than one candidate engine. Overloading it would let a Forge checkout
# silently satisfy a mage assertion.
DEFAULT_LIVE_MAGE = Path("/home/moeen/code/mage-d3q6")
LIVE_MAGE = Path(os.environ.get("MAGE_WORKTREE") or DEFAULT_LIVE_MAGE)


def _git(args: list[str], cwd: Path) -> None:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"git {args}: {proc.stderr}"


@pytest.fixture()
def enginerepo(tmp_path: Path) -> Path:
    wt = tmp_path / "engine"
    wt.mkdir()
    _git(["init", "-b", "master"], wt)
    _git(["config", "user.email", "t@example.com"], wt)
    _git(["config", "user.name", "T"], wt)
    _git(["config", "remote.origin.url", f"https://github.com/{MAGE_SLUG}.git"], wt)
    (wt / "code.txt").write_text("engine\n", encoding="utf-8")
    _git(["add", "."], wt)
    _git(["commit", "-m", "init"], wt)
    return wt


def _profile(name: str) -> dict:
    return json.loads((PROFILES / f"{name}.json").read_text(encoding="utf-8"))


def test_profiles_parse_and_carry_required_keys() -> None:
    for name in ("cpl", "mage", "forge"):
        profile = _profile(name)
        for key in (
            "profile",
            "repo_slug",
            "default_branch",
            "canonical_policy",
            "stale_markers",
            "forbidden_mutation",
            "safe_external_dirs",
        ):
            assert key in profile, (name, key)
    assert _profile("cpl")["canonical_policy"] is True
    assert _profile("mage")["canonical_policy"] is False
    assert _profile("mage")["default_branch"] == "master"
    assert _profile("forge")["default_branch"] == "master"


def test_stale_mage_agents_fails_closed(enginerepo: Path) -> None:
    (enginerepo / "AGENTS.md").write_text(
        "# WS33 contract\nTASK_COMPLETE gates\nPROJECT_STATE.md\n", encoding="utf-8"
    )
    result = drift_mod.check(str(enginerepo), _profile("mage"), "")
    assert result["verdict"] == "DRIFT_FAIL"
    surfaces = {f["surface"]: f["classification"] for f in result["findings"]}
    assert surfaces["AGENTS.md"] == "SUPERSEDED_BUT_REACHABLE"


def test_marker_free_engine_agents_still_fails_closed(enginerepo: Path) -> None:
    (enginerepo / "AGENTS.md").write_text(
        "# Some engine notes\nBuild with make.\n", encoding="utf-8"
    )
    result = drift_mod.check(str(enginerepo), _profile("mage"), "")
    assert result["verdict"] == "DRIFT_FAIL"
    surfaces = {f["surface"]: f["classification"] for f in result["findings"]}
    assert surfaces["AGENTS.md"] == "AMBIGUOUS"


def test_engine_local_project_config_fails_even_when_model_matches(
    enginerepo: Path,
) -> None:
    (enginerepo / "opencode.json").write_text(
        json.dumps({"model": drift_mod.CANONICAL_MODEL}), encoding="utf-8"
    )
    result = drift_mod.check(str(enginerepo), _profile("mage"), "")
    assert result["verdict"] == "DRIFT_FAIL"
    surfaces = {f["surface"]: f["classification"] for f in result["findings"]}
    assert surfaces["opencode.json"] == "AMBIGUOUS"


def test_wrong_repo_identity_fails(enginerepo: Path) -> None:
    _git(
        ["config", "remote.origin.url", "https://github.com/someone-else/other.git"],
        enginerepo,
    )
    result = drift_mod.check(str(enginerepo), _profile("mage"), "")
    assert result["verdict"] == "DRIFT_FAIL"


@pytest.mark.parametrize(
    "remote",
    [
        "https://github.com/other/moeendres-png/mage.git",
        "https://not-github.invalid/moeendres-png/mage.git",
        "https://github.com/moeendres-png/mage-lookalike.git",
    ],
)
def test_drift_identity_reuses_exact_source_lock_contract(enginerepo, remote):
    _git(["config", "remote.origin.url", remote], enginerepo)
    result = drift_mod.check(str(enginerepo), _profile("mage"), "")
    assert result["verdict"] == "DRIFT_FAIL"
    assert remote not in json.dumps(result)


def test_drift_rejects_multiple_remote_records(enginerepo):
    _git(
        ["config", "--add", "remote.origin.url", f"https://github.com/{MAGE_SLUG}.git"], enginerepo
    )
    result = drift_mod.check(str(enginerepo), _profile("mage"), "")
    assert result["verdict"] == "DRIFT_FAIL"


def test_cpl_target_with_canonical_surfaces_is_clean(tmp_path: Path) -> None:
    wt = tmp_path / "cpl"
    wt.mkdir()
    _git(["init", "-b", "main"], wt)
    _git(["config", "user.email", "t@example.com"], wt)
    _git(["config", "user.name", "T"], wt)
    _git(["config", "remote.origin.url", f"https://github.com/{CPL_SLUG}.git"], wt)
    (wt / "AGENTS.md").write_text("# canonical\n", encoding="utf-8")
    (wt / "opencode.json").write_text("{}", encoding="utf-8")
    _git(["add", "."], wt)
    _git(["commit", "-m", "init"], wt)
    result = drift_mod.check(str(wt), _profile("cpl"), "")
    assert result["verdict"] == "DRIFT_CLEAN", result["findings"]
    assert result["canonical_policy_hash"] is not None


def test_bundle_hash_stable_and_content_sensitive(tmp_path: Path) -> None:
    root = tmp_path / "canon"
    root.mkdir()
    (root / "AGENTS.md").write_text("policy v1\n", encoding="utf-8")
    h1 = drift_mod.canonical_bundle_hash(str(root), ["AGENTS.md"])
    h2 = drift_mod.canonical_bundle_hash(str(root), ["AGENTS.md"])
    assert h1 == h2 and len(h1) == 64
    (root / "AGENTS.md").write_text("policy v2\n", encoding="utf-8")
    assert drift_mod.canonical_bundle_hash(str(root), ["AGENTS.md"]) != h1


def test_live_mage_worktree_drift_fails_read_only() -> None:
    """Read-only proof against the real mage checkout (not a fixture).

    Two different absences mean two different things, and conflating them sends
    the wrong signal:

    * no checkout at all -> a property of this machine. Nothing changed and
      there is nothing to re-adjudicate; the correct response is to point
      MAGE_WORKTREE at a checkout, or to accept that the claim this test makes
      is simply not established on this machine.
    * a checkout that exists but has no AGENTS.md -> reality changed, and the
      drift profile is now describing a state that no longer holds.

    Only the second is a reason to re-adjudicate. The single skip message this
    replaced said "reality changed" for both, so a fresh CI machine reported a
    change in reality where none had occurred.
    """
    if not LIVE_MAGE.is_dir():
        pytest.skip(
            f"no mage checkout at {LIVE_MAGE}: this test is machine-local, so the "
            "'not a fixture artifact' claim is not established here. Set MAGE_WORKTREE "
            "to a mage checkout to enable it."
        )
    agents = LIVE_MAGE / "AGENTS.md"
    if not agents.is_file():
        pytest.skip(
            f"mage checkout at {LIVE_MAGE} exists but carries no AGENTS.md: THIS is the "
            "'reality changed' condition. Re-adjudicate .foundry/repo-profiles/mage.json "
            "before trusting its drift verdict."
        )
    result = drift_mod.check(str(LIVE_MAGE), _profile("mage"), "")
    by_surface = {f["surface"]: f for f in result["findings"]}
    assert "AGENTS.md" in by_surface
    assert by_surface["AGENTS.md"]["classification"] in (
        "SUPERSEDED_BUT_REACHABLE",
        "AMBIGUOUS",
    )
    assert result["verdict"] == "DRIFT_FAIL"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))


@pytest.mark.parametrize("scope", ["local", "global", "environment"])
def test_drift_rejects_effective_url_rewrites(enginerepo, tmp_path, monkeypatch, scope):
    key = "url.https://private-marker.invalid/.insteadOf"
    if scope == "local":
        _git(["config", key, "https://github.com/"], enginerepo)
    elif scope == "global":
        config = tmp_path / "global-gitconfig"
        _git(["config", "--file", str(config), key, "https://github.com/"], enginerepo)
        monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    else:
        monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
        monkeypatch.setenv("GIT_CONFIG_KEY_0", key)
        monkeypatch.setenv("GIT_CONFIG_VALUE_0", "https://github.com/")
    result = drift_mod.check(str(enginerepo), _profile("mage"), "")
    assert result["verdict"] == "DRIFT_FAIL"
    assert "private-marker" not in json.dumps(result)
    assert any("EFFECTIVE_URL_REWRITE" in f["detail"] for f in result["findings"])


def test_drift_fails_closed_if_rewrite_guard_is_unavailable(enginerepo, monkeypatch):
    def unavailable(*args):
        raise OSError("private-marker")

    monkeypatch.setattr(drift_mod, "_no_url_rewrites", unavailable)
    result = drift_mod.check(str(enginerepo), _profile("mage"), "")
    assert result["verdict"] == "DRIFT_FAIL"
    assert "private-marker" not in json.dumps(result)
