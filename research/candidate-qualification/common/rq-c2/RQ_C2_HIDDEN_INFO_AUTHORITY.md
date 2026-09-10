# RQ-C2 Hidden-Information Authority Review

Baseline: CR effective 2026-08-07. Rule: principal-scoped observations
only; no hidden-information leakage in observations, logs, evidence, or
errors. This review states what official Rules/Oracle establish per
scenario; the future candidate provider must enforce the authorized
projection. No information-security rule is invented beyond Magic's
actual visibility requirements.

## General provisions applied

- **701.20a (reveal)**: showing a card to ALL players briefly, for as
  long as needed to complete the relevant effect parts. Reveal is
  PUBLIC, never principal-scoped.
- **701.23a (search)**: the SEARCHER looks at all cards in the zone
  (even hidden); other players do not.
- **701.23e**: found cards are revealed only if instructed.
- **701.22a (scry)**: the scrying player looks; APNAP only for
  simultaneous multi-player scry (701.22c).
- **708.5**: only the controller may look at their face-down permanents;
  708.2/702.37c: public face-down identity is 2/2, no text/name.
- **Library/hand zones are hidden** except as effects expose them; zones
  moved to (graveyard, exile-face-up, stack, battlefield) are public.
- **No memory-wipe rule exists**: knowledge gained while information was
  public remains usable by the player afterward. "Becomes hidden again"
  restricts future inspection, not retained knowledge.

## Per-scenario findings (all 40 checked; only deviations listed in full)

- **F02 Duress — CORRECTION REQUIRED (blocking for hidden-info
  contract)**: RQ-C1 expects "P1 hand revealed TO P0 ONLY" with P2/P3
  observing counts. **Contradicted by 701.20a**: Duress's "reveals
  their hand" shows all three cards to ALL players during resolution.
  Required amendment: hand public to ALL while revealed; post-resolution
  the zone is hidden again BUT all observers (P0/P2/P3) retain usable
  knowledge of the three identities. The chooser mechanics (P0 picks a
  noncreature-nonland; Bear/Forest excluded) are unaffected.
- **F01 Rampant Growth — SUPPORTED**: searcher-only visibility
  (701.23a); found land enters tapped (public); others observe
  counts-only; post-resolution privacy holds (nothing was revealed).
- **C02 Altar's Reap — SUPPORTED**: two drawn cards known only to P0
  (hand is hidden; no reveal instructed).
- **C01 Force of Will — MOOT AS SPECIFIED**: pitch-selection privacy is
  moot because the pitch is uncastable (Island colorless); after the
  C01 fixture amendment, the exiled blue card was known only to P0 until
  exile, then public (701.20a-analogous zone publicity; exile is
  public). Stack spells/targets public to all (601.2a).
- **J03 Hymn — SUPPORTED**: random 2-of-4 selection by Rules-RNG with NO
  reveal of the retained pair; discarded pair public (graveyard);
  retained pair stays private to P1 — including from P0 (P0 never saw
  them). This is the correct contrast case to F02.
- **F03 Willbender — SUPPORTED**: face-down 2/2 public with no text
  (702.37c/708.2); identity knowable only to P0 (708.5); turn-up reveals
  to all (special action is public); trigger + new target public.
- **B02 Flickerwisp — SUPPORTED**: exiled Bear is face-up in exile
  (public to all); no hidden information created.
- **A03/A04/B01/B03/B04/C03/C04/D-series/E-series/G01/G02/G03/G04/G05/
  H01/H02/I01/I02/I03/J01/J02/K01/K02/A02/F04 — SUPPORTED**: RQ-C1
  checkpoints match authority (public stacks/targets/votes/damage;
  private hands; commander-damage ledger public; G03 ledger is public
  game state, not hidden).
- **G04 note**: leaving-player information (who left, what left with
  them) is public game state (800.4); no principal retains private
  rights over departed objects.

## Provider obligation carried forward

The F02 amendment (reveal-to-all + retained-knowledge) must be encoded
in the authorized observation projection before F02 executes; the
current RQ-C1 expectation would otherwise bake hidden-information
leakage-in-reverse (under-sharing to P2/P3 during resolution, then
false amnesia for P0/P2/P3 after) into qualification evidence.
