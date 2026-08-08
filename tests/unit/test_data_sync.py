from __future__ import annotations

from commander_lab.data_sync import audit_current_sources, sync_current_sources


def test_current_canonical_sources_match_prepared_imports(repo_root):
    result = audit_current_sources(repo_root)
    assert result["status"] == "MATCH"
    assert {row["source"] for row in result["checks"]} == {
        "inventory",
        "korvold_rogshai_decks",
        "opponent_baselines",
    }
    assert all(row["status"] == "MATCH" for row in result["checks"])
    assert result["mutated"] is False


def test_data_sync_dry_run_is_non_mutating_when_sources_match(repo_root):
    result = sync_current_sources(repo_root, dry_run=True)
    assert result["status"] == "MATCH"
    assert result["mutated"] is False
    assert all(row["action"] == "would_not_touch" for row in result["actions"])
