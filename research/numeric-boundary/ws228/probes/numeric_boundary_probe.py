"""WS228 research-only probe: numeric-domain narrowing reproduction (F-RULES-02).

Drives the LOCKED production code (ExternalPilotDecisionPolicy._decide_numeric
via decide()) without modifying it. A recording pilot wrapper captures the exact
set of numeric PilotActionViews offered to the pilot for each decision class and
each [min, max] bound pair.

Classification of this probe's output: SYNTHETIC research probe proving Lab
transformation semantics (which integers reach the pilot). It does NOT prove
actual-card behavior; live full-game runs remain UNKNOWN until S6.

Run:  python3 research/numeric-boundary/ws228/probes/numeric_boundary_probe.py
      python3 -m pytest research/numeric-boundary/ws228/probes/ -q  (if pytest available)
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from commander_lab.agents import GenericCommanderPilot  # noqa: E402
from commander_lab.engine.rules.full_game import (  # noqa: E402
    ExternalPilotDecisionPolicy,
    FullGamePilotBinding,
    _RuntimePilot,
)
from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength  # noqa: E402

OUT_PATH = Path(__file__).resolve().parent.parent / "LIVE_PROBE_RESULTS.json"


class RecordingPilot(GenericCommanderPilot):
    """Wraps the production pilot; records offered action ids, delegates choice."""

    def __init__(self, config: PilotConfig) -> None:
        super().__init__(config)
        self.offered: list[list[str]] = []

    def choose_action(self, state, actions: Iterable, rng: random.Random):  # type: ignore[override]
        offered = [a.action_id for a in actions]
        self.offered.append(offered)
        return super().choose_action(state, actions, rng)


def _policy(recorder: RecordingPilot) -> ExternalPilotDecisionPolicy:
    runtimes: list[_RuntimePilot] = []
    for seat in range(1, 5):
        config = PilotConfig(
            pilot_name="auto",
            strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
            mode=PilotDecisionMode.DETERMINISTIC,
        )
        binding = FullGamePilotBinding(
            seat=seat,
            deck_id=f"fixture-{seat}",
            strategy="generic",
            commander_names=("Isamaru, Hound of Konda",),
            config=config,
            pilot_identity="RecordingPilot",
            pilot_version="0.0.0-research",
            decision_policy_version="xmage-full-game-policy-1.0.0",
        )
        runtimes.append(
            _RuntimePilot(binding=binding, pilot=recorder if seat == 1 else GenericCommanderPilot(config))
        )
    return ExternalPilotDecisionPolicy(tuple(runtimes), 20260915)  # type: ignore[arg-type]


def _state() -> dict[str, Any]:
    actor = {
        "player_id": "actor",
        "seat": 0,
        "life": 40,
        "hand_count": 7,
        "library_count": 92,
        "graveyard_count": 0,
        "battlefield": [],
        "graveyard": [],
        "command": [{"object_id": "commander", "name": "Isamaru, Hound of Konda"}],
        "hand": [{"object_id": f"hand-{i}", "name": "Plains"} for i in range(7)],
        "mana_pool": {"white": 1, "blue": 0, "black": 0, "red": 0, "green": 0, "colorless": 0},
    }
    opponents = [
        {
            "player_id": f"opponent-{seat}",
            "seat": seat,
            "life": 40,
            "hand_count": 7,
            "library_count": 92,
            "graveyard_count": 0,
            "battlefield": [],
            "graveyard": [],
            "command": [],
        }
        for seat in range(1, 4)
    ]
    return {
        "game_id": "engine-opaque",
        "actor_id": "actor",
        "seat": 0,
        "turn_number": 1,
        "active_player_id": "actor",
        "priority_player_id": "actor",
        "phase": "precombat_main",
        "step": None,
        "players": [actor, *opponents],
        "stack": [],
    }


def _option(option_id: str, option_type: str, label: str, **metadata: Any) -> dict[str, Any]:
    return {"option_id": option_id, "option_type": option_type, "label": label, "metadata": metadata}


def _request(
    decision_class: str,
    options: list[dict[str, Any]],
    *,
    minimum: int,
    maximum: int,
    context: dict[str, Any] | None = None,
    offset: int = 1,
) -> dict[str, Any]:
    return {
        "decision_id": f"ws228-probe-{decision_class}",
        "decision_offset": offset,
        "actor_id": "actor",
        "decision_class": decision_class,
        "pilot_state": _state(),
        "context": context or {},
        "minimum_selections": minimum,
        "maximum_selections": maximum,
        "legal_options": options,
        "prompt": decision_class,
    }


def run_case(decision_class: str, minimum: int, maximum: int) -> dict[str, Any]:
    recorder = RecordingPilot(
        PilotConfig(
            pilot_name="auto",
            strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
            mode=PilotDecisionMode.DETERMINISTIC,
        )
    )
    policy = _policy(recorder)
    if decision_class == "target_amount":
        options = [_option("actor", "target_amount", "Full Game Seat 1")]
        context: dict[str, Any] = {"outcome": "benefit", "numeric_min": minimum, "numeric_max": maximum}
        req = _request(decision_class, options, minimum=1, maximum=1, context=context)
    else:
        context = {"outcome": "benefit", "numeric_min": minimum, "numeric_max": maximum}
        req = _request(decision_class, [], minimum=0, maximum=0, context=context)
    response = policy.decide(req)
    offered_ids = recorder.offered[-1] if recorder.offered else []
    offered_values = sorted(int(v.split(":", 1)[1]) for v in offered_ids)
    span = maximum - minimum
    # Never materialize million-element expectation lists into evidence:
    # verify endpoints + sampling for huge spans, exact lists for small ones.
    if span <= 1000:
        authorized_count = span + 1
        missing_count = (span + 1) - len(offered_values)
        missing_sample = [v for v in range(minimum, maximum + 1) if v not in set(offered_values)][:10]
    else:
        authorized_count = span + 1
        offered_set = set(offered_values)
        # midpoint + endpoints must be present; interior absent by construction
        # of the narrowed set: prove by probing interior witnesses instead.
        witnesses = [minimum + 1, minimum + span // 4, minimum + span // 2 + 1, maximum - 1]
        missing_sample = [w for w in witnesses if w not in offered_set]
        missing_count = authorized_count - len(offered_values)
    return {
        "decision_class": decision_class,
        "numeric_min": minimum,
        "numeric_max": maximum,
        "span": span,
        "authorized_count": authorized_count,
        "offered_values": offered_values,
        "offered_count": len(offered_values),
        "missing_sample": missing_sample,
        "missing_count": missing_count,
        "narrowed": missing_count > 0,
        "submitted_numeric_choice": response.get("numeric_choice"),
    }


def main() -> int:
    classes = ["announce_x", "amount", "multi_amount", "target_amount"]
    bound_pairs = [
        (0, 0),    # degenerate single value
        (0, 5),    # small domain
        (1, 5),    # small domain, nonzero min
        (0, 16),   # boundary: span == 16 -> full exposure expected
        (0, 17),   # boundary: span == 17 -> narrowing expected
        (0, 100),  # large domain (X-spell-like)
        (1, 40),   # life-total-like span
        (0, 1000000),  # pathological span (offered set must stay tiny today)
    ]
    cases = [run_case(cls, lo, hi) for cls in classes for (lo, hi) in bound_pairs]
    verdicts = {
        "small_domain_full": all(
            not c["narrowed"] for c in cases if c["span"] <= 16
        ),
        "boundary_16_full": all(
            not c["narrowed"] for c in cases if c["span"] == 16
        ),
        "boundary_17_narrowed": all(
            c["narrowed"] for c in cases if c["span"] == 17
        ),
        "large_domain_narrowed": all(
            c["narrowed"] for c in cases if c["span"] > 16
        ),
        "large_domain_offered_is_min_mid_max": all(
            c["offered_values"]
            == sorted({c["numeric_min"], c["numeric_min"] + (c["numeric_max"] - c["numeric_min"]) // 2, c["numeric_max"]})
            for c in cases
            if c["span"] > 16 and c["span"] < 1000000
        ),
    }
    payload = {
        "probe": "ws228-numeric-boundary",
        "codebase_head_note": "locked WS223 audit base; production code unmodified",
        "evidence_class": "SYNTHETIC research probe of Lab transformation semantics",
        "cases": cases,
        "verdicts": verdicts,
        "f_rules_02_reproduced": bool(
            verdicts["small_domain_full"]
            and verdicts["boundary_16_full"]
            and verdicts["boundary_17_narrowed"]
            and verdicts["large_domain_narrowed"]
            and verdicts["large_domain_offered_is_min_mid_max"]
        ),
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({"verdicts": verdicts, "f_rules_02_reproduced": payload["f_rules_02_reproduced"]}, indent=2))
    for c in cases:
        if c["span"] in (16, 17) or c["numeric_max"] in (5, 100):
            print(
                f'{c["decision_class"]:13s} [{c["numeric_min"]},{c["numeric_max"]}] '
                f'span={c["span"]:3d} offered={c["offered_count"]:3d} '
                f'missing={c["missing_count"]:3d} submitted={c["submitted_numeric_choice"]}'
            )
    return 0 if payload["f_rules_02_reproduced"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
