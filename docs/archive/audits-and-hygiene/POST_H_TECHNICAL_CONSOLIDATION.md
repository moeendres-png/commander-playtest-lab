# Audit H – Technical consolidation

## Baseline

- Canonical GitHub main at H start: `f8d42919a37e93f34756907ac86ceb2e6a13be4c`.
- Canonical tree: `ef531c1b9600d963699ec4c663a8b07061efd292`.
- Package version: `1.13.4`.
- G technical work is complete. Deletion of `audit/g-modeling-data-quality` is an explicit deferred manual follow-up and is not reopened by H.

## H scope

H consolidates active technical truth, release/recovery behavior, runtime/source hygiene, active workflows, active Drive status documents and the branch handoff to I. It does not modify decklists, inventory, opponent truth, purchases, physical allocations or the completed G decision-quality work.

## Technical consolidation

### Release/recovery

The active `Release Artifacts` workflow previously ran on pull requests, `release/**` pushes and manual dispatch, but not on an ordinary canonical `main` push. That allowed a fully verified recovery set to be tied to a synthetic PR merge SHA even when the repository was later squash-merged to a different canonical main commit with the same tree.

H adds `main` as an explicit push trigger while retaining pull-request validation and `release/**` behavior. The workflow already binds repository ZIP, bundle, status, manifest and reproducibility metadata to `GITHUB_SHA`; therefore a post-merge main run now provides a canonical-commit recovery snapshot without redesigning release semantics.

`package_version_bump_required = false` because product/package code and runtime semantics are not changed by H. `recovery_snapshot_refresh_required = true` because the recovery workflow itself is corrected and must be rerun on the final canonical main after merge.

### Runtime/source contract

The baseline clean-tree contract was exercised with doctor, phase-8.6 audit, structural validation and tactical/offline validation. Runtime output remained under ignored runtime paths and did not dirty the tracked tree. H does not mass-refactor `artifacts/`; individual historical artifacts remain evidence unless a reproducible tracked-tree mutation requires a narrow fix.

### Active workflows

Canonical active workflow truth is the set of files present under `.github/workflows/` on main:

- `ci.yml` – required CI quality/security gate.
- `release-artifacts.yml` – required PR release/recovery gate and, after H, canonical-main recovery snapshot generator.
- `windows-runtime.yml` – required Windows runtime hygiene gate.
- `external-engine-integration.yml` – optional/manual external XMage integration; not an H completion gate.

Historical GitHub Actions workflow records whose source files are absent from main are historical metadata, not parallel implementations.

### OpenAI integration

H keeps the existing optional OpenAI integration. It uses explicit project configuration, separate session/trace runtime paths and an optional dependency group. Live API execution and API-key provisioning are not H gates. Local dependency installation was unavailable in the current recovery runtime, so optional live-runtime compatibility is delegated to the existing repository test/CI boundaries rather than redesigned.

## Drive organization

Drive readback shows older `PLAYTEST_LAB_CURRENT_STATUS` and `PLAYTEST_LAB_SOURCE_INDEX` material still claiming much older software/data states. Those records are historical evidence, not current software truth. After H is merged and the post-merge recovery snapshot succeeds, Drive must expose one current technical status tied to canonical GitHub main and move/mark superseded current-looking documents and legacy `LATEST` recovery artifacts as historical without deleting unique evidence.

## Branch organization

H does not redo F branch forensics. The G work branch is `DELETE_SAFE_MANUAL` but deletion is explicitly deferred by the user. Branches retained by F because of exclusive/history/recovery value remain `DEFER_TO_I` unless refreshed evidence proves otherwise. I owns final historical branch disposition.

## Validation and recovery

Final local and GitHub validation results are filled only from actual runs. A local recovery build is a functional check of the H tree; the authoritative commit-bound recovery proof must be produced again after merge on the actual canonical main commit.

## Preserved boundaries

- Structural model estimates are not empirical win rates.
- Tactical Oracle is not XMage or Forge.
- External rules-engine validation remains pending unless a real external workflow succeeds.
- Real-play calibration remains inactive and is not an H gate.
- No deck, inventory, opponent, purchase or physical-allocation mutation is authorized by H.

## Local validation evidence

- Python: `3.13.5`; GitHub CI remains authoritative on Python `3.12`.
- `pytest --collect-only`: 326 tests.
- Deterministically grouped execution: 325 passed, 1 expected external-engine differential skip, 0 failed.
- H workflow contract regression test: passed.
- `python -m compileall -q src tests`: PASS.
- `git diff --check`: PASS.
- Doctor + phase-8.6 audit + structural validation + tactical/offline validation: tracked tree remained clean.
- Ruff `0.16.2` on H's changed Python test: PASS; formatter check PASS.
- Global repository Ruff/format remains a pre-existing non-H-clean baseline. H does not mass-format historical scripts/tests because CI intentionally gates changed Python files and H forbids cosmetic scope expansion.
- Mypy is not installed in the recovery runtime; local installation also cannot complete because the environment package index does not expose the required build dependency. Marked `LOCAL_UNAVAILABLE`; GitHub quality remains the final authority.
- Optional OpenAI dependency installation is likewise `LOCAL_UNAVAILABLE` in this local recovery runtime and is not a live-API H gate.
