# WS58 PR #178 State-Writer Review Remediation (WS58R)

## 1. Original PASS (preserved, not rewritten)

- WS58 terminal checkpoint at ENTRY HEAD `d3159eaaa4e276445a58bb7269c25b7625c97b9d`
  (TREE `506337ffcd89bbfea88d1033b62be312518b4094`) recorded
  `FOUNDRY_STATE_PERSISTENCE_HARDENING_PASS` with `validated_head: null`
  (honest null: nothing beyond the audit base claimed as validated in that
  checkpoint document).
- Original evidence preserved in place (not modified by this remediation):
  - `research/foundry/ws58-state-persistence-hardening/WS58_FINAL_REPORT.md`
  - `WS58_TEST_MATRIX.json`, `WS58_NEGATIVE_CONTROLS.json`,
    `WS58_INCIDENT_MATRIX.json`, `WS58_CALLSITE_INVENTORY.json`,
    `WS58_DESIGN.md`, `WS58_SOURCE_LOCK.md`
  - `research/foundry/ws58-state-persistence-hardening/WORKSTREAM_STATE.yaml`
    history prior to this addendum (36 writer tests;
    full `tests/foundry/` 152 passed + 1 pre-existing live-export skip;
    Ruff clean; terminal re-run `test_state_v2` 11 / `test_foundry_tools` 45 /
    `test_state_writer` 36).
- This addendum does not rewrite that history to pretend the defects were
  never present. The defects below were real and are repaired here.

## 2. Later PR review findings (PR #178)

Post-terminal review of PR #178 found two valid defects in the canonical
writer surface (`tools/foundry/state.py`):

- **P1 — validation credit persistable without workdir/ancestry proof.**
  Non-null `validated_head` could be persisted without a workdir, skipping
  validation-credit ancestry checking.
- **P2 — write-intent flags without a write mode silently no-op.**
  Write-intent flags without a write mode fell through to read-only
  validation and returned `STATE_OK`.

Both were accepted as valid. No other review findings are in scope for WS58R.

## 3. P1 / P2 exact defects

### P1 (before fix)

- `write_state()` gated ancestry only on
  `if workdir is not None and doc.get("validated_head") is not None:` —
  so `write_state(path, doc_with_non_null_validated_head, workdir=None)`
  **persisted without any ancestry check**.
- `update_state()` delegates to `write_state()`, so both setting non-null
  credit (`validated_head=<sha>`, `workdir=None`) and *preserving* a stored
  non-null credit (existing file has credit, patch touches only another
  field, `workdir=None`) persisted unchecked.
- CLI: `--set-validated-head + --patch-file` without `--workdir` succeeded
  via the same hole; `--write-from` carrying non-null `validated_head`
  without `--workdir` succeeded via the same hole.

### P2 (before fix)

- `main()` routed strictly on `if args.write_from or args.patch_file:
  return _main_write(args)` and otherwise ran read-only validation.
- Therefore each of these, alone with `--state FILE` and no write mode,
  was silently ignored and returned `STATE_OK` on a valid file:
  `--set-validated-head`, `--clear-validated-head`, `--stamp-head`,
  `--allow-identity-change`.
- Same silent-drop class: `--in-place` without `--migrate` (ignored),
  `--migrate` combined with `--write-from`/`--patch-file` (migrate flag
  silently dropped because the write branch took precedence).

## 4. Impact adjudication

- **No prior test depended on the defective paths**, so no previously green
  test goes red because its expectation was wrong: the pre-remediation suite
  contained no case asserting "non-null credit without workdir succeeds" and
  no case asserting "write-intent without write mode returns STATE_OK".
  Verified by `git diff --numstat` on the test file for this remediation:
  `216 additions, 0 deletions` — existing assertions untouched.
- **Guarantee impact (why requalification was mandatory):**
  - P1 weakened the headline invariant ("ancestry-checked validation
    credit"): a normal writer path could mint validation credit without
    proof. Any validation-credit claim persisted without a workdir before
    this fix is **not** ancestry-proven.
  - P2 weakened the CLI contract: a mis-invoked write could look
    successful-or-innocuous (`STATE_OK`) while doing nothing.
- **Evidence survival:**
  - Null-credit bootstrap / migration / update / read-only results survive
    (semantics unchanged for `validated_head: null`).
  - With-workdir ancestry positives survive pending re-run (semantics
    unchanged when workdir is supplied; re-run below confirms).
  - Outside-lock (`VALIDATED_OUTSIDE_LOCK`) and rewritten-history
    (`VALIDATED_REWRITTEN`) rejections survive pending re-run (predicate
    logic unchanged; only the missing-workdir hole was closed).
- **Required requalification:** full `tests/foundry/` surface plus Ruff on
  changed Python, on the clean committed code HEAD (see section 7).

## 5. Fixes (shared API boundary first, CLI defense in depth)

All changes in `tools/foundry/state.py` (plus regression tests):

1. **P1 at the shared API boundary — `write_state()`:** any document with
   non-null `validated_head` and `workdir=None` now raises `StateWriteError`
   fail-closed ("ancestry cannot be proven without live Git ... pass
   workdir ... or clear validation credit to null"). With a workdir, the
   existing audit-base/live-HEAD ancestry checks remain binding and unchanged.
   `update_state()` inherits this for both the set-credit and
   preserve-credit cases because it delegates its final persist to
   `write_state()`. Null stays valid without a workdir; clearing to null
   stays possible without a workdir.
2. **P1 CLI explicit guards — `_main_write()`:** `--set-validated-head`
   without `--workdir` rejects with `STATE_REJECT` before any write;
   `--write-from` whose document carries non-null `validated_head` without
   `--workdir` rejects with `STATE_REJECT` before any write. The preserved-
   credit CLI case is enforced inside `write_state`/`update_state` (no second
   implementation of ancestry logic).
3. **P2 top-level guards — `main()`:** any of `--set-validated-head` /
   `--clear-validated-head` / `--stamp-head` / `--allow-identity-change`
   without `--write-from`/`--patch-file` returns nonzero `STATE_REJECT`
   ("refusing silent no-op") instead of falling through to `STATE_OK`.
   Additionally: `--in-place` without `--migrate` rejects; `--migrate` with
   `--write-from`/`--patch-file` rejects as mutually exclusive.
   `--allow-identity-change` is documented and enforced as requiring
   `--write-from`/`--patch-file` (the migrate `--in-place` path does not
   consume it, so passing it there stays a reject rather than a silent drop).
   Ordinary read-only `state.py --state FILE` is untouched and stays
   `STATE_OK` on a valid file.
4. **Help text:** `--set-validated-head` now documents
   "requires --patch-file and --workdir for ancestry proof";
   `--allow-identity-change` documents "requires --write-from or
   --patch-file".

No engine, provider, qualification, safe-push, or unrelated-test changes.
No fallback legality was introduced; unsupported paths fail closed.

## 6. Negative controls (13 hard gates)

New adversarial tests in `tests/foundry/test_state_writer.py`
(36 pre-existing + 17 new = 53; every negative asserts byte-identical
preservation of the prior file):

| # | Gate | Covering test(s) |
|---|------|------------------|
| 1 | API non-null `validated_head` without workdir rejected | `test_p1_api_write_state_nonnull_without_workdir_rejected` (ancestry-valid SHA still rejected without workdir), `test_p1_api_update_state_set_without_workdir_rejected` |
| 2 | CLI `--set-validated-head` + patch-file without workdir rejected | `test_p1_cli_set_patch_without_workdir_rejected` |
| 3 | write-from non-null `validated_head` without workdir rejected | `test_p1_cli_write_from_nonnull_without_workdir_rejected` |
| 4 | outside-audit-base validation SHA rejected | pre-existing `test_negative_fabricated_validated_head_rejected` + `test_cli_fabricated_validated_head_rejected` (re-run green) |
| 5 | validation SHA not ancestor of live HEAD rejected | pre-existing `test_negative_rewritten_validated_head_rejected` (re-run green) + new CLI `test_p1_cli_rewritten_validated_head_rejected` |
| 6 | `--set-validated-head` without write mode rejected (no `STATE_OK`) | `test_p2_set_without_write_mode_rejected` (asserts `STATE_REJECT` on stderr, no `STATE_OK` on stdout) |
| 7 | `--clear-validated-head` without write mode rejected | `test_p2_clear_without_write_mode_rejected` |
| 8 | `--stamp-head` without write mode rejected | `test_p2_stamp_without_write_mode_rejected` |
| 9 | meaningless `--allow-identity-change`/no-write rejected | `test_p2_allow_without_write_mode_rejected`; also `test_p2_in_place_without_migrate_rejected`, `test_p2_migrate_with_patch_file_rejected` for the equivalent silent-drop class |
| 10 | negative state-write cases preserve original bytes | every new negative asserts `path.read_bytes() == before`; pre-existing negatives unchanged |
| 11 | null-credit bootstrap/migration/update remains green | pre-existing positives/migrate/bootstrap (re-run green) + new `test_p1_cli_write_from_null_without_workdir_allowed`, `test_p2_clear_with_patch_without_workdir_allowed`, `test_p1_api_clear_without_workdir_allowed` |
| 12 | valid ancestry-checked validation-credit update remains green | pre-existing `test_positive_explicit_valid_validated_head_persists`, `test_cli_validated_head_lifecycle` (re-run green) + new `test_p1_cli_write_from_nonnull_with_workdir_allowed` |
| 13 | ordinary read-only validation remains green | new `test_p2_read_only_remains_ok` (`--state FILE` -> `STATE_OK`) plus full-suite read paths |

Preserved-credit nuance is pinned by
`test_p1_api_update_state_preserve_without_workdir_rejected` (stored credit
+ workdir-less patch update fails closed) and its dual
`test_p1_api_clear_without_workdir_allowed` (clearing stays possible).

## 7. Requalification (terminal, on the clean committed code HEAD)

Code HEAD (validated): `4bf61fc10ccb2b9fd587df8567920277b70ce2bb`
(TREE `883aa6fbc920816326c1285b301107122bd60550`), commit
"WS58R: fail-closed P1/P2 state-writer remediation + adversarial regression
(53 writer tests)". Tree was clean before and after each run.

On that exact clean HEAD:

- `python3 -m pytest tests/foundry/test_state_writer.py -q` — **53 passed**.
- `python3 -m pytest tests/foundry/test_state_v2.py tests/foundry/test_foundry_tools.py -q` — **56 passed**.
- `python3 -m pytest tests/foundry/ -q` — **169 passed, 1 skipped**
  (skip: `tests/foundry/test_telemetry.py:104` "no live export snapshot
  present", pre-existing).
- `python3 -m ruff check tools/foundry/state.py tests/foundry/test_state_writer.py` — **clean**.
- `python3 -m ruff format --check tools/foundry/state.py tests/foundry/test_state_writer.py` — **clean**.
- `GIT_CONFIG_*` scrub: not required — parent process environment contained
  no `GIT_CONFIG_*` push-guard variables, and the full suite (including
  local-file-remote fixtures) passed as-is. No global git config changes
  were made.

Evidence classification for the above: `DIRECTLY_VERIFIED` (fresh terminal
runs on the named code HEAD).

## 8. Final disposition

- `FOUNDRY_STATE_PERSISTENCE_HARDENING_PASS` (reaffirmed after remediation).
- `PR178_REVIEW_REMEDIATION_PASS`.
- `CANONICAL_STATE_WRITER_READY = YES`.
- `FUTURE_HAND_WRITTEN_STATE_YAML_REQUIRED = NO`.
- `RULES_BEHAVIOR_CREDIT_CHANGE = 0`.
- `ARCHITECTURE_FREEZE = NOT CLAIMED`.
- `PRODUCTION_PROVIDER = NOT SELECTED`.
- Source lock: audit base `e207286200854bf9bff557e67bf3b37b5e428392`
  (tree `6e89a980bf0a7e40273ba11b108fe3febed39d47`); WS58R code
  `validated_head = 4bf61fc10ccb2b9fd587df8567920277b70ce2bb`; report/state
  terminal commit descends from `validated_head` and claims no additional
  validation.
