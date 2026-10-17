# Card coverage: known, implemented, text-checked

Three levels of card coverage for the precon, opponent and real-deck cards
(basic lands excluded; the Owner's collection is never part of this).

## 1. Known to the engine

Every card name the decks reference exists in the engine's card database.

Command: `python3 scripts/export_xmage_card_facts.py`

## 2. Implemented

The engine has rules text, mana cost, types and P/T for the card
(`data/cards/xmage_card_facts.json`). A card can be implemented but still
say something different from the printed card — that is what level 3 checks.

## 3. Text checked against Oracle

`scripts/card_text_drift_report.py` compares the engine's rules text with
the printed Oracle text (`data/cards/pilot_card_knowledge.json`, Scryfall
source) for every in-scope card and triages the differences.

Command: `PYTHONPATH=src python3 scripts/card_text_drift_report.py --out-dir docs/card_text_drift`

Tiers: **A** = a structural field differs (mana cost, types, P/T, ...);
**B** = numbers or keywords differ; **C** = similarity below 0.8;
**OK** = no finding. `EXPORT_GAP` = the facts export lacks the field
(e.g. null power on a Vehicle).

Triage classes in `docs/card_text_drift/REPORT.md`: `WORDING` (same effect,
different phrasing), `EXPORT_GAP`, `DIFFERENT` (candidate implementation
difference — never a proven engine bug from text alone, each with a proposed
in-game check), `UNSURE`.

## Current figures

From `docs/card_text_drift/report.json` (run 2026-10-17):

- A: 2, B: 85, C: 47, OK: 606, EXPORT_GAP: 7
- Excluded basic lands: 5
- 165 real-deck cards have engine facts but no Oracle entry to compare
  (listed as missing in the report).
