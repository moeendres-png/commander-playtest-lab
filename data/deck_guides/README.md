# Deck guides

One guide per deck the project plays: 183 precon decks (165 real, 9 originals the engine cannot
fully play, 9 synthetic replacement decks) and the two Owner decks (`custom/rogshai`,
`custom/chulane`). Each guide is a pair in `guides/`: `<slug>.json` (parameters, schema in
`FORMAT.md`) and `<slug>.md` (the short plan a person reads). The slug is the `deck_id` with `/`
replaced by `_` (`rogshai` and `chulane` for the two Owner decks).

**Status: hypotheses, not measurements.** Card facts (costs, types, oracle text, colour
identity, land count, curve) come from the printed cards. Everything derived from them (roles,
commander target turn, utility deltas, keep-test windows, threat overrides, packages) is
`MODELED` or `CODE_DERIVED` and carries that label in the file. No pilot reads a guide yet; whether
a guide makes a pilot play better is decided only by paired real-game runs, never by this data.

**Origin.** Generated on 2026-10-24 from the deck lists, a Scryfall card cache and the repository's
own `card_roles()` and `permanent_value()`, then adjusted by hand for the two Owner decks (fields
marked `"handgesetzt": true`). The generator and the card-cache fetcher are not part of the
repository; the output is the source of record. The synthetic replacement decks keep the id the
deck files use (`precon-synthetic/...`).

**Guards.** `tests/unit/test_deck_guides.py` checks that every deck of the pool has exactly one
guide, that commanders and listed cards belong to the deck, that every delta stays inside the
documented bounds and that each JSON has its Markdown partner. When the deck pool changes, the
guides must be regenerated; the test fails until they are.

**Known gaps** (from the generation report, kept so nobody has to rediscover them): there is no
`combo` tag and no proliferate or counters archetype; key cards follow board value, not synergy
(the synergy centre of a deck can be missed); the commander target turn is `mana value` minus a
0 or 1 ramp allowance; the RogShai guide names cards that
`data/decks/rogshai_current.json` does not hold (it follows the Owner's current list), and the
Chulane deck list is not in the repository, so the card checks skip both Owner guides.
