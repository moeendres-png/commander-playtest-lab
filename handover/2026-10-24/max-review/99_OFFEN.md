# Max-Review — 99_OFFEN: Selbstcheck, Lücken, Nicht-Geprüftes

Stand: 2026-10-25 (Pass B abgeschlossen — s. „Pass B: Abschluss" unten).

## Selbstcheck: Was habe ich weggelassen, wo war ich unsicher, wo fehlte der Beleg?

1. **197 Zeilen ohne Laufzeit-Verifikation (O-01).** Die PR-Tabelle
   (`01_PR_PRUEFUNG.md`) beruht auf Body + Git-Diff. Nur #1002 und #1003
   sind von Muse laufzeit-verifiziert. Das ist kein Versehen, sondern
   die Grenze des Auftrags: 199 Zeilen in einer Nacht lassen sich nicht
   alle nachspielen. Die Tabelle sagt das auf jeder Zeile ehrlich
   („NICHT GEPRÜFT, Wirkung UNBEKANNT"). Wer eine Zeile als
   „bestätigt" liest, liest falsch.
2. **Unsicher: die E1+E3-Spannweite (15–30 %).** Sie stammt aus dem
   Engine-Dossier, nicht aus einer Messung. In 03 steht sie als
   Schätzung mit Spanne, nicht als Zahl. Eine engere Zahl hätte
   Profiling gebraucht, das in dieser Nacht nicht lief.
3. **Unsicher: R-01-Anteile.** Die Top-3-Ursachen der Zahlungsabbrüche
   sind erst nach der Abort-Ketten-Auswertung bekannt. R-01 ist
   deshalb ein Programm (messen → schließen), kein Fix-Versprechen.
   Die alte Hypothese (Filterländer/Any-Color) wurde bewusst als
   UNBELEGT markiert, nicht still ersetzt.
4. **Weggelassen: Forge-AI-Interna.** Der Code war per API nicht
   erreichbar (404). Statt aus Sekundärquellen zu raten, steht in
   04 nur die Lücke (Q13). Das ist eine bewusste Auslassung.
5. **Weggelassen: Offene Issues als Prüfgegenstand.** Der Auftrag
   verlangte gemergte PRs; offene Issues (#992, #996, #979 u. a.)
   stehen nur als Referenzen in 02/03, nicht als eigene Prüfzeilen.
   Ihre Inhalte sind damit nicht verifiziert.
6. **Weggelassen: Upstream nach 2026-10-20.** Der Fork-Diff (Pass A,
   Bereich 5) vergleicht gegen Upstream `fab0f23b7` (2026-10-20).
   Was Upstream danach getan hat, ist NICHT GEPRÜFT (kein Fetch).
   Ein „der Fork ist vorn/hinten"-Urteil wäre damit unbelegt.
7. **Beleg-Lücke: #1006-Auftragszahl.** 136/3.599 Zahlungen stammen
   aus dem #1006-Body. Die Abort-Baseline wird sie prüfen — bis
   dahin ist sie eine Body-Behauptung, keine Messung.
8. **Korrektur während der Arbeit (ehrlich):** Die erste Abort-Kette
   lief mit System-Python statt Venv-Python und crashte bei allen
   24 Seeds (`No module named 'pydantic'`). Gefixt (Venv-Aktivierung
   im Skript) und neu gestartet; die erste Kette lieferte 0 Spiele
   und wurde nicht als Ergebnis gewertet. Lektion: Ketten-Skripte
   müssen die Venv-Aktivierung enthalten — steht jetzt im Skript,
   nicht nur im Kopf.

## O-01 — 197 Zeilen ohne Laufzeit-Verifikation

199 Tabellenzeilen (187 Lab + 12 Fork + M4-Zeile, gezählt per
Datenzeilen-Skript). Davon verifiziert: #1002 (vollständig),
#1003 (vollständig, Sonderbefund B-13). Ausstehend beim Abschluss:
#1004, #1005, #1006 (Reproduktionen in Pass B). Rest: NICHT GEPRÜFT.
Body-Messungen stehen als „Body:", nie als Verifikation.

## O-02 — Fork-#64 / #62 nur teilweise rekonstruierbar

Fork-#64 (Gesamt-Merge): Der Merge-Diff ist aus dem Clone nicht
rekonstruierbar (kein reiner Diff gegen eine bekannte Base); nur
Body + Datei-Aggregat stehen in der Tabelle. Fork-#62: teilweise
rekonstruierbar (Titel/Beschreibung + Teil-Diff). Beide Zeilen
tragen den Vermerk. Kein Urteil über ihren Inhalt über den Body
hinaus.

## O-03 — Offene Issues nicht Teil der Tabelle

#992 (OOM-Fix, `agent:muse`, offen), #996 (Hash-Rekalibrierung,
offen), #979 (Fork-Karten, Claudes Lane), #999/#1001 (erledigt, Hans
schließt selbst) sowie O5/O6/O7 (Owner-Entscheidungen) sind in
02/03 referenziert, aber nicht als Prüfzeilen abgearbeitet. Ihre
Akzeptanzkriterien sind damit nicht verifiziert — R-09 (#992) und
R-16 (#979-Batch) sind Vorbereitungen, keine Umsetzungen.

## O-04 — Pass-A-Restliste (aus 00_ABDECKUNG.md)

- `XmageLosslessHiddenPlan.java` (668 Zeilen, Bridge): NICHT gelesen.
- 209 Bridge-Testdateien (62.530 Zeilen): nur inventarisiert, NICHT
  gelesen.
- Grep-Abdeckung: nur `engine/rules` + `pilots.py` für die
  „keine zweite Engine"-Aussage; repo-weit NICHT GEPRÜFT.
- Mess-Verzeichnisse in Bereich 1 (Regeln/Mission): teilweise gelesen.
- 4.710 `def test_`-Definitionen gezählt (keine Laufzeit-Fallzahl).

## Pass B: Abschluss (2026-10-25)

1. Abort-Kette ausgewertet → B-05 final (135 Casts, 1,57/1000, 136/136
   erzwungen, alte Hypothese widerlegt) + R-01-Baseline in 03 + Draft 01.
2. Kernzahlen-Reproduktionen: #1005 vollständig aus Artefakten verifiziert
   (36/36 Hash + Sieger, Median 3342.0 exakt); #1004/#1006 teilweise
   (Tests grün, Regel-Code gelesen, Sign-off-Zahlen aus Repo nicht
   reproduzierbar → B-20); Echt-Spiele-Teile (je 24 Paare) nicht
   nachgespielt — Bodies nennen den Recorded-Sign-off als Abnahme.
3. Nächster Schritt: Staging neu kopieren, alle Dateien auf
   `muse/claude-handover` unter `handover/2026-10-24/max-review/` pushen
   (push-files, NUL-Pfaddatei, Blob-SHA-Verifikation remote=lokal), dann
   Abschlussbericht an Hans (≤8 Zeilen, Ergebnis zuerst).
