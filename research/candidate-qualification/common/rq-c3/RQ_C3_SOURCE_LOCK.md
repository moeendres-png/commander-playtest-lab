# RQ-C3 Source Lock

Workstream: `RQ-C3-RULES-AUTHORITY-CLOSURE`
Branch: `research/rules-authority-closure-rq-c3-20260910`
Worktree: `/home/moeen/code/rq-c3-rules-authority-closure`
Writer: `foundry-implementer` (`opencode-go/muse-spark-1.3-contributor`, effort HIGH)

## Parent locks (immutable inputs; NOT modified)

- RQ-C1 HEAD: `714ad417c1c090eb4ddf1ccd0828a2e869a80a74`
- RQ-C1 TREE: `709a5944c9826dbaaa433052f3538425c8f0573b`
- RQ-C1 branch: `research/candidate-neutral-architecture-reverser-corpus-rq-c1-20260910`
- RQ-C1 disposition: `NEUTRAL_CORPUS_READY_PENDING_RULES_ADJUDICATION`
- RQ-C2 HEAD: `fb7d493e6b04a59d09bc43d1de3cd8c2eaf59bc8`
- RQ-C2 TREE: `7abcb331fd378a9663bd9222eb8135ad34dff102`
- RQ-C2 branch: `research/rules-authority-verification-rq-c2-20260910` (pack-complete commit)
- RQ-C2 disposition: `RULES_AUTHORITY_PACK_READY_FOR_SOL`

Verified at RQ-C3 start: worktree HEAD == `fb7d493e6b04a59d09bc43d1de3cd8c2eaf59bc8`, tree == `7abcb331fd378a9663bd9222eb8135ad34dff102`, branch as above, working tree clean except untracked `research/candidate-qualification/common/rq-c3/` output directory itself.

## Non-modification guarantee

No artifact under `research/candidate-qualification/common/rq-c1/` or `research/candidate-qualification/common/rq-c2/` is modified by this workstream. All corrected material lives under `research/candidate-qualification/common/rq-c3/` only. RQ-C3-local validation re-checks this on every run (see `RQ_C3_PARENT_IMMUTABILITY.json` + `validate_rqc3.py`).

## Official authority baseline (reused unchanged from RQ-C2; NOT refreshed)

- Comprehensive Rules: official text effective **August 7, 2026**, retrieved 2026-09-10 from first-party Wizards host `https://media.wizards.com/2026/downloads/MagicCompRules%2020260819.txt` (file header states effective August 7, 2026). Local working-copy sha256 `4381ad1b39ab2c05f7d03633a20f711ed37277074d3266dcba5f38cbb527423f` (977,822 bytes, 9,397 lines). Full provenance in RQ-C2 `RQ_C2_AUTHORITY_BASELINE.md`.
- Official Oracle/rulings: first-party Gatherer, pages retrieved 2026-09-10 for 11 corpus cards (see RQ-C2 baseline). No silent refresh or substitution in RQ-C3; corrections use exactly the RQ-C2 captured evidence plus explicit Sol High adjudication below.
- Secondary crosscheck only: Scryfall 49/49 (2026-09-10). NEVER authority.

## Authority order (binding)

1. newest direct user statement (this RQ-C3 contract + Sol High adjudication §3);
2. freshly verified repository/branch/commit/tree/worktree;
3. current Actions/artifacts/tests/source;
4. RQ-C2 captured official-authority evidence (baseline above);
5. current official CR/Oracle/Rulings only via RQ-C2 baseline (no independent refresh);
6. historical reports/chats/handoffs (provenance, not authority).

Candidate engines (Forge, XMage, Argentum, Manabrew), candidate self-tests, and Q6 are NOT Rules authority.

## Evidence policy

Classes exactly as project policy: `DIRECTLY_VERIFIED`, `CODE_DERIVED`, `TECHNICALLY_CONFORMANT`, `EXTERNALLY_RULE_VALIDATED`, `MODELED`, `SYNTHETIC`, `UNKNOWN`. RQ-C3 records `DIRECTLY_VERIFIED` for transformation/validation facts only. Sol-approved official-Rules expected outcomes receive `EXTERNALLY_RULE_VALIDATED`. No candidate receives `TECHNICALLY_CONFORMANT` or behavior credit here (`BEHAVIOR_CREDIT_CHANGE = 0`).

## Invariants

`BEHAVIOR_CREDIT_CHANGE = 0`. `FULL107 = NOT_RUN`. `ARCHITECTURE_FREEZE = NOT CLAIMED`. `PRODUCTION_PROVIDER = NOT SELECTED`. No candidate executed. RQ-C1/RQ-C2 unmodified.
