# B1 — Is `final-current-boundary-20260927` sealed or living?

Status: **AUTHORITY_GATE (Coordinator)**. This memo prepares the decision; it does
not take it. Written 2026-09-30 by the CSN-POST-AUDIT-HARDENING-2026-09-30 campaign
(Claude Opus 5.5) against `origin/main` `0fbea2ec`.

## Facts

- `docs/project_health_20260930/LEDGER.md` H-08 calls the tree "the sealed boundary"
  and says re-sealing belongs to the PB-03/Coordinator lane.
- In practice the tree is rewritten in place: 30 commits on `main` touch
  `qualification/final-current-boundary-20260927/`, 14 of them on 2026-09-29/30
  ("Merge origin/main … and requalify at …", last `820a4642`). Each rewrites
  receipts, runtime identities and the FULL107 result files.
- The tree mixes **inputs** the runner and assembler read (`wsr20-ingest/`,
  `xmage_native_fixture_bindings.json`, `SOURCE_LOCK.json`,
  `SUCCESSOR_INHERITANCE_PROOF.json`) with **outputs** they write (`FULL107_*`,
  `AF*`, `receipts/`, `NATIVE_SUITE_RECEIPTS.json`, …). Both scripts hard-code the
  directory (`OUT_DIR` / `OUT`).
- On `main` the tree still reports XMage FULL107 5 PASS / 0 FAIL / 58 UNKNOWN /
  44 BLOCKED with `native_promotions: 0`. The GATE 2 producer (#411, issue #408)
  is merged; a full scratch run on `567b914e` produced 14 PASS
  (`native_promotions: 9`), with runner and assembler exiting 0. That result is
  **not** in the committed tree because writing it there is exactly the question
  below.

## Options

**(a) Living tree.** The directory is the *current* boundary, requalified in place
whenever its inputs change; each requalify commit is the seal of its epoch, and
older epochs are recovered by commit SHA.
- Change: rewrite H-08's wording from "sealed" to "requalified in place; the commit
  is the epoch". No code change.
- Cost: an epoch is identified by a commit, not a path, so a reference must cite
  the SHA.
- Unblocks: requalify now, which moves XMage FULL107 to the credited 14 PASS.

**(b) Sealed epochs.** `final-current-boundary-20260927` is frozen at a named commit,
and new runs write to a successor directory.
- Change:
  - split inputs from outputs;
  - make `--output-dir` explicit and required in both scripts;
  - have the PB-03 workflow pass the successor path;
  - add a guard test that refuses writes into a sealed directory.
- Cost: a mechanical refactor of about two scripts plus the workflow; the input files
  either move or are referenced from the sealed tree.

## Recommendation

**(a)**. It matches what `main` has done 30 times, needs no code, and the name
"current boundary" already says it is the moving one. Git gives each epoch
immutable, citable identity (commit + tree SHA) with less machinery than copied
directories. Choose (b) only if a consumer needs a *path* that never changes
content.

## After the decision

- (a): run `scripts/run_current_boundary_qualification.py --candidate xmage` and
  then `scripts/assemble_current_boundary_evidence.py` on a clean `main` checkout.
  Commit the regenerated tree and correct H-08.
- (b): do the refactor above, then run the same two scripts against the successor
  directory.
