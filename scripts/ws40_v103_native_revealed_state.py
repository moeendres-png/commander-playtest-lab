#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f"{label}: expected 1 occurrence, got {n}")
    return text.replace(old, new, 1)


def patch_state_java(path: Path) -> None:
    s = path.read_text(encoding="utf-8")

    s = once(
        s,
        "import forge.game.card.Card;\n",
        "import forge.game.card.Card;\nimport forge.game.card.CardCollection;\nimport forge.game.card.CardCopyService;\n",
        "native reveal card imports",
    )

    s = once(
        s,
        '            case "library" -> ZoneType.Library;\n',
        '            case "library" -> ZoneType.Library;\n            case "revealed" -> ZoneType.Library; // Forge reveal is a transient visibility state over Library.\n',
        "revealed physical zone mapping",
    )

    s = once(
        s,
        '                    if (s.controller == seat && zone.equals(s.zone)) specs.add(s);\n',
        '                    String physicalZone = "revealed".equals(s.zone) ? "library" : s.zone;\n                    if (s.controller == seat && zone.equals(physicalZone)) specs.add(s);\n',
        "revealed library materialization",
    )

    s = once(
        s,
        '            if (s.zonePosition != null && "library".equals(s.zone)) {\n',
        '            if (s.zonePosition != null && ("library".equals(s.zone) || "revealed".equals(s.zone))) {\n',
        "revealed zone-position binding",
    )

    marker = "    private static void applyCombat(Game game) {\n"
    helper = '''    private static boolean rememberedAsRevealed(Card source, Card card) {\n        if (source == null || card == null || card.getZone() == null || !card.getZone().is(ZoneType.Library)) return false;\n        for (Object remembered : source.getRemembered()) {\n            if (remembered instanceof Card && ((Card) remembered).getId() == card.getId()) return true;\n        }\n        return false;\n    }\n\n    private static boolean isNativelyRevealed(Card card) {\n        if (card == null || card.getZone() == null || !card.getZone().is(ZoneType.Library)) return false;\n        for (SpellAbility sa : stackAbilities.values()) {\n            if (sa.hasParam("RememberRevealed") && rememberedAsRevealed(sa.getHostCard(), card)) return true;\n        }\n        return false;\n    }\n\n    private static void applyRevealedState(Game game) {\n        List<ObjSpec> revealedSpecs = new ArrayList<>();\n        for (ObjSpec s : objectSpecs) if ("revealed".equals(s.zone)) revealedSpecs.add(s);\n        if (revealedSpecs.isEmpty()) return;\n        revealedSpecs.sort(Comparator.comparingInt(s -> s.zonePosition == null ? Integer.MAX_VALUE : s.zonePosition));\n\n        List<SpellAbility> revealSources = new ArrayList<>();\n        for (SpellAbility sa : stackAbilities.values()) {\n            if (sa.hasParam("RememberRevealed")) revealSources.add(sa);\n        }\n        if (revealSources.size() != 1) {\n            throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_REVEALED_NATIVE_SOURCE_COUNT:" + revealSources.size());\n        }\n        SpellAbility revealSa = revealSources.get(0);\n        Card source = revealSa.getHostCard();\n        if (!source.getRemembered().isEmpty()) {\n            throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_REVEALED_SOURCE_PREPOPULATED");\n        }\n\n        ObjSpec first = revealedSpecs.get(0);\n        Player libraryPlayer = player(game, first.controller);\n        if (revealSa.getActivatingPlayer() != libraryPlayer) {\n            throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_REVEALED_ACTOR_MISMATCH");\n        }\n\n        CardCollection revealedCards = new CardCollection();\n        for (ObjSpec s : revealedSpecs) {\n            if (s.owner != first.owner || s.controller != first.controller || s.zonePosition == null) {\n                throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_REVEALED_UNSUPPORTED_SHAPE:" + s.semanticId);\n            }\n            Card c = semanticCards.get(s.semanticId);\n            if (c == null || c.getZone() == null || !c.getZone().is(ZoneType.Library)) {\n                throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_REVEALED_NOT_IN_LIBRARY:" + s.semanticId);\n            }\n            int nativePosition = libraryPlayer.getCardsIn(ZoneType.Library, false).indexOf(c);\n            if (nativePosition != s.zonePosition) {\n                throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_REVEALED_POSITION_MISMATCH:" + s.semanticId + ":" + nativePosition);\n            }\n            revealedCards.add(c);\n        }\n\n        // Recreate the exact native Fact-or-Fiction transient state: the cards remain in Library,\n        // Forge publishes the reveal, and the spell source remembers LKI copies for TwoPiles.\n        game.getAction().reveal(revealedCards, ZoneType.Library, libraryPlayer, false, "WS40 restored native reveal");\n        Map<Integer, Card> cachedMap = new HashMap<>();\n        for (Card c : revealedCards) source.addRemembered(CardCopyService.getLKICopy(c, cachedMap));\n\n        for (ObjSpec s : revealedSpecs) {\n            Card c = semanticCards.get(s.semanticId);\n            if (!isNativelyRevealed(c)) {\n                throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_REVEALED_NATIVE_OBSERVATION_MISSING:" + s.semanticId);\n            }\n        }\n    }\n\n'''
    s = once(s, marker, helper + marker, "native revealed-state helper insertion")

    s = once(
        s,
        "        applyStack(game);\n        applyCombat(game);\n",
        "        applyStack(game);\n        applyRevealedState(game);\n        applyCombat(game);\n",
        "native revealed-state application",
    )

    s = once(
        s,
        '        String attached = c.getEntityAttachedTo() instanceof Card ? semanticOf((Card)c.getEntityAttachedTo()) : null;\n        Integer zonePosition = null;\n',
        '        String attached = c.getEntityAttachedTo() instanceof Card ? semanticOf((Card)c.getEntityAttachedTo()) : null;\n        boolean nativeRevealed = isNativelyRevealed(c);\n        Integer zonePosition = null;\n',
        "native revealed observation computation",
    )

    s = once(
        s,
        '            + ",\\\"zone_position\\\":" + (zonePosition == null ? "null" : zonePosition)\n            + ",\\\"sick\\\":" + c.isSick() + "}";\n',
        '            + ",\\\"zone_position\\\":" + (zonePosition == null ? "null" : zonePosition)\n            + ",\\\"native_revealed\\\":" + nativeRevealed\n            + ",\\\"sick\\\":" + c.isSick() + "}";\n',
        "native revealed observation field",
    )

    path.write_text(s, encoding="utf-8")


def patch_runner(path: Path) -> None:
    s = path.read_text(encoding="utf-8")
    s = once(
        s,
        '        for k in ("card_identity", "owner", "controller", "zone", "tapped", "face_down"):\n            row[k] = got[k]\n',
        '        for k in ("card_identity", "owner", "controller", "tapped", "face_down"):\n            row[k] = got[k]\n        # "revealed" is provider-neutral transient state. Forge proves it as a Library card\n        # remembered by a native RememberRevealed stack source; never echo the requested zone.\n        row["zone"] = "revealed" if got.get("native_revealed") is True else got["zone"]\n',
        "native revealed normalization",
    )
    path.write_text(s, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state-java", type=Path)
    ap.add_argument("--runner", type=Path)
    args = ap.parse_args()
    if bool(args.state_java) == bool(args.runner):
        raise SystemExit("pass exactly one of --state-java or --runner")
    if args.state_java:
        patch_state_java(args.state_java)
        print("WS40_V103_NATIVE_REVEALED_STATE_JAVA_PATCH=PASS")
    else:
        patch_runner(args.runner)
        print("WS40_V103_NATIVE_REVEALED_STATE_RUNNER_PATCH=PASS")


if __name__ == "__main__":
    main()
