#!/usr/bin/env python3
"""Throwaway diagnosis (M1): rerun the p1g1 sweep with a tee on the bridge
subprocess streams, so the raw failure (redacted by the Lab runner in normal
output) becomes visible locally. Logs stay in ~/workspace/tmp/m1/diag/ and
never enter any report. Faithful to the sweep: same module, same arguments.
"""
import subprocess
import sys
import threading
from pathlib import Path

DIAG = Path("/home/hatch/workspace/tmp/m1/diag")
DIAG.mkdir(parents=True, exist_ok=True)
_counter = {"n": 0}
_lock = threading.Lock()
RealPopen = subprocess.Popen


class TeeStream:
    def __init__(self, raw, logfile):
        self._raw = raw
        self._log = logfile

    def readline(self, *a):
        line = self._raw.readline(*a)
        if line:
            try:
                self._log.write(line)
                self._log.flush()
            except Exception:
                pass
        return line

    def read(self, *a):
        data = self._raw.read(*a)
        if data:
            try:
                self._log.write(data)
                self._log.flush()
            except Exception:
                pass
        return data

    def __iter__(self):
        return self

    def __next__(self):
        line = self.readline()
        if not line:
            raise StopIteration
        return line

    def __getattr__(self, name):
        return getattr(self._raw, name)


class TeeStdin:
    def __init__(self, raw, logfile):
        self._raw = raw
        self._log = logfile

    def write(self, data):
        try:
            self._log.write(data)
            self._log.flush()
        except Exception:
            pass
        return self._raw.write(data)

    def __getattr__(self, name):
        return getattr(self._raw, name)


def TeePopen(*args, **kwargs):
    proc = RealPopen(*args, **kwargs)
    with _lock:
        n = _counter["n"]
        _counter["n"] += 1
    if kwargs.get("stdout") is subprocess.PIPE and proc.stdout is not None:
        out_log = open(DIAG / f"bridge_{n:02d}_stdout.log", "w", encoding="utf-8", errors="replace")
        proc.stdout = TeeStream(proc.stdout, out_log)
    if kwargs.get("stderr") is subprocess.PIPE and proc.stderr is not None:
        err_log = open(DIAG / f"bridge_{n:02d}_stderr.log", "w", encoding="utf-8", errors="replace")
        proc.stderr = TeeStream(proc.stderr, err_log)
    if kwargs.get("stdin") is subprocess.PIPE and proc.stdin is not None:
        in_log = open(DIAG / f"bridge_{n:02d}_stdin.log", "w", encoding="utf-8", errors="replace")
        proc.stdin = TeeStdin(proc.stdin, in_log)
    return proc


subprocess.Popen = TeePopen

sys.path.insert(0, "/home/hatch/workspace/github/wt-m1-sweep/scripts")
sys.argv = [
    "precon_pod_sweep.py",
    "--jar", "/home/hatch/workspace/tmp/m1/bridge.jar",
    "--out", "/home/hatch/workspace/tmp/m1/diag/sweep_tee.json",
    "--import-report", "/home/hatch/workspace/tmp/m1/imports.json",
    "--workers", "1",
]
import precon_pod_sweep  # noqa: E402

raise SystemExit(precon_pod_sweep.main())
