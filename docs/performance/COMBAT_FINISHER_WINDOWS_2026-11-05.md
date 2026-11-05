# Open combat finishing windows

## Problem and change

An offered attack with a 3/3 Claim Jumper against an open opponent at three life lost
to an attack against another opponent at forty life with fourteen or more prior
commander damage. Claim Jumper is not the commander that dealt that damage. The
existing board evaluator identified the open finishing window, but its score was
capped at three when converted to a pilot action. Its uncapped score only broke
ties after the pilot's utility evaluation; commander pressure could win first.

Reuse the existing attack evaluator's estimate as `lethal_window` metadata on the
already offered attack action. The pilot adds eight win-progress points for an
explicit boolean true on a combat target. This is a strategic estimate, not a
claim that damage, elimination, or victory will occur. Blocking, prevention,
responses, and the result remain engine decisions. No new attack options or joint
attack plans are constructed.

Unknown, boolean, zero, and negative defender life do not produce this estimate.
An untapped potential blocker and a nonlethal attack retain their existing
evaluation. Actions outside combat targets do not receive the bonus.

## Deterministic evidence

The counterexample spans three existing pilot strategies, three strength settings,
and prior commander damage of fourteen, eighteen, and twenty: 27 cases. With the
new metadata bonus disabled, all 27 select the other defender. A bonus of three
corrects nine cases; seven and 7.3 correct 26; 7.4 and eight correct all 27. Eight
is the chosen simple coefficient with a small margin, not a claim of optimal
play or a coefficient fitted to full-game winners.

Regression controls cover a blocker, four life, missing life, invalid life values,
crackback danger, an unavailable finishing target, metadata types, and action-kind
scope. Existing commander-pressure and seeded attack-tie tests are retained.

Local checks passed: 748 guarded Python tests with one private coverage test
explicitly deselected, strict mypy over 349 source files, the Any-usage ratchet,
Ruff lint, and formatting. After the final test-only assertion cleanup, the new
regressions and ratchet passed again (44 tests). Formatting is also checked on
this evidence document before staging.

## Source and empirical evidence

The baseline is the runtime source of PR #1122, with the pinned v14 engine and
bridge JAR SHA-256
`5fe48fd25ab055fc12fce99aab807d0d045bc5912dfde626d585ff30dedba788`.
Only `agents/pilots.py`, `full_game_pilot/combat.py`, and
`full_game_pilot_views.py` differ in the candidate runtime. The fork and pin do
not change.

Eight paired games are prescribed before examining candidate results: two
four-player pods and two six-player pods, each at seeds one and two. This sample
contains fifteen distinct public precons and does not cover the full pool.
Both runtime snapshots are immutable. Raw traces remain outside the repository.
Results and source hashes are in
`measurements-2026-11-05/combat-finisher-summary.json`.

All four prescribed four-player pairs completed successfully, with identical
semantic hashes before and after: 11,961 decisions, 208 cancellation-adjusted
priority cast selections, and one payment cancellation in each cohort. This
establishes preservation of these four trajectories; it does not demonstrate
that the rare commander-pressure counterexample occurred in them. The direct
evidence for that preference change is the deterministic regression.

The original baseline process pool terminated abruptly after seven complete
games. The environment reported an OOM kill counter of one, without sufficient
evidence to attribute its time or process. The missing game is retried separately;
the original interruption is retained and is not counted as a successful first
attempt. A memory-based retry was deliberately stopped when the shared cgroup
exceeded five GiB; its unpersisted trace is unknown. A disk-backed retry and the
paired six-player measurements continue separately. Other six-player baselines
completed, but unpaired baselines are not candidate full-game evidence.

Main subsequently advanced through the deckbau CLI work in PR #1123. Its changes
add a readiness command, two scripts, documentation and tests; the measured
pilot files, bridge and pin remain identical. A normal merge imports this base,
with another 15 guarded readiness/deckbau/ratchet tests and strict mypy passing.
The immutable snapshots therefore preserve the relevant game runtime; no new
game result is claimed for the added CLI entrypoints.

A separate deterministic manifest covers all 177 explicitly allowed deck
snapshots in 45 four-player and 30 six-player pods. It is prepared, not yet run;
manifest construction is not successful game coverage.

Cast selections, cancellation-adjusted selections, later engine stack witnesses,
and resolved spells are different measures. Repeated offers are decision windows,
not distinct cards. Matching or divergent game trajectories do not by themselves
prove playing strength or a causal speed improvement.

All local Python validation uses a guard that rejects both lexical and resolved
private collection paths. The private collection-coverage test is explicitly
deselected. Style checks enumerate tracked source and document files while
excluding the forbidden trees; collection or inventory loaders are not used.
