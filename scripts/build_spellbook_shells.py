"""Build the spellbook shell counts (#1366) for the Chulane pool.

``spellbook_card_links.csv`` counts variants — every concrete way to assemble
a combo — so one combo with many printed equivalents for a flexible slot
inflates the count (Pitiless Plunderer: 3,282 variants). This script reads the
Commander Spellbook bulk export (one public JSON document; only variant ids
from the committed link file are looked up in it, nothing about the
collection leaves the machine beyond that public download) and writes
``spellbook_shells.csv`` next to the link file: per collection card the
number of distinct combos (shells: combos that share a variant through ``of`` are one
shell) it takes part in
under Chulane — colour identity WUG, every used card in the legal pool of 927
(the pool of ``data/research/chulane_legal_pool_gap_matrix.json``) — split by
card count (two vs. three or more, template slots counted) and by commander
involvement.

    python scripts/build_spellbook_shells.py --bulk ~/Downloads/variants.json.gz

Without ``--bulk`` the export is downloaded from
https://json.commanderspellbook.com/variants.json.gz (the route the
spellbook itself publishes for full exports).
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from commander_lab.studio import spellbook_shells  # noqa: E402

BULK_URL = "https://json.commanderspellbook.com/variants.json.gz"
RESEARCH = _REPO_ROOT / "data" / "research"
LINKS_FILE = RESEARCH / "deckbuilder_1655" / "spellbook_card_links.csv"
POOL_FILE = RESEARCH / "chulane_legal_pool_gap_matrix.json"
OUTPUT_FILE = RESEARCH / "deckbuilder_1655" / "spellbook_shells.csv"
FIELDS = [
    "commander_name",
    "card_name",
    "fetch_status",
    "shell_count",
    "shell_count_2card",
    "shell_count_3plus",
    "shell_count_commander",
    "shell_ids",
]
VALID_IDENTITY = frozenset({"W", "U", "B", "R", "G", spellbook_shells.COLOURLESS})


def _parse_identity(text: str) -> frozenset[str]:
    letters = {char for char in text.strip().upper() if char not in {",", " ", "/"}}
    unknown = letters - VALID_IDENTITY
    if not letters or unknown:
        raise ValueError(f"invalid colour identity: {text!r}")
    return frozenset(letters - {spellbook_shells.COLOURLESS})


def _load_bulk(path: Path | None) -> tuple[dict[str, object], str]:
    """The bulk document and the SHA-256 of the exact bytes it was read from."""
    if path is None:
        request = urllib.request.Request(BULK_URL, headers={"User-Agent": "commander-lab-shells"})
        with urllib.request.urlopen(request, timeout=300) as response:
            raw = response.read()
    else:
        raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    document = json.loads(raw)
    if not isinstance(document, dict):
        raise ValueError("the spellbook bulk export is not a JSON object")
    return document, digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bulk", type=Path, help="local variants.json[.gz] (default: download)")
    parser.add_argument("--links", type=Path, default=LINKS_FILE)
    parser.add_argument("--pool", type=Path, default=POOL_FILE)
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE)
    parser.add_argument("--commander", default=spellbook_shells.CHULANE_NAME)
    parser.add_argument("--identity", default="WUG")
    args = parser.parse_args()

    identity = _parse_identity(args.identity)
    commander = args.commander.strip()
    if not commander:
        raise ValueError("--commander must not be blank")

    document, digest = _load_bulk(args.bulk)
    variants = document.get("variants")
    aliases = document.get("aliases")
    if not isinstance(variants, list) or not isinstance(aliases, list):
        raise ValueError("the spellbook bulk export lacks variants/aliases")
    index = spellbook_shells.build_variant_index(variants, aliases)

    matrix = json.loads(args.pool.read_text(encoding="utf-8"))
    pool = {str(card["card_name"]) for card in matrix["cards"]}

    rows: list[dict[str, object]] = []
    with args.links.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            ids = [part for part in (row.get("variant_ids") or "").split(";") if part.strip()]
            counts = spellbook_shells.count_shells(
                ids, index, pool, identity=identity, commander=commander
            )
            rows.append(
                {
                    "commander_name": commander,
                    "card_name": row["card_name"],
                    "fetch_status": row.get("fetch_status") or "AVAILABLE",
                    "shell_count": counts.shells,
                    "shell_count_2card": counts.two_card,
                    "shell_count_3plus": counts.three_plus,
                    "shell_count_commander": counts.with_commander,
                    "shell_ids": ";".join(str(shell) for shell in counts.shell_ids),
                }
            )
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    listed = sum(1 for row in rows if int(str(row["shell_count"])) > 0)
    distinct = len({shell for row in rows for shell in str(row["shell_ids"]).split(";") if shell})
    print(f"bulk version {document.get('version')}, timestamp {document.get('timestamp')}")
    print(f"bulk sha256 {digest}")
    print(f"variants indexed {len(index)}, pool {len(pool)}, commander {commander}")
    print(f"rows {len(rows)}, cards with shells {listed}, distinct shells {distinct}")
    print(f"written {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
