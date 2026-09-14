# WS207 Successor Specification — phased pilot + setup completion

Status: execution-ready planning. Do NOT execute inside WS207. Each item is a
separately-scoped workstream with its own contract, source lock, and
requalification burden. All seeds below are explicit Rules seeds with
`rules_seed_explicit=true` twin-proven provenance (see SEED_CATALOG.json).

## S-SETUP-1. Setup completion for the 8 UNKNOWN slots (setup-state machine v2)

Retain uniform budgets or pre-register any change; keep behavior cards held.

- A04 (seed 9919 has Serpent + one enchantment in opening): needs Doubling
  Season (5 mana) cast + second enchantment drawn. Options: larger uniform turn
  budget (~turn 6+) and/or green ramp suite in P0's deck (legal 1-ofs).
- B01 (seed 10498): Essence Warden native cast PROVEN (offset 246); needs the
  other three Wardens drawn + stack fully resolved. Needs tutor suite and/or
  longer budget; keep APNAP-ordering wishes for the successor.
- E01 (seed 12463): Propaganda + Bear assembled; needs Grizzly Bears drawn.
  Tutor or draw suite.
- G02/G03: Ghalta (12 mana, no cost reduction in these decks) is unreachable
  ~turn 3. Needs: creature-power cost-reduction suite for Ghalta AND/OR a much
  longer uniform budget (12+ land drops), then G03's native ledger prelude
  (2+ unblocked hits) before the tested hit. Also capture the per-commander
  damage ledger in assertion state (current capture has life only).
- H01-HF (seed 15258): needs P2 to draw + cast Humility (4 mana) after Bear is
  out and Clone held. Longer budget and/or white tutor suite.
- I01 (seed 16025): needs P0 to draw + cast Bear, then P1 Pacifism targeting
  it. MUST FIRST adjudicate the Aura-controller target-state question
  (AUTHORITY_ADJUDICATION.md §5): WS90 says controller P0, Rules says P1.
- J02 (seed 16403): needs Delina (5 mana) + Bear assembled, then the phased
  attack/trigger/d20 sequence (successor pilot).

## S-PILOT-2. Phased behavior pilot (S3 scope, not WS207)

Versioned successor (`ws207-setup-v1` → phased pilot) whose phase transitions
trigger ONLY on public native milestones through the actor's OWN
principal-scoped stream/state: behavior casts after neutral predicates hold;
G02 Murder after Ghalta ETB; G03 tested hit after ledger ≥ 12; J02
attack→target→d20→decline sequencing; H01 ordering-specific scripts. Prove per
transition that trigger information was PILOT_VISIBLE to that actor. Never
privileged assertion state, never cross-principal hidden info, never
requested-result filtering.

## S-MECH-3. Setup dealing upgrades (Coordinator authority required)

Tutor/draw suites (legal singleton 1-ofs), opening-mulligan shaping within
engine-offered options only, and turn-budget policy. Any deck-composition
change needs legality re-proof (import) and catalog amendment. Seed-discovery
ranges/criteria changes must be recorded before setup-runs consume them.

## Explicitly NOT successor work

Behavior credit/qualification scoring, provider ranking, Architecture Freeze,
Full107, production bridge changes (WS213 owns Rules-seed productionization),
engine changes (E02/G04 hooks remain with the engine workstream).
