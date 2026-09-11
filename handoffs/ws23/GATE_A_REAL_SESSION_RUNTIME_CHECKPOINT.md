# WS-23 Gate A — Real Forge Session Runtime Checkpoint

## Source Lock

- WS-23 branch source commit: `2f20c17c8e4b57e0d434dc142c01acdd1b90a202`
- PR #139 merge test SHA used by GitHub Actions: `ce9cfce60813f76181a6aecda6951e1fa26f10e7`
- WS-19 required head: `5822250fb865351d457f8970a00fc1f23083fd3c`
- WS-19 runtime-bearing commit: `d06fe667e5bc432709cf9244ea2188a543386c91`
- Forge commit: `1e604105f9e279331063824943b9222b6589f5d8`
- Forge tree: `994976e06aaf99b807646b60b1aa2ac9f7703df4`
- WS-10R bundle SHA-256: `2f002a4d020e99e44270239fd3a894e9be6f08eddf9fdd233b81ba8d3f070577`
- common fixture manifest SHA-256: `e7f34ea4b2543132440e7e5fdb47c6cb4d4908f05fb49f6fa59f3e0592ca3bd4`

## Runtime Evidence

GitHub Actions workflow: `WS-23 Forge Production Vertical Slice`

- run id: `33277637248`
- job id: `99167055213`
- artifact id: `9722008125`
- artifact name: `ws23-forge-vertical-ce9cfce60813f76181a6aecda6951e1fa26f10e7`
- uploaded artifact ZIP SHA-256: `968ef305f909cedf342d4af3b00a31e2b1366f2d8d2e8bdb3edb611a7f4fda18`

The runtime job passed all of the following in one execution:

1. exact WS-19 ancestry and frozen WS-10R/common-manifest hashes;
2. exact pinned Forge commit/tree/license/controller/RemoteClientGui blobs;
3. unmodified pinned Forge `forge-core` + `forge-game` Maven build;
4. regenerated WS-19 strict-shell regression: 109 abstract callbacks and 3 prohibited stock RemoteClientGui defaults;
5. generated WS-23 strict external provider compilation;
6. provider source/classpath exclusion of `forge-ai`, `forge-gui`, `RemoteClientGuiGame`, and `PlayerControllerAi`;
7. headless Forge `StaticData` initialization entirely in the GPL-side JVM;
8. creation of a real Forge `Match` and real Forge `Game` with exactly four real Forge `Player` seats;
9. externally answered Forge startup decisions;
10. real Forge turn/phase progression into priority;
11. 17 invocations of the real `PlayerController.chooseSpellAbilityToPlay()` path, with 16 externally submitted PASS decisions and the 17th invocation producing the intentional controlled-stop guard;
12. final provider result `WS23_CONTROLLED_AFTER_PRIORITY_16`;
13. separate-process GPL boundary evidence generation.

The session runner summary was:

```json
{"priority_decisions": 17, "stop_reason": "WS23_CONTROLLED_AFTER_PRIORITY_16", "verdict": "PASS"}
```

## Gate A Verdict

**PASS — RUNTIME_VERIFIED**

This proves the architecture can keep a persistent authoritative Forge game in a separate non-GUI/non-AI JVM, externally route real production startup/priority callbacks, progress a genuine game, and terminate under provider control.

This checkpoint does **not** promote Gate B/C/D or the WS-23 Continue/Stop decision. In particular, complete priority option enumeration, representative non-priority decision round-trips, actor-scoped observation, honeycard safety, common semantic fixtures, replay/RNG, and Commander semantics remain separate gates.
