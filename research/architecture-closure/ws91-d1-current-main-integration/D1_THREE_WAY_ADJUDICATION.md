# WS91 — D1 Three-Way Adjudication (XHIGH, read-first, pre-edit)

Adjudicator: `foundry-adjudicator` at XHIGH, read-only, session `ses_f6548b44affehmFl3jKr42FCHU`.
Range adjudicated: D1 `f89c824e..8d0f6849` (26 paths) against current main `4f69aa36`.
Current-main delta `f89c824e..4f69aa36` confirms WS78/WS88/WS90 additions.
`READ_FIRST_XHIGH_ADJUDICATION = PASS`. No edits were made by the adjudicator.

## Per-path classification

| Path | Class |
|---|---|
| `.foundry/repo-profiles/mage.json` | DURABLE_D1_TO_INTEGRATE |
| `.opencode/agents/foundry-adjudicator.md` | DURABLE_D1_TO_INTEGRATE |
| `.opencode/agents/foundry-implementer.md` | SEMANTIC_MERGE_REQUIRED (D1 explicit-state wording + HEAD WS78 saved-output paragraph; disjoint ranges, union) |
| `.opencode/agents/foundry-reviewer.md` | DURABLE_D1_TO_INTEGRATE |
| `.opencode/skills/continuation/SKILL.md` | DURABLE_D1_TO_INTEGRATE |
| `.opencode/skills/failure-classification/SKILL.md` | DURABLE_D1_TO_INTEGRATE |
| `.opencode/skills/rules-authority-escalation/SKILL.md` | DURABLE_D1_TO_INTEGRATE |
| `.opencode/skills/workstream-bootstrap/SKILL.md` | DURABLE_D1_TO_INTEGRATE |
| `AGENTS.md` | DURABLE_D1_TO_INTEGRATE |
| `config/rules_engines.json` | SUPERSEDED_BY_CURRENT_MAIN — discard wholesale (D1 pins `77d7646` stale; HEAD `cfc36f` authoritative) |
| `docs/FORK_AGENT_POINTER_SPEC.md` | DURABLE_D1_TO_INTEGRATE (append §5, §§1–4 verbatim) |
| `docs/RETENTION_AND_LIFECYCLE_POLICY.md` | SEMANTIC_MERGE_REQUIRED (D1 hunks 1–2 verbatim; hunk 3 merged with WS88 resolution — keep both dated notes) |
| `docs/foundry-execution/COMPACTION_AND_RESUMABILITY.md` | DURABLE_D1_TO_INTEGRATE |
| `docs/foundry-execution/GITHUB_REMOTE_GATES.md` | DURABLE_D1_TO_INTEGRATE |
| `docs/foundry-execution/README.md` | DURABLE_D1_TO_INTEGRATE |
| `docs/foundry-execution/ROUTING_AND_EFFORT.md` | DURABLE_D1_TO_INTEGRATE |
| `.foundry/WORKSTREAM_STATE.yaml` → `research/.../HISTORICAL-...yaml` | DURABLE_D1_TO_INTEGRATE (R100 byte-identical archive + root removal, after tooling lands) |
| `research/.../WORKSTREAM_CONTRACT.md` (D1) | HISTORICAL_ONLY (D1 provenance; WS91 writes its own package) |
| `research/.../WORKSTREAM_STATE.yaml` (D1) | HISTORICAL_ONLY (D1 operational state; not live doctrine) |
| `tests/foundry/test_foundry_tools.py` | DURABLE_D1_TO_INTEGRATE |
| `tests/foundry/test_launcher.py` | DURABLE_D1_TO_INTEGRATE |
| `tests/foundry/test_ws75_tooling_hardening.py` | DURABLE_D1_TO_INTEGRATE |
| `tests/unit/test_ws_arclose_d1_authority_drift.py` | SEMANTIC_MERGE_REQUIRED (stale-pin/wording portion SUPERSEDED; rebase to `cfc36f` + WS88 wording + WS91 archive path) |
| `tools/foundry/bootstrap.py` | DURABLE_D1_TO_INTEGRATE (HEAD == f89 base; D1 version is terminal) |
| `tools/foundry/launcher.py` | SEMANTIC_MERGE_REQUIRED (D1 explicit-state hunks + HEAD WS78 `tool_output` block; disjoint, union) |
| `tools/foundry/worktree_inventory.py` | DURABLE_D1_TO_INTEGRATE (HEAD == f89 base; D1 version is terminal) |

`D1_PATH_CLASSIFICATION = PASS`. `WHOLESALE_D1_MERGE = NO`.

## 18 adjudicated answers (summary)

1. Already present: zero D1 hunks present equivalently on HEAD (20/26 blobs equal
   f89; 3 merged paths carry only the other side; config carries neither).
2. Missing: all durable hunks + merged-path D1 sides + rewritten regression test.
3. Stale via WS88/WS90: `config/rules_engines.json` wholesale; D1 test pin/wording
   assertions (`77d7646`, pre-WS88 `known_stale_pointers` strings, verbatim H4
   retention without WS88). WS79/WS90 untouched by D1, stay authoritative.
4. WS78 overlap: exactly `tools/foundry/launcher.py` and
   `.opencode/agents/foundry-implementer.md`.
5. Combined result for overlaps: union, no textual conflict (launcher: keep WS78
   `_validated_tool_output` + propagation, add D1 explicit-state/`worktree_states`;
   implementer: keep WS78 saved-output paragraph, apply all 5 D1 wordings).
6. `context_capsule.py`: unaffected (WS78-only, absent from D1 range). Stays
   byte-intact; its CWD default degrades to `CAPSULE_REJECT` when root is absent.
7. Root removal: SAFE after D1 tooling+docs land (no production path then
   succeeds via root).
8. Live callers on HEAD still requiring implicit root: yes pre-integration
   (`bootstrap.py:43,120,260`, `launcher.py:293-294,388`,
   `worktree_inventory.py:32-33,105`, 13 doc/skill/agent references, capsule CWD
   default) — hence removal lands with the integration, not before it.
9. Conventional-path fallback post-integration: none.
10. CLI inventory explicit pairs: yes on D1 (`--worktree-state WORKTREE=STATE`,
    repeatable, shared parse delegate).
11. Malformed/conflicting maps: fail closed (launcher `LAUNCH_REFUSED`, bootstrap
    `BOOTSTRAP_FAIL`, inventory `INVENTORY_FAIL` exit 1).
12. No-map ownership: `UNKNOWN`.
13. Current docs/skills naming root state: yes on HEAD (13 sites listed) — all
    replaced by D1 wording; locked by `test_no_current_doc_names_root_state_canonical`.
14. Mirror rules: safe (sync-only fast-forward, no project files on mirror master,
    drift gate fail-closed; Dockerfiles pin-free by design).
15. `config/rules_engines.json` stays byte-identical: yes (`6471495e`).
16. WS78 stays byte/semantically intact: yes (5 files byte-identical; 2 overlaps unioned).
17. Rules/provider/qualification change required: none.
18. Genuine Authority Gate: none.

Root cause: `HARNESS_DEFECT` (implicit-root semantics superseded by explicit-state
authority). First-failing boundary: `bootstrap.py:43,120` + `launcher.py:293-294,388`
+ `worktree_inventory.py:32-33`. Contract verdict on HEAD: `FAIL`. No `AUTHORITY_GATE`.
