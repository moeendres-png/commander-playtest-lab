# Test-impact inventory contract

Run from a quiescent checkout root (or supply it explicitly):

```sh
python tools/foundry/test_impact.py --workdir /path/to/checkout --base <commit>
```

The existing advisory mapping and contract-required test override are unchanged.
This tool does not authorize qualification, publication, or skipping tests.

## Collection

- Resolve the base to a commit before diffing; `resolved_base` records that identity.
  The existing `base` field retains the requested input. `head` must be known.
- Inventory committed changes since the base, staged changes, unstaged changes,
  and individual non-ignored untracked files. Ignored files are intentionally excluded.
- Include both removed and added paths for renames, including cross-surface moves.
- Consume NUL-delimited Git paths without whitespace splitting or quote removal.
  JSON escapes preserve tabs, newlines and non-UTF-8 pathname bytes (surrogate escapes).
- Disable external diff/textconv and rename heuristics for collection; explicitly
  include dirty submodules as their parent-repository paths. The mapper does not
  recursively qualify a submodule's contents.
- Refuse subdirectory workdirs and incomplete nested-repository directory entries.
- Bound each Git command to 15 seconds. Failed commands, malformed framing,
  invalid commit identities and detected HEAD movement produce exit 1 and
  `TEST_IMPACT_ERROR` on stderr, with no newly generated plan. Raw Git stderr is not
  forwarded. Success is exit 0 with JSON, not a qualification PASS.

If `--output` already exists when collection fails, it is left untouched. Consumers
must check the current invocation's exit status; an older report is not fresh evidence.

## Limits and recovery

Stop concurrent writers before collecting. The final HEAD check detects committed
movement, but this is not an atomic filesystem snapshot or a lock: concurrent edits
with unchanged HEAD can race collection. This tool does not replace Foundry's writer
ownership, source-lock, or artifact integrity mechanisms. It trusts the selected local
Git executable and repository environment; it does not authenticate remote identity.

On failure, inspect the indicated Git operation locally, confirm the checkout root
and base commit, stop competing writes, then rerun. Resolve nested repositories as
separate explicit workstreams. Never substitute an empty plan for a collection error.

Validation: `pytest -q tests/foundry/test_test_impact_inventory.py
tests/foundry/test_telemetry.py`, followed by the Foundry regression suite. Tests use
synthetic Git repositories; they confer no engine behavior credit.
