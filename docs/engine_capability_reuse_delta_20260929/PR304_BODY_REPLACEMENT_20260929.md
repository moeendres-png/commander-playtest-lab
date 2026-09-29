## What this is

A capability-delta audit plus the one integration cluster it justified.

All 44 `BLOCKED` rows of the 107-row current-boundary denominator cite **one**
cause: the provider reported `starting_state_injection_supported = false`. The
Lab's own `XmageNativeStateRestoration` already materialises those mid-game
states through XMage public APIs, revalidates them with engine-authoritative
state-based actions plus layers, and proves them with a strict native readback
compare with SHA-256 digests. It was constructed from **exactly one production
site, always with a `null` restoration**, and its per-dimension manifest had
**exactly one caller: a test**.

This is a missing *route*, not a missing capability. `PB03_ROOT_CAUSE_AND_REMEDIATION.md`
already recorded the consequence: *"Nothing consumes that manifest at the
qualification boundary."*

## Ownership

The implementation touches **no file owned by an open PR** (#284, #289, #299, #300).
`Main.java` was the only free dispatch point, so the cluster is delivered as a
new `midgame` lane plus one added branch there, composing the existing seam by
construction rather than editing it.

Verified mechanically against the union of files touched by all 43 open PRs.

## What is new

| File | Purpose |
|---|---|
| `XmageMidgameJsonlBridge.java` | Protocol-2 surface reusing the existing decision controller, player, redactor and action projection. **Zero new Rules semantics.** |
| `Main.java` | one `midgame` lane branch |
| `XmageMidgameLaneTest.java` | 10 native tests incl. a 16-row census and a 4-player combat declaration |
| `midgame_lane.py` | manifest consumer; refuses to fall back to the coarse bit |
| `run_midgame_capability_probe.py` | real-process end-to-end receipt |
| `test_current_boundary_midgame_lane.py` | 14 unit tests over the consumer's refusal semantics |
| `MIDGAME_CAPABILITY_PROBE.json` | runtime receipt |
| `docs/engine_capability_reuse_delta_20260929/*` | source lock, matrix, archaeology, provenance, decision |

## Evidence (pinned process, `engine_commit b1959698…`)

| Command | Result |
|---|---|
| `mvn -o -Dtest=XmageMidgameLaneTest test` | 10 run, 0 failures — **PASS** |
| `mvn -o test` (full native regression) | 412 run, 0 failures, 1 skipped — **PASS** |
| `run_midgame_capability_probe.py` | 16 rows: **8** `ENGINE_NATIVE_REACHABLE`, 3 `ENGINE_STATE_ACCEPTED`, 1 `CONSTRUCTION_MISMATCH`, 4 `ENGINE_REJECTED` with the engine's own codes |
| `pytest test_current_boundary_midgame_lane.py` | 14 passed — **PASS** |
| `ruff check` / `ruff format --check` / `mypy --strict` | **PASS** |

Actual-card proof: `WS05-MP-COMBAT-4` drives a **four-player Commander** mid-game
state with real `Grizzly Bears` and `Rograkh, Son of Rohgahh`, declares two
obligate 2/2 attacks against two different opponents by selecting only the
engine's own offered option labels, and proves construction against the frozen
record's spec digest.

## Deliberate refusals

- **The coarse bit stays `false`.** Flipping it would have "unblocked" the rows
  in one edit and would also be false — stack placement, control divergence,
  tapped permanents, counters and attachments are all still rejected with codes.
  The lane publishes the per-dimension manifest and
  `global_starting_state_injection_claimed = false` instead. Rows were made
  reachable by reaching them, not by relabelling.
- **No hidden arrival loop.** `complete_midgame_arrival` does engine-side work
  only. The mulligan, the choosing-player pick and every priority pass are
  submitted by the external caller over the same protocol.
- **No qualification row promoted.** The current boundary keeps
  `BLOCKED 44 / UNKNOWN 59` until its owners rerun it.
- **PB-09 / PB-06 / PB-08 untouched.** No Forge evidence read or re-attributed.
- **No GPL/AGPL transfer.** Forge `PlayerController`, Manabrew's parity harness
  and phase.rs scenarios are all `REFERENCE_ONLY`; Manabrew is AGPL-3.0-or-later
  and nothing was copied, transliterated or adapted.
- **No engine branch.** The one capability needing an upstream change
  (XMage's split Rules RNG) is issued as a dispatch packet.

## Two existing findings independently reproduced

`life P2: requested 0 observed 40` (the engine re-derives starting life) and the
stack-placement / control-divergence coded rejections, both now on a
production-reachable surface instead of only in JUnit.

---

## Causal completion campaign (2026-09-29, branch head `8a7e8e30`)

**Status: the pre-causal counts above are historical.** The branch now carries
two causal entries on the same lane (`causal_stack`, `causal_elimination`) plus
placement-obligation drivers, all reusing the landed seam with zero new Rules
semantics and zero edits to files owned by other PRs (#284/#289/#299/#300/#316).

Final measured partition — 29 rows probed on the pinned process
(`engine_commit=b1959698…`), every decision from the engine's own offered
options:

| Outcome | Count | Rows |
|---|---|---|
| `ENGINE_NATIVE_REACHABLE` | 8 | COMBAT-4/5, CMD-ELIM-4, CMD-DMG-SPLIT, CMD-PARTNER-ZONE, CMD-TAX-2, MICRO_COMBAT, CARD_02 |
| `CAUSAL_ROUTE_REACHABLE` | 9 | BLOCK-4 (802.4a partition), PRIO-3/5 (live priority rings), ELIM-PRIO-3/OWNED-3/TURN-3/ELIM-5 (14 real Bolts each via engine SBAs), MICRO_REPLACEMENT (3 doubled to 6), MICRO_ZONE_CHANGES |
| `CAUSAL_ROUTE_MEASURED_BLOCKED` | 10 | TURN-5 (normal rotation, no extras; missing `causal_cast` entry), CMD-ZONE ×8 (duality traces, zero choice classes), ELIM-STACK-3 (needs combined stack+elimination entry) |
| `ENGINE_REJECTED` | 2 | CMD-DMG-CONTROL, ELIM-CONTROL-3 (both `UNSUPPORTED_CONTROL_DIVERGENCE`) |
| `CONSTRUCTION_MISMATCH` / transport failures | 0 | — |

Evidence: JUnit lane 10/10 + causal 25/25, full native **509/0/0/2**, probe
receipt `qualification/midgame-lane-20260929/MIDGAME_CAPABILITY_PROBE.json`,
pytest 17/17, `ruff check`/`format --check`/`mypy --strict` clean.
`EXTERNALLY_RULE_VALIDATED` unclaimed throughout. No row promoted; no pin
changed. PB-09/PB-06/PB-08, CAP-08, CAP-11, Forge untouched.

Full account: `docs/engine_capability_reuse_delta_20260929/CAUSAL_CONTINUATION_20260929.md`.

`ARCHITECTURE_FREEZE = NOT CLAIMED` · `PRODUCTION_PROVIDER = NOT SELECTED`
