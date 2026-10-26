# Pass 3 — Offen / Selbstcheck (99_OFFEN.md) — Stand 2026-10-26

## Was NICHT erreicht wurde (ehrlich, mit Grund)

1. **#1027-Kernzahl NICHT reproduziert (24 Spiele, Bitter Downfall 23 → 0, alle Abbrüche 43 → 20, Entscheidungen 72.021 → 70.874).** Grund: Eine 24-Spiele-Kette braucht freie JVM-Kapazität über längere Zeit; am 2026-10-26 teilen sich Pass 3, #1029-Dump, UI-Smoke und #1034-Tests die JVMs (Pass-3-Build allein hat bereits eine #1029-Scheibe durch Last gekillt, siehe Haupt-Chat). Eine weitere Kette jetzt zu starten, hätte fremde Arbeit gefährdet und wäre nach der Standing Rule (keine parallelen Ketten) falsch gewesen. Status: NICHT GEPRÜFT — weder bestätigt noch widerlegt. Nächster Schritt, wenn JVMs frei sind: `scripts/benchmark_xmage_full_games.py` (oder der #1027-Vergleichsbefehl aus dem PR) mit 24 Seeds, gepaart, absolutem Jar-Pfad (B-05-Falle beachten).
2. **#1008-Kernzahl NICHT reproduziert (200-Spiele-Vergleich, Urteil identisch, Peak-RSS 1824 vs. 2391 MB).** Gleicher Grund wie (1). Status: NICHT GEPRÜFT.
3. **36-Seed-Referenz am HEAD NICHT neu erzeugt.** Die Staleness ist per Diff BEWIESEN (B-01), die neue Referenz selbst ist ein E1-Issue, kein Pass-3-Nebenprodukt — sonst hätte Pass 3 seinen eigenen Messgegenstand verändert, während es ihn prüft.
4. **XMage-`Commander`-Validator NICHT gelesen.** Er liegt im Fork (Java, nicht in der Bridge), seine Checks (Duplikate/Banned/Colour-Identity) sind damit für B-04 nur aus der Bridge-Seite abgeleitet. Folge-Issue: E5, Item 4 (Lese-Doku).
5. **`Mage.Player.AIMCTS/SimulatedPlayerMCTS.java` NICHT gelesen.** Fork-Änderung (1 Datei, nicht Sets/Tests), Bridge-Relevanz offen. In Pass D als NICHT recherchiert vermerkt.
6. **Forge-Code, Cockatrice-Code, Hearthstone-Papers im Original NICHT gelesen.** Pass D markiert sie als GEHÖRT, nicht als Beleg. Keine Reuse-Empfehlung stützt sich darauf.
7. **Fork-Diff gegen AKTUELLES Upstream NICHT berechenbar.** Remote HEAD per ls-remote gesehen (`8a0cc931`), nicht gefetcht (kein Fetch im Auftrag, kein Push, kein Remote-Wechsel). Für den Pin-Stand ist der Diff gegen den letzten Upstream-Merge (`fab0f23b`) der relevante — der steht in Pass A.
8. **docs/claude/ nur Überschriften, docs/performance/ nur Verzeichnis + Referenz.** Tiefe Lesung dieser Verzeichnisse hätte Pass A verlängert, ohne einen neuen Befund zu versprechen (die relevanten Dateien — REPIN_RUNBOOK, Referenz — sind gelesen bzw. zitiert).
9. **Alle 255 Lab-PRs + 12 Fork-PRs: Inventar vollständig, Tiefe selektiv.** Jede PR hat eine Zeile in `01_PR_PRUEFUNG.md` (Nummer, Datum, Head, Anspruch aus dem Body). Eine Zeile-für-Zeile-Code-Prüfung aller 267 PRs war in einem Durchlauf nicht leistbar und wird hier NICHT behauptet. Tiefe Prüfung: substantielle PRs (Pilot/Bridge/Precon/Meta/Engine, jüngste, hohe Wirkung) + alle Befunde in `02_BEFUNDE.md`. Evidence-/Seal-/Workflow-/Docs-PRs sind als Inventar belegt, ihre Zahlen werden nicht als Spiel-Evidenz gewertet.
10. **Pass-2-Dateien/Push/Abschlussbericht weiterhin offen.** Pass 3 ersetzt Pass 2 NICHT (Hans-Go 2026-10-26: dritter Durchlauf auf neuem Stand, alte Referenzen nicht fortgeschrieben). Wer Pass 2 braucht, muss ihn separat schließen — das ist kein Pass-3-Versäumnis, sondern eine bewusste Trennung.

## Selbstcheck: Was habe ich weggelassen, wo war ich unsicher, wo fehlte ein Beleg?

- **Weggelassen (bewusst):** MCTS als Issue (passt nicht ins Budget, siehe Pass D §2); Politik/Verhandlung als Issue (kein messbares "besser"); externe Priors als harte Filter (PR7 nicht freigegeben); cEDH (außerhalb Pod-Profil); Convoke/Delve/Improvise/Assist im Payment-Plan (eigenes Architektur-Issue, nicht in E7 versteckt); Löschen der Korvold-Klassen (nur Markieren in E2, Löschen braucht Go).
- **Unsicher:** Schwere-Einstufung von B-11 (mittel, Tendenz hoch) — die Zeilenzahl (~530) ist hoch, der Spiel-Effekt ist null (toter Code), also ist "hoch" für Spielstärke falsch, für Hygiene richtig. Die Einstufung "mittel" ist ein Kompromiss, im Befund offengelegt.
- **Unsicher:** Ob die 195→173-Mulligan-Drift praktisch etwas ändert (B-02). Der Code beweist nur, dass kein Refit belegt ist, nicht, dass das Modell falsch liegt. E4 formuliert deshalb "messen, ob es etwas ändert", nicht "fixen, weil es falsch ist".
- **Beleg fehlt:** Für B-10 (Commander-Sichtbarkeit) fehlt die Spiel-Messung — deshalb ist E6 als "Messung zuerst" formuliert, nicht als Bridge-Änderung. Für B-06 (Guides) fehlt die Messung, ob Guides überhaupt helfen — deshalb ist die Guide-Verdrahtung ein Mess-Issue, kein Stärke-Claim.
- **Korrigierte eigene Fehler in Pass 3 (ehrlich):** (a) Erster Bridge-Build mit falschem `-pl`-Pfad (Fork-Install fehlgeschlagen, gekillt, mit vollem Pfad + Gate neu gestartet). (b) Erster Smoke mit relativem Jar-Pfad (BRIDGE_CLOSED, Ursache per diag_smoke.py gefunden: `.runtime/engine` als Arbeitsverzeichnis). (c) Subagenten-Angabe "7 Korvold-Klassen" korrigiert auf 6 (grep-verifiziert). (d) Subagenten-Angabe "Fork ist kein shallow Clone" korrigiert (doch shallow, 259 Commits, älteste 2026-09-14).
- **Was ich NICHT getan habe (und warum das richtig war):** Kein Code in Pilot, Bridge, Workflows, config/ oder qualification/ geändert; kein Merge, kein Approve, kein Fork-Push, kein Repin, kein Seal; keine Sammlungsdaten gelesen; keine Issue auf GitHub angelegt (das ist Hans' Schritt, siehe unten); keine parallele Messkette zu #1029/UI/#1034 gestartet.

## Nächste Schritte (nach diesem Bericht, in Reihenfolge)

1. Hans entscheidet: Welche E-Issues auf GitHub angelegt werden (Liste unten, im Abschlussbericht).
2. Wenn JVMs frei sind: #1027-Kette (24 Seeds) + 36-Seed-Referenz am HEAD (E1) — dann sind B-01 und die #1027-Zahl geschlossen.
3. Claude ab Do 2026-10-29 (kein Kontingent bis dahin, Memory): E6 (Bridge-Sicht, nur wenn Messung > 0), E8 (Fork-Karten, Repin/Seal), E2-Löschung (falls gewünscht).
4. Pass 2 separat schließen oder explizit als überholt erklären (Hans-Entscheidung, nicht Muse-Entscheidung).
