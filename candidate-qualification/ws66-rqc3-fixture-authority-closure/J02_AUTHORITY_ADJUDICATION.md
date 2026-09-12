# RQ-C3-J02 Authority Adjudication (WS66, research/authority only)

- Source lock: CPL base `7796619e69b0434cd232de8335ff5cab3c5d08e5`;
  RQ-C3 authority `897d72f0b57bb8febe045870acaa3d2dba4bde56`.
- No engine/provider/harness semantic edits. No behavior reruns. No behavior
  credit from this workstream. Read-only sealed-artifact parsing only.

## 1. The question

Delina, Wild Mage oracle text:

> Whenever Delina attacks, choose target creature you control, then roll a d20.
> 1-14 | Create a tapped and attacking token that's a copy of that creature...
> 15-20 | Create one of those tokens. You may roll again.

The fixture scripts a d20 sample of **17** (15-20 band) plus an explicit
**decline** of the may-roll-again offer, then token exile at end of combat.
Is the semantic obligation the exact value 17, or the band plus the decline?

## 2. Three-layer separation

**Layer 1 -- Rules semantics (band + decline, not exact value).**
What the Comprehensive Rules decide: the 1-14 / 15-20 band boundary controls
whether the may-roll-again offer exists at all; the token is created on any
sample 1-20; the decline is an explicit yes/no decision only offered on
15-20; the token exiles at end of combat either way. Any sample in 15-20 with
a declined offer (17, 18, 20, ...) is Rules-identical: one tapped-attacking
Bear token, no recursion, EOC exile, Delina+Bear survive. The exact value 17
carries zero Rules information beyond band membership. The recursion offer is
the decision-seam payload of this scenario: the 1-14 band never offers it, so
only a 15-20 run exercises the offer/decline mechanics (this is why WS65's
complete 1-14 path earns no credit toward the scripted obligation).

**Layer 2 -- deterministic RNG / replay requirements (exact value lives here).**
`rng_operations` ("replay from recorded seed reproduces 17") and the RNG
journal assertion ("domain 1-20, sampled 17, band 15-20") pin the exact sample
as the recorded-seed concretization: the replay contract is seed -> 17 ->
token sequence, with changed-seed as negative control. Exactness here is a
replay-verification requirement, not a Rules-lawfulness claim. A run sampling
18 with decline would be Rules-correct but would satisfy a different seed
concretization, failing only the scripted-sample assertion (fixture-miss, not
Rules-fail; failure taxonomy must keep these distinct). Supporting observation
(read-only): WS65's Forge d20 is native but unjournaled (frames carry the
fixed effective seed only), so the exact-sample journal entry is additionally
a provider-journaling scope matter, not Rules semantics.

**Layer 3 -- fixture convenience (script choice).**
"Scripted roll 17" is one chosen path; the fixture notes explicitly defer the
1-14 band variant and the accept-recursion variant as "second paths for later
harnesses." Choosing 17 over 18 is arbitrary-as-lawful sampling inside the
band. Nothing in the Rules prefers 17.

## 3. Disposition

**J02_AUTHORITY_DISPOSITION=VALID_AS_WRITTEN**, with the layered reading above
recorded as binding clarification (not a correction).

- Scripting an exact seeded sample with journaled domain/band plus an explicit
  decline is legitimate deterministic test design, not a Rules error: 17 is
  lawful, the band mapping is asserted alongside it, and replay-from-seed is
  properly scoped as a replay requirement.
- No rule is misstated; no assertion is unsatisfiable (contrast B01). The
  fixture's own notes already scope the untested bands as deferred paths, so
  there is no over-claim to repair.
- **J02_CORRECTED_REQUIREMENT=none (clarification only):** the Rules-semantic
  core binding on providers is the 15-20 band + explicit decline + exactly one
  token created then exiled at EOC + Delina/Bear survive; the exact value 17
  binds this scripted test's PASS (recorded-seed sample + journaled
  domain/band entry) as a Layer-2/Layer-3 concretization.

## 4. Impact consequences (no rerun; see WS60_IMPACT.json / WS65_IMPACT.json)

- WS60 J02 PASS (XMAGE twin, scripted 15-20+decline path) stands: no correction
  exists to disturb it; sealed evidence already proves the scripted
  concretization including the decline.
- WS65 J02 UNKNOWN stands with 0 credit: sealed evidence (read-only verified:
  Delina CZ-cast works; attack ->P2; trigger targets Bear-8; token-defender
  P2; token 2/2 combat damage + EOC exile; zero roll-again offer frames;
  Delina+Bear survive; hidden PASS; replay 0 divergences) proves the 1-14 band
  completely as partial behavior, but the scripted 15-20 offer/decline
  mechanics -- the scenario's decision-seam payload -- remain unexercised
  (seed fixed; no conformant steering available). Class FIXTURE_AUTHORITY_GAP
  retained as a fixture-path miss, correctly not a Rules failure.
