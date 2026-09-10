# RQ-C2 Source Lock

Workstream: `RQ-C2-OFFICIAL-RULES-ORACLE-AUTHORITY-VERIFICATION`
Branch: `research/rules-authority-verification-rq-c2-20260910`
Worktree: `/home/moeen/code/rq-c2-rules-authority-verification`
Model: `opencode-go/muse-spark-1.3-contributor` (effort HIGH)

## RQ-C1 parent (immutable input)

- RQ-C1 parent HEAD: `714ad417c1c090eb4ddf1ccd0828a2e869a80a74`
- RQ-C1 parent TREE: `709a5944c9826dbaaa433052f3538425c8f0573b`
- Parent branch: `research/candidate-neutral-architecture-reverser-corpus-rq-c1-20260910`
- RQ-C1 terminal disposition: `NEUTRAL_CORPUS_READY_PENDING_RULES_ADJUDICATION`
- RQ-C1 scope taken as input: 40 scenario families, 15-scenario first wave,
  37 Rules Authority packets, 3 Oracle-text verification flags
  (Murder / Cultivate / Ornithopter), 15 negative controls.

Verified at RQ-C2 start: worktree HEAD == `714ad417`,
tree == `709a5944`, branch as above, working tree clean except the
untracked RQ-C2 output directory itself.

## Non-modification guarantee

No RQ-C1 artifact under `research/candidate-qualification/common/rq-c1/`
is modified by this workstream. All corrected recommendations live in
`research/candidate-qualification/common/rq-c2/` only. RQ-C2-local
validation re-checks this on every run.

## Official authority baseline (single coherent baseline)

- Comprehensive Rules: official text effective **2026-08-07**, retrieved
  2026-09-10 from first-party Wizards host
  `https://media.wizards.com/2026/downloads/MagicCompRules%2020260819.txt`
  (file content header states "effective as of August 7, 2026").
  Local working copy sha256:
  `4381ad1b39ab2c05f7d03633a20f711ed37277074d3266dcba5f38cbb527423f`
  (977,822 bytes, 9,397 lines). Full provenance in
  `RQ_C2_AUTHORITY_BASELINE.md`.
- Official Oracle / rulings: first-party Gatherer
  (`https://gatherer.wizards.com`), pages retrieved 2026-09-10 for
  11 corpus cards (see baseline doc for the page list).
- Secondary crosscheck only: Scryfall API, 49/49 corpus names resolved
  2026-09-10. Scryfall is NEVER authority; status
  `SECONDARY_METADATA_CROSSCHECK` where used.

## Authority order (binding)

1. newest direct project instruction;
2. current official Comprehensive Rules (baseline above);
3. current official Oracle card text (Gatherer);
4. current official card-specific rulings (Gatherer);
5. exact RQ-C1 scenario specification;
6. candidate-neutral project evidence.

Candidate engines (Forge, XMage, Argentum, Manabrew), candidate
self-tests, and Q6 are NOT Rules authority and are not used as
expected-outcome authority anywhere in this pack.

## Evidence policy

Classes used exactly as defined by project policy: `DIRECTLY_VERIFIED`,
`CODE_DERIVED`, `TECHNICALLY_CONFORMANT`, `EXTERNALLY_RULE_VALIDATED`,
`MODELED`, `SYNTHETIC`, `UNKNOWN`. RQ-C2 establishes `DIRECTLY_VERIFIED`
for exact source/retrieval facts only. RQ-C2 awards
`EXTERNALLY_RULE_VALIDATED` to NOTHING; only Sol High may promote
prepared official-authority evidence into that class. `RUNTIME_VERIFIED`
is not introduced.

## Terminal verdict vocabulary (exactly one at end)

`RULES_AUTHORITY_PACK_READY_FOR_SOL` /
`RULES_AUTHORITY_PACK_READY_WITH_SOURCE_BLOCKERS` /
`RULES_AUTHORITY_PACK_CORPUS_CORRECTION_REQUIRED` / `BLOCKED_UNKNOWN`.

Invariants repeated at handoff: `BEHAVIOR_CREDIT_CHANGE = 0`,
`FULL107 = NOT_RUN`, `ARCHITECTURE_FREEZE = NOT CLAIMED`,
`PRODUCTION_PROVIDER = NOT SELECTED`.
