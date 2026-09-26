# Impact Adjudication — donor PASS → new-base verdicts

Policy: donor evidence is provenance, never inherited PASS. Every ported
behavior was re-run on base `aebcfda3` + port commits. Same xmage-1.4.61
pin on both sides (Maven artifact identical; source-pointer prose
cfc36f44→db134b97 with DIRECTLY_VERIFIED descendant lineage).

## REQUALIFIED_PASS (re-ran green on new base)

- Bridge suite 153/153 offline (62 pre-existing + 91 ported: lifecycle
  12/12 incl. 2–5P concession/elimination/combat/hidden-info, seed
  binding, combat-damage, name canary, numeric WS229, player count/
  boundary, census/projection families).
- Python ported behavioral gates green: variable-player, replay-tape
  machinery (12 tests), numeric domain, ws223 files NOT (see parked),
  ws224 canary (27 incl. sealed-tape scan), operational 4P policy,
  compatibility pin+bootstraps (4/4 after 2-line workflow pin coherence),
  full-game + decision-matrix updates, docker-pin authorities, arclose
  drift, retention predicates 6/6 (47-predicate static gate verifies
  byte-fidelity of ported Session/Provider/JsonlBridge/full_game files).
- LIVE 4P full gate on new base: 2 complete games → natural terminal
  (winner seat 3), 4476 external decisions / 8 classes, semantic replay
  MATCH, no private-state leakage (DIRECTLY_VERIFIED 2026-09-19).
- LIVE 2/3/5P bounded smokes on new base: see VALIDATION.md outcomes.

## RETAINED (not re-run, rationale recorded, never RUNTIME_VERIFIED)

- Donor campaign observations/matrices (24-run twin matrix, 9985-frame
  oracle, FULL107-adjacent counts): layout-specific to donor runs;
  superseded by fresh runs above for the ported surface.

## PARKED — NOT_RUN / NOT_APPLICABLE_ON_BASE (cause, no weakening)

- ws223 cardinality/environment ×14 + compat workflow ×1 (now fixed):
  assert donor-era `.github` wiring (hashseed pins, smoke args, digests).
  Main owns CI wiring; behavior covered by green gates above. Follow-up:
  CI-lane wiring workstream (main-CI owner).
- tests/test_candidate_lossless_handoff.py: uncollectible (hypothesis
  missing; main's version needs it too — pre-existing environmental).
- 34 modules uncollectible (31 openpyxl-chain + fastapi + …):
  pre-existing environmental, identical class to repo's own prior
  adjudication; proven pre-existing for the 5 runtime-surface cases via
  pristine-base rerun (all 5 fail identically on aebcfda3).
- tests/qualification/{ws17r,ws221,ws222,ws225}: governance tier, never
  ported by design.
- Dual-run replay beyond the 4P gate, FULL107, 6P, APNAP extras,
  production-credit claims: NOT_RUN / NOT_CLAIMED as before.

## Impact of main-side context (no overlap, verified)

Main changed publisher/CPL surfaces + Mordor data since MB; zero overlap
with ported paths. Full collectible unit suite: 756 passed; residual
failures = 15 parked CI-wiring + 5 proven-pre-existing-environmental.
No donor change altered main-owned files (workflow edit is 2-line
pin-default coherence, YAML-validated).
