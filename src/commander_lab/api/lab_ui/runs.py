"""Simulations-Warteschlange der Lab UI.

Die UI ruft den bestehenden Treiber UNVERAENDERT auf
(`scripts/run_full_game_deck_comparison.py`): dieselben Flags, dieselbe
Evidenz (Hash-Twin, Seed-Paarung, fail closed). Neu ist nur die
Warteschlange aussenherum: Spec validieren, Prozess starten, Fortschritt
aus dem Ergebnisverzeichnis lesen, abbrechen.

Deck-Pfade muessen Repo-relativ unter data/ liegen (die Deck-Liste
liefert genau solche Pfade). Keine Sammlungsdaten, keine beliebigen
Dateizugriffe.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path

_SEEDS_RE = re.compile(r"^\d+(-\d+)?(,\d+(-\d+)?)*$")


@dataclass
class RunSpec:
    baseline: str
    opponents: list[str]
    variant: str | None = None
    swaps: list[str] = field(default_factory=list)
    seeds: str = "1-25"
    no_rotate: bool = False
    workers: int | None = None
    stop_when_decided: bool = False
    look_every: int | None = None
    comparison_id: str | None = None
    retry_failed: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> RunSpec:
        opponents = data.get("opponents", [])
        swaps = data.get("swaps", [])
        if not isinstance(opponents, list) or not isinstance(swaps, list):
            raise ValueError("opponents und swaps muessen Listen sein")
        return cls(
            baseline=str(data.get("baseline", "")),
            opponents=[str(o) for o in opponents],
            variant=str(data["variant"]) if data.get("variant") else None,
            swaps=[str(s) for s in swaps],
            seeds=str(data.get("seeds", "1-25")),
            no_rotate=bool(data.get("no_rotate", False)),
            workers=int(data["workers"]) if data.get("workers") else None,
            stop_when_decided=bool(data.get("stop_when_decided", False)),
            look_every=int(data["look_every"]) if data.get("look_every") else None,
            comparison_id=str(data["comparison_id"]) if data.get("comparison_id") else None,
            retry_failed=bool(data.get("retry_failed", False)),
        )


def _check_deck_path(repo_root: Path, path: str) -> str | None:
    data_root = (repo_root / "data").resolve()
    resolved = (repo_root / path).resolve()
    if not resolved.is_relative_to(data_root):
        return f"Deck-Pfad ausserhalb von data/: {path}"
    if "collections" in resolved.parts or "coverage_decks" in resolved.parts:
        return f"Sammlungsdaten sind tabu: {path}"
    if resolved.suffix != ".json":
        return f"Deck-Pfad muss eine .json-Datei sein: {path}"
    return None


def validate_spec(spec: RunSpec, repo_root: str | Path) -> list[str]:
    """Alle Spec-Fehler sammeln (leere Liste = gueltig)."""
    root = Path(repo_root)
    errors: list[str] = []
    if not spec.baseline:
        errors.append("baseline fehlt")
    elif (err := _check_deck_path(root, spec.baseline)) is not None:
        errors.append(err)
    if spec.variant is not None and (err := _check_deck_path(root, spec.variant)) is not None:
        errors.append(err)
    if not spec.variant and not spec.swaps:
        errors.append("mindestens eine --variant oder ein --swap fehlt")
    if not 1 <= len(spec.opponents) <= 3:
        errors.append("1 bis 3 Gegner erforderlich")
    for opp in spec.opponents:
        if (err := _check_deck_path(root, opp)) is not None:
            errors.append(err)
    if not _SEEDS_RE.match(spec.seeds):
        errors.append(f"Seeds-Format ungueltig: {spec.seeds!r} (z. B. 1-25, 3,7,9)")
    if spec.workers is not None and not 1 <= spec.workers <= 16:
        errors.append("workers muss zwischen 1 und 16 liegen")
    if spec.look_every is not None and spec.look_every < 1:
        errors.append("look_every muss >= 1 sein")
    return errors


def expand_seeds(seeds: str) -> list[int]:
    """'1-25' -> [1..25], '3,7,9' -> [3, 7, 9]."""
    out: list[int] = []
    for part in seeds.split(","):
        if "-" in part:
            start, end = part.split("-", 1)
            out.extend(range(int(start), int(end) + 1))
        else:
            out.append(int(part))
    return out


def planned_games(spec: RunSpec) -> int:
    contenders = 1 + (1 if spec.variant else 0) + len(spec.swaps)
    seats = 1 if spec.no_rotate else 4
    return len(expand_seeds(spec.seeds)) * seats * contenders


def build_argv(spec: RunSpec, driver_script: str | Path, out_dir: str | Path) -> list[str]:
    argv = [
        sys.executable,
        str(driver_script),
        "--baseline",
        spec.baseline,
        "--opponent",
        spec.opponents[0],
        "--seeds",
        spec.seeds,
        "--out",
        str(out_dir),
    ]
    for opp in spec.opponents[1:]:
        argv += ["--opponent", opp]
    if spec.variant:
        argv += ["--variant", spec.variant]
    for swap in spec.swaps:
        argv += ["--swap", swap]
    if spec.no_rotate:
        argv.append("--no-rotate")
    if spec.workers is not None:
        argv += ["--workers", str(spec.workers)]
    if spec.stop_when_decided:
        argv.append("--stop-when-decided")
    if spec.look_every is not None:
        argv += ["--look-every", str(spec.look_every)]
    if spec.comparison_id:
        argv += ["--comparison-id", spec.comparison_id]
    if spec.retry_failed:
        argv.append("--retry-failed")
    return argv


@dataclass
class Job:
    id: str
    spec: RunSpec
    out_dir: Path
    status: str = "queued"
    log_tail: str = ""
    error: str | None = None
    process: subprocess.Popen[bytes] | None = field(default=None, repr=False)

    def progress(self) -> dict[str, object]:
        games_dir = self.out_dir / "games"
        done = len([p for p in games_dir.iterdir() if p.is_file()]) if games_dir.is_dir() else 0
        report = self.out_dir / "COMPARISON_REPORT.json"
        return {
            "done": done,
            "planned": planned_games(self.spec),
            "report_ready": report.is_file(),
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "status": self.status,
            "out_dir": str(self.out_dir),
            "progress": self.progress(),
            "log_tail": self.log_tail,
            "error": self.error,
        }


class JobManager:
    """Startet Treiber-Prozesse, liest Fortschritt, bricht ab."""

    def __init__(
        self,
        repo_root: str | Path,
        results_root: str | Path,
        driver_script: str | Path | None = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.results_root = Path(results_root)
        self.driver_script = (
            Path(driver_script)
            if driver_script is not None
            else self.repo_root / "scripts" / "run_full_game_deck_comparison.py"
        )
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def plan_only(self, spec: RunSpec) -> str:
        """Echten Treiber mit --plan-only laufen lassen (kein Spiel)."""
        errors = validate_spec(spec, self.repo_root)
        if errors:
            raise ValueError("; ".join(errors))
        argv = build_argv(spec, self.driver_script, self.results_root / "plan")
        argv.append("--plan-only")
        env = dict(os.environ)
        env["PYTHONPATH"] = str(self.repo_root / "src")
        proc = subprocess.run(
            argv,
            cwd=self.repo_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if proc.returncode != 0:
            raise ValueError((proc.stderr or proc.stdout).strip()[-2000:])
        return proc.stdout

    def submit(self, spec: RunSpec) -> Job:
        errors = validate_spec(spec, self.repo_root)
        if errors:
            raise ValueError("; ".join(errors))
        job_id = uuid.uuid4().hex[:12]
        out_dir = self.results_root / job_id
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "spec.json").write_text(
            json.dumps(
                {
                    "baseline": spec.baseline,
                    "variant": spec.variant,
                    "swaps": spec.swaps,
                    "opponents": spec.opponents,
                    "seeds": spec.seeds,
                    "no_rotate": spec.no_rotate,
                    "workers": spec.workers,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        job = Job(id=job_id, spec=spec, out_dir=out_dir, status="running")
        with self._lock:
            self._jobs[job_id] = job
        thread = threading.Thread(target=self._run, args=(job,), daemon=True)
        thread.start()
        return job

    def _run(self, job: Job) -> None:
        argv = build_argv(job.spec, self.driver_script, job.out_dir)
        env = dict(os.environ)
        env["PYTHONPATH"] = str(self.repo_root / "src")
        log_path = job.out_dir / "driver.log"
        try:
            with log_path.open("wb") as log_file:
                proc = subprocess.Popen(
                    argv,
                    cwd=self.repo_root,
                    env=env,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                job.process = proc
                proc.wait()
            if job.status == "running":
                job.status = "completed" if proc.returncode == 0 else "failed"
        except OSError as exc:
            job.status = "failed"
            job.error = str(exc)
        job.process = None
        try:
            text = log_path.read_text(encoding="utf-8", errors="replace")
            job.log_tail = "\n".join(text.splitlines()[-50:])
        except OSError:
            job.log_tail = ""

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())

    def cancel(self, job_id: str) -> bool:
        job = self.get(job_id)
        if job is None or job.process is None:
            return False
        try:
            os.killpg(job.process.pid, signal.SIGTERM)
        except (OSError, ProcessLookupError):
            return False
        job.status = "cancelled"
        return True
