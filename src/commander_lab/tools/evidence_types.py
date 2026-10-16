"""Typed shapes of the evidence JSON files the tool service reads.

``json.loads`` of these files is cast to the shape at the reader boundary
(``read_optional_json_as``). Nothing here validates at
runtime; every key is optional because an absent or older file reads as ``{}``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict, cast


class CardRulesCoverageFile(TypedDict, total=False):
    """``data/rules/card_rules_coverage.json``."""

    external_engine_execution_status: str
    deck_statistics: dict[str, object]


class PilotProfileRow(TypedDict, total=False):
    pilot_id: str


class PoliticsRegimeRow(TypedDict, total=False):
    regime_id: str


class PilotPoliticsRegistryFile(TypedDict, total=False):
    """``data/robustness/pilot_and_politics_registry.json``."""

    pilot_profiles: list[PilotProfileRow]
    politics_regimes: list[PoliticsRegimeRow]


class Phase1213ResultFile(TypedDict, total=False):
    """``artifacts/phase12_13/PHASE12_13_RESULT.json``."""

    execution_status: str
    completion_status: str
    external_rules_engine_observations: int


class CanonicalDeckListsFile(TypedDict, total=False):
    """``data/canonical_import/2026-08-07/deck_lists.json`` (provenance keys only)."""

    source_file: str
    source_workbook: str
    source_drive_file_id: str
    source_drive_id: str


def read_optional_json_as[Shape](root: Path, relative: str, shape: type[Shape]) -> Shape:
    """Read ``root/relative`` as ``shape`` (a TypedDict); an absent file reads as ``{}``."""
    path = root / relative
    if not path.exists():
        return cast(Shape, {})
    return cast(Shape, json.loads(path.read_text(encoding="utf-8")))
