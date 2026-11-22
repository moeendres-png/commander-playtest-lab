"""The one-click starter (``commander_lab.studio.oneclick``) with fake processes and folders.

Every guard the Owner asked for has a test that fails when the guard is removed: no pull on a
dirty or foreign branch, no install without a typed "J", no JAR without pin and checksum check,
no start when the port is taken, no token in the output, no write in ``--nur-pruefen``.
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
SECRET = "ghp_SECRETSECRETSECRET"

Rule = tuple[
    Callable[[list[str]], bool], oc.Lauf | Callable[[list[str], dict[str, object]], oc.Lauf]
]


class FakeRun:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.kwargs: list[dict[str, object]] = []
        self.rules: list[Rule] = []

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
        for match, result in self.rules:
            if match(cmd):
                return result(cmd, kwargs) if callable(result) else result
        return oc.Lauf(0)

    def ran(self, *words: str) -> bool:
        return any(all(word in call for word in words) for call in self.calls)

    def joined(self) -> str:
        return "\n".join(" ".join(call) for call in self.calls)


World = tuple[oc.Umgebung, FakeRun, list[str]]


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
    run.on(has("status", "--porcelain"), oc.Lauf(0, ""))
    run.on(has("@{u}"), oc.Lauf(0, "origin/main\n"))
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
        (has("status", "--porcelain"), oc.Lauf(0, " M src/x.py\n")),
        (has("status", "--porcelain"), oc.Lauf(0, "?? meine_notiz.txt\n")),
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
        "repository": {"full_name": oc.REPO_SLUG},
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
            _run(3, "3" * 40, repository={"full_name": "someone/fork"}),
            _run(4, "4" * 40, path=".github/workflows/other.yml"),
            _run(5, "5" * 40),
        ),
    )
    run.on(lambda c: "actions/runs/5/artifacts" in " ".join(c), _arts("5" * 40, expired=True))
    picked, _reason = oc.waehle_artefakt(u, "gh", HEAD)
    assert picked is None
    assert not any("runs/1/" in c or "runs/2/" in c or "runs/3/" in c for c in run.joined().split())


def test_artifact_choice_prefers_the_local_head(world: World) -> None:
    u, run, _out = world
    run.on(has("api"), _runs(_run(9, "9" * 40), _run(8, HEAD)))
    run.on(lambda c: "actions/runs/8/artifacts" in " ".join(c), _arts(HEAD))
    run.on(lambda c: "actions/runs/9/artifacts" in " ".join(c), _arts("9" * 40))
    picked, _reason = oc.waehle_artefakt(u, "gh", HEAD)
    assert picked is not None and picked.run_id == 8


def _gh_world(u: oc.Umgebung, run: FakeRun, *, pin: str = PIN) -> None:
    tools = {"git": "/usr/bin/git", "java": "/usr/bin/java", "gh": "gh"}
    u.which = lambda name: tools.get(name)
    run.on(has("api"), _runs(_run(8, HEAD)))
    run.on(lambda c: "actions/runs/8/artifacts" in " ".join(c), _arts(HEAD))

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
    run.calls.clear()
    oc.erstimport(u, oc.Bericht(), None, nur_pruefen=False)
    assert not run.ran("import-all")


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
