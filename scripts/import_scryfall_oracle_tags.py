#!/usr/bin/env python3
"""Import Scryfall Tagger bulk dataset into Commander Studio via studio-roles-2.

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
- Employs strict alias separation: aliases never overwrite canonical slugs or labels.
- Truly audits negative vocabulary targets ('stax', 'token', 'card-selection').
- Generates a standard 'studio-roles-2' role snapshot file for the 17 canonical Studio roles.
- Resolves target Oracle IDs across all store sources: collection (card), corpus (corpus_deck_card),
  and Scryfall database (scryfall_card).
- Imports via standard `commander_lab.studio.roles.import_roles`, sharing transactions,
  origin ranking, and `--replace-scope` snapshot management.

No private collection, deck, or owner data is stored or exposed.
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import sys
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from commander_lab.studio.roles import (
    FULL_SNAPSHOT,
    ORIGIN_TAGGER,
    ROLES,
    ROLES_SCHEMA,
    SEARCH_ALIASES,
    import_roles,
    read_role_file,
)
from commander_lab.studio.store import (
    StudioStore,
    now_utc,
    studio_data_dir,
)

logger = logging.getLogger(__name__)

SCRYFALL_BULK_METADATA_URL = "https://api.scryfall.com/bulk-data"
USER_AGENT = "CommanderPlaytestLab/1.0 (+https://github.com/moeendres-png/commander-playtest-lab)"
DEFAULT_SCOPE_KEY = "ALL_CARDS"

# Negative vocabulary targets that must not exist in Scryfall Tagger bulk vocabulary
NEGATIVE_VOCABULARY_TARGETS: tuple[str, ...] = ("stax", "token", "card-selection")


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
    node_id_by_alias: dict[str, str] = field(default_factory=dict)
    total_tags_count: int = 0
    parse_errors_count: int = 0

    def add_node(self, node: TagNode) -> None:
        self.nodes_by_id[node.tag_id] = node
        if node.slug:
            self.node_id_by_slug[node.slug.lower()] = node.tag_id
        if node.label:
            self.node_id_by_label[node.label.lower()] = node.tag_id
        for alias in node.aliases:
            clean = alias.strip().lower()
            if clean:
                self.node_id_by_alias.setdefault(clean, node.tag_id)
        self.total_tags_count += 1

    def find_tag_id(self, identifier: str) -> str | None:
        """Find tag ID checking slug first, then label, then aliases."""
        clean = identifier.strip().lower()
        return (
            self.node_id_by_slug.get(clean)
            or self.node_id_by_label.get(clean)
            or self.node_id_by_alias.get(clean)
        )

    def get_descendant_oracle_ids(self, target_identifier: str) -> tuple[frozenset[str], str]:
        """Collect all oracle_ids for a tag including its child hierarchy.

        Returns (frozenset of oracle_ids, mapping_rule).
        """
        canonical_slug = SEARCH_ALIASES.get(target_identifier.lower(), target_identifier.lower())
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
        valid_children_count = 0

        while queue:
            curr_id = queue.pop(0)
            if curr_id in visited:
                continue
            visited.add(curr_id)
            node = self.nodes_by_id.get(curr_id)
            if not node:
                continue
            if curr_id != root_id:
                valid_children_count += 1
            gathered.update(node.oracle_ids)
            for child_id in node.child_ids:
                if child_id in self.nodes_by_id and child_id not in visited:
                    queue.append(child_id)

        if valid_children_count > 0:
            rule = f"{rule} + hierarchy ({valid_children_count} children)"

        return frozenset(gathered), rule


@dataclass(frozen=True)
class VocabularyAudit:
    total_tags: int
    negative_hits: dict[str, int]
    negative_audit_passed: bool
    roles_found: dict[str, bool]
    available_roles_count: int
    missing_roles_count: int


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


def iter_bulk_lines(file_path: Path) -> Iterator[str]:
    """Stream lines from a JSONL or JSONL.gz file."""
    if file_path.suffix == ".gz":
        with gzip.open(file_path, "rt", encoding="utf-8", errors="replace") as f:
            for line in f:
                yield line
    else:
        with file_path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                yield line


def load_bulk_graph(bulk_path: Path) -> BulkGraph:
    """Stream bulk file and build in-memory tag hierarchy graph."""
    if not bulk_path.is_file():
        raise FileNotFoundError(f"Bulk file not found: {bulk_path}")

    graph = BulkGraph()
    for idx, line in enumerate(iter_bulk_lines(bulk_path), start=1):
        clean_line = line.strip()
        if not clean_line:
            continue
        try:
            node = parse_tag_line(clean_line, idx)
            graph.add_node(node)
        except ValueError as err:
            graph.parse_errors_count += 1
            logger.warning("Parse error at %s line #%d: %s", bulk_path.name, idx, err)
    return graph


def audit_vocabulary(graph: BulkGraph) -> VocabularyAudit:
    """Audit bulk graph for negative targets and presence of canonical roles."""
    neg_hits: dict[str, int] = {}
    for target in NEGATIVE_VOCABULARY_TARGETS:
        tid = graph.find_tag_id(target)
        if tid is not None:
            node = graph.nodes_by_id[tid]
            neg_hits[target] = len(node.oracle_ids) or 1
        else:
            neg_hits[target] = 0

    all_neg_zero = all(count == 0 for count in neg_hits.values())

    role_found: dict[str, bool] = {}
    for role, slug in ROLES.items():
        canonical = SEARCH_ALIASES.get(slug, slug)
        role_found[role] = graph.find_tag_id(canonical) is not None

    avail_count = sum(1 for f in role_found.values() if f)
    missing_count = sum(1 for f in role_found.values() if not f)

    return VocabularyAudit(
        total_tags=graph.total_tags_count,
        negative_hits=neg_hits,
        negative_audit_passed=all_neg_zero,
        roles_found=role_found,
        available_roles_count=avail_count,
        missing_roles_count=missing_count,
    )


def fetch_oracle_tags_bulk_metadata(timeout: float = 30.0) -> dict[str, str]:
    """Discover official download URI and timestamp from Scryfall bulk-data API."""
    req = urllib.request.Request(
        SCRYFALL_BULK_METADATA_URL,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
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


def download_file(url: str, dest: Path, timeout: float = 30.0) -> Path:
    """Download a file with chunked streaming via a .part temporary file."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    dest.parent.mkdir(parents=True, exist_ok=True)
    part_dest = dest.with_name(dest.name + ".part")
    with urllib.request.urlopen(req, timeout=timeout) as resp, part_dest.open("wb") as out_f:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status} downloading {url}")
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            out_f.write(chunk)
    part_dest.replace(dest)
    return dest


def resolve_all_store_oracle_ids(store: StudioStore) -> set[str]:
    """Return all unique oracle_ids known in the store (collection, corpus, and scryfall)."""
    with store.connection as db:
        rows = db.execute(
            """
            SELECT oracle_id FROM card WHERE oracle_id IS NOT NULL AND oracle_id != ''
            UNION
            SELECT oracle_id FROM corpus_deck_card WHERE oracle_id IS NOT NULL AND oracle_id != ''
            UNION
            SELECT oracle_id FROM scryfall_card WHERE oracle_id IS NOT NULL AND oracle_id != ''
            """
        ).fetchall()
    return {str(row[0]).strip().lower() for row in rows if row[0]}


def build_studio_roles_payload(
    graph: BulkGraph,
    *,
    target_oracle_ids: set[str] | None = None,
    fetched_at: str | None = None,
    scope_key: str = DEFAULT_SCOPE_KEY,
) -> dict[str, object]:
    """Generate a standard studio-roles-2 dictionary for the 17 Studio roles."""
    roles_output: dict[str, list[str]] = {}
    for role_name, primary_slug in ROLES.items():
        oids, _rule = graph.get_descendant_oracle_ids(primary_slug)
        filtered = oids & target_oracle_ids if target_oracle_ids is not None else oids
        roles_output[role_name] = sorted(filtered)

    payload: dict[str, object] = {
        "schema": ROLES_SCHEMA,
        "source": "Scryfall tagger (otag), public bulk data (oracle-tags)",
        "role_origin": ORIGIN_TAGGER,
        "fetched_at": fetched_at or now_utc(),
        "scope": {
            "mode": FULL_SNAPSHOT,
            "key": scope_key,
            "completeness": "COMPLETE_FOR_SCOPE",
        },
        "tags": dict(ROLES),
        "tag_aliases": {
            tag: SEARCH_ALIASES[tag] for tag in ROLES.values() if tag in SEARCH_ALIASES
        },
        "roles": roles_output,
    }
    return payload


def export_studio_roles_file(
    graph: BulkGraph,
    out_path: Path,
    *,
    target_oracle_ids: set[str] | None = None,
    fetched_at: str | None = None,
    scope_key: str = DEFAULT_SCOPE_KEY,
) -> Path:
    """Generate and write a validated studio-roles-2 JSON file."""
    payload = build_studio_roles_payload(
        graph,
        target_oracle_ids=target_oracle_ids,
        fetched_at=fetched_at,
        scope_key=scope_key,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    # Validate structure using standard Studio roles reader
    read_role_file(out_path)
    return out_path


def import_tagger_bulk(
    store: StudioStore,
    bulk_path: Path,
    *,
    out_roles_path: Path | None = None,
    allow_scope_replace: bool = False,
    scope_key: str = DEFAULT_SCOPE_KEY,
    snapshot_date: str | None = None,
) -> dict[str, object]:
    """Process bulk file, create studio-roles-2 file, and import via roles.import_roles."""
    graph = load_bulk_graph(bulk_path)
    vocab_audit = audit_vocabulary(graph)

    target_oids = resolve_all_store_oracle_ids(store)

    effective_roles_path = (
        out_roles_path
        if out_roles_path is not None
        else bulk_path.parent / "scryfall_tagger_roles_snapshot.json"
    )

    export_studio_roles_file(
        graph,
        effective_roles_path,
        target_oracle_ids=target_oids,
        fetched_at=snapshot_date,
        scope_key=scope_key,
    )

    # Import through standard roles subsystem
    import_result = import_roles(
        store, effective_roles_path, allow_scope_replace=allow_scope_replace
    )

    return {
        "roles_file": str(effective_roles_path),
        "vocabulary_audit": {
            "total_tags": vocab_audit.total_tags,
            "negative_audit_passed": vocab_audit.negative_audit_passed,
            "available_roles_count": vocab_audit.available_roles_count,
            "missing_roles_count": vocab_audit.missing_roles_count,
        },
        "target_oracle_ids_count": len(target_oids),
        "import_result": import_result,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bulk-file", help="Path to local oracle_tags JSONL/JSONL.gz file")
    parser.add_argument("--download", action="store_true", help="Download latest bulk dataset")
    parser.add_argument(
        "--download-dir",
        default=".cache/scryfall",
        help="Directory to store downloaded bulk files",
    )
    parser.add_argument("--out-roles", help="Path to write generated studio-roles-2 JSON snapshot")
    parser.add_argument(
        "--scope-key",
        default=DEFAULT_SCOPE_KEY,
        help="Scope key for role snapshot (default: ALL_CARDS)",
    )
    parser.add_argument(
        "--replace-scope",
        action="store_true",
        help="Allow full snapshot to replace existing claims for this scope",
    )
    parser.add_argument("--store", help="Path to Studio SQLite directory or file")
    parser.add_argument("--audit-only", action="store_true", help="Only audit vocabulary and exit")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    bulk_path: Path
    snapshot_date: str | None = None

    if args.download or not args.bulk_file:
        logger.info("Fetching Scryfall oracle_tags bulk metadata...")
        meta = fetch_oracle_tags_bulk_metadata()
        download_url = meta["download_uri"]
        snapshot_date = meta["updated_at"]
        dest_filename = Path(download_url).name
        dest_dir = Path(args.download_dir)
        bulk_path = dest_dir / dest_filename

        if not bulk_path.exists():
            logger.info("Downloading %s to %s...", download_url, bulk_path)
            download_file(download_url, bulk_path)
        else:
            logger.info("Found cached bulk file at %s", bulk_path)
    else:
        bulk_path = Path(args.bulk_file)
        if not bulk_path.exists():
            logger.error("Bulk file %s does not exist", bulk_path)
            return 1

    if args.audit_only:
        logger.info("Loading bulk graph from %s...", bulk_path)
        graph = load_bulk_graph(bulk_path)
        audit = audit_vocabulary(graph)
        logger.info("Vocabulary Audit: %s", audit)
        if not audit.negative_audit_passed:
            logger.error("Negative vocabulary audit failed: %s", audit.negative_hits)
            return 2
        logger.info("Negative vocabulary audit PASS: all targets confirmed absent.")
        return 0

    store_path = Path(args.store).resolve() if args.store else studio_data_dir()
    store = StudioStore.open(store_path)
    try:
        out_roles = Path(args.out_roles) if args.out_roles else None
        res = import_tagger_bulk(
            store,
            bulk_path,
            out_roles_path=out_roles,
            allow_scope_replace=args.replace_scope,
            scope_key=args.scope_key,
            snapshot_date=snapshot_date,
        )
        logger.info("Import completed successfully: %s", json.dumps(res, indent=2))
    finally:
        store.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
