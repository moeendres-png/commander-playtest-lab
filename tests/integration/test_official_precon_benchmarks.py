from __future__ import annotations

from pathlib import Path

from commander_lab.repositories.opponents import CurrentOpponentRepository

ROOT = Path(__file__).resolve().parents[2]

EXPECTED_IDS = {
    "opponent/scions-spellcraft-precon",
    "opponent/counter-intelligence-precon",
    "opponent/turtle-power-precon",
    "opponent/silverquill-influence-precon",
    "opponent/fantastic-four-precon",
    "opponent/avengers-assemble-precon",
    "opponent/doom-prevails-precon",
}
# Current opponents that are unchanged official precons with an exact packaged list; Blight
# Curse also carries an observed commander preference, so it is not a pure benchmark.
EXACT_LIST_IDS = EXPECTED_IDS | {
    "opponent/blight-curse-precon",
    "opponent/dance-elements-precon",
    "opponent/wakanda-forever-precon",
}


def test_benchmarks_are_official_precon_evidence_only() -> None:
    records = {record.deck_id: record for record in CurrentOpponentRepository(ROOT).records()}

    for deck_id in EXPECTED_IDS:
        assert tuple(kind.value for kind in records[deck_id].evidence_kinds) == ("official_precon",)
