# Studio: Export-Format des Nutzerzustands `studio-user-state-2`

Stand: 2026-11-24, Refs #1668 (K-2a), #1703 (K-2a2), #1656, #1167. Grundlage: Owner-Entscheid
E15 Q9 und Charta v2 §3.2 E-A2/E-A6. Diese Seite beschreibt das Format `studio-user-state-2`
(abwärtskompatibel beim Lesen/Importieren von `studio-user-state-1`), die Befehle und das
Prüfmittel. Die Migration selbst (Dateischnitt, Schema 22, K-2c bis K-2e) ist ein eigenes Paket.

## 1. Zweck

1. **Sicherung**: eine kleine Datei (kB bis MB) mit allem, was der Nutzer selbst angelegt hat,
   unabhängig von den 254 MB Importdaten im Store (Zahl: Sandbox-Kopie, nicht der Owner-PC; dort
   `UNKNOWN`).
2. **Migrationsweg**: Phase 2 liest diese Datei in das neue Nutzer-Schema (Karten über
   `oracle_id`).
3. **Prüfmittel**: Export, Import, Export ergibt denselben Inhalts-SHA-256; das ist die
   Rundlauf-Prüfung vor und nach jeder Schema-Änderung.

Nutzerdaten gehören nie ins Repository (`AGENTS.md` §12). Die Export-Datei eines echten Stores wird
nicht eingecheckt und ihr Inhalt steht in keinem Bericht; berichtet werden nur Zeilen je Tabelle
und Zahlen. Alle Fixtures der Tests sind synthetisch. `export-state --to` verweigert ein Ziel im
Repository.

## 2. Datei

gzip-komprimiertes JSON, UTF-8, ein Objekt:

| Feld | Inhalt |
|---|---|
| `format` | `studio-user-state-2` (Import und `--verify` akzeptieren zusätzlich `studio-user-state-1`; andere Werte lehnt der Import ab) |
| `source_schema_version` | Schema des Stores, aus dem exportiert wurde (heute 21) |
| `created_at` | UTC-Zeit des Exports; nicht Teil des SHA |
| `content_sha256` | SHA-256 über die kanonische Form von `content` (unten) |
| `not_exported_rows` | Zeilen je Tabelle in `simulation_run`, `simulation_card`, `experiment`, `experiment_arm`, die das Format auslässt (Zahl, oder `null` = nicht zählbar); nicht Teil des SHA; fehlt ein Feld (z. B. in `studio-user-state-1`), gilt es als unbekannt |
| `content` | `tables` und `not_in_schema` |

**Kanonische Form**: `json.dumps(content, sort_keys=True, ensure_ascii=False,
separators=(",", ":"), allow_nan=False)` als UTF-8. Zeilen je Tabelle stehen nach Primärschlüssel
sortiert. Gleicher Inhalt gibt also denselben SHA, unabhängig von Zeit und Reihenfolge der
Einfügung.

### 2.1 `content.tables`

Jede Tabelle ist eine Liste von Zeilen, Schlüssel = Spaltennamen des Schemas (alle Spalten, so wie
`PRAGMA table_info` sie nennt; eine neue Spalte wird ohne Codeänderung mitgeschrieben).

| Tabelle | Inhalt |
|---|---|
| `source` | nur die Quellen, auf die `deck_revision.source_id` zeigt (Fremdschlüssel) |
| `deck`, `deck_revision`, `deck_branch` | Decks, Stände (alte `revision_id`, `deck_hash`, Elternstand, Notiz), Zweige |
| `deck_revision_card` | Karten eines Stands: Zone, Menge, Kartenidentität |
| `deck_draft` | Entwürfe; `cards` ist hier eine Liste von Einträgen mit Kartenidentität statt eines JSON-Textes |
| `deck_label`, `deck_primer` | Deck-Labels, Primer |
| `deck_module`, `deck_module_card` | Module und ihre Karten |
| `card_mark`, `card_label` | Markierungen und Karten-Labels |
| `strength_profile`, `universe_profile` | gespeicherte Profile |
| `tam_cardmarket_price` | ab `studio-user-state-2` (#1703 K-2a2): manuell erfasste TAM-Richtwerte je `oracle_id` (Schlüssel direkt `oracle_id`; Test-Fixtures strikt synthetisch, `AGENTS.md` §12) |

**Kartenidentität**: jede Zeile mit einem Kartenverweis trägt `card_id` (Schlüssel des Stores, für
den Rundlauf in Schema 21), `oracle_id` (Scryfall, der Schlüssel des Zielmodells E-A3) und `name`
(`oracle_name`). Fehlt einer Karte die `oracle_id` oder die Zeile in `card`, bricht der Export ab
(Abschnitt 4).

### 2.2 `content.not_in_schema`

`["setting", "table_preset"]`: Abschnitte des Zielmodells (Einstellungen, Tische ab B2 #1658), für
die Schema 21 keine Tabelle hat. Sie fehlen im Inhalt; **fehlend heißt unbekannt, nicht leer**. Sobald
es die Tabellen gibt, kommen sie als optionale Abschnitte dazu; ein Import, der einen Abschnitt ohne
Ziel findet, bricht ab und lässt ihn nie still fallen.

### 2.3 Bewusst nicht enthalten

- Alle Importtabellen (Karten, Sammlung, Korpus, Beobachtungen, Rollen, Signale, `tam_price_print`,
  `tam_cardmarket_guide*`, ...). Sie sind neu bauen, nicht sichern (E-A1).
- `tier_snapshot`: aus Daten und Profil ableitbar.
- `simulation_run`, `simulation_card` (Ergebnisse, `SIMULATED_RESULT`), `experiment`,
  `experiment_arm` (vollständig aus `games/experiments/<id>/plan.json` und `decision.json` via
  `experiments.rebuild_index()` rekonstruierbare Indizes) und `games/`: Export, Import, `--verify`,
  `--check` und die Start-Kopie melden dazu eine Zeile
  `Nicht exportierte Zeilen aus simulation_run/simulation_card/experiment/experiment_arm: n`
  (Summe der Tabellen; `unbekannt`, wenn eine Tabelle nicht zählbar ist oder die Datei das Feld
  nicht trägt; nie 0 für unbekannt).
- `meta`, `commander_binding` und was der Import schreibt.

## 3. Befehle

```text
python -m commander_lab.studio [--data ORDNER] export-state [--to DATEI|ORDNER] [--check] [--json]
python -m commander_lab.studio [--data ORDNER] import-state DATEI [--verify] [--json]
```

- `export-state` liest alle Tabellen in **einer Lese-Transaktion** (`BEGIN`): ein Commit eines
  laufenden Servers zwischen zwei Tabellen kann die Datei nicht uneinheitlich machen. Schreibt atomar
  (Temporärdatei, dann Umbenennen). Ohne `--to` geht die Datei nach
  `<Datenordner>/state-exports/studio-state-<UTC>.json.gz`. Exit 0 ok, 2 bei blockiertem Export,
  keine Datei bei einem Abbruch.
- `export-state --check` meldet vorab: blockierende Verweise (Liste) und Sammlungskarten ohne
  `oracle_id` als n von N (blockieren nur, wenn der Nutzerzustand sie nennt).
- `import-state DATEI --verify` prüft Format und SHA-256 und nennt Zeilen je Tabelle; es schreibt
  nichts.
- `import-state DATEI` liest in den Store von `--data`, der **keinen Nutzerzustand** haben darf
  (frischer Ordner; sonst Abbruch). Reihenfolge: SHA prüfen vor jedem Schreiben; eine Transaktion
  (Fremdschlüssel erst beim Commit); Karten, die der Zielstore nicht kennt, bekommen eine
  Stub-Zeile in `card` (`identity_evidence = state_import_stub`, `color_identity` leer, Quelle mit
  Datenklasse `UNKNOWN`; die Kartenfakten liefert der nächste Import der Kartendaten über die
  `oracle_id`). Kennt der Zielstore `card_id` mit anderer `oracle_id`, bricht der Import ab. Am Ende
  wird in der Transaktion erneut exportiert; weicht der Hash vom Hash des Dateiinhalts ab, wird
  alles zurückgerollt und die abweichenden Tabellen werden genannt. Bricht ein Fremdschlüssel erst
  beim Commit (Datei mit gültiger SHA, aber uneinheitlichem Inhalt), ist das ein `StateFileError`
  mit Rollback und Exit 2, kein roher `IntegrityError`. In `meta` steht danach
  `user_state_import_sha256`.

## 4. Fehlerfälle (kein Raten)

| Fall | Verhalten |
|---|---|
| Karte in Stand, Entwurf, Modul, Markierung oder Label ohne `oracle_id` | Export bricht ab, Liste mit Tabelle, Schlüssel, `card_id`, Name; Exit 2; keine Datei |
| Verweis auf `card_id` ohne Zeile in `card` | wie oben, Grund `no_card_row` |
| Entwurf nicht lesbar, Binärwert in einer Zeile | wie oben (`draft_unreadable`, `blob_value`) |
| SHA stimmt nicht, kein gz/JSON, falsches `format` | Import und `--verify` brechen ab, nichts geschrieben |
| Tabelle oder Spalte ohne Ziel | Abbruch |
| Zielstore hat Nutzerzustand | Abbruch |
| Fremdschlüsselbruch beim Commit (Datei in sich uneinheitlich) | Rollback, Exit 2, nichts importiert |
| Zielstore hat dieselbe `card_id` mit anderer `oracle_id`, oder mit anderem Namen | Abbruch, Rollback, Exit 2 (siehe 4.1) |

### 4.1 Bekannte Grenzen (dokumentiert, nicht behoben)

- **Gleiche `oracle_id`, umbenannte Karte** (F5): Kennt der Zielstore eine Karte unter derselben
  `card_id` und `oracle_id`, aber mit anderem Namen, fällt das erst bei der Rückexport-Prüfung auf
  (der Name der Datei weicht vom Namen im Zielstore ab, "nicht verlustfrei", die Tabellen werden
  genannt); der Import bricht ab und schreibt nichts (fail-closed, kein Verlust). Eine umbenannte
  Karte stoppt damit die Migration, bis Quelle oder Ziel abgeglichen sind; es wird nicht geraten.
- **Race beim Übernehmen einer verwaisten Sperre** (F2): Lesen zwei Starter gleichzeitig dieselbe
  verwaiste Sperre, kann der zweite die frische Datei des ersten löschen und seine anlegen; dann
  halten beide die Sperre. Das Zeitfenster ist klein (Einzelnutzer, ein Start von Hand); die Sperre
  ist ein Schutz gegen versehentlichen Doppelstart, keine Garantie gegen gleichzeitige Starter.
- **Eingefrorener Server** (F2/F5): Ein Server, der länger als 30 s keinen Herzschlag schreibt
  (Ruhezustand, angehaltener Prozess), gilt als verwaist und wird übernommen, auch wenn sein Prozess
  lebt. Der alte Server merkt es beim nächsten Herzschlag (Token fremd) und schreibt die Sperre nicht
  mehr, läuft aber weiter und kann den Store beschreiben.

## 5. Kopie beim Start und eine Instanz je Ordner

- `serve` legt vor dem Start des Servers eine Kopie nach `<Datenordner>/state-exports/` und behält
  die letzten **14** (`KEEP_COPIES`; Namen `studio-state-<UTC>[-n].json.gz`, andere Dateien dort
  bleiben). Ein blockierter Export legt keine Kopie an, rotiert nicht und stoppt den Server nicht
  (eine Zeile auf stderr).
- Sperrdatei `studio.lock` im Datenordner mit PID, Token, Startzeit und Herzschlag (alle 5 s). Ein
  zweiter `serve` auf demselben Ordner findet einen Herzschlag unter 30 s, meldet den Halter und
  endet mit Exit 3, bevor er den Store öffnet. Ein Herzschlag älter als 30 s, oder ein Halter, dessen
  PID es nicht mehr gibt, gilt als verwaist und wird übernommen. Ein unlesbarer, frischer Eintrag
  gilt als belegt.
- **Windows**: `os.kill(pid, 0)` beendet dort den Prozess, die PID-Probe entfällt; es entscheidet
  allein der Herzschlag. Verhalten von Sperrdatei und Pfaden unter Windows: `UNKNOWN`, bis
  `windows-runtime.yml` oder der Owner-PC es zeigt.

## 6. Prüfmittel

`tests/unit/test_studio_state_export.py` (synthetische Schema-21-Fixture mit allen Tabellen):

- Rundlauf Export, Import, Export: gleicher Inhalts-SHA **und** gleiche Zeilen je Tabelle, gemessen
  mit einer unabhängigen SQL-Abfrage (nicht mit dem Exporter).
- Karte ohne `oracle_id`: Abbruch mit Liste; Sammlungskarten ohne `oracle_id` als n von N.
- Zweiter Start endet mit Meldung (Sperre, und `serve` zweimal im Test); verwaiste Sperre wird
  übernommen, auch bei lebender PID mit altem Herzschlag (und umgekehrt: frischer Herzschlag mit
  lebender PID wird nicht übernommen); Rotation behält genau 14.
- Import: injizierter Fehler mitten im Schreiben und ein verlustbehafteter Einfügeschritt bringen
  den Store auf den Stand davor zurück (Zeilen aller Tabellen gezählt, keine offene Transaktion);
  Fremdschlüsselbruch beim Commit endet mit Exit 2.
- Export unter laufendem Schreiber: ein Commit zwischen zwei Tabellenlesevorgängen erreicht die
  Datei nicht (Test `test_an_export_reads_one_snapshot_while_the_server_commits_in_between`).
- **Mutationsproben** (jede muss die zugehörige Prüfung rot machen): M1 ein Feld (Entwürfe) beim
  Export weglassen, M2 SHA nicht prüfen (manipulierte Datei wird importiert), M3 Rotation behält 15.
  Zusätzlich (Review F3, von Hand an den Quellen nachgespielt, je rot): N1 Rückexport-Hashprüfung
  entfernen, N3 `ROLLBACK` durch `COMMIT` ersetzen, N7 Altersregel der Sperre entfernen, N-F1 die
  Lese-Transaktion entfernen (Test `test_m4_...` hält das als Mutationsprobe im Test fest).
  Ergebnis im PR: n/n rot.
- Import unter `COMMANDER_LAB_CACHE_CHECK=1`-Modus (Schreibfenster deklariert, `cache.write`).

Nicht geprüft, `UNKNOWN`: Rundlauf an der echten Export-Datei des Owner-PCs (der Owner schickt sie
einmal nach dem Merge; die Datei kommt nie ins Repository, gemeldet werden nur Zeilen je Tabelle und
die Zahl nicht abbildbarer Karten); Windows (siehe 5); Größe der Datei am Owner-PC.

## 7. Versionierung

`studio-user-state-1` ist eine eigene Version neben dem Schema des Stores (E-A6). Ändert sich das
Format, steigt die Zahl und der Rundlauf wird gegen Fixtures jeder früheren Version gefahren. Kein
`SCHEMA_VERSION`-Bump in K-2a.
