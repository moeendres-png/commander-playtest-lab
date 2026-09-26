# Card Coverage Current — Audit G

Date: 2026-08-09
Baseline package: `1.13.4`
Baseline live `main`: `5cf2089e054bdc032e9041214115094ce8476168`
Evidence type: structural-model evidence; not empirical win rate and not external-rules-engine validation.

## Scope and result

Audit G prioritizes cards by decision relevance rather than raw coverage percentage. The global structural-role library remains 195 profiles; G adds orthogonal mechanic tags to 43 high-impact profiles (99 tag assignments) and adds native high-impact cards directly to opponent fixtures where a complete per-card global profile would add little decision value.

No canonical decklist, inventory quantity, physical allocation, purchase decision, or recommendation was applied.

## Decision-relevant coverage added

### Korvold / RogShai mechanics

The high-impact profiles now distinguish structural mechanics that the older role-only layer conflated, including:

- sacrifice payoff/outlet/cost;
- repeatable token engines;
- land and graveyard recursion;
- rebuild;
- table damage vs Commander-damage support;
- commander-dependent vs commander-independent axes;
- stack interaction;
- finisher compression;
- go-wide and artifact-engine behavior.

Important semantic checks include:

- `Kediss, Emberclaw Familiar`: table damage, not Commander damage;
- `Jeska, Thrice Reborn`: Commander-damage support, not generic table damage;
- `Mirkwood Bats` / `Exsanguinate`: independent compressed table reach;
- `Aftermath Analyst` / `Splendid Reclamation`: land-recursion rebuild;
- relevant counterspells: stack-interaction tags.

### Kaervek

The exact 100-card structural snapshot remains unchanged. G explicitly audits all 13 native nonbasic land entries. Utility now distinguishes:

- `Temple of Malice`: mana source + selection;
- `Barren Moor`: mana source + selection/cycling abstraction;
- `Path of Ancestry`: mana source + selection abstraction;
- `Bojuka Bog`: mana source + graveyard hate.

The current project truth that the physical `Path of Ancestry` slot is open is **not** resolved by G; no substitute was invented and no deck/allocation change was made.

### Opponent native high-impact coverage

The opponent fixture layer now carries named cards for threat selection and engine/wipe recognition while preserving residual role-density completion:

| Opponent | Evidence | Named native high-impact cards added | Residual uncertainty |
|---|---|---:|---|
| Morcant / Elves | observed | 9 | 18 provisional slots + 28 synthetic basics remain; final list incomplete |
| Cosmic Spider-Man | observed | 3 additional natives beyond the commander/hard-known core | 96 slots remain unknown/synthetic |
| Blight Curse | verified official baseline | 8 | local commander choice may vary; official baseline retained |
| Kaervek | verified exact snapshot | exact 100 already available | physical Path slot remains open outside structural list |
| Doom Prevails | verified official baseline | 7 | concrete local upgrades unknown |
| Dance of the Elements | verified official baseline | 8 | no local upgrade set asserted |
| Wakanda Forever | verified official baseline | 10 | no local upgrade set asserted |

These additions target actual decision points: wipe timing, flexible interaction, artifact/enchantment pressure, graveyard interaction, engine-vs-threat choices, and compressed finishes.

## What remains intentionally open

1. Cosmic Spider-Man: 96 non-hard-known slots are still not claimed as verified.
2. Morcant / Elves: the final local list remains incomplete.
3. Doom Prevails: the official precon is baseline; concrete local upgrades remain unknown.
4. Kaervek physical Path-of-Ancestry slot: unresolved physical data point, not a structural-model excuse to invent a replacement.
5. Many low-impact cards remain role-density abstractions rather than bespoke native profiles; this is deliberate until they become decision-relevant.

## Decision-quality consequence

Coverage is considered improved only because controlled pilot scenarios now expose distinctions that the old role-only model missed. The G development corpus moves from 18/24 baseline passes to 24/24 post-change; the untouched holdout moves from 9/12 to 12/12. The result is evidence about structural decision discrimination, not a claim that every Magic card is natively modeled.
