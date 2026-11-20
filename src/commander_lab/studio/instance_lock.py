"""One server instance per Studio data folder (#1668).

A lock file ``studio.lock`` in the data folder names the process (PID), a start time and a
heartbeat that the running server refreshes every few seconds. A second ``serve`` on the same
folder finds a fresh heartbeat, says so and ends; a lock whose heartbeat is stale (the server was
killed or the machine lost power) is taken over. Two servers writing one SQLite file are what the
lock prevents, so a lock that cannot be told apart from a live one counts as live.

The PID check is only used where it is safe: ``os.kill(pid, 0)`` terminates the process on Windows,
so there the heartbeat alone decides, and the behaviour of the lock file under Windows is
``UNKNOWN`` until ``windows-runtime.yml`` or the Owner PC shows it.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path

from .store import _repository_root, studio_data_dir

LOCK_NAME = "studio.lock"
HEARTBEAT_SECONDS = 5.0
STALE_AFTER_SECONDS = 30.0
_TAKEOVER_ATTEMPTS = 3


class InstanceAlreadyRunning(RuntimeError):
    """Another server holds the lock of this data folder."""


def resolve_data_folder(data: str | Path | None) -> Path:
    """The folder ``StudioStore.open`` would use, created, never inside the repository."""
    directory = Path(data).resolve() if data is not None else studio_data_dir()
    if directory.is_relative_to(_repository_root()):
        raise RuntimeError(f"the Studio store must be outside the repository: {directory}")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _pid_alive(pid: int) -> bool | None:
    """True/False where a signal-0 probe is safe, ``None`` (unknown) on Windows."""
    if sys.platform == "win32" or pid <= 0:
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by someone else
    except OSError:
        return None
    return True


class InstanceLock:
    """The lock of one data folder; use as a context manager or ``acquire``/``release``."""

    def __init__(
        self,
        folder: str | Path,
        *,
        clock: Callable[[], float] = time.time,
        heartbeat_seconds: float = HEARTBEAT_SECONDS,
        stale_after_seconds: float = STALE_AFTER_SECONDS,
    ) -> None:
        self.path = Path(folder) / LOCK_NAME
        self._clock = clock
        self._heartbeat_seconds = heartbeat_seconds
        self._stale_after = stale_after_seconds
        self._token = uuid.uuid4().hex
        self._started = 0.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.held = False

    def __enter__(self) -> InstanceLock:
        self.acquire()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.release()

    # -- reading -------------------------------------------------------------------------

    def _read(self) -> dict[str, object] | None:
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return loaded if isinstance(loaded, dict) else None

    def _holder_is_live(self, info: dict[str, object] | None) -> tuple[bool, str]:
        """Whether the lock in ``info`` still belongs to a live server, and a description."""
        now = self._clock()
        if info is None:
            # unreadable or half written: fall back to the file time, never guess "stale" early
            try:
                age = now - self.path.stat().st_mtime
            except OSError:
                return False, "kein lesbarer Eintrag"
            return age < self._stale_after, f"unlesbarer Eintrag, Datei {age:.0f} s alt"
        pid = info.get("pid")
        beat = info.get("heartbeat_epoch")
        pid_number = pid if isinstance(pid, int) and not isinstance(pid, bool) else 0
        beat_number = float(beat) if isinstance(beat, int | float) else 0.0
        age = now - beat_number
        description = f"PID {pid_number}, letzter Herzschlag vor {max(age, 0.0):.0f} s"
        if age >= self._stale_after:
            return False, description
        if _pid_alive(pid_number) is False:
            return False, description
        return True, description

    # -- taking and giving back ----------------------------------------------------------

    def _payload(self) -> str:
        return json.dumps(
            {
                "pid": os.getpid(),
                "token": self._token,
                "started_epoch": self._started,
                "heartbeat_epoch": self._clock(),
            },
            sort_keys=True,
        )

    def acquire(self) -> None:
        """Take the lock or raise ``InstanceAlreadyRunning`` with the reason."""
        self._started = self._clock()
        last = "kein Eintrag"
        for _attempt in range(_TAKEOVER_ATTEMPTS):
            try:
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            except FileExistsError:
                live, last = self._holder_is_live(self._read())
                if live:
                    raise InstanceAlreadyRunning(
                        f"Ein Studio-Server läuft schon auf diesem Datenordner ({last}; "
                        f"{self.path}). Dieser Start endet. Läuft keiner mehr, verfällt die "
                        f"Sperre nach {self._stale_after:.0f} s ohne Herzschlag."
                    ) from None
                with contextlib.suppress(FileNotFoundError):
                    self.path.unlink()  # stale: take over; a racing taker fails the O_EXCL next
                continue
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(self._payload())
            self.held = True
            self._stop.clear()
            self._thread = threading.Thread(target=self._beat, name="studio-lock", daemon=True)
            self._thread.start()
            return
        raise InstanceAlreadyRunning(
            f"Die Sperre {self.path} konnte nicht übernommen werden ({last}); "
            "ein anderer Start war schneller."
        )

    def _beat(self) -> None:
        while not self._stop.wait(self._heartbeat_seconds):
            info = self._read()
            if info is not None and info.get("token") != self._token:
                self.held = False  # someone took the stale lock over; do not write over it
                return
            temporary = self.path.with_name(f"{LOCK_NAME}.{self._token[:8]}.tmp")
            try:
                temporary.write_text(self._payload(), encoding="utf-8")
                os.replace(temporary, self.path)
            except OSError:
                with contextlib.suppress(OSError):
                    temporary.unlink()  # a failed beat only ages the lock; the next one retries

    def release(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=2.0)
            self._thread = None
        if not self.held:
            return
        self.held = False
        info = self._read()
        if info is not None and info.get("token") == self._token:
            with contextlib.suppress(OSError):
                self.path.unlink()
