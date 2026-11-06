# Native optional mana costs in pilot choices

Riku of Two Reflections asks `Create a token that's a copy of that creature?`
without printing its `{G}{U}` cost. The existing optional-cost prompt parser
cannot discover that cost. In public-precon pod `coverage-4p-001`, the first
two sampled Yes replies led immediately to payment cancellation with no
available mana. Another sampled payment ended with green still unpaid.

The bridge now supplies a cost hint through the pinned native
`DoIfCostPaid.getCost()` API. It requires the immediate, nonnested native
payment callback and a single exact-base `DoIfCostPaid` in the source's
current mode. Non-mana costs, variable or unsupported symbols, subclasses,
multiple effects and unrelated callbacks omit the hint. No card-name price
table or reflection is introduced.

The Python pilot reuses its existing visible-mana estimate and prefers the
offered No when the hinted cost falls short. Both Boolean alternatives stay
available. These costs belong to effect resolution: the original spell cost
has already been paid and is not added again. For recognized native hints,
the older prompt-based guard is suppressed to avoid that double counting.
Missing or unsupported hints retain the previous behavior.

## Measured native games

Both candidate games complete under the native engine with seed 1, the same
ordered public 100-card decks and the same public card assets as their
references. Exact inputs and hashes are in the
[measurement artifact](measurements-2026-11-06/native-optional-cost-summary.json).

| Pod | Decisions before → after | Payment cancellations before → after |
| --- | --- | --- |
| `coverage-4p-000`, control | 1,892 → 1,892 | 0 → 0 |
| `coverage-4p-001`, Riku | 6,219 → 2,366 | 13 → 2 |

Riku-attributed cancellations fall from twelve to two. Two actual custom
creature-copy questions carry the native `{G}{U}` hint and choose No while
both Yes and No remain offered. Other native hints include the spell-copy
cost `{U}{R}` and Arahbo's optional `{1}{G}{W}` payment.

The control semantic hash is unchanged. Both references and candidates reach
native winners, with the winner unchanged for each pod. The problem game's
trajectory changes substantially; this does not establish improved playing
strength. Its adjusted priority cast selections change from 96 to 50, or
15.44 to 21.13 per 1,000 decisions. These are report proxies that exclude
observed cancelled attempts, not counts of resolved spells.

Raw wall times are retained in the artifact. Concurrent workloads differ,
so no causal speed improvement is claimed. Two Riku cancellations remain;
the visible-mana estimate retains its existing limitations.

## Validation and source lock

The native positive regression first reached the real payment callback and
errored on the missing hint. The five native behavior tests pass, including
negative controls for nesting, subclasses, multiple effects, non-mana costs,
variable X and unrelated questions. Capture assertions require actual
callbacks; the nested control accepts the outer zero-cost payment before
checking the inner question.

Full `mvn -f engine-bridge/pom.xml verify` succeeds: 1,161 tests, zero failures
or errors, one existing skip. A later fixture-only correction selects answers
uniquely by Boolean value and adds a reversed-option-order control; all six
targeted native tests and the first-option ratchet pass. Production source
and the measured JAR are unchanged, so the full-game evidence remains applicable. Python's isolated regression began with two
failures and eleven passing controls. The final focused run passes 88 tests;
a broader guarded run passes 247, including the Any-usage ratchet. These
suites overlap. Strict mypy passes over 350 source files, and Ruff lint and
format checks pass on explicitly selected public paths. Python test and
game imports use private-path access guards.

An independent read-only review found no P1/P2 issues and verified that the
negative controls reach their intended callbacks. This review is code-derived;
test execution and full games provide their separate evidence. Association
is established on the inspected current-mode native resolution path.
Arbitrary ad hoc wrappers with a different effect instance are not qualified.

The unchanged engine pin is `2ec507b721ac04834eaa4d553b494681c46d996f`.
All 49,798 `mage/*.class` entries in the new JAR have identical content to
the v14 reference JAR. The source files match the measured frozen snapshot.
The new bridge JAR SHA-256 is
`7f8ea3b34ee8cfb8e7aab3a1b407ffb6b7bfef1f7ecb0f227f3632a651104f36`;
runtime source-tree digest is
`8dddeb5ea01f9f7e5ff12e3a4b7b929bac7291c8572f81d055a70dcb1bcbaa7e`.

The Rules Core supplies all legal choices, costs and results. The added
metadata changes pilot preference without becoming an exact mana solver.
Raw traces, JARs and scratch helpers remain local. The ongoing 177-deck
campaign is separate and is not declared complete by these two games.
