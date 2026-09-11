#!/usr/bin/env python3
"""Apply the adjudicated WS40 v1.0.3 stack-observer identity projection.

This patch is deliberately narrower than target resolution. It changes only the
normalization of Card targets already present on native Forge SpellAbility
objects. The runtime observer never receives or consults the requested target
value.

Authorized rule (see WS40_V1_0_3_IDENTITY_NORMALIZATION_ADJUDICATION.json):
  * Player and SpellAbility target projection remains unchanged.
  * A Card target must correspond to exactly one bound ObjSpec.
  * Preserve the current semantic_id by default.
  * Only when that ObjSpec's frozen card_lineage_id starts with `line:obj:` emit
    the suffix after `line:` as the stack-card target identity.
  * Ambiguous or unavailable native identity fails closed.

No attachment, combat, global semanticOf, legality, card-name, case-folding,
owner/controller, or requested-state behavior is changed here.
"""
from __future__ import annotations

import argparse
from pathlib import Path

MARKER = "WS40_V103_STACK_OBSERVER_IDENTITY_PROJECTION"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected exactly one patch target, got {n}")
    return text.replace(old, new, 1)


def patch(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"{path}: stack observer identity projection already applied")
        return

    old = '''    private static String stackTargetSemantic(Game game, GameObject target) {
        String key = null;
        if (target instanceof Player) key = playerId(game, (Player) target);
        else if (target instanceof SpellAbility) key = semanticOf((SpellAbility) target);
        else if (target instanceof Card) key = semanticOf((Card) target);
        if (key == null) {
            throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STACK_TARGET_IDENTITY_UNAVAILABLE:" + target);
        }
        return key;
    }'''

    new = '''    // WS40_V103_STACK_OBSERVER_IDENTITY_PROJECTION: stack-card normalization only.
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
    }

    private static String stackTargetSemantic(Game game, GameObject target) {
        String key = null;
        if (target instanceof Player) key = playerId(game, (Player) target);
        else if (target instanceof SpellAbility) key = semanticOf((SpellAbility) target);
        else if (target instanceof Card) key = stackCardTargetSemantic((Card) target);
        if (key == null) {
            throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STACK_TARGET_IDENTITY_UNAVAILABLE:" + target);
        }
        return key;
    }'''

    text = replace_once(text, old, new, "stack target observer")
    path.write_text(text, encoding="utf-8")
    print(f"{path}: applied {MARKER}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state-java", type=Path, required=True)
    args = ap.parse_args()
    patch(args.state_java)


if __name__ == "__main__":
    main()
