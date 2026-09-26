# Explicit execution-provider override

The default remains `opencode-go/muse-spark-1.3-contributor`. For an
operator-authorized workstream, add `--execution-provider zen` to its existing
Foundry `init` or `launch` invocation. All existing required arguments,
especially `--state`, source lock and ownership, remain required.

```text
python3 tools/foundry/launcher.py launch <existing workstream arguments> --effort high --execution-provider zen
```

Omit the option for canonical Go. `zen` is the only accepted override value;
unknown values fail closed. This flag is the explicit operator choice for this
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

`launch-context.json` records `execution` (override, provider, model, requested
effort, variant resolution). Both session metric records carry the selected
model, `execution_provider`, `execution_override`, `variant_resolution` and
requested reasoning effort; the end record also carries interruption status.

Missing Zen availability/authentication fails on that selected launch without
switching provider. Launcher/config tests do not prove authenticated connectivity.
Do not inspect credential files. Only project-policy-covered technical data may
be sent; unrelated private data and raw secrets remain forbidden.
