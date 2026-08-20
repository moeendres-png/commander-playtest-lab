from __future__ import annotations

import dataclasses
import inspect
import json
from pathlib import Path

from commander_lab.engine.structural import (
    StructuralDeckProfile,
    StructuralMatchConfig,
    StructuralMatchResult,
    StructuralSimulator,
)
from commander_lab.robustness import load_project_structural_decks, run_structural_policy_tournament
from commander_lab.whole_deck.lab import WholeDeckDesignLab


def sig(obj):
    try:
        return str(inspect.signature(obj))
    except Exception as exc:
        return f"<signature-error:{type(exc).__name__}:{exc}>"


def methods(cls):
    out = {}
    for name in dir(cls):
        if name.startswith("_"):
            continue
        obj = getattr(cls, name)
        if callable(obj):
            out[name] = sig(obj)
    return out


def fields(cls):
    if not dataclasses.is_dataclass(cls):
        return {"dataclass": False, "signature": sig(cls)}
    return {
        f.name: {
            "type": str(f.type),
            "default": None if f.default is dataclasses.MISSING else repr(f.default),
            "factory": None if f.default_factory is dataclasses.MISSING else repr(f.default_factory),
        }
        for f in dataclasses.fields(cls)
    }


def main() -> None:
    root = Path.cwd()
    decks = load_project_structural_decks(root)
    lab = WholeDeckDesignLab(root)
    context = getattr(lab, "context", None)
    baseline = decks.get("rogshai/current")
    payload = {
        "evidence_guard": {"holdout_accessed": False, "purpose": "surface_probe_only"},
        "structural_simulator": {"signature": sig(StructuralSimulator), "methods": methods(StructuralSimulator)},
        "structural_match_config": fields(StructuralMatchConfig),
        "structural_match_result": fields(StructuralMatchResult),
        "structural_deck_profile": fields(StructuralDeckProfile),
        "baseline_profile": dataclasses.asdict(baseline) if baseline is not None and dataclasses.is_dataclass(baseline) else repr(baseline),
        "run_structural_policy_tournament": sig(run_structural_policy_tournament),
        "whole_deck_design_lab": {
            "signature": sig(WholeDeckDesignLab),
            "methods": methods(WholeDeckDesignLab),
            "context_type": type(context).__name__ if context is not None else None,
            "context_methods": methods(type(context)) if context is not None else {},
            "context_attrs": sorted(vars(context)) if context is not None else [],
        },
        "structural_deck_ids": sorted(decks),
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
