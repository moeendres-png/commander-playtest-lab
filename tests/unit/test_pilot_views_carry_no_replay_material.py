"""#662 SLOT-06 (c) R4: pilot-facing views never carry replay material.

The full-game replay export holds the Rules seed and every decklist, and the seed
fixes every library order, so it is orchestration-only. Pilots see only the
typed views in ``commander_lab.models.pilots``. Those views must have no field
through which the seed, the decision record, decklists of other players or the
replay digests could reach a pilot.
"""

from __future__ import annotations

import inspect

from pydantic import BaseModel

from commander_lab.models import pilots

FORBIDDEN_FIELD_PARTS = (
    "seed",
    "replay",
    "decisions_digest",
    "offered_digest",
    "chosen_keys",
    "final_state_digest",
    "mainboard",
    "decklist",
    "library_order",
)


def _view_models() -> list[type[BaseModel]]:
    return [
        obj
        for name, obj in inspect.getmembers(pilots, inspect.isclass)
        if issubclass(obj, BaseModel) and obj.__module__ == pilots.__name__ and "View" in name
    ]


def test_pilot_views_exist() -> None:
    names = {model.__name__ for model in _view_models()}
    assert "PilotStateView" in names
    assert "PilotActionView" in names


def test_no_pilot_view_field_can_carry_replay_material() -> None:
    offenders = [
        f"{model.__name__}.{field}"
        for model in _view_models()
        for field in model.model_fields
        if any(part in field.lower() for part in FORBIDDEN_FIELD_PARTS)
    ]
    assert offenders == []


def test_the_scan_flags_a_view_with_a_seed_field() -> None:
    """Red control: the field scan is not vacuous."""

    class LeakyView(BaseModel):
        rules_seed: int = 0

    assert any(part in "rules_seed" for part in FORBIDDEN_FIELD_PARTS)
    assert [
        field
        for field in LeakyView.model_fields
        if any(part in field.lower() for part in FORBIDDEN_FIELD_PARTS)
    ] == ["rules_seed"]
