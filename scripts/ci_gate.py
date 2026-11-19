#!/usr/bin/env python3
"""Decide the required ``quality`` gate of ``.github/workflows/ci.yml`` from job results.

Every needed job must have ended ``success``. The only accepted ``skipped`` is a job named by
``--allow-skipped`` (the two packaging jobs) while the ``changes`` job succeeded, its flag
``--packaging-needed`` is exactly ``false`` and every job named by ``--allow-skipped`` was
skipped: the named jobs are halves of one piece of work and are skipped together or not at all.
A ``--allow-skipped`` name without a ``--job`` result fails the gate. ``cancelled``,
``failure``, any other value and a skip while the flag is not ``false`` fail the gate. Every result is printed.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence

CONTROL_JOB = "changes"


def evaluate(
    results: Mapping[str, str], skip_allowed: Sequence[str], needed_flag: str
) -> tuple[bool, list[str]]:
    """Return ``(ok, lines)``: the verdict and one report line per job."""
    ok = True
    lines: list[str] = []
    skipped_together = all(results.get(name) == "skipped" for name in skip_allowed)
    for name, result in results.items():
        if result == "success":
            lines.append(f"ok: {name} = success")
        elif (
            result == "skipped"
            and name in skip_allowed
            and skipped_together
            and results.get(CONTROL_JOB) == "success"
            and needed_flag == "false"
        ):
            lines.append(f"ok: {name} = skipped (not needed for this change)")
        else:
            ok = False
            lines.append(f"::error::job {name} finished as '{result}', not success")
    if CONTROL_JOB not in results:
        ok = False
        lines.append(f"::error::the {CONTROL_JOB} job result was not provided")
    for name in skip_allowed:
        if name not in results:
            ok = False
            lines.append(f"::error::--allow-skipped {name} has no --job {name} result")
    return ok, lines


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--job", action="append", default=[], metavar="NAME=RESULT")
    parser.add_argument("--allow-skipped", action="append", default=[], metavar="NAME")
    parser.add_argument("--packaging-needed", default="")
    args = parser.parse_args(argv)
    results: dict[str, str] = {}
    for item in args.job:
        name, _, result = item.partition("=")
        if not name or name in results:
            print(f"::error::bad or repeated --job {item!r}", file=sys.stderr)
            return 2
        results[name] = result
    ok, lines = evaluate(results, args.allow_skipped, args.packaging_needed)
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
