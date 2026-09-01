#!/usr/bin/env python3
"""Close the concrete Forge Primitive-A qualification adapter gaps.

Forge GameState.applyToGame delegates through GameAction.invoke. From the Match start
hook that invocation may be asynchronous, so evidence sampled immediately afterward
can still observe the ordinary opening-hand/UNTAP state. In addition, GameState
materializes named zone cards through StaticData.commonCards; the existing finalist
bootstrap constructed Mountain PaperCards for Commander decks but did not register
Mountain in that headless card database. Finally, after SESSION_RESULT Forge's game
thread pool can keep this one-session qualification JVM alive even though the protocol
transaction is complete.

This qualification-only post-overlay patch therefore:
1. registers the already loaded Mountain rules as a real PaperCard in commonCards;
2. executes applyToGame from Forge's game thread and blocks the hook until completion;
3. exits the one-session provider JVM with status 0 only after runSession has emitted
   and flushed its terminal SESSION_RESULT.

Pinned Forge source remains unmodified.
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
        // This qualification provider is intentionally one session per JVM.
        // runSession flushes SESSION_RESULT before returning; explicit exit prevents
        // Forge's non-daemon game executors from keeping a completed transaction alive.
        System.exit(0);
    }
}''',
        "one-session Forge provider lifecycle",
    )

    path.write_text(text, encoding="utf-8")
    print("FORGE_PRIMITIVE_A_MOUNTAIN_REGISTRATION=PASS")
    print("FORGE_PRIMITIVE_A_SYNC_BARRIER=PASS")
    print("FORGE_PRIMITIVE_A_ONE_SESSION_EXIT=PASS")


if __name__ == "__main__":
    main()
