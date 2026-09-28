# Capsule error privacy — local integration candidate

## Source lock / bounded contract

Repository: moeendres-png/commander-playtest-lab.
Audit HEAD: aebcfda37d61eb435dde6cd11792ef80019dcd10.
Audit TREE: bf003afc0c0b71535094b6b96e3b1184d6dd0f1f.
Branch: astra/capsule-error-privacy-20260916.
Workspace: scratch/capsule-error-privacy (new isolated clone).

Objective: rejected compact capsules must not echo raw state/parser/Git error payloads.
Inputs: current context_capsule.py, canonical state validator, WS78 tests and /work use.
Authority: explicit autonomous local engineering request. No publication authority.
Ownership: context_capsule.py, new test_capsule_error_privacy.py and this document only.
Protected: #204/WS241 publisher security, #196/#205 runtime/publication, engine work,
and four earlier Astra intake packages identified in the latest Issue #200 checkpoint.
Out of scope: state schema, ancestry policy, successful capsule fields, writer locks,
publisher, engine pins, qualification status and previous candidates.
Dependencies: existing Git/Python/PyYAML; no new dependency or provider call.
Deliverables: local commit, regression tests, checked patch and ZIP with evidence/hash manifest.
Hard gates: unchanged success behavior and rejection gates, safe diagnostics, tests green.
Stop conditions: ownership conflict or required authority-policy change.
WORK_NECESSITY: PASS for the explicitly requested independent bounded engineering lane.

## Chosen problem / changes

The helper forwarded the first state-validator error and Git stderr into a /work-facing
rejection. Both may contain values that should remain in local detailed diagnostics.
Initial synthetic regressions directly reproduced these two leaks (2 failed, 1 passed).
The YAML syntax test was already private for its particular fixture; no raw YAML-value
leak is claimed from that passing case. OS/YAML exception strings also carried private
state paths; these are now omitted consistently.

The small production change:

- replaces raw exception/validator text with actionable fixed diagnostics;
- handles UTF-8, YAML recursion and validator type errors as CAPSULE_REJECT;
- handles Git fact-query launch/decoding/timeout failures without a traceback;
- bounds each direct Git fact query to 15 seconds;
- reports a branch mismatch without echoing supplied branch contents.

Existing exit 2/no-capsule behavior remains. Inspect the explicit state locally with
`state.py --state PATH` for full detail; do not automatically copy that output into
the capsule. Successful text/JSON/full-state rendering is unchanged. This is not a
redactor for successful authorized state content or a change to source authority.

The 15-second bound applies to context_capsule._git fact queries, NOT a global deadline
for YAML parsing, schema validation, or the unchanged state._is_ancestor helper.
No total runtime bound or hardened shared state validator is claimed.

## Tests / evidence

Environment: WSL Ubuntu, Python 3.14.4, Git 2.53.0, Ruff 0.16.6.

```sh
python3 -m pytest -q -o addopts= tests/foundry/test_capsule_error_privacy.py tests/unit/test_ws78_token_economy.py
# 34 passed
python3 -m pytest -q -o addopts= tests/foundry
# 384 passed, 1 skipped
ruff check tools/foundry/context_capsule.py tests/foundry/test_capsule_error_privacy.py
# PASS
ruff format --check tools/foundry/context_capsule.py tests/foundry/test_capsule_error_privacy.py
# PASS
python3 ../capsule-privacy-cli-probe.py tools/foundry/context_capsule.py
# Three actual CLI negative paths: exit 2, no stdout, no sentinel/traceback
git diff --check
# PASS
```

12 new test cases plus existing WS78 success, determinism, JSON, full-state, environment
privacy and source/validation-ancestry rejection controls. Adversarial cases include
schema values, private paths, Git stderr, malformed UTF-8, nested YAML, unhashable status,
OS/timeout/decoding faults and branch mismatch. Skipped evidence is not PASS.
DIRECTLY_VERIFIED: executed outcomes; SYNTHETIC: inputs/fault injection;
CODE_DERIVED: unchanged schema/Rules behavior. Native Windows execution remains UNKNOWN.

## Integration / handoff

Exactly three changed files:
tools/foundry/context_capsule.py;
tests/foundry/test_capsule_error_privacy.py;
docs/foundry-execution/CAPSULE_ERROR_PRIVACY.md.

ZIP includes committed files, patch, source-lock seal, hash manifest, before/final logs
and CLI probe. Verify hashes and applicability against fresh main; apply in an isolated
normal OpenCode integration lane with current ownership checks, run the commands above,
then obtain separate publication authorization. Publisher #204 gates still apply.
Prior candidates remain separate and are not superseded. No engine requalification is
unblocked or required by this change. No local implementation blocker remains.

CANONICAL_REPOS_MODIFIED = NO
LOCAL_SOURCE_MODIFIED = YES
LOCAL_COMMITS_CREATED = YES (exact HEAD/TREE in external seal)
REMOTE_WRITES = NO
RULES_AUTHORITY_CHANGED = NO
ENGINE_PIN_CHANGED = NO
BEHAVIOR_CREDIT_CHANGED = NO
ARCHITECTURE_FREEZE = NOT_CLAIMED
PRODUCTION_PROVIDER = NOT_SELECTED
READY_FOR_COORDINATOR_INTEGRATION = YES
