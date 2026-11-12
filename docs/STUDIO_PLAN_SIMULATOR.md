# Commander Studio: plan for PLAY and SIMULATE (2026-11-12)

Owner decisions of 2026-11-12 (evening) and the plan that follows from them. It replaces no
decision in `docs/OWNER_DECISIONS_STUDIO_20261112.md` except rows A8, S5 and P7, which are
updated there. The BUILD plan stays in `docs/STUDIO_ROADMAP_20261112.md`.

## Decisions

| | Decision |
|---|---|
| D1 | XMage stays the only rules engine. No own engine in another language: it would cover a fraction of the cards for years and be a second rules authority whose games differ from real ones. |
| D2 | Speed comes from removing idle work around the engine, in this order: Studio series use what the repository already has (S1), more data per game (S2), a leaner bridge (S4). |
| D3 | A bridge change for the Studio merges under the Studio bridge gate (`AGENTS.md` §10) instead of a new sealed qualification epoch. Fork pushes and repins still need the Owner's go. |
| D4 | Code that the Studio never reaches and that belongs to removed things is deleted (S3). Git history keeps it. Sealed qualification records are not touched. |
| D5 | `pyproject.toml` may change for S3 (two unused console scripts); its digest in `WS17_SHA256SUMS` is updated in the same PR. |
| D6 | The rule "at least 10 seeds for a pilot change" is withdrawn. How many games a statement needs follows from its interval, which every result shows. |

## Where the time of a game goes

From `docs/performance/XMAGE_FULL_GAME_SPEED_2026-10-12.md` and
`XMAGE_EFFICIENCY_OFFENSIVE_2026-10-21.md` (measured then, not re-measured for this plan):

- A game in a fresh JVM costs about 85 CPU-seconds, the same game in a warm JVM about 37.
  Fixed cost per JVM is about 8 seconds.
- Most engine time is whole-game copies that XMage makes to work out playable cards.
- The bridge builds two full state views and two state hashes for every decision (about
  3,200 per game) and deep-copies the pending request once per millisecond while it waits.
- The Python pilots take about 6 % of the time.
- Studio series today: one game after the other, one Python process and one JVM per game,
  no serial GC, no AppCDS archive.

## Steps

| Step | Content | Gate |
|---|---|---|
| S1 | Studio series play several games per JVM on several workers with the fast JVM flags. Proof: every game of a batch has the same semantic hash as played alone. | Python only |
| S2 | Card outcomes (`studio/card_outcomes.py`) for every seat of every game, not only the Owner's deck; series stop when the interval of the question asked is narrow enough; results on the Tierliste page as their own field next to the counted spread. | Python only |
| S3 | Removal in three PRs: (a) OpenCode and Foundry tooling, its workflows and tests; (b) packages no live path reaches (`whole_deck`, `tools`, optimizer, mulligan lab, RogShai, candidate workflow, old CLIs and others); (c) nine workflows that guard only those. Then `AGENTS.md` and `CLAUDE.md` are shortened to the current state. | Required checks; (b) updates `WS17_SHA256SUMS` |
| S4 | Leaner bridge: one state view per decision instead of two, state hash only where it is used, no deep copy while polling. Declared `NEUTRAL`. | Studio bridge gate |
| S5 | Engine look-ahead as a measured experiment: the bridge offers "play this option on a copy of the game and report the resulting state" to a pilot. Default off. Becomes default only if a paired series shows a benefit. Declared `BEHAVIOUR`. | Studio bridge gate |
| S6 | Human seat: decision time limit configurable (default two minutes), then the play page (issue #1169, requirements in `docs/research/PLAY_HUMAN_SEAT_REQUIREMENTS.md`). | Studio bridge gate |
| S7 | Real-game outcomes: Playgroup data collected from a public card list on the Owner's machine, shown next to the simulated outcomes, never mixed. | Python only |

Not removed in S3, on purpose: `qualification/` and everything the sealed records name by
path (the current-boundary qualification modules, the PB-03 workflow, `tests/qualification`).
They are history that tests still verify; they move only as a whole and only by a separate
decision.

## Reference set for the Studio bridge gate

The set of `docs/performance/XMAGE_EFFICIENCY_OFFENSIVE_2026-10-21.md`, R1: the real
four-player pod of `scripts/run_real_4p_full_game_smoke.py`, seeds 1 to 36.

```bash
python scripts/benchmark_xmage_full_games.py run --jar BEFORE.jar --out before.json --seeds 1-36 --workers 4 --games-per-jvm 9 --fast
python scripts/benchmark_xmage_full_games.py run --jar AFTER.jar  --out after.json  --seeds 1-36 --workers 4 --games-per-jvm 9 --fast
python scripts/benchmark_xmage_full_games.py compare before.json after.json
```

`compare` fails on any different semantic hash, any status change and any missing game. Both
jars are built from the same pin. The PR pastes the compare output and both jar digests.

## What a result must always say

Seed set, pods, pilot version, engine pin and bridge jar digest; number of games finished,
failed and skipped; the interval; `SIMULATED_RESULT`. A result produced on a bridge changed
under the gate is never presented as covered by the sealed qualification epoch.
