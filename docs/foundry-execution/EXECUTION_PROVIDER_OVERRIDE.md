# Explicit execution profile and provider overrides

The committed/default and preferred executor is `opencode-go/space-bunny-free` at native `max`.

## Space Bunny Max profile

Space Bunny MAX is selected by default. An explicit `--execution-profile space-bunny` is equivalent and may be used for clarity in
Foundry `init` or `launch` invocation:

```text
python3 tools/foundry/launcher.py launch <existing workstream arguments> --effort max --execution-profile space-bunny
```

This selects `opencode-go/space-bunny-free` and pins every injected agent to native
`max` reasoning. The launcher requires `--effort max` for this profile; no HIGH/XHIGH alias is accepted. This preserves the
native Space Bunny reasoning level. The selected profile/model/native variant are
recorded in launch context/environment and existing model/provider telemetry.

No automatic model fallback exists. Space Bunny failure, quota/auth failure, or child
exit ends that run. A later Muse run may resume the same branch and explicit workstream
state only after the first writer exits/releases the lock. Parallel Muse + Space Bunny
writers are allowed only on independently owned worktrees/surfaces under the normal
Foundry ownership gates.

The committed config defaults to Space Bunny MAX. Each launch narrows the bundle
to its explicitly selected executor; caller model/variant passthrough is refused.

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

## Muse XHIGH profile

Muse is an explicit alternate only:

```text
--execution-profile muse --effort xhigh
```

This selects `opencode-go/muse-spark-1.3-contributor` and pins the main model,
small model and reachable injected agents to native `xhigh`. Muse HIGH is rejected.
There is no silent fallback from Space Bunny MAX to Muse XHIGH or vice versa.


## Historical Zen override

The legacy `--execution-provider zen` flag still exists in the launcher. It does not
provide verified native XHIGH and is not authorized as an active executor. Its
implementation removal/refusal is deferred to the active launcher owner.
No automatic model/provider fallback exists. Historical Zen records remain valid
provenance of their own runs, not authority for new work.

## Effort resolution

`--execution-profile space-bunny --effort max` and
`--execution-profile muse --effort xhigh` are the only active pairs. Omission
selects Space Bunny MAX at the policy/config level. **Implementation gap:** the
current launcher still requires a historical high/xhigh project-tier argument and
rejects max. Do not treat these desired native-pair examples as currently working
launcher commands or use HIGH as an authorized workaround. The active completion
campaign owns the launcher repair; see `../project_integrity_20260928/OWNERSHIP_DEFERRALS.json`.
Direct OpenCode root configuration already pins the native variants.
Use explicit session IDs or a fresh TUI `/work`; blind continuation is refused.

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
carries interruption status. Muse's selected native XHIGH identity is recorded explicitly.

Missing selected-executor availability/authentication fails without switching provider. Launcher/config tests do not prove authenticated connectivity.
Do not inspect credential files. Only project-policy-covered technical data may
be sent; unrelated private data and raw secrets remain forbidden.
