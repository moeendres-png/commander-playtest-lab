# WSR27/WSR28/WSR30 Current-Boundary Consumption — Durable State

Bounded state for the current qualification-remediation stream. The campaign
state remains `WORKSTREAM_STATE.yaml` (WSR22 successor); this file records the
WSR27/WSR28/WSR30 remediation line only. Not a qualification report.

## Source lock (final)

| Item | Value |
| --- | --- |
| Lab repository | `moeendres-png/commander-playtest-lab` |
| Lab branch | `wsr27/final-candidate-remediation-20260928` |
| Lab evidence head (runtime + packet) | `cc799fc4f9285e7f1e7cebcd96ca269995a8fea9`; this state file is a successor commit on top of it |
| Lab PR | #286, OPEN, DRAFT, base `main` |
| Runner commit recorded in evidence | `f5d3197a90503b0ff1e50142a1828c89d83ab752` |
| Canonical main merged | `6b8c2150e02d0ef6db6f4c4d3df5a104b4e7e890` (PR #281), via `b132f9a5`; earlier `c9277b90` (PR #283) via `f04c90b0` |
| Forge Rules Core | `ef958ee91ac6c9ce0152189f2654bf6e05abf273`, tree `fc3387bf37aab19d780b2939a235309ed32b0492` |
| Forge bridge/evidence head | `e15f37d6b2b5c0ad682948f86f037e07b6aaded5`, tree `a1d4d4a8fe421e57b919e8e0bd9fda7d9deb0d3b`, PR #5 DRAFT |
| WSR20 evidence tip | `18bba95a4528f6ab5910633f1f87f603b8c4ddf8` |
| Upstream baseline | `a37a865a53280dd8ad6fad3384d69611e8c5a42f` — ancestry only, not pristine, not observed |
| Forge worktree | `/tmp/opencode/forge-pr4` at the exact head, built at that head |

## Completed

- Normal merges of current main (twice) into the owned branch; no rebase, no
  history rewrite, no wholesale ours/theirs.
- Dual-shape principal binding in `validate_principal_scoping`: exact live-engine
  envelope OR authoritative in-state actor marker; contradictory or absent
  binding fails closed. Provider requester-binding metadata is excluded from the
  content distinctness comparison (`observer_player_id`,
  `observer_engine_player_id`, `observer_seat`, `is_actor`, monotonic offset).
- Provider-neutral draw-skip observation in `game_driver`: names the engine-stated
  acting principal, validates whichever binding shape is emitted, persists only
  zone counts plus a mechanism label, fails closed otherwise, and never persists a
  live engine principal id. Repairs main's int/string seat defect. START-2 guard
  observations are persisted in `terminal_facts`.
- Lab rebound to Forge PR #5; Rules Core unchanged; PB-09 identity distinction
  intact. Native-suite stage scoped to the selected candidates.
- Forge runtime requalification at `e15f37d6`, runner `f5d3197a`:
  - FULL107 Forge **PASS 5 / FAIL 0 / UNKNOWN 58 / BLOCKED 44** (was 4/0/59/44);
    `WS05-CMD-START-2` PASS on engine-reported zone counts, marker binding.
  - AF03 PASS: `deck_not_legal` from the Rules Core for illegal commander and
    colour-identity probes; `deck_import_failed` for unreadable decks.
  - HIDDEN_INFO_FORGE `PRINCIPAL_SCOPED`, attribution `NONE`, four established
    requesters, no findings.
  - RNG_REPLAY_FORGE `ACKNOWLEDGED_ENGINE_SEED`, engine readback, `rng_credit: true`.
  - Native receipts: forge direct 150/150, mechanism 67/67 at `e15f37d6`.
- Readiness packet updated to the observed figures; the XMage column is explicitly
  the committed pre-#283 artifact and its bytes were not regenerated.
- WS17 manifests resealed from the integrated tree.

## Wrong-reason audit

- AF03: refusals carry the Rules Core's own messages; the colour probe is the
  non-basic, non-legendary `Shivan Reef`, so colour identity is isolated; the
  `Black Lotus` wrong-reason pattern is gone.
- Principal scoping: content-only distinctness. The negative control (one
  identical content view with every binding field varied) must stay
  `distinct_state_views = 1`; it does.
- Seed: the acknowledgement is the engine readback; reject/divergence fail closed;
  unseeded launches clear a stale binding.
- START-2: counts come from the marked principal's `zones.hand` and
  `zones.library_size`; the guard inputs are persisted.

## Open (not claimed)

- AF04–AF09, AF11 for Forge; PB-07, PB-09; the 44 BLOCKED starting-state rows.
- XMage current-boundary column is the pre-#283 run; PR #283 carries the
  remediation and its own runtime verification. Not re-run here.
- Lab PR #286 CI is pending at this read-back; record its terminal state.

## Exact next action

Read PR #286 CI to terminal state and record it. Then stop for Coordinator
routing: XMage is a separate battlefield and is not started here.
`PRODUCTION_PROVIDER = NOT SELECTED`; `ARCHITECTURE_FREEZE = NOT CLAIMED`.
