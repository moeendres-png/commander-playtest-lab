"""Remembered answers of expensive read routes (#1563).

Several read routes (``/api/evidence``, ``/api/pool``, ``/api/rating-layers`` and others)
recomputed the same answer on every call although nothing had changed. Here an answer is kept
as the JSON bytes the route would send, keyed by

- the store state (``cache.cached``: the store file's stamp, so every committed write, import or
  mark change makes the next request recompute; an open transaction or an in-memory store is
  never remembered),
- the route name and all of its parameters, and
- the identity (path, size, modification time) of every data file the answer reads per call
  (``files``), so a changed repository file is seen at once, as before.

The bytes are produced exactly as FastAPI produces them for the route's declared return type
(``TypeAdapter.validate_python`` then ``dump_json``, the framework's own fast path), so a
remembered answer is byte-identical to a computed one. Bytes cannot be changed by a caller:
the remembered value is safe by construction, whatever a reader does with what it gets.

Answers that read no store at all (``/api/tournament-conversion`` reads only the TopDeck
files) are kept per file state alone (``file_answer``).

Size: the answers share the size limit of ``cache`` and have a limit of their own there (kind
``answer``: at most ``cache.KIND_LIMITS['answer']`` entries and bytes), so many distinct
parameters (a search typed letter by letter) push out older answers, never the warm figures
behind them. ``file_answer`` holds at most ``_MAX_FILE_ANSWERS`` entries.
"""

from __future__ import annotations

import os
import threading
from collections import OrderedDict
from collections.abc import Callable, Hashable, Iterable
from pathlib import Path
from typing import Literal

from fastapi import Response
from pydantic import TypeAdapter

from . import cache
from .store import StudioStore

OBJECT = TypeAdapter(dict[str, object])
OBJECT_LIST = TypeAdapter(list[dict[str, object]])

_MAX_FILE_ANSWERS = 8
_file_lock = threading.Lock()
_file_answers: OrderedDict[tuple[Hashable, ...], bytes] = OrderedDict()

type FileStamp = tuple[str, int, int] | tuple[str, None, None]
type Shape = Literal["object", "list"]


def file_stamp(path: str | Path) -> FileStamp:
    """Path, size and modification time of a data file (``None`` twice when it is absent)."""
    try:
        found = os.stat(path)
    except OSError:
        return (str(path), None, None)
    return (str(path), found.st_size, found.st_mtime_ns)


def folder_stamp(folder: str | Path) -> tuple[FileStamp, ...]:
    """The stamps of every file directly in ``folder`` (sorted by name), so a new, removed or
    changed file changes the result; empty when the folder is absent."""
    try:
        names = sorted(entry.name for entry in os.scandir(folder) if entry.is_file())
    except OSError:
        return ()
    return tuple(file_stamp(Path(folder) / name) for name in names)


def dump(value: object, shape: Shape = "object") -> bytes:
    """The JSON bytes FastAPI sends for ``value`` from a route declared to return
    ``dict[str, object]`` (``shape`` ``object``) or ``list[dict[str, object]]`` (``list``)."""
    if shape == "list":
        return OBJECT_LIST.dump_json(
            OBJECT_LIST.validate_python(value, from_attributes=True), by_alias=True
        )
    return OBJECT.dump_json(OBJECT.validate_python(value, from_attributes=True), by_alias=True)


def _response(body: bytes) -> Response:
    return Response(content=body, media_type="application/json")


def json_answer(
    store: StudioStore,
    name: str,
    params: tuple[Hashable, ...],
    compute: Callable[[], object],
    *,
    files: Iterable[str | Path] = (),
    shape: Shape = "object",
) -> Response:
    """The answer of route ``name`` for ``params``, remembered per store state and data files.
    ``compute`` may raise (the error reaches the route as before and nothing is kept)."""
    key = ("answer", name, params, tuple(file_stamp(path) for path in files))
    return _response(cache.cached(store, key, lambda: dump(compute(), shape)))


def file_answer(
    name: str,
    params: tuple[Hashable, ...],
    stamps: tuple[Hashable, ...],
    compute: Callable[[], object],
    *,
    shape: Shape = "object",
) -> Response:
    """Like ``json_answer`` for a route that reads no store: remembered per ``stamps`` (the
    identity of every file it reads) and ``params``."""
    key = (name, params, stamps)
    with _file_lock:
        body = _file_answers.get(key)
        if body is not None:
            _file_answers.move_to_end(key)
    if body is None:
        body = dump(compute(), shape)
        with _file_lock:
            _file_answers[key] = body
            while len(_file_answers) > _MAX_FILE_ANSWERS:
                _file_answers.popitem(last=False)
    return _response(body)


def clear() -> None:
    """Forget the answers kept per file state (the store answers go with ``cache``)."""
    with _file_lock:
        _file_answers.clear()


__all__ = ["OBJECT", "OBJECT_LIST", "clear", "dump", "file_answer", "file_stamp", "json_answer"]
