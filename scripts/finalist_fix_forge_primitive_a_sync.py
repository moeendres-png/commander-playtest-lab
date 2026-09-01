#!/usr/bin/env python3
"""Close concrete Forge Primitive-A qualification adapter gaps.

This qualification-only post-overlay patch keeps pinned Forge source unmodified and:
1. registers Mountain in StaticData.commonCards so GameState can materialize it;
2. executes GameState.applyToGame synchronously on Forge's game thread;
3. routes getAbilityToPlay strictly over Forge-supplied native SpellAbility options;
4. exits the one-session provider JVM only after the flushed SESSION_RESULT.

A singleton getAbilityToPlay list is non-discretionary and is recorded as automatic.
A genuine multi-option list is exposed to the external controller and must be selected
from exactly the options Forge supplied; no first/default/random/AI fallback is used.
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
                // Running on Forge's game thread makes GameState.applyToGame synchronous.
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
        // One qualification session per JVM. runSession flushes SESSION_RESULT first.
        System.exit(0);
    }
}''',
        "one-session Forge provider lifecycle",
    )

    path.write_text(text, encoding="utf-8")
    print("FORGE_PRIMITIVE_A_MOUNTAIN_REGISTRATION=PASS")
    print("FORGE_PRIMITIVE_A_GET_ABILITY_TO_PLAY=PASS")
    print("FORGE_PRIMITIVE_A_SYNC_BARRIER=PASS")
    print("FORGE_PRIMITIVE_A_ONE_SESSION_EXIT=PASS")


if __name__ == "__main__":
    main()
