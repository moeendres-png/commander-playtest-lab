# Phase 4 Closeout — P1 Bounded Candidate-Domain Correctness

Source lock (execution): worktree HEAD `69ad29e2` on `2231ff4b`
(engine `1.4.61`/`db134b97`, seed 424242).

## Systemic invariant (no second legality engine, no card-name logic)

```text
offered_options ⊆ authoritative_candidate_domain
chosen_option ∈ offered_options
non_candidate_object ∉ offered_options
```

Proven across three decision families with engine-issued identities only:

- **Look domain** (`XmageFullGameCandidateDomainTest.scryDomainConfinementWithDecoy`,
  actual card Serum Visions): engine offers exactly the 2 looked cards;
  both ⊆ engine-direct library UUID universe; hand-card decoy never offered;
  decoy forgery rejected typed (`ILLEGAL_ACTION`) with the decision parked;
  completion only through explicit offered selections.
- **Target domain** (`targetOptionsSubsetOfEngineGameUniverse`): every offered
  Bolt target ∈ engine-direct universe (battlefield permanents + players).
- **Mode domain** (Phase 3): exactly the 2 Oracle modes, routed by exact
  identity; transport rejects un-offered (Phase 3 negative).

Coverage of looked-at/revealed/search/pile/choose-object/replacement/hidden-hand
subsets: the invariant is enforced generically at the transport
(`ILLEGAL_ACTION` on anything un-offered) and proven per family above for
look (scry), target, and mode; pile/search/replacement families need
stack/library dimensions still blocked (Phase 1) and are recorded as such —
no card-specific production logic was added anywhere.

## Actual-card regression

Serum Visions selected over Dig Through Time (documented reason): DTT needs
{7}{U} plus delve fuel, far outside the minimal restoration vehicle; Serum
Visions exercises the identical generic look-domain path
(choose-from-looked-cards through the native bottom-of-library callback
identity) for {U}. Oracle semantics bound at runtime (scry 2 → exactly 2
offered). No card-name-specific production logic exists.

## Impact

New test file only; no production bytes changed → all prior evidence retained.
Ledger `EC-XMAGE-CHOICE-02 → IMPLEMENTED_AND_RUNTIME_VERIFIED`.
