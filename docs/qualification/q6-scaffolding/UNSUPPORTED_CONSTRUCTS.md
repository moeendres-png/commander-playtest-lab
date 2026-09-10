# Unsupported Constructs (Task 2B, explicit registry)

Scaffolding only. No behavior PASS is measured or awarded here. No behavior
credit. No coverage promotion.

Source of truth for tooling: `tools/q6_scaffolding/unsupported_registry.json`
(`q6-unsupported-registry-0.2.0`); sealed copy:
`evidence/unsupported-registry.json`. Patterns are generic grammar
constructs. **No card-name exceptions exist.** The Gisela MeldPair example
remains a systemic unsupported construct (generic meld-pair support was not
implemented).

## Remaining parser-unsupported topkeys (AFTER census, 146 files)

| Construct | Files | Disposition |
| --- | --- | --- |
| `topkey:HandLifeModifier` (UC-TOPKEY-HANDLIFEMODIFIER) | 106 | UNSUPPORTED; Vanguard/avatar starting stats need variant-game setup; runtime qualification required |
| `topkey:Draft` (UC-TOPKEY-DRAFT) | 24 | UNSUPPORTED; draft context does not exist in constructed Commander qualification |
| `topkey:MeldPair` (UC-TOPKEY-MELDPAIR) | 14 | UNSUPPORTED; pair-card setup is bespoke scenario design; Rules adjudication + runtime qualification required |
| `topkey:SETCOLORID` (UC-TOPKEY-SETCOLORID) | 1 | UNSUPPORTED; pre-game deckbuilding color choice (Cryptic Spires) needs human setup |
| `topkey:Lights` (UC-TOPKEY-LIGHTS) | 1 | UNSUPPORTED; Un-set variant mechanic, out of scope |

Fixed during Task 2B (no longer unsupported): `topkey:DBCleanup` (SVar-like
`DB$ Cleanup` record, Spirit of Resilience shape — parsed generically),
`topkey:CopyFaceFrom` (split-face copy marker — face-class record),
`topkey:ODeckHints` (benign deck-hint metadata, same shape as DeckHints).

## Unknown-token tripwire classes (all zero on the census)

UC-CLASS-UNKNOWN-VERB, UC-CLASS-UNKNOWN-TMODE, UC-CLASS-UNKNOWN-STATIC-MODE,
UC-CLASS-UNKNOWN-ABILITY-MODE: never-seen grammar routes to
MANUAL_REVIEW_REQUIRED with the exact token in the reason, ahead of any
Rules adjudication. The curator extends the registry from public
documentation or records the family out of scope.

## Curator-review verbs (known token, always manual review)

`verb_registry.json` MANUAL_REVIEW-flagged verbs (AFTER file counts):
MakeCard 176, BecomeMonarch 60, RingTemptsYou 49, Venture 45, LosesGame 45,
Draft 42, WinsGame 42, TakeInitiative 23, AssembleContraption 22,
OpenAttraction 20, DayTime 14, ControlPlayer 9, ControlSpell 6, UnlockDoor 4,
Subgame 3, BidLife 3, RemoveFromMatch 2, GameDrawn 2, LosePerpetual 2,
AdvanceCrank 1, RestartGame 1, ChooseSector 1. These mechanics need bespoke
scenario design (subgames, player control, game outcomes, variant tracks,
digital-only conjure/perpetual); recognizing the token must not read as
support.

## Ambiguity (11 files, fail-closed)

`duplicate_param` diagnostics (13 occurrences) and missing-record shapes.
Ambiguous inputs route to AMBIGUOUS ahead of every other state; the
diagnostics carry byte spans for curator inspection.

## Automation ceiling (stays unsupported / manual by design)

Full replacement/prevention/layer/copy/control Rules semantics are never
encoded; richer interpretation stops at adjudication routing. Variant-game
directives stay UNSUPPORTED. Commander-damage support: 0 script signals in
the corpus (matches the retained D2 XMage finding); never inferred.
