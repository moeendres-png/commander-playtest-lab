"""Environment diagnostics for Commander Studio (``python -m commander_lab.studio doctor``)."""

from __future__ import annotations

import importlib
import os
import shlex
import sys
from collections.abc import Callable
from pathlib import Path

from commander_lab.qualification.current_boundary.bridge_launcher import (
    canonical_xmage_engine_pin,
)

from . import builder, engine_check, launch
from .store import DATABASE_NAME, STUDIO_DATA_ENV, studio_data_dir

_REQUIRED_IMPORTS: tuple[tuple[str, str], ...] = (
    ("pydantic", "pydantic"),
    ("openpyxl", "openpyxl"),
    ("PyYAML", "yaml"),
    ("typer", "typer"),
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
)


def _default_unconfigured_data_dir() -> Path:
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA", "").strip()
        if local:
            return Path(local) / "CommanderStudio"
    return Path.home() / ".local" / "share" / "commander-studio"


def _resolve_data_folder(data_folder: str | Path | None) -> tuple[Path, bool]:
    if data_folder is not None:
        return Path(data_folder).expanduser().resolve(), True
    try:
        return studio_data_dir().resolve(), True
    except RuntimeError:
        return _default_unconfigured_data_dir().resolve(), False


def _is_dir_writable(target: Path) -> bool:
    if target.exists():
        return target.is_dir() and os.access(target, os.W_OK)
    for ancestor in target.parents:
        if ancestor.exists():
            return ancestor.is_dir() and os.access(ancestor, os.W_OK)
    return False


def _repo_built_jar() -> Path:
    return (
        launch._repository_root()
        / "engine-bridge"
        / "target"
        / "xmage-engine-bridge-0.1.0-SNAPSHOT.jar"
    )


def _check_python() -> dict[str, object]:
    major, minor, micro = sys.version_info[:3]
    version = f"{major}.{minor}.{micro}"
    ok = (major, minor) >= (3, 12)
    return {
        "name": "python",
        "status": "PASS" if ok else "FAIL",
        "required": True,
        "version": version,
        "executable": sys.executable,
        "detail": f"Python {version}" if ok else f"Python {version} (< 3.12)",
        "remediation": None if ok else "Python 3.12 oder neuer installieren.",
    }


def _check_dependencies(
    importer: Callable[[str], object] = importlib.import_module,
) -> dict[str, object]:
    missing: list[str] = []
    for dist_name, module_name in _REQUIRED_IMPORTS:
        try:
            importer(module_name)
        except ImportError:
            missing.append(dist_name)
    ok = not missing
    return {
        "name": "dependencies",
        "status": "PASS" if ok else "FAIL",
        "required": True,
        "missing": missing,
        "detail": "Alle Kern- und Studio-Pakete importierbar."
        if ok
        else f"Fehlende Pakete: {', '.join(missing)}",
        "remediation": None if ok else 'pip install -e ".[api]" (oder requirements/lock.txt)',
    }


def _parse_env_command() -> tuple[list[str] | None, str | None]:
    raw = os.environ.get(launch.ENGINE_COMMAND_ENV, "").strip()
    if not raw:
        return None, None
    try:
        tokens = shlex.split(raw, posix=(os.name != "nt"))
    except ValueError as exc:
        return [], f"Ungültiger Startbefehl in {launch.ENGINE_COMMAND_ENV}: {exc}"
    return tokens, None


def _check_java(env_cmd: list[str] | None, env_err: str | None) -> dict[str, object]:
    if env_err is not None:
        return {
            "name": "java",
            "status": "FAIL",
            "required": True,
            "detail": env_err,
            "remediation": f"{launch.ENGINE_COMMAND_ENV} korrigieren oder entfernen.",
        }
    if env_cmd is not None:
        if not env_cmd or not engine_check._runnable(env_cmd[0]):
            shown = env_cmd[0] if env_cmd else "(leer)"
            return {
                "name": "java",
                "status": "FAIL",
                "required": True,
                "executable": shown,
                "detail": f"Startprogramm aus {launch.ENGINE_COMMAND_ENV} fehlt: {shown}",
                "remediation": "Gültigen Engine-Startbefehl setzen oder Umgebungsvariable entfernen.",
            }
        if not launch._is_java_launcher(env_cmd):
            return {
                "name": "java",
                "status": "PASS",
                "required": True,
                "executable": env_cmd[0],
                "detail": f"Benutzerdefinierter Engine-Launcher: {env_cmd[0]}",
                "remediation": None,
            }
        java = env_cmd[0]
    else:
        java = launch._java_executable() or ""
    if not java:
        return {
            "name": "java",
            "status": "FAIL",
            "required": True,
            "executable": None,
            "major_version": None,
            "detail": f"Java {launch.MIN_JAVA_MAJOR}+ nicht gefunden (PATH und JAVA_HOME leer).",
            "remediation": "Eclipse Temurin JDK 17 oder neuer installieren und JAVA_HOME/PATH setzen.",
        }
    major = launch._java_major(java)
    if major is None:
        return {
            "name": "java",
            "status": "FAIL",
            "required": True,
            "executable": java,
            "major_version": None,
            "detail": f"Java-Version unter {java} nicht lesbar.",
            "remediation": f"Funktionsfähiges JDK {launch.MIN_JAVA_MAJOR}+ verwenden.",
        }
    if major < launch.MIN_JAVA_MAJOR:
        return {
            "name": "java",
            "status": "FAIL",
            "required": True,
            "executable": java,
            "major_version": major,
            "detail": f"Java {major} gefunden ({java}), nötig ist >= {launch.MIN_JAVA_MAJOR}.",
            "remediation": f"JDK {launch.MIN_JAVA_MAJOR} oder neuer installieren.",
        }
    return {
        "name": "java",
        "status": "PASS",
        "required": True,
        "executable": java,
        "major_version": major,
        "detail": f"Java {major} ({java})",
        "remediation": None,
    }


def _resolve_active_jar(data_dir: Path, env_cmd: list[str] | None) -> Path | None:
    if env_cmd is not None:
        return launch.jar_path_for_command(env_cmd)
    return data_dir / launch.ENGINE_JAR


def _check_engine_bridge(
    data_dir: Path,
    env_cmd: list[str] | None,
    env_err: str | None,
    qual: dict[str, object],
) -> dict[str, object]:
    if env_err is not None:
        return {
            "name": "engine_bridge",
            "status": "FAIL",
            "required": True,
            "detail": env_err,
            "remediation": f"{launch.ENGINE_COMMAND_ENV} korrigieren.",
        }
    jar_path = _resolve_active_jar(data_dir, env_cmd)
    if env_cmd is not None and jar_path is None:
        return {
            "name": "engine_bridge",
            "status": "PASS",
            "required": True,
            "mode": "env_command",
            "jar_path": None,
            "sha256": None,
            "bridge_qualification": qual,
            "detail": f"Über {launch.ENGINE_COMMAND_ENV} konfiguriert (ohne -jar).",
            "remediation": None,
        }
    if jar_path is None:
        return {
            "name": "engine_bridge",
            "status": "FAIL",
            "required": True,
            "jar_path": None,
            "sha256": None,
            "bridge_qualification": qual,
            "detail": "Kein Bridge-JAR-Pfad auflösbar.",
            "remediation": f"{launch.ENGINE_COMMAND_ENV} oder Datenordner prüfen.",
        }
    if not jar_path.is_file():
        repo_jar = _repo_built_jar()
        if repo_jar.is_file():
            remediation = (
                f"Bereitstellen mit: python scripts/provision_engine_bridge.py "
                f"--source {repo_jar} --data-dir {data_dir}"
            )
        else:
            remediation = (
                "Release-JAR herunterladen oder im Repo bauen (mvn -B verify in engine-bridge/) "
                "und mit scripts/provision_engine_bridge.py in den Datenordner kopieren."
            )
        return {
            "name": "engine_bridge",
            "status": "FAIL",
            "required": True,
            "jar_path": str(jar_path),
            "sha256": None,
            "bridge_qualification": qual,
            "detail": f"Bridge-JAR fehlt: {jar_path}",
            "remediation": remediation,
        }
    sha256 = launch._file_sha256(jar_path)
    return {
        "name": "engine_bridge",
        "status": "PASS",
        "required": True,
        "jar_path": str(jar_path),
        "sha256": sha256,
        "bridge_qualification": qual,
        "detail": (
            f"Bridge-JAR vorhanden: {jar_path} "
            f"(sha256={sha256[:12] if sha256 else '?'}, qual={qual.get('status')})"
        ),
        "remediation": None,
    }


def _check_engine_pin(jar_path: Path | None, expected_pin: str) -> dict[str, object]:
    if jar_path is None or not jar_path.is_file():
        return {
            "name": "engine_pin",
            "status": "WARN",
            "required": False,
            "expected_pin": expected_pin,
            "recorded_pin": None,
            "detail": f"Pin-Abgleich übersprungen (keine JAR-Datei; Soll-Pin {expected_pin[:10]}).",
            "remediation": None,
        }
    pin_file = jar_path.parent / "ENGINE_PIN.txt"
    if not pin_file.is_file():
        return {
            "name": "engine_pin",
            "status": "WARN",
            "required": False,
            "expected_pin": expected_pin,
            "recorded_pin": None,
            "detail": f"ENGINE_PIN.txt fehlt neben {jar_path.name} (Soll-Pin {expected_pin[:10]}).",
            "remediation": (
                "Zur eindeutigen Pin-Zuordnung über scripts/provision_engine_bridge.py --source bereitstellen."
            ),
        }
    recorded = pin_file.read_text(encoding="utf-8").strip()
    matches = recorded == expected_pin
    return {
        "name": "engine_pin",
        "status": "PASS" if matches else "FAIL",
        "required": True,
        "expected_pin": expected_pin,
        "recorded_pin": recorded,
        "detail": (
            f"Engine-Pin stimmt überein ({expected_pin[:10]})."
            if matches
            else f"Pin-Abweichung: installiert {recorded[:10]}, erwartet {expected_pin[:10]}."
        ),
        "remediation": None
        if matches
        else "Passende Bridge-JAR zum aktuellen Pin neu bereitstellen.",
    }


def _check_appcds(jar_path: Path | None) -> dict[str, object]:
    if jar_path is None or not jar_path.is_file():
        return {
            "name": "appcds_archive",
            "status": "WARN",
            "required": False,
            "archive_path": None,
            "detail": "AppCDS-Archiv nicht geprüft (keine JAR-Datei).",
            "remediation": None,
        }
    archive = Path(f"{jar_path}.jsa")
    exists = archive.is_file()
    return {
        "name": "appcds_archive",
        "status": "PASS" if exists else "WARN",
        "required": False,
        "archive_path": str(archive),
        "detail": (
            f"AppCDS-Archiv vorhanden: {archive}"
            if exists
            else f"Optionales AppCDS-Archiv fehlt ({archive}); Serien starten ohne schnelleres Klassenladen."
        ),
        "remediation": None
        if exists
        else "Optional nach Bereitstellung einmalig erzeugen für schnellere JVM-Starts.",
    }


def _check_card_knowledge() -> dict[str, object]:
    ok = builder.sim_readiness_available()
    return {
        "name": "card_knowledge",
        "status": "PASS" if ok else "FAIL",
        "required": True,
        "detail": "Kartenliste/Pilot-Kartenwissen lesbar."
        if ok
        else "Kartenliste/Pilot-Kartenwissen nicht lesbar.",
        "remediation": None
        if ok
        else "Repository-Vollständigkeit prüfen (Kartenfakten für Engine-Prüfung fehlen).",
    }


def _check_studio_data(data_dir: Path, configured: bool) -> dict[str, object]:
    writable = _is_dir_writable(data_dir)
    db_path = data_dir / DATABASE_NAME
    has_db = db_path.is_file()
    if not writable:
        return {
            "name": "studio_data",
            "status": "FAIL",
            "required": True,
            "data_dir": str(data_dir),
            "configured": configured,
            "database_exists": has_db,
            "detail": f"Studio-Datenordner nicht beschreibbar: {data_dir}",
            "remediation": f"Schreibrechte prüfen oder {STUDIO_DATA_ENV} auf einen beschreibbaren Pfad setzen.",
        }
    if not configured:
        return {
            "name": "studio_data",
            "status": "WARN",
            "required": False,
            "data_dir": str(data_dir),
            "configured": False,
            "database_exists": has_db,
            "detail": (
                f"{STUDIO_DATA_ENV} ist nicht gesetzt (Standardpfad: {data_dir}, "
                f"Datenbank {'vorhanden' if has_db else 'noch nicht angelegt'})."
            ),
            "remediation": f"Mit --data, {STUDIO_DATA_ENV} oder scripts/studio_start.sh/.ps1 starten.",
        }
    return {
        "name": "studio_data",
        "status": "PASS",
        "required": True,
        "data_dir": str(data_dir),
        "configured": True,
        "database_exists": has_db,
        "detail": (
            f"Datenordner bereit: {data_dir} "
            f"(Datenbank {'vorhanden' if has_db else 'wird bei erstem Start angelegt'})"
        ),
        "remediation": None,
    }


def run_doctor(
    data_folder: str | Path | None = None,
    *,
    check_dependencies: bool = True,
) -> dict[str, object]:
    """Run local environment diagnostics and return structured status payload."""
    data_dir, configured = _resolve_data_folder(data_folder)
    expected_pin = canonical_xmage_engine_pin()
    qual = launch.bridge_qualification_state()
    env_cmd, env_err = _parse_env_command()
    jar_path = _resolve_active_jar(data_dir, env_cmd) if env_err is None else None

    checks: list[dict[str, object]] = [
        _check_python(),
    ]
    if check_dependencies:
        checks.append(_check_dependencies())
    checks.extend(
        [
            _check_java(env_cmd, env_err),
            _check_engine_bridge(data_dir, env_cmd, env_err, qual),
            _check_engine_pin(jar_path, expected_pin),
            _check_appcds(jar_path),
            _check_card_knowledge(),
            _check_studio_data(data_dir, configured),
        ]
    )

    counts = {"pass": 0, "warn": 0, "fail": 0}
    for item in checks:
        key = str(item["status"]).lower()
        if key in counts:
            counts[key] += 1

    ok = counts["fail"] == 0
    overall = "FAIL" if counts["fail"] else ("WARN" if counts["warn"] else "PASS")
    return {
        "schema": "studio-doctor-1",
        "ok": ok,
        "status": overall,
        "summary": counts,
        "data_dir": str(data_dir),
        "data_dir_configured": configured,
        "expected_pin": expected_pin,
        "bridge_qualification": qual,
        "checks": checks,
    }


def format_doctor_report(report: dict[str, object]) -> str:
    """Format a ``run_doctor`` payload into concise, actionable terminal lines."""
    lines = [f"Commander Studio Doctor: {report['status']} ({report['data_dir']})"]
    raw_checks = report.get("checks")
    if isinstance(raw_checks, list):
        for entry in raw_checks:
            if not isinstance(entry, dict):
                continue
            status = entry.get("status", "UNKNOWN")
            name = entry.get("name", "?")
            detail = entry.get("detail", "")
            lines.append(f"[{status}] {name}: {detail}")
            remediation = entry.get("remediation")
            if remediation:
                lines.append(f"       -> {remediation}")
    return "\n".join(lines)
