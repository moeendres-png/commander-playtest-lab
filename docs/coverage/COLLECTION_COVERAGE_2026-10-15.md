# Collection coverage in real XMage full games, 2026-10-15 (#747)

These are technical results: the games show that the cards run in the engine, not which deck
is stronger. They are local measurements, not qualification evidence.

- **Decks:** the 18 owner-collection coverage decks (`data/coverage_decks/collection`, #748).
- **Pin:** XMage `38cb21a8`, bridge from this PR.
- **Pods:** each deck plays at every pod size.
  - 4P: 5 pods
  - 5P: 4 pods
  - 6P: 3 pods
- **Seeds:** 1–3. Every pod is played twice with the same seed (twin), and both semantic
  transcript SHA-256 hashes must match.
- **Runner:** `scripts/run_collection_coverage_games.py`.

## Result with the fixed bridge

| Games ok | Twin pairs identical | Twins diverged | Decks covered |
|---:|---:|---:|---:|
| 72 / 72 | 36 / 36 | 0 | 18 / 18 |

Raw rows: `collection_coverage_38cb21a8_2026-10-15.json`.

## Findings on the bridge before this PR

On the bridge before this PR, 68 of the 72 games passed. Two pods with seed 3 ended in both
twins:

| Pod | Failure | Cause | XMage reference behaviour |
|---|---|---|---|
| 4P veyran, zegana, agrus, arcanis | `NO_LEGAL_ACTION` | no castable spell ability listed for Wear // Tear | `HumanPlayer.chooseAbilityForCast` falls back to `card.getSpellAbility()` |
| 5P titania, veyran, zegana, agrus, arcanis | `BRIDGE_PROTOCOL_ERROR` | empty replacement-effect choice (every competing effect lacks a source ability) | `HumanPlayer.chooseReplacementEffect` returns 0 for a map of size <= 1 |

The bridge now follows XMage in both cases and logs a forced move.

**Regression check:** all 68 games that passed on the old bridge have identical semantic
transcripts on the new one, and the 4 failed games now complete. The fix changes no game
that never reaches these two paths.

## Rerun

```bash
python scripts/run_collection_coverage_games.py --jar <bridge.jar> --out c.json --seeds 1-3 --workers 2
```
