# X and multikicker payment reserves

The fixed-seed public-precon campaign exposed twelve cancelled Comet Storm
payments in `coverage-4p-002`. In the first attempt, records 1090–1095 accepted
five `{1}` multikicker payments and declined the sixth. Record 1096 then chose
X=5 without reserving those five payments. The engine requested twelve mana
(`{R}{R}`, five kickers, X=5), produced eight, and cancelled with four still due.
This is a directly observed payment failure, not an inference from a cast offer.

The existing multikicker cap and X budget are reused. Known X spells reserve
roughly half the visible spare mana for X before accepting additional kickers,
with at least one payment of each X symbol reserved when available. Accepted
multikicker costs are remembered by seat and source, retained after the final
No, and deducted from the subsequent X budget. Repeated ordinals do not add
the same promise twice. A new priority action clears the memory. Native
priority cost facts take precedence over the printed base cost for this
reservation. Non-X and unknown spell costs retain the existing cap behavior.

These are pilot strategy hints. The Rules Core still supplies the legal
boolean alternatives, numeric domain, targets, actual costs and game result.
The scalar mana estimate is conservative and does not prove exact payability.
The numeric domain remains intact even when a pilot chooses above the budget
hint. No Rules Core, bridge or pin change is involved.

## Matched native games

Both games use seed 1, the same ordered public 100-card decks and the unchanged
v14 bridge JAR. The control pod contains Ruthless Regiment, Plunder the Graves,
Subjective Reality and Built from Scratch. The problem pod contains Paradox
Power, Call the Spirits, Heavenly Inferno and Breed Lethality. Exact deck
hashes, source hashes, semantic hashes and archive checksums are in the
[measurement artifact](measurements-2026-11-05/x-multikicker-summary.json).

| Pod | Decisions before → after | Payment cancellations before → after |
| --- | --- | --- |
| Control, `coverage-4p-000` | 1,892 → 1,892 | 0 → 0 |
| Problem, `coverage-4p-002` | 2,537 → 2,142 | 18 → 6 |

All four native games completed. The control semantic hash is unchanged.
Comet Storm cancellations fall from twelve to zero in the problem pod. The
candidate chooses X=3 at record 1093 after reserving its accepted kickers;
the controller’s later native priority observation at record 1108 shows
Comet Storm on the stack after payment. In-flight cast observations are
excluded from this witness. Stack presence
does not establish resolution, and report cast counters count priority
selections after excluding observed payment cancellations.

The source is frozen from parent `51e36a957ee7462727f2a2bc91f6a8fcc1a31628`,
with runtime tree digest
`1084190ad5a84b2fff5f8ffa3d2636a89cd0dffbdf0cdf97a8ca4908b354e9e7`.
The engine pin is `2ec507b721ac04834eaa4d553b494681c46d996f`; JAR SHA-256 is
`5fe48fd25ab055fc12fce99aab807d0d045bc5912dfde626d585ff30dedba788`.
All four changed runtime files match the measured snapshot byte for byte.

## Validation and limits

The initial isolated regression failed twice before implementation: the
fourth kicker was accepted, and the later double-X choice ignored the
commitments. After implementation, 188 focused tests passed. A broader guarded
run passed 800 tests with one private collection-coverage test explicitly
deselected. These suites overlap and must not be added together. Controls
cover source/seat isolation, reset at priority, retained commitments after No,
duplicate ordinals, first-offer refusal, non-X and unknown costs, native base
costs, double-X and the unchanged authoritative numeric domain.

Strict mypy passed over 350 source files. Ruff lint and format checks passed
on the explicitly selected public paths; the Any-usage ratchet passed.
Python tests and game setup used the private-path access guard before imports.
Raw traces and scratch helpers remain local and are not committed.

Whether hypothetical direct `numeric_non_x_mana_value` facts already include
optional payments is unknown; the pinned observed path uses pre-kicker
priority facts. Such an overlap could conservatively lower the strategy hint.
This change does not claim an exact mana solver or eliminate every optional
payment failure. No playing-strength or causal speed claim is made: local
wall times include concurrent work.

The independent 177-deck campaign remains in progress. Its separate
`coverage-4p-005` bridge closure is a failed game with a retained verified
archive, not a successful full game or coverage result.
