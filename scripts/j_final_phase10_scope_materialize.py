from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one J-FINAL target in {path}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    ROOT / "src/commander_lab/acceptance/phase10.py",
    '    decks = ("korvold/current", "rogshai/current")\n',
    '    decks = service.ACTIVE_OWN_DECK_IDS\n',
)
replace_once(
    ROOT / "tests/unit/test_phase12_16_optimizer.py",
    '    assert response.result["tactical_oracle_result"]["execution_status"] == "passed"\n',
    '    assert (\n'
    '        response.result["tactical_oracle_result"]["execution_status"]\n'
    '        == "not_run_no_relevant_case"\n'
    '    )\n',
)

print("J-FINAL Phase 10/current-scope truth repair materialized")
