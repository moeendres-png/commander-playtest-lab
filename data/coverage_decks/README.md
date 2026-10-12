# Coverage decks

Test inputs for real XMage full games. They exist to exercise as many distinct cards as
possible; they are not tuned decks, not own-deck snapshots and carry no deck-strength claim.

`collection/` holds 18 Commander decks built from the owner's card collection
(`data/collections/owner_collection_2026-10-12.txt`, 1,401 oracle names) by
`scripts/build_collection_coverage_decks.py`. Every non-basic card is used by at most one
deck, so the 18 decks together cover 1,254 distinct collection cards (commanders included).
Nine collection cards have no implementation in the pinned XMage card repository and are
not used; `Crusade` is excluded because the XMage Commander validator bans it.

All 18 decks import through the bridge's XMage Commander validator (color identity,
singleton, banned list), which stays the legality oracle at game start.
