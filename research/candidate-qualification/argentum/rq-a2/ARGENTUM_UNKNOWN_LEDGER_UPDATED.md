# RQ-A2 — Argentum Unknown Ledger (updated at terminal state)

`UNKNOWN != PASS`. RQ-A1 items carried forward with RQ-A2 disposition. New RQ-A2 findings
appended as N-A…N-F. Evidence classes per item.

## A. Rules-correctness unknowns

- U1. 23 mechanisms: PARTIALLY ADDRESSED. 13 rules-dense runtime probes green
  (`ARGENTUM_RULES_DENSE_PROBES.json`, DIRECTLY_VERIFIED behavior, exact decision sequences
  recorded). Zero mechanisms `EXTERNALLY_RULE_VALIDATED`. Six authority gates open
  (`ARGENTUM_RULES_AUTHORITY_GATES.md`). Residual: UNKNOWN (official validation).
- U2. CR 800.4a/d remaining-LTB: behavior RECORDED (theft reverts; Watcher silent off
  5-object mass removal; pod continues), `AUTHORITY_GATE-1` open. UNKNOWN (rules).
- U2b. CR 800.4c static-exile: source-cited only, no fixture. `AUTHORITY_GATE-2` open. UNKNOWN.
- U3. Per-opposing-teammate fan-out: behavior RECORDED (fires once, shared 30→29),
  `AUTHORITY_GATE-3` open. UNKNOWN (rules).
- U4. Loyalty/battle excess damage: untouched. UNKNOWN.

## B. Coverage-measurement unknowns

- U5. Card↔behavior linkage: CLOSED as inventory (`ARGENTUM_CARD_BEHAVIOR_LINKAGE.md/.json`):
  13,402 declared / 11,144 canonical / 2,227 generated / 4,532 behavior-linked (~34%,
  strong+heuristic mix) / 7,621 UNKNOWN (~57%). Executable coverage stays UNKNOWN.
- U6. Set-completion %: untouched. UNKNOWN.
- U7. Era dirs: untouched. UNKNOWN.
- U8. Multiplayer/Commander card tests: CLOSED as inventory (10 named multiplayer, 1 named
  commander). Coverage UNKNOWN.
- U9. Full-corpus compile: CLOSED for main sources — every era/core/sdk jar built at the lock
  during RQ-A2 (DIRECTLY_VERIFIED). Test-source compile established per executed scope only.

## C. Player-count unknowns

- U10. 5P/6P runtime: 5P CLOSED for feasibility (init/rotation/priority/Commander/elimination
  green, `ARGENTUM_FIVE_PLAYER_PROBE.json`); 6P smoke only (partial). 5P conformance in the
  qualification sense remains open (feasibility ≠ conformance).
- U11. 2–5P conformance: open. UNKNOWN.

## D. Decision-seam unknowns

- U12. Starting player: CLOSED — configuration-only input (3-seat runtime + static;
  `ARGENTUM_DECISION_FRESHNESS.json`). Tournament procedure external.
- U13. Voting: untouched (absence stands). UNKNOWN.
- U14. Web-client filtering: untouched. UNKNOWN.
- U15. Trigger ordering: CLOSED — AUTOMATIC (engine-determined APNAP/detector order; no
  PendingDecision seam; may/modal/target choices remain authoritative). RQ-A1 matrix row 17
  corrected. Materiality gate open (`AUTHORITY_GATE-5`).
- Freshness (new seam, no RQ-A1 number): CLOSED — F1–F5 fail-closed at runtime
  (exact-id equality, epoch-equivalent rejection messages recorded).

## E. Hidden-information unknowns

- U16. No-leak property: PROMOTED TO DEFECT-FOUND. D1 draw-leak defect (high,
  production-reachable, `ClientEvent.kt:990-1027`); D2 face-down-exile DTO/gym divergence
  gated (`AUTHORITY_GATE-4`); managed Gym path clean (0/0); spectator DTO clean; errors
  clean; decision-status path clean; in-process full-state caveat demonstrated (integration
  must pin `GameGymEnv.observe()`/managed observations). Session/log paths: the same
  `PermanentLeft` descriptions flow into per-player logs (CODE_DERIVED impact extension).
- U17. Hidden names in errors: CLOSED for probed paths (DIRECTLY_VERIFIED, bounded).
- U18. Replay-viewer projection: PARTIAL — spectator DTO clean in probed state; viewer stream
  reuses `SpectatorStateBuilder` (CODE_DERIVED). Full-path adversarial still open.

## F. RNG/replay unknowns

- U19. Round-trip fidelity: CLOSED bounded — 3 games EXACT via fresh fold and via candidate
  `ReplayReconstructor` (codec round-trip, checkpoints, fidelity EXACT) + 7 tamper controls
  all DETECTED. `TECHNICALLY_CONFORMANT (bounded: tested games/decks/seeds; UNKNOWN
  elsewhere)` — never a general guarantee. Existing complements green:
  `CompactReplayReconstructionTest` 2/2, `ReproducibilityTest` 5/5.
- U20. Cross-version stability: untouched. UNKNOWN.
- U21. RNG statistics: untouched. UNKNOWN (low priority stands).
- U22. AbilityId impact: CLOSED with documented holes — semantic identity holds cross-process
  (527 frames canonical-EXACT); transport identity isolated (runtime generate() ids,
  activation resolutionKeys, fixture UUIDs); normalization safe in non-Rules journal layer on
  tested (yield-free) paths; yields/batches over synthetic identities UNKNOWN.

## G. Process unknowns

- U23. Stale-doc blast radius: untouched. UNKNOWN.
- U24. Full-suite green: partial — RQ-A1 254/254 + RQ-A2 executed scopes green (masking 10/10,
  replay/determinism 7/7, all probe games). Full suite NOT_RUN.
- U25. Throughput: untouched. UNKNOWN.

## New RQ-A2 findings

- N-A. Seat-id namespace collision (e<N> seats): CLOSED as N5 control (fails closed, never
  silent). Not a candidate defect. Optional hardening note (reject/advance on collision).
- N-B. `EntityId.generate()` live use (activation `resolutionKey`): CLOSED — identity-only,
  replay-safe. Corrects RQ-A1's "absent from live paths".
- N-C. RQ-A1 decision-matrix row 17 corrected (trigger ordering AUTOMATIC, not INDEX_BASED).
- N-D. Declare-step skip with no attackers: observed (BEGIN_COMBAT→END_COMBAT), gated
  (`AUTHORITY_GATE-6`).
- N-E. DTO/gym face-down-exile divergence: gated (`AUTHORITY_GATE-4`).
- N-F. Test-definition shadowing (e.g. Lightning Bolt): methodology caveat recorded; test
  behavior may exercise a different definition than production.

## Explicit non-unknowns (closed in RQ-A2)

Source locks; harness topology (CPL-side, zero candidate mutation); ENGINE_DETERMINISM,
REEXECUTION, tested-path CONTROLLED_RULES_RNG (DIRECTLY_VERIFIED); commander-shortcut
unreachable (`FORCED_COMMANDER_SHORTCUT_PRODUCTION_REACHABLE = NO`); RNG use-site closure
(no Rules-path bypass; split: tested-path DIRECTLY_VERIFIED, exhaustive CODE_DERIVED);
5P engine feasibility; starting-player seam; freshness fail-closed; trigger-ordering seam
class; card↔behavior inventory.
