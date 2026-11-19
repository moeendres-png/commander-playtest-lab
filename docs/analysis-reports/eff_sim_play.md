# Effizienz SIMULATE und PLAY: Messung, Äquivalenz, Maßnahmen (Refs #1558)

Stand: 2026-11-19, Lab `origin/main` 51185f2d8 (Worktree, nur gelesen), Engine-Pin f4d12f6e8,
Bridge-JAR sha256 204dd9ad…, Java 21.0.12, Python 3.13. Art: nur Messen, Analysieren, Planen.
Keine Repo-Änderung, nichts gepusht oder gepostet. Alle Zahlen sind Werte dieser VM (4 vCPU, 16 GB),
keine Zielwerte und keine Aussage über den Owner-PC.

## 0. Kurzfassung

1. **Die Zeit geht in das Aufwärmen der JVM, nicht in Start, Logs oder Piloten.** Eine frische
   Bridge-JVM kostet rund 64 CPU-Sekunden Übersetzungsarbeit (JIT), verteilt auf ihre ersten Partien.
   Warm kostet eine Vierer-Partie 14,3 CPU-s; im Serien-Default (6 Partien je JVM) sind es etwa 25,
   mit einer Partie je JVM 53. Länger lebende JVMs sind der größte Hebel, bei identischen Ergebnissen.
2. **Durchsatz auf dieser 4-Kern-VM** (Vierer-Tisch aus vier Precons, 8 Partien je JVM, ruhige CPU):
   1 Worker 235, 3 Worker 533, 4 Worker 595 Partien/h. Der Vorbefund „541 Partien/h mit 6 Workern“
   (#1251, Owner-PC, anderer Tisch) ist hier weder bestätigt noch widerlegt: andere Maschine.
3. **Äquivalenz: 424 von 424 Partien identisch** über 31 Zellen (Worker 1 bis 4, 1 bis 16 Partien je
   JVM, mit und ohne AppCDS, SerialGC oder G1, Prozess- oder Thread-Pfad): gleicher Seed ergibt
   gleichen Transkript-Hash, gleiche Sieger, gleiche Entscheidungszahl, gleiche Starthände.
   `skipForcedDecisions` ändert nur die Frame-Folge (genau die erzwungenen KI-Pässe fehlen), nicht
   Transkript-Hash, Sieger oder die Frames mit echter Wahl.
4. **Gepaarte Serie Ende-zu-Ende ist deutlich langsamer als die Batch-Serie:** 350 gestartete
   Partien/h gegen 595 (gleiche Maschine, 4 Worker). Gründe: je Look-Fenster neue JVMs (5 Partien je
   JVM), Fensterschranke, Threads statt Prozesse, und 4 von 80 Partien liefen in einen
   Engine-Hänger (je etwa 90 s). Wegen dieser 4 Partien endete die Serie als `NOT_DECIDED`
   (`CENSORING_LIMIT`).
5. **Statistik schlägt Tempo:** Mit Slot-Ausrichtung (#1516) waren 10,8 % der Paare diskordant
   (4 von 37, Wilson-95 % 4,3 bis 24,7 %) statt 48,4 % bei unabhängigen Partien. Das entspricht einer
   4,6-fach kleineren Varianz je Paar (n=37, ein Deckpaar, drei getauschte Karten; breite Unsicherheit).
6. **PLAY: die Gegner-KI rechnet schnell, die Wartezeit ist eingestellt.** Die KI braucht im Median
   8 ms je Entscheidung, für eine ganze Partie 8,9 s. Die Seite setzt beim Öffnen 500 ms Pause je
   KI-Entscheidung: bei 1.455 KI-Entscheidungen sind das 12 Minuten reines Warten je Partie.
   42 % der KI-Entscheidungen sind erzwungene Pässe; mit `skipForcedDecisions` entfallen sie bei
   identischem Spiel. Das Polling der Seite (400 ms) kostet weitere rund 113 s je Partie.

## 1. Messaufbau

- **Tisch:** `precon/2016/open_hostility` (Sitz 0), `precon/2026/lorehold_spirit`,
  `precon/2024/animated_army`, `precon/2022/token_triumph` (der Tisch des Echt-Engine-Tests
  `tests/unit/test_human_seat_play_1169.py`). Seeds 1 bis 8 für die Matrix, 2/4/5/7 für die
  Digest-Proben, 1000 bis 1039 für die gepaarte Serie, 21 für PLAY. Partien dieser Seeds haben im
  Mittel 2.715 Engine-Entscheidungen (1.603 bis 4.399) und 30 bis 61 Züge.
- **Werkzeug:** eigenes Messskript (nicht im Repo), Kopie unter
  `/tmp/claude-0/-home-user/ef006e8b-893c-5ebd-80a1-8743a09c7458/scratchpad/costudio/eff_sim_play_data/tools/`
  (`h.py`, `phase.py`, `play_meas.py`, `pair_an.py`, `agg.py`). Es startet dieselben Wege wie das
  Studio: Batch-Pfad = ein Kindprozess `python -m commander_lab.studio play-batch` je Chunk (wie
  `BatchSimulation._process_chunk`); Thread-Pfad = ein Python-Prozess, je Chunk ein Thread mit
  `play_recorded_games` (wie `parallel_window_player` seit #1513). Der Engine-Befehl wird wie in
  `launch.series_engine` gebildet, jeder Teil schaltbar.
- **Replikat-Entwurf:** In einer Zelle spielt jeder der W Worker dieselbe Seed-Liste 1 bis 8. So ist
  die Arbeit je Worker gleich, die Zellen sind Seed für Seed vergleichbar, und jede Partie fällt
  mehrfach an (Determinismus-Probe unter Last).
- **Messgrößen:** Wandzeit; CPU-Sekunden aus `/proc` getrennt nach `java` und `python` (alle 0,2 s
  abgetastet); Fremdlast = belegte Kerne der Maschine minus eigene; Spitzen-RSS und -PSS der
  Prozessfamilie; Partiebeginn aus dem Erscheinen der Logdatei.
- **Last:** Während des ersten Messblocks (18.11., 23:04 bis 23:58 UTC) lief eine zweite Messung auf
  derselben Maschine, mit 0,05 bis 1,1 Kernen Dauerlast, nicht nur Spitzen. Nach dem Neustart der VM
  (19.11., 02:11 UTC) war die Maschine ruhig (Fremdlast ≤ 0,07 Kerne bei den Zellen `q_*`,
  `pair40`, PLAY). Jede Zeile nennt ihre Fremdlast. Aussagen zum Durchsatz bei W ≥ 3 stützen sich
  auf die ruhigen Zellen; belastete Zellen stehen daneben und sind so benannt.
- **Umfang:** 31 Zellen, 424 beendete Partien, dazu 80 Partien der gepaarten Serie, 2 PLAY-Partien,
  3 Wiederholungen der Hänger-Seeds. Reine Messzeit etwa 90 Minuten (über dem Ziel von 60 bis 75).
- **Nicht gemessen (weggelassen wegen Zeit):** Zellen W=2/G=4 und W=4/G=1 (abgebrochen), G=24, G1
  unter Volllast, `-Xmx` kleiner als 3g. Diese Felder sind unten als UNKNOWN oder Modell markiert.

## 2. SIMULATE: Durchsatz

### 2.1 Matrix Worker × Partien je JVM

Serien-Standard: `-XX:+UseSerialGC`, `skipForcedDecisions=true`, `-Xmx3g`, kein AppCDS. n = Partien
der Zelle. „Spiele/h“ = beendete Partien / Wandzeit der Zelle. CPU-s je Partie = (java + python).
Befehl je Zelle: `python3 tools/h.py cell --tag <Zelle> --path <batch|thread> --workers W
--games-per-jvm G --chunks "<Seeds je Chunk>"`.

| Zelle | Pfad | W | G | n | Wand s | Spiele/h | s/Partie | CPU-s/Partie (java+py) | eigene Kerne | Fremdlast | RSS MB | Load vor→nach |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| m_w1_g8 | Batch | 1 | 8 | 8 | 124,3 | 231,7 | 15,5 | 21,9 (18,9+3,0) | 1,41 | 1,00 | 951 | 2,3→3,2 |
| q_w1_g8 | Batch | 1 | 8 | 8 | 122,5 | 235,2 | 15,3 | 22,3 (19,1+3,1) | 1,45 | 0,21 | 948 | 6,1→1,8 |
| t_w1_g8 | Thread | 1 | 8 | 8 | 121,8 | 236,5 | 15,2 | 22,5 (19,5+3,0) | 1,48 | 0,19 | 926 | 5,4→1,8 |
| m_w2_g8 | Batch | 2 | 8 | 16 | 145,0 | 397,2 | 9,1 | 22,6 (19,7+3,0) | 2,50 | 0,81 | 1.907 | 2,5→3,8 |
| m_w3_g8 | Batch | 3 | 8 | 24 | 170,5 | 506,7 | 7,1 | 22,3 (19,3+3,0) | 3,14 | 0,58 | 2.857 | 3,8→5,6 |
| **q_w3_g8** | Batch | 3 | 8 | 24 | 162,2 | **532,7** | 6,8 | 23,3 (20,1+3,2) | 3,44 | 0,05 | 2.895 | 6,5→4,4 |
| t_w3_g8 | Thread | 3 | 8 | 24 | 174,0 | 496,5 | 7,3 | 22,2 (19,4+2,9) | 3,07 | 0,40 | 2.551 | 5,1→5,4 |
| m_w4_g8 | Batch | 4 | 8 | 32 | 250,3 | 460,2 | 7,8 | 23,7 (20,6+3,2) | 3,03 | 0,89 | 3.812 | 5,6→7,3 |
| **q_w4_g8** | Batch | 4 | 8 | 32 | 193,5 | **595,4** | 6,1 | 23,2 (20,1+3,1) | 3,84 | 0,03 | 3.869 | 4,4→7,2 |
| t_w4_g8 | Thread | 4 | 8 | 32 | 206,8 | 557,0 | 6,5 | 22,0 (19,1+2,9) | 3,40 | 0,05 | 3.337 | 6,8→5,1 |
| qt_w4_g8 | Thread | 4 | 8 | 32 | 216,9 | 531,1 | 6,8 | 23,4 (20,4+3,0) | 3,45 | 0,02 | 3.352 | 7,2→6,1 |
| m_w1_g4 | Batch | 1 | 4 | 8 | 142,9 | 201,5 | 17,9 | 29,6 (26,1+3,5) | 1,65 | 0,74 | 946 | 7,3→3,2 |
| m_w3_g4 | Batch | 3 | 4 | 24 | 205,2 | 421,2 | 8,6 | 27,8 (24,7+3,1) | 3,26 | 0,44 | 2.852 | 7,1→6,8 |
| m_w4_g4 | Batch | 4 | 4 | 32 | 269,3 | 427,8 | 8,4 | 29,1 (25,9+3,3) | 3,46 | 0,41 | 3.787 | 3,2→7,1 |
| m_w1_g1 | Batch | 1 | 1 | 8 | 212,8 | 135,4 | 26,6 | 53,3 (48,9+4,5) | 2,00 | 1,11 | 894 | 3,2→3,2 |
| f_g16 | Batch | 1 | 16 | 16 | 233,1 | 247,1 | 14,6 | 18,3 (15,3+3,0) | 1,26 | 0,16 | 1.013 | 1,8→1,1 |

Nicht gemessen: W=2 mit G=1/4, W=3 mit G=1, W=4 mit G=1 (UNKNOWN; Modell in 2.2).

Lesart:

- **CPU je Partie hängt an G, nicht an W:** bei G=8 21,9 bis 23,7 CPU-s in allen 11 Zellen
  (Spanne 8 %), bei G=4 27,8 bis 29,6, bei G=1 53,3, bei G=16 18,3.
- **W=1, G=8 dreimal gemessen:** 231,7 / 235,2 / 236,5 Spiele/h (Spanne 2 %), obwohl die Fremdlast
  zwischen 0,19 und 1,0 Kernen lag. Ein einzelner Worker ist gegen Fremdlast unempfindlich.
- **W=4 ist es nicht:** 595 Spiele/h bei ruhiger Maschine, 460 bei 0,9 Kernen Fremdlast. Unter
  dieser Last war W=3 (507) schneller als W=4 (460). Der Default `min(4, Kerne - 1)` ist deshalb
  für einen PC, an dem nebenher gearbeitet wird, die bessere Wahl.
- **Dauer je Seed, kalt gegen warm (W=1, G=8, drei Läufe):** erste Partie einer JVM (Seed 1)
  22,0 bis 22,8 s; dieselbe Partie an Position 9 einer JVM 13,9 s. Bei W=4 dauert die erste Partie
  56,5 bis 58,6 s (ruhig, n=4), bei W=3 41,4 bis 42,7 s (n=3): die Übersetzer-Threads der JVMs
  konkurrieren um die Kerne.

### 2.2 Der eigentliche Kostentreiber: JIT-Aufwärmen

Zelle `f_g16`: eine JVM spielt die Seeds 1 bis 8 zweimal hintereinander (16 Partien, W=1,
Fremdlast 0,16).

| Durchgang | Wand s | java CPU-s | python CPU-s | CPU-s/Partie |
|---|---|---|---|---|
| Partien 1 bis 8 (JVM frisch) | 119,8 | 154,5 | 21,8 | 22,0 |
| Partien 9 bis 16 (JVM warm) | 111,6 | 90,4 | 24,2 | **14,3** |

Differenz: 64 java-CPU-s je JVM-Leben für Klassenladen und JIT (38 s davon in der ersten Partie,
der Rest in den Partien 2 bis 8). Daraus das Modell **CPU je Partie ≈ 14,3 + 63/G** für G ≥ 4
(Prüfung: G=4 gemessen 29,6, Modell 30,1; G=8 gemessen 22,3, Modell 22,2; G=16 gemessen 18,3,
Modell 18,2). Für G=1 gilt es nicht (gemessen 53,3: nur der Anteil der ersten Partie fällt an).
Modellwerte, nicht gemessen: G=6 (Default) 24,8; G=24 (heutiges Maximum) 16,9.

Anteil des Aufwärmens an der gesamten CPU: 73 % bei G=1, 42 % bei G=6 (Modell), 36 % bei G=8, 22 % bei G=16.

Folgen:

- Auf einem ausgelasteten Rechner (W = Kerne) wird die Aufwärm-CPU zu Wandzeit. Deshalb fällt
  W=4/G=4 (428 Spiele/h) hinter W=4/G=8 (595) zurück, obwohl der JVM-Start selbst nur Sekunden kostet.
- Der reine JVM-Start ist klein: Prozessstart 1 ms, `start_engine` 0,1 s, erster `import_deck`
  5,0 s (Kartendatenbank öffnen, Klassen laden), Python-Start und Deck-Vorbereitung 1,2 bis 1,6 s.
- `-XX:TieredStopAtLevel=1` (nur der schnelle Übersetzer) hilft nicht: 184,8 s statt 122 s für
  dieselben 8 Partien (+50 % Wandzeit, CPU gleich). Verworfen.

### 2.3 Schalter: AppCDS, GC, skipForcedDecisions (W=1, Seeds 1 bis 8)

Vergleichsbasis: Mittel der drei Standard-Läufe W=1/G=8 (122,9 s Wand; 22,2 CPU-s/Partie; 942 MB RSS).

| Zelle | Änderung | n | Wand s | CPU-s/Partie | RSS MB | Fremdlast | Befund |
|---|---|---|---|---|---|---|---|
| f_appcds_g8 | mit AppCDS | 8 | 120,7 | 21,6 | 962 | 0,19 | erste Partie 19,8 s statt 22,0 bis 22,8 s: −2,6 s je JVM-Start; −0,6 CPU-s je Partie |
| f_appcds_g1 | AppCDS, G=1, Seeds 1 bis 4 | 4 | 84,3 | 46,1 | 874 | 0,17 | je Partie 19,7 s statt 25,4 s (dieselben Seeds in m_w1_g1, dort Fremdlast 1,1: Vergleich verzerrt) |
| f_g1gc_g8 | G1 statt SerialGC | 8 | 116,3 | 22,6 | 1.381 | 0,14 | Wand −5 % (freie Kerne helfen dem GC), CPU +2 %, RAM +47 % |
| f_skip0_g8 | skipForcedDecisions aus | 8 | 130,1 | 23,7 | 952 | 0,13 | Wand +6 %, CPU +7 %, python CPU 3,5 statt 3,1 s; 21.717 statt 13.556 Frames |
| f_c1_g8 | nur C1-Übersetzer | 8 | 184,8 | 23,8 | 839 | 0,08 | Wand +50 %: verworfen |
| e_ref | G1, kein skip, G=1 (Befehl einer Einzelpartie), Seeds 2/4/5/7, mit Digest | 4 | 91,6 | 52,0 | 1.080 | 0,12 | Referenz-Konfiguration; 22,9 s je Partie |

Einordnung der Vorbefunde:

- **skipForcedDecisions:** bestätigt, −6 % Wandzeit und CPU, −38 % Frames, Logs 24 % kleiner.
- **SerialGC „−10 % CPU“:** auf diesem Tisch nicht reproduziert (CPU ±2 %, je n=1 gegen n=3).
  Belegt ist der Speicher: 942 gegen 1.381 MB je Worker. G1 unter Volllast (W=3/4): UNKNOWN.
- **AppCDS:** spart je JVM-Start 2,6 s Wandzeit und etwa 6,5 CPU-s (n=1 gegen n=4 erste Partien).
  Je Partie bei G=8 sind das 2 bis 3 %. Archiv 322 MB, Bau 24 s. JIT-Code speichert es nicht.
- **`-Xmx3g`:** nie erreicht. Spitzen-RSS je Worker 0,84 bis 1,01 GB (SerialGC). Kleineres `-Xmx`
  wurde nicht gemessen (UNKNOWN); ein Gewinn ist nicht zu erwarten, weil der Heap nicht drückt.

### 2.4 Batch-Pfad gegen gepaarten Pfad

Gleiche Arbeit, nur die Parallelisierung verschieden (Replikat-Zellen):

- W=1: gleich (236,5 gegen 231,7 bis 235,2 Spiele/h).
- W=3: kein belastbarer Unterschied (Thread 496,5 bei Fremdlast 0,40; Batch 506,7 bei 0,58 und
  532,7 bei 0,05).
- **W=4, ruhig: Thread 531,1 und 557,0 (n=2), Batch 595,4 (n=1): Thread-Pfad 6 bis 11 % langsamer.**
  Er nutzt 3,40 bis 3,45 statt 3,84 Kerne. Erklärung (CODE_DERIVED, nicht isoliert gemessen): vier
  Threads teilen sich einen Python-Interpreter (GIL); je Partie fallen 3 s Python-CPU auf etwa 14 s an.
- Speicher: Thread-Pfad 13 % weniger (3.352 gegen 3.869 MB bei W=4), weil nur ein Python-Prozess läuft.

Ende-zu-Ende über den echten Weg (`compare-decks`, 40 Paare, Look alle 10 Paare, W=4, G=8,
Fremdlast 0,07; Befehl in Abschnitt 4.2):

| Größe | Wert |
|---|---|
| Partien gestartet / beendet | 80 / 76 |
| Wandzeit | 822 s |
| Partien/h gestartet / beendet | 350 / 333 |
| CPU-s je gestarteter Partie | 33,5 (java 29,6 + python 3,9) |
| eigene Kerne | 3,26 |
| Spitzen-RSS | 3.439 MB |

Gegen 595 Spiele/h und 23,2 CPU-s der Batch-Replikat-Zelle. Ursachen, soweit belegt:

1. **Partien je JVM:** `plan_look_window_chunks` begrenzt einen Chunk auf
   `min(G, ceil(Partien im Fenster / W))` = `min(8, 5)` = 5. Jedes Fenster startet 4 neue JVMs;
   80 Partien brauchten mindestens 16 JVM-Leben. Modell für G=5: 26,9 CPU-s je Partie.
2. **Engine-Hänger:** 4 Partien (Seeds 1024 Basis, 1029 Variante, 1033 beide Arme) endeten mit
   `ENGINE_FAILURE [BRIDGE_ERROR]`. Einzeln nachgespielt (Zellen `x_fail_def`, `x_fail_ref`):
   reproduzierbar, unabhängig von den Schaltern, je 89 bis 96 s Wandzeit und 113 bis 126 java-CPU-s.
   Die letzte Frame liegt jeweils im Schritt `declare_attackers`; in
   `XmageFullGameSession.java` steht `SETTLE_TIMEOUT = 75 s`. Die Ursache selbst ist UNKNOWN
   (Diagnose ist geschwärzt). In den Seeds 1 bis 8 trat der Fehler nie auf (0 von 424).
3. **Fensterschranke:** das nächste Fenster beginnt erst, wenn alle Chunks des Fensters fertig sind.
4. **Threads statt Prozesse** (oben, 6 bis 11 % bei W=4).
5. Die Partien der Seeds 1000 bis 1039 sind 6 % länger (2.869 gegen 2.715 Entscheidungen).

Die Anteile von 1, 3 und 4 sind nicht getrennt gemessen. Geschätzt aus den Einzelläufen: Punkt 2
allein bindet 4 × 90 s = 360 von 3.288 Worker-Sekunden (11 %).

### 2.5 Wohin geht die Zeit? (Phasen einer Serie)

Zelle `t_w1_g8` mit Beobachter (`phase.py`: umhüllt Aufrufe, ändert nichts; gleicher Transkript-Hash
wie ohne). 8 Partien, 13.556 Frames, 121,8 s Wandzeit, eine JVM, Fremdlast 0,19.

| Phase | Sekunden | Anteil |
|---|---|---|
| Python-Start, Importe, Decks laden, Partien vorbereiten | 1,2 | 1,0 % |
| JVM-Start und Handshake (`start_engine`, Version, Fähigkeiten) | 0,8 | 0,6 % |
| Decks importieren (32 Aufrufe; der erste 4,96 s: Kartendatenbank, Klassenladen) | 5,7 | 4,6 % |
| Partie anlegen und starten | 0,2 | 0,1 % |
| **Warten auf die Bridge je Entscheidung** (Regelkern, Zustands-JSON, Pipe) | 93,1 | 76,5 % |
| JSON der Antworten lesen und prüfen (Python) | 3,8 | 3,1 % |
| JSON der Anfragen schreiben (Python) | 0,4 | 0,3 % |
| **Pilot entscheidet** (`ExternalPilotDecisionPolicy.decide`) | 10,0 | 8,2 % |
| Aufzeichnen (`GameRecorder.record`, schreiben, flush) | 3,7 | 3,0 % |
| Ergebnis und Ereignisprotokoll holen | 0,4 | 0,4 % |
| Log packen (gzip, 8 Dateien) | 0,4 | 0,4 % |
| Rest (Schleife, Audit verdeckter Information, Thread-Übergabe) | 2,1 | 1,7 % |

- **Prozesskommunikation:** 325 MB Antworten über die Pipe für 13.556 Entscheidungen, also
  24 KB JSON je Entscheidung und 41 MB je Partie; Anfragen 2,7 KB. Das Lesen kostet 3,1 %.
- **I/O:** Logs 52 bis 219 KB je Partie (gepackt), Mittel 117 KB. Kartendatenbank 273 MB (einmal
  gebaut; der Erstlauf dauerte 56 s statt 22 s). Je Worker-Slot eine private Kopie von 261 MB
  (W=4: 1,0 GB Platte). AppCDS-Archiv 322 MB.
- **GC:** nicht getrennt gemessen. SerialGC und G1 unterscheiden sich in der CPU um 2 %.
- **Was in den 76,5 % steckt:** hier nicht profiliert. Vorbefund #1298 (JFR, nicht nachgemessen):
  38 % der JVM-CPU sind Zustandskopien, zwei Drittel davon aus der Spielbarkeits-Prüfung
  (`getPlayable`). Der Vorbefund S4/#1264 („schlanke Bridge“ ohne Gewinn) wurde nicht wiederholt.

Latenz je Entscheidung in der Serie (ms, n = Entscheidungen der 8 Partien):

| Klasse | n | Bridge Median | Bridge p95 | Pilot Median | Pilot p95 |
|---|---|---|---|---|---|
| Priorität | 7.331 | 6,4 | 15,7 | 0,69 | 1,72 |
| Mana bezahlen | 3.687 | 5,4 | 15,1 | 0,29 | 1,02 |
| Ziel | 346 | 5,6 | 16,7 | 1,26 | 3,66 |
| Angreifer | 860 | 2,2 | 12,5 | 0,89 | 1,54 |
| Blocker | 365 | 2,3 | 14,7 | 0,18 | 0,42 |

Größte Einzelwerte: Pilot 120 ms (eine Mana-Zahlung), Bridge 245 ms. Der Pilot ist mit 8 % der Zeit
kein Hebel; seine Logik wurde nicht angefasst.

### 2.6 Speicher

Je Worker 0,84 bis 1,01 GB RSS (JVM etwa 0,83 GB, Python etwa 0,11 GB), PSS 2 bis 4 % darunter.
W=4: 3,9 GB (Batch) oder 3,4 GB (Thread). G1 braucht 1,38 GB je Worker. Von G=8 auf G=16 wuchs das
RSS um 62 MB (951 → 1.013 MB); für G=24 und mehr: UNKNOWN.

## 3. Äquivalenz: gleicher Seed, gleiches Spiel

Geprüft wurde jede beendete Partie gegen alle anderen Partien desselben Seeds (Tisch gleich).

| Merkmal | Quelle | Ergebnis |
|---|---|---|
| Transkript-Hash (`semantic_transcript_sha256`) | Engine-Ergebnis | 424/424 identisch je Seed, über alle 31 Zellen |
| Sieger, Entscheidungszahl | Log-Abschluss | 424/424 |
| Starthände aller Sitze | erste eigene Frame je Sitz | 424/424 |
| Entscheidungsfolge (Sitz, Klasse, Wahl) | Log-Frames | identisch je Seed innerhalb gleicher skip-Einstellung |
| Frame-Folge aus dem Log, Kurz-IDs `[3a4]` normalisiert | Log-Frames | identisch je Seed innerhalb gleicher skip-Einstellung (3 frühe Zellen vor der Normalisierung nicht gewertet) |
| Frame-Digest des Repos (`frame_digest.py`, das Maß des Studio-Bridge-Gates) | Beobachter im Kindprozess | 56/56: je Seed ein Wert in den 6 Zellen mit skip, ein Wert in den 2 Zellen ohne skip |
| Frame-Digest ohne erzwungene Frames (`skip_forced`) | derselbe Beobachter | 56/56: **ein** Wert je Seed über alle 8 Zellen, mit und ohne skip |

Die 8 Digest-Zellen (Seeds 2/4/5/7): Referenz (G1, kein skip, eine Partie je JVM), Serien-Standard,
skip aus, AppCDS, G1, C1, Batch W=4, Thread W=4.

**Was `skipForcedDecisions` ändert, exakt:** Die Bridge beantwortet erzwungene Prioritäts-Pässe von
KI-Sitzen selbst. Entscheidungszahl und Transkript-Hash bleiben gleich (die Bridge schreibt die
Pässe weiter ins Transkript); `forced_decisions_skipped` nennt die Zahl (692 bis 1.313 je Partie,
im Mittel 38 % der Entscheidungen). Im Log fehlen genau diese Frames. Probe an der PLAY-Partie
Seed 21: 1.801 Frames ohne skip, minus 618 erzwungene KI-Pässe = 1.183; die verbleibende Folge ist
Frame für Frame gleich der Partie mit skip (1.183/1.183), die 346 Frames des Menschen sind gleich.
Mensch-Sitze schließt die Bridge aus (Bedingung 5 in `XmageFullGameDecisionController.java`).

**Zwei Abweichungen, beide außerhalb des Spiels:**

1. **Ereignisprotokoll (`event_log` im Log-Abschluss) ist nicht reihenfolgestabil.** Je Seed
   fanden sich 1 bis 25 verschiedene Hashes bei 45 bis 60 Läufen. An einem Paar geprüft: dieselben
   610 Ereignisse, zwei benachbarte `DAMAGED_PERMANENT`-Einträge desselben Kampfschadens vertauscht.
   Ob jede Abweichung nur eine solche Vertauschung ist, ist an einem Paar belegt, sonst UNKNOWN.
   Auswertungen, die das Protokoll lesen, dürfen sich nicht auf die Reihenfolge gleichzeitiger
   Ereignisse stützen.
2. **Rohe Logzeilen** tragen Kurz-IDs der Engine (`Skullclamp [8bb]`), die je Lauf wechseln
   (322 von 1.256 Frames einer Partie). Bytegleich sind zwei Logs desselben Spiels deshalb nie; das
   Gate-Maß des Repos normalisiert das bereits.

Keine Maßnahme dieses Berichts berührt die Pilot-Logik, fügt eine Heuristik hinzu oder nutzt eine
XMage-KI.

## 4. Maximum, Owner-PC, Statistik

### 4.1 Was ist auf 4 Kernen erreichbar?

Die Worker sind unabhängige Prozesse; einen seriellen Anteil im Sinn von Amdahl gibt es nur beim
Aufwärmen. Die Grenze ist Rechenkapazität: Spiele/h ≤ nutzbare Kerne × 3600 / CPU-s je Partie.
Gemessen nutzte W=4 im Batch-Pfad 3,84 von 4 Kernen.

| Konfiguration | CPU-s/Partie | Grenze bei 3,84 Kernen | Status |
|---|---|---|---|
| G=1 (früherer gepaarter Pfad) | 53,3 | 259 | Modell aus gemessener CPU |
| W=3, G=6 (heutiger Default) | 24,8 (Modell) | etwa 500 (mit den 3,44 Kernen, die W=3 nutzte) | Modell; G=8 gemessen 507 bis 533 |
| W=4, G=8 | 23,2 | 595 | **gemessen** (q_w4_g8) |
| W=4, G=16 | 18,3 (gemessen bei W=1) | 755 | Modell; bei W=4 nicht gemessen |
| W=4, G=24 (heutiges Maximum) | 16,9 (Modell) | 818 | Modell |
| dauerhaft warme JVMs | 14,3 (gemessen, Partien 9 bis 16) | 967 | Obergrenze; 1.007 bei vollen 4 Kernen |

Gemessen sind auf dieser Maschine +12 % von W=3 auf W=4 bei G=8 (533 → 595, ruhig, je n=1). Gegen
den Default (W=3, G=6, nach Modell etwa 500) wären das +19 %, und bis etwa +90 % als Obergrenze mit
warmen JVMs, ohne eine Entscheidung zu ändern. Zwischen 595 und 967 ist nichts gemessen.

Faustregel aus den eigenen Kernen je Worker: eine JVM in den ersten 8 Partien belegt im Mittel
1,45 Kerne, warm 1,03. Mit kurzem JVM-Leben trägt eine Maschine etwa Kerne/1,5 Worker ohne
Wandzeit-Verlust; mit langem JVM-Leben etwa einen Worker je Kern.

### 4.2 Owner-PC

Kernzahl, Takt, RAM, Java-Version: UNKNOWN. #1251 nennt 541 Partien/h mit 6 Workern × 8 Partien,
also 90 je Worker; hier sind es 149 je Worker bei W=4 und 235 bei W=1, an einem anderen Tisch. Eine
Übertragung wäre geraten. Deshalb das Messprotokoll in Abschnitt 7.

### 4.3 Statistik-Hebel: mehr Aussage je Partie

Gepaarte Serie `effpair`, Befehl (unter dem Messskript, Fremdlast 0,07):

```
python -m commander_lab.studio --data <Kopie> compare-decks \
  --base-deck data/decks/precons/2016_open_hostility.json --variant-deck <ausgerichtete Variante> \
  --opponent …2026_lorehold_spirit.json --opponent …2024_animated_army.json \
  --opponent …2022_token_triumph.json \
  --pairs 40 --look-every 10 --base-seed 1000 --workers 4 --games-per-jvm 8
```

Variante: drei Karten getauscht (Wight of Precinct Six → Cultivate, Grave Upheaval → Swords to
Plowshares, Wilderness Elemental → Beast Within), absichtlich alphabetisch gelistet und dann mit
`paired_series._align_variant_file` ausgerichtet. Vor der Ausrichtung stimmte 1 von 99 Slots mit
der Basis überein, danach 96 von 99.

| Größe | Wert |
|---|---|
| Paare gespielt / auswertbar / zensiert | 40 / 37 / 3 (4 fehlgeschlagene Partien, siehe 2.4) |
| Status der Serie | `NOT_DECIDED`, `stop_reason: CENSORING_LIMIT` (7,5 % zensiert > 5 %) |
| Siegquote Basis / Variante (Sitz 0) | 43,2 % / 37,8 % |
| Differenz | −5,4 Prozentpunkte, 95 %-Intervall −16,4 bis +5,6 |
| **diskordante Paare** | **4 von 37 = 10,8 %** (Wilson-95 %: 4,3 bis 24,7 %) |
| diskordant, wären die Partien unabhängig | 48,4 % |
| Varianz je Paar gepaart / unabhängig | 0,105 / 0,481, **Verhältnis 4,6** |
| Streuung der Paardifferenz | 0,329 (Planungswert im Code: 0,63) |
| eigene Starthand in beiden Armen gleich | 33 von 37 = 89 % |
| Starthände der Gegner gleich | 37 von 37 |
| ganze Partie identisch (gleicher Transkript-Hash) | 17 von 37 = 46 % |
| Sieger gleich | 32 von 37 |
| gemeinsamer Anfang der Frame-Folge | Median 56 %, Quartile 1 % / 56 % / 100 % |
| diskordant bei gleicher / verschiedener Starthand | 2 von 33 / 2 von 4 |

Was das trägt und was nicht:

- Die Slot-Ausrichtung wirkt: fast neun von zehn Paaren beginnen mit derselben Hand, knapp die
  Hälfte verläuft vollständig gleich. Ein Paar kostet zwei Partien, liefert aber etwa so viel wie
  4,6 unabhängige Paare. Das Intervall der Diskordanz ist breit; am oberen Rand (24,7 %) bliebe ein
  Faktor von etwa 2.
- Das gilt für ein Deckpaar mit drei Tauschkarten, Sitz 0, einen Tisch. Bei mehr getauschten Karten
  sinkt der Anteil gleicher Hände (bei drei Karten rechnerisch 80 % für sieben gezogene Karten).
  Eine allgemeine Zahl ist UNKNOWN.
- **Planung:** `planned_detectable_difference_pp` rechnet mit Paar-Streuung 0,63 („pairing
  correlation unmeasured“). Mit 0,329 bräuchte dieselbe Trennschärfe (0,329/0,63)² = 27 % der
  Paare. Das ist eine Planungsgröße; die Entscheidungsregel (Cluster-t, O'Brien-Fleming-Looks,
  Zensurgrenze) bleibt unberührt. Vorschlag: gemessene Streuung als Bandbreite neben dem
  konservativen Wert ausweisen, gestützt auf mehrere Deckpaare.
- **Sequentielle Stopp-Regel:** vorhanden. In diesem Lauf entschied nicht die Statistik, sondern die
  Zensurgrenze. Solange 5 % der Partien an diesem Tisch hängen bleiben, enden Serien hier ohne
  Antwort; das ist der dringendste Punkt für die Aussagekraft.
- **Gemeinsame Zufallszahlen über Varianten hinweg:** Weil Partien deterministisch sind (424/424),
  ist die Basis-Partie eines Seeds für jeden weiteren Vergleich gegen dieselbe Basis dieselbe. Sie
  muss nicht neu gespielt werden, wenn Schlüssel (JAR-SHA, Pilot- und Policy-Version, Deck-Hashes in
  Sitzreihenfolge, Seed, skip-Einstellung) übereinstimmen. Das halbiert die Partien jedes weiteren
  Vergleichs. Nicht gebaut, nicht gemessen; Mehrfachvergleiche gegen eine Basis brauchen eine
  Aussage zur Fehlerrate (Statistik-Review).
- **Nicht empfohlen ohne Beweis:** die Varianten-Partie auslassen, wenn die getauschten Karten in
  der Basis-Partie nie berührt wurden. Der Pilot leitet seinen Deckplan aus der Liste ab; ob die
  Partie dann identisch wäre, lässt sich ohne Engine-Unterstützung nicht beweisen (UNKNOWN).

## 5. PLAY: Gegner-KI schnell ohne Qualitätsverlust

Messung: Vierer-Partie Seed 21, Mensch auf Sitz 0 als deterministisches Testskript (`_ActiveScript`
des Echt-Engine-Tests, ein Mulligan; kein Pilot, keine Stärkeaussage), nur über `/api/games`,
`/api/play/{id}` und `/api/play/{id}/decision`, KI-Pause 0, Fremdlast 0,03. Befehl:
`python3 tools/play_meas.py p_def 21 precon/2016/open_hostility 1 <Kopie>`; zweiter Lauf `p_skip`
mit `COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="java -XX:+UseSerialGC -Dh2.bindAddress=127.0.0.1
-Dcommanderlab.fullGame.skipForcedDecisions=true -Xmx3g -jar <JAR> full-game"`. Je Konfiguration
eine Partie; die Verteilungen haben n = Entscheidungen dieser Partie.

### 5.1 Latenz je Entscheidung

| Größe | Standard-Befehl | mit skip + SerialGC |
|---|---|---|
| Frames gesamt | 1.801 | 1.183 |
| Entscheidungen des Menschen | 346 (297 Priorität = 86 %) | 346 |
| KI-Frames | 1.455 | 837 |
| Start bis erste Entscheidung des Menschen | 6,3 s | 5,9 s |
| Partie ohne Denkzeit und ohne Pause | 15,9 s | 14,6 s |
| POST einer Antwort (Engine verarbeitet, nächster Status steht): Median / p95 / max | 10,6 / 19,4 / 125 ms | 14,2 / 25,2 / 148 ms |
| Lücke bis zur nächsten Entscheidung des Menschen: Median / p95 / max | 20,4 / 81,5 / 174 ms | 11,0 / 65,5 / 179 ms |
| KI-Entscheidungen je Lücke: Mittel / p95 / max | 2,85 / 9 / 18 | 1,38 / 7 / 17 |
| KI-Zeit je KI-Entscheidung: Median / p95 | 8,2 / 14,3 ms | 11,6 / 20,5 ms |
| Summe KI-Zugzeit der Partie | 8,9 s | 6,5 s |
| GET des Zustands (`count=0`): Median / p95, Größe | 3,9 / 8,9 ms, 14 KB | 3,8 / 8,7 ms, 15 KB |
| eine Seite mit 1.000 Frames | 128 ms, 2,4 MB | 178 ms, 3,5 MB |
| Ergebnis | Sieger Sitz 3, 1.801 Entscheidungen, Hash 1de59311… | dasselbe |

POST nach Klasse (Standard-Befehl; Median / p95 in ms): Priorität n=297 10,5 / 19,4; Mana n=36
11,3 / 17,1; Ziel n=4 11,5 / 13,8; Angreifer n=2 12,4; Blocker n=1 11,9; Mulligan n=2 68 / 125.
Die Klassen mit n < 10 sind Einzelbeobachtungen, keine Verteilung.

Die Maschine antwortet also in 10 bis 20 ms. Wartezeit des Menschen an der Engine: 13 s je Partie.

### 5.2 Wo die Zeit verschenkt wird

| Quelle | Beleg | Kosten je Partie (diese Partie) |
|---|---|---|
| **KI-Pause je KI-Entscheidung** (`ai_delay_ms`; Sitzung 250 ms, die Seite setzt beim Öffnen den Reglerwert 500 ms) | `play.py` `_wait_ai_delay`, `partie.js` Zeilen 1323 und 1523 | 1.455 × 0,5 s = **727 s**; bei 250 ms 364 s; bei „sehr schnell“ (50 ms) 73 s |
| davon erzwungene KI-Pässe | 618 der 1.455 KI-Frames (42 %) haben eine einzige Option | 309 s bei 500 ms |
| davon KI-Prioritäts-Pässe insgesamt | 1.058 der 1.455 KI-Frames | 529 s bei 500 ms |
| davon Mana-Schritte der KI (jede Quelle ein Frame) | 199 | 100 s bei 500 ms |
| **Polling** der Seite: 400 ms ohne offene Entscheidung, 1.500 ms mit, 150 ms beim Vorspulen | `partie.js` `follow()` | 283 Lücken mit KI-Zügen × 0,4 s = **113 s** bei Pause 0; beim Vorspulen 42 s |
| HTTP je Antwort des Menschen | `submitHumanChoice`: ein POST, danach ein GET | 346 × (12 + 4 ms) = 5,5 s |
| Frames serialisieren, Schwärzung (`redact_*`, `deepcopy`) | im GET enthalten | 3,9 ms je Abfrage: kein Hebel |
| JVM-Kaltstart der Partie | 6,3 s bis zur ersten Entscheidung | 6,3 s einmalig |

Rechenwerte: Zahl × Dauer, nicht im Browser gestoppt. Die Denkzeit des Menschen ist nicht Teil der
Messung (UNKNOWN).

### 5.3 Pässe des Menschen, Vorspulen, Auto-Pass

Von 346 Entscheidungen des Menschen waren 297 Prioritätsfragen. Was die vorhandenen Regeln der Seite
davon abnehmen würden (dieselben Prüfungen wie `vorspulen.js` und `maybeAutoPassHuman`, nur gezählt):

| Regel | Entscheidungen | Anteil |
|---|---|---|
| einzige Option ist Passen (erzwungen) | 68 | 20 % |
| Auto-Pass-Kästchen der Seite (nur Passen möglich, oder fremder Zug mit leerem Stapel) | 196 | 57 % |
| Vorspulen, hält bei Gegner-Objekt auf dem Stapel | 181 | 52 % |
| Vorspulen ohne diesen Halt | 226 | 65 % |
| Vorspulen hält: eigener Zug beginnt / andere Klasse / Gegner-Objekt | 71 / 49 / 45 | |

„Vorspulen nur mit der Pass-Option“ (Owner, 17.11.) nimmt dem Menschen also gut die Hälfte der
Klicks ab. Jeder dieser Pässe läuft heute über die Seite: Abfrage im 150-ms-Takt, POST, GET. Das
sind 181 × etwa 0,17 s = 30 s je Partie nur für den Transport. Würde die Sitzung auf dem Server mit
derselben Regel antworten (ausschließlich die von der Engine angebotene Option `pass_priority`,
serverseitig geprüft, keine Regelrechnung), entfiele der Transport: 181 × 12 ms = 2 s.

Die Bridge selbst überspringt Pässe von Mensch-Sitzen nie (Bedingung 5). Das zu ändern wäre eine
BEHAVIOUR-Änderung unter dem Studio-Bridge-Gate und ist nicht nötig: der Server kann die einzige
angebotene Option selbst senden.

### 5.4 Tempo-Regler (Owner-Entscheid P2)

Fakten für den Entscheid: Die KI braucht keine Pause, um richtig zu spielen; die Pause dient nur dem
Mitlesen. Sie gilt heute für jede KI-Entscheidung gleich, auch für erzwungene Pässe und einzelne
Mana-Schritte, an denen sich für den Zuschauer nichts ändert. Mit `skipForcedDecisions` bleiben 837
KI-Frames; pausiert man zusätzlich nur bei Frames, die keine Pässe und keine Mana-Schritte sind,
bleiben in dieser Partie 198 (1.455 − 1.058 − 199), also 99 s statt 727 s bei 500 ms. Welche
Schritte „sichtbar“ heißen sollen, ist eine Produktfrage; die Zählung liefert nur die Größenordnung.
Auswahl der Schritte allein nach Feldern, die die Engine veröffentlicht (Klasse, gewählte Option).

## 6. Maßnahmen-Rangliste

Gewinn auf dieser Maschine und diesem Tisch. „Äquivalenz“ nennt den Nachweis aus Abschnitt 3.
MATERIAL = ändert Ergebnisse, Standards oder Owner-Vorbehalte.

### 6.1 Reine Konfiguration (sofort, auch am Owner-PC)

| # | Maßnahme | Gewinn | Risiko | Äquivalenz | Gate | MATERIAL | Owner-Gate | Aufwand |
|---|---|---|---|---|---|---|---|---|
| K1 | Batch-Serien mit `--games-per-jvm 16` bis `24` statt 6 | CPU je Partie 24,8 (Modell) → 18,3 (gemessen, G=16): −26 %; an der CPU-Grenze +36 % Spiele/h | Fortschritt erscheint erst je Chunk; ein Hänger verwirft die JVM; Speicher bei G=24 ungemessen | 16/16 (f_g16), Teil der 424/424 | PERF-Messung am Owner-PC | nein | nein | 0 |
| K2 | `--workers` = Kernzahl, wenn der PC sonst ruht | W=4 gegen W=3: 595 gegen 533 (+12 %, je n=1, ruhig) | unter Fremdlast langsamer (460 gegen 507) | 424/424 | PERF | nein | nein (Nutzung des PCs) | 0 |
| K3 | AppCDS bauen (`build-appcds`) | −2,6 s je JVM-Start; PLAY-Start kürzer (nicht gemessen) | 322 MB Platte; Archiv passt nur zum JAR | 4/4 Digest, 16/16 Hash | keins | nein | nein | 24 s |
| K4 | PLAY mit `skipForcedDecisions=true` und SerialGC über `COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD` | −42 % KI-Frames; −309 s Pause je Partie bei 500 ms; RAM 850 statt 1.166 MB | erzwungene KI-Pässe erscheinen nicht mehr als Frames (Titel nennt die Zahl); die Variable gilt dann auch für Einzelpartien | gleicher Hash, 1.183/1.183 Frames, 346/346 Mensch-Frames (eine Partie) | keins (Flag #1421 existiert) | nein | **ja: Flag für PLAY freigeben** | 0 |
| K5 | Tempo-Regler auf 50 ms stellen (vorhanden) | 727 s → 73 s Pause je Partie | Züge der KI kaum mitzulesen | entfällt (Anzeige) | keins | nein | nein | 0 |

### 6.2 Python und JavaScript (agent-ready nach Claim)

| # | Maßnahme | Gewinn | Risiko | Äquivalenz | Gate | MATERIAL | Owner-Gate | Aufwand |
|---|---|---|---|---|---|---|---|---|
| A1 | Gepaarte Serie: langlebige Worker-JVMs über Look-Fenster hinweg, Arbeit aus einer Warteschlange, Prozesse statt Threads | 350 → Richtung 595 Spiele/h (+70 % Obergrenze); CPU 33,5 → etwa 18 bis 23 s | Fehlerisolierung und Abbruch neu zu prüfen; Reihenfolge der Auswertung darf sich nicht ändern | Position in der JVM und Pfad ändern nichts (424/424) | Tests + PERF; Identität 36/36 gegen den heutigen Pfad | nein | nein | M |
| A2 | Fortschritt und Abschluss je Partie statt je Chunk (`on_game` während `run_batch`) | macht K1 bedienbar; Abbruch verliert weniger | gering | keine Wirkung auf das Spiel | Tests | nein | nein | S |
| A3 | Default `DEFAULT_GAMES_PER_JVM` 6 → 16 (nach A2 und Owner-PC-Messung) | wie K1 für alle Serien | wie K1 | wie K1 | PERF | nein | Lead | S |
| A4 | Basis-Partien wiederverwenden (Schlüssel: JAR-SHA, Pilot/Policy, Deck-Hashes in Sitzfolge, Seed, skip) | bis −50 % Partien je weiterem Vergleich gegen dieselbe Basis | falscher Schlüssel = falsche Partie; Mehrfachvergleich | Determinismus 424/424 | Tests + Statistik-Review | **ja** (Auswertungsweg) | Lead/Owner | M |
| A5 | Planung: gemessene Paar-Streuung als Bandbreite neben 0,63 | Budgets bis 3,7-fach kleiner planbar | ein Deckpaar ist keine Regel; mehrere Paare nötig | entfällt | Statistik-Review | **ja** (Planungsstandard) | Lead/Owner | S |
| A6 | PLAY: interaktive Partie startet mit Serien-Schaltern (wie K4, im Code) | wie K4 ohne Umgebungsvariable | wie K4 | wie K4 | Tests | nein | **ja** (wie K4) | S |
| A7 | PLAY: Pause nur für sichtbare KI-Schritte, Stufe „ohne Pause“, Default neu | 727 s → etwa 99 s (bei 500 ms) oder 0 | Auswahl der Schritte ist Produktentscheid | entfällt (Anzeige) | Tests | nein | **ja** (P2) | S |
| A8 | PLAY: Server meldet neue Entscheidungen sofort (Long-Poll oder Server-Sent Events) statt 400-ms-Abfrage | −113 s je Partie bei Pause 0; −42 s beim Vorspulen | Verbindungsabbruch, Rückfall auf Abfrage nötig | entfällt | Tests | nein | nein | M |
| A9 | PLAY: Vorspulen und Auto-Pass auf dem Server, nur mit der angebotenen `pass_priority`-Option | −30 s Transport je Partie; 181 bis 226 von 346 Klicks | Halt-Regeln müssen dieselben bleiben; nie eine andere Option | Antwort ist dieselbe Option wie heute vom Client | Tests | nein | durch Owner-Entscheid 17.11. gedeckt, Halt-Regeln bestätigen | M |
| A10 | Auswertungen des `event_log` reihenfolgefest machen (gleichzeitige Ereignisse sortieren) | Reproduzierbarkeit | keins | behebt die Abweichung in Abschnitt 3 | Tests | nein | nein | S |

### 6.3 Bridge (nur Vorschlag; Studio-Bridge-Gate; Fork-Push, Repin, Versiegelung beim Owner)

| # | Vorschlag | Messbeleg | Gewinn | Gate | MATERIAL | Owner-Gate |
|---|---|---|---|---|---|---|
| B1 | Hänger nach `declare_attackers` beheben (75-s-Settle-Timeout) | 4 von 80 Partien, reproduzierbar mit Seed 1033 und 1024 am Tisch dieses Berichts, je 89 bis 96 s und 113 bis 126 CPU-s; Serie endet `CENSORING_LIMIT` | −11 % Worker-Zeit; Serien werden auswertbar | BEHAVIOUR | **ja** (bisher fehlgeschlagene Partien bekämen ein Ergebnis) | ja |
| B2 | Reihenfolge gleichzeitiger Ereignisse im `event_log` festlegen | 1 bis 25 Varianten je Seed | Reproduzierbarkeit | BEHAVIOUR (nur Protokoll) | nein | ja |
| B3 | Aufwärmen verkürzen über die JVM (neueres JDK mit AOT-Cache) | 64 CPU-s je JVM-Leben | UNKNOWN: hier nur JDK 21, nichts gemessen | PERF + Identität | nein | ja (Toolchain) |
| B4 | Zustandskopien der Spielbarkeits-Prüfung | nur Vorbefund #1298, hier nicht nachgemessen | UNKNOWN | BEHAVIOUR-Risiko im Regelkern | ja | ja |

Nicht empfohlen: C1-Übersetzer (+50 % Wandzeit), kleinere Frames in der Bridge (Vorbefund #1264 ohne
Gewinn, hier nicht widerlegt), Pilot-Abkürzungen jeder Art.

## 7. Messprotokoll für den Owner-PC (Windows, PowerShell)

Ziel: Durchsatz und Identität am echten Gerät, etwa 45 Minuten. Nichts anderes rechnen lassen.

1. Gerät notieren:
   `Get-CimInstance Win32_Processor | Select Name,NumberOfCores,NumberOfLogicalProcessors`,
   `(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory`, `java -version`.
2. Variable setzen: `$JAR = "<Studio-Datenordner>\engine\xmage-engine-bridge.jar"`; Prüfsumme mit
   `Get-FileHash $JAR -Algorithm SHA256` notieren.
3. Sechs Zellen, jede mit denselben 48 Seeds. K = Zahl der physischen Kerne.

   | Zelle | Worker | Partien je JVM |
   |---|---|---|
   | ref | 1 | 8 |
   | a | K/2 (abgerundet) | 8 |
   | b | K − 1 | 8 |
   | c | K | 8 |
   | d | K − 1 | 24 |
   | e | K | 24 |

   Befehl je Zelle (im Repo-Ordner; `<W>`, `<G>`, `<Zelle>` einsetzen):

   ```
   Measure-Command { python scripts/benchmark_xmage_full_games.py run --jar $JAR --out <Zelle>.json `
     --seeds 1-48 --workers <W> --games-per-jvm <G> --fast --private-card-repository `
     --jvm-option=-Dcommanderlab.fullGame.skipForcedDecisions=true --frame-digest-skip-forced }
   ```

   Vor jeder Zelle `Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 1 -MaxSamples 5`
   (soll unter 5 % liegen) und den Wert notieren. Zelle b zweimal fahren (Streuung).
4. Auswertung je Zelle: Spiele/h = 3600 × 48 / `total_wall_s` aus der JSON-Datei; s/Partie =
   `total_wall_s` / 48; RAM aus dem Task-Manager (Summe `java` + `python`) als Spitzenwert notieren.
   CPU-Sekunden liefert das Skript unter Windows nicht (UNKNOWN dort).
5. Identität jeder Zelle gegen die Referenz:
   `python scripts/benchmark_xmage_full_games.py compare ref.json <Zelle>.json --expect-games 48`.
   Erwartet: `identical 48/48` und `frames identical 48/48`, Exit-Status 0. Jede Abweichung ist ein
   Befund und beendet die Messung für diese Zelle.
6. Zurückmelden: die Tabelle (Zelle, W, G, Wandzeit, Spiele/h, RAM, Last vorher, Identität) und die
   sechs JSON-Dateien. Der Tisch dieses Skripts ist der „real“-Tisch des Repos, nicht der
   Precon-Tisch dieses Berichts; absolute Zahlen sind deshalb nicht mit Abschnitt 2 vergleichbar,
   wohl aber die Verhältnisse zwischen den Zellen.

Für PLAY am Owner-PC: eine Partie mit Regler „sehr schnell“ und eine mit der Variable aus K4 spielen
und im Titel der Partie die Zahl „(+ N erzwungene Pässe)“ ablesen.

## 8. Grenzen und UNKNOWN

- Eine Maschine, ein Tisch (vier Precons), Seeds 1 bis 8 für die Matrix. Andere Decks ergeben andere
  Partielängen; die Verhältnisse (G-Effekt, W-Effekt) sind belastbarer als die absoluten Zahlen.
- Zellen sind meist Einzelläufe mit n = 8 bis 32 Partien; wiederholt wurden W=1/G=8 (3×), W=3/G=8
  (2× Batch, 1× Thread), W=4/G=8 (2× Batch, 2× Thread). Streuung zwischen Wiederholungen bei
  ruhiger Maschine: W=1 2 %; für W=4 Thread 5 %; Batch ruhig nur n=1.
- Der erste Messblock lief unter Fremdlast; betroffen sind vor allem m_w2_g8, m_w3_g8, m_w4_g8,
  m_w1_g1, m_w1_g4, m_w3_g4, m_w4_g4.
- UNKNOWN: Owner-PC; G=24 und Speicher über viele Partien; G1 unter Volllast; kleineres `-Xmx`;
  Anteile der fünf Ursachen im gepaarten Pfad; Ursache des Engine-Hängers; ob das `event_log` immer
  nur vertauscht ist; Diskordanz bei anderen Deckpaaren; Wartezeit im echten Browser; Denkzeit.
- Nicht nachgemessene Vorbefunde: #1264 (schlanke Bridge), #1298 (Zustandskopien), #1251 (541/h).
- PLAY: eine Partie je Konfiguration, Mensch als Testskript.

## 9. Artefakte und Aufräumen

- Rohdaten (JSON je Zelle, Phasen, Paar-Auswertung, PLAY) und Messskripte:
  `/tmp/claude-0/-home-user/ef006e8b-893c-5ebd-80a1-8743a09c7458/scratchpad/costudio/eff_sim_play_data/`.
- Issue-Entwürfe:
  `/tmp/claude-0/-home-user/ef006e8b-893c-5ebd-80a1-8743a09c7458/scratchpad/costudio/eff_sim_play_issues.json`.
- Aufgeräumt: Worktree `wt_eff_b` entfernt; eigene Kopie des Studio-Ordners, Kartendatenbanken der
  Worker-Slots (1,6 GB), AppCDS-Archiv (322 MB) und alle Partie-Logs der Messung gelöscht. Frei danach:
  9,0 GB. Der ursprüngliche Ordner `play_store` wurde nicht beschrieben.
