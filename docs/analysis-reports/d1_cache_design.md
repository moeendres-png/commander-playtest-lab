# D-1 Cache-Schicht neu: Entwurf (Option D, Tracking #1612)

Stand: `main` @ `2a2bd4d5` (2026-11-19, enthält #1609 als `cc58e5b6`); PR #1611 offen, Head
`f670cefd`. Nur gelesen und an Wegwerf-Dateien gemessen: keine Suite, kein Engine-Lauf, kein Server,
nichts gepusht oder kommentiert. Alle Zeilenangaben gelten für `2a2bd4d5`, Pfade ohne Präfix
liegen unter `src/commander_lab/studio/`.
Legende: **[M]** hier gemessen (Skripte unter
`/tmp/claude-0/-home-user/ef006e8b-893c-5ebd-80a1-8743a09c7458/scratchpad/d1design/tools/`,
Python 3.13.18, SQLite 3.53.1, Maschine fremdbelastet, 1-Minuten-Last 5,9 bis 8,5),
**[D]** Issue, PR oder Messbericht sagt es, **[S]** statisch aus dem Code abgeleitet (Obergrenze,
kein Beweis), **[V]** Vermutung.

## 0. Ergebnis zuerst

1. **Ein Mechanismus, an Ort und Stelle in `cache.py`**, Signatur `cache.cached(store, key, compute)`
   bleibt (22 Aufrufstellen). Die Art eines Eintrags ist wie heute `key[0]` (`cache.py:33-35`,
   #1611 `IMPORT_ONLY`). Neu ist ein Register je Art: gelesene Tabellengruppen, Wertform, Grenzen,
   Sperr-Ebene, Aufwärm-Rang.
2. **Sieben Gruppen über alle 44 Tabellen** (IMPORT 27, DECKS 9, MARKS 2, PROFILES 2, SIMULATION 2,
   SNAPSHOT 1, META 1) [M: `kind_reads.py`]. Je Store-Datei ein Generationszähler je Gruppe, verankert
   am Dateistempel. Ein Eintrag gilt, solange der Stempel dem Anker gleicht und die Zähler seiner
   Gruppen unverändert sind.
3. **Abhängigkeiten werden deklariert, nicht zur Laufzeit erfasst.** Die Erfassung per Authorizer
   prüft die Deklaration (Tests immer, Betrieb per Schalter) und kann sie nur verschärfen. Grund: Eine
   dauerhaft installierte Erfassung übersieht wiederverwendete Statements (gemessen, 1.2).
   Die **Schreibseite** dagegen wird zur Laufzeit beobachtet (Authorizer auf der einen schreibenden
   Verbindung, kein blinder Fleck gefunden): geschriebene Gruppen werden gesehen, nicht geglaubt.
4. **Fremde Schreiber verwerfen alles.** Beweis eines eigenen Schreibvorgangs wie in #1611
   (`PRAGMA data_version` der Schreibverbindung unverändert, Rollback-Journal, Zählerdifferenz),
   plus eine neue Pflichtregel: der Stempel vor dem Schreibfenster muss dem Anker gleichen (1.4, I3).
5. **Option A wird empfohlen**, als „Nutzerzustand als dünne Auflage“: `pool_cards` = Kernlesung
   ohne Markierungen plus Auflage aus zwei Abfragen. Damit überleben `strength` und `evidence` den
   Favoriten-Klick, und `pool`/`layers` rechnen nur noch die Auflage neu.
6. **Fünf PRs** (P1 Kern, P2 Deklarationen und `memo`-Ablösung, P3 Option A, P4 Aufwärmen und
   Datenbericht, P5 Aufräumen), alle MATERIAL. #1609 ist Bestandteil, #1611 wird vor P1 gemergt
   oder von P1 übernommen (Abbildung in 7.1). Keine neue Abhängigkeit, kein Schema-Umbau.

## 1. Abhängigkeitsmodell

### 1.1 Gruppen

| Gruppe | Tabellen | Schreiber im Serverprozess |
|---|---|---|
| IMPORT (27) | `card`, `inventory`, `card_location`, `scryfall_card`, `card_printing`, `scryfall_token`, `scryfall_card_token`, `card_ruling`, `card_ruling_source`, `corpus_deck`, `corpus_deck_card`, `corpus_cohort`, `corpus_deck_part`, `corpus_deck_stat`, `corpus_deck_role`, `commander_binding`, `neutral_board_row`, `observation`, `card_signal`, `card_role`, `card_role_claim`, `commander_combo`, `playgroup_card_atlas`, `playgroup_top_commander`, `playgroup_final_zone`, `source`, `source_capture_event` | nur `save_batch_to_store` (`source` über `simulations.py:653`, `commander_binding` `:729-737`) |
| MARKS (2) | `card_mark`, `card_label` | Favorit `web.py:1474`, Markierung `:1485`, Karten-Label `:1506` |
| DECKS (9) | `deck`, `deck_revision`, `deck_revision_card`, `deck_branch`, `deck_draft`, `deck_label`, `deck_primer`, `deck_module`, `deck_module_card` | Deck-Label `:1522`, Deck anlegen `:1555`, Entwurf `:1596/1624/1652`, Revision `:1663`, Module `:1702/1723/1734/1754`, Primer `:1784` |
| PROFILES (2) | `universe_profile`, `strength_profile` | `:979`, `:1000`, `:882`, `:897` |
| SIMULATION (2) | `simulation_run`, `simulation_card` | `save_batch_to_store` (`simulations.py:591-739`, Aufruf im Serien-Thread `:1065`) |
| SNAPSHOT (1) | `tier_snapshot` | keiner; einziger Schreiber ist `import_all.py:711` (CLI) |
| META (1) | `meta` | keiner; `field_read.py:204` und Migration `store.py:827/860` (CLI, Öffnen) |

Zählung: 44 `CREATE TABLE` in `store.py:38-520`, die Sicht `card_fact` (`store.py:527-545`) zählt
als ihre Basistabellen `card` und `scryfall_card`. 18 Routen schreiben den Store, 0 davon `GET`
[S: `route_writes2.py`, modulaufgelöster Aufrufgraph, 114 Routen]; dazu genau ein
Hintergrund-Schreiber im Prozess (Serien-Thread). Alle Importer laufen als eigener Prozess
(47 CLI-Unterbefehle, `__main__.py`), sind für den Server also fremd.

Warum IMPORT nicht feiner: es gibt im Serverprozess keinen Schreiber, der nur einen Teil davon
schreibt; eine Unterteilung brächte mehr Deklarationen ohne eine einzige ersparte Neuberechnung.
Warum Nutzerzustand in MARKS/DECKS/PROFILES geteilt: das ist Option B aus #1561 ohne
Sondermechanik (Primer, Entwurf, Deck-Label lassen jeden Eintrag stehen, der nur MARKS oder
PROFILES liest). FK-Kaskaden bleiben in der Gruppe: die drei `ON DELETE CASCADE`
(`store.py:218/226/233`) liegen alle in DECKS.

Pflichttest: jede Tabelle des Schema-Texts steht in genau einer Gruppe (eine neue Tabelle ohne
Gruppe macht den Test rot und erzwingt die Entscheidung).

### 1.2 Deklarieren oder automatisch erfassen

| | Deklariert (Register je Art) | Automatisch je Eintrag (Authorizer beim Rechnen) |
|---|---|---|
| Korrektheit | Richtig genau dann, wenn die Deklaration alle Lesepfade abdeckt. Ein Trace kann sie nur widerlegen, nicht beweisen: datenabhängige Zweige fehlen im Trace (Beleg: #1611 misst für `evidence` kein `universe_profile`, der statische Pfad `pool_cards` → `builder_counted_universe` (`builder.py:627`) → `universe.py:414` existiert [S]). Fehler ist eine sichtbare, prüfbare Zeile | Im Prinzip genauer (was nicht gelesen wurde, kann das Ergebnis nicht geändert haben). Praktisch drei stille Lücken: (a) dauerhaft installierter Authorizer meldet bei erneuter Ausführung desselben Statement-Texts **nichts** [M: zweite Ausführung `[]`, erst nach erneutem `set_authorizer` wieder `['a','b']`], ein innerer Eintrag erbt also die Lesungen des äußeren nicht; (b) Zwischenspeicher je Verbindung verdecken Lesungen (`StudioStore._epoch_cache`, `store.py:1058-1067`: zweiter Aufruf von `data_epoch()` führt kein SQL aus); (c) Treffer auf einen inneren Eintrag führen kein SQL aus, die Abhängigkeit muss vererbt werden. Jede Lücke heißt: veralteter Wert, unbemerkt |
| Kosten Laufzeit | 0 | +17 µs je Statement-Übersetzung (36,0 → 53,0 µs, 35 Rückrufe für einen Join mit 31 Spalten) [M]; bei 491 `execute` der Aufwärmphase [D: A3] etwa 8 ms. Lücke (a) schließt nur ein Neu-Installieren je Rechenrahmen (alle Statements der Verbindung verfallen) |
| Kosten Bau | Register mit rund 30 Zeilen; je Art ein Tracer im Test (Muster #1611: „eine Art ohne eigenen Tracer macht den Test rot“) | Authorizer in jeder Verbindung (`store.py:820`), Rahmenstapel je Thread, Vererbung, Konflikt mit dem Commit-Zähler aus #1611 (ein Trace-Rückruf je Verbindung) |
| Wartbarkeit | Neue Art ohne Deklaration verhält sich wie heute (liest „alles“): langsam, nie falsch. Zu enge Deklaration fällt im Test und im Prüfmodus auf | Kein Aufwand je Art, dafür unsichtbare Maschine; ein neuer Zwischenspeicher irgendwo im Paket bricht die Korrektheit, ohne dass ein Test es merkt |

**Empfehlung: deklarieren, die Erfassung als Prüfer einsetzen.** Gültigkeit hängt allein an der
Deklaration. In Tests immer und im Betrieb per Umgebungsschalter (Prüfmodus) läuft die Erfassung
mit; liest eine Rechnung eine Tabelle außerhalb ihrer Deklaration, schlägt der Test fehl, im Betrieb
wird der Eintrag auf „liest alles“ erweitert und gezählt. Die Erfassung kann so nur vorsichtiger
machen, ihre Lücken können nie zu einem veralteten Wert führen. Zusätzlich im Test die statische
Obergrenze aus dem Aufrufgraphen (`kind_reads.py`): statisch erreichbare Gruppen ⊆ deklarierte.

**Schreibseite anders, mit Begründung:** Im Schreibfenster arbeitet genau eine Verbindung, ohne
verschachtelte Rahmen. `set_authorizer` beim Eintritt lässt ältere Statements verfallen
[M: vor der Installation übersetztes Statement wird danach gemeldet]. Gemeldet werden auch
Trigger- und FK-Kaskaden-Schreibzugriffe [M: `DELETE` auf Elternzeile meldet Kind-Tabelle; Trigger
meldet Zieltabelle]. Kosten: unter 1 ms je Schreibroute [M: 17 µs je Übersetzung]. Daher: jede
Schreibroute **deklariert** ihre Gruppen und die Schicht **beobachtet** sie. Beobachtet ⊄ deklariert
heißt im Test Fehler, im Betrieb „alles verwerfen“ plus Zähler. Jede andere Aktion als
INSERT/UPDATE/DELETE auf `main` (DDL, `PRAGMA` mit Wert, `ATTACH`, `VACUUM`) gilt als „alles“.

**Importer:** deklarieren ihre Gruppen als Daten im selben Register (z. B. `import-marks` → MARKS,
`importers.py:480/1398`, `marks.py:166`; `import-simulation` → SIMULATION und IMPORT,
`importers.py:1273-1300`; `import-all` → zusätzlich SNAPSHOT). Das hat heute **keine
Laufzeitwirkung**, weil der Server einen fremden Prozess nicht beweisen kann; es dient dem Test
(beobachtet ⊆ deklariert) und einem späteren Import im Serverprozess.

### 1.3 Register (Skizze, `mypy strict`, keine neue Abhängigkeit)

```python
class Group(enum.Enum): IMPORT; MARKS; DECKS; PROFILES; SIMULATION; SNAPSHOT; META
ALL: Final = frozenset(Group)
TABLE_GROUP: Final[Mapping[str, Group]]          # 44 Tabellen, vollständig

@dataclass(frozen=True, slots=True)
class Kind:
    reads: frozenset[Group] = ALL                # Vorgabe: wie heute
    seal: Literal["bytes", "frozen", "copy", "shared"] = "shared"   # "shared" nur im Übergang
    level: int = 0                               # Sperr-Ebene (Abschnitt 4)
    max_entries: int = 4                         # Pflicht, kein unbegrenzter Typ
    max_bytes: int | None = None
    warm: int | None = None                      # Aufwärm-Rang (Abschnitt 5)

def cached[T](store: StudioStore, key: tuple[Hashable, ...], compute: Callable[[], T]) -> T: ...
@contextmanager
def write(store: StudioStore, groups: Collection[Group]) -> Iterator[None]: ...
```

Zustand je Store-Pfad: `anchor` (Stempel wie `cache.py:68-87`) und `gen[Group]`. Eintrag:
Schlüssel `(Pfad, Art, Parameter)`, dazu Wert, die Generationen seiner `reads`, Gewicht. Flug
(gemeinsame Berechnung) je `(Pfad, Art, Parameter, Generationen)`: nach einem Schreibvorgang auf
eine fremde Gruppe ist der Flugschlüssel unverändert, gleichzeitige Anfragen teilen die laufende
Rechnung weiter. Das ist der Unterschied zum Umschlüsseln in #1611 (`_carry`), wo ein Eintrag,
der während des Klicks gerade rechnet, verworfen wird (`cache.py:121`: nur merken, wenn der
Stempel gleich blieb).

Was nicht im Store steht, gehört in den Schlüssel, wie heute: Datum (`web.py:446`), Dateistempel
(`answer_cache.py:98`, `web.py:501` `card_understanding.stamp()`), alle Parameter.

### 1.4 Invarianten

- **I1 Anker.** Ausgeliefert wird nur, wenn der aktuelle Stempel dem Anker gleicht und die
  gemerkten Generationen den aktuellen entsprechen. Kein Stempel (Store im Speicher, offene
  Transaktion, Datei unlesbar: `cache.py:71-86`) heißt rechnen ohne merken, wie heute.
- **I2 Fail closed.** Jede Stempeländerung, die kein abgeschlossenes, bewiesenes Schreibfenster
  erklärt, erhöht alle Generationen und verwirft alle Einträge des Pfads. Das trifft: zweiter
  Prozess, direktes SQL, Import, eine Route ohne `write()` (vergessene Einhängung = heutiges
  Verhalten), `VACUUM` (`store.py:868`), Migration beim Öffnen.
- **I3 Fenster.** Ein Schreibfenster zählt nur, wenn (a) der Stempel bei Eintritt dem Anker gleicht
  (sonst zuerst I2), (b) die Bedingungen aus #1611 halten (Rollback-Journal: Header-Bytes 18/19 = 1,
  keine `-wal`/`-journal`-Datei, keine offene Transaktion, `PRAGMA data_version` der
  Schreibverbindung vor und nach gleich, Zählerdifferenz = eigene ändernde Commits),
  (c) beobachtete Gruppen ⊆ deklarierte. Dann steigen nur diese Gruppen, der Anker wird der Stempel
  danach. Reihenfolge wie in #1611: `data_version` zuerst und zuletzt, die Stempel dazwischen.
  Ohne (a) würde ein fremder Commit **vor** dem Fenster vom eigenen Beweis verdeckt; #1611 deckt
  das implizit ab (umgeschlüsselt wird nur „genau der Stempel davor“), im Generationenmodell muss
  es ausdrücklich stehen und hat einen eigenen Mutationstest (8, m4).
- **I4 Rechnen über eine Änderung hinweg.** Nach `compute()` wird der Stempel neu gelesen und
  abgeglichen; gemerkt wird nur, wenn die Generationen der gelesenen Gruppen noch die vom Start
  sind (heute: nur bei gleichem Stempel, `cache.py:120-121`).
- **I5 Im Schreibfenster kein Cache.** Der schreibende Thread rechnet direkt und merkt nichts
  (gleiche Regel wie heute bei offener Transaktion, `cache.py:72`; `decks.py:223`).
- Fehler im Fenster oder ein Fenster ohne Beweis: alles verwerfen (wie #1611). Fenster ohne
  Dateiänderung (Stempel gleich): nichts tun.

### 1.5 Zähler- und Stempel-Auflösung

| Signal | sieht eigenen Commit | sieht fremden Commit | WAL | Kosten | Befund |
|---|---|---|---|---|---|
| Dateistempel: Header-Bytes 24–27, Größe, mtime, WAL-Größe/-mtime (`cache.py:68-87`) | ja, +1 je änderndem Commit [M] | ja, auch zweiter Prozess | Header-Zähler +0 [M], nur über die WAL-Datei | 24 µs [M, Last 8] | Anker der Leseseite. Sagt nicht, wer schrieb |
| `PRAGMA data_version` der Schreibverbindung | nein [M] | ja, vor und nach dem eigenen Commit im Fenster [M] | ja [M] | einmal je Fenster | der Beweis „niemand sonst im Fenster“ |
| Zählerdifferenz = eigene ändernde Commits (#1611) | – | – | nein | – | allein nicht hinreichend: ein mitgezählter Commit ohne Seitenänderung plus ein fremder ergibt dieselbe Differenz [M]. `UPDATE` auf denselben Wert: `total_changes` +1, Zähler +0 [M], die Zählregel aus #1611 zählt dann 1 zu viel und verwirft (sichere Richtung). Bleibt als zweite Probe |
| `PRAGMA data_version` einer langlebigen Wächter-Verbindung | ja | ja | ja | 6–8 µs [M] | Werte zweier Verbindungen nicht vergleichbar [M: zwei frische 1/1, Wächter 3]. Braucht dauerhaft offenen Datei-Handle: Verhalten unter Windows (Löschen, Wiederherstellen aus `backup.py`) UNKNOWN. **Nicht für D-1**; Option, falls der Store je auf WAL geht |
| Datenepoche (`store.py:1024-1067`) | – | – | – | 175 ms ungepuffert [D: A1] | sieht Änderungen an bestehenden Zeilen nicht (`builder.py:291-293`, `memo.py:17-20`). Kein Gültigkeitssignal (Auflage 5 in #1561) |
| Schema-Skript bei jedem Öffnen (`store.py:823`) | Zähler +0 [M] | – | – | – | bewegt den Stempel nicht |

WAL-Store (Header 18/19 = 2): keine Fenster-Buchung, jede Änderung verwirft alles. Der Store ist
heute im Modus `delete` [D: A4] und der Code setzt keinen `journal_mode` [M: grep].

## 2. Werte unveränderlich oder kopiert

Heute: „must treat the returned value as read-only“ (`cache.py:91`, `memo.py:31`), Kopien an
`web.py:446`, `:546`, `builder.py:211` (`dict(...)`), Bytes in `answer_cache.py`.
`overall_rating.with_overall` kopiert nur die Kartenzeile flach (`overall_rating.py:623`), die
verschachtelten `components` teilen sich `strength` und `strength_overall`.

Gemessen an einer synthetischen Antwort von 10,6 MB (927 Karten × 22 Komponenten) [M, n = 3,
Minimum, Last 8,4]:

| Mechanismus | Kosten | Urteil |
|---|---|---|
| Bytes merken (`validate_python` + `dump_json`, #1609) | 24 ms einmal, danach 0 je Treffer | **für Antworten**: unveränderlich durch Bauart, 10,1 MB statt rund 22,6 MB Objektgraph |
| `copy.deepcopy` je Treffer | 117 ms | nur für kleine Werte (Grenze 1 MiB im Register) |
| `json.loads` der Bytes je Treffer | 92 ms | nein |
| rekursiv einfrieren (`MappingProxyType`, `tuple`) | 50 ms einmal | nicht für Antworten: pydantic und `json.dumps` können `mappingproxy` nicht serialisieren [M], und 675 `isinstance(`-Stellen im Paket [D: Bewertung 1.5] erwarten zum Teil `dict`/`list` (z. B. `evidence.py:520`) |
| Prüfsumme (`blake2b`) je Treffer | 17 ms | nur Prüfmodus |

Drei Wertformen im Register:

- **`bytes`** für Routen-Antworten. Schon so: `pool`, `evidence`, `rating-layers`, `roles/audit`,
  `universe/counted`, `deck-browser` (`web.py:670/740/817/837/950/2217`). Neu: `strength`
  (11,8 MB; heute `dict`, FastAPI serialisiert je Aufruf: 1,6 ms Rechnen, Rest Serialisierung,
  warm 74 ms [D: A3/A2]), `layer_overview`, `data_report` (die frischen Teile werden um die
  gemerkten Abschnitte herum gesetzt, 5).
- **`frozen`** für innere Kennzahlen, die zwischen Rechnungen geteilt werden und für eine Kopie zu
  groß sind (`corpus_deck_sets`, `corpus_hits`, `universe_decks` mit 7,5 MB serialisiert,
  `memo.py:27-29`). Mechanismus: die Rechnung liefert unveränderliche Typen (`frozenset`, `tuple`,
  oberste Ebene `MappingProxyType`), die Signaturen wechseln auf `Mapping`/`Sequence`/`AbstractSet`.
  Damit lehnt **mypy** jede Veränderung an allen Aufrufstellen ab; der Laufzeitschutz kostet eine
  einmalige Umwandlung. Vorbild: `package_candidates` (`packages.py:242-246`), `resolve`
  (`universe.py:642`), `slot_catalog` (`combos.py:558`).
- **`copy`** für kleine veränderliche Werte (`status_store_part` `web.py:546`, `cohort_sizes`).
- `shared` (heutiges Verhalten) nur im Übergang; P5 endet mit einem Test „keine Art ist `shared`“.

Prüfmodus: beim Merken eine Prüfsumme, bei jedem Treffer verglichen. Das beantwortet das UNKNOWN
der Bewertung („ob geteilte Werte heute irgendwo verändert werden“) in P1, bevor eine Form
umgestellt wird.

## 3. Speichergrenzen, Verdrängung, unbegrenzter Parameterraum

Heute: `MAX_ENTRIES = 64` (`cache.py:29`), `answer` 16 Einträge / 48 MiB (`cache.py:35`), `memo`
64 gesamt und 8 für `universe_decks` (`memo.py:43-44`), dazu drei handgebaute Wörterbücher mit
„bei 16 leeren“ (`builder.py:724-758`, `sources.py` Combo-Karten, `answer_cache.py:46-48`).
Prozessspeicher: 570–579 MB nach der Aufwärmphase [D: A1], 711/721 MB nach 37 × 6 Anfragen
[D: #1609]; voller Cache nicht gemessen [D: #1615 Punkt 6].

Entwurf:

1. **Grenze je Art ist Pflicht** (`max_entries`, für `bytes` zusätzlich `max_bytes`). Erledigt #1615
   Punkt 3 (`slot_catalog`, `cohort_sizes` verdrängen sonst warme Antworten) als Regel statt als
   Einzelfall.
2. **`answer` wird je Route eine eigene Art** (`answer:pool`, `answer:evidence`, …). Erledigt #1615
   Punkt 2 an der Wurzel: eine Sammelart kann nie eine einheitliche Deklaration tragen
   (`pool` liest `card_mark`, `deck-browser` liest `deck_label`).
3. **Verdrängung:** innerhalb der Art nach letzter Nutzung. Über Arten hinweg zuerst Antworten
   (billig aus Kennzahlen wiederherstellbar), zuletzt Basis-Kennzahlen der Ebene 0 (Sekunden).
   Gesamtgrenzen als Startwerte: Antworten 96 MiB (4 × `strength` 47 MB, 2 × `evidence` 11 MB,
   Rest rund 10 MB), Kennzahlen 64 Einträge wie heute. Bestätigung per Messung in P1.
4. **Sofort freigeben:** steigt eine Gruppe, fallen alle Einträge, die sie lesen (heute nur für
   alte Stempel, `cache.py:126-131`).
5. **Unbegrenzter Parameterraum** (Suche in `deck-browser` `web.py:2206-2243`, Regler in `strength`
   über `settings`-JSON `web.py:495`, freie Universums-Spezifikation `universe.py:641`, Decklisten in
   POST-Körpern): die Grenze je Art verhindert, dass solche Schlüssel fremde Arten verdrängen;
   Schlüssel über 256 Byte werden als `blake2b`-Auszug gehalten; Antworten über 1 MiB aus einer
   offenen Art werden erst beim zweiten gleichen Aufruf gemerkt (kleine Vormerkliste, 256 Auszüge).
6. **Durchläufe** (`cache.read_only()`, `web.py:443`, Datenbericht über 104 Commander) bleiben:
   lesen ja, merken nein.

## 4. Parallelität

Heute: gemeinsame Berechnung je Schlüssel (`_KeyLock`, `cache.py:40-51`, `:103-141`), Hierarchie
nur als Text (`cache.py:95-98`); `memo` rechnet ohne gemeinsame Berechnung doppelt (`memo.py:97-111`).

| Sperre | hält über | Regel |
|---|---|---|
| L1 Zustand | Wörterbuch-Zugriffe | nie über Rechnen, SQL oder Datei-Lesen |
| L2 Flug je Schlüssel (`RLock`) | die Rechnung | eine Rechnung der Ebene n darf nur Arten mit Ebene < n anfordern; die Schicht prüft das am Rahmenstapel des Threads (Fehler im Test und Prüfmodus). Die Prosa aus `cache.py:95-98` wird Daten (`Kind.level`) |
| L3 Schreibfenster je Store-Pfad | den `write()`-Block | reihenfolgt eigene Schreiber (SQLite lässt ohnehin nur einen zu). Im Block nimmt der Thread nie L2 (I5), daher kein Kreis L3 ↔ L2 |

- **Leser während eines Fensters:** Stempel = Anker → schneller Pfad, ohne L3. Stempel ≠ Anker →
  auf L3 warten, Stempel neu lesen: gleicht er jetzt dem Anker, war es das eigene Fenster; sonst I2.
  So wird ein laufender eigener Schreibvorgang nicht als fremd verworfen.
- **Thundering Herd nach einem Klick:** die Seite feuert mehrere Routen (Startseite 17–18
  API-Anfragen [D: A5]). Betroffene Arten rechnen einmal (L2), unberührte bleiben Treffer.
- **Nach einem fremden Schreibvorgang:** alles neu, je Schlüssel einmal; das Aufwärmen reiht sich
  dahinter ein (5).
- Fehler werden nie gemerkt, der nächste Wartende rechnet selbst (`cache.py:13`). Kein Zeitlimit
  für Wartende (Rechnungen sind deterministisch, kein Netz).
- Zähler je Art (Treffer, Rechnungen, verworfen nach Grund: eigene Gruppe, fremd, Grenze), lesbar
  für Tests und für `/api/status` (keine neue Route nötig).

## 5. Aufwärmen

Heute: ein Daemon-Thread, je Commander sechs Schritte hintereinander (`__main__.py:730-782`,
Start `:794`), 28,1–29,8 CPU-s bei `51185f2d8` [D: A1]. Der Prototyp der inzwischen gemergten
Join-Reihenfolge (#1604, `bbe1eba4`) lag bei 18,8 CPU-s [D]; Wert auf heutigem `main` UNKNOWN.
Befund aus den Messungen: die erste `strength`-Anfrage **während** der Aufwärmphase braucht 16,3 s,
**ohne** Aufwärmen 7,99 s [D: A2]. Das Aufwärmen verdoppelt also die Wartezeit der ersten Anfrage.

Entwurf:

1. **Plan aus dem Register:** Reihenfolge nach Ebene (Basis-Kennzahlen zuerst), dann nach
   `Kind.warm`. Commander-Reihenfolge: der Commander des zuletzt geänderten Decks zuerst
   (`deck_revision.created_at`, nur gelesen, kein neuer Zustand), danach wie heute alle mit
   `has_data` und `in_collection` (`__main__.py:748`).
2. **Vordergrund hat Vorrang:** die Schicht zählt Anfrage-Threads, die rechnen oder warten. Der
   Aufwärm-Thread beginnt keinen Schritt, solange der Zähler > 0 ist, und wartet danach 200 ms Ruhe.
   Ein laufender Schritt wird nicht abgebrochen (Python kann das nicht); der größte Einzelschritt
   war `_universe_raw_sets` mit 8,5 s in 4 Aufrufen [D: A3], nach #1604 0,62 s je Aufruf [D: A4].
3. **Kein Verhungern:** braucht die Anfrage genau die Kennzahl, die gerade aufgewärmt wird, teilt
   sie die Rechnung (L2, wie heute). Braucht sie eine andere, rechnet sie sofort selbst und der Plan
   überspringt den Schritt später als Treffer.
4. **Abbrechbar:** jeder Schritt prüft die Generationen; nach einem fremden Schreibvorgang wird der
   Plan neu aufgebaut und von vorn begonnen (automatisches Nachwärmen nach Import). Nach
   Nutzerzustands-Schreibvorgängen kein Nachwärmen, die Seite fragt selbst.
5. **Datenbericht ans Ende** (Folgepunkt 3 aus #1562) und in Abschnitte nach Gruppe geteilt
   (`data_report.py:505-525`): schwere Abschnitte `_commanders`, `_roles`, Signal-Alarme, `_corpus`
   lesen nur IMPORT [S]; `_marks_and_games` (`:317`), `_universes` (`:370`), `fallbacks_used`
   (`field_read.py`) und `bridge_qualification` werden je Aufruf frisch gesetzt. Heute rechnet der
   Bericht nach jedem Klick neu (40–42 s, nach #1605 Median 19,2 s [D]); danach nur nach Import
   und Tageswechsel (`_scryfall(db, moment)` `:514` hängt am Datum, das Datum bleibt im Schlüssel).

## 6. Schreib-Entkopplung: Option A

Lage: `pool_cards` liest `card_mark` (`builder.py:552`, Felder `:595-597`) und `card_label`
(`:540`, `:598`). Vier Verbraucher lesen keines dieser vier Felder [S: alle `card[...]`-Zugriffe
gesichtet]: `evidence.pool_evidence` (`evidence.py:516`; `TIER_POLICY.never_inputs`
`evidence.py:71-78` nennt genau diese Felder), `strength_view.rating_layers` (`:804`),
`strength_view` Vorbereitung (`:960`), `sources.calculate_pool_gap_matrix` (`sources.py:771`).
Zwei brauchen sie: die Route `pool` (`web.py:640`) und `layer_overview` (`import_all.py:195`,
Zählung `:305`). Messung dazu: `strength` und `evidence` sind nach einem Favoriten-Klick
byte-gleich [D: A2]; für „ausgeschlossen“, Notiz und Labels fehlt die Messung, dort trägt bisher
nur der statische Befund.

**Entwurf:** `builder.pool_base(...)` = heutige Funktion ohne den `LEFT JOIN card_mark` und ohne
`card_labels`; `pool_cards` = `pool_base` plus Auflage aus `read_marks` (`builder.py:348-359`) und
`labels.card_labels` (`labels.py:46`), mit den vier Feldern an derselben Stelle im Wörterbuch
(zwischen `reserved` und `roles`), sonst ist die Antwort nicht byte-gleich. Die vier Verbraucher
ohne Markierungen rufen `pool_base`.

| Art | liest heute | nach Option A | Favoriten-Klick |
|---|---|---|---|
| `strength`, `strength_overall` | IMPORT, MARKS, PROFILES, SNAPSHOT [D: #1611 Authorizer] | IMPORT, PROFILES, SNAPSHOT | bleibt |
| `answer:evidence` | IMPORT, MARKS, SIMULATION [D] (+ PROFILES [S]) | IMPORT, SIMULATION, PROFILES | bleibt |
| `answer:rating-layers` | IMPORT, MARKS, PROFILES [S] | IMPORT, PROFILES | bleibt |
| `pool_base` (neu, `frozen`) | – | IMPORT, PROFILES | bleibt |
| `answer:pool`, `layer_overview` | IMPORT, MARKS, PROFILES | unverändert | nur Auflage und Serialisierung neu (heute `pool_cards` 0,25–0,27 s [D: A3], `layers` 0,74–1,23 s nach Klick [D: A2]) |
| `land_source_groups` | IMPORT [D: #1611] | unverändert | bleibt (seit #1611) |

Semantische Gleichheit der Auflage: `bool(row["favorite"])` ist für Karten ohne Markierungszeile
`False` (`LEFT JOIN`, `builder.py:595`), `read_marks` liefert nur Karten mit Zeile; fehlende Karte
= `False`/`False`/`""`. `row["note"] or ""` steht an beiden Stellen (`builder.py:354`, `:597`).

**Äquivalenznachweis (Pflicht in P3):**

- E1 Der heutige Rumpf bleibt als Referenz im Test (Muster `_reference_cohort_shapes`,
  `tests/unit/test_studio_perf_equivalence.py:116`). Für die Zustandsfamilie {keine Markierung,
  Favorit, ausgeschlossen, Notiz, Karten-Label, alles zusammen} × {1 Commander, 2 Partner, ohne}
  × {`profile` gesetzt/leer} × {`with_signals` an/aus} × {`strength` gesetzt/leer}:
  `json.dumps(alt) == json.dumps(neu)` ohne `sort_keys`.
- E2 Unabhängigkeit direkt: Antwort von `strength`, `evidence`, `rating-layers`, Lückenmatrix auf
  Zustand S byte-gleich zu S′, das sich nur in `card_mark`/`card_label` unterscheidet (alle sechs
  Zustände). Das ist die Aussage, die bisher nur für den Favoriten gemessen ist.
- E3 Authorizer: die vier Rechnungen lesen weder `card_mark` noch `card_label`
  (`_trace_reads` aus #1611).
- E4 37 Referenzanfragen Basis gegen Kandidat, 0 Abweichungen; Schreibmatrix 8 × 37.
- E5 Gegenproben: `LEFT JOIN card_mark` wieder in `pool_base` → E3 rot; Notiz aus der Auflage
  entfernt → E1 rot; Feldreihenfolge vertauscht → E1 rot.

Bewertung: geringes Risiko (kein Rechenweg der Kennzahlen ändert sich, nur die Leseform),
größter Hebel des Pakets. Option C (Korpus-Kennzahlen als nur-IMPORT) ist Teil von P2 und halbiert
allein nur (3,0 s, davon `corpus_hits` 1,4 s [D: #1561]); Option B ist im Gruppenmodell enthalten.

## 7. Migrationspfad

### 7.1 Nichts wegwerfen: Abbildung von #1609 und #1611

| Vorhanden | wird |
|---|---|
| `answer_cache.dump/json_answer` (`answer_cache.py:73-99`), Byte-Tests | Wertform `bytes`; die Tests bleiben unverändert |
| `KIND_LIMITS`, `_apply_kind_limit` (`cache.py:35`, `:144-159`) | `Kind.max_entries`/`max_bytes` |
| `answer_cache.file_answer`, `file_stamp`, `folder_stamp` (`answer_cache.py:54-123`) | Datei-Arten im selben Register (P5), zusammen mit `builder._cached_combo_partners` und den Combo-Karten in `sources.py` |
| #1611 `IMPORT_ONLY = {"land_source_groups"}` | `Kind(reads={IMPORT})` |
| #1611 `USER_STATE_TABLES` (14 Tabellen) | `TABLE_GROUP`, geteilt in MARKS, DECKS, PROFILES, SNAPSHOT |
| #1611 `user_state_write` samt Beweisbedingungen | `cache.write(store, groups)`; der alte Name bleibt als Alias, bis die 10 eingehängten Routen ihre Gruppen nennen |
| #1611 `_carry` (umschlüsseln) | entfällt als Mechanismus (Generationen), sein Test bleibt als Verhaltenstest: Eintrag wird nach bekanntem Schreibvorgang nicht neu gerechnet |
| #1611 `_trace_reads`, `_import_only_violations`, Schreibmatrix (11 Schreibvorgänge), Negativtest fremder Commit/Import, WAL-Test | allgemeine Deklarationstests über alle Arten und alle 18 Routen |
| #1615 Punkte 1–6 | 1 → P1 (Schlüsseltest `label`, `limit_cards`), 2 und 3 → 3, 4 → UNKNOWN/P5, 5 → außerhalb (D-3), 6 → Abnahme A8 |

Ist #1611 beim Start von P1 noch offen, übernimmt P1 dessen zwei Commits per Merge des Branches
(kein Rebase, Autorschaft und Tests bleiben), statt den Mechanismus neu zu schreiben.

### 7.2 Schritte (jeder für sich mergebar und rückholbar)

1. **S1** `TABLE_GROUP`, `Group`, Register mit allen heutigen Arten (`reads=ALL`, `shared`),
   Vollständigkeitstest über 44 Tabellen, AST-Test „jeder `cached`-Aufruf nennt eine registrierte
   Art“. Kein Verhalten ändert sich.
2. **S2** Generationen und Anker in `cache.py`, `write()` mit beobachteten Gruppen, I1–I5. Mit
   `reads=ALL` verwirft jeder Schreibvorgang weiter alles; einzige Ausnahme `land_source_groups`
   (wie #1611).
3. **S3** Alle 18 Schreibrouten und `save_batch_to_store` eingehängt (10 aus #1611, neu: Stärke-
   und Universumsprofile, 4 Modul-Routen); `cache.invalidate()` an `web.py:993/1007` entfällt.
4. **S4** Grenzen je Art, `answer` je Route, Prüfmodus (Prüfsumme, Lese-Erfassung), Zähler.
5. **S5** Deklarationen der reinen IMPORT-Kennzahlen, je Art mit Tracer: `corpus_deck_ids`,
   `corpus_deck_sets`, `corpus_hits`, `cohort_deck_sets`, `cohort_shapes`, `cohort_sizes`,
   `card_name_index`, `spelling_owners`, `resolve`, `package_candidates`, `package_deck_sets`,
   `deck_evidence_bundle`, `similar_decks_index`, `slot_catalog`; `universe_context` mit PROFILES.
6. **S6** `memo` abgelöst: `universe_options` (`universe.py:436`), `universe_decks` (`:1057`),
   `corpus_oracle_ids` (`import_all.py:331`) als Arten mit `reads={IMPORT}` (Profilinhalt steht
   schon im Schlüssel, `universe.py:1060`); `memo.py` wird Fassade. Verhalten: wie bisher kostet ein
   Favorit nichts; neu sehen sie Änderungen an bestehenden Importzeilen (Lücke `memo.py:17-20`
   geschlossen) und die 2-Sekunden-Sperre `_STAT_GUARD_NS` entfällt.
7. **S7** Wertform `frozen` für die Kennzahlen aus S5/S6 (Signaturen, mypy).
8. **S8** Option A (`pool_base`, Auflage), `strength` als Bytes.
9. **S9** Aufwärm-Plan, Vorrang, Nachwärmen; Datenbericht in Abschnitten.
10. **S10** Datei-Arten vereinheitlicht, `memo.py` entfernt, `shared` entfernt, Importer-Deklarationen.

`store.data_epoch()` bleibt (Identität des gespeicherten Snapshots, `tier_snapshot.py:48-49`,
Spalte `store.py:481`). Reine Funktions-Speicher (`games.py:72`, `builder.py:43`) bleiben.

## 8. Abnahme

| # | Kriterium | Maß |
|---|---|---|
| A1 | Erste `POST /api/strength` nach `PUT /api/cards/{id}/favorite` | < 0,2 s, Median aus 5 (je Klick eine Anfrage, Last notiert); SHA-256 gleich vor dem Klick und gleich einem frisch gestarteten Server. Heute 5,17–5,58 s [D: A2], mit #1611 3,23 s [D] |
| A2 | 37 Referenzanfragen Basis gegen Kandidat, je 6 Aufrufe | 0 Abweichungen (Status, Länge, SHA-256) |
| A3 | Schreibmatrix 8 × 37 (Favorit, „ausgeschlossen“, Karten-Label, Deck-Label, Entwurf, Revision, Primer, Universumsprofil) | 296 Vergleiche erster und gemerkter Aufruf gegen Basis-Server: 0 Abweichungen; am Ende 37/37 gegen frischen Server |
| A4 | Einheitsmatrix 18 Routen + Serien-Thread × alle Arten | beobachtete ⊆ deklarierte Gruppen; Art bleibt genau dann, wenn `reads` ∩ geschrieben leer ist, **beide Richtungen** geprüft |
| A5 | Nach Import (CLI in zweitem Prozess), nach direktem SQL, nach fremdem Commit im Fenster eines Klicks | kein einziger Treffer bis zur Neuberechnung (Zähler), 37/37 gleich frischem Server |
| A6 | „Gecachtes Objekt ändern scheitert“, parametrisiert über das Register | `bytes`/`frozen`: `TypeError`/`AttributeError`; `copy`: zweiter Abruf unverändert; nach P5 keine Art `shared` |
| A7 | Mutationstests, je einer muss einen benannten Test röten | m1 Art fälschlich `reads={IMPORT}` (liest `card_mark`); m2 Route mit zu wenig Gruppen; m3 `data_version`-Probe entfernt; m4 I3(a) entfernt (fremder Commit vor dem Fenster); m5 I4 entfernt (Rechnung über Import hinweg); m6 Tabelle ohne Gruppe; m7 Option A (E5); m8 `json.dumps` statt `dump_json` (vorhanden); m9 `label` oder `limit_cards` aus dem `deck-browser`-Schlüssel entfernt (#1615 Punkt 1) |
| A8 | Speicher | RSS nach Aufwärmen ≤ 637 MB und nach 37 × 6 Anfragen ≤ 793 MB (heute 579 und 721 MB, je +10 %); zusätzlich RSS bei vollem Cache gemessen und berichtet |
| A9 | Erste `strength`-Anfrage während der Aufwärmphase | ≤ 10 s (heute 16,3 s; ohne Aufwärmen 7,99 s [D: A2]); Aufwärm-CPU ≤ heutiger Wert + 5 % |
| A10 | Parallelität | 8 gleichzeitige gleiche Anfragen nach Invalidierung: 1 Rechnung; Ebenenverstoß wirft im Prüfmodus; bestehende Tests aus `test_studio_cache_single_flight.py` mit gleicher Aussage |
| A11 | Rahmen | `pyproject.toml`, `requirements/lock.txt`, `_SCHEMA`, `SCHEMA_VERSION = 21` (`store.py:17`) ohne Diff |

A1 ist erst mit P3 erfüllt. P1 und P2 berichten ihren Zwischenwert ehrlich als „nicht erfüllt“
(wie #1611).

## 9. Risiken und Abbruchkriterien

| Risiko | Folge | Gegenmaßnahme |
|---|---|---|
| Zu enge Deklaration einer Art | veraltete Zahl in der Evidenzanzeige | Vorgabe „liest alles“; je Art Tracer plus statische Obergrenze; Prüfmodus auf dem echten Store vor Owner-Sitzung 1; m1 |
| Beweis des Fensters lückenhaft | fremder Commit wird übernommen | drei unabhängige Proben (I3), m3/m4, WAL und Fehler verwerfen |
| Tests greifen auf Interna zu: `cache._entries` 7×, `cache._flights` 4×, `memo._cache` 2×, `memo._MAX_PER_NAME` 1× in drei Dateien [M: grep] | Anpassung nötig; `AGENTS.md:90` verbietet Abschwächen, `ci-definition-integrity-shadow` meldet | Schlüsselform erst in P1 ändern, Tabelle „alte Zusicherung → neue Zusicherung“ im PR, Review prüft Gleichstärke |
| Kollisionsdateien `web.py`, `__main__.py`, `builder.py` (Onboarding §3) | Konflikte mit laufenden Lanes | in `web.py` nur die Einhängung je Route; Claim in #1612 und #1167; D-2 (Lane 2) berührt `simulations.py`: `save_batch_to_store` absprechen |
| Windows (Dateistempel, mtime, Virenscanner) | Stempel schwankt oder ist teuer | Verhalten wie heute (derselbe Stempel); Messung am Owner-PC als Auflage, nicht als Annahme |
| Antwort-Bytes für `strength` verlieren das Antwortmodell (#1615 Punkt 5) | OpenAPI ist ohnehin aus (`openapi_url=None`) | Byte-Gleichheit je FastAPI-Version im Test (#1609) |
| Mehr Speicher durch Bytes neben Kennzahlen | RSS-Grenze | A8; Zwischenwert `strength` als `dict` nicht mehr halten, wenn nur die Route ihn braucht |

**Abbruchkriterien:** (1) Budget über 6 Lane-Tage (4 + 50 %, #1612). (2) Eine Abweichung in A2/A3
bleibt nach zwei Tagen unerklärt: zurück auf `reads=ALL` für die betroffene Art, das Register
ist der Schalter. (3) E2 scheitert für „ausgeschlossen“, Notiz oder Label: Option A fällt, Abnahme
A1 wird dem Co-Lead als nicht erreichbar gemeldet, P1/P2/P4 bleiben gültig. (4) Der Prüfmodus
findet auf dem echten Store eine undeklarierte Lesung, die sich nicht erklären lässt: Art zurück auf
„liest alles“ und Befund ins Issue. (5) Die Testanpassung in P1 ist ohne Abschwächung nicht
darstellbar: Schlüsselform `(Stempel, Art, …)` behalten und Generationen als Umschlüsseln bauen
(#1611-Weg, verliert nur die laufenden Rechnungen über einen Klick).

## 10. PR-Schnitt

| PR | Inhalt (Schritte) | MATERIAL | Wirkung |
|---|---|---|---|
| P1 Kern | S1–S4, #1615 Punkt 1–3 | ja (Gültigkeit aller gemerkten Zahlen, > 300 Zeilen, Tests angepasst) | keine sichtbare; `land-advisor` wie #1611; Profile und Module verwerfen nicht mehr alles |
| P2 Deklarationen | S5–S7 | ja (Evidenzzahlen) | Option C: erste `strength` nach Klick etwa halbiert [D: 3,0 s, davon 1,4 s `corpus_hits`] |
| P3 Option A | S8 | ja (Lesepfad von `strength`/`evidence`) | A1 erfüllt; `pool`, `layers` nach Klick nur Auflage |
| P4 Aufwärmen und Datenbericht | S9 | ja nach Größe (`__main__.py`, `web.py`, `data_report.py`) | A9; Datenbericht nicht mehr nach jedem Klick |
| P5 Aufräumen | S10 | ja (entfernt `memo.py`, Testumzug) | ein Mechanismus, keine Art `shared` |

Reihenfolge: (#1611 mergen oder in P1 übernehmen) → P1 → P2 → P3 → P4 → P5. P4 hängt nur an P1
und kann vor P2 gezogen werden, wenn die Owner-Sitzung die Aufwärmphase früher braucht; P3 braucht
P1, nicht P2. Voraussetzung für alle: der Antwort-Vergleich aus D-0 (37 Anfragen) als Werkzeug im
Repo, sonst hängt jeder Nachweis an Skripten außerhalb.

## 11. UNKNOWN

- **Owner-PC (Windows):** Kosten und Stabilität des Dateistempels, mtime-Auflösung, Virenscanner,
  Sperrverhalten; ob der Store in einem Sync-Ordner liegt (`memo.py:22-24`).
- **SQLite-Version am Owner-PC:** das Verhalten „`UPDATE` auf gleichen Wert bewegt den Zähler
  nicht“ ist nur auf 3.53.1 gemessen.
- **Lesemengen:** per Authorizer belegt sind nur drei Arten (#1611). Alle anderen Angaben in 6 und
  7.2 sind statisch [S] und in P2/P3 zu belegen. Die Abschnittsaufteilung des Datenberichts ist
  nicht getraced.
- **Unabhängigkeit von „ausgeschlossen“, Notiz und Labels** für `strength`/`evidence`: nicht
  gemessen (nur Favorit), E2 klärt es.
- **Ob geteilte Werte heute verändert werden:** nicht geprüft; der Prüfmodus in P1 beantwortet es.
- **Speicher je Kennzahl** und RSS bei vollem Cache (#1615 Punkt 6); die Grenzen in 3 sind
  Startwerte.
- **Aufwärm-CPU auf heutigem `main`** nach #1604; die Schwelle in A9 ist aus alten Messungen
  abgeleitet.
- **Alle eigenen Zeiten** unter Last 5,9–8,5 gemessen, synthetische Antwort statt echter
  `strength`-Antwort; Verhältnisse belastbar, Absolutwerte nicht.
- **Dateistempel gleicher Größe im selben Tick** (#1615 Punkt 4) und `combos._load_template_snapshot`
  (`combos.py:473`, Schlüssel nur der Pfad, sieht Dateiänderungen erst nach Neustart): ob gewollt.
- **Koppelung Serie → Datenepoche:** `save_batch_to_store` legt eine `source`-Zeile an
  (`simulations.py:653`), die Datenepoche zählt `source` (`store.py:1025`), damit wird der
  Tier-Snapshot nach jeder gespeicherten Serie als veraltet gemeldet (`tier_snapshot.py:242-246`) [S].
  Nicht ausgeführt, nicht Teil von D-1; gehört dem Co-Lead vorgelegt.
- **Ob CLI-Importe in der Praxis bei laufendem Server laufen** und wie oft; davon hängt der Wert
  des Nachwärmens ab.
- **Review-Ausgang von #1611**; der Entwurf nimmt an, dass dessen Beweisbedingungen bestehen.
