# Run-manifest integrity repair

## Problem and repaired behavior

On audit-main `7890aed0f692e67052dd51925575380828996ab4`, `runs-verify`
could return `valid` after a file was added or its entry was removed from the
manifest. The producer omitted every file named `run-manifest.json`, including
nested receipts. Malformed JSON object shapes could raise uncaught exceptions;
duplicate JSON keys were silently accepted. These were reproduced locally:
19 failing and two passing baseline regression cases (BASELINE.json).

The producer and verifier now share a complete regular-file inventory:

- only the root `run-manifest.json` and explicit `.quarantine` components below
  the supplied run root are excluded; nested manifests are ordinary artifacts;
- declared and observed artifact names must match exactly;
- schema v1 headers, canonical relative paths, integer sizes and SHA-256 values
  are validated before use; duplicate keys and non-finite JSON values fail closed;
- symlinks, Windows directory junctions and non-regular artifacts are rejected
  without reading their targets;
- size and digest come from the same open file, with observed identity/change
  checks; scan/read failures produce a structured negative verification result;
- creation validates the full document before the existing atomic writer replaces
  a previous manifest. Failed creation preserves the previous seal.

The public schema remains v1. Existing completed/failed/aborted/incomplete status
handling is retained. No engine, provider, Rules, replay or evidence classification
is changed. The CLI consumer still exits 1 for invalid evidence, now with a JSON
result rather than an uncaught decoder/object exception.

## Scope and limits

Use quiescent run trees: this is not a transactional snapshot against a malicious
concurrent filesystem writer. Observed changes are rejected; callers still must
stop artifact writers before sealing/verifying. Windows path/descriptor `ctime`
values can differ for the same unchanged file; Windows identity comparison uses
file ID, size and modification time, while POSIX also checks change time.

An internally consistent manifest is not a signature, trusted expected artifact
set, or proof of simulation correctness. Removing both an artifact and its record,
or replacing a manifest and all matching data, cannot be disproved without an
external trusted anchor. This repair makes no such authenticity claim.

Previously generated incomplete manifests can now fail validation. Preserve sealed
historical evidence; do not silently regenerate it or promote it to PASS. No stored
run or qualification artifact was rewritten in this workstream.

## Validation and persistence

The new regression module covers malformed headers and entries, duplicate keys,
UTF-8 failure, missing/unlisted artifacts, nested manifests, path aliases, links,
special files, read/scan errors, failed-publication preservation, legacy statuses,
relative quarantine handling and structured CLI rejection. Existing atomic/storage
tests and Phase10 acceptance exercise the current producer/consumer contract.

The failing-before checkpoint is commit `051dffba`; the repair checkpoint is
`0269a34c`. Subsequent validation and the exact published PR head are recorded in
CHECKPOINT.json and the PR handoff. Windows capability skips are not PASS; the
Linux CI run must cover the symbolic-link and FIFO cases before integration.

## Handoff

Source lock and ownership: WORKSTREAM.md. Findings: BASELINE.json and this document.
Changes: one production storage module, one new test module, this evidence packet.
No provider selected; no Architecture Freeze; no active foreign surface modified.
After publication, Sol may integrate through the normal PR path only after fresh
exact-head checks and review/ownership gates pass, then persist merge HEAD/TREE.
Do not repeat provider qualification or restart the earlier governance campaign.
