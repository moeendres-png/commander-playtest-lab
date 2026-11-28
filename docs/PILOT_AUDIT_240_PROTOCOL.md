# Pilot audit, 240 decisions: protocol (#1524, G-SIM point 2, part b)

Label: `SIMULATED_RESULT`, weight 0, never a tier list. The package plans, samples, blinds,
collects and scores. It never judges a decision; every judgement is human. The result is valid for
exactly one pilot fingerprint and covers the sample part only; the frozen gold cases (part c) are
answered separately. Source: `docs/OWNER_DECISIONS_STUDIO_20261118.md`, G-SIM point 2.

Binding minimums are hard floors in the code and cannot be lowered by any option: 24 games, 240
rateable decisions, 120 from the tested seat, 40 calibration items. `score` re-checks all of them
from the key and returns UNKNOWN if any is not met.

## What the Owner does (about 2 to 2.5 hours)

Order: plan, then run the series, then sample. All files stay outside the repository (the tool
refuses an output folder inside a git checkout).

1. Fix the plan BEFORE the series. Seed, tested deck and the strata (decision classes with a quota
   per half; default 48 priority, 18 target, 12 declare_attacker, 12 declare_blocker, 12
   choose_object, 6 mode, 6 choice, 6 choose_use) are written once, with a creation time:

   ```
   python -m commander_lab.studio.pilot_audit_sample plan --out <private>/plan.json \
     --seed 20261201 --tested-deck-id <chulane deck_id>
   ```

   Optional `--strata class=quota,...` (per half, sum 120). It refuses to overwrite a plan.
2. Run the audit-recorded series on the Owner PC (at least 24 games, all AI seats, the tested deck
   rotating through the seats). Recordings land in `<data>/pilot_audit/`. `sample` refuses games
   recorded before the plan was created.
3. Draw the sample:

   ```
   python -m commander_lab.studio.pilot_audit_sample sample \
     --audit-dir <data>/pilot_audit --out-dir <private>/pilot_audit_240 --plan <private>/plan.json
   ```

   It refuses mixed pilot fingerprints, non-`SIMULATED_RESULT` or human headers, fewer than 24
   games, fewer than 240 rateable decisions (or 120 per half), or a tested deck that never changes
   seat. The tested seat of a game is the seat whose `deck_id` equals the plan's tested deck.
4. Outputs: `annotation_sheet_A.csv`, `annotation_sheet_B.csv` (blinded), `owner_calibration_sheet.csv`
   (the 40 calibration items, blank) and `sample_key.json` (key; item to game, seat, frame index,
   source sha256, calibration flags). Keep the key away from the annotators.
5. Give sheet A to annotator A and sheet B to annotator B, independently. They judge from the
   deciding seat's view only, using `state_summary`, `options` and `chosen`.
6. Owner calibration: fill `owner_calibration_sheet.csv` yourself, blind to A and B (about 40 items).
7. Run `score` once with the owner calibration sheet and `--owner-template`. It lists disputed
   items and writes `owner_template.csv` with blank rows for every disputed item and every
   calibration item still missing. Fill those rows (no A/B verdicts are shown) and save as
   `owner_sheet.csv`; owner rows count only from the sheet passed as `--sheet-owner`:

   ```
   python -m commander_lab.studio.pilot_audit_sample score \
     --key sample_key.json --sheet-a annotation_sheet_A.csv --sheet-b annotation_sheet_B.csv \
     --sheet-owner owner_sheet.csv --owner-template owner_template.csv --out-json result.json
   ```

   Exit code 0 PASS, 1 FAIL, 2 UNKNOWN, 3 refusal. Combine your calibration rows and the
   dispute rows into the one owner sheet (same columns).

## Rateable rule (a documented proxy)

The engine does not label "different play consequence", so a decision counts as rateable by this
proxy: it is not `mana_payment`, its response selects only legal options, it has at least two
options after merging identical (option type, label) pairs, and `minimum_selections` is smaller
than that number (so not forced and not pass-only). The sample is drawn per half (tested seat,
other seats) from the plan's strata, round-robin across games with the plan seed. A class with too
few decisions is not silently dropped: its shortfall is moved proportionally to planned classes
with spare decisions, and the key reports planned versus drawn per class. Classes not in the plan
are not sampled and are listed in the key.

## What annotators see

Only what the redacted state of the deciding seat carries: phase, life, poison, own hand, opponent
hand counts, battlefield with tapped, power/toughness, damage and counters, face-down permanents
as "face-down permanent", graveyard and exile, library counts, mana pool, command zone, and the
stack. Opponents are "Opponent N", the deciding seat is "You"; seat-revealing engine names are
replaced. No ids, deck names or engine keys.

## Annotator workflow

Fill per row: `verdict` = `ok` | `questionable` | `clear_error`; `severity` = `none` (for ok and
questionable) or `minor` | `major` | `game_deciding` (required for clear_error); `note` optional
(no engine keys). Blank rows count as missing; a duplicate row for an item makes the sheet invalid.
Judge the choice given what the seat could see, not hindsight.

## Reading the result

`result.json` and the text output give Cohen's kappa on the verdict (A vs B, and A and B each vs
the owner on calibration items), and n/N with the Wilson 95 % upper bound for clear errors (limit
10 %, at most 14/240), game-deciding errors (limit 3 %, at most 2/240) and tested-seat clear errors
(limit 10 %, at most 5/120). Final verdict per item: Owner if present, else A and B when they agree
(same verdict and, for clear errors, same severity), else disputed. Any disputed item, missing or
invalid annotation, missing owner calibration row, or a key below the minimums gives UNKNOWN, never
PASS. PASS needs all three bounds met. Record the pilot fingerprint with the result; it does not
transfer.
