"""Launch options that make a bridge JVM cheaper without changing a game.

One source for the speed benchmark (``scripts/benchmark_xmage_full_games.py --fast``) and the
Commander Studio series: both start the bridge with the same options, so a measured identity
holds for both.
"""

from __future__ import annotations

from pathlib import Path


def fast_jvm_options(jar: Path) -> list[str]:
    """Launch options that make a bridge JVM cheaper without changing a game.

    Serial GC: the live set is small and the games allocate about 1 GB/s, so one collector
    thread beats G1's concurrent threads (measured -10 % CPU, identical transcripts). With an
    AppCDS archive next to the jar (``<jar>.jsa`` from ``build_xmage_cds_archive.py``) the JVM
    also maps its classes instead of loading them; JVM logging then goes to stderr, because the
    JVM's own warning (a stale archive) would otherwise reach the protocol on stdout.
    """
    # H2 AUTO_SERVER listens on every interface by default; the bridge needs the loopback only.
    options = ["-XX:+UseSerialGC", "-Dh2.bindAddress=127.0.0.1"]
    archive = jar.resolve().with_suffix(".jsa")
    if archive.is_file():
        options += ["-Xlog:disable", "-Xlog:all=warning:stderr", f"-XX:SharedArchiveFile={archive}"]
    return options
