from __future__ import annotations

import os
import subprocess
import sys

from commander_lab.whole_deck.optimizer_v2 import _process_is_alive


def test_process_liveness_recognizes_current_process_without_signal() -> None:
    assert _process_is_alive(os.getpid())
    assert not _process_is_alive(-1)


def test_process_liveness_recognizes_external_child_without_signal() -> None:
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        assert _process_is_alive(child.pid)
    finally:
        child.terminate()
        child.wait(timeout=10)
