# WS62 — FORGE SUCCESSOR PIN + CPL REQUALIFICATION — FINAL REPORT (fail-closed bounded)

- Branch: `ws62/forge-successor-requalification-20260911`
- CPL audit base: `e39c7de053573625e51006b917bef43468161752` / `2a94ca9212b27c25231ba8ecacdb592508187d22`
- Old pin: `66caae16015bd403bc0a52fa6689afb5508f74d0` / `40fc8f29ce4de31a964972461db2b48b4221e07f` (read-only, never runtime)
- Successor (only pin adopted): `a9a95db6662c2d28814390a9c0c2f986e39aa8b4` / `2c18327f79e330f2ed167067166ffd42d61b0849` / `moeendres-png/forge` / `/tmp/ws62-forge-src-a9a95db` (verified HEAD/tree/log; one WS59 commit on old pin)
- Policy: `c1a760af21469fc1358dbdb9b821f79dcdfaf2db`
- Validated head candidate: `74ed56ec8ed6a1b42a9ce22126ce418670ce4508` (implementation; terminal validation ran on this clean HEAD; report commit descends and does not promote)
- Terminal verdict: **FORGE_SUCCESSOR_REQUALIFICATION_PARTIAL** — **FORGE_SUCCESSOR_PIN_ACCEPTED=YES**, **FORGE_RQC3_FIRST_WAVE_ENTRY_PREREQUISITES_READY=NO** (exact blocker: A04 full-cast runtime reachability)
- `BEHAVIOR_CREDIT=0/107` · `FULL107=NOT_RUN` · `ARCHITECTURE_FREEZE=NOT_CLAIMED` · `PRODUCTION_PROVIDER=NOT_SELECTED`

## 1. Work completed

1. **Phase A inventory.** Read WS53/WS55/WS55R sources/evidence/build scripts; classified every 66caae consumer as pin authority / build input / runtime input / evidence-only / stale (global manifest + docker + historic scripts untouched per gate); produced `WS62_PIN_IMPACT_LEDGER.json`; created candidate-local `WS62_FORGE_PIN.json` (historical line lacked single authority).
2. **Phase B fresh build.** `mvn -o` successor forge-core+game SUCCESS; generated provider against successor PlayerController (110 callbacks, successor constants); applied WS40→WS48→WS53→WS55→WS62(v2) overlays; compiled provider+helper against successor-first classpath (old-pin fail-closed gate); handshake proves successor-only runtime; digests + `provider.classpath` persisted in `WS62_BUILD_RECEIPT.json`.
3. **Phase C authority.** Rules Core owns all legality; provider translates only. New WS62 transports: conditional concession (`canConcede`→external→`concede`, never unconditional, never direct, never priority-gated) and stack-SA target binding (Human `chooseCardFromStack` parity: resolve authoritative SA via `canTargetSpellAbility`+host-ID, label host Card, fail closed on 0/multiple). Forbidden items verified absent (static + journal censuses). See `WS62_ADAPTER_AUDIT.json`.
4. **Phase D requalification.** Fresh successor probes: C01 875-frame full continuation with counter (target+confirm+exile all ACCEPTED, life 39, Frog exiled, Elves countered, replay 0-div, hidden PASS) and A04 1282-frame native sequencing with 0 fabricated frames; plus engine mvn suites (A04 3/3, C01 2/2, G04 4/4) on successor; plus selection/sequence/hidden/RNG/replay/taxonomy evidence. Historical 17-kind proofs preserved without rerun (no shared change). See integrity/sequence/hidden/RNG/adjudication JSONs.
5. **Phase E gates.** C01 READY (11/11 stages PASS, including payment/counter actually executed — upgrades WS59R NOT_RUN for F/G); G04 READY (engine 4/4 + CPL conditional transport, 2P/3P native, any-time); A04 NOT_READY (engine direct 3/3 PASS but full-cast provider runtime still 0 offers, Serpent 0/0 — honest reachability gap, no synthesis). See prereq JSONs.
6. **Phase F readiness.** Corrected 15 scenarios / 20 kinds (no `may`/generic `ordering`/DAO): 14 READY, 1 NOT_READY (A04 replacement ordering), 0 UNKNOWN. Overall READY=NO (fail closed). See `WS62_FIRST_WAVE_READINESS.json`.

## 2. New findings

- **F1. C01 stack binding must be SA, not Card.** Successor proxy makes host Card pass `canTarget`, but `add(Card)` fizzles (pre-fix run: FoW graveyard yet Elves battlefield). Human binds SA via `chooseCardFromStack`; WS62 provider now does (post-fix: Elves graveyard, countered). First provider-level proof of SA binding for TargetType stack effects.
- **F2. C01 full payment/counter now DIRECTLY_VERIFIED via provider** (life 39, Frog exile, Elves countered), upgrading WS59R F/G NOT_RUN. Hidden pitch IS externally transportable (Frog o0 single-match, P1-only projection).
- **F3. A04 full-cast gap narrows to payment path.** Direct `moveToStack`/`moveToPlay` passes (7|8); natural cast with X=3 via provider (ranged descriptor value=3, 3 G paid, DS+HS present) still yields 0 and 0 offers. `changeZone` equals-gate or payment-path X wiring is the remaining engine scope (no provider repair conformant).
- **F4. Structural-pass cap matters for long games.** Default 256 terminates at ~271 frames; 2048 reaches 875/1282-frame objectives (harness config, no semantics change; stamped).
- **F5. MINTED determinism preserved across pins** (MINTED-3/8/196 stable old→new for same deck+seed).

## 3. Changes

Implementation (committed before validation; HEAD `74ed56ec`):
- `WS62_SOURCE_LOCK.md`, `WS62_FORGE_PIN.json`, `WS62_PIN_IMPACT_LEDGER.json`
- `ws62_provider_overlay.py` (v2: concession + stack-SA binding)
- `Ws62ConcessionTransport.java` (conditional direct transport helper)
- `ws62_build_successor.sh` (successor-fresh build, old-pin fail-closed)
- `ws62_breadth_runner.py` (WS55R-verbatim + successor pin/gate/identity)
- `ws62_successor_runner.py` (shim; superseded by full runner for credited probes)
Evidence (this commit, descends from validated head, does not promote it):
- `WS62_BUILD_RECEIPT.json`, `WS62_ADAPTER_AUDIT.json`, `WS62_SELECTION_INTEGRITY.json`, `WS62_DECISION_SEQUENCE_IMPACT.json`, `WS62_HIDDEN_INFO.json`, `WS62_RNG_REPLAY_IMPACT.json`, `WS62_A04_PREREQ.json`, `WS62_C01_PREREQ.json`, `WS62_G04_PREREQ.json`, `WS62_FIRST_WAVE_READINESS.json`, `WS62_HISTORICAL_ADJUDICATION.json`, `ev-ws62/` (3 journals), this report, `WORKSTREAM_STATE.yaml` (via state.py only).
No other tree paths touched. No global manifest/docker repin. No Forge edits.

## 4. Tests / Evidence

- Fresh build: mvn compile SUCCESS + provider javac SUCCESS + handshake successor-only + digests/classpath gates (DIRECTLY_VERIFIED).
- Engine mvn on successor: A04 3/3, C01 2/2 (non-bypass SA binding), G04 4/4 (all PASS).
- Provider live: C01 875 frames (pitch/target/confirm/exile all ACCEPTED, countered, life/exile verified, hidden PASS, replay 0-div) + A04 1282 frames (0 offers, no fabrication, hidden PASS).
- Static: no AI/GUI/first/random/default/concede-direct/filtering/solver/injection (CODE_DERIVED).
- Labels: DIRECTLY_VERIFIED (runtime), CODE_DERIVED (static/ledger), TECHNICALLY_CONFORMANT where noted; never RUNTIME_VERIFIED.

## 5. PASS / FAIL / UNKNOWN

**FORGE_SUCCESSOR_REQUALIFICATION_PARTIAL** (bounded, fail closed).
- `FORGE_SUCCESSOR_PIN_ACCEPTED=YES` (exact identity, fresh build, no old-pin load, handshake proof).
- `FORGE_RQC3_FIRST_WAVE_ENTRY_PREREQUISITES_READY=NO` (exact blocker below).
- Zero UNKNOWN verdicts in fresh scope; historical UNKNOWN none.

## 6. Remaining blockers

1. **A04 full-cast runtime reachability** (only blocker): engine direct 7|8 proven, but natural-cast provider path still 0 offers/0 counters (1282 frames). Needs Forge-remediation follow-up for full-cast cause/X propagation (packet narrows to `changeZone` equals-gate/payment wiring). No provider repair conformant. Blocks First-Wave entry (A04 scenario).
2. No other adapter/transport blockers known (C01/G04 entry prerequisites met; 12 other scenarios preserved READY).

## 7. Outputs

`candidate-qualification/ws62-forge-successor-requalification/` (see Changes; evidence journals under `ev-ws62/`).

## 8. Dependencies unblocked

- Successor pin accepted for CPL candidate lineage (exact record + fresh build + provenance).
- C01 pitch/target/payment/counter transport proven (unblocks First-Wave C01 execution once A04 dispositioned).
- G04 concession seam transport proven (unblocks G04 execution).
- A04 engine-change packet narrowed for Forge-remediation scoping.

## 9. Exact next action

**Coordinator:** (1) disposition A04 full-cast gap as follow-on Forge-remediation work (packet in `WS62_A04_PREREQ.json` + `ev-ws62/WS62_A04_EVID.json`); (2) confirm RQ-C3/Sol Rules-authority readiness for First-Wave behavior (no behavior credit claimed here); (3) commission WS63 First-Wave execution for the 14 READY scenarios only after (1), or rule A04 out-of-wave. Do not start Full107, Freeze, or provider selection from WS62.

`BEHAVIOR_CREDIT=0/107` `FULL107=NOT_RUN` `ARCHITECTURE_FREEZE=NOT_CLAIMED` `PRODUCTION_PROVIDER=NOT_SELECTED`
