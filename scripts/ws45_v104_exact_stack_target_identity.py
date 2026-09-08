#!/usr/bin/env python3
"""Supersede the WS40 v1.0.3 lineage-alias stack-target projection for WS45 v1.0.4.

WS44 v1.0.4 repaired dangling target identities to exact record-local semantic
identities.  The native Forge stack observer must therefore emit the unique
semantic_id bound to the final live Card object, not a card_lineage_id suffix.

This patch runs only after ws40_v103_stack_observer_identity_projection.py.
It does not read requested targets, perform card-name/zone heuristics, or alter
Forge legality.  Zero or multiple native Card -> ObjSpec bindings fail closed.
"""
from __future__ import annotations

import argparse
from pathlib import Path

MARKER = "WS45_V104_EXACT_STACK_TARGET_IDENTITY"

OLD = '''    // WS40_V103_STACK_OBSERVER_IDENTITY_PROJECTION: stack-card normalization only.
    // The projection is derived solely from the native Card -> bound ObjSpec relation and
    // frozen provider-neutral lineage metadata. Requested target values are not consulted.
    private static String stackCardTargetSemantic(Card card) {
        String current = semanticOf(card);
        if (current == null) {
            throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STACK_CARD_SEMANTIC_IDENTITY_UNAVAILABLE:" + card);
        }

        ObjSpec bound = null;
        for (ObjSpec spec : objectSpecs) {
            Card candidate = semanticCards.get(spec.semanticId);
            if (candidate != card) continue;
            if (bound != null && !bound.semanticId.equals(spec.semanticId)) {
                throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STACK_CARD_OBSERVER_IDENTITY_AMBIGUOUS:" + current);
            }
            bound = spec;
        }
        if (bound == null) {
            throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STACK_CARD_OBJSPEC_UNAVAILABLE:" + current);
        }

        if (bound.cardLineageId != null && bound.cardLineageId.startsWith("line:obj:")) {
            return bound.cardLineageId.substring("line:".length());
        }
        return current;
    }'''

NEW = '''    // WS45_V104_EXACT_STACK_TARGET_IDENTITY: WS44 v1.0.4 requires the exact
    // record-local semantic identity bound to the final live native Card.  The historical
    // v1.0.3 lineage suffix is provenance only and must not replace that exact binding.
    // Requested stack targets are never consulted here.
    private static String stackCardTargetSemantic(Card card) {
        String current = semanticOf(card);
        if (current == null) {
            throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_V104_STACK_CARD_SEMANTIC_IDENTITY_UNAVAILABLE:" + card);
        }

        ObjSpec bound = null;
        for (ObjSpec spec : objectSpecs) {
            Card candidate = semanticCards.get(spec.semanticId);
            if (candidate != card) continue;
            if (bound != null && !bound.semanticId.equals(spec.semanticId)) {
                throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_V104_STACK_CARD_OBSERVER_IDENTITY_AMBIGUOUS:" + current);
            }
            bound = spec;
        }
        if (bound == null) {
            throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_V104_STACK_CARD_OBJSPEC_UNAVAILABLE:" + current);
        }
        if (!bound.semanticId.equals(current)) {
            throw new Ws23ForgeVerticalProvider.ControlledStop(
                    "WS45_V104_STACK_CARD_SEMANTIC_BINDING_MISMATCH:" + current + ":" + bound.semanticId);
        }
        return bound.semanticId;
    }'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state-java", type=Path, required=True)
    args = ap.parse_args()
    text = args.state_java.read_text(encoding="utf-8")
    if MARKER in text:
        print("WS45_V104_EXACT_STACK_TARGET_IDENTITY=ALREADY_APPLIED")
        return 0
    n = text.count(OLD)
    if n != 1:
        raise SystemExit(f"WS45 v1.0.4 stack target identity patch target count {n}, expected 1")
    args.state_java.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("WS45_V104_EXACT_STACK_TARGET_IDENTITY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
