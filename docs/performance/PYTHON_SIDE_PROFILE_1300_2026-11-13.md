# Issue #1300 (E5) Schritt 1: Python-Seite je Entscheidung messen

- **Datum:** 2026-11-13
- **Art:** Schritt 1 von #1300 — nur Messen. Keine Umsetzung, kein Produktcode
  geändert, kein Push, kein PR. (Die Umsetzung von Schritt 2+ folgt erst nach
  dem #1267-/#1304-Merge, wie im Claim auf #1300 angekündigt.)

## Messstand (Lesson 19)

- **Lab-Stand:** `dc7ccaa11` (Merge PR #1281, 2026-11-13) = aktuelles
  `origin/main` zum Messzeitpunkt (per `git fetch` verifiziert), frischer
  Worktree `wt-1300` auf exakt diesem Commit.
- **Engine-Pin:** `f4d12f6e8066203fba7aa38bd35ea3358117393d` (v15,
  `config/rules_engines.json`).
- **Bridge-JAR:** `wt-1298/engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar`,
  SHA256 `1bb1bdd6f7833ce02781174bd78005f7fdf25959aad0405e1de7d024605136a2`
  (auf `dc7ccaa11` gebaut; `git diff dc7ccaa11..origin/main -- engine-bridge/`
  ist leer, das JAR ist also auf dem Messstand aktuell).
- **Messpfad = Studio-Pfad, wie #1300 ihn beschreibt:**
  `BatchRecordingRunner` (aus `scripts/measure_throughput_steady_state.py`
  wiederverwendet, Treiber `run_python_profile_1300.py` im Rohverzeichnis) →
  `XmageFullGameRunner._drive` mit scharfem Hidden-Information-Audit →
  `RecordingPolicy.decide` → Pilot (`full_game_pilot`) + `GameRecorder.record`
  → `frame_of` → `_write` (`json.dumps` + `flush()` je Frame). Der optionale
  Frame-Digest (#1271) wird in diesem Serien-Pfad nicht berechnet
  (`run_batch` fährt `_drive` ohne `progress`-Liste; CODE_DERIVED) — sein
  Kostenanteil hier ist 0.
- **Tisch:** echter Vierer-Tisch wie #1279/#1281 — Chulane
  (`data/decks/deckbau/chulane_current.json`) gegen Lorehold Spirit,
  Animated Army, Token Triumph. Seeds 1–8, `--workers 1 --games-per-jvm 8
  --fast` (SerialGC, `-Xmx3g`), **eine** JVM für alle 8 Partien.
- **Hardware/Caveat:** diese VM — 4 geteilte, gedrosselte Kerne
  (1,5 Shared-CPUs), ~7,9 GB RAM. **Nur die Verteilung (Anteile) ist
  belastbar; absolute Zeiten sind VM-Werte.** Zweiter Caveat: cProfile
  bläht die Python-CPU um den Faktor **2,57** auf (gemessen: profilierter
  Lauf 268,8 s Python-CPU gegen 104,4 s im identischen unprofilierten Lauf).
  Die Töpfe unten sind Kumulativzeiten des profilierten Laufs; ihre
  *Anteile* sind der Befund, nicht ihre absoluten Sekunden.

## Methode

1. **Smoke (Pflicht vor der Vollkette):** 1 Partie, Seed 1, unter cProfile.
   Ergebnis: `finished`, 3.193 Entscheidungen, semantischer Hash
   `1009e97ca3ea9f10aa9d2f011b78a248029b54553d2cc7d610ac5e162d798b61`
   = exakt die #1281-Referenz; Profil lesbar, alle Anker vorhanden
   (Pilot-`decide`, `record`, `audit_actor_scoped_frame` je 3.193 Aufrufe =
   Entscheidungszahl).
2. **Vollkette profiliert:** 8 Partien in einer JVM unter
   `python -m cProfile`. Identität: **8/8** Hashes und Entscheidungszahlen
   exakt wie die #1281-Referenz (`raw_games.csv`, Lauf `jfr_1w_12g`),
   zusammen **37.626 Entscheidungen**.
3. **Vollkette unprofiliert (Begleitlauf, gleicher Treiber ohne cProfile):**
   Identität zu beiden anderen Läufen identisch (8/8). Liefert die ehrliche
   Prozess-Zerlegung ohne Profiler-Aufschlag.
4. **Topf-Regeln (vor der Zählung festgelegt, jede Funktion in genau einem
   Topf):**
   - **Audit** = Kumulativzeit von `audit_actor_scoped_frame`
     (`full_game.py`), je Entscheidung in `_drive` aufgerufen; sein Unterbaum
     enthält weder Pilot- noch Recorder-Aufrufe.
   - **Pilot** = Kumulativzeit von `full_game_pilot/policy.py: decide`
     (Einlass des Piloten; Unterbaum = alle Pilot-Module inkl. des
     Zustands-SHA-256 in `choices.py`).
   - **Recorder** = Kumulativzeit von `GameRecorder.record` (Unterbaum inkl.
     `frame_of` und `_write`) + `close` + `save_event_log` (disjunkt zu
     `record`).
   - **JSON-Lesen** = Kumulativzeit von `json.loads` **nur** mit direktem
     Aufrufer `_RawFullGameClient.request` (`full_game.py`) — die
     Bridge-Antworten — aus der Caller-Tabelle von pstats.
   - **Rest** = Python-Prozess-CPU des Laufs minus Töpfe (1)–(4).
   - Quercheck der Disjunktheit: `RecordingPolicy.decide` (der gemeinsame
     Eltern-Knoten von Pilot und Recorder) hat Kumulativzeit 254,13 s;
     Pilot + Recorder = 253,74 s; Differenz 0,39 s = seine eigene Zeit. ✓

## Ergebnis

### Prozess-Zerlegung (unprofilierter Lauf, DIRECTLY_VERIFIED)

| Anteil | gesamt (8 Partien) | je Partie |
|---|---:|---:|
| Wandzeit | 502,7 s | 62,8 s |
| Python-Prozess-CPU | 104,4 s | 13,1 s |
| JVM-CPU (Kindprozesse) | 445,1 s | 55,6 s |
| Residuum (Wand − Python − JVM) | −46,9 s | — |

Das negative Residuum heißt: Es gibt **keine zusätzliche Leerlauf-Wartezeit**
auf Prozessebene — Python- und JVM-Arbeit überlappen (Pump-Threads, mehrere
JVM-Threads) und sättigen die Wandzeit vollständig. Die Zeit, die der
Python-Hauptthread in `client.request` auf die Bridge-Antwort wartet
(profiliert abgeleitet: 432,3 s von 451,9 s `request`-Kumulativzeit), ist
die Rechenzeit der JVM selbst und steckt bereits in der JVM-CPU oben —
sie ist **kein** Python-Topf und darf nicht doppelt gezählt werden.

### Python-Töpfe (profilierter Lauf, 37.626 Entscheidungen, DIRECTLY_VERIFIED als Profil-Anteile)

Python-CPU des Laufs (process_time, profiliert): 268,8 s ≙ 33,6 s je Partie
≙ 7,14 ms je Entscheidung. Anteile an dieser Python-CPU:

| Topf | gesamt | je Partie | je Entscheidung | Anteil an Python-CPU | > 5 %? |
|---|---:|---:|---:|---:|:--|
| **Pilot** (`full_game_pilot`) | **192,4 s** | 24,05 s | 5,11 ms | **71,6 %** | **JA** |
| **Recorder** (`GameRecorder`) | **61,3 s** | 7,67 s | 1,63 ms | **22,8 %** | **JA** |
| **JSON-Lesen Bridge-Antworten** (`json.loads` aus `request`) | **17,2 s** | 2,15 s | 0,46 ms | **6,4 %** | **JA (knapp)** |
| Audit (`audit_actor_scoped_frame`) | 2,8 s | 0,35 s | 0,07 ms | 1,0 % | NEIN |
| Rest (s. u.) | −5,0 s | −0,62 s | — | −1,9 % | — |
| **Summe Töpfe** | 273,8 s | 34,2 s | | 101,9 % | |

Zum Rest: Die Töpfe sind cProfile-*Kumulativzeiten* (verstrichene Zeit je
Aufruf, inkl. Profiler-Overhead und Entschedulung auf der gedrosselten VM),
der Nenner ist Prozess-*CPU*-Zeit. Dass die Topf-Summe den Nenner um 1,9 %
übersteigt, ist dieser Methodenunterschied; der echte Rest
(`_drive`-Schleife, Request-Hüllkurve samt `json.dumps` der Anfragen
= 1,2 s, Deck-Laden, Runner-Setup) ist von 0 nicht unterscheidbar und liegt
sicher unter 2 %. Das Schwellen-Urteil ist unter beiden Nennern identisch
(gegen die Topf-Summe 273,8 s: Pilot 70,3 %, Recorder 22,4 %,
JSON-Lesen 6,3 %, Audit 1,0 %).

### Wo die Töpfe innen sitzen (Kumulativzeiten, verschachtelt — nicht addierbar)

- **Pilot:** `_decide_priority` 89,1 s (25.863 Prioritäts-Entscheidungen);
  `_pilot_state` (state.py, Zustands-Neuableitung) 81,3 s (17.774 Aufrufe);
  Mana-Zahlungs-Komplex `_decide_mana` 46,3 s / `_complete_payment` 46,0 s mit
  `payment_plan.solve` 33,8 s (946.152 Aufrufe; darin `is_land_entry`
  11,0 Mio. Aufrufe); Views `player_threat` 63,5 s (131.961 Aufrufe),
  `entry_value` 45,6 s (2,04 Mio. Aufrufe). Der in #1300 vermutete
  Zustands-SHA-256 (`choices.py`, `json.dumps(state, sort_keys=True)` +
  `hashlib.sha256` im `_decide_boolean`-Pfad) ist dagegen **vernachlässigbar:
  0,002 s** — er läuft nur im Boolean-Pfad und ist kein Hebel.
- **Recorder:** `frame_of` 47,4 s von 61,3 s (77 %) — der Sicht-Bau je Frame
  (Spieler/Zonen/Karten) ist der Recorder-Block, nicht das Schreiben;
  `_write` (`json.dumps` + `flush()` je Frame) 10,0 s; `close`/gzip in diesem
  Batch-Pfad 0 s (die Logs werden vom Treiber verworfen; der gzip-Abschluss
  gehört zum Serien-Wrapper `play_recorded_games`, hier nicht gefahren).
- **JSON-Lesen:** `json.loads` gesamt 17,5 s, davon 17,2 s mit Aufrufer
  `client.request` — praktisch alles sind Bridge-Antworten.
- **Audit:** 2,8 s bei 37.626 Aufrufen — trotz Vollprüfung je Frame klein,
  weil er nur über die schon gebauten Frame-Daten läuft.

### Übertragung auf den unprofilierten Lauf (MODELED, keine Messung)

Trüge man die Profil-Anteile auf die unprofilierte Python-CPU (13,1 s je
Partie) über, ergäben sich je Partie ≈ Pilot 9,4 s, Recorder 3,0 s,
JSON-Lesen 0,8 s, Audit 0,1 s. Der Profiler-Aufschlag ist aufrufzahl-abhängig
und damit topfweise verschieden; diese Werte sind eine Einordnung, keine
Messung. Am Schwellen-Urteil ändert die Übertragung nichts.

## Schwellen-Urteil für die Umsetzung (Schritt 2+, #1300 Punkt 4)

> **Überholt (2026-11-14).** #1300 ist entschieden und geschlossen. Die 5-%-Schwelle gilt
> für die Laufzeit einer Partie, nicht für den Anteil an der Python-CPU. Gegen die Laufzeit
> gerechnet ergeben die Zahlen dieses Berichts: Pilot rund 14,9 %, Recorder rund 4,7 %,
> JSON-Lesen rund 1,3 %. Die gleichheitsgeprüften Piloten-Änderungen sparten gemessen rund
> 1 s von 216 s und wurden nicht gemergt; der Rahmen-Digest des Messwerkzeugs ist mit #1317
> beschleunigt. Die folgende Einstufung „optimierbar“ ist deshalb keine Arbeitsanweisung.

Nach der 5-%-Regel aus #1300 darf später nur an Töpfen über 5 % optimiert
werden:

1. **Pilot (71,6 %) — optimierbar.** Größte Innen-Posten: wiederholte
   Zustands-Ableitung (`_pilot_state`) und die Bewertungs-Views
   (`player_threat`, `entry_value`) sowie der Zahlungs-Solver. Punkt 4 von
   #1300 (Ableitungen je Frame zwischenspeichern, ohne die Wahl zu ändern)
   zielt auf den gemessenen Block. Der Zustands-Hash ist **kein** Hebel
   (0,002 s).
2. **Recorder (22,8 %) — optimierbar.** Der Hebel sitzt in `frame_of`
   (47,4 s), erst danach im Schreiben/`flush()` (10,0 s). Das in #1300
   geplante `log_detail: summary` (Punkt 2) und die Pufferung (Punkt 3)
   adressieren den kleineren Teil (Schreiben); für `frame_of` heißt
   „leichtes Protokoll" konkret: Frames gar nicht erst bauen, die
   `summary` nicht braucht — Bau und Schreiben fallen dann gemeinsam weg.
3. **JSON-Lesen (6,4 %) — knapp über der Schwelle, optimierbar nur im
   Rahmen von Punkt 5** (Standardbibliothek/vorhandene Abhängigkeiten).
   Absolut ist es der kleinste der drei Hebel.
4. **Audit (1,0 %) — unter der Schwelle: nicht anfassen.** Eine
   Beschränkung der Prüfung ist nach #1300 Punkt 4 ohnehin verboten, wenn
   sie die Prüfung abschwächt; die Messung gibt auch keinen Grund dazu.

Einordnung gegen die Gesamtpartie (unprofiliert): Python-CPU 13,1 s von
62,8 s Wandzeit je Partie (20,8 %); JVM-CPU 55,6 s. Selbst vollständiges
Wegfallen von Recorder + JSON-Lesen senkte die Wandzeit nur, soweit der
Python-Hauptthread der Engpass ist — die Partie ist überwiegend
JVM-gebunden; der E5-Gesamthebel bleibt kleiner als die Bridge-/Kopier-Hebel
aus #1264/#1298. Das deckt sich mit #1251 (Pilot dort 10,5 % der Wanduhr).

## Evidenzklassen

- Identitätsnachweise (8/8 in beiden Läufen, Smoke 1/1), Prozess-Zerlegung
  des unprofilierten Laufs, Topf-Anteile und Innen-Posten des profilierten
  Laufs, Schwellen-Urteil: **DIRECTLY_VERIFIED** (cProfile/process_time/
  rusage an identitätsgeprüften Partien).
- Frame-Digest-Anteil 0 in diesem Pfad: **CODE_DERIVED** (am Code gelesen:
  `run_batch` ohne `progress`).
- Übertragung der Anteile auf unprofilierte Sekunden je Partie:
  **MODELED** (Profiler-Aufschlag topfweise verschieden).
- Absolute Zeiten/Durchsätze auf dieser VM: nicht behauptet (Caveat oben).
- py-spy: im Venv nicht vorhanden; verwendet wurde ausschließlich cProfile
  (im Briefing als Alternative vorgesehen).

## Rohdaten

`docs/performance/measurements-1300-2026-11-13/`:
- `run_python_profile_1300.py` — Treiber (Smoke/Vollkette, beide Modi)
- `analyze_python_profile.py` — Topf-Auswertung (Regeln im Docstring)
- `smoke_result.json` — Smoke (Seed 1, Hash = #1281)
- `full_result.json` — Vollkette profiliert (8 Partien)
- `plain_result.json`, `plain_comparison.json` — Vollkette unprofiliert +
  Vergleich (Identität identisch, Inflationsfaktor 2,57)
- `buckets.json`, `buckets.csv` — Topf-Tabelle
- `cprofile_top60.txt` — pstats-Auszug (Top 60 kumulativ)
- `pilot_internals.txt` — Innen-Posten des Piloten

Die Profil-Dateien selbst liegen nicht im Repository (`AGENTS.md` §12); `MANIFEST.json` nennt ihre Digests.
