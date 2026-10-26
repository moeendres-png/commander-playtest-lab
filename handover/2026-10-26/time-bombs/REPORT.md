# Time-Bomb-Audit — Bericht (Issue #1028)

Source Lock: Lab main `6fb26071b` (Worktree `~/workspace/github/wt-1028`,
Branch `muse/time-bomb-audit-1028`). Vorgänger-Arbeit übernommen:
statische Klassifikation, Clock-Plugin, Kontroll-Lauf (siehe Abschnitt 5);
neu: Verifikation der Klassifikation, tests/-Scan, Läufe, Befundliste.

Trigger: #1025 (Meta-Lane PR6). `build_meta_functional_profile(now=None)`
las die Wanduhr für das Staleness-Fenster; Tests fielen erst ab
2027/2028. Der Fix ist gemergt. Dieses Audit fragt, ob es mehr Stellen
derselben Form gibt.

Methode: AST-Scan (Ratchet-Muster, deterministisch, keine grep-Artefakte
aus Kommentaren/Strings) + pytest-Plugin mit vorgeschobener Uhr.
Evidenzklasse der Zahlen: DIRECTLY_VERIFIED (Läufe gesehen), der
statischen Liste: CODE_DERIVED (AST + Kontextlektüre).

## 1. Statische Liste (src/commander_lab + scripts/)

Befehle (reproduziert, Ergebnis identisch zum Vorgänger):

    cd ~/workspace/github/wt-1028
    python3 ~/workspace/tmp/1028/scan_clock.py . > ~/workspace/tmp/1028/sites.json
    python3 ~/workspace/tmp/1028/classify.py

Ergebnis: **103 Call-Sites = A 32 + B 3 + C 3 + M 47 + T 18** (Summenprobe
bestanden: 32+3+3+47+18 = 103; Rescan byte-identisch).

Klassen: A = nur Log-/Provenienz-Stempel (nur Anzahl, Anhang A);
B = speist eine Entscheidung; C = Cache/Lock/Cleanup auf Zeitbasis;
M = time.monotonic Dauer/Timeout (wanduhr-immun); T = time.time Dauer
(wanduhr-immun, relativ).

### B/C-Einzelbefunde (Kontext geprüft)

- B `src/commander_lab/whole_deck/meta.py:121` (`is_source_stale`):
  12-Monats-Staleness, `now` injizierbar. Das ist die #1025-Stelle;
  Tests seit dem Fix gepinnt.
- B `scripts/refresh_meta.py:175` (`main`): Report-Tool, `now` default
  Wanduhr, `--as-of` vorhanden. Per Design zeitabhängig (Staleness-
  Report); alle Skript-Tests übergeben `--as-of` explizit (geprüft:
  `test_meta_refresh_pr6.py`, u. a. `--as-of 2027-09-01`). Zusätzlich
  läuft das Skript als Subprozess und wird vom Plugin nicht gepatcht.
  Kein Fix.
- B `scripts/upstream_delta.py:574` (`build_report`): Trigger T1,
  Pin-Alter in Wochen, `today` injizierbar (`today or date.today()`).
  Trigger-Test übergibt `today` explizit (`date.today() + 7 Wochen`).
  T1-Flip mit alterndem Pin ist beabsichtigt. Kein Fix.
- C `src/commander_lab/engine/rules/full_game.py:484`
  (`_remove_orphan_private_directories`): private dirs älter als 24 h
  (mtime vs. time.time()). Beabsichtigtes Cleanup, kein Fix.
  Plugin-Artefakt möglich (s. Abschnitt 3).
- C `src/commander_lab/whole_deck/optimizer_v2.py:733`
  (`OptimizerLock.acquire`): Lock stale nach 12 h
  (`stale_after_seconds=43200`). Beabsichtigt; Tests nutzen frische
  Locks ohne fabrizierte created_at-Literale (geprüft). Kein Fix.
- C `scripts/run_current_boundary_qualification.py:497`
  (`run_native_suite`): `not_before`-Filter (Report-Dirs ab Laufstart).
  Relativ, per Konstruktion datumsimmun; nur in tests/qualification
  referenziert, nicht in tests/unit. Kein Fix.

### A-Stellen: Stichproben-Verifikation (nicht nur Funktionsname)

Geprüft und als reine Stempel bestätigt (keine Alters-/Expiry-Entscheidung
beim Lesen): `storage/result_cache.py:147` (`put` stempelt `created_at`,
`get` prüft nur Key + Hash, keine Expiry), `qualification/…/evidence_epoch.py:271`
(`created_utc`-Stempel mit injizierbarem Override), `engine/process_manager.py:37`
(`started_at`/`last_healthcheck_at`-Stempel), `meta/store.py:32` (`_now`-Stempel),
`models/provenance.py` (Record-Default-Stempel), `storage/run_integrity.py:168`
(Manifest-Stempel). Restliche A-Stellen: Report-/Import-/Metadaten-Stempel
in `acceptance/`, `agents/tracing.py`, `audit/runner.py`, `observability/`,
`primer/compiler.py`, `tools/`, `scripts/*`-Mains.

### Zusatz-Scan: tests/ (nicht im 103er-Total enthalten)

Befehl: AST-Scan über `tests/` (gleiches Muster):

    python3 -c "scan(tests)"  →  25 Sites: datetime.now 1, date.today 1,
    time.monotonic 18, time.time 5

Die zwei Wanduhr-Stellen: `tests/fixtures/fake_external_engine_bridge.py:77`
(Response-`timestamp`-Stempel) und `tests/unit/test_upstream_delta.py:458`
(`today=date.today() + 7 Wochen`, explizit übergeben → shift-immun).
Die time.time-Stellen liegen in `tests/foundry/` und
`tests/qualification/` (nicht in tests/unit). Fazit: tests/ enthält
keine zusätzliche Zeitbombe für den tests/unit-Lauf.

Verbotene Bereiche (nur Vorschläge, nichts angefasst):
`qualification/`-Sites sind alle A (Stempel) oder M (monotonic-Timeouts)
— kein Vorschlag nötig. `engine-bridge/`, `config/`, Workflows,
Collection-Daten: keine Uhr-Sites gefunden.

## 2. Läufe

### BLOCKER (2026-10-26, ca. 14:10 Uhr): Dateierstellung in der Exec-Umgebung kaputt

Befund: Neue Dateien anlegen schlägt überall mit `EPERM (Operation not
permitted)` fehl — verifiziert per Flag-Matrix (`O_CREAT`, alle
Kombinationen, Workspace-Platte und /tmp). `mkdir` geht, Anhängen an
bestehende Dateien geht, `git init` scheitert beim Template-Kopieren,
`tempfile.gettempdir()` findet kein benutzbares Verzeichnis, `git` in
Test-Fixtures stirbt mit Exit 128. Die Muse-Write-Tools legen dagegen
weiterhin Dateien an — die Platte ist in Ordnung, die Exec-Sandbox ist
es nicht (vermutlich seit dem Runtime-Restart, der den Vorgänger
killte; erste Symptome: git-128er im Shift-Subset ca. 13:45 Uhr).

Folge: Der Kontroll-Lauf (Vorgänger-PID 3811, bis 42 % gelaufen) ist
ab dem Einsetzen der Störung UNGÜLTIG (F/E-Häufung ab ~40 % ist
Umgebung, kein Code-Befund) und wurde von mir gestoppt. Das
Shift-Subset ist ebenfalls kontaminiert (s. Abschnitt 3). Nach
Wiederherstellung der Dateierstellung müssen Kontrolle + beide
Shift-Läufe komplett neu laufen. Bis dahin: keine Lauf-Aussage.

Blocker-Update (Anlauf 4, 2026-10-26): EPERM-Störung verifiziert vorbei
(Schritt-0-Prüfung in eigener Exec zweimal grün: touch /tmp, touch
Workspace, python-open; danach lief die Kontrolle fehlerfrei durch).
Kontroll-Lauf 1 (Anlauf 3, PID 12589) starb am 26.10. 15:13 UTC durch einen
VM-Restart bei 59 % (Log gesichert als control-run1-vmrestart.log; sein
F aus der 37-%-Zeile ist ohne End-Zusammenfassung nicht identifizierbar
und wurde in Lauf 2 nicht reproduziert). Kontroll-Lauf 2 (s. Ergebnisse)
ist grün — die Lauf-Aussage steht damit.

Kontrolle (echte Uhr, muss grün sein, sonst zählt nichts):

    cd ~/workspace/github/wt-1028
    source ~/workspace/venvs/commander-lab/bin/activate
    export TMPDIR=~/workspace/tmp/pytest-tmp PYTHONPATH=~/workspace/github/wt-1028/src
    python -m pytest tests/unit -q

Shift-Läufe (Plugin `~/workspace/tmp/1028/clock_plugin.py`, Inhalt im
Anhang B, nicht ins Repo committet; Korrektur gegenüber dem Entwurf:
Das Plugin-Verzeichnis muss auf dem PYTHONPATH stehen):

    export TMPDIR=~/workspace/tmp/pytest-tmp PYTHONPATH=~/workspace/github/wt-1028/src:~/workspace/tmp/1028
    CLOCK_SHIFT_TO=2028-01-01 python -m pytest tests/unit -q -p clock_plugin
    CLOCK_SHIFT_TO=2035-01-01 python -m pytest tests/unit -q -p clock_plugin

Gepatcht: `whole_deck.meta.datetime`, `whole_deck.optimizer_v2.datetime`,
`time.time` (global, für Orphan-Cleanup), `upstream_delta.date`.
Nicht gepatcht (bewusst): `time.monotonic` (Dauern), Stempel-Module,
Subprocess-Skripte (refresh_meta läuft mit `--as-of` bzw. ungepatcht).

### Ergebnisse

Kontrolle (echte Uhr, Anlauf 4, Lauf 2):

    cd ~/workspace/github/wt-1028
    source ~/workspace/venvs/commander-lab/bin/activate
    export TMPDIR=~/workspace/tmp/pytest-tmp PYTHONPATH=~/workspace/github/wt-1028/src
    python -m pytest tests/unit -q  (detached per setsid, PID 1834)

Ergebnis: 3241 passed, 2 skipped in 1747.34 s (29:07 Min). Die 2 Skips sind
beides „Windows junction semantics" (test_run_manifest_integrity.py:276,
test_run_quarantine.py:65) — Umgebungs-Skips, keine Befunde. 0 failed,
0 errors. Log: ~/workspace/tmp/1028/control.log. Damit ist die Kontrolle
grün; erst jetzt zählen Shift-Diffs als Befunde.

Shift 2028 (Anlauf 4):

    export TMPDIR=~/workspace/tmp/pytest-tmp PYTHONPATH=~/workspace/github/wt-1028/src:~/workspace/tmp/1028
    CLOCK_SHIFT_TO=2028-01-01 python -m pytest tests/unit -q -p clock_plugin  (detached per setsid, PID 9330)

Ergebnis: 1 failed, 3240 passed, 2 skipped in 1671.63 s (27:51 Min).
Die 2 Skips sind dieselben Windows-junction-Skips wie in der Kontrolle.
Der einzige Fail ist das vorab registrierte Plugin-Artefakt (s. Abschnitt 3),
kein neuer Befund. Log: ~/workspace/tmp/1028/shift2028.log.

Shift 2035 (Anlauf 4, nach der #1034-Vollsuite — Koordinationshinweis
Parent beachtet: keine zwei Voll-Suiten parallel; Parent-Go „keine
Voll-Suite mehr aus meiner Richtung" lag vor):

    export TMPDIR=~/workspace/tmp/pytest-tmp PYTHONPATH=~/workspace/github/wt-1028/src:~/workspace/tmp/1028
    CLOCK_SHIFT_TO=2035-01-01 python -m pytest tests/unit -q -p clock_plugin

Lauf 1 (PID 23966, gestartet 16:43 UTC / 17:43 CET) starb bei 8 % durch
einen VM-Restart (Uptime danach 3 Min; setsid schützt nicht vor
VM-Restarts — gleiche Ursache wie Kontroll-Lauf 1). Log gesichert als
shift2035-run1-vmrestart.log (379 Bytes, keine Zusammenfassung).
Schritt 0 nach dem Restart erneut grün, Worktree weiter 6fb26071b,
kein pytest aktiv. Lauf 2 (Wrapper-PID 1867, pytest-PID 1868,
gestartet 16:50 UTC / 17:50 CET, Env aus /proc/1868/environ verifiziert:
CLOCK_SHIFT_TO=2035-01-01, PYTHONPATH mit Plugin-Verzeichnis) lief
durch.

Ergebnis Lauf 2: 2 failed, 3239 passed, 2 skipped in 1366.53 s (22:46 Min).
Die 2 Skips sind dieselben Windows-junction-Skips wie in der Kontrolle.
Fail 1 = das vorab registrierte Orphan-Artefakt (s. Abschnitt 3).
Fail 2 = `test_large_finite_numeric_literal_remains_valid`
(`test_run_manifest_integrity.py:126`, Fehler „run inventory or manifest
changed during verification") — KEIN Zeit-Befund, sondern ein
uhr-unabhängiger Umgebungs-Flake (Beweis s. Abschnitt 3). Log:
~/workspace/tmp/1028/shift2035.log.

## 3. Befundliste

Jeder Befund nennt Modul, Test und Datum, ab dem er fällt. Reine
Plugin-Artefakte werden als solche markiert, nicht als Fix-PR.

Vorab registriertes Artefakt (vor den Shift-Läufen aus dem Testcode
abgelesen, kein Befund): `test_orphans_older_than_a_day_are_removed_and_slots_and_young_ones_kept`
(`test_full_game_private_card_repository.py:211`) setzt das „junge"
Verzeichnis auf die echte Jetzt-mtime; unter vorgeschobenem
`time.time` ist es älter als der 24-h-Cutoff und wird gelöscht —
der Test fällt unter dem Plugin, obwohl er in echter Zeit an jedem
Datum grün ist (jung = „gerade erzeugt", nicht „kalendarisch jung").

Bestätigt im Shift-Lauf 2035 (Anlauf 4, Lauf 2): Der Orphan-Test fiel
erneut exakt wie vorhergesagt (`test_full_game_private_card_repository.py:228`,
`assert young.exists()`, young-Verzeichnis `bbbb…` gelöscht). Sonst kein
Shift-Diff in 2035 außer dem unten klassifizierten Flake.

Zweiter Fail in 2035 (KEIN Zeit-Befund — Umgebungs-Flake, CODE_DERIVED +
DIRECTLY_VERIFIED durch Reproduktion):
`test_large_finite_numeric_literal_remains_valid`
(`test_run_manifest_integrity.py:126`) fiel im 2035-Vollauf mit
„run inventory or manifest changed during verification" — die
TOCTOU-Guards in `storage/run_integrity.py` (`_identity` = dev/ino/size/
mtime_ns/ctime_ns) schlugen auf Dateien an, die kein Prozess verändert.
Gegenprobe (alle im Worktree wt-1028, derselbe Test, isoliert):
- 1× unter 2035-Shift: passed; danach 5× unter 2035-Shift: 4 passed,
  1 failed (Fehlertext nicht festgehalten).
- Loop A, 20× unter 2035-Shift (Workspace-TMPDIR): 14 passed, 5 errors
  („artifact changed before/while reading"), 1 failed (derselbe
  „changed during verification"-Fehler).
- Loop B, 20× unter echter Uhr (Workspace-TMPDIR): 12 passed, 4 errors,
  4 failed (derselbe Fehler) — gleiche Rate OHNE vorgeschobene Uhr.
- Loop C, 20× unter echter Uhr (TMPDIR=/tmp, tmpfs-Kontrolle):
  20 passed, 0 Fehler.
Fazit: Der Test ist auf der Workspace-Platte (Overlayfs über btrfs)
flaky (~30 % pro Aufruf), uhr-unabhängig. Auf tmpfs ist er stabil.
Die Guards machen genau ihren Fail-closed-Job gegen instabile
Dateisystem-Metadaten frisch erzeugter Dateien; das ist kein
Wanduhr-Verhalten und kein Fix-Ziel dieses Audits (kein Draft-PR;
die Flake-Ursache — Overlayfs-Metadaten vs. Sync — liegt außerhalb
des Issue-Scopes und ist nicht abschließend belegt).

Endgültige Befundliste: KEINE echte Zeitbombe in tests/unit.
Alle 103 statischen Sites sind by design (Abschnitt 1); beide
Shift-Läufe zeigen außer dem vorab registrierten Orphan-Artefakt
und dem uhr-unabhängigen Flake keinen Diff. Die #1025-Stelle war
die einzige echte Zeitbombe dieser Form; ihr Fix ist gemergt.

## 4. Fixes / PRs

KEINE. Begründung: Alle B/C-Stellen sind beabsichtigtes Verhalten
(Abschnitt 1); der einzige reproduzierbare Shift-Effekt ist das
vorab registrierte Orphan-Plugin-Artefakt (Test-Artefakt, kein
Produktionscode-Fehler — der Test misst „gerade erzeugt", nicht
„kalendarisch jung"); der zweite 2035-Fail ist ein uhr-unabhängiger
Umgebungs-Flake (Abschnitt 3), kein Zeit-Befund. Damit gibt es keinen
klaren Python-only-Fix im Sinne des Auftrags und folglich keine
Draft-PRs. Mergen nur nach Dirigent-Review, Hans mergt selbst —
hier gibt es nichts zu mergen.

## 5. Übernahme vom Vorgänger (Protokoll)

- Statische Klassifikation (103 Sites, Summenprobe) übernommen und per
  Rescan byte-identisch reproduziert; B/C-Kontexte und A-Stichproben
  zusätzlich von mir geprüft (s. Abschnitt 1).
- Clock-Plugin übernommen, Import per `--collect-only` verifiziert
  (3243 Tests in tests/unit).
- Kontroll-Lauf des Vorgängers (PID 3811, gestartet 13:01 Uhr) lebte
  als Waise nach dem Runtime-Restart weiter und wurde von mir
  übernommen statt neu gestartet; mein Duplikat-Lauf wurde gestoppt
  (CPU: 2 Kerne, keine parallelen Voll-Suiten).
- Der partielle Vorgänger-Log enthielt ein `F` (~35 %); ob es sich im
  vollständigen Kontroll-Lauf reproduziert, steht in Abschnitt 2.

## Anhang A: A-Sites (Stempel, 32)

Arbeitsdatei `classified.json` (nicht im Bericht abgedruckt, nur Anzahl);
A-Stellen siehe Abschnitt 1 (Stichproben-Verifikation).

## Anhang B: Plugin-Inhalt (Reproduktion)

Siehe `~/workspace/tmp/1028/clock_plugin.py` (82 Zeilen, Arbeitsdatei;
Inhalt: `_ShiftedDatetime.now` → Mitternacht des Shift-Datums,
`_ShiftedDate.today` → Shift-Datum, `time.time` → konstante
Shift-Epoche; Session-Fixture, autouse).
