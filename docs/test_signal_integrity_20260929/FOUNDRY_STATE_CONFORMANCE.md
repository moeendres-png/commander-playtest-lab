# `.foundry/` State-File Conformance

Read-only audit, with **two defects fixed** and the rest classified.

Measured at `origin/main` = `7055740ec2f08d4864bf7e200f7b48ace521fe57`, then at this branch head.

---

## 1. Headline: the schema is not enforced

> `.foundry/WORKSTREAM_STATE.schema.json` is an **unexecuted document.** Zero production-reachable
> code paths read it.

The only live validator is `tools/foundry/state.py`, which its own docstring describes as
*"Mirrors `.foundry/WORKSTREAM_STATE.schema.json` (2.0)"*. A hand-mirrored reimplementation can
drift silently from the JSON Schema — and has.

| Tool | Reads the schema? | What it actually does |
|---|---|---|
| `tools/foundry/state.py` | **no** (`rg 'schema.json\|jsonschema'` → 0 hits) | hand-mirrored `REQUIRED_V1/V2`, `LIST_FIELDS`, vocabularies |
| `tools/foundry/launcher.py` | no (`rg 'state.validate'` → 0 hits) | only enforces that state lives under `ROOT/.foundry` |
| `tools/foundry/drift_check.py` | no | reads only `.foundry/repo-profiles/` |
| `tools/foundry/context_capsule.py` | no (delegates to `state.py`) | default path is `.foundry/WORKSTREAM_STATE.yaml` — a filename convention **no tracked file uses** |

### 1.1 Enforced in the schema, not in code — the false guarantees

| Check | Schema | `state.py` |
|---|---|---|
| Extra/unknown keys (`additionalProperties: false`) | rejected | **accepted** |
| `ownership` must be a string | rejected | **accepted** |
| `tests_run` / `in_scope` / `technical_decisions` element types | rejected | **accepted** |
| `execution_profile` enum | enforced | **not checked** |
| `native_variant` enum | enforced | **not checked** |

So a state file naming `execution_profile: "not-a-profile"` or a retired executor **passes the
real validator** while the published schema would reject it.

### 1.2 Enforced in code, not in the schema

`state.py` supports only `1.0` and `2.0` (`SUPPORTED_VERSIONS`), while the schema accepts any
`^[0-9]+\.[0-9]+$`. So `schema_version: "9.9"` validates against the published schema but is
hard-rejected in code — a future incompatible v3 could validate clean against the committed
schema.

### 1.3 One test pins the divergence in place

`tests/foundry/test_executor_profiles.py:120-131` asserts the schema's `execution_profile` enum
**must contain** `muse`, `glm`, `muse-free-zen` — executors the launcher refuses
(`tests/foundry/test_project_integrity.py:58-60`). **On inspection this is correct and was
deliberately not changed:** the schema must stay able to record *historical* provenance from
runs that used those executors, while the launcher refuses to *select* them. The two tests are
not in conflict. Recorded because it looks like a contradiction on first read.

---

## 2. The one real bug — FIXED

**`.foundry/legacy-donor-salvage-20260929.yaml` could not be parsed by any YAML loader.**

```text
yaml.scanner.ScannerError: mapping values are not allowed here
  in ".foundry/legacy-donor-salvage-20260929.yaml", line 89, column 173
```

Cause: an unquoted block-sequence scalar containing `": "` —

```yaml
- tests/qualification/…: 57 passed, then full tests/qualification/: 410 passed, 5 skipped …
```

YAML read `tests/qualification/` as a mapping key and then hit `: 410`.

**Why this mattered:** the file is the committed continuity record for workstream
`LAB-LEGACY-DONOR-SALVAGE-20260929`, and this project treats `.foundry/` as the continuation
map. The entry was machine-dead: a resuming session could not have loaded it.

**Fix:** one line quoted. Verified content-preserving — the loaded string is byte-identical to
the original raw line, and all 19 top-level keys and 12 `tests_run` entries survive. Both
`.foundry` YAML files now parse.

**Corroboration that this class of problem was already seen and not fixed:** the *last line* of
that same file already recorded the red-test-baseline cause as
`PRE_EXISTING_ENVIRONMENT` — *"missing httpx2/pytest_asyncio packages, bare-subprocess
ModuleNotFoundError without installed distribution"*. A prior session diagnosed that and did not
act. The subprocess half is fixed in this workstream (see `TEST_SIGNAL_INTEGRITY.md`).

---

## 3. Conformance table

13 tracked files (10 top level, 3 under `repo-profiles/`). The prior campaign counted 11 and did
not test validity at all — only counted.

| File | Class | JSON Schema | `state.py` |
|---|---|---|---|
| `claude-mp-campaign-20260929.json` | state 2.0 | **VALID** | PASS |
| `claude-xmage-2p-draw-skip-20260929.json` | state 2.0 | **VALID** | PASS |
| `foundry-deepseek-primary-migration-20260929.json` | state 2.0 | **VALID** | PASS |
| `wsr24-freeze-production-bootstrap-readiness-20260927.json` | pre-schema v0 | INVALID (12) | REJECT |
| `project-hygiene-canonicalization-20260929.yaml` | ad-hoc | INVALID (15) | REJECT |
| `legacy-donor-salvage-20260929.yaml` | ad-hoc | **UNPARSEABLE → now parses** | now parses |
| `conformance-ledger-2026-09-10.json` | not a state file | INVALID (12) | REJECT |
| `executor-profiles.json` | not a state file | INVALID (12) | REJECT |
| `safe-auto-battery-2026-09-10.json` | not a state file | INVALID (12) | REJECT |
| `repo-profiles/{cpl,forge,mage}.json` | not a state file | INVALID (13 each) | REJECT |

**"INVALID" is expected for the six non-state files** — they are ledgers, profiles and batteries
that legitimately have different shapes. The meaningful results are the three conforming
2.0 files and the pre-schema `wsr24` file.

### 3.1 `wsr24` is not merely missing fields

It uses **renamed** fields: `audit_base_commit` where the schema wants `audit_base_sha`, and
`head_at_state_write` where it wants `state_written_against_head` — precisely the ambiguity
schema 2.0 was written to eliminate. With `additionalProperties: false` it also trips 15
unexpected keys. Migrating it is a mechanical but real edit to a 2026-09-27 record.

---

## 4. Test coverage — the gap

**No test asserts that any tracked `.foundry/*.yaml|json` state file validates. No test asserts
the schema and `state.py` agree.** Both do not exist.

The only tests touching the schema use it as a **lookup table for one enum**:
`test_project_integrity.py:20` asserts one `current_reasoning_tier` enum member;
`test_executor_profiles.py:120-131` asserts the `execution_profile`/`native_variant` enums.

`tests/foundry/test_foundry_tools.py:261` is the sharpest summary of the gap:

```python
def test_repo_root_state_absent_schema_kept():
    assert not (REPO_ROOT / ".foundry" / "WORKSTREAM_STATE.yaml").exists()
    assert (REPO_ROOT / ".foundry" / "WORKSTREAM_STATE.schema.json").is_file()
```

It asserts only that the schema **file exists**. That is a presence check, not a conformance
check — and it is exactly the false guarantee this audit is about.

Meanwhile the 12 `test_state_v2.py` tests and 53 `test_state_writer.py` tests exercise
`state.py` thoroughly — but **exclusively against synthetic in-memory dicts and `tmp_path`
files**, never against the 13 real committed files.

---

## 5. Staleness

| State file | Branch named | On remote? | Merged? | Claimed status | Reality |
|---|---|---|---|---|---|
| `claude-mp-campaign-20260929.json` | `claude/mp-campaign-checkpoint-2-20260929` | **no** | base is ancestor | **`ACTIVE`** | **STALE-CONTRADICTORY** |
| `claude-xmage-2p-draw-skip-20260929.json` | `claude/xmage-2p-draw-skip-20260929` | no | base is ancestor | `COMPLETE` | closed; self-declares its successor |
| `foundry-deepseek-primary-migration-20260929.json` | `foundry/deepseek-primary-migration-20260929` | no | base is ancestor | `COMPLETE` | merged as PR #350 |
| `wsr24-…-20260927.json` | `wsr24/…-20260927` | **yes** | not merged | *(no status field)* | **open, oldest artifact, pre-schema** |
| `legacy-donor-salvage-20260929.yaml` | `integration/legacy-donor-salvage-20260929` | no | base is ancestor | *(none)* | unresolved |
| `conformance-ledger-2026-09-10.json` | `project/opencode-muse-cross-repo-hardening-v2-…` | yes | **merged** | checkpoint `G-FINAL` | closed, 19 days stale |

**Highest-signal staleness finding:** `claude-mp-campaign-20260929.json` is the only file whose
recorded `status` is `ACTIVE` while its branch no longer exists. `status` is the first field a
continuation session reads, and it is wrong.

**Deliberately not changed.** Rewriting a recorded `status` is the same category of action as
altering a historical result, and the honest alternative is this record. Changing it would also
make the file look as though it had been written under current truth.

---

## 6. Gitignore

`.foundry/` is **not** gitignored, and that is correct — state is meant to be durable and
versioned. The root `.gitignore` has exactly one `.foundry`-scoped rule: line 29,
`.foundry/metrics.jsonl`. Verified with `git check-ignore -v` both with and without `--no-index`:
**no tracked `.foundry` path is matched by any rule.**

The consequence is a *missing guard*, not a missing ignore: nothing prevents committing a new,
schema-invalid state file, and nothing enforces the `WORKSTREAM_STATE.yaml` naming convention
that `context_capsule.py:30` and `bootstrap.py:13` assume. That protection is convention only.

---

## 7. Recommendations

Ordered by leverage. Originally all were left to the Coordinator on the reasoning that they touch
the durable-state contract. **That reasoning was too broad, and acting on it left real defects in
place.** Two of the five have since been done; the rest are marked with why they genuinely remain
someone else's decision.

**DONE — 1. Validate every tracked `.foundry` state file.** Landed as
`tests/foundry/test_foundry_state_conformance.py` plus the conformance fix to this workstream's own
state file (PRs #375). The "which authority is normative" question did **not** need a Coordinator
ruling: `safe_push.py` already answers it by calling `state.py.validate` and rejecting the push on
any error. The guard therefore mirrors `state.py`, and the JSON schema is deliberately not used.
Note what the original deferral concealed: this workstream's own state file **failed that
validator as merged in #371**, so it could not have pushed through the canonical gate. It never
surfaced because the workstream pushed with plain `git push` and never called the gate. A defect
that only appears on a code path you never take is still a defect.

**PARTLY DONE — 2. Reconcile the schema with `state.py`.** The *decision* is still the
Coordinator's, and this workstream does not make it. What has changed is that the situation is no
longer unmonitored. `tests/foundry/test_state_spec_agreement.py` now asserts, in both directions,
every part of the overlap that must agree — the required field sets, the three shared enum
vocabularies, `root_cause_class`, and the 17 `LIST_FIELDS` — so editing one specification without
mirroring it in the other fails. It also pins the premise (that `safe_push` enforces `state.py`)
and records each of the four known divergences with a rot-proof check. Mutation-tested: six
one-sided schema mutations, six catches.

The four recorded divergences are the complete, verified agenda for the Coordinator:

| Divergence | Consequence |
|---|---|
| `additionalProperties: false` over 43 fields | the three tracked `.json` files fit inside it; every hand-written `.yaml` file needs keys it forbids, so enforcing the schema would delete recorded research |
| `schema_version` pattern vs `SUPPORTED_VERSIONS` | `1.5` passes the schema's pattern and is refused by `state.py` |
| `execution_profile` / `native_variant` enums | schema-constrained, absent from `state.py` entirely |
| no 1.0 model in the schema | `state.py` models 1.0 with `current_head`; no 1.0 file can validate against the schema |

**REMAINS COORDINATOR / OWNER — 3. Migrate `wsr24-…-20260927.json`** to schema 2.0, including the
`audit_base_commit` → `audit_base_sha` and `head_at_state_write` → `state_written_against_head`
renames. WSR24 is a foreign workstream (merged as PR #274); the file is registered as an
exemption with its owner in the guard rather than rewritten here.

**REMAINS OPEN — 4. Correct the `ACTIVE` status** in `claude-mp-campaign-20260929.json`, or add an
explicit `superseded_by` field — as a new recorded fact, not a rewrite. Still `ACTIVE` against a
branch, `claude/mp-campaign-checkpoint-2-20260929`, that no longer exists on the remote; only
`claude/optimistic-bohr-6asye6` remains. Deliberately **not** changed here: stating what superseded
it requires that lane's knowledge, and inventing it would be a worse defect than the stale field.

**PARTLY ADDRESSED — 5. Filename convention.** The guard detects state files by *content*
(`objective` or `workstream`) rather than by filename, which is strictly more robust than
enforcing the `WORKSTREAM_STATE.yaml` name: a state file under any naming convention is still
covered. The convention assumption in `context_capsule.py:30` and `bootstrap.py:13` remains
unenforced.

## 8. Classification

Conformance results are `DIRECTLY_VERIFIED` by executed validator runs (`jsonschema` 4.19.2
`Draft7Validator` and the project's own `state.py`). Staleness is `DIRECTLY_VERIFIED` for
branch existence and ancestry via `git ls-remote --heads origin` and `git merge-base`.

**NOT_ESTABLISHED** (read-only limits at audit time): whether PR #274 (`wsr24`) and the
`project-hygiene` PR were still open, and the merge outcome of PR #344 (`legacy-donor-salvage`).

**Now established.** A later session, with API access, resolved all three: PR #274 and PR #359
(`project-hygiene`) and PR #344 (`legacy-donor-salvage`) are all **MERGED**. That is why the two
closed campaigns from this writer's lineage are recorded as exemptions rather than open work, and
it is the fact that distinguishes them from `pb03`, which is still live. Recorded here because the
audit's own limitation should be closed out rather than left standing as an unknown.
