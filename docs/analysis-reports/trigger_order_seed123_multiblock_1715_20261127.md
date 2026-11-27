# #1715-Nachtrag: Seed-123-Verifikation und gezielte 4P-Mehrfachblock-Messung (`SIMULATED_RESULT`)

> **Einordnung:** `SIMULATED_RESULT` (Gewicht `0`, fließt nie in Tierliste/Einstufung ein), `BRIDGE_AHEAD_OF_QUALIFICATION` (`covered_by_sealed_epoch: false`).  
> **Bezug:** [#1715](https://github.com/moeendres-png/commander-playtest-lab/issues/1715), [#1692](https://github.com/moeendres-png/commander-playtest-lab/issues/1692), [PR #1802](https://github.com/moeendres-png/commander-playtest-lab/pull/1802), [PR #1862](https://github.com/moeendres-png/commander-playtest-lab/pull/1862), [#1167](https://github.com/moeendres-png/commander-playtest-lab/issues/1167).  
> **Umgebung (Owner-PC, Linux):** Engine-Pin `f4d12f6e8066203fba7aa38bd35ea3358117393d` (XMage 1.4.62), Bridge-JAR `$HOME/studio-serien/engine/xmage-engine-bridge.jar` (SHA-256 `b184148260a46865092bb105bf1fd566af1cc9e349c173ebe19c39394dc38d5f`), `-Xms512m -Xmx2g -XX:+UseSerialGC -Dcommanderlab.skipForcedDecisions=true`, `private_card_repository=true`.

---

## 1. Teil 1 — Seed-123-Verifikation auf aktuellem Bridge-JAR (`DIRECTLY_VERIFIED`)

In `docs/analysis-reports/trigger_order_4p_1715_20261127.md` (PR #1862) war Seed `123` (`pod="real"`, `scripts/run_real_4p_full_game_smoke.py`) noch historisch als `FAIL` geführt, obwohl die `Zone.EXILED`-Ursache bereits über [PR #1802](https://github.com/moeendres-png/commander-playtest-lab/pull/1802) (`XmageStableOrder.exiledCardContent`, `#1692`) behoben worden war. Zur sauberen Beleglage wurde Seed `123` auf dem aktuellen Bridge-JAR (`b1841482`) sowohl **prozessübergreifend** (`4× single`, je eigene JVM) als auch **je JVM-Prozess** (`4× batch`, eine JVM mit `-Dcommanderlab.fullGame.gamesPerJvm=4`) neu gemessen:

| Modus | Läufe (`n/N`) | `terminal` | `winner_seats` | `decisions` | `frames` (`skip_forced=False` / `True`) | `semantic_transcript_sha256` | `FrameDigest` (`skip_forced=False`) | `FrameDigest` (`skip_forced=True`) |
|---|---:|---|---:|---:|---:|---|---|---|
| Cross-JVM (`single_1..4`) | `4/4` | `True` (`4/4`) | `[4]` (`4/4`) | `4744` (`4/4`) | `4744` / `3431` (`4/4`) | `b5be21dec8671d6be13b7b8a27bc931681084ea4140a52c4b15504e641a736ae` (`4/4`) | `2c132634ba87feb6b2c9b2313e43dfbfd476cba177f0a633c9a50f9780b54817` (`4/4`) | `65b8be906102f22b0d881ab959da8204b1babf53423468ffbff907d086216a31` (`4/4`) |
| Within-JVM (`batch_1..4`) | `4/4` | `True` (`4/4`) | `[4]` (`4/4`) | `4744` (`4/4`) | `4744` / `3431` (`4/4`) | `b5be21dec8671d6be13b7b8a27bc931681084ea4140a52c4b15504e641a736ae` (`4/4`) | `2c132634ba87feb6b2c9b2313e43dfbfd476cba177f0a633c9a50f9780b54817` (`4/4`) | `65b8be906102f22b0d881ab959da8204b1babf53423468ffbff907d086216a31` (`4/4`) |

- **Ergebnis:** **`8/8` identisch** über beide Modi (`single_1..4` und `batch_1..4`); auch alle 4 `by_seat`-Digests sind `8/8` identisch (`0`: `4878e972...`, `1`: `cc0052bd...`, `2`: `0a05ce38...`, `3`: `c5693a48...`). Laufzeit Batch (`4` Spiele): `188.85 s`.
- **Einordnung:** Der `Zone.EXILED`-Fix aus PR #1802 hält auf dem aktuellen Bridge-JAR (`b1841482`) sowohl prozessübergreifend als auch im 4er-Batch. Die in `#1692` dokumentierten zwei P3-Restpunkte an `XmageStableOrder.java:112` (Short-ID-Tag-Bereinigung auf benannten Exilzonen sowie Testabdeckung des benannten `ExileZone`-Pfads) bleiben davon unberührt offen und wurden hier nicht verändert.

---

## 2. Teil 2 — Gezielte 4P-Mehrfachblock-Gleichstandsmessung (`DIRECTLY_VERIFIED`)

In PR #1862 (`A4`-Zufallstisch) blieben gezielte 4P-Mehrfachblock-Gleichstände (`trigger_order`) noch `UNKNOWN`, da unklar war, ob der Referenztisch überhaupt entsprechende Gleichstandsstellen erzeugte.

### 2.1 Versuchsaufbau (`4P`, 100-Karten-Commander-Decks)

- **Sitz 0 (`multiblock-attacker-gorm-virtus`, `100` Karten):** Commander `Gorm the Great` + `Virtus the Veiled` (erzwingt `>= 2` Blocker), bestückt mit `Thicket Basilisk`, `Engulfing Slagwurm`, `Cockatrice`, `Lowland Basilisk`, `Elven Warhounds`, `Venomous Dragonfly`, `Kaldra Compleat`, `Sword of Kaldra`, `Infiltration Lens`, `Lure`, `Nemesis Mask`, `Taunting Elf`, `Prized Unicorn`, `Noble Quarry`, `Roar of Challenge`, `Shinen of Life's Roar`, `Tempting Licid`, Tutoren und Mana-Ramp.
- **Sitze 1–3 (`multiblock-blocker-rhys-s1..s3`, je `100` Karten):** Commander `Rhys the Redeemed` mit günstigen Kreaturen/Token-Erzeugern ohne Artefakt-/Verzauberungs-Removal, um zuverlässig Mehrfachblocks zu erzeugen.
- **Seed-Sondierung (`seed 1..4`):**
  - `seed=1`: `terminal=True`, `frames=5448`, `trigger_order=38`, **`ties=38`** (z. B. Frame `2485`, `seat=0`: `5×` identisches Label `Thicket Basilisk — Whenever {this} blocks or becomes blocked by a non-Wall creature, destroy that creature at end of combat.` mit **`5×` identischer `option_id` `39060ce88c808f5f4d6b476f4411dc0a496f3f375a8bec7adaa0926096b3a38b`**).
  - `seed=2`: `frames=2439`, `trigger_order=0`, `ties=0`.
  - `seed=3`: `frames=3125`, `trigger_order=19`, `ties=17`.
  - `seed=4`: `frames=2801`, `trigger_order=1`, `ties=1`.

### 2.2 Wiederholungsmessung auf `seed=1` (`N = 10` Cross-JVM + `N = 10` Within-JVM)

| Modus | Läufe (`n/N`) | Eindeutige `FrameDigest` (`skip_forced=False` / `True`) | Eindeutige `semantic_transcript_sha256` | Siegerverteilung | Frame-Anzahlen | Laufzeit |
|---|---:|---:|---:|---|---|---:|
| Cross-JVM (`single_01..10`) | `10/10` | **`10`** / **`10`** (`0` Paare identisch) | `8` | `seat 3`: `6`, `seat 1`: `4` | `4759` (`3×`), `4760` (`3×`), `5448` (`4×`) | `22.42–29.09 s` je Lauf |
| Within-JVM (`batch_01..10`, `gamesPerJvm=10`) | `10/10` | **`10`** / **`10`** (`0` Paare identisch) | `6` | `seat 3`: `5`, `seat 1`: `5` | `4759` (`4×`), `4760` (`1×`), `5448` (`3×`), `5657` (`1×`), `6105` (`1×`) | `190.67 s` gesamt |
| **Gesamt (`single` + `batch`)** | **`20/20`** | **`20/20` verschieden** | **`12/20` eindeutig** | **`seat 3`: `11`, `seat 1`: `9`** | **`4759`..`6105`** | — |

### 2.3 Einzel-Frame-Befunde der Divergenz (`DIRECTLY_VERIFIED`)

1. **Frühe `declare_blocker`-Divergenz vor `trigger_order`:**
   - `seed1_single_01` vs. `seed1_single_02` weicht bereits an Frame **`2475`** (`decision_class=declare_blocker`, `seat=1`) in der Reihenfolge der angebotenen Blocker-Optionen ab (`Centaur Healer blocks Gorm the Great` vs. `Rhys the Redeemed blocks Gorm the Great`).
   - `seed1_batch_01` vs. `seed1_batch_02` weicht analog an Frame **`2476`** (`decision_class=declare_blocker`, `seat=1`) ab (`Wall of Blossoms blocks ...` vs. `Cat Soldier Token blocks ...`).
2. **Identische `option_id` bei Mehrfachblock-`trigger_order`:**
   - Wie in Frame `2485` (`seed=1`) belegt, erhalten alle `5` gleichzeitig ausgelösten `Thicket Basilisk`-Trigger dieselbe `option_id` (`39060ce8...`), was die in `#1715` per Code-Lesung festgestellte `byId`/`stableId`-Kollision im Live-Lauf direkt bestätigt.
3. **Semantischer Hash übersieht Zustandsdivergenz (wie in `#1715` beobachtet):**
   - `seed1_single_03` (`norm_digest=a5e34efd3684...`) und `seed1_single_08` (`norm_digest=5a93b2e15a72...`) besitzen beide `frames=5448` und denselben `semantic_transcript_sha256` (`7fa59e831a2e...`) sowie identische `decision_class`/`seat`/`legal_options`-Labels bis zum Spielende, laufen aber ab Frame **`3141`** (`decision_class=priority`, `seat=0`, `phase=combat`) in `pilot_state` und den Zustandsreferenzen (`actor-view:id#9915` vs. `id#9886`) auseinander. Dasselbe Muster tritt bei `single_05` vs. `single_09` (`semantic=bc3714d61e9e...`, `frames=4759`, verschiedene `norm_digest`s `4ce12680c620...` vs. `fbe7106c687a...`) auf.

---

## 3. Rohlog-Nachweis (außerhalb Repo)

Alle `28` komprimierten Rohlogs (`8×` Seed `123` + `20×` `seed=1` Mehrfachblock), Deck-JSONs (`5×`: `4×` aktives Setup + `1×` vorangehende Sonde) und Zusammenfassungen (`3×`) liegen lokal unter `$HOME/studio-messung/logs_1715_part2/` und sind über `$HOME/studio-messung/logs_1715_part2/sha256sums.txt` (`36` Einträge, SHA-256 `c77edced0f05187dd2ff965a10f79ab1e78d3516a08e37004034b573407b9b3c`) gesichert.
