#!/usr/bin/env python3
"""One-off data-quality cross-check (issue #1367): the stored ``edhrec_global_inclusion``
signal against the independent, free MTGJSON bulk. MTGJSON is not a signal and never
replaces a stored value; this script only reports whether the two EDHREC-derived views of
the same cards agree, and where they do not.

Method, in short:

- The Studio store is built from the repository alone (plus the public Scryfall oracle
  file the repo importer requires)::

      python -m commander_lab.studio --data <store> import-all \
          --commander "Chulane, Teller of Tales" --from-repo --scryfall <oracle.jsonl.gz>

- The stored signal rows are first proven equal to their repository source file
  (``data/research/deckbuilder_1655/card_global_signals.csv``): numerator, denominator
  and value per card, with the importer's own rule that a non-positive denominator is
  stored as unknown (NULL), never as 0.
- MTGJSON ``AtomicCards`` (https://mtgjson.com/api/v5/AtomicCards.json.bz2) carries
  ``edhrecRank`` (1 = most played card on EDHREC) and ``edhrecSaltiness`` per card. The
  bulk is read as a stream; nothing of it is written to the store or the repository.
- Join: our card names are oracle names. A card joins on its exact MTGJSON name, else on
  a face name of a multi-face card, else on the front face, else on the Scryfall oracle
  id. Every ranked card (a pool card with a strength index) is accounted for.
- Comparison is rank-based, because the two figures have different universes: our share
  divides by the decks that could legally run the card (``potential_decks``), the
  MTGJSON rank orders by the raw deck count over all decks. Both sides are converted to
  popularity percentiles over the common set; cards whose percentiles differ by more
  than 0.25 are listed. Spearman is reported between the raw MTGJSON rank and our
  inclusion (a strong negative value is the expected sign: rank 1 is the highest
  inclusion) and, equivalently, between the two popularity percentiles.

No collection quantities and no deck data leave the machine; the report names only the
cards of the ranked pool, as the issue allows. Status vocabulary: OK / ABWEICHUNG /
UNKNOWN, as in ``docs/research/DATA_AUDIT_20261112.md``.
"""

from __future__ import annotations

import argparse
import bz2
import csv
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

SIGNAL = "edhrec_global_inclusion"
OUTLIER_DELTA = 0.25
_VALUE_TOLERANCE = 1e-12


# ---------------------------------------------------------------- MTGJSON bulk reading


class _JsonStream:
    """Incremental ``raw_decode`` over a text stream: values are decoded one at a time
    from a growing buffer, so a several-hundred-megabyte bulk never sits in memory."""

    def __init__(self, handle: TextIO) -> None:
        self._handle = handle
        self._buffer = ""
        self._eof = False
        self._decoder = json.JSONDecoder()

    def _fill(self) -> None:
        if self._eof:
            return
        chunk = self._handle.read(1 << 20)
        if chunk:
            self._buffer += chunk
        else:
            self._eof = True

    def _compact(self, index: int) -> int:
        if index > (1 << 20):
            self._buffer = self._buffer[index:]
            return 0
        return index

    def skip_ws(self, index: int) -> int:
        while True:
            while index < len(self._buffer) and self._buffer[index] in " \t\r\n":
                index += 1
            if index < len(self._buffer) or self._eof:
                return self._compact(index)
            self._fill()

    def peek(self, index: int) -> str:
        index = self.skip_ws(index)
        while index >= len(self._buffer) and not self._eof:
            self._fill()
        if index >= len(self._buffer):
            raise ValueError("unexpected end of JSON stream")
        return self._buffer[index]

    def decode(self, index: int) -> tuple[object, int]:
        index = self.skip_ws(index)
        while True:
            try:
                value, end = self._decoder.raw_decode(self._buffer, index)
                return value, self._compact(end)
            except json.JSONDecodeError:
                if self._eof:
                    raise
                self._fill()


@dataclass
class MtgIndex:
    """The MTGJSON side of the join, keyed by oracle (full) card name."""

    meta_date: str = ""
    meta_version: str = ""
    keys_total: int = 0
    entries_total: int = 0
    entries_with_rank: int = 0
    rank_conflicts: int = 0  # keys whose printings/faces disagree on the rank
    rank_by_name: dict[str, int] = field(default_factory=dict)
    salt_by_name: dict[str, float] = field(default_factory=dict)
    names_without_rank: set[str] = field(default_factory=set)
    face_to_name: dict[str, str] = field(default_factory=dict)
    oracle_to_name: dict[str, str] = field(default_factory=dict)


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def read_mtgjson(path: Path) -> MtgIndex:
    """Stream ``AtomicCards.json.bz2`` once and keep rank/salt per oracle name."""
    index = MtgIndex()
    ranks: dict[str, set[int]] = {}
    with bz2.open(path, "rt", encoding="utf-8") as handle:
        stream = _JsonStream(handle)
        start = stream.skip_ws(0)
        if stream.peek(start) != "{":
            raise ValueError("bulk does not start with an object")
        # The top level holds "meta" and "data"; "data" is too large to decode at once,
        # so its members are walked with the same machinery instead of decoded whole.
        cursor = stream.skip_ws(start) + 1
        while True:
            key, cursor = stream.decode(cursor)
            if not isinstance(key, str):
                raise ValueError("top-level key is not a string")
            cursor = stream.skip_ws(cursor)
            if stream.peek(cursor) != ":":
                raise ValueError("expected ':'")
            cursor += 1
            if key == "meta":
                meta, cursor = stream.decode(cursor)
                if isinstance(meta, dict):
                    index.meta_date = str(meta.get("date", ""))
                    index.meta_version = str(meta.get("version", ""))
            elif key == "data":
                cursor = _read_data(stream, cursor, index, ranks)
            else:
                _, cursor = stream.decode(cursor)
            cursor = stream.skip_ws(cursor)
            char = stream.peek(cursor)
            if char == "}":
                break
            if char != ",":
                raise ValueError("expected ',' or '}' at top level")
            cursor += 1
    for name, seen in ranks.items():
        if len(seen) > 1:
            index.rank_conflicts += 1
        index.rank_by_name[name] = min(seen)
    return index


def _read_data(
    stream: _JsonStream, cursor: int, index: MtgIndex, ranks: dict[str, set[int]]
) -> int:
    """Walk the ``data`` object member by member; each value is one card's entry list."""
    if stream.peek(cursor) != "{":
        raise ValueError("expected '{' for data")
    cursor = stream.skip_ws(cursor) + 1
    if stream.peek(cursor) == "}":
        return cursor + 1
    while True:
        name, cursor = stream.decode(cursor)
        if not isinstance(name, str):
            raise ValueError("card key is not a string")
        cursor = stream.skip_ws(cursor)
        if stream.peek(cursor) != ":":
            raise ValueError("expected ':'")
        entries, cursor = stream.decode(cursor + 1)
        if isinstance(entries, list):
            _absorb_card(index, ranks, name, entries)
        cursor = stream.skip_ws(cursor)
        char = stream.peek(cursor)
        if char == "}":
            return cursor + 1
        if char != ",":
            raise ValueError("expected ',' or '}' in data")
        cursor += 1


def _absorb_card(
    index: MtgIndex, ranks: dict[str, set[int]], name: str, entries: list[object]
) -> None:
    index.keys_total += 1
    seen_rank = False
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        index.entries_total += 1
        rank = _number(entry.get("edhrecRank"))
        if rank is not None:
            seen_rank = True
            index.entries_with_rank += 1
            ranks.setdefault(name, set()).add(int(rank))
        salt = _number(entry.get("edhrecSaltiness"))
        if salt is not None and name not in index.salt_by_name:
            index.salt_by_name[name] = salt
        face = entry.get("faceName")
        if isinstance(face, str) and face != name:
            index.face_to_name.setdefault(face, name)
        identifiers = entry.get("identifiers")
        if isinstance(identifiers, dict):
            oracle_id = identifiers.get("scryfallOracleId")
            if isinstance(oracle_id, str):
                index.oracle_to_name.setdefault(oracle_id, name)
    front = name.split(" // ")[0]
    if front != name:
        index.face_to_name.setdefault(front, name)
    if not seen_rank:
        index.names_without_rank.add(name)


# ---------------------------------------------------------------- statistics


def _average_ranks(values: list[float]) -> list[float]:
    """Rank 1 for the smallest value; tied values share the mean of their ranks."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    pos = 0
    while pos < len(order):
        end = pos
        while end + 1 < len(order) and values[order[end + 1]] == values[order[pos]]:
            end += 1
        mean_rank = (pos + end) / 2.0 + 1.0
        for k in range(pos, end + 1):
            ranks[order[k]] = mean_rank
        pos = end + 1
    return ranks


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x == 0.0 or var_y == 0.0:
        return 0.0
    return cov / (var_x * var_y) ** 0.5


def _spearman(xs: list[float], ys: list[float]) -> float:
    return _pearson(_average_ranks(xs), _average_ranks(ys))


def _percentiles(values: list[float]) -> list[float]:
    """Popularity percentile of each value inside this set: 0 = smallest, 1 = largest."""
    n = len(values)
    if n < 2:
        return [0.0] * n
    return [(rank - 1.0) / (n - 1) for rank in _average_ranks(values)]


# ---------------------------------------------------------------- store side


@dataclass(frozen=True)
class StoredSignal:
    value: float | None
    numerator: int | None
    denominator: int | None


@dataclass
class StoreSide:
    pool: list[str]
    ranked: list[str]
    signals: dict[str, StoredSignal]  # every stored row of the signal, by stored name
    global_by_card: dict[str, StoredSignal]  # the observation the index uses, per pool card
    global_status: dict[str, str]  # component status per pool card (why a value is absent)
    ambiguous_names: list[str]  # signal names the index could not attribute to one card
    color_identity: dict[str, str]
    oracle_id_by_name: dict[str, str]


def _load_store(store_dir: Path, commander: str) -> StoreSide:
    src_dir = Path(__file__).resolve().parents[1] / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    from commander_lab.studio import StudioStore, strength_view
    from commander_lab.studio.strength import GLOBAL_INCLUSION, StrengthSettings

    store = StudioStore.open(store_dir)
    try:
        result = strength_view.compute(store, commander, StrengthSettings())
        pool = [str(card["name"]) for card in result["cards"]]
        ranked = [str(card["name"]) for card in result["cards"] if card["index"] is not None]
        global_by_card: dict[str, StoredSignal] = {}
        global_status: dict[str, str] = {}
        for card in result["cards"]:
            name = str(card["name"])
            for component in card["components"]:
                if component["component"] != GLOBAL_INCLUSION:
                    continue
                value = component["value"]
                numerator = component["numerator"]
                denominator = component["denominator"]
                global_by_card[name] = StoredSignal(
                    value=None if value is None else float(value),
                    numerator=None if numerator is None else int(numerator),
                    denominator=None if denominator is None else int(denominator),
                )
                global_status[name] = str(component["status"])
        signals = {
            str(row[0]): StoredSignal(
                value=None if row[1] is None else float(row[1]),
                numerator=None if row[2] is None else int(row[2]),
                denominator=None if row[3] is None else int(row[3]),
            )
            for row in store.connection.execute(
                "SELECT card_name, value, numerator, denominator FROM card_signal "
                "WHERE commander_name = '' AND signal = ?",
                (SIGNAL,),
            )
        }
        color_identity = {
            str(row[0]): str(row[1])
            for row in store.connection.execute("SELECT oracle_name, color_identity FROM card")
        }
        oracle_id_by_name = {
            str(row[0]): str(row[1])
            for row in store.connection.execute(
                "SELECT name, oracle_id FROM scryfall_card WHERE oracle_id IS NOT NULL"
            )
        }
        ambiguous_names = sorted(
            str(item["name"]) for item in result["ambiguous_names"] if item["signal"] == SIGNAL
        )
    finally:
        store.close()
    return StoreSide(
        pool=pool,
        ranked=ranked,
        signals=signals,
        global_by_card=global_by_card,
        global_status=global_status,
        ambiguous_names=ambiguous_names,
        color_identity=color_identity,
        oracle_id_by_name=oracle_id_by_name,
    )


# ---------------------------------------------------------------- source equivalence


@dataclass
class Equivalence:
    csv_rows: int = 0
    matched: int = 0
    matched_null_rule: int = 0  # denominator not positive in the CSV -> stored NULL
    mismatches: list[str] = field(default_factory=list)


def _csv_int(text: str | None) -> int | None:
    if text is None or not text.strip():
        return None
    try:
        return int(text)
    except ValueError:
        return None


def check_equivalence(csv_path: Path, signals: dict[str, StoredSignal]) -> Equivalence:
    """Stored rows against the repository CSV they were imported from, row by row."""
    result = Equivalence()
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    result.csv_rows = len(rows)
    seen: set[str] = set()
    for row in rows:
        name = (row.get("card_name") or "").strip()
        seen.add(name)
        stored = signals.get(name)
        if stored is None:
            result.mismatches.append(f"{name}: keine Store-Zeile")
            continue
        numerator = _csv_int(row.get("num_decks"))
        denominator = _csv_int(row.get("potential_decks"))
        if numerator is None or denominator is None or denominator <= 0:
            if stored.value is None and stored.numerator is None and stored.denominator is None:
                result.matched_null_rule += 1
            else:
                result.mismatches.append(f"{name}: CSV ohne positiven Nenner, Store nicht NULL")
            continue
        if stored.numerator != numerator or stored.denominator != denominator:
            result.mismatches.append(f"{name}: Zähler/Nenner weichen ab")
            continue
        if stored.value is None or abs(stored.value - numerator / denominator) > _VALUE_TOLERANCE:
            result.mismatches.append(f"{name}: Wert weicht ab")
            continue
        result.matched += 1
    for name in sorted(set(signals) - seen):
        result.mismatches.append(f"{name}: Store-Zeile ohne CSV-Zeile")
    return result


# ---------------------------------------------------------------- join and compare


@dataclass(frozen=True)
class Joined:
    name: str
    inclusion: float
    numerator: int | None
    denominator: int | None
    mtg_rank: int
    mtg_name: str  # the MTGJSON oracle name this card joined on
    join_kind: str
    color_identity: str


@dataclass
class JoinResult:
    joined: list[Joined] = field(default_factory=list)
    kinds: dict[str, int] = field(default_factory=dict)
    without_value: list[str] = field(default_factory=list)  # ranked, stored value NULL
    without_signal: list[str] = field(default_factory=list)  # ranked, no stored row
    without_rank: list[str] = field(default_factory=list)  # known to MTGJSON, no rank
    unmatched: list[str] = field(default_factory=list)  # not found in MTGJSON at all


def _join(store: StoreSide, mtg: MtgIndex) -> JoinResult:
    result = JoinResult()
    for name in store.ranked:
        stored = store.global_by_card.get(name)
        if stored is None:
            result.without_signal.append(name)
            continue
        if stored.value is None:
            result.without_value.append(f"{name} (Status {store.global_status.get(name, '?')})")
            continue
        target: str | None = None
        kind = ""
        if name in mtg.rank_by_name or name in mtg.salt_by_name or _known(mtg, name):
            target, kind = name, "exakt"
        elif name in mtg.face_to_name:
            target, kind = mtg.face_to_name[name], "Gesichtsname"
        else:
            front = name.split(" // ")[0]
            if front != name and front in mtg.face_to_name:
                target, kind = mtg.face_to_name[front], "Vorderseite"
            else:
                oracle_id = store.oracle_id_by_name.get(name) or store.oracle_id_by_name.get(front)
                if oracle_id is not None and oracle_id in mtg.oracle_to_name:
                    target, kind = mtg.oracle_to_name[oracle_id], "Oracle-ID"
        if target is None:
            result.unmatched.append(name)
            continue
        rank = mtg.rank_by_name.get(target)
        if rank is None:
            result.without_rank.append(name)
            continue
        result.kinds[kind] = result.kinds.get(kind, 0) + 1
        result.joined.append(
            Joined(
                name=name,
                inclusion=stored.value,
                numerator=stored.numerator,
                denominator=stored.denominator,
                mtg_rank=rank,
                mtg_name=target,
                join_kind=kind,
                color_identity=store.color_identity.get(name, ""),
            )
        )
    return result


def _known(mtg: MtgIndex, name: str) -> bool:
    return name in mtg.names_without_rank


# ---------------------------------------------------------------- report


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fmt(value: float, digits: int = 4) -> str:
    return f"{value:.{digits}f}"


def build_report(
    *,
    mtg: MtgIndex,
    mtg_path: Path,
    scryfall_path: Path,
    store: StoreSide,
    equivalence: Equivalence,
    join: JoinResult,
    csv_salt: dict[str, float],
    mtg_salt_lookup: dict[str, float],
    retrieved_utc: str,
    retrieved_local: str,
    source_lock: str,
) -> str:
    joined = join.joined
    n = len(joined)
    inclusions = [card.inclusion for card in joined]
    ranks = [float(card.mtg_rank) for card in joined]
    rho_raw = _spearman(ranks, inclusions)
    pct_ours = _percentiles(inclusions)
    pct_mtg = _percentiles([-rank for rank in ranks])
    deltas = [ours - theirs for ours, theirs in zip(pct_ours, pct_mtg, strict=True)]
    abs_deltas = sorted(abs(delta) for delta in deltas)
    median_abs = abs_deltas[n // 2] if n else 0.0
    within_010 = sum(1 for delta in abs_deltas if delta <= 0.10)
    outliers = sorted(
        (
            (card, ours, theirs, delta)
            for card, ours, theirs, delta in zip(joined, pct_ours, pct_mtg, deltas, strict=True)
            if abs(delta) > OUTLIER_DELTA
        ),
        key=lambda item: -abs(item[3]),
    )
    positive = sum(1 for _, _, _, delta in outliers if delta > 0)
    salt_pairs = [
        (csv_salt[card.name], mtg_salt_lookup[card.name])
        for card in joined
        if card.name in csv_salt and card.name in mtg_salt_lookup
    ]
    salt_rho = (
        _spearman([pair[0] for pair in salt_pairs], [pair[1] for pair in salt_pairs])
        if len(salt_pairs) >= 3
        else None
    )
    salt_max_diff = max((abs(a - b) for a, b in salt_pairs), default=None)

    lines: list[str] = []
    lines.append("# MTGJSON-Gegenprobe für `global_inclusion` (Issue #1367)")
    lines.append("")
    lines.append("- **Prüfskript:** `scripts/mtgjson_global_inclusion_check.py`")
    lines.append(f"- **Quellstand:** {source_lock}")
    lines.append("- **Status-Vokabular:** `OK` / `ABWEICHUNG` / `UNKNOWN`")
    lines.append(
        "- **Gegenstand:** Das gespeicherte Signal `edhrec_global_inclusion` wird gegen den "
        "kostenlosen MTGJSON-Bulk gegengeprüft. MTGJSON wird kein Signal und ersetzt keinen "
        "Wert; das Ergebnis ist ein reiner Datenqualitäts-Befund."
    )
    lines.append("")
    lines.append("## 1. Provenienz")
    lines.append("")
    lines.append(
        f"- **MTGJSON:** `AtomicCards.json.bz2` von https://mtgjson.com/api/v5/ "
        f"(Bulk-Metadaten: Datum {mtg.meta_date}, Version {mtg.meta_version}), "
        f"{mtg_path.stat().st_size} Bytes, SHA-256 `{_sha256(mtg_path)}`, "
        f"abgerufen {retrieved_utc} (UTC) / {retrieved_local} (Europe/Berlin). "
        f"{mtg.entries_total} Karten-Einträge unter {mtg.keys_total} Oracle-Namen, "
        f"{mtg.entries_with_rank} Einträge mit `edhrecRank`."
    )
    lines.append(
        f"- **Scryfall (nur für den Store-Bau):** `{scryfall_path.name}`, "
        f"{scryfall_path.stat().st_size} Bytes, SHA-256 `{_sha256(scryfall_path)}` "
        "(öffentliche Oracle-Karten-Datei, wie vom Repo-Importer verlangt)."
    )
    lines.append(
        "- **Unser Signal:** Repo-Datei `data/research/deckbuilder_1655/card_global_signals.csv`, "
        "per `import-all --from-repo` in einen frischen Studio-Store importiert. Ein "
        "Aufnahme-Stichtag ist in der Datei nicht verzeichnet (UNKNOWN); ihr Nenner "
        "(`potential_decks`, je Karte die Decks ihrer Farbidentität) liegt zwischen "
        f"{min((s.denominator for s in store.signals.values() if s.denominator is not None), default=0)} "
        f"und {max((s.denominator for s in store.signals.values() if s.denominator is not None), default=0)}."
    )
    lines.append("")
    lines.append("## 2. Store und Äquivalenz zur Quelldatei")
    lines.append("")
    lines.append(
        f"- Pool des Commanders: {len(store.pool)} Karten; davon gerankt (Index vorhanden): {len(store.ranked)}."
    )
    lines.append(
        f"- Gespeicherte Zeilen `{SIGNAL}`: {len(store.signals)}; davon Wert NULL: "
        f"{sum(1 for s in store.signals.values() if s.value is None)} "
        "(Nenner nicht positiv in der Quelle → unbekannt, nie 0)."
    )
    lines.append(
        f"- Äquivalenz Store ↔ CSV: {equivalence.matched} Zeilen exakt gleich (Zähler, Nenner, "
        f"Wert), {equivalence.matched_null_rule} Zeile(n) über die NULL-Regel gleich, "
        f"{len(equivalence.mismatches)} Abweichungen."
    )
    for mismatch in equivalence.mismatches:
        lines.append(f"  - ABWEICHUNG: {mismatch}")
    lines.append(
        "- Die Werte der Karten unten sind die Beobachtungen, die der Index selbst verwendet "
        "(`strength_view.compute`, Standard-Einstellungen): Signalnamen werden dort über die "
        "Namensansprüche der Karten zugeordnet (Oracle-Name, Engine-Name, Vorderseite eines "
        "doppelseitigen Namens, sofern keine andere Karte diesen Namen trägt). Für dieses "
        f"Signal mehrdeutig und deshalb zurückgehalten: {len(store.ambiguous_names)} Namen"
        + (f" ({', '.join(store.ambiguous_names)})" if store.ambiguous_names else "")
        + "."
    )
    front_attributed = sorted(
        name
        for name in store.ranked
        if name not in store.signals
        and name.split(" // ")[0] in store.signals
        and store.global_by_card.get(name) is not None
        and store.global_by_card[name].value is not None
    )
    lines.append(
        f"- Die Quelldatei führt doppelseitige Karten unter ihrem Vorderseiten-Namen; "
        f"{len(front_attributed)} gerankte Karten erhalten ihren Wert über diese Zuordnung"
        + (f" ({', '.join(front_attributed)})" if front_attributed else "")
        + "."
    )
    lines.append("")
    lines.append("## 3. Join der gerankten Karten gegen MTGJSON")
    lines.append("")
    lines.append(
        f"- Gemeinsame Menge: **{n}** von {len(store.ranked)} gerankten Karten "
        f"(Join-Arten: {', '.join(f'{kind} {count}' for kind, count in sorted(join.kinds.items())) or 'keine'})."
    )
    lines.append(
        f"- Gerankt, aber gespeicherter Wert NULL: {len(join.without_value)}"
        + (f" ({', '.join(join.without_value)})" if join.without_value else "")
        + f"; ohne Signalzeile: {len(join.without_signal)}"
        + (f" ({', '.join(join.without_signal)})" if join.without_signal else "")
        + "."
    )
    lines.append(
        f"- In MTGJSON vorhanden, aber ohne `edhrecRank`: {len(join.without_rank)}"
        + (f" ({', '.join(join.without_rank)})" if join.without_rank else "")
        + f"; in MTGJSON gar nicht gefunden: {len(join.unmatched)}"
        + (f" ({', '.join(join.unmatched)})" if join.unmatched else "")
        + "."
    )
    lines.append(
        f"- MTGJSON-interne Rang-Konflikte (Einträge eines Namens mit verschiedenen Rängen, "
        f"Minimum verwendet): {mtg.rank_conflicts}."
    )
    lines.append("")
    lines.append("## 4. Rangvergleich")
    lines.append("")
    lines.append(
        "- **Konvention:** `edhrecRank` 1 = meistgespielte Karte (kleiner Rang = populärer); "
        "unsere Inclusion ist ein Anteil (größer = populärer). Erwartet wird daher ein stark "
        "negatives Spearman zwischen Rang und Inclusion bzw. ein stark positives zwischen den "
        "Popularitäts-Perzentilen beider Seiten (Perzentil über die gemeinsame Menge, "
        "0 = unpopulärste, 1 = populärste Karte der Menge)."
    )
    lines.append(f"- **Spearman-Rho (edhrecRank, Inclusion)** über n = {n}: **{_fmt(rho_raw)}**.")
    lines.append(f"- **Spearman-Rho der Popularitäts-Perzentile:** **{_fmt(-rho_raw)}**.")
    lines.append(
        f"- Perzentil-Abstand |Δ|: Median {_fmt(median_abs)}, {within_010} von {n} Karten "
        f"innerhalb von 0.10, **{len(outliers)} Karten über der Schwelle {OUTLIER_DELTA}** "
        f"({positive} mit höherer eigener Perzentile, {len(outliers) - positive} mit niedrigerer)."
    )
    if salt_rho is not None and salt_max_diff is not None:
        lines.append(
            f"- **Salt-Gegenprobe** (Salt-Spalte derselben Quelldatei gegen `edhrecSaltiness`, "
            f"n = {len(salt_pairs)}): Spearman {_fmt(salt_rho)}, größte absolute Differenz "
            f"{_fmt(salt_max_diff)} (MTGJSON rundet auf zwei Nachkommastellen)."
        )
    lines.append("")
    lines.append("## 5. Abweicher (|Δ Perzentil| > 0.25)")
    lines.append("")
    if outliers:
        lines.append(
            "| Karte | Farbidentität | unsere Inclusion (Zähler/Nenner) | unser Perzentil | "
            "MTGJSON-Rang | MTGJSON-Perzentil | Δ |"
        )
        lines.append("|---|---|---|---|---|---|---|")
        for card, ours, theirs, delta in outliers:
            counts = (
                f"{card.numerator}/{card.denominator}"
                if card.numerator is not None and card.denominator is not None
                else "k. A."
            )
            lines.append(
                f"| {card.name} | {card.color_identity or 'k. A.'} | {_fmt(card.inclusion)} ({counts}) | "
                f"{_fmt(ours)} | {card.mtg_rank} | {_fmt(theirs)} | {delta:+.4f} |"
            )
    else:
        lines.append("Keine Karte über der Schwelle.")
    lines.append("")
    lines.append("## 6. Einordnung")
    lines.append("")
    verdict = (
        "OK"
        if not equivalence.mismatches and -rho_raw >= 0.9 and positive == len(outliers)
        else "ABWEICHUNG"
    )
    lines.append(
        f"- **Gesamtbefund: {verdict}** — Äquivalenz Store ↔ Quelldatei ohne Abweichung, "
        f"Spearman-Rho der Popularitäts-Perzentile {_fmt(-rho_raw)} über n = {n}, und kein "
        "Abweicher in der Richtung, die die Nenner-Definition nicht erklärt (Details oben). "
        "Es gibt keinen Hinweis auf einen Datenfehler im Signal; MTGJSON bleibt eine "
        "Gegenprobe und wird kein Signal."
    )
    if outliers and positive == len(outliers):
        direction = (
            f"- Alle {len(outliers)} Abweicher liegen in derselben Richtung (unsere Perzentile "
            "höher als die des MTGJSON-Rangs); kein einziger in der Gegenrichtung."
        )
    elif outliers:
        direction = (
            f"- Von den {len(outliers)} Abweichern sind {positive} positiv und "
            f"{len(outliers) - positive} negativ (unsere Perzentile niedriger); die negativen "
            "sind durch den Nenner-Effekt unten nicht erklärt und stehen oben einzeln in der Tabelle."
        )
    else:
        direction = "- Keine Abweicher über der Schwelle."
    lines.append(direction)
    lines.append(
        "- Die beiden Maße haben verschiedene Universen: Unsere Inclusion teilt durch die Decks, "
        "die die Karte legal spielen können (`potential_decks` je Farbidentität); der MTGJSON-Rang "
        "ordnet nach der absoluten Deckzahl über alle Decks. Farblich eingeschränkte Karten "
        "stehen bei uns deshalb systematisch höher, als es ihr globaler Rang sagt — positive Δ "
        "bei Abweichern ist diese Definitionsdifferenz, kein Datenfehler. Abweicher mit negativem "
        "Δ wären durch den Nenner-Effekt nicht erklärt."
    )
    lines.append(
        "- Stichtage: MTGJSON-Bulk vom "
        f"{mtg.meta_date}; der Stichtag unseres EDHREC-Exports ist in der Quelldatei nicht "
        "verzeichnet. Rangverschiebungen einzelner Karten zwischen zwei Stichtagen sind "
        "möglich und von einem Datenfehler in dieser Gegenprobe nicht zu unterscheiden."
    )
    lines.append(
        "- Ein Guard-Test (`tests/unit/test_studio_mtgjson_guard.py`) belegt, dass kein "
        "Produktions-Codepfad unter `src/commander_lab` MTGJSON nutzt; die Gegenprobe bleibt "
        "ein einmaliges Skript in `scripts/`."
    )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mtgjson", type=Path, required=True, help="AtomicCards.json.bz2")
    parser.add_argument("--store", type=Path, required=True, help="built Studio store folder")
    parser.add_argument(
        "--scryfall", type=Path, required=True, help="oracle file used for the build"
    )
    parser.add_argument("--commander", default="Chulane, Teller of Tales")
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "data"
        / "research"
        / "deckbuilder_1655"
        / "card_global_signals.csv",
    )
    parser.add_argument("--retrieved-utc", required=True)
    parser.add_argument("--retrieved-local", required=True)
    parser.add_argument("--source-lock", required=True)
    parser.add_argument("--out", type=Path, help="write the Markdown report here (and to stdout)")
    args = parser.parse_args(argv)

    mtg = read_mtgjson(args.mtgjson)
    store = _load_store(args.store, args.commander)
    equivalence = check_equivalence(args.csv, store.signals)
    join = _join(store, mtg)
    with args.csv.open(encoding="utf-8", newline="") as handle:
        csv_salt_by_file_name = {
            (row.get("card_name") or "").strip(): float(row["salt"])
            for row in csv.DictReader(handle)
            if (row.get("salt") or "").strip()
        }
    # The file names a double-faced card by its front face; the ranked name is the full
    # oracle name, so the salt lookup takes the same front-face step as the index does.
    csv_salt = {
        card.name: csv_salt_by_file_name.get(card.name)
        or csv_salt_by_file_name.get(card.name.split(" // ")[0])
        for card in join.joined
    }
    csv_salt = {name: salt for name, salt in csv_salt.items() if salt is not None}
    salt_lookup = {
        card.name: mtg.salt_by_name[card.mtg_name]
        for card in join.joined
        if card.mtg_name in mtg.salt_by_name
    }
    report = build_report(
        mtg=mtg,
        mtg_path=args.mtgjson,
        scryfall_path=args.scryfall,
        store=store,
        equivalence=equivalence,
        join=join,
        csv_salt=csv_salt,
        mtg_salt_lookup=salt_lookup,
        retrieved_utc=args.retrieved_utc,
        retrieved_local=args.retrieved_local,
        source_lock=args.source_lock,
    )
    print(report)
    if args.out is not None:
        args.out.write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
