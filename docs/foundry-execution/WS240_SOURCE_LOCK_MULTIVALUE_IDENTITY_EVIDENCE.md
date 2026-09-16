# WS240 Source-Lock Multivalue Identity — Evidence Seal (PR #202 P2 successor)

Status: SEALED on exact bytes below. Adjudication belongs to the Coordinator;
this seal describes reality only. `ARCHITECTURE_FREEZE=NOT_CLAIMED`.
`PRODUCTION_PROVIDER=NOT_SELECTED`. `FULL107=NOT_RUN`.

## 1. Source lock

- WS239 audit base (immutable, sealed, not mutated):
  HEAD `f30d4c436f63c9d5b5a9fea7c18d2815691c981d`,
  TREE `2a12e4f39b6a2211942bab721e37fa7fa5fe0645`.
- WS240 descendant commit (this workstream, branch
  `ws240/source-lock-multivalue-identity-20260916`):
  HEAD `e5530bc906fd3ab6132fcf6f1560c8e6f0e2e516`,
  TREE `8b02cf30d5f51da5d4440024daca5d4d1815b683`.
- Parent chain: `e5530bc9` child of `f30d4c43` child of post-WS238 main
  `cce0d792e4d4b79b3a736d70bec46f876ed76990`. No rebase, no amend of sealed
  history. WS239 branch, PR #202, PR #199, and main untouched.
- Schema: workstream state schema 2.0 (external state file, not in tree).

## 2. Review provenance (P2)

- PR #202 (`ws239/...` → `main`, Draft) unresolved Codex review thread
  `discussion_r4025238740` at `tools/foundry/source_lock.py:53`:
  `git config --get-all remote.origin.url` returning two records
  (canonical + blank/whitespace-only) collapses through `_git(...).strip()`,
  so `verify()` returns no identity error (false PASS). Coordinator comment
  `issuecomment-5696626453` blocks merge pending a successor with
  fail-before reproduction, fail-closed multivalue parsing in primary
  `verify()`/bootstrap, adversarial regressions, and fresh qualification.
- Read-only code inspection of exact PR head `f30d4c43` confirmed the lossy
  seam; runtime reproducer below is independently rerun (DIRECTLY_VERIFIED),
  not review-reported.

## 3. Root cause (TECHNICALLY_CONFORMANT, runtime-reproduced)

`remote_identity()` piped multi-record `--get-all` output through the
text-mode `_git()` helper whose `.strip()` removes outer whitespace. A
trailing blank/whitespace-only second record therefore vanished, leaving the
canonical string; `is_canonical_remote()` then passed and `verify()` returned
`[]`. `check_canonical_ref()` shared the same lossy read. Duplicate-canonical
and divergent-second-URL cases already failed closed (joined string rejected),
but every blank-adjacent variant passed. Reproducer:
`/tmp/opencode/ws240_repro.py` (scratch, not committed).

## 4. Fix (narrow scope; `_git` contract unchanged)

- New `_git_raw()` (bytes, no decode/strip) + `remote_url_records()`
  (NUL-delimited `git config --null --get-all`, order- and
  emptiness-preserving, UTF-8 strict, remote-name validated, count-only
  diagnostics). `_git_raw` maps `OSError`/`UnicodeError`/timeout to sanitized
  `RuntimeError`, mirroring `_git`.
- `remote_identity()` requires exactly one record; otherwise raises
  `ambiguous remote identity` (verify → fail-closed `cannot read origin url`,
  no values echoed). A single empty record is returned and rejected
  downstream by `is_canonical_remote` (`WRONG_LOCAL_REPOSITORY`).
- `check_canonical_ref()` reads the same seam for its remote and returns
  `REMOTE_REF_UNKNOWN: ambiguous remote identity` before any rewrite
  inspection or live probe.
- Five ported test doubles updated to stub `remote_url_records` instead of
  `_git`; assertions unchanged (seam moved, semantics identical).

## 5. Changed paths (5 + this seal)

| path | sha256 | change |
|---|---|---|
| `tools/foundry/source_lock.py` | `a3129733…e544c` | `_git_raw`, `remote_url_records`, exactly-one gate, taxonomy note |
| `tests/foundry/test_source_lock_multivalue_identity.py` | `338014b6…b41e9` | NEW: 31 P2 negatives/controls |
| `tests/foundry/test_source_lock_identity.py` | `a9269e37…bb6b1` | 3 doubles re-seamed, assertions unchanged |
| `tests/foundry/test_remote_ref_freshness.py` | `132bbfb8…28cef` | 2 doubles re-seamed, assertions unchanged |
| `docs/foundry-execution/SOURCE_LOCK_REMOTE_EVIDENCE.md` | `7a628444…012ff3` | record-preserving identity bullet |
| `docs/foundry-execution/WS240_SOURCE_LOCK_MULTIVALUE_IDENTITY_EVIDENCE.md` | (this file) | evidence seal |

Full hashes in §8. WS239 5-file provenance otherwise byte-intact.

## 6. Runs (exact head `e5530bc9`, qualified OpenCode 1.18.30 env)

- Baseline fail-before (tracked fix stashed, new tests against `f30d4c43`
  bytes): 22 failed / 9 passed — every multivalue negative fails, positives
  hold. DIRECTLY_VERIFIED.
- Fix-after new suite: 31 passed.
  `tests/foundry/test_source_lock_multivalue_identity.py`. DIRECTLY_VERIFIED.
- Impacted full `tests/foundry`: 372 passed, 1 skipped (established
  telemetry/environment skip, same as WS239). DIRECTLY_VERIFIED. Includes the
  WS239 P1 rewrite suite (15 tests, green → P1 retained), identity suite,
  remote-ref freshness suite, bootstrap/launcher/security suites.
- `tests/qualification`: 15 passed (infrastructure; not behavior credit).
- `ruff check .`: PASS. `ruff format --check .`: PASS (820 files).
- `compileall` on touched files: OK. `mypy`: NOT_RUN (not installed;
  CI covers). Full-repo pytest: NOT_RUN as a whole (47 pre-existing
  collection errors from missing third-party modules — environmental,
  unrelated, same as WS239).
- Negative controls: canonical+blank, blank+canonical, whitespace, newline,
  tab, duplicate, divergent, double-blank extras; env (`GIT_CONFIG_COUNT`)
  and global second records; missing/malformed/single-empty origins;
  undecodable bytes; invalid remote name; marker-URL non-echo in every
  diagnostic surface. No live network in any test (multivalue ref-check
  asserts no-probe ordering via a forbidden stub).

## 7. Evidence adjudication

- RETAINED: WS239 P1 rewrite negatives/controls (rerun green on `e5530bc9`
  as part of `tests/foundry`; no semantic change to the rewrite guard path).
- INVALIDATED (superseded, cause: parser seam moved): the WS239 claim that
  "ambiguous multi-URL configurations fail" for blank-adjacent variants —
  false on `f30d4c43`, repaired and re-proven on `e5530bc9`. Historical P1 and
  positive PASSes were NOT transferred to changed bytes without rerun; §6 is
  fresh on exact bytes.
- No credential/URL values appear in diagnostics, reasons, or this seal
  (marker string is a synthetic `.invalid` fixture name, never a secret).

## 8. Artifact hashes (sha256, exact committed bytes)

- `a3129733f57632c96dd23bd01db9d300bfdbae88597c20972a39a62cb99e544c`
  `tools/foundry/source_lock.py`
- `338014b6397bd73860af0ee9f4c5dd84fe3304aff76e465014d8f549eebb41e9`
  `tests/foundry/test_source_lock_multivalue_identity.py`
- `a9269e37959b67e75703861d2e8967a2d54871452486f3f0aecca1ab772bb6b1`
  `tests/foundry/test_source_lock_identity.py`
- `132bbfb83f6e7d9c84455f7af5976d49e2671d42d266225da4194de28cef7a29`
  `tests/foundry/test_remote_ref_freshness.py`
- `7a6284448e1d2fd103b48586d5474d105e012ff32cae81e52d136e72a50a6e35`
  `docs/foundry-execution/SOURCE_LOCK_REMOTE_EVIDENCE.md`

## 9. Remaining

CI on the replacement PR, external review, source-drift adjudication vs
latest main, and merge by a separately authorized integration step are
UNKNOWN (not run here). PR #202/#199 stay open until the replacement is
accepted. Safe-push publication + replacement-PR preparation recorded in the
workstream state file.
