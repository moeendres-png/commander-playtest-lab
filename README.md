# Commander Playtest Lab

Commander Studio: a local application to build Commander decks, play them and simulate them. Games are full rules games on the pinned XMage engine through the Java bridge (`engine-bridge/`), played by the pilots in `src/commander_lab/engine/rules` and `src/commander_lab/agents`. The sealed qualification epoch (`qualification/`, `candidate-qualification/`) is the evidence that engine and bridge are fit for this. `docs/README.md` indexes the documents; what describes removed or finished things is under `docs/archive/`.

## Project authority — read these before anything else

This README is an orientation summary, not authority. Where it disagrees with a
governing document, the governing document wins.

| Question | Authoritative source |
|---|---|
| Durable rules every session must follow | [`AGENTS.md`](AGENTS.md) — including the source-truth order, rules authority, evidence semantics, Git/worktree authority, and the fact that filenames containing `CURRENT`/`FINAL`/`LATEST` prove nothing |
| Permanent player limit | [`docs/OWNER_DECISION_SIX_PLAYER_MAX_20261108.md`](docs/OWNER_DECISION_SIX_PLAYER_MAX_20261108.md): **maximum 6** players in new simulator sessions, default **4**, no 7+ roadmap |
| Playgroup Live Phase-1 audit | [`docs/research/PLAYGROUP_LIVE_PHASE1_ARCHITECTURE_AUDIT_20261108.md`](docs/research/PLAYGROUP_LIVE_PHASE1_ARCHITECTURE_AUDIT_20261108.md) — public code availability, WebGL, APIs, hidden state, rules and licensing |
| Current owner-deck work focus | [`docs/OWNER_DECK_FOCUS_CURRENT.md`](docs/OWNER_DECK_FOCUS_CURRENT.md) — Chulane only, with explicit agent priorities and remaining evidence gaps |
| Governing mission and gates | [`docs/PROJECT_MISSION.md`](docs/PROJECT_MISSION.md) — outranks any summary, including the one on this page |
| Current engine pins | [`config/rules_engines.json`](config/rules_engines.json) — the sole machine-readable pin authority. Do not restate pins from prose |
| Current execution authority (who runs what, at which effort) | [`docs/CURRENT_EXECUTION_AUTHORITY.md`](docs/CURRENT_EXECUTION_AUTHORITY.md) with `AGENTS.md` §6–§7 |
| Documentation map | [`docs/README.md`](docs/README.md); code and docs onboarding map: [`docs/MODULE_MAP.md`](docs/MODULE_MAP.md); deck-variant workflow: [`docs/DECK_VARIANT_WORKFLOW.md`](docs/DECK_VARIANT_WORKFLOW.md) |
| Live PRs, issues and branches | [`docs/REPOSITORY_TRIAGE_INDEX.md`](docs/REPOSITORY_TRIAGE_INDEX.md) |

## Project identity, licensing, and third-party software

Commander Playtest Lab / Commander Simulator Next is an independent, unofficial research and engineering project. It is not maintained by XMage and is not affiliated with or endorsed by Wizards of the Coast.

The Lab's own package metadata currently declares `LicenseRef-Proprietary`. Public repository visibility does not by itself grant a license to reuse the Lab's original code or documentation. That project-level status does not replace or absorb third-party rights: third-party engines, data, rules text, card names, artwork, and other materials remain subject to their respective licenses and rights holders.

The external rules engine is tracked under its own upstream license (Forge was removed on 2026-10-13):

- [XMage](https://github.com/magefree/mage) — MIT-licensed upstream project. The separate [Commander Simulator Next XMage fork](https://github.com/moeendres-png/mage) retains XMage's upstream [`LICENSE.txt`](https://github.com/magefree/mage/blob/master/LICENSE.txt) and copyright/permission notice.

The Lab does not claim legal clearance for all uses of Wizards intellectual property merely by being public or by linking to the [Wizards Fan Content Policy](https://company.wizards.com/en/legal/fancontentpolicy). Magic: The Gathering and related Wizards materials remain property of their respective rights holders. This section records attribution and repository-status boundaries; it is not legal advice or a substitute for a separate legal-clearance decision.

These statements are not a production-provider decision. Architecture Freeze and production-provider selection remain governed by the project's qualification gates.

## Commander Simulator Next: project goal

A practical Commander simulator for real deck-building decisions: it plays real
100-card Commander decks rules-correctly on the pinned XMage engine, so that simulated
games stand in for real games (deck and card choices, matchups, pilot improvement,
deck optimization).

- Rules-correct play is required, but maximal rules correctness is not the top
  doctrine. A gap that would mean chasing defects without end is recorded visibly.
- Card coverage matters: as many effects and cards as possible, including cards the
  base XMage engine does not cover.
- Four players (one own deck, three opponents) is the usual game; other player counts
  are supported where useful.

[`docs/PROJECT_MISSION.md`](docs/PROJECT_MISSION.md) is the governing text; this
summary follows it.

## Runtime truth

Do not treat a commit SHA copied into this README as canonical software truth. At execution time, resolve the repository default branch and pin the exact commit/tree in the run manifest; the engine pin is `config/rules_engines.json`.

The decision scope is the Owner decisions in `docs/OWNER_DECISIONS_STUDIO_20261112.md`: games of up to 6 players, default 4 (one own deck, three opponents). No simulation result automatically mutates a deck, inventory quantity, physical allocation or purchase state.

## Evidence boundary

Results from real games on the pinned XMage engine are evidence about that engine's play, not empirical win rates of real tables. Evidence classes are defined in `AGENTS.md` §4. The removed structural simulator, optimizer and tool service (see `docs/archive/`) are not part of the product and give no evidence.

## Current-source policy

Current decisions should resolve through current, content-addressed sources such as:

```text
data/decks/*current*
data/collections/current/
data/decision/DECISION_CONTRACT_CURRENT.json
data/opponents/
data/opponent_ensembles/
data/cards/
data/sync/current_sources.json
```

Dated `data/canonical_import/...` snapshots are historical/regression provenance, not current deck, inventory or rules truth.

For volatile software identity, use the actual GitHub default-branch commit/tree at execution time. A Drive status summary may be useful provenance but must not override a newer verified GitHub software state.

For deck, physical inventory, allocation and opponent truth, use the current canonical project sources and newer direct project statements according to the project source hierarchy.

## Setup and validation

Requirements: Python 3.12, and for real games a JDK (CI builds with Temurin 17; 21 also works) and Maven 3.9.

### Python suite (the way CI runs it)

```bash
python -m venv .venv && . .venv/bin/activate
python -m pip install --require-hashes -r requirements/lock.txt
python -m pip install --no-deps --no-build-isolation -e .
ruff check . && ruff format --check . && mypy src/commander_lab
PYTHONHASHSEED=0 pytest -q --shards=4 --ignore=tests/qualification   # ci.yml: four processes, about 6 minutes
PYTHONHASHSEED=0 pytest -q --ignore=tests/qualification   # the same tests in one process
pytest -q tests/qualification                             # production-qualification.yml
```

CI splits the suite in two: `ci.yml` runs everything except `tests/qualification`, and
`production-qualification.yml` runs `tests/qualification`
(`tests/unit/test_required_test_ownership.py` keeps each file to one owner). A plain
`pytest -q` runs both halves. `--shards=N` is explained in
`docs/performance/CI_QUALITY_SHARDS_2026-10-21.md`.

Skipping the hash-locked install produces failures that are **environmental, not product
defects**:

- Tests that spawn a child interpreter rely on the `subprocess_env` fixture in
  `tests/conftest.py`, because `pythonpath = ["src"]` applies to the pytest process only.

A full run writes only `.pytest_cache/`, which is gitignored, so running the suite does not
leave the tracked tree dirty.

### Bridge and a real XMage game

The engine is the fork pin named by `primary_engine` in `config/rules_engines.json` (do not
copy the commit from prose). Build its Maven artifacts once, then the bridge:

```bash
PIN=$(python -c "import json;print(json.load(open('config/rules_engines.json'))['primary_engine']['commit'])")
git clone https://github.com/moeendres-png/mage ../xmage && git -C ../xmage checkout "$PIN"
(cd ../xmage && mvn -B -ntp -DskipTests install -am -pl Mage,Mage.Sets,\
Mage.Server.Plugins/Mage.Deck.Constructed,Mage.Server.Plugins/Mage.Game.CommanderFreeForAll,\
Mage.Server.Plugins/Mage.Game.CommanderDuel)
(cd engine-bridge && mvn -B -ntp verify)       # bridge tests + jar, as in CI
export COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="java -XX:+UseSerialGC -Dh2.bindAddress=127.0.0.1 -jar $PWD/engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar full-game"
```

Then compare decks on real four-player games (finished games are reused when the command
is run again with the same `--out`):

```bash
python scripts/run_full_game_deck_comparison.py \
  --baseline data/decks/deckbau/chulane_current.json --variant data/decks/deckbau/chulane_v2.json \
  --opponent data/decks/opponents/kaervek/current/deck.json \
  --opponent data/opponents/hosts_of_mordor_precon.json \
  --opponent data/opponents/lorehold_spirit_precon.json \
  --seeds 1-5 --out artifacts/deckbau/chulane-current-v2
```

A variant that differs from the baseline by a few cards needs no deck file:
`--swap "Sol Ring=>Mind Stone"` plays the baseline with that card exchanged (repeat the
option for more variants, or join several swaps of one variant with `;`). Every other card
keeps its library slot, so the paired games stay identical until a swapped card matters.
Commanders cannot be swapped, and a card the baseline does not play, a card that is
already in the deck (basic lands excepted) or a swap that changes nothing is refused.

Runs are reproducible per seed: the same seed, decks, pilot policy, bridge jar and pin
play the same game, and the batch keys each finished record by all of them. If two games
of one seed still differ, `scripts/determinism_probe.py` names the first request on which
they part ways (`docs/performance/DETERMINISM_PROBE.md`).

The engine shuffles each library in decklist order with the game seed. A variant is
therefore played with its unchanged cards in the baseline's library slots and its added
cards in the slots of the removed ones (the deck itself is unchanged, only the list order
is). Paired games then stay identical until a changed card matters. In one local
measurement (one swapped card, six seeds, not a CI result), two pairs played the exact
same game (equal decision transcript) and the other four stayed identical for 13% to 57%
of their decisions; the same swap listed at the end of the deck changed the opening hand
in every pod. Which added card takes which freed slot depends only on the two card lists
(added cards in name order), not on how the variant file lists them. The report counts the
`identical_pairs`, which are ties and carry no evidence either way, and records the
alignment (`slot_alignment`, with the hash of the list that was actually played). Variant
games started before this alignment have other batch keys and are played again; baseline
games are reused.

The `commander-lab` console script exposes `candidates normalize|validate|prepare-simulation`
and `engine-verify` (the same check as `python -m commander_lab.engine.verify_cli`). The former
validation, profile, probe, MCP and tool-server commands were removed.
