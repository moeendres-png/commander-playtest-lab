"""Repository identity and real Git rewrite regressions; no live network."""

import subprocess

import pytest
from test_remote_ref_freshness import lock

SLUG = lock.CANONICAL_SLUG


def test_explicit_empty_ref_must_not_skip_required_probe(monkeypatch, capsys):
    monkeypatch.setattr(lock, "verify", lambda *a: [])
    monkeypatch.setattr(lock, "remote_identity", lambda *a: f"https://github.com/{SLUG}")
    monkeypatch.setattr(lock, "_git", lambda *a: "a" * 40)
    assert (
        lock.main(
            [
                "--repo",
                SLUG,
                "--branch",
                "main",
                "--audit-base-sha",
                "a" * 40,
                "--check-remote-ref",
                "",
            ]
        )
        == 1
    )
    assert "LOCK_OK" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "url",
    [
        f"https://github.com/{SLUG}",
        f"https://github.com/{SLUG}.git",
        f"git@github.com:{SLUG}.git",
        f"ssh://git@github.com/{SLUG}.git",
        f"https://github.com:443/{SLUG}.git/",
        f"ssh://git@github.com:22/{SLUG}.git",
    ],
)
def test_equivalent_identities(url):
    assert lock.is_canonical_remote(url)


@pytest.mark.parametrize(
    "url",
    [
        f"https://github.com/{SLUG}-other.git",
        f"https://github.com/prefix-{SLUG}.git",
        "https://github.com/other/commander-playtest-lab.git",
        f"https://evil.invalid/{SLUG}.git",
        f"https://github.com.evil.invalid/{SLUG}",
        f"https://github.com/../{SLUG}",
        f"https://github.com/./{SLUG}",
        f"https://github.com/{SLUG}/..",
        f"https://github.com/{SLUG}?extra=1",
        f"https://github.com/{SLUG}#fragment",
        f"https://secret@github.com/{SLUG}",
        f"https://github.com:8443/{SLUG}",
        f"https://github.com/{SLUG}\n",
        f"/tmp/{SLUG}",
        f"https://github.com/{SLUG}/extra",
    ],
)
def test_lookalike_identities_rejected(url):
    assert not lock.is_canonical_remote(url)


@pytest.mark.parametrize("source", ["local", "environment"])
def test_rewrite_to_wrong_repo_cannot_pass(tmp_path, monkeypatch, source):
    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=tmp_path, check=True, capture_output=True, text=True
        ).stdout.strip()

    git("init", "-b", "topic")
    git(
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "--allow-empty",
        "-m",
        "fixture",
    )
    head = git("rev-parse", "HEAD")
    nominal = f"https://github.com/{SLUG}.git"
    git("remote", "add", "origin", nominal)
    if source == "local":
        git("config", "url." + tmp_path.as_uri() + ".insteadOf", nominal)
    else:
        monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
        monkeypatch.setenv("GIT_CONFIG_KEY_0", "url." + tmp_path.as_uri() + ".insteadOf")
        monkeypatch.setenv("GIT_CONFIG_VALUE_0", nominal)
    # Canonical baseline reads this unrelated local repository as if canonical.
    present, detail = lock.check_canonical_ref("topic", str(tmp_path))
    assert not present, (head, present, detail)
    assert "UNKNOWN" in detail


def test_local_decode_error_is_controlled(monkeypatch):
    def broken(*a, **kw):
        raise UnicodeDecodeError("utf8", b"\xff", 0, 1, "bad")

    monkeypatch.setattr(lock.subprocess, "run", broken)
    reasons = lock.verify(SLUG, "main", "a" * 40, ".")
    assert reasons and "cannot read origin" in reasons[0]


def test_rewrite_guard_does_not_read_values(monkeypatch):
    def run(args, **kw):
        assert "--name-only" in args
        assert kw["stdout"] == subprocess.DEVNULL
        assert kw["stderr"] == subprocess.DEVNULL
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(lock.subprocess, "run", run)
    assert not lock._no_url_rewrites(".", {})


def test_configuration_change_after_probe_is_unknown(monkeypatch):
    monkeypatch.setattr(lock, "_git", lambda *a: f"https://github.com/{SLUG}.git")
    checks = iter([True, False])
    monkeypatch.setattr(lock, "_no_url_rewrites", lambda *a: next(checks))
    monkeypatch.setattr(
        lock.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess([], 0, "a" * 40 + "\trefs/heads/topic\n", ""),
    )
    assert not lock.check_canonical_ref("topic", ".")[0]


def test_credentials_not_echoed_on_identity_failure(monkeypatch):
    monkeypatch.setattr(lock, "remote_identity", lambda *a: f"https://TOKEN@github.com/{SLUG}")
    result = lock.verify(SLUG, "main", "a" * 40, ".")
    assert result and "TOKEN" not in str(result)


def test_final_head_failure_is_controlled(monkeypatch, capsys):
    monkeypatch.setattr(lock, "verify", lambda *a: [])

    def fail(*a):
        raise RuntimeError("unavailable")

    monkeypatch.setattr(lock, "_git", fail)
    assert lock.main(["--repo", SLUG, "--branch", "main", "--audit-base-sha", "a" * 40]) == 1
    assert "LOCK_FAIL" in capsys.readouterr().err


@pytest.mark.parametrize(
    "output", ["a" * 40 + " refs/heads/topic\n", "0" * 40 + "\trefs/heads/topic\n"]
)
def test_strict_wire_shape_and_nonzero_oid(monkeypatch, output):
    monkeypatch.setattr(lock, "_git", lambda *a: f"https://github.com/{SLUG}.git")
    monkeypatch.setattr(lock, "_no_url_rewrites", lambda *a: True)
    monkeypatch.setattr(
        lock.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess([], 0, output, "")
    )
    assert not lock.check_canonical_ref("topic", ".")[0]


def test_auth_environment_preserved(monkeypatch):
    monkeypatch.setenv("SSH_AUTH_SOCK", "/fixture/agent")
    monkeypatch.setenv("GIT_ASKPASS", "/fixture/askpass")
    monkeypatch.setattr(lock, "_git", lambda *a: f"https://github.com/{SLUG}.git")
    monkeypatch.setattr(lock, "_no_url_rewrites", lambda *a: True)

    def response(*args, **kw):
        assert kw["env"]["SSH_AUTH_SOCK"] == "/fixture/agent"
        assert kw["env"]["GIT_ASKPASS"] == "/fixture/askpass"
        assert "GIT_CONFIG_GLOBAL" not in kw["env"]
        return subprocess.CompletedProcess([], 0, "a" * 40 + "\trefs/heads/topic\n", "")

    monkeypatch.setattr(lock.subprocess, "run", response)
    assert lock.check_canonical_ref("topic", ".")[0]
