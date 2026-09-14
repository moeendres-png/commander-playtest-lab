# WS197 Final Report — Forge WS191 First-Wave Runtime Qualification

## Verdict

`FORGE_RQC3_FIRST_WAVE = 0 PASS / 0 FAIL / 15 BLOCKED / 0 UNKNOWN` over denominator exactly 15 (corrected WS90 authority). `H01_CORRECTED_FAMILY_FRESH = BLOCKED (A BLOCKED, B BLOCKED, C BLOCKED inside one slot)`. `GLOBAL_BEHAVIOR_CREDIT_CHANGE = 0`. `FULL107 = NOT_RUN`. `ARCHITECTURE_FREEZE = NOT_CLAIMED`. `PRODUCTION_PROVIDER = NOT_SELECTED`.

This is HONEST bounded evidence, not a promotion to production-ready. Forge remains `PARTIAL`/`NO_PROVIDER_READY`.

## What was executed (real runtime, DIRECTLY_VERIFIED)

Complete corrected Forge First Wave against the exact WS191 candidate through the real separate-process Protocol-2 bridge (`run_ws197_first_wave.py`), one live 4P game per slot with actual WS90 cards natively resolved by Forge:

- Handshake per slot: `provider=forge`, `protocol=2.0.0`, `engine_commit=aa5c00aa…`, caps `legal=false/submit=false/events=false` (truthful DEGRADED).
- Deck import 4/4 per slot with slot-specific actual cards (e.g. A03 Drudge Skeletons/Lightning Bolt; C01 Force of Will/Turn to Frog; H01 Clone/Humility/Runeclaw Bear; G02 Ghalta commander + Murder) — all natively resolved (15/15 import ok).
- 4P create/start with no injected seat/life; external STARTING_PLAYER choice (actor+revision bound, opaque option IDs); mulligan keeps; PRIORITY pass with `executed=true` and `pre_hash != post_hash`; principal-scoped `get_game_state` (own hand visible, all opponent hands `<hidden>`, libraries withheld); fail-closed unknown-option `submit_action` rejected with `RulesEngineProtocolError` (15/15); clean shutdown.
- Per-slot transcript: `transcripts/RQ-C3-*.json` (15) with game/actor/revision/action/hash/observation/probe evidence + `source_lock` (WS197 head/tree, bridge/commit/tree, Rules-Core SHA/tree, WS90 package, RNG/replay identity).

## Why BLOCKED (systemic, evidenced — not assumed)

Two inseparable layers, both recorded per slot:

1. `SCENARIO_INJECTION_UNSUPPORTED`: the H4F bridge starts from natural deck-import/game-start only. No surface establishes the authority's `neutral_initial_state` (battlefield permanents, hands, counters,-controller mappings, life tweaks). Every slot's scripted Rules events are therefore unreachable terminally.
2. First WS90 decision-kind unsupported on the authoritative H4F surface (zero-mana-only execution; classifier UNSUPPORTED on targeting/modes/X/announce/optional-costs/non-forced parts; `chooseCard/order/getChoices` throw; combat/triggers/tuck/concede/replay/RNG/partners/non-4P unsupported):
   - CAST-first slots (A03 A04 B01 C01 C03 D06 F01 G02 H01 I01): `CAST_UNSUPPORTED` (nonzero mana → `MANA_PAYMENT_CHOICE`).
   - Combat-first slots (E01 E02 G03 J02): `ATTACKERS_UNSUPPORTED`.
   - G04: `CONCESSION_UNSUPPORTED`.
   - Full per-kind reasons in each transcript's `unsupported_kinds`; RNG `UNCONTROLLED` (`seed_supported=false`) and `NO_TWIN_REPLAY` bound per slot (material for J02 d20 and all replay claims).

No slot was skipped (`NOT_REACHED` count 0). Construction/import is not claimed as behavior proof; process startup is not claimed as behavior proof; the green H4F handshake is claimed only as bounded-lifecycle proof with semantic assertions (hash change, scoping, fail-closed) — never as First-Wave PASS.

## H01 corrected family (one slot, three subcases)

`H01_FAMILY.json`: HUMILITY_FIRST BLOCKED (copy surface unsupported; absence non-discriminating alone; post-Humility 0/0 SBA discriminator unexecutable without injection); CLONE_FIRST BLOCKED (required copy offer absent); NO_HUMILITY BLOCKED (required copy offer absent). Terminal 1/1 alone never claimed sufficient. First slot-level blocker recorded as CAST (Clone `{3}{U}` nonzero precedes copy choice in script order); copy-choice layer documented in the family record.

## Legality / scoping / fail-closed

- `LEGAL_ACTION_AUTHORITY = Rules Core alone` (bridge-native `getAllPossibleAbilities+canPlay`; Lab routes versioned requests, validates pydantic surface, chooses only offered discretionary options).
- `PRINCIPAL_SCOPING = PASS` (15/15 live: own hand visible, opponents `<hidden>`).
- `FAIL_CLOSED_UNSUPPORTED_DECISIONS = PASS` (15/15 unknown-option probes rejected; no silent skip; unsupported frames carry zero options + explicit reason).
- `REQUESTED_OPTION_FILTERING = ABSENT`. `INTERNAL_FORGE_AI_AUTHORITY = ABSENT` (no `forge-ai` dep; `AvailableActions` never consulted; headless GUI choice-calls throw).
- Forbidden shortcuts (first/random/default yes-no, fabricated actions/targets/modes/mana, heuristic legality, outcome injection, GUI defaults): all ABSENT by construction + probe evidence.

## Files

- `run_ws197_first_wave.py` (harness, Lab-owned, no Rules semantics)
- `SOURCE_LOCK.md`, `WS191_IMPACT_ADJUDICATION.md`, `WS90_INTEGRITY.md`, `FINAL_REPORT.md` (this file)
- `FIRST_WAVE_MATRIX.json` (15 rows), `H01_FAMILY.json`, `WS197_SUMMARY.json`, `transcripts/*.json` (15), `SHA256SUMS`
- Resolved manifests: `qualification/SHA256SUMS` + `WS17_SHA256SUMS` resealed per WS17 contract (coverage only).

## Exact next action

Checkpoint + commit this evidence; push via canonical `safe_push.py` (dry-run → actual → fetch verification); return terminal handoff. Do NOT run Full107, select a provider, claim Freeze, merge WS196, or open a PR.
