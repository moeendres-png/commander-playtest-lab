# DECKBAU_INTERFACE — Deckbau Chat / Commander Playtest Lab

Source: `moeendres-png/commander-playtest-lab`. Rules authority: **pinned XMage**, see `config/rules_engines.json`. New candidate files are separate from all registered reference decks. **No collection files are needed.**

## 1. Candidate storage and format

Put new candidates in **`data/decks/deckbau/`**, e.g. `data/decks/deckbau/chulane_v1.json`. Do not edit `data/decks/manifest.json`, existing precons, opponents, Kaervek, or RogShai for this interface.

The simulator's `RulesDeckInput` **Python model** (not the on-disk JSON format) has fields `deck_id`, `name`, `commander_names`, `mainboard`, optional `sideboard`, `card_printings`, `deck_hash`, `source_path`. `mainboard` contains **98 cards for two commanders** or **99 cards for one commander**, as repeated card names. The validator requires **exactly 100 cards including commander(s)**.

The **on-disk JSON snapshot** read by `load_rules_deck_snapshot` and all game/readiness commands uses `commander` and `cards` instead of directly serializing `RulesDeckInput`:

```json
{
  "deck_id": "deckbau/chulane_v1",
  "name": "Chulane Candidate v1",
  "commander": {
    "commanders": ["Chulane, Teller of Tales"],
    "uses_partner": false,
    "commander_identity_override": null
  },
  "cards": [
    {"oracle_name": "Chulane, Teller of Tales", "quantity": 1, "zone": "commander"},
    {"oracle_name": "Sol Ring", "quantity": 1, "zone": "main"},
    {"oracle_name": "Forest", "quantity": 30, "zone": "main"}
  ]
}
```

**Template only:** replace the example with a complete, legal 100-card list (99 in main + 1 commander). `zone` is `main`, `commander` or `sideboard`; commander-zone rows are illustrative, but all commanders **must** appear in `commander.commanders`. `quantity` expands to that many copies. Partner decks list both commanders and 98 mainboard cards. A normal Commander list has no sideboard. Optional `physical_copy_ids`/`notes` fields are not needed for simulations.

The **text source** accepts one card per line, e.g. `1x Sol Ring` or `1 Sol Ring`. A heading such as `Commander` is **not** part of the importer grammar. Supply commander(s) with `--commander` instead. A text list can include commander rows: the importer removes matches from the mainboard and writes commander entries automatically.

```text
1x Chulane, Teller of Tales
1x Sol Ring
30x Forest
# ...remaining cards...
```

Convert (from repository root):

```bash
python scripts/import_deck.py --name "Chulane Candidate v1" --commander "Chulane, Teller of Tales" --input data/decks/deckbau/chulane_v1.txt --output data/decks/deckbau/chulane_v1.json --format text
```

Two commanders: `--commander "Ishai, Ojutai Dragonspeaker; Rograkh, Son of Rohgahh"`. `import_deck.py` only warns about incorrect counts; the checks below reject invalid 100-card counts. Import is **not** proof of Commander color identity, singleton legality, successful XMage import, or runtime behavior.

### Printed names: split, Adventure, Prepare, double-faced

Use the exact Oracle name from the pinned engine's card facts. For `Wear // Tear`, use the full printed two-part name with spaces around `//` when available; the card-facts resolver also recognizes the **front/left face** `Wear`. For Adventure and Prepare cards, use the primary creature/front name (or the exact `Front // Adventure` / `Front // Prepared Spell` entry if it is recorded in the catalog). Never submit the spell-only back half as a separate physical card. When uncertain, check the exported facts and use the primary/front name; readiness is a catalog check, **not** engine-level name-construction evidence. Do not invent alternate face spellings.

## 2. Deterministic validation

Install package dependencies per `README.md` and run from repository root. The first command is the canonical one-line **catalog and pilot readiness** gate:

```bash
python -m commander_lab.deck_readiness data/decks/deckbau/chulane_v1.json --json
```

Exit 0 = `READY`; exit 1 = one or more `NO_CARD_FACTS`, `KNOWN_MISSING_IN_XMAGE` or `NO_PILOT_KNOWLEDGE`; exit 2 = import/file failure.

For the **full 177-deck registered pool** (173 precons, two opponent precons, Kaervek, RogShai), run `python scripts/deckbau_pool_readiness.py --json`. Exit 0 requires 177/177 READY and zero NO_CARD_FACTS. This reads only registered public deck snapshots and card-facts data. Results list unknown card names and counts. The existing equivalent is `python scripts/deck_readiness.py --deck <path> --json`.

For commander mana-source/castability facts (seeded structural Monte Carlo, **not** an XMage rules adjudication):

```bash
python scripts/mana_castability_report.py --deck data/decks/deckbau/chulane_v1.json --trials 20000 --json
```

Readiness does not validate every spell interaction, mana payment, color-identity legality, or actual castability. **Full-game XMage testing is required** before claiming a deck works in the simulator.

## 3. Engine setup (one-time on the host)

The authoritative source pin is `config/rules_engines.json -> primary_engine.commit`. Use one sibling checkout; the README calls it `../xmage`, whereas a local `../mage` checkout also works if pinned:

```bash
git fetch origin
git status --short --branch
PIN=$(python -c "import json;print(json.load(open('config/rules_engines.json'))['primary_engine']['commit'])")
git -C ../mage rev-parse HEAD
# Only after verifying the checkout has no uncommitted work and the expected pin exists:
git -C ../mage checkout "$PIN"
(cd ../mage && mvn -B -ntp -DskipTests install -am -pl Mage,Mage.Sets,Mage.Server.Plugins/Mage.Deck.Constructed,Mage.Server.Plugins/Mage.Game.CommanderFreeForAll,Mage.Server.Plugins/Mage.Game.CommanderDuel)
(cd engine-bridge && mvn -B -ntp verify)
```

Requirements: Python >=3.12, JDK 17 (or supported 21), Maven 3.9. This builds `engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar`. Never update the engine pin or `main` as part of deck evaluation. Use `../xmage` instead of `../mage` in all commands if that is the checkout you have.

## 4. Standardized 4-player test pods

All pods have the candidate in **seat 1**; opponents' source JSONs are fixed. These are labels for testing, not certified power ratings.

| Pod | Comparison field | Fixed three opponents |
|---|---|---|
| `precon` | Precon-level | Lorehold Spirit (2026), Animated Army (2024), Token Triumph (2022) |
| `mixed` | Mixed | Kaervek, Animated Army, Lorehold Spirit |
| `optimized` | Higher-powered reference | RogShai, Kaervek, The Hosts of Mordor |

**Exactly one full game** for a first technical candidate check:

```bash
python scripts/deckbau_eval.py --deck data/decks/deckbau/chulane_v1.json --pod precon --seeds 1 --out artifacts/deckbau/chulane-precon-smoke.json
```

A deterministic four-game sample (same deck and pod):

```bash
python scripts/deckbau_eval.py --deck data/decks/deckbau/chulane_v1.json --pod mixed --seeds 1-4 --out artifacts/deckbau/chulane-mixed-1-4.json
```

Use `--plan-only` to inspect inputs without starting the JVM. A report path must not already exist (fail closed, no overwriting). The script checks **all four** decks for readiness first, uses **one private XMage JVM per game**, requires the full-game runner to return successfully, and writes `status`, winner seats, rounds, decision telemetry and a candidate-seat summary to JSON.

**Metrics:** `win_rate_completed_games`, completed/failed games, average game rounds, candidate spell casts per own turn (labeled **proxy**, not actual mana efficiency), cancelled mana payments, per-card cast opportunities, and cards repeatedly offered but not cast (`rotting`). Exact card **hand-residence turns** and real **mana spent / available** are **NOT_MEASURED**; the report declares those values missing rather than fabricating them. A small fixed-seat sample is exploratory, not a robust winrate estimate.

For actual **paired comparison** of two completed candidate builds with full seat rotation and confidence intervals, reuse the established CLI:

```bash
export COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="java -XX:+UseSerialGC -jar $PWD/engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar full-game"
python scripts/run_full_game_deck_comparison.py --baseline data/decks/deckbau/chulane_v1.json --variant data/decks/deckbau/chulane_v2.json --opponent data/decks/precons/2026_lorehold_spirit.json --opponent data/decks/precons/2024_animated_army.json --opponent data/decks/precons/2022_token_triumph.json --seeds 1-25 --workers 1 --require-ready --out artifacts/deckbau/chulane-v1-v2
```

The paired-comparison report is `artifacts/deckbau/chulane-v1-v2/COMPARISON_REPORT.json`. Readiness and whole games are **separate gates**. No hidden rules are implemented outside XMage.

## 5. Handoff fields for every new deck

Deliver: the file path, immutable revision identifier (e.g. `chulane_v1`), full commander name(s), 100-card count, readiness JSON, pod and seeds, game report, observed failures, and explicit `NOT_MEASURED` metrics. Never edit reference decks or read `data/collections/**` for this workflow.
