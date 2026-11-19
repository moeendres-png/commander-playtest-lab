"""Retrieval dates and source addresses stated in a data folder's own README (Refs #1545).

Several research files carry no date inside the file (signal CSVs, the rulings file, the spellbook
files). The folder README names the retrieval date per file in its table. The readers here take
that statement and nothing else: no network, no estimate. A file the README does not list, or
lists without a retrieval date, stays undated (the caller leaves ``snapshot_date`` empty, shown as
unknown). ``register_stated_source`` writes what the readers found into the ``source`` row of the
file: a stated value replaces the stored one of the same file hash, an unstated value leaves the
stored one untouched (it is never blanked, so a stored value without a README statement stays).

Only a date that directly follows the word ``Abruf`` (or ``Abrufdatum``) in the last cell of the
row is a retrieval date. A date that stands for a count (``Zählung``), a build (``Build``), a
filtering step or a re-fetch of part of the data is not, and an ``Erstabruf`` is not the current
retrieval either. A window such as ``Abruf 2026-11-11/12`` yields its first day: everything in the
file is at least that fresh, which is the statement the data supports. Two different retrieval
dates in one cell are ambiguous and yield nothing.

The same last cell may name where the file comes from as an address (``https://...``); that is
the source address (``source.url``), read only when the cell names exactly one address (#1545).
An address is ``http`` or ``https`` with a host name made of non-empty labels (letters, digits,
hyphens), an optional port and path, and no credentials; a trailing full stop, comma, colon,
quotation mark or Markdown emphasis mark is not part of it. Anything that is not such an address
(``https://.``, an address with a quotation mark, asterisk or bracket inside) makes the cell
unreadable for the address: unknown, never a repaired guess.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from .store import DataClass, StudioStore

README_NAME = "README.md"
_RETRIEVAL = re.compile(r"\bAbruf(?:datum)?\s*:?\s*(20\d{2})-(\d{2})-(\d{2})(?:/\d{1,2})?")
_ADDRESS = re.compile(r"https?://[^\s)\]>|`]+")
_ADDRESS_TAIL = ".,;:!?*\"'"  # sentence punctuation, quotation and emphasis marks after an address
_ADDRESS_FORBIDDEN = re.compile(r"[\"'*<>(){}\[\]\\^|`]")
_HOST_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?")
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


def _retrieval_dates(cell: str) -> set[str]:
    """The valid calendar dates a cell names as ``Abruf <Datum>`` (a window: its first day)."""
    found: set[str] = set()
    for year, month, day in _RETRIEVAL.findall(cell):
        try:
            found.add(date(int(year), int(month), int(day)).isoformat())
        except ValueError:
            continue
    return found


def _readme_source_cell(path: Path) -> str | None:
    """The last cell (source / retrieval) of the README table row that lists ``path``'s file
    name, or ``None`` (no README, no such row)."""
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
        if any(_pattern_regex(item).fullmatch(path.name) for item in listed):
            return cells[-1]
    return None


def readme_retrieval_date(path: Path) -> str | None:
    """The retrieval date in the README table row that lists ``path``'s file name, or ``None``.

    Only the last cell of the row (source / retrieval) is read, so a date inside a content
    description is never taken for a retrieval date, and only a date marked ``Abruf`` counts
    (see the module docstring). Anything else is ``None``: unknown, never an estimate."""
    cell = _readme_source_cell(path)
    if cell is None:
        return None
    dates = _retrieval_dates(cell)
    return next(iter(dates)) if len(dates) == 1 else None


def _valid_address(candidate: str) -> str | None:
    """``candidate`` without trailing punctuation or Markdown marks, or ``None`` when it is not
    an ``http``/``https`` address with a host (see the module docstring)."""
    value = candidate.rstrip(_ADDRESS_TAIL)
    if _ADDRESS_FORBIDDEN.search(value):
        return None
    try:
        parts = urlsplit(value)
        host, _port = parts.hostname, parts.port  # ``port`` raises ValueError for a bad port
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not host or "@" in parts.netloc:
        return None
    if not all(_HOST_LABEL.fullmatch(label) for label in host.split(".")):
        return None
    return value


def readme_source_url(path: Path) -> str | None:
    """The source address in the last cell of the README row that lists ``path``'s file name.

    Only when the cell names exactly one valid address (see the module docstring); two different
    addresses, none, or a malformed one give ``None``: unknown, never a guess."""
    cell = _readme_source_cell(path)
    if cell is None:
        return None
    found = {_valid_address(match) for match in _ADDRESS.findall(cell)}
    return next(iter(found)) if len(found) == 1 and None not in found else None


def register_stated_source(
    store: StudioStore,
    *,
    data_class: DataClass,
    title: str,
    sha256: str,
    snapshot_date: str | None,
    url: str | None = None,
) -> str:
    """``store.register_source`` for a file whose date and address come from its own statement.

    ``register_source`` never overwrites a stored date, so a store imported before the rule of
    this module keeps what that older rule wrote (an id fragment, a tournament date). A value
    that this import states (retrieval date from the file or its README, address from its
    README) replaces what is stored for the same file hash; a value it does not state leaves the
    stored one as it is. Nothing is estimated."""
    source_id = store.register_source(
        data_class=data_class, title=title, sha256=sha256, snapshot_date=snapshot_date, url=url
    )
    if snapshot_date:
        store.connection.execute(
            "UPDATE source SET snapshot_date = ? WHERE source_id = ? AND snapshot_date IS NOT ?",
            (snapshot_date, source_id, snapshot_date),
        )
    if url:
        store.connection.execute(
            "UPDATE source SET url = ? WHERE source_id = ? AND url IS NOT ?",
            (url, source_id, url),
        )
    return source_id
