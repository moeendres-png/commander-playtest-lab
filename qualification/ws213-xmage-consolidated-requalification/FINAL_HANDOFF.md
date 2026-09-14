# WS213 FINAL_HANDOFF — XMage Consolidated Core Repin and Requalification

## Source Lock

- Lab: `moeendres-png/commander-playtest-lab`,
  `ws213/xmage-consolidated-core-repin-requalification-20260914`,
  audit base WS207 `17ddab61` (tree `3dc04b70`).
- Production XMage: WS212 `db134b9737e951367d65ef5806ad986319cc73ab`
  (tree `4c7cae47`); WS208 `08658972`; WS214 `c044d40f6` (TEST-ONLY).
- `ARCHITECTURE_FREEZE = NOT_CLAIMED`. `PRODUCTION_PROVIDER = NOT_SELECTED`.

## Work Completed

1. Repinned the Lab to the exact WS212 candidate with lineage + clean-room
   build + artifact correspondence proof (ENGINE_REPIN_PROOF).
2. Bound every credited session's seed to the native per-game Rules RNG
   (`setRulesSeed` + `setRequireExplicitSeed`, fail-closed); retired
   `RandomUtil` as authority; truthful per-run `seed_supported`.
3. Exposed authoritative CONCEDE (offer/submit, actor==subject==principal,
   one-shot token, native execution) with full negatives.
4. Re-ran the WS204 battery (105/105), D1–D5, 19-construction fresh-process
   twin matrix (D5 PASS), hidden-info (8709/0), E02 trample/double-block
   runtime (PASS mechanism), G04 runtime (PASS mechanism), all qualified
   setups (7/7), seed controls, player-count + semantic-replay impact gates.
5. Adjudicated I01 (no gate; fixture untouched), credited H01-NO_HUMILITY
   (+1, the workstream's first behavior credit), sealed 21 evidence files.

## New Findings

- WS208's false-twin matrix is fully resolved by the binding (all six TRUE).
- The WS205 twin harness under-answered numeric-only frames (schema-min
  instead of recorded value); fixed in the WS213 driver copy.
- Driver wish substrings match hold labels ("Do not attack with X") — scan
  prefs must drop declaration wishes for press policies.
- Short-mana cancel → identical native activation failure in both twins
  (C01/C03; pre-existing path, determinism-neutral).
- Losers' zones are cleaned on leave (empty terminal graveyards are correct).
- Trample dialogue bounds observed live: (0..7)→7, (0..0)→0, (2..7)→2.
- H01-NO_HUMILITY copy chain runs natively end-to-end (choose_use + copy
  choice + 2/2 copy, twin-identical).

## Changes

- `engine-bridge` (session binding/proof, concede offer+submit, player
  token, bridge endpoints, capabilities, pin strings) + 5 new test classes
  (seed binding, combat damage, concede, hidden-info, player-count).
- Pin consumers: manifest, both bootstraps, conformance script, 3 workflows,
  pilots doc, census/Java/Python pin tests, revised WS207 guard.
- New `qualification/ws213-xmage-consolidated-requalification/` namespace:
  `Ws213Driver.java` (run/twin/opening-hand, hidden verdicts, concede
  interrogation, spoil hook, bounds recording), `ws213_decks.py`,
  `ws213_driver.py`, 21 evidence files, `runs/` matrix.
- Sealed history untouched (all prior pins/evidence preserved).

## Tests / Evidence

- Bridge 105/105; Python WS213 scope 88/88; ruff PASS.
- Matrix: 12 behavior twins + 7 setup twins + 12 opening twins + 3 seed
  controls + E02 ladder; D5 PASS; hidden 8709/0; credit +1 (H01-NH).
- Broader suite: 880 passed; 6 failed + 40 errors, all pre-existing
  environmental (missing modules, uninstalled package, binary drift).
- FULL107 = NOT_RUN (burden stated in VALIDATION).

## PASS / FAIL / UNKNOWN

PASS: repin, binding, seed_supported, generic battery, D1–D5 (+D5 twins),
E02 mechanism, G04 mechanism, hidden-info, setup consumption, 4P, I01 (no
gate), credit ledger. PARTIAL: semantic replay. NOT_SUPPORTED: 2P/3P/5P
(fail-closed, successor specified). UNKNOWN: unassembled setups (A04, B01,
E01, G02, G03, H01-agg, I01, J02), unattempted slots (A04/E01/G02/G03/J02),
scenario-exact E02 split. NOT_RUN: FULL107.

## Remaining Blockers

- None in-scope: all WS213 gates terminal. Successors only (bounded):
  variable-player session (2/3/5P), replay/checkpoint contract, FULL107
  matrix, E02 exact-split + illegal-runtime observation, remaining setups.

## Outputs

- `qualification/ws213-xmage-consolidated-requalification/` (code + 21
  evidence files + `runs/` matrix).
- Local commits through the work (repin+binding+concede, hidden-info,
  driver namespace, race hardening).

## Dependencies Unblocked

- WS214 harness may proceed as test-only consumer; production lane needs no
  further engine change for 4P qualification; successor workstreams have
  exact bounded specs (player-count, replay, FULL107, setups).

## Exact Next Action

- Coordinator: review this handoff + sealed evidence; publish via canonical
  safe_push dry-run first (no raw push/PR/merge); then charter successors
  (variable-player, replay contract, FULL107, setup closure) as directed.
