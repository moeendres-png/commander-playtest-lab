# Commander Playtest Lab

Local, reproducible decision system for Commander deck validation, Structural simulation, pilot/ensemble analysis, paired comparisons, ablation, holdout, sensitivity and constrained optimization.

## Project authority — read these before anything else

This README is an orientation summary, not authority. Where it disagrees with a
governing document, the governing document wins.

| Question | Authoritative source |
|---|---|
| Durable rules every session must follow | [`AGENTS.md`](AGENTS.md) — including the source-truth order, rules authority, evidence semantics, Git/worktree authority, and the fact that filenames containing `CURRENT`/`FINAL`/`LATEST` prove nothing |
| Governing mission and gates | [`docs/PROJECT_MISSION.md`](docs/PROJECT_MISSION.md) — outranks any summary, including the one on this page |
| Current engine pins | [`config/rules_engines.json`](config/rules_engines.json) — the sole machine-readable pin authority. Do not restate pins from prose |
| Current execution authority (who runs what, at which effort) | [`docs/CURRENT_EXECUTION_AUTHORITY.md`](docs/CURRENT_EXECUTION_AUTHORITY.md) with `AGENTS.md` §6–§7 |
| Foundry execution system | [`docs/foundry-execution/README.md`](docs/foundry-execution/README.md) — start a workstream with `.opencode/skills/workstream-bootstrap/SKILL.md` |
| Documentation map | [`docs/README.md`](docs/README.md); code and docs onboarding map: [`docs/MODULE_MAP.md`](docs/MODULE_MAP.md) |
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

Do not treat a commit SHA copied into this README as canonical current software truth. At execution time, resolve the repository default branch and pin the exact commit/tree in the run manifest. Package version alone is not a sufficient software identity.

The current decision architecture includes:

- Optimizer-v2 1E hierarchical gates + Pareto;
- 2F sequential paired precision;
- question-specific mechanics-fidelity routing;
- Structural simulator fidelity corrections;
- abort/censoring fail-closed decision evidence;
- content-addressed current decision/semantic inputs.

The existing Structural simulation's operational decision scope remains **4-player
Commander only**. This implementation boundary does not constrain Commander Simulator
Next's architecture or research scope. Other player counts require their own qualified
runtime and decision evidence; this documentation change does not enable them.

Active own-deck scope must be read from the current project/collection scope and newer direct project truth, not inferred from this README or historical snapshots. Frozen opponent-only decks likewise come from the current opponent/project registries.

No search, confirmatory result, diagnostic, or holdout automatically mutates a canonical/current deck, inventory quantity, physical allocation, purchase state, or opponent observation.

## Optimizer-v2 decision path

The official path is:

```text
manifest -> preflight -> run/search -> mechanics-fidelity routing -> confirm -> diagnose -> holdout
```

The current architecture uses:

- SESOI separated from model precision;
- paired sequential confirmatory looks defined by the current decision contract;
- multiplicity control;
- MCSE and seed-stability gates;
- seat, pilot and opponent robustness within 4P;
- fresh critical diagnostics;
- a single frozen challenger before a fresh single-look sealed holdout.

Historical `effective_resolution` promotion logic is retired and cannot authorize advancement.

### Fidelity-aware search and confirmatory routing

Structural search is deliberately asymmetric by evidence cost:

1. legal candidates may receive the smallest Exploratory Structural screening budget;
2. a candidate whose delta is outside the question-specific Structural decision-safe mechanics contract cannot receive later Structural racing budgets;
3. screening-only / tactical / external-rules candidates do not train adaptive Structural operator or policy rewards;
4. the frontier remains auditable and keeps routed candidates visible;
5. Structural confirmatory uses only a diverse shortlist of decision-safe frontier candidates;
6. a non-decision-safe frontier candidate does not block unrelated decision-safe candidates;
7. if no decision-safe candidate remains, confirmatory fails closed.

The mechanics contract distinguishes:

- `MECHANISTICALLY_SUPPORTED`;
- `APPROXIMATED_DECISION_SAFE`;
- `APPROXIMATED_SCREENING_ONLY`;
- `TACTICAL_REQUIRED`;
- `EXTERNAL_RULES_REQUIRED`;
- `UNSUPPORTED`.

Only the first two categories can support Structural confirmatory decisions. Higher-layer candidates require an actually valid tactical/external evidence path or remain unresolved/fail-closed.

## Evidence boundary

Simulator outputs are `structural_model_estimates`. They are not empirical win rates and are not external-rules-engine evidence.

The Tactical Oracle is a separate bounded abstraction and is not an external rules engine.

XMage evidence may only be called `external_rules_engine` when a real provider run was actually executed and validated for the relevant scenario class.

A known semantic profile is not equivalent to mechanistic support. Mechanics that need exact targets, modes, payment resources, stack sequencing, combat assignment, attachments, trigger copying or other rules-complete state are routed to a higher evidence layer or fail closed.

Structural semantic-model changes invalidate prior confirmatory mechanics evidence with `STALE_MODEL_VERSION`; a different Git commit alone is not treated as a sufficient semantic compatibility claim.

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

## Main implementation files

```text
data/decision/DECISION_CONTRACT_CURRENT.json
src/commander_lab/whole_deck/mechanics_fidelity.py
src/commander_lab/whole_deck/optimizer_search.py
src/commander_lab/engine/structural/fact_fidelity.py
src/commander_lab/engine/structural/simulator_fidelity.py
```

## Setup and validation

Requirements: Python 3.12, and for real games a JDK (CI builds with Temurin 17; 21 also works) and Maven 3.9.

### Python suite (the way CI runs it)

```bash
python -m venv .venv && . .venv/bin/activate
python -m pip install --require-hashes -r requirements/lock.txt
python -m pip install --no-deps --no-build-isolation -e .
ruff check . && ruff format --check . && mypy src/commander_lab
PYTHONHASHSEED=0 pytest -q --ignore=tests/qualification   # ci.yml, about 10 minutes
pytest -q tests/qualification                             # production-qualification.yml
```

CI splits the suite in two: `ci.yml` runs everything except `tests/qualification`, and
`production-qualification.yml` runs `tests/qualification`
(`tests/unit/test_required_test_ownership.py` keeps each file to one owner). A plain
`pytest -q` runs both halves.

Skipping the hash-locked install produces failures that are **environmental, not product
defects**:

- `tests/integration/test_phase5_server.py` and `tests/unit/test_phase5_openai_adapter.py`
  fail to **collect** when `httpx2` and `pytest-asyncio` (dev extras) are absent, and
  `test_phase10_acceptance.py` then reports `failed` instead of `passed_with_limitations`.
- Tests that spawn a child interpreter rely on the `subprocess_env` fixture in
  `tests/conftest.py`, because `pythonpath = ["src"]` applies to the pytest process only.

A full run writes only `.pytest_cache/`, which is gitignored, so running the suite does not
make canonical inputs look stale to `src/commander_lab/tools/service.py`.

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
export COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="java -jar $PWD/engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar full-game"
```

Then compare decks on real four-player games (finished games are reused when the command
is run again with the same `--out`):

```bash
python scripts/run_full_game_deck_comparison.py \
  --baseline data/decks/rogshai_current.json --variant my_variant.json \
  --opponent data/decks/opponents/kaervek/current/deck.json \
  --opponent data/opponents/hosts_of_mordor_precon.json \
  --opponent data/opponents/lorehold_spirit_precon.json \
  --seeds 1-5 --out artifacts/deck-comparison/try
```

A variant that differs from the baseline by a few cards needs no deck file:
`--swap "Sol Ring=>Mind Stone"` plays the baseline with that card exchanged (repeat the
option for more variants, or join several swaps of one variant with `;`). The card keeps
its library slot, so the paired games stay identical until it matters. Commanders cannot
be swapped; a card the baseline does not play is refused.

Runs are reproducible per seed: the same seed, decks, pilot policy, bridge jar and pin
play the same game, and the batch keys each finished record by all of them.

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

Useful project commands include:

```bash
commander-lab validate-local --root .
commander-lab generate-structural-profiles --root .
commander-lab validate-structural --iterations 24 --workers 2 --seed 20260804 --root .
commander-lab validate-pilots --iterations 24 --workers 2 --seed 20260804 --root .
commander-lab probe-rules-engines --root .
python -m commander_lab.optimizer_v2_cli preflight --manifest <manifest> --root .
python -m commander_lab.optimizer_v2_cli fidelity --frontier <frontier> --root .
```

## Optimization rule

Candidate changes remain read-only until explicitly accepted. A baseline or challenger may be evaluated through paired comparison, commander-denial, ablation, holdout, sensitivity, pilot and opponent-ensemble workflows only within the evidence layers that are valid for the mechanics involved and within the current operational 4P scope.
