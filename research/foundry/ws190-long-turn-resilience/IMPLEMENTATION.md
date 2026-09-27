# WS190 implementation

## Read-first findings and decision

The launcher read `rc` in finally after an interrupted subprocess.run; the red
regression reproduced UnboundLocalError. A top-level model substitution alone
would leave Go provider policies and agent Markdown model/variant settings active.
The canonical config file is not changed. Launcher-owned `--execution-provider zen`
derives a bounded injection bundle and records one explicit execution identity.

No new provider framework/helper or state schema is needed. `metrics.py` changes
only its allowed fields (execution_provider, execution_override,
variant_resolution, interrupted), because it rejects unknown metric keys.
Bootstrap, context capsule, CLI pin, opencode.json and agent/command files are unchanged.

The provider bundle preserves permissions, snapshot content, instructions and output
bounds. It includes provider-use policy substitution and per-agent model selection;
inline config wins after Markdown loading. Empty variant clears inherited Go
selection, rather than inventing equivalent Zen HIGH/XHIGH mechanics. Named variants
are disabled and no Zen reasoningEffort option is fabricated. Requested policy tier
and unverified provider-default resolution are separately recorded.

The lock owner uses an outer finally around child execution and all telemetry.
The child result is initialized; interrupt is explicit 130; ordinary status is
preserved; spawn failure is 127; unexpected errors propagate without masking them.
End telemetry records the selected execution rather than always claiming Go.

## Directly relevant external technical sources (2026-09-13)

- https://opencode.ai/docs/zen/: exact `opencode/muse-spark-1.3-contributor-free` ID.
- https://opencode.ai/docs/config/: provider allowlist/denylist and content injection.
- https://opencode.ai/docs/models/: CLI model precedence; disabled variant semantics.
- `sst/opencode` tag `v1.18.30`, `packages/opencode/src/config/config.ts`:
  CONFIG_CONTENT merges after agent loading; OPENCODE_PERMISSION applies later.
- Same tag, `packages/opencode/src/agent/agent.ts`: `value.variant ?? item.variant`
  permits empty-string clearing; no fabricated native capability claim.

The pinned CLI was also found at its standard local executable path. Config
inspection used a separate network namespace (`unshare -Urn`), empty isolated
HOME/XDG directories, no inherited credential environment, and disabled model
fetch/update. Both default and Zen effective configs passed, including canonical
role permissions and `/work`. No authenticated model request occurred.

See VALIDATION.json for exact committed-head validation and FINAL_REPORT.md for
scope disposition. Tooling PASS does not establish Zen runtime authentication or
provider-native HIGH/XHIGH equivalence.
