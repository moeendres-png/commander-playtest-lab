# Filter funding, native tap budgets and precon roles — 2026-11-05

## Changes

Automatic mana-source planning now requires funding evidence before selecting a
costed source: the native pool verdict, or an existing completion-plan proof for
hybrid costs. A free source can seed a filter chain; an unfunded filter without
such a source contributes no mana to the supported numeric estimate. The early
pooled-mana route applies the same reservation checks as the ordinary route.
Non-consuming converters retain the ordinary pilot choice and No-Progress guard.

The bridge projects `source_tap_mana_abilities_blocked` for the acting player's
face-up permanents. It calls XMage's `TapSourceCost.canPay`, including as-though
permissions. It does not infer summoning sickness from entry turns or a Haste
string. The fact is absent from opponent and public views. It is independent of
current mana-pool funding, so an unfunded filter remains a possible future source.

All three payment estimates respect an explicit native blocked verdict. The
additional filter-budget reduction uses the existing payment planner as a
strategy hint. Unreadable sources, capped searches, unknown public rules, mana
modifiers and cost reducers preserve the prior estimate. Priority recording and
retry checking use the same full-state estimate. Engine options, numeric domains,
cost adjudication and rules resolution remain authoritative in XMage.

Three public precon staples had missing roles:

| Card | Public precon files | Added role |
|---|---:|---|
| Fact or Fiction | 11 | Selection |
| Windfall | 9 | Draw |
| Overwhelming Stampede | 9 | Combat payoff |

The changes match printed text, with neighboring-text negative controls. They
also exercise the existing priority-impact and instant-timing fields. Counts are
over 173 public precon files, including registered reprint/collector variants.
Missing classification does not itself prove that a card was incorrectly withheld.

## Source lock and validation

The baseline is `252ea5cc44e39c53904266b29cb1dfb0588d8d7a`. Main subsequently
integrated #1121 as `2cb74106`; its tree is identical to the baseline tree.
The engine remains the pin in `config/rules_engines.json`. The compact
[measurement evidence](measurements-2026-11-05/wave4-summary.json) binds the
manifest, final runtime source files, public deck files and both bridge jars by
SHA-256. The measured Python sources and jars were frozen separately before runs.

- Guarded Python suite: 706 passed; one private collection-coverage test deselected.
- Native bridge `mvn verify`: 1,156 tests, zero failures/errors, one existing skip
  (`start2DrawStepObservedWithNoDraw`); 1,155 passed.
- Ruff lint/format and strict mypy passed (349 source files).
- Any-usage ratchet passed; the fixture decreases from 2,135 to 2,134 uses.
- Independent code review found a mana-multiplier shortfall and a proof-coverage
  gap. Both were addressed; the final scoped code review reported no blockers.
  The reviewer did not independently establish a runtime PASS.

The regression controls include sick/ready mana creatures, Haste and native
Thousand-Year Elixir permission, actor/public/opponent/face-down boundaries,
unfunded filter chains, reserved sources, hybrid funding, repeated converters,
Mana Reflection on either player's board, and consistent retry-budget recording.

## Complete-game observations

Ten matched games before and after completed normally. A/B use seeds 1–2; C uses
1–4; D uses 1–2. The C extension and conditional D extension were declared for
card-coverage purposes, without selecting winners or discarding unsuccessful
gameplay outcomes. All compared outcomes are included in the JSON evidence.

| Metric | Before | After |
|---|---:|---:|
| Decisions | 30,706 | 32,240 |
| Priority cast selections, less observed cancellations | 546 | 559 |
| Observed payment cancellations | 31 | 23 |
| Identical semantic transcripts | — | 6 / 10 |

Four game trajectories differ. The cancellation reduction is a local observation,
not an isolated causal estimate or a strength/win-rate claim. Wall and pilot times
are retained per game; concurrent validation load prevents a performance claim.
Twenty-three cancellations remain and need further diagnosis.

| Card | Offered decisions before → after | Adjusted selections | Later priority-stack objects |
|---|---:|---:|---:|
| Fact or Fiction | 55 → 65 | 2 → 3 | 2 → 3 |
| Windfall | 43 → 16 | 3 → 4 | 3 → 4 |
| Overwhelming Stampede | 19 → 22 | 0 → 1 | 0 → 1 |

A stack witness matches a preceding spell selection's source name and controller
to a later priority observation, counting distinct stack object IDs. It supports
that the spell reached the stack; it does not prove resolution. Offer windows are
repeated opportunities, not unique physical cards. In C1, Stampede was withheld on
empty or one-power boards; those windows were not treated as proof of bad play.

Four earlier attempts timed out during database startup with zero recorded
decisions. They are preserved separately, excluded from the comparison, and never
counted as successful games. The local runner then reused the public XMage card
database cache and used a 600-second request timeout. Those settings are
measurement-only; the production timeout was not changed.

## Reproduction

The evidence lists every pod's four distinct public deck snapshots. From a
checkout at the corresponding source lock, reuse the existing runner/report API:

```python
import sys
from pathlib import Path

sys.path.insert(0, "scripts")
import benchmark_xmage_full_games as bench
import pilot_decision_report as report
from commander_lab.engine.rules.full_game import XmageFullGameRunner

# paths: the four public paths for one evidence pod; seed: its recorded seed.
scenario, decks, pilots = bench._setup(tuple(Path(p) for p in paths))
command = bench.bridge_command(jar, ["-Xmx768m", "-XX:+UseSerialGC"])
records = []
runner = XmageFullGameRunner(
    command,
    cwd="engine-bridge/target",
    private_card_repository=True,
    request_timeout_seconds=600.0,
)
with report.recording(records):
    result = runner.run(
        scenario=scenario.model_copy(update={"seed": seed}),
        decks=decks,
        pilots=pilots,
    )
summary = report.summarize(records, 4)
```

Use the corresponding jar, a populated public `db` cache in the working directory,
and a maximum of two workers. The local audit guard rejected private collection
paths before imports, including symlink resolution. Raw recordings and helper
scripts remain in scratch and are not repository artifacts.

## Scope and process deviations

An early delegated test invocation accidentally included the prohibited private
collection-coverage test. Whether any files matched is unknown; no contents were
output. That invocation is excluded from compliant validation evidence. A reviewer
also performed an overbroad filename search that traversed restricted trees; its
filtered output exposed only public Java paths, with no private names or contents.
Both deviations were recorded and subsequent searches used explicit paths; final
Python tests and measured games used the guard and coverage-test exclusion.

These measurements do not renew the historical 36-seed reference, change sealed
records or establish full rules qualification. `UNKNOWN` and `NOT_RUN` are not
promoted to PASS.
