"""Ein-Klick-Einrichtung und Start des Commander Studio.

``python -m commander_lab.studio.oneclick`` (unter Windows über ``Studio starten.cmd`` im
Repo-Hauptordner, unter Linux/WSL über ``scripts/studio_oneclick.sh``) erledigt in acht Schritten,
was ``docs/STUDIO_OWNER_PC_SETUP.md`` von Hand beschreibt:

1. Python 3.12+ und Java 17+ prüfen (fehlt Java, wird der winget-Befehl genannt und nur nach
   ausdrücklichem „J“ ausgeführt; ``--ja`` beantwortet diese Frage nie);
2. das Repository mit ``git pull --ff-only`` aktualisieren, nur auf ``main`` mit sauberem
   Arbeitsbaum und Upstream; nie ``reset``, nie ``stash``;
3. ``.venv`` anlegen und die Pakete aus ``requirements/lock.txt`` installieren, nur wenn sich die
   Prüfsumme von Lock-Datei und ``pyproject.toml`` seit dem letzten erfolgreichen Lauf geändert hat;
4. die Engine-JAR bereitstellen: eine geprüfte JAR im Datenordner bleibt; sonst das neueste
   erfolgreiche Artefakt von ``release-artifacts.yml`` auf ``main`` über ``gh`` (Prüfsummen und
   ``ENGINE_PIN.txt`` gegen den Pin aus ``config/rules_engines.json``, den ``doctor`` meldet); sonst,
   nur nach Bestätigung, der Eigenbau mit Maven (Pin-Nachweis über die Antwort der Engine selbst);
   eine JAR ohne Pin- und Prüfsummen-Abgleich gilt nie als gültig;
5. ``build-appcds``, wenn die JAR neu ist oder das Archiv fehlt oder nicht passt;
6. ``doctor`` und eine Zusammenfassung in einfachem Deutsch (grün/gelb/rot);
7. ``import-all --from-repo`` für Chulane, solange der Datenordner leer ist (die Scryfall-Datei
   wird nie heruntergeladen, sie muss im Ordner ``kartendaten`` liegen);
8. ``serve --open`` auf 127.0.0.1; läuft das Studio schon, öffnet es nur den Browser.

Das Modul selbst importiert beim Laden nur die Standardbibliothek: es läuft mit dem System-Python,
bevor ``.venv`` existiert. Alles, was Pakete braucht, läuft als Kindprozess mit dem Python aus
``.venv``. Netz: nur ``git pull`` und der Artefakt-Download über ``gh``; keine Preise, keine
Telemetrie; Tokens werden weder gelesen noch ausgegeben.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import urllib.request
import webbrowser
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

REPO_SLUG = "moeendres-png/commander-playtest-lab"
RELEASE_WORKFLOW = "release-artifacts.yml"
RELEASE_WORKFLOW_PATH = ".github/workflows/release-artifacts.yml"
ARTIFACT_PREFIX = "commander-playtest-lab-release-"
JAR_NAME = "xmage-engine-bridge.jar"
SHA_NAME = f"{JAR_NAME}.sha256"
PIN_NAME = "ENGINE_PIN.txt"
SUMS_NAME = "PLAYTEST_LAB_SHA256SUMS.txt"
BUILT_JAR = Path("engine-bridge") / "target" / "xmage-engine-bridge-0.1.0-SNAPSHOT.jar"
ENGINE_COMMAND_ENV = "COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD"
STUDIO_DATA_ENV = "COMMANDER_LAB_STUDIO_DATA"
OWNER_DATA_ENV = "COMMANDER_LAB_OWNER_DATA"
DATABASE_NAME = "studio.sqlite3"
MIN_PYTHON = (3, 12)
MIN_JAVA = 17
DEFAULT_PORT = 8765
COMMANDER = "Chulane, Teller of Tales"
SCRYFALL_FOLDER = "kartendaten"
SCRYFALL_PATTERN = re.compile(r"^oracle-cards.*\.jsonl(?:\.gz)?$")
STATE_FOLDER = "einrichten"
IMPORT_MARKER = "erstimport-fertig.json"
SHORTCUT_STATE = "verknuepfung.json"
PACKAGES_MARKER = "studio-pakete.sha256"
WINGET_JAVA = ("winget", "install", "--id", "EclipseAdoptium.Temurin.17.JDK", "-e")
WINGET_PYTHON = ("winget", "install", "--id", "Python.Python.3.12", "-e")
WINGET_GH = ("winget", "install", "--id", "GitHub.cli", "-e")
HANDSHAKE_TIMEOUT = 180
_SHA40 = re.compile(r"[0-9a-f]{40}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_JAVA_VERSION = re.compile(r'version "(\d+)(?:\.(\d+))?')

GRUEN, GELB, ROT = "grün", "gelb", "rot"
SCHRITTE = 8


@dataclass
class Lauf:
    """Result of one child process (stdout/stderr only when captured)."""

    returncode: int
    stdout: str = ""
    stderr: str = ""


Runner = Callable[..., Lauf]


def _run_real(
    cmd: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    capture: bool = True,
    timeout: float | None = None,
    stdin_text: str | None = None,
) -> Lauf:
    try:
        done = subprocess.run(  # fixed argument lists, never a shell
            list(cmd),
            cwd=str(cwd) if cwd else None,
            env=dict(env) if env is not None else None,
            capture_output=capture,
            input=stdin_text,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return Lauf(127, "", f"{type(error).__name__}")
    return Lauf(done.returncode, done.stdout or "", done.stderr or "")


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _studio_answers(port: int) -> bool:
    """True when the page on 127.0.0.1:port is the Commander Studio (no proxy, local only)."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"http://127.0.0.1:{port}/", timeout=2) as response:
            body = response.read(4096).decode("utf-8", errors="replace")
    except (OSError, ValueError):
        return False
    return "<title>Commander Studio</title>" in body


@dataclass
class Umgebung:
    """Everything the steps touch outside of pure logic; tests replace each part."""

    repo: Path
    data: Path
    windows: bool
    interaktiv: bool
    ja: bool
    env: dict[str, str]
    run: Runner = _run_real
    which: Callable[[str], str | None] = shutil.which
    eingabe: Callable[[str], str] = input
    sagen: Callable[[str], None] = print
    port_offen: Callable[[int], bool] = _port_open
    studio_antwortet: Callable[[int], bool] = _studio_answers
    browser: Callable[[str], object] = webbrowser.open
    python_version: tuple[int, int] = (sys.version_info[0], sys.version_info[1])
    python_exe: str = sys.executable


@dataclass
class Befund:
    bereich: str
    farbe: str
    satz: str
    naechstes: str | None = None


@dataclass
class Bericht:
    befunde: list[Befund] = field(default_factory=list)

    def add(self, bereich: str, farbe: str, satz: str, naechstes: str | None = None) -> None:
        self.befunde.append(Befund(bereich, farbe, satz, naechstes))

    @property
    def alles_bereit(self) -> bool:
        return all(item.farbe == GRUEN for item in self.befunde)


# --- small helpers -------------------------------------------------------------------------


def frage(u: Umgebung, text: str, *, installation: bool = False) -> bool:
    """Ask J/N. ``--ja`` answers yes, except for a program installation (winget), which always
    needs a typed "J" in a console. Without a console every answer is no."""
    if u.ja and not installation:
        u.sagen(f"{text} (J/N): J (wegen --ja)")
        return True
    if not u.interaktiv:
        u.sagen(f"{text} (J/N): N (keine Eingabe möglich)")
        return False
    try:
        answer = u.eingabe(f"{text} (J/N): ")
    except EOFError:
        return False
    return answer.strip().lower() in {"j", "ja", "y", "yes"}


def fehlt(u: Umgebung, was: str, als_naechstes: str) -> None:
    u.sagen(f"  Das fehlt noch: {was}")
    u.sagen(f"  Das mache ich als Nächstes: {als_naechstes}")


def sha256_datei(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def venv_python(repo: Path, windows: bool) -> Path:
    return repo / ".venv" / ("Scripts/python.exe" if windows else "bin/python")


def kind_env(u: Umgebung) -> dict[str, str]:
    env = dict(u.env)
    env[STUDIO_DATA_ENV] = str(u.data)
    env["PYTHONPATH"] = str(u.repo / "src")
    env["PYTHONUTF8"] = "1"
    return env


def standard_datenordner(env: Mapping[str, str], windows: bool) -> Path:
    explicit = env.get(STUDIO_DATA_ENV, "").strip()
    if explicit:
        return Path(explicit).expanduser()
    owner = env.get(OWNER_DATA_ENV, "").strip()
    if owner:
        return Path(owner).expanduser() / "studio"
    if windows and env.get("LOCALAPPDATA", "").strip():
        return Path(env["LOCALAPPDATA"]) / "CommanderStudio"
    return Path.home() / ".local" / "share" / "commander-studio"


def parse_java_major(text: str) -> int | None:
    match = _JAVA_VERSION.search(text)
    if match is None:
        return None
    major = int(match.group(1))
    if major == 1 and match.group(2) is not None:
        return int(match.group(2))
    return major


def finde_java(u: Umgebung) -> str | None:
    found = u.which("java")
    if found:
        return found
    home = u.env.get("JAVA_HOME", "").strip()
    if home:
        candidate = Path(home) / "bin" / ("java.exe" if u.windows else "java")
        if candidate.is_file():
            return str(candidate)
    return None


# --- step 1: Python and Java ---------------------------------------------------------------


def pruefe_python(u: Umgebung, bericht: Bericht) -> bool:
    version = ".".join(str(part) for part in u.python_version)
    if u.python_version >= MIN_PYTHON:
        u.sagen(f"  Python {version} ist da.")
        bericht.add("Python", GRUEN, f"Python {version} ist installiert.")
        return True
    command = " ".join(WINGET_PYTHON)
    fehlt(u, f"Python 3.12 oder neuer (gefunden: {version}).", f"nichts; installiere: {command}")
    bericht.add(
        "Python",
        ROT,
        f"Python {version} ist zu alt.",
        f"Python 3.12 installieren ({command}) und den Starter neu öffnen.",
    )
    return False


def pruefe_java(u: Umgebung, bericht: Bericht, *, nur_pruefen: bool) -> str | None:
    java = finde_java(u)
    major: int | None = None
    if java:
        probe = u.run([java, "-version"], capture=True, timeout=20)
        major = parse_java_major(f"{probe.stderr}\n{probe.stdout}")
    if java and (major is None or major >= MIN_JAVA):
        shown = f"Java {major}" if major is not None else "Java (Version nicht lesbar)"
        u.sagen(f"  {shown} ist da.")
        bericht.add("Java", GRUEN, f"{shown} ist installiert.")
        return java
    command = " ".join(WINGET_JAVA)
    reason = "Java 17 oder neuer" if not java else f"Java 17 oder neuer (gefunden: {major})"
    if not u.windows:
        fehlt(u, f"{reason}.", "Java mit der Paketverwaltung installieren (z. B. openjdk-17-jdk).")
        bericht.add(
            "Java",
            ROT,
            f"{reason} fehlt; ohne Java gibt es keine Partien und keine Serien.",
            "Java 17 installieren (z. B. Paket openjdk-17-jdk) und neu starten.",
        )
        return None
    fehlt(u, f"{reason}.", f"dir anbieten, Java zu installieren: {command}")
    if (
        not nur_pruefen
        and u.which("winget")
        and frage(u, f"Soll ich Java jetzt installieren ({command})?", installation=True)
    ):
        done = u.run(list(WINGET_JAVA), capture=False)
        if done.returncode == 0:
            u.sagen("  Java wurde installiert. Schließe dieses Fenster und starte neu.")
            bericht.add(
                "Java",
                GELB,
                "Java wurde gerade installiert und ist erst nach einem Neustart des Starters sichtbar.",
                "Fenster schließen und „Studio starten“ noch einmal öffnen.",
            )
            return None
        u.sagen("  Die Installation von Java hat nicht geklappt.")
    bericht.add(
        "Java",
        ROT,
        f"{reason} fehlt; ohne Java gibt es keine Partien und keine Serien.",
        f"In einer Eingabeaufforderung ausführen: {command}, dann neu starten.",
    )
    return None


# --- step 2: update the repository ---------------------------------------------------------


def aktualisiere_repo(u: Umgebung, bericht: Bericht, *, nur_pruefen: bool) -> bool:
    """``git pull --ff-only`` only on a clean ``main`` with an upstream. Returns True when HEAD
    moved (the caller then restarts itself so the new code runs)."""
    git = u.which("git")
    if not git or not (u.repo / ".git").exists():
        u.sagen("  Kein Git gefunden; ich überspringe das Aktualisieren.")
        bericht.add(
            "Aktualisieren",
            GELB,
            "Das Programm wurde nicht aktualisiert (Git fehlt).",
            "Git installieren (winget install --id Git.Git -e).",
        )
        return False

    def g(*args: str, capture: bool = True) -> Lauf:
        return u.run([git, "-C", str(u.repo), *args], capture=capture, timeout=300)

    branch = g("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if branch != "main":
        u.sagen(
            f"  Du bist auf dem Zweig „{branch or '?'}“, nicht auf main; ich aktualisiere nicht."
        )
        bericht.add(
            "Aktualisieren",
            GELB,
            f"Nicht aktualisiert: der Zweig ist „{branch or '?'}“, nicht main.",
            "Auf main wechseln, wenn du den neuesten Stand willst.",
        )
        return False
    status = g("status", "--porcelain")
    if status.returncode != 0 or status.stdout.strip():
        u.sagen("  Im Ordner gibt es geänderte Dateien; ich aktualisiere nicht und ändere nichts.")
        bericht.add(
            "Aktualisieren",
            GELB,
            "Nicht aktualisiert: im Programmordner gibt es geänderte oder neue Dateien.",
            "Die Dateien prüfen (git status); der Starter fasst sie nicht an.",
        )
        return False
    upstream = g("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if upstream.returncode != 0 or not upstream.stdout.strip():
        u.sagen("  Der Zweig main hat keine Gegenstelle; ich aktualisiere nicht.")
        bericht.add("Aktualisieren", GELB, "Nicht aktualisiert: main hat keine Gegenstelle.")
        return False
    if nur_pruefen:
        u.sagen("  Aktualisieren wäre möglich (nur prüfen: nichts geändert).")
        bericht.add("Aktualisieren", GRUEN, "Aktualisieren ist möglich (nicht ausgeführt).")
        return False
    before = g("rev-parse", "HEAD").stdout.strip()
    pulled = g("pull", "--ff-only", capture=False)
    if pulled.returncode != 0:
        u.sagen("  Das Aktualisieren hat nicht geklappt; ich arbeite mit dem bisherigen Stand.")
        bericht.add(
            "Aktualisieren",
            GELB,
            "Das Aktualisieren hat nicht geklappt (kein Netz oder abweichender Stand).",
            "Später noch einmal starten; der bisherige Stand bleibt.",
        )
        return False
    after = g("rev-parse", "HEAD").stdout.strip()
    if after and after != before:
        u.sagen("  Neuer Stand geholt.")
        return True
    u.sagen("  Das Programm ist schon auf dem neuesten Stand.")
    bericht.add("Aktualisieren", GRUEN, "Das Programm ist auf dem neuesten Stand.")
    return False


# --- step 3: virtual environment and packages ----------------------------------------------


def pakete_pruefsumme(repo: Path) -> str:
    digest = hashlib.sha256()
    for name in ("requirements/lock.txt", "pyproject.toml"):
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update((repo / name).read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def richte_venv_ein(u: Umgebung, bericht: Bericht, *, nur_pruefen: bool, neu: bool) -> bool:
    py = venv_python(u.repo, u.windows)
    if not py.is_file():
        if nur_pruefen:
            fehlt(u, "die Python-Umgebung .venv.", "nichts (nur prüfen).")
            bericht.add(
                "Python-Pakete",
                ROT,
                "Die Python-Umgebung .venv fehlt noch.",
                "Den Starter ohne --nur-pruefen laufen lassen.",
            )
            return False
        fehlt(u, "die Python-Umgebung .venv.", "sie im Programmordner anlegen.")
        made = u.run([u.python_exe, "-m", "venv", str(u.repo / ".venv")], capture=False)
        if made.returncode != 0 or not py.is_file():
            bericht.add(
                "Python-Pakete",
                ROT,
                "Die Python-Umgebung .venv ließ sich nicht anlegen.",
                "Python 3.12 neu installieren und den Starter neu öffnen.",
            )
            return False
    probe = u.run(
        [str(py), "-c", "import sys; print('%d.%d' % sys.version_info[:2])"],
        capture=True,
        timeout=60,
    )
    parts = probe.stdout.strip().split(".")
    ok = probe.returncode == 0 and len(parts) == 2 and all(p.isdigit() for p in parts)
    if not ok or (int(parts[0]), int(parts[1])) < MIN_PYTHON:
        bericht.add(
            "Python-Pakete",
            ROT,
            "Die Python-Umgebung .venv ist beschädigt oder zu alt.",
            "Den Ordner .venv umbenennen (z. B. in .venv-alt) und den Starter neu öffnen.",
        )
        return False
    marker = u.repo / ".venv" / PACKAGES_MARKER
    wanted = pakete_pruefsumme(u.repo)
    recorded = marker.read_text(encoding="utf-8").split()[0] if marker.is_file() else ""
    if recorded == wanted and not neu:
        u.sagen("  Die Python-Pakete sind aktuell.")
        bericht.add("Python-Pakete", GRUEN, "Die Python-Pakete sind installiert und aktuell.")
        return True
    if nur_pruefen:
        fehlt(u, "aktuelle Python-Pakete.", "nichts (nur prüfen).")
        bericht.add(
            "Python-Pakete",
            GELB,
            "Die Python-Pakete müssen neu installiert werden.",
            "Den Starter ohne --nur-pruefen laufen lassen.",
        )
        return True
    fehlt(u, "aktuelle Python-Pakete.", "sie aus requirements/lock.txt installieren.")
    env = kind_env(u)
    pip = [str(py), "-m", "pip", "install", "--disable-pip-version-check"]
    lock = u.run(
        [*pip, "--require-hashes", "-r", str(u.repo / "requirements" / "lock.txt")],
        cwd=u.repo,
        env=env,
        capture=False,
    )
    weg = "lock"
    if lock.returncode != 0:
        u.sagen("  Die Installation aus der Lock-Datei hat nicht geklappt.")
        if not frage(u, 'Soll ich stattdessen pip install -e ".[api]" versuchen?'):
            bericht.add(
                "Python-Pakete",
                ROT,
                "Die Python-Pakete ließen sich nicht installieren.",
                "Die Meldungen von pip oben lesen; Netz prüfen und neu starten.",
            )
            return False
        weg = "api"
        done = u.run([*pip, "-e", ".[api]"], cwd=u.repo, env=env, capture=False)
    else:
        done = u.run(
            [*pip, "--no-deps", "--no-build-isolation", "-e", "."],
            cwd=u.repo,
            env=env,
            capture=False,
        )
    if done.returncode != 0:
        bericht.add(
            "Python-Pakete",
            ROT,
            "Die Python-Pakete ließen sich nicht vollständig installieren.",
            "Die Meldungen von pip oben lesen; Netz prüfen und neu starten.",
        )
        return False
    marker.write_text(f"{wanted} {weg}\n", encoding="utf-8")
    u.sagen("  Die Python-Pakete sind installiert.")
    bericht.add("Python-Pakete", GRUEN, "Die Python-Pakete sind installiert und aktuell.")
    return True


# --- doctor (used for the pin and for step 6) ----------------------------------------------


def doctor(u: Umgebung) -> dict[str, object] | None:
    py = venv_python(u.repo, u.windows)
    if not py.is_file():
        return None
    done = u.run(
        [str(py), "-m", "commander_lab.studio", "--data", str(u.data), "doctor", "--json"],
        cwd=u.repo,
        env=kind_env(u),
        capture=True,
        timeout=300,
    )
    try:
        report = json.loads(done.stdout)
    except ValueError:
        return None
    return report if isinstance(report, dict) and isinstance(report.get("checks"), list) else None


def soll_pin(report: dict[str, object] | None) -> str | None:
    pin = report.get("expected_pin") if report else None
    return pin if isinstance(pin, str) and _SHA40.fullmatch(pin) else None


def doctor_check(report: dict[str, object] | None, name: str) -> dict[str, object]:
    checks = report.get("checks") if report else None
    if isinstance(checks, list):
        for entry in checks:
            if isinstance(entry, dict) and entry.get("name") == name:
                return entry
    return {}


# --- step 4: engine JAR --------------------------------------------------------------------


def _first_token(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return ""
    return text.split()[0].lower() if text else ""


def jar_geprueft(engine_dir: Path, pin: str) -> tuple[bool, str]:
    """(valid, reason): the JAR, its recomputed SHA-256 equal to the ``.sha256`` sidecar, and
    ``ENGINE_PIN.txt`` equal to ``pin``. Anything else is not valid."""
    jar = engine_dir / JAR_NAME
    if not jar.is_file():
        return False, "keine Engine-Datei im Datenordner"
    recorded = _first_token(engine_dir / SHA_NAME)
    if not _SHA256.fullmatch(recorded):
        return False, "Prüfsummen-Datei fehlt oder ist unlesbar"
    if sha256_datei(jar) != recorded:
        return False, "Prüfsumme passt nicht zur Engine-Datei"
    if _first_token(engine_dir / PIN_NAME) != pin:
        return False, "Engine-Version (Pin) passt nicht oder fehlt"
    return True, "Engine-Datei geprüft (Prüfsumme und Pin passen)"


def engine_meldet_pin(u: Umgebung, java: str, jar: Path) -> str | None:
    """The ``engine_commit`` the bridge itself reports (``get_provider_version``), or None."""
    requests = (
        '{"request_id":"studio-start-1","protocol_version":"2.0.0",'
        '"message_type":"get_provider_version"}\n'
        '{"request_id":"studio-start-2","protocol_version":"2.0.0",'
        '"message_type":"shutdown_engine"}\n'
    )
    done = u.run(
        [java, "-jar", str(jar), "full-game"],
        capture=True,
        timeout=HANDSHAKE_TIMEOUT,
        stdin_text=requests,
    )
    for line in done.stdout.splitlines():
        try:
            reply = json.loads(line)
        except ValueError:
            continue
        if not isinstance(reply, dict) or reply.get("request_id") != "studio-start-1":
            continue
        payload = reply.get("payload")
        commit = payload.get("engine_commit") if isinstance(payload, dict) else None
        if reply.get("success") and isinstance(commit, str) and _SHA40.fullmatch(commit):
            return commit
    return None


def stelle_bereit(source: Path, engine_dir: Path, sha: str, pin: str) -> None:
    """Copy a verified JAR next to its sidecars: temp file in the same folder, re-hash, replace."""
    engine_dir.mkdir(parents=True, exist_ok=True)
    temp = engine_dir / f"{JAR_NAME}.neu"
    shutil.copyfile(source, temp)
    if sha256_datei(temp) != sha:
        temp.unlink()
        raise RuntimeError("Prüfsumme nach dem Kopieren verschieden")
    os.replace(temp, engine_dir / JAR_NAME)
    for name, text in ((SHA_NAME, f"{sha}  {JAR_NAME}\n"), (PIN_NAME, f"{pin}\n")):
        part = engine_dir / f"{name}.neu"
        part.write_text(text, encoding="utf-8")
        os.replace(part, engine_dir / name)


def _gh_json(u: Umgebung, gh: str, route: str) -> object:
    done = u.run([gh, "api", route], capture=True, timeout=120, env=u.env)
    if done.returncode != 0:
        return None
    try:
        return json.loads(done.stdout)
    except ValueError:
        return None


@dataclass(frozen=True)
class Artefakt:
    run_id: int
    name: str
    head_sha: str
    size: int


def waehle_artefakt(u: Umgebung, gh: str, local_head: str) -> tuple[Artefakt | None, str]:
    """The newest usable release artifact on main, preferring the run built from
    ``local_head``; or (None, reason)."""
    runs_doc = _gh_json(
        u,
        gh,
        f"repos/{REPO_SLUG}/actions/workflows/{RELEASE_WORKFLOW}/runs"
        "?branch=main&status=success&per_page=20",
    )
    runs = runs_doc.get("workflow_runs") if isinstance(runs_doc, dict) else None
    if not isinstance(runs, list):
        return None, "Die Liste der Artefakte ließ sich nicht abrufen."
    usable = [
        run
        for run in runs
        if isinstance(run, dict)
        and run.get("head_branch") == "main"
        and run.get("conclusion") == "success"
        and run.get("path") == RELEASE_WORKFLOW_PATH
        and isinstance(run.get("id"), int)
        and isinstance(run.get("head_sha"), str)
        and isinstance(run.get("repository"), dict)
        and run["repository"].get("full_name") == REPO_SLUG
    ]
    usable.sort(key=lambda run: run.get("head_sha") != local_head)  # stable: own head first
    for run in usable[:5]:
        arts_doc = _gh_json(u, gh, f"repos/{REPO_SLUG}/actions/runs/{run['id']}/artifacts")
        arts = arts_doc.get("artifacts") if isinstance(arts_doc, dict) else None
        if not isinstance(arts, list):
            continue
        for art in arts:
            if (
                isinstance(art, dict)
                and isinstance(art.get("name"), str)
                and art["name"].startswith(ARTIFACT_PREFIX)
                and art["name"].endswith(f"-{run['head_sha']}")
                and art.get("expired") is False
            ):
                size = art.get("size_in_bytes")
                found = Artefakt(
                    run["id"], art["name"], run["head_sha"], size if isinstance(size, int) else 0
                )
                return found, "gefunden"
    return None, "Es gibt kein gültiges Engine-Artefakt mehr (sie verfallen nach 30 Tagen)."


def pruefe_artefakt(folder: Path, pin: str) -> tuple[str | None, str]:
    """(sha, reason): only the four expected files are read; the JAR hash must equal both the
    ``.sha256`` file and its line in ``PLAYTEST_LAB_SHA256SUMS.txt``; the pin must equal ``pin``."""
    jar = folder / JAR_NAME
    for name in (JAR_NAME, SHA_NAME, PIN_NAME, SUMS_NAME):
        candidate = folder / name
        if not candidate.is_file() or candidate.is_symlink():
            return None, f"Im Artefakt fehlt {name}."
    sha = sha256_datei(jar)
    if _first_token(folder / SHA_NAME) != sha:
        return None, "Die Prüfsumme der Engine-Datei passt nicht."
    listed = ""
    for line in (folder / SUMS_NAME).read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("*").removeprefix("./") == JAR_NAME:
            listed = parts[0].lower()
    if listed != sha:
        return None, "Die Engine-Datei steht nicht passend in PLAYTEST_LAB_SHA256SUMS.txt."
    if _first_token(folder / PIN_NAME) != pin:
        return None, "Die Engine-Version im Artefakt passt nicht zu config/rules_engines.json."
    return sha, "geprüft"


def hole_artefakt(u: Umgebung, pin: str, java: str | None) -> tuple[bool, str]:
    gh = u.which("gh")
    if not gh:
        return False, f"Das GitHub-Programm gh fehlt (installieren: {' '.join(WINGET_GH)})."
    if u.run([gh, "auth", "status"], capture=True, timeout=60, env=u.env).returncode != 0:
        return False, "gh ist nicht angemeldet (einmal ausführen: gh auth login)."
    git = u.which("git")
    head = ""
    if git:
        head = u.run([git, "-C", str(u.repo), "rev-parse", "HEAD"], capture=True).stdout.strip()
    picked, reason = waehle_artefakt(u, gh, head)
    if picked is None:
        return False, reason
    run_id, name, head_sha, size = picked.run_id, picked.name, picked.head_sha, picked.size
    u.sagen(f"  Ich lade das Engine-Paket vom Stand {head_sha[:10]} (etwa {size // 1_000_000} MB).")
    u.data.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="engine-download-", dir=u.data) as temp:
        target = Path(temp) / "artefakt"
        done = u.run(
            [gh, "run", "download", str(run_id), "-R", REPO_SLUG, "-n", name, "-D", str(target)],
            capture=True,
            timeout=3600,
            env=u.env,
        )
        if done.returncode != 0:
            return False, "Der Download des Engine-Pakets hat nicht geklappt."
        sha, reason = pruefe_artefakt(target, pin)
        if sha is None:
            return False, reason
        if java:
            reported = engine_meldet_pin(u, java, target / JAR_NAME)
            if reported is not None and reported != pin:
                return False, "Die Engine meldet eine andere Version als config/rules_engines.json."
        stelle_bereit(target / JAR_NAME, u.data / "engine", sha, pin)
    return True, f"Engine-Paket vom Stand {head_sha[:10]} geprüft und bereitgestellt."


def baue_mit_maven(u: Umgebung, pin: str, java: str | None) -> tuple[bool, str]:
    missing = [
        name for name in ("git", "javac", "mvn") if not (u.which(name) or u.which(f"{name}.cmd"))
    ]
    if java is None or missing:
        what = ", ".join(missing) if missing else "Java"
        return False, f"Für den Eigenbau fehlt: {what}."
    u.sagen(
        "  Der Eigenbau lädt die Engine-Quellen und Maven-Bibliotheken; er dauert lange und "
        "braucht mehrere Gigabyte Platz (genaue Werte für diesen PC sind nicht bekannt)."
    )
    if not frage(u, "Soll ich die Engine jetzt selbst bauen?"):
        return False, "Eigenbau abgelehnt."
    env = kind_env(u)
    env["ENGINE_PROVIDER"] = "xmage"
    for override in ("COMMANDER_LAB_XMAGE_COMMIT", "COMMANDER_LAB_XMAGE_REPOSITORY"):
        env.pop(override, None)  # the pin comes from config/rules_engines.json only
    scripts_dir = venv_python(u.repo, u.windows).parent
    env["PATH"] = f"{scripts_dir}{os.pathsep}{env.get('PATH', '')}"
    if u.windows:
        script = u.repo / "scripts" / "bootstrap_engine_windows.ps1"
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)]
    else:
        cmd = ["bash", str(u.repo / "scripts" / "bootstrap_engine_linux.sh")]
    if u.run(cmd, cwd=u.repo, env=env, capture=False).returncode != 0:
        return False, "Der Bau der Engine-Quellen ist fehlgeschlagen (Meldungen oben)."
    mvn = u.which("mvn") or u.which("mvn.cmd") or "mvn"
    built = u.run([mvn, "-B", "verify"], cwd=u.repo / "engine-bridge", env=env, capture=False)
    jar = u.repo / BUILT_JAR
    if built.returncode != 0 or not jar.is_file():
        return False, "Der Bau der Engine-Datei ist fehlgeschlagen (Meldungen oben)."
    reported = engine_meldet_pin(u, java, jar)
    if reported != pin:
        return (
            False,
            "Die selbst gebaute Engine meldet nicht die Version aus config/rules_engines.json.",
        )
    stelle_bereit(jar, u.data / "engine", sha256_datei(jar), pin)
    return True, "Engine selbst gebaut, Version geprüft und bereitgestellt."


def sorge_fuer_engine(
    u: Umgebung, bericht: Bericht, pin: str | None, java: str | None, *, nur_pruefen: bool
) -> bool:
    """Step 4; returns True when a new JAR was staged in this run."""
    if u.env.get(ENGINE_COMMAND_ENV, "").strip():
        u.sagen(f"  {ENGINE_COMMAND_ENV} ist gesetzt; die Engine bleibt, wie sie ist.")
        bericht.add("Engine", GRUEN, "Ein eigener Engine-Befehl ist eingestellt (unverändert).")
        return False
    if pin is None:
        fehlt(
            u,
            "die Soll-Version der Engine (die Systemprüfung lief nicht).",
            "die Engine nicht anfassen.",
        )
        bericht.add(
            "Engine",
            ROT,
            "Die Soll-Version der Engine ist unbekannt, weil die Systemprüfung nicht lief.",
            "Zuerst die Python-Pakete in Ordnung bringen, dann neu starten.",
        )
        return False
    engine_dir = u.data / "engine"
    valid, reason = jar_geprueft(engine_dir, pin)
    if valid:
        u.sagen("  Die Engine ist da und geprüft.")
        bericht.add("Engine", GRUEN, "Die Engine ist da; Prüfsumme und Version passen.")
        return False
    jar = engine_dir / JAR_NAME
    if jar.is_file() and java and not nur_pruefen and engine_meldet_pin(u, java, jar) == pin:
        stelle_bereit(jar, engine_dir, sha256_datei(jar), pin)
        u.sagen("  Die vorhandene Engine meldet die richtige Version; Prüfdateien ergänzt.")
        bericht.add(
            "Engine", GRUEN, "Die Engine ist da; die Engine selbst meldet die richtige Version."
        )
        return False
    if nur_pruefen:
        fehlt(u, f"eine geprüfte Engine ({reason}).", "nichts (nur prüfen).")
        bericht.add(
            "Engine",
            ROT,
            f"Keine geprüfte Engine: {reason}.",
            "Den Starter ohne --nur-pruefen laufen lassen.",
        )
        return False
    fehlt(u, f"eine geprüfte Engine ({reason}).", "das fertige Engine-Paket von GitHub holen.")
    ok, why = hole_artefakt(u, pin, java)
    if ok:
        u.sagen(f"  {why}")
        bericht.add("Engine", GRUEN, why)
        return True
    u.sagen(f"  {why}")
    fehlt(u, "das fertige Engine-Paket.", "dir den Eigenbau mit Maven anbieten.")
    built, built_why = baue_mit_maven(u, pin, java)
    u.sagen(f"  {built_why}")
    if built:
        bericht.add("Engine", GRUEN, built_why)
        return True
    bericht.add(
        "Engine",
        ROT,
        f"Die Engine fehlt: {why}",
        "gh installieren und anmelden (gh auth login) und neu starten; BUILD geht auch ohne Engine.",
    )
    return False


# --- step 5: AppCDS ------------------------------------------------------------------------


def baue_appcds(
    u: Umgebung,
    bericht: Bericht,
    report: dict[str, object] | None,
    *,
    neu: bool,
    java: str | None,
    nur_pruefen: bool,
) -> None:
    status = doctor_check(report, "appcds_archive").get("status")
    jar = u.data / "engine" / JAR_NAME
    if u.env.get(ENGINE_COMMAND_ENV, "").strip() or not jar.is_file() or java is None:
        u.sagen("  Übersprungen (keine Engine oder kein Java).")
        return
    if not neu and status == "PASS":
        u.sagen("  Die Schnellstart-Datei der Engine ist da.")
        return
    if nur_pruefen:
        fehlt(u, "die Schnellstart-Datei der Engine.", "nichts (nur prüfen).")
        return
    u.sagen("  Ich baue die Schnellstart-Datei der Engine (einmalig, etwa eine halbe Minute).")
    done = u.run(
        [
            str(venv_python(u.repo, u.windows)),
            "-m",
            "commander_lab.studio",
            "--data",
            str(u.data),
            "build-appcds",
        ],
        cwd=u.repo,
        env=kind_env(u),
        capture=False,
    )
    if done.returncode != 0:
        u.sagen("  Die Schnellstart-Datei ließ sich nicht bauen; Partien starten trotzdem.")


# --- step 6: doctor summary ----------------------------------------------------------------

_DOCTOR_TEXT: dict[str, tuple[str, str, str]] = {
    # name: (Bereich, Satz bei grün, nächste Handlung bei rot/gelb)
    "python": ("Python", "Python passt.", "Python 3.12 installieren und neu starten."),
    "dependencies": (
        "Python-Pakete",
        "Alle nötigen Python-Pakete sind da.",
        "Den Starter neu starten; er installiert die Pakete.",
    ),
    "java": (
        "Java",
        "Java passt.",
        f"Java 17 installieren ({' '.join(WINGET_JAVA)}) und neu starten.",
    ),
    "engine_bridge": (
        "Engine",
        "Die Engine-Datei ist da.",
        "gh installieren und anmelden (gh auth login), dann neu starten.",
    ),
    "engine_pin": (
        "Engine-Version",
        "Die Engine passt zur erwarteten Version.",
        "Den Starter neu starten; er holt die passende Engine.",
    ),
    "appcds_archive": (
        "Schnellstart-Datei",
        "Die Schnellstart-Datei der Engine passt.",
        "Nicht schlimm: Partien starten etwas langsamer. Der Starter baut sie beim nächsten Mal.",
    ),
    "card_knowledge": (
        "Kartenwissen",
        "Das Kartenwissen der KI ist lesbar.",
        "Das Programm neu holen (git pull) oder melden.",
    ),
    "studio_data": (
        "Datenordner",
        "Der Datenordner ist bereit.",
        "Schreibrechte für den Datenordner prüfen.",
    ),
}


def fasse_doctor_zusammen(u: Umgebung, bericht: Bericht, report: dict[str, object] | None) -> None:
    if report is None:
        u.sagen("  [rot] Systemprüfung: Sie ließ sich nicht ausführen.")
        bericht.add(
            "Systemprüfung",
            ROT,
            "Die Systemprüfung ließ sich nicht ausführen.",
            "Die Python-Pakete in Ordnung bringen und neu starten.",
        )
        return
    checks = report.get("checks")
    assert isinstance(checks, list)
    for entry in checks:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "?"))
        bereich, gut, handlung = _DOCTOR_TEXT.get(name, (name, "In Ordnung.", "Meldung prüfen."))
        status = entry.get("status")
        if status == "PASS":
            u.sagen(f"  [grün] {bereich}: {gut}")
            continue
        farbe = ROT if status == "FAIL" else GELB
        detail = str(entry.get("detail") or "keine Angabe")
        u.sagen(f"  [{farbe}] {bereich}: {detail}")
        u.sagen(f"         Nächster Schritt: {handlung}")
        if not any(item.bereich == bereich and item.farbe != GRUEN for item in bericht.befunde):
            bericht.add(bereich, farbe, detail, handlung)


# --- step 7: first data import -------------------------------------------------------------


def datenordner_leer(data: Path) -> bool:
    db = data / DATABASE_NAME
    if not db.is_file():
        return True
    try:
        connection = sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True)
    except sqlite3.Error:
        return False
    try:
        row = connection.execute("SELECT COUNT(*) FROM card").fetchone()
    except sqlite3.Error:
        return True  # no card table yet: nothing imported
    finally:
        connection.close()
    return not row or int(row[0]) == 0


def finde_scryfall(data: Path, given: Path | None) -> Path | None:
    if given is not None:
        return given if given.is_file() else None
    folder = data / SCRYFALL_FOLDER
    if not folder.is_dir():
        return None
    found = sorted(p for p in folder.iterdir() if p.is_file() and SCRYFALL_PATTERN.match(p.name))
    return found[-1] if found else None


def erstimport(u: Umgebung, bericht: Bericht, scryfall: Path | None, *, nur_pruefen: bool) -> None:
    marker = u.data / STATE_FOLDER / IMPORT_MARKER
    if marker.is_file() or not datenordner_leer(u.data):
        u.sagen("  Die Studio-Daten sind schon da.")
        bericht.add("Daten", GRUEN, "Sammlung und Kartendaten sind importiert.")
        return
    found = finde_scryfall(u.data, scryfall)
    if found is None:
        folder = u.data / SCRYFALL_FOLDER
        fehlt(
            u,
            f"die Kartendaten-Datei von Scryfall (oracle-cards-….jsonl.gz) im Ordner {folder}.",
            "den ersten Import überspringen; das Studio startet trotzdem.",
        )
        bericht.add(
            "Daten",
            GELB,
            "Die Sammlung ist noch nicht importiert: die Scryfall-Kartendatei fehlt.",
            f"Bei scryfall.com/docs/api/bulk-data die Datei „Oracle Cards“ laden, nach {folder} "
            "legen und den Starter neu öffnen.",
        )
        return
    if nur_pruefen:
        fehlt(u, "der erste Import der Sammlung.", "nichts (nur prüfen).")
        bericht.add("Daten", GELB, "Die Sammlung ist noch nicht importiert.")
        return
    u.sagen(f"  Ich importiere die Sammlung und die Repo-Daten für {COMMANDER}.")
    done = u.run(
        [
            str(venv_python(u.repo, u.windows)),
            "-m",
            "commander_lab.studio",
            "--data",
            str(u.data),
            "import-all",
            "--commander",
            COMMANDER,
            "--from-repo",
            "--scryfall",
            str(found),
        ],
        cwd=u.repo,
        env=kind_env(u),
        capture=False,
    )
    if done.returncode != 0:
        bericht.add(
            "Daten",
            ROT,
            "Der erste Import ist nicht vollständig gelaufen.",
            "Die Meldungen oben lesen; beim nächsten Start versucht der Starter es erneut.",
        )
        return
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        json.dumps({"commander": COMMANDER, "scryfall": found.name}) + "\n", encoding="utf-8"
    )
    bericht.add("Daten", GRUEN, "Sammlung und Kartendaten sind importiert.")


# --- desktop shortcut (Windows, asked once) ------------------------------------------------


def verknuepfung(u: Umgebung) -> None:
    if not u.windows:
        return
    state = u.data / STATE_FOLDER / SHORTCUT_STATE
    if state.is_file():
        return
    if not u.interaktiv and not u.ja:
        return
    wanted = frage(u, "Soll ich eine Verknüpfung „Commander Studio“ auf dem Desktop anlegen?")
    if wanted:
        target = str(u.repo / "Studio starten.cmd").replace("'", "''")
        workdir = str(u.repo).replace("'", "''")
        script = (
            "$s = New-Object -ComObject WScript.Shell; "
            "$d = [Environment]::GetFolderPath('Desktop'); "
            "$l = $s.CreateShortcut((Join-Path $d 'Commander Studio.lnk')); "
            f"$l.TargetPath = '{target}'; $l.WorkingDirectory = '{workdir}'; $l.Save()"
        )
        made = u.run(["powershell", "-NoProfile", "-Command", script], capture=True, timeout=60)
        u.sagen(
            "  Verknüpfung angelegt."
            if made.returncode == 0
            else "  Die Verknüpfung ließ sich nicht anlegen."
        )
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps({"angelegt": wanted}) + "\n", encoding="utf-8")


# --- step 8: start -------------------------------------------------------------------------


def starte(u: Umgebung, port: int) -> int:
    url = f"http://127.0.0.1:{port}/"
    if u.port_offen(port):
        if u.studio_antwortet(port):
            u.sagen(f"  Das Studio läuft schon; ich öffne nur den Browser: {url}")
            u.browser(url)
            return 0
        u.sagen(f"  Ein anderes Programm belegt Port {port}.")
        u.sagen(f"  Das mache ich als Nächstes: nichts. Starte mit --port {port + 1}.")
        return 4
    u.sagen(f"  Ich starte das Studio: {url} (beenden mit Strg+C)")
    done = u.run(
        [
            str(venv_python(u.repo, u.windows)),
            "-m",
            "commander_lab.studio",
            "--data",
            str(u.data),
            "serve",
            "--open",
            "--port",
            str(port),
        ],
        cwd=u.repo,
        env=kind_env(u),
        capture=False,
    )
    if done.returncode == 3:
        u.sagen(f"  Das Studio läuft schon für diesen Datenordner; ich öffne den Browser: {url}")
        u.browser(url)
        return 0
    return done.returncode


# --- the whole flow ------------------------------------------------------------------------


def schritt(u: Umgebung, number: int, title: str) -> None:
    u.sagen("")
    u.sagen(f"Schritt {number} von {SCHRITTE}: {title}")


def zusammenfassung(u: Umgebung, bericht: Bericht) -> None:
    u.sagen("")
    if bericht.alles_bereit:
        u.sagen("Alles bereit.")
        return
    u.sagen("Es fehlt:")
    for item in bericht.befunde:
        if item.farbe == GRUEN:
            continue
        line = f"  [{item.farbe}] {item.bereich}: {item.satz}"
        u.sagen(line if not item.naechstes else f"{line} Nächster Schritt: {item.naechstes}")


def ablauf(u: Umgebung, args: argparse.Namespace, neu_starten: Callable[[], int]) -> int:
    bericht = Bericht()
    nur = bool(args.nur_pruefen)
    u.sagen("Commander Studio: Einrichten und Starten")
    u.sagen(f"Programmordner: {u.repo}")
    u.sagen(f"Datenordner:    {u.data}")
    if u.data.resolve().is_relative_to(u.repo.resolve()):
        u.sagen("Der Datenordner liegt im Programmordner; das ist nicht erlaubt (private Daten).")
        u.sagen(f"Setze {STUDIO_DATA_ENV} auf einen Ordner außerhalb von {u.repo}.")
        return 2

    schritt(u, 1, "Python und Java prüfen")
    if not pruefe_python(u, bericht):
        zusammenfassung(u, bericht)
        return 1
    java = pruefe_java(u, bericht, nur_pruefen=nur)

    schritt(u, 2, "Programm aktualisieren")
    if args.ohne_update:
        u.sagen("  Übersprungen.")
    elif aktualisiere_repo(u, bericht, nur_pruefen=nur):
        u.sagen("  Ich starte mich mit dem neuen Stand neu.")
        return neu_starten()

    schritt(u, 3, "Python-Umgebung und Pakete")
    pakete_ok = richte_venv_ein(u, bericht, nur_pruefen=nur, neu=bool(args.pakete_neu))
    report = doctor(u) if pakete_ok else None

    schritt(u, 4, "Engine bereitstellen")
    neu = sorge_fuer_engine(u, bericht, soll_pin(report), java, nur_pruefen=nur)

    schritt(u, 5, "Schnellstart-Datei der Engine")
    baue_appcds(u, bericht, report, neu=neu, java=java, nur_pruefen=nur)

    schritt(u, 6, "Systemprüfung")
    if pakete_ok and not nur:
        report = doctor(u)
    fasse_doctor_zusammen(u, bericht, report)

    schritt(u, 7, "Erste Daten")
    if pakete_ok:
        erstimport(u, bericht, args.scryfall, nur_pruefen=nur)
    else:
        u.sagen("  Übersprungen (Python-Pakete fehlen).")

    if not nur:
        verknuepfung(u)
    zusammenfassung(u, bericht)

    schritt(u, 8, "Studio starten")
    if nur or args.ohne_start:
        busy = u.port_offen(args.port)
        u.sagen(f"  Nicht gestartet (Port {args.port} {'belegt' if busy else 'frei'}).")
        return 0 if bericht.alles_bereit else 1
    if not pakete_ok:
        u.sagen("  Ohne Python-Pakete kann das Studio nicht starten.")
        return 1
    return starte(u, args.port)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="commander_lab.studio.oneclick",
        description="Commander Studio einrichten, aktualisieren und starten (ein Klick).",
    )
    p.add_argument("--data", type=Path, default=None, help="Studio-Datenordner")
    p.add_argument(
        "--nur-pruefen", action="store_true", help="nur prüfen und berichten, nichts ändern"
    )
    p.add_argument(
        "--ja",
        action="store_true",
        help="Rückfragen mit Ja beantworten (nie Programm-Installationen über winget)",
    )
    p.add_argument("--ohne-update", action="store_true", help="kein git pull")
    p.add_argument("--ohne-start", action="store_true", help="einrichten, aber nicht starten")
    p.add_argument("--pakete-neu", action="store_true", help="Python-Pakete neu installieren")
    p.add_argument("--scryfall", type=Path, default=None, help="Scryfall-Datei Oracle Cards")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    return p


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def main(argv: Sequence[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    args = parser().parse_args(raw)
    windows = os.name == "nt"
    env = dict(os.environ)
    data = (args.data or standard_datenordner(env, windows)).expanduser()
    u = Umgebung(
        repo=_repo_root(),
        data=data,
        windows=windows,
        interaktiv=sys.stdin is not None and sys.stdin.isatty(),
        ja=bool(args.ja),
        env=env,
    )

    def neu_starten() -> int:
        cmd = [sys.executable, "-m", "commander_lab.studio.oneclick", *raw, "--ohne-update"]
        return u.run(cmd, cwd=u.repo, env=kind_env(u), capture=False).returncode

    return ablauf(u, args, neu_starten)


if __name__ == "__main__":
    sys.exit(main())
