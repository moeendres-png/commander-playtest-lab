#!/usr/bin/env python3
"""Make Forge GameState materialization synchronous for finalist Primitive-A qualification.

Forge GameState.applyToGame delegates through GameAction.invoke. From the Match start
hook that invocation may be asynchronous, so evidence sampled immediately afterward
can still observe the ordinary opening-hand/UNTAP state. This qualification-only
post-overlay patch executes applyToGame from Forge's game thread and blocks the hook
until completion. Pinned Forge source remains unmodified.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", type=Path, required=True)
    args = parser.parse_args()

    path = args.provider
    text = path.read_text(encoding="utf-8")
    old = '''        GameState state = new GameState();
        state.parse(lines);
        state.applyToGame(game);
        game.getPhaseHandler().setPriority(game.getPlayers().get(0));
        broker.out.println("{\\\"protocol\\\":" + esc(PROTOCOL)'''
    new = '''        GameState state = new GameState();
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
        broker.out.println("{\\\"protocol\\\":" + esc(PROTOCOL)'''
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Primitive-A sync anchor mismatch: expected 1, observed {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("FORGE_PRIMITIVE_A_SYNC_BARRIER=PASS")


if __name__ == "__main__":
    main()
