from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from commander_lab.models import CardRole, StructuralCardProfile


@dataclass(frozen=True)
class PlaystyleCardAssessment:
    oracle_name: str
    normal_turn_action_load: str
    repetitive_action_load: str
    trigger_bookkeeping_load: str
    loop_dependency: str
    game_object_bookkeeping: str
    decision_value_per_action: str
    playstyle_fit: str
    confidence: str
    signals: tuple[str, ...]
    evidence_class: str = "qualitative_structural_playstyle_estimate"
    boundary: str = (
        "Soft practicality/fun signal only; not a power score, archetype ban, or proof of actual "
        "turn duration. Complex decisive turns, engines, combos and sacrifice elements remain "
        "eligible."
    )

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class PlaystyleAnalyzer:
    """Qualitative bookkeeping/action-load signals from current Oracle text + structural roles."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        path = self.root / "data/canonical_import/2026-08-07/inventory_snapshot.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.inventory = {
            str(row["oracle_name"]): dict(row)
            for row in payload.get("cards", [])
            if row.get("oracle_name")
        }

    def analyze_card(self, card: StructuralCardProfile) -> PlaystyleCardAssessment:
        row = self.inventory.get(card.oracle_name, {})
        text = str(row.get("oracle_text", "") or "").casefold()
        signals: set[str] = set()

        trigger_count = text.count("whenever") + text.count("at the beginning")
        if trigger_count:
            signals.add("repeated_trigger_text")
        if "create" in text and "token" in text or CardRole.TOKEN_SOURCE in card.roles:
            signals.add("token_bookkeeping")
        if "sacrifice" in text or CardRole.SACRIFICE_OUTLET in card.roles:
            signals.add("sacrifice_actions")
        if any(token in text for token in ("put a counter", "+1/+1 counter", "counters on")):
            signals.add("counter_bookkeeping")
        if CardRole.ENGINE in card.roles:
            signals.add("engine_repetition_potential")
        explicit_loop = any(
            token in text
            for token in (
                "repeat this process",
                "you may repeat",
                "any number of times",
                "repeat this loop",
            )
        )
        if explicit_loop:
            signals.add("explicit_repeat_text")

        category_count = len(signals - {"engine_repetition_potential"})
        if explicit_loop or category_count >= 4:
            normal_load = "high_risk"
        elif category_count >= 2 or (trigger_count >= 2 and CardRole.ENGINE in card.roles):
            normal_load = "moderate_risk"
        else:
            normal_load = "low_or_not_detected"

        if explicit_loop:
            repetitive = "high_risk"
        elif len({"repeated_trigger_text", "token_bookkeeping", "sacrifice_actions"} & signals) >= 2:
            repetitive = "moderate_risk"
        else:
            repetitive = "low_or_not_detected"

        if trigger_count >= 2:
            trigger_load = "moderate_to_high_risk"
        elif trigger_count == 1:
            trigger_load = "some_bookkeeping"
        else:
            trigger_load = "not_detected"

        object_signals = len({"token_bookkeeping", "counter_bookkeeping"} & signals)
        game_objects = (
            "moderate_to_high_risk"
            if object_signals >= 2
            else ("some_bookkeeping" if object_signals == 1 else "not_detected")
        )
        loop_dependency = (
            "explicit_repeat_text_present" if explicit_loop else "not_detected_from_current_evidence"
        )
        playstyle_fit = (
            "caution"
            if "high_risk" in {normal_load, repetitive}
            else ("mixed" if "moderate_risk" in {normal_load, repetitive} else "compatible")
        )
        confidence = "medium" if explicit_loop or category_count >= 2 else "low"

        return PlaystyleCardAssessment(
            oracle_name=card.oracle_name,
            normal_turn_action_load=normal_load,
            repetitive_action_load=repetitive,
            trigger_bookkeeping_load=trigger_load,
            loop_dependency=loop_dependency,
            game_object_bookkeeping=game_objects,
            decision_value_per_action="not_quantified_from_current_evidence",
            playstyle_fit=playstyle_fit,
            confidence=confidence,
            signals=tuple(sorted(signals)),
        )

    def compare_cards(
        self,
        remove: StructuralCardProfile,
        add: StructuralCardProfile,
    ) -> dict[str, object]:
        return {
            "remove": self.analyze_card(remove).as_dict(),
            "add": self.analyze_card(add).as_dict(),
            "automatic_rejection": False,
            "preference_type": "soft_practicality_and_fun_preference",
        }


__all__ = ["PlaystyleAnalyzer", "PlaystyleCardAssessment"]
