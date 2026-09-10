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
