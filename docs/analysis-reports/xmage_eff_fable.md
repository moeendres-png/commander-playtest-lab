# XMage-Effizienz: Fork und Bridge für Headless-Serien und PLAY (Fable-Engine-Architekt, Refs #1558)

Stand 2026-11-19. Nur gelesen, nichts gemessen, nichts gepusht, kein Issue/Kommentar.

**Quellen (Datei:Zeile bezieht sich immer auf diese Stände):**
- CPL `main` 60be9fa8 (flacher Clone, nach dem Bericht gelöscht): `engine-bridge/src/main/java/org/commanderlab/xmage/…` = unten kurz `B/…`.
- Fork am Pin f4d12f6e8066… (lokale Kopie `scratchpad/engine_work/mage`, `git rev-parse HEAD` = Pin; `/home/user/mage` steht auf `master` 16dc17ea, **nicht** am Pin, deshalb nicht benutzt): `Mage/src/main/java/mage/…` = unten kurz `E/…`.
- Upstream magefree/mage 5769a6cb (18.11.2026, flacher Clone ohne Historie).
- Messdaten: `eff_sim_play.md` (Effizienz-Lane, 19.11.), `docs/performance/` (COPY_ATTRIBUTION_1298, THROUGHPUT_STEADY_STATE, XMAGE_EFFICIENCY_OFFENSIVE, XMAGE_FULL_GAME_SPEED), Issues #1264, #1297, #1298, #1584, #1585, #1576 (gelesen über die REST-API).

Evidenzklassen: **MESSUNG** = Zahl aus einem genannten Vorbericht (nicht von mir nachgemessen); **CODE** = am Code gelesen (CODE_DERIVED, keine Laufzeitaussage); **VERMUTUNG** = Schätzung, braucht Messung.

---

## 0. Kurzfassung

1. **Es gibt keinen Server-, Netz-, Log- oder KI-Overhead zu holen.** Die Bridge fährt die Engine wie Upstreams Test-Harness direkt im Prozess (kein `Mage.Server`, keine Session, kein `GameView`, kein `ComputerPlayer`). Die Zeit einer warmen Partie liegt in drei Blöcken: Zustandskopien der Engine für die Spielbarkeits-Prüfung, Sicht-/Optionsbau der Bridge je Entscheidung, übrige Regelarbeit. Über allem liegt das JIT-Aufwärmen je JVM-Leben (64 CPU-s, MESSUNG).
2. **Größter Hebel bleibt die Lebensdauer der JVM, und er kostet keine Zeile Java:** die Bridge erlaubt beliebig viele Partien je JVM (`B/XmageFullGameJsonlBridge.java:26-28,169`), begrenzt wird nur in Python (`src/commander_lab/studio/launch.py:40`, Maximum 24) und durch die Look-Fenster (`paired_comparison.py:797`). Von 22,2 CPU-s je Partie (G=8) auf etwa 15 (JVM lebt die ganze Serie): −30 % CPU, an der CPU-Grenze bis +45 % Partien/h.
3. **Neuer Code-Befund (bisher in keinem Bericht):** die Bridge sortiert Optionen mit `Comparator.comparing(key)` und berechnet den Schlüssel bei **jedem Vergleich für beide Seiten neu**; der Schlüssel ruft die GUI-Funktion `permanent.getRules(game)` (Regeltexte, Hinweise, Scan der Restriktions-Effekte) und kopiert die Battlefield-Liste (`B/XmageStableOrder.java:93-108`, `B/XmageFullGamePlayer.java:837,2362,4161-4166`). Schlüssel einmal je Element berechnen ist per Konstruktion ergebnisgleich (`NEUTRAL`). Gewinn UNKNOWN, VERMUTUNG 2 bis 8 % der warmen JVM-CPU; der geparkte Zweig #1264 hat diese Stelle nicht berührt.
4. **Upstream bietet nichts Schnelleres:** in den heißen Dateien (GameImpl, GameState, GameStates, PlayerImpl, CardUtil, Battlefield, AbilitiesImpl, TriggeredAbilities, Watchers) hat Upstream gegenüber dem Pin keine Performance-Änderung; der Fork ist dort voraus (Lazy-Card-Copy, Lazy-Triggers, Bulk-Kartenscan). Kein Upstream-Commit mit Performance-Bezug gefunden (Baum-Vergleich; Commit-Liste UNKNOWN, weil der Clone flach ist).
5. **Fork-Änderungen lohnen heute nicht allein:** erreichbar wären VERMUTUNG 10 bis 15 % (äußere Spielbarkeits-Kopie rund 11 %, Lesezeichen 5,1 %; MESSUNG #1298), gegen Owner-Go, Repin, Requalifikation, neues Siegel und eine Vorgeschichte von Abweichungen genau an dieser Stelle (13/14, `AddManaChosenColorEffect`). Nur gebündelt mit einem Repin, der ohnehin kommt (Upstream-Merge-Lane).

---

## 1. Wo geht in einer Headless-Partie die Zeit hin?

### 1.1 Gemessene Bilanz (Vorberichte)

| Größe | Wert | Herkunft |
|---|---|---|
| CPU je Partie, JVM warm (Partien 9 bis 16) | 14,3 CPU-s (java 11,3 + python 3,0) | MESSUNG `eff_sim_play.md` §2.2 |
| Aufwärmen je JVM-Leben | 64 java-CPU-s; Modell 14,3 + 63/G | MESSUNG ebd. |
| Anteil Aufwärmen an der CPU | 73 % (G=1), 36 % (G=8), 22 % (G=16) | MESSUNG ebd. |
| Wandzeit einer Serie (W=1, G=8): Warten auf die Bridge 76,5 %, Pilot 8,2 %, Deck-Import 4,6 %, JSON lesen 3,1 %, Aufzeichnen 3,0 % | | MESSUNG ebd. §2.5 |
| Kopier-Stichproben in warmer JVM | 37,6 % aller, 41,5 % der Spiel-Thread-Stichproben | MESSUNG `COPY_ATTRIBUTION_1298` (vor #1316) |
| davon Spielbarkeits-Prüfung / Lesezeichen / Permanent-Erzeugung / Bridge-Wächter / Trigger | 67,7 % / 13,5 % / 9,1 % / 4,5 % / 1,6 % | MESSUNG ebd. |
| nach #1316 (innere Kopie entfernt): CPU −6,3 bis −9,6 %; Rest: äußere Kopie rund 11 %, Lesezeichen 5,1 %, Wächter 1,7 % aller Stichproben | | MESSUNG #1298-Abschlusskommentar |
| Bridge inklusiv (Sichten, Hash, JSON) | 22 % (#1297) bis 37,1 % (Nachzählung #1281, Spanne 32,8 bis 41,6 %); `bindViews` 21,3 %, JSONL-Haupt-Thread 10,4 % | MESSUNG, zwei Attributionen |
| „schlanke Bridge“ (Hash gestreamt, öffentliche Sicht teilweise abgeleitet, Monitor statt Abfrage, JSONL gestreamt) | 318,1 gegen 320,2 CPU-s: **kein Gewinn** | MESSUNG #1264 |
| Allokation | 347 GB über 10 warme Partien (rund 35 GB je Partie) | MESSUNG `COPY_ATTRIBUTION_1298` (Stichproben-Gewichte) |

**Offener Widerspruch:** Die Bridge hat 22 bis 37 % der Stichproben, aber das Entfernen von Hash-Kopie, zweiter Sicht (teilweise), Abfrage-Kopie und JSON-Zwischenobjekt brachte 0 %. Was im Bridge-Topf wirklich Zeit kostet, ist damit **UNKNOWN**; der Befund 1.3 (b) unten ist ein Kandidat für die Erklärung.

### 1.2 Engine, mit Datei:Zeile (CODE)

- **Zustandskopie.** `GameImpl(GameImpl)` kopiert Karten (lazy nur im Spielbarkeits-Pfad, `E/game/GameImpl.java:228-233,468-477`), LKI-Karten, `state.copy()` (`:244`). `GameState(GameState)` kopiert Stack, Exil, Battlefield, alle Effekte, Trigger (lazy nur im Spielbarkeits-Pfad, `E/game/GameState.java:172-179`), Delayed, Combat, Watchers, CardState, Attribute (`:150-195`). Kein einzelner Hotspot: Battlefield 31 %, Trigger 27 %, Modes/Effects 35 %, Watchers 7 %, ContinuousEffects 7 % (inklusiv, MESSUNG Effizienz-Offensive §7, vor Lazy-Triggers).
- **Wer kopiert.** `PlayerImpl.getPlayable` (`E/players/PlayerImpl.java:4366`) und `getManaAvailable` (`:3626`) rufen je `createSimulationForPlayableCalc` (`E/game/GameImpl.java:360-374`); Lesezeichen: `bookmarkState` → `saveState(true)` → `GameStates.save` = volle `GameState.copy()` (`E/game/GameImpl.java:984-990,1128-1138`, `E/game/GameStates.java:22-23`), ausgelöst je Prioritätsschleife (`GameImpl.java:1997-1999`), je Cast (`PlayerImpl.java:1370`), je Mana-Fähigkeit (`:1571-1572`), je Fähigkeit (`:1595`), je Trigger (`:1763`). `saveState(false)` ist ohne `saveGame` ein No-op (`GameImpl.java:985-988`); Turn-Rollback ist in der Bridge aus (`B/XmageFullGameSession.java:211-213`).
- **KI-Simulation:** `createSimulationForAI` (`GameImpl.java:352-357`) wird nur von `ComputerPlayer6`/MCTS aufgerufen (`Mage.Server.Plugins/Mage.Player.AI.MAD/…/ComputerPlayer6.java:410`). Die Bridge hängt nicht von den AI-Modulen ab (`engine-bridge/pom.xml`: nur `mage`, `mage-deck-constructed`, zwei Commander-Spieltypen, gson) und `XmageFullGamePlayer extends PlayerImpl` (`B/XmageFullGamePlayer.java:83`). **`ComputerPlayer`-/`SimulatedPlayer2`-Anteil = 0.** Die Spieler-Kopie der Bridge ist schlank (`:357-361`, nur `super(player)` und eine Referenz).
- **Layer-Neuberechnung:** `GameImpl.applyEffects` (`:2260`) → `ContinuousEffects.apply` (`E/abilities/effects/ContinuousEffects.java:1082ff.`, entfernt inaktive Effekte und wendet alle Layer neu an), aufgerufen vor jeder Priorität und nach jeder Aktion (`GameImpl.java:1985,2006,2027`). Anteil nicht separat gemessen (steckt in „übrige Regelarbeit“ rund 30 bis 36 %): **UNKNOWN**.
- **Watcher:** `Watcher.copy()` ist reine Reflection je Watcher je Zustandskopie (`getDeclaredConstructors`, zweimal `getDeclaredFields`, `setAccessible`, `newInstance`, `E/watchers/Watcher.java:81-123`), ohne Cache. Als *Auslöser* 0 Stichproben, als Teil der Kopie 7 % (MESSUNG oben).
- **Logging/Event-Bus:** `informPlayers` ruft einen Datensammler (aus) und `tableEventSource.fireTableEvent` (`GameImpl.java:3534-3543`); in Simulationen wird übersprungen. Die Bridge hängt einen einzigen Listener an, der nur `ERROR` liest (`B/XmageFullGameSession.java:214-227`), und liefert keine log4j-Konfiguration aus (kein `src/main/resources`). Kein `GameLog`/`ChatMessage`-Pfad, weil kein Server läuft. Log-Text wird trotzdem gebaut (String-Verkettung in `PlayerImpl`); Anteil nicht gemessen, VERMUTUNG < 1 %.
- **Start:** `CardScanner.scan` läuft in jeder JVM (`B/XmageDeckImporter.java:420`); `Sets.getInstance()` lädt dabei alle Set-Klassen, deren Klassen-Literale alle Kartenklassen laden (37.730 geladene Klassen, 98 % aus dem AppCDS-Archiv, MESSUNG Effizienz-Offensive §6). Erster `import_deck` 4,96 s; AppCDS −2,6 s Wand und rund −6,5 CPU-s je JVM-Start (MESSUNG `eff_sim_play.md`). H2 läuft als Datei mit `AUTO_SERVER=TRUE` (`E/cards/repository/DatabaseUtils.java:28-29`), deshalb je Worker eine private Kopie (261 MB). **Klassenladen ist der kleine Teil des Aufwärmens (rund 10 % von 64 CPU-s), der Rest ist JIT**; wie viel davon Übersetzer-CPU und wie viel langsamer Code ist: **UNKNOWN** (mit `-XX:+CITime` oder JFR `jdk.Compilation` in einem Lauf klärbar).

### 1.3 Bridge je Entscheidung, mit Datei:Zeile (CODE)

a) **Kopien der Engine, die die Bridge auslöst.** Prioritäts-Frame: ein `getPlayable` je Spieler mit wiederverwendetem Mana (`B/XmageFullGamePlayer.java:525-539,833`), die innere Kopie überspringt ein wortgleicher Spiegel von `PlayerImpl.getManaAvailable` (`:383-393,402-407,421-522`). Dazu je `{T}`-Mana-Fähigkeit mit eigenen Manakosten eine **eigene** Simulations-Kopie (`manaCostAffordable`, `:4139-4158`) und je Crew-Fähigkeit eine (`:4093-4113`). **Mana-Frame** (27 % aller Frames: 3.687 von 13.556, MESSUNG): wieder ein volles `getPlayable` über alle Zonen, nur um die Mana-Fähigkeiten herauszufiltern, **zusätzlich** zur Engine-eigenen Aufzählung `getUseableManaAbilities` je Permanent (`:2349-2363`; Engine-Funktion `E/players/PlayerImpl.java:1916-1927`, kopiert nichts).

b) **Sortierschlüssel werden je Vergleich neu berechnet (neu).** `playable.sort(Comparator.comparing(c -> abilitySortKey(c, game)))` (`:837`, ebenso `:606,736,2362,2410`). `Comparator.comparing` ruft den Schlüssel-Extraktor bei jedem Vergleich für beide Elemente; bei n Optionen sind das rund 2·n·log2(n) Schlüssel. Ein Schlüssel = `objectKey` (vier `String.format` je Permanent, `B/XmageStableOrder.java:43-79,112-114`) + `ability.getRule()` + `contentKey` → `permanentContent` (`:93-108`): `permanent.getRules(game)` (Regeltexte aller Fähigkeiten plus dynamische Hinweise plus Scan aller Restriktions- und Requirement-Effekte, `E/game/permanent/PermanentImpl.java:315-390`), Regex je Regelzeile, zwei Sortierungen, zwei weitere `String.format` und `new ArrayList<>(getAllPermanents()).indexOf(...)`. `XmageStableOrder.objects` (`:37-41`) rechnet `contentKey` nur bei Gleichstand, `abilitySortKey` immer. Passt zum Profil: `java.util.regex` 274 von 7.230 Stichproben als Blatt-Paket (MESSUNG `THROUGHPUT_STEADY_STATE` §5), Zuordnung zu dieser Stelle aber **nicht belegt**.

c) **Sichten und Prüfsummen.** `bindViews` baut Akteur-Sicht und öffentliche Sicht (die intern noch eine Akteur-Sicht baut, `B/XmageFullGameStateRedactor.java:394,558-561`) und zwei Hashes mit `deepCopy` + `toString` + SHA-256 (`B/XmageFullGameDecisionController.java:498-510`, `B/XmageAuditEventLog.java:100-104`); die Sicht erzeugt je Permanent die Regeltexte aller Fähigkeiten (`Redactor:688-692`). Erzwungene KI-Pässe werden **vor** dem Sichtbau abgefangen (`Controller:268-271,345ff.`), aber **nach** der Optionsberechnung: die Engine-Arbeit eines erzwungenen Passes bleibt.

d) **Übergabe.** Engine-Thread und Haupt-Thread tauschen über einen Monitor (`Controller:283-303,701-717`). Zusätzlich fragt `awaitDecisionAdvance` im 1-ms-Takt ab und kopiert dabei die ganze Anfrage (`B/XmageFullGameSession.java:1115-1146`, `Controller:697-699`); die Anfrage wird beim Bau dreimal tief kopiert (`Controller:264,267,273`). Das ist Wartezeit ohne CPU und überlappt mit der Rechenzeit der Engine; #1264 hat den Ersatz gemessen: kein CPU-Gewinn. Latenz-Untergrenze für PLAY ≤ 1 ms je Entscheidung, bei 10 bis 20 ms je Antwort (MESSUNG) bedeutungslos.

e) **Threads und Fristen.** Ein Spiel-Thread „GAME full-game …“ (`Session:504-508`; der Name erfüllt `ThreadUtils.isRunGameThread`, `E/util/ThreadUtils.java:20,99-111`), ein Haupt-Thread (JSONL), dazu JIT-Threads und der H2-Auto-Server. Fristen: `SETTLE_TIMEOUT` 75 s (`Session:1153`), Entscheidungs-Fortschritt 20 s (`:541`), Entscheidungs-Frist per Property (`Controller:77,102`). Eine warme JVM belegt 1,03 Kerne, in den ersten 8 Partien 1,45 (MESSUNG). Der Hänger #1584 (Endlosschleife in `Combat.selectBlockers`, weil die Bridge die Blocker des falschen Spielers anbietet und sich als Mensch ausgibt, so dass die Grenze `aiTries > 20` nicht greift, `E/game/combat/Combat.java:705-709`) verbrennt je Partie 113 bis 126 CPU-s; Behebung ist geclaimt (#1584, `BEHAVIOUR`).

---

## 2. Was bietet Upstream, was hat die Bridge eigen gelöst, was ist doppelt?

| Thema | Upstream (Datei:Zeile am Pin, in Upstream gleich) | Bridge | Urteil |
|---|---|---|---|
| Headless ohne Server | `Mage.Tests/…/CardTestPlayerAPIImpl.java:317-324`: `GameOptions.testMode`, `stopOnTurn`, `currentGame.start(...)` im selben Prozess; Spieler `TestPlayer(TestComputerPlayer)` (`MageTestPlayerBase.java:188`) | derselbe Aufbau: `Game` direkt, eigener `PlayerImpl`, eigener Spiel-Thread | richtig gelöst, kein Server-/Netz-Overhead vorhanden |
| Kartenscan überspringen | `FAST_SCAN_WITHOUT_DATABASE_CREATE` setzt `CardScanner.scanned = true` (`CardTestPlayerAPIImpl.java:160-166`) | scannt immer und lehnt einen vorinitialisierten Scanner bewusst ab (`XmageDeckImporter.java:398-420`); der Fork fragt alle gespeicherten Karten in einer Abfrage (`E/cards/repository/CardScanner.java:55-62`) | kein Hebel: `Sets` lädt die Klassen ohnehin, AppCDS deckt es |
| Server-Optionen | `Mage.Server/config/config.xml:49-57` (`maxGameThreads`, `maxSecondsIdle`, `maxAiOpponents`, `saveGameActivated`), `-Dxmage.testMode` (`Mage.Server/…/Main.java:72-116`) | nicht benutzt (kein Server) | nicht anwendbar |
| Debug-/Log-Schalter | `E/util/DebugUtil.java:24-36` (alle `false`), `HintUtils.RESTRICT_HINTS_ENABLE` (`final`, `true`) | unverändert | nichts abzuschalten; Hinweise abschalten wäre eine Fork-Änderung und änderte Regeltexte (Sortierschlüssel der Bridge) |
| Seeds | `RandomUtil` ist ein statischer Nicht-Regel-Strom (`E/util/RandomUtil.java:22,55`) | je Partie `game.setRulesSeed` (Fork-API, `B/XmageFullGameSession.java:201-210`) | Fork-eigen, richtig; Determinismus 424/424 (MESSUNG) |
| Rollback | `GameOptions.rollbackTurnsAllowed` (`E/game/GameOptions.java:51`) | `false` (`Session:211-213`) | genutzt |
| Mana-Aufzählung | `getUseableManaAbilities` (`PlayerImpl.java:1916-1927`), so zahlt `HumanPlayer` (`HumanPlayer.java:1820`) | ruft sie **und** ein volles `getPlayable` (`Player:2349-2356`) | **doppelt**; Kandidat C3 |
| `getManaAvailable` ohne zweite Kopie | nicht vorhanden | wortgleicher Spiegel der Engine-Methode in der Bridge (`Player:402-407,421-522`), muss bei jedem Repin verglichen werden | **Verdopplung von Engine-Code**; gehört beim nächsten Repin als Einzeiler in den Fork (kein Tempo-Gewinn, nur Pflegelast) |
| Warten auf die Engine | – | Monitor **und** 1-ms-Abfrage mit Kopie (`Session:1115-1146`) | doppelt, aber gemessen ohne CPU-Kosten (#1264) |
| Zustands-Sicht | `GameView`/`CardView` (Client-Server) | eigener Redactor, zwei Sichten je Entscheidung | nötig (Sicht je Prinzipal, feste Reihenfolge); Kosten UNKNOWN |
| Sortierschlüssel | – | GUI-Funktion `getRules(game)` als Schlüssel, je Vergleich neu | unnötig teuer; Kandidat C1 |
| Kartendatenbank | H2-Datei mit Auto-Server | private Kopie je Worker (261 MB) | Platte, keine Zeit |
| Schnellere Engine-Pfade seit Fork-Stand | keine in den heißen Dateien (Baum-Vergleich Pin gegen 5769a6cb: Unterschiede sind Fork-Änderungen) | – | nichts zu holen; Commit-Liste UNKNOWN |

---

## 3. Kandidaten, gerankt nach Gewinn/Risiko

Messregel für alle: Identität mit `scripts/benchmark_xmage_full_games.py run … --seeds 1-36 --workers 4 --games-per-jvm 9 --fast` und `compare … --expect-games 36` (Hash und Frame-Digest), dazu ein Arm `--games-per-jvm 1` auf 6 Seeds. Tempo nur **verschränkt** (A, B, A, B …) auf derselben Kartendatenbank-Kopie, W=1, G=16, gewertet die Partien 9 bis 16, mindestens 5 saubere Paare, Fremdlast ≤ 0,1 Kerne notiert (wie #1316; Lehre aus `UPSTREAM_PICKS_V15` §Speed hygiene). Geltende Schwelle aus #1264: unter 5 % Gewinn wird nicht gemergt.

| # | Kandidat | Ebene | Erwarteter Gewinn | Äquivalenzrisiko | Gate | Aufwand | Wie messen |
|---|---|---|---|---|---|---|---|
| **C0** | **Langlebige Worker-JVMs**: Batch G=16 bis 24 sofort (K1), Fortschritt je Partie (A2), gepaarte Serie mit einer JVM je Worker über alle Look-Fenster (#1585, #1576), Obergrenze 24 in `launch.py:40` anheben | Python | CPU je Partie 22,2 (G=8) → rund 15 (G ≥ 100, Modell 14,3 + 63/G): −30 %; gepaart 33,5 → 15 bis 18: −45 bis −55 %; an der CPU-Grenze 595 → bis 967 Partien/h (Obergrenze, MESSUNG der warmen Partien) | keins für das Spiel (Position in der JVM ändert nichts: 424/424, 18/18 in einer JVM). **UNKNOWN: Speicher und Identität jenseits von 24 Partien je JVM** (G=8→16: +62 MB) | Tests + PERF, keine Bridge-Änderung | M | Zellen G=24/48/96 bei W=1 und W=Kerne, je 96 Partien, RSS-Verlauf, Identität 36/36 gegen G=1 |
| **C1** | **Sortierschlüssel einmal je Element** (Schlüssel vorab in eine Liste, dann sortieren) in `abilitySortKey` und `XmageStableOrder` | Bridge | UNKNOWN; VERMUTUNG 2 bis 8 % der warmen JVM-CPU (2·n·log n teure Schlüssel je Frame mit Optionen; Regex 3,8 % Blatt-Stichproben) | praktisch keins: gleiche Schlüssel, gleicher stabiler Sortierer, gleiche Reihenfolge; Voraussetzung ist nur, dass ein Schlüssel innerhalb einer Sortierung konstant ist (sonst wäre die heutige Sortierung schon unbestimmt) | Studio-Bridge-Gate `NEUTRAL` | S (< 50 Zeilen + Test „gleiche Reihenfolge“) | **zuerst M0** (unten); dann 5 Paare |
| **M0** | **Ein Profil am heutigen Stand** (nach #1316): W=1, G=12, JFR ab Partie 3, `stackdepth=512`, `jfr print --stack-depth 512`; auszählen: `permanentContent`/`abilitySortKey`, Redactor-Regeltexte, `playManaFrame → getPlayable`, `manaCostAffordable`, `GameStates.save`, `Watcher.copy`, `ContinuousEffects.apply`; dazu `-XX:+CITime` für die Übersetzer-CPU | Messung | klärt den Widerspruch aus 1.1 und entscheidet C1 bis C4 und F1 bis F3; rund 10 Minuten Rechenzeit | keins | keins (nur Messen) | S | n = 10 warme Partien, zwei unabhängige Zählungen wie #1298 |
| **C2** | **JDK 25 als Laufzeit** (JAR unverändert, Ziel 17): AOT-Cache mit Methoden-Profilen (JEP 483/514/515) statt AppCDS; kompakte Objekt-Header (`-XX:+UseCompactObjectHeaders`, JEP 519) | Startbefehl/Toolchain | VERMUTUNG: Aufwärmen −10 bis −25 % von 64 CPU-s (Profile sofort da; die Übersetzung selbst bleibt), Start −1 bis −3 s über AppCDS hinaus; warme CPU −3 bis −8 % durch kleinere Objekte bei 35 GB Allokation je Partie. Mit C0 schrumpft der Aufwärm-Teil auf wenige Prozent; es bleibt der Header-Effekt und der PLAY-Start | gering: Regeln hängen nicht an der JDK-Version; Rest-Risiko versteckte Abhängigkeit von Identity-Hash- oder Bibliotheks-Reihenfolgen. Beweisbar mit demselben JAR auf zwei JDKs | PERF + Identität 36/36 (ohne `--require-different-jars`); **Owner entscheidet die Toolchain** (Owner-PC: Java-Version UNKNOWN) | S (nur Befehl), M mit Archiv-Bau im Studio | 4 Zellen JDK 21/25 × mit/ohne Cache, G=1 und G=16, je 5 Paare |
| **C3** | **Mana-Frame ohne volles `getPlayable`** (nur Mana-Fähigkeiten aufzählen, eine Simulations-Kopie für die Mana-Verfügbarkeit) | Bridge, sauber nur mit kleiner Fork-Hilfe | VERMUTUNG 3 bis 5 % (Oktober-Profil: Mana-Frame-Spielbarkeit 11 % + 5 %, seither zwei Kopien entfernt; 27 % der Frames) | **mittel**: eine eigene Aufzählung in der Bridge spiegelt Engine-Logik (Mana aus Hand, Exil, Command-Zone, Alternativkosten); der Referenzsatz beweist nur die Karten, die er spielt, der Rest wäre `UNKNOWN` | `NEUTRAL` (Frames müssen gleich bleiben) | M | nach M0; nur wenn der Block ≥ 8 % hat |
| **C4** | **Eine geteilte Simulations-Kopie je Frame für `manaCostAffordable`** (heute eine je Signet-artiger Fähigkeit) | Bridge | 1,7 % (MESSUNG #1298), unter der Schwelle | gering, aber die Kopie wird je Fähigkeit verändert (`setTapped(true)`), Teilen braucht Zurücksetzen | `NEUTRAL` | S | nur gebündelt mit C1 |
| **F1** | Spielbarkeits-Prüfung ohne äußere Kopie bzw. Simulation je Fenster wiederverwenden (der „perf port“ existiert, ändert Optionstext) | **Fork** | rund 11 % der Stichproben als Obergrenze (MESSUNG #1298) | **hoch**: genau hier wich eine Partie ab (13/14, `AddManaChosenColorEffect`); `BEHAVIOUR` | Owner-Go Push/Repin, Requalifikation (PB-03, AF11), neues Siegel | L | 36 Seeds + 46 Precon-Pods lokal, erst danach Antrag |
| **F2** | `Watcher.copy`: Konstruktor und Felder je Klasse einmal ermitteln (gleiche Felder, gleiche Reihenfolge) | **Fork** | VERMUTUNG 1 bis 2 % (Watchers 7 % der Kopie inklusiv) | sehr gering | wie F1 | S | nur im Bündel |
| **F3** | Lesezeichen billiger (`GameStates.save`) | **Fork** | 5,1 % Obergrenze; ein Lesezeichen muss eine echte Momentaufnahme bleiben, realistisch 1 bis 2 % | mittel | wie F1 | M | nur im Bündel |
| **F4** | Spiegel von `getManaAvailable` in den Fork verlegen (eine Zeile dort, rund 110 Zeilen Bridge weg) | **Fork** | 0 % Tempo; entfernt Repin-Pflegelast | gering | wie F1 | S | Identität 36/36 |
| C5 | PLAY-Start: warme oder vorgestartete JVM je Studio-Sitzung, AppCDS, Serien-Schalter (K4/A6 der Effizienz-Lane) | Python/Konfig | 6,3 s → VERMUTUNG 1 bis 3 s bis zur ersten Entscheidung | keins | Tests; K4 braucht Owner-Freigabe | S bis M | 5 Starts je Variante |

**Bewertet und nicht empfohlen:**

- **Schlankere Frames, JSON-Streaming, Monitor statt Abfrage:** gemessen 0 % (#1264). Frame-Inhalt kürzen wäre `BEHAVIOUR` und träfe höchstens 3,1 % (Python liest) plus 3,0 % (Aufzeichnen).
- **`-XX:TieredStopAtLevel=1`:** +50 % Wandzeit (zweimal gemessen). Parallel-GC, feste Young-Generation, Huge Pages: gemessen ohne Vorteil gegenüber SerialGC (Effizienz-Offensive §4). Der JDK-21-Flag-Raum ist ausgeschöpft.
- **GraalVM Native Image / AOT:** Karten entstehen per Reflection, `Watcher.copy` und ormlite ebenfalls; 32.000 Klassen bräuchten Reflection-Konfiguration; spart nur Startzeit; Spitzenleistung ohne PGO unter C2. Graal-JIT als C2-Ersatz: Gewinn UNKNOWN, Aufwärmen eher schlechter. **CRaC:** nur Linux, der Owner-PC ist Windows.
- **Mehrere Partien gleichzeitig in einer JVM** (geteiltes Aufwärmen, weniger RAM): Upstreams Server tut das, aber ohne Anspruch auf Bit-Gleichheit; statischer veränderlicher Zustand in 2,1 Mio. Zeilen Kartencode wäre ein seltenes, schwer beweisbares Äquivalenzrisiko; das Ergebnis trägt heute `seed_scope: single_isolated_jvm_process` (`B/XmageFullGameSession.java:1104`); das Protokoll müsste Sitzungen multiplexen. C0 holt denselben CPU-Gewinn ohne dieses Risiko.
- **Parallelität innerhalb einer Partie:** Engine und Pilot wechseln sich ab (1,03 Kerne warm); bei W = Kerne gibt es nichts zu verteilen, und Rechnen auf Verdacht verbietet sich (Rules-RNG, Determinismus).
- **Weitere „erzwungene“ Klassen in der Bridge beantworten:** nur der einzelne Pass ist belegt neutral (`Controller:345ff.`); andere Ein-Options-Klassen laufen durch Pilot-Buchhaltung (`FORCED_PASS_PRECHECK_1299`, Teil A).
- **Zweite Kopie in `getManaAvailable` im Fork streichen:** abgelehnt (13/14). **`HashMap` vorbelegen:** ändert Iterationsreihenfolgen.
- **Kartenscan überspringen, H2 nur lesend öffnen, `Sets` lazy:** trifft nur 5 bis 8 s je JVM-Start, die C0 und AppCDS bereits erledigen; H2-URL liegt im Fork.
- **Kürzeres `SETTLE_TIMEOUT`:** würde einen Hänger billiger machen, erzeugt aber unter CPU-Last falsche `DECISION_ADVANCE_TIMEOUT` (Effizienz-Offensive §9); #1584 behebt die Ursache.

**Fork oder nur Bridge, ehrlich:** Alles Belegte oberhalb der 5-%-Schwelle liegt in Python (C0) oder ist Konfiguration (C2). Die Bridge hat nach #1316 noch einen ungeprüften Kandidaten (C1) und zwei kleine (C3, C4). Der Fork hält den größten Rest-Block (äußere Kopie rund 11 %), aber mit dem höchsten Risiko und den höchsten Fixkosten; die geltende Auslöse-Regel (Owner-PC unter 500 Partien/h, gemessen 541) ist nicht erfüllt. Ein Fork-Bündel F2 + F4 (+ F3, + F1 nur mit eigenem Nachweis) lohnt genau dann, wenn ein Repin ohnehin ansteht.

---

## 4. Empfehlung

**Die drei besten Hebel, in dieser Reihenfolge:**

1. **C0, JVM-Lebensdauer (Python, sofort):** K1 als Betriebsanweisung, dann A2 und #1585/#1576, danach die Obergrenze 24 anheben, sobald G=48/96 gemessen ist. Größter belegter Gewinn, kein Regel- und kein Bridge-Risiko.
2. **M0, dann C1 (+ C4) als ein `NEUTRAL`-PR:** erst das eine Profil am heutigen Stand, das den Bridge-Widerspruch auflöst; wenn die Sortierschlüssel ≥ 5 % tragen, die kleine Änderung unter dem Studio-Bridge-Gate. Trägt M0 den Befund nicht, entfällt C1 ohne Schaden.
3. **C2, JDK 25 mit AOT-Cache und kompakten Headern, als Messversuch:** reine Startbefehl-Änderung, per Referenzsatz beweisbar; übernimmt für Einzelpartien, PLAY-Start und kurze Serien, was C0 dort nicht erreicht.

**Was wir lassen:** schlanke Frames und Streaming (#1264), C1-Übersetzer und weitere GC-Schalter, Native Image, CRaC, mehrere Partien je JVM gleichzeitig, Parallelität in der Partie, weitere Auto-Antworten der Bridge, Fork-Kopier-Umbauten ohne anstehenden Repin, Start-Mikrooptimierungen (Scan, H2).

**Nur der Owner entscheidet:**
- jede Fork-Änderung (Push, Repin, Requalifikation, neues Siegel), also F1 bis F4, auch als Bündel mit dem Upstream-Merge;
- die Java-Laufzeit am Owner-PC und im Release-Paket (C2), samt der Frage, ob ein JDK mitgeliefert wird;
- `skipForcedDecisions` für PLAY (K4/A6 der Effizienz-Lane) und den Standard-Startbefehl der Evidenz-Lanes (eine Partie je JVM, Owner-Entscheid 2026-10-15);
- ob die 5-%-Schwelle und die 500-Partien/h-Regel als Auslöser für Fork-Arbeit weiter gelten.

**UNKNOWN (nicht bewertbar ohne neue Messung oder weil außerhalb des Auftrags):**
- Anteil der Sortierschlüssel, der Redactor-Regeltexte, der Mana-Frame-Spielbarkeit und der Layer-Neuberechnung an der warmen CPU (kein Profil nach #1316; die JFR-Rohdateien liegen nicht im Repository und nicht auf dieser Maschine).
- Zusammensetzung der 64 CPU-s Aufwärmen (Übersetzer-CPU gegen langsamen Code); damit auch der Gewinn von C2.
- Verhalten des Pins auf JDK 25 (Start, Bibliotheken, Identität) und ob der AOT-Cache von JDK 25 mit SerialGC alle Teile nutzt; was neuere JDKs (AOT-Code-Cache) zusätzlich bringen.
- Speicher und Identität bei mehr als 24 Partien je JVM; G1 unter Volllast.
- Owner-PC: Kerne, RAM, Java-Version, Durchsatz nach #1316.
- Upstream-Commits seit dem Fork-Stand als Liste (flacher Clone, kein API-Zugriff auf magefree/mage in dieser Sitzung); der Baum-Vergleich der heißen Dateien zeigt keine Performance-Änderung, andere Dateien wurden nicht verglichen.
- Ob die Stichproben-Anteile aus #1281/#1298 (Chulane-Tisch, Ryzen bzw. gedrosselte VM, vor #1316) auf den Precon-Tisch von `eff_sim_play.md` übertragbar sind.
- Zeit je Log-Text-Erzeugung der Engine (`informPlayers`-Strings) und Kosten der GC unter 4 Workern (Speicherbandbreite).
