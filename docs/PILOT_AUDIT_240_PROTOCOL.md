# Pilot audit, 240 decisions: protocol (#1524, G-SIM point 2, part b)

Label: `SIMULATED_RESULT`, weight 0, never a tier list. The package samples, blinds, collects and
scores. It never judges a decision; every judgement is human. The result is valid for exactly one
pilot fingerprint and covers the sample part only; the frozen gold cases (part c) are answered
separately. Source: `docs/OWNER_DECISIONS_STUDIO_20261118.md`, G-SIM point 2.

## What the Owner does (about 2 to 2.5 hours)

1. Run the audit-recorded series on the Owner PC (at least 24 games, all AI seats, seat rotation,
   Chulane deck in rotating seats). Recordings land in `<data>/pilot_audit/`.
2. Fix the seed before looking at anything. Write it down once, for example `20261201`.
3. Draw the sample (never into the repository; the tool refuses output inside a git checkout):

   ```
   python -m commander_lab.studio.pilot_audit_sample sample \
     --audit-dir <data>/pilot_audit --out-dir <private>/pilot_audit_240 \
     --seed 20261201 --tested-deck-id <chulane deck_id>
   ```

   Without `--tested-deck-id` the tested seat is the fixed `--tested-seat` (default 0). It refuses
   mixed pilot fingerprints, non-`SIMULATED_RESULT` or human headers, fewer than 24 games, fewer
   than 240 rateable decisions, or no seat rotation.
4. Outputs: `annotation_sheet_A.csv`, `annotation_sheet_B.csv` (blinded) and `sample_key.json`
   (key; item to game, seat, frame index, source sha256, calibration flags). Keep the key away from
   the annotators.
5. Give sheet A to annotator A and sheet B to annotator B, independently. They judge from the
   deciding seat's view only, using `state_summary`, `options` and `chosen`.
6. Calibration and disputes: after the annotators are done, run `score` once without an owner
   sheet. It lists `calibration_missing_owner` (40 items, half tested seat) and
   `disputed_for_owner`. Copy sheet A, keep only those rows, fill them yourself (about 40 plus the
   disputed items), save as `owner_sheet.csv`.
7. Score:

   ```
   python -m commander_lab.studio.pilot_audit_sample score \
     --key sample_key.json --sheet-a annotation_sheet_A.csv --sheet-b annotation_sheet_B.csv \
     --sheet-owner owner_sheet.csv --out-json result.json
   ```

   Exit code 0 PASS, 1 FAIL, 2 UNKNOWN, 3 refusal.

## Rateable rule

A decision is rateable when it is not `mana_payment`, its response selects only legal options, it
has at least two options after merging identical (option type, label) pairs, and
`minimum_selections` is smaller than that number (so not forced and not pass-only). Strata:
half the sample from the tested seat, half from other seats, each split by decision kind in
proportion (at least one per kind), drawn round-robin across games with the fixed seed.

## Annotator workflow

Fill per row: `verdict` = `ok` | `questionable` | `clear_error`; `severity` = `none` (for ok and
questionable) or `minor` | `major` | `game_deciding` (required for clear_error); `note` optional
(no engine keys). Blank rows count as missing. Judge the choice given what the seat could see,
not hindsight.

## Reading the result

`result.json` and the text output give: Cohen's kappa on the verdict (A vs B), and n/N with the
Wilson 95 % upper bound for clear errors (limit 10 %, at most 14/240), game-deciding errors
(limit 3 %, at most 2/240) and tested-seat clear errors (limit 10 %, at most 5/120).
Final verdict per item: Owner if present, else A and B when they agree (same verdict and, for
clear errors, same severity), else disputed. Any disputed item, missing or invalid annotation,
missing Owner calibration row, or a sample below 240 gives UNKNOWN, never PASS. PASS needs all
three bounds met. Record the pilot fingerprint with the result; it does not transfer.
