# WS207 Authority Adjudication — setup-only overlay + WS208/WS212 impact

Status: adjudicated. Zero behavior credit. The sealed WS90 pack remains
immutable provenance; this overlay alters only setup facts impossible under
legal Commander construction, per explicit Coordinator authority.

## 1. B01 singleton fixture (Soul Warden ×2 on P0 → Soul Warden + Essence Warden)

Fresh Oracle verification (Scryfall API, 2026-09-14):

- Soul Warden: `{W}`, Creature — Human Cleric, 1/1,
  "Whenever another creature enters, you gain 1 life."
  (`oracle_id f3fad295-…`, Commander legal).
- Essence Warden: `{G}`, Creature — Elf Shaman, 1/1,
  "Whenever another creature enters, you gain 1 life."
  (`oracle_id 6ca2a89e-…`, Commander legal).

Semantic equivalence proof for THIS scenario:

1. Trigger sentences byte-identical: mandatory (no "may"), no intervening
   "if", no replacement wording, no additional triggered/activated/static
   ability on either card (`keywords: []` both).
2. Entering creature is Llanowar Elves in both worlds: each Warden sees it
   ("another creature") and triggers once; P0 controls exactly two
   simultaneous relevant triggers either way.
3. Five total triggers (P0×2, P1/P2/P3×1), APNAP stacking with P0 ordering
   its own two, top-down resolution — unchanged.
4. Differing facts (name, `{W}` vs `{G}`, Human Cleric vs Elf Shaman) have no
   Rules interaction with any tested mechanic (no tribal, color, or type
   matters in B01). P0's commander (Kenrith, 5-color) covers both identities;
   P0 basics carry Plains + Forest so both setup casts are payable.
5. Life assertions (P0 42, others 41) and Elves-on-battlefield assertions are
   preserved verbatim.

Deck singleton-legality PROVEN in-engine (`deck_validation.json`, 4/4 seats
import `ok`, 99+1). Native Essence Warden cast observed at setup offset 246
(DIRECTLY_VERIFIED, zero credit).

## 2. E01 singleton fixture (Runeclaw Bear ×2 on P1 → Runeclaw Bear + Grizzly Bears)

Fresh Oracle verification (Scryfall API, 2026-09-14):

- Runeclaw Bear: `{1}{G}`, Creature — Bear, 2/2, empty Oracle text
  (`oracle_id ec49dfcf-…`, Commander legal).
- Grizzly Bears: `{1}{G}`, Creature — Bear, 2/2, empty Oracle text
  (`oracle_id 14c8f55d-…`, Commander legal).

Equivalence proof: identical game objects except name (same cost, P/T,
subtype, color, no abilities). The tested mechanics — two separate attackers,
two defenders, per-creature Propaganda `{2}` tax on the P0-bound attacker
only, unblocked 2-damage each — cannot distinguish them. Propaganda +
Runeclaw Bear assembled natively in setup (DIRECTLY_VERIFIED); Grizzly Bears
undrawn in the single attempt (UNKNOWN, retained blocker).

## 3. G03 native commander-damage ledger (no injection)

Correction: the 12 pre-existing commander damage must be built by native
Ghalta combat hits on P1 (same commander, same player) before the tested
subsequent hit; the prelude carries zero behavior credit. Procedure: cast
commander Ghalta natively → attack P1 (no blockers available) → each unblocked
12-power hit ledgers 12 natively → tested hit takes the ledger 12→24 (21+
SBA loss under 903.10a). Setup evidence: ledger UNPROVEN in the uniform
500-decision budget (Ghalta costs 12 with no cost reduction available; ~turn 3
reached; P1 life 40; twin match). No injection mechanism exists or was used.

## 4. WS208/WS212 seed-authority impact (adjudicated, binding implemented)

1. Inspection: every WS207 seed path previously controlled only the
   process-global `RandomUtil` (production `XmageFullGameSession` calls
   `RandomUtil.setSeed(seed)`; zero `setRulesSeed` references in
   `engine-bridge/src/main` — CODE_DERIVED via grep).
2. Engine contract on the pin (javap `mage.game.Game`): `setRulesSeed(long)`,
   `getRulesSeed()`, `isRulesSeedExplicit()`, `setRequireExplicitSeed(boolean)`
   all present. No repin needed; WS212 authority commit not required locally.
3. Bytecode note: `Library.shuffle()` (no-arg) delegates to
   `RandomUtil.getRandom()`, but the discrimination experiment proves the
   initial deal does NOT follow that path (see 5).
4. All `opening_` (RandomUtil-only) scan evidence SUPERSEDED: retained as audit
   trail, never selected, never reproduced, never credited.
5. Discrimination experiment (F01 decks, fresh JVMs):
   A (ru=13405, rules=13405) and B (ru=99999, rules=13405) dealt IDENTICAL
   hands (6×Forest + Rampant Growth); C (ru=13405, rules=99999) dealt a
   different hand. The native initial shuffle is driven by the per-game Rules
   RNG. WS208 CONFIRMED empirically (DIRECTLY_VERIFIED, zero credit).
6. Binding model `DUAL_FIXED_EXPLICIT`: production constructor still fixes
   `RandomUtil.setSeed(seed)`; the qualification-only hook additionally calls
   `game.setRulesSeed(seed)` + `game.setRequireExplicitSeed(true)` BEFORE
   `game.start/init` and fails closed when `isRulesSeedExplicit()` is false or
   the seed mismatches. Production `XmageFullGameSession` untouched (grep
   PROVEN at seal). Reproduction: F01-13405 identical rare opening in 3/3
   fresh JVMs; all 15 catalog seeds reproduced by independent twin JVMs
   (stream match 15/15).
7. H01 joint-opening note: Clone+Bear joints were 0/1800 across both binding
   models (singles at theory rate), then hit in recorded extensions for all
   three orderings (15258/16238/16859). Joints are rare (~0.3–0.5%), not
   impossible; no hard exclusion. Catalog seeds stand on fresh-process
   evidence, not on rate arguments.
8. WS214: NOT_APPLICABLE — no `TestPlayer` use anywhere in the WS207 surface
   (test-guarded); the path uses headless `XmageFullGamePlayer` only.

## 5. I01 Aura-controller note (flagged, unmaterialized)

WS90 I01 neutral lists Pacifism (owner P1) under controller P0; Rules
expectation is P1 control (caster). The WS207 predicate follows the WS90
value; no setup-run assembled the Aura, so no conflict materialized. The
successor MUST adjudicate the target-state controller check before scoring
I01 (recorded in SUCCESSOR_SPEC.md). Not an authority change.
