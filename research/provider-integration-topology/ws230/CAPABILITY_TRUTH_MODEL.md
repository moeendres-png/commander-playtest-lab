# Capability Truth Model (fail-closed negotiation)

Evidence class: `CODE_DERIVED` (design derived from normative fail-closed semantics + observed provider truth).
Canonical evidence vocabulary is NOT changed: `PASS/FAIL/UNKNOWN/NOT_RUN/PARTIAL/NOT_APPLICABLE` (gates) and provider booleans stay as-is on the wire.
This model governs how the successor *interprets* booleans + notes, so bounded proof is never silently upgraded.

## 1. The problem (observed)

- Forge WS227 proves a strong **bounded** surface (30 decision families mapped, divided-allocation + representative-family replay with fresh-JVM proof, actor-only observations, Core-owned RNG) while its **global** flags stay intentionally false: `legal_actions_supported=false`, `action_submission_supported=false`, `event_log_supported=false`, `replay_supported=false` (`export_replay` unsupported; replay only via SemanticReplay projection). The spec note is explicit: "Global action flags stay false; bounded proven subset is described in families."
- XMage full-game lane proves complete discretionary-family behavior (17 families, PILOT_BOUNDARY PASS) and cardinality/RNG/hidden-info PASS, yet the B4-D compatibility lane still reports `legal_actions_supported=false, action_submission_supported=false` because target/mode/choice/combat classes are incomplete on *that* lane. Same provider, different lanes, different truth.
- A single global boolean per capability therefore cannot carry the truth. Any consumer that reads `replay_supported_via_semantic=true` as global `replay_supported=true`, or that reads a bounded family PASS as whole-boundary PASS, manufactures a gate PASS from design. WS226 already blocks this: Forge AF04 stays FAIL (stock-path prohibited defaults) and AF03 stays UNKNOWN (seam-scoped authority is supporting, not satisfying) despite WS217 seam progress.

## 2. Five-state capability value (interpretation layer, not new vocabulary)

Every capability is interpreted as one of:

| State | Meaning | Gate effect |
|-------|---------|-------------|
| `SUPPORTED_GLOBAL` | Proven across the whole production-reachable surface at the pinned identity | May satisfy the corresponding gate *together with* all other required evidence |
| `SUPPORTED_BOUNDED` | Proven for an explicitly enumerated family/subset/lane only (with the bound recorded: family list, lane, pin, run IDs) | Satisfies NOTHING global; only the enumerated bound may be consumed, and only by consumers that declare the same bound |
| `UNSUPPORTED` | Provider truthfully reports absence (flag false + fail-closed behavior proven) | Consumer must not request it; requesting it is a typed failure, not a fallback trigger |
| `NOT_QUALIFIED` | Surface exists in code but required runtime was never executed at this pin (`NOT_RUN`) | Fail closed: treated as absent until runtime proves otherwise |
| `UNKNOWN` | No reliable statement exists | Fail closed: treated as absent; blocks any dependent PASS |

Wire representation is UNCHANGED (existing booleans + `notes` array + family descriptors). The five states are derived by the handshake consumer as: `boolean + notes/family scope + standing/evidence refs`. No flag inflation: setting a global boolean true on bounded evidence is forbidden and is itself a handshake-falsification negative (see `FAIL_CLOSED_NEGATIVE_MATRIX.json`).

## 3. Application to current truth (no upgrades)

| Capability | XMage full-game lane | XMage B4-D compat lane | Forge WS227 (Protocol 2.0.0 + SemanticReplay) |
|------------|----------------------|------------------------|-----------------------------------------------|
| Legal-action enumeration | `SUPPORTED_BOUNDED` (17 discretionary families on full-game lane; WS215 PILOT_BOUNDARY PASS; global completeness still bounded by AF08 UNKNOWNs) | `UNSUPPORTED` (flags false; target/mode/choice/combat incomplete; truth boundary in `rules_engines.json`) | `SUPPORTED_BOUNDED` (complete parked-set multiset per frame + 30 family mapping; whole-boundary `UNSUPPORTED` — stock path FAIL preserved) |
| Action submission | `SUPPORTED_BOUNDED` (bounded targetless/nonmodal + generic decision-bound submission with negatives 117/117) | `UNSUPPORTED` (flag false) | `SUPPORTED_BOUNDED` (exactly-once validated submit per frame; free-input/divided vectors Core-validated) |
| Observation / hidden-info | `SUPPORTED_BOUNDED` (HIDDEN_INFO_CARDINALITY PASS per count; oracle 9985 frames/0 violations; F-HIDE-02 hardening noted as improvement) | lane-scoped, not claimed | `SUPPORTED_BOUNDED` (actor-only projection + WRONG_ACTOR negatives; whole-engine hidden-info campaign `NOT_QUALIFIED`) |
| Rules RNG | `SUPPORTED_BOUNDED` (explicit per-game seed binding + twins/diverge controls per count; campaign-scale attribution stays with AF09 tape lane) | `UNSUPPORTED` (`seed_supported=false`; "Seed remains unknown/uncontrolled") | `SUPPORTED_BOUNDED` (Core-owned `bindSeed`/root/explicit/calls; single-flight discipline; unseeded legacy path observational-only) |
| Semantic replay | `SUPPORTED_BOUNDED` (WS218 tape lane 2P–5P dual PASS + tamper matrix; XMage-side consumer exists) | `UNSUPPORTED` (`replay_supported=false`) | `SUPPORTED_BOUNDED` (provider-observed via SemanticReplay; `export_replay` stays `UNSUPPORTED`; Forge Lab consumer `NOT_QUALIFIED` — explicitly not implemented here) |
| Cardinality 2P–5P | `SUPPORTED_GLOBAL` for session mechanics (AF02 PASS per count; 6P NOT_SUPPORTED) | not claimed | `NOT_QUALIFIED` (`max_players=4` in WS227 caps; 5P/Commander gaps unrelated and unproven) |
| Event export | `SUPPORTED_BOUNDED` (B4-D audit stream = bridge-lifecycle boundaries, explicitly NOT an exhaustive internal tap) | same bounded note | `UNSUPPORTED` (`export_event_log` refused for principal privacy; audit internal only) |

## 4. Negotiation rules (fail closed)

1. Handshake advertises booleans + machine-readable bound descriptors (family list / lane / pin / evidence refs). Absent descriptor ⇒ interpreted as global claim ⇒ verified globally or rejected.
2. Consumer declares the bound it needs. Need ⊄ offered bound ⇒ typed `unsupported` failure before any game starts. No downgrade, no subset-silent-execution.
3. Post-handshake requests for anything outside the negotiated bound fail with typed `unsupported`, even if the provider "could" do it on another lane.
4. Bounded PASS rows never roll up to global PASS in standing computation (standing generator semantics preserved).
5. Any global flag flipped true on bounded evidence alone = falsified handshake ⇒ AF01 can never PASS for that build (negative test required).
