# WSR23 — Foundry bootstrap ownership-identity repair

Date: 2026-09-27
Workstream: `wsr23-project-integration-hygiene-20260927`
Branch: `wsr23/project-integration-hygiene-20260927`
Repair commit: `372851c145fc35f5b2dc887a21fdd872ef1184d5`

## 1. The reported symptom

A launcher attempt returned `LAUNCH_REFUSED / BOOTSTRAP_FAIL` with the state
ownership field reported as descriptive prose, while the launcher expected the exact
workstream identity `wsr23-project-integration-hygiene-20260927`. The same attempt reported
`DRIFT_CLEAN` for canonical policy surfaces and a clean worktree.

The instruction was explicit: do not blindly edit the state to make a gate green, and do not
weaken writer ownership. So the actual layer was established before any edit.

## 2. Reproduction (fail-before)

Run with the workstream identity the launcher actually uses, against the unmodified state:

```text
$ python3 tools/foundry/bootstrap.py \
    --worktree /home/moeen/code/wsr23-project-integration-hygiene \
    --workstream wsr23-project-integration-hygiene-20260927 \
    --branch wsr23/project-integration-hygiene-20260927 \
    --audit-base-sha bbbb6b9c3e9297265c2a488c9ae72a72c0ff3719 \
    --state docs/project_integration_hygiene_20260927/WORKSTREAM_STATE.yaml \
    --profile cpl --canonical-root /home/moeen/code/commander-playtest-lab \
    --allow-same-cwd-pids

BOOTSTRAP_FAIL: state ownership 'WSR23 is the sole writer of branch ...' != workstream
'wsr23-project-integration-hygiene-20260927' (explicit state conflict: refusing to run
under another workstream's state)
BOOTSTRAP_FAIL
BOOTSTRAP_NOTE: same-CWD opencode explicitly allowed: [290551]
```

The first failing boundary is `tools/foundry/bootstrap.py:165-173`, gate 3 of 6. The
launcher's `LAUNCH_REFUSED` is this failure surfaced, not a separate defect.

## 3. Which side is wrong: the state, or the launcher

The gate was **correct**. Four independent lines of evidence, all from the project's own
source at the audit base:

1. **The tool's own state generator writes the token, not prose.**
   `bootstrap.py:47-74`, `init_state()`, sets `"ownership": workstream` — the bare identity
   string. The generator and the gate already agree; only this one hand-written state
   disagreed.

2. **The field is consumed as a machine identity, twice.**
   `safe_push.py:590-593` refuses an empty or `UNKNOWN` ownership and then records it as
   `ctx["task_id"]` — the push task identity in telemetry. Prose is not a task id.

3. **The field is compared for exclusive-ownership conflicts.**
   `worktree_inventory.py` reports per-worktree ownership from the explicit state map so
   that duplicate writers are visible. A string comparison only protects exclusivity if both
   sides are tokens. Prose on both sides would defeat the check; prose on one side makes the
   refusal unexplainable.

4. **The in-repo historical convention is the token.**
   Six committed schema-2.0 states were inspected. Five hold a bare token
   (`WS190`, `WS75-FOUNDRY-OPENCODE-TOOLING-HARDENING`, `WS61-FOUNDRY-SAFE-PUSH-LINEAGE-INTEGRATION`,
   `WS88-XMAGE-INTEGRATED-SUCCESSOR-PROMOTION`, `WS79-RQC3-H01-AUTHORITY-REMEDIATION`,
   `WS80-XMAGE-CALLBACK-REACHABILITY`). The single prose outlier,
   `research/foundry/ws58-state-persistence-hardening/WORKSTREAM_STATE.yaml`
   (`WS58 session (branch ws58/foundry-state-persistence-hardening-20260911)`), is a
   historical instance of this same defect, not a competing convention.

Conclusion: the state was malformed. A minimal, provenance-preserving metadata repair is
legitimate. Loosening the gate to accept prose would have been the actual defect, and would
have weakened the single-writer guarantee.

## 4. Repair 1 — state metadata (minimal, provenance-preserving)

`docs/project_integration_hygiene_20260927/WORKSTREAM_STATE.yaml`

- `ownership` now holds the exact token `wsr23-project-integration-hygiene-20260927`.
- The original sentence is preserved **verbatim** as the first entry of `technical_decisions`,
  with the reason it moved. Its substance is unchanged and still independently recorded in
  `WORKSTREAM_CONTRACT.md` (§ "One workstream ↔ one branch ↔ one worktree ↔ one mutation
  surface"), in `in_scope`, and in `files_modified`. No information was destroyed.
- No schema change. `.foundry/WORKSTREAM_STATE.schema.json` declares `ownership` as a plain
  string; the gate, not the schema, is the identity authority, and the schema was left alone
  so the repair cannot be read as widening the contract.

## 5. Repair 2 — the systemic tooling defect found while diagnosing it

`tools/foundry/worktree_inventory.py`, `_ownership_from_file`, was a genuine second defect
found at the same layer, and it is the reason the prose was not caught earlier by reporting.

The old reader line-scanned for a bare `ownership:` YAML key. A schema-2.0 state file is
routinely JSON — `state.py` and `bootstrap.py` both read it through `yaml.safe_load`, which
accepts JSON — and WSR23's own state is JSON. The line scan therefore returned `UNKNOWN` for
every JSON state, even though the two authoritative readers read the very same field
correctly from the very same file.

`UNKNOWN` is not cosmetic. Downstream it means "reported as unowned", which is a real
evidence loss in exactly the inventory that exists to prove there is no second writer.

Repair: use the same structured reader as the rest of the stack, and fail closed on any
non-mapping document, unparseable text, or non-string value. The module stays a dependency
leaf (no import of `state.py`), and the divergent second implementation is removed rather
than kept alongside a new one.

This path is disjoint from WSR22: `git diff --name-only origin/main...origin/wsr22/...`
contains no `tools/foundry/**` or `tests/foundry/**` entry, so the WSR22 successor
integration cannot conflict with it.

## 6. Tests

`tests/foundry/test_foundry_tools.py` (+6) and `tests/foundry/test_launcher.py` (+2):

| Test | Pins |
|---|---|
| `test_inventory_reports_ownership_from_json_state` | the JSON regression itself |
| `test_inventory_json_and_yaml_states_agree_on_ownership` | serialization must not change the reading |
| `test_inventory_reports_prose_ownership_verbatim` | the reporter reports; it does not judge or truncate |
| `test_inventory_unreadable_or_malformed_state_is_unknown` | list, scalar, empty, absent, null, blank, nested-object and truncated-JSON documents all fail closed |
| `test_inventory_reads_minimal_mapping_field` | field-level read; whole-document validity stays `state.py`'s job |
| `test_bootstrap_rejects_prose_state_ownership` | prose is refused **even when it names the correct workstream** — the gate compares, it never parses prose to guess the owner |
| `test_bootstrap_accepts_matching_token_in_json_state` | a JSON state is first-class, not degraded |

`tests/foundry`: **437 → 447 passed, 1 skipped**.

## 7. Verification (fix-after)

```text
bootstrap gate 3:  BOOTSTRAP_FAIL (prose)  ->  BOOTSTRAP_PASS
state.py --check-validated --fail-on-validated-problem:  STATE_OK, exit 0
tests/foundry:     447 passed, 1 skipped
full suite (clean tree, lock-faithful Python 3.12.14 venv): 1638 passed, 5 skipped, 0 failed
ruff check: All checks passed
ruff format --check: 961 files already formatted
mypy src/commander_lab (strict): Success, no issues in 261 source files
python -m compileall -q src tests: exit 0
```

The validation environment is a lock-faithful venv built outside the worktree
(`/tmp/opencode/cpl-venv`, CPython 3.12.14, `pip install --require-hashes -r requirements/lock.txt`
then `pip install --no-deps --no-build-isolation -e .`), matching the CI quality job. The
ambient system interpreter cannot run the suite at all: it is missing `typer`, `httpx2` and
`pytest-asyncio`, which is a pre-existing environment boundary and not a repository defect
(recorded in `hypotheses_rejected`).

**A diagnostic worth recording.** An intermediate full-suite run showed 52 failures with the
message `stale canonical inputs rejected: tracked software worktree differs from recorded git
tree`. That was not a regression: the suite contains an intentional source-lock staleness
guard, and the four repair files were still uncommitted. Committing the repair and re-running
on a clean tree produced 0 failures. Recorded so a later session does not misread the same
signature as a production defect.

## 8. What this repair does NOT do

It does not grant, simulate, or work around Foundry writer ownership.

`tools/foundry/safe_push.py` gate 6 still rejects, correctly, with `PUSH_REJECT: no writer lock
(run inside the validated launcher)`. Gates 1-5 and 7-9 all pass now, so gate 6 is genuinely
the only remaining publication gate on the tool side.

The launcher-held lock precondition was **verified, not assumed**. This session carries no
`FOUNDRY_*` launcher context whatsoever, and the run directory
`/tmp/foundry-launch-wsr23-project-integration-hygiene-20260927` is empty — no launcher ever
acquired or held a lock for this worktree. Acquiring
`writer_lock.WriterLock(...).acquire()` from this process would make this process the recorded
holder and would satisfy the gate. That is the bypass the gate exists to prevent: it would let
any process self-authorize as the exclusive writer of any worktree. It was not done, and it is
now recorded in `out_of_scope` so a later session does not mistake it for unexplored work.

`ARCHITECTURE_FREEZE = NOT CLAIMED`. `PRODUCTION_PROVIDER = NOT SELECTED`.
