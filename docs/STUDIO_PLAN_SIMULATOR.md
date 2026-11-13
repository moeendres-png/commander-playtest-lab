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
| D5 | `pyproject.toml` may change for S3: its two console scripts become unused once the workflows that call them are removed (S3 a and c). The digest in `WS17_SHA256SUMS` is regenerated in the same PR with `scripts/regenerate_hash_manifests.py`; `tests/qualification/test_ws17_qualification.py` verifies it. |
| D6 | The rule "at least 10 seeds for a pilot change" is withdrawn. How many games a statement needs follows from its interval, which every result shows. |

## Where the time of a game goes

From `docs/performance/XMAGE_FULL_GAME_SPEED_2026-10-12.md` and
`XMAGE_EFFICIENCY_OFFENSIVE_2026-10-21.md` (measured then, not re-measured for this plan):

- A game in a fresh JVM costs about 85 CPU-seconds, the same game in a warm JVM about 37.
  Fixed cost per JVM is about 8 seconds.
- Most engine time is whole-game copies that XMage makes to work out playable cards.
- The bridge builds two full state views and two state hashes for every decision
  (`XmageFullGameDecisionController.java`, `bindViews`); a precon game has about 3,200
  decisions. By reading the source (not measured): while it waits for an answer the session
  polls the pending request every millisecond and each poll deep-copies it.
- The Python pilots took about 6 % of the time in the profile of 2026-10-12.
- Studio series today: one game after the other, one Python process and one JVM per game,
  no serial GC, no AppCDS archive.

## Steps

| Step | Content | Gate |
|---|---|---|
| S1 | Studio series play several games per JVM on several workers with the fast JVM flags. Proof: every game of a batch has the same semantic hash as played alone. | Python only |
| S2 | Card outcomes (`studio/card_outcomes.py`) for every seat of every game, not only the Owner's deck; series stop when the interval of the question asked is narrow enough; results on the Tierliste page as their own field next to the counted spread. | Python only |
| S3 | Removal in three PRs: (a) OpenCode and Foundry tooling, its workflows and tests; (b) packages no live path reaches (`whole_deck`, `tools`, optimizer, mulligan lab, RogShai, candidate workflow, old CLIs and others); (c) nine workflows that guard only those. Then `AGENTS.md` and `CLAUDE.md` are shortened to the current state. | Required checks; (b) updates `WS17_SHA256SUMS` |
| S4 | Leaner bridge: one state view per decision instead of two, state hash only where it is used, no deep copy while polling. `NEUTRAL` only if the frames the pilots receive stay identical; a change that removes frame content is `BEHAVIOUR`. Its first PR adds the normalized frame digest to the benchmark and to `compare`. | Studio bridge gate |
| S5 | Engine look-ahead as a measured experiment: the bridge offers a pilot "play this option on a copy of the game" and reports only that seat's principal-scoped view of the copy. Hidden zones of the copy are redetermined from public information and the seat's own knowledge; the copy uses its own recorded RNG, never the real game's; every choice inside the copy is made by the pilots or ends the look-ahead (fail closed, no engine AI). A test proves that no hidden card identity is returned. Default off; becomes default only if a paired series shows a benefit. Declared `BEHAVIOUR`. | Studio bridge gate |
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
python scripts/benchmark_xmage_full_games.py compare before.json after.json --expect-games 36 --require-different-jars
```

`compare` fails on a different semantic hash or status of a game that is in both files. It
does NOT fail on games missing from both, so the PR also shows that the output says
`identical 36/36`: all 36 seeds, pod `real`, every game finished. More conditions of the
gate that the command alone does not enforce:

- BEFORE is built from the merge base of `engine-bridge/`, AFTER from the exact PR head, on
  the same pin; the PR pastes both jar SHA-256 values and they differ.
- The PR changes neither `scripts/benchmark_xmage_full_games.py` nor the transcript-hash
  code in `src/commander_lab/engine/rules/full_game.py`.
- Tooling for the points below (normalized frame digest, `--expect-games`,
  `--require-different-jars`): `docs/STUDIO_BRIDGE_GATE_TOOLING.md`.
- The transcript hash covers decisions and outcomes, not what a pilot was shown. A `NEUTRAL`
  change therefore also compares the frames the pilots received, per decision, after the
  same identifier normalization the transcript hash uses (per-run object ids always
  differ). No tool does that yet: the first `NEUTRAL` PR adds the normalized frame digest to
  the benchmark rows and to `compare`. The hidden-information tests pass.
- One AFTER run with `--games-per-jvm 1` on at least 6 seeds whose hashes equal BEFORE, so
  that batching cannot hide state carried from one game to the next.

## What a result must always say

Seed set, pods, pilot version, engine pin and bridge jar digest; number of games finished,
failed and skipped; the interval; `SIMULATED_RESULT`. A result produced on a bridge changed
under the gate is never presented as covered by the sealed qualification epoch.
