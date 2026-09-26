# Fork Agent-Pointer Specification (design only)

Status: design by WS-A1R. WS-A1R owns only `commander-playtest-lab` and edits no
fork. Actual fork files require the follow-up workstreams in §4.

## 1. Problem (DIRECTLY_VERIFIED 2026-09-10)

`moeendres-png/mage` and `moeendres-png/forge` roots contain no project-local
agent pointers (upstream readmes only). A worker opening either fork sees ~100
(mage) branches with no local instruction about mirror discipline, patch
ownership, or authority.

## 2. Design: smallest safe mechanism

One short `AGENTS.md` (≤60 lines) at each fork root:

1. Identity: "Commander Simulator Next engine fork (remediation/compatibility
   surface). Project-wide authority lives in `moeendres-png/commander-playtest-lab`
   (`docs/PROJECT_MISSION.md`, `AGENTS.md`, `config/rules_engines.json`)."
2. Mirror rule: default branch (`master`) is an upstream mirror. Direct commits to
   it are prohibited; sync is fast-forward-only from upstream, recorded with
   before/after SHAs.
3. Patch rule: project work lives on explicitly owned `foundry/*`, `work/*`, or
   `playtest-lab-*` branches, one workstream per branch; every branch states its
   upstream base SHA.
4. Verdict rule: no Qualification PASS/FAIL is claimed in the fork; verdicts live
   in the lab's `qualification/`.
5. Source-lock rule: every handoff records fork HEAD, tree, upstream base SHA,
   and the lab pin that consumes it.
6. Freeze rule: nothing in the fork selects a provider or claims Architecture
   Freeze (`ARCHITECTURE_FREEZE = NOT CLAIMED`, `PRODUCTION_PROVIDER = NOT SELECTED`).
7. Cross-link: lab `.foundry/repo-profiles/{mage,forge}.json` remain the
   machine-readable control plane; the fork file is the human/agent pointer.

No workflow, code, or CI changes in the forks. No duplication of lab policy text —
pointer, not copy (prevents divergence).

## 3. Why not alternatives

- Full policy copy in forks: diverges from lab authority (rejected).
- No pointer (status quo): workers infer discipline from branch names (rejected —
  this audit cycle proved the cost).
- Shared-workflows enforcement: disproportionate; convention + review suffices.

## 4. Follow-up workstreams (NOT executed by WS-A1R)

- **WS-A1R-F1 (mage pointer):** add `AGENTS.md` per §2 to `moeendres-png/mage`
  root on a `foundry/` or `chore/` branch; PR against fork `master`; merge only
  after lab-side review. No engine code touched. Muse HIGH, writer (fork scope).
- **WS-A1R-F2 (forge pointer):** same for `moeendres-png/forge`.
- Both require fork-write authorization (outside WS-A1R ownership) and must not
  ride along with engine remediation branches.

## 5. Disposition (WS-ARCLOSE-D1, 2026-09-13 — appended; §§1–4 above preserved verbatim as the WS-A1R design record)

**WS-A1R-F1 / WS-A1R-F2: `SUPERSEDED` (design-only, never executed).**

Rationale, verified against current source truth at Source Lock
`f89c824e93664b8285b0b44e4445118bd99b9f98`:

1. Per-run policy injection replaces the pointer need. The launcher injects
   canonical authority into every session (`OPENCODE_CONFIG_CONTENT`:
   canonical model/permission lock; `OPENCODE_CONFIG_DIR`: canonical
   agent/skill snapshot; `tools/foundry/launcher.py`), and `.foundry/repo-profiles/`
   is the machine-readable control plane — no fork-resident file is required
   for a worker to receive current authority.
2. The drift gate forbids the mechanism. `tools/foundry/drift_check.py`
   classifies ANY fork-root `AGENTS.md`/`CLAUDE.md` on a non-canonical
   profile as `SUPERSEDED_BUT_REACHABLE` (stale markers) or `AMBIGUOUS`
   (marker-free), and either verdict fails the check and blocks unattended
   launch. A merged F1/F2 pointer file would therefore permanently trip the
   gate it was meant to satisfy.
3. Mirror discipline forbids the landing zone. Both fork `master` branches
   are upstream mirrors (fast-forward-only sync; no project-only commits —
   contract hard gate). Landing a project pointer on mirror `master` would
   intentionally create project divergence from upstream.

Successor mechanism (already in force, no new workstream required):
launcher policy injection + repo profiles + fail-closed drift gate, with
human re-adjudication against a declared reference root when the gate
fires. Do not revive F1/F2 without a Coordinator authority decision
re-opening mirror-master project writes.

`ARCHITECTURE_FREEZE = NOT CLAIMED`. `PRODUCTION_PROVIDER = NOT SELECTED`.
