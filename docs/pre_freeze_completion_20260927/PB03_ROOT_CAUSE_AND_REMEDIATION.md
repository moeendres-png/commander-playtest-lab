# PB-03 — root cause, correct layer, and remediation design

Date: 2026-09-27
Status: root cause **established and evidenced**; implementation **not started** (see §7)
Classification: `CODE_DERIVED` from current source at `origin/main` + WSR22 evidence head `208341c6…`

---

## 1. Claim under test

WSR22 recorded PB-03 as the largest decision-relevant asymmetry: 33 XMage FULL107 rows `BLOCKED`
because *"the Lab execution path exposes no generic starting-state injection (bridge reports
`starting_state_injection_supported=false`)"*, while Forge executes 79 rows to PASS.

**The symptom is confirmed. The stated cause is wrong, and the wrong cause points at the wrong fix.**

| Claim | Verdict |
|---|---|
| 33 XMage rows are `BLOCKED` | **TRUE** — `PROVIDER_BLOCKERS.json` `blocked_rows.xmage` has exactly 33 entries |
| the rows are blocked by an *execution seam* problem, not an XMage Rules-capability limit | **TRUE** and correctly classified by WSR22 |
| the seam is *absent* because the bridge reports `starting_state_injection_supported=false` | **FALSE** — the seam exists, is production-wired, and publishes a machine-readable dimension manifest |
| flipping that flag would be the fix | **FALSE and forbidden** — see §4 |

## 2. The seam exists and is production-reachable

`engine-bridge/src/main/java/org/commanderlab/xmage/XmageNativeStateRestoration.java` (1381 lines,
Lab-owned, not XMage-owned) implements explicit, fail-closed, **engine-native** starting-state
restoration. It is wired into the production path by `XmageFullGameSession.java`, and four sibling
production classes consume it: `XmageTemporalProgressionDriver`, `XmageCausalStackReconstruction`,
`XmageCausalEliminationReconstruction`, `XmageControlDivergenceReconstruction`, plus
`XmageHiddenStateRestoration`.

Its own design contract (`XmageNativeStateRestoration.java:40-93`) states the properties that make
this the *right* mechanism and not a Rules-authority violation:

- no reflection into privates, no fabricated history events, no outcome injection, no legality bypass;
- post-placement `Game.applyEffects` plus `Game.checkStateAndTriggered` run **before** any credit;
- credit requires an **exact readback match** with field-level compare and digests;
- scaffolding decks are construction vehicles, never fixture content;
- pilot-facing observation stays principal-scoped through `XmageFullGameStateRedactor`, with
  honeycard adversarial non-leakage tests.

Critically, it **already publishes a machine-readable dimension manifest** —
`dimensionsPayload()` at line 1026, `schema_version: native-state-restoration-dimensions-1.1.0`,
with `supported_dimensions[]` and `unsupported_dimensions[]`, alongside
`starting_state_injection_supported: false` (line 1028).

So the bridge says, in machine-readable form, exactly which starting-state dimensions it can and
cannot construct. **Nothing consumes that manifest at the qualification boundary.**

## 3. The actual cause: a fixture-id prefix hardcode in the runner

`scripts/run_current_boundary_qualification.py:385` (WSR22 evidence head):

```python
if fixture_id.startswith(("WS05-MP-", "WS05-CMD-ZONE-", "WS05-CMD-DMG-", "WS05-CMD-ELIM-")):
    reason = ("no current-boundary execution seam: the effective obligation requires a "
              "frozen mid-game starting state, and the Lab execution path does not expose "
              "generic starting-state injection (the XMage bridge reports "
              "starting_state_injection_supported=false). ...")
    rows.append(non_executed_row(record, candidate=candidate, outcome="BLOCKED", reason=reason, ...))
```

and at line 450 the same shape for `NATIVE_MICRO_ROWS` (the 15 `MICRO_*` rows).

Four facts follow, and they change the remediation:

1. **The outcome is decided by a string prefix on the fixture id.** No capability is consulted, no
   dimension is checked, and the bridge is never asked. The row's status is a property of its *name*.
2. **The reason text is misleading about the mechanism.** It attributes the block to the global
   capability flag. That flag is truthfully `false` — but it is false because *generic* injection of
   an *arbitrary* frozen position is unsupported, which is the correct and desirable answer. The
   dimension-scoped seam that these particular rows need is supported and available.
3. **There is a duplicated, dead constant.** `full107.py:58` defines
   `INJECTION_BLOCKED_FAMILIES = ("WS05-MP-", "WS05-CMD-ZONE-", "WS05-CMD-DMG-", "WS05-CMD-ELIM-")`
   and it is **never referenced anywhere in the repository**. The runner hardcodes the same tuples
   inline. Two expressions of one semantic, one of them dead — a second, smaller defect in its own
   right.
4. **This is a qualification-harness limitation being reported as a candidate capability gap.** The
   campaign's own taxonomy separates *capability difference* from *evidence asymmetry* and
   *qualification-harness limitation*. PB-03 was filed under the first framing; the evidence places
   it in the third.

## 4. What must NOT be done

- **Do not flip `starting_state_injection_supported` to `true`.** It is a truthful statement that
  generic arbitrary-position injection is unavailable. Flipping it to unblock a qualification run is a
  fabricated capability claim — a production-reachable legality/capability lie, forbidden by
  AGENTS.md §2. Two dedicated tests currently assert it stays `false`
  (`XmageNativeStateRestorationTest:800,802,879`, `XmageFullGameBridgeContractTest:45`); those tests
  are correct and must stay.
- **Do not reconstruct starting states adapter-side.** The restoration must keep going through
  `XmageNativeStateRestoration` so the engine remains the sole authority.
- **Do not shrink the denominator.** `WS47_PROVIDER_DENOMINATOR_107.json` carries
  `denominator_decreased_to_bypass_blocker: false`, and `materialization.py` raises if that flag is
  not exactly `false`. The denominator stays 107.
- **Do not transfer credit from adjacent mechanisms.** WSR22 was right that
  `XmageCausalStackReconstruction` and friends reach *adjacent* mechanisms but are not the same
  obligation. Each row must be executed as itself or stay BLOCKED.

## 5. Correct layer

**Primary: the candidate-neutral Lab qualification harness** —
`src/commander_lab/qualification/current_boundary/full107.py` and
`scripts/run_current_boundary_qualification.py`.

**Secondary, only for rows needing dimensions the bridge does not yet support: the Lab-owned XMage
bridge** `engine-bridge/src/main/java/org/commanderlab/xmage/XmageNativeStateRestoration.java`.

**Not the XMage repository.** `engine-bridge/` lives in the Lab repo and is the Lab's own Java
component that drives XMage over JSONL; the restoration runs inside the XMage JVM using XMage's own
public/native setup and game-load APIs. No XMage source change is implied by the 18 admission
candidates below. Only genuinely engine-internal gaps would reach XMage, and none is demonstrated yet.

This is also the reuse-first answer: `REUSE_AS_IS` for the restoration seam and its dimension
manifest; `EXTRACT_AND_GENERALIZE` for a dimension-admission check; `NEW_IMPLEMENTATION_REQUIRED` for
nothing at this stage.

## 6. Remediation design

**Step 1 — dimension admission replaces the prefix hardcode.** Introduce one shared constant (in
`full107.py`, exported, with the dead `INJECTION_BLOCKED_FAMILIES` either used or deleted — never
left as a second expression) and replace the `startswith` decision with an explicit per-row
**required-dimension** declaration. Admission compares each row's required dimensions against the
bridge's live `dimensionsPayload()`:

- every required dimension in `supported_dimensions` → row is **routed to the real seam** and
  executed; its outcome is whatever the engine actually produces (`PASS`, or `FAIL` — never
  coerced to `PASS`);
- any required dimension in `unsupported_dimensions` → row stays `BLOCKED`, and the reason names
  **the specific missing dimension**, not a blanket family and not the global flag;
- the manifest is unavailable or unparsable → **fail closed** to `BLOCKED` with that exact reason.

**Step 2 — honest expected transition, per the bridge's own manifest.** This is a projection, not a
promise; each row must still be executed to learn its real outcome.

| Family | n | Bridge support | Projected disposition |
|---|---|---|---|
| `WS05-CMD-ZONE-*` | 12 | battlefield/graveyard/exile placement, hand identity, command-zone commander prior-cast counts | **admitted → executed** |
| `WS05-MP-*` | 6 | player count, seats, life totals, turn-1 temporal allow-list, active/priority binding | **admitted → executed** |
| `MICRO_COSTS`, `MICRO_MANA_PAYMENT`, `MICRO_PRIORITY`, `MICRO_ZONE_CHANGES` | 4 | no stack/counters/attachments needed | **likely admitted → executed** |
| `MICRO_STACK`, `MICRO_TRIGGERS`, `MICRO_REPLACEMENT`, `MICRO_PREVENTION`, `MICRO_COPY`, `MICRO_MODES`, `MICRO_CONTINUOUS_EFFECTS`, `MICRO_STATE_BASED_ACTIONS`, `MICRO_CONTROL`, `MICRO_COMBAT`, `MICRO_RULES_RANDOMNESS` | 11 | `stack spells` and `attachments and counters` are **unsupported**; `controller/owner divergence` unsupported; `temporal points outside the qualified turn-1 allow-list` unsupported | **remain genuinely BLOCKED** unless those dimensions are added to the bridge |

So the realistic ceiling for step 1 alone is roughly **22 of 33** rows leaving `BLOCKED`. The
remaining ~11 need new restoration dimensions in the Lab bridge — a larger, separately scoped piece
of work that must preserve every fail-closed property in §2 and must be justified dimension by
dimension against a concrete blocked obligation, not speculatively.

**Step 3 — verification obligations.** Fail-before reproduction of all 33 `BLOCKED` rows; positive
tests for admitted rows reaching the real seam; **negative** tests proving (a) an unsupported
dimension still yields `BLOCKED`, (b) a missing/unparsable manifest fails closed, (c) a stale or
mismatched `requested_state_digest` fails closed, (d) the global capability flag is still `false`,
and (e) a malformed or unknown fixture id is never silently admitted; principal-scoped hidden
information and honeycard non-leakage re-verified; Rules-RNG seed binding and replay identity
preserved; multiplayer state (2–5P, bounded 6P) preserved; and the denominator asserted still 107
with `denominator_decreased_to_bypass_blocker = false`.

**Step 4 — requalify only the impacted rows**, then recompute the comparison matrix and the AF06 /
AF08 / AF10 gates that PB-03 touches. No blanket 107+107 rerun.

## 7. Why implementation did not start here

Not difficulty. Three verified blockers, in order:

1. **No authorized branch.** The successor integration must land on `main` before the PB-03 driver
   exists on any integration surface: `full107.py`, `run_current_boundary_qualification.py` and the
   `current_boundary` package exist **only on the WSR22 branch**, not on `main`. Writing them into
   the WSR23 integration-hygiene branch would pollute a branch whose entire purpose is to stay
   minimal and mergeable, and would create work that cannot reach `main` through the authorized path.
2. **No publication path.** `git switch -c*`, `git checkout -b*`, `git worktree add*` and `git push*`
   are all `deny` in the root policy, and no `FOUNDRY_*` launcher context exists, so `safe_push` gate 6
   cannot be satisfied. See `CAMPAIGN_STATE.md` §11.
3. **Runtime evidence would be unpushable.** Java 21, Maven and XMage 1.4.61 *are* present here, so
   the 33 rows could in principle be executed locally — but an unpublishable, unreviewable,
   unsealed evidence set must not be presented as qualification. `UNKNOWN` and `NOT_RUN` are not
   `PASS`.

The specification above is therefore the deliverable: a layer-correct, reuse-first, fail-closed
design with a per-row projection, ready to execute the moment an authorized branch and publication
path exist.

## 8. Classification of PB-03

| Field | Value |
|---|---|
| category | **qualification-harness limitation**, mis-filed as a candidate execution-seam gap |
| candidate | `XMAGE` (the affected lane); the defect itself is Lab-owned and candidate-neutral |
| affected gates | AF06, AF08, AF10 |
| affected rows | 33 (12 `WS05-CMD-ZONE-*`, 6 `WS05-MP-*`, 15 `MICRO_*`) |
| first failing boundary | `scripts/run_current_boundary_qualification.py:385` (WSR22 evidence head) |
| root cause class | `HARNESS_DEFECT` |
| decision-critical | **YES** — it is the single largest contributor to the XMage/Forge evidence asymmetry |
| Blocks provider comparison | **YES**, until rows are executed or honestly shown to need unsupported dimensions |
