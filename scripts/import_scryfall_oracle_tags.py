#!/usr/bin/env python3
"""Import Scryfall Tagger bulk dataset into Commander Studio.

Source and Provenance:
- Source: Scryfall Bulk Data API (https://api.scryfall.com/bulk-data, type: "oracle_tags")
- Official Bulk URI format:
  https://data.scryfall.io/oracle-tags/oracle-tags-<timestamp>.jsonl.gz
- Scryfall Attribution / License Notice:
  Tag data courtesy of Scryfall Tagger community (https://tagger.scryfall.com).
  Magic: The Gathering is copyright Wizards of the Coast LLC.
  Scryfall is not affiliated with Wizards of the Coast. Scryfall data is
  provided under Scryfall's API Terms of Service.

Functionality:
- Streams JSONL/JSONL.gz bulk file line by line (one tag graph node per line).
- Builds hierarchy of tag parents/children so descendant tags are mapped to parent roles.
- Supports 24-category functional taxonomy (17 Studio roles + 7 extensions).
- Negativnachweis: validates that 'stax', 'token', 'card-selection' have 0 matches in bulk vocabulary.
- Explicit mapping rules for aliased tags ('sweeper' -> board_wipe, 'hate-graveyard' -> graveyard_hate).
- Writes claims with origin 'SCRYFALL_TAGGER_BULK' into card_role_claim without overwriting
  existing claims from other origins (lossless merge, transactional).
- Rebuilds card_role and corpus_deck_role respecting origin priority.

No private collection, deck, or owner data is stored or exposed.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from commander_lab.studio.roles import (
    LEGACY_ORIGIN,
    ORIGIN_CROSSWALK,
    ORIGIN_ORACLE_TEXT,
    ORIGIN_TAGGER,
)
from commander_lab.studio.store import (
    DataClass,
    StudioStore,
    rebuild_corpus_deck_role,
    sha256_file,
    studio_data_dir,
)

SCRYFALL_BULK_METADATA_URL = "https://api.scryfall.com/bulk-data"
USER_AGENT = (
    "CommanderPlaytestLab-Research/1.0 (+https://github.com/moeendres-png/commander-playtest-lab)"
)
ORIGIN_TAGGER_BULK = "SCRYFALL_TAGGER_BULK"
SCOPE_KEY_GLOBAL = "ALL_CARDS"

# Negative vocabulary targets that must not exist in Scryfall Tagger bulk vocabulary
NEGATIVE_VOCABULARY_TARGETS: tuple[str, ...] = ("stax", "token", "card-selection")

# Known aliases: query slug -> canonical tag slug in bulk
KNOWN_ALIASES: dict[str, str] = {
    "board-wipe": "sweeper",
    "graveyard-hate": "hate-graveyard",
}

# 24-category functional taxonomy: role_name -> primary tag slug
ROLE_TAXONOMY_24: dict[str, str] = {
    # 17 Studio roles from roles.ROLES
    "ramp": "ramp",
    "mana_rock": "mana-rock",
    "mana_dork": "mana-dork",
    "land_ramp": "land-ramp",
    "card_draw": "draw",
    "card_advantage": "card-advantage",
    "cantrip": "cantrip",
    "tutor": "tutor",
    "removal": "removal",
    "board_wipe": "sweeper",
    "counterspell": "counterspell",
    "bounce": "bounce",
    "flicker": "flicker",
    "recursion": "recursion",
    "protection": "protection",
    "graveyard_hate": "hate-graveyard",
    "lifegain": "lifegain",
    # 7 Extensions completing the 24 taxonomy
    "anthem": "anthem",
    "hatebear": "hatebear",
    "evasion": "evasion",
    "extra_turn": "extra-turn",
    "card_selection": "card-selection",
    "stax": "stax",
    "token": "token",
}

_ORIGIN_RANK = (
    f"CASE role_origin "
    f"WHEN '{ORIGIN_TAGGER}' THEN 0 "
    f"WHEN '{ORIGIN_CROSSWALK}' THEN 1 "
    f"WHEN '{ORIGIN_ORACLE_TEXT}' THEN 2 "
    f"WHEN '{ORIGIN_TAGGER_BULK}' THEN 3 "
    f"WHEN '{LEGACY_ORIGIN}' THEN 4 "
    f"ELSE 5 END"
)


@dataclass(frozen=True)
class TagNode:
    """One tag node parsed from the bulk stream."""

    tag_id: str
    slug: str
    label: str
    aliases: tuple[str, ...]
    parent_ids: tuple[str, ...]
    child_ids: tuple[str, ...]
    oracle_ids: frozenset[str]


@dataclass
class BulkGraph:
    """Graph of all tags and their hierarchy."""

    nodes_by_id: dict[str, TagNode] = field(default_factory=dict)
    node_id_by_slug: dict[str, str] = field(default_factory=dict)
    node_id_by_label: dict[str, str] = field(default_factory=dict)
    total_tags_count: int = 0
    parse_errors_count: int = 0

    def add_node(self, node: TagNode) -> None:
        self.nodes_by_id[node.tag_id] = node
        if node.slug:
            self.node_id_by_slug[node.slug.lower()] = node.tag_id
        if node.label:
            self.node_id_by_label[node.label.lower()] = node.tag_id
        for alias in node.aliases:
            if alias:
                self.node_id_by_slug[alias.lower()] = node.tag_id
        self.total_tags_count += 1

    def find_tag_id(self, identifier: str) -> str | None:
        clean = identifier.strip().lower()
        return self.node_id_by_slug.get(clean) or self.node_id_by_label.get(clean)

    def get_descendant_oracle_ids(self, target_identifier: str) -> tuple[frozenset[str], str]:
        """Collect all oracle_ids for a tag including its child hierarchy.

        Returns (frozenset of oracle_ids, mapping_rule).
        """
        canonical_slug = KNOWN_ALIASES.get(target_identifier.lower(), target_identifier.lower())
        root_id = self.find_tag_id(canonical_slug)
        if not root_id:
            return frozenset(), "not_found_in_vocabulary"

        root_node = self.nodes_by_id[root_id]
        rule = (
            f"alias: {target_identifier} -> {root_node.slug}"
            if canonical_slug != target_identifier.lower()
            else f"direct: {root_node.slug}"
        )

        gathered: set[str] = set()
        visited: set[str] = set()
        queue: list[str] = [root_id]

        while queue:
            curr_id = queue.pop(0)
            if curr_id in visited:
                continue
            visited.add(curr_id)
            node = self.nodes_by_id.get(curr_id)
            if not node:
                continue
            gathered.update(node.oracle_ids)
            for child_id in node.child_ids:
                if child_id not in visited:
                    queue.append(child_id)

        if len(visited) > 1:
            rule = f"{rule} + hierarchy ({len(visited) - 1} children)"

        return frozenset(gathered), rule


@dataclass(frozen=True)
class VocabularyAudit:
    total_tags: int
    negative_hits: dict[str, int]
    negative_audit_passed: bool
    categories_found: dict[str, bool]
    available_categories_count: int
    missing_categories_count: int


@dataclass(frozen=True)
class ImportStats:
    total_bulk_tags: int
    matched_collection_cards: int
    total_collection_cards: int
    claims_written: int
    claims_per_role: dict[str, int]
    vocabulary_audit: VocabularyAudit


def parse_tag_line(line: str, index: int) -> TagNode:
    """Validate and parse a single JSON line into a TagNode."""
    try:
        obj = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Line #{index}: invalid JSON: {exc}") from exc

    if not isinstance(obj, dict):
        raise ValueError(f"Line #{index}: expected JSON object, got {type(obj).__name__}")

    tag_id = obj.get("id")
    if not isinstance(tag_id, str) or not tag_id.strip():
        raise ValueError(f"Line #{index}: missing or invalid 'id'")

    slug = str(obj.get("slug") or "").strip()
    label = str(obj.get("label") or "").strip()

    raw_aliases = obj.get("aliases")
    aliases: tuple[str, ...] = ()
    if isinstance(raw_aliases, list):
        aliases = tuple(str(a).strip() for a in raw_aliases if isinstance(a, str) and a.strip())

    raw_parents = obj.get("parent_ids")
    parent_ids: tuple[str, ...] = ()
    if isinstance(raw_parents, list):
        parent_ids = tuple(str(p).strip() for p in raw_parents if isinstance(p, str) and p.strip())

    raw_children = obj.get("child_ids")
    child_ids: tuple[str, ...] = ()
    if isinstance(raw_children, list):
        child_ids = tuple(str(c).strip() for c in raw_children if isinstance(c, str) and c.strip())

    raw_taggings = obj.get("taggings")
    oracle_ids: set[str] = set()
    if isinstance(raw_taggings, list):
        for t in raw_taggings:
            if isinstance(t, dict):
                oid = t.get("oracle_id")
                if isinstance(oid, str) and oid.strip():
                    oracle_ids.add(oid.strip().lower())

    return TagNode(
        tag_id=tag_id.strip(),
        slug=slug,
        label=label,
        aliases=aliases,
        parent_ids=parent_ids,
        child_ids=child_ids,
        oracle_ids=frozenset(oracle_ids),
    )


def iter_bulk_tags(path: Path) -> Iterator[TagNode]:
    """Iterate tag nodes from a .jsonl or .jsonl.gz file."""
    if not path.is_file():
        raise FileNotFoundError(f"Bulk file not found: {path}")

    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            for idx, line in enumerate(stream, start=1):
                line_str = line.strip()
                if not line_str:
                    continue
                yield parse_tag_line(line_str, idx)
    else:
        with path.open("r", encoding="utf-8") as stream:
            for idx, line in enumerate(stream, start=1):
                line_str = line.strip()
                if not line_str:
                    continue
                yield parse_tag_line(line_str, idx)


def load_bulk_graph(path: Path) -> BulkGraph:
    """Read bulk file into an in-memory BulkGraph."""
    graph = BulkGraph()
    for node in iter_bulk_tags(path):
        graph.add_node(node)
    return graph


def audit_vocabulary(graph: BulkGraph) -> VocabularyAudit:
    """Check negative vocabulary proof and available categories."""
    neg_hits: dict[str, int] = {}
    for term in NEGATIVE_VOCABULARY_TARGETS:
        tid = graph.find_tag_id(term)
        if tid is not None:
            node = graph.nodes_by_id[tid]
            neg_hits[term] = len(node.oracle_ids)
        else:
            neg_hits[term] = 0

    all_neg_zero = all(count == 0 for count in neg_hits.values())

    cat_found: dict[str, bool] = {}
    for role, slug in ROLE_TAXONOMY_24.items():
        canonical = KNOWN_ALIASES.get(slug, slug)
        cat_found[role] = graph.find_tag_id(canonical) is not None

    avail_count = sum(1 for f in cat_found.values() if f)
    missing_count = sum(1 for f in cat_found.values() if not f)

    return VocabularyAudit(
        total_tags=graph.total_tags_count,
        negative_hits=neg_hits,
        negative_audit_passed=all_neg_zero,
        categories_found=cat_found,
        available_categories_count=avail_count,
        missing_categories_count=missing_count,
    )


def fetch_oracle_tags_bulk_metadata() -> dict[str, str]:
    """Discover official download URI and timestamp from Scryfall bulk-data API."""
    req = urllib.request.Request(
        SCRYFALL_BULK_METADATA_URL,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status} fetching bulk metadata")
        payload = json.loads(resp.read().decode("utf-8"))

    data = payload.get("data", [])
    if not isinstance(data, list):
        raise ValueError("Invalid bulk metadata response: 'data' is not a list")

    for item in data:
        if isinstance(item, dict) and item.get("type") == "oracle_tags":
            uri = item.get("jsonl_download_uri") or item.get("download_uri")
            updated_at = item.get("updated_at")
            if isinstance(uri, str) and isinstance(updated_at, str):
                return {"download_uri": uri, "updated_at": updated_at}
    raise RuntimeError("No 'oracle_tags' bulk entry found in Scryfall bulk metadata")


def download_file(url: str, dest: Path) -> Path:
    """Download a file with chunked streaming."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(req) as resp, dest.open("wb") as out_f:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status} downloading {url}")
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            out_f.write(chunk)
    return dest


def resolve_collection_cards(store: StudioStore) -> dict[str, str]:
    """Return mapping of oracle_id -> oracle_name for all collection cards in store."""
    with store.connection as db:
        rows = db.execute(
            "SELECT oracle_id, oracle_name FROM card WHERE oracle_id IS NOT NULL"
        ).fetchall()
    return {str(row[0]).strip().lower(): str(row[1]) for row in rows}


def resolve_front_name(card_name: str) -> str:
    """Extract front name of a double-faced or split card."""
    return card_name.split(" // ")[0].strip()


def import_tagger_bulk_claims(
    store: StudioStore,
    bulk_path: Path,
    *,
    snapshot_date: str | None = None,
    dry_run: bool = False,
) -> ImportStats:
    """Read bulk file, match against store cards, write claims to card_role_claim."""
    graph = load_bulk_graph(bulk_path)
    vocab_audit = audit_vocabulary(graph)

    collection_cards = resolve_collection_cards(store)
    collection_oids = set(collection_cards.keys())

    # Build DFC front-name lookup fallback if needed
    name_to_oid: dict[str, str] = {}
    for oid, name in collection_cards.items():
        name_to_oid[name.lower()] = oid
        front = resolve_front_name(name).lower()
        if front != name.lower():
            name_to_oid[front] = oid

    file_sha256 = sha256_file(bulk_path)

    # Gather claims per category
    claims_to_insert: list[tuple[str, str, str, str, str | None, str, str]] = []
    matched_cards_global: set[str] = set()
    claims_per_role: dict[str, int] = {}

    for role, slug in ROLE_TAXONOMY_24.items():
        oids, rule = graph.get_descendant_oracle_ids(slug)
        # Direct oracle_id match with collection
        direct_matched = oids.intersection(collection_oids)
        matched_cards_global.update(direct_matched)
        claims_per_role[role] = len(direct_matched)

        for oid in direct_matched:
            claims_to_insert.append(
                (
                    oid,
                    role,
                    ORIGIN_TAGGER_BULK,
                    SCOPE_KEY_GLOBAL,
                    None,  # source_id assigned below
                    slug,
                    rule,
                )
            )

    if not dry_run:
        with store.connection as db:
            source_id = store.register_source(
                data_class=DataClass.ORIGINAL_SOURCE,
                title=bulk_path.name,
                sha256=file_sha256,
                snapshot_date=snapshot_date,
                url="https://tagger.scryfall.com/",
            )

            # Preserve existing card_role rows without claims as legacy claims
            db.execute(
                "INSERT INTO card_role_claim(oracle_id, role, role_origin, scope_key, source_id, "
                "original_tag, mapping_rule) SELECT r.oracle_id, r.role, ?, 'LEGACY', r.source_id, "
                "NULL, 'card_role row without claim' FROM card_role r WHERE NOT EXISTS ("
                "SELECT 1 FROM card_role_claim c WHERE c.oracle_id = r.oracle_id AND c.role = r.role)",
                (LEGACY_ORIGIN,),
            )

            # Insert claims without overwriting existing claims from any origin
            db.executemany(
                "INSERT OR IGNORE INTO card_role_claim(oracle_id, role, role_origin, scope_key, "
                "source_id, original_tag, mapping_rule) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (oid, role, origin, scope, source_id, tag, rule)
                    for oid, role, origin, scope, _, tag, rule in claims_to_insert
                ],
            )

            # Rebuild card_role respecting origin priority
            db.execute("DELETE FROM card_role")
            db.execute(
                "INSERT INTO card_role(oracle_id, role, source_id) "
                "SELECT oracle_id, role, source_id FROM ("
                "SELECT oracle_id, role, source_id, "
                f"ROW_NUMBER() OVER (PARTITION BY oracle_id, role ORDER BY {_ORIGIN_RANK}, source_id) AS n "
                "FROM card_role_claim) WHERE n = 1"
            )
            rebuild_corpus_deck_role(db)

    return ImportStats(
        total_bulk_tags=graph.total_tags_count,
        matched_collection_cards=len(matched_cards_global),
        total_collection_cards=len(collection_oids),
        claims_written=len(claims_to_insert),
        claims_per_role=claims_per_role,
        vocabulary_audit=vocab_audit,
    )


def format_import_report(stats: ImportStats, bulk_path: Path, sha256_hex: str) -> str:
    """Format counting protocol report for stdout."""
    v = stats.vocabulary_audit
    lines: list[str] = [
        "=== Scryfall Tagger Bulk Import Zählprotokoll ===",
        f"Quelldatei: {bulk_path.name}",
        f"SHA-256: {sha256_hex}",
        f"Gesamtzahl Tags im Bulk-Graph: {stats.total_bulk_tags}",
        "",
        "--- Negativnachweis Vokabular ---",
        f"Negativnachweis bestanden: {'JA (0 Treffer)' if v.negative_audit_passed else 'NEIN (Fehler!)'}",
    ]
    for term, count in v.negative_hits.items():
        lines.append(f"  - {term}: {count} Treffer im Vokabular")

    lines.extend(
        [
            "",
            "--- 24er-Taxonomie Abdeckung ---",
            f"Verfügbare Kategorien im Vokabular: {v.available_categories_count} / 24",
            f"Fehlende Kategorien (NOT_FOUND): {v.missing_categories_count} / 24",
            f"Karten der Sammlung im Store: {stats.total_collection_cards}",
            f"Sammlungskarten mit mindestens 1 Tagger-Claim: {stats.matched_collection_cards} / {stats.total_collection_cards}",
            f"Gesamtzahl erzeugter Role-Claims: {stats.claims_written}",
            "",
            "--- Zählungen je Kategorie (Sammlung) ---",
        ]
    )
    for role in sorted(stats.claims_per_role.keys()):
        count = stats.claims_per_role[role]
        lines.append(f"  {role:<18}: {count:>4} Karten")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import Scryfall Tagger bulk dataset into Studio as lossless role claims."
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=None,
        help="Path to Studio data folder holding studio.sqlite3 (defaults to COMMANDER_LAB_STUDIO_DATA).",
    )
    parser.add_argument(
        "--bulk",
        type=Path,
        default=None,
        help="Path to local oracle_tags bulk file (.jsonl or .jsonl.gz).",
    )
    parser.add_argument(
        "--download-to",
        type=Path,
        default=None,
        help="If --bulk is omitted, download bulk file to this path and import.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and count without mutating the database.",
    )
    args = parser.parse_args(argv)

    bulk_path = args.bulk
    snapshot_date: str | None = None

    if bulk_path is None:
        print("Discovering Scryfall oracle_tags bulk metadata...")
        meta = fetch_oracle_tags_bulk_metadata()
        uri = meta["download_uri"]
        snapshot_date = meta["updated_at"]
        print(f"Discovered: {uri} (snapshot: {snapshot_date})")
        target_dest = args.download_to or Path("/tmp") / Path(uri).name
        print(f"Downloading to {target_dest}...")
        bulk_path = download_file(uri, target_dest)

    file_sha = sha256_file(bulk_path)
    print(f"Bulk file: {bulk_path} (SHA-256: {file_sha})")

    store_dir = args.data or studio_data_dir()
    print(f"Opening Studio store at {store_dir}...")
    store = StudioStore.open(store_dir)

    try:
        stats = import_tagger_bulk_claims(
            store,
            bulk_path,
            snapshot_date=snapshot_date,
            dry_run=args.dry_run,
        )
    finally:
        store.close()

    print()
    print(format_import_report(stats, bulk_path, file_sha))
    return 0


if __name__ == "__main__":
    sys.exit(main())
