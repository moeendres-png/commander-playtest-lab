# LAB Publisher Security Reintegration — Handoff (2026-09-27)

## Source Lock

- Repo `moeendres-png/commander-playtest-lab`, worktree
  `/home/moeen/code/ws-lab-publisher-reint-20260927` (sole writer), branch
  `lab/publisher-reintegration-20260927`.
- Dispatch canonical main `fa315da3`; main advanced to `d04bf9e4` (PR #252,
  README-only, 1 file) before mutation: impact adjudicated none (zero overlap
  with affected surface); workstream rebased to `d04bf9e4` as current base.
- Content commit `e55b1d0e`, pushed fast-forward (new remote branch).
  PR: https://github.com/moeendres-png/commander-playtest-lab/pull/253
  (base main, no merge performed here).

## Historical Authority

- PR #206 `WS241-safe-push-effective-target-identity-fix-204`, qualified head
  `80abaae6`, base `aebcfda3`. NOT merged as-is (stale base/history).
- WSR20 audit re-verified: no stronger local remediation; cpl/r10 `b048d682`
  byte-identical safe_push (no strengthening); main regressed the hardening.
- #206 treated strictly as implementation/evidence provenance for porting.

## Current-Main Impact Adjudication

- `tools/foundry/safe_push.py`: main 534 lines strictly weaker (substring slug
  check, plain push, redacted echo). Full WS241-C delta STILL_REQUIRED.
- `tests/foundry/test_safe_push_effective_target.py` + evidence doc: DELETED
  on main → STILL_REQUIRED (restored).
- `test_safe_push/launcher/telemetry/ws75` tests: tiny deltas, all
  strengthening → STILL_REQUIRED (ported).
- ALREADY_PRESENT_EQUIVALENT: `source_lock.is_canonical_remote`,
  `remote_url_records` (no source_lock port needed).
- SUPERSEDED_BY_STRONGER / INCOMPATIBLE: none (new CLI flag additive,
  default-deny; launcher call path compatible).
- Shared regions byte-identical → port equals #206 bytes on current base.

## Exact Changes

- `tools/foundry/safe_push.py` (534→800 lines): exact effective-target
  validation (one fetch record, exact slug, no substring); pushurl/mirror/
  receivepack rejection; insteadOf/pushInsteadOf guards (all scopes + env);
  `get-url --push --all` byte-equality; pre-write recheck; `--no-follow-tags`;
  `--allow-local-path-target` fixture-only flag; count-only diagnostics
  (no URLs/userinfo/output in rejects).
- Restored `test_safe_push_effective_target.py` (57 cases) + WS241 evidence doc.
- Strengthened `test_safe_push/launcher/telemetry/ws75` deltas.

## Tests / Evidence

- Effective-target suite: 57 passed. Safe_push/launcher/telemetry/ws75: 139
  passed, 1 pre-existing env skip (no live export snapshot).
- Full `tests/foundry/`: 421 passed, 1 env skip. Drift suite: 8 passed.
- `ruff check` + `ruff format --check`: clean on all touched files.
- Genuine git fixtures throughout (local bare remotes); no network probes.

## Security Negative Matrix (22/22 present, all green)

HTTPS/SSH identity, lookalike-slug, pushurl (single/multi/blank/env),
pushInsteadOf/insteadOf (local/global/system/env), multi/blank/divergent URL
records, malformed config, secret diagnostics (4 tests), local-path reject +
fixture positive, followTags, refspec-by-construction (+mirror gate),
pre-write recheck, local-bare positive write, unauthorized remote unchanged,
ancestor/source/ownership/FF locks.

## Secret-Safety Evidence

- Rejects carry counts/static text only (asserted: credential_pushurl_never_
  echoed, metrics/logs/ls-remote/push-output withholding tests).
- Only synthetic sentinels in tests (`s3cret-ws241`, MARKER, test-host
  fixtures); no real credentials/tokens/URLs in code, tests, or this handoff.

## PASS / FAIL / UNKNOWN

- PASS: all 7 hard-gate conditions hold (proven destination, fail-closed
  ambiguity, no unauthorized write, positive-control write, secret-safe
  diagnostics, publisher invariants survive, impacted regression green).
- FAIL: none. UNKNOWN: none (residual: none; scope intentionally bounded).

## Remaining Blockers

- Coordinator adjudication that PR #253 contains the required semantics, then
  Coordinator-directed disposition of PR #206 (do NOT auto-close).
- Remote CI on PR #253 to be observed (local lanes green; push just landed).

## PR / Branch / HEAD / TREE

- Branch `lab/publisher-reintegration-20260927`, HEAD `e55b1d0e`, remote
  `e55b1d0e` (fast-forward, verified pre-push).
- PR #253: https://github.com/moeendres-png/commander-playtest-lab/pull/253

## Relationship to PR #206

Replacement candidate carrying #206's exact qualified semantics onto current
main without its stale history. #206 stays OPEN until Coordinator confirms.

## Exact Next Action

Coordinator: review PR #253 (diff = pure WS241 restoration), await remote CI,
adjudicate semantics parity, then direct #206 closure and merge of #253.
Do not broaden into FULL107/Forge/XMage/provider/Freeze.

ARCHITECTURE_FREEZE = NOT CLAIMED
PRODUCTION_PROVIDER = NOT SELECTED
