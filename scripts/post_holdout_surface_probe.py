from __future__ import annotations

import inspect
import json
from pathlib import Path

from commander_lab.engine.structural import StructuralSimulator
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


def main() -> None:
    root = Path.cwd()
    decks = load_project_structural_decks(root)
    lab = WholeDeckDesignLab(root)
    context = getattr(lab, "context", None)
    payload = {
        "evidence_guard": {
            "holdout_accessed": False,
            "purpose": "surface_probe_only",
        },
        "structural_simulator": {
            "signature": sig(StructuralSimulator),
            "methods": methods(StructuralSimulator),
        },
        "run_structural_policy_tournament": sig(run_structural_policy_tournament),
        "whole_deck_design_lab": {
            "signature": sig(WholeDeckDesignLab),
            "methods": methods(WholeDeckDesignLab),
            "context_type": type(context).__name__ if context is not None else None,
            "context_methods": methods(type(context)) if context is not None else {},
        },
        "structural_deck_ids": sorted(decks),
        "structural_deck_types": {key: type(value).__name__ for key, value in sorted(decks.items())},
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
