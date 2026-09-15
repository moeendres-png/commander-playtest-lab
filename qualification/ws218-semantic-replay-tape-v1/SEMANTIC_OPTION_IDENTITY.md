# WS218 SEMANTIC_OPTION_IDENTITY — `semantic-option-identity-1.0.0`

Implementation: `semantic_replay/fingerprint.py::option_fingerprint`.
Inputs are ONLY authoritative decision data: `option_type`, redacted
`label`, semantic metadata subset, plus observation-joined public
projections for object references (hand/zone occurrence, controller/owner
seat, tapped, power/toughness, damage, counters, face-up ability text).
Raw UUIDs (option/object/source/ability/card/defender/attacker/blocker/
player/game/decision ids, `stableId` hashes thereof) never enter a digest.
Name-only matching is never used alone for object references. Ability
copies join `source_object_id`/`card_id` to stable occurrences, so
identical Plains play-abilities resolve exactly-one via hand occurrence
(smoke step 20 ambiguity repaired systemically, not by first-pick).
Legal sets are multisets (`legal_set_digest` over sorted fingerprints,
counts preserved). Zero native matches → `CHOSEN_OPTION_MISSING`;
>1 → `CHOSEN_OPTION_AMBIGUOUS`; never fuzzy, never first. Duplicate
identical public projections are AMBIGUOUS by design (fail closed).

Engine-neutral: classes are opaque strings; Forge
`TARGET_SELECTION`/`DIVIDED_ALLOCATION`/`NUMBER_CHOICE` bind later without
XMage assumptions. Unit tests pin UUID-insensitivity, target-join vs
name-only, multiset counts, and designed ambiguity.

Machine companion: `SEMANTIC_OPTION_IDENTITY.json`.
