# Run-manifest verification integrity

Objective: make storage run verification reject malformed or incomplete artifact
inventories instead of returning valid or raising an unhandled parsing exception.

Authority: direct user request for additional important code defect detection,
repair and publication. One bounded storage-integrity workstream.

Source lock: main `7890aed0f692e67052dd51925575380828996ab4`, tree
`32b7a20115ccfe7ad89409ff3ac71f9697a5d1ae` (includes merged Astra PR #280).
Branch: `astra/run-manifest-integrity-20260928`, exclusively owned by this session.
Reuse the now-free dedicated Astra checkout; no foreign worktree access.

Owned: `src/commander_lab/storage/run_integrity.py`, a new focused regression test
module, and this evidence directory. Existing acceptance and CLI consumers are
validated without modifying their implementation. No overlap with published
sbmax/full-completion or WSR27 branches, checked against their merge bases.

Out of scope: provider/Rules/replay semantics, launcher/routing, qualification
artifacts, cache identity, concurrent hostile filesystem security, signatures or
external attestation. Hash integrity is not simulation correctness or authenticity.

Reuse gate: inspected storage atomic writer, current manifest producer/verifier,
CLI and Phase10 consumers, existing tests and repository history. No compatible
sealed donor repair found; the similarly named calibration patch is unrelated.
Reuse the existing atomic writer; do not introduce another artifact format.

Hard gates: reproduce against source-locked main before repair; keep schema v1
valid producer output interoperable; reject invalid inputs explicitly; preserve
existing manifests when creation fails; no foreign mutation or evidence promotion.
An explicit `.quarantine` subtree remains excluded; only the root manifest itself
is excluded from ordinary artifact coverage.

Persistence: commit failing-before test evidence, then validated repairs, then
publish a dedicated PR with exact-head CI and a Sol integration handoff. No need
to repeat the already completed governance campaign or provider qualification.

Required evidence: negative reproduction, positive producer/verifier round trip,
existing storage/CLI/acceptance regression, Ruff/format, strict mypy, compileall,
current source/ownership readback and exact PR head. Missing runtime coverage
stays NOT_RUN; stop for genuine source/ownership/authority gates.

ARCHITECTURE_FREEZE = NOT CLAIMED
PRODUCTION_PROVIDER = NOT SELECTED
