from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VARIANT_DIR = ROOT / "data" / "decks" / "pretest_variants"


def test_superseded_pretest_variant_tree_is_absent() -> None:
    assert not VARIANT_DIR.exists()


def test_only_current_rogshai_deck_files_remain() -> None:
    deck_dir = ROOT / "data" / "decks"
    assert (deck_dir / "rogshai_current.txt").is_file()
    assert (deck_dir / "rogshai_current.json").is_file()
    assert not (deck_dir / "korvold_current.txt").exists()
    assert not (deck_dir / "korvold_current.json").exists()
