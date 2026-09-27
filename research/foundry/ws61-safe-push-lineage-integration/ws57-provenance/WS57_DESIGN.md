# WS57 Design — explicit remote-source-lineage creation gate

## Problem

`tools/foundry/safe_push.py` gate 10 permits target-branch creation only when
`audit_base_sha` is equal to or an ancestor of remote `main`/`master`. Valid
candidate/research lineages rooted on other remote branches (WS54 XMage:
`foundry/ws39-commander-history-state-restore`; RQ-A2:
`research/argentum-readonly-qualification-20260910`) are rejected with
`branch creation refused: audit base is outside the remote history`, even
though the audit base is already part of trusted remote history.

## Change (narrow, fail-closed, backward compatible)

New OPTIONAL parameter `--expected-audit-base-ref <branch>` (also accepted as
`safe_push(..., expected_audit_base_ref=...)` / `_decide_push(..., ...)`).

- Target branch already exists on remote: logic unchanged (fast-forward-only /
  UP_TO_DATE). The new option is not consulted.
- Target branch absent WITHOUT the option: legacy main/master creation rule,
  byte-for-byte unchanged (default path preserved).
- Target branch absent WITH the option: creation proceeds only after
  `_resolve_expected_remote_base(...)` proves, read-only, that `audit_base_sha`
  is equal to or an ancestor of the tip of exactly
  `refs/heads/<expected-audit-base-ref>` on the already-validated expected
  remote. All prior gates (1–9) still run first, unchanged.

## New validation (`_valid_source_ref_name`)

Strict branch-name gate with source-reference (identity-evidence) semantics:

- Allows what destination semantics forbid ONLY where safe: protected names
  (`main`/`master`) are accepted as *format-valid* source identity; ancestry
  proof still decides (a diverged `main` still rejects).
- Rejects: empty names; `HEAD`; `refs/` prefixes; leading `-`/`.`; unsafe
  characters (same strict regex as destinations: whitespace, `:`, `..`,
  `~^:?*[\`, `@{`); 40-hex SHA-like pseudo-refs; anything
  `git check-ref-format --branch` rejects (this also excludes ls-remote
  wildcard characters, so the lookup is always literal); equality with the
  push target branch.

## New resolver (`_resolve_expected_remote_base`)

1. Format-validate the name (above).
2. Exactly `git ls-remote <remote> refs/heads/<name>` — no wildcards, no
   enumeration. Require exactly one output line whose ref field equals the
   requested ref (absent/ambiguous → reject).
3. `git merge-base --is-ancestor <audit_base> <tip>` (equality allowed).
   Unrelated lineage → reject. Never writes.

## Security invariants (all preserved)

Schema 2.0 validation; protected-branch push rejection; expected-slug remote
validation; live/expected/state triple match; single-worktree ownership;
ancestor-held writer lock; validated_head non-null + ancestry; clean tree;
audit-base ancestry of live HEAD; existing-target fast-forward-only; exact
single ref push; no force/delete/tags/caller refspec/manual hook bypass;
credential redaction. The source ref is identity evidence only, never a
refspec: the sole write remains `git push <remote> HEAD:refs/heads/<target>`.

## Operator prerequisite

The local clone must contain the source-tip object for the ancestry check:
`git fetch origin <source-branch>` (read-only) before invoking safe_push with
the flag. Equality (tip == audit base, the WS54/RQ-A2 shape) needs no fetch
beyond the existing clone.

## Alternatives rejected

- Wildcard/implicit source discovery: silent trust, rejected.
- Accepting tags/SHAs/refspecs: caller-controlled identity, rejected.
- Auto-fallback to any containing branch: same as wildcards, rejected.
- Fetching inside safe_push: network write-adjacent side effect inside a push
  gate, rejected; caller fetches explicitly.
