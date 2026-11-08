# Chulane — active owner deck focus (2026-11-08)

## Binding owner priorities

- **Chulane, Teller of Tales is the only active personal deckbuilding, optimization, pilot and game-evaluation goal.** Do not start or continue owner-focused RogShai optimization, purchasing, candidate search or default pods.
- Recorded 100-card baseline: `data/decks/chulane_current.txt`; identical simulator snapshot: `data/decks/deckbau/chulane_current.json` (deck ID `custom/chulane`). Changes to the baseline require a new owner decision. Build and test alternatives as separate versioned candidates.
- Confirmed edit (2026-10-31): **Whitemane Lion + Elvish Mystic IN; Aether Adept + Kor Skyfisher OUT**. The Chulane deck guide represents modeled playing advice, not measured win-rate evidence.
- Existing RogShai decks, scripts required by older tests, sealed evidence and archival guides stay **read-only for regression and reproducibility**. They must not be considered an active owner-deck objective. Historical `data/decks/manifest.json` activation fields are not a newer owner decision. Do not rewrite inventory/ownership/allocation truths merely to change deckbuilding focus.
- This assignment does not authorize reading or exposing `data/collections/**`. Do not send the deck list or partial list to external APIs. Other Commander/planeswalker conversations and their price limits are separate from this Chulane build.

## Agent instructions and remaining work

1. **Deck builder:** optimize Chulane's creature-bounce/value engine, Clue/token package, landfall, interaction, protection from wipes and scalable multiplayer win conditions. Compare against the unchanged baseline. Prioritize games against **three or more opponents**, not 1v1 assumptions.
2. **EDHREC/data auditor:** review actual Chulane lists and card co-occurrences per archetype, not only summary percentages. Previous audit report (2026-11-08): **594 cards still lacked independent manual deep review**; treat the count as a reported backlog pending verification, never as a passed gate.
3. **Rules/combo auditor:** independently verify creature-bounce loops, triggered abilities, prerequisites and win lines using official Magic rules and the pinned XMage engine. The full independent combo-rule audit remains **open**. Catalog `READY` does not prove all interactions or legality.
4. **Multiplayer evaluator:** run Chulane in deterministic 4-player XMage full games, using the fixed `precon`, `mixed`, `optimized` pods. For paired candidates use the seat-rotated comparison runner and report seeds, win shares, failures and pilot limitations. **5+/6-player Chulane-specific results are unverified**; the Deckbau CLI supports only 4P until a separate qualified multi-seat workflow exists.
5. **Pilot/metrics auditor:** validate `custom/chulane` guide suggestions and per-card cast opportunity telemetry. Exact mana-spent efficiency and hand residence are currently `NOT_MEASURED`, not zero.

## Commands and acceptance

```bash
python -m commander_lab.deck_readiness data/decks/deckbau/chulane_current.json --json
python scripts/deckbau_pool_readiness.py --json
python scripts/deckbau_eval.py --deck data/decks/deckbau/chulane_current.json --pod mixed --seeds 1 --out artifacts/deckbau/chulane-mixed-1.json
```

The active 177-deck test shortlist is **173 precons + two opponent precons + Kaervek + Chulane**; there is no RogShai opponent in the Deckbau pods. Consult `DECKBAU_INTERFACE.md` for paired comparisons, full game report schema and exact limits.

**Not yet established:** complete independent EDHREC card reviews, complete combo Rules reviews, Chulane-specific 5+ player results, or a new exact-HEAD XMage full-game validation. `UNKNOWN` is not `PASS`. Keep XMage as sole Rules authority, existing source-lock/CI/review gates, and the separate live privacy-policy PR untouched.
