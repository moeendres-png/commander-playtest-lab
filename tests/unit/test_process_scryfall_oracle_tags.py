"""Unit tests for Scryfall oracle_tags bulk processor and subtree semantics.

Governing requirements:
- Stream Scryfall oracle_tags bulk JSONL line by line.
- Subtree semantics: assignments sit on child tags; category is the union of root and all descendants.
- Multi-word labels appear with spaces in the bulk (e.g. 'card advantage', 'land ramp', 'sacrifice outlet').
- Known vocabulary differences:
  - Search tag 'board-wipe' maps to bulk label 'sweeper'.
  - Search concept 'graveyard hate' maps to bulk label/slug 'hate-graveyard'.
- Negativnachweis:
  - 'stax', 'token', and 'card-selection' do NOT exist in the bulk vocabulary and are NOT_FOUND.

References:
    GitHub Issue #1233: Scryfall-Oracle-Tags-Bulk aufbereiten (Subtree-Semantik)
"""

from __future__ import annotations

import gzip
from pathlib import Path

from scripts.process_scryfall_oracle_tags import (
    build_audit_protocol,
    load_vocabulary,
    stream_oracle_tags,
)

FIXTURE_PATH = Path("tests/fixtures/scryfall/oracle_tags_sample.jsonl")


def test_stream_oracle_tags_and_vocabulary() -> None:
    """Validate loading and indexing from the JSONL fixture."""
    assert FIXTURE_PATH.is_file(), f"Missing fixture at {FIXTURE_PATH}"

    tags = list(stream_oracle_tags(FIXTURE_PATH))
    assert len(tags) == 8

    vocab = load_vocabulary(FIXTURE_PATH)
    assert len(vocab) == 8

    # Check a specific tag node
    ramp_tag = vocab.find_tag("land ramp")
    assert ramp_tag is not None
    assert ramp_tag.slug == "land-ramp"
    assert ramp_tag.label == "land ramp"
    assert "ramp-land" in ramp_tag.aliases
    assert len(ramp_tag.taggings) == 1
    assert ramp_tag.taggings[0].oracle_id == "00000000-0000-0000-0000-000000000004"


def test_subtree_semantics_and_card_advantage() -> None:
    """Validate that taggings on child tags roll up to the parent category."""
    vocab = load_vocabulary(FIXTURE_PATH)

    status, matched_tags, taggings = vocab.resolve_category_taggings("card advantage")
    assert status == "AVAILABLE"
    # Root + draw + impulse-draw = 3 subtree tags
    assert len(matched_tags) == 3
    matched_slugs = {t.slug for t in matched_tags}
    assert matched_slugs == {"card-advantage", "draw", "impulse-draw"}

    # 3 unique cards: oid-1, oid-2 (shared across both children), oid-3
    assert len(taggings) == 3
    assert "00000000-0000-0000-0000-000000000001" in taggings
    assert "00000000-0000-0000-0000-000000000002" in taggings
    assert "00000000-0000-0000-0000-000000000003" in taggings

    # oid-2 appeared in draw (weight 1.0) and impulse (weight 0.8) -> max weight 1.0
    assert taggings["00000000-0000-0000-0000-000000000002"] == 1.0


def test_multiword_labels_with_spaces() -> None:
    """Validate multi-word labels with spaces and hyphenated slug fallback."""
    vocab = load_vocabulary(FIXTURE_PATH)

    for label in ["card advantage", "land ramp", "sacrifice outlet"]:
        tag = vocab.find_tag(label)
        assert tag is not None, f"Tag {label} not found by space-separated label"
        assert tag.label == label

        # Also findable by slug
        slug = label.replace(" ", "-")
        tag_by_slug = vocab.find_tag(slug)
        assert tag_by_slug is not None
        assert tag_by_slug.tag_id == tag.tag_id


def test_canonical_mappings() -> None:
    """Validate board-wipe -> sweeper and graveyard hate -> hate-graveyard mappings."""
    vocab = load_vocabulary(FIXTURE_PATH)

    # 1. board-wipe -> sweeper
    status, matched_tags, taggings = vocab.resolve_category_taggings("board-wipe")
    assert status == "AVAILABLE"
    assert any(t.slug == "sweeper" for t in matched_tags)
    assert any(t.slug == "wrath" for t in matched_tags)
    assert "00000000-0000-0000-0000-000000000007" in taggings

    # 2. graveyard hate -> hate-graveyard
    status_gy, matched_gy, taggings_gy = vocab.resolve_category_taggings("graveyard hate")
    assert status_gy == "AVAILABLE"
    assert any(t.slug == "hate-graveyard" for t in matched_gy)
    assert "00000000-0000-0000-0000-000000000006" in taggings_gy


def test_negative_vocabulary_not_found() -> None:
    """Validate that stax, token, and card-selection strictly return NOT_FOUND."""
    vocab = load_vocabulary(FIXTURE_PATH)

    for target in ["stax", "token", "card-selection"]:
        status, matched_tags, taggings = vocab.resolve_category_taggings(target)
        assert status == "NOT_FOUND", f"Expected NOT_FOUND for {target}, got {status}"
        assert len(matched_tags) == 0
        assert len(taggings) == 0

    # Unknown random tag
    status_unknown, _, _ = vocab.resolve_category_taggings("random-nonexistent-concept")
    assert status_unknown == "NOT_FOUND"


def test_build_audit_protocol() -> None:
    """Validate generation of the count and category protocol."""
    vocab = load_vocabulary(FIXTURE_PATH)
    protocol = build_audit_protocol(vocab)

    assert protocol["tags_total"] == 8
    assert protocol["tags_with_taggings"] == 6
    assert protocol["taggings_total"] == 8

    categories = protocol["categories"]
    assert isinstance(categories, dict)
    assert categories["card advantage"]["status"] == "AVAILABLE"
    assert categories["card advantage"]["distinct_oracle_ids"] == 3
    assert categories["board-wipe"]["status"] == "AVAILABLE"
    assert categories["stax"]["status"] == "NOT_FOUND"
    assert categories["token"]["status"] == "NOT_FOUND"
    assert categories["card-selection"]["status"] == "NOT_FOUND"


def test_gzip_streaming(tmp_path: Path) -> None:
    """Validate transparent streaming of gzipped .jsonl.gz files."""
    gz_path = tmp_path / "tags.jsonl.gz"
    content = FIXTURE_PATH.read_bytes()
    with gzip.open(gz_path, "wb") as gz_out:
        gz_out.write(content)

    vocab = load_vocabulary(gz_path)
    assert len(vocab) == 8
    status, _, taggings = vocab.resolve_category_taggings("land ramp")
    assert status == "AVAILABLE"
    assert len(taggings) == 1
