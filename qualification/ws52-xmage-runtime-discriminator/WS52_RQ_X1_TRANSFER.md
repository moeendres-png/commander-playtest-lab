# WS52 — RQ-X1 Hypothesis Transfer (CODE_DERIVED + DIRECTLY_VERIFIED delta)

RQ-X1 is source evidence, not runtime qualification. This file records
exactly which RQ-X1 findings WS52 consumes as hypotheses and the basis
on which they transfer from pin `77d7646d` to the candidate pin
`0c1f455e`.

## Transfer basis (DIRECTLY_VERIFIED)

`git -C /tmp/rq-xmage-src diff --name-only 77d7646d 0c1f455e` returns
exactly the 6 WS39/WS42 commander-history/restore files listed in
`WS52_SOURCE_LOCK.md`. Every other engine file — including all files
cited below — is byte-identical at both pins. Transfer of source-level
findings for unchanged files is therefore exact, not approximate.

## Consumed hypotheses and WS52 re-verification plan

| # | RQ-X1 claim | Engine files (identical at both pins) | WS52 runtime re-verification |
|---|---|---|---|
| H1 | Engine computes exact legal sets; `XmageFullGamePlayer`-equivalent native path selects within them (priority via `getPlayable`, cast via `getCastableSpellAbilities`, targets via `possibleTargets`, modes via `getAvailableModes`) | `PlayerImpl.java`, `TargetImpl.java`, `Modes.java`, `ChoiceImpl.java`, bridge `XmageFullGamePlayer.java` | M1: live priority/cast/target frames; oracle compares credited set to engine set; mode boundary recorded |
| H2 | Selection binds exact native UUID with server-side revalidation; duplicate-equal objects cannot be confused (`Map<UUID,…>`, `MageObjectReference` zcc) | `AbilityImpl.java`, `MageObjectImpl.java`, `MageObjectReference.java`, `TargetImpl.java` | M2: non-first selection + execution ack distinguishing alternatives; twin-run divergence |
| H3 | No native global semantic Action ID / state-revision / execution-ack envelope; `PlayerResponse` carries value only | `PlayerResponse.java`, `HumanPlayer.java` wait/response | M3: project envelope rejects stale/wrong/unknown/malformed; state-revision gap recorded explicitly |
| H4 | Server-side per-principal projection exists (`GameView` per-viewer); client cannot expand legal sets | `GameController.java`, `GameSessionPlayer.java`, `GameView` | M4: ledger/gateway runtime sentinel test (project-owned projection, not `GameView` — source `GameView` redaction is NOT claimed as runtime PASS) |
| H5 | Rules RNG is JVM-global (`RandomUtil`), shared with AI/setup, plus unseeded sources (`Collections.shuffle()` no-arg, per-call `SecureRandom`, per-UUID `Random`); `setSeed` is manual global only; no per-game stream/serialization | `RandomUtil.java` (byte-identical, body re-quoted in §below), `PlayerImpl.java` shuffle/flip/dice sites, `ComputerPlayer*.java`, `Library.java` | M5: core-stream repeat, unseeded-source, contamination, snapshot/reexecution, process-isolation probes with a real Rules-random event |
| H6 | Existing replay facilities do not satisfy CSN Semantic Replay | replay/bookmark APIs | M5-RD: bounded decision-prefix reexecution; first divergence persisted |

## Re-quoted `RandomUtil` body at candidate pin (DIRECTLY_VERIFIED)

`git show 0c1f455e:Mage/src/main/java/mage/util/RandomUtil.java`:

- `private static final Random random = new Random();` (JVM-global static)
- `public static Random getRandom()` exposes the shared instance
- `public static void setSeed(long newSeed)` mutates global state
- `randomFromCollection` walks collection iteration order
- No tape, no per-game seed, no serialization hooks

Identical to the RQ-X1 quotation at `77d7646d`.

## Non-transferable items (remain UNKNOWN until runtime)

- Actual client/server wire behavior (WS52 uses the headless
  `XmageFullGamePlayer` lane, not the `HumanPlayer` network path).
- Timing/concurrency, performance, true hidden-info safety under
  adversarial observation (M4 tests this at runtime).
- Real RNG streams and replay fidelity (M5 tests this at runtime).
- Any MTG Rules question (→ `AUTHORITY_GATE: MTG_RULES`, none raised yet).

## Evidence discipline

- Runtime-executed facts: `DIRECTLY_VERIFIED`.
- Bounded contract proven by runtime gates: `TECHNICALLY_CONFORMANT`.
- Source-inspection findings: `CODE_DERIVED`.
- Unreached/unproven: `UNKNOWN`.
- No new evidence class is introduced.
