# Pre-Freeze Completion Campaign — current-state ledger

Date: 2026-09-27
Session role: OpenCode Space Bunny MAX (native `max`), project effort `high`
Workstream: `wsr23-project-integration-hygiene-20260927` (sole writer; see §11 for the authority gate)

This is the Phase B campaign ledger required by the campaign instruction. It is an operational
index, not Source Authority. Every mutable fact below was freshly verified in this session; the
verification command is named for each.

---

## 1. CURRENT_MAIN_SHA / CURRENT_MAIN_TREE

| Field | Value | Verified by |
|---|---|---|
| `origin/main` HEAD | `8d2aacd530ea47d3ef39f4ab4f974f301da3cf24` | `git rev-parse origin/main` |
| `origin/main` TREE | `b54ea3992bd2d58712c3e6d5e6daa63349802ab1` | `git rev-parse origin/main^{tree}` |
| Tip subject | `Merge PR #262: meta-qualification v1` | `git log --oneline -1 origin/main` |

`8d2aacd5` matches the Coordinator's stated current main, so the Coordinator's main is confirmed
fresh; no main movement occurred during this session.

**Local `main` is stale and must not be used as an integration base.** The canonical worktree
`/home/moeen/code/commander-playtest-lab` has local `main` at `586914ea` (`Merge PR #257`), which is
an *ancestor* of `origin/main` `8d2aacd5`. The stale local ref was **not** fast-forwarded: that
would require `git merge`, which the root policy denies. Any successor branch must be cut from
`origin/main`, never from local `main`.

## 2. ACTIVE_PROVIDER_PINS

Authority: `config/rules_engines.json` on `origin/main`, which declares itself *"the sole
machine-readable authority for current engine pins"*.

| Candidate | Pin | License |
|---|---|---|
| XMage (primary) | commit `b19596980f2734496ea1896504253e1bdd2756dd` | **MIT** |
| Forge (secondary) | release `forge-2.0.14`, Rules-Core commit `a37a865a53280dd8ad6fad3384d69611e8c5a42f` | **GPL-3.0** |
| Forge Lab bridge source | `4753bb7c72ea60d653121e0bab989077b4009f9c` (base `a37a865a`) | — |
| Protocol | `2.0.0` | — |
| Maven | `3.9.16` | — |

**PB-05 UNDERSTATED — see §7. The Forge candidate that WSR22 actually executed
(`ef958ee91ac6c9ce0152189f2654bf6e05abf273`) matches neither pinned Forge identity.**

## 3. ACTIVE_PRS

WSR23's own packet classified all 41 open PRs at `c5f9418e` and closed four as proven-superseded
(`docs/project_integration_hygiene_20260927/OPEN_PR_CLASSIFICATION.json`, 41 → 36). Those closures
are durable on the remote. That classification was **not** re-run here: `gh pr list` and
`gh api` are `ask`/`deny` in this session, and the packet is the persisted, provenance-carrying
record. The two PRs that matter to this campaign:

| PR | Head | Role |
|---|---|---|
| **#269** WSR22 | `208341c6124674046787f3a4b1d699c98c286a27` | current-boundary provider qualification evidence; **immutable provenance** |
| **#262** Meta-Qualification v1 | merged as `8d2aacd5` | COMPLETE, integrated in main; regression infrastructure |

## 4. ACTIVE_WORKTREES

173 Lab worktrees (`git worktree list`). `tools/foundry/worktree_inventory.py --fail-on-duplicate-writer`
reports `duplicate_writers=[]` — no branch is checked out in two worktrees, so there is no
competing writer on any surface this campaign touches.

Campaign-relevant worktrees: `wsr23-project-integration-hygiene` (this one, clean),
`wsr22-final-current-boundary-freeze` (at the immutable evidence head), `commander-playtest-lab`
(canonical, local `main` stale).

## 5. CURRENT_CONTRACT_IDENTITY

| Artifact | Blob / sha256 |
|---|---|
| `qualification/CURRENT_PRE_FREEZE_CONTRACT.json` | git blob `3f1ed8d6…`, sha256 `33ad8390…` |
| `FULL107_SUCCESSOR_CONTRACT_v1_0_6.json` | git blob `267909c4…`, sha256 `f898abb7…` |
| `SEMANTIC_FIXTURE_SCHEMA_v1_0_6_SUCCESSOR.json` | git blob `428ed8d5…`, sha256 `8c98b33f…` |
| `AF01_QUALIFICATION_BOUNDARY_V2.json` | git blob `e4388a36…`, sha256 `3eb74212…` |
| `architecture_freeze_gate_catalog_v2.json` | git blob `1b0c7ede…`, sha256 `f7e4ffdc…` |
| `architecture_freeze_contract_v2.schema.json` | git blob `7fde656b…`, sha256 `c9048b05…` |
| `WS47_PROVIDER_DENOMINATOR_107.json` | git blob `5b76e8cd…`, sha256 `803b4026…` |
| `schemas/engine_adapter_protocol.schema.json` | git blob `ea8651f7…`, sha256 `741e0acc…` |
| Qualification boundary | `commander-lab.pre-freeze-qualification/2.0.0` |
| Denominator | **107**, with `denominator_decreased_to_bypass_blocker = false` |

## 6. CURRENT_RULES_AUTHORITY

**`CURRENT_RULES_AUTHORITY = 2026-09-25`** — adopted per the binding Coordinator adjudication, and
**independently re-verified in this session against the live official source.**

| Field | Value |
|---|---|
| Document | `MagicCompRules 20260925.txt` |
| URL | `https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt` |
| Effective date text | "These rules are effective as of September 25, 2026." |
| Bytes / sha256 (WSR22 capture) | 977752 / `8d860e451f20f38865b725b42d82feb714c725373dd8f3b32b8652b3eeb070ca` |
| Applicable rule | 103.8a |
| 103.8a text | "In a two-player game, the player who plays first skips the draw step (see rule 504, "Draw Step") of their first turn." |

**Independent verification performed here (`webfetch`, live official URL, 2026-09-27):** the fetched
document opens with the September 25, 2026 effective-date sentence and contains rule 103.8a
verbatim, character-for-character identical to the text WSR22 recorded. Classification:
`DIRECTLY_VERIFIED_CURRENT_OFFICIAL`.

`RULES_AUTHORITY_CONTRADICTION = RESOLVED`, and the resolution is **convergent** rather than a bare
override: main's receipt and WSR22's capture independently agree that the 2026-08-07 artifact is
superseded, and WSR22 additionally recorded that the previously recorded 20260807 TXT URL now
returns HTTP 404. WSR22 also self-validated its capture pipeline by re-capturing the 2026-08-19 TXT
and matching the repository's own historical hash `4381ad1b…` exactly.

`FULL107_RUNTIME_EVIDENCE_INVALIDATED = NO` — confirmed. Every qualification-relevant rule diffed
between 2026-08-19 and 2026-09-25 (103.8a/b/c, 504.1, 800.4a/j, 508.8) carries
`semantic_delta: NONE`.

## 7. NEW FINDING — Forge source lock does not match the pin authority

This is the most decision-relevant new fact produced by this campaign, and it is **not** in the
inherited blocker register.

- `config/rules_engines.json` (sole pin authority on main) pins Forge at
  `a37a865a53280dd8ad6fad3384d69611e8c5a42f` (Rules-Core) and `4753bb7c…` (Lab bridge source).
- WSR22's `SOURCE_LOCK.json` `candidate_identities.forge_commit` and its
  `FULL107_FORGE_RUNTIME_LOG_INDEX.json` both record the **executed** Forge commit as
  `ef958ee91ac6c9ce0152189f2654bf6e05abf273`.
- `ef958ee9…` matches **neither** pinned Forge identity.

PB-05 classified this as `BOUNDED_NON_BLOCKING` and asserted *"The reported commit matched the
candidate exactly."* Against the pin manifest that assertion does not hold. Because Forge's reported
commit is operator-supplied (`engine_commit_source=env:FORGE_ENGINE_SHA`, not build-proven), the
run cannot be shown to have executed the pinned candidate at all.

Consequence: **Forge `AF00 SOURCE_AND_BUILD_LOCK = PASS` is not supported by the current pin
authority.** This is an evidence-integrity defect, not a Forge capability defect, and it must be
resolved before Forge evidence can be compared to XMage evidence. It is recorded as **PB-09** in
`PRE_FREEZE_COMPARISON_PACKAGE.md`.

The XMage side is clean: WSR22's `xmage_commit` `b1959698…` is exactly main's pin.

## 8. REUSABLE_EVIDENCE

Per the Coordinator's accepted adjudication, and re-checked against current source with no
contradicting drift found. All classification `UNAFFECTED_REUSABLE`, no runtime rerun required.

| Evidence family | Status |
|---|---|
| FULL107 107+107 runtime results | `UNAFFECTED_REUSABLE` (subject to §7 for the Forge half) |
| START-2 v1.0.6 | `UNAFFECTED_REUSABLE` |
| AF00–AF11 matrices | `UNAFFECTED_REUSABLE` (AF00 Forge reclassified — §7) |
| Protocol-2 lifecycle evidence | `UNAFFECTED_REUSABLE` |
| 385 native engine tests | `UNAFFECTED_REUSABLE` |
| XMage runtime evidence (168 native tests green) | `UNAFFECTED_REUSABLE` |
| Forge runtime evidence (217 native tests green) | `UNAFFECTED_REUSABLE` |
| comparison classifications | `UNAFFECTED_REUSABLE` |
| hidden-information evidence | `UNAFFECTED_REUSABLE` |
| replay/RNG evidence | `UNAFFECTED_REUSABLE` |
| successor-inheritance proof | `UNAFFECTED_REUSABLE` |
| provider blocker register | `UNAFFECTED_REUSABLE`, extended by PB-09 |
| provider/adapter/build source locks | `XMAGE UNAFFECTED_REUSABLE`; `FORGE REQUIRES_RECONCILIATION` (§7) |
| Meta-Qualification v1 (8 attempted / 8 killed / 0 survived / 0 NOT_RUN / coverage 1.0) | `UNAFFECTED_REUSABLE` as regression infrastructure |

**Why no runtime rerun is required.** The only accepted change is a Rules-authority *receipt*
change. The receipt records an effective date and a byte-exact hash; it does not alter the contract
blob, the denominator, the protocol schema, the materialization, or any engine pin. The Coordinator
adjudicated `FULL107_BLANKET_RERUN_REQUIRED = NO`, and the source evidence agrees: the rule-level
diff over the qualification-relevant rule set is `semantic_delta: NONE` throughout.

## 9. INVALIDATED_EVIDENCE

| Item | Classification |
|---|---|
| `qualification/pre-freeze-successor/CURRENT_RULES_AUTHORITY.json` at `8d2aacd5` (the 2026-08-07 receipt) | `STALE_RECEIPT` per Coordinator adjudication; **independently falsified** here by live capture |
| Forge `AF00 = PASS` at the WSR22 boundary | `REQUIRES_RECONCILIATION` (§7) — not invalidated, not confirmed |
| `PB-05` reason text ("the reported commit matched the candidate exactly") | `REFUTED` against `config/rules_engines.json` |

Nothing else is invalidated. In particular, no runtime artifact is invalidated by the receipt change.

## 10. MECHANICAL_REQUALIFICATION_REQUIRED

Exactly as the Coordinator scoped it, and no more:

1. Regenerate/reseal `qualification/SHA256SUMS`.
2. Regenerate/reseal `WS17_SHA256SUMS`.
3. Update and run the affected assertions in `tests/qualification/test_pre_freeze_contract_successor.py`.
4. Run directly impacted integrity/meta checks.

All four are consequences of the four conflicting paths identified in
`WSR22_IMPACT_ADJUDICATION.md`. They are *generated or derived* surfaces and must be **regenerated
from the final integrated tree**, never transplanted from either side.

## 11. AUTHORITY_GATE — the campaign's integration spine cannot be executed in this session

This is a hard, verified permission boundary, not a difficulty, and it is recorded here so the next
session resumes from facts rather than re-deriving them.

| Required campaign action | Blocking condition | Verified by |
|---|---|---|
| Publish WSR23 (fast-forward push) | root `opencode.json` sets `git push*` = **deny** | the tool permission layer refused the shape; `opencode.json:88` |
| Create the WSR22 successor branch | `git switch -c*` = deny, `git checkout -b*` = deny, `git worktree add*` = deny | permission layer; `opencode.json:90,91,95` |
| Push / PR / merge any campaign branch | same | — |
| Satisfy `safe_push` gate 6 | this session holds **no** `FOUNDRY_*` launcher context; the run dir `/tmp/foundry-launch-wsr23-project-integration-hygiene-20260927` is **empty**, so no launcher ever acquired a lock | the empty run dir; the absent environment |

**Writer-lock honesty.** `writer_lock.WriterLock(...).acquire()` from this process would satisfy
gate 6. It was not done and must not be done: it would make this process the recorded holder and let
any process self-authorize as a worktree's exclusive writer, collapsing the single-writer guarantee.
That is now recorded in the WSR23 state file's `out_of_scope` so it cannot be mistaken for
unexplored work. `gh api -X POST` is also `deny`, so no PR can be opened through that path either.

What this session *did* complete is recorded in `PHASE_A_FOUNDRY_REPAIR.md` and
`STATE_OWNERSHIP_REPAIR.md`: the launcher refusal was diagnosed at its real layer and repaired, and
the branch now carries honest validation credit. Gates 1–5 and 7–9 of `safe_push` all pass; gate 6
is the only remaining tool-side rejection.

## 12. NEXT_ACTION

1. **Operator:** start a launcher-spawned Foundry *writer* session for
   `/home/moeen/code/wsr23-project-integration-hygiene`, `--workstream wsr23-project-integration-hygiene-20260927`,
   `--state docs/project_integration_hygiene_20260927/WORKSTREAM_STATE.yaml`. Run the single
   safe-push command in `PUBLICATIONS.md` §2, then open the WSR23 PR against `origin/main` `8d2aacd5`.
2. **Then, in a launcher-authorized session:** cut the WSR22 successor branch from `origin/main`
   (never from stale local `main`), transplant the justified WSR22 content with provenance to
   `208341c6…`, adopt the 2026-09-25 receipt, regenerate the two manifests, run only the four
   mechanical requalification items, then PR and merge.
3. **Then:** PB-03, per `PB03_ROOT_CAUSE_AND_REMEDIATION.md` — the remediation is now correctly
   located and must not be implemented as a capability-flag flip.
4. **Before any Forge/XMage comparison is read as capability ranking:** resolve PB-09 (§7).
