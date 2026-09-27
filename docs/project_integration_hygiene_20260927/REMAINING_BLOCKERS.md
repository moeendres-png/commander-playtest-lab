# WSR23 — Remaining Blockers

Ordered by consequence. Each names the exact surface, the exact evidence, and who owns it.
Nothing here was fixed by WSR23 because each item belongs to another surface.

## B1 — HIGH — Sole unpublished carrier of the RG-07 and RG-08 qualifications

**Surface:** local branch `camp/rg-closure-20260925` (head `ca8950e5`, 12 unpublished commits),
worktree `/home/moeen/code/ws-rg-closure-20260925`, repository `commander-playtest-lab`.
**No remote branch exists.** The workstream is terminal — its own handoff ends with
"Coordinator: review this handoff + branch … authorize publication". The worktree is clean, no
process, no writer lock, no `ACTIVE` state. Nobody owns it.

**Measured disposition:**

- `git cherry origin/main camp/rg-closure-20260925` → **12 `+`**, i.e. 12 commits with no
  patch-equivalent commit on `main`.
- `git merge-base origin/main <branch>` = `c491528c`; the branch is **129 commits behind** `main`.
- It is a **divergent sibling** of merged PR #249: `git merge-base ca5164bf6 <branch>` is also
  `c491528c`, and neither tip is an ancestor of the other.
- 10 paths exist **only** on this branch, plus its handoff:
  `engine-bridge/src/main/java/…/XmageFullGameTemporalDriver.java`,
  `XmageFullGameStackExecutionTest.java`, `XmageFullGameTemporalProgressionTest.java`,
  `XmageFullGameCommanderDamageTest.java`, `XmageFullGameControlDivergenceTest.java`,
  `XmageFullGameEliminationTest.java`, `XmageFullGameHexOfferTest.java`,
  `XmageFullGameReplacementTest.java`, `XmageFullGameHiddenRestorationTest.java`,
  `XmageFullGameWs05TemporalExecutionTest.java`,
  `docs/workstream_rg_closure_20260925/HANDOFF.md`.
- 8 further paths differ from `main`, including the two **production** files
  `XmageNativeStateRestoration.java` and `XmageFullGameDecisionController.java`.
- `RG-07` / `RG-08` appear **nowhere** on `origin/main` except as incidental strings in
  `config/rules_engines.json` and the residual-repin source lock.

**Why it is `NOT_READY` for publication (not `PUBLICATION_READY`):**

- §12.9 fails. Its evidence (299 Java bridge tests / 301-test suite, correspondence gate 9/9,
  9/9 and 12× FULL107 promotions) is bound to base `c491528c` + head `d445aee6` on engine pin
  XMage `b1959698`. Both the base and the pin were superseded: PR #242 repinned the candidate and
  merged PR #249 landed a *different* implementation of the same residuals on a later base.
- §12.7/§12.10 fail. It cannot fast-forward, and its production-file changes conflict with the
  canonical classes merged by #249 (`XmageCausalStackReconstruction`,
  `XmageCausalEliminationReconstruction`, `XmageControlDivergenceReconstruction`,
  `XmageHiddenStateRestoration`, `XmageTemporalProgressionDriver`).
- §12.11 fails. Merging it would collide with merged canonical work.

**Why it must not be deleted.** It is the only holder of the RG-07 exact-N Hex offer
qualification (6/6) and the RG-08 replacement-effect timing qualification (8/8), plus the RG-04
harness flake fix (UUID-ordered cleanup discards ate injected hand cards, ~1 in 5 runs) and the
RG-06A engine-defect finding in B2.

**Exact next action for the Coordinator.** Open a new workstream on current `main` whose sole
objective is to *port the RG-07 and RG-08 evidence* (and record B2/B3) onto the current engine
pin, then requalify only those two families. Do **not** rebase the whole branch. The branch
should then be retained as provenance, per §17.

## B2 — HIGH — Recorded engine defect in the Mage provider (not WSR23's to fix)

**Surface:** `moeendres-png/mage`, seam lineage at pin `b1959698`, reported by the RG-closure
campaign in `camp/rg-closure-20260925:docs/workstream_rg_closure_20260925/HANDOFF.md` §3.4.

**Finding.** Restored morphs of cards with **activated abilities** offer and execute those
abilities — e.g. Akroma firebreathing yields a 3/2 face-down permanent, leaking identity through
ability enumeration. Natural morphs are clean; a manifested Lavamancer is clean (fresh-effect
path). NATURAL vs RESTORED divergence suggests a simulation-copy vs live-object mechanism, but
that mechanism is **unproven**; the campaign correctly made no speculative engine patch.

**Lab containment already built (on the unpublished branch only):** an
`ACTIVATED_ABILITY_PRESENT` refusal for morph / Megamorph / Disguise, which is why RG-06 is
`PASS-BOUNDED` rather than PASS.

**Owner:** the Mage lane (WSR22's successor or a dedicated XMage workstream). §25 and §15: WSR23
records, it does not patch XMage Rules semantics. Fix requires a dedicated Mage worktree/branch
from the current pin, an offer-path root cause, a minimal fix, an engine regression, and a local
requalification before any repin adjudication.

## B3 — MEDIUM — Unowned tracked modifications to Mage engine sources

**Surface:** `/home/moeen/code/xmage-ws49-baseline`, detached at `66d97ebd` (2026-09-04), repository
`moeendres-png/mage`. **7 tracked files modified, unstaged:**

```text
M Mage.Sets/src/mage/cards/e/ExposeTheCulprit.java
M Mage.Sets/src/mage/cards/g/GhastlyConscription.java
M Mage.Sets/src/mage/cards/j/JalumGrifter.java
M Mage.Sets/src/mage/cards/j/JeskaiInfiltrator.java
M Mage.Sets/src/mage/cards/v/VialSmasherTheFierce.java
M Mage/src/main/java/mage/players/PlayerImpl.java
M Mage/src/main/java/mage/util/RandomUtil.java
```

Four of these are real cards and two are core engine files (`PlayerImpl`,
`RandomUtil` — the latter is Rules-randomness infrastructure). Nobody owns these edits, and they
are 23 days old. They are preserved exactly as found; `git diff` was not run against them and
nothing was reverted. **This is a `DIRTY_UNKNOWN_OWNER` surface in a Rules provider and needs a
Coordinator ruling**: it is either throwaway experiment residue or an unrecorded change to
hidden-information and randomness code, and WSR23 has no authority to decide which.

## B4 — MEDIUM — WSR22 and PR #260 overlap on two live paths

**Surface:** `qualification/pre-freeze-successor/CURRENT_RULES_AUTHORITY.json` and
`tests/qualification/test_pre_freeze_contract_successor.py` are in **both** PR #260's diff and
WSR22's local diff. WSR22's `dfb490e2` ("Gate 1: direct official CR 2026-09-25 capture resolves
Rules-authority freshness conflict") suggests the overlap is deliberate, but two active writers
touching the same two files is a live collision risk. WSR23 read both diffs and changed nothing.

**Owner:** Coordinator, to sequence #260 and WSR22 explicitly.

## B5 — LOW — 33 open PRs hold unique unpublished content

`OPEN_PR_CLASSIFICATION.json` shows 31 `SUPERSEDED_BUT_UNIQUE_CONTENT_REMAINS` and 2
`STALE_BUT_UNADJUDICATED` (#163, #164). Roughly 400 000 added lines and 40 000 changed files sit
on those PRs and on the matching local branches, none of it on `main`.

Closure requires content to be either integrated or explicitly retained as provenance, and that
is a per-PR Coordinator judgement, not a hygiene sweep. Two concrete notes:

- `origin/main`'s own live contract `qualification/ws47/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json`
  embeds the head SHAs of #142 (135×), #145 (136×), #155 (135×) and #158 (2×). Those four are
  load-bearing provenance for a current artifact and must not be closed on supersession alone.
- #163 and #164 have branch heads that are **not descendants of their own PR heads**
  (`0799c008` / `925d21a9`), i.e. the branches were rewritten after the PRs opened. They need
  reconciling before any disposition.

## B6 — LOW — Publication gate status for the WSR23 branch

See `PUBLICATIONS.md`. If the WSR23 push did not complete, this is recorded as
`BLOCKED_BY_PUSH_POLICY_GATE` with exactly one verified safe human command, and the WSR23
commits remain local-only and resumable.

## B7 — LOW — Provider qualification continues to require Coordinator authority

`PRODUCTION_PROVIDER = NOT SELECTED` and `ARCHITECTURE_FREEZE = NOT CLAIMED` remain in force. WSR23
made no Provider selection, no Freeze claim, and no requalification. WSR22 remains the active
qualification campaign.

## B8 — INFO — Repository `forge-candidate-h4f` is an unregistered second Forge clone

See `DELETION_CANDIDATES.md` Tier 5. No action taken; recorded so it is not later mistaken for a
Forge worktree.
