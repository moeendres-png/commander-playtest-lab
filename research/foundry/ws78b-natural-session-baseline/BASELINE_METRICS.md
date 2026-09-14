# WS78B Baseline Metrics (human-readable companion to `BASELINE_METRICS.json`)

Every number below carries its classification. Unclassified numbers are not
claimed. `UNKNOWN` fields were verified absent, not overlooked.

## WS191 — Forge bridge integration (lane: XHIGH)

DIRECTLY_VERIFIED identity: model
`opencode-go/muse-spark-1.3-contributor`, provider `opencode-go`, override
`canonical`, variant `canonical_agent_variant`, CLI `1.18.30`, profile
`forge`, base `aa5c00aa…`, branch `ws191/forge-aa5c-h4f-integration-20260914`
(from `launch-context.json` + one-line `metrics.jsonl`).

- Run-dir visible window: 2026-09-14T00:17:28Z → 00:35:12Z = 1064 s
  (DIRECTLY_VERIFIED file mtimes). This is a lower bound on activity, not
  session wall time (UNKNOWN — no export `info.time`).
- Session id: launch-context `session` is `""` (DIRECTLY_VERIFIED); OpenCode
  session ID UNKNOWN; no export JSON in run root (DIRECTLY_VERIFIED).
- Tokens: input / output / reasoning / cache-read / cache-write all UNKNOWN
  (DIRECTLY_VERIFIED absence: no token keys in `metrics.jsonl`, no export).
  Cache hits are never inferred from context shape.
- Turns / tool calls / by-tool / errors / retries / timeouts / no-progress:
  all UNKNOWN (no export to feed `session_stats.py`).
- Cost (provider-reported): UNKNOWN. Quota indicators: UNKNOWN.
- Context growth: UNKNOWN.
- Validated milestones (7, session-reported DIRECTLY_VERIFIED bytes in
  `ws191-results.json` + transcript + stderr):
  1. 59-test bridge unit/process suite, BUILD SUCCESS;
  2. reactor compile incl. bridge + 0 checkstyle violations;
  3. separate-process 4-message handshake `WS191_HANDSHAKE=PASS`
     (engine_commit `aa5c`, conservative capabilities, exit 0);
  4. H01 Clone/Humility 3/3 PASS;
  5. WS76 immediate-concession 5/5 PASS;
  6. Ws59G04 adjacent concession 4/4 PASS;
  7. minimal additive delta: 35 files, +8446/−0, sole non-bridge path
     1-line `pom.xml` wiring.
  Bridge engine init 7938 ms (DIRECTLY_VERIFIED stderr). Historical H4F/H01
  credit explicitly NOT_RUN/UNKNOWN per the session's own report. Forge-side
  independent revalidation from this CPL worktree is NOT_RUN (separate repo,
  no reference root declared); terminal SHA `7360737b…` is task-provenance.
- Checkpoints: 3 state patches (DIRECTLY_VERIFIED) + session-reported port
  checkpoint `77cca347` and terminal `7360737b…` (CODE_DERIVED from run
  root). Terminal status COMPLETE with `validated_head == 7360737b…`
  (DIRECTLY_VERIFIED state-file bytes).

## WS196 — CPL cross-repo tool routing (lane: HIGH)

DIRECTLY_VERIFIED identity: same model/provider/override/variant/CLI,
profile `cpl`, base `7725570b…`, branch
`ws196/cross-repo-tool-routing-20260914`.

- Run-dir visible window: 2026-09-14T00:26:02Z → 00:37:27Z = 685 s
  (DIRECTLY_VERIFIED). Terminal commit `691dbe50` authored 00:36:23Z
  (DIRECTLY_VERIFIED `git show`), ~10.3 min after launch, inside the window.
  True session wall UNKNOWN.
- Session id / tokens / turns / tools / errors / retries / cost / quota /
  context: all UNKNOWN for the same verified-absence reasons as WS191.
- The ~127k context figure is user-reported provenance only (UNKNOWN until
  an export-backed `session_stats.py` summary verifies it).
- Validated milestones (DIRECTLY_VERIFIED in this repo): terminal commit
  `691dbe50` (`git log --all --grep=WS196`, `git show`: 6 files, +530/−0);
  `validated_head == 691dbe50…` in the dedicated state file; terminal status
  COMPLETE pending review (checkpoint patch bytes). Authored: 12 hermetic
  test functions in `tests/foundry/test_canonical_tool_routing.py`
  (CODE_DERIVED blob count, 435 lines). Test execution verdict UNKNOWN (no
  run log in run root).

## Comparative rates (CODE_DERIVED over lower-bound denominators)

- WS191: 7 claims / ≥17.7 min ≈ 23.7 claims/hr visible. True rate UNKNOWN
  (denominator incomplete; numerator session-reported).
- WS196: 1 commit / ≥11.4 min ≈ 5.3 commits/hr visible; 12 test functions
  authored ≈ 63 test-fns/hr authored (execution UNKNOWN).
- Turns/milestone, tools/milestone, quota-dollar/milestone, token
  composition, cache-read ratio, retry cost: all UNKNOWN — no honest
  comparison is possible on those axes until exports are captured.
- Lane contrast: bounded XHIGH adjudication (WS191) unlocked the additive
  port analysis then 7 fresh runtime validations; routine HIGH (WS196)
  delivered deterministic routing + authored hermetic tests. No
  quality/cost equivalence claimed.
- Sealing overhead: WS191's 3674-entry artifact index (CODE_DERIVED) is
  dominated by the config-dir snapshot including `node_modules`; scope
  future indexes to workstream outputs (MODELED recommendation).

## Accounting ledger

Provider-reported cost: UNKNOWN. Locally token-derived estimate: UNKNOWN
(no tokens). Quota/accounting indicators: UNKNOWN. Any disagreement remains
`ACCOUNTING_UNKNOWN`. Detail in `QUOTA_ECONOMICS.md`.
