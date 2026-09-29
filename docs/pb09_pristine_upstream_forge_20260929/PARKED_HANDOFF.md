# PB-09 — parked checkpoint / resume handoff

Date: 2026-09-29
Machine-readable checkpoint: `.foundry/PB09_PRISTINE_FORGE_PARKED_20260929.json`
Status: **parked by user instruction.** This document is a resume receipt, not an analysis and not a decision.

---

## 1. Source lock at parking

| Item | Value |
|---|---|
| Lab `origin/main` | `878125ab3c75ee2af2358dbaa8d11282617c050e` (tree `d987b2edaa9aaaa505781fc41667468b1c5114c6`) |
| PB-09 branch | `glm-max/pb09-pristine-forge-20260929` |
| PB-09 HEAD / TREE | `dfed3f437c2731f57e1b357b0b4ae8e2b32ab115` / `c94f696d1318c828f041fba139ed419244644bcb` |
| Remote branch | `dfed3f43…` — **equal to local HEAD** |
| Working tree | **clean**, nothing untracked |
| main merged into branch | yes (normal merge, no rebase, zero overlap with PB-09 surfaces) |
| PR #299 | **OPEN, DRAFT, MERGEABLE** — `DRAFT_DO_NOT_MERGE` |
| Exact-head CI | decision-workflow-contract, infrastructure, mutation-detection, quality, security, windows-runtime: **pass**; exact-main-admission skipped |
| Unresolved review threads | none |

---

## 2. PB-09 status — two separate things

**Technical qualification: `COMPLETE_TO_REACHABLE_BOUNDARY`.**
The pristine pinned upstream candidate has been genuinely runtime-observed and source-locked. The evidence gap *"what does the actual pristine pin do?"* is closed.

**Coordinator adjudication: `OPEN`.**
This is not another engineering task. The open question is:

> Which Forge identity should be treated as the production candidate for the Architecture-Freeze comparison?

Four identities, never collapsed:

| Role | Commit | Tree |
|---|---|---|
| `UPSTREAM_FORGE_BASELINE` (attribution/control baseline) | `a37a865a5328…` | `4471ff06…` |
| `COMMANDER_LAB_FORGE_FORK` (production fork candidate) | `ef958ee91ac…` | `fc3387bf37…` |
| `PINNED_BRIDGE_SOURCE` (Rules-Core byte-identical to the baseline) | `4753bb7c72e…` | `4cd539f1c5…` |
| `BRIDGE_EVIDENCE_HEAD` (PR #5, Draft, untouched) | `e15f37d6b2b…` | `a1d4d4a8fe…` |

The pin manifest was **not** repinned. `PRODUCTION_PROVIDER = NOT SELECTED`, `ARCHITECTURE_FREEZE = NOT CLAIMED`.

---

## 3. Pristine runtime results (preserved, not paraphrased)

**FULL107 — 107 rows, denominator unchanged** (`FULL107_PRISTINE_PIN_RESULTS.json`):

`PASS 1 · FAIL 4 · UNKNOWN 58 · BLOCKED 44 · CRASH/TIMEOUT/PROTOCOL_FAILURE 0 · TOTAL 107`

- **PASS** — `PLAYER_COUNT_4P`: a real 4P Commander lifecycle under Protocol 2.0.0, reaching an external PRIORITY decision with engine-offered options bound.
- **FAIL** — `PLAYER_COUNT_2P`, `PLAYER_COUNT_3P`, `PLAYER_COUNT_5P`: provider refusal `player_count_unsupported` ("this bridge qualifies exactly four players"). `WS05-CMD-START-2`: a 2P obligation blocked by the same refusal, so CR 103.8a's draw-skip postcondition was **never exercised** — an unmeasured obligation, *not* a Rules finding about pristine Forge. 6P is a bounded secondary count recorded outside the denominator.

**AF matrix** (`AF00_AF11_PRISTINE_PIN.json`):
`AF00 PASS · AF01 UNKNOWN · AF02 UNKNOWN · AF03 FAIL · AF04 UNKNOWN · AF05 UNKNOWN · AF06 UNKNOWN · AF07 UNKNOWN · AF08 UNKNOWN · AF09 UNKNOWN · AF10 PASS · AF11 FAIL`
(AF01's single non-PASS invariant is `rules_randomness_core_owned`, because the provider truthfully reports `seed_supported=false`.)

**AF03 = FAIL, precisely:** after a **successful legal control import**, the pristine candidate **accepted** an illegal Commander deck — `Hill Giant` as commander, and 99× `Shivan Reef` under a mono-white commander (isolating colour identity). It **refused** unknown card names, a short mainboard and an empty mainboard. Measured statement: deck-size and card-name validity are enforced at this import boundary; Commander format legality is not. This is observed candidate behaviour, **not** a Rules ruling, and must not be generalised beyond the probed import boundary. Differential: the fork lane reaches PASS on the corresponding gate because **Lab work (PR #5) added the repair**.

**Other runtime facts:** 2P/3P/4P/5P/6P all attempted; non-4P refused by the pristine bridge surface. Hidden-information content is principal-separated and non-overlapping and an unknown observer id reveals nothing, but there is **no `is_actor` marker and no observer envelope**, so requester-binding attestation is missing and the gate stays **UNKNOWN, not PASS** (and is not a demonstrated leak). Every bound decision was engine-offered. Rules RNG is **UNCONTROLLED** (`seed_supported=false`, nothing acknowledged) → **no RNG credit**. Replay and event-log export are **refused**. Actual-card corpus: **0 behavioural executions**; import/construction is not behaviour evidence. Native suite: **59 tests, 59 passed**, bound to the pin with `RULES_CORE_MAIN_SOURCE_TREES_IDENTICAL`.

---

## 4. Candidate differential — Rules Core vs bridge surface

**Rules-Core differences (compile/runtime evidence):**
The current Lab bridge **does not compile** against the pristine Rules Core (rc=1). It requires `PlayerController#assignCombatDamage`, `CombatDamageSelection`/`CombatDamageDecisionView`, `AmountDistribution*` (WS40), the `DividedAllocation*` CR 601.2d seam (WS217), and the fork's `MyRandom` seed surface. These are fork-only engine surfaces.

**Bridge/provider-surface differences — `BRIDGE_DIFFERENCE`:** seed support, target/mode/trigger-order selection, starting-state injection, scenario injection, `min_players`, concession. These exist on the fork-lane provider surface and not on the pinned bridge. **They must not automatically be read as pristine Rules-Core incapabilities** — the pristine Rules Core was never exercised through a surface exposing them. This distinction is essential for tomorrow's adjudication.

Comparison was per-dimension and owner-classified. **Aggregate PASS counts were deliberately not compared**, because the columns executed different engines.

---

## 5. GLM experiment status (experiment, not routing)

- `GLM_DIRECT_EXECUTION = YES` — `opencode-go/glm-5.3`, max, direct manual session (no `FOUNDRY_*` context). GLM performed the identity/provenance/build phases correctly, including dual-remote commit verification and byte-identity proof of all six Rules-Core modules.
- `GLM_FOUNDRY_RUNTIME_ACTIVE = NO` — **not** a Foundry executor. No routing-policy change; GLM is **not** registered as canonical production automation.
- Handoff point: the GLM contingent was exhausted after the runtime-reachability receipt. The successor executor `opencode-go/space-bunny-free` (max) authored the qualification runner, executed FULL107, ran the native suite, the falsification campaign, the AF matrix, the lane-B compile probe, and the PR. No observation was re-attributed.

---

## 6. Divergence recorded for tomorrow (important)

A **second, independent PB-09 workstream** exists: branch `muse-xhigh/pb09-pristine-forge-20260929`, **PR #297** (Draft, head `95f29200906`). It is a divergent history that does **not** contain this branch's head, modifies the same shared `current_boundary` files, and reports **PASS 5/107** with a build-derived-identity claim — **disagreeing with this workstream's PASS 1/107**.

This workstream did **not** merge, overwrite, rebase against or supersede that branch, and did not touch its PR. Two PB-09 evidence sets now exist for the same pinned candidate; they must be reconciled before either is treated as *the* pristine baseline.

---

## 7. Resume point

**First action:** the Coordinator adjudicates the Forge candidate identity (pinned upstream `a37a865a` vs Lab fork `ef958ee9`) using `qualification/pb09-pristine-upstream-20260929/` together with the already-qualified fork evidence, and reconciles the parallel PR #297 packet.

Do **not** today/next-without-a-ruling: merge #299, repin the manifest, change AF11, port fork APIs to pristine, repair pristine Commander legality, start a new FULL107 campaign, select a provider, or claim a freeze.

---

`PB09_TECHNICAL_QUALIFICATION = COMPLETE` · `PB09_COORDINATOR_ADJUDICATION = OPEN` · `PRISTINE_FORGE_RUNTIME_OBSERVED = YES` · `GLM_DIRECT_EXECUTION = YES` · `GLM_FOUNDRY_RUNTIME_ACTIVE = NO` · `PRODUCTION_PROVIDER = NOT SELECTED` · `ARCHITECTURE_FREEZE = NOT CLAIMED`
