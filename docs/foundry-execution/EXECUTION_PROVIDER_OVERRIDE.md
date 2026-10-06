# Explicit execution profile and provider overrides

The committed/default and preferred executor is `opencode-go/deepseek-v4.1-flash` at native `max`.
The explicitly selectable secondary executor is `opencode-go/space-bunny` at native `max`.

## DeepSeek Max profile

DeepSeek MAX is the default. An explicit `--execution-profile deepseek` is equivalent and may be
used for clarity in Foundry `init` or `launch` invocation:

```text
python3 tools/foundry/launcher.py launch <existing workstream arguments> --effort high --execution-profile deepseek
```

The required policy selects `opencode-go/deepseek-v4.1-flash` at native `max`. The launcher pins
that exact `--model` on the child argv, so the committed default cannot drift at run time. Do not
substitute a different model or a lower native level. The selected profile/model/native variant are
recorded in launch context/environment and existing model/provider telemetry.

No automatic model fallback exists. A DeepSeek runtime, quota, auth or catalog failure is
fail-closed and ends that run. Selecting another executor afterwards is an explicit task-rerouting
decision, never a silent retry. A later Space Bunny run may resume the same branch and explicit
workstream state only after the first writer exits and releases the lock. Parallel DeepSeek +
Space Bunny writers are allowed only on independently owned worktrees/surfaces under the normal
Foundry ownership gates.

The committed config defaults to DeepSeek MAX. Each launch narrows the bundle to its explicitly
selected executor; caller model/variant passthrough is refused.

### Qualified CLI compatibility

The qualified Foundry CLI remains OpenCode `1.18.30`. Direct verification of the live `opencode-go`
catalog on 2026-09-29 lists `deepseek-v4.1-flash` exactly, and an authenticated bounded smoke under
the exact launcher-injected bundle resolved `providerID=opencode-go modelID=deepseek-v4.1-flash`
with the `foundry-implementer` agent and exit 0.

If the catalog/model/auth path is unavailable, the selected DeepSeek run fails closed; it must
never fall back silently to Space Bunny. Requalification is required if the CLI pin, catalog
contract, provider protocol, or DeepSeek reasoning contract changes.

## Space Bunny Max secondary profile

Space Bunny MAX is the explicit secondary executor:

```text
--execution-profile space-bunny --effort high
```

The authorized Space Bunny identity is `opencode-go/space-bunny` with main model, small model
and reachable agents at native `max`. After the catalog-ID rebind landed in PR #576, a fresh
authenticated trusted `/bunny` smoke on 2026-10-06 ran the pinned OpenCode CLI with
`MODEL=opencode-go/space-bunny` and `VARIANT=max`; runtime logs resolved
`providerID=opencode-go modelID=space-bunny`, and the Bunny job completed successfully. The
immutable receipt is `.foundry/space-bunny-rebind-runtime-activation-20261006.json`.

The 2026-09-29 authenticated smoke resolved the then-current
`opencode-go/space-bunny-free` identity. That receipt remains historical provenance only and is
not activation evidence for the rebound model ID. Use Space Bunny for bounded, mechanical,
token-heavy, bulk and background work, or where a workstream contract explicitly selects it.
There is no silent fallback between DeepSeek MAX and Space Bunny MAX in either direction.

## Non-authorized executors

The current OpenCode authority contains exactly two execution profiles: `deepseek` and
`space-bunny`, both at native `max`. Any other profile or provider override is rejected.

Historical receipts that name earlier executor experiments remain valid provenance of their
own runs. They do not authorize future routing changes, are not migration targets, and must
not by themselves trigger a new governance/routing issue. Expanding or replacing the active
two-profile allowlist requires a new direct user instruction.

## Effort resolution

`--execution-profile deepseek --effort high` and `--execution-profile space-bunny --effort high`
are the active pairs; `--effort xhigh` is also accepted and describes task/authority routing only.
Omission selects DeepSeek MAX. `--effort` must be `high` or `xhigh`; below-`high` values are
rejected. The project effort field never lowers either executor's native `max` level and never
opens a second native variant. Direct OpenCode root configuration already pins the native variants.
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
`execution_profile`, `native_variant`, `variant_resolution`, and requested project
reasoning effort; the end record also carries interruption status. The selected
executor's actual native identity is recorded explicitly.

Missing selected-executor availability/authentication fails without switching provider. Launcher/config tests do not prove authenticated connectivity.
Do not inspect credential files. Only project-policy-covered technical data may
be sent; unrelated private data and raw secrets remain forbidden.
