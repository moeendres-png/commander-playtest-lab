# WS58 Final Report — Foundry State Persistence Hardening

Verdict: **FOUNDRY_STATE_PERSISTENCE_HARDENING_PASS**

## Objective (met)

A minimal canonical state-write/update path now exists so Foundry workstreams
persist state without hand-authoring YAML serialization. Malformed YAML is
structurally impossible through the normal API (parsed mappings only, single
`yaml.safe_dump` choke point); schema-invalid state is refused BEFORE it
replaces the on-disk file; failures leave the prior file byte-identical. No
general configuration framework was created; validation was not weakened (one
error path hardened: unparseable YAML in validate flow now exits `STATE_INVALID`
instead of a traceback).

## What changed

- `tools/foundry/state.py` (+writer API, all additive except the hardened
  migrate write and the parse-error branch above):
  `StateWriteError`, `IMMUTABLE_IDENTITY_FIELDS`,
  `dump_state`, `atomic_write_text` (same-dir temp + flush/fsync +
  `os.replace` + best-effort dir fsync, temp cleanup, mode preservation),
  `write_state` (validate → identity → ancestry → atomic → readback
  re-validate), `update_state` (mutable patch only; `validated_head` rejects
  in-patch smuggling and changes only via the explicit parameter; never
  auto-promoted; no enum coercion anywhere), CLI `--write-from` /
  `--patch-file` / `--set-validated-head` / `--clear-validated-head` /
  `--stamp-head` / `--allow-identity-change`, migrate `--in-place` now
  validate-before-replace + atomic (1.0→2.0 semantics preserved, still
  `validated_head: null`).
- `tools/foundry/bootstrap.py`: `--init-state` writes via
  `state_mod.write_state` (validated + atomic); constructor unchanged.
- `tools/foundry/safe_push.py`: UNCHANGED — still validates independently,
  never trusts writer provenance.
- `docs/foundry-execution/README.md`: concise "Workstream state writes
  (canonical)" section (no hand-concatenation; canonical path; validate after
  checkpoint; `validated_head` = actual evidence).
- `tests/foundry/test_state_writer.py`: 36 tests — reproductions A–G
  end-to-end, 10 positives, 11 negatives, every negative proving
  byte-identical preservation.

## PASS-criteria audit

| Criterion | Evidence |
|---|---|
| Writer cannot emit malformed YAML | Round-trip tests (colons, multiline, Unicode, `#`/quotes/brackets) + write readback re-validate; `DIRECTLY_VERIFIED` |
| Schema-invalid rejected before replace | 11 adversarial negatives incl. `ARGENTUM_ENGINE_DEFECT` (never coerced); `DIRECTLY_VERIFIED` |
| Original bytes preserved on failure | Every negative asserts `read_bytes() == before`; serializer/replace-failure controls incl. temp cleanup; `DIRECTLY_VERIFIED` |
| Source-lock identity protected | All 5 fields guarded in patch + full-doc paths; explicit `--allow-identity-change` rebind only; `DIRECTLY_VERIFIED` |
| `validated_head` never fabricated | Patch smuggling rejected; omission preserves; explicit value ancestry-checked with `workdir`; `DIRECTLY_VERIFIED` |
| Valid explicit credit ancestry-checked | Inside-lock ok / outside-lock + rewritten rejected on real git histories; `DIRECTLY_VERIFIED` |
| Atomic-write negative control | Simulated replace failure: prior bytes intact, no temp residue; `DIRECTLY_VERIFIED` |
| Impacted suites green | `test_state_v2` 11 + `test_foundry_tools` 45 + `test_state_writer` 36 + full `tests/foundry/` 152 passed / 1 pre-existing skip; ruff check+format clean |
| UNKNOWN 0 in changed scope | No UNKNOWN claims; incident classifications marked `CODE_DERIVED`; sandbox-guard anomaly documented, not hidden |

## Environment anomaly (documented, not hidden)

The sandbox injects `remote.origin.pushurl=file:///dev/null/ws58-foundry-push-disabled`
into every process env, so `test_safe_push.py`/`test_telemetry.py` fixtures that
push to ephemeral local file-remote bare repos fail setup unscrubbed (15 errors +
1 failure, all "does not appear to be a git repository"). With ONLY those
`GIT_CONFIG_*` guard variables scrubbed for the pytest subprocess (local fixtures
only; no remote touched): 26 passed / 1 pre-existing skip, and full
`tests/foundry/`: 152 passed / 1 skip. Pre-existing and unrelated to this change
(failing layer is `git push` in fixture setup, untouched by this workstream).

## New finding (minor, out of scope)

`tools/foundry/test_impact.py --base <sha>` crashes (`FileNotFoundError:
'rev-parse'` — argv missing the `git` prefix at call site). Pre-existing (file
untouched by WS58); impact mapping was done manually from the call-site
inventory instead. Left for a future tooling workstream; not repaired here per
"do not rewrite unrelated tools".

## Non-goals honored

No engine/qualification/behavior/ranking/provider changes; no old-workstream
repair (branch-root WS-A1D state untouched); no push/merge/rebase; no bulk
normalization; migration fabricates no credit.

## Outputs

`research/foundry/ws58-state-persistence-hardening/`: `WS58_SOURCE_LOCK.md`,
`WS58_CALLSITE_INVENTORY.json`, `WS58_DESIGN.md`, `WS58_NEGATIVE_CONTROLS.json`
(pre-fix baseline), `WS58_TEST_MATRIX.json`, `WS58_INCIDENT_MATRIX.json`,
`WS58_FINAL_REPORT.md` (this file), `WORKSTREAM_STATE.yaml`
(`validated_head: null` — honest; WS58 claims no validation credit for itself
beyond its own test evidence, and no push is requested).

ARCHITECTURE_FREEZE = NOT CLAIMED
PRODUCTION_PROVIDER = NOT SELECTED
RULES_BEHAVIOR_CREDIT_CHANGE = 0
