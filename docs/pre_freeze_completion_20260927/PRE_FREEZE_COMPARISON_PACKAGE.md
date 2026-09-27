# Pre-Freeze current-boundary candidate comparison package

Date: 2026-09-27
Evidence base: WSR22 immutable head `208341c6124674046787f3a4b1d699c98c286a27`
Lab `main` at `8d2aacd530ea47d3ef39f4ab4f974f301da3cf24` / tree `b54ea3992bd2d58712c3e6d5e6daa63349802ab1`
Coordinator adjudication applied: `CURRENT_RULES_AUTHORITY = 2026-09-25`

**This package contains no score, no ranking and no preferred provider.** It reports what was
executed, what was not, and what the asymmetry between the two candidates actually consists of.

---

## 1. Source Lock

| Field | Value |
|---|---|
| Lab `main` HEAD / TREE | `8d2aacd5…` / `b54ea399…` |
| Lab evidence head / TREE (WSR22) | `208341c6…` / `d8f6c80a…` |
| XMage pin / license | `b19596980f2734496ea1896504253e1bdd2756dd` / **MIT** |
| Forge pin / license | `forge-2.0.14`, Rules-Core `a37a865a53280dd8ad6fad3384d69611e8c5a42f` / **GPL-3.0** |
| Forge **executed** commit | `moeendres-png/forge@ef958ee91ac` (master, 2026-09-21) — Rules-Core pin **satisfied**; Lab bridge-source pin `4753bb7c…` **not** satisfied, divergent by 328 commits (§7.1) |
| Qualification boundary | `commander-lab.pre-freeze-qualification/2.0.0` |
| Transport protocol | `2.0.0` |
| FULL107 successor contract | `FULL107_SUCCESSOR_CONTRACT_v1_0_6.json`, sha256 `f898abb7…` |
| Denominator | 107, `denominator_decreased_to_bypass_blocker = false` |
| Rules authority | `MagicCompRules 20260925.txt`, effective 2026-09-25, sha256 `8d860e45…` |

## 2. FULL107 — denominator-complete accounting

Every one of the 107 rows carries exactly one explicit outcome. 30+44+33 = 107 and 79+21+7 = 107.
Zero `CRASH`, `TIMEOUT` or `PROTOCOL_FAILURE` on either candidate. No row is omitted and no hidden
bucket exists.

| Outcome | XMage | Forge |
|---|---|---|
| PASS | **30** | **79** |
| FAIL | 0 | 0 |
| UNKNOWN | **44** | **21** |
| BLOCKED | **33** | **7** |
| CRASH / TIMEOUT / PROTOCOL_FAILURE | 0 | 0 |
| **Total** | **107** | **107** |

Per-row disposition split (both candidates, 107 rows):

| Disposition | xmage | forge | rows |
|---|---|---|---|
| `SAME_SEMANTICS` | PASS | PASS | 25 |
| `NON_COMPARABLE` | PASS | UNKNOWN | 5 |
| `NON_COMPARABLE` | UNKNOWN | PASS | 28 |
| `NON_COMPARABLE` | UNKNOWN | UNKNOWN | 16 |
| `NON_COMPARABLE` | BLOCKED | PASS | 26 |
| `NON_COMPARABLE` | BLOCKED | BLOCKED | 7 |

**The 79-vs-30 gap is not a capability ranking.** Only 25 of 107 rows are `SAME_SEMANTICS`; the
other 82 are `NON_COMPARABLE`, and it is overwhelmingly in the `NON_COMPARABLE` bucket that Forge
scores higher. A candidate scoring higher on rows that are *not comparable* has not demonstrated
better Rules behaviour — it has demonstrated a larger executed surface. This is exactly the
Coordinator's caution, and it is confirmed by the evidence.

## 3. AF00–AF11 standing

| Gate | Name | XMage | Forge |
|---|---|---|---|
| AF00 | SOURCE_AND_BUILD_LOCK | PASS | **PASS → REQUIRES_RECONCILIATION** (PB-09) |
| AF01 | PROTOCOL_HANDSHAKE | **UNKNOWN** | PASS |
| AF02 | PLAYER_CARDINALITY | PASS | PASS |
| AF03 | RULES_AUTHORITY | PASS | PASS |
| AF04 | LEGAL_ACTION_AND_DECISION_BOUNDARY | **FAIL** | UNKNOWN |
| AF05 | HIDDEN_INFORMATION | UNKNOWN | UNKNOWN |
| AF06 | GENERAL_RULES_CORRECTNESS | UNKNOWN | UNKNOWN |
| AF07 | ACTUAL_CARD_BEHAVIOR | UNKNOWN | UNKNOWN |
| AF08 | MULTIPLAYER_COMMANDER | UNKNOWN | UNKNOWN |
| AF09 | RNG_REPLAY | UNKNOWN | UNKNOWN |
| AF10 | RUNTIME_EVIDENCE_RELIABILITY | PASS | PASS |
| AF11 | INTEROP_LICENSE_TOPOLOGY | **FAIL** | **FAIL** |

Gate detail that matters for selection:

- **AF11 fails on both candidates, and the recorded evidence names licensing**: *"XMage MIT, Forge
  GPL-3.0 (recorded in the source lock)"*, plus a per-candidate request-body convention difference
  (XMage reads `payload`, Forge reads `params`) and different decision-identity fields. Both
  candidates do satisfy the process-isolation half (genuine separate external processes over
  stdin/stdout JSONL, no engine code embedded in Lab).
- **AF04 FAIL on XMage** is driven by PB-01: the generic Protocol-2 lane only exposes an external
  decision surface when the game is created with `external_control=true`; otherwise
  `get_legal_actions` fails closed with `LEGAL_ACTIONS_UNAVAILABLE` and the engine would self-play.
  WSR22 proved the lane works when the parameter is set, so this is a *contract-documentation* gap,
  not an XMage Rules-capability gap. The fail-closed behaviour is correct and must be preserved.
- **AF01 UNKNOWN on XMage** is PB-04: the *generic* comparison lane truthfully reports
  `seed_supported=false` while the production-reachable full-game lane reports `seed_supported=true`.
  Lane-scoped capability reporting is the fix; the values themselves are not in conflict.

## 4. Multiplayer, hidden information, replay/RNG, actual cards

| Surface | XMage | Forge | Notes |
|---|---|---|---|
| Independent live lifecycles | 2P, 3P, 4P, 5P | 2P, 3P, 4P, 5P | executed |
| Bounded 6P lifecycle | executed | executed | bounded, not the primary benchmark |
| START-2 (v1.0.6) | executed | executed | reusable without rerun |
| Principal-scoped state read | 4 seats, live 4P | 4 seats, live 4P | executed |
| Per-scenario hidden channels | not exposed | not exposed | **PB-06**, both sides |
| Native hidden/replay suites | 168 tests green | 217 tests green | 385 total |
| Replay export in a live game | executed | executed | executed |
| Per-fixture clean-process replay twin | unproven | unproven | **PB-08**, both sides |
| Actual 100-card Commander deck | engine-validated | engine-validated | engine owns deck legality |
| Effective 29-card corpus | unexecuted | unexecuted | **PB-07**, both sides |

## 5. Meta-Qualification v1 standing

Treated as existing, complete regression infrastructure exactly as instructed. No catalogue
expansion: no new mutation class was added, because this campaign encountered no concrete
production-relevant fault seam that the existing eight domains would miss.

Invariant preserved and verified as consumed: `kill_rate` and `catalog_coverage` are separate
metrics, and 100% `kill_rate` would be insufficient if any catalogue mutation were `NOT_RUN`.
Current v1 completion is **8 attempted / 8 killed / 0 survived / 0 NOT_RUN / catalogue coverage 1.0**
across the eight v1 domains: Legal Actions, Decision Identity, Rules RNG, Semantic Events, Principal
Observation, Post-State, Terminal Outcome, Live Hidden Information. This proves detector
effectiveness for this bounded catalogue, **not** universal full-rules MTG correctness.

## 6. Known FAIL / UNKNOWN / BLOCKED

**FAIL (3 gate instances, 2 distinct causes)**
- AF11 on XMage and AF11 on Forge — licensing/topology, recorded evidence names MIT vs GPL-3.0.
- AF04 on XMage — PB-01, missing `external_control=true` contract requirement on the generic lane.

**UNKNOWN**
- XMage 44 rows, Forge 21 rows; gates AF01 (XMage), AF04 (Forge), AF05, AF06, AF07, AF08, AF09.
- PB-01, PB-02, PB-04, PB-05, PB-06, PB-07, PB-08.

**BLOCKED**
- XMage 33 rows (PB-03), Forge 7 rows.

**No result anywhere was coerced toward PASS**, and no evidence was promoted without an impact
adjudication.

## 7. Provider blocker register, re-derived

| ID | Candidate | Class | Fresh status |
|---|---|---|---|
| PB-01 | xmage | `BOUNDED_NON_BLOCKING` | confirmed; affects AF01/AF04/AF11 |
| PB-02 | both | `BOUNDED_NON_BLOCKING` | confirmed; interface shape, not Rules behaviour |
| **PB-03** | xmage | was `UNKNOWN_IMPACT` | **reclassified `HARNESS_DEFECT`.** Cause is a fixture-id prefix hardcode, not a missing seam. See `PB03_ROOT_CAUSE_AND_REMEDIATION.md` |
| PB-04 | xmage | `BOUNDED_NON_BLOCKING` | confirmed; lane-scoped reporting fix |
| PB-05 | forge | `BOUNDED_NON_BLOCKING` | **its reason text is refuted** — see PB-09 |
| PB-06 | both | `UNKNOWN_IMPACT` | confirmed still open; 5 Forge seams + `WS05-CMD-MULL-2` |
| PB-07 | both | `UNKNOWN_IMPACT` | confirmed still open; 29-card corpus |
| PB-08 | both | `UNKNOWN_IMPACT` | confirmed still open; 5 replay/RNG rows |
| **PB-09** | forge | **NEW — `EVIDENCE_INTEGRITY_DEFECT`** | Forge's **Rules-Core** pin is satisfied, but its **Lab bridge-source** pin is not. See §7.1 — this is the mechanical cause of the apparent Forge capability lead |

### 7.1 PB-09 resolved: the Forge evidence-build asymmetry has an identified mechanism

PB-09 was raised in this campaign after reading the WSR22 evidence. It has since been traced to a
concrete, verifiable divergence in `/home/moeen/code/forge` (`moeendres-png/forge`, the Lab-owned
Forge candidate/bridge repository).

| Identity | Commit | Date | Status |
|---|---|---|---|
| Upstream Rules-Core pin (`secondary_engine.commit`) | `a37a865a532` — `[maven-release-plugin] prepare release forge-2.0.14` | — | **ancestor of the executed commit** — pin satisfied |
| Lab bridge-source pin (`secondary_engine.bridge_source.commit`) | `4753bb7c72e` — tip of `candidate/forge-2.0.14-h4f-integration-20260912` | 2026-09-12 | **NOT an ancestor of the executed commit** — pin not satisfied |
| **Actually executed** (WSR22 `candidate_identities.forge_commit` and `FULL107_FORGE_RUNTIME_LOG_INDEX.json`) | `ef958ee91ac` — `master`, "Merge pull request #3 from moeendres-png/merge-wsr19-into-master" | 2026-09-21 | 9 days newer than the pin; **328 commits** from pin to executed tip |

The two bridge identities are on **divergent histories**: `4753bb7c` does not appear anywhere in
`ef958ee9`'s history. The executed commit additionally carries wsr15–wsr19 Lab work absent from
the pinned commit — 2–5P multiplayer conformance (`a29afd5e5a1`), six-player support (`7af7b322bcc`),
CI qualification (`f7a8c6c702a`), and promotion packets (`9c41bff2809`, `04784906f09`).
`ef958ee9` is an ancestor of `wsr24/forge-candidate-evidence-closure-20260927` = `18bba95a`, which is
exactly the `historical_wsr20_reference.evidence_tip` that WSR22 records.

**What this does and does not mean.**

- It does **not** mean Forge violated its Rules-Core pin: `a37a865a` is an ancestor of the executed
  commit, so the executed build did include the pinned upstream release.
- It **does** mean the executed Forge candidate was a materially different Lab bridge than the one
  `config/rules_engines.json` pins — one carrying 328 commits of additional Lab multiplayer and
  six-player engineering.
- It therefore supplies a **mechanical, candidate-side explanation for the 79-vs-30 gap**: the Forge
  side executed substantially more unpinned Lab bridge engineering, including the 2–5P and six-player
  work, while the XMage side executed at exactly its pinned commit (`b1959698…`, verified matching).
  This is the "evidence asymmetry" the Coordinator cautioned against reading as capability ranking,
  now with a specific cause rather than a suspicion.
- It also means Forge's `AF00 SOURCE_AND_BUILD_LOCK = PASS` and `AF11` rest on an **unreconciled
  bridge identity**, and that Forge's reported commit is operator-supplied
  (`engine_commit_source=env:FORGE_ENGINE_SHA`) rather than build-proven, so the evidence cannot
  demonstrate which bridge it ran.

**Remedy, in order.** (1) Decide which bridge identity is the candidate: either repin
`config/rules_engines.json` to `ef958ee9` as the intended candidate, or re-run Forge evidence at
`4753bb7c`. (2) Make the bridge report a **build-derived** commit/tree instead of reading
`FORGE_ENGINE_SHA`. (3) Only then is a Forge-versus-XMage comparison sound. Do **not** edit
`ef958ee9` into a provenance field to make it match a pin — the executed commit is a historical fact
and stays recorded.


PB-09 is the highest-priority item after PB-03, because it is not a coverage gap — it means part of
the Forge evidence may describe a candidate that is not the pinned one, which would make any
Forge-versus-XMage comparison unsound at its foundation.

## 8. Same-case comparison

**Exact comparable denominator: 25 of 107 rows (`SAME_SEMANTICS`), on which both candidates PASS.**

That is the only sound basis for comparison. On those 25 rows the two candidates are equivalent.
Everything else is `NON_COMPARABLE` (82 rows) and differences there are *evidence asymmetry* or
*interface shape*, not demonstrated Rules divergence.

No actual Rules divergence between XMage and Forge is demonstrated anywhere in this evidence set.
That is itself a decision-relevant fact: the evidence does not currently distinguish the two
candidates on Rules correctness in either direction.

Engine-local identifiers excluded from comparison: `game_id`, `engine_game_id`, `player_id`,
`decision_id`, `option_id`, `revision` (PB-02).

## 9. Evidence quality

| Classification | Applies to |
|---|---|
| `DIRECTLY_VERIFIED` | the 2026-09-25 Rules capture — re-fetched live in this session, effective-date text and rule 103.8a confirmed verbatim; both candidates' provider-side card-legality and lifecycle rejections observed live |
| `RUNTIME_VERIFIED` (via `DIRECTLY_VERIFIED` runs) | FULL107 executed rows, 2–5P + bounded 6P lifecycles, START-2, hidden-info 4-seat reads, replay export, AF01 invariant execution, 385 native engine tests |
| `CODE_DERIVED` | PB-03 root cause, PB-09, the dead `INJECTION_BLOCKED_FAMILIES` constant, gate arithmetic |
| `TECHNICALLY_CONFORMANT` | Protocol-2 lifecycle shape, process isolation, principal-scoped redaction contracts |
| `EXTERNALLY_RULE_VALIDATED` | rule 103.8a semantics across 2026-08-19 → 2026-09-25 (`semantic_delta: NONE`) |
| `MODELED` | the ~22-of-33 PB-03 row projection in §6 of the PB-03 document — a projection from the bridge's published dimension manifest, **not** an executed result |
| `SYNTHETIC` | none promoted as evidence |
| `UNKNOWN` | 44 XMage rows, 21 Forge rows, gates AF01/AF04–AF09 as tabulated, PB-06/07/08 |

## 10. Architecture implications — facts only

1. **Licensing is a live architectural fact, not a preference.** AF11 fails on both candidates and its
   own evidence names MIT versus GPL-3.0. For a system intended to execute real Commander decks and
   be maintained as a repository, that difference bears directly on distribution. It is recorded as a
   fact; the Coordinator owns the weighting.
2. **Neither candidate currently dominates on Rules correctness.** No Rules divergence is
   demonstrated, and the headline 79-vs-30 split lives in `NON_COMPARABLE` rows.
3. **The largest asymmetry is Lab-owned.** PB-03's 33 rows are blocked by a Lab harness hardcode, and
   the remediation is a Lab harness change plus, for ~11 rows, a Lab bridge change. Closing it improves
   XMage's *measured* standing without any XMage modification.
4. **Both candidates already satisfy process isolation**, external-process execution with no engine
   code embedded in Lab. That part of the architecture is settled.
5. **A provider-specific decision-identity shim is required** for any single provider-neutral pilot
   (PB-02). That is interface shape and belongs in the adapter, outside Rules authority.
6. **Forge's build identity is not build-proven** (PB-05, PB-09). Whatever provider is selected, the
   commit-to-build binding should be derived from built bytes, not an environment variable.
7. **Rules authority is now settled and byte-exact** at 2026-09-25 with no qualification-relevant
   semantic delta, so it is no longer a source of schedule risk.

## 11. Freeze readiness

| Question | Answer | Basis |
|---|---|---|
| `PROVIDER_COMPARISON_COMPLETE` | **NO** | comparable denominator is 25/107; PB-03 leaves 33 XMage rows unexecuted; PB-09 leaves Forge's build identity unreconciled |
| `DECISION_CRITICAL_UNKNOWN_REMAINS` | **YES** | PB-03, PB-06, PB-07, PB-08, PB-09, plus AF04/AF05/AF06/AF07/AF08/AF09 not established for either candidate |
| `PROVIDER_SELECTION_READY` | **NO** | only 25 same-semantics rows; no demonstrated Rules divergence to weigh; Forge's executed bridge identity unreconciled (§7.1) |
| `ARCHITECTURE_FREEZE_READY_FOR_COORDINATOR` | **NO** | AF11 unresolved on both; AF06/AF08 (Rules correctness, multiplayer Commander) UNKNOWN on both |

**None of these four is a terminal authority blocker.** Every one is addressable by ordinary
engineering once an authorized branch and publication path exist. The ordered path is:
PB-09 (cheap, unblocks soundness of the comparison) → PB-03 (largest asymmetry, Lab-owned) →
PB-06/07/08 by decision value → AF closure → final current-boundary package.

`ARCHITECTURE_FREEZE = NOT CLAIMED`.
`PRODUCTION_PROVIDER = NOT SELECTED`.
