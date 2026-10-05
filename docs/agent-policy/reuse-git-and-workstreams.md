# Agent Policy — Reuse, Workstreams, Git and Ownership

Routed from repository-root AGENTS.md. Read this document before substantial implementation/reuse decisions and before branch/PR/worktree mutation, integration, ownership transfer, or cross-workstream access.

Migration source: AGENTS.md at 84edf0eaadb6d62cfa56d8b4056998b4ffa6b69f. The detailed policy below is preserved from that source lock.

## 9. Reuse-first gate

Before substantial new implementation, search for an existing solution in this order:

1. current canonical source on the active lineage;
2. historical project workstreams, donor branches, port ledgers, tests, and sealed evidence;
3. the exact pinned Rules Engine and its tests/APIs;
4. current upstream of that engine when a newer fix may supersede a project patch;
5. alternate qualified candidate engines or external libraries when they can materially
   reduce work without moving Rules authority out of the Rules Core.

Classify each material capability before implementing it as one of:
`REUSE_AS_IS`, `EXTRACT_AND_GENERALIZE`, `WRAP`, `PORT_FROM_DONOR`,
`ENGINE_NATIVE_REUSE`, `REFERENCE_ONLY`, or `NEW_IMPLEMENTATION_REQUIRED`.
`NEW_IMPLEMENTATION_REQUIRED` needs a concrete source-level reason why current source,
historical donors, engine-native APIs/tests, and relevant external donors cannot safely
satisfy the requirement.

Prefer reuse > extract/generalize > wrap > port > new implementation when Rules
Correctness, evidence integrity, licensing, and source-lock compatibility permit it.
Historical code and tests may transfer; historical PASS evidence does not transfer
without impact adjudication. Never wholesale-merge a diverged donor branch merely because
it contains useful code. Prefer the smallest reviewed transplant and retain provenance.

This gate is bounded discovery, not a research stopping point: once a clearly superior,
compatible donor is established, use it and continue implementation/build/test/debug/
qualification. Do not create a second Rules Engine, second observation layer, second replay
system, or parallel decision protocol when a qualified existing mechanism can be reused.

Qualification fixture or obligation names are evidence labels, not architecture requirements. Before adding a new decision class or protocol surface, inspect the engine callback and its authoritative context; an obligation may already be satisfied by a generic existing decision family plus a specific engine-supplied domain.

## 10. Workstream contract

One session owns exactly one primary workstream and one primary mutation surface by
default. A bounded cross-workstream integration assignment may additionally own explicitly
declared `owned-write` surfaces under that SAME workstream, provided every surface has
matching state ownership and a live writer lock held for the full child lifetime. Every
substantial assignment needs Objective, Source Lock, In/Out of Scope, Ownership,
Dependencies, Hard Gates, Forbidden Shortcuts, Evidence Requirements, Persistence, and
Stop Conditions. One primary objective; do not silently broaden scope.

### Delegated Git integration authority

`DELEGATED_GIT_INTEGRATION_AUTHORITY = ENABLED`

Inside an exclusively owned workstream, the worker may autonomously: fetch remotes;
inspect refs/remotes/branches; create feature branches; create isolated worktrees;
merge current target/base INTO the owned feature branch (normal merge only);
bounded cherry-pick; commit; push the owned non-protected feature branch normally;
create/update PRs; comment on PRs/issues; inspect CI; repair attributable failures;
push follow-ups; mark ready; and merge the campaign-owned PR through the normal GitHub
PR merge path once every merge-gate condition below holds. Routine user confirmation
is not required for those operations.

Hard boundaries (never evaded by wrappers, alternate binaries, or shell indirection):
no force push in any spelling; no direct push to `main`/`master`; no committing while
checked out on `main`/`master`; no history rewriting; no general rebase; no
`reset --hard`; no `clean`; no destructive branch/worktree deletion; no `update-ref`,
ref, filter, or forced-tag mutation; no branch-protection or admin bypass; no
remote-repository creation/deletion; no secret/token extraction or exposure.

A campaign-owned PR may merge without further confirmation only when: exclusive
ownership holds; exact PR head and target SHAs are freshly verified; target drift is
adjudicated; all required exact-head CI/qualification gates PASS; no current
non-outdated unresolved P1/P2 remains; no FAIL/UNKNOWN/BLOCKED is hidden; Rules and
evidence integrity hold; no source-lock or ownership conflict remains; the merge needs
no force/admin bypass/history rewrite; the branch is the worker's own; and canonical
HEAD/TREE is re-read with a persisted receipt afterwards. Otherwise repair if
technical and in-scope, or stop on a genuine authority/ownership/source blocker.

## 11. Git, worktree, ownership

Do not modify another active workstream's branch or worktree. Do not modify `main`
directly. Local commits for resumability are encouraged. Project-scoped Git/GitHub
operations are pre-authorized for the selected OpenCode executor when they are
evidence-backed and within the active campaign/workstream, and follow the delegated
authority above: create/switch owned branches, create isolated worktrees, push owned
branches, create/update/merge/close PRs, maintain issues, and bounded cherry-pick or
normal merge into owned integration branches. Rebase, destructive worktree/branch
deletion and history rewriting remain forbidden as specified in section 10. Preserve immutable
evidence/provenance branches and unique unintegrated work; do not force a result
toward PASS. Remote repository creation, paid services, raw-secret exposure,
account/org security changes, Production Provider selection, and Architecture Freeze
remain outside ordinary executor authority. Before material work, verify branch,
HEAD, tree, `git status`, contract/state or durable campaign checkpoint, and resume
from the newest verified state without redoing valid evidence.

### Cross-workstream access

Project-wide understanding does not imply project-wide write authority.

The normal Foundry run owns one primary writable worktree. A bounded integration task may
also declare additional verified workspace surfaces:

- `read-only`: exact repository + HEAD/tree, materialized into a disposable detached runtime snapshot; the authoritative source worktree remains non-writable;
- `owned-write`: exact repository + branch + HEAD/tree + state path + matching ownership;
  for cross-WS mutation the checkout must be standalone (checkout-local `.git`), its state
  must live under that checkout's `.foundry`, and writable surfaces must be disjoint.

All owned-write surfaces must name the CURRENT workstream as state ownership, be locked
before the OpenCode child starts, and remain locked for its entire lifetime.
Foreign-active, unknown-owner and undeclared sibling worktrees remain non-writable.
Cross-workstream child execution uses Bubblewrap with the host filesystem mounted
read-only and only the explicitly writable standalone surfaces, unique runtime directory,
and narrow tool caches rebound read-write. Missing/unusable Bubblewrap is a launch refusal,
never a silent downgrade. Agents must not use sudo or bypass the sandbox to install it.
DeepSeek MAX and Space Bunny MAX use the same access contract.
