# Engine Pin Divergence — Fact Package

**This package establishes facts only. It adjudicates no Magic: The Gathering rules question
and recommends no resolution.** Deciding whether a described engine behaviour is a defect, and
which engine should be adopted, is a Rules-authority and Coordinator decision.

Measured at `origin/main` = `7055740ec2f08d4864bf7e200f7b48ace521fe57`.

---

## 1. The question

Four open issues report `RULES_CORE_DEFECT` findings against pin
`b19596980f2734496ea1896504253e1bdd2756dd`, while CI builds
`f79e4168902e65063034b21be6f4585397fd43b3`. Do the defect reports apply to the engine CI
actually builds?

**Answer: the pins differ, and they are on a single linear line — the issues are filed against
an ancestor of the CI pin, not against a divergent engine.** The decision does not resolve to a
single yes or no; it splits. §4.

---

## 2. Pin inventory

`git grep -oE '\b[0-9a-f]{40}\b'` yields ~2,900 distinct 40-hex strings, and the most frequent
are **MTG card Oracle IDs**, not commits. Exactly three are engine commits.

| Pin | Occurrences | Role |
|---|---:|---|
| `f79e4168…` | 29 | **current CI pin** — `config/rules_engines.json:47` |
| `b1959698…` | 181 | prior pin; the pin all four issues claim |
| `db134b97…` | 173 | oldest pin; sealed historical evidence |

### 2.1 `f79e4168…` — authoritative, and genuinely consumed

- `config/rules_engines.json:47` — the sole machine-readable authority (`:6`).
- Four workflows checkout and **identity-assert** it, e.g.
  `.github/workflows/meta-qualification.yml:51,67`:
  ```yaml
  ref: ${{ env.XMAGE_COMMIT }}
  run: test "$(git rev-parse HEAD)" = "$XMAGE_COMMIT"
  ```
  Also `external-engine-integration.yml:34,40`, `xmage-full-game-conformance.yml:39`,
  `xmage-real-4p-smoke.yml:45`.
- Runtime identity: `engine-bridge/…/XmageProvider.java:12` (`ENGINE_COMMIT`), both bootstrap
  scripts, and the three `run_*.py` runners.
- Ten test files assert it as a literal.

### 2.2 `b1959698…` — prior pin, and one **live machine-readable boundary**

Not authoritative any more (`config/rules_engines.json:5` lists it under
`known_stale_pointers`). But `src/commander_lab/qualification/current_boundary/source_lock.py:29`
still pins it as `XMAGE_CANDIDATE_COMMIT`, and
`tests/qualification/test_xmage_mp_candidate_repin_20260929.py:92-98` **actively requires** the
live pin to differ from it. That is a deliberate, tested separation, not drift.

### 2.3 `docker/` carries no literal pin — by design

`docker/xmage/Dockerfile:11-13` and `docker/forge/Dockerfile:15-19` declare `ARG ENGINE_COMMIT`
with **no default** and fail closed on absence (`:19-22`), resolving the pin at build time via
`scripts/docker_resolve_engine_pin.py`. Good design; noted so it is not mistaken for a gap.

---

## 3. Lineage — ESTABLISHED

Objects resolve in the local Mage clone (`/home/moeen/code/mage-ws33`), not the Lab repo.

```
  db134b9737e9…  2026-09-14  tree 4c7cae47  WS212 Rules-RNG explicit-seed authority
        |  +29
        v
  b19596980f27…  2026-09-25  tree 04c00f25  RG-06A hidden-state restore handoff
        |          <-- the pin all four open issues claim
        |  +13  (F-18, F-19, F-20, F-21 integration)
        v
  f79e4168902e…  2026-09-29  tree 18c3e8e7  PR #24 candidate
                     <-- the pin CI actually builds
        |  +55  (F-22, F-23)   [NOT merged; remote branch only]
        v
  fcfde9dad30f…  2026-09-29  tree ba0d02bd  PR #26 F-22/F-23 successor
```

Verified with `git merge-base --is-ancestor` and `git rev-list --count`:

- `b1959698` **is an ancestor of** `f79e4168`; the reverse is false. `f79e4168..b1959698` = 0 commits.
- `db134b97` is an ancestor of both. `git merge-base b1959698 f79e4168` = `b1959698` itself.
- **Zero divergence on any pair.** Single branch, three known points.

### 3.1 What changed between the two pins

`git diff --shortstat b1959698...f79e4168` → **41 files, +1789 / −23**

- **11 production source files.** `Game.java` is **+45/−0, pure addition** (two new `default`
  methods). `GameImpl.java` +60/−4. `SacrificeAllEffect.java` +13/−3. `Initiative.java` +5.
  Six `Tempt*.java` card classes.
- **24 test files, all additions**, incl. `CommanderZoneApnapTestBase.java` (+267),
  `SimultaneousSacrificeApnapTestBase.java` (+224), `InitiativeLeavesGameTestBase.java` (+185).
- 5 research/handoff docs.

Diff facts bearing on the four issues — **stated as diff facts, not as findings**:

- `git diff --name-only b1959698...f79e4168 -- '*Combat.java'` → **empty.** No `Combat.java` change.
- In `GameImpl.java`, the `checkStateBasedActions` hunk is confined to the **commander-zone** SBA
  loop, annotated `704.3 + 101.4`. No battle/protector hunk appears.
- `GameImpl.leave()` gained a `takeInitiative(...)` block — the F-20 change.
- `Game.getOpponents(...)`'s existing body has **zero modified lines**.
- Corroborated by the Lab's own lock,
  `qualification/xmage-mp-candidate-repin-20260929/SUCCESSOR_SOURCE_LOCK.json:58`:
  `"integration": "NOT merged; bounded port (global Game.getOpponents change rejected)"`.

---

## 4. Defect-report applicability — the split

| Issue | Title | Created (UTC) | Pin claimed |
|---|---|---|---|
| #327 | F-20 initiative not passed on when its holder leaves | 13:07:02Z | `b1959698…` |
| #328 | F-21 simultaneous "each opponent" choices not in APNAP order | 13:27:30Z | `b1959698…` |
| #334 | F-22 a battle keeps a protector who left the game | 15:04:03Z | `b1959698…` |
| #335 | F-23 players who left this turn still count as opponents | 15:04:12Z | `b1959698…` |

### 4.1 Established facts

1. **All four state `b1959698…`, which is 13 commits behind the CI pin. The stated pin does not
   equal the CI pin.** `DIRECTLY_VERIFIED`.
2. **No issue claims its pin is current.** #327: *"The Lab XMage pin is not moved. The repin is
   a separate step."* #328: *"The Lab pin is not moved."* #334: *"(not moved)."* #335 states the
   pin without a currency claim. `DIRECTLY_VERIFIED`.
3. **The issues straddle the repin.** The Lab pin moved in commit `738cfaf5`
   (2026-09-29T14:44:23Z, merged via PR #337). #327 and #328 predate it; #334 and #335
   postdate it. `DIRECTLY_VERIFIED`.
4. **The Lab's own lock already treats #327 and #328 as integrated.**
   `SUCCESSOR_SOURCE_LOCK.json:47-59` maps F-20 → `merged unchanged` and F-21 →
   `NOT merged; bounded port (global Game.getOpponents change rejected)`.
   `DIRECTLY_VERIFIED`.
5. **#334 and #335 have no integration record on `main`.** Their only artifacts live on an
   unmerged branch. `DIRECTLY_VERIFIED` by absence.
6. Both Lab SHAs named by the issues (`9d5b17af`, `b31f144b`) are genuine ancestors of `HEAD`.
   The authors worked against real history. `DIRECTLY_VERIFIED`.

### 4.2 How this resolves the original question

- **#327 and #328** were filed against a pin CI no longer builds, and the Lab's own successor
  lock claims F-20 was integrated and F-21 partially integrated into `f79e4168`.
- **#334 and #335** were also filed against `b1959698`, were opened *after* the repin, and are
  the named `findings` of an unmerged branch proposing a third pin.

**All four are filed against an ancestor of the engine CI builds.** That is a materially
different situation from "filed against the wrong engine", and the audit's earlier one-line
wording implied the latter. Corrected here.

---

## 5. The pending re-pin

`origin/sol/xmage-f22-f23-repin-20260929` @ `7ce42274e7c6`, **not merged**, 19 commits behind
`main`, `diverged` (ahead 89, behind 19). It changes `config/rules_engines.json` from
`f79e4168…` to `fcfde9dad30f…` and adds
`qualification/xmage-f22-f23-successor-repin-20260929/SUCCESSOR_SOURCE_LOCK.json` whose
`findings` name **#334 and #335 by tracker number**.

31 changed files — precisely the literal-consumer surface: the 4 workflows,
`config/rules_engines.json`, `XmageProvider.java`, two Java tests, both bootstrap scripts, the
three `run_*.py` runners, the 7 `tests/unit/*` pin assertions — and it **enables two
previously-`@Disabled` bridge regressions** (`XmageMultiplayerBattleTest.java`,
`XmageMultiplayerVoteTest.java`), which correspond to the F-22/F-23 findings.

`fcfde9da` is a linear descendant of `f79e4168` (55 ahead, 0 behind), consistent with the lock's
`parent_commit` claim. **One discrepancy, reported unresolved:** `gh api .../commits/fcfde9da`
returns parent `9cb5fb9e9558…`, while the lock asserts `parent_commit: f79e4168…` — that is the
merge base / ancestor, not the direct parent. Whether that imprecision is a defect or shorthand
is not adjudicated here.

---

## 6. Impact surface if the pin changes again

**Ten test files** assert a literal current pin:
`tests/qualification/test_xmage_mp_candidate_repin_20260929.py:14`,
`tests/unit/test_xmage_full_game.py:29`, `test_xmage_compatibility_provider.py:9`,
`test_xmage_variable_player.py:21`, `test_ws_a1r_pin_authority.py:30`,
`test_ws_arclose_d1_authority_drift.py:23`, `test_ws223_cardinality_regression.py:44`,
`test_ws_a1d_docker_pin_authority.py:31`, plus two Java tests.

**Four workflows** and **six runtime/boot files** carry literal pins.

**Records to reseal:** `config/rules_engines.json`, the successor lock, `WS17_SHA256SUMS`,
`qualification/SHA256SUMS`.

**Must NOT be invalidated** (sealed, and policy forbids rewriting them): the 16 files under
`qualification/final-current-boundary-20260927/`, `docs/architecture_freeze_readiness_20260927/`,
the WS218 replay tapes, `RETENTION_PREDICATES.json`, and
`src/commander_lab/qualification/current_boundary/source_lock.py:29`.

`tests/qualification/test_residual_xmage_repin_20260925.py` is already fully superseded — all
three of its pin tests are permanently skipped by design and name their successor in the skip
reason. That is correct sealed-history behaviour, **not** a defect.

---

## 7. Not established

1. **Whether any of the four defects is real, and whether any still reproduces on `f79e4168` or
   `fcfde9da`.** Rules-authority and runtime verification; explicitly out of scope. The §3.1 diff
   facts are *inputs* to that determination, not the determination.
2. What the issues' post-creation edits changed — timestamps were compared, comment bodies were
   not diffed.
3. Whether `fcfde9da` is sound or a good target. It is not in the local object store; only
   read-only `gh api` metadata and compare were used. No build, no test run, no tree inspection.
4. The `parent_commit` imprecision in the unmerged lock.
5. Conflict/drift assessment of the re-pin branch against current `main`.

## 8. The open decision

For the Coordinator and the Rules-authority tier, per issue: whether the described behaviour is
a Rules-Core defect at all, whether the `f79e4168` delta already addresses it, and whether the
`fcfde9da` branch should be adopted. This package supplies the lineage, the delta, and the
integration records. It does not answer them.
