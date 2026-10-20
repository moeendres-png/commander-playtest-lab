# Simplified Card Implementations — Documentation

**Status:** SYNTHETIC (not verified in-game)  
**Date:** 2026-10-19  
**Fork branch:** `perf-avoid-nested-playable-copy`

These ~45 cards were implemented as simplified simulations for the Commander Lab.
They have correct mana cost, type line, power/toughness, and basic keywords.
Complex abilities were omitted (documented per card below).

## Why simplified?

The 195 official Commander precons (2011-2026) contain cards not present in the
XMage 1.4.61 card database. To enable precon deck imports, the missing cards were
implemented with simplified abilities. Full implementations would require significant
engine work for complex mechanics (face-down cards, modal X-spells, text-box exchanges, etc.).

## Card list (omitted abilities)

| Card | Omitted Abilities |
|------|-------------------|
| Aminatou, Veil Piercer | Enchantment-related abilities |
| Cyber Conversion | Face-down Cyberman effect |
| Dack Fayden, Helping Hand | Complex ETB reveal/goad ability |
| Desert Warfare | Complex return-to-battlefield ability |
| Doomsday Confluence | Modal X-spell effects (sacrifice/Dalek-token/discard modes) |
| Exchange of Words | Text-box exchange ability |
| Eye of Duskmantle | Graveyard casting ability |
| Feather, Radiant Arbiter | Copy ability |
| Ichor Elixir | (see source) |
| Immortal Obligation | (see source) |
| Missy | Face-down return ability |
| Nissa, Leyline Tamer | Second landfall ability |
| Omnath, Locus of the Void | (see source) |
| Osgood, Operation Double | Copy and Paradox abilities |
| Otherworldly Escort | Dies/return-as-Spirit and charge-counter abilities |
| Psychic Paper | Name/type-choosing and ward/unblockable effects (basic Equipment with Equip {2} only) |
| River Song's Diary | Imprint and upkeep cast-from-exile effects |
| Space Beleren | (see source) |
| Susan Foreman | (see source) |
| The Eighth Doctor | (see source) |
| ... | (full list in git history) |

## Evidence standard

Per the evidence standard, these are classified as **SYNTHETIC**:
- Import/Parsing proves the card exists in the database
- It does NOT prove the card functions correctly in-game
- The simplified abilities mean the card does NOT behave as the real card

## Future work

1. **In-game smoke tests:** Each simplified card needs a game where it's cast/activated to verify it doesn't crash.
2. **Full implementations:** Complex abilities need proper XMage implementations.
3. **Precon game validation:** WS2 found that precon decks fail with ENGINE_FAILURE during games. Simplified cards are the prime suspects.

## References

- Git history: `git log --grep="simplified" -i` on fork branch `perf-avoid-nested-playable-copy`
- WS2 Handoff: `~/workspace/your_files/WS2-Handoff-2026-10-19.md` (precon ENGINE_FAILURE)
