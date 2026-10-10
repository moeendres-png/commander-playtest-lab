# Explicit execution profile and provider overrides

Since the Owner directives of 2026-10-10 the default and only active executor is Space Bunny
on OpenCode Zen, `opencode/space-bunny-free`, at native `max`. `opencode-go/deepseek-v4.1-flash`
is SUSPENDED: its OpenCode Go monthly quota is exhausted. The Go Space Bunny id
`opencode-go/space-bunny` draws on the same Go monthly limit (refused with HTTP 429
`GoUsageLimitError` in workflow run 38049493597) and is no longer admitted; Zen serves Space
Bunny at no charge under the same `OPENCODE_API_KEY` variable.

## Space Bunny Max profile (default, only active)

Omission selects Space Bunny MAX. An explicit `--execution-profile space-bunny` is equivalent
and may be used for clarity in Foundry `init` or `launch` invocation:

```text
python3 tools/foundry/launcher.py launch <existing workstream arguments> --effort high --execution-profile space-bunny
```

The launcher inspects the live pinned-CLI catalog (`opencode models opencode`), selects
`opencode/space-bunny-free` (else fails closed; Go ids never substitute) and pins that exact `--model` on the child argv, so the identity cannot drift at run
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

The authorized Space Bunny identity is `opencode/space-bunny-free` (OpenCode Zen) with main
model, small model and reachable agents at native `max`. The trusted `/bunny` run 38053801098
(issue #684, 2026-10-10) completed with the existing `OPENCODE_API_KEY` and its session store
reported `providerID=opencode modelID=space-bunny-free variant=max`
(`activation_evidence_2026_10_10` in `.foundry/executor-profiles.json`).

Earlier Go evidence: after the catalog-ID rebind landed in PR #576, a fresh
authenticated trusted `/bunny` smoke on 2026-10-06 ran the pinned OpenCode CLI with
`MODEL=opencode-go/space-bunny` and `VARIANT=max`, the DeepSeek lane was skipped, and the Bunny
job completed successfully. The agent result reported `providerID=opencode-go modelID=space-bunny`;
that resolved identity is agent self-report (`CODE_DERIVED`) unless an authoritative runtime log is
bound, while the configured pins, job outcome and provider policy are `DIRECTLY_VERIFIED`. The
immutable receipt is `.foundry/space-bunny-rebind-runtime-activation-20261006.json`.

The 2026-09-29 authenticated smoke resolved the then-current
`opencode-go/space-bunny-free` identity. That receipt remains historical provenance only and is
not activation evidence for the rebound model ID. Both Go receipts are provenance only and
do not establish the Zen identity.

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
