#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"WS45 overlay expected exactly one {label}, found {count}")
    return text.replace(old, new, 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--generated-dir", type=Path, required=True)
    ap.add_argument("--strict-source", type=Path, required=True)
    args = ap.parse_args()

    state = args.generated_dir / "Ws40SuccessorState.java"
    provider = args.generated_dir / "Ws23ForgeVerticalProvider.java"
    strict = args.generated_dir / "Ws45StrictObservation.java"
    source = state.read_text(encoding="utf-8")

    old = '''    private static void bindNonStackObjects(Game game) {
        semanticCards.clear();
        commanderCards.clear();
        Set<Card> used = new HashSet<>();
        for (ObjSpec s : objectSpecs) {
            if ("stack".equals(s.zone)) continue;
            List<Card> candidates = new ArrayList<>();
            for (Card c : new ArrayList<>(player(game, s.controller).getCardsIn(zoneType(s.zone), false))) {
                if (sameCard(c, s, used)) candidates.add(c);
            }
            if (s.zonePosition != null && ("library".equals(s.zone) || "revealed".equals(s.zone))) {
                Card at = player(game, s.controller).getCardsIn(ZoneType.Library, false).get(s.zonePosition);
                candidates.clear();
                if (sameCard(at, s, used)) candidates.add(at);
            }
            if (candidates.isEmpty()) {
                throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_BIND_MISSING:" + s.semanticId);
            }
            // Equal physical cards are intentionally indistinguishable to Forge. Semantic identity is a
            // provider-neutral mapping layer only; choose the first still-unbound card in native zone order.
            Card c = candidates.get(0);
            used.add(c);
            semanticCards.put(s.semanticId, c);
            if (!s.commanderId.isEmpty()) commanderCards.put(s.commanderId, c);
        }
    }'''
    new = '''    private static void bindNonStackObjects(Game game) {
        semanticCards.clear();
        commanderCards.clear();
        for (int i = 0; i < objectSpecs.size(); i++) {
            ObjSpec s = objectSpecs.get(i);
            if ("stack".equals(s.zone)) continue;
            int expectedNativeId = 1000 + i;
            Card c = game.findById(expectedNativeId);
            if (c == null) {
                throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_STATE_BIND_NATIVE_ID_MISSING:" + s.semanticId + ":" + expectedNativeId);
            }
            Set<Card> noneUsed = java.util.Collections.emptySet();
            if (!sameCard(c, s, noneUsed)) {
                throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_STATE_BIND_NATIVE_ID_STATE_MISMATCH:" + s.semanticId + ":" + expectedNativeId);
            }
            if (s.zonePosition != null && ("library".equals(s.zone) || "revealed".equals(s.zone))) {
                Card at = player(game, s.controller).getCardsIn(ZoneType.Library, false).get(s.zonePosition);
                if (at != c) {
                    throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_STATE_BIND_NATIVE_ID_LIBRARY_POSITION_MISMATCH:" + s.semanticId);
                }
            }
            semanticCards.put(s.semanticId, c);
            if (!s.commanderId.isEmpty()) commanderCards.put(s.commanderId, c);
        }
    }'''
    source = replace_once(source, old, new, "deterministic native card binding block")

    old = '''        applyRevealedState(game);
        applyCombat(game);
        String finalPriority = env("COMMANDER_LAB_WS40_PRIORITY_SEAT");'''
    new = '''        applyRevealedState(game);
        applyCombat(game);
        Ws45StrictObservation.afterNativeStateLoad(game, semanticCards, commanderCards);
        String finalPriority = env("COMMANDER_LAB_WS40_PRIORITY_SEAT");'''
    source = replace_once(source, old, new, "strict observation install")

    marker = '''    private static String combatJson(Game game) {'''
    helper = '''    private static String eligibleBlockersJson(Game game) {
        Combat combat = game.getCombat();
        if (combat == null) return "[]";
        List<String> ids = new ArrayList<>();
        Player active = game.getPhaseHandler().getPlayerTurn();
        for (Player defender : game.getPlayers()) {
            if (defender == active) continue;
            for (Card blocker : defender.getCreaturesInPlay()) {
                boolean legal = false;
                for (Card attacker : combat.getAttackers()) {
                    if (CombatUtil.canBlock(attacker, blocker, combat)) { legal = true; break; }
                }
                if (!legal) continue;
                String sid = semanticOf(blocker);
                if (sid == null) throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_COMBAT_NATIVE_ELIGIBLE_BLOCKER_IDENTITY_UNAVAILABLE:" + blocker);
                ids.add(sid);
            }
        }
        ids.sort(String::compareTo);
        StringBuilder b = new StringBuilder("[");
        for (int i = 0; i < ids.size(); i++) { if (i > 0) b.append(','); b.append(Ws23ForgeVerticalProvider.esc(ids.get(i))); }
        return b.append(']').toString();
    }

'''
    if source.count(marker) != 1:
        raise SystemExit("WS45 overlay combatJson marker mismatch")
    source = source.replace(marker, helper + marker, 1)
    old = '''        return "{\\"attackers\\":" + a + ",\\"blockers\\":" + bl
            + ",\\"eligible_attackers\\":" + eligibleAttackersJson(game) + "}";'''
    new = '''        return "{\\"attackers\\":" + a + ",\\"blockers\\":" + bl
            + ",\\"eligible_attackers\\":" + eligibleAttackersJson(game)
            + ",\\"eligible_blockers\\":" + eligibleBlockersJson(game) + "}";'''
    source = replace_once(source, old, new, "native eligible blockers combat projection")

    old = '''        String ws40BoundConfig = boundConfigJson();
        String raw = "{\\"natural_registration\\":" + natural
            + ",\\"provider_entry_mode\\":\\"NATIVE_STATE_LOAD\\""'''
    new = '''        String raw = "{\\"natural_registration\\":" + natural
            + ",\\"provider_entry_mode\\":\\"NATIVE_STATE_LOAD\\""'''
    source = replace_once(source, old, new, "bound config local in native snapshot")
    old = '''            + ",\\"rules_commander\\":" + game.getRules().hasAppliedVariant(forge.game.GameType.Commander)
            + ",\\"rules_seed_configured\\":" + Ws23ForgeVerticalProvider.esc(env("COMMANDER_LAB_FORGE_RULES_SEED"))
            + ",\\"bound_config\\":" + ws40BoundConfig
            + ",\\"config_binding_digest\\":" + Ws23ForgeVerticalProvider.esc(sha256(ws40BoundConfig)) + "}";'''
    new = '''            + ",\\"rules_commander\\":" + game.getRules().hasAppliedVariant(forge.game.GameType.Commander)
            + ",\\"ws45_observation\\":" + Ws45StrictObservation.json(game, semanticCards, commanderCards) + "}";'''
    source = replace_once(source, old, new, "bound config output in native snapshot")

    start = source.find('    public static void emitNaturalRegistration(Game game, Ws23ForgeVerticalProvider.Broker broker) {')
    end = source.find('    private static String counterJson(Card c) {', start)
    if start < 0 or end < 0:
        raise SystemExit("WS45 overlay could not locate historical emitNaturalRegistration")
    source = source[:start] + '''    public static void emitNaturalRegistration(Game game, Ws23ForgeVerticalProvider.Broker broker) {
        throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_FORBIDDEN_REGISTRATION_ONLY_NATURAL_PATH");
    }

''' + source[end:]
    state.write_text(source, encoding="utf-8")

    p = provider.read_text(encoding="utf-8")
    old = '''        @Override
        public boolean mulliganKeepHand(Player player, int cardsToReturn) {
            return broker.chooseBoolean("mulliganKeepHand", this.player, "KEEP", "MULLIGAN");
        }'''
    new = '''        @Override
        public boolean mulliganKeepHand(Player player, int cardsToReturn) {
            boolean keep = broker.chooseBoolean("mulliganKeepHand", this.player, "KEEP", "MULLIGAN");
            Ws45StrictObservation.recordMulliganDecision(player.getGame(), player, cardsToReturn, keep);
            return keep;
        }'''
    p = replace_once(p, old, new, "mulligan trace callback")
    old = '''            String ws40EntryMode = System.getenv("COMMANDER_LAB_WS40_ENTRY_MODE");
            String ws40ConstructionOnly = System.getenv("COMMANDER_LAB_WS40_CONSTRUCTION_ONLY");
            if ("1".equals(ws40ConstructionOnly) && "NATURAL_GAME_START".equals(ws40EntryMode)) {
                Ws40SuccessorState.emitNaturalRegistration(game, broker);
            } else if ("NATIVE_STATE_LOAD".equals(ws40EntryMode)) {
                match.startGame(game, () -> Ws40SuccessorState.applyNativeState(game, broker));
            } else {
                match.startGame(game);
            }'''
    new = '''            String ws40EntryMode = System.getenv("COMMANDER_LAB_WS40_ENTRY_MODE");
            String ws40ConstructionOnly = System.getenv("COMMANDER_LAB_WS40_CONSTRUCTION_ONLY");
            Ws45StrictObservation.installRulesRandomnessBeforeGameStart();
            if ("1".equals(ws40ConstructionOnly) && "NATURAL_GAME_START".equals(ws40EntryMode)) {
                Ws45StrictObservation.prepareNatural(game);
                match.startGame(game, () -> Ws45StrictObservation.emitNaturalLifecycle(game, broker));
            } else if ("NATIVE_STATE_LOAD".equals(ws40EntryMode)) {
                match.startGame(game, () -> Ws40SuccessorState.applyNativeState(game, broker));
            } else {
                match.startGame(game);
            }'''
    p = replace_once(p, old, new, "runSession lifecycle block")
    provider.write_text(p, encoding="utf-8")
    strict.write_text(args.strict_source.read_text(encoding="utf-8"), encoding="utf-8")

    active = state.read_text(encoding="utf-8") + provider.read_text(encoding="utf-8") + strict.read_text(encoding="utf-8")
    forbidden = [
        "candidates.get(0)",
        "RestoredQualificationHistory",
        "COMMANDER_LAB_WS45_KNOWLEDGE_CANONICAL_B64",
        '\\"bound_config\\":',
    ]
    bad = [item for item in forbidden if item in active]
    if bad:
        raise SystemExit("WS45 overlay forbidden active patterns: " + repr(bad))
    print("WS45 generated overlay applied: deterministic native IDs + typed/native observations + natural lifecycle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
