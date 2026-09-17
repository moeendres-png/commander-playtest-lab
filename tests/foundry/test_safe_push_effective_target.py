"""WS241: effective push-target identity for tools/foundry/safe_push.py.

Fail-before (OLD gate 3: ``git config --get remote.<r>.url`` + substring
``expected_slug in url``), DIRECTLY_VERIFIED with hermetic local fixtures:
canonical fetch + divergent ``remote.origin.pushurl`` -> DRY_RUN_OK;
``url.*.pushInsteadOf`` rewrite -> DRY_RUN_OK; reversed multivalue origin
(evil first, canonical last; ``--get`` returns the last record) ->
DRY_RUN_OK; lookalike path containing the slug as a substring -> DRY_RUN_OK;
raw ``ls-remote``/``push`` stderr (URLs, hosts) echoed into PUSH_REJECT.

Fix-after (WS241-C): exact owner/repo identity on the single fetch URL
record; NO pushurl record of any kind (single, blank, multivalue,
environment-injected); NO mirror/receivepack records; no
insteadOf/pushInsteadOf in any scope; the single Git-expanded effective
push URL must be byte-equal to the validated fetch record; pre-write
re-check; no URL/credential/command-output echoes.

Closure fix (production-slug local paths + tag widening), DIRECTLY_VERIFIED
with hermetic local fixtures: ``file://`` / plain-path remotes are rejected
by default even when the path ends at a ``/`` boundary with the expected
slug (slug-suffixed attacker path + production slug -> PUSH_REJECT at the
fetch-identity gate, dry AND actual, no write); hermetic fixtures keep
working only through the explicit fixture-only
``--allow-local-path-target`` flag; ``push.followTags=true`` no longer
widens the authorized push (``--no-follow-tags`` on the single refspec;
PUSHED with zero remote tags).

No network. Real local git repos (file:// bare remotes A/B); pushes that
must not happen are verified absent. The lock path runs safe_push as a
genuine child of a lock-holding parent.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
TOOL = ROOT / "tools" / "foundry" / "safe_push.py"
TOOLS_DIR = ROOT / "tools"

sys.path.insert(0, str(TOOLS_DIR))

from foundry import safe_push as safe_push_mod  # noqa: E402

SLUG = "test-host/fixture-repo"
FORGE_SLUG = "moeendres-png/forge"
PROD_SLUG = "moeendres-png/commander-playtest-lab"
MARKER = "leak-marker-ws241.invalid"
SECRET = "s3cret-ws241"


@pytest.fixture()
def hermetic_env(tmp_path, monkeypatch):
    """Isolate HOME/global/system config and scrub environment config overrides."""
    home = tmp_path / "home"
    home.mkdir()
    empty_global = home / "empty-global"
    empty_global.write_text("", encoding="utf-8")
    empty_system = home / "empty-system"
    empty_system.write_text("", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty_global))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(empty_system))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.delenv("GIT_CONFIG_COUNT", raising=False)
    for index in range(10):
        monkeypatch.delenv(f"GIT_CONFIG_KEY_{index}", raising=False)
        monkeypatch.delenv(f"GIT_CONFIG_VALUE_{index}", raising=False)
    monkeypatch.setenv("GIT_AUTHOR_NAME", "T")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "t@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "T")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "t@example.com")
    monkeypatch.setenv("GIT_TERMINAL_PROMPT", "0")
    return {"home": home}


def _git(args: list[str], cwd: Path, env: dict | None = None) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False, env=env
    )
    assert proc.returncode == 0, f"git {args}: {proc.stderr}"
    return proc.stdout.strip()


def _raw_env() -> dict:
    return dict(os.environ)


def _make_bare(parent: Path, *parts: str) -> Path:
    remote = parent.joinpath(*parts)
    remote.parent.mkdir(parents=True, exist_ok=True)
    _git(["init", "--bare", "-b", "main", str(remote)], parent, _raw_env())
    return remote


def _seed(remote: Path, work_parent: Path, name: str = "seed") -> tuple[Path, str]:
    seed = work_parent / name
    _git(["clone", str(remote), str(seed)], work_parent, _raw_env())
    (seed / "f.txt").write_text("v1\n", encoding="utf-8")
    _git(["add", "."], seed, _raw_env())
    _git(["commit", "-m", "init"], seed, _raw_env())
    _git(["push", "origin", "HEAD:refs/heads/main"], seed, _raw_env())
    return seed, _git(["rev-parse", "HEAD"], seed, _raw_env())


def _worktree(
    tmp_path: Path,
    origin_url: str,
    branch: str = "test/ws",
    slug: str = SLUG,
    owner: str = "TEST-WORKSTREAM",
    locks: Path | None = None,
) -> dict:
    wt = tmp_path / "wt"
    _git(["clone", origin_url, str(wt)], tmp_path, _raw_env())
    _git(["checkout", "-b", branch], wt, _raw_env())
    (wt / "work.txt").write_text("work\n", encoding="utf-8")
    _git(["add", "."], wt, _raw_env())
    _git(["commit", "-m", "work"], wt, _raw_env())
    base = _git(["rev-parse", "origin/main"], wt, _raw_env())
    head = _git(["rev-parse", "HEAD"], wt, _raw_env())
    lock_dir = locks or (tmp_path / "locks")
    lock_dir.mkdir(exist_ok=True)
    state = {
        "schema_version": "2.0",
        "repository": slug,
        "worktree": str(wt),
        "branch": branch,
        "audit_base_sha": base,
        "audit_base_tree": "0" * 40,
        "state_written_against_head": head,
        "validated_head": head,
        "objective": "x",
        "in_scope": [],
        "out_of_scope": [],
        "ownership": owner,
        "status": "ACTIVE",
        "exact_next_action": "push",
    }
    state_path = wt / "STATE.yaml"
    state_path.write_text(yaml.safe_dump(state), encoding="utf-8")
    _git(["add", "."], wt, _raw_env())
    _git(["commit", "-m", "checkpoint state"], wt, _raw_env())
    return {
        "wt": wt,
        "locks": lock_dir,
        "state": state_path,
        "env": _raw_env(),
        "branch": branch,
        "owner": owner,
        "slug": slug,
    }


@pytest.fixture()
def rig(tmp_path: Path, hermetic_env) -> dict:
    """Canonical bare remote A whose path ends exactly with the trust slug."""
    remote_a = _make_bare(tmp_path, "test-host", "fixture-repo.git")
    evil_b = _make_bare(tmp_path, "evil", "b.git")
    _seed(remote_a, tmp_path)
    out = _worktree(tmp_path, str(remote_a))
    out["remote_a"] = remote_a
    out["evil_b"] = evil_b
    return out


def _run_push(
    rig: dict, *extra: str, dry: bool = False, via_holder: bool = True, local_path: bool = True
) -> subprocess.CompletedProcess:
    cmd = [
        sys.executable,
        str(TOOL),
        "--worktree",
        str(rig["wt"]),
        "--expected-branch",
        rig["branch"],
        "--state",
        str(rig["state"]),
        "--expected-slug",
        rig["slug"],
        *extra,
    ]
    if local_path:
        # Hermetic fixtures use local-path remotes; production invocations
        # omit the fixture-only flag (safe default rejects local targets).
        cmd.append("--allow-local-path-target")
    if dry:
        cmd.append("--dry-run")
    env = dict(rig["env"])
    env["FOUNDRY_LOCK_DIR"] = str(rig["locks"])
    env["PYTHONPATH"] = str(TOOLS_DIR)
    if not via_holder:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env)
    driver = (
        "import subprocess, sys; "
        "from foundry import writer_lock; "
        f"lock = writer_lock.WriterLock(sys.argv[1], {rig['owner']!r}, "
        f"{rig['branch']!r}, 'ses-t'); "
        "lock.acquire(); "
        "p = subprocess.run(sys.argv[2:], capture_output=True, text=True); "
        "sys.stdout.write(p.stdout); sys.stderr.write(p.stderr); "
        "lock.release(); "
        "sys.exit(p.returncode)"
    )
    return subprocess.run(
        [sys.executable, "-c", driver, str(rig["wt"]), *cmd],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )


def _remote_has(remote: Path, wt: Path, ref: str) -> bool:
    out = _git(["ls-remote", str(remote), ref], wt, _raw_env())
    return bool(out)


# ---------------------------------------------------------------------------
# Positive controls: exact identity keeps working.
# ---------------------------------------------------------------------------


def test_exact_identity_dry_run_then_actual(rig: dict) -> None:
    assert not _remote_has(rig["remote_a"], rig["wt"], "refs/heads/test/ws")
    dry = _run_push(rig, dry=True)
    assert dry.returncode == 0, dry.stderr
    assert "DRY_RUN_OK" in dry.stdout
    assert not _remote_has(rig["remote_a"], rig["wt"], "refs/heads/test/ws")
    push = _run_push(rig)
    assert push.returncode == 0, push.stderr
    assert "PUSHED" in push.stdout
    assert _remote_has(rig["remote_a"], rig["wt"], "refs/heads/test/ws")
    assert not _remote_has(rig["evil_b"], rig["wt"], "refs/heads/test/ws")
    again = _run_push(rig)
    assert again.returncode == 0 and "UP_TO_DATE" in again.stdout


def test_explicit_canonical_pushurl_rejected(rig: dict) -> None:
    """WS241-C correction 1: even a canonical pushurl is never accepted."""
    _git(["config", "remote.origin.pushurl", str(rig["remote_a"])], rig["wt"], _raw_env())
    for dry in (True, False):
        proc = _run_push(rig, dry=dry)
        assert proc.returncode == 2, dry
        assert "pushurl" in proc.stderr, proc.stderr
    assert not _remote_has(rig["remote_a"], rig["wt"], "refs/heads/test/ws")
    assert not _remote_has(rig["evil_b"], rig["wt"], "refs/heads/test/ws")


def test_canonical_pushurl_file_scheme_variant_rejected(rig: dict) -> None:
    _git(
        ["config", "remote.origin.pushurl", rig["remote_a"].as_uri()],
        rig["wt"],
        _raw_env(),
    )
    proc = _run_push(rig, dry=True)
    assert proc.returncode == 2
    assert "pushurl" in proc.stderr


def test_blank_pushurl_rejected(rig: dict) -> None:
    _git(["config", "remote.origin.pushurl", ""], rig["wt"], _raw_env())
    proc = _run_push(rig, dry=True)
    assert proc.returncode == 2
    assert "pushurl" in proc.stderr


def test_env_injected_pushurl_rejected(rig: dict, monkeypatch) -> None:
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "remote.origin.pushurl")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", str(rig["evil_b"]))
    rig["env"] = _raw_env()
    proc = _run_push(rig, dry=True)
    assert proc.returncode == 2
    assert "pushurl" in proc.stderr
    assert not _remote_has(rig["evil_b"], rig["wt"], "refs/heads/test/ws")


def test_forge_slug_positive(tmp_path: Path, hermetic_env) -> None:
    remote = _make_bare(tmp_path, "moeendres-png", "forge.git")
    _seed(remote, tmp_path)
    forge_rig = _worktree(tmp_path, str(remote), slug=FORGE_SLUG, owner="FORGE-TEST")
    proc = _run_push(forge_rig, dry=True)
    assert proc.returncode == 0, proc.stderr
    assert "DRY_RUN_OK" in proc.stdout
    push = _run_push(forge_rig)
    assert push.returncode == 0, push.stderr
    assert "PUSHED" in push.stdout


@pytest.mark.parametrize(
    ("url", "slug", "want"),
    [
        (f"https://github.com/{SLUG}.git", SLUG, True),
        (f"https://github.com/{SLUG}", SLUG, True),
        (f"git@github.com:{SLUG}.git", SLUG, True),
        (f"ssh://git@github.com/{SLUG}.git", SLUG, True),
        # Lookalikes: substring, suffix, query, fragment, credentials, ports.
        (f"https://github.com/{SLUG}-evil.git", SLUG, False),
        (f"https://github.com/evil-{SLUG}.git", SLUG, False),
        (f"https://github.com/{SLUG}.git?x=1", SLUG, False),
        (f"https://github.com/{SLUG}.git#frag", SLUG, False),
        (f"https://user:{SECRET}@github.com/{SLUG}.git", SLUG, False),
        (f"https://github.com:8443/{SLUG}.git", SLUG, False),
        (f"https://example.com/{SLUG}.git", SLUG, False),
        ("", SLUG, False),
        (f"https://github.com/{SLUG}.git", "someone-else/other-repo", False),
        ("not a url at all", SLUG, False),
    ],
)
def test_expected_target_identity_units(url: str, slug: str, want: bool) -> None:
    assert safe_push_mod._is_expected_target(url, slug) is want


def test_expected_target_file_identity_units(tmp_path: Path) -> None:
    allow = {"allow_local_path_target": True}
    canon = str(tmp_path / "test-host" / "fixture-repo.git")
    # Fixture-only flag preserves the hermetic local-path semantics.
    assert safe_push_mod._is_expected_target(canon, SLUG, **allow) is True
    assert safe_push_mod._is_expected_target("file://" + canon, SLUG, **allow) is True
    assert safe_push_mod._is_expected_target(canon.removesuffix(".git"), SLUG, **allow) is True
    evil = str(tmp_path / "test-host" / "fixture-repo-evil.git")
    assert safe_push_mod._is_expected_target(evil, SLUG, **allow) is False
    assert safe_push_mod._is_expected_target("file://" + evil, SLUG, **allow) is False
    nested = str(tmp_path / "test-host" / "fixture-repo" / "remote.git")
    assert safe_push_mod._is_expected_target(nested, SLUG, **allow) is False
    assert safe_push_mod._is_expected_target("", SLUG, **allow) is False
    assert safe_push_mod._is_expected_target(canon, "bad slug!!", **allow) is False
    # Safe default: every local path is rejected without the fixture flag,
    # even a slug-exact one (production slugs can never match locally).
    assert safe_push_mod._is_expected_target(canon, SLUG) is False
    assert safe_push_mod._is_expected_target("file://" + canon, SLUG) is False
    prod = str(tmp_path / "moeendres-png" / "commander-playtest-lab.git")
    assert safe_push_mod._is_expected_target(prod, PROD_SLUG) is False
    assert safe_push_mod._is_expected_target("file://" + prod, PROD_SLUG) is False
    assert (
        safe_push_mod._is_expected_target("file://localhost/" + prod.lstrip("/"), PROD_SLUG)
        is False
    )


# ---------------------------------------------------------------------------
# Negative controls: every divergent effective push target fails closed.
# ---------------------------------------------------------------------------


def test_divergent_pushurl_rejected_dry_and_actual(rig: dict) -> None:
    _git(["config", "remote.origin.pushurl", str(rig["evil_b"])], rig["wt"], _raw_env())
    dry = _run_push(rig, dry=True)
    assert dry.returncode == 2
    assert "WRONG_REMOTE" in dry.stderr or "pushurl" in dry.stderr
    push = _run_push(rig)
    assert push.returncode == 2
    assert "WRONG_REMOTE" in push.stderr or "pushurl" in push.stderr
    assert not _remote_has(rig["evil_b"], rig["wt"], "refs/heads/test/ws")
    assert not _remote_has(rig["remote_a"], rig["wt"], "refs/heads/test/ws")


def test_pushinsteadof_rewrite_rejected(rig: dict) -> None:
    fetch = _git(["config", "--get", "remote.origin.url"], rig["wt"], _raw_env())
    _git(["config", f"url.{rig['evil_b']}.pushInsteadOf", fetch], rig["wt"], _raw_env())
    for dry in (True, False):
        proc = _run_push(rig, dry=dry)
        assert proc.returncode == 2, dry
        assert "EFFECTIVE_URL_REWRITE" in proc.stderr, proc.stderr
    assert not _remote_has(rig["evil_b"], rig["wt"], "refs/heads/test/ws")


def test_insteadof_rewrite_rejected(rig: dict) -> None:
    fetch = _git(["config", "--get", "remote.origin.url"], rig["wt"], _raw_env())
    _git(["config", f"url.{rig['evil_b']}.insteadOf", fetch], rig["wt"], _raw_env())
    proc = _run_push(rig, dry=True)
    assert proc.returncode == 2
    assert "EFFECTIVE_URL_REWRITE" in proc.stderr
    assert not _remote_has(rig["evil_b"], rig["wt"], "refs/heads/test/ws")


def test_env_scoped_rewrite_rejected(rig: dict, monkeypatch) -> None:
    fetch = _git(["config", "--get", "remote.origin.url"], rig["wt"], _raw_env())
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", f"url.{rig['evil_b']}.insteadOf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", fetch)
    rig["env"] = _raw_env()
    proc = _run_push(rig, dry=True)
    assert proc.returncode == 2
    assert "EFFECTIVE_URL_REWRITE" in proc.stderr


def test_global_scoped_rewrite_rejected(rig: dict, hermetic_env, tmp_path: Path) -> None:
    fetch = _git(["config", "--get", "remote.origin.url"], rig["wt"], _raw_env())
    hermetic_env["home"].joinpath("empty-global").write_text(
        f'[url "{rig["evil_b"]}"]\n\tinsteadOf = {fetch}\n', encoding="utf-8"
    )
    proc = _run_push(rig, dry=True)
    assert proc.returncode == 2
    assert "EFFECTIVE_URL_REWRITE" in proc.stderr


def test_multivalue_origin_rejected_both_orders(rig: dict) -> None:
    canon = _git(["config", "--get", "remote.origin.url"], rig["wt"], _raw_env())
    evil = str(rig["evil_b"])
    # Canonical first, evil second (``--get`` surfaces the second record).
    _git(["config", "--add", "remote.origin.url", evil], rig["wt"], _raw_env())
    proc = _run_push(rig, dry=True)
    assert proc.returncode == 2
    assert "ambiguous remote identity" in proc.stderr
    # Reversed: evil first, canonical last — the order the OLD substring
    # gate passed (``--get`` returns the canonical last record).
    _git(["config", "--unset-all", "remote.origin.url"], rig["wt"], _raw_env())
    _git(["config", "--add", "remote.origin.url", evil], rig["wt"], _raw_env())
    _git(["config", "--add", "remote.origin.url", canon], rig["wt"], _raw_env())
    proc2 = _run_push(rig, dry=True)
    assert proc2.returncode == 2
    assert "ambiguous remote identity" in proc2.stderr
    assert not _remote_has(rig["evil_b"], rig["wt"], "refs/heads/test/ws")
    assert not _remote_has(rig["remote_a"], rig["wt"], "refs/heads/test/ws")


def test_blank_second_url_record_rejected(rig: dict) -> None:
    _git(["config", "--add", "remote.origin.url", ""], rig["wt"], _raw_env())
    proc = _run_push(rig, dry=True)
    assert proc.returncode == 2
    assert "ambiguous remote identity" in proc.stderr


def test_multiple_pushurls_rejected(rig: dict) -> None:
    _git(["config", "remote.origin.pushurl", str(rig["remote_a"])], rig["wt"], _raw_env())
    _git(
        ["config", "--add", "remote.origin.pushurl", str(rig["evil_b"])],
        rig["wt"],
        _raw_env(),
    )
    proc = _run_push(rig, dry=True)
    assert proc.returncode == 2
    assert "pushurl" in proc.stderr
    assert not _remote_has(rig["evil_b"], rig["wt"], "refs/heads/test/ws")


def test_lookalike_fetch_slug_rejected(tmp_path: Path, hermetic_env) -> None:
    evil = _make_bare(tmp_path, "test-host", "fixture-repo-evil.git")
    _seed(evil, tmp_path)
    look_rig = _worktree(tmp_path, str(evil))
    proc = _run_push(look_rig, dry=True)
    assert proc.returncode == 2
    assert "WRONG_REMOTE" in proc.stderr
    assert "fetch identity" in proc.stderr
    push = _run_push(look_rig)
    assert push.returncode == 2
    assert _git(["ls-remote", str(evil), "refs/heads/test/ws"], tmp_path, _raw_env()) == ""


# ---------------------------------------------------------------------------
# Closure: production-slug local targets rejected by default (G1 defect).
# ---------------------------------------------------------------------------


def _prod_slug_rig(tmp_path: Path, url_form: str = "plain") -> tuple[dict, Path]:
    """Attacker-style rig: local bare path ending with the production slug."""
    atk = _make_bare(tmp_path, "atk", "moeendres-png", "commander-playtest-lab.git")
    _seed(atk, tmp_path)
    atk_rig = _worktree(tmp_path, str(atk), slug=PROD_SLUG)
    if url_form == "file":
        _git(["remote", "set-url", "origin", atk.as_uri()], atk_rig["wt"], _raw_env())
    return atk_rig, atk


def test_production_slug_plain_attacker_path_rejected(tmp_path: Path, hermetic_env) -> None:
    """G1: slug-suffixed local path must not satisfy the production slug."""
    atk_rig, atk = _prod_slug_rig(tmp_path)
    for dry in (True, False):
        proc = _run_push(atk_rig, dry=dry, local_path=False)
        assert proc.returncode == 2, dry
        assert "WRONG_REMOTE" in proc.stderr, proc.stderr
        assert "fetch identity" in proc.stderr, proc.stderr
    assert _git(["ls-remote", str(atk), "refs/heads/test/ws"], tmp_path, _raw_env()) == ""


def test_production_slug_file_attacker_path_rejected(tmp_path: Path, hermetic_env) -> None:
    atk_rig, atk = _prod_slug_rig(tmp_path, url_form="file")
    for dry in (True, False):
        proc = _run_push(atk_rig, dry=dry, local_path=False)
        assert proc.returncode == 2, dry
        assert "WRONG_REMOTE" in proc.stderr, proc.stderr
    assert _git(["ls-remote", str(atk), "refs/heads/test/ws"], tmp_path, _raw_env()) == ""


def test_fixture_local_path_rejected_without_flag(rig: dict) -> None:
    """Safe default: even legitimate fixture paths need the explicit flag."""
    proc = _run_push(rig, dry=True, local_path=False)
    assert proc.returncode == 2
    assert "WRONG_REMOTE" in proc.stderr
    assert not _remote_has(rig["remote_a"], rig["wt"], "refs/heads/test/ws")


def test_followtags_config_does_not_push_tags(rig: dict) -> None:
    """Local push.followTags must not widen the single-refspec write."""
    _git(["tag", "-a", "v9.9", "-m", "annotated tag on pushed history"], rig["wt"], _raw_env())
    _git(["config", "push.followTags", "true"], rig["wt"], _raw_env())
    push = _run_push(rig)
    assert push.returncode == 0, push.stderr
    assert "PUSHED" in push.stdout
    assert _remote_has(rig["remote_a"], rig["wt"], "refs/heads/test/ws")
    assert _git(["ls-remote", str(rig["remote_a"]), "refs/tags/*"], rig["wt"], _raw_env()) == ""


def test_noncanonical_https_slug_rejected_before_network(rig: dict) -> None:
    _git(
        ["remote", "set-url", "origin", "https://github.com/someone-else/other-repo.git"],
        rig["wt"],
        _raw_env(),
    )
    proc = _run_push(rig, dry=True)
    assert proc.returncode == 2
    assert "WRONG_REMOTE" in proc.stderr


def test_missing_origin_rejected(rig: dict) -> None:
    _git(["remote", "remove", "origin"], rig["wt"], _raw_env())
    proc = _run_push(rig, dry=True)
    assert proc.returncode == 2
    assert "PUSH_REJECT" in proc.stderr


def test_invalid_remote_name_rejected_unit(tmp_path: Path, hermetic_env) -> None:
    assert safe_push_mod._verify_push_target(str(tmp_path), "origin;evil", SLUG) is not None


def test_config_records_allowlist_and_unset(tmp_path: Path, hermetic_env) -> None:
    work = tmp_path / "work"
    work.mkdir()
    _git(["init", "-b", "main"], work, _raw_env())
    assert safe_push_mod._config_records(str(work), "remote.origin.pushurl") == []
    assert safe_push_mod._config_records(str(work), "remote.origin.mirror") == []
    assert safe_push_mod._config_records(str(work), "remote.origin.receivepack") == []
    with pytest.raises(RuntimeError):
        safe_push_mod._config_records(str(work), "core.pager")


# ---------------------------------------------------------------------------
# WS241-C correction 3: mirror / receivepack broadening guards.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["true", "false", ""])
def test_mirror_records_rejected(rig: dict, value: str) -> None:
    _git(["config", "remote.origin.mirror", value], rig["wt"], _raw_env())
    for dry in (True, False):
        proc = _run_push(rig, dry=dry)
        assert proc.returncode == 2, (value, dry)
        assert "mirror" in proc.stderr, proc.stderr
    assert not _remote_has(rig["remote_a"], rig["wt"], "refs/heads/test/ws")


def test_multivalue_mirror_rejected(rig: dict) -> None:
    _git(["config", "remote.origin.mirror", "false"], rig["wt"], _raw_env())
    _git(["config", "--add", "remote.origin.mirror", "true"], rig["wt"], _raw_env())
    proc = _run_push(rig, dry=True)
    assert proc.returncode == 2
    assert "mirror" in proc.stderr


def test_env_injected_mirror_rejected(rig: dict, monkeypatch) -> None:
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "remote.origin.mirror")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "true")
    rig["env"] = _raw_env()
    proc = _run_push(rig, dry=True)
    assert proc.returncode == 2
    assert "mirror" in proc.stderr


@pytest.mark.parametrize("value", ["git-receive-pack", "", "true"])
def test_receivepack_records_rejected(rig: dict, value: str) -> None:
    _git(["config", "remote.origin.receivepack", value], rig["wt"], _raw_env())
    for dry in (True, False):
        proc = _run_push(rig, dry=dry)
        assert proc.returncode == 2, (value, dry)
        assert "receivepack" in proc.stderr, proc.stderr
    assert not _remote_has(rig["remote_a"], rig["wt"], "refs/heads/test/ws")


def test_multivalue_receivepack_rejected(rig: dict) -> None:
    _git(["config", "remote.origin.receivepack", "git-receive-pack"], rig["wt"], _raw_env())
    _git(["config", "--add", "remote.origin.receivepack", "other"], rig["wt"], _raw_env())
    proc = _run_push(rig, dry=True)
    assert proc.returncode == 2
    assert "receivepack" in proc.stderr


def test_mirror_and_receivepack_absent_by_default(rig: dict) -> None:
    assert safe_push_mod._config_records(str(rig["wt"]), "remote.origin.mirror") == []
    assert safe_push_mod._config_records(str(rig["wt"]), "remote.origin.receivepack") == []
    assert safe_push_mod._config_records(str(rig["wt"]), "remote.origin.pushurl") == []


# ---------------------------------------------------------------------------
# WS241-C corrections 2 + 4: fetch==push equality; fail-closed rewrite guard.
# ---------------------------------------------------------------------------


def test_push_matches_fetch_unit() -> None:
    assert safe_push_mod._push_matches_fetch("a", "a") is True
    assert safe_push_mod._push_matches_fetch("a", "b") is False
    assert safe_push_mod._push_matches_fetch("", "") is False
    assert safe_push_mod._push_matches_fetch("a", "") is False
    assert safe_push_mod._push_matches_fetch("a", "a ") is False


def test_effective_push_equals_validated_fetch_e2e(rig: dict) -> None:
    """Green path proves the equality gate admits the unredirected target."""
    fetch = _git(["config", "--get", "remote.origin.url"], rig["wt"], _raw_env())
    proc = _git(["remote", "get-url", "--push", "--all", "origin"], rig["wt"], _raw_env())
    assert proc == fetch
    dry = _run_push(rig, dry=True)
    assert dry.returncode == 0, dry.stderr


def test_rewrite_guard_fails_closed_on_subprocess_error(monkeypatch, tmp_path: Path) -> None:
    def boom(*args, **kwargs):
        raise OSError("injected transport failure")

    monkeypatch.setattr(safe_push_mod.subprocess, "run", boom)
    assert safe_push_mod._no_push_rewrites(str(tmp_path), {}) is False


def test_rewrite_guard_fails_closed_on_timeout(monkeypatch, tmp_path: Path) -> None:
    import subprocess as sp

    def slow(*args, **kwargs):
        raise sp.TimeoutExpired(cmd=args[0] if args else "git", timeout=30)

    monkeypatch.setattr(safe_push_mod.subprocess, "run", slow)
    assert safe_push_mod._no_push_rewrites(str(tmp_path), {}) is False


# ---------------------------------------------------------------------------
# Mutation between dry-run and actual; failure-output redaction.
# ---------------------------------------------------------------------------


def test_mutation_between_dry_run_and_actual_rejected(rig: dict) -> None:
    dry = _run_push(rig, dry=True)
    assert dry.returncode == 0, dry.stderr
    assert "DRY_RUN_OK" in dry.stdout
    # Adversary redirects the push target after the successful dry-run.
    _git(["config", "remote.origin.pushurl", str(rig["evil_b"])], rig["wt"], _raw_env())
    push = _run_push(rig)
    assert push.returncode == 2
    assert "pushurl" in push.stderr
    assert not _remote_has(rig["evil_b"], rig["wt"], "refs/heads/test/ws")
    assert not _remote_has(rig["remote_a"], rig["wt"], "refs/heads/test/ws")


def test_credential_pushurl_never_echoed(rig: dict) -> None:
    evil = f"https://user:{SECRET}@{MARKER}/{SLUG}.git"
    _git(["config", "remote.origin.pushurl", evil], rig["wt"], _raw_env())
    proc = _run_push(rig, dry=True)
    assert proc.returncode == 2
    combined = proc.stdout + proc.stderr
    assert MARKER not in combined
    assert SECRET not in combined
    assert "user" not in combined.replace("PUSH_REJECT", "")


def test_lsremote_failure_withholds_output(rig: dict) -> None:
    missing = rig["wt"].parent / MARKER / "test-host" / "fixture-repo.git"
    _git(["remote", "set-url", "origin", str(missing)], rig["wt"], _raw_env())
    # The slug-anchored (but nonexistent) remote passes exact identity, so
    # gate 10 ls-remote fails locally (no network). The raw path carrying
    # the marker must not surface in diagnostics.
    proc = _run_push(rig, dry=True)
    assert proc.returncode == 2
    assert MARKER not in (proc.stdout + proc.stderr)
    assert "remote output withheld" in proc.stderr


def test_push_failure_withholds_remote_output(rig: dict, monkeypatch, capsys) -> None:
    """A failing push must not echo remote output (URLs/credentials).

    Drives the real in-process gate chain (lock gate stubbed; every other
    gate genuinely passes against the hermetic fixture) with only the
    ``git push`` exec faked to fail carrying marker/secret stderr.
    """
    import subprocess as sp

    real_run = sp.run

    def fake_run(args, **kwargs):
        if isinstance(args, list) and args[:2] == ["git", "push"]:
            return sp.CompletedProcess(args, 128, "", f"fatal: {MARKER} token {SECRET}\n")
        return real_run(args, **kwargs)

    monkeypatch.setattr(sp, "run", fake_run)
    monkeypatch.setattr(safe_push_mod, "_lock_held_by_ancestor", lambda *a: None)
    rc = safe_push_mod.safe_push(
        str(rig["wt"]),
        "test/ws",
        str(rig["state"]),
        "origin",
        SLUG,
        dry_run=False,
        allow_local_path_target=True,  # hermetic fixture remote; exercises the push-failure path
    )
    out_err = capsys.readouterr()
    assert rc == 2
    assert MARKER not in (out_err.out + out_err.err)
    assert SECRET not in (out_err.out + out_err.err)
    assert "PUSH_REJECT" in out_err.err
    assert "remote output withheld" in out_err.err
    assert not _remote_has(rig["remote_a"], rig["wt"], "refs/heads/test/ws")


def test_metrics_reject_reason_carries_no_secrets(rig: dict, tmp_path: Path) -> None:
    metrics = tmp_path / "metrics.jsonl"
    evil = f"https://user:{SECRET}@{MARKER}/{SLUG}.git"
    _git(["config", "remote.origin.pushurl", evil], rig["wt"], _raw_env())
    proc = _run_push(rig, "--metrics", str(metrics), dry=True)
    assert proc.returncode == 2
    content = metrics.read_text(encoding="utf-8")
    assert MARKER not in content
    assert SECRET not in content


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
