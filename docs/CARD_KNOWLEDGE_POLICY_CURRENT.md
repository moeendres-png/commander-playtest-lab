# MTG Card Knowledge Policy — CURRENT

**Effective:** 2026-08-20  
**Scope:** every currently physically owned card identity  
**Current baseline:** 1,338 physical identities / 1,409 physical lots

## Architecture

The project maintains a persistent Card Knowledge Base instead of fully re-evaluating every card before every optimization run.

### Persistent intrinsic layer

Stored once and updated incrementally:

- project-stable card identity and canonical Oracle name;
- Oracle rules text and hash;
- color identity and Commander legality;
- mana cost / mana value;
- card types / subtypes / faces where known;
- functional mechanics and structural roles;
- mana/ramp semantics;
- draw/selection/card-advantage semantics;
- removal/counter/protection/wipe/graveyard-hate semantics;
- recursion and graveyard use;
- token/Treasure/Clue/Food/artifact material;
- generic commander dependency/reference;
- structural multiplayer semantics;
- setup dependency;
- immediate impact;
- repeatability;
- synergy hooks;
- generic possible package memberships;
- semantic confidence and provenance;
- physical lots, printing references, availability and reservation facts.

No universal numeric card-power score is created.

### Context layer

Recomputed when context changes:

- current commander/deck fit;
- slot competition and replacement opportunity cost;
- package completion/interaction;
- current manabase and curve fit;
- current opponent and matchup relevance;
- commander-denial/rebuild/finish implications;
- Pareto/Whole-Deck comparison results.

## Incremental invalidation rules

Intrinsic card knowledge is rebuilt only when one or more of the following changes:

1. a new physical card identity enters the inventory;
2. Oracle rules/identity changes;
3. Commander legality changes;
4. canonical identity/inventory mapping changes;
5. semantic taxonomy/engine changes materially.

Deck/package/opponent/policy changes invalidate only the contextual evaluation layer unless they also change intrinsic card facts.

## Evidence boundaries

- `FACT` = objective card/rules/identity facts;
- `PHYSICAL_INVENTORY_FACT` = actual physical ownership/quantity/location/printing facts;
- `DERIVED_STRUCTURAL` = semantic roles and structural multiplayer/setup/repeatability interpretation;
- `DECK_CONTEXT_EVALUATION` = deck-specific fit, never universal card quality;
- unknown is never silently converted to false or zero;
- Structural semantics are not full rules-engine equivalence and are not empirical winrates.

## Oracle UUID policy

The current canonical inventory does not contain verified external Scryfall `oracle_id` UUIDs. These are therefore left explicitly unresolved rather than inferred. Until a verified bulk join is performed, `project_stable_card_id + canonical oracle_name + Oracle text hash` is the authoritative local identity triple.

## Deck-search boundary

Full knowledge coverage does not widen deck legality or candidate pools. RogShai search remains Commander-legal and color-identity-compatible with WUR. Off-color cards may be fully understood without becoming RogShai candidates.
