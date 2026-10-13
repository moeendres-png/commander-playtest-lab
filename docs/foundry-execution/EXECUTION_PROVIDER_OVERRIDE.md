# Explicit execution profile and provider overrides

Since the Owner directives of 2026-10-12 the default and only active executor is Step 5 Preview
on OpenCode Zen, `opencode/step-5-preview-free`, at its highest native variant `high` (the Zen
catalog lists no `max` for it). Whenever the project uses OpenCode it uses this model and
nothing else, because its Zen quota is free. `opencode-go/deepseek-v4.1-flash` is SUSPENDED:
its OpenCode Go monthly quota is exhausted. Every earlier executor is retired and removed from
the active configuration.

## Step 5 Preview HIGH profile (default, only active)

Omission selects Step 5 Preview HIGH. An explicit `--execution-profile step` is equivalent
and may be used for clarity in Foundry `init` or `launch` invocation:

```text
python3 tools/foundry/launcher.py launch <existing workstream arguments> --effort high --execution-profile step
```

The launcher inspects the live pinned-CLI catalog (`opencode models opencode`), selects
`opencode/step-5-preview-free` (else fails closed; Go ids never substitute) and pins that exact `--model` on the child argv, so the identity cannot drift at run
time. Do not substitute a different model or a lower native level. The selected
profile/model/native variant are recorded in launch context/environment and existing
model/provider telemetry.

No automatic model fallback exists. A Step 5 Preview runtime, quota, auth or catalog failure is
fail-closed and ends that run; it never re-resolves to DeepSeek or any other model.

The committed config whitelists only Step 5 Preview HIGH. Each launch narrows the bundle to the
resolved runtime identity; caller model/variant passthrough is refused.

## DeepSeek Max profile (SUSPENDED)

`--execution-profile deepseek` is refused with a `SUSPENDED` launch error. The profile stays in
`.foundry/executor-profiles.json` with its suspension reason and authority so that a later direct
Owner instruction can re-activate it by setting `runtime_status` back to `ACTIVE`; quota recovery
alone does not re-activate it. Its model is absent from `opencode.json` and from every lane.

### Qualified CLI compatibility

The qualified Foundry CLI remains OpenCode `1.18.30`. The 2026-09-29 DeepSeek smoke
(`providerID=opencode-go modelID=deepseek-v4.1-flash`, `foundry-implementer`, exit 0) is
historical provenance for the suspended profile. Requalification is required if the CLI pin,
catalog contract, provider protocol, or Step 5 Preview reasoning contract changes.

### Step 5 Preview runtime evidence

The authorized identity is `opencode/step-5-preview-free` (OpenCode Zen) with main model, small
model and reachable agents at native `high`. Its live catalog presence is `DIRECTLY_VERIFIED`
(2026-10-12, `opencode models opencode --verbose`: status active, cost 0, variants
low/medium/high). The authenticated runtime smoke is `NOT_RUN`: the first trusted lane run after
the switch is the runtime observation for the Zen identity and key
(`activation_evidence_2026_10_12` in `.foundry/executor-profiles.json`). Receipts of earlier
executors stay historical provenance of their own runs only.

## Non-authorized executors

The registry holds exactly two execution profiles, `step` (ACTIVE) and `deepseek`
(SUSPENDED), each at its highest native level (`high` and `max`). Only the ACTIVE one resolves; any other profile or provider
override is rejected.

Historical receipts that name earlier executor experiments remain valid provenance of their
own runs. They do not authorize future routing changes, are not migration targets, and must
not by themselves trigger a new governance/routing issue. Expanding or replacing the active
allowlist, including re-activating DeepSeek, requires a new direct user instruction.

## Effort resolution

`--execution-profile step --effort high` is the active pair; `--effort xhigh` is also
accepted and describes task/authority routing only. Omission selects Step 5 Preview HIGH. `--effort`
must be `high` or `xhigh`; below-`high` values are rejected. The project effort field never
lowers the executor's native level and never
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
