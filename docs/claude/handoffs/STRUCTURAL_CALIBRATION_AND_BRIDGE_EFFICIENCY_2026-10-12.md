# Handoff: Structural calibration vs XMage and bridge efficiency (2026-10-12)

Branch `claude/oracle-optimizer-pilots-batch-e1y485`, on top of main after #753. Refs #733.
Git, tests and CI are Source Truth; this note only says where to pick up.

## 1. Why the Structural simulator disagreed with XMage

The optimizer-v2 screen ranks candidates with the Structural simulator, but on identical
pods its ranking did not track XMage full games (Spearman about -0.2 to -0.95, log-loss of
the XMage winner 1.71-1.89 against 1.386 for a uniform guess). Root causes found:

- 7 of the 15 opponent profiles (morcant, spiderman, blight, dance, wakanda, lorehold,
  hosts) were 51-63 % placeholder "role card NNN" cards.
- `build_default_profile` gives uncurated creatures `base_power=0`, so decks nobody curated
  could not win through combat.
- FINISHER came only from curated `ROLE_GROUPS`; commander cost and power were guessed.
- Kaervek's card-specific cast trigger dominates: Kaervek wins about 50 % in Structural,
  7-10 % in XMage (per-game damage: ~26 from the trigger, ~28 from combat).

## 2. What is implemented on this branch

| Piece | Where |
|---|---|
| XMage card facts export (power, toughness, types, mana value, rules text from the bridge H2 card DB) | `scripts/export_xmage_card_facts.py` -> `data/cards/xmage_card_facts.json` (1,885 cards) |
| Facts -> Structural profiles (power for uncurated creatures, text finishers, commander stats; curated values always win) | `src/commander_lab/engine/structural/card_facts.py`, used in `engine/structural/project.py` and `whole_deck/search_context.py` |
| Hosts and Lorehold opponents built from their exact 100-card precon lists | `data/opponents/{hosts_of_mordor,lorehold_spirit}_structural_profile.json` |
| Tunable combat/damage constants (defaults = old constants, so behaviour is unchanged) | `StructuralTuning` / `DEFAULT_TUNING` in `engine/structural/simulator.py` |
| Calibration harness: replay XMage pods in Structural, metrics, held-out split, coordinate-descent fit, process pool | `engine/structural/xmage_calibration.py`, `scripts/calibrate_structural_vs_xmage.py` |
| Reference XMage results (159 pods: 145 ground-truth pods over 22 decks + 14 control pods) | `data/calibration/xmage_reference_pods_2026-10-12.json` |
| Bridge efficiency: reuse the mana options `getPlayable` already computed | `engine-bridge/.../XmageFullGamePlayer.java` (`playableWithManaAvailable`) |
| Tests | `tests/unit/test_structural_xmage_calibration.py` (7 tests) |

Python unit suite on the branch: 2051 passed, 2 skipped. Bridge Java tests could not run
offline (surefire junit-platform artifact missing); CI must run them.

## 3. Rerun

```bash
# refresh facts after a new jar/card DB (needs the bridge runtime DB)
python scripts/export_xmage_card_facts.py \
  --h2-jar ~/.m2/repository/com/h2database/h2/1.4.197/h2-1.4.197.jar

# calibrate with the default tuning against the committed reference pods
python scripts/calibrate_structural_vs_xmage.py \
  --pods-json data/calibration/xmage_reference_pods_2026-10-12.json \
  $(for d in data/coverage_decks/collection/*.json; do printf -- '--deck %s ' "$d"; done) \
  --seeds-per-pod 40 --workers 4 --out /tmp/cal.json

# add --fit --fit-seeds 16 --fit-rounds 2 to fit StructuralTuning on one half
# and report the other (held-out) half
```

Baseline with facts, default tuning, 3 seeds per pod: Spearman 0.384 over 22 decks,
log-loss 1.866 vs uniform 1.386. Facts alone moved the ranking from negative to positive,
but the absolute win probabilities are still worse than a uniform guess.

## 4. Open work (in priority order)

1. **Run the fit** (above, `--fit`). A local run was started but its result was not
   persisted. Then apply the agreed decision rule on the held-out half:
   Structural stays an evaluator only if held-out log-loss is clearly below uniform AND
   Spearman >= 0.5. Otherwise demote it to a cheap prefilter and let XMage full games rank.
2. If the fit cannot pull Kaervek down, scale or drop its card-specific cast trigger
   (`_resolve_cast_triggers`, now driven by `StructuralTuning.cast_trigger_damage`).
3. The other 7 opponents with placeholder cards need exact lists (as done for Hosts and
   Lorehold) or should be excluded from the 15-deck screening ensemble.
4. ~~Bridge mana-cache~~ **Done:** merged in #761 (`playableWithManaAvailable`) and part of
   every later pin's bridge.
5. 15 of 160 ground-truth XMage games ended `ENGINE_FAILURE / XMAGE_ACTION_EXECUTION_FAILED`
   (gitrog, ramos, omnath, selvala among others) on pin `3cbf7741`. Superseded by the #747
   coverage run on pin `38cb21a8` (72 twin games over all 18 decks in 4/5/6P pods). It found two
   reproducible bridge failures, `NO_LEGAL_ACTION` on Wear // Tear and an empty
   replacement-effect choice; both are fixed in #777.
6. ~~Further XMage speed levers~~ **Settled** (see `docs/performance/XMAGE_FULL_GAME_SPEED_2026-10-12.md`):
   - AppCDS is merged in #761 (`scripts/build_xmage_cds_archive.py`).
   - The bulk card scan is in the live pin `38cb21a8`.
   - The per-source memo was dropped: no gain.
   - The lazy card copy was not proposed for a repin: wall time fell, CPU did not.
   - JVM reuse across games stays an Owner decision (D17 isolation).

## 5. Takeover by the Coordinator (2026-10-14)

- `main` merged: Forge removal, pin `38cb21a8`.
- Fix: the project context, and with it the exact result cache key, now hashes
  `data/cards/xmage_card_facts.json`. Before, a Structural result cached before a facts change
  could be served after it.
- Baseline reproduced with facts profiles and 3 seeds per pod: Spearman 0.371 over 22 decks,
  log-loss 1.900 against 1.386 for a uniform guess.
