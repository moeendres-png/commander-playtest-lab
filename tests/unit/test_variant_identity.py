from commander_lab.variant_identity import build_variant_identity, deduplicate_exact_variants


def test_exact_variant_identity_deduplicates_only_exact_deck_state() -> None:
    first = build_variant_identity(
        baseline_deck_hash="a" * 64,
        variant_deck_hash="b" * 64,
        context_snapshot_hash="c" * 64,
        deck_diff=(("Cut", "Add"),),
        functional_replacement_groups=("draw",),
    )
    duplicate = build_variant_identity(
        baseline_deck_hash="a" * 64,
        variant_deck_hash="b" * 64,
        context_snapshot_hash="c" * 64,
        deck_diff=(("Different label", "Same materialized deck"),),
        functional_replacement_groups=("draw",),
    )
    related_but_distinct = build_variant_identity(
        baseline_deck_hash="a" * 64,
        variant_deck_hash="d" * 64,
        context_snapshot_hash="c" * 64,
        deck_diff=(("Cut", "Other Add"),),
        functional_replacement_groups=("draw",),
    )

    unique, duplicates = deduplicate_exact_variants((first, duplicate, related_but_distinct))

    assert unique == (first, related_but_distinct)
    assert duplicates == {duplicate.identity_hash: first.identity_hash}
    assert first.functional_family_hash == related_but_distinct.functional_family_hash
