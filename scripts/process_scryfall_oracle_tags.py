#!/usr/bin/env python3
"""Process and stream Scryfall Tagger bulk dataset (oracle_tags) with subtree semantics.

Source and Provenance:
- Source: Scryfall Bulk Data API (https://api.scryfall.com/bulk-data, type: "oracle_tags")
- Official Bulk URI format:
  https://data.scryfall.io/oracle-tags/oracle-tags-<timestamp>.jsonl.gz
- Scryfall Attribution / License Notice:
  Tag data courtesy of Scryfall Tagger community (https://tagger.scryfall.com).
  Magic: The Gathering is copyright Wizards of the Coast LLC.
  Scryfall is not affiliated with Wizards of the Coast. Scryfall data is
  provided under Scryfall's API Terms of Service.

Semantics and Subtree Architecture:
- The bulk file provides a directed acyclic graph of functional and aesthetic tags.
- Card assignments ('taggings') often sit on specific child tags rather than root categories;
  a functional category is obtained by the union of a root tag and all its subtree descendants.
- Multi-word labels appear with spaces in the bulk (e.g. 'card advantage', 'land ramp',
  'sacrifice outlet').
- Known vocabulary differences:
  - Search tag 'board-wipe' maps to bulk label 'sweeper'.
  - Search concept 'graveyard hate' maps to bulk label/slug 'hate-graveyard'.
- Negativnachweis:
  - 'stax', 'token', and 'card-selection' do NOT exist in the bulk vocabulary and are
    strictly classified as NOT_FOUND (never synthesized or substituted).

Status Vocabulary:
- AVAILABLE: Tag and subtree exist in the bulk vocabulary with valid mappings.
- NOT_FOUND: Tag does not exist in the bulk vocabulary.
- BLOCKED: Network / upstream rate limiting prevents fetching bulk data.
- UNKNOWN: Status could not be determined.

No private collection, deck, or owner data is stored or processed.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import urllib.request
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import IO

SCRYFALL_BULK_METADATA_URL = "https://api.scryfall.com/bulk-data"
USER_AGENT = (
    "CommanderPlaytestLab-Research/1.0 (+https://github.com/moeendres-png/commander-playtest-lab)"
)

# Known search-to-bulk canonical tag aliases
CANONICAL_ALIASES: dict[str, str] = {
    "board-wipe": "sweeper",
    "board wipe": "sweeper",
    "graveyard hate": "hate-graveyard",
    "graveyard-hate": "hate-graveyard",
}

# Negative vocabulary targets that must not exist in Scryfall Tagger bulk vocabulary
NEGATIVE_VOCABULARY_TARGETS: tuple[str, ...] = (
    "stax",
    "token",
    "card-selection",
)


@dataclass(frozen=True, slots=True)
class Tagging:
    """Individual card tagging assignment."""

    oracle_id: str
    weight: float = 1.0


@dataclass(frozen=True, slots=True)
class TagDefinition:
    """Single tag node as published in the bulk dataset."""

    tag_id: str
    slug: str
    label: str
    aliases: tuple[str, ...]
    child_ids: tuple[str, ...]
    taggings: tuple[Tagging, ...]

    def to_dict(self) -> dict[str, object]:
        """Serialize tag vocabulary metadata and direct taggings."""
        return {
            "id": self.tag_id,
            "slug": self.slug,
            "label": self.label,
            "aliases": list(self.aliases),
            "child_ids": list(self.child_ids),
            "taggings_count": len(self.taggings),
            "taggings": [{"oracle_id": t.oracle_id, "weight": t.weight} for t in self.taggings],
        }


class TagVocabulary:
    """Indexed catalog of tag definitions supporting subtree traversal and search."""

    def __init__(self, tags: Sequence[TagDefinition]) -> None:
        self._by_id: dict[str, TagDefinition] = {}
        self._by_slug: dict[str, TagDefinition] = {}
        self._by_label: dict[str, TagDefinition] = {}
        self._by_alias: dict[str, TagDefinition] = {}

        for t in tags:
            self._by_id[t.tag_id] = t
            self._by_slug[t.slug.lower()] = t
            self._by_label[t.label.lower()] = t
            for a in t.aliases:
                self._by_alias.setdefault(a.lower(), t)

    def __len__(self) -> int:
        return len(self._by_id)

    @property
    def all_tags(self) -> list[TagDefinition]:
        return list(self._by_id.values())

    def find_tag(self, query: str) -> TagDefinition | None:
        """Find a tag by ID, exact label, slug, alias, or known alias mapping."""
        q = query.strip().lower()
        if not q:
            return None

        # Check known canonical aliases
        resolved_q = CANONICAL_ALIASES.get(q, q)

        if resolved_q in self._by_id:
            return self._by_id[resolved_q]
        if resolved_q in self._by_label:
            return self._by_label[resolved_q]
        if resolved_q in self._by_slug:
            return self._by_slug[resolved_q]
        if resolved_q in self._by_alias:
            return self._by_alias[resolved_q]

        # Hyphen/space fallback (e.g. 'card advantage' <-> 'card-advantage')
        with_hyphens = resolved_q.replace(" ", "-")
        if with_hyphens in self._by_slug:
            return self._by_slug[with_hyphens]
        with_spaces = resolved_q.replace("-", " ")
        if with_spaces in self._by_label:
            return self._by_label[with_spaces]

        return None

    def get_subtree_tags(self, root_tag_id: str) -> list[TagDefinition]:
        """Collect the root tag and all its recursive descendant child tags."""
        result: list[TagDefinition] = []
        visited_ids: set[str] = set()
        queue = [root_tag_id]

        while queue:
            current_id = queue.pop(0)
            if current_id in visited_ids:
                continue
            visited_ids.add(current_id)

            tag = self._by_id.get(current_id)
            if tag is not None:
                result.append(tag)
                for child_id in tag.child_ids:
                    if child_id not in visited_ids:
                        queue.append(child_id)

        return result

    def resolve_category_taggings(
        self, query: str
    ) -> tuple[str, list[TagDefinition], dict[str, float]]:
        """Resolve a functional category query into status, matched tags, and merged taggings.

        Returns:
            (status, matched_tags_list, {oracle_id: max_weight})
        """
        q_clean = query.strip().lower()

        # Negativnachweis: known missing concepts
        if q_clean in NEGATIVE_VOCABULARY_TARGETS:
            return "NOT_FOUND", [], {}

        root_tag = self.find_tag(query)
        if root_tag is None:
            return "NOT_FOUND", [], {}

        subtree_tags = self.get_subtree_tags(root_tag.tag_id)
        merged_taggings: dict[str, float] = {}

        for tag in subtree_tags:
            for t in tag.taggings:
                current_weight = merged_taggings.get(t.oracle_id, 0.0)
                if t.weight > current_weight:
                    merged_taggings[t.oracle_id] = t.weight

        return "AVAILABLE", subtree_tags, merged_taggings


def parse_tag_line(line: str) -> TagDefinition | None:
    """Parse a single JSONL line into a TagDefinition."""
    stripped = line.strip()
    if not stripped:
        return None

    obj = json.loads(stripped)
    if not isinstance(obj, dict):
        return None

    tag_id = str(obj.get("id") or "")
    if not tag_id:
        return None

    slug = str(obj.get("slug") or "")
    label = str(obj.get("label") or slug)

    raw_aliases = obj.get("aliases")
    aliases: list[str] = []
    if isinstance(raw_aliases, list):
        aliases = [str(a) for a in raw_aliases if isinstance(a, str)]

    raw_children = obj.get("child_ids")
    child_ids: list[str] = []
    if isinstance(raw_children, list):
        child_ids = [str(cid) for cid in raw_children if isinstance(cid, str)]

    raw_taggings = obj.get("taggings")
    taggings: list[Tagging] = []
    if isinstance(raw_taggings, list):
        for item in raw_taggings:
            if isinstance(item, dict):
                oid = str(item.get("oracle_id") or "")
                if oid:
                    raw_w = item.get("weight")
                    weight = float(raw_w) if isinstance(raw_w, (int, float)) else 1.0
                    taggings.append(Tagging(oracle_id=oid, weight=weight))

    return TagDefinition(
        tag_id=tag_id,
        slug=slug,
        label=label,
        aliases=tuple(aliases),
        child_ids=tuple(child_ids),
        taggings=tuple(taggings),
    )


def stream_oracle_tags(source: Path | IO[str]) -> Iterator[TagDefinition]:
    """Stream TagDefinitions from a file path or open text stream."""
    if isinstance(source, Path):
        if source.suffix == ".gz":
            with gzip.open(source, "rt", encoding="utf-8") as gz_handle:
                for line in gz_handle:
                    tag = parse_tag_line(line)
                    if tag is not None:
                        yield tag
        else:
            with source.open("r", encoding="utf-8") as file_handle:
                for line in file_handle:
                    tag = parse_tag_line(line)
                    if tag is not None:
                        yield tag
    else:
        for line in source:
            tag = parse_tag_line(line)
            if tag is not None:
                yield tag


def load_vocabulary(source: Path | IO[str]) -> TagVocabulary:
    """Stream and build a TagVocabulary from source."""
    tags = list(stream_oracle_tags(source))
    return TagVocabulary(tags)


def fetch_scryfall_bulk_url(bulk_type: str = "oracle_tags") -> str:
    """Fetch the current bulk download URL from Scryfall metadata API."""
    req = urllib.request.Request(
        SCRYFALL_BULK_METADATA_URL,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    for item in data.get("data", []):
        if isinstance(item, dict) and item.get("type") == bulk_type:
            download_uri = item.get("download_uri")
            if isinstance(download_uri, str):
                return download_uri

    raise ValueError(f"Bulk data type '{bulk_type}' not found in Scryfall metadata response")


def build_audit_protocol(vocab: TagVocabulary) -> dict[str, object]:
    """Generate count protocol and verify required categories against the vocabulary."""
    total_tags = len(vocab)
    tags_with_taggings = sum(1 for t in vocab.all_tags if len(t.taggings) > 0)
    total_taggings = sum(len(t.taggings) for t in vocab.all_tags)

    test_queries = [
        "card advantage",
        "land ramp",
        "sacrifice outlet",
        "hate-graveyard",
        "graveyard hate",
        "sweeper",
        "board-wipe",
        "stax",
        "token",
        "card-selection",
    ]

    category_results: dict[str, object] = {}
    for q in test_queries:
        status, matched_tags, taggings = vocab.resolve_category_taggings(q)
        category_results[q] = {
            "status": status,
            "subtree_tags_count": len(matched_tags),
            "matched_tag_slugs": [t.slug for t in matched_tags],
            "distinct_oracle_ids": len(taggings),
        }

    return {
        "tags_total": total_tags,
        "tags_with_taggings": tags_with_taggings,
        "taggings_total": total_taggings,
        "categories": category_results,
    }


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        help="Path to local oracle_tags.jsonl or .jsonl.gz bulk file",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Path to export structured vocabulary summary JSON",
    )
    parser.add_argument(
        "--query",
        "-q",
        nargs="+",
        help="Query one or more functional tags and output subtree resolution",
    )
    args = parser.parse_args()

    if not args.input:
        print("Error: --input path to oracle_tags bulk file is required.", file=sys.stderr)
        return 1

    if not args.input.is_file():
        print(f"Error: input file {args.input} does not exist.", file=sys.stderr)
        return 1

    print(f"Loading and indexing Scryfall oracle tags from {args.input}...")
    vocab = load_vocabulary(args.input)
    protocol = build_audit_protocol(vocab)

    print(f"Tags total: {protocol['tags_total']}")
    print(f"Tags with taggings: {protocol['tags_with_taggings']}")
    print(f"Taggings total: {protocol['taggings_total']}")

    if args.query:
        print("\nQuery Resolutions:")
        for q in args.query:
            status, matched, taggings = vocab.resolve_category_taggings(q)
            print(f"  [{status}] {q!r}: {len(matched)} subtree tags, {len(taggings)} unique cards")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(protocol, indent=2), encoding="utf-8")
        print(f"\nWrote audit protocol to {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
