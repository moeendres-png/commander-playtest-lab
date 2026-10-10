# Explicit execution profile and provider overrides

Since the Owner directive of 2026-10-10 the default and only active executor is
`opencode-go/space-bunny` at native `max`. `opencode-go/deepseek-v4.1-flash` is SUSPENDED: its
OpenCode Go monthly quota is exhausted. Space Bunny draws on the same OpenCode Go monthly limit
(its calls were refused with HTTP 429 `GoUsageLimitError` in workflow run 38049493597), so runs on
it end as `BLOCKED_SERVICE` until the quota resets or the Owner restores it.

## Space Bunny Max profile (default, only active)

Omission selects Space Bunny MAX. An explicit `--execution-profile space-bunny` is equivalent
and may be used for clarity in Foundry `init` or `launch` invocation:

```text
python3 tools/foundry/launcher.py launch <existing workstream arguments> --effort high --execution-profile space-bunny
```

The launcher inspects the live pinned-CLI catalog, selects the canonical
`opencode-go/space-bunny` (else the admitted legacy alias `opencode-go/space-bunny-free`, else
fails closed) and pins that exact `--model` on the child argv, so the identity cannot drift at run
time. Do not substitute a different model or a lower native level. The selected
profile/model/native variant are recorded in launch context/environment and existing
model/provider telemetry.

No automatic model fallback exists. A Space Bunny runtime, quota, auth or catalog failure is
fail-closed and ends that run; it never re-resolves to DeepSeek or any other model.

The committed config whitelists only Space Bunny MAX. Each launch narrows the bundle to the
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
catalog contract, provider protocol, or Space Bunny reasoning contract changes.

### Space Bunny runtime evidence

The authorized Space Bunny identity is `opencode-go/space-bunny` with main model, small model
and reachable agents at native `max`. After the catalog-ID rebind landed in PR #576, a fresh
authenticated trusted `/bunny` smoke on 2026-10-06 ran the pinned OpenCode CLI with
`MODEL=opencode-go/space-bunny` and `VARIANT=max`, the DeepSeek lane was skipped, and the Bunny
job completed successfully. The agent result reported `providerID=opencode-go modelID=space-bunny`;
that resolved identity is agent self-report (`CODE_DERIVED`) unless an authoritative runtime log is
bound, while the configured pins, job outcome and provider policy are `DIRECTLY_VERIFIED`. The
immutable receipt is `.foundry/space-bunny-rebind-runtime-activation-20261006.json`.

The 2026-09-29 authenticated smoke resolved the then-current
`opencode-go/space-bunny-free` identity. That receipt remains historical provenance only and is
not activation evidence for the rebound model ID. The 2026-10-06 smoke ran the `/bunny` lane
(`bunny-verifier`); the `/oc` lane (`foundry-implementer`) runs the same pinned model since
2026-10-10, and its first authenticated run after this change is its own runtime observation.

## Non-authorized executors

The registry holds exactly two execution profiles, `space-bunny` (ACTIVE) and `deepseek`
(SUSPENDED), both at native `max`. Only the ACTIVE one resolves; any other profile or provider
override is rejected.

Historical receipts that name earlier executor experiments remain valid provenance of their
own runs. They do not authorize future routing changes, are not migration targets, and must
not by themselves trigger a new governance/routing issue. Expanding or replacing the active
allowlist, including re-activating DeepSeek, requires a new direct user instruction.

## Effort resolution

`--execution-profile space-bunny --effort high` is the active pair; `--effort xhigh` is also
accepted and describes task/authority routing only. Omission selects Space Bunny MAX. `--effort`
must be `high` or `xhigh`; below-`high` values are rejected. The project effort field never
lowers the executor's native `max` level and never
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
