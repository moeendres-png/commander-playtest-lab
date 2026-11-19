# D-2 Entwurf: ein Spiele-Pool als Ausführungsschicht für Serien (Refs #1612, #1585, #1586, #1576)

Stand: 2026-11-19, Lab `origin/main` 14a802bc (Clone, nur gelesen). Art: Entwurf. Kein Engine-Lauf, keine
Suite, nichts gepusht oder kommentiert. Zahlen mit [M] sind Messwerte aus `eff_sim_play.md` (4-Kern-VM,
16 GB, Java 21, JAR 204dd9ad…, ein Tisch), [C] ist aus dem Code abgeleitet (Datei:Zeile), [S] ist Modell
oder Schätzung, [V] ist Vorschlag dieses Entwurfs. Pfade ohne Präfix liegen unter
`src/commander_lab/studio/`; `fg.py` steht für `src/commander_lab/engine/rules/full_game.py`, `Bridge:`
für `engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGameJsonlBridge.java`, `Session:` für
`…/XmageFullGameSession.java`.

## 0. Ergebnis zuerst

1. **Der Pool ist ohne Bridge-Änderung baubar.** Die Java-Seite begrenzt die Partien je JVM nicht nach oben
   (`Bridge:27`: `Math.max(1, Integer.getInteger(...))`), lässt die nächste Partie nach `shutdown_game` zu
   (`Bridge:169-173`), gibt die spielbezogenen statischen Einträge frei (`Session:1310-1314`) und behält
   nur die Decks der laufenden Partie (`Bridge:245`). Die Grenze 24 ist reine Python-Vorgabe
   (`launch.py:40`, `web.py:284/305`, `static/paired.js:478`).
2. **Ein Punkt braucht vor dem Bau einen Entscheid (E-1, MATERIAL): worauf ein Partie-Ergebnis ruht.**
   Heute entsteht ein Ergebnis erst, wenn die JVM, die die Partie spielte, sauber beendet wurde
   (`fg.py:225-227` Literal `graceful_shutdown`, Prüfung `fg.py:1818-1821`, Regeltext `fg.py:1270-1278`).
   Eine JVM, die über Look-Fenster hinweg lebt, kann für den Look kein Ergebnis liefern. Ohne E-1 bleibt
   das JVM-Leben an das Fenster gebunden und das Ziel 560 Partien/h ist bei 10 Paaren je Look rechnerisch
   nicht erreichbar (Abschnitt 2.2).
3. **Neuer Befund [C]: der Web-Standard der gepaarten Serie spielt faktisch eine Partie je JVM.**
   Standard ist Budget 20, Look alle 4 Paare, Sitze rotieren (`web.py:292-299`,
   `paired_series.py:670-673`). Ein Fenster hat dann 4 Einheiten = 1 Seed × 4 Sitze = 8 Partien;
   `plan_look_window_chunks` bildet je (Arm, Sitz) ein eigenes Stück (`paired_comparison.py:799-803`),
   also 8 Stücke mit je 1 Partie: 40 JVM-Leben für 40 Partien. Gemessen sind für eine Partie je JVM
   53,3 CPU-s [M], warm 14,3 [M]. Der Messlauf mit 350 Partien/h hatte Sitz 0 fest und Look 10, also
   5 Partien je JVM; der Web-Standard liegt darunter (nicht gemessen).
4. **Zweiter Befund [C]: eine abgestürzte Batch-Serie ist nicht wiederaufnehmbar.** Der Serien-Datensatz
   wird erst am Ende geschrieben (`simulations.py:1072`), nicht im Fehlerzweig (`:1074-1078`);
   `from_saved_series` verlangt ihn (`:940-942`). Nur beendete oder regulär abgebrochene Serien lassen
   sich fortsetzen. Der gemeinsame Verwalter behebt das nebenbei (Manifest beim Start).
5. **Erwartung [S], nicht gemessen:** gepaart, 40 Paare, 4 Worker, ohne Engine-Hänger als Obergrenze 581 /
   671 / 792 Partien/h bei einem Partien-Budget der JVM von 8 / 16 / 24, mit geschätztem Leerlauf am
   Fensterende 537 / 621 / 733. Das Ziel 560 verlangt also ein Budget von mindestens 16. Mit den vier
   Hängern von #1584 sind es bei Budget 24 nur 515 bis 553, also unter dem Ziel. Die Abnahmezahl hängt
   damit am Budget und am Stand von #1584 (Abschnitt 8).

## 1. Schnittstelle

### 1.1 Aufgabe, Ergebnis, Ereignisse [V]

Neue Datei `game_pool.py` (Aufsicht) und `pool_worker.py` (Worker-Prozess). Keine neue Abhängigkeit; nur
Standardbibliothek und `ctypes`.

```python
@dataclass(frozen=True)
class GameTask:
    task_id: str                  # innerhalb der Serie fest: "base-s1000-t0" bzw. "s1000"
    game_id: str                  # Log-Id wie heute: f"{series_id}-{arm}-s{seed}-t{seat}" / f"batch-{id}-s{seed}"
    seed: int
    deck_paths: tuple[str, ...]   # Sitzreihenfolge 0..n-1, bereits durch pod_decks gedreht
    deck_sha256: tuple[str, ...]  # Datei-Hashes beim Planen; der Worker prüft sie vor dem Spiel
    order: int                    # Platz in der kanonischen Reihenfolge des Plans
    window: int                   # Look-Fenster (Batch: 0)
    strategy: str = "generic"; style: float | None = None; seat_styles: Mapping[int, float] | None = None
    max_decisions: int = 50_000

class GameOutcome(TypedDict):
    task_id: str; game_id: str; game_key: str
    status: Literal["finished", "failed"]
    failure_class: str | None      # derselbe öffentliche Klassenname wie heute im Log-Abschluss
    failure_kind: Literal["GAME", "INFRA"] | None
    attempts: int
    winner_seats: list[int]; decision_count: int; forced_decisions_skipped: int
    semantic_transcript_sha256: str | None
    log: str
    worker: int; jvm_generation: int; position_in_jvm: int; wall_seconds: float

class GamePool:
    def __init__(self, data_folder, engine: SeriesEngine, *, workers: int, jvm_game_budget: int,
                 journal: SeriesJournal, load_policy: LoadPolicy | None = None,
                 worker_factory: WorkerFactory = spawn_worker): ...
    def run(self, tasks: Sequence[GameTask], *, on_event: Callable[[PoolEvent], None] | None = None,
            should_cancel: Callable[[], bool] | None = None) -> dict[str, GameOutcome]: ...
    def close(self, *, graceful: bool = True) -> list[JvmExit]: ...
```

- `run` blockiert, bis jede Aufgabe ein endgültiges Ergebnis hat oder abgebrochen wurde. Die Worker und
  ihre JVMs bleiben nach `run` warm; der nächste `run`-Aufruf (nächstes Look-Fenster) nutzt sie weiter.
  Das passt ohne Umbau zur Statistik: `run_comparison_series` ruft `play(arm, seed, seat)` in fester
  Reihenfolge (`paired_comparison.py:594-619`); der Adapter füllt je Fenster einen Cache, wie heute
  `parallel_window_player` (`:984-996`).
- **Ergebnis je Partie per Rückruf:** `on_event` erhält `TaskDone(outcome)` in Abschluss-Reihenfolge, dazu
  `TaskStarted`, `TaskProgress(task_id, decisions)` (gedrosselt, alle 5 s), `JvmStarted/JvmRetired(reason,
  disposition, games, rss_mb)`, `WorkerDied`, `LoadChanged(active, foreign_cores)`. Die Reihenfolge der
  Ereignisse ist nicht Teil des Vertrags; Verbraucher ordnen nach `order` (Abschnitt 3).
- **Zugmodell:** die Aufsicht schickt einem Worker die nächste Aufgabe, sobald sein `done` da ist. Es gibt
  keine vorab geschnittenen Stücke mehr; `plan_chunks` (`simulations.py:748-765`) und die Stück-Kappe
  `min(G, ceil(Partien/W))` (`paired_comparison.py:797`) entfallen. Damit ist auch #1576 erledigt: ein
  Worker spielt Partien verschiedener (Arm, Sitz)-Tische nacheinander; `run_batch` nimmt die Decks schon
  je Partie (`fg.py:1255-1263`).
- **Spielschlüssel `game_key`** = SHA-256 über JAR-SHA, Engine-Pin, Pilot- und Policy-Version, Strategie
  und Stile, Deck-Hashes in Sitzfolge, Seed, Spielerzahl, `skipForcedDecisions`. Er enthält weder Worker
  noch Reihenfolge noch das JVM-Budget. Er steht in jedem Journal-Eintrag und macht den Determinismus
  prüfbar (gleicher Schlüssel, anderer Transkript-Hash = Alarm). Er ist auch die Grundlage für die spätere
  Wiederverwendung von Basis-Partien (Bericht A4); die ist nicht Teil von D-2.

### 1.2 Protokoll Aufsicht ↔ Worker [V]

Ein Worker ist `python -m commander_lab.studio pool-worker --data … [--private-card-repository]`, gestartet
mit `subprocess.Popen` und Pipes, Engine-Befehl über `COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD` wie heute
(`simulations.py:1235-1237`). JSON-Zeilen in beide Richtungen; das ist eine Obermenge der heutigen
`play-batch`-Meldezeile `{"game_id","status"}` (`__main__.py:714-715`, Leser `simulations.py:1310-1318`).

| Richtung | Zeile | Bedeutung |
|---|---|---|
| → | `{"op":"play","task":{…}}` | genau eine Partie; nie mehr als eine je Worker unterwegs |
| → | `{"op":"cancel"}` | laufende Partie abbrechen, JVM sauber beenden, Worker endet |
| → | `{"op":"recycle"}` / `{"op":"retire"}` | JVM sauber beenden; Worker bleibt für eine frische JVM / endet |
| ← | `{"ev":"ready","pid":…}`, `{"ev":"jvm","pid":…,"gen":n}` | PIDs für Sperre, Lastmessung, Aufräumen |
| ← | `{"ev":"started","task_id":…}`, `{"ev":"hb","task_id":…,"decisions":n,"rss_mb":…}` | Fortschritt je Partie, Herzschlag alle 5 s |
| ← | `{"ev":"done","outcome":{…}}` | Log ist geschlossen, Ergebnis endgültig |
| ← | `{"ev":"jvm_exit","gen":n,"disposition":…,"games":k,"reason":…}` | Lebensende einer JVM mit beobachteter Art |

stdin-Ende gilt als `retire`. Die Partie selbst baut der Worker mit `prepare_game` (`play.py:175-191`:
„eine allein gespielte und eine im Stück gespielte Partie entstehen durch diese eine Funktion“) und
schließt das Log mit `close_recorded_game` (`play.py:299-359`); beides bleibt unverändert.

### 1.3 Abbruch [V]

Heute drei Arten: Batch beendet die Kindprozesse mit `terminate()` (`simulations.py:863-869`; unter Windows
ist das ein hartes Beenden ohne den SIGTERM-Griff aus `__main__.py:707-711`); gepaart setzt nur ein
Merkzeichen (`paired_series.py:497-499`), das erst vor dem nächsten Stück und nach dem Fenster wirkt
(`paired_comparison.py:855-859, 936, 982`), also bis zu einem ganzen Stück Wartezeit; interaktiv eigener Weg.

Neu, ein Weg: `cancel` setzt im Worker ein Ereignis, das der Aufzeichnungs-Wrapper vor der nächsten
Entscheidung prüft (jede Entscheidung läuft durch `RecordingPolicy.decide`, `games.py:462-472`); die Partie
endet mit einer Ausnahme, die JVM wird mit `shutdown_engine` sauber beendet (`fg.py:857-872`), das
angefangene Log wird verworfen. Ziel: Abbruch in höchstens 10 s. Antwortet der Worker nicht, beendet die
Aufsicht ihn über das Prozess-Handle und die JVM über die gemeldete PID (Abschnitt 5.3). Beendete Partien
bleiben beendet gespeichert (zweites Abnahmekriterium von #1586). Abgebrochene Aufgaben bekommen keinen
endgültigen Journal-Eintrag und werden bei Wiederaufnahme neu eingereiht.

### 1.4 Fehlerklassen, Wiederholung, Zensur

Grundsatz [V]: **Eine Partie hat je Spielschlüssel genau ein Ergebnis. Wiederholt wird nur, was nicht aus
dem Spiel kam.** Partien sind deterministisch (424/424 [M]; die Hänger von #1584 traten bei jedem
Nachspielen wieder auf [M]), also ändert ein neuer Versuch nie das Ergebnis, nur ob es vorliegt.

| Auslöser (heutige Stelle) | `failure_kind` | Wiederholung | Wirkung in der Statistik |
|---|---|---|---|
| Engine meldet Fehler (`fg.py:1555-1561`, Code `ENGINE_FAILURE`) | GAME | keine | Paar zensiert (`paired_comparison.py:637-638`); Batch: gescheiterte Zeile |
| Bridge-Fehler in der Partie, auch `DECISION_ADVANCE_TIMEOUT` nach 75 s (`fg.py:714-721`, `Session:1153, 1182-1198`) | GAME | keine; eine, wenn im selben Zeitraum der Herzschlag des Workers ≥ 15 s ausfiel (Rechner stand) | wie oben |
| `max_decisions` überschritten (`fg.py:1578-1587`, Vorgabe 50.000 `play_batch.py:56`) | GAME | keine | wie oben |
| Verstoß verdeckte Information (`fg.py:1604-1609`) | GAME | keine; Serie zeigt Warnung | wie oben |
| Karten-Repository-Kollision beim Start (`fg.py:982-984, 1336-1347`) | kein Fehler | wie heute bis 4 Versuche mit 3 s × Versuch | keine |
| JVM weg: `BRIDGE_CLOSED`, `BRIDGE_NOT_WRITABLE`, `BRIDGE_EXITED` (`fg.py:609-612, 662-663, 689-692`) | INFRA | 1 × auf frischer JVM | nur wenn auch der zweite Versuch scheitert: zensiert, Klasse sichtbar |
| `BRIDGE_TIMEOUT`: 120 s ohne Antwort (`fg.py:550, 684-688`) | INFRA | 1 × | wie oben |
| Worker-Prozess endet (heute `ChunkProcessExited`, `simulations.py:1293-1307`) | INFRA (`WorkerExited`) | 1 × | wie oben |
| Zeitlimit der Aufsicht (heute je Stück 300 s × Partien, `simulations.py:745, 1263, 1287-1289`) | INFRA (`TimeLimit`) | 1 × | wie oben |
| `BRIDGE_START_FAILED` (`fg.py:624-633`) zweimal in Folge | Serie | keine | Serie endet `failed`, nicht N zensierte Partien |

- **Namen bleiben:** für GAME-Fehler dieselbe Zeichenkette wie heute (`public_exception_type`,
  `play.py:314`), damit `failure_classes` im Ergebnis (`paired_comparison.py:608, 624, 696-698`) gleich bleibt.
- **Zeitlimit neu je Partie statt je Stück:** heute scheitern bei einem Stück-Zeitlimit alle noch nicht
  gemeldeten Partien des Stücks mit (`simulations.py:1284-1289`); der gepaarte Weg hat gar keine Aufsicht
  außer dem 120-s-Limit je Anfrage. Neu: 150 s ohne Herzschlag-Fortschritt oder 300 s Wandzeit je Partie
  (der heutige Wert `CHUNK_SECONDS_PER_GAME`), dann Worker und JVM beenden.
- **Warum Wandzeit-Limits als INFRA gelten:** ein Wandzeit-Limit trifft lange Partien häufiger, und die
  Länge hängt mit dem Sieger zusammen; eine solche Zensur wäre nicht neutral. Deshalb erst wiederholen,
  und ein endgültiges `TimeLimit` als eigene Klasse zählen und anzeigen. Das einzige spielbezogene
  Längenlimit bleibt die Entscheidungszahl.
- **Zensurregel unberührt:** Grenze 5 % und Asymmetrie-Test (`paired_comparison.py:58-59, 259-283`) sehen
  wie heute nur `PlayedGame{exposure, failure_class}` (`:144-148`). Die Wiederholung liegt darunter.
- **Verhaltensänderung, offen zu legen:** heute bleibt eine Partie, die an der Infrastruktur scheiterte,
  in der gepaarten Serie zensiert, auch nach Wiederaufnahme (`_load_progress_jsonl` lädt gescheiterte mit,
  `paired_series.py:913-945`); die Batch-Serie spielt bei Wiederaufnahme dagegen alle nicht beendeten Seeds
  neu, auch deterministisch gescheiterte (`simulations.py:826-827`). Die Tabelle oben vereinheitlicht
  beides. Das ändert, welche Paare zensiert werden: Statistik-Review nötig; bis dahin ist die Wiederholung
  per Schalter aus (`max_attempts=1`), siehe Paket P5.

## 2. Lebenszyklus der Worker-JVMs

### 2.1 Was heute gilt [C]

- Eine JVM lebt für einen `run_batch`-Aufruf (`fg.py:1310-1317`). Je Partie: Policy bauen, Partie öffnen,
  treiben, Ergebnis holen, `shutdown_game` (`fg.py:1323-1334`).
- Nach einer gescheiterten Partie wird die JVM verworfen, der Rest läuft in einer frischen
  (`fg.py:1335-1350`).
- Partien, die vor einem unsauberen Ende derselben JVM fertig waren, werden einzeln in eigener JVM
  **nachgespielt** (`fg.py:1355-1364`). Ein Hänger in Partie 5 eines Stücks kostet also bis zu 4
  Einzel-JVM-Partien zu je etwa 53 CPU-s [M für G=1]. Dieser Anteil steckt in den 33,5 CPU-s der gepaarten
  Messung, ist dort aber nicht ausgewiesen.
- `on_game` kommt erst nach `run_batch` (`play_batch.py:184-193`), weil das Ergebnis erst nach dem
  JVM-Ende gebaut wird (`fg.py:1354-1374`). Das ist die Ursache von #1586.
- Kosten [M]: 64 java-CPU-s Aufwärmen je JVM-Leben (38 s in der ersten Partie); CPU je Partie 53,3 / 29,6 /
  22,3 / 18,3 / 14,3 bei 1 / 4 / 8 / 16 / warm; Modell 14,3 + 63/G für G ≥ 4. Start selbst: 0,1 s
  `start_engine`, 5,0 s erster Deck-Import, 1,2 bis 1,6 s Python.

### 2.2 Entscheid E-1: Grundlage eines Partie-Ergebnisses (MATERIAL, Lead/Owner)

| Option | Inhalt | Folge |
|---|---|---|
| **E-1a (Empfehlung)** | Für Studio-Serien ruht ein Ergebnis auf dem bestätigten `shutdown_game` der Partie (die Bridge meldet `shut_down`, `engine_thread_alive: false`, `game_over`, `Session:291-322`; heute wird die Antwort nicht gelesen, `fg.py:1334`). Eigener Ergebnistyp mit eigenem Schema, kein gelockertes Feld im Konformitäts-Ergebnis. Die Art des späteren JVM-Endes wird je JVM-Leben im Journal festgehalten und in der Serie gezählt. | JVM lebt über Look-Fenster; Ergebnis je Partie sofort; kein Nachspielen nach Hängern |
| E-1b | Regel bleibt: Ergebnis erst nach sauberem JVM-Ende. Pool beendet die JVMs an jeder Look-Grenze. | 10 Paare je Look, 4 Worker: 5 Partien je JVM, 26,9 CPU-s [S], Obergrenze 3,84 × 3600 / 26,9 = 514/h; Ziel 560 nicht erreichbar. Web-Standard: 2 statt 1 Partie je JVM |
| E-1c | Looks rechnen auf vorläufigen Ergebnissen, Bestätigung beim späteren JVM-Ende, sonst Nachspielen mit Hash-Vergleich | Stopp-Entscheide auf unbestätigten Daten; aufwendig; nicht empfohlen |

Für E-1a gibt es einen Präzedenzfall im Repo: `FullGameBatchReportBatched` ist ein eigener Typ mit eigenem
Schema und der festen Angabe `state_isolation_basis = "SHUTDOWN_GAME_ONLY_NOT_A_PROCESS_BOUNDARY"`
(`engine/rules/full_game_batch.py:151-165`), statt die Aussage „eine JVM je Partie“ aufzuweichen. Evidenz-
und Qualifikationsläufe behalten `run()` mit einer Partie je Prozess (`fg.py:1215-1253`); `run_batch`
behält seine Regel. Rechnung zur Schwelle: 560/h bei 3,84 genutzten Kernen [M] verlangt höchstens
3,84 × 3600 / 560 = 24,7 CPU-s je Partie, nach Modell also G ≥ 6,1 Partien je JVM-Leben.

### 2.3 Lebenszyklus im Pool [V] (unter E-1a)

1. **Start:** die Aufsicht startet `min(W, Zahl der Aufgaben)` Worker. Jeder Worker startet seine JVM
   sofort (`start_engine`, Handshake) und hält einen privaten Karten-Slot `private/slot-<n>`
   (`fg.py:724-785`; Sperre über `flock` bzw. `msvcrt.locking`, `fg.py:505-523`; 261 MB je Slot [M]).
   Kein künstliches Aufwärmen: Aufwärmpartien kosten dieselben 64 CPU-s und liefern nichts; die ersten
   echten Partien wärmen. AppCDS wirkt wie heute, wenn das Archiv da ist (`launch.py:196-207`, −2,6 s je
   JVM-Start [M]).
2. **Wiederverwendung:** die JVM bleibt zwischen Partien und zwischen Look-Fenstern offen. Zwischen zwei
   `run`-Aufrufen wartet sie auf stdin; es läuft keine Anfrage, also greift kein Zeitlimit
   (`fg.py:684`). Verhalten einer minutenlang wartenden JVM: UNKNOWN (U-3).
3. **Geplanter Ruhestand** an einer Partiegrenze, sauber (`shutdown_engine`), wenn eines gilt:
   - Partien in dieser JVM = `jvm_game_budget` (die JVM wird mit
     `-Dcommanderlab.fullGame.gamesPerJvm=<Budget>` gestartet, `launch.py:199`; die Bridge lehnt Partie
     Budget+1 ab, `Bridge:175-184`);
   - JVM-RSS über der Schwelle (Vorschlag 2,2 GB bei `-Xmx3g`, `launch.py:136`) oder freier Arbeitsspeicher
     unter 1 GB;
   - die Aufsicht senkt die Zahl aktiver Worker wegen Speicherdruck.
4. **Neustart nach Fehler:** nach jeder gescheiterten Partie wird die JVM verworfen wie heute
   (`fg.py:1335`), bei verlorenem Kanal ohne Handshake (`fg.py:575-580, 857`). Der Worker meldet
   `jvm_exit` mit der beobachteten Art (`graceful_shutdown`, `unacked_exit`, `forced_kill`,
   `already_exited`, `fg.py:840-845`) und startet eine frische JVM. Kosten je Hänger: rund 90 s Wandzeit und
   113 bis 126 CPU-s [M] plus 64 CPU-s Aufwärmen; das Nachspielen der Nachbarn entfällt unter E-1a.
5. **Ende der Serie:** `close()` beendet alle JVMs sauber und schreibt je JVM-Leben einen `jvm_exit`.
6. **Warmhalten über Serien hinweg** (JVMs 10 min behalten, wenn Befehl und JAR-SHA gleich sind) spart bei
   kurzen Serien viel: 40 Partien, 4 Worker = 256 von 828 CPU-s Aufwärmen, 31 % [S]. Nicht Teil der
   Abnahme; erst nach Messung U-3.

### 2.4 Partien je JVM: Vorgabe und Grenze

- Belegt [M]: Identität bis Position 16 in einer JVM (16/16), RSS 951 → 1.013 MB von 8 auf 16 Partien
  (+62 MB). Das Referenz-Set des Bridge-Gates fährt 9 je JVM (`docs/STUDIO_PLAN_SIMULATOR.md:64-65`). Ein
  JFR-Lauf mit 12 je JVM hatte 1.197 MB (`docs/performance/THROUGHPUT_STEADY_STATE_2026-11-13.md` §3).
- **UNKNOWN:** Speicher und Identität ab 17, erst recht über 24; ob die 62 MB Wachstum Leck oder
  Heap-Zuschnitt sind; gemischte Tische in einer JVM.
- Vorgabe [V]: `jvm_game_budget` = 16 (belegter Bereich), Obergrenze bleibt 24, bis die Messung unten
  vorliegt. Das Feld `games_per_jvm` der Oberfläche behält Namen und Bereich (`web.py:284, 305`) und heißt
  künftig „höchstens so viele Partien je JVM-Leben“. Die heutige Vorgabe 6 (`launch.py:40`) würde im Pool
  24,8 CPU-s je Partie [S] festschreiben; die Anhebung ist laut Bericht A3 Sache des Leads.

**Messvorschrift für die Grenze (UNKNOWN → Zahl), je Zelle seriell, ruhige Maschine, Fremdlast notiert:**

| Zelle | Aufbau | Messgrößen je Partie | Bestanden, wenn |
|---|---|---|---|
| M1 | 1 Worker, eine JVM, 96 Partien = Seeds 1 bis 8 zwölfmal (Aufbau wie `f_g16`) | RSS von JVM und Python-Worker, Wandzeit, CPU-s, Transkript-Hash, Sieger, Entscheidungszahl, Frame-Digest | 96/96 je Seed gleich; Steigung des RSS über die Partien 17 bis 96 ≤ 2 MB je Partie; Wandzeit des 12. Durchgangs innerhalb ±5 % des 2. |
| M2 | wie M1, aber gemischte Tische: 2 Arme × 4 Sitze im Wechsel (deckt `retainOnly`, `Bridge:245`) | wie M1 | wie M1 |
| M3 | 4 Worker × 96 Partien | Summe RSS, Partien/h je Durchgang | kein Swap; Durchsatz des letzten Durchgangs ≥ 95 % des zweiten |
| M4 | M1 mit GC-Protokoll über `COMMANDER_LAB_XMAGE_JVM_FLAGS` (vorhandener Diagnose-Weg, `fg.py:960-976`) | belegter Heap nach vollem GC | flach: unterscheidet Leck von Heap-Zuschnitt |

Budget wird der größte bestandene Wert, höchstens 48 im ersten Schritt. RSS ohne neue Abhängigkeit: Linux
`/proc/<pid>/status`, Windows `K32GetProcessMemoryInfo` über `ctypes`. Dauer M1 [S]: 96 × 14 s ≈ 23 min.

## 3. Determinismus-Vertrag

**Zusage:** gleicher Spielschlüssel ergibt gleichen Transkript-Hash (`semantic_transcript_sha256`,
`fg.py:1874-1916, 1949-1951`), gleiche Sieger, gleiche Entscheidungszahl und gleichen Frame-Digest
(`engine/rules/frame_digest.py`), unabhängig von Worker, Position in der JVM, Reihenfolge, Zahl der
Worker, Versuch und Wiederaufnahme. Belegt für Position und Pfad: 424/424 und 56/56 Digest [M]; nicht
belegt für gemischte Tische, Positionen über 16 und wartende JVMs.

Was der Pool dafür einhalten muss:

1. **Alles wird beim Planen festgelegt.** Seed, Decks in Sitzfolge, `game_id` und Stil stehen im Manifest,
   bevor ein Worker startet. Nichts davon hängt an Worker-Nummer, Zeitpunkt oder Zuteilung.
2. **Startsitz** bleibt `seed % Spielerzahl` in der Engine-Schicht (`fg.py:1514`); der Pool reicht den Seed
   unverändert durch. Die Serie plant fortlaufende Seeds, damit die Zugfolge ausgeglichen ist
   (`paired_series.py:401-411`, `:753-756`).
3. **Sitzzuordnung der Paare:** Tisch = `pod_decks(Kandidat, Gegner, Sitz + 1)`
   (`engine/rules/full_game_comparison.py:143-158`, Aufruf `paired_comparison.py:767, 937`); beide Arme
   eines Paares unterscheiden sich nur im getesteten Sitz. Der Planer bildet die Deck-Liste, der Pool
   dreht nichts. Batch: eigenes Deck immer Sitz 0 (`simulations.py:1223-1227`).
4. **Alignment:** `align_to_baseline_slots` (`full_game_comparison.py:243-292`) läuft einmal beim
   Serienstart und schreibt die Varianten-Datei in Basis-Reihenfolge (`paired_series.py:291-320`, Aufruf
   `:742-744`). Der Pool spielt genau diese Datei. Neu [V]: ihr Datei-Hash steht im Manifest, der Worker
   prüft ihn vor jeder Partie; bei Wiederaufnahme wird er gegen `slot_alignment.played_mainboard_sha256`
   geprüft. Heute liest die Wiederaufnahme `base-*.json`/`variant-*.json` ungeprüft neu
   (`paired_series.py:978-985`).
5. **Gleicher Engine-Befehl für alle Worker einer Serie** (`SeriesEngine.command`, `launch.py:158-207`,
   mit `skipForcedDecisions`, `:197-198`). Der Frame-Digest hängt an dieser Einstellung [M].
6. **Frische Piloten je Partie** (`fg.py:1473-1480`); ein Worker hält keinen Zustand zwischen Partien
   außer der offenen JVM. Ob Pilot-Caches bei wechselnden Tischen in einem Prozess neutral sind: U-3.
7. **Auswertung in Planreihenfolge.** Das Journal steht in Abschluss-Reihenfolge; jeder Leser ordnet nach
   `order`. Gepaart ist das durch den Cache und die feste Schleife gegeben
   (`paired_comparison.py:594, 614`), Batch durch `_games_in_seed_order` (`simulations.py:876-878`).
8. **Nicht Teil der Zusage:** Bytes der Logs (Zeitstempel `games.py:330, 399`; Kurz-IDs der Engine [M]).
   Das Ereignisprotokoll wird beim Speichern bereits kanonisch geordnet (`games.py:429-447`).
9. **Wächter:** tritt ein Spielschlüssel im Journal mit zwei verschiedenen Hashes auf (Wiederholung,
   Wiederaufnahme, Identitätsprobe), endet die Serie `failed` mit `DETERMINISM_VIOLATION`.

Aufteilung der Dispatch-Reihenfolge im Fenster [V]: Basis und Variante derselben Einheit stehen in der
Warteschlange nebeneinander. Das ändert kein Ergebnis, aber Paare werden früh vollständig und ein Abbruch
hinterlässt weniger halbe Paare.

## 4. Die zwei Kunden

### 4.1 Batch-Serie

Aufgabenliste = ein `GameTask` je Seed mit `[eigenes Deck, *Gegner]` und `game_id = batch-<id>-s<seed>`
(`simulations.py:845-846`). Ein `pool.run`. Auf `TaskDone` liest die Serie die Kennzahlen wie heute aus dem
Log (`extract_game_log_telemetry`, `simulations.py:1272-1274`) und hängt die Zeile an (`_add_game`,
`:1116-1120`). `aggregate_batch_results` (`:483-588`) und `save_batch_to_store` (`:591-739`) bleiben. Es
entfallen `plan_chunks`, `_run_chunk`, `_process_chunk`, die Stück-Datei `…-chunk-s<seed>.out`. Der Block
`execution` (`:848-861`) nennt statt `chunks` den Pool (`workers`, `jvm_game_budget`, `assignment:
"dynamic"`) und je JVM-Leben Zahl und Ende; `seeds` bleibt die Quelle für die Wiederaufnahme (`:949-950`).

### 4.2 Gepaarte Serie: aus `plan_look_window_chunks` wird die Aufgabenliste je Fenster

```python
def plan_look_window_tasks(units: Sequence[tuple[int, int]]) -> list[tuple[str, int, int]]:
    """(arm, seed, seat) eines Look-Fensters in der Reihenfolge, in der die Auswertung sie verbraucht."""
    return [(arm, seed, seat) for seed, seat in units for arm in ARMS]
```

`workers` und `games_per_jvm` fallen aus dem Planer heraus: die Stückelung gehört dem Pool.
`parallel_window_player` behält Signatur und Rückgabe (ein `PairPlayer`, `paired_comparison.py:151-152`)
mit `preloaded`, `on_game_result`, `on_pair_done`, `is_cancelled`, `cancel_error_factory`, `play_single`.
Ersetzt wird nur der Engine-Zweig von `_run_window` (`:914-982`): fehlende Aufgaben → `GameTask`-Liste →
`pool.run(...)`; je `TaskDone` wird `_summary_to_played_game` (`:732-743`) gebildet, `on_game_result` und
`_mark_game_done` aufgerufen, der Cache gefüllt. Fensterzuordnung (`windows_by_start`, `:834-840`),
Cache und Paar-Zählung (`:846-873`) bleiben Zeile für Zeile.

**Unangetastet** bleiben `_summarize` (`:335-479`), `run_comparison_series` (`:554-729`),
`_censoring_issues` (`:259-283`), `pair_exposures` (`:221-256`), `compare_logs` (`:482-551`) und die ganze
Datei `engine/rules/full_game_comparison.py` (Look-Zahlen `:661-664`, O'Brien-Fleming-Stufen `:667-697`).
Die Look-Grenze bleibt eine Schranke: das nächste Fenster beginnt erst, wenn alle Partien des Fensters ein
endgültiges Ergebnis haben.

**Ausdrücklich nicht in D-2: Vorgreifen auf das nächste Fenster.** Partien jenseits eines Looks zu starten,
solange dessen letzte Partien laufen, würde bei einem frühen Stopp Logs erzeugen, die die Serie nicht
auswertet, die aber im selben Ordner liegen und von `compare_logs` und den Karten-Auswertungen gelesen
werden (`load_exposures(games_dir)`, `paired_comparison.py:509`). Das wäre eine Änderung am Auswertungsweg.
Der Preis der Schranke ist Leerlauf am Fensterende, geschätzt 5 bis 10 % bei 20 Partien je Fenster und
4 Workern [S, nicht gemessen].

Auch `compare-decks` (`__main__.py:559-656`) wird Kunde; der Einzelweg `recorded_game_player`
(`paired_comparison.py:746-773`) wird zum Pool mit einem Worker und Budget 1 für Starter, die nicht `java`
sind (`launch.py:189-190`). Hinweis [C]: `compare-decks` richtet die Variante heute nicht aus (kein Aufruf
von `_align_variant_file` in `__main__.py:593-628`), der Web-Weg schon; D-2 ändert das nicht (U-9).

## 5. Ein Verwalter statt drei

### 5.1 Bestand [C]

| Verwalter | Sperren | Ablage | Abbruch | Wiederaufnahme |
|---|---|---|---|---|
| `SimulationBatchManager` (`simulations.py:1321`) | Register-Lock `:1326`, je Serie `:843`; keine Datei-Sperre | `<id>.series.json` nur am Ende (`:1072, 1080-1086`), stderr je Stück als `.out` im Partien-Ordner (`:1239`) | Prozesse beenden (`:863-869`) | aus Datensatz plus Log-Suche (`:915-1026`); nicht nach Absturz (Befund 0.4); kein Schutz gegen doppeltes Fortsetzen aus zwei Prozessen (`:1470-1472` prüft nur den Speicher) |
| `PairedSeriesManager` (`paired_series.py:653`) | Register-Lock `:659`, je Serie drei (`:439-441`), `running.lock` mit PID (`:449-462`) | `<id>.paired.json` atomar (`:323-332, 505-507`), `paired_decks/<id>/progress.jsonl` je Partie (`:482-495`) | Merkzeichen (`:497-499`), nur im Speicher bekannte Serien (`:1157-1164`) | `resume_series` (`:947-1138`) |
| `InteractivePlayManager` (`play.py:1023`) | ein Lock `:1027` | Partie-Log | `shutdown_game` | keine |

Nebenbefund [C, nicht am laufenden Server geprüft]: `list_games` führt jede `.out`-Datei ohne Log als
gescheiterte Partie `start_failed` (`games.py:611-613, 726-744`); die Stück-Dateien der Batch-Serie liegen
in diesem Ordner und werden nie gelöscht (`simulations.py:1239-1283`).

### 5.2 Ziel [V]

Ein `SeriesManager` mit einem Ablageformat je Serie unter `games/series/<series_id>/`:

- `manifest.json`: beim Start atomar geschrieben, danach unverändert. Art (batch | paired), Plan (Seeds,
  Sitze, Arme, Budget, Look-Abstand, Schwelle, Niveau), Decks mit Datei-Hash, `slot_alignment`,
  `seed_plan`, Engine-Identität (Befehl, JAR-SHA, Qualifikationsstand), Pool-Einstellungen. Schema
  `studio-series-manifest-1`.
- `journal.jsonl`: nur anhängen, eine Zeile je endgültigem Partie-Ergebnis (`GameOutcome`) und je
  JVM-Lebensende, mit `flush` und `fsync`. Eine abgeschnittene letzte Zeile wird überlesen, wie heute
  (`paired_series.py:468-480, 920-923`).
- `running.lock`: PID der Aufsicht, Startzeit, Herzschlag (wirklich alle 10 s erneuert; heute nur je
  Partie-Ergebnis geschrieben und nie gelesen, `paired_series.py:452-462, 495, 830-843`), dazu die PIDs der
  Worker und JVMs.
- `worker-<n>.err`: stderr der Worker, nicht mehr im Partien-Ordner.

Die Antworten der Routen bleiben, wie sie sind: `to_dict()` der Batch-Serie (`simulations.py:880-913`) und
der gepaarten Serie (`paired_series.py:518-569`, Schema `studio-paired-series-job-1`) werden aus Manifest
und Journal gebildet und weiter als `<id>.series.json` bzw. `<id>.paired.json` geschrieben. Das sind
Ansichten, keine zweite Wahrheit. `simulation_manager` und `paired_series_manager` bleiben als dünne
Namen bestehen, damit `web.py` (`:1100-1270`, Kollisionsdatei) nur in den Einhängungen berührt wird.

Der interaktive Verwalter behält seinen Protokolltreiber (das ist D-3). Er teilt mit dem Serien-Verwalter
die Prozess-Hilfen aus 5.3 und meldet seine JVM beim Lastbudget an (Abschnitt 6), damit eine Partie am
Brett und eine Serie voneinander wissen. Ob die Abnahme „3 → 1“ ihn mitzählt: U-2.

### 5.3 Wiederaufnahme-Vertrag von #1544: was erhalten bleibt

1. Eine Serie mit Status `running`/`pending` ohne lebende Sperre heißt „unterbrochen“ und ist fortsetzbar,
   wenn `_is_disk_resumable` zutrifft (`paired_series.py:845-911`).
2. Fortsetzen spielt nur Fehlendes; Gespieltes wird nicht neu gespielt und nicht doppelt gezählt
   (`preloaded`, `paired_comparison.py:847-853, 914-930`).
3. Das Ergebnis ist gleich dem der ununterbrochenen Serie; Looks nur an den geplanten Grenzen, auch mitten
   im Fenster (`windows_by_start`, `:834-840`).
4. Abgelehnt wird: abgeschlossene Serie, lebende Sperre, fehlende Deck-Dateien, abweichende Gegner,
   abweichender `seed_plan`, abweichende JAR-SHA (`paired_series.py:959-1092`).
5. Die Tests bleiben unverändert grün: `test_orphaned_running_series_is_reported_as_interrupted_and_
   resumed_identically`, `test_paired_resume_route_returns_updated_job_and_rejects_completed`,
   `test_paired_resume_persists_custom_opponents_and_rejects_mismatch`,
   `test_paired_resume_live_lockfile_and_engine_chunk_filtering`
   (`tests/unit/test_studio_db_c_paired_readiness.py:1456, 1635, 1681, 1820`).
6. Alte Serien auf der Platte bleiben lesbar und fortsetzbar: ein Leser für `progress.jsonl` übernimmt
   deren Einträge beim Fortsetzen ins Journal.

Neu dazu: Batch-Serien bekommen denselben Vertrag (Manifest beim Start, Sperre, „unterbrochen“).

### 5.4 Windows

- **Liveness:** `_is_pid_alive` (`paired_series.py:796-828`: `OpenProcess` mit
  `PROCESS_QUERY_LIMITED_INFORMATION`, `GetExitCodeProcess == 259`, Zugriff verweigert zählt als lebend)
  zieht unverändert nach `procs.py`; der alte Name bleibt als Weiterleitung für die Tests.
- **Prozesse statt Threads**, gestartet mit `subprocess.Popen` und Pipes wie heute der Stück-Prozess
  (`simulations.py:1244-1251`); kein `multiprocessing`, also kein Pickle-Zwang unter `spawn`.
- **Kein Signal nötig:** Abbruch über stdin-Nachricht (1.3). Rückfall: Worker über das Handle beenden, JVM
  über die gemeldete PID (`taskkill /PID <pid> /T /F` bzw. `os.kill`), danach Liveness prüfen.
- **Verwaiste JVMs:** die Slot-Sperre hält der Python-Prozess, nicht die JVM (`fg.py:749-757`). Stirbt ein
  Worker hart, kann seine JVM im Slot weiterlaufen und die nächste JVM dort kollidiert. Die Bridge endet
  bei stdin-Ende ihrer Leseschleife (`Main.java:79`), ruft danach aber kein `System.exit`; ob eine JVM im
  Hänger dann endet, ist UNKNOWN (U-5). Deshalb räumt die Aufsicht beim Start und bei der Wiederaufnahme
  die in der alten Sperre genannten JVM-PIDs ab, wenn der Prozess noch lebt und ein Java-Prozess ist.
- **PID-Wiederverwendung:** heute gilt jede lebende PID als „Serie läuft“ (`:830-843`). Neu zusätzlich:
  Herzschlag älter als 120 s bei lebender PID gilt als nicht laufend. Das ändert Punkt 1 des Vertrags in
  einem Randfall und braucht einen eigenen Test.
- Messwerkzeuge: `resource` ist in beiden Skripten inzwischen abgefangen
  (`scripts/benchmark_xmage_full_games.py:42-45`, `scripts/check_studio_series_identity.py:33-36`);
  `docs/STUDIO_SCOPE.md:122-124` führt den Punkt noch als offen. Ein Lauf unter Windows: UNKNOWN.

## 6. Last und Kernzahl

Messlage [M]: 235 / 533 / 595 Partien/h bei 1 / 3 / 4 Workern auf 4 Kernen, ruhig. Mit 0,9 Kernen Fremdlast
460 bei 4 Workern gegen 507 bei 3. Eine JVM belegt in den ersten 8 Partien 1,45 Kerne, warm 1,03. Je Worker
0,84 bis 1,01 GB RSS. Zweite Quelle (`docs/performance/THROUGHPUT_STEADY_STATE_2026-11-13.md:4, §1, §3`,
Ryzen 7 7700 mit 8 Kernen/16 Threads, 16 GB): 6 Worker 541,2/h, 8 Worker 524,7/h mit +2,9 GB Swap.
`paired_series.py:66-71` nennt 541,2 als Messung am Owner-PC; dass diese Hardware der Owner-PC ist, ist
daraus abgeleitet, nicht bestätigt (U-6).

Strategie [V]:

1. **Obergrenze `W_max`** = die Einstellung `workers`; ohne Angabe bleibt `min(4, Kerne − 1)`
   (`launch.py:140-142`). Zusätzlich gedeckelt durch Speicher: `(freier RAM − 3 GB) / 1,3 GB` je Worker.
   Auf 16 GB sind das rechnerisch 9, die Messung zeigt Swap schon bei 8; bis zur Owner-Messung höchstens 6.
2. **Aktive Worker `W_aktiv`** ≤ `W_max`, nur an Partiegrenzen geändert, nie mitten in einer Partie.
   Regel mit Hysterese: Fremdlast ≥ 0,75 Kerne über 30 s → `W_aktiv = max(1, W_max − aufgerundete
   Fremdlast)`; Fremdlast ≤ 0,25 Kerne über 60 s → einer mehr. Ein pausierter Worker behält seine warme JVM
   (kostet nur rund 0,9 GB) und geht bei Speicherdruck in den Ruhestand. Damit gilt „Worker = Kerne“ nur
   auf ruhigem Rechner. Die Schwellen stützen sich auf zwei Messpunkte und sind zu prüfen (U-7).
3. **Fremdlast** = belegte Kerne der Maschine minus eigene Prozessfamilie, alle 5 s, geglättet über 30 s
   (dieselbe Größe wie im Messbericht). Ohne neue Abhängigkeit: Linux `/proc/stat` und `/proc/<pid>/stat`;
   Windows `GetSystemTimes` und `GetProcessTimes` über `ctypes` für die bekannten Worker- und JVM-PIDs. Ist
   die Messung nicht verfügbar, bleibt `W_aktiv = W_max` und das Journal sagt `load_sensing: unavailable`.
4. **Niedrigere Priorität** für Worker und JVMs (Windows `BELOW_NORMAL_PRIORITY_CLASS` als Startflag, sonst
   `os.nice`), damit der Owner am PC nichts spürt. Wirkung auf den Durchsatz: UNKNOWN, im Protokoll messen.
5. Die Zeitreihe von `W_aktiv` und Fremdlast steht im Journal und im Block `execution`. Sie berührt kein
   Spielergebnis (Abschnitt 3).

**Owner-PC-Messprotokoll** (ergänzt Abschnitt 7 des Messberichts; PowerShell, rund 75 min, K = physische
Kerne, je Zelle dieselben 48 Seeds, vor jeder Zelle Prozessorlast unter 5 % notieren):

| Zelle | Worker | Budget je JVM | Zweck |
|---|---|---|---|
| ref, a, b, c | 1, K/2, K−1, K | 8 | wie im Bericht, alter Weg; b zweimal (Streuung) |
| p1, p2 | K−1, K | 16 | Pool gegen alten Weg bei gleicher Arbeit |
| p3 | K−1 | 48 | langes JVM-Leben, RAM-Spitze |
| p4 | 1 | 96 | Speicherkurve M1 |
| p5 | K | 16, nach 3 min zwei Prozesse `python -c "while True: pass"` für 3 min | greift die Lastregel, erholt sie sich |
| p6 | K−1 | 16 | gepaart, 40 Paare, alter Weg gegen Pool |

Je Zelle zurückmelden: Wandzeit, Partien/h, RAM-Spitze (Summe `java` + `python`), Last vorher, Identität
gegen `ref` (48/48 Hash, Sieger, Entscheidungszahl, Frame-Digest), bei p5 die Zeitreihe von `W_aktiv`.
Das Skript dafür ist Teil von Paket P5; CPU-Sekunden unter Windows über `GetProcessTimes`.

## 7. Migrationspfad

| Schritt | Inhalt | Alter Weg | Nachweis |
|---|---|---|---|
| S1 (#1586, erster Teil) | Fortschritt je Partie im Stück: `BatchRecordingRunner` meldet „gespielt“, sobald `_drive` einer Partie endet (Überschreibung in `play_batch.py`; `play.py` und `fg.py` bleiben). `play-batch` druckt dafür eine Zeile, die Batch-Serie zählt „x von n gespielt“. Die Logs schließen weiter am JVM-Ende. | unverändert | gleicher Transkript-Hash je Partie; Zähler steigt je Partie (Test mit nachgebautem Runner) |
| S2 (E-1a) | Engine-Schnittstelle `FullGameSeriesSession` in `fg.py`: eine offene Bridge, `play(scenario, decks, pilots)` je Partie, Ergebnis im eigenen Typ, `close()` mit beobachteter Art. `_run_batch` nutzt denselben Partie-Rumpf, Verhalten gleich. | `run`, `run_batch` unverändert | bestehende Tests `test_full_game_batch_*` grün ohne Änderung; 36/36 alter gegen neuer Python-Stand, gleiche JAR |
| S3 (#1586 Rest) | Pool, Worker-Prozess, Journal, Manifest, Prozess-Hilfen. Batch-Serie als erster Kunde hinter `COMMANDER_LAB_STUDIO_SERIES_POOL=1`. | bleibt Vorgabe | 36/36 Pool gegen alten Weg; Abbruch behält beendete Partien; Absturz-Wiederaufnahme Batch |
| S4 (#1585, #1576) | Gepaarte Serie und `compare-decks` als Kunden; `plan_look_window_tasks`; Journal statt `progress.jsonl` mit Leser für alte Serien. | bleibt Vorgabe | Ergebnis der Serie gleich (Paare, Differenz, Intervalle, Stopp-Grund); 80/80 je Partie; Durchsatz gemessen |
| S5 | Ein `SeriesManager`; Schalter wird Vorgabe; alte Wege entfernt; Lastregel, Messskript, Owner-Protokoll. Budget über 24 erst nach M1 bis M4. | entfernt nach einer Woche ohne Befund | Wiederaufnahme-Tests, Architekturtest, Owner-PC-Lauf |

S1 ist sofort startbar und unabhängig von E-1. S2 wartet auf E-1. Fällt E-1 auf E-1b, entfällt S2; S3 bis
S5 liefern dann Struktur, Prozesse statt Threads (6 bis 11 % [M]), gemischte Tische und Fortschritt je
Partie, aber nicht das Tempo-Ziel.

## 8. Abnahme

| # | Kriterium | Messung |
|---|---|---|
| A1 | Identität 36/36 | Referenz-Set des Bridge-Gates (echter Vierer-Tisch, Seeds 1 bis 36, `docs/STUDIO_PLAN_SIMULATOR.md:58-66`): alter Weg gegen Pool mit 4 Workern, dieselbe JAR; Transkript-Hash, Sieger, Entscheidungszahl, Frame-Digest je Seed gleich, alle 36 beendet |
| A2 | Unabhängig von Zuteilung | dieselben 36 mit 1 Worker, mit 4 Workern und mit umgekehrter Warteschlange: 36/36 untereinander |
| A3 | Gemischte Tische | 36 Aufgaben = 9 Seeds × 2 Arme × 2 Sitze, jede einzeln (alter Einzelweg) und im Pool: 36/36 |
| A4 | Gepaart Ende zu Ende | Befehl aus Bericht 4.3 (40 Paare, Look 10, Seeds ab 1000, 4 Worker): Ergebnis der Serie gleich dem alten Weg; je Partie 80/80 (gescheiterte mit gleicher Klasse) |
| A5 | Durchsatz gepaart ≥ 560 gestartete Partien/h auf der 4-Kern-VM (heute 350 [M]) | derselbe Befehl, dieselbe JAR vorher und nachher, Fremdlast ≤ 0,1 Kerne, je zwei Läufe; dazu CPU-s je Partie, eigene Kerne, Zahl der JVM-Leben, RSS |
| A6 | Web-Standard | Budget 20, Look 4, Sitze rotieren: JVM-Leben 40 [C] → 4 plus Zahl der Fehler; Wandzeit vorher/nachher |
| A7 | Orchestrierer 3 → 1 | nur `game_pool.py` startet für Serien Engine-Prozesse: Test, dass `simulations.py`, `paired_comparison.py`, `paired_series.py` weder `ThreadPoolExecutor` noch `subprocess.Popen` enthalten; `plan_chunks`, `plan_look_window_chunks`, `_process_chunk` sind weg; ein Sperr- und ein Ablageformat für Serien |
| A8 | Wiederaufnahme | die vier Tests aus 5.3 unverändert grün; neu: Batch nach Absturz, Worker mitten in der Partie beendet (Aufgabe neu eingereiht, gleicher Hash), Aufsicht beendet, abgeschnittene Journal-Zeile, alte `progress.jsonl`-Serie, doppeltes Fortsetzen abgelehnt |
| A9 | Abbruch | ≤ 10 s; beendete Partien bleiben beendet; danach kein Java-Prozess der Serie mehr |
| A10 | Statistik unangetastet | der Diff enthält keine Zeile in den in 4.2 genannten Funktionen und nicht in `full_game_comparison.py`; Test: gleiches `PairedComparison` (ohne `execution`) für alten und neuen Weg, auch bei gemischter Abschluss-Reihenfolge, eingestreuten Fehlern und Wiederaufnahme mitten im Fenster |

Erwartung zu A5 [S], Modell 14,3 + 63/G bei 3,84 Kernen, 80 Partien auf 4 Worker:

| Budget je JVM | JVM-Leben | CPU-s je Partie | Obergrenze | mit 7,5 % Fensterleerlauf |
|---|---|---|---|---|
| 8 | 12 | 23,8 | 581 | 537 |
| 16 | 8 | 20,6 | 671 | 621 |
| 24 | 4 | 17,5 | 792 | 733 |

Mit den vier Hängern von #1584 (je 90 s plus 64 CPU-s Neustart) bei Budget 24: 553/h ohne, 515/h mit
Fensterleerlauf. Der Wert 350 enthält diese Hänger. #1584 ist diagnostiziert und beansprucht (Branch
`fix/engine-hang-declare-attackers-1584`, kein offener PR am 2026-11-19); nach seinem Merge ändert sich
die JAR und der Ausgangswert ist neu zu messen. A5 ist deshalb zweimal anzugeben: mit der heutigen JAR und,
sobald vorhanden, mit der JAR nach #1584.

## 9. Risiken und Abbruchkriterien

| # | Risiko | Beleg | Gegenmaßnahme / Abbruch |
|---|---|---|---|
| R1 | E-1a wird abgelehnt | `fg.py:1270-1278` ist Evidenztext | E-1b bauen; Tempo-Ziel streichen, Struktur-Ziele bleiben |
| R2 | Hash-Abweichung bei gemischten Tischen oder langem JVM-Leben | nur gleiche Tische und Position ≤ 16 gemessen | Rückfall „ein Tisch je JVM-Leben“ und Budget 16; bleibt sie zwei Tage unerklärt: Schalter aus (Kriterium aus #1612) |
| R3 | Hänger fressen den Gewinn | 4 von 80, je 90 s [M]; Modell 515 bis 553 | #1584 abwarten; A5 mit beiden JARs |
| R4 | Windows: verwaiste JVMs, Prozessbaum, `ctypes`-Aufrufe | keine Windows-Messung im Repo | Vorgabe erst nach Owner-PC-Lauf umstellen (S5) |
| R5 | Speicher: lange lebende JVMs auf 16 GB | +62 MB von 8 auf 16 [M]; Swap bei 8 Workern | RSS-Schwelle, Speicher-Deckel, M1 bis M4 vor Budget über 24 |
| R6 | Wiederholung ändert die Zensur | 1.4 | Schalter aus bis zum Statistik-Review |
| R7 | Kollisionsdateien | „Nie zwei offene PRs auf `paired_series.py`“ (#1523); `web.py`; `fg.py` auch Ziel von D-3 | Reihenfolge P2 vor D-3; Claim in #1612 und #1167 je Paket |
| R8 | Zwei Wahrheiten (Journal und Ansichts-Datei) | 5.2 | Ansicht nur aus Manifest und Journal bilden; Test |
| R9 | PID-Wiederverwendung: Serie „läuft“ für immer | `paired_series.py:830-843` | Herzschlag-Alter (5.4) |
| R10 | Budget | D-2: 5 bis 7 Lane-Tage (#1612) | Abbruch über 10,5 Lane-Tagen |
| R11 | Architekturtest D-0 (größte Zyklus-Gruppe ≤ 12) | Claim-Kommentar in #1612 | `game_pool.py` importiert weder `simulations` noch `paired_*`; Richtung nur Kunde → Pool → `play_batch`/`games`/`launch` |

## 10. PR-Schnitt

| Paket | Inhalt (Schritt) | Dateien | Größe [S] | MATERIAL | Vorher nötig |
|---|---|---|---|---|---|
| P1 | Fortschritt je Partie im Stück (S1) | `play_batch.py`, `__main__.py` (`play-batch`), `simulations.py` (Zähler), Tests | 150 bis 250 Zeilen, 0,5 Lane-Tage | nein (nur Studio, unter 300 Zeilen, kein Ergebnis ändert sich) | nichts |
| P2 | `FullGameSeriesSession` und Ergebnistyp je Partie (S2) | `engine/rules/full_game.py`, Tests | 250 bis 350, 1 Lane-Tag | **ja** (Engine-Datei, Evidenz-Grundlage) | E-1 |
| P3 | Pool, Worker, Journal, Manifest, `procs.py`; Batch-Serie hinter Schalter (S3) | neu `game_pool.py`, `pool_worker.py`, `series_store.py`, `procs.py`; `simulations.py`, `__main__.py`; Tests | 700 bis 900, 2 Lane-Tage | **ja** (über 300 Zeilen) | P2 |
| P4 | Gepaarte Serie und `compare-decks` als Kunden (S4) | `paired_comparison.py` (nur Ausführungsteil ab `:776`), `paired_series.py`, `__main__.py`, Tests | 400 bis 600, 1,5 Lane-Tage | **ja** (Größe; wegen der Stopp-Regel Review aus frischem Kontext, wie #1523 es verlangt) | P3 |
| P5 | Ein Verwalter, Schalter wird Vorgabe, alte Wege weg, Lastregel, Messskript, Doku (S5) | `series_manager.py` neu, `simulations.py`, `paired_series.py`, `web.py` (nur Einhängung), `hostload.py` neu, `scripts/`, `docs/STUDIO_GAME_VIEWER.md:101` | 600 bis 900, 1,5 Lane-Tage; teilbar in Verwalter und Lastregel | **ja** (Größe, Vorgabe ändert sich) | P4, Owner-PC-Lauf für die Vorgabe |

Summe 6,5 Lane-Tage (±40 %). Jedes Paket führt den Äquivalenznachweis aus Abschnitt 8, der zu ihm gehört:
P1 Hash je Partie; P2 A1 auf Python-Ebene; P3 A1, A2, A9; P4 A3 bis A6, A10; P5 A7, A8. Kein Paket ändert
`engine-bridge/`, `qualification/`, `pyproject.toml`, Workflows oder den Pin. PRs sagen `Refs`.

## 11. UNKNOWN

| # | Was | Wie zu klären |
|---|---|---|
| U-1 | E-1: Grundlage des Partie-Ergebnisses; ob P1 trotz Berührung der Fortschrittsanzeige nicht MATERIAL ist | Lead/Owner |
| U-2 | Ob „Orchestrierer 3 → 1“ den interaktiven Verwalter einschließt. Dieser Entwurf zählt die drei Stellen, die für Serien Prozesse starten (`simulations.py:1039-1047` mit `:1244`, `paired_comparison.py:902-910/973-981`, `:746-773`), und lässt den Protokolltreiber bei D-3 | Lead |
| U-3 | Identität bei gemischten Tischen in einer JVM und einem Python-Prozess, bei Positionen über 16, nach minutenlangem Warten | A3, M1, M2 |
| U-4 | Speicherverlauf über 16 Partien; Leck oder Heap-Zuschnitt | M1, M4 |
| U-5 | Windows: Verhalten nach hartem Beenden, ob eine hängende JVM bei stdin-Ende endet, `taskkill`-Baum, Priorität, Virenscanner auf den Slot-Ordnern | Owner-PC-Lauf, P5 |
| U-6 | Owner-PC: Kerne, RAM, Java-Version; Nutzen von mehr als 6 Workern; Skalierung über Hyperthreads | Protokoll Abschnitt 6 |
| U-7 | Schwellen der Lastregel | zwei Messpunkte vorhanden; Zelle p5 |
| U-8 | Anteil des Fensterleerlaufs; Anteile der vier Ursachen aus #1585 | A5 mit Zeitreihe je Worker |
| U-9 | Ob `compare-decks` die Variante absichtlich nicht ausrichtet | Lead |
| U-10 | Ob `shutdown_game` nach natürlichem Partie-Ende immer `game_over: true` meldet; welche Werte `shutdown_unwind` annimmt | in P2 mitschreiben, nicht als Fehler werten |
| U-11 | Durchsatz mit 4 Workern und langem JVM-Leben: zwischen 595 und 967 ist nichts gemessen [M] | A5 |
| U-12 | Statistische Wirkung der Wiederholungsregel | Statistik-Review vor Einschalten |
| U-13 | Stand und Zeitpunkt von #1584; Ausgangswert mit neuer JAR | nach dessen Merge messen |
| U-14 | Ob die Stück-`.out`-Dateien heute wirklich als gescheiterte Partien in der Liste erscheinen | am laufenden Studio prüfen |
| U-15 | Claim-Tabelle #1167 und Kommentare der Issues #1523, #1544 nicht gelesen; offene PRs am 2026-11-19: #1609, #1611, #1614, keiner auf den Serien-Dateien | vor dem Start prüfen |

Nicht geprüft: Laufzeitverhalten jeder Art (Auftrag: keine Engine-Läufe), die Java-Seite über die
genannten Stellen hinaus, `play.py` ab Zeile 409 (interaktiver Teil), die Tests im Einzelnen.
