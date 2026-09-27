# WSR22 Workstream Contract — FINAL-CURRENT-BOUNDARY-FREEZE-QUALIFICATION-20260927

## Objective

Produce the FINAL CURRENT-BOUNDARY runtime evidence required for the
Coordinator to decide between XMage and Forge and to perform Architecture
Freeze, under the current canonical pre-Freeze contract
`commander-lab.pre-freeze-qualification/2.0.0`. Execute the current contract;
do not restate WSR20/WSR21, and do not perform another generic engine survey.

## Source Lock

- Repository `moeendres-png/commander-playtest-lab`; dispatch main
  `c5f9418e755a02ffec0e02c34b4a739baf10f5f0`, tree
  `610f93d81e3b7154731d95472be6dcac05057eac`; verified, no drift.
- Authorized branch `wsr22/final-current-boundary-freeze-qualification-20260927`;
  sole-writer worktree `/home/moeen/code/wsr22-final-current-boundary-freeze`.
- Candidate identities fixed: XMage `b19596980f2734496ea1896504253e1bdd2756dd`
  (Lab runtime authority `593326713faeddb8c90df2fdc5e5bafbe1fccf1b`; Mage master
  NOT a permitted substitute); Forge `ef958ee91ac6c9ce0152189f2654bf6e05abf273`
  tree `fc3387bf37aab19d780b2939a235309ed32b0492` (WSR20 tip
  `18bba95a4528f6ab5910633f1f87f603b8c4ddf8`, evidence only).
- FULL107 frozen source `5a2e4f462fd45bba25f2271153212aab9faf09f5`, 107 rows,
  immutable.
- Protocol `2.0.0`; schema blob `ea8651f75a1461ecc41dc1f24586c00bff97fee5`.
- Full blob/sha256 bindings: `SOURCE_LOCK.json`.

## In Scope

Gate 0 source/contract/build lock; Gate 1 direct official Rules-authority
capture and freshness-conflict resolution; current Protocol-2 AF01 for both
candidates; fresh current-boundary execution of all 107 effective rows per
candidate; `WS05-CMD-START-2` under the v1.0.6 successor; player cardinality
2P/3P/4P/5P with bounded 6P; hidden-information, actual-card, Rules-RNG and
semantic-replay probes; AF00–AF11 explicit verdicts per candidate;
current-boundary comparison; divergence isolation; provider-blocker
classification; adversarial self-review; resumable evidence tree.

## Out of Scope

Selecting a Production Provider; claiming Architecture Freeze; creating the
Production Repository; modifying XMage or Forge production Rules semantics;
repinning either engine; merging WSR20 into Forge master; rewriting historical
WSR20/WSR21 evidence; provider remediation; pilot/deckbuilding/performance work;
touching PR #261 or any foreign workstream.

## Ownership

Single writer on the authorized branch/worktree. Forge and Mage references are
read-only: inspected, built and executed, never edited (verified byte-clean
after every run). No other workstream's branch or worktree was mutated.

## Hard Gates

- No historical verdict may enter a current-boundary count.
- Every denominator row must carry exactly one explicit outcome per candidate.
- Rules authority must be directly captured, never inherited.
- No provider score, ranking or winner anywhere.
- No engine production-code modification.
- Unsupported production-reachable paths fail closed.

## Forbidden Shortcuts

First option; random option; default yes/no; silent skip; internal engine AI
substituting for external decisions; requested-option filtering that
reconstructs legality; manual outcome injection; construction/import counted as
runtime behaviour; collapsing a failure into UNKNOWN instead of repairing it.

## Evidence Requirements

Machine-readable packets plus human-readable summaries for every gate; exact
runtime identities; per-change impact adjudication; schema/JSON validation;
denominator-complete accounting; lint/format on touched code; adversarial
self-review.

## Stop Conditions

Complete when the Coordinator can adjudicate provider selection and
Architecture Freeze without guessing — i.e. every gate has an explicit verdict,
every denominator row is classified, divergences are isolated, and blocking
gaps are classified with a concrete smallest remediation. Otherwise stop only on
a proven terminal Source / Rules-Authority / Scope / External-Dependency gate.
