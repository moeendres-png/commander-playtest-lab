# Explicit execution profile and provider overrides

Since the Owner instruction of 2026-10-16 the default and only active executor is DeepSeek V4.1
Flash on OpenCode Zen, `opencode/deepseek-v4.1-flash-free`, at its highest native variant `max`
(models.dev lists effort values low/high/max; context 200000, output 32000; Zen marks it free,
zero-retention, no training). Step 5 Preview left the live Zen catalog (checked 2026-10-16) and is
retired. The OpenCode Go provider and every earlier executor are retired and removed from the
active configuration. Whenever the project uses OpenCode it uses this model and nothing else.

## DeepSeek V4.1 Flash MAX profile (default)

Omission selects it. An explicit `--execution-profile deepseek` is equivalent and may be used for
clarity in Foundry `init` or `launch` invocation:

```text
python3 tools/foundry/launcher.py launch <existing workstream arguments> --effort high --execution-profile deepseek
```

The launcher inspects the live pinned-CLI catalog (`opencode models opencode`), selects
`opencode/deepseek-v4.1-flash-free` (else fails closed; no other id substitutes) and pins that
exact `--model` on the child argv, so the identity cannot drift at run time. Do not substitute a
different model or a lower native level (no variant below `high` is configured anywhere). The
selected profile/model/native variant are recorded in launch context/environment and existing
model/provider telemetry.

No automatic model fallback exists. A runtime, quota, auth or catalog failure is fail-closed and
ends that run; it never re-resolves to another model.

The committed config whitelists only DeepSeek V4.1 Flash with `max` enabled and every other
variant disabled. Each launch narrows the bundle to the resolved runtime identity; caller
`--model`/`--variant` passthrough is refused.

### Qualified CLI compatibility

The qualified Foundry CLI remains OpenCode `1.18.30`. Requalification is required if the CLI pin,
catalog contract, provider protocol, or the DeepSeek reasoning contract changes. Earlier smokes
(OpenCode Go DeepSeek 2026-09-29, Space Bunny, Step 5 Preview) are historical provenance of their
own runs only.

### Runtime evidence

The authorized identity is `opencode/deepseek-v4.1-flash-free` (OpenCode Zen) with main model,
small model and reachable agents at native `max`. Its live catalog presence is `DIRECTLY_VERIFIED`
(2026-10-16, GET https://opencode.ai/zen/v1/models lists `deepseek-v4.1-flash-free`). The
authenticated runtime smoke is `NOT_RUN`: the first trusted lane run after the switch is the
runtime observation for the Zen identity and key (`activation_evidence_2026_10_16` in
`.foundry/executor-profiles.json`).

## Non-authorized executors

The registry holds exactly one execution profile, `deepseek` (ACTIVE, native `max`). Any other
profile or provider override is rejected.

Historical receipts that name earlier executors remain valid provenance of their own runs. They do
not authorize future routing changes, are not migration targets, and must not by themselves trigger
a new governance/routing issue. Adding or replacing the active allowlist requires a new direct
user instruction. The Token Harbor profile (`/oc-th`, `deepseek-th`) was retired 2026-10-16 by
Owner instruction (balance exhausted, no top-up).

## Effort resolution

`--execution-profile deepseek --effort high` is the active pair; `--effort xhigh` is also
accepted and describes task/authority routing only. Omission selects DeepSeek V4.1 Flash MAX.
`--effort` must be `high` or `xhigh`; below-`high` values are rejected. The project effort field
never lowers the executor's native level (`max`) and never opens a second native variant. Direct
OpenCode root configuration already pins the native variant.
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
