# WS190 Final Report

## Source Lock

Base `6eea80fb33746257e8434fd4e1c906765d8f22e9`, tree
`3a3ca37639d6cb30864bda0fa60bb35d3d7b94c5`, freshly verified against GitHub
main and isolated origin/main before edits. Branch:
`ws190/opencode-zen-provider-override-20260913`.

Validated technical head: `775384c27f24ad6ae198cadb4c36fd501d979ec3`;
tree `4fe833a5d7d7b33e9956445dda6b5c39dd31dfc1`.
Subsequent seal changes only evidence/state. The published branch HEAD identifies
that seal; validated technical identity deliberately stays separate.

## Work completed / architecture

Implemented launcher-owned `--execution-provider zen`, explicit one-invocation
substitution only. Go remains canonical and default; no quota/auth/error fallback.
Effective Zen config restricts the provider/model, substitutes provider-use policy,
retains canonical permissions and snapshots, and records identity in context and
both telemetry records. CLI model selection also overrides stale resumed-model history.

HIGH/XHIGH remains policy. Zen native variant equivalence is not established:
empty inherited agent variant, named variants disabled, no invented reasoning
option, `provider_default_unverified` recorded separately from requested effort.

KeyboardInterrupt is explicit exit 130 with end telemetry. Writer ownership is
released by outer finally even if telemetry itself fails. Ordinary child status is
preserved; spawn failure is 127; no process-killing or retry mechanism was added.

## Changes and preserved surfaces

- `tools/foundry/launcher.py`: bounded override, context/metrics identity, interrupt
  lifecycle, permission-override removal and forbidden passthrough checks.
- `tools/foundry/metrics.py`: four necessary allowlist fields only.
- `tests/foundry/test_launcher.py`: 31 new hermetic regression cases.
- `docs/foundry-execution/{README.md,ROUTING_AND_EFFORT.md,EXECUTION_PROVIDER_OVERRIDE.md}`:
  concise operator contract and technical effort distinction.
- This research directory: contract, implementation, validation, state and report.

Operator evidence preserved. No opencode.json, bootstrap, context capsule, CLI pin,
agent/command, state schema, simulator, engine pin, data or qualification changes.

## Tests / Evidence

DIRECTLY_VERIFIED: red interrupt reproduced exact UnboundLocalError; final committed
head passed 294 tests with 2 explicit skips (live export absent; CLI not on test
PATH). Required modules are individually enumerated in VALIDATION.json. Full
Foundry regression was justified by shared launcher/metrics changes. Ruff check
and format check passed for all touched Python files.

DIRECTLY_VERIFIED: actual pinned OpenCode 1.18.30 offline config resolution passed
for both Go and Zen in a network namespace with empty isolated credential/config
directories. Canonical role restrictions and `/work` survived effective merging.
CODE_DERIVED: config/policy interpretation and disabled-variant semantics.
ZEN_PROVIDER_RUNTIME=NOT_RUN: no authenticated or paid provider call.

## PASS / FAIL / UNKNOWN

WS190_LONG_TURN_RESILIENCE=PASS
INTERRUPT_SAFE_LAUNCHER=PASS
CANONICAL_DEFAULT_CHANGED=NO
ZEN_OVERRIDE_TOOLING=PASS
ZEN_OVERRIDE_EXPLICIT=PASS
ZEN_AUTO_FALLBACK=0
PERMISSION_WEAKENING=0
BELOW_HIGH_EXECUTION_ENABLED=0
WS78_TOKEN_ECONOMY_PRESERVED=PASS
RULES_BEHAVIOR_CHANGE=0
ENGINE_PIN_CHANGE=0
BEHAVIOR_CREDIT_CHANGE=0
ARCHITECTURE_FREEZE=NOT_CLAIMED
PRODUCTION_PROVIDER=NOT_SELECTED

## Remaining blockers / outputs / next action

No in-scope tooling blocker. Provider authentication, availability and internal
reasoning budget remain separate runtime prerequisites/unknowns. No credentials
were inspected. Persistent outputs are this evidence package and the authorized
branch; no PR/merge. A future authorized workstream explicitly adds
`--execution-provider zen`, or omits it for canonical Go; TUI resume remains `/work`.

Dependency unblocked: operator-selected Zen execution without editing canonical
config; interrupt-safe resumption under the existing ownership/state gates.
