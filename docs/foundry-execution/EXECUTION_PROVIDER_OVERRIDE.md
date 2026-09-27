# Explicit execution profile and provider overrides

The committed default remains `opencode-go/muse-spark-1.3-contributor`.

## Space Bunny Max profile

For an operator-selected run, add `--execution-profile space-bunny` to the existing
Foundry `init` or `launch` invocation:

```text
python3 tools/foundry/launcher.py launch <existing workstream arguments> --effort high --execution-profile space-bunny
```

This selects `opencode-go/space-bunny-free` and pins every injected agent to native
`max` reasoning. The project-level `--effort high|xhigh` field remains required and
continues to describe task/authority routing; for this profile it does not reduce the
native Space Bunny reasoning level. The selected profile/model/native variant are
recorded in launch context/environment and existing model/provider telemetry.

No automatic model fallback exists. Space Bunny failure, quota/auth failure, or child
exit ends that run. A later Muse run may resume the same branch and explicit workstream
state only after the first writer exits/releases the lock. Parallel Muse + Space Bunny
writers are allowed only on independently owned worktrees/surfaces under the normal
Foundry ownership gates.

The committed `opencode.json` remains Muse-only by default. The Space Bunny model is
narrowed into a run-specific `OPENCODE_CONFIG_CONTENT` bundle, so enabling the profile
does not make both models simultaneously selectable inside a session. Caller
`--model`/`--variant` flags remain refused.

### Qualified CLI compatibility

The qualified Foundry CLI remains OpenCode `1.18.30`; this profile does not require
a CLI repin merely because Space Bunny was added later. Direct source verification of
OpenCode `v1.18.30` shows that its ModelsDev service fetches the live catalog from
`https://models.opencode.ai/api.json` (with a five-minute cache) and that configured
models merge against that catalog. The current authoritative models.dev entry
`providers/opencode-go/models/space-bunny-free.toml` declares
`low|medium|high|xhigh|max` effort levels, a 1,048,576-token context limit, tool use,
and OpenAI-compatible reasoning. The pinned `v1.18.30` transform maps catalog-declared
effort values for `@ai-sdk/openai-compatible` to `reasoningEffort`, so the injected
`max` variant has a verified configuration path.

This is source-level compatibility evidence, not a claim that a particular local account
is authenticated or that the limited-time preview remains available forever. If the
catalog/model/auth path is unavailable, the selected Space Bunny run fails closed; it
must never fall back silently to Muse. Requalification is required if the CLI pin,
catalog contract, provider protocol, or Space Bunny reasoning contract changes.

## Legacy Zen Muse override

For an operator-authorized workstream, add `--execution-provider zen` to its existing
Foundry `init` or `launch` invocation. All existing required arguments,
especially `--state`, source lock and ownership, remain required.

```text
python3 tools/foundry/launcher.py launch <existing workstream arguments> --effort high --execution-provider zen
```

Omit both override/profile options for canonical Muse on Go. Unknown values fail
closed, and `--execution-provider zen` cannot be combined with
`--execution-profile space-bunny`. This flag is the explicit operator choice for this
invocation. Quota, errors and credentials never select it. No committed config
edit is necessary. It is unrelated to Rules providers or Production Provider selection.

The run-specific bundle selects only provider `opencode`, whitelists only
`muse-spark-1.3-contributor-free`, disables Go and substitutes the provider-use
policy. Main/small model and canonical agent model overrides use that identity.
The CLI model argument also binds an explicit resumed session to Zen. The unchanged
canonical agent/skill/command snapshot retains all role-specific permission
restrictions. Sharing stays disabled; tool output stays 2000 lines / 51200 bytes.
Ambient `OPENCODE_PERMISSION` is removed because the pinned CLI would otherwise
apply it after the canonical bundle. Its value is neither inspected nor logged.

## Effort resolution

Only `high` and `xhigh` are valid Foundry tiers. For Zen, this release makes no
claim that provider-native reasoning variants implement those tiers. It sends no
invented `reasoningEffort` option: named below-HIGH and HIGH/XHIGH variants are
disabled, and an empty agent variant clears inherited Go selection in the pinned
CLI. `execution.requested_effort` records project discipline;
`execution.variant_resolution=provider_default_unverified` records the technical
limit honestly. The provider's internal reasoning budget remains unverified.
This is not permission to request below-HIGH work. A task requiring demonstrated
provider-native HIGH/XHIGH must not treat this override as such evidence.

Model/variant passthrough flags and blind `--continue`/`-c` are refused. Use the
launcher option; retain explicit session IDs or relaunch the TUI and type `/work`.
Saved full-output inspection remains preferred over expensive reruns.

## Interruption and evidence

KeyboardInterrupt returns 130, records `interrupted=true` and
`failure_class=INTERRUPTED`, and releases the writer lock. Child SIGINT (-2) is
normalized to 130; a child 130 is recorded as conventional interruption.
Other child exits retain their status. Spawn failure returns 127 with
`CHILD_START_FAILED`; no retry/provider switch occurs. Unexpected exceptions
propagate after end-telemetry is attempted; the outer finally releases the lock
even when telemetry fails. No process-killing mechanism is added.

`launch-context.json` records the full `execution` identity. Both session metric
records carry the selected model, `execution_provider`, `execution_override`,
`execution_profile`, `native_variant` when one is directly pinned,
`variant_resolution`, and requested project reasoning effort; the end record also
carries interruption status. Muse's project-level XHIGH routing is not mislabeled as a
top-level native model variant.

Missing Zen availability/authentication fails on that selected launch without
switching provider. Launcher/config tests do not prove authenticated connectivity.
Do not inspect credential files. Only project-policy-covered technical data may
be sent; unrelated private data and raw secrets remain forbidden.
