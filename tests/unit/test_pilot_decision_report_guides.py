"""The --guides arm of scripts/pilot_decision_report.py: guided seats get weights, others keep theirs.

No JVM, no games are played; only the seat bindings of the real pod are built and compared.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from commander_lab.agents.deck_guides import find_guide, guided_weights

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "pilot_decision_report.py"
spec = importlib.util.spec_from_file_location("pilot_decision_report_guides", SCRIPT)
assert spec and spec.loader
pdr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pdr)


def _real_pod() -> tuple[object, object, tuple[object, ...]]:
    ((_, paths),) = pdr.bench._pods(False)
    return pdr.bench._setup(paths)


def test_a_seat_with_a_guide_takes_its_deltas_and_the_others_keep_their_weights() -> None:
    _, _, plain = _real_pod()
    _, _, guided = pdr._guided(_real_pod())
    assert len(plain) == len(guided) > 0
    changed = 0
    for before, after in zip(plain, guided, strict=True):
        guide = find_guide(before.deck_id, before.commander_names)
        if guide is None:
            assert after.config == before.config, before.deck_id
            continue
        changed += 1
        assert after.config.weights == guided_weights(guide, before.config.strength)
        assert after.deck_id == before.deck_id
    assert changed > 0, "no seat of the real pod has a guide"


def test_the_plain_arm_is_not_touched_by_building_the_guided_one() -> None:
    _, _, before = _real_pod()
    pdr._guided(_real_pod())
    _, _, again = _real_pod()
    assert [b.config for b in before] == [b.config for b in again]
