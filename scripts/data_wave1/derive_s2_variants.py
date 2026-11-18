"""S2, offline: derive the white-blue-green variants and the alias table from the raw bulk file.

Input: ``raw/variants.json.gz`` of a run folder written by ``fetch_s2_spellbook.py``. No network.
The 740 MB unpacked JSON is read as a stream (never held whole in memory; limits
``--max-unpacked-mb`` and 64 MiB per object). When it has succeeded the raw file is DELETED (it still
contains prices, salt votes and popularity), only hash and size stay in the manifest; ``--keep-raw``
keeps it and the manifest then says so (``raw_contains_excluded_fields: true``). Output:

* ``derived/variants_wug.jsonl``: every variant whose colour identity is a subset of {W, U, G}
  (plus colourless): id, status, commander legality, identity, cards with Oracle id and zones,
  requirements, results, prerequisites, ``generates`` and ``includes_combos`` (ids of other combo
  records, NOT aliases), ``bracket_tag`` (raw, see below).
* ``derived/aliases.jsonl``: the real alias table of the source (top level ``aliases``: old id to
  current ``variant``; most have no target).

Not copied: prices, salt votes, popularity and variant counters, description and notes text, image
addresses. Card facts only; no collection reference (that is computed by ``validate_s2.py``).

``bracket_tag`` is kept raw: only "B if and only if not commander legal" is verified; the other
letters are the source's own estimate per combo and no explained deck bracket, so they must never
be mixed with the bracket cohort of decks until the legend is documented.
"""

from __future__ import annotations

import argparse
import collections
import gzip
import json
import re
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as common

COLOURS = frozenset("WUG") | {"C"}
MARKER = '"variants": ['
CHUNK = 1 << 22
COMPACT_AFTER = 1 << 23


class VariantStream:
    """Incremental reader: header text, then variant objects, then the alias list."""

    def __init__(
        self, path: Path, max_unpacked: int = common.DEFAULT_MAX_UNPACKED_MB * common.MIB
    ) -> None:
        self._path = path
        self._max_unpacked = max_unpacked
        self._read_total = 0
        self._file: Any = None
        self._buffer = ""
        self._eof = False
        self.timestamp: str | None = None
        self.version: str | None = None
        self.aliases: list[dict[str, Any]] = []
        self.aliases_found = False

    def _fill(self) -> bool:
        if self._eof:
            return False
        chunk = self._file.read(CHUNK)
        if not chunk:
            self._eof = True
            return False
        self._read_total += len(chunk)
        if self._read_total > self._max_unpacked:
            raise common.ResponseTooLarge(
                f"unpacked stream exceeds {self._max_unpacked} characters"
            )
        self._buffer += chunk
        return True

    def variants(self) -> Iterator[dict[str, Any]]:
        with gzip.open(self._path, "rt", encoding="utf-8") as handle:
            self._file = handle
            yield from self._variants()

    def _variants(self) -> Iterator[dict[str, Any]]:
        decoder = json.JSONDecoder()
        while MARKER not in self._buffer:
            if len(self._buffer) > common.MAX_LINE_BYTES:
                raise common.ResponseTooLarge("no 'variants' list within the size limit")
            if not self._fill():
                raise common.WaveError("variants.json.gz has no 'variants' list")
        start = self._buffer.index(MARKER)
        header = self._buffer[:start]
        stamp = re.search(r'"timestamp": "([^"]+)"', header)
        version = re.search(r'"version": "([^"]+)"', header)
        self.timestamp = stamp.group(1) if stamp else None
        self.version = version.group(1) if version else None
        pos = start + len(MARKER)
        buffer = self._buffer
        while True:
            while True:
                while pos < len(buffer) and buffer[pos] in ", \n\r\t":
                    pos += 1
                if pos < len(buffer):
                    break
                self._buffer = buffer
                if not self._fill():
                    raise common.WaveError("variants list is not closed")
                buffer = self._buffer
            if buffer[pos] == "]":
                break
            try:
                item, end = decoder.raw_decode(buffer, pos)
            except json.JSONDecodeError:
                if len(buffer) - pos > common.MAX_LINE_BYTES:
                    raise common.ResponseTooLarge(
                        "one variant object exceeds the size limit"
                    ) from None
                self._buffer = buffer
                if not self._fill():
                    raise common.WaveError("truncated variant object") from None
                buffer = self._buffer
                continue
            pos = end
            yield item
            if pos > COMPACT_AFTER:
                buffer = buffer[pos:]
                pos = 0
        self._buffer = buffer[pos + 1 :]
        while self._fill():
            pass
        tail = self._buffer
        index = tail.find('"aliases"')
        if index >= 0:
            self.aliases = json.loads("{" + tail[index:])["aliases"]
            self.aliases_found = True


def _ids(items: Any, shape: collections.Counter[str], field: str) -> list[Any]:
    result = []
    for item in items or []:
        if set(item) != {"id"}:
            shape[field] += 1
        result.append(item.get("id"))
    return result


def variant_row(variant: dict[str, Any], shape: collections.Counter[str]) -> dict[str, Any]:
    legal = bool((variant.get("legalities") or {}).get("commander"))
    cards = []
    for use in variant.get("uses") or []:
        card = use.get("card") or {}
        cards.append(
            {
                "card_id": card.get("id"),
                "oracle_id": card.get("oracleId"),
                "name": card.get("name"),
                "type_line": card.get("typeLine"),
                "faces": card.get("faces"),
                "spoiler": card.get("spoiler"),
                "zones": use.get("zoneLocations"),
                "quantity": use.get("quantity"),
                "must_be_commander": use.get("mustBeCommander"),
                "used_face": use.get("usedFace"),
            }
        )
    return {
        "id": variant.get("id"),
        "status": variant.get("status"),
        "spoiler": variant.get("spoiler"),
        "commander_legal": legal,
        "identity": variant.get("identity") or "",
        "bracket_tag": variant.get("bracketTag"),
        "cards": cards,
        "requires": variant.get("requires"),
        "produces": [
            {
                "feature_id": (item.get("feature") or {}).get("id"),
                "name": (item.get("feature") or {}).get("name"),
                "quantity": item.get("quantity"),
            }
            for item in (variant.get("produces") or [])
        ],
        "easy_prerequisites": variant.get("easyPrerequisites"),
        "notable_prerequisites": variant.get("notablePrerequisites"),
        "mana_needed": variant.get("manaNeeded"),
        "mana_value_needed": variant.get("manaValueNeeded"),
        "generates": _ids(variant.get("of"), shape, "of"),
        "includes_combos": _ids(variant.get("includes"), shape, "includes"),
    }


def derive(
    raw: Path, derived_dir: Path, max_unpacked: int = common.DEFAULT_MAX_UNPACKED_MB * common.MIB
) -> dict[str, Any]:
    stream = VariantStream(raw, max_unpacked)
    total = legal_total = wug = wug_legal = 0
    status: collections.Counter[str | None] = collections.Counter()
    bracket: collections.Counter[str | None] = collections.Counter()
    shape: collections.Counter[str] = collections.Counter()
    with common.open_text_out(derived_dir / "variants_wug.jsonl") as writer:
        for variant in stream.variants():
            total += 1
            legal = bool((variant.get("legalities") or {}).get("commander"))
            legal_total += legal
            status[variant.get("status")] += 1
            if not set(variant.get("identity") or "") <= COLOURS:
                continue
            wug += 1
            wug_legal += legal
            bracket[variant.get("bracketTag")] += 1
            writer.write(json.dumps(variant_row(variant, shape), ensure_ascii=False) + "\n")
    seen: set[Any] = set()
    duplicates = with_target = 0
    with common.open_text_out(derived_dir / "aliases.jsonl") as writer:
        for alias in stream.aliases:
            duplicates += alias["id"] in seen
            seen.add(alias["id"])
            with_target += alias.get("variant") is not None
            writer.write(
                json.dumps(
                    {"alias_id": alias["id"], "variant_id": alias.get("variant")},
                    ensure_ascii=False,
                )
                + "\n"
            )
    return {
        "timestamp": stream.timestamp,
        "version": stream.version,
        "variants_total": total,
        "commander_legal_total": legal_total,
        "wug_rows": wug,
        "wug_commander_legal": wug_legal,
        "status_values": dict(status),
        "wug_bracket_tag_values": dict(bracket),
        "aliases_found": stream.aliases_found,
        "aliases_rows": len(stream.aliases),
        "aliases_with_target": with_target,
        "aliases_duplicate_ids": duplicates,
        "of_includes_elements_with_other_keys_than_id": dict(shape),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run-dir", type=Path, required=True, help="S2 run folder")
    common.add_limit_arguments(parser, download=False)
    parser.add_argument(
        "--keep-raw",
        action="store_true",
        help="keep raw/variants.json.gz (it contains price, salt and popularity fields); "
        "default: delete it after deriving",
    )
    args = parser.parse_args(argv)
    run_dir = common.assert_outside_repository(args.run_dir)
    raw = run_dir / "raw" / "variants.json.gz"
    try:
        counts = derive(
            raw, run_dir / "derived", common.mib_limit(args.max_unpacked_mb, "--max-unpacked-mb")
        )
    except (common.WaveError, OSError, EOFError, json.JSONDecodeError) as error:
        print(f"STOP: {error}", file=sys.stderr)
        return 2
    common.write_json(run_dir / "derived" / "derive_counts.json", counts)
    variants = run_dir / "derived" / "variants_wug.jsonl"
    aliases = run_dir / "derived" / "aliases.jsonl"
    entries = [
        common.derived_entry(
            variants,
            run_dir,
            rows_in=counts["variants_total"],
            data_class="Kartenfakten",
            filter="identity subset of {W,U,G,C} (C = colourless)",
            cohort_scope="keine (Kartenfakten)",
        ),
        common.derived_entry(
            aliases,
            run_dir,
            rows_in=counts["aliases_rows"],
            data_class="Kartenfakten",
            note="real alias table: old variant id to current variant id (null without target)",
        ),
        common.derived_entry(run_dir / "derived" / "derive_counts.json", run_dir, kind="zaehlung"),
    ]
    common.update_manifest(
        run_dir,
        {
            "counts": counts,
            "dropped_fields": [
                "prices",
                "salt",
                "saltVoteCount",
                "popularity",
                "variantCount",
                "description",
                "notes",
                "image URIs",
            ],
            "field_mapping_source_to_derived": {
                "of": "generates (ids of the combo records that generate this variant; NOT aliases)",
                "includes": "includes_combos (ids of contained combo records; NOT aliases)",
                "aliases (top level of the raw file)": "derived/aliases.jsonl {alias_id, variant_id}",
                "legalities.commander": "commander_legal",
                "bracketTag": "bracket_tag (raw)",
                "uses[].card.oracleId": "cards[].oracle_id",
            },
            "bracket_tag_note": (
                "raw; only 'B <=> not commander legal' is verified; the legend of the other "
                "letters is not documented here: the source's own estimate per combo, no "
                "explained deck bracket, never mix with the bracket cohort of decks"
            ),
        },
        entries,
    )
    common.settle_raw(run_dir, keep=args.keep_raw)
    print(json.dumps(counts, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
