# Full review of 2026-10-30: findings, fixes and what is next

Refs #1067, #989. Source lock: Lab `main` `4f6e0fd6a` (after #1066), engine pin `2ec507b721` (v14),
bridge jar sha256 `035a5b4e6ff6ff2911d0b49ff070e4c9e9b0df501539bcc32462b832f3fef3a0`, pod profile
casual/mid. Evidence class `LOCAL_OBSERVED`, no CI credit. Win rates are not claimed anywhere.

## 1. What this review covered (and did not)

Done in this session, each with its command:

- Re-read of the previous full review (Muse, `muse/claude-handover`, `handover/2026-10-24/max-review/`)
  and the cross-check `pilot-ai/GEGENPRUEFUNG_MAXREVIEW.md`; its open items re-checked against `main`.
- A fresh 24-seed real-pod dump (`pilot_request_corpus.py record --all`, 66,699 decisions) searched
  for wrong decisions: answer position per class (index 0 share), every cancelled payment traced to
  its card, every `choose_use` answer per card, every colour choice inside a payment, all 242 trigger
  orders. Counting rules are in the commands of this note; the counting script of #1066 is
  `scripts/pilot_dump_reach.py`.
- Two 36-seed runs (`benchmark_xmage_full_games.py run`) against the 36-seed reference: all games
  `ok`, hashes and winners compared.
- Source reading of the pilot paths that the findings touch (`choices.py` `_decide_boolean` and
  `_decide_choice`, `payment.py`, `priority.py`, `full_game_pilot_views.py`, `mcp/server.py`).
- Web research (section 5).

**Not done** (stated, not hidden): this was not a line-by-line re-read of the 115,010 source and
117,379 test lines, nor of the fork diff or the 672 bridge files. The per-PR claim table of the
2026-10-24 review (`01_PR_PRUEFUNG.md`) was not redone, and the Phase 1 to 3 headline numbers were
not reproduced again. Those rows keep the status that review and the cross-check gave them.

## 2. Findings

| ID | Severity | Finding | Evidence | Status |
|---|---|---|---|---|
| F-1 | medium | Louisoix's Sacrifice ({U}, "sacrifice a legendary creature or pay {2}") was cast with mana for the {U} only: the {2} is asked after the first payment, the payment is cancelled and the counterspell is lost. 19 of the 29 cancelled payments in 24 real games. | dump of seeds 1-24, per-card count of `cancel_mana_payment` | fixed here |
| F-2 | medium | The payment model counted a planeswalker loyalty ability ("+1: Add {R}{R}.") as a mana source. It is not one (CR 605.1a) and the engine offered none in 10,539 recorded payment prompts. It made F-1 and the optional-cost checks optimistic (Chandra on the board, seed 22). | dump: 0 of 10,539 prompts; seed 22 trace | fixed here |
| F-3 | medium | `test_real_stdio_mcp_roundtrip` flaked in CI (reply to `tools/call` missing). Cause: after `shutdown` the server waited 2 s for the running tool, then cancelled it and dropped its reply; a slow tool on a loaded host loses the reply. | job log of run 41025659310 (FAILED line), `mcp/server.py` `serve_stdio`, control below | fixed here |
| F-4 | low | Remaining cancelled payments (11 cancels in 7 of 24 games, seeds 2, 3, 4, 7, 13, 22, 23; corrected 2026-10-31, the first version said "11 of 24 games" and "one card each": Expressive Iteration cancels three times in seed 3) are mostly single cards. Largest families: "Cast X? (You still pay the costs)" answered Yes without a payability check (Talisman twice), and the colour choice of a nested payment (Hall of Oracles) that sees only the inner cost `{1}` and not the spell's `{R}` (2 of 186 in-payment colour choices: Garna, Shriekmaw). | dump traces | backlog (R-A below) |
| F-5 | info | Previous finding B-02 ("conftest makes 41 tests green without checking dirty state") is documented in the fixture and covered by `tests/unit/test_tracked_worktree_gate.py`, which uses the unpatched checks. Downgraded from medium to info. | `tests/conftest.py:73-110`, `test_tracked_worktree_gate.py` | no change |
| F-6 | info | Trigger ordering (P0-3) has low stakes: of 242 orders the top pairs are two "whenever cards leave your graveyard" value triggers, two draw triggers or an Arcane Denial pair; the order rarely changes the outcome. | dump, class `trigger_order` | ranking changed (section 4) |
| F-7 | info | The real pod is lopsided: one deck won 19 of 36 games (seats 1-4: 4, 3, 19, 10). The start seat is balanced (6 each in 24 seeds). Fine for pilot measurements, not a deck-strength statement. | `real36_main_6db6934f5_run1.json`, dump | none |
| F-8 | low | `docs/claude/state/HANDOFF.md` was stale (closed issues listed). | file header | regenerated |

Not a finding: `choose_use` answers follow the card text. "Pay {2}{W} and return this card"
(Vanguard of the Restless) is declined 25 of 25 times because the seat could not pay the cost
(checked on the first case: one untapped land for a {2}{W} cost); other may-prompts were answered Yes where they are free.

## 3. Fixes and their measurement

All three are Python only: no bridge, fork, pin or sealed record changes, so nothing here needs
requalification.

1. **F-1** `full_game_pilot_additional_cost.py` reads "As an additional cost to cast this spell,
   [sacrifice ... or | reveal a K card from your hand or] pay {N}." from the card text.
   `_extra_cost_cast_unpayable` (in `payment.py`, called from `priority.py`) withholds the cast when
   the printed price plus the extra mana is provably out of reach; a revealable card in hand, a cost
   reducer, a cost the model cannot read and flashback/alternative casts are left to the pilot.
2. **F-2** `_LOYALTY_COST` in `payment.py` keeps loyalty abilities out of `_visible_mana_offer`.
   One test that pinned the old reading (`test_pilot_optional_costs.py`) now expects the correct
   answer (two Swamps and Chandra do not pay {5}).
3. **F-3** `_SHUTDOWN_DRAIN_SECONDS = 30` for calls made before an explicit `shutdown`; EOF and
   cancelled calls keep the 2 s grace.

Measurement (seeds 1-36, same jar and settings as the reference):

| | Reference `6db6934f5` | With the fixes |
|---|---|---|
| Games finished (`status ok`) | 36 of 36 | 36 of 36 |
| Games with the same hash | | 26 of 36 (seeds 6, 7, 12, 13, 14, 19, 22, 26, 27, 32 differ) |
| Same winner | | 34 of 36 (changed: seed 13 seat 4 to 3, seed 32 seat 1 to 3) |
| Cancelled payments, seeds 1-24 | 29 | 11 |
| Louisoix's Sacrifice cancels | 19 | 1 |
| Cancelled payments in the 7 changed seeds of 1-24 | 21 | 3 |

The 7 other seeds of 1-24 have identical hashes, so their counts did not change. Winners change in
2 of 36 games and win rate is not claimed (36 games carry only very large effects). Wall time is
not a claim: the runs were taken with other work on the machine (+22 %).
Files: `measurements-2026-10-30/real36_fix1067_run1.json`; the reference moves with this change
(follow-up PR with a twin run).

Controls from the wrong reason: the unit tests fail on the old code for the right reason (the
Louisoix case is withheld only by the new method; with `_SHUTDOWN_DRAIN_SECONDS = 0` the MCP test
loses the reply of call 3, which is the CI failure); the measurement script gives the known 29
cancels on the unchanged `main` dump.

## 4. Ranking of what is next

1. **R-A Abort backlog, small.** "Cast X? (You still pay the costs)" payability guard and the nested
   colour choice (F-4). Expected: a few of the 11 cancels, 0.1 per game. Cheap, Python only.
2. **P1-2 postcombat default for sorcery-speed permanents** (1,135 candidates in 24 games, #1066).
   Stays the largest open timing item; paired games mandatory.
3. **P0-3 trigger order: demoted** (F-6). Forge's AI has no ordering logic either (source below), the
   rules let the controller choose (CR 603.3b), and the stakes are small. Build it only if a game
   shows a damaging order.
4. **P4 fast path and engine throughput (E1+E3)**: biggest reach, no change to play; E1+E3 need a
   fork push and a repin, so the Owner's go.
5. **Pod realism check (new, cheap):** ask Commander Spellbook's bracket estimation for the four
   real-pod decks and the pool, to back the "casual/mid" profile with a number.

## 5. Research (source and date; "read" = I read it, "heard" = not verified)

- Forge AI trigger ordering: a developer thread says the AI "has no logic how to stack Abilities put
  on the stack at the same time" and works decision by decision (read, search result 2026-10-30,
  `slightlymagic.net/forum/viewtopic.php?p=207033`; old, the current source was not read: heard).
- Rule basis: CR 603.3b, each player in APNAP order puts own triggers on the stack in any order they
  choose (read via search, 2026-10-30).
- Variance reduction: AIVAT (Burch et al., AAAI 2018, `arxiv.org/abs/1612.06915`) and the Baseline
  control variates (Bowling et al., AAMAS 2013) cut the hands needed by up to a factor of 10, but
  both need a good value function; not usable for Commander without one. Our paired seeds stay the
  method (read, 2026-10-30).
- Commander Spellbook bracket estimation API, `/estimate-bracket` (heard: from a generated client
  documentation and a forum post; check the Swagger schema, terms and rate limits before use).

## 6. Open

- F-4 backlog items are not built. The follow-up PR for the new 36-seed reference (twin run) comes
  after this one merges, because the reference names the merge commit.
- The local mypy check could not run in this container (pydantic missing); CI is the check.
- Win rate of the three fixes: UNDECIDED, could only see effects of about 25 points on 24 pairs.
