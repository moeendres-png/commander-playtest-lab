"""Game key, manifest and journal of a series played on the worker pool (S1, #1660).

``game_key`` covers every input that this package can name and that can decide a game: bridge
JAR, engine pin, the pilot fingerprint and style of every seat, the pilot strategy, the deck
files in seat order, seed, seat count, table options, the forced-pass switch, the round limit,
the engine's mana-copy switch (``-Dcommanderlab.nestedCopySkip``), the JVM option variables of the
environment (``JAVA_TOOL_OPTIONS``, ``JDK_JAVA_OPTIONS``, ``_JAVA_OPTIONS``) and all other JVM
options of the worker command before ``-jar`` (``-javaagent``, any other ``-D``, ...). The option
texts can carry any ``-D`` property or agent and can name machine paths, so each enters the key
only as a SHA-256 (environment variables: of the whitespace-normalised text, one digest per
variable; the command: ``jvm_command_options_digest`` hashes only the remaining option arguments
after the launcher word and before ``-jar`` in their order, one digest — not the path or major
version of the Java binary itself, e.g. ``/opt/jdk-17/bin/java`` vs. ``java``) and the text itself
is never stored: not in the key, the task, the manifest or the journal (AGENTS.md section 12). The
command's options are closed against a list of performance-only options
(``game_pool.PERFORMANCE_ONLY_JVM_OPTIONS``: heap, stack, collector, AppCDS, logging); an option not
on it counts (fail-closed). It does not cover what lies outside the process's own configuration
(the Java binary itself, the content of a ``JDK_JAVA_OPTIONS`` ``@argfile``, files an agent reads)
and it deliberately excludes the performance-only options and
``-Dcommanderlab.fullGame.gamesPerJvm`` (below). The
event log is not part of it (its order is not stable, #1589). Two games with the same key must
have the same transcript; the determinism guard ends a series whose journal shows one key with
two transcript hashes (``DETERMINISM_VIOLATION``).

Deliberately NOT in the key (#1660, S1 Rest): ``-Dcommanderlab.fullGame.gamesPerJvm`` and the
performance-only JVM options (``-Xmx``, serial GC, AppCDS archive, loopback bind, ...). They
decide how many games one JVM plays and how fast, not a game. ``gamesPerJvm`` in particular must
stay out: a game must not depend on its position in its JVM, and that is exactly what the guard
shall be able to catch (the same key played at JVM position 1 and at position 16); a key that
contained it would give those two games two keys and blind the guard to it. The evidence is the
measured identity of ``scripts/check_studio_series_identity.py`` (168 of 168 repeated seeds
semantically identical, #1588), not a proof; the guard stays the safety net.

Per series there is ``games/series/<id>/manifest.json`` (``studio-series-manifest-1``), written
once when the series starts and never changed afterwards; it names the key version it was
recorded with (``game_key_schema``; a manifest without the field was recorded with
``studio-game-key-1``). A series recorded with another key version is not resumed and its games
are never mixed with new ones: its keys name other inputs, so the new plan gives other keys for
the same games. That is not a determinism violation (the guard reads the stored keys as they
are and never recomputes one); the start is refused with ``KeyVersionMismatch`` ("neue Serie
starten"), also on the chunked path (``series_key_problem``), and ``journal.jsonl`` with one line per
final game result. Whether a game belongs to the series is decided by the manifest only: a log
or journal line of a game the manifest does not name is never counted, whatever folder it is in.
A cancelled series is resumed from its journal; a journal line cut off by the cancel is ignored
(even when the cut splits a multi-byte character: the journal is read as bytes, line by line),
and the next line starts after it, so no later line (a violation least of all) is lost with it.
The guard groups games by the key the manifest names: a journal line whose key differs from the
manifest's key of its game is ignored and counted. A finished game without a transcript hash or
without a key cannot be compared; the guard never passes it silently but counts it
(``unguarded``: n of N finished games).
Every final result is final, a failed one too (also an infrastructure failure): a resumed series
does not replay it, as the progress log of ``paired_series`` does not, so a resumed series counts
what an uninterrupted one would have counted. Journal and manifest are synced to disk after each
write; two processes running one series at once are not locked against each other (the manifest
is created once, by hard link or, where the file system has none, by exclusive create; journal
appends of two processes may interleave). Where the exclusive create is used, the file exists
(empty) for a moment before its content is there: a second start that finds it empty or cut off
waits and reads again (``_read_stored_manifest``, ``MANIFEST_READ_ATTEMPTS`` reads) before it
calls it incomplete, and it never rewrites it. Only a manifest still unreadable after that, which
an aborted first start leaves, ends as ``ManifestMismatch``.

Nothing here reuses a game (that is #1589, Owner); S1 builds the key and the guard it needs.
A green series is no evidence of determinism: in a normal A/B series every key is unique (each
arm, seed and seat is one game), so the guard can only trip when one key is played twice.
A series whose journal shows a violation is not resumable on either path (``series_violation``).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from .games import games_folder
from .store import now_utc
from .table_spec import canonical_json, sha256_of

#: How often a start reads a manifest that is empty or cut off, and how long it waits between
#: two reads: the writer of the exclusive-create fallback is then still between create and write.
MANIFEST_READ_ATTEMPTS: Final = 20
MANIFEST_READ_WAIT_SECONDS: Final = 0.1
GAME_KEY_SCHEMA: Final = "studio-game-key-2"
MANIFEST_SCHEMA: Final = "studio-series-manifest-1"
JOURNAL_SCHEMA: Final = "studio-series-journal-1"
DETERMINISM_VIOLATION: Final = "DETERMINISM_VIOLATION"
#: The failure classes a worker gives a game it refuses before the engine starts; they are
#: infrastructure (the setup was wrong), never a result of the deck.
INFRASTRUCTURE_FAILURES: Final = (
    "DeckHashMismatch",
    "PilotFingerprintMismatch",
    "BridgeJarMismatch",
    "TaskIncomplete",
    "GameKeyMismatch",
)


class DeterminismViolation(RuntimeError):
    """One game key with two transcript hashes: the series ends without a comparison result.

    Raised from the pool run, it ends the paired series like any error of its run: status
    ``failed`` with this message (it starts with ``DETERMINISM_VIOLATION``) as its error, and no
    comparison is computed. Games of the series that ended before were already reported to its
    progress log; they stay there as they were, but no result of the series rests on them.
    """

    status = DETERMINISM_VIOLATION

    def __init__(self, game_key: str, hashes: Sequence[str], game_ids: Sequence[str]) -> None:
        self.game_key = game_key
        self.hashes = tuple(hashes)
        self.game_ids = tuple(game_ids)
        super().__init__(
            f"{DETERMINISM_VIOLATION}: Spielschlüssel {game_key[:12]} hat "
            f"{len(self.hashes)} verschiedene Transkript-Hashes (Partien {', '.join(game_ids)})"
        )


class ManifestMismatch(RuntimeError):
    """The manifest of a series already exists with other content; it is never rewritten."""


class KeyVersionMismatch(ManifestMismatch):
    """The series was recorded with another game key version: not comparable, never resumed."""


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def game_key(
    *,
    jar_sha256: str,
    engine_pin: str,
    pilot_fingerprints: Sequence[str],
    seat_styles: Sequence[float],
    deck_sha256: Sequence[str],
    seed: int,
    strategy: str,
    table_options: Mapping[str, object] | None,
    skip_forced_decisions: bool | None,
    round_limit: int | None,
    jvm_options: Mapping[str, object],
) -> str:
    """SHA-256 over everything that decides a game (``charter_simulate.md`` §7.1).

    Every per-seat list is in seat order and has one entry per seat; the seat count is their
    length. A missing JAR or engine pin is an error, never an empty field: a key without them
    would match games played on another bridge. ``skip_forced_decisions`` and ``round_limit``
    are ``None`` when the command does not set them (the bridge default holds); ``None`` is a
    value of its own in the key, never equal to ``True``/``False`` or a number.

    ``jvm_options`` is what ``game_pool.jvm_options_of`` reads from the bridge command and the
    environment: ``nested_copy_skip`` (``None`` when the command does not set it) and
    ``env_options`` (the JVM option variables that are set, name -> SHA-256 of the
    normalised text; never the text) and ``command_options`` (SHA-256 of the options before
    ``-jar`` that are not performance-only, ``None`` when there are none; never the options).
    All three fields are required, so a caller cannot leave them out by accident;
    ``{"nested_copy_skip": None, "env_options": {}, "command_options": None}`` is "nothing set",
    a value of its own.
    """
    if not jar_sha256 or not jar_sha256.strip() or not engine_pin or not engine_pin.strip():
        raise ValueError("ein Spielschlüssel braucht Bridge-JAR-SHA und Engine-Pin")
    if not strategy or not strategy.strip():
        raise ValueError("ein Spielschlüssel braucht eine Strategie, kein leeres Feld")
    seats = len(deck_sha256)
    if not seats or len(pilot_fingerprints) != seats or len(seat_styles) != seats:
        raise ValueError(
            "Pilot-Fingerabdrücke, Stile und Deck-Hashes brauchen je einen Eintrag pro Sitz"
        )
    if any(not value or not value.strip() for value in (*pilot_fingerprints, *deck_sha256)):
        raise ValueError("leerer Pilot-Fingerabdruck oder Deck-Hash im Spielschlüssel")
    jvm = _checked_jvm_options(jvm_options)
    payload: dict[str, object] = {
        "schema": GAME_KEY_SCHEMA,
        "jar_sha256": jar_sha256,
        "engine_pin": engine_pin,
        "pilot_fingerprints": list(pilot_fingerprints),
        # exact (shortest round-trip form): two different styles never share a key
        "seat_styles": [repr(float(style)) for style in seat_styles],
        "deck_sha256": list(deck_sha256),
        "seed": int(seed),
        "strategy": strategy,
        "seats": seats,
        "table_options": dict(table_options) if table_options is not None else None,
        "skip_forced_decisions": skip_forced_decisions,
        "round_limit": round_limit,
        "jvm_options": jvm,
    }
    return sha256_of(payload)


_SHA256: Final = re.compile(r"[0-9a-f]{64}")
#: The fields of ``jvm_options`` in the key; nothing else may enter it unnoticed.
JVM_OPTION_FIELDS: Final = ("nested_copy_skip", "env_options", "command_options")


def _checked_jvm_options(options: Mapping[str, object]) -> dict[str, object]:
    """``options`` with exactly the known fields and shapes, env options in name order."""
    if set(options) != set(JVM_OPTION_FIELDS):
        raise ValueError(f"JVM-Optionen des Spielschlüssels: genau die Felder {JVM_OPTION_FIELDS}")
    nested = options["nested_copy_skip"]
    if not (nested is None or isinstance(nested, bool)):
        raise ValueError("nested_copy_skip ist true, false oder None (nicht gesetzt)")
    env = options["env_options"]
    if not isinstance(env, Mapping) or any(
        not isinstance(name, str) or not isinstance(digest, str) or not _SHA256.fullmatch(digest)
        for name, digest in env.items()
    ):
        # a digest, never the option text itself: it can name machine paths and agents (§12)
        raise ValueError("env_options ist eine Zuordnung Name -> SHA-256 des normalisierten Texts")
    command = options["command_options"]
    if not (command is None or (isinstance(command, str) and _SHA256.fullmatch(command))):
        # a digest or None (no such option), never the options themselves: they can name paths
        raise ValueError("command_options ist None oder der SHA-256 der Befehlsoptionen")
    return {
        "nested_copy_skip": nested,
        "env_options": {name: env[name] for name in sorted(env)},
        "command_options": command,
    }


def series_folder(data_folder: str | Path, series_id: str) -> Path:
    if not series_id or "/" in series_id or "\\" in series_id or series_id in {".", ".."}:
        raise ValueError(f"ungültige Serien-Kennung: {series_id!r}")
    return games_folder(data_folder) / "series" / series_id


@dataclass
class SeriesRecord:
    """Manifest, journal and determinism guard of one series."""

    folder: Path
    manifest: dict[str, object]
    #: game id -> its journal entry (the last final line of a manifest member)
    _entries: dict[str, dict[str, object]] = field(default_factory=dict, init=False)
    #: game key -> {transcript hash -> game ids}
    _hashes: dict[str, dict[str, list[str]]] = field(default_factory=dict, init=False)
    ignored_lines: int = field(default=0, init=False)
    #: journal lines of a member whose key is not the manifest's key of that game (also ignored)
    key_mismatch_lines: int = field(default=0, init=False)

    @property
    def manifest_path(self) -> Path:
        return self.folder / "manifest.json"

    @property
    def journal_path(self) -> Path:
        return self.folder / "journal.jsonl"

    def members(self) -> dict[str, str | None]:
        """game id -> game key of every game the manifest names."""
        games = self.manifest.get("games")
        found: dict[str, str | None] = {}
        if isinstance(games, list):
            for game in games:
                if isinstance(game, dict) and isinstance(game.get("game_id"), str):
                    key = game.get("game_key")
                    found[str(game["game_id"])] = key if isinstance(key, str) else None
        return found

    @classmethod
    def open(
        cls,
        data_folder: str | Path,
        series_id: str,
        *,
        games: Sequence[Mapping[str, object]],
        table_hash: str | None,
        table: Mapping[str, object] | None,
    ) -> SeriesRecord:
        """Start the series (write its manifest) or resume it (same manifest, read journal)."""
        folder = series_folder(data_folder, series_id)
        manifest: dict[str, object] = {
            "schema": MANIFEST_SCHEMA,
            "series_id": series_id,
            "table_hash": table_hash,
            "table": dict(table) if table is not None else None,
            "game_key_schema": GAME_KEY_SCHEMA,
            "games": [dict(game) for game in games],
        }
        path = folder / "manifest.json"
        if path.is_file():
            stored = _read_stored_manifest(path, series_id)
            _require_current_key_version(stored, series_id)
            body = {k: v for k, v in stored.items() if k != "created_at"}
            if canonical_json(body) != canonical_json(manifest):
                raise ManifestMismatch(
                    f"Serie {series_id}: das Manifest ist nach dem Start unveränderlich, "
                    "der neue Auftrag weicht ab"
                )
            manifest = stored
        else:
            folder.mkdir(parents=True, exist_ok=True)
            manifest = {**manifest, "created_at": now_utc()}
            temp = folder / f"manifest.{os.getpid()}.tmp"
            try:
                with temp.open("wb") as handle:
                    handle.write(canonical_json(manifest))
                    handle.flush()
                    os.fsync(handle.fileno())
                try:
                    # a hard link never replaces: of two starts of one series only one wins
                    os.link(temp, path)
                except FileExistsError:
                    raise
                except OSError:
                    # no hard links here (FAT/exFAT, some shares): exclusive create, never replace
                    _create_exclusive(path, canonical_json(manifest))
                _fsync_folder(folder)
            except FileExistsError:
                return cls.open(
                    data_folder, series_id, games=games, table_hash=table_hash, table=table
                )
            finally:
                temp.unlink(missing_ok=True)
        record = cls(folder, manifest)
        record._read_journal()
        return record

    def _read_journal(self) -> None:
        if not self.journal_path.is_file():
            return
        members = self.members()
        with self.journal_path.open("rb") as handle:
            for raw in handle:
                if not raw.endswith(b"\n"):
                    # the last line, cut off by a cancel: never a result (``record`` starts a
                    # new line after it, so no later line is joined to it)
                    self.ignored_lines += 1
                    continue
                try:
                    # bytes: a cut inside a multi-byte character is a ``ValueError`` of this line
                    entry = json.loads(raw)
                except ValueError:
                    self.ignored_lines += 1
                    continue
                game_id = entry.get("game_id") if isinstance(entry, dict) else None
                if not isinstance(game_id, str) or game_id not in members:
                    self.ignored_lines += 1  # not a member of this series: never counted
                    continue
                if entry.get("game_key") != members[game_id]:
                    # the guard groups by the manifest's key, never by the key a line claims
                    self.key_mismatch_lines += 1
                    self.ignored_lines += 1
                    continue
                self._admit(entry)

    def _admit(self, entry: dict[str, object]) -> None:
        game_id = str(entry["game_id"])
        self._entries[game_id] = entry
        key = entry.get("game_key")
        transcript = entry.get("semantic_transcript_sha256")
        if entry.get("status") != "finished" or not isinstance(key, str):
            return
        if not isinstance(transcript, str) or not transcript:
            return
        by_hash = self._hashes.setdefault(key, {})
        by_hash.setdefault(transcript, []).append(game_id)
        if len(by_hash) > 1:
            ids = [gid for gids in by_hash.values() for gid in gids]
            raise DeterminismViolation(key, sorted(by_hash), ids)

    def unguarded(self) -> tuple[int, int]:
        """(n, N): n of the N finished games (last result per game) the guard cannot compare.

        A finished game without a transcript hash or without a game key is not checked for
        determinism; it is counted here, never passed silently. ``(0, 0)`` means no finished
        game yet, not "all guarded".
        """
        finished = [entry for entry in self._entries.values() if entry.get("status") == "finished"]
        unguarded = [
            entry
            for entry in finished
            if not isinstance(entry.get("game_key"), str)
            or not isinstance(entry.get("semantic_transcript_sha256"), str)
            or not entry.get("semantic_transcript_sha256")
        ]
        return len(unguarded), len(finished)

    def comparable_keys(self) -> int:
        """How many game keys have two or more different games with a transcript hash.

        Only those keys can show a violation; a key played once is not compared with anything.
        """
        return sum(
            1
            for by_hash in self._hashes.values()
            if len({game_id for ids in by_hash.values() for game_id in ids}) >= 2
        )

    def results(self) -> dict[str, dict[str, object]]:
        """The final result of every manifest member that has one (game id -> summary)."""
        found: dict[str, dict[str, object]] = {}
        for game_id, entry in self._entries.items():
            summary = entry.get("summary")
            if isinstance(summary, dict):
                found[game_id] = dict(summary)
        return found

    def record(self, game_id: str, summary: Mapping[str, object]) -> None:
        """Append the final result of a game; the guard runs before the line is written."""
        members = self.members()
        if game_id not in members:
            raise ValueError(f"Partie {game_id} steht nicht im Manifest der Serie")
        entry: dict[str, object] = {
            "schema": JOURNAL_SCHEMA,
            "game_id": game_id,
            "game_key": members[game_id],
            "status": summary.get("status"),
            "failure_class": summary.get("failure_class"),
            "semantic_transcript_sha256": summary.get("semantic_transcript_sha256"),
            "recorded_at": now_utc(),
            "summary": dict(summary),
        }
        line = json.dumps(entry, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        try:
            self._admit(entry)
        finally:
            # a violating line is written too: the journal is the evidence of the violation
            self.folder.mkdir(parents=True, exist_ok=True)
            with self.journal_path.open("ab") as handle:
                if self.journal_path.stat().st_size and not _ends_with_newline(self.journal_path):
                    handle.write(b"\n")  # end the cut-off line, never join this one to it
                handle.write(line.encode("utf-8") + b"\n")
                handle.flush()
                os.fsync(handle.fileno())


@dataclass(frozen=True)
class SeriesFolderAudit:
    """Fail-closed inspection result of one series directory (S1, #1660).

    ``members`` holds the manifest's ``game_id`` set when ``manifest.json`` is valid, or ``None``
    when the manifest is missing, corrupt or unreadable. ``violated`` is True when the journal
    shows a ``DETERMINISM_VIOLATION`` or when ``manifest.json`` / ``journal.jsonl`` is unreadable
    or corrupt.
    """

    members: frozenset[str] | None
    violated: bool


def audit_series_folder(folder: Path) -> SeriesFolderAudit:
    """Inspect a series folder (``manifest.json`` and optional ``journal.jsonl``) fail-closed.

    A manifest is valid only as a JSON object whose ``games`` field is a list of objects each
    naming a non-empty string ``game_id``. When ``journal.jsonl`` is present, every newline-
    terminated line must parse as a JSON object, a non-empty journal with no complete line counts
    as corrupt, and :class:`SeriesRecord` must read it without ``DeterminismViolation``.
    """
    manifest_path = folder / "manifest.json"
    try:
        stored = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return SeriesFolderAudit(members=None, violated=True)
    if not isinstance(stored, dict):
        return SeriesFolderAudit(members=None, violated=True)
    games_raw = stored.get("games")
    if not isinstance(games_raw, list):
        return SeriesFolderAudit(members=None, violated=True)
    members: set[str] = set()
    for entry in games_raw:
        if not isinstance(entry, dict):
            return SeriesFolderAudit(members=None, violated=True)
        gid = entry.get("game_id")
        if not isinstance(gid, str) or not gid:
            return SeriesFolderAudit(members=None, violated=True)
        members.add(gid)
    member_set = frozenset(members)
    record = SeriesRecord(folder, stored)
    journal_path = record.journal_path
    if journal_path.exists() or journal_path.is_symlink():
        if not journal_path.is_file():
            return SeriesFolderAudit(members=member_set, violated=True)
        try:
            total_lines = 0
            complete_lines = 0
            with journal_path.open("rb") as handle:
                for raw in handle:
                    total_lines += 1
                    if not raw.endswith(b"\n"):
                        continue
                    complete_lines += 1
                    parsed = json.loads(raw)
                    if not isinstance(parsed, dict):
                        return SeriesFolderAudit(members=member_set, violated=True)
            if total_lines > 0 and complete_lines == 0:
                return SeriesFolderAudit(members=member_set, violated=True)
            record._read_journal()
        except (DeterminismViolation, OSError, ValueError):
            return SeriesFolderAudit(members=member_set, violated=True)
    return SeriesFolderAudit(members=member_set, violated=False)


def series_violation(data_folder: str | Path, series_id: str) -> DeterminismViolation | None:
    """The violation the stored journal of a series shows, whichever path played it.

    Reads the stored manifest as it is (no plan to compare against) and its journal. ``None``:
    no journal or no violation in it. A journal without a readable manifest cannot be checked
    and raises ``ManifestMismatch`` (fail-closed, never "no violation").
    """
    try:
        _stored_record(data_folder, series_id)
    except DeterminismViolation as violation:
        return violation
    return None


def series_guard(data_folder: str | Path, series_id: str) -> dict[str, object] | None:
    """What the guard of a stored series saw, for its status.

    ``unguarded`` n of ``finished`` N (the finished games the guard cannot compare) and
    ``comparable_keys``: how many game keys have two or more guarded games, the only keys the
    guard can compare at all. The word is "vergleichbar", not "verglichen": in a normal A/B series
    every key is played once, so the guard compares nothing and says so (``comparable_keys`` 0).

    ``None``: no journal (a chunked series, or nothing played yet), so unknown, never "0 of 0".
    A journal without a finished game gives ``None`` for all three counts for the same reason:
    ``unguarded`` 0 of 0 would read as "all guarded". After a violation the journal is not read to
    its end: all three are ``None``.
    """
    try:
        record = _stored_record(data_folder, series_id)
    except DeterminismViolation:
        return {"violation": True, "unguarded": None, "finished": None, "comparable_keys": None}
    if record is None:
        return None
    unguarded, finished = record.unguarded()
    if finished == 0:
        return {"violation": False, "unguarded": None, "finished": None, "comparable_keys": None}
    return {
        "violation": False,
        "unguarded": unguarded,
        "finished": finished,
        "comparable_keys": record.comparable_keys(),
    }


def _stored_record(data_folder: str | Path, series_id: str) -> SeriesRecord | None:
    """The stored manifest and journal of a series (journal read); ``None`` without a journal."""
    folder = series_folder(data_folder, series_id)
    record = SeriesRecord(folder, {})
    if not record.journal_path.is_file():
        return None
    try:
        stored = json.loads(record.manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ManifestMismatch(
            f"Serie {series_id}: Journal ohne lesbares Manifest, nicht prüfbar"
        ) from error
    if not isinstance(stored, dict):
        raise ManifestMismatch(f"Manifest der Serie {series_id} ist kein Objekt")
    record.manifest = stored
    record._read_journal()
    return record


#: The key version of a manifest that does not name one: every series recorded before the field.
LEGACY_GAME_KEY_SCHEMA: Final = "studio-game-key-1"


def _require_current_key_version(stored: Mapping[str, object], series_id: str) -> None:
    """``KeyVersionMismatch`` when ``stored`` was recorded with another game key version."""
    recorded = stored.get("game_key_schema", LEGACY_GAME_KEY_SCHEMA)
    if recorded != GAME_KEY_SCHEMA:
        raise KeyVersionMismatch(
            f"Serie {series_id} wurde mit der Spielschlüssel-Version {recorded} aufgezeichnet, "
            f"diese Version ist {GAME_KEY_SCHEMA}: ihre Partien sind mit neuen nicht vergleichbar "
            "und werden nicht fortgesetzt, bitte eine neue Serie starten"
        )


def series_key_problem(data_folder: str | Path, series_id: str) -> str | None:
    """Why a stored series cannot be resumed for its key version, or ``None``.

    Only a readable manifest of another key version is a problem here; no manifest (a chunked
    series) or an unreadable one is not decided by this check.
    """
    path = series_folder(data_folder, series_id) / "manifest.json"
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(stored, dict):
        return None
    try:
        _require_current_key_version(stored, series_id)
    except KeyVersionMismatch as error:
        return str(error)
    return None


def _read_stored_manifest(path: Path, series_id: str) -> dict[str, object]:
    """The stored manifest; an empty or cut-off file is read again before it counts as broken.

    A start without hard links creates the file and writes it in two steps, so a second start can
    see it empty. That is a race, not a broken series: wait and read again, at most
    ``MANIFEST_READ_ATTEMPTS`` reads. The file is never touched here. A file still unreadable
    after that was left by a first start that aborted or is still writing; the text says so and
    does not claim more.
    """
    last_error: ValueError | None = None
    for attempt in range(MANIFEST_READ_ATTEMPTS):
        if attempt:
            time.sleep(MANIFEST_READ_WAIT_SECONDS)
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as error:  # empty, cut off or not text (JSONDecodeError, UnicodeError)
            last_error = error
            continue
        if not isinstance(stored, dict):
            raise ManifestMismatch(f"Manifest der Serie {series_id} ist kein Objekt")
        return stored
    raise ManifestMismatch(
        f"Manifest der Serie {series_id} ist nach {MANIFEST_READ_ATTEMPTS} Leseversuchen "
        f"({MANIFEST_READ_ATTEMPTS * MANIFEST_READ_WAIT_SECONDS:.0f} s) noch leer oder "
        "unvollständig: ein früherer Start brach ab oder schreibt noch. Die Datei wird nie "
        "überschrieben; die Serie ist so nicht fortsetzbar, der Ordner ist zu prüfen"
    ) from last_error


def _create_exclusive(path: Path, data: bytes) -> None:
    """Create ``path`` with ``data``; ``FileExistsError`` if it exists (never replaced)."""
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0))
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _fsync_folder(folder: Path) -> None:
    """Sync the folder entry of a new file; best effort (a folder cannot be opened on Windows)."""
    try:
        fd = os.open(folder, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _ends_with_newline(path: Path) -> bool:
    with path.open("rb") as handle:
        handle.seek(-1, os.SEEK_END)
        return handle.read(1) == b"\n"


__all__ = [
    "DETERMINISM_VIOLATION",
    "GAME_KEY_SCHEMA",
    "INFRASTRUCTURE_FAILURES",
    "MANIFEST_SCHEMA",
    "DeterminismViolation",
    "KeyVersionMismatch",
    "ManifestMismatch",
    "SeriesFolderAudit",
    "SeriesRecord",
    "audit_series_folder",
    "file_sha256",
    "game_key",
    "series_folder",
    "series_guard",
    "series_key_problem",
    "series_violation",
]
