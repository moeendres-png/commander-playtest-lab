# Explicit execution profile and provider overrides

Since the Owner directive of 2026-10-13 the default and only active executor is DeepSeek V4.1
Flash on OpenCode Go, `opencode-go/deepseek-v4.1-flash`, at its highest native variant `max`.
Whenever the project uses OpenCode it uses this model and nothing else.
`opencode/step-5-preview-free` (Step 5 Preview on OpenCode Zen) is SUSPENDED. Every earlier
executor is retired and removed from the active configuration.

## DeepSeek MAX profile (default, only active)

Omission selects DeepSeek MAX. An explicit `--execution-profile deepseek` is equivalent
and may be used for clarity in Foundry `init` or `launch` invocation:

```text
python3 tools/foundry/launcher.py launch <existing workstream arguments> --effort high --execution-profile deepseek
```

The launcher resolves the canonical Go id `opencode-go/deepseek-v4.1-flash` (verifying it against
the live pinned-CLI catalog `opencode models opencode-go` whenever a catalog is supplied or
inspected; absent from it fails closed) and pins that exact `--model` on the child argv, so the identity cannot drift at run
time. Do not substitute a different model or a lower native level. The selected
profile/model/native variant are recorded in launch context/environment and existing
model/provider telemetry.

No automatic model fallback exists. A DeepSeek runtime, quota, auth or catalog failure is
fail-closed and ends that run; it never re-resolves to Step 5 Preview or any other model.

The committed config whitelists only DeepSeek MAX. Each launch narrows the bundle to the
resolved runtime identity; caller model/variant passthrough is refused.

## Step 5 Preview profile (SUSPENDED)

`--execution-profile step` is refused with a `SUSPENDED` launch error. The profile stays in
`.foundry/executor-profiles.json` with its suspension reason and authority so that a later direct
Owner instruction can re-activate it by setting `runtime_status` back to `ACTIVE`. Its model is
absent from `opencode.json` and from every lane. If it were re-activated it would resolve only
after live inspection of the Zen catalog (`opencode models opencode`).

### Qualified CLI compatibility

The qualified Foundry CLI remains OpenCode `1.18.30`. The 2026-09-29 DeepSeek smoke
(`providerID=opencode-go modelID=deepseek-v4.1-flash`, `foundry-implementer`, exit 0) is
historical provenance for the same model id. Requalification is required if the CLI pin,
catalog contract, provider protocol, or DeepSeek reasoning contract changes.

### DeepSeek runtime evidence

The authorized identity is `opencode-go/deepseek-v4.1-flash` (OpenCode Go) with main model, small
model and reachable agents at native `max`. The reactivation of 2026-10-13 follows the direct Owner
instruction "OpenCode soll wieder OpenCode Go über die aktuelle API im GitHub laufen". Quota
recovery after the 2026-10-10 monthly-quota exhaustion is assumed by the Owner and is not verified.
The live catalog check and the authenticated runtime smoke are `NOT_RUN`: the pinned-CLI catalog
inspection and the first trusted lane run after the switch are the reverification
(`activation_evidence_2026_10_13` in `.foundry/executor-profiles.json`). Receipts of earlier
executors stay historical provenance of their own runs only.

## Non-authorized executors

The registry holds exactly two execution profiles, `deepseek` (ACTIVE) and `step`
(SUSPENDED), each at its highest native level (`max` and `high`). Only the ACTIVE one resolves; any other profile or provider
override is rejected.

Historical receipts that name earlier executor experiments remain valid provenance of their
own runs. They do not authorize future routing changes, are not migration targets, and must
not by themselves trigger a new governance/routing issue. Expanding or replacing the active
allowlist, including re-activating Step 5 Preview, requires a new direct user instruction.

## Effort resolution

`--execution-profile deepseek --effort high` is the active pair; `--effort xhigh` is also
accepted and describes task/authority routing only. Omission selects DeepSeek MAX. `--effort`
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
