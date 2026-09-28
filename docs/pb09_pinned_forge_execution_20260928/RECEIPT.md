# PB-09 — pinned upstream Forge candidate, executed

Date: 2026-09-28
Classification: `DIRECTLY_VERIFIED` (live external process, real engine)
`ARCHITECTURE_FREEZE = NOT CLAIMED`. `PRODUCTION_PROVIDER = NOT SELECTED`.

## Source lock

| Field | Value |
|---|---|
| Rules-Core candidate (pin) | `a37a865a53280dd8ad6fad3384d69611e8c5a42f` — upstream `forge-2.0.14` |
| Bridge source (pinned) | `4753bb7c72ea60d653121e0bab989077b4009f9c` |
| Bridge name / version | `forge-protocol2-bridge` / `2.0.14-ws-a1d-h4f` |
| Transport protocol | `2.0.0` |
| Build tree | disposable `git archive` export of `4753bb7c`, outside every existing Forge checkout |
| Maven | offline (`-o`), `-pl forge-protocol2-bridge -am`, `-DskipTests` |
| Lab HEAD at execution | see `RECEIPT.json` |

## What PB-09 previously recorded

`docs/pre_freeze_completion_20260927/PB09_FORGE_CANDIDATE_IDENTITY.md` §7 recorded:

> *upstream_baseline*: no exact pristine upstream checkout with proven provenance has been
> established, so upstream behaviour is UNKNOWN.

and §4 recorded that the existing Forge column was produced at `ef958ee9`, a
Lab-authored fork of the Forge Rules Core, so it measured Lab's Forge work rather
than Forge.

## What was established here

**1. The bridge source is purely additive over the pin.** The full diff from the
pin to the bridge commit touches only `forge-protocol2-bridge/**` and `pom.xml`.
Zero `forge-core`, `forge-game`, `forge-ai` or `forge-gui` source files changed, so
the executed tree contains the pinned Rules Core unmodified and adds only a
Protocol-2 transport. This is the same property the container drift guard demands
(`docker/forge/Dockerfile`).

**2. The pinned candidate builds offline.** `mvn -o -DskipTests -pl
forge-protocol2-bridge -am install` succeeded against the local dependency closure.
No network was required and no plugin or dependency was missing.

**3. The pinned candidate executes a live 4P Commander lifecycle with an external
decision surface.** `tests/integration/test_forge_bridge_h4f_live.py` passed
(38.79 s) against `FORGE_SOURCE_DIR` pointing at the pinned tree. That test is the
existing qualified mechanism and it independently pins
`FORGE_ENGINE_SHA=a37a865a…` and asserts the bridge reports exactly that commit.
It exercises the full nine-phase protocol: canonical handshake, four real deck
imports, four-player Commander game creation, an external `STARTING_PLAYER`
decision answered from engine-offered options, mulligan convergence, a `PRIORITY`
decision with a changed post-state hash, principal-scoped state where the actor
sees its own hand and every opponent hand is fully hidden, a fail-closed rejection
of a fabricated `legal_action_id`, and clean shutdown.

**4. The bridge reports the pinned commit, not the fork.**

```json
{"provider": "forge", "release": "2.0.14",
 "engine_commit": "a37a865a53280dd8ad6fad3384d69611e8c5a42f",
 "engine_commit_source": "env:FORGE_ENGINE_SHA",
 "protocol_version": "2.0.0",
 "bridge_name": "forge-protocol2-bridge", "bridge_version": "2.0.14-ws-a1d-h4f"}
```

## What is still NOT established

- **PB-05 remains open.** `engine_commit_source` is `env:FORGE_ENGINE_SHA`: the
  commit string is operator-supplied, not derived from the built bytes. The *build*
  here is provably pinned (it came from a `git archive` of `4753bb7c`, whose first
  parent is the pin and whose diff is purely additive), but the value the bridge
  reports about itself is not self-verifying. A build-derived commit or an
  equivalent container provenance file is still required for AF00.
- **This is not the Forge FULL107 column.** The H4-F surface is one bounded
  live lifecycle. The 107-row denominator has **not** been re-executed at the
  pinned candidate, so no comparison of the two candidates at their true identities
  exists yet.
- **PB-09 itself is still OPEN and Coordinator-owned.** This receipt is decision
  *input*. It makes the pinned-upstream resolution executable and costed; it does
  not select it, and nothing here repins any field.
- **The existing native-suite credit is not transferable.** The fork's bound
  native suites execute at a descendant whose engine modules differ from the pin,
  so `verify_engine_identity` correctly refuses to transfer them. A pin-side
  native suite would have to be authored; 19 of the 23 classes the fork bound do
  not exist at `4753bb7c`.
- **Licence posture is not adjudicated.** If the pin is selected, AF11 must be
  recomputed for plain upstream GPL-3.0 rather than for a Lab GPL derivative.

## Reproduction

```
git -C <forge-clone> archive 4753bb7c72ea60d653121e0bab989077b4009f9c \
  | tar -x -C <pinned-build-tree>
cd <pinned-build-tree>
MAVEN_OPTS=-Djava.io.tmpdir=<writable> mvn -B -ntp -o -DskipTests \
  -Dcheckstyle.skip=true -pl forge-protocol2-bridge -am install
MAVEN_OPTS=-Djava.io.tmpdir=<writable> mvn -B -ntp -o -q -pl forge-protocol2-bridge \
  dependency:build-classpath -DincludeScope=runtime \
  -Dmdep.outputFile=<absolute path>/forge-protocol2-bridge/target/cp-wsr22.txt

cd <lab>
FORGE_SOURCE_DIR=<pinned-build-tree> FORGE_LIVE_TMPDIR=<writable> \
  python -m pytest -q tests/integration/test_forge_bridge_h4f_live.py -v
```

Note: `dependency:build-classpath` resolves a relative `-Dmdep.outputFile` against
the module directory, producing a doubled path
(`forge-protocol2-bridge/forge-protocol2-bridge/target/...`). Pass an absolute path
or move the file afterwards; `bridge_launcher._read_classpath` fails closed when
the manifest is absent.
