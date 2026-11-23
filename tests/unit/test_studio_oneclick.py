"""The one-click starter (``commander_lab.studio.oneclick``) with fake processes and folders.

The guards the Owner asked for (no pull on a dirty or foreign branch, no program install without a
typed "J", no JAR without pin and checksum check, no start when the port is taken, no token in the
output, no write in ``--nur-pruefen``) have tests here; how many hand-made mutations they catch is
recorded, as X of Y, in the pull request, not claimed for every possible change.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest

from commander_lab.studio import oneclick as oc

PIN = "a" * 40
OTHER_PIN = "b" * 40
HEAD = "c" * 40
SECRET = "TOKEN-DARF-NIE-ERSCHEINEN"

Rule = tuple[
    Callable[[list[str]], bool], oc.Lauf | Callable[[list[str], dict[str, object]], oc.Lauf]
]


class FakeRun:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.kwargs: list[dict[str, object]] = []
        self.rules: list[Rule] = []
        # git diff --quiet <sha> HEAD -- engine-bridge/: return code per source commit; any
        # other spelling of the command answers 128 (unknown), so it never counts as fresh.
        self.bridge: dict[str, int] = {HEAD: 0}

    def on(
        self,
        match: Callable[[list[str]], bool],
        result: oc.Lauf | Callable[[list[str], dict[str, object]], oc.Lauf],
    ) -> None:
        self.rules.insert(0, (match, result))

    def __call__(self, cmd: list[str], **kwargs: object) -> oc.Lauf:
        cmd = [str(part) for part in cmd]
        self.calls.append(cmd)
        self.kwargs.append(kwargs)
        if cmd[3:5] == ["diff", "--quiet"]:
            exact = len(cmd) == 9 and cmd[6:] == ["HEAD", "--", "engine-bridge/"]
            return oc.Lauf(self.bridge.get(cmd[5], 128) if exact else 128)
        for match, result in self.rules:
            if match(cmd):
                return result(cmd, kwargs) if callable(result) else result
        return oc.Lauf(0)

    def ran(self, *words: str) -> bool:
        return any(all(word in call for word in words) for call in self.calls)

    def joined(self) -> str:
        return "\n".join(" ".join(call) for call in self.calls)


World = tuple[oc.Umgebung, FakeRun, list[str]]


def STATUS(cmd: list[str]) -> bool:
    return cmd[3:] == ["status", "--porcelain"]


def has(*words: str) -> Callable[[list[str]], bool]:
    return lambda cmd: all(word in cmd for word in words)


def _doctor_report(**statuses: str) -> dict[str, object]:
    names = (
        "python",
        "dependencies",
        "java",
        "engine_bridge",
        "engine_pin",
        "appcds_archive",
        "card_knowledge",
        "studio_data",
    )
    return {
        "expected_pin": PIN,
        "checks": [
            {"name": n, "status": statuses.get(n, "PASS"), "detail": f"detail {n}"} for n in names
        ],
    }


@pytest.fixture
def world(tmp_path: Path) -> tuple[oc.Umgebung, FakeRun, list[str]]:
    repo = tmp_path / "repo"
    (repo / "requirements").mkdir(parents=True)
    (repo / "requirements" / "lock.txt").write_text("pkg==1 --hash=sha256:00\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (repo / ".git").mkdir()
    venv_py = oc.venv_python(repo, windows=False)
    venv_py.parent.mkdir(parents=True)
    venv_py.write_text("", encoding="utf-8")
    data = tmp_path / "data"
    run = FakeRun()
    out: list[str] = []
    run.on(has("-c"), oc.Lauf(0, "3.12\n"))
    run.on(has("doctor", "--json"), oc.Lauf(0, json.dumps(_doctor_report())))
    run.on(has("rev-parse", "--abbrev-ref", "HEAD"), oc.Lauf(0, "main\n"))
    run.on(lambda c: c[-2:] == ["rev-parse", "HEAD"], oc.Lauf(0, f"{HEAD}\n"))
    run.on(STATUS, oc.Lauf(0, ""))
    run.on(has("@{u}"), oc.Lauf(0, "origin/main\n"))
    run.on(has("remote", "get-url"), oc.Lauf(0, f"https://github.com/{oc.REPO_SLUG}.git\n"))
    tools = {"git": "/usr/bin/git", "java": "/usr/bin/java", "winget": "winget"}
    u = oc.Umgebung(
        repo=repo,
        data=data,
        windows=False,
        interaktiv=False,
        ja=False,
        env={"PATH": "/usr/bin", "GH_TOKEN": SECRET},
        run=run,
        which=lambda name: tools.get(name),
        eingabe=lambda _prompt: "N",
        sagen=out.append,
        port_offen=lambda _port: False,
        studio_antwortet=lambda _port: False,
        browser=lambda url: out.append(f"BROWSER {url}"),
        python_version=(3, 12),
        python_exe="/usr/bin/python3",
    )
    return u, run, out


def _args(**overrides: object) -> argparse.Namespace:
    args = oc.parser().parse_args([])
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _artifact_folder(folder: Path, *, jar: bytes = b"JAR", pin: str = PIN) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / oc.JAR_NAME).write_bytes(jar)
    (folder / oc.SHA_NAME).write_text(f"{_sha(jar)}  {oc.JAR_NAME}\n", encoding="utf-8")
    (folder / oc.PIN_NAME).write_text(f"{pin}\n", encoding="utf-8")
    (folder / oc.SUMS_NAME).write_text(
        f"{_sha(b'x')}  ENGINE_PIN.txt\n{_sha(jar)}  {oc.JAR_NAME}\n", encoding="utf-8"
    )


# --- questions -----------------------------------------------------------------------------


def test_ja_never_confirms_an_installation_but_confirms_other_questions(world: World) -> None:
    u, _run, _out = world
    u.ja = True
    assert oc.frage(u, "Programm?", installation=True) is False
    assert oc.frage(u, "Eigenbau?") is True


def test_without_a_console_every_answer_is_no_and_a_typed_j_is_yes(world: World) -> None:
    u, _run, _out = world
    assert oc.frage(u, "Frage?") is False
    u.interaktiv = True
    u.eingabe = lambda _prompt: "J"
    assert oc.frage(u, "Frage?", installation=True) is True


# --- step 1: Java ----------------------------------------------------------------------------


def _no_java(u: oc.Umgebung) -> None:
    tools = {"git": "/usr/bin/git", "winget": "winget"}
    u.which = lambda name: tools.get(name)
    u.windows = True


def test_missing_java_is_installed_only_after_a_typed_j(world: World) -> None:
    u, run, out = world
    _no_java(u)
    u.ja = True  # --ja must not be enough
    bericht = oc.Bericht()
    assert oc.pruefe_java(u, bericht, nur_pruefen=False) is None
    assert not run.ran("winget")
    assert any("EclipseAdoptium.Temurin.17.JDK" in line for line in out)
    assert bericht.befunde[-1].farbe == oc.ROT
    u.interaktiv, u.eingabe = True, (lambda _prompt: "j")
    oc.pruefe_java(u, oc.Bericht(), nur_pruefen=False)
    assert run.ran("winget", "install", "EclipseAdoptium.Temurin.17.JDK")


def test_old_java_is_reported_and_a_current_one_passes(world: World) -> None:
    u, run, _out = world
    run.on(has("-version"), oc.Lauf(0, "", 'openjdk version "11.0.2"'))
    bericht = oc.Bericht()
    assert oc.pruefe_java(u, bericht, nur_pruefen=False) is None
    assert bericht.befunde[-1].farbe == oc.ROT
    run.on(has("-version"), oc.Lauf(0, "", 'openjdk version "17.0.9"'))
    assert oc.pruefe_java(u, oc.Bericht(), nur_pruefen=False) == "/usr/bin/java"


def test_python_below_312_stops_the_flow(world: World) -> None:
    u, run, _out = world
    u.python_version = (3, 11)
    assert oc.ablauf(u, _args(), lambda: 0) == 1
    assert not run.ran("pull")


# --- step 2: git -----------------------------------------------------------------------------


def test_pull_only_on_clean_main_with_upstream(world: World) -> None:
    u, run, _out = world
    assert oc.aktualisiere_repo(u, oc.Bericht(), nur_pruefen=False) is False
    assert run.ran("pull", "--ff-only")
    assert not run.ran("reset") and not run.ran("stash") and not run.ran("clean")


@pytest.mark.parametrize(
    ("rule", "result"),
    [
        (STATUS, oc.Lauf(0, " M src/x.py\n")),
        (STATUS, oc.Lauf(0, "?? meine_notiz.txt\n")),
        (has("rev-parse", "--abbrev-ref", "HEAD"), oc.Lauf(0, "feature\n")),
        (has("@{u}"), oc.Lauf(128, "")),
    ],
)
def test_no_pull_on_a_dirty_tree_another_branch_or_without_upstream(
    world: World, rule: Callable[[list[str]], bool], result: oc.Lauf
) -> None:
    u, run, _out = world
    run.on(rule, result)
    bericht = oc.Bericht()
    assert oc.aktualisiere_repo(u, bericht, nur_pruefen=False) is False
    assert not run.ran("pull")
    assert bericht.befunde[-1].farbe == oc.GELB


def test_a_moved_head_restarts_the_starter(world: World) -> None:
    u, run, _out = world
    heads = iter([f"{HEAD}\n", f"{'d' * 40}\n"])
    run.on(lambda c: c[-2:] == ["rev-parse", "HEAD"], lambda _cmd, _kw: oc.Lauf(0, next(heads)))
    restarted: list[int] = []

    def restart() -> int:
        restarted.append(1)
        return 7

    code = oc.ablauf(u, _args(), restart)
    assert restarted == [1]
    assert code == 7


def test_nur_pruefen_reports_but_never_pulls(world: World) -> None:
    u, run, _out = world
    assert oc.aktualisiere_repo(u, oc.Bericht(), nur_pruefen=True) is False
    assert not run.ran("pull")


# --- step 3: packages ------------------------------------------------------------------------


def test_packages_install_only_when_the_lock_checksum_changed(world: World) -> None:
    u, run, _out = world
    assert oc.richte_venv_ein(u, oc.Bericht(), nur_pruefen=False, neu=False)
    assert run.ran("pip", "--require-hashes")
    assert run.ran("pip", "--no-deps", "--no-build-isolation", "-e", ".")
    marker = u.repo / ".venv" / oc.PACKAGES_MARKER
    assert marker.read_text(encoding="utf-8").split()[0] == oc.pakete_pruefsumme(u.repo)
    run.calls.clear()
    assert oc.richte_venv_ein(u, oc.Bericht(), nur_pruefen=False, neu=False)
    assert not run.ran("pip")
    (u.repo / "requirements" / "lock.txt").write_text("pkg==2\n", encoding="utf-8")
    oc.richte_venv_ein(u, oc.Bericht(), nur_pruefen=False, neu=False)
    assert run.ran("pip", "--require-hashes")


def test_a_failed_install_writes_no_marker(world: World) -> None:
    u, run, _out = world
    run.on(has("--require-hashes"), oc.Lauf(1))
    bericht = oc.Bericht()
    assert oc.richte_venv_ein(u, bericht, nur_pruefen=False, neu=False) is False
    assert not (u.repo / ".venv" / oc.PACKAGES_MARKER).exists()
    assert not run.ran("-e", ".[api]")  # the fallback needs a yes
    assert bericht.befunde[-1].farbe == oc.ROT


def test_a_missing_venv_is_created_but_not_in_nur_pruefen(world: World) -> None:
    u, run, _out = world
    oc.venv_python(u.repo, windows=False).unlink()
    assert oc.richte_venv_ein(u, oc.Bericht(), nur_pruefen=True, neu=False) is False
    assert not run.ran("venv")
    oc.richte_venv_ein(u, oc.Bericht(), nur_pruefen=False, neu=False)
    assert run.ran("/usr/bin/python3", "-m", "venv")


# --- step 4: engine --------------------------------------------------------------------------


def _engine(u: oc.Umgebung, jar: bytes = b"JAR", pin: str = PIN, sha: str | None = None) -> Path:
    engine = u.data / "engine"
    engine.mkdir(parents=True, exist_ok=True)
    (engine / oc.JAR_NAME).write_bytes(jar)
    (engine / oc.SHA_NAME).write_text(f"{sha or _sha(jar)}  {oc.JAR_NAME}\n", encoding="utf-8")
    (engine / oc.PIN_NAME).write_text(f"{pin}\n", encoding="utf-8")
    (engine / oc.SOURCE_NAME).write_text(f"{HEAD}\n", encoding="utf-8")
    (engine / oc.CONFIRM_NAME).write_text(f"{pin}\n", encoding="utf-8")
    return engine


def test_jar_valid_only_with_matching_checksum_and_pin(world: World) -> None:
    u, _run, _out = world
    engine = _engine(u)
    assert oc.jar_geprueft(engine, PIN)[0] is True
    assert oc.jar_geprueft(engine, OTHER_PIN)[0] is False
    _engine(u, sha="0" * 64)
    assert oc.jar_geprueft(engine, PIN)[0] is False
    _engine(u)
    (engine / oc.PIN_NAME).unlink()
    assert oc.jar_geprueft(engine, PIN)[0] is False


def test_artifact_check_needs_both_checksums_and_the_pin(tmp_path: Path) -> None:
    good = tmp_path / "good"
    _artifact_folder(good)
    assert oc.pruefe_artefakt(good, PIN)[0] == _sha(b"JAR")
    assert oc.pruefe_artefakt(good, OTHER_PIN)[0] is None
    sums = tmp_path / "sums"
    _artifact_folder(sums)
    (sums / oc.SUMS_NAME).write_text(f"{'0' * 64}  {oc.JAR_NAME}\n", encoding="utf-8")
    assert oc.pruefe_artefakt(sums, PIN)[0] is None
    side = tmp_path / "side"
    _artifact_folder(side)
    (side / oc.SHA_NAME).write_text(f"{'0' * 64}  {oc.JAR_NAME}\n", encoding="utf-8")
    assert oc.pruefe_artefakt(side, PIN)[0] is None
    missing = tmp_path / "missing"
    _artifact_folder(missing)
    (missing / oc.PIN_NAME).unlink()
    assert oc.pruefe_artefakt(missing, PIN)[0] is None


def _runs(*runs: dict[str, object]) -> oc.Lauf:
    return oc.Lauf(0, json.dumps({"workflow_runs": list(runs)}))


def _run(run_id: int, sha: str, **over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": run_id,
        "head_sha": sha,
        "head_branch": "main",
        "conclusion": "success",
        "path": oc.RELEASE_WORKFLOW_PATH,
        "event": "push",
        "head_repository": {"full_name": oc.REPO_SLUG},
    }
    base.update(over)
    return base


def _arts(sha: str, expired: bool = False) -> oc.Lauf:
    art = {"name": f"{oc.ARTIFACT_PREFIX}1.25.0-{sha}", "expired": expired, "size_in_bytes": 5}
    return oc.Lauf(0, json.dumps({"artifacts": [art]}))


def test_artifact_choice_rejects_foreign_failed_and_expired_runs(world: World) -> None:
    u, run, _out = world
    run.on(
        has("api"),
        _runs(
            _run(1, "1" * 40, head_branch="feature"),
            _run(2, "2" * 40, conclusion="failure"),
            _run(3, "3" * 40, head_repository={"full_name": "someone/fork"}),
            _run(6, "6" * 40, event="pull_request"),
            _run(4, "4" * 40, path=".github/workflows/other.yml"),
            _run(5, "5" * 40),
        ),
    )
    run.on(lambda c: "actions/runs/5/artifacts" in " ".join(c), _arts("5" * 40, expired=True))
    picked, _reason = oc.waehle_artefakt(u, "gh", HEAD)
    assert picked is None
    assert not any(f"runs/{n}/" in c for n in (1, 2, 3, 4, 6) for c in run.joined().split())
    assert "event=push" in run.calls[0][-1]


def test_artifact_choice_prefers_the_local_head(world: World) -> None:
    u, run, _out = world
    run.on(has("api"), _runs(_run(9, "9" * 40), _run(8, HEAD)))
    run.on(lambda c: "actions/runs/8/artifacts" in " ".join(c), _arts(HEAD))
    run.on(lambda c: "actions/runs/9/artifacts" in " ".join(c), _arts("9" * 40))
    picked, _reason = oc.waehle_artefakt(u, "gh", HEAD)
    assert picked is not None and picked.run_id == 8


def _gh_world(u: oc.Umgebung, run: FakeRun, *, pin: str = PIN, sha: str = HEAD) -> None:
    tools = {"git": "/usr/bin/git", "java": "/usr/bin/java", "gh": "gh"}
    u.which = lambda name: tools.get(name)
    run.on(has("api"), _runs(_run(8, sha)))
    run.on(lambda c: "actions/runs/8/artifacts" in " ".join(c), _arts(sha))

    def download(cmd: list[str], _kw: dict[str, object]) -> oc.Lauf:
        _artifact_folder(Path(cmd[cmd.index("-D") + 1]), pin=pin)
        return oc.Lauf(0, f"token {SECRET}")

    run.on(has("run", "download"), download)


def test_a_verified_artifact_is_staged_with_its_sidecars(world: World) -> None:
    u, run, out = world
    _gh_world(u, run)
    bericht = oc.Bericht()
    assert oc.sorge_fuer_engine(u, bericht, PIN, None, nur_pruefen=False) is True
    engine = u.data / "engine"
    assert oc.jar_geprueft(engine, PIN)[0] is True
    assert not run.ran("auth", "token")
    assert SECRET not in "\n".join(out)
    assert not list(u.data.glob("engine-download-*"))  # temp folder gone


def test_an_artifact_with_a_foreign_pin_is_never_staged(world: World) -> None:
    u, run, _out = world
    _gh_world(u, run, pin=OTHER_PIN)
    bericht = oc.Bericht()
    assert oc.sorge_fuer_engine(u, bericht, PIN, None, nur_pruefen=False) is False
    assert not (u.data / "engine" / oc.JAR_NAME).exists()
    assert bericht.befunde[-1].farbe == oc.ROT


def test_an_artifact_whose_engine_reports_another_commit_is_refused(world: World) -> None:
    u, run, _out = world
    _gh_world(u, run)
    reply = {
        "request_id": "studio-start-1",
        "success": True,
        "payload": {"engine_commit": OTHER_PIN},
    }
    run.on(has("-jar"), oc.Lauf(0, json.dumps(reply) + "\n"))
    assert oc.sorge_fuer_engine(u, oc.Bericht(), PIN, "/usr/bin/java", nur_pruefen=False) is False
    assert not (u.data / "engine" / oc.JAR_NAME).exists()


def test_no_gh_or_no_login_names_what_is_missing(world: World) -> None:
    u, run, _out = world
    ok, why = oc.hole_artefakt(u, PIN, None)
    assert not ok and "GitHub.cli" in why
    u.which = lambda name: {"gh": "gh"}.get(name)
    run.on(has("auth", "status"), oc.Lauf(1, f"Logged in with {SECRET}"))
    ok, why = oc.hole_artefakt(u, PIN, None)
    assert not ok and "gh auth login" in why and SECRET not in why
    assert not run.ran("run", "download")


def test_a_valid_jar_needs_no_download_and_nur_pruefen_downloads_nothing(world: World) -> None:
    u, run, _out = world
    _gh_world(u, run)
    _engine(u)
    assert oc.sorge_fuer_engine(u, oc.Bericht(), PIN, None, nur_pruefen=False) is False
    assert not run.ran("gh")
    (u.data / "engine" / oc.PIN_NAME).write_text(OTHER_PIN, encoding="utf-8")
    assert oc.sorge_fuer_engine(u, oc.Bericht(), PIN, None, nur_pruefen=True) is False
    assert not run.ran("gh")


def test_without_a_known_pin_the_engine_is_left_alone(world: World) -> None:
    u, run, _out = world
    _gh_world(u, run)
    bericht = oc.Bericht()
    assert oc.sorge_fuer_engine(u, bericht, None, None, nur_pruefen=False) is False
    assert not run.ran("gh") and bericht.befunde[-1].farbe == oc.ROT


def test_an_existing_jar_without_sidecars_counts_only_when_the_engine_reports_the_pin(
    world: World,
) -> None:
    u, run, _out = world
    engine = _engine(u)
    (engine / oc.SHA_NAME).unlink()
    (engine / oc.PIN_NAME).unlink()
    reply = {"request_id": "studio-start-1", "success": True, "payload": {"engine_commit": PIN}}
    run.on(has("-jar"), oc.Lauf(0, json.dumps(reply) + "\n"))
    assert oc.sorge_fuer_engine(u, oc.Bericht(), PIN, "/usr/bin/java", nur_pruefen=False) is False
    assert oc.jar_geprueft(engine, PIN)[0] is True


def test_maven_build_needs_a_yes_and_the_reported_pin(world: World) -> None:
    u, run, _out = world
    tools = {"git": "g", "java": "j", "javac": "jc", "mvn": "mvn"}
    u.which = lambda name: tools.get(name)
    u.env["COMMANDER_LAB_XMAGE_COMMIT"] = OTHER_PIN
    ok, _why = oc.baue_mit_maven(u, PIN, "/usr/bin/java")
    assert not ok and not run.ran("mvn")
    u.ja = True
    jar = u.repo / oc.BUILT_JAR
    jar.parent.mkdir(parents=True)
    jar.write_bytes(b"BUILT")
    reply = {
        "request_id": "studio-start-1",
        "success": True,
        "payload": {"engine_commit": OTHER_PIN},
    }
    run.on(has("-jar"), oc.Lauf(0, json.dumps(reply) + "\n"))
    ok, _why = oc.baue_mit_maven(u, PIN, "/usr/bin/java")
    assert not ok and not (u.data / "engine" / oc.JAR_NAME).exists()
    assert run.ran("mvn", "-B", "verify")
    bootstrap_env = next(
        kw["env"] for c, kw in zip(run.calls, run.kwargs, strict=True) if "bash" in c
    )
    assert "COMMANDER_LAB_XMAGE_COMMIT" not in bootstrap_env  # type: ignore[operator]
    reply["payload"] = {"engine_commit": PIN}
    run.on(has("-jar"), oc.Lauf(0, json.dumps(reply) + "\n"))
    ok, _why = oc.baue_mit_maven(u, PIN, "/usr/bin/java")
    assert ok and oc.jar_geprueft(u.data / "engine", PIN)[0] is True


def test_handshake_parsing_ignores_noise_and_failures(world: World) -> None:
    u, run, _out = world
    ok = {"request_id": "studio-start-1", "success": True, "payload": {"engine_commit": PIN}}
    bad = dict(ok, success=False)
    run.on(has("-jar"), oc.Lauf(0, "log line\n" + json.dumps(bad) + "\n"))
    assert oc.engine_meldet_pin(u, "java", Path("x.jar")) is None
    run.on(has("-jar"), oc.Lauf(0, "log line\n" + json.dumps(ok) + "\n"))
    assert oc.engine_meldet_pin(u, "java", Path("x.jar")) == PIN


# --- steps 5 and 6 ---------------------------------------------------------------------------


def test_appcds_is_built_for_a_new_jar_and_skipped_when_it_matches(world: World) -> None:
    u, run, _out = world
    _engine(u)
    report = _doctor_report()
    oc.baue_appcds(u, oc.Bericht(), report, neu=False, java="j", nur_pruefen=False)
    assert not run.ran("build-appcds")
    oc.baue_appcds(u, oc.Bericht(), report, neu=True, java="j", nur_pruefen=False)
    assert run.ran("build-appcds")


def test_doctor_summary_is_not_ready_on_any_warning(world: World) -> None:
    u, _run, out = world
    bericht = oc.Bericht()
    oc.fasse_doctor_zusammen(u, bericht, _doctor_report())
    assert bericht.alles_bereit
    bericht = oc.Bericht()
    oc.fasse_doctor_zusammen(u, bericht, _doctor_report(appcds_archive="WARN", java="FAIL"))
    assert not bericht.alles_bereit
    assert {item.farbe for item in bericht.befunde} == {oc.GELB, oc.ROT}
    assert any(line.startswith("  [rot] Java") for line in out)
    assert any("Nächster Schritt" in line for line in out)


# --- step 7: first import --------------------------------------------------------------------


def test_first_import_runs_once_and_marks_only_success(world: World) -> None:
    u, run, _out = world
    scry = u.data / oc.SCRYFALL_FOLDER / "oracle-cards-20261110.jsonl.gz"
    scry.parent.mkdir(parents=True)
    scry.write_bytes(b"x")
    run.on(has("import-all"), oc.Lauf(1))
    oc.erstimport(u, oc.Bericht(), None, nur_pruefen=False)
    assert run.ran("import-all", "--from-repo", oc.COMMANDER, str(scry))
    assert not (u.data / oc.STATE_FOLDER / oc.IMPORT_MARKER).exists()
    assert not (u.data / oc.DATABASE_NAME).exists()  # the empty check created no database
    run.on(has("import-all"), oc.Lauf(0))
    oc.erstimport(u, oc.Bericht(), None, nur_pruefen=False)
    assert (u.data / oc.STATE_FOLDER / oc.IMPORT_MARKER).is_file()
    _fill_store(u)
    run.calls.clear()
    bericht = oc.Bericht()
    oc.erstimport(u, bericht, None, nur_pruefen=False)
    assert not run.ran("import-all")
    assert bericht.befunde[-1].farbe == oc.GRUEN


def _fill_store(u: oc.Umgebung) -> None:
    u.data.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(u.data / oc.DATABASE_NAME) as db:
        db.execute("CREATE TABLE IF NOT EXISTS card (oracle_id TEXT)")
        db.execute("INSERT INTO card VALUES ('x')")
    db.close()


def test_a_marker_without_a_store_is_not_green_and_imports_again(world: World) -> None:
    u, run, _out = world
    marker = u.data / oc.STATE_FOLDER / oc.IMPORT_MARKER
    marker.parent.mkdir(parents=True)
    marker.write_text("{}", encoding="utf-8")
    bericht = oc.Bericht()
    oc.erstimport(u, bericht, None, nur_pruefen=False)
    assert bericht.befunde[-1].farbe == oc.GELB  # no Scryfall file: yellow, never green
    scry = u.data / oc.SCRYFALL_FOLDER / "oracle-cards-1.jsonl.gz"
    scry.parent.mkdir(parents=True)
    scry.write_bytes(b"x")
    oc.erstimport(u, oc.Bericht(), None, nur_pruefen=False)
    assert run.ran("import-all")


def test_no_scryfall_file_means_no_import_and_a_yellow_hint(world: World) -> None:
    u, run, _out = world
    bericht = oc.Bericht()
    oc.erstimport(u, bericht, None, nur_pruefen=False)
    assert not run.ran("import-all")
    assert bericht.befunde[-1].farbe == oc.GELB


def test_a_filled_store_is_not_imported_again(world: World) -> None:
    u, run, _out = world
    u.data.mkdir(parents=True)
    with sqlite3.connect(u.data / oc.DATABASE_NAME) as db:
        db.execute("CREATE TABLE card (oracle_id TEXT)")
        db.execute("INSERT INTO card VALUES ('x')")
    db.close()
    oc.erstimport(u, oc.Bericht(), Path("/nope"), nur_pruefen=False)
    assert not run.ran("import-all")


# --- step 8: start ---------------------------------------------------------------------------


def test_a_running_studio_only_gets_the_browser(world: World) -> None:
    u, run, out = world
    u.port_offen = lambda _port: True
    u.studio_antwortet = lambda _port: True
    assert oc.starte(u, 8765) == 0
    assert not run.ran("serve")
    assert "BROWSER http://127.0.0.1:8765/" in out


def test_a_port_taken_by_another_program_starts_nothing(world: World) -> None:
    u, run, out = world
    u.port_offen = lambda _port: True
    assert oc.starte(u, 8765) == 4
    assert not run.ran("serve")
    assert not any(line.startswith("BROWSER") for line in out)


def test_a_free_port_starts_serve_and_lock_exit_opens_the_browser(world: World) -> None:
    u, run, out = world
    run.on(has("serve"), oc.Lauf(3))
    assert oc.starte(u, 8765) == 0
    assert run.ran("serve", "--open", "--port", "8765")
    env = run.kwargs[-1]["env"]
    assert env[oc.STUDIO_DATA_ENV] == str(u.data)  # type: ignore[index]
    assert "BROWSER http://127.0.0.1:8765/" in out


# --- whole flow ------------------------------------------------------------------------------


def test_nur_pruefen_changes_nothing(world: World) -> None:
    u, run, out = world
    _gh_world(u, run)
    code = oc.ablauf(u, _args(nur_pruefen=True), lambda: 99)
    joined = run.joined()
    for word in (
        "pull",
        "pip",
        "venv",
        "download",
        "serve",
        "build-appcds",
        "import-all",
        "winget",
    ):
        assert word not in joined.split(), word
    assert code == 1  # no engine yet: not everything is ready
    assert "Es fehlt:" in out


def test_the_full_flow_ends_with_a_summary_and_starts(world: World) -> None:
    u, run, out = world
    _engine(u)
    scry = u.data / oc.SCRYFALL_FOLDER / "oracle-cards-1.jsonl.gz"
    scry.parent.mkdir(parents=True)
    scry.write_bytes(b"x")
    (u.repo / ".venv" / oc.PACKAGES_MARKER).write_text(oc.pakete_pruefsumme(u.repo), "utf-8")
    run.on(has("-version"), oc.Lauf(0, "", 'version "17.0.1"'))
    assert oc.ablauf(u, _args(), lambda: 99) == 0
    assert "Alles bereit." in out
    assert run.ran("serve")
    assert out.index("Alles bereit.") < next(i for i, s in enumerate(out) if "Ich starte" in s)


def test_a_data_folder_inside_the_repo_is_refused(world: World) -> None:
    u, run, _out = world
    u.data = u.repo / "daten"
    assert oc.ablauf(u, _args(), lambda: 0) == 2
    assert run.calls == []


def test_the_shortcut_is_asked_once(world: World) -> None:
    u, run, _out = world
    u.windows, u.interaktiv = True, True
    asked: list[str] = []

    def answer(prompt: str) -> str:
        asked.append(prompt)
        return "n"

    u.eingabe = answer
    oc.verknuepfung(u)
    oc.verknuepfung(u)
    assert len(asked) == 1
    assert not run.ran("powershell")


def test_default_data_folder_is_outside_the_repo_and_follows_the_environment(
    tmp_path: Path,
) -> None:
    assert oc.standard_datenordner({"COMMANDER_LAB_STUDIO_DATA": str(tmp_path)}, True) == tmp_path
    assert oc.standard_datenordner({"LOCALAPPDATA": str(tmp_path)}, True) == (
        tmp_path / "CommanderStudio"
    )
    assert oc.standard_datenordner({"COMMANDER_LAB_OWNER_DATA": str(tmp_path)}, False) == (
        tmp_path / "studio"
    )


def test_a_failed_editable_install_writes_no_marker_either(world: World) -> None:
    u, run, _out = world
    run.on(has("--no-build-isolation"), oc.Lauf(1))
    assert oc.richte_venv_ein(u, oc.Bericht(), nur_pruefen=False, neu=False) is False
    assert not (u.repo / ".venv" / oc.PACKAGES_MARKER).exists()


def test_a_yellow_line_alone_is_not_all_ready(world: World) -> None:
    u, _run, out = world
    bericht = oc.Bericht()
    oc.fasse_doctor_zusammen(u, bericht, _doctor_report(appcds_archive="WARN"))
    oc.zusammenfassung(u, bericht)
    assert not bericht.alles_bereit
    assert "Es fehlt:" in out and "Alles bereit." not in out


def test_a_fork_pull_request_run_from_a_branch_named_main_is_never_used(world: World) -> None:
    u, run, _out = world
    fork = _run(7, HEAD, event="pull_request", head_repository={"full_name": "x/fork"})
    run.on(has("api"), _runs(fork))
    run.on(lambda c: "actions/runs/7/artifacts" in " ".join(c), _arts(HEAD))
    picked, _reason = oc.waehle_artefakt(u, "gh", HEAD)
    assert picked is None


def test_a_locked_or_damaged_store_is_not_empty(world: World) -> None:
    u, run, _out = world
    u.data.mkdir(parents=True)
    (u.data / oc.DATABASE_NAME).write_bytes(b"this is not a sqlite database at all" * 40)
    scry = u.data / oc.SCRYFALL_FOLDER / "oracle-cards-1.jsonl.gz"
    scry.parent.mkdir(parents=True)
    scry.write_bytes(b"x")
    assert oc.datenordner_leer(u.data) is False
    oc.erstimport(u, oc.Bericht(), None, nur_pruefen=False)
    assert not run.ran("import-all")


def test_a_store_without_the_card_table_is_empty(world: World) -> None:
    u, _run, _out = world
    u.data.mkdir(parents=True)
    with sqlite3.connect(u.data / oc.DATABASE_NAME) as db:
        db.execute("CREATE TABLE meta (key TEXT)")
    db.close()
    assert oc.datenordner_leer(u.data) is True


def test_a_running_studio_stops_the_starter_before_any_change(world: World) -> None:
    u, run, out = world
    _gh_world(u, run)
    u.port_offen = lambda _port: True
    u.studio_antwortet = lambda _port: True
    assert oc.ablauf(u, _args(), lambda: 99) == 0
    joined = run.joined().split()
    for word in ("pull", "pip", "venv", "download", "serve", "import-all", "build-appcds"):
        assert word not in joined, word
    assert "BROWSER http://127.0.0.1:8765/" in out


def test_a_failed_copy_is_reported_not_raised(tmp_path: Path) -> None:
    blocked = tmp_path / "blocked"
    blocked.write_text("a file where the engine folder should be", encoding="utf-8")
    source = tmp_path / "x.jar"
    source.write_bytes(b"JAR")
    assert oc.stelle_bereit(source, blocked, _sha(b"JAR"), PIN, HEAD, gemeldet=True) is False


def test_a_store_locked_by_a_running_studio_is_not_empty(world: World) -> None:
    u, _run, _out = world
    u.data.mkdir(parents=True)
    holder = sqlite3.connect(u.data / oc.DATABASE_NAME)
    try:
        holder.execute("CREATE TABLE card (oracle_id TEXT)")
        holder.commit()
        holder.execute("BEGIN EXCLUSIVE")
        holder.execute("INSERT INTO card VALUES ('x')")
        assert oc.datenordner_leer(u.data) is False
    finally:
        holder.rollback()
        holder.close()


def test_the_handshake_runs_outside_the_repository(world: World) -> None:
    u, run, _out = world
    oc.engine_meldet_pin(u, "java", Path("x.jar"))
    cwd = Path(str(run.kwargs[-1]["cwd"]))
    assert not cwd.resolve().is_relative_to(u.repo.resolve())
    assert cwd.resolve().is_relative_to(u.data.resolve())


# --- negative tests from the reviews of #1766 --------------------------------------------


def test_eof_and_an_empty_answer_are_no(world: World) -> None:
    u, _run, _out = world
    u.interaktiv = True

    def eof(_prompt: str) -> str:
        raise EOFError

    u.eingabe = eof
    assert oc.frage(u, "Frage?") is False
    u.eingabe = lambda _prompt: ""
    assert oc.frage(u, "Frage?") is False


def test_a_missing_sha_file_makes_the_jar_invalid(world: World) -> None:
    u, _run, _out = world
    engine = _engine(u)
    (engine / oc.SHA_NAME).unlink()
    assert oc.jar_geprueft(engine, PIN)[0] is False


def _reply(commit: str, request_id: str = "studio-start-1") -> oc.Lauf:
    body = {"request_id": request_id, "success": True, "payload": {"engine_commit": commit}}
    return oc.Lauf(0, json.dumps(body) + "\n")


@pytest.mark.parametrize("answer", [_reply(OTHER_PIN), oc.Lauf(0, ""), oc.Lauf(1, "boom")])
def test_an_existing_jar_without_sidecars_and_a_wrong_or_silent_engine_stays_unverified(
    world: World, answer: oc.Lauf
) -> None:
    u, run, _out = world
    engine = _engine(u)
    for name in (oc.SHA_NAME, oc.PIN_NAME, oc.SOURCE_NAME):
        (engine / name).unlink()
    run.on(has("-jar"), answer)
    oc.sorge_fuer_engine(u, oc.Bericht(), PIN, "/usr/bin/java", nur_pruefen=False)
    assert not (engine / oc.SHA_NAME).exists() and not (engine / oc.PIN_NAME).exists()
    assert oc.jar_geprueft(engine, PIN)[0] is False


def test_maven_with_a_silent_engine_is_not_staged_and_drops_repository_override(
    world: World,
) -> None:
    u, run, _out = world
    tools = {"git": "g", "java": "j", "javac": "jc", "mvn": "mvn"}
    u.which = lambda name: tools.get(name)
    u.ja = True
    u.env["COMMANDER_LAB_XMAGE_REPOSITORY"] = "https://example.invalid/fork.git"
    jar = u.repo / oc.BUILT_JAR
    jar.parent.mkdir(parents=True)
    jar.write_bytes(b"BUILT")
    run.on(has("-jar"), oc.Lauf(0, ""))
    ok, _why = oc.baue_mit_maven(u, PIN, "/usr/bin/java")
    assert not ok and not (u.data / "engine" / oc.JAR_NAME).exists()
    env = next(kw["env"] for c, kw in zip(run.calls, run.kwargs, strict=True) if "bash" in c)
    assert "COMMANDER_LAB_XMAGE_REPOSITORY" not in env  # type: ignore[operator]


def test_a_failing_git_status_counts_as_not_clean(world: World) -> None:
    u, run, _out = world
    run.on(STATUS, oc.Lauf(128, ""))
    assert oc.aktualisiere_repo(u, oc.Bericht(), nur_pruefen=False) is False
    assert not run.ran("pull")


@pytest.mark.parametrize(
    ("upstream", "url"),
    [
        ("fork/feature", f"https://github.com/{oc.REPO_SLUG}.git"),
        ("origin/main", "https://github.com/someone/commander-playtest-lab.git"),
        ("origin/main", "https://example.invalid/moeendres-png/commander-playtest-lab"),
    ],
)
def test_pull_needs_main_of_the_official_repository(world: World, upstream: str, url: str) -> None:
    u, run, _out = world
    run.on(has("@{u}"), oc.Lauf(0, f"{upstream}\n"))
    run.on(has("remote", "get-url"), oc.Lauf(0, f"{url}\n"))
    bericht = oc.Bericht()
    assert oc.aktualisiere_repo(u, bericht, nur_pruefen=False) is False
    assert not run.ran("pull") and bericht.befunde[-1].farbe == oc.GELB


def test_a_pull_lists_what_came_in_and_names_ohne_update(world: World) -> None:
    u, run, out = world
    heads = iter([f"{HEAD}\n", f"{'d' * 40}\n"])
    run.on(lambda c: c[-2:] == ["rev-parse", "HEAD"], lambda _c, _k: oc.Lauf(0, next(heads)))
    run.on(has("rev-list", "--count"), oc.Lauf(0, "2\n"))
    run.on(has("log", "--format=%s"), oc.Lauf(0, "Erste Änderung\nZweite Änderung\n"))
    assert oc.aktualisiere_repo(u, oc.Bericht(), nur_pruefen=False) is True
    text = "\n".join(out)
    assert "2 neue Änderungen" in text and "Zweite Änderung" in text and "--ohne-update" in text


def test_winget_is_never_offered_in_nur_pruefen(world: World) -> None:
    u, run, _out = world
    _no_java(u)
    u.interaktiv, u.eingabe = True, (lambda _prompt: "J")
    oc.pruefe_java(u, oc.Bericht(), nur_pruefen=True)
    assert not run.ran("winget")


def test_an_artifact_named_for_another_commit_is_not_picked(world: World) -> None:
    u, run, _out = world
    run.on(has("api"), _runs(_run(8, HEAD)))
    run.on(lambda c: "actions/runs/8/artifacts" in " ".join(c), _arts("9" * 40))
    assert oc.waehle_artefakt(u, "gh", HEAD)[0] is None


def test_a_symlinked_file_in_the_artifact_is_refused(tmp_path: Path) -> None:
    folder = tmp_path / "a"
    _artifact_folder(folder)
    real = tmp_path / "pin.txt"
    real.write_text(PIN, encoding="utf-8")
    (folder / oc.PIN_NAME).unlink()
    (folder / oc.PIN_NAME).symlink_to(real)
    assert oc.pruefe_artefakt(folder, PIN)[0] is None


def test_a_copy_that_changes_on_the_way_is_not_activated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "x.jar"
    source.write_bytes(b"JAR")
    monkeypatch.setattr(oc.shutil, "copyfile", lambda _a, b: Path(b).write_bytes(b"EVIL"))
    engine = tmp_path / "engine"
    assert oc.stelle_bereit(source, engine, _sha(b"JAR"), PIN, HEAD, gemeldet=True) is False
    assert not (engine / oc.JAR_NAME).exists()


def test_soll_pin_needs_a_full_commit() -> None:
    assert oc.soll_pin({"expected_pin": "abc"}) is None
    assert oc.soll_pin({"expected_pin": PIN}) == PIN


def test_a_reply_to_another_request_does_not_count(world: World) -> None:
    u, run, _out = world
    run.on(has("-jar"), _reply(PIN, request_id="other"))
    assert oc.engine_meldet_pin(u, "java", Path("x.jar")) is None


def test_the_download_names_the_repository_and_the_restart_never_pulls(world: World) -> None:
    u, run, _out = world
    _gh_world(u, run)
    oc.hole_artefakt(u, PIN, None)
    download = next(c for c in run.calls if "download" in c)
    assert download[download.index("-R") + 1] == oc.REPO_SLUG
    cmd = oc.neustart_befehl("py", ["--ja", "--ohne-update"])
    assert cmd.count("--ohne-update") == 1 and cmd[-1] == "--ohne-update" and "--ja" in cmd


def test_an_artifact_whose_engine_stays_silent_is_not_staged(world: World) -> None:
    u, run, _out = world
    _gh_world(u, run)
    run.on(has("-jar"), oc.Lauf(0, ""))
    assert oc.sorge_fuer_engine(u, oc.Bericht(), PIN, "/usr/bin/java", nur_pruefen=False) is False
    assert not (u.data / "engine" / oc.JAR_NAME).exists()


def test_an_oversized_artifact_is_not_downloaded(world: World) -> None:
    u, run, _out = world
    _gh_world(u, run)
    big = {"name": f"{oc.ARTIFACT_PREFIX}1.25.0-{HEAD}", "expired": False, "size_in_bytes": 3 << 30}
    run.on(
        lambda c: "actions/runs/8/artifacts" in " ".join(c),
        oc.Lauf(0, json.dumps({"artifacts": [big]})),
    )
    assert oc.hole_artefakt(u, PIN, None)[0] is None
    assert not run.ran("run", "download")


def test_a_stale_bridge_asks_gh_and_a_foreign_artifact_is_only_yellow(world: World) -> None:
    u, run, _out = world
    newer = "e" * 40
    _gh_world(u, run, sha=newer)
    _engine(u)
    run.bridge = {HEAD: 1, newer: 1}  # both differ from HEAD's engine-bridge/
    bericht = oc.Bericht()
    assert oc.sorge_fuer_engine(u, bericht, PIN, None, nur_pruefen=False) is True
    assert run.ran("run", "download")
    assert bericht.befunde[-1].farbe == oc.GELB
    # the source is the artifact's commit, not the local HEAD
    assert (u.data / "engine" / oc.SOURCE_NAME).read_text(encoding="utf-8").strip() == newer


def test_a_stale_bridge_without_a_new_package_stays_yellow_and_is_kept(world: World) -> None:
    u, run, _out = world
    _engine(u)
    run.bridge = {HEAD: 1}
    bericht = oc.Bericht()
    assert oc.sorge_fuer_engine(u, bericht, PIN, None, nur_pruefen=False) is False
    assert bericht.befunde[-1].farbe == oc.GELB
    assert (u.data / "engine" / oc.JAR_NAME).is_file()
    assert not run.ran("mvn")


def test_a_fallback_install_stays_yellow_and_retries_the_lock(world: World) -> None:
    u, run, _out = world
    marker = u.repo / ".venv" / oc.PACKAGES_MARKER
    marker.write_text(f"{oc.pakete_pruefsumme(u.repo)} api\n", encoding="utf-8")
    run.on(has("--require-hashes"), oc.Lauf(1))
    bericht = oc.Bericht()
    assert oc.richte_venv_ein(u, bericht, nur_pruefen=False, neu=False) is True
    assert run.ran("--require-hashes")
    assert bericht.befunde[-1].farbe == oc.GELB


def test_unreadable_java_version_damaged_store_and_own_engine_command_are_yellow(
    world: World,
) -> None:
    u, run, _out = world
    run.on(has("-version"), oc.Lauf(1, "", "kaputt"))
    bericht = oc.Bericht()
    oc.pruefe_java(u, bericht, nur_pruefen=False)
    assert bericht.befunde[-1].farbe == oc.GELB
    u.data.mkdir(parents=True)
    (u.data / oc.DATABASE_NAME).write_bytes(b"not a database" * 100)
    oc.erstimport(u, bericht, None, nur_pruefen=False)
    assert bericht.befunde[-1].farbe == oc.GELB
    u.env[oc.ENGINE_COMMAND_ENV] = "java -jar x.jar full-game"
    oc.sorge_fuer_engine(u, bericht, PIN, None, nur_pruefen=False)
    assert bericht.befunde[-1].farbe == oc.GELB


def test_the_shortcut_is_never_made_by_ja_alone_and_never_overwritten(world: World) -> None:
    u, run, _out = world
    u.windows, u.ja = True, True
    oc.verknuepfung(u)
    assert not run.ran("powershell")
    u.interaktiv, u.eingabe = True, (lambda _prompt: "J")
    oc.verknuepfung(u)
    script = next(c for c in run.calls if "powershell" in c)[-1]
    assert "Test-Path" in script and "exit 3" in script


# --- second delta review of #1766: freshness, caught-up handshake, no repeated download -----


def test_three_starts_with_no_newer_package_download_exactly_once(world: World) -> None:
    u, run, _out = world
    _gh_world(u, run, sha=HEAD)
    run.bridge = {HEAD: 1}  # the release run for the current code is not there yet
    results = []
    for _start in range(3):
        bericht = oc.Bericht()
        results.append(oc.sorge_fuer_engine(u, bericht, PIN, None, nur_pruefen=False))
        assert bericht.befunde[-1].farbe != oc.GRUEN
    assert sum(1 for c in run.calls if c[1:3] == ["run", "download"]) == 1
    assert results == [True, False, False]


def test_a_package_staged_without_java_is_never_green_until_the_engine_answers(
    world: World,
) -> None:
    u, run, _out = world
    _gh_world(u, run)
    bericht = oc.Bericht()
    assert oc.sorge_fuer_engine(u, bericht, PIN, None, nur_pruefen=False) is True
    assert bericht.befunde[-1].farbe == oc.GELB
    engine = u.data / "engine"
    assert oc._first_token(engine / oc.CONFIRM_NAME) == "nein"
    bericht = oc.Bericht()
    oc.sorge_fuer_engine(u, bericht, PIN, None, nur_pruefen=False)
    assert bericht.befunde[-1].farbe == oc.GELB  # still no Java: at most yellow
    run.on(has("-jar"), _reply(OTHER_PIN))
    bericht = oc.Bericht()
    oc.sorge_fuer_engine(u, bericht, PIN, "/usr/bin/java", nur_pruefen=False)
    assert oc._first_token(engine / oc.CONFIRM_NAME) != PIN
    assert bericht.befunde[-1].farbe != oc.GRUEN
    run.on(has("-jar"), _reply(PIN))
    _engine(u)
    (engine / oc.CONFIRM_NAME).write_text("nein\n", encoding="utf-8")
    bericht = oc.Bericht()
    oc.sorge_fuer_engine(u, bericht, PIN, "/usr/bin/java", nur_pruefen=False)
    assert oc._first_token(engine / oc.CONFIRM_NAME) == PIN
    assert bericht.befunde[-1].farbe == oc.GRUEN


def test_freshness_asks_git_exactly_for_engine_bridge_at_the_recorded_source(
    world: World,
) -> None:
    u, run, _out = world
    _engine(u)
    source = "f" * 40
    (u.data / "engine" / oc.SOURCE_NAME).write_text(f"{source}\n", encoding="utf-8")
    run.bridge = {source: 0}
    bericht = oc.Bericht()
    oc.sorge_fuer_engine(u, bericht, PIN, None, nur_pruefen=False)
    assert bericht.befunde[-1].farbe == oc.GRUEN
    diff = next(c for c in run.calls if c[3:5] == ["diff", "--quiet"])
    git = ["/usr/bin/git", "-C", str(u.repo)]
    assert diff == [*git, "diff", "--quiet", source, "HEAD", "--", "engine-bridge/"]


def test_an_unknown_source_commit_is_never_green(world: World) -> None:
    u, run, _out = world
    _engine(u)
    run.bridge = {}  # git answers 128: commit unknown here
    bericht = oc.Bericht()
    oc.sorge_fuer_engine(u, bericht, PIN, None, nur_pruefen=False)
    assert bericht.befunde[-1].farbe == oc.GELB


def test_a_non_sha_source_never_reaches_git_and_an_adopted_jar_does_not_claim_head(
    world: World,
) -> None:
    u, run, _out = world
    engine = _engine(u)
    for name in (oc.SHA_NAME, oc.PIN_NAME, oc.SOURCE_NAME, oc.CONFIRM_NAME):
        (engine / name).unlink()
    run.on(has("-jar"), _reply(PIN))
    bericht = oc.Bericht()
    oc.sorge_fuer_engine(u, bericht, PIN, "/usr/bin/java", nur_pruefen=False)
    assert oc._first_token(engine / oc.SOURCE_NAME) == "unbekannt"
    assert not any(c[3:5] == ["diff", "--quiet"] for c in run.calls)
    assert all(item.farbe != oc.GRUEN for item in bericht.befunde)


def test_nur_pruefen_colours_a_stale_jar_yellow_and_a_missing_one_red(world: World) -> None:
    u, run, _out = world
    _engine(u)
    run.bridge = {HEAD: 1}
    bericht = oc.Bericht()
    oc.sorge_fuer_engine(u, bericht, PIN, None, nur_pruefen=True)
    assert bericht.befunde[-1].farbe == oc.GELB
    (u.data / "engine" / oc.JAR_NAME).unlink()
    bericht = oc.Bericht()
    oc.sorge_fuer_engine(u, bericht, PIN, None, nur_pruefen=True)
    assert bericht.befunde[-1].farbe == oc.ROT
    assert not run.ran("run", "download")


def test_an_oversized_jar_in_the_package_is_not_activated(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    u, run, _out = world
    _gh_world(u, run)
    monkeypatch.setattr(oc, "MAX_JAR_BYTES", 2)
    assert oc.hole_artefakt(u, PIN, None)[0] is None
    assert not (u.data / "engine" / oc.JAR_NAME).exists()


def test_a_fallback_install_is_never_green_in_the_same_run(world: World) -> None:
    u, run, _out = world
    u.ja = True
    run.on(has("--require-hashes"), oc.Lauf(1))
    bericht = oc.Bericht()
    assert oc.richte_venv_ein(u, bericht, nur_pruefen=False, neu=False) is True
    assert run.ran("-e", ".[api]")
    assert bericht.befunde[-1].farbe == oc.GELB


@pytest.mark.parametrize(
    "url",
    [
        "https://notgithub.com/moeendres-png/commander-playtest-lab.git",
        "https://evil.example/x/github.com/moeendres-png/commander-playtest-lab.git",
    ],
)
def test_lookalike_remote_urls_do_not_pull(world: World, url: str) -> None:
    u, run, _out = world
    run.on(has("remote", "get-url"), oc.Lauf(0, f"{url}\n"))
    assert oc.aktualisiere_repo(u, oc.Bericht(), nur_pruefen=False) is False
    assert not run.ran("pull")


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/moeendres-png/commander-playtest-lab.git",
        "https://github.com/moeendres-png/commander-playtest-lab",
        "git@github.com:moeendres-png/commander-playtest-lab.git",
        "ssh://git@github.com/moeendres-png/commander-playtest-lab.git",
    ],
)
def test_the_official_remote_spellings_pull(world: World, url: str) -> None:
    u, run, _out = world
    run.on(has("remote", "get-url"), oc.Lauf(0, f"{url}\n"))
    oc.aktualisiere_repo(u, oc.Bericht(), nur_pruefen=False)
    assert run.ran("pull", "--ff-only")
