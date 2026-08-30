# WS-23 — FINAL HANDOFF

## Final Verdict

**WS-23 workstream verdict: PASS.**

**Architecture gate verdict: `CONTINUE`.** Forge has been runtime-qualified far enough to show that a genuine separate GPL JVM can own the authoritative game/rules state, expose Forge-authoritative external decisions, accept exact external selections, preserve actor-scoped hidden information, replay the same discretionary/RNG sequence deterministically, and execute the bounded common vertical slice without GUI/AI/default legality reconstruction.

**Production readiness: `FALSE`.** `CONTINUE` is an architecture-viability result, not production admission. Broad behavioral coverage is intentionally incomplete: 17/135 canonical common fixtures PASS and 1/29 actual-card regression fixtures PASS. All unexecuted semantics remain `NOT_RUN / FAIL_CLOSED_UNSUPPORTED`; load/parse/reachability receives no functionality credit.

`FORGE_ARCHITECTURAL_STOP` is **not warranted**.

---

## Source Lock

### Commander Lab

- Repository: `moeendres-png/commander-playtest-lab`
- PR: Draft PR #139, `ws23/forge-production-provider` -> `main`
- Base/main lock used by the final PR evidence: `c83e52ae79ff2242578757c0f517badbb1a2621c`
- WS-19 baseline lock: `5822250fb865351d457f8970a00fc1f23083fd3c`
- Final implementation/evidence head before this handoff-only commit: `f024ba494b7367a514efcb5b89687ffcefb8a154`
- Corresponding PR merge SHA used by the final evidence workflows: `9e3a46128d75f1150c8b7bc7f841bb5897b6c16c`

This handoff is a documentation-only successor commit. Runtime claims below remain locked to `f024ba494b7367a514efcb5b89687ffcefb8a154` / merge SHA `9e3a46128d75f1150c8b7bc7f841bb5897b6c16c` unless explicitly identified as earlier checkpoint evidence.

### Forge

- Upstream: `Card-Forge/forge`
- Commit: `1e604105f9e279331063824943b9222b6589f5d8`
- Tree: `994976e06aaf99b807646b60b1aa2ac9f7703df4`
- Version: `2.0.15-SNAPSHOT`
- Upstream source modified by WS-23: **no**

### Frozen qualification inputs

- Rules Service Protocol: `commander-lab.rules-service/1.1.0`
- WS-10R bundle SHA256: `2f002a4d020e99e44270239fd3a894e9be6f08eddf9fdd233b81ba8d3f070577`
- Common fixture manifest SHA256: `e7f34ea4b2543132440e7e5fdb47c6cb4d4908f05fb49f6fa59f3e0592ca3bd4`
- Qualification obligation catalog SHA256: `df3b354858d5e01cdb899ac24cdbf5f269fb81c0bf495b1bcb4129b1498dd963`

### GPL helper source hashes

- `qualification/providers/forge/gpl/Ws23ForgeAuthority.java` — `67e292411710f1fc739921ab7e574626062a9f84505447c84a4b6086eb6ade96`
- `qualification/providers/forge/gpl/Ws23ForgeBootstrap.java` — `51e40edea789cd35bceec5ccde8d20372d201939685c46ec226aa24adfbc5dd5`
- `qualification/providers/forge/gpl/Ws23ForgeGateD.java` — `721a4a99ec5df2dcdcee5555a4a0db5e8cfc34cd7aa7cd1af25aa1c97ac15280`

The WS-17 integrity manifests were updated only to cover these newly committed qualification files; no WS-17 semantic verdict was weakened or bypassed.

---

## Work Completed

1. Preserved the WS-19 isolated, fail-closed Forge process boundary and requalified it against the current branch.
2. Built the pinned, unmodified Forge game modules in CI.
3. Generated a strict GPL-side `PlayerController` surface covering all 109 abstract callbacks; production-reachable discretion is either explicitly externalized or fails closed.
4. Constructed a real persistent four-player Forge `Match` / `Game` in a separate JVM with no `forge-ai`, `forge-gui`, `RemoteClientGuiGame`, or `PlayerControllerAi` provider dependency.
5. Routed real Forge priority/action selection, targets, native mana payment, combat, Commander replacement choices, simultaneous-trigger ordering, and explicit pass decisions to external DecisionFrames.
6. Serialized viewer-scoped observations on the Forge side before the process boundary and verified hidden/public information behavior.
7. Exercised actual Lightning Bolt through Forge priority, target, native mana cost, stack, and resolution.
8. Exercised actual Rograkh, Son of Rohgahh (`CARD_02`) from the real Command zone through native Commander replacement/cast semantics to the battlefield; Forge commander-cast count is 1.
9. Exercised two actual Soul Wardens producing two simultaneous native ETB triggers; external `orderSimultaneousSa` selected their ordering and native resolution produced exactly +2 life.
10. Exercised actual Fog through the same Forge-authoritative priority/mana/stack path. Its combat prevention was runtime-observed with attacker damage 0 and blocker damage 0 and both creatures surviving.
11. Exercised rules randomness through real Forge `FlipCoinEffect/MyRandom`, seed 230023, with a 16-flip rules-RNG tape.
12. Replayed the complete DecisionTape in a clean second JVM and required actor, decision kind, options digest, offered option IDs, selection, RNG semantics, and final snapshot to match.
13. Produced a canonical bounded matrix of 14/14 PASS and only then set the architecture gate to `CONTINUE`.
14. After `CONTINUE`, executed real Forge lifecycle smoke qualification for 2P, 3P, 4P, and 5P. Each reached native `FORGE_GAME_RETURNED` with external priority decisions rather than a synthetic controlled success.
15. Materialized the full 29-card behavioral denominator and full 135-common-fixture denominator without giving parsing/reachability credit.
16. Committed Ruff formatting and restored standard CI integrity/hash coverage.
17. Re-ran WS-19 requalification, dedicated WS-23 workflows, production qualification, Windows hygiene, and standard CI on the final implementation/evidence head.

---

## New Findings

### 1. Forge architecture is viable across the required process boundary

The pinned Forge architecture can sustain external player authority while the GPL JVM remains the sole owner of legality and rules execution for the demonstrated paths. No proprietary-side legality reconstruction was required for the bounded slice.

### 2. Native Forge priority-pass semantics matter

For pinned Forge `PhaseHandler`, a completed external priority PASS must map to `chooseSpellAbilityToPlay() == null`. Returning an empty list does not express the same native pass semantics and caused the initial broad lifecycle loop to remain in priority. The final provider maps the explicit external PASS to the Forge-native null pass result; it does not invent legal actions.

### 3. Architecture viability is not broad card/rules completeness

The strongest current broad result is intentionally partial:

- 2P–5P lifecycle smoke: 4/4 PASS / `RUNTIME_VERIFIED`.
- bounded common slice: 14/14 PASS / `RUNTIME_VERIFIED`.
- full common denominator: 17/135 PASS, 118/135 `NOT_RUN / FAIL_CLOSED_UNSUPPORTED`.
- actual-card behavioral denominator: 1/29 PASS (`CARD_02` Rograkh), 28/29 `NOT_RUN / FAIL_CLOSED_UNSUPPORTED`.
- `production_ready = false`.

The 2P–5P result proves real lifecycle/priority progress and native game return for those player counts. It is a lifecycle smoke result, not proof of complete multiplayer card/rules behavior for every count.

---

## Changes

Principal WS-23 artifacts include:

- `handoffs/ws23/WORKSTREAM_CONTRACT.md`
- `handoffs/ws23/GATE_A_REAL_SESSION_RUNTIME_CHECKPOINT.md`
- `handoffs/ws23/WS23_FINAL_HANDOFF.md`
- `qualification/providers/forge/gpl/Ws23ForgeAuthority.java`
- `qualification/providers/forge/gpl/Ws23ForgeBootstrap.java`
- `qualification/providers/forge/gpl/Ws23ForgeGateD.java`
- `scripts/ws23_generate_forge_vertical_provider_v2.py`
- `scripts/ws23_run_vertical_v2.py`
- `scripts/ws23_build_bounded_common_matrix.py`
- `scripts/ws23_generate_forge_broad_provider.py`
- `scripts/ws23_run_player_count_matrix.py`
- `scripts/ws23_build_broad_qualification.py`
- `.github/workflows/ws23-forge-authority-v2.yml`
- `.github/workflows/ws23-forge-broad-qualification.yml`
- WS-23 vertical-slice workflow/support files on PR #139
- `qualification/SHA256SUMS`
- `WS17_SHA256SUMS`

Forge upstream source was not modified.

---

## Tests / Evidence

### Gate A checkpoint

Earlier preserved real-session checkpoint:

- Workflow: `WS-23 Forge Production Vertical Slice`
- Run: `33277637248`
- Job: `99167055213`
- Source commit: `2f20c17c8e4b57e0d434dc142c01acdd1b90a202`
- Artifact: `9722008125`
- ZIP SHA256: `968ef305f909cedf342d4af3b00a31e2b1366f2d8d2e8bdb3edb611a7f4fda18`
- Result: PASS / `RUNTIME_VERIFIED`

### Final Gate-D / authority evidence

- Workflow: `WS-23 Forge Authority Observation V2`
- Run: `33303413877`
- Result: SUCCESS
- Head: `f024ba494b7367a514efcb5b89687ffcefb8a154`
- PR merge SHA: `9e3a46128d75f1150c8b7bc7f841bb5897b6c16c`
- Artifact ID: `9729683700`
- Artifact ZIP SHA256: `b533ad46a3e7248473b2186b49866d0876cfa6ea81a0d616326e9543f0f83d7a`

Key runtime results:

- 14/14 bounded matrix PASS.
- architecture verdict `CONTINUE`.
- `CARD_02` Rograkh behavioral PASS.
- two real Soul Warden triggers externally ordered and natively resolved, +2 life.
- actual Fog prevention: attacker damage 0, blocker damage 0.
- RNG engine path `FlipCoinEffect/MyRandom`, seed `230023`, sequence `TTHHHHHTHHTHHTHT`.
- clean-JVM DecisionTape/RNG/final-snapshot replay PASS.

### Final broad qualification

- Workflow: `WS-23 Forge Broad Qualification`
- Run: `33303413910`
- Result: SUCCESS
- Head: `f024ba494b7367a514efcb5b89687ffcefb8a154`
- Artifact ID: `9729685688`
- Artifact ZIP SHA256: `b82bc0021234dd497002c392c420bb60445a82894462be2062b5e9fcf1486585`

Broad summary:

- Gate D: `CONTINUE`.
- Player-count lifecycle: 4/4 PASS (`PLAYER_COUNT_2P`, `PLAYER_COUNT_3P`, `PLAYER_COUNT_4P`, `PLAYER_COUNT_5P`).
- Natural Forge game-return turns: 2P turn 66, 3P turn 98, 4P turn 131, 5P turn 164.
- Common fixture denominator: 17 PASS / 135 total; 118 NOT_RUN.
- Actual-card denominator: 1 PASS / 29 total; 28 NOT_RUN.
- `production_ready = false`.
- Separate-JVM GPL boundary: PASS; no Forge AI/GUI on provider classpath; no Forge classes in proprietary process; upstream Forge tree unmodified.

The 17 common PASS IDs are the 14 bounded IDs plus `PLAYER_COUNT_2P`, `PLAYER_COUNT_3P`, and `PLAYER_COUNT_5P`; `PLAYER_COUNT_4P` is already in the bounded set. Every remaining common row is explicitly `NOT_RUN / FAIL_CLOSED_UNSUPPORTED`. Every actual-card row except `CARD_02` is explicitly `NOT_RUN / FAIL_CLOSED_UNSUPPORTED`.

### Final standard CI

- Workflow: `CI`
- Run: `33303413853`
- Head: `f024ba494b7367a514efcb5b89687ffcefb8a154`
- Result: SUCCESS
- Ruff lint: PASS
- Ruff format: PASS (`719 files already formatted`)
- Mypy: PASS (`250 source files`)
- Test suite: PASS — `798 passed, 1 skipped` in 456.91 s
- Compile: PASS
- Secret-pattern scan: PASS
- Wheel build: PASS
- Security job: PASS
- CI evidence artifact ID: `9729783511`
- CI evidence ZIP SHA256: `29be3c6b3700ab5ccdf2df011f3e9404c62a720cd45e610fa71b96ff37d7650a`
- Security evidence artifact ID: `9729677738`
- Security evidence ZIP SHA256: `b5b8fa959f82427ca5a42253467dfe951e824e2620dde28b20ef0cb8e4532e8a`

The single skipped test is the pre-existing differential test requiring a separately configured XMage or Forge differential command; it is not counted as PASS evidence.

### Final WS-19 regression requalification

- Workflow: `WS-19 Forge Post-WS17R Requalification`
- Run: `33303413856`
- Result: SUCCESS
- Artifact ID: `9729705061`
- Artifact ZIP SHA256: `3a0f206ce7caccddd5d801cfdd93146d78edc4b7e3353268685a2af33e3f85f2`
- Exact baseline/frozen semantics verification, pinned Forge source/build, strict provider generation, WS-10R handshake, and fresh 135-request execution all succeeded.

### Other final-head workflows

- `WS-23 Forge Production Vertical Slice` run `33303413883`: SUCCESS; artifact `9729682941`, ZIP SHA256 `48f1527fd93a365aac578f099ec18f4f794cb1caf4f3993784ef868986466233`.
- `Production Qualification` run `33303413857`: SUCCESS.
- `Windows Runtime Hygiene` run `33303413869`: SUCCESS.

---

## PASS / FAIL / UNKNOWN

| Area | Verdict | Evidence class / qualification |
|---|---|---|
| Frozen project/source inputs | PASS | verified hashes/commits |
| GPL separate-process boundary | PASS | runtime/static verified |
| Upstream Forge source unchanged | PASS | verified |
| Gate A real session | PASS | RUNTIME_VERIFIED |
| Gate B external decisions / native round trips for bounded paths | PASS | RUNTIME_VERIFIED |
| Gate C actor-scoped observations | PASS | RUNTIME_VERIFIED |
| Gate D bounded common slice | PASS | 14/14 RUNTIME_VERIFIED |
| Architecture Continue/Stop gate | **CONTINUE** | architecture viable |
| 2P–5P lifecycle smoke | PASS | 4/4 RUNTIME_VERIFIED |
| Actual-card broad behavioral coverage | PARTIAL | 1/29 PASS; 28 NOT_RUN |
| Full common-fixture behavioral coverage | PARTIAL | 17/135 PASS; 118 NOT_RUN |
| Replay/RNG bounded proof | PASS | RUNTIME_VERIFIED |
| Standard CI / security / formatting | PASS | final implementation head |
| WS-19 regression requalification | PASS | final implementation head |
| `FORGE_ARCHITECTURAL_STOP` | NOT WARRANTED | no architectural stop condition observed |
| Forge production admission | **FAIL / NOT READY** | `production_ready=false` |
| WS-23 architecture-qualification workstream | **PASS / COMPLETE** | required deliverables completed |

No `NOT_RUN` row is promoted to PASS. No card receives behavioral PASS from import, loading, parsing, or source presence.

---

## Remaining Blockers

There are **no remaining blockers to closing WS-23 itself**.

There are substantial follow-on blockers before Forge can be admitted as a production Rules Core:

1. implement and runtime-qualify the remaining 118 canonical common fixtures;
2. implement and runtime-qualify the remaining 28 actual-card regression fixtures;
3. widen the strict external decision callback surface as those rule/card paths become production-reachable;
4. rerun provider-neutral admission/differential qualification after the denominator materially expands;
5. preserve exact 4P Commander decision-evidence requirements for project deck decisions even though the engine/provider may support 2P–5P technically.

These are production-development / later-workstream blockers, not reasons to leave WS-23 open.

---

## Outputs

- Draft PR #139: `https://github.com/moeendres-png/commander-playtest-lab/pull/139`
- Workstream contract: `handoffs/ws23/WORKSTREAM_CONTRACT.md`
- Gate A checkpoint: `handoffs/ws23/GATE_A_REAL_SESSION_RUNTIME_CHECKPOINT.md`
- Final handoff: `handoffs/ws23/WS23_FINAL_HANDOFF.md`
- Final implementation/evidence head: `f024ba494b7367a514efcb5b89687ffcefb8a154`
- Final Broad artifact: `9729685688`, SHA256 `b82bc0021234dd497002c392c420bb60445a82894462be2062b5e9fcf1486585`
- Final Gate-D artifact: `9729683700`, SHA256 `b533ad46a3e7248473b2186b49866d0876cfa6ea81a0d616326e9543f0f83d7a`
- Final CI artifact: `9729783511`, SHA256 `29be3c6b3700ab5ccdf2df011f3e9404c62a720cd45e610fa71b96ff37d7650a`
- Final WS-19 regression artifact: `9729705061`, SHA256 `3a0f206ce7caccddd5d801cfdd93146d78edc4b7e3353268685a2af33e3f85f2`

PR #139 remains Draft and unmerged. WS-23 does not select Forge as the final provider, merge architecture, or freeze the project architecture.

---

## Dependencies Unblocked

WS-23 unblocks the central coordinator to treat Forge as an architecture-qualified `CONTINUE` candidate and compare that result against the other candidate handoffs without granting Forge production status.

If Forge remains on the active path, the next implementation wave can widen real behavioral coverage from the proven external-authority/process/replay foundation instead of reopening the architecture viability question.

---

## Exact Next Action

**Coordinator action:** ingest this handoff as `WS-23 = COMPLETE`, `Forge architecture = CONTINUE`, `production_ready = false`; compare it against the other candidate qualification results and choose the next architecture/integration workstream. If Forge is continued, prioritize implementation and runtime qualification of the 118 remaining common fixtures and 28 remaining actual-card behaviors before using Forge for production Commander deck-decision evidence.

Do **not** merge PR #139 or select Forge as final Rules Core solely from this workstream.
