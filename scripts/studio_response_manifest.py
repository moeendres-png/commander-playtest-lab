"""Response manifest of a local Studio server on a store COPY, and the comparison of two manifests.

Refs #1612 (architecture option D, package D-0 part i). Equivalence proof for refactors of the
Studio server: the same store template and the same inputs must give byte-identical answers
before and after a change.

``run``     copies the store template into a work folder (the template is only read; its files
            are hashed before and after and the run fails if anything changed), starts
            ``python -m commander_lab.studio serve`` from ``--src`` on a free local port against
            the copy, asks the 30 read routes in ``read_requests`` ``--repeat`` times each and
            writes status, length and SHA-256 per answer as a manifest JSON. The manifest must
            lie outside the repository. The copy is deleted afterwards (``--keep-work`` keeps it).
``writes``  the optional write matrix: after each write (favorite, mark, label, draft, revision,
            primer, universe profile) the read routes plus ``observer_requests`` of the running
            server must equal those of a freshly started server on the same written copy.
``compare`` two ``run`` manifests; exit 0 if the inputs and every answer agree, 1 otherwise.

Normalisation: only for fields shown to depend on the run, listed in ``NORMALIZATIONS``. Today
that is ``image_cache.folder`` of ``GET /api/status``: the server reports the absolute folder of
the store copy, which differs between two runs by construction. It is replaced by
``<STUDIO_DATA>/images`` only when it is exactly the folder of this run's copy; the raw length
and hash stay in the manifest. Every other byte is compared as served.

Portability: standard library only, no shell, no ``/proc``; the server is started with
``subprocess.Popen`` and stopped through that handle (its own PID) only; HTTP goes to
``127.0.0.1`` without any proxy. Exit codes: 0 equal / done, 1 different, 2 usage or setup error,
3 safety stop (template changed, the server answered for another store).

Usage::

    python scripts/studio_response_manifest.py run --store <template folder> --out <file>
        [--src <checkout>/src] [--commander NAME] [--deck-id ID] [--repeat 2]
    python scripts/studio_response_manifest.py writes --store <template folder> --out <file>
    python scripts/studio_response_manifest.py compare <manifest A> <manifest B>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORMAT = "studio-response-manifest/1"
WRITES_FORMAT = "studio-response-writes/1"
DEFAULT_COMMANDER = "Chulane, Teller of Tales"
DEFAULT_DECK = "chulane"
DATABASE = "studio.sqlite3"
DATA_PLACEHOLDER = "<STUDIO_DATA>"
WRITE_MARK = "d0-messnetz"

# Route key -> JSON paths whose value is the absolute store folder of the run (see module text).
NORMALIZATIONS: dict[str, tuple[tuple[str, ...], ...]] = {
    "GET /api/status": (("image_cache", "folder"),),
}


class ManifestError(Exception):
    """A setup or usage problem (exit 2)."""


class SafetyStop(Exception):
    """The template changed or the server is not the one this run started (exit 3)."""


@dataclass(frozen=True)
class Request:
    method: str
    path: str
    body: object = None

    @property
    def key(self) -> str:
        return f"{self.method} {self.path}"


@dataclass(frozen=True)
class DeckInputs:
    commander: str
    deck_id: str
    revision_id: str
    cards: tuple[tuple[str, int, str], ...]

    def card_entries(self) -> list[dict[str, object]]:
        return [
            {"card_id": card_id, "quantity": quantity, "zone": zone}
            for card_id, quantity, zone in self.cards
        ]

    def main_ids(self) -> list[str]:
        return [card_id for card_id, _quantity, zone in self.cards if zone == "main"]

    def record(self) -> dict[str, object]:
        listing = json.dumps(self.card_entries(), sort_keys=True).encode("utf-8")
        return {
            "commander": self.commander,
            "deck_id": self.deck_id,
            "revision_id": self.revision_id,
            "cards": len(self.cards),
            "cards_sha256": hashlib.sha256(listing).hexdigest(),
            "environment": studio_environment(),
        }


def _q(value: str) -> str:
    return urllib.parse.quote(value, safe="")


def read_requests(inputs: DeckInputs) -> list[Request]:
    """The 30 read routes (2 pages, 28 API answers). POST routes here compute and never write."""
    c = _q(inputs.commander)
    cards = inputs.card_entries()
    main = inputs.main_ids()
    if len(main) < 2:
        raise ManifestError(f"deck {inputs.deck_id} has fewer than two main cards")
    owned = {"cards": cards, "owned_only": True}
    return [
        Request("GET", "/"),
        Request("GET", "/tierliste.html"),
        Request("GET", "/api/status"),
        Request("GET", "/api/commanders?collection=true"),
        Request("GET", f"/api/pool?commander={c}"),
        Request("GET", f"/api/layers?commander={c}"),
        Request("GET", f"/api/cohorts?commander={c}"),
        Request("GET", "/api/allocation"),
        Request("GET", f"/api/evidence?view=commander&commander={c}"),
        Request("GET", "/api/data-report"),
        Request("POST", "/api/strength", {"commander": inputs.commander}),
        Request("GET", f"/api/rating-layers?commander={c}&pod_size=4"),
        Request("GET", f"/api/universe/options?commander={c}"),
        Request("GET", f"/api/universe/counted?commander={c}"),
        Request("GET", f"/api/roles/audit?commander={c}"),
        Request("GET", f"/api/tournament-conversion?commander={c}"),
        Request("GET", "/api/decks"),
        Request("GET", f"/api/revisions/{_q(inputs.revision_id)}"),
        Request("GET", f"/api/outcomes?deck_id={_q(inputs.deck_id)}"),
        Request("GET", f"/api/deck-browser?commander={c}"),
        Request("GET", f"/api/similar-decks?commander={c}&deck_id={_q(inputs.deck_id)}"),
        Request("POST", "/api/check", owned),
        Request("POST", "/api/deck-doctor", {"commander": inputs.commander, "cards": cards}),
        Request("POST", "/api/deck-evidence", {"cards": cards}),
        Request(
            "POST",
            "/api/card-duel",
            {
                "commander": inputs.commander,
                "deck_card_ids": main,
                "card_a": main[0],
                "card_b": main[1],
            },
        ),
        Request("POST", "/api/cut-lab", {"cards": cards}),
        Request("POST", "/api/deck-facts", owned),
        Request(
            "POST",
            "/api/land-advisor",
            {**owned, "cohort": "all", "min_share": 0.20},
        ),
        Request("POST", "/api/castability", owned),
        Request("POST", "/api/packages", {"commander": inputs.commander, "cards": cards}),
    ]


def observer_requests(inputs: DeckInputs) -> list[Request]:
    """Extra reads of the write matrix only: the routes that show the primer, the universe
    profiles and the label list, which none of the 30 read routes reflects."""
    return [
        Request("GET", f"/api/decks/{_q(inputs.deck_id)}/primer"),
        Request("GET", "/api/universe/profiles"),
        Request("GET", "/api/labels"),
    ]


def write_requests(inputs: DeckInputs) -> list[tuple[str, Request]]:
    """The write matrix: one write per kind of user state, in this order."""
    main = inputs.main_ids()
    if len(main) < 3:
        raise ManifestError(f"deck {inputs.deck_id} has fewer than three main cards")
    deck = _q(inputs.deck_id)
    cards = inputs.card_entries()
    return [
        ("favorite", Request("PUT", f"/api/cards/{_q(main[0])}/favorite", {"favorite": True})),
        (
            "mark",
            Request(
                "PUT",
                f"/api/cards/{_q(main[1])}/mark",
                {"favorite": False, "excluded": False, "note": WRITE_MARK},
            ),
        ),
        ("label", Request("PUT", f"/api/cards/{_q(main[2])}/labels", {"labels": [WRITE_MARK]})),
        (
            "draft",
            Request(
                "PUT",
                f"/api/decks/{deck}/branches/main/draft",
                {"cards": cards, "base_revision_id": inputs.revision_id},
            ),
        ),
        (
            "revision",
            Request(
                "POST",
                f"/api/decks/{deck}/revisions",
                {
                    "cards": cards,
                    "branch": WRITE_MARK,
                    "note": WRITE_MARK,
                    "parent_revision_id": inputs.revision_id,
                },
            ),
        ),
        ("primer", Request("PUT", f"/api/decks/{deck}/primer", {"content": WRITE_MARK})),
        (
            "universe_profile",
            Request(
                "PUT",
                f"/api/universe/profiles/{WRITE_MARK}?commander={_q(inputs.commander)}",
                {"commanders": [inputs.commander]},
            ),
        ),
    ]


# --- normalisation --------------------------------------------------------------------------


def _fastapi_json(value: object) -> bytes:
    """Serialised as FastAPI's ``JSONResponse.render`` does."""
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, indent=None, separators=(",", ":")
    ).encode("utf-8")


def _same_path(left: str, right: Path) -> bool:
    def canon(value: str) -> str:
        return os.path.normcase(os.path.normpath(os.path.abspath(value)))

    return canon(left) == canon(str(right))


def normalize(key: str, body: bytes, data_folder: Path) -> tuple[bytes, list[str]]:
    """The body with the run-dependent fields of ``NORMALIZATIONS[key]`` replaced, and the
    dotted names of the fields that were replaced. A field is only replaced when its value is
    exactly ``<data_folder>/images``; any other value stays and will show as a difference."""
    paths = NORMALIZATIONS.get(key)
    if not paths:
        return body, []
    try:
        parsed = json.loads(body)
    except ValueError:
        return body, []
    if _fastapi_json(parsed) != body:
        raise ManifestError(f"{key}: the answer does not re-serialise byte-identically")
    applied: list[str] = []
    for path in paths:
        holder: object = parsed
        for part in path[:-1]:
            holder = holder.get(part) if isinstance(holder, dict) else None
        if not isinstance(holder, dict):
            continue
        value = holder.get(path[-1])
        if isinstance(value, str) and _same_path(value, data_folder / "images"):
            holder[path[-1]] = f"{DATA_PLACEHOLDER}/images"
            applied.append(".".join(path))
    if not applied:
        return body, []
    return _fastapi_json(parsed), applied


# --- HTTP and server --------------------------------------------------------------------------

_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(base: str, request: Request, timeout: float = 900.0) -> tuple[int, bytes, float]:
    """(status, body, milliseconds). Write marker and JSON body as the page sends them."""
    data = None if request.body is None else json.dumps(request.body).encode("utf-8")
    prepared = urllib.request.Request(
        base + request.path,
        data=data,
        method=request.method,
        headers={"x-studio": "1", "content-type": "application/json"},
    )
    started = time.perf_counter()
    try:
        with _OPENER.open(prepared, timeout=timeout) as response:
            status, body = int(response.status), response.read()
    except urllib.error.HTTPError as error:
        status, body = int(error.code), error.read()
    return status, body, (time.perf_counter() - started) * 1000


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


class StudioServer:
    """One ``commander_lab.studio serve`` child process on a store copy."""

    def __init__(self, python: str, src: Path, data: Path, log: Path, port: int) -> None:
        self.python, self.src, self.data, self.log = python, src, data, log
        self.port = port or free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.process: subprocess.Popen[bytes] | None = None
        self.startup_seconds = 0.0

    def start(self, timeout: float) -> None:
        env = {
            **os.environ,
            "PYTHONPATH": str(self.src),
            "COMMANDER_LAB_STUDIO_DATA": str(self.data),
            "PYTHONIOENCODING": "utf-8",
        }
        started = time.perf_counter()
        with self.log.open("ab") as log:
            self.process = subprocess.Popen(
                [self.python, "-m", "commander_lab.studio", "serve", "--port", str(self.port)],
                env=env,
                cwd=str(self.data.parent),
                stdout=log,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
            )
        deadline = started + timeout
        while True:
            if self.process.poll() is not None:
                raise ManifestError(f"server exited with {self.process.returncode}: {self.tail()}")
            try:
                status, _body, _ms = call(self.base, Request("GET", "/"), timeout=5)
                if status == 200:
                    break
            except OSError:
                pass
            if time.perf_counter() > deadline:
                self.stop()
                raise ManifestError(f"server did not answer within {timeout:.0f} s: {self.tail()}")
            time.sleep(0.2)
        self.startup_seconds = round(time.perf_counter() - started, 2)
        self.check_store()

    def check_store(self) -> None:
        """Safety: the server must report the image folder of THIS copy (never another store)."""
        status, body, _ms = call(self.base, Request("GET", "/api/status"))
        folder: object = None
        if status == 200:
            parsed = json.loads(body)
            image_cache = parsed.get("image_cache") if isinstance(parsed, dict) else None
            folder = image_cache.get("folder") if isinstance(image_cache, dict) else None
        if not (isinstance(folder, str) and _same_path(folder, self.data / "images")):
            self.stop()
            raise SafetyStop(f"server on port {self.port} reports store folder {folder!r}")

    def stop(self) -> None:
        if self.process is None or self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=30)

    def tail(self, lines: int = 15) -> str:
        try:
            text = self.log.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        return " | ".join(text.splitlines()[-lines:])


# --- store copy and template guard ------------------------------------------------------------


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


SQLITE_SIDECARS = ("-wal", "-shm", "-journal")


def _single_file_set(template: Path) -> list[Path]:
    """A single-file template plus its SQLite side files that exist next to it."""
    sidecars = [template.with_name(template.name + suffix) for suffix in SQLITE_SIDECARS]
    return [template, *(path for path in sidecars if path.is_file())]


def template_fingerprint(template: Path) -> dict[str, dict[str, object]]:
    """Per file of the template: size, mtime in ns and SHA-256 (the template is only read).
    A single-file template counts together with its ``-wal``/``-shm``/``-journal`` files."""
    files = _single_file_set(template) if template.is_file() else sorted(template.rglob("*"))
    result: dict[str, dict[str, object]] = {}
    for path in files:
        if not path.is_file():
            continue
        stat = path.stat()
        name = path.name if template.is_file() else path.relative_to(template).as_posix()
        result[name] = {
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "sha256": _sha256_file(path),
        }
    return result


def _inside(path: Path, folder: Path) -> bool:
    try:
        path.resolve().relative_to(folder.resolve())
    except ValueError:
        return False
    return True


def copy_store(template: Path, destination: Path) -> Path:
    """Copy the template (a folder with ``studio.sqlite3``, or that file) to ``destination``;
    returns the data folder of the copy. Refuses any overlap of template and destination."""
    if not template.exists():
        raise ManifestError(f"store template {template} does not exist")
    folder = template if template.is_dir() else template.parent
    if template.is_dir() and not (template / DATABASE).is_file():
        raise ManifestError(f"store template {template} has no {DATABASE}")
    if _inside(destination, folder) or _inside(folder, destination):
        raise ManifestError("store copy and template overlap; the template is never written")
    if destination.exists():
        raise ManifestError(f"copy destination {destination} exists already")
    if template.is_dir():
        shutil.copytree(template, destination)
    else:
        destination.mkdir(parents=True)
        for path in _single_file_set(template):
            shutil.copy2(path, destination / (DATABASE + path.name[len(template.name) :]))
    return destination


def check_out_path(out: Path, repositories: Sequence[Path]) -> None:
    """The manifest is evidence of one run and never lands in a repository checkout."""
    for repo in repositories:
        if _inside(out, repo):
            raise ManifestError(f"--out {out} lies inside the repository {repo}; write it outside")


# --- manifest ---------------------------------------------------------------------------------


def _load() -> object:
    getter = getattr(os, "getloadavg", None)
    if getter is None:
        return "UNKNOWN"
    return [round(value, 2) for value in getter()]


def _git(src: Path, *args: str) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(src), *args], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"


def studio_environment() -> dict[str, str]:
    """``COMMANDER_LAB_*`` variables the server inherits (they can change answers, e.g.
    ``COMMANDER_LAB_TOPDECK_DIR``); the data folder variable is set by this tool."""
    return {
        name: value
        for name, value in sorted(os.environ.items())
        if name.startswith("COMMANDER_LAB_") and name != "COMMANDER_LAB_STUDIO_DATA"
    }


def resolve_inputs(base: str, commander: str, deck_id: str) -> DeckInputs:
    """Deck and cards from the copy itself: ``/api/decks`` -> branch ``main`` (else the first)
    -> ``/api/revisions/<id>``."""
    status, body, _ms = call(base, Request("GET", "/api/decks"))
    decks = json.loads(body) if status == 200 else None
    if not isinstance(decks, list):
        raise ManifestError(f"/api/decks answered {status}")
    deck = next((d for d in decks if isinstance(d, dict) and d.get("deck_id") == deck_id), None)
    if deck is None:
        known = [d.get("deck_id") for d in decks if isinstance(d, dict)]
        raise ManifestError(f"deck {deck_id!r} not in the store copy (decks: {known})")
    branches = [b for b in deck.get("branches") or [] if isinstance(b, dict)]
    branch = next((b for b in branches if b.get("branch") == "main"), None) or (
        branches[0] if branches else None
    )
    if branch is None:
        raise ManifestError(f"deck {deck_id!r} has no saved revision")
    revision_id = str(branch["revision_id"])
    status, body, _ms = call(base, Request("GET", f"/api/revisions/{_q(revision_id)}"))
    revision = json.loads(body) if status == 200 else None
    if not isinstance(revision, dict) or not isinstance(revision.get("cards"), list):
        raise ManifestError(f"/api/revisions/{revision_id} answered {status}")
    cards = tuple(
        (str(card["card_id"]), int(card["quantity"]), str(card["zone"]))
        for card in revision["cards"]
        if isinstance(card, dict)
    )
    return DeckInputs(commander, deck_id, revision_id, cards)


def answer_records(
    base: str, requests: Sequence[Request], data_folder: Path, repeat: int
) -> list[dict[str, object]]:
    """One record per request: status, length and SHA-256 of the first answer (normalised),
    raw length and hash, whether all ``repeat`` answers were byte-identical, and timings."""
    records: list[dict[str, object]] = []
    for request in requests:
        hashes: set[str] = set()
        timings: list[float] = []
        first: tuple[int, bytes] | None = None
        for _ in range(max(1, repeat)):
            status, body, ms = call(base, request)
            timings.append(round(ms, 1))
            hashes.add(f"{status}:{hashlib.sha256(body).hexdigest()}")
            if first is None:
                first = (status, body)
        if first is None:
            raise ManifestError("no answer recorded")
        status, raw = first
        normalized, applied = normalize(request.key, raw, data_folder)
        records.append(
            {
                "key": request.key,
                "status": status,
                "length": len(normalized),
                "sha256": hashlib.sha256(normalized).hexdigest(),
                "stable": len(hashes) == 1,
                "normalized": applied,
                "raw_length": len(raw),
                "raw_sha256": hashlib.sha256(raw).hexdigest(),
                "ms": timings,
            }
        )
        print(
            f"{status} {len(raw):>10} B {timings[0]:>9.1f} ms stable={len(hashes) == 1} "
            f"{request.key[:90]}",
            flush=True,
        )
    return records


@dataclass
class RunContext:
    template: Path
    src: Path
    python: str
    work: Path
    port: int
    start_timeout: float
    settle: float
    owned_copy: bool = False


def _header(
    context: RunContext, fingerprint: Mapping[str, Mapping[str, object]]
) -> dict[str, object]:
    database = fingerprint.get(DATABASE, {})
    return {
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "src": str(context.src),
        "src_git_head": _git(context.src, "rev-parse", "HEAD"),
        "src_git_dirty": _git(context.src, "status", "--porcelain", "--untracked-files=no") != "",
        "python": context.python,
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "template": str(context.template),
        "template_files": len(fingerprint),
        "template_database_sha256": database.get("sha256", "UNKNOWN"),
        "settle_seconds": context.settle,
    }


def _guard_template(context: RunContext, before: Mapping[str, Mapping[str, object]]) -> None:
    after = template_fingerprint(context.template)
    if after != before:
        changed = sorted(
            name for name in set(before) | set(after) if before.get(name) != after.get(name)
        )
        raise SafetyStop(f"the store template changed during the run: {changed}")


def _copy(context: RunContext) -> Path:
    """The store copy of this run; only a copy this run created is ever deleted again."""
    data = copy_store(context.template, context.work / "store")
    context.owned_copy = True
    return data


def _start(context: RunContext, data: Path) -> StudioServer:
    server = StudioServer(
        context.python, context.src, data, context.work / "server.log", context.port
    )
    server.start(context.start_timeout)
    if context.settle > 0:
        time.sleep(context.settle)
    return server


def run_manifest(
    context: RunContext, commander: str, deck_id: str, repeat: int
) -> dict[str, object]:
    before = template_fingerprint(context.template)
    started = time.perf_counter()
    load_before = _load()
    try:
        data = _copy(context)
        copy_seconds = round(time.perf_counter() - started, 2)
        server = _start(context, data)
        try:
            inputs = resolve_inputs(server.base, commander, deck_id)
            records = answer_records(server.base, read_requests(inputs), data, repeat)
        finally:
            server.stop()
    finally:
        # also after a failure: a changed template is a safety stop (exit 3), not a setup error
        _guard_template(context, before)
    return {
        "format": FORMAT,
        "tool": "scripts/studio_response_manifest.py",
        "run": {
            **_header(context, before),
            "copy_seconds": copy_seconds,
            "startup_seconds": server.startup_seconds,
            "total_seconds": round(time.perf_counter() - started, 1),
            "repeat": repeat,
            "load_before": load_before,
            "load_after": _load(),
        },
        "inputs": inputs.record(),
        "requests": records,
    }


def compare_records(
    left: Sequence[Mapping[str, object]], right: Sequence[Mapping[str, object]]
) -> list[str]:
    """Differences in route set, status, length, hash and in-run stability."""
    differences: list[str] = []
    a = {str(record["key"]): record for record in left}
    b = {str(record["key"]): record for record in right}
    differences.extend(f"only in A: {key}" for key in sorted(set(a) - set(b)))
    differences.extend(f"only in B: {key}" for key in sorted(set(b) - set(a)))
    for key in [str(record["key"]) for record in left]:
        if key not in b:
            continue
        for field in ("status", "length", "sha256"):
            if a[key].get(field) != b[key].get(field):
                differences.append(f"{key}: {field} {a[key].get(field)!r} != {b[key].get(field)!r}")
        for side, record in (("A", a[key]), ("B", b[key])):
            if record.get("stable") is not True:
                differences.append(f"{key}: answers in run {side} were not byte-identical")
    return differences


def compare_manifests(left: Mapping[str, object], right: Mapping[str, object]) -> list[str]:
    for name, manifest in (("A", left), ("B", right)):
        if manifest.get("format") != FORMAT:
            raise ManifestError(f"manifest {name} is not {FORMAT}")
    differences: list[str] = []
    left_inputs, right_inputs = left.get("inputs"), right.get("inputs")
    if left_inputs != right_inputs:
        differences.append(f"inputs differ: {left_inputs!r} != {right_inputs!r}")
    left_requests, right_requests = left.get("requests"), right.get("requests")
    if not isinstance(left_requests, list) or not isinstance(right_requests, list):
        raise ManifestError("a manifest has no request list")
    differences.extend(compare_records(left_requests, right_requests))
    return differences


def run_writes(
    context: RunContext, commander: str, deck_id: str, selected: Sequence[str]
) -> dict[str, object]:
    """Write matrix on one copy: per write, running server against a fresh restart."""
    before = template_fingerprint(context.template)
    started = time.perf_counter()
    steps: list[dict[str, object]] = []
    server: StudioServer | None = None
    try:
        data = _copy(context)
        server = _start(context, data)
        inputs = resolve_inputs(server.base, commander, deck_id)
        reads = read_requests(inputs) + observer_requests(inputs)
        writes = [(name, request) for name, request in write_requests(inputs) if name in selected]
        unknown = sorted(set(selected) - {name for name, _ in write_requests(inputs)})
        if unknown:
            raise ManifestError(f"unknown writes: {unknown}")
        for name, request in writes:
            print(f"== write {name}: {request.key}", flush=True)
            status, body, ms = call(server.base, request)
            server.check_store()
            warm = answer_records(server.base, reads, data, 1)
            server.stop()
            server = _start(context, data)
            fresh = answer_records(server.base, reads, data, 1)
            differences = compare_records(warm, fresh)
            steps.append(
                {
                    "write": name,
                    "key": request.key,
                    "status": status,
                    "answer_sha256": hashlib.sha256(body).hexdigest(),
                    "ms": round(ms, 1),
                    "differences": differences,
                    "warm": warm,
                    "fresh": fresh,
                }
            )
    finally:
        if server is not None:
            server.stop()
        _guard_template(context, before)
    ok = all(step["status"] == 200 and not step["differences"] for step in steps)
    return {
        "format": WRITES_FORMAT,
        "tool": "scripts/studio_response_manifest.py",
        "run": {
            **_header(context, before),
            "total_seconds": round(time.perf_counter() - started, 1),
            "load_after": _load(),
        },
        "inputs": inputs.record(),
        "ok": ok,
        "steps": steps,
    }


# --- command line -----------------------------------------------------------------------------


def _count(value: object) -> int:
    return len(value) if isinstance(value, list) else 0


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def _context(args: argparse.Namespace) -> tuple[RunContext, bool]:
    src = Path(args.src).resolve()
    if not (src / "commander_lab" / "studio").is_dir():
        raise ManifestError(f"--src {src} holds no commander_lab/studio package")
    out = Path(args.out).resolve()
    checkout = src.parent
    check_out_path(out, [ROOT, *([checkout] if (checkout / "pyproject.toml").is_file() else [])])
    template = Path(args.store).resolve()
    created = args.work_dir is None
    if not created:
        given = Path(args.work_dir).resolve()
        folder = template if template.is_dir() else template.parent
        if _inside(given, folder) or _inside(folder, given):
            raise ManifestError("--work-dir and the store template overlap; nothing was touched")
        if (given / "store").exists():
            raise ManifestError(f"{given / 'store'} exists already; nothing was touched")
    work = Path(tempfile.mkdtemp(prefix="studio-manifest-")) if created else Path(args.work_dir)
    work.mkdir(parents=True, exist_ok=True)
    context = RunContext(
        template=template,
        src=src,
        python=args.python,
        work=work.resolve(),
        port=args.port,
        start_timeout=args.start_timeout,
        settle=args.settle,
    )
    return context, created


def _cleanup(context: RunContext, created: bool, keep: bool) -> None:
    if keep:
        print(f"work folder kept: {context.work}", flush=True)
        return
    if context.owned_copy:
        shutil.rmtree(context.work / "store", ignore_errors=True)
    if created:  # a fresh temporary folder of this run, never a given --work-dir
        shutil.rmtree(context.work, ignore_errors=True)


def _add_run_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--store", required=True, help="store template (folder or studio.sqlite3)")
    parser.add_argument("--out", required=True, help="manifest file, outside the repository")
    parser.add_argument("--src", default=str(ROOT / "src"), help="checkout src/ to serve")
    parser.add_argument("--python", default=sys.executable, help="interpreter for the server")
    parser.add_argument("--commander", default=DEFAULT_COMMANDER)
    parser.add_argument("--deck-id", default=DEFAULT_DECK)
    parser.add_argument("--port", type=int, default=0, help="0: a free local port")
    parser.add_argument("--work-dir", default=None, help="where the copy goes (default: temp)")
    parser.add_argument("--keep-work", action="store_true", help="keep the copy and server log")
    parser.add_argument("--start-timeout", type=float, default=600.0)
    parser.add_argument("--settle", type=float, default=0.0, help="seconds to wait after start")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="manifest of the read routes on a store copy")
    _add_run_options(run)
    run.add_argument("--repeat", type=int, default=2, help="answers per route (stability)")
    writes = commands.add_parser("writes", help="write matrix: warm server against fresh start")
    _add_run_options(writes)
    writes.add_argument(
        "--writes",
        default="favorite,mark,label,draft,revision,primer,universe_profile",
        help="comma-separated subset of the write matrix",
    )
    compare = commands.add_parser("compare", help="compare two run manifests (exit 1 if different)")
    compare.add_argument("left")
    compare.add_argument("right")
    args = parser.parse_args(argv)
    try:
        if args.command == "compare":
            left = json.loads(Path(args.left).read_text(encoding="utf-8"))
            right = json.loads(Path(args.right).read_text(encoding="utf-8"))
            differences = compare_manifests(left, right)
            for line in differences:
                print(line)
            print(f"{_count(left.get('requests'))} routes, {len(differences)} difference(s)")
            return 1 if differences else 0
        context, created = _context(args)
        try:
            if args.command == "run":
                result = run_manifest(context, args.commander, args.deck_id, args.repeat)
                _write_json(Path(args.out), result)
                print(f"{_count(result.get('requests'))} routes -> {args.out}")
                return 0
            selected = [name.strip() for name in args.writes.split(",") if name.strip()]
            outcome = run_writes(context, args.commander, args.deck_id, selected)
            _write_json(Path(args.out), outcome)
            steps = outcome.get("steps")
            for step in steps if isinstance(steps, list) else []:
                if isinstance(step, dict):
                    print(
                        f"write {step.get('write')}: status {step.get('status')}, "
                        f"{_count(step.get('differences'))} difference(s)"
                    )
            return 0 if outcome["ok"] else 1
        finally:
            _cleanup(context, created, args.keep_work)
    except SafetyStop as error:
        print(f"SAFETY STOP: {error}", file=sys.stderr)
        return 3
    except (ManifestError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
