# Issue #1298 Stufe 1: Kopien im Regelkern zuordnen (nur Messen)

- **Datum:** 2026-11-13
- **Art:** Stufe 1 von #1298 — nur Messen/Zuordnen. Kein Produktcode geändert,
  kein Claim, kein Push, kein PR.

## Messstand (Lesson 19)

- **Lab-Stand:** `dc7ccaa11` (Merge PR #1281, 2026-11-13), frischer Worktree
  `wt-1298` auf exakt diesem Commit. Seit dem #1297-Profil ist im gemessenen
  Pfad nichts gemergt worden, was die Engine-Seite ändert (PR #1281 selbst
  brachte nur das Mess-Skript und seinen Bericht; der Studio-Runner ist
  derselbe wie in #1281).
- **Engine-Pin:** `f4d12f6e8066203fba7aa38bd35ea3358117393d` (v15,
  `config/rules_engines.json`), Mage-Worktree `wt-mage-v15` auf exakt diesem
  Commit.
- **Bridge-JAR:** lokal gebaut (Fork-Install der Module Mage Root, Mage
  Framework, Mage Sets, Mage Deck Constructed, Commander Two Player,
  Commander Free For All, `-am -DskipTests install`, BUILD SUCCESS 9:01 min;
  danach `engine-bridge` `mvn package -DskipTests`, BUILD SUCCESS 1:21 min).
  JAR-SHA256:
  `1bb1bdd6f7833ce02781174bd78005f7fdf25959aad0405e1de7d024605136a2`
  (79.715.314 Bytes). Das alte JAR aus `~/workspace/bridge-jars/` (17.10.,
  alter Pin) wurde **nicht** verwendet.
- **Tisch:** echter Vierer-Tisch wie #1279/#1281 — Chulane
  (`data/decks/deckbau/chulane_current.json`) gegen Lorehold Spirit,
  Animated Army, Token Triumph, gefahren über den unveränderten
  `BatchRecordingRunner`-Pfad des Skripts
  `scripts/measure_throughput_steady_state.py` (Treiber:
  `measurements-1298-2026-11-13/run_copy_profile_1298.py`, ändert nur den
  JFR-Anschluss).
- **Hardware/Caveat:** diese VM — 4 geteilte, gedrosselte Kerne
  (1,5 Shared-CPUs), ~7,9 GB RAM. **Nur die Verteilung (Anteile) ist
  belastbar; absolute Zeiten und Durchsätze werden nicht behauptet.**
  (Gesamtwandzeit der 12 Partien hier: 680,9 s — VM-Wert, kein Befund.)

## Methode

1. **Smoke (Pflicht vor der Vollkette):** 1 Partie, Seed 1,
   `--workers 1 --games-per-jvm 1 --fast`. Ergebnis: `finished`,
   3.193 Entscheidungen, semantischer Hash
   `1009e97ca3ea9f10aa9d2f011b78a248029b54553d2cc7d610ac5e162d798b61`
   = exakt die #1281-Referenz. JFR von außen per `jcmd` angehängt
   (`JFR.configure` bestätigte „Stack depth: 512“), `.jfr` per `jfr print`
   lesbar (2.341 ExecutionSamples, 15.139 AllocationSamples).
   Erster Smoke-Versuch war ein Setup-Fehler (`java` nicht auf dem PATH →
   `BRIDGE_START_FAILED`), behoben durch `source ~/workspace/tools/env.sh`;
   keine Vollkette auf dem fehlerhaften Setup gestartet.
2. **Vollkette:** 12 Partien in **einer** JVM
   (`--workers 1 --games-per-jvm 12 --fast`, Seeds 1–12), JFR-Aufzeichnung
   ab Partie 3 bis Partie 12 (Partien 1–2 Aufwärmen, wie #1281):
   `jcmd <pid> JFR.configure stackdepth=512`, dann
   `jcmd <pid> JFR.start settings=profile` (das JDK-17-`profile.jfc`
   aktiviert `jdk.ObjectAllocationSample` mit Throttle 300/s bereits).
   Aufzeichnungsdauer 564 s.
3. **Identität:** Alle 12 Seeds liefern Hash **und** Entscheidungszahl exakt
   wie die #1281-Referenz (`docs/performance/measurements-2026-11-13/raw_games.csv`,
   Lauf `jfr_1w_12g`): 12/12 MATCH. Ausgewertet werden die warmen Partien
   3–12 mit zusammen **45.349 Entscheidungen**.
4. **Auswertung:** `jfr print --json --stack-depth 512`
   (ExecutionSamples) bzw. `--stack-depth 1` (AllocationSamples).
   **Falle, dokumentiert:** `jfr print` kürzt Stacks ohne `--stack-depth`
   auf **5 Frames** — der erste Dump dieser Messung war damit wertlos und
   wurde verworfen und neu erzeugt. Skript:
   `measurements-1298-2026-11-13/analyze_copy_attribution.py`.
5. **Gegenzählung:** Zweite, unabhängig geschriebene Zählung über den
   Text-Parse-Weg (`jfr print` ohne `--json`, Streaming), Skript
   `countercheck_text_parse.py`, Ergebnis `attribution_countercheck.json`.
   **Alle Töpfe exakt gleich** (Gesamt 19.885, Kopien 7.482, Klassen
   1012/5066/118/0/0/1286, Sim-Anker 4.461, Allocation-Events 157.864).
   Einzige Abweichung: Allocation-*Gewichte* weichen um ~0,05 % ab, weil die
   Textausgabe Gewichte gerundet mit Einheiten druckt (JSON-Weg ist exakt).

### Definitionen (vor der Zählung festgelegt)

- Stichprobe = `jdk.ExecutionSample` auf GAME- oder `main`-Thread
  (Filter wie #1281). Blatt = erstes Frame, Wurzel = letztes.
- **Kopier-Stichprobe:** Stack enthält ≥ 1 expliziten Kopier-Einstieg
  (Menge E): Methode `copy` auf einer `mage.*`-Klasse, oder
  `deepCopyObject`/`copyCardsLazily`/`copyGameState` auf `mage.*`, oder
  `GameImpl.createSimulation*`. Breit-Definition (E oder bekannter
  Kopier-Konstruktor wie `Effects.<init>`, `GameState.<init>`, …) ergibt
  7.484 statt 7.482 — die zwei Differenz-Stichproben ändern nichts.
- **Anker** = wurzelnächster E-Frame. **Auslöser-Klasse** = erstes
  zutreffendes Muster in den Frames oberhalb des Ankers, Priorität
  (a) bookmark → (b) Spielbarkeit → (c) Trigger → (e) Watchers →
  (d) sonstige Zustands-Speicherung → (f) sonstige.

## Ergebnis

Stichproben gesamt (GAME + main): **19.885** (GAME 18.010, main 1.875;
im File liegen 19.895, 10 auf sonstigen Threads).
**Kopier-Stichproben: 7.482 = 37,6 % aller Stichproben, 41,5 % der
GAME-Stichproben** — dieselbe Größenordnung wie #1297 (42,1 %) und die
#1281-Nachzählung (43,7 % von GAME). Alle Kopier-Stichproben liegen auf
GAME-Threads; auf `main` kopiert die Bridge JSON, keine Spielzustände.

### Auslöser-Tabelle (DIRECTLY_VERIFIED, beide Zählungen identisch)

| Auslöser | Stichproben | Anteil an Kopien | Anteil an allen (19.885) |
|---|---:|---:|---:|
| **(b) Spielbarkeits-Prüfung** (`getPlayable`/`canPlay`/`createSimulationForPlayableCalc` oberhalb) | **5.066** | **67,7 %** | 25,5 % |
| (f) sonstige (Zerlegung unten) | 1.286 | 17,2 % | 6,5 % |
| **(a) bookmark** (`GameStates.save`/`saveState`/`bookmarkState`) | **1.012** | **13,5 %** | 5,1 % |
| (c) Trigger-Prüfung | 118 | 1,6 % | 0,6 % |
| (d) sonstige Zustands-Speicherung | 0 | 0 % | 0 % |
| (e) Watchers (als Auslöser oberhalb) | 0 | 0 % | 0 % |
| **Summe** | **7.482** | 100 % | 37,6 % |

Anker (wurzelnächster Kopier-Einstieg), Top 5: 
`GameImpl.createSimulationForPlayableCalc` **4.461 (59,6 % aller Kopien)**,
`GameState.copy` 1.012, `AbilitiesImpl.copy` 687,
`TriggeredAbilities.copy` 585, `CardUtil.deepCopyObject` 472.

Zerlegung von (f) nach dem direkten Aufrufer oberhalb des Ankers:
`PermanentCard.copyFromCard` 684 (9,1 % aller Kopien — Fähigkeits-Kopie bei
der Permanent-Erzeugung im Zonenwechsel: `Spell.resolve → moveCards →
ZonesHandler → new PermanentCard → copyFromCard`; das ist **kein**
redundantes Zustandskopieren, sondern einmalige Arbeit je eintretendem
Permanent), Bridge-Guard `XmageFullGamePlayer.manaCostAffordable` 331 +
`crewPayableWithoutSource` 5, `PlayerImpl.getManaAvailable` 229,
`PermanentImpl.addAbility` 20, Rest ≤ 5 je Aufrufer.

Inhaltliche Nachschärfung (aus den Stacks direkt abgelesen, Beleg-Stapel im
Rohverzeichnis nachvollziehbar): Die 331 `manaCostAffordable`-Stichproben
haben als Anker ebenfalls `createSimulationForPlayableCalc` — der
Bridge-Guard löst pro Prioritätsprüfung eine **eigene** volle
Simulations-Kopie aus. Zählt man sie zur Spielbarkeits-Prüfung, trägt der
Spielbarkeits-Komplex **5.402 von 7.482 Kopier-Stichproben = 72,2 %**
(strict nach Definition: 67,7 %). Die direkten Aufrufer des
Simulations-Ankers: `PlayerImpl.getPlayable` 2.199,
`PlayerImpl.getManaAvailable` 1.926, Bridge `manaCostAffordable` 331,
`crewPayableWithoutSource` 5 — pro Entscheidungsfenster wird die
Simulations-Kopie also von bis zu drei Stellen getrennt neu gebaut.
Für (a) gilt: alle 1.012 Stichproben haben Anker `GameState.copy` mit
direktem Aufrufer `GameStates.save` (100 %).

### Widerspruch zu #1297 — offen benannt

#1297 meldete „davon unter `createSimulationForPlayableCalc`: 0,1 %“.
Diese identitäts-verifizierte Messung findet **59,6 % der
Kopier-Stichproben unter genau diesem Frame** (4.461 Stichproben enthalten
den Frame; er ist zugleich der Anker). Eine Tiefen-Erklärung ist für die
eigenen Daten ausgeschlossen: Der Simulations-Anker liegt im Median 18
Frames über dem Blatt (Mittel 20,3; Maximum 60; Stapel-Tiefe gesamt
Mittel 33,0). Plausible Erklärung (MODELED, nicht verifiziert, weil die
#1297-Rohdatei laut #1297 Sitzungs-Scratch und nicht im Repo ist): Das
#1297-Profil lief über den anderen Runner
(`benchmark_xmage_full_games.py`, 6 Partien) und — falls sein
`jfr print`-Abzug ohne `--stack-depth` lief — wäre der Simulations-Frame
bei Median-Distanz 18 im Tiefen-5-Abzug unsichtbar; die sichtbaren 0,1 %
entsprächen dann genau den Stapeln, deren Blatt ≤ 4 Frames unter dem
Simulations-Frame liegt (`GameState.<init> → GameImpl.copy →
createSimulation…`). Die Ursache bleibt **UNKNOWN**; der eigene Befund ist
an Hashes des #1281-Laufs verankert und per Gegenzaehlung doppelt gezählt.

### Kopien je Entscheidung: UNKNOWN

Nicht ehrlich ableitbar, Grund: Der Allocation-Sampler ist gesättigt —
157.864 Events in 564 s ≈ 280/s gegen das `profile`-Throttle von 300/s.
Event-Zähler sind damit **keine** Objekt-Zähler. Für `mage.game.GameState`
liegen nur 7 gesampelte Events vor (Gewicht 87.831.888 Bytes); das Gewicht
ist eine Byte-Schätzung, und ohne die mittlere Objektgröße eines
GameState (tiefer Objektgraph) lässt sich daraus keine Stückzahl rechnen.
Statt einer Schätzung die gesampelten Rohwerte (DIRECTLY_VERIFIED als
Stichproben-Daten, nicht als Zählung): gesamt repräsentiert
346.938.300.400 Bytes Allocation-Gewicht über die 10 warmen Partien
(45.349 Entscheidungen); größte `mage.*`-Klassen: `mage.Mana` 3.141 Events /
12,05 GB, `Modes` 1.859 / 8,31 GB, `ManaCostsImpl` 1.513 / 5,67 GB,
`FirstTargetPointer` 1.464 / 6,08 GB, `Counters` 1.426 / 5,57 GB,
`CardState` 896 / 3,27 GB, `AbilitiesImpl` 710 / 2,78 GB,
`Effects` 520 / 1,75 GB, `GameState` 7 / 87,8 MB, `Watchers` 2 / 10,5 MB.

## Empfehlung für Stufe 2 (was der Befund trägt — und was nicht)

1. **Trägt voll: Stufe-2-Kandidat „Spielbarkeit je Prioritätsfenster einmal
   berechnen und gemeinsam nutzen“** (#1298 Stufe 2, zweiter Kandidat).
   Der Spielbarkeits-Komplex ist mit 67,7 % (streng) bis 72,2 % (mit
   Bridge-Guards) der Kopier-Stichproben der dominante Auslöser; pro
   Fenster bauen `getPlayable`, `getManaAvailable` und der Bridge-Guard
   `manaCostAffordable` getrennte volle Simulations-Kopien
   (`createSimulationForPlayableCalc` = `GameImpl.copy()` mit Lazy-Card-Copy,
   Engine-Code am Pin gelesen, `GameImpl.java:360`, Aufrufer
   `PlayerImpl.java:3626/4366`). Gemeinsame Nutzung einer Simulation je
   Fenster adressiert den größten gemessenen Block. Umsetzung ist
   Bridge-Arbeit → Studio-Tor `NEUTRAL`, Lane Claude (Dirigat #1297).
2. **Trägt teilweise: `GameStates`-Listen-Kandidat** (Stufe 2, erster
   Kandidat). bookmark-Kopien sind real (1.012 Stichproben, 13,5 % der
   Kopien, alle über `GameStates.save`), aber sie sind der zweitgrößte,
   nicht der dominante Block. Das Freigeben der Lesezeichen-Liste senkt
   Speicher/GC — die Kopie selbst fällt beim `save` an und bleibt.
   Die #1298-Vermutung (a) („über 800 Mana-Zahlungen treiben bookmark“)
   wird als Teilursache gestützt, nicht als Hauptursache.
3. **Trägt nicht als eigener Hebel: Watchers.** Als Auslöser oberhalb eines
   Kopier-Ankers: 0 Stichproben. Watchers werden *innerhalb* der
   Zustandskopien mitkopiert (2 Allocation-Events), sind aber kein
   eigenständiger Auslöser — kein separates Watchers-Paket aus Stufe 1
   begründbar. Ebenso (d) sonstige Zustands-Speicherung: 0.
4. **Fork-Stufe 3:** Die Kandidaten „Spielbarkeits-Prüfung ohne Kopie“ und
   „Copy-on-Write unveränderlicher Teile“ zielen auf denselben dominanten
   Block (Simulations-Kopien), sind aber Fork-Arbeit mit Owner-Go und
   Requalifikation; nach dem Dirigat zu #1297 ist die Fork-Stufe bei
   541,2 Partien/h (≥ 500-Regel) derzeit nicht ausgelöst. Stufe 1 ändert
   daran nichts — sie ordnet nur zu. Der Kandidat „bookmarkState für reine
   Mana-Fähigkeiten überspringen“ adressiert höchstens einen Teil der
   13,5 % und ist nach diesem Befund **nicht** der erste Fork-Hebel.

## Evidenzklassen

- Auslöser-Tabelle, Anteile, Anker, Identitätsnachweis, Smoke:
  **DIRECTLY_VERIFIED** (zwei unabhängige Zählungen, exakte Übereinstimmung;
  Hashes gegen #1281-Referenz).
- Engine-Pfad-Beschreibung (`createSimulationForPlayableCalc` = volle
  Spiel-Kopie, Aufrufer): **CODE_DERIVED** (am Pin gelesen).
- Erklärung des #1297-Widerspruchs: **UNKNOWN** (Mechanismus als MODELED
  benannt, Rohdatei von #1297 nicht verfügbar).
- Kopien je Entscheidung: **UNKNOWN** (Begründung oben; keine Schätzung).
- Absolute Zeiten/Durchsatz auf dieser VM: nicht behauptet (Caveat oben).

## Rohdaten

`docs/performance/measurements-1298-2026-11-13/`:
- `full_profile.jfr` — 36.029.515 Bytes, SHA256
  `49045555520505f5e2910ec257beb2bd1e8521ae48a101a6ea95a7c1a90f9274`.
  Speicherform im Repo: gzip + Base64 in Parts `full_profile.jfr.gz.b64.p000`
  bis `.p098` (Roh-Chunks zu 79.998 Bytes); Wiederherstellung per
  `reassemble_jfr.py` mit `MANIFEST.json` ergibt exakt diese SHA256
  (lokal bit-genau verifiziert).
- `smoke_profile.jfr` — 5.804.678 Bytes, SHA256
  `d2cba39db3f08e27c1642a074ef89e002e7189c67a404e66a0f71a376c991ce0`.
  Speicherform im Repo: gzip + Base64 in Parts `smoke_profile.jfr.gz.b64.p000`
  bis `.p014`; Wiederherstellung wie oben, exakt diese SHA256.
- `full_result.json`, `smoke_result.json` — Partien, Hashes, jcmd-Protokoll
- `attribution_primary.json`, `attribution_countercheck.json` — beide
  Zählungen
- `run_copy_profile_1298.py`, `analyze_copy_attribution.py`,
  `countercheck_text_parse.py` — Treiber und beide Auswertungen
- Die `jfr print`-JSON-Abzüge (Execution 1,6 GB, Allocation 0,6 GB) wurden
  als regenerierbare Zwischenprodukte gelöscht; Neuerzeugung:
  `jfr print --events jdk.ExecutionSample --json --stack-depth 512 full_profile.jfr`
  bzw. `jdk.ObjectAllocationSample --json --stack-depth 1`.

## Exakte Kommandos

```bash
source ~/workspace/tools/env.sh
# Fork-Install (in wt-mage-v15 @ f4d12f6e80)
~/workspace/tools/mvn-proxy.sh install -DskipTests \
  -pl Mage,Mage.Sets,Mage.Server.Plugins/Mage.Deck.Constructed,\
Mage.Server.Plugins/Mage.Game.CommanderFreeForAll,\
Mage.Server.Plugins/Mage.Game.CommanderDuel -am
# Bridge-Build (in wt-1298/engine-bridge)
~/workspace/tools/mvn-proxy.sh package -DskipTests
# Smoke und Vollkette (PYTHONPATH auf Worktree-src, Lesson 9)
TMPDIR=~/workspace/tmp/pytest-tmp PYTHONPATH=~/workspace/github/wt-1298/src \
  ~/workspace/venvs/commander-lab/bin/python \
  docs/performance/measurements-1298-2026-11-13/run_copy_profile_1298.py \
  --mode smoke|full \
  --jar engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar \
  --work <workdir> --jfr-out <profile.jfr> --result-out <result.json>
```
