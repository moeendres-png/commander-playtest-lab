# WS232 Rules Authority Audit

## Verdict: PASS (XMage sole authority preserved)

- Rules Core: XMage 1.4.61 / commit
  `db134b9737e951367d65ef5806ad986319cc73ab` / protocol 2.0.0 (predicates
  P-ENGINE-PIN family, 47/47 STATIC_PASS; provider handshake verified in
  every run record).
- All legality (casts, costs, mana, targets, divides, bottoms, mulligans,
  combat, replacements, RNG) originates engine-side. 800+ fresh-process
  games drove the native callbacks; Lab code only routes engine options
  to pilots and validates membership (fail-closed rejections observed
  live: forged/unoffered/illegal selections raise, never coerce).
- Test helpers construct legal initial scenarios only (singleton-legal
  symmetric decks, engine-validated at import: size/singleton/identity
  enforced with fail-closed rejections observed). No legality computed in
  Python; no outcome injected (outcomes observed via public state).
- Spotlight preference (test-only pilot discretion among authorized
  options), mulligan/bottom shaping, land development, tap discipline,
  and resolution-bounded X are pilot-behavior shaping, never legality:
  every selection is re-validated against offered membership by the
  policy layer, which raises on any unoffered id.
- No second legality engine: no Python Magic-rules implementation; no
  pilot/adapter/harness/test-helper fallback legality; no first-option,
  random-option, default yes/no, silent skip, or parent-class fallback in
  any production-reachable path (negative suites green, see VALIDATION).
- RNG: explicit seeds per game; `setRulesSeed` + `setRequireExplicitSeed`
  + `getRulesRandomCalls` bindings captured per run; pilot stochasticity
  derived separately and never fed back as Rules RNG.
- Replay: schema `semantic-replay-tape/1.0.0` unchanged; recorder/consumer
  untouched; numeric vector extension exercised (Arc divide replayed).

## New limitation (not an authority breach)

FINDING_PILOT_BOTTOM_GAP.md: look-then-bottom decisions (Dig) are
unanswerable from the hand domain and fail closed. Fail-closed is the
policy-correct behavior; no authority leaks (nothing fabricated).
Chartered as successor scope, not fixed here (production boundary).
