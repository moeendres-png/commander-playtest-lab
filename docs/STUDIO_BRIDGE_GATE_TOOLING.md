# Studio bridge gate: tooling

Two bridge builds are interchangeable for Studio only if, on the same games, the pilots chose
the same things (semantic transcript hash) **and were shown the same things** (frame digest).
The hash alone does not cover the second half. `scripts/benchmark_xmage_full_games.py` records both.

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
| UUID-shaped text anywhere becomes `id#<n>` by first appearance in the game | JVM object ids differ in every run; the same pattern the transcript hash normalizes. "The same object twice" stays visible |
| Values of `option_id`, `decision_id`, `public_state_reference`, `private_actor_state_reference` become `id#<n>` | the bridge hashes the UUID-bearing views and requests, so these differ in every run |
| Text leaves pass through `XmageFullGameRunner._semantic_text` | the transcript normalization itself: engine short ids (`Name [3a4]`) and `object_id=` markup attributes |
| `pilot_state.commander_status` entries are sorted by their normalized text | the bridge builds the list from a UUID-keyed map, so its order follows the run's UUIDs |

Everything else, including the order of every other list (battlefield, hand, stack, legal
options), life totals and opponents' hand contents, is in the digest.
