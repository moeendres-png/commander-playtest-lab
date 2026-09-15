# WS229 F-RULES-03 Dispositions (all five CLOSED)

Rule: forced moves auto-submit ONLY with no pilot discretion AND a logged
forced-move record. Core-authorized discretionary actions are never
hidden. Prompt-text heuristics are dead.

## 1. Single-offer shortcut (bridge: chooseAbilityForCast, chooseLandOrSpellAbility)

No discretion exists with exactly one lawful ability, so auto-submit is
kept — but now with a `forced_move` transcript record (decision class,
prompt, chosen ability label) via
`XmageFullGameDecisionController.recordForcedMove`, observable in the
session transcript. Previously silent. Proven: `forcedMoveRecordedInTranscript`
+ live 2P/3P smokes green (transcript path exercised).

## 2. Mulligan-cap forced keep (Lab `_decide_mulligan`)

The cap (3 mulligans) overrides pilot discretion, so the forced keep is
now a structured `_LOG` record (seat, count, pilot wanted mulligan).
Behavior unchanged (cap retained as a policy rule), silence removed.
Proven: `test_mulligan_cap_forces_keep_with_record` + live smokes
traverse mulligan decisions.

## 3. Priority mana-action withholding (Lab `_decide_priority`)

Withholding hid discretionary actions: REPAIRED by expansion. Mana
abilities are offered to the pilot as explicit views
(`_priority_mana_action`, metadata `is_mana_ability: True`); the pilot
ranks them against other actions and pass. Only a lone pass (no
discretion) auto-submits, with a forced-move log. Pilot returns are now
membership-checked (previously unchecked). Proven: mana-inclusion tests
+ live smokes traverse priority with the new path (2P: 25 decisions incl
priority; 3P likewise).

## 4. Mana-pool shortcut (Lab `_decide_mana`)

Pool-first routing kept (with the WS215 liveness guard intact), but
auto-submit gated to the no-discretion case: a lone productive pool
candidate is a logged forced move; several candidates (real discretion
over which color to spend) go to the pilot with preference-ordered
views reproducing the old deterministic pick. Proven: single/multi
pool tests + liveness-guard test + live smokes traverse mana_payment.

## 5. London-bottom prompt sniffing (Lab `_decide_targets` + bridge)

Prompt-substring routing (`"bottom" in prompt and "library" in prompt`)
is DELETED. Routing uses the bridge-supplied structured flag
`context.bottom_of_library_selection`, set only inside the native
`putCardsOnBottomOfLibrary` path (proven by pinned 1.4.61 bytecode to
funnel through `choose(Outcome, Cards, TargetCard, Ability, Game)`),
via a thread-local marker cleared in `finally`; the singular overload
delegates virtually to the plural, so one override covers both.
Side effect (intended correction): targeted bottom prompts (e.g. tuck
choices, decision_class `target`) no longer take the bottom-card path;
they rank generically, which matches their strategic content.
Proven: flag-routing tests incl the negative (bottom prompt WITHOUT the
flag takes the generic path).
