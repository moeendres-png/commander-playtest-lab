# Handoff to Sol — Claude session 2026-09-29 (Opus 5.5)

`ARCHITECTURE_FREEZE = NOT CLAIMED` · `PRODUCTION_PROVIDER = NOT SELECTED`

Everything below is fresh as of this handoff. Re-verify the SHAs before acting.

## Source lock

| Item | Identity |
|---|---|
| Lab `main` (base of this branch) | `74841a08` (PR #303 merge); tree `1f4cf10f` before this branch |
| This branch / PR | `claude/xmage-corpus-completion-20260929` (PR, see below) |
| Earlier Claude PR | #294, **merged** as `15f88b5f` (2P CommanderDuel + review; Sol integrated `2ca4313c`/`b239a161`) |
| XMage pin | `b19596980f27…` (unchanged) |
| Forge executing Rules Core | `ef958ee9` (unchanged); upstream baseline `a37a865a` |
| Rules / Oracle | CR 2026-09-25 (sha256 `8d860e45…`, identical to project receipt); Oracle and rulings via Scryfall API, fetched 2026-09-29 |

## What is already on main (#294)

1. **CR 103.8a fix, XMage.** Both bridge lanes now build 2P tables as the engine's own `CommanderDuel`; 3–6P stay `CommanderFreeForAll`. Before this, every Lab 2P XMage game drew for the starting player on turn 1.
   - Coverage: `XmageFirstTurnDrawRuleTest`.
   - Evidence impact: all XMage 2P evidence from before `15f88b5f` was measured under the illegal draw. That covers `PLAYER_COUNT_2P`, #289's START-2 and 2P native receipts.
2. **Independent evidence-integrity review.** See `EVIDENCE_INTEGRITY_REVIEW.md`, findings F-01…F-11.
3. **Actual-card corpus probes.** `XmageActualCardCorpusTest`, 21 cards, hardened by Sol.

## What this branch adds (ready to merge)

- `XmageActualCardCorpusTest`:
  - start variant with per-player partner commanders;
  - **CARD_03 Esior**: the {3} tax applies only when targeting its controller's commander; runtime PASS;
  - **CARD_08 Jeska**: loyalty = commander casts from the command zone (counts itself, per the 2020-11-10 ruling); −X deals X; runtime PASS.
- Three documented `@Disabled` findings, no weakened assertions:
  - **CARD_12 Dig Through Time, F-12:** delve not projected on the lane;
  - **CARD_27 Path of Ancestry, F-13:** no scry, UNKNOWN;
  - **CARD_09 Magma Opus, F-14:** divided-damage response shape, UNKNOWN.
- Review document: F-12…F-14, plus the note on the `746a0f44` regression and Sol's fix.
- Validation on this branch: engine-bridge full suite **408 run, 0 failures, 4 skipped**. The skips are the START-2 v1.0.5 provenance test plus F-12/F-13/F-14. The corpus class runs 29 tests: 26 pass, 3 skipped.
- Command: `cd engine-bridge && mvn -o -Dcheckstyle.skip=true test`.

**XMage corpus standing:** 23 of 29 cards have native Oracle-derived runtime probes (CARD_01, 03, 05–08, 10, 11, 13–26 except 12, and 28). CARD_02 has older native tests. Missing: CARD_04 Kediss (needs multi-turn commander combat), 09, 12, 27 (findings) and 29 Boseiju (saga across turns). These are native technical evidence at the pin. **No FULL107 row and no current-boundary credit is claimed.** Whether native corpus probes may feed AF07/PB-07 is Sol's evidence-policy call.

## Decisions reserved to Sol / Coordinator

1. **F-11 (P1), Forge Find // Finality.** Lab commit `bc347e62` (WS234) added `K:Aftermath` to Finality inside the executing Forge Rules Core `ef958ee9`. Oracle and the official rulings say it is a plain split card, and upstream Forge was correct. Forge PR #6 and DeepSeek #287 depend on the false premise, and an evidence comment is posted on Forge #6. Decide:
   - whether to revert the hunk (Forge lane, tied to PB-09);
   - whether to re-derive CARD_28 before any Forge PB-07 credit.
2. **Evidence policy.** Can native actual-card probes (Oracle-derived, engine-offered decisions only) count toward AF07/PB-07, or only via a FULL107 row?
3. **F-03.** XMage generic lane `chooseMulligan` returns keep with no fail-closed path. #300 appears to address it; confirm on merge.
4. **F-01/F-02.** The START-2 classifier does not compare hand/library counts or the observation step. #300 ("discriminating S…") appears to address it. Then requalify the XMage 2P rows on a head containing `15f88b5f`.
5. **PB-09.** Forge candidate identity. #297/#299 run pristine upstream Forge; F-11 is direct evidence that the fork diverges from Oracle on at least one card.

## Merge instructions for this branch

1. Re-lock `main`. If it moved, normal-merge `main` into the branch (never rebase or force), then re-run `cd engine-bridge && mvn -o -Dcheckstyle.skip=true test`.
2. Required CI: quality, security, infrastructure, build-and-integrate, conformance, h4-xmage, h4-forge, real-4p-smoke, mutation-detection (exact-main-admission skips on PRs).
3. Test and docs only: no production Java change and no qualification evidence regenerated. Impact class: NON_IMPACTING to runtime evidence.

## Housekeeping

Two stash entries from this session in the shared stash, both obsolete and safe to drop by an operator (`stash drop` is policy-denied for agents):
- `claude-seed-wip-20260929`: superseded by #293;
- `claude-batch4-local-20260929`: ported here on top of Sol's payer.

Obsolete worktree: `/home/moeen/code/claude-xmage-2p-draw-skip-20260929`; its branch was merged and deleted. The active worktree is `/home/moeen/code/claude-corpus-completion-20260929`.

## Exact next action

Merge this branch after green CI. Then adjudicate F-11 before any Forge PB-07 or Forge #6 credit. Then land #300 and requalify the XMage 2P rows.

## Addendum — branch `claude/xmage-special-mana-actions-20260929` (after #305)

- **F-12 fixed (production bridge change, full-game lane).** `XmageFullGamePlayer.playMana` now projects the engine-authored special mana actions (delve, convoke, improvise), as XMage's human player does. `XmageFullGameActionProjection` maps `special_mana_action` to `pay_cost`, and its projection test pins that.
  - Impact: this adds payment options only where the engine offers them. Pilots of already-qualified games with no delve/convoke/improvise cards see no difference, so evidence for those runs is NON_IMPACTING. Any lane evidence involving such cards needs re-execution.
- **F-14 resolved.** Divided damage needs target plus amount in one response; Magma Opus passes.
- **XMage corpus:** 25 of 29 cards now have native Oracle-derived runtime probes. Missing: CARD_04 Kediss, CARD_27 Path (F-13, UNKNOWN) and CARD_29 Boseiju; CARD_02 has older tests.
- Validation: engine-bridge suite 416 run, 0 failures, 2 skipped (START-2 provenance; F-13).
