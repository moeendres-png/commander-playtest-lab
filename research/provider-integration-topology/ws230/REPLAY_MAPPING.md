# Replay Mapping (one Lab tape, two native projections)

Evidence class: `CODE_DERIVED`. No replay runtime was executed by WS230. No Forge Lab replay implemented here.

## 1. The neutral contract both lanes map onto

- Tape contract: `semantic-replay-tape/1.0.0` (Lab-owned).
- Consumer discipline (WS218 `REPLAY_CONSUMER_CONTRACT.json`, 14 steps): exactly-one resolution (`0 => CHOSEN_OPTION_MISSING`, `>1 => CHOSEN_OPTION_AMBIGUOUS`); forbidden: fuzzy match, skip, missing-decision injection, requested-option filtering, second legality engine.
- Fresh process per replay; one game per process enforced; atomic tmp+replace writes; `.incomplete` never sealed.
- Canonicalization excludes timestamps, wall-clock diagnostics, request ids, raw engine/player/object UUIDs (unless proven nonsemantic and mapped), process-local array positions; preserves stack/graveyard/transcript order.
- Divergence taxonomy (18 classes, fail closed, no WARN_AND_CONTINUE): source/domain/initial-state/actor/class/revision/observation/legal-set/chosen-missing/chosen-ambiguous/RNG-call/RNG-result/event-digest/state-digest/early-termination/extra-decision/terminal-outcome/malformed-tape.
- RNG: calls-coordinate-plus-state-transition; `explicit_required=true`; `RandomUtil` NOT authoritative; root = manifest seed + live binding; results never injected.

## 2. XMage lane: `semantic-replay-tape/1.0.0` (native)

- Modules: canonicalization / fingerprint / tape / tape_helpers / divergence / source_lock / recorder / consumer / capability (WS218 `CHOSEN_REPLAY_ARCHITECTURE.json`, option A: Python-side tape over production JSONL lane, no Java changes; fingerprints from authoritative frames; calls-coordinate RNG; concede lifecycle steps).
- State digest `semantic-state-digest-1.0.0`; option identity `semantic-option-identity-1.0.0`; canonicalization `semantic-canonical-1.0.0`.
- Proven: 4 records + 8 replays across 2P–5P all PASS (fresh JVMs); same-seed twins MATCH; distinct-seed DIVERGE; tamper matrix 19/19 fail-closed (WS218 `VALIDATION.json` / `POSITIVE_REPLAY.md`; AF09 PASS tape-lane scope).
- Still out of tape-lane scope (WS215 impact note, unchanged): campaign-scale (135-fixture) replay proof stays with G14; `bit_exact_replay_validated` false everywhere (honest).

## 3. Forge lane: `forge-semantic-replay/1.0.0` over `semantic-replay-tape/1.0.0` (native projection)

- `SemanticReplay.java` serializes authoritative Core state/options into stable neutral semantics (projection-only; Core validates before mutation).
- Per-step coordinates: manifest (`commander-ffa` seat principals pN, explicit seed binding), `decision_class` (`forge:<kind>/1`), actor pN, revision frameSeq, observation/principal digests, legal-set digest+size, selected fingerprints+redacted labels, numeric value+bounds coherence, RNG callsBefore/After, event offset/digest, post digest, terminal seat outcomes.
- Proven in Forge repo (WS227 seal, 139 bridge tests + 9 semantic-replay + 2 fresh-process): Arc 2+1 in-process + fresh-JVM RECORD+REPLAY dual PASS; Seedcore 3+1 PASS; tamper/divergence 8 fail-closed (legal-set drift, malformed, ambiguous, missing, RNG drift, state drift, stale revision, wrong actor); no state injection (tape scan would find 0 injection fields); no outcome injection; exactly-once resolution.
- Preserved: no state injection (ScenarioBootstrap rejects stack/decision_script; record/replay construct exact scenario/manifest + seed and submit native options/vectors only); no outcome injection; no raw-UUID equality dependence (fingerprints exclude UUIDs; redaction mirrors WS218 lineage); Core-owned RNG regeneration (`bindSeed`, regenerate-not-inject).

## 4. How both fit under one Lab tape/consumer model

| Concern | XMage native | Forge native | Shared consumer rule |
|---|---|---|---|
| Manifest | orchestration seed + deck handles + N + seat map | scenario/manifest + seed + seat principals pN | Same required fields; seat maps N-principal; source-lock SHAs differ per provider (never unified) |
| Decision identity | decision_id/offset/actor-UUID/class | frameSeq/class/actor-pN | Compared by coordinate equality within a tape, never across providers |
| Option identity | semantic fingerprint (Python lane) | optionFingerprint SHA256 (Java lane) | Same exactly-once rule (0→MISSING, >1→AMBIGUOUS) |
| RNG coordinates | rules_seed + explicit + getRulesRandomCalls | root_seed + explicit + getCallCount before/after | Same drift rule (callsBefore mismatch → RNG_CALL_DRIFT; contract mismatch → RESULT_DRIFT) |
| Event coordinates | monotonic audit offset + pre/post state hashes | auditSize offset + eventDigest | Same digest-mismatch abort |
| Checkpoints | seed + calls + turn/phase + offset + state digest | postDigest + public/principal digests + turn/phase/step + revision + event offset | Same checkpoint-compare-then-continue |
| Terminal | seat-ordered outcomes | seat-sorted five-field rows + digests | Same TERMINAL_OUTCOME_MISMATCH rule |

## 5. Exact future integration seam (NOT implemented in WS230)

1. **Forge Lab consumer module** (CPL Python, new file): reads `semantic-replay-tape/1.0.0` tapes whose `tape_producer == forge-semantic-replay/1.0.0`, launches a fresh Forge child JVM per replay (`FORGE_ENGINE_SHA` bound, DISPLAY removed, stdout JSONL only), replays manifest+seed + native submits, and compares coordinates with the shared divergence taxonomy. Mirrors the XMage consumer's 14 steps; shares canonicalization policy, not code paths that assume XMage UUIDs.
2. **Tape discrimination**: consumer refuses tapes whose producer id / decision-class namespace / source-lock SHAs it does not implement (typed failure, never cross-provider replay).
3. **Provenance gate**: only tapes recorded from the pinned provider SHA (`eb87b317…` / successor pin) with explicit seed binding are replayable; unseeded legacy `setRandom` tapes are observational-only.
4. **What stays provider-side**: fingerprint computation, redaction, digest algorithms (Forge-native `forge-semantic-canonical/1.0.0` vs Lab `semantic-canonical-1.0.0` — policy-equivalent, implementation-distinct). The Lab consumer verifies digests by recomputation from observed frames, never by trusting the tape's self-report alone.
