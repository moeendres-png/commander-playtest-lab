# WS213 FRESH_PROCESS_TWINS

Method: one JVM per game; same explicit seed + identical decks/prefs/policy;
twin follows the primary's stream (exact label + offset/class gate +
recorded-numeric overwrite, incl. the WS213 empty-frame numeric fix);
semantic projection per WS205 precedent (multiset offered types, normalized
labels/ids, terminal board/seats).

- Behavior twins: 12/12 constructions twin_match TRUE at decision level
  (11 strict-hash TRUE; C03 strict-hash differs only in post-failure capture
  rows — identical native `XMAGE_ACTION_EXECUTION_FAILED` at the same offset
  in both twins; see D5_ADJUDICATION).
- Setup twins: 7/7 strict TRUE (500/500).
- Opening-hand twins (`opening-hand` mode, catalog/neutral seeds): 12/12
  identical hands + library sizes + first decision (mulligan seat 0).
- Long twins: E02 xlong2 (4656/4656 identical incl. spoil) and xlong3
  (5746/5746 identical incl. 3 damage frames).
- Different-seed controls (A03/F01/E02): same-seed hands reproduced,
  alt-seed hands differ → seed influence demonstrated.
- Hidden-info verdicts ride every decision row: 8709 rows, 0 violations.

Raw runs: `runs/<slot>/{behavior,setup,opening-a,opening-b}/…`,
`runs/RQ-C3-E02/{combat-scan-*,long-scan-*,xlong*-twin,…}`,
`runs/MATRIX.json`, `runs/SETUP_CHECKS.json`.

Machine companion: `FRESH_PROCESS_TWINS.json`.
