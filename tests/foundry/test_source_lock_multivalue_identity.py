"""WS240 P2: multivalue remote.origin.url must fail closed, never collapse.

Baseline flaw (PR #202 P2 thread): ``remote_identity()`` piped
``git config --get-all remote.origin.url`` through ``_git(...).strip()``,
so a canonical first URL plus a blank/whitespace-only second record
collapsed back to the canonical string and ``verify()`` returned no
identity error (false PASS). The fix parses NUL-delimited records and
requires exactly one record.

No live network. Real local Git fixtures carry the multivalue config;
the no-probe ``verify()``/``main()``/``bootstrap()`` path must fail
closed. Config values never enter diagnostics.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

PATH = Path(__file__).resolve().parents[2] / "tools/foundry/source_lock.py"
spec = importlib.util.spec_from_file_location("lock_multivalue_under_test", PATH)
lock = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lock)

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from foundry import bootstrap as bootstrap_mod  # noqa: E402

SLUG = lock.CANONICAL_SLUG
NOMINAL = f"https://github.com/{SLUG}.git"
SSH_NOMINAL = f"git@github.com:{SLUG}.git"
BRANCH = "ws240-multivalue-topic"
MARKER_URL = "https://leak-marker-ws240.invalid/somewhere/else.git"


@pytest.fixture()
def hermetic_git_env(tmp_path, monkeypatch):
    """Sandbox HOME/global/system config plus environment config overrides."""
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


def _make_repo(root, name, first_url, extras):
    """Init repo on BRANCH; first_url None means no origin until extras."""
    work = root / name
    work.mkdir()
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
    if first_url is not None:
        _git(["remote", "add", "origin", first_url], work)
    for extra in extras:
        _git(["config", "--add", "remote.origin.url", extra], work)
    head = _git(["rev-parse", "HEAD"], work)
    return work, head


@pytest.mark.parametrize(
    "extras",
    [
        [""],  # canonical + blank second: the exact P2 report
        ["   "],  # canonical + whitespace-only second
        ["\n"],  # canonical + newline-only second
        ["\t"],  # canonical + tab-only second
        [NOMINAL],  # duplicate canonical is still ambiguous
        [MARKER_URL],  # canonical + different URL
        ["", ""],  # canonical + two blank extras
    ],
)
def test_multivalue_verify_fails_closed(tmp_path, hermetic_git_env, extras):
    work, head = _make_repo(tmp_path, "work", NOMINAL, extras)
    reasons = lock.verify(SLUG, BRANCH, head, str(work))
    assert reasons, "multivalue origin must never verify clean"
    assert any("ambiguous" in r or "cannot read origin" in r for r in reasons), reasons


@pytest.mark.parametrize(
    "first_extra",
    ["", "   "],
)
def test_blank_first_canonical_second_verify_fails_closed(tmp_path, hermetic_git_env, first_extra):
    """Record order must not matter: leading junk is still ambiguity."""
    work = tmp_path / "work"
    work.mkdir()
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
    _git(["remote", "set-url", "origin", first_extra], work)
    _git(["config", "--add", "remote.origin.url", NOMINAL], work)
    head = _git(["rev-parse", "HEAD"], work)
    records = lock.remote_url_records(str(work))
    assert records[0] == first_extra and records[1] == NOMINAL
    reasons = lock.verify(SLUG, BRANCH, head, str(work))
    assert reasons, "leading-blank multivalue origin must never verify clean"
    assert any("ambiguous" in r or "cannot read origin" in r for r in reasons), reasons


def test_env_provided_second_url_fails_closed(tmp_path, hermetic_git_env, monkeypatch):
    """A GIT_CONFIG_COUNT environment record joins the identity: still reject."""
    work, head = _make_repo(tmp_path, "work", NOMINAL, [])
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "remote.origin.url")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", NOMINAL)
    assert len(lock.remote_url_records(str(work))) == 2
    reasons = lock.verify(SLUG, BRANCH, head, str(work))
    assert reasons, "environment-added second URL must never verify clean"


def test_global_second_url_fails_closed(tmp_path, hermetic_git_env, monkeypatch):
    """A global-config record joins the identity: still reject."""
    work, head = _make_repo(tmp_path, "work", NOMINAL, [])
    hermetic_git_env["global"].write_text(
        f'[remote "origin"]\n\turl = {MARKER_URL}\n', encoding="utf-8"
    )
    assert len(lock.remote_url_records(str(work))) == 2
    reasons = lock.verify(SLUG, BRANCH, head, str(work))
    assert reasons, "global-added second URL must never verify clean"
    assert "leak-marker-ws240" not in str(reasons)


def test_missing_origin_fails_closed(tmp_path, hermetic_git_env):
    work, head = _make_repo(tmp_path, "work", None, [])
    reasons = lock.verify(SLUG, BRANCH, head, str(work))
    assert reasons and any("cannot read origin" in r for r in reasons), reasons


def test_single_empty_origin_fails_closed(tmp_path, hermetic_git_env):
    work, head = _make_repo(tmp_path, "work", None, [""])
    assert lock.remote_identity(str(work)) == ""
    reasons = lock.verify(SLUG, BRANCH, head, str(work))
    assert reasons and any("WRONG_LOCAL_REPOSITORY" in r for r in reasons), reasons


def test_single_malformed_origin_fails_closed(tmp_path, hermetic_git_env):
    work, head = _make_repo(tmp_path, "work", "/tmp/not-a-remote", [])
    reasons = lock.verify(SLUG, BRANCH, head, str(work))
    assert reasons and any("WRONG_LOCAL_REPOSITORY" in r for r in reasons), reasons


def test_records_preserve_order_and_emptiness(tmp_path, hermetic_git_env):
    work, _ = _make_repo(tmp_path, "work", NOMINAL, ["", "   "])
    assert lock.remote_url_records(str(work)) == [NOMINAL, "", "   "]


def test_remote_identity_single_canonical(tmp_path, hermetic_git_env):
    work, _ = _make_repo(tmp_path, "work", NOMINAL, [])
    assert lock.remote_identity(str(work)) == NOMINAL


def test_remote_identity_rejects_multiple(tmp_path, hermetic_git_env):
    work, _ = _make_repo(tmp_path, "work", NOMINAL, [""])
    with pytest.raises(RuntimeError, match="ambiguous"):
        lock.remote_identity(str(work))


def test_remote_identity_never_echoes_values(monkeypatch):
    monkeypatch.setattr(lock, "remote_url_records", lambda *a: [NOMINAL, MARKER_URL])
    with pytest.raises(RuntimeError) as excinfo:
        lock.remote_identity(".")
    assert "leak-marker-ws240" not in str(excinfo.value)


def test_undecodable_record_fails_closed(monkeypatch):
    monkeypatch.setattr(lock, "_git_raw", lambda *a: b"\xff\x00")
    with pytest.raises(RuntimeError, match="unavailable"):
        lock.remote_url_records(".")


def test_invalid_remote_name_rejected():
    with pytest.raises(RuntimeError):
        lock.remote_url_records(".", "origin;evil")


def test_ref_check_refuses_multivalue_without_probe(tmp_path, hermetic_git_env, monkeypatch):
    """Ambiguous identity stops before any rewrite inspection or ls-remote."""

    def no_probe(*a, **k):  # pragma: no cover - must never run
        raise AssertionError("multivalue ref check must not probe")

    monkeypatch.setattr(lock, "_no_url_rewrites", no_probe)
    work, _ = _make_repo(tmp_path, "work", NOMINAL, [""])
    present, detail = lock.check_canonical_ref(BRANCH, str(work))
    assert not present
    assert "REMOTE_REF_UNKNOWN" in detail
    assert "ambiguous" in detail


def test_ref_check_refuses_missing_origin_without_probe(tmp_path, hermetic_git_env, monkeypatch):
    monkeypatch.setattr(
        lock, "_no_url_rewrites", lambda *a: (_ for _ in ()).throw(AssertionError("probe"))
    )
    work, _ = _make_repo(tmp_path, "work", None, [])
    present, detail = lock.check_canonical_ref(BRANCH, str(work))
    assert not present
    assert "REMOTE_REF_UNKNOWN" in detail


@pytest.mark.parametrize("extras", [[""], ["   "], [NOMINAL], [MARKER_URL]])
def test_multivalue_main_no_probe_fails_closed(tmp_path, hermetic_git_env, capsys, extras):
    work, head = _make_repo(tmp_path, "work", NOMINAL, extras)
    rc = lock.main(
        [
            "--repo",
            SLUG,
            "--branch",
            BRANCH,
            "--audit-base-sha",
            head,
            "--workdir",
            str(work),
        ]
    )
    out_err = capsys.readouterr()
    assert rc == 1
    assert "LOCK_OK" not in out_err.out
    assert "leak-marker-ws240" not in out_err.err
    assert "ambiguous" in out_err.err or "cannot read origin" in out_err.err


@pytest.mark.parametrize("origin", [NOMINAL, SSH_NOMINAL])
def test_single_canonical_positives_preserved(tmp_path, hermetic_git_env, capsys, origin):
    """Supported HTTPS and SSH identities still PASS end to end."""
    work, head = _make_repo(tmp_path, "work", origin, [])
    assert lock.verify(SLUG, BRANCH, head, str(work)) == []
    rc = lock.main(
        [
            "--repo",
            SLUG,
            "--branch",
            BRANCH,
            "--audit-base-sha",
            head,
            "--workdir",
            str(work),
        ]
    )
    out_err = capsys.readouterr()
    assert rc == 0
    assert "LOCK_OK" in out_err.out


def test_p1_rewrite_guard_retained_after_repair(tmp_path, hermetic_git_env):
    """WS239 P1: single canonical URL under an active rewrite still fails closed."""
    work, head = _make_repo(tmp_path, "work", NOMINAL, [])
    _git(["config", "url.https://example.invalid/.insteadOf", NOMINAL], work)
    reasons = lock.verify(SLUG, BRANCH, head, str(work))
    assert any("EFFECTIVE_URL_REWRITE" in r for r in reasons), reasons


def _bootstrap_state(work, head, tmp_path):
    (work / "AGENTS.md").write_text("# canonical policy\n", encoding="utf-8")
    state = {
        "schema_version": "2.0",
        "repository": SLUG,
        "worktree": str(work),
        "branch": BRANCH,
        "audit_base_sha": head,
        "audit_base_tree": "0" * 40,
        "state_written_against_head": head,
        "validated_head": None,
        "objective": "WS240 P2 bootstrap negative control",
        "in_scope": [],
        "out_of_scope": [],
        "ownership": "WS240-TEST",
        "status": "ACTIVE",
        "exact_next_action": "fail closed",
    }
    state_path = tmp_path / "state.yaml"
    state_path.write_text(yaml.safe_dump(state), encoding="utf-8")
    return state_path


def test_bootstrap_source_lock_gate_rejects_multivalue(tmp_path, hermetic_git_env):
    """End-to-end P2: bootstrap() step 1 fails closed on multivalue identity."""
    work, head = _make_repo(tmp_path, "work", NOMINAL, [""])
    state_path = _bootstrap_state(work, head, tmp_path)
    root = Path(__file__).resolve().parent.parent.parent
    result = bootstrap_mod.bootstrap(
        str(work),
        "WS240-TEST",
        BRANCH,
        head,
        str(state_path),
        "cpl",
        str(root / ".foundry" / "repo-profiles"),
        "",
        False,
        False,
        None,
        {os.path.realpath(str(work)): str(state_path)},
    )
    assert result["verdict"] == "BOOTSTRAP_FAIL", result
    assert any(
        f.startswith("source lock") and ("ambiguous" in f or "cannot read origin" in f)
        for f in result["failures"]
    ), result["failures"]


def test_bootstrap_control_passes_single_canonical(tmp_path, hermetic_git_env):
    work, head = _make_repo(tmp_path, "work", NOMINAL, [])
    state_path = _bootstrap_state(work, head, tmp_path)
    root = Path(__file__).resolve().parent.parent.parent
    result = bootstrap_mod.bootstrap(
        str(work),
        "WS240-TEST",
        BRANCH,
        head,
        str(state_path),
        "cpl",
        str(root / ".foundry" / "repo-profiles"),
        "",
        False,
        False,
        None,
        {os.path.realpath(str(work)): str(state_path)},
    )
    assert not any(f.startswith("source lock") for f in result["failures"]), result
