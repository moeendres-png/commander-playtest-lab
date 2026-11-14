#!/usr/bin/env python3
"""Turn ``ruff check --output-format=json`` into GitHub workflow annotations.

CI runs ruff once with JSON output (kept as evidence) and prints the annotations from that
file, instead of running the whole check a second time with ``--output-format=github``.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path


def _escape(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def annotations(diagnostics: Sequence[dict[str, object]], workspace: Path | None = None) -> list[str]:
    lines = []
    for item in diagnostics:
        location = item.get("location") or {}
        end = item.get("end_location") or {}
        assert isinstance(location, dict) and isinstance(end, dict)
        name = Path(str(item.get("filename", "")))
        if workspace is not None:
            try:
                name = name.relative_to(workspace)
            except ValueError:
                pass
        code = item.get("code") or "ruff"
        lines.append(
            f"::error title=Ruff ({code}),file={name},line={location.get('row', 1)},"
            f"col={location.get('column', 1)},endLine={end.get('row', location.get('row', 1))},"
            f"endColumn={end.get('column', location.get('column', 1))}::{_escape(str(item.get('message', '')))}"
        )
    return lines


def main(argv: Sequence[str]) -> int:
    if len(argv) != 1:
        print("usage: ci_ruff_annotations.py RUFF_JSON", file=sys.stderr)
        return 2
    try:
        diagnostics = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"no annotations: {error}", file=sys.stderr)
        return 0
    print("\n".join(annotations(diagnostics, Path.cwd())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
