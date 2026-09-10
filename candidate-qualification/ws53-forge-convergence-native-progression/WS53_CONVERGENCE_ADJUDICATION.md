# WS53 — XHIGH Convergence Adjudication (Milestone B)

- Adjudicator: read-only `foundry-adjudicator`, XHIGH lane. No writes/edits/commits performed by adjudicator.
- Worktree `/home/moeen/code/ws53-forge-convergence-native-progression`, branch
  `ws53/forge-convergence-native-progression-20260910`, adjudicated at Milestone A HEAD
  `5dbe2d73bbd1576e6a343011e641a1b93dde3356` (on top of `66d5aa44`).
- Scope: draft convergence matrix (11 deltas, `DRAFT_PENDING_XHIGH`) + proposed WS53 chained
  overlay / runner / gates / C1–C4 fresh-evidence plan. No engine mutation, no Full107, no credit,
  no Freeze, no provider selection.
- **Verdict: PASS** (plan satisfies source-lock/lineage/overlay-ordering/restore-boundary/
  fresh-evidence contract, subject to binding corrections below).
- Runtime `BEHAVIOR_CREDIT=0/107`, `FULL107=NOT_RUN`. Full107/broad runs NOT READY until C1–C4 +
  ledger close and Coordinator authorizes next scope.

## Evidence inspected by adjudicator (read/test first)

Lineage/graph/show-stat for `5dbe2d73`, `c3864218`, `e636e705`; current-tree Repair-01 overlay
(zero-add label, cardinality guard, index range check, `priority_binding` event; anchor
application + required markers); R1F report §§2–5,10–11; R1F runtime + negative witnesses
(MINTED-22/77 recurrence machine-caught); R1f pytest (14); static gate; R1F postfix regression
(10 rows); WS50 donor files via `git show e636e705:` (overlay incl. idempotency comment +
`WS50_OVERLAY_REPAIR01_NOT_APPLIED` check; 933-line runner incl. subject-scoping +
`structural_cap=256` + byte-identical `--runners` check; static gates; Checkpoint C summary
with RUN10 repair proof; B 92f / C 495f journals; `WS50_C_INTENT_V17.json` 18 entries);
base generator (`Broker` single-add line 204, `decisionSeq`, single DECISION_FRAME emit),
ws25 PASS rewrite (grounds binding anchor), `sessionSnapshot` pure getters, R1e probe
(`behavior_env` entry modes, `Driver.ritual()` bound 8, structural-pass cap 64,
`offered_for_digest` kind/actor/options-only, `finish()` taxonomy); WS51 disposition
(`RESTORE_PATH_REJECTED` scoped; replacement = restore strictly before first decision-bearing
step or natural start; `rules_authority_gate:null`); WS47 contract fixtures
(`PILOT_CHOOSE_MODE` NATIVE_STATE_LOAD turn1 precombat_main; `PILOT_MULLIGAN`
NATURAL_GAME_START pregame/mulligan turn0; `WS05-MP-BLOCK-4` NATIVE_STATE_LOAD turn1
combat/declare_blockers).

Falsification challenges attempted and resolved: residual WS50-repair need (none — fail-loud
absence, strictly weaker form); D04 timing/determinism perturbation (pure getters,
deterministic seq, env-only RNG — plus one masking caveat → C4 hardening); scenario-B
rehabilitation (falsified — load IS at decision-bearing precombat_main); natural-start
sufficiency (confirmed strongest boundary, but C-shape has zero blocker frames → correction);
missed SEMANTIC_CONFLICT (none — only porting constraints + fixture-bound negative
invalidation).

## Q1 — Omit WS50 Repair-01 hunk — CONFIRM

Anchor non-existence proven (current overlay has zero code `nativeOptions.add(sa)`; base adds
exactly once; post-fix provider 1 add/1 label). WS50 exact-count guard would fail-loud if
attempted — omission is required avoidance of forbidden resurrection. Guard-strength ordering
strictly favors current tree (WS50 single-add only, no guards). Chained-position interaction:
discard/metadata anchors all lie outside `Broker.choosePriority` seen-block; `once()`
containment sound for those hunks. Ordering: WS48 overlay first, WS53 chained second, never
reversed. **Binding:** WS53 overlay asserts `PRIORITY_DOUBLE_ADD_OLD` absent (fail-loud if
matched) as defense-in-depth.

## Q2 — D03/D04 orthogonality — CONFIRM with binding hardening

(a) D03 touches discard path only — orthogonal confirmed. D04 additive payload only; old-driver
digest ignores new fields. D04 **is** a new hidden-information surface (provider-side
per-principal projection absent in WS48); WS51 NO_IMPACT does not cover it. Implementer C4
rerun (not NO_IMPACT) **correct and required**. (b) Timing/determinism: read-only getters,
identical `decisionSeq` increment, env-only RNG, single emit per frame — replay preserved under
fixed seed. **Correction:** `CHOOSE_NEW` try/catch degrades to `UNAVAILABLE`/null without
fail-closed → C4 must assert **zero `UNAVAILABLE`/null-snapshot frames** on credited path; C2
must prove offered-digest stability despite larger payload.

## Q3 — D06 SUPERSEDED_BY_WS51 — CONFIRM

`PILOT_CHOOSE_MODE` = NATIVE_STATE_LOAD at turn1 precombat_main, a decision-bearing step (B
frames 6–24 occur in restored step). Downstream native declares do not rehabilitate the prefix.
Strictly-pre-first-decision rehabilitation does not apply to scenario-B as defined; a different
fixture/mode would need Coordinator approval + fresh evidence. Scenario-B intent mechanics may
be reused diagnostically, never credited. **Binding:** credited WS53 runner allowlists
`NATURAL_GAME_START` only (explicit `--allow-diagnostic-restore` required otherwise, journal
marked non-crediting); `BASE_FIXTURE` PILOT_CHOOSE_MODE entry + `INTENT_B` not selectable as
Objective B witness.

## Q4 — NATURAL_GAME_START as Objective B boundary — CONFIRM with material correction

Natural start is the strongest native-progression boundary (zero restore; WS51 F5 explicitly
allows "natural start per WS50"). Earliest-practical-boundary rule does not obligate a restore-
seeded alternative. Structural PASS prefix is probative waiting, not skipped entry.
**Correction:** WS50-C shape is **insufficient** for BLOCK-4 class — C journal has 3
`declare_attacker` and **zero `declare_blocker`** (canonical decks offer no blocks). Fresh WS53
intent on `PILOT_MULLIGAN` must be re-derived to force a natively-entered `declare_blocker`
frame with CombatUtil-legal options; attacker-only + discards cannot close Objective B.
Implementer note: natively solvable within NATURAL_GAME_START (e.g. second Rograkh cast {0}
held as blocker); no state-load, no legality reconstruction; else return to Coordinator.

## Q5 — Evidence carry-forward — CONFIRM all three, with exact scope

(a) R1f static gate + pytest + witness **rerun fresh** on converged provider (same compilation
unit touched); old `WS48_R1F_*` JSONs become historical. (b) WS50 journals/digests are
source-lock-bound (pre-Repair-01 tree + weaker repair) — equality as pass criteria forbidden;
`offered_digest` shape/kind-coverage may guide design only. (c) R1e bounded rows:
**TARGETED_REQUALIFICATION_REQUIRED** — one bounded 10-row probe (5 TRANSCRIPT_COMPLETE /
3 BLOCKED_AT / 1 EXPECTED_FAIL_CLOSED_PASS / 1 retained PROBE_FAIL) with identical
verdict/frames/consumed/offered_digest + anti-echo invariance; R1f 14-NO_IMPACT ledger stays
historical; WS53 authors its own impact ledger. No Full107.

## Q6 — Missed SEMANTIC_CONFLICT/UNKNOWN — CORRECT (none new; one invalidation + five constraints)

`SEMANTIC_CONFLICT=0`, `UNKNOWN=0` stand. Draft misses corrected as binding:

1. **Negatives re-derived, never verbatim.** neg-zero (frame-25 declare) / neg-multi (frame-7
   choose_mode) expectations are fixture-bound to `PILOT_CHOOSE_MODE`. D05 mechanism ports as
   `SAFE_ORTHOGONAL_PORT`; expected sites/frames/keys are `EVIDENCE_ONLY_NO_PORT`, re-derived
   fresh on natural start. C3 lists re-derived expectations only.
2. `--runners` byte-identical check + transport import repointed to current-tree probe + WS53
   runners dir; static-gates `--root` default replaced by explicit WS53 paths.
3. Structural cap 64→256 documented as intentional divergence (C needed 470 passes/495f);
   per-frame `structural_passes` audit + `__TERMINATE__` semantics retained; R1e rerun proves
   identical digests under converged cap.
4. Terminal taxonomy preserved (`HARNESS_BOUNDED_CLOSE` = harness EOF signal, not engine
   defect); R1e verdict equivalence kept; no reclassification of retained rows.
5. Ritual path scoping: credited path exercises NATURAL_GAME_START ritual only;
   NATIVE_STATE_LOAD ritual unreachable without diagnostic flag.
6. ws25 PASS-anchor ordering: generate → ws25 → WS48-overlay → WS53-chained → javac, with
   fail-loud anchor checks; WS53 overlay never touches priority binding region.

## Corrected classifications (all CONFIRM; D05 split)

D01/D02/D11 `SUPERSEDED_BY_WS48_REPAIR01` (D02 + doubled-add-absence assertion; D11 rerun as
C1); D03/D04 `SAFE_ORTHOGONAL_PORT` (D04 + C4 `UNAVAILABLE`-absence); D05
`SAFE_ORTHOGONAL_PORT` for driver core/subject-scoping/comparator/taxonomy, D05-neg-expected-
values as `EVIDENCE_ONLY_NO_PORT`; D06 `SUPERSEDED_BY_WS51` (+ entry-mode allowlist); D07
`SAFE_ORTHOGONAL_PORT` (+ blocker-bearing re-derivation); D08 `SAFE_ORTHOGONAL_PORT` (+ explicit
paths); D09/D10 `EVIDENCE_ONLY_NO_PORT`.

## Authorized port list (ordering constraints binding)

1. WS53 chained overlay (new WS53-owned file): DISCARD + metadata hunks ONLY; repair hunk
   OMITTED + doubled-add-absence assertion. Never touch WS48-owned/pinned/WS47 files.
2. WS53 runner (new WS53-owned): driver core + subject-scoping + `script_position=front` +
   KIND_FAMILIES + comparator + taxonomy; repointed checks; credited allowlist
   `PILOT_MULLIGAN/NATURAL_GAME_START`; fresh blocker-bearing intent (not `INTENT_C`
   verbatim, not `INTENT_B` credited).
3. WS53 static gates: explicit WS53 provider/journal paths; fresh journals only.
4. WS53 build script: authored (D09 donor), pinned order, WS53 paths, digest checks.
5. Forbidden: D01/D02 hunks, D06 credited setup, D10 equality gates, verbatim
   neg-zero/neg-multi expectations, verbatim build scripts/absolute paths.

## C1–C4 gate requirements (fresh at WS53 HEAD, zero import)

- C1: static gate (incl. provider check + mutate-check) + 14 pytest + non-first ACT witness
  (LAST of ~8 identical-sa ACTs; Java + engine tripwires) + negative double-add caught.
- C2: (i) bounded R1e 10-row rerun identical + anti-echo; (ii) fresh NATURAL_GAME_START
  sequence with fresh blocker-bearing intent + structural-pass audit + replay zero-divergence.
- C3: re-derived zero-match + multi-match + unsupported-kind self-terminate +
  replay-mismatch comparator detection, all on natural start with fresh expectations.
- C4: per-frame adversary zero violations + positive control + planted-leak DETECTED +
  fallback audit + zero `UNAVAILABLE`/null-snapshot frames.

## AUTHORITY_GATE items

None detected. No ambiguous MTG Rules policy; all mechanics are harness/adapter/engine-design
under existing authority. `rules_authority_gate:null` undisturbed. Future blocker-ordering/
legality questions go to Sol High only if genuinely Rules-ambiguous.

## Adjudication fields

- `root_cause_class`: UNKNOWN (plan adjudication; no new runtime failure; referenced defects
  retain Repair-01 `PROVIDER_ADAPTER_DEFECT` and WS51 joint `HARNESS_DEFECT` /
  `ARCHITECTURAL_UNSUPPORTED` + contributing adapter — never upgraded without evidence).
- `first_failing_boundary`: none for plan; referenced: Repair-01 `Broker.choosePriority`
  opaque-index mapping; BLOCK-4 `PhaseHandler` declare_blockers entry bypass via
  `devModeSet`-positioned restore.
- contract: plan PASS subject to binding corrections; `BEHAVIOR_CREDIT=0/107`, `FULL107=NOT_RUN`.
- `shared_or_provider_specific`: provider-adapter-specific (ephemeral generated provider
  composition); no shared engine/contract change; harness WS53-owned.
- `minimal_repair_surface`: none pre-implementation; corrections are plan constraints.
- `repair_priority`: n/a; implementation priority C1 → R1e rerun → C2 blocker sequence →
  C3 negatives → C4 adversary → impact ledger.
- `recommended_execution_tier`: bounded qualification tier (fresh builds vs read-only pin,
  prebuilt-class reuse, no Full107, no Freeze/provider action).
- `validation_corpus`: C1–C4 + WS53 impact ledger; WS47 denominator untouched; Full107 not
  authorized (WS51 §13).
- `full107_or_broad_run_readiness`: NOT READY.
