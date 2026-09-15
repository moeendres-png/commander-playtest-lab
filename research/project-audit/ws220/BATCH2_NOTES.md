# WS220 Batch-2 notes — integrity of what we run + how we work

Status: 4 read-only subagent surveys + auditor diff-level verification.
Covers H-RULES-01, H-HIDE-01, H-REPLAY-01, H-TEST-01, H-CI-01, H-WS-01,
H-FOUNDRY-01, H-EFF-01, H-ROAD-01, H-MP-01, H-CAND-01, H-EXPL-01 (part).

## C1. Rules authority HOLDS statically; 5 policy narrowings + thin live negatives (H-RULES-01)

- All offered sets originate in engine queries; controller + projection only
  validate membership/revision/actor/bounds; XMage-AI/GUI automation disabled;
  out-of-scope callbacks fail closed on both JVM and Python sides; no second
  engine, outcome injection, silent default, or `sa.resolve`/`AbilitySub`
  substitute found in production-reachable paths (incl. compat-lane
  `XmageBridgePlayer` unreachable from full-game lane).
- Gaps (disposition, not expansions): single-offer shortcut bypasses pilot +
  transcript (Low); mulligan cap, priority mana-withhold, mana pool shortcut,
  prompt-sniff routing (Low); **numeric-domain narrowing to 3 values when
  span>16 (Medium — only observed engine-domain narrowing)**; live-engine
  rejection negatives for only 3/17 classes (Medium-Low; transport generics
  cover wire shapes for all 17); 11/17 classes runtime-unobserved in WS204.
- Pilot RNG clean: seed+seat+offset+class derivation holds, no unseeded
  randomness in production-reachable pilot paths; twin confirmation still
  needed for bit-exact claims (honestly unclaimed).

## C2. Hidden-info assured for XMage lane; 4 GAP/UNKNOWN edges (H-HIDE-01)

- ASSURED: redactor actorView (+D2 grant window, face-down/exile discipline),
  transcript `pilot_state` drop (code + sample + conformance-script gate),
  audit-log schema, error messages (UUID echo only, no hidden echo), cache
  keys (public-only), doctor/probe, oracle isolation (test-only dirs).
- GAP: (1) no name-canary honeycard — 8709-row oracle checks UUID absence,
  a name-only leak passes it; (2) Forge parity — no Forge redactor exists,
  assurance is XMage-only; (3) structural-lane debug/fixture surface
  (`ReplayDebugger`, `known_library_tops`) has no actor scoping; assurance
  claims must not generalize beyond the XMage lane.
- UNKNOWN: engine-internal GameLog/stderr history; historical primary.json
  artifact contents for cross-principal reads.

## C3. Replay requirement honestly PARTIAL; 12 design risks for WS218 (H-REPLAY-01)

- Normative bar = semantic equality (UUID-scrubbed, pilot_state-dropped);
  bit-exact explicitly false everywhere; twins explicitly not replay;
  checkpoint/consumer/gate explicitly absent; injection ban explicit; N=2..5
  noted-not-completed. RNG attribution complete for Rules seed + pilot RNG;
  iteration-order/timestamp/engine-wide/identical-label determinism
  unspecified. Contract NOT provider-neutral as specified (XMage taxonomy,
  seed-binding API, label vocabulary baked in).
- 12 risks recorded (R1 checkpoint undefined … R10 raw-hash field list vs
  `engine_game_id` first … R12 two-definitions coexistence). R10 is the top
  clarification: `raw_result_sha256` over a dict containing per-process UUIDs
  should fail across fresh JVMs, yet 11/12 strict TRUE is reported — the exact
  hashed object must be pinned by allowlist before "raw" is normative.

## C4. Test strategy guard-strong, rules-behavior-thin in unit (H-TEST-01)

- 32-file census: 19 GUARD / 5 CONSTRUCTION / 8 structural-pilot-stub
  BEHAVIOR; zero sampled unit tests execute official MTG rules (by design —
  Rules Core is external). Real rules evidence lives in mvn-verify lanes,
  fresh-JVM matrices, conformance scripts. No per-forbidden-shortcut-class
  regression mapping (generic legal-only gates only). Overfit card names HIGH
  in test_pilots.py. Fuzz/property fully seeded (good). No flaky list/rerun
  policy; risk concentrates in 2 sleep/process tests + JVM lanes.
  `test_impact.py` advisory-only, zero CI consumers; `ci.yml` runs full
  `pytest -q` every push/PR.

## C5. Environment version-recorded, not locked (H-CI-01)

- Ranges everywhere + 6-pin no-transitive lock + floating `eclipse-temurin:21`
  + JDK17-vs-21 skew + 12/16 lanes without PYTHONHASHSEED + pip cache keys
  ignoring runtime.lock. WS213/WS215 "5-6+40 environmental" traced to
  missing-extra/uninstalled-package/CLI-drift classes — harmless to scoped
  PASS, proof the full suite is lane-dependent. Secret scan narrow-but-honest
  (OpenAI-only). Windows lane = 4-file portability slice.

## C6. Retained-47 adjudication (H-EVID-02 core — auditor diff verification)

Strongest form ("47 PASS-equivalents carried") FALSIFIED: CARD_29 and MICRO_13
were never runtime PASS (aggregates all-NOT_RUN, WS205/207 credit 0); rows
carry NOT_RUN→NOT_RUN with deferral rationale + "zero behavior credit
claimed". REPLAY_5 carry PARTIAL→PARTIAL with explicit absent-item lists.
No PASS credit moves.

Weaker form SUBSTANTIATED with three precise defects:
(a) Retention sentences are literally inaccurate: "engine pin unchanged"
(CARD rows, post-WS213-repin) and "Lab paths byte-identical" (MICRO rows;
WS215 changed target tiebreak TD01, mana liveness guard, cardinality inputs).
Substance currently holds at N=4 — behavioral changes confined to rerun
classes (TARGETS, MANA rerun ✓) + N≠4-only inputs — but the sentences are
prose without machine-checked predicates; a future rewrite can inherit the
sentences without the substance.
(b) Retention reasoning is 4P-shaped but unscoped: at N≠4 every retained
row's Lab inputs changed (pod_size, opponents_to_act_before_next_turn,
tiebreak, mana guard). AF02-per-count × AF06/AF07 coverage has a hole the
disposition never states.
(c) No test asserts retained-path stability; the impact argument is
manual-diff-based and will rot.

## C7. Workstream graph: serial stacks, ceremony-heavy micros (H-WS-01)

- Two unmerged stacks (XMage WS203→215, 18 commits/10k files; Foundry
  WS196→200) + 1 parallel (WS197) + WS208 sibling consumed conceptually but
  not in ancestry (WS213 claims WS208 resolution without its commit).
  WS218/WS219 zero-unique placeholders — no drift.
- Bulk is evidence (6.6M lines) not code (1–4k). RQ-C3 slots re-driven 3-4×
  with near-duplicate neutral runs (16/17 zero-offers repeats).
  Micro-streams (WS196 1-commit, WS204 1-commit, WS208 1-commit) wrap tiny
  surfaces in full ceremony. 18-deep unmerged stack + RED integrity gate =
  growing rebase/re-seal burden.

## C8. Foundry: sound split, unproven resumption, dedup available (H-FOUNDRY-01)

- State/volatility split sound (policy stable, state absorbs SHAs/decisions);
  sizes 1–11k reflect complexity. Resumption well-specified but UNKNOWN by
  project semantics (no live-resume trial, no committed token data,
  TOKEN_ECONOMY_BENCHMARK=NOT_RUN). Prompt core ~33KB always-on; biggest
  safe trim is implementer↔AGENTS↔ROUTING dedup (~2–4KB) + keep 14/15
  foundry-execution docs on-demand (already optimal) + skills lazy (already
  optimal). Dynamic context (/work+capsule) is the real lever, already built.

## C9. Efficiency: rebuilds justified, FULL107 withheld, rollup broken (H-EFF-01)

- Maven rebuilds per workstream justified (bridge changed); full source builds
  rare + lineage-proofed. CI repetition × floating deps is the sink, not
  workstream rebuilds. Impact-selection used correctly in seals (scoped
  suites + FULL107 NOT_RUN). Fixture→requirement lookup works (one JSON
  filter); requirement→verdict rollup broken (vocabs + no AF verdicts).
  drift_check live gate; test_impact write-mostly advisory.

## C10. Roadmap: no single document; order needs two corrections (H-ROAD-01)

- Fragments only (mission + freeze contract + successor specs + handoffs).
  Dependencies: comparison needs G01 (YES — ranks ungrounded numbers
  otherwise); Freeze needs WS218 replay (YES — AF09 PARTIAL blocks);
  Freeze needs 16 UNKNOWNs only partially (APNAP/extra-turn/CR800.4/damage
  material; zone-exile/hand/library + partner deferrable with chartered
  successor); comparison does NOT need FULL107 (retire-as-unit stands).
- Post-WS218/219 order: publish WS213/215 + refresh manifests (clear RED) →
  AF09/G01 closure → trigger-rich setup/pilot successors → 135-disposition
  rerun where impact argument thinnest (CARD_29 + MICRO_13 + N≠4) → only then
  comparison; Freeze last.

## C11. Multiplayer scope (H-MP-01): 6P correctly deferred; 10 of 16 UNKNOWNs material

- 16 UNKNOWNs itemized with per-family causes. Material pre-Freeze: APNAP×2,
  extra-turn×2, CR800.4-control×1, damage thresholds×3 (Commander-defining
  loss rules). Deferrable: zone-choice×6 (SBA choose_use proven both ways via
  GY), partner×2 (Ishai uncastable artifact). 6P: mission requires only
  2–5P + fail-closed; WS215 delivers both; defer indefinitely.

## C12. Candidate fairness: neutral bar, unequal practice, no admission procedure (H-CAND-01)

- Same 15-slot denominator + same NO_PROVIDER_READY gate, but XMage has 3
  remediation rounds with twins/seed authority vs Forge 1 round, no twins,
  uncontrolled RNG, earlier-pipeline BLOCKEDs. Genuine maturity gap, but
  without a written bar it is indistinguishable from incumbency bias. No
  third-candidate admission procedure (harness porting, determinism template,
  comparison layer all missing/stale). Mission mandates neutrality as
  principle, not procedure.

## C13. Exploratory assumptions (H-EXPL-01, 5 unstated + 5 untested failure modes)

Twin-MATCH=determinism; engine-owned=engine-correct; oracle-count=no-leakage;
committed-JSON=reviewable; serial-stacking=safe. Untested: variable-player
regression merges green (no CI gate); integrity-gate normalization;
trigger-rich starvation steady-state; third-candidate miscomparison;
capsule/carryover hallucination after compaction.

## Reprioritization after batch 2

- PROMOTE to P0/P1 candidacy: numeric narrowing (needs disposition +
  per-class live negatives), name-canary gap, 4P-shaped retention hole at
  N≠4, G01 re-acquisition, AF rollup computability, RED-gate + CI-4P-only
  (already H-CI-02/03).
- DEMOTE: broad second-engine hunt (clean; keep negative-test growth as
  routine), Forge parity work before WS219 (WS219 owns), prompt-trimming
  beyond dedup (dynamic context already optimal), FULL107 (closed).
- NEW: H-RULES-02 (numeric-domain narrowing disposition); H-HIDE-02
  (name-canary negatives); H-EVID-04 (retention predicates machine-checked +
  N-scoped).
