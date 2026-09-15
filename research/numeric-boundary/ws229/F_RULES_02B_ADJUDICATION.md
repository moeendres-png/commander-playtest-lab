# WS229 F-RULES-02b Adjudication (CLOSED by this workstream)

## Structural deviation (WS228, feasibility-preserving, not legality-breaking)

Native multi_amount is ONE joint vector decision (`isGoodValues`); the
bridge sequentialized it into per-leg scalar frames. Each leg additionally
suffered the {min,mid,max} narrowing, and the pilot could not express
joint preferences.

## Disposition

CLOSED by joint restoration (JOINT_MULTI_AMOUNT_IMPLEMENTATION.md): the
pilot-facing shape is one joint bounded integer-vector decision; the
sequentializer is deleted outright (no transport shim retained — a shim
would need cross-frame caching, i.e. reconstructed legality).

## Proof

- Single-frame assertion: the joint live test counts served frames
  (framesAnswered == 1 for a 3-leg distribution).
- Joint semantics: legs + binding total executed live (P-M1), native
  `isGoodValues` gate green.
- Old per-leg tests rewritten to the joint contract (CombatDamageTest);
  full-game test drivers answer joint frames with feasible vectors.
