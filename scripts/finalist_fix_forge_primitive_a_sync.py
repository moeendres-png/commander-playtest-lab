#!/usr/bin/env python3
"""Close concrete Forge Primitive-A qualification adapter gaps.

Qualification-only post-overlay patch. Pinned Forge source remains unmodified.
The patch keeps every discretionary choice external/fail-closed and treats native
resolution only as a transaction-boundary signal; the Python runner independently
checks the final Bolt zone, P2 life, and native cast/resolution events before PASS.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label} anchor mismatch: expected 1, observed {count}")
    return text.replace(old, new, 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", type=Path, required=True)
    args = parser.parse_args()

    path = args.provider
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '''        PaperCard finalistBoltCard = new PaperCard(finalistBoltRules, "M11", forge.card.CardRarity.Common);
        PaperCard finalistBearsCard = new PaperCard(finalistBearsRules, "10E", forge.card.CardRarity.Common);
        forge.StaticData.instance().getCommonCards().addCard(finalistBoltCard);
        forge.StaticData.instance().getCommonCards().addCard(finalistBearsCard);''',
        '''        PaperCard finalistMountainCard = new PaperCard(finalistMountainRules, "10E", forge.card.CardRarity.BasicLand);
        PaperCard finalistBoltCard = new PaperCard(finalistBoltRules, "M11", forge.card.CardRarity.Common);
        PaperCard finalistBearsCard = new PaperCard(finalistBearsRules, "10E", forge.card.CardRarity.Common);
        forge.StaticData.instance().getCommonCards().addCard(finalistMountainCard);
        forge.StaticData.instance().getCommonCards().addCard(finalistBoltCard);
        forge.StaticData.instance().getCommonCards().addCard(finalistBearsCard);''',
        "Primitive-A Mountain common-card registration",
    )

    text = replace_once(
        text,
        '''        @Override
        public SpellAbility getAbilityToPlay(Card hostCard, List<SpellAbility> abilities, ITriggerEvent triggerEvent) {
            throw failClosed("getAbilityToPlay");
        }''',
        '''        @Override
        public SpellAbility getAbilityToPlay(Card hostCard, List<SpellAbility> abilities, ITriggerEvent triggerEvent) {
            if (abilities == null || abilities.isEmpty()) {
                broker.recordAutomatic("getAbilityToPlay:NO_NATIVE_OPTIONS:" + hostCard.getName());
                return null;
            }
            if (abilities.size() == 1) {
                broker.recordAutomatic("getAbilityToPlay:SINGLE_NATIVE_OPTION:" + hostCard.getName());
                return abilities.get(0);
            }
            java.util.List<String> labels = new ArrayList<>();
            for (SpellAbility ability : abilities) {
                labels.add("ABILITY_TO_PLAY:" + hostCard.getName()
                    + ":basic=" + ability.isBasicSpell()
                    + ":" + String.valueOf(ability));
            }
            String selectedId = broker.choose("ability_to_play", this.player, labels);
            int selectedIndex = Integer.parseInt(selectedId.substring(1));
            if (selectedIndex < 0 || selectedIndex >= abilities.size()) {
                throw failClosed("getAbilityToPlay:STALE_SELECTION");
            }
            return abilities.get(selectedIndex);
        }''',
        "engine-supplied getAbilityToPlay routing",
    )

    text = replace_once(
        text,
        '''        @Override
        public CostDecisionMakerBase getCostDecisionMaker(Player player, SpellAbility ability, boolean effect, String prompt) {
            throw failClosed("getCostDecisionMaker");
        }''',
        '''        @Override
        public CostDecisionMakerBase getCostDecisionMaker(Player player, SpellAbility ability, boolean effect, String prompt) {
            return new CostDecisionMakerBase(player, effect, ability, ability.getHostCard()) {
                @Override public boolean paysRightAfterDecision() { return true; }
                @Override public PaymentDecision visit(CostBehold cost) { throw failClosed("costDecision:CostBehold"); }
                @Override public PaymentDecision visit(CostBeholdExile cost) { throw failClosed("costDecision:CostBeholdExile"); }
                @Override public PaymentDecision visit(CostGainControl cost) { throw failClosed("costDecision:CostGainControl"); }
                @Override public PaymentDecision visit(CostChooseColor cost) { throw failClosed("costDecision:CostChooseColor"); }
                @Override public PaymentDecision visit(CostChooseCreatureType cost) { throw failClosed("costDecision:CostChooseCreatureType"); }
                @Override public PaymentDecision visit(CostCollectEvidence cost) { throw failClosed("costDecision:CostCollectEvidence"); }
                @Override public PaymentDecision visit(CostDiscard cost) { throw failClosed("costDecision:CostDiscard"); }
                @Override public PaymentDecision visit(CostDamage cost) { throw failClosed("costDecision:CostDamage"); }
                @Override public PaymentDecision visit(CostDraw cost) { throw failClosed("costDecision:CostDraw"); }
                @Override public PaymentDecision visit(CostExile cost) { throw failClosed("costDecision:CostExile"); }
                @Override public PaymentDecision visit(CostExileFromStack cost) { throw failClosed("costDecision:CostExileFromStack"); }
                @Override public PaymentDecision visit(CostExiledMoveToGrave cost) { throw failClosed("costDecision:CostExiledMoveToGrave"); }
                @Override public PaymentDecision visit(CostExert cost) { throw failClosed("costDecision:CostExert"); }
                @Override public PaymentDecision visit(CostEnlist cost) { throw failClosed("costDecision:CostEnlist"); }
                @Override public PaymentDecision visit(CostFlipCoin cost) { throw failClosed("costDecision:CostFlipCoin"); }
                @Override public PaymentDecision visit(CostForage cost) { throw failClosed("costDecision:CostForage"); }
                @Override public PaymentDecision visit(CostRollDice cost) { throw failClosed("costDecision:CostRollDice"); }
                @Override public PaymentDecision visit(CostMill cost) { throw failClosed("costDecision:CostMill"); }
                @Override public PaymentDecision visit(CostAddMana cost) { throw failClosed("costDecision:CostAddMana"); }
                @Override public PaymentDecision visit(CostPayLife cost) { throw failClosed("costDecision:CostPayLife"); }
                @Override public PaymentDecision visit(CostPayEnergy cost) { throw failClosed("costDecision:CostPayEnergy"); }
                @Override public PaymentDecision visit(CostGainLife cost) { throw failClosed("costDecision:CostGainLife"); }
                @Override public PaymentDecision visit(CostPartMana cost) {
                    broker.recordAutomatic("costDecision:CostPartMana:" + cost.toString());
                    return new PaymentDecision(0);
                }
                @Override public PaymentDecision visit(CostPromiseGift cost) { throw failClosed("costDecision:CostPromiseGift"); }
                @Override public PaymentDecision visit(CostPutCardToLib cost) { throw failClosed("costDecision:CostPutCardToLib"); }
                @Override public PaymentDecision visit(CostTap cost) { throw failClosed("costDecision:CostTap"); }
                @Override public PaymentDecision visit(CostSacrifice cost) { throw failClosed("costDecision:CostSacrifice"); }
                @Override public PaymentDecision visit(CostReturn cost) { throw failClosed("costDecision:CostReturn"); }
                @Override public PaymentDecision visit(CostReveal cost) { throw failClosed("costDecision:CostReveal"); }
                @Override public PaymentDecision visit(CostRevealChosen cost) { throw failClosed("costDecision:CostRevealChosen"); }
                @Override public PaymentDecision visit(CostRemoveAnyCounter cost) { throw failClosed("costDecision:CostRemoveAnyCounter"); }
                @Override public PaymentDecision visit(CostRemoveCounter cost) { throw failClosed("costDecision:CostRemoveCounter"); }
                @Override public PaymentDecision visit(CostPutCounter cost) { throw failClosed("costDecision:CostPutCounter"); }
                @Override public PaymentDecision visit(CostPutCounterYou cost) { throw failClosed("costDecision:CostPutCounterYou"); }
                @Override public PaymentDecision visit(CostUntapType cost) { throw failClosed("costDecision:CostUntapType"); }
                @Override public PaymentDecision visit(CostUntap cost) { throw failClosed("costDecision:CostUntap"); }
                @Override public PaymentDecision visit(CostUnattach cost) { throw failClosed("costDecision:CostUnattach"); }
                @Override public PaymentDecision visit(CostTapType cost) { throw failClosed("costDecision:CostTapType"); }
                @Override public PaymentDecision visit(CostPayShards cost) { throw failClosed("costDecision:CostPayShards"); }
                @Override public PaymentDecision visit(CostBlight cost) { throw failClosed("costDecision:CostBlight"); }
            };
        }''',
        "Primitive-A fail-closed cost decision maker",
    )

    text = replace_once(
        text,
        '''            if (isPrimitiveAFixture(finalistFixture) && primitiveATerminal(game)) {
                throw new ControlledStop("FINALIST_PRIMITIVE_A_TERMINAL");
            }''',
        '''            if (isPrimitiveAFixture(finalistFixture)
                    && automatic.contains("NATIVE_SPELL_RESOLVED:Lightning Bolt:fizzled=false")) {
                throw new ControlledStop("FINALIST_PRIMITIVE_A_TERMINAL");
            }''',
        "Primitive-A post-native-resolution priority boundary",
    )

    text = replace_once(
        text,
        '''        @Override
        public void declareAttackers(Player attacker, Combat combat) {
            throw failClosed("declareAttackers");
        }''',
        '''        @Override
        public void declareAttackers(Player attacker, Combat combat) {
            String finalistFixture = System.getenv("COMMANDER_LAB_FORGE_FIXTURE_ID");
            if (isPrimitiveAFixture(finalistFixture)
                    && broker.automatic.contains("NATIVE_SPELL_RESOLVED:Lightning Bolt:fizzled=false")) {
                throw new ControlledStop("FINALIST_PRIMITIVE_A_TERMINAL");
            }
            throw failClosed("declareAttackers");
        }''',
        "Primitive-A post-native-resolution phase-transition boundary",
    )

    text = replace_once(
        text,
        '''        GameState state = new GameState();
        state.parse(lines);
        state.applyToGame(game);
        game.getPhaseHandler().setPriority(game.getPlayers().get(0));
        broker.out.println("{\\\"protocol\\\":" + esc(PROTOCOL)''',
        '''        GameState state = new GameState();
        state.parse(lines);
        java.util.concurrent.CountDownLatch stateApplied = new java.util.concurrent.CountDownLatch(1);
        java.util.concurrent.atomic.AtomicReference<RuntimeException> stateFailure =
            new java.util.concurrent.atomic.AtomicReference<>();
        game.getAction().invoke(() -> {
            try {
                state.applyToGame(game);
                game.getPhaseHandler().setPriority(game.getPlayers().get(0));
            } catch (RuntimeException exc) {
                stateFailure.set(exc);
            } finally {
                stateApplied.countDown();
            }
        });
        try {
            if (!stateApplied.await(30, java.util.concurrent.TimeUnit.SECONDS)) {
                throw new ControlledStop("FINALIST_PRIMITIVE_A_STATE_APPLY_TIMEOUT");
            }
        } catch (InterruptedException exc) {
            Thread.currentThread().interrupt();
            throw new ControlledStop("FINALIST_PRIMITIVE_A_STATE_APPLY_INTERRUPTED");
        }
        if (stateFailure.get() != null) throw stateFailure.get();
        broker.out.println("{\\\"protocol\\\":" + esc(PROTOCOL)''',
        "Primitive-A synchronous GameState application",
    )

    text = replace_once(
        text,
        '''        runSession(in, out);
    }
}''',
        '''        runSession(in, out);
        System.exit(0);
    }
}''',
        "one-session Forge provider lifecycle",
    )

    path.write_text(text, encoding="utf-8")
    print("FORGE_PRIMITIVE_A_MOUNTAIN_REGISTRATION=PASS")
    print("FORGE_PRIMITIVE_A_GET_ABILITY_TO_PLAY=PASS")
    print("FORGE_PRIMITIVE_A_COST_DECISION=PASS")
    print("FORGE_PRIMITIVE_A_NATIVE_RESOLUTION_BOUNDARY=PASS")
    print("FORGE_PRIMITIVE_A_PHASE_TRANSITION_BOUNDARY=PASS")
    print("FORGE_PRIMITIVE_A_SYNC_BARRIER=PASS")
    print("FORGE_PRIMITIVE_A_ONE_SESSION_EXIT=PASS")


if __name__ == "__main__":
    main()
