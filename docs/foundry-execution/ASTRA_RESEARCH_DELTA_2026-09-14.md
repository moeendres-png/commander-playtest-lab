# Astra / Deep-Research Delta — 2026-09-14

Status: `CURRENT-SOURCE RECONCILIATION`

Purpose: reconcile the earlier OpenCode + Muse Spark 1.3 research recommendations against current `main`. The research remains useful design provenance, but it is not current repository state. Current Git/repository evidence wins on conflict.

Source lock for this reconciliation:

- Commander Lab `main`: `7725570b6b8690daed6e645dc1611f5e196de8c5`
- Tree: `8b926c73cf35468c6110d64615c5f5e863ac2aa1`
- WS190 is already integrated at this main head.

## Top-10 recommendation reconciliation

| Research action | Current disposition | Current source truth |
|---|---|---|
| 1. Strengthen `AGENTS.md` | **DONE** | Root `AGENTS.md` is canonical durable policy. |
| 2. Configure `opencode.json` | **DONE** | Canonical model/effort/permissions are machine-enforced; HIGH default, XHIGH escalation, below-HIGH disabled. |
| 3. Worktree isolation + source locks | **DONE / HARDENED** | `tools/foundry/source_lock.py`, `worktree_inventory.py`, writer locks, explicit-state bootstrap and workstream ownership exist. |
| 4. Failure-analysis skill | **DONE** | `.opencode/skills/failure-classification/SKILL.md` plus deterministic `cluster_failures.py`. |
| 5. Test-impact tooling | **DONE** | `.opencode/skills/test-impact/SKILL.md` plus `tools/foundry/test_impact.py`. |
| 6. Evidence / artifact tooling | **DONE** | Evidence-seal skill plus `tools/foundry/evidence.py` provide deterministic manifests/hashes and handoff generation. |
| 7. Rate-limit / provider availability policy | **RESEARCH CLAIM SUPERSEDED AS POLICY INPUT** | Do not encode the report's fixed `100 RPM` claim without current provider evidence. WS190 instead provides an explicit operator-selected Zen override, no auto-fallback, with the canonical Go default unchanged. |
| 8. Metrics dashboard/input capture | **FOUNDATION DONE** | `tools/foundry/metrics.py`, `session_stats.py`, and `docs/foundry-execution/METRICS.md` define JSONL metrics and session statistics. Presentation/dashboard polish is optional, not a correctness blocker. |
| 9. HIGH-vs-XHIGH benchmark | **DESIGN COMPLETE / EXECUTION NOT RUN** | `HIGH_XHIGH_BENCHMARK.md` defines the replay design. No results are claimed. Do not fabricate benchmark conclusions during a provider outage. |
| 10. Backup/resume state mechanism | **DONE / REVISED** | Explicit dedicated `--state` paths, schema 2.0, continuation skill and atomic state writer exist. The research proposal for one implicit repository-root `.foundry/WORKSTREAM_STATE.yaml` is superseded and must not be reintroduced. |

## Additional research recommendations already present

- Deterministic failure clustering: present.
- Explicit evidence sealing and SHA-256 artifact indexing: present.
- Foundry implementer/adjudicator/reviewer roles: present.
- Canonical HIGH/XHIGH routing: present.
- Explicit Work necessity gate: present.
- Compaction/resumability policy: present; repository state is the durable authority rather than model memory.
- Interrupt-safe long-running launcher behavior: integrated by WS190.
- Explicit Zen execution override: integrated by WS190; it is invocation-scoped and never an automatic fallback.

## Recommendations intentionally not copied verbatim

### Fixed provider quota claims

The research report's provider-rate-limit numbers are not durable project authority. Quotas and provider behavior are external/volatile. Operational policy therefore records observed failure/availability and uses explicit provider selection rather than baking a guessed numerical quota into correctness logic.

### Implicit root state

The research suggested `.foundry/WORKSTREAM_STATE.yaml` as a generic active-state file. Current authority deliberately rejects this model. Every material workstream must use its explicit dedicated `--state` path; historical state files remain evidence, not an implicit active root.

### “Start on HIGH, escalate later” as a universal rule

Current policy is more precise: HIGH is the normal bounded execution tier; XHIGH is selected when nonlocal causality, cross-subsystem reasoning or architecture-adjacent implementation warrants it. A task does not need to waste a valid HIGH run merely to satisfy a ritual escalation sequence, and difficult tasks may start XHIGH when the source facts already justify it.

### Broad autonomous subagent parallelism

Parallelism is allowed only after branch/worktree/ownership/semantic-surface independence is proven. The project does not adopt “spawn several children” as a default because safe parallelism is a Source-Truth and ownership question, not a throughput preference.

## Current remaining Foundry-specific work

1. **HIGH/XHIGH empirical benchmark remains NOT_RUN.** Run it only when the execution provider is available and the selected replay tasks have immutable source locks. It is useful optimization evidence, not a project-correctness blocker.
2. **Metrics presentation can improve later.** Current collection is sufficient for evidence; a dashboard is convenience work and ranks below candidate qualification / Rules correctness.
3. **Provider availability observations should be recorded from real sessions.** Do not turn temporary outage anecdotes or historical quota claims into canonical constants.

These are lower priority than the current Rules/provider integration blocker below.

## Current project blocker discovered during reconciliation

The repository's current Forge materialization source and WS90's required future Rules-Core source are on divergent lines:

- canonical current Forge Rules-Core: `a37a865a53280dd8ad6fad3384d69611e8c5a42f`;
- current H4F bridge source: `4753bb7c72ea60d653121e0bab989077b4009f9c`, a descendant of `a37a865a...`;
- WS90 future Forge Rules-Core authority: `aa5c00aa32dfd40e213f223f8fd400c43daabb24`;
- direct comparison: `4753bb7c...` and `aa5c00aa...` diverge at merge base `a37a865a...`.

Therefore the highest-value next engineering step is not another Foundry-tooling feature. It is the bounded integration defined by `handoffs/ws191/WS191_FORGE_SUCCESSOR_BRIDGE_INTEGRATION.md`: port the qualified H4F bridge onto the `aa5c00aa...` Rules-Core lineage, revalidate it, then return an exact integrated successor for Coordinator adjudication before any repin or WS90 First-Wave run.

## Non-claims

```ini
HIGH_XHIGH_BENCHMARK=NOT_RUN
FORGE_INTEGRATED_SUCCESSOR=NOT_RUN
BEHAVIOR_CREDIT_CHANGE=0
ARCHITECTURE_FREEZE=NOT_CLAIMED
PRODUCTION_PROVIDER=NOT_SELECTED
```
