"""Retrieval dates stated in a data folder's own README (Refs #1545).

Several research files carry no date inside the file (signal CSVs, the rulings file, the spellbook
files). The folder README names the retrieval date per file in its table. This module reads that
statement and nothing else: no network, no estimate. A file the README does not list, or lists
without a date, stays undated (the caller leaves ``snapshot_date`` empty, shown as unknown).
"""

from __future__ import annotations

import re
from pathlib import Path

README_NAME = "README.md"
_DATE = re.compile(r"(20\d{2})-(\d{2})-(\d{2})(?:/(\d{1,2}))?")
_TOKEN = re.compile(r"\{(\d+)\.\.(\d+)\}|\{([^{}]+)\}|\*")


def _pattern_regex(pattern: str) -> re.Pattern[str]:
    """``name_{1..4}.csv`` / ``name_{a,b}_*.csv`` as a full-match regex over a file name."""
    out: list[str] = []
    position = 0
    for match in _TOKEN.finditer(pattern):
        out.append(re.escape(pattern[position : match.start()]))
        if match.group(0) == "*":
            out.append(".*")
        elif match.group(1) is not None:
            low, high = int(match.group(1)), int(match.group(2))
            out.append("(?:" + "|".join(str(n) for n in range(low, high + 1)) + ")")
        else:
            out.append("(?:" + "|".join(re.escape(p) for p in match.group(3).split(",")) + ")")
        position = match.end()
    out.append(re.escape(pattern[position:]))
    return re.compile("".join(out))


def _row_dates(text: str) -> list[str]:
    found: list[str] = []
    for year, month, day, day_to in _DATE.findall(text):
        last_day = int(day_to) if day_to else int(day)
        found.append(f"{year}-{month}-{last_day:02d}")
    return found


def readme_retrieval_date(path: Path) -> str | None:
    """The latest date in the README table row that lists ``path``'s file name, or ``None``.

    Only the last cell of the row (source / retrieval) is read, so a date inside a content
    description is never taken for a retrieval date. A window such as ``2026-11-11/12`` yields
    its last day."""
    readme = path.parent / README_NAME
    try:
        lines = readme.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        listed = re.findall(r"`([^`]+)`", cells[0])
        if not any(_pattern_regex(item).fullmatch(path.name) for item in listed):
            continue
        dates = _row_dates(cells[-1])
        return max(dates) if dates else None
    return None
