# WS218 TAMPER_MATRIX

19 cases on the 2P tape, each a fresh-process replay that must fail closed
(no partial mutation then PASS). All 19 fail closed with the expected (or
explicitly allowed equivalent) divergence; failure diagnostics carry only
class/seat/revision/calls (leak scan: no card names in any diagnostic).

SOURCE/PROTOCOL→SOURCE_LOCK_MISMATCH; DECK→DOMAIN_LOCK_MISMATCH;
COUNT→MALFORMED_TAPE; SEED/RNG_RESULT→RULES_RNG_RESULT_DRIFT;
ACTOR/CLASS/REVISION/OBSERVATION/LEGAL/OPTION_MISSING/OPTION_AMBIGUOUS/
RNG_CALLS/EVENT/STATE/TERMINAL→exact class; TRUNCATED/EXTRA→EXTRA_DECISION
(truncated prefix leaves native decisions unconsumed — fail closed, never
PASS). Full table: `runs/TAMPER_MATRIX.json` (+ namespace
`TAMPER_MATRIX.json` copy). Mutated inputs are deterministically
reproducible via `ws218_driver._mutate_for_tamper` from the sealed 2P tape
(not retained as bulk copies).

Machine companion: `runs/TAMPER_MATRIX.json` (+ `TAMPER_MATRIX.json` pointer).
