"""Train a class-data-sharing (AppCDS) archive for the XMage bridge jar.

Every full game starts a fresh bridge JVM, and about 6-8 s of each start is the JVM
loading and verifying XMage's classes. An AppCDS archive of those classes, made once
per jar build, cuts that to about 4 s (measured 2026-10-12 on real 4P pods; the
semantic transcripts of 14 games were identical with and without the archive).

The archive is written by a short real 4P smoke game played with
``-XX:ArchiveClassesAtExit``; the JVM writes it while it exits, so the training run
allows a long shutdown. The script then prints the bridge command to use:

    python scripts/build_xmage_cds_archive.py
    export COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="<printed command>"

The archive belongs to exactly one jar. The JVM checks this itself and runs without
the archive when the jar changed; the printed command sends JVM log output to stderr,
because the warning it writes then would otherwise reach stdout, which carries the
bridge protocol. The archive changes no game behaviour, only how classes are loaded.
"""

from __future__ import annotations

import argparse
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_real_4p_full_game_smoke import build_real_4p_setup  # noqa: E402

from commander_lab.engine.rules.full_game import XmageFullGameRunner  # noqa: E402

DEFAULT_JAR = ROOT / "engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar"
# Unified JVM logging goes to stderr only; stdout is the bridge protocol.
JVM_LOG_FLAGS = ("-Xlog:disable", "-Xlog:all=warning:stderr")
TRAINING_SHUTDOWN_GRACE_SECONDS = 300.0


def bridge_command(jar: Path, archive: Path) -> tuple[str, ...]:
    return (
        "java",
        *JVM_LOG_FLAGS,
        f"-XX:SharedArchiveFile={archive}",
        "-jar",
        str(jar),
        "full-game",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--jar", type=Path, default=DEFAULT_JAR)
    parser.add_argument(
        "--archive", type=Path, default=None, help="default: the jar path with .jsa"
    )
    parser.add_argument("--decisions", type=int, default=40, help="smoke length")
    args = parser.parse_args(argv)

    jar = args.jar.resolve()
    if not jar.is_file():
        print(f"bridge jar not found: {jar}", file=sys.stderr)
        return 2
    archive = (args.archive or jar.with_suffix(".jsa")).resolve()
    archive.unlink(missing_ok=True)

    scenario, decks, pilots, _ = build_real_4p_setup(ROOT)
    training = XmageFullGameRunner(
        (
            "java",
            *JVM_LOG_FLAGS,
            f"-XX:ArchiveClassesAtExit={archive}",
            "-jar",
            str(jar),
            "full-game",
        ),
        shutdown_grace_seconds=TRAINING_SHUTDOWN_GRACE_SECONDS,
    )
    training.run_smoke(
        scenario=scenario,
        decks=decks,
        pilots=pilots,
        smoke_decision_target=args.decisions,
    )
    if not archive.is_file():
        print(f"the training JVM wrote no archive at {archive}", file=sys.stderr)
        return 1
    print(shlex.join(bridge_command(jar, archive)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
