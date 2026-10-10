# #668 — source-bound batch resume

Direct Owner takeover: Codex implements and integrates this bounded workstream;
no further OC dispatch. Earlier monthly-quota/cancelled/clean-rescue receipts stay
historical in issue #668; they do not prove an implementation or test result.

Source lock: Lab main `977e1d64eab5f1b9ad1a071bd378267cbc89d3a4`, tree
`69811693d3a320e21cfae3a48977507cb5ce6fda`. Branch
`fix/batch-resume-source-20261010`. Writable batch module, dedicated tests and this
directory only. Claude #662 A1/A2, #634 B2 and #441 remain read-only. No config,
pins, qualification contracts, rules, decisions or RNG changes.

Reuse-first: EXTRACT_AND_GENERALIZE existing run key/record/retry mechanism;
REUSE_AS_IS actual engine cwd resolver and privacy formatter. Identity version2
conservatively invalidates old cache keys. No relabelling of historical records.

Identity is refreshed for every case/cache lookup, including repeated calls on
one object. Explicit `.jar`/`.py` command tokens resolve against the same cwd
authority as the process; each command position has its own SHA256. Ordered
command, resolved cwd, decision limit and request timeout feed a configuration
digest. Public identity fields expose no paths/command arguments. Missing or
unreadable artifacts raise a fixed safe configuration error before cache reuse.
Post-game identity drift cannot produce a completed record; existing classified
failure/retry behaviour is preserved. Different cases may execute under refreshed
identities, each with its own run key.

Boundary: explicit file tokens, not every JVM executable, transitive classpath,
environment variable, dependency or mutable database. Artifacts must remain
stable during execution. Before/after hashing detects persistent drift, not a
malicious change-and-restore between checks. This is no hermetic build proof or
native/card-behaviour qualification.

Old code controls: 10 FAIL /4 PASS (exit1) on locked baseline with new controls.
Additional unreadable-identity and privacy controls added afterward. Corrected
validation and fresh-context review/hosted exact-head results are recorded in
the immutable GitHub issue/PR receipts. An initial adjacent privacy run without
inherited PYTHONPATH had 87 PASS/2 FAIL due to child import setup; corrected
environment rerun is required, no assertion changed.

Status: COMPLETE (2026-10-10). PR #673, head
`ed0de7a3c59d56c8b8700056cf59c57780b2eae2`, merged normally as main
`f0e7af9116adf8446d0fd006fa80933cc0784f30`. Required quality/security/
infrastructure PASS on the exact head and on that main commit; integration with
main `93cf55af` plus #673 ran the affected tests (269 passed). #668 closed with the
merge receipt (issue comment 6097210908). UNKNOWN/NOT_RUN != PASS. No native Foundry
certificate, provider release or Freeze claimed. Required handoff is persisted
in #668, including exact reviewed source, tests, CI, merge and remaining limits.
