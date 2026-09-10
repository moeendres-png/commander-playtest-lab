# RQ-X1 — XMage Source Lock (DIRECTLY_VERIFIED)

Status: `XMAGE_SOURCE_LOCK_VERIFIED`

Verification performed 2026-09-10 (UTC) by the RQ-X1 worker, by direct
`git rev-parse` in both checkouts. No builds, no mutations, no upgrades.

## CPL research base (this repository)

| Field | Value |
|---|---|
| Repository | `moeendres-png/commander-playtest-lab` |
| Worktree | `/home/moeen/code/rq-xmage-architecture-audit` |
| Branch | `research/xmage-architecture-reverser-audit-20260910` (`git branch --show-current`) |
| HEAD commit | `c162871ba416c338d37f83a44fbd5b054e79ca0e` (`git rev-parse HEAD`) |
| HEAD tree | `b75a51d3326f502f33f0af2ce5d897ac89d60cc5` (`git rev-parse HEAD^{tree}`) |
| Working tree at audit start | clean (`git status --short --branch` showed only the branch header, no dirty entries) |

HEAD is the PR #172 merge (OpenCode/Muse execution-system consolidation on top
of post-PR173 canonical mission). This matches the contracted CPL research base.

## XMage read-only checkout (audited engine source)

| Field | Value |
|---|---|
| Repository | `moeendres-png/mage` (upstream XMage fork mirror) |
| Checkout path | `/tmp/rq-xmage-src` |
| Commit | `77d7646da6958fdf8125ee7c8f4aabd130d21d4c` (`git -C /tmp/rq-xmage-src rev-parse HEAD`) |
| Tree | `f0a028b265f9c008ea0aedc4cec6b8f14500b69f` (`git -C /tmp/rq-xmage-src rev-parse HEAD^{tree}`) |
| State | detached HEAD (`## HEAD (no branch)`), `git status --porcelain=v1` empty (clean) |
| Top commit subject | `feat: implement Ashling the Limitless` (`git log --oneline -3`) |

This matches the contracted XMage identity exactly. It is intentionally tied to
existing project XMage evidence (J-P3B spike lineage, frozen at a different
older pin `06d166b` — see §4). It was NOT replaced with current master and was
NOT upgraded at any point during this audit.

## Mutation-surface compliance (DIRECTLY_VERIFIED)

- `/tmp/rq-xmage-src` was opened read-only: only `git rev-parse` / `git status` /
  `git log` (plumbing) plus file reads and `rg`/`find`/`wc` counting were used.
  Post-audit `git status --porcelain=v1` in `/tmp/rq-xmage-src` is empty.
- No XMage file was repaired, extended, patched, or tested by modification.
- No CPL provider code, Q6, WS48/WS50/WS51, hardening, AGENTS.md, opencode
  config, shared Foundry tooling, or optimizer surface was touched. The only
  CPL writes are the twelve RQ-X1 files under
  `research/candidate-qualification/xmage/rq-x1/` (owned surface).
- No runtime mirror was implemented; no adapter was written; existing XMage
  builds/tests were not executed (counts are static file/annotation counts,
  not runs).

## Relation to prior XMage pins in project evidence

- J-P3B spike evidence (`docs/J_P3_XMAGE_SPIKE_REPORT.md`) is frozen at
  `xmage_1.4.60V3 @ 06d166b098ad36b277edef01116472203d5a047e` — an OLDER,
  different pin. Findings at `77d7646d` do not retroactively re-qualify or
  invalidate J-P3B bounded results; impact adjudication would be required
  before mixing evidence across pins (none performed here — out of scope).
- The `77d7646d` pin was chosen by the contract because existing project XMage
  evidence is tied to it. All file:line cites in this audit are valid only at
  this pin.

## License correction (DIRECTLY_VERIFIED, supersedes task premise)

The task brief states "XMage code is GPL-licensed". At this pin the repository
root `LICENSE.txt` begins with `MIT License / Copyright (c) 2010
betasteward@gmail.com` (first 8 lines read directly), and a repo-wide search
for `General Public License|GPLv` returns zero hits. The GPL premise is
factually wrong at this pin. This does NOT authorize copying: any direct reuse
or port of XMage source or tests still requires `LEGAL_REVIEW_REQUIRED`
clearance (see `XMAGE_TEST_CORPUS.md`). Classification: DIRECTLY_VERIFIED.

## Evidence-classification discipline used in this audit

- `DIRECTLY_VERIFIED`: shell-verified identities, counts, and quoted file
  content re-checked by the worker (source-lock SHAs, test counts, RNG
  utility body, license header, absence of `stateId|requestId`, key method
  signatures/line counts).
- `CODE_DERIVED`: all semantic findings from read-only source inspection by
  six parallel exploration passes (decision seam, selection→execution binding,
  hidden info, RNG/replay, test corpus, multiplayer seam). Source inspection
  is NEVER runtime evidence.
- `UNKNOWN`: anything requiring execution (actual client/server behavior,
  timing, concurrency, performance, true hidden-info safety under adversarial
  observation, real RNG streams, replay fidelity). No runtime claims are made.
- Nothing in this audit is `RUNTIME_VERIFIED`, `EXTERNALLY_RULE_VALIDATED`
  (no Comprehensive Rules cross-check performed), or a qualification PASS.
