# WS213 SEMANTIC_REPLAY_IMPACT — `SEMANTIC_REPLAY_STATUS = PARTIAL`

Inspected the actual candidate (`XmageFullGameSession`,
`XmageFullGameDecisionController`, payloads). Same-seed twins are NOT
equated with semantic replay.

Present (Rules-RNG attribution):
- Explicit seed + `rulesSeedExplicit` + `requireExplicitSeed` per run
  (`rules_seed_binding` on every payload).
- `getRulesRandomCalls` consumption accounting per run.
- Native decision transcript (`decision_requested`/`decision_accepted` with
  offsets, classes, seats, prompts, option types/labels, selected
  types/labels, and `numeric_choice` incl. nulls) plus `controller_failure`
  events — sufficient to attribute every discretionary input.

Absent (replay/checkpoint contract):
- No checkpoint format (seed + calls + turn/phase + decision offset +
  state digest) and no state restore path (restore would be
  zone/life/ledger injection, forbidden without its own authority).
- No shipped replay consumer (transcript-driven resubmission with semantic
  comparison) and no replay validation gate; twin stream-following is a
  qualification driver, not a production contract.
- `bit_exact_replay_validated` remains false everywhere (honest).

Bounded successor: (1) checkpoint schema + capture point definition;
(2) replay consumer + semantic-compare; (3) CI replay gate
(`replay_match` on catalog seeds); (4) keep the injection ban: checkpoints
are evidence digests plus RNG coordinates, never state writes.

Machine companion: `SEMANTIC_REPLAY_IMPACT.json`.
