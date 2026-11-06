# Optional self-counter growth

The P6b/seed 1 six-player measurement repeatedly answered Yes to optional
Enduring Scalelord triggers in turn 50. One retained observation had a 497/497
source, six controlled Scalelords, an opponent at 48 life, opposing toughness
up to eleven, and 3,696 Scalelord abilities on the stack. Earlier runs were
interrupted by resource guards; their game results remain unknown.

The boolean-action ranking now estimates low marginal value for further pure
self-counter growth on the specifically asked creature when:

- The engine supplies both boolean alternatives and identifies an actor-owned
  triggered ability and its original ID.
- Its HTML-normalized prompt and exported printed facts match the narrow
  repeatable self-counter trigger shape, with another identified copy controlled
  by the actor.
- Current power and remaining toughness exceed a public life/creature-stat
  comparison, with a minimum of forty, when another copy already exceeds that
  comparison in both power and remaining toughness. Without that redundancy the
  source must exceed twice the comparison.
- Visible information is complete for the comparison and no additional counter
  text suggests another payoff. An exact pure stat-counter replacement text is
  handled separately; its increased counters are already reflected in native
  current characteristics.

Only the offered No action receives the existing aligned-action preference.
Both options stay in the pilot ranking; no action, draw, loop ruling or game
result is invented. Small peers may continue to grow, and a smaller requested
source keeps its usual ranking. This is a strategy estimate, not proof that
declining is optimal under every interaction or hidden hand.

The comparison uses observed power/toughness even for printed noncreature cards.
The bridge also supplies ordinary lands with neutral 0/0 and zero damage; those
values add no combat comparison. Missing or invalid relevant values retain the
previous ranking. No animation or combat legality is reconstructed.

The original large-source fixture chose Yes before this ranking change and No
afterwards. Separate negative controls cover the source identity, ownership,
original ability ID, trigger type, prompt, incomplete observations, small bodies,
different peer sizes, face-down cards, additional draw/damage/win payoffs, and an
offer containing only Yes. The observed-stat regression first failed for an
animated 1000/1000 land; a second control exposed neutral native 0/0 fields.
Both controls pass in the final implementation.

The comparison does not chase the arbitrary size of an opposing copy of the
same optional growth engine. Other observed large creatures still raise the
comparison. An opposing copy never counts as a friendly backup.

An initial candidate preferred No only above the larger individual-body margin.
It selected 1,541 No answers but still ended through the engine's offered
infinite-loop draw question with eighteen stack entries. This completed draw is
not evidence that the chain emptied. The final estimate also values an already
large peer, allowing redundant bodies to stop growing earlier. A regression
distinguishes a healthy large peer from one with very little remaining toughness.
The native draw proposal remains a real boolean choice. The pilot can prefer
the offered continuation after it has actually declined known self-growth in
the same game, seat and turn, while the visible stack contains only that known
trigger family. This requires a smaller observed queue or increased public-body
development, capped per body at twice the public life comparison. Every later
refusal requires further progress relative to the last refusal. Growth beyond
the utility cap does not qualify. Unknown observations, additional counter
payoffs, an unchanged queue/development score, or an absent No alternative keep
the previous draw strategy. No draw or winner is supplied by the harness.

Targeted validation: 170 guarded tests including the Any-usage ratchet, strict
mypy over 350 source files, and Ruff lint/format passed. Full-game evidence is
recorded separately on an immutable source snapshot; intermediate source runs
are not credited to the final implementation. The fork, bridge and v14 pin are
unchanged. The broader guarded regression passed 800 tests with the private
collection-coverage test explicitly deselected.

On the final snapshot, P6a/seed 1 completed with 4,244 decisions and the same
semantic hash as its reference. P6b/seed 1 completed with 7,384 decisions and
native winner seat four. It selected 624 No answers to growth and six No answers
to offered draw proposals; two other draw replies agreed, without producing a
draw. Record 6,746 shows a later empty native stack, 2,995 decisions after the
first growth decline. The control had six payment cancellations; the problem
pod had none. Cast counters mean cancellation-adjusted priority selections.
This sample does not establish playing strength or a causal speed gain against
the incomplete original baseline.

Source hashes, deck order, metrics and observations are in
`measurements-2026-11-05/optional-counter-growth-summary.json`. Final Python tests
and game setup used access guards before imports. A separate delegated API
triage violated its path restriction by running a broad filesystem metadata
search while locating a compiler. It was stopped; no private paths or contents
appeared in its output, while traversal of excluded trees remains unknown.
That search is excluded from compliant evidence. No private files or raw traces
are committed.
