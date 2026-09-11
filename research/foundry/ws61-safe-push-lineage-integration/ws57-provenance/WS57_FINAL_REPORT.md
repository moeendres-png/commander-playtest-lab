# WS57 Final Report — Foundry remote-lineage safe-push remediation

## Verdict

`FOUNDRY_REMOTE_LINEAGE_SAFE_PUSH_PASS`

## Source lock

- Repo `moeendres-png/commander-playtest-lab`, branch
  `ws57/foundry-safe-push-lineage-remediation-20260911`
- HEAD `dd3be6026515e40f4b18a6121058877f5cab5725`,
  TREE `3e73de272899c39963160c1884e5280cfe86276a` (DIRECTLY_VERIFIED).

## Defect reproduced

Pre-fix `safe_push --dry-run` on a diverged-lineage rig (remote source branch
at audit base B, B outside main ancestry, target absent) rejects with
`PUSH_REJECT: branch creation refused: audit base is outside the remote
history` (rc 2). See `WS57_DEFECT_REPRO.json`. (DIRECTLY_VERIFIED)

## Design

Narrow optional `--expected-audit-base-ref <branch>`: when the target is
absent, the creation anchor may be one explicitly named pre-existing remote
source branch whose tip must equal-or-contain the audit base, proven read-only
via exactly `git ls-remote <remote> refs/heads/<name>` plus local merge-base.
Default (no flag) keeps the legacy main/master rule byte-identical;
existing-target fast-forward/UP_TO_DATE logic is untouched. Source-ref
validation is strict-format but not destination-protected (a historical source
name is identity evidence, never a refspec). See `WS57_DESIGN.md`.
(CODE_DERIVED + TECHNICALLY_CONFORMANT)

## Changes

- `tools/foundry/safe_push.py`: module docstring gate-10 rule; new
  `_valid_source_ref_name` + `_resolve_expected_remote_base`; creation-path
  branch; `safe_push()`/`_decide_push()`/`main()` thread the optional
  parameter (keyword default `None`; existing positional callers unaffected).
- `tests/foundry/test_safe_push.py`: `lineage_rig` fixture (WS54 shape) + 15
  tests (3 positive, 11 negative, 1 source-vs-destination semantics unit test).
- No engine, evidence, ranking, or production-repository changes.

## Security invariants

All 17 hold (verified by the adversarial matrix, every negative proving no
remote write via ls-remote): schema 2.0; protected-branch push rejection;
slug validation; triple match; single-worktree ownership; ancestor-held lock;
validated_head gates; clean tree; audit-base ancestry; FF-only existing
targets; exact single refspec; no force/delete/tags/caller refspec/hook
bypass; redaction. UNKNOWN in changed security scope: 0.

## Positive tests

Dry-run OK with no write; real creation at live HEAD then UP_TO_DATE;
advanced-source-tip (ancestor) permitted after fetch. (DIRECTLY_VERIFIED)

## Negative tests

Legacy rejection without flag; absent/unrelated source ref; 12 malformed /
injection / SHA-like / self shapes; wrong remote; dirty tree; missing and
sibling locks; null validated_head; foreign audit base; non-fast-forward with
rival tip preserved. Full matrix: `WS57_ADVERSARIAL_TEST_MATRIX.json`.
(DIRECTLY_VERIFIED)

## Regression

- `tests/foundry/test_safe_push.py`: 30 passed (15 pre-existing + 15 new).
- Related Foundry suites (telemetry, launcher, foundry_tools, state_v2,
  writer_lock): 93 passed, 1 skipped (pre-existing live-snapshot skip).
- `ruff check` clean; `ruff format` clean.
- Local-run note: this sandbox exports a `remote.origin.pushurl` override that
  breaks file:// fixture pushes; test runs scrubbed only the `GIT_CONFIG_*`
  process env for the pytest subprocess (no repo/config change; CI
  unaffected). Pre-existing and new tests behave identically under it.

## WS54 applicability

Exact required future flag:
`--expected-audit-base-ref foundry/ws39-commander-history-state-restore`
(audit base `0c1f455ea8c8fa48ab9d638ad5068ec242800428`, target
`qualification/ws54-xmage-rng-reexecution-remediation-20260910`).
Read-only verified: source tip == audit base; target absent.

## RQ-A2 applicability

Exact required future flag:
`--expected-audit-base-ref research/argentum-readonly-qualification-20260910`
(audit base `a62a8c7cced4cc226ae9b9a44d06539fbf542bd6`, target
`research/argentum-comparable-qualification-rq-a2-20260910`).
Read-only verified: source tip == audit base; target absent.

## Dependencies unblocked

- `WS54_SAFE_PUSH_UNBLOCKED = YES` (lineage-creation gate; terminal push still
  subject to WS54's own gates 1–9 — run `--dry-run` first).
- `RQA2_SAFE_PUSH_UNBLOCKED = YES` (same scope qualification).

No push to mage or RQ-A2 was performed inside WS57.

## Remaining blockers

None in WS57 scope. Next actions belong to the owning workstreams (fetch
source branch, dry-run, then push from inside their lock-holding launchers).

Standing state: ARCHITECTURE_FREEZE = NOT CLAIMED,
PRODUCTION_PROVIDER = NOT SELECTED.
