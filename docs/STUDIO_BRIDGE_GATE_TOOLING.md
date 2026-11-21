# Studio bridge gate: tooling

Two bridge builds are interchangeable for Studio only if, on the same games, the pilots chose
the same things (semantic transcript hash) **and were shown the same things** (frame digest).
The hash alone does not cover the second half. `scripts/benchmark_xmage_full_games.py` records both.

The two last sections of this page, the fixed reference set of the gate and what a result must
always say, were moved here verbatim from the Studio simulator plan (`STUDIO_PLAN_SIMULATOR.md`
at commit `41938a58dc8489aa3121a98bab3c64990ac9a7c3`, lines 58 to 92), which is archived since
the Owner answer 8a of 2026-11-21 (#1667, `docs/OWNER_DECISIONS_STUDIO_20261118.md` section 6).
`AGENTS.md` §10 points here for the reference set and the commands.

## Commands

```bash
# per jar: seeds 1-4 of the real pod; the frame digest is on by default (--no-frame-digest turns it off)
python scripts/benchmark_xmage_full_games.py run --jar OLD.jar --out old.json --seeds 1-4 \
    --workers 2 --games-per-jvm 2 --fast
python scripts/benchmark_xmage_full_games.py run --jar NEW.jar --out new.json --seeds 1-4 \
    --workers 2 --games-per-jvm 2 --fast
# the gate: exactly 4 finished games with frame digests in both, identical hashes AND frames,
# and two different jars (compared by SHA-256, recorded as bridge_jar_sha256 at the top of a report)
python scripts/benchmark_xmage_full_games.py compare old.json new.json \
    --expect-games 4 --require-different-jars
```

`compare` prints `identical K/N` (semantic hashes) and `frames identical K/M` separately; a frame
difference is reported per seed with the lowest seat whose frames differ (`FRAMES DIFFERENT`).
Exit status is 1 on any difference, any game in only one file, a failed game, `--expect-games`
or `--require-different-jars` violations, and (new) when no game is in both files.
`--expect-games` also demands a frame digest in every game, so a report recorded without one
cannot pass the gate. Without the new options the old behaviour is unchanged.

## What the frame digest is

`src/commander_lab/engine/rules/frame_digest.py`. A SHA-256 over every decision request the
pilot policy receives in a game, in order, after a deterministic normalization (canonical JSON,
sorted keys). Per game a row carries `frame_digest`, `frame_digest_by_seat` (the frames each seat
received) and `frames` (their count). It is an observer wrapped around the policy: the pilots get
the request unchanged and play does not change (the semantic hash is the same with and without it).

Normalization, the complete list:

| Rule | Reason |
| --- | --- |
| Dropped: `timeout_millis`, `protocol_version`, `protocol_identity` (top level only) | transport, not observation: a deadline and wire-protocol version strings |
| UUID-shaped text anywhere becomes `id#<n>` by first appearance in the game | JVM object ids differ in every run. The pattern is 8-4-4-4-12 hex groups bounded by non-hex characters (so `<uuid>_<uuid>` keys are caught); it is broader than the `\b` pattern the transcript hash (`_semantic_text`) uses, which is unchanged and does not match a UUID next to `_`. "The same object twice" stays visible |
| Values of `option_id`, `decision_id`, `public_state_reference`, `private_actor_state_reference` become `id#<n>` | the bridge hashes the UUID-bearing views and requests, so these differ in every run |
| Text leaves pass through `XmageFullGameRunner._semantic_text` | the transcript normalization itself: engine short ids (`Name [3a4]`) and `object_id=` markup attributes |
| `pilot_state.commander_status` entries are sorted by their normalized text | the bridge builds the list from a UUID-keyed map, so its order follows the run's UUIDs |

Everything else, including the order of every other list (battlefield, hand, stack, legal
options), life totals and opponents' hand contents, is in the digest.

## Known blind spots

- Reports carry no normalization version. Since #1716 the UUID pattern also catches ids next to
  `_` or the letters g-z (`<uuid>_<uuid>`), which stayed raw before. Do not `compare` a report
  taken before #1716 with one taken after it; take both gate arms with the same tool version. A
  mixed comparison can only produce a false FAIL, never a false EQUAL.

- Text the shared transcript normalization removes is not in the digest: `object_id='…'`
  attributes in prompt markup and bracketed short hex ids (`Name [3a4]`). A difference confined
  to them is invisible to both the hash and the frame digest.
- Values of `option_id`, `decision_id` and the two state references are mapped to placeholders
  only when they are 64-hex hashes (state references with their `public-view:` / `actor-view:`
  prefix); the hashes themselves are not compared across runs.
- `bridge_jar_sha256` is taken after the games have run, so a jar replaced during a run would
  be recorded as the new one.
- `compare` prints both reports' execution settings (workers, `games_per_jvm`, JVM options);
  it does not require them to be equal, because the gate compares an unbatched arm on purpose.

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
