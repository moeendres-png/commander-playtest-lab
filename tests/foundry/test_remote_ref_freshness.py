"""Fresh remote evidence must never fall back to local tracking refs."""

import importlib.util
import subprocess
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[2] / "tools/foundry/source_lock.py"
spec = importlib.util.spec_from_file_location("lock_under_test", PATH)
lock = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lock)


def test_stale_tracking_ref_after_transport_failure(tmp_path, monkeypatch, capsys):
    # Real Git creates the stale local ref. Only network failure is injected.
    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=tmp_path, check=True, capture_output=True, text=True
        ).stdout.strip()

    git("init", "-b", "main")
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
    git("update-ref", "refs/remotes/origin/topic", head)
    git(
        "config",
        "remote.origin.url",
        "https://github.com/" + lock.CANONICAL_SLUG + ".git",
    )
    real_run = subprocess.run

    def fail_remote(args, **kwargs):
        if "ls-remote" in args:
            return subprocess.CompletedProcess(args, 128, "", "network unavailable")
        return real_run(args, **kwargs)

    monkeypatch.setattr(lock.subprocess, "run", fail_remote)
    present, detail = lock.check_canonical_ref("topic", str(tmp_path))
    assert not present, (present, detail)
    assert "REMOTE_REF_UNKNOWN" in detail
    assert (
        lock.main(
            [
                "--repo",
                lock.CANONICAL_SLUG,
                "--branch",
                "main",
                "--audit-base-sha",
                head,
                "--workdir",
                str(tmp_path),
                "--check-remote-ref",
                "topic",
            ]
        )
        == 1
    )
    output = capsys.readouterr()
    assert "LOCK_OK" not in output.out
    assert "REMOTE_REF_UNKNOWN" in output.err


@pytest.mark.parametrize(
    "code,output,expected",
    [
        (0, "a" * 40 + "\trefs/heads/topic\n", True),
        (2, "", False),
        (128, "a" * 40 + "\trefs/heads/topic\n", False),
        (0, "a" * 40 + "\trefs/tags/topic\n", False),
        (0, "bad\trefs/heads/topic\n", False),
        (0, "", False),
        (0, ("a" * 40 + "\trefs/heads/topic\n") * 2, False),
    ],
)
def test_response_contract(monkeypatch, code, output, expected):
    # WS240: identity is read through the record-preserving seam; _git no
    # longer carries remote URLs, so stub remote_url_records (assertions
    # unchanged from the WS237/WS239 port).
    monkeypatch.setattr(
        lock,
        "remote_url_records",
        lambda *a: ["https://github.com/" + lock.CANONICAL_SLUG + ".git"],
    )
    monkeypatch.setattr(lock, "_no_url_rewrites", lambda *a: True)
    monkeypatch.setattr(
        lock.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess([], code, output, ""),
    )
    present, detail = lock.check_canonical_ref("topic", ".")
    assert present is expected
    if code == 2:
        assert "REQUESTED_REF_ABSENT_FROM_CANONICAL_REMOTE" in detail
    elif not expected:
        assert "REMOTE_REF_UNKNOWN" in detail


@pytest.mark.parametrize(
    "ref",
    ["*", "topic?", "-topic", "refs/remotes/origin/topic", "topic\nother", "../topic"],
)
def test_invalid_ref_stops_before_command(monkeypatch, ref):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid ref reached Git")

    monkeypatch.setattr(lock.subprocess, "run", forbidden)
    assert lock.check_canonical_ref(ref, ".")[0] is False


def test_cli_unknown_is_not_absent(monkeypatch, capsys):
    monkeypatch.setattr(lock, "verify", lambda *a: [])
    monkeypatch.setattr(
        lock, "remote_identity", lambda *a: "https://github.com/" + lock.CANONICAL_SLUG
    )
    monkeypatch.setattr(
        lock,
        "check_canonical_ref",
        lambda *a: (False, "REMOTE_REF_UNKNOWN: access unavailable"),
    )
    result = lock.main(
        [
            "--repo",
            lock.CANONICAL_SLUG,
            "--branch",
            "main",
            "--audit-base-sha",
            "a" * 40,
            "--check-remote-ref",
            "topic",
        ]
    )
    output = capsys.readouterr()
    assert result == 1
    assert "REMOTE_REF_UNKNOWN" in output.err
    assert "REQUESTED_REF_ABSENT" not in output.err
    assert "LOCK_OK" not in output.out


def test_timeout_is_unknown(monkeypatch):
    def timeout(*a, **k):
        raise subprocess.TimeoutExpired("git", 30)

    monkeypatch.setattr(lock.subprocess, "run", timeout)
    assert "REMOTE_REF_UNKNOWN" in lock.check_canonical_ref("topic", ".")[1]


def test_prior_lock_failure_does_not_query_remote(monkeypatch):
    monkeypatch.setattr(lock, "verify", lambda *a: ["branch mismatch"])

    def forbidden(*a):
        pytest.fail("dependent remote query ran after invalid lock")

    monkeypatch.setattr(lock, "remote_identity", forbidden)
    assert (
        lock.main(
            [
                "--repo",
                lock.CANONICAL_SLUG,
                "--branch",
                "main",
                "--audit-base-sha",
                "a" * 40,
                "--check-remote-ref",
                "topic",
            ]
        )
        == 1
    )


def test_explicit_tag_and_command_contract(monkeypatch):
    # WS240: see test_response_contract — stub the record-preserving seam.
    monkeypatch.setattr(
        lock,
        "remote_url_records",
        lambda *a: ["https://github.com/" + lock.CANONICAL_SLUG + ".git"],
    )
    monkeypatch.setattr(lock, "_no_url_rewrites", lambda *a: True)

    def response(args, **kwargs):
        assert args == [
            "git",
            "-c",
            "http.followRedirects=false",
            "ls-remote",
            "--exit-code",
            "--refs",
            "--",
            "https://github.com/" + lock.CANONICAL_SLUG + ".git",
            "refs/tags/v1",
        ]
        assert kwargs["timeout"] == 30
        assert kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"
        return subprocess.CompletedProcess(args, 0, "a" * 40 + "\trefs/tags/v1\n", "")

    monkeypatch.setattr(lock.subprocess, "run", response)
    assert lock.check_canonical_ref("refs/tags/v1", ".")[0]


@pytest.mark.parametrize(
    "error", [FileNotFoundError(), UnicodeDecodeError("utf8", b"\xff", 0, 1, "bad")]
)
def test_execution_errors_are_unknown(monkeypatch, error):
    def failure(*a, **kw):
        raise error

    monkeypatch.setattr(lock.subprocess, "run", failure)
    assert "REMOTE_REF_UNKNOWN" in lock.check_canonical_ref("main", ".")[1]


def test_real_git_present_and_absent(tmp_path, monkeypatch):
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
    # Redirect transport in the test harness only, not through Git configuration.
    git("remote", "add", "origin", "https://github.com/" + lock.CANONICAL_SLUG + ".git")
    real_run = subprocess.run

    def fixture_transport(args, **kwargs):
        if "ls-remote" in args:
            args = list(args)
            args[-2] = str(tmp_path)
        return real_run(args, **kwargs)

    monkeypatch.setattr(lock.subprocess, "run", fixture_transport)
    assert lock.check_canonical_ref("topic", str(tmp_path))[0]
    present, detail = lock.check_canonical_ref("missing", str(tmp_path))
    assert not present and "REQUESTED_REF_ABSENT_FROM_CANONICAL_REMOTE" in detail
