# Pass 3 — Verbesserungen (Pass C) — Arbeitsstand 2026-10-26

Rang nach Hebel × Testbarkeit ÷ Risiko. Jeder Vorschlag nennt Evidenz aus Pass A/B, Messung (Seeds, Signatur, Teststärke), Risiko und Abhängigkeit. Nichts davon ist in Pass 3 implementiert — das sind Issue-Kandidaten, keine Code-Änderungen. "Refs #N" in den Issue-Entwürfen verweist auf die dort neu anzulegenden Issues, nicht auf bestehende.

## Rangliste (Top 10, alle Felder abgedeckt)

| # | Vorschlag | Feld | Hebel | Testbarkeit | Risiko | Issue |
|---|---|---|---|---|---|---|
| V1 | Referenz am HEAD neu erzeugen + automatische Invalidierung | 4 Statistik | hoch | hoch (36 Seeds, Twin) | niedrig | E1 |
| V2 | Korvold-Totcode markieren / Legacy-Pfad in Tests verbieten | 6 Architektur | mittel-hoch | hoch (Routing-Test) | niedrig | E2 |
| V3 | Katalog-Laden fail closed (0 Einträge = Abbruch) | 6 Architektur / 1 Pilot | mittel | hoch (Unit + Smoke) | niedrig | E3 |
| V4 | Mulligan-Modell auf 173er-Pool neu fitten + Keep-Rate-Vergleich | 1 Pilot / 7 Daten | mittel | mittel (10+ Seeds) | niedrig | E4 |
| V5 | Deck-Hash-Verifikation + Duplikat-/Farb-Gate vor Import | 2 Coverage / 6 Architektur | mittel | hoch (Unit + Import) | niedrig* | E5 |
| V6 | Commander-Schaden/Tax für den Piloten sichtbar machen | 1 Pilot / 2 Regeln | mittel-hoch | mittel (10+ Seeds + Signatur) | mittel (Bridge!) | E6 |
| V7 | Mana-Budget-Residual (Self-Tap/Sacrifice um 1) schließen | 1 Pilot | mittel | mittel (Zahlungs-Zählung) | niedrig-mittel | E7 |
| V8 | #979: 31 engine-unbekannte Precon-Karten als Printed (Fork) | 2 Coverage | hoch | mittel (Fork-Quali) | hoch (Fork, Claude-Go) | E8 |
| V9 | Cluster-robuste Vergleichs-Intervalle (Seed-Rotation = Cluster) | 4 Statistik | mittel | hoch (Re-Analyse) | niedrig | E9 |
| V10 | Graveyard/Artifact-Archetypen: echte Deltas oder zusammenlegen | 1 Pilot | niedrig | hoch (Vergleich) | niedrig | E10 |

\* V5 ist kein Rules-Engine-Eingriff (Deck-Konstruktion, nicht Spiel-Legalität) — die Abgrenzung steht im Issue-Entwurf, sonst wäre es ein Verstoß gegen "XMage = einzige Rules Engine".

## Feld 1 — Pilotstärke

- **V4 Mulligan-Refit (173er-Pool):** Modell heute auf 195 gefittet (pilots.py:320), Pool 173. Refit + Vergleich der Keep-Raten und der frühen Spielstärke auf ≥10 Seeds, gepaart. Erwartung: klein, aber jede Partie betroffen; Unsicherheit: R² war schon vorher nur 0,33 — ein Refit kann auch zeigen, dass das Modell am Limit ist, dann ist das Ergebnis "Modell ersetzen, nicht refitten" (z. B. land-/castable-basierte Regel statt Fit).
- **V6 Commander-Sichtbarkeit:** `commander_damage_visible`/`commander_tax_visible` = false in beiden Lanes (notes_bridge.md). Der Pilot sieht weder den 21er-Schaden noch die Tax — er kann weder gezielt auf Commander-Schaden spielen noch die Tax in seine Kostenrechnung nehmen. Messung zuerst: In wie vielen echten Spielen entscheidet ein Zug anders, wenn die Sicht da ist? (Replay mit/ohne Sicht, gleiche Seeds.) Erst wenn die Zahl > 0 ist, ist es ein Stärke-Hebel, sonst nur ein Sauberkeits-Item. Bridge-Änderung → Requalifizierung durch Claude, kein Muse-Selbststart.
- **V7 Mana-Budget:** Residual im Code vermerkt (payment.py:1516-1535). Zuerst zählen: Wie oft in echten Spielen überschätzt das Budget um 1 (Log der betroffenen Zahlungen, 24+ Seeds)? Dann fixen, dann gepaarten Vergleich. Kein Convoke/Delve/Improvise/Assist im Payment-Plan — das ist ein eigenes, größeres Item, hier bewusst NICHT als "mal eben" vorgeschlagen: Der Plan braucht ein Kostenmodell für alternative Kosten, das ist eine Bridge-/Pilot-Architekturentscheidung, kein Patch.
- **V10 Archetypen:** Graveyard/Artifact = Engine (pilots.py:1663-1667). Entweder Deltas (Graveyard: Friedhof als Ressource werten; Artifact: Artefakt-Synergie) mit Messung, oder zusammenlegen. Ohne Messung ist jede "Verbesserung" hier Kosmetik.
- **Kein Mehrzug-Plan / keine Kombos / keine Politik:** Aus Pass A (notes_pilot_core.md) bekannt, aber bewusst NICHT als Top-Item: Ein Planer (MCTS/Suche) passt nach den Pass-1/2-Erkenntnissen nicht ins Millisekunden-Budget der Entscheidungsschleife, und Politik (Deals, Kingmaking) ist im Pod-Profil casual/mid nicht messbar als "besser" ohne ein Politik-Modell. Als Forschungs-Item in Pass D vermerkt, nicht als Issue mit falscher Versprechung.

## Feld 2 — Kartenabdeckung / Regelfidelity (nach Häufigkeit in den Decks, Schwere)

- **V8 #979 (31 Karten):** Größter offener Coverage-Posten (offenes Issue #979, Follow-up zu #920). Fork-Arbeit, braucht Claude + Hans-Go (Fork-Push, Repin, Requalifizierung). Reihenfolge nach Häufigkeit: Die 31 Karten zuerst nach Vorkommen in den 173 Precons sortieren (nicht nach Alphabet), dann in Paketen implementieren, jedes Paket mit einem echten Spiel, in dem die Karte gezogen wird — sonst ist "implementiert" nur Parsing.
- **V5 Deck-Gate:** Siehe oben. Zusätzlich: Der XMage-`Commander`-Validator (Duplikate/Banned/Colour-Identity) ist in Pass 3 UNGELESEN — ein Issue, das ihn liest und seine Checks gegen die Commander-Regeln testet, ist ein reines Lese-/Test-Issue (kein Engine-Code), aber es schließt die Lücke in B-04.
- **#1027-Muster verallgemeinern (vorsichtig):** `target_discount.py` deckt exakt EIN Muster ("costs {N} less … creature dealt damage this turn"). Die Verallgemeinerung ("alle Kostenreduktionen, die vom Target abhängen") ist ein echtes Feld-2-Item, aber nur mit einer Liste aller betroffenen Karten im Pool + je Karte einem Test — sonst wird aus einem Spezialfall ein heuristisches Raten. Als Issue mit "erst Liste, dann Regel" formuliert, nicht als "einfach verallgemeinern".

## Feld 3 — Durchsatz (nur verhaltensneutrale Hebel, oder klar markiert)

- **Verhaltensneutral, direkt prüfbar:** Batch-Record-Slimming (#1008, bereits gemergt, Peak-RSS 2391 → 1824 MB im PR-Claim — in Pass 3 NICHT reproduziert) als Muster: Records slimmen, nicht Spiele kürzen. Weitere neutrale Hebel aus Pass A: Surefire-/JVM-Startkosten (Bridge-Tests 801 s allein für ReplayTwin in Pass 3 — das ist Test-Durchsatz, kein Spiel-Durchsatz; als CI-Item, nicht als Spiel-Item).
- **NICHT vorgeschlagen:** Spiele parallelisieren über die eine-JVM-pro-Spiel-Regel hinaus, Entscheidungen cappen, um schneller zu werden, oder Seeds mit "langweiligen" Spielen überspringen — alles das ändert das Messobjekt. Wer Durchsatz will, misst zuerst, wo die Zeit hingeht (JVM-Start vs. Entscheidungen vs. Card-Scan), sonst optimiert er blind. Das ist ein Mess-Issue, kein Tuning-Issue.
- **Card-Scan:** `docs/performance/xmage-card-scan-bulk-lookup.patch` liegt im Repo, in Pass 3 NICHT gelesen — als Prüfpunkt, nicht als Empfehlung: Erst lesen, dann entscheiden, ob der Bulk-Lookup verhaltensneutral ist.

## Feld 4 — Statistik / Vergleichsmethodik (inkl. "wie viele Spiele braucht ein Urteil?")

- **V1 Referenz am HEAD:** Siehe B-01. Ohne aktuelle Referenz ist jeder Pilot-Vergleich am HEAD gegen einen alten Piloten gemessen.
- **V9 Cluster-Intervalle:** Sitz-Rotationen eines Seeds teilen den Shuffle (comparison.py:515-519, im Code dokumentiert). Lösung: Seed als Cluster behandeln (Cluster-Bootstrap oder Mixed-Effects), oder Rotationen als eigene Seeds zählen. Re-Analyse bestehender Vergleiche möglich, ohne neue Spiele.
- **Teststärke ehrlich:** Win-Rates nur, wenn die Teststärke sie trägt, sonst "UNDECIDED, könnte nur Effekte ab X sehen" (Auftrag). Konkret: Für einen Deckbau-Verdikt ("Deck A > Deck B") mit gepaarten Spielen und typischer Streuung braucht es — je nach Effektgröße — Dutzende bis Hunderte Spiele; ein 10-Seed-Vergleich trägt Verhaltens-Signaturen (Abbrüche, Klassen, Fehler), aber keine Win-Rate. Das gehört als Rechen-Tabelle in den Issue-Entwurf E9 (mit den 36-Seed-Zahlen als Anker: Entscheidungen/Spiel 1.656–4.955, Median 2.767).
- **Falsche-Grund-Kontrolle (standing rule):** Jede Messung braucht eine Kontrolle, die das bekannte Ergebnis auf einem bekannten Fall reproduziert (z. B. #1007-Kette: 23/48 bit-identisch). Ein Issue ohne diese Kontrolle ist unvollständig.

## Feld 5 — Deckbau-Nützlichkeit

- **Guides verdrahtet (V6-ähnlich, aber Feld 5):** 184 Guide-JSONs existieren, kein Live-Spiel nutzt sie (notes_pilot_rest.md §7, nur Mess-Arm in pilot_decision_report.py). Deckbau-Nützlichkeit entsteht erst, wenn ein Guide als Pilot-Parameter in einem Vergleich läuft: Guide-Deck vs. No-Guide-Deck, gleiche Seeds, Verhaltens-Signatur + (mit Teststärke) Win-Rate. Bis dahin sind Guides Doku, nicht Evidenz.
- **Strukturelle Vergleiche (optimization/):** `all_legal_single_swaps` ist Deckbau-Legalität, keine Spiel-Regel — als Filter für Swap-Vorschläge gut, als Ranking verboten (Adjudizierung: Filter nur, kein Ranking). Ein Issue, das Swap-Vorschläge mit echten Spielen validiert (Top-N Swaps je Deck, je 10+ Seeds), ist das ehrliche Deckbau-Item.
- **Was NICHT hilft:** Noch mehr Metriken pro Spiel (17-Metriken-Wiederholung ist per §7.6-Adjudizierung entschieden: keine Wiederholung). Deckbau braucht wenige, stabile Signaturen, nicht mehr Zahlen.

## Feld 6 — Architektur / Tests / Qualität / Operationen

- **V2 Korvold-Totcode:** Siehe B-11. Zusätzlich: Ein Hygiene-Test, der beweist, dass `commander_lab.agents.build_pilot` == Live-Routing ist (kein Legacy-Import in Produktionspfaden außer ensemble/service_knowledge, dort mit Kommentar).
- **V3 Katalog fail closed:** Siehe B-12. Zusätzlich: Startup-Gate, das Kataloggröße gegen Pool-Größe prüft (z. B. < 50 % der Pool-Karten mit Eintrag = Abbruch).
- **V8-Begleitung:** Fork-Diff-Pflege: Der Fork-Diff gegen den letzten Upstream-Merge (fab0f23b → HEAD: 620 Dateien) sollte als Artefakt bei jedem Repin neu erzeugt werden, sonst verliert man die Übersicht, was Fork und was Upstream ist.
- **ReplayExport-Nachweis (B-03):** Surefire-Report der Klasse als CI-Artefakt, oder Klasse in eigenen Schritt. Klein, aber ohne ihn ist "Bridge-Tests grün" übertrieben.
- **Relativer Jar-Pfad (B-05):** Beispiele auf absoluten Pfad umstellen. Direkt PR-fähig, keine Rules-Änderung, keine Messung nötig (der Smoke selbst ist die Kontrolle).

## Feld 7 — Daten / Realismus des Pods

- **Pod-Profil casual/mid, nicht cEDH (Auftrag):** Alle Verbesserungen gelten für dieses Profil. Ein cEDH-Pod (schnelle Kombos, Stack-Kriege) würde andere Pilot-Prioritäten brauchen und ist explizit NICHT Ziel — wer ihn vorschlägt, muss zuerst das Pod-Profil ändern lassen (Hans-Entscheidung).
- **Pool-Realismus:** 173 Precons, 9 SYNTHETIC-Proxies. Die Proxies sind Platzhalter für engine-unbekannte Karten — ihre Realismus-Grenze muss in jedem Report stehen (Proxy ≠ echte Karte, keine Win-Rate aus Proxy-Spielen). #979 schließt Proxies, wenn die Karten implementiert werden.
- **Mulligan-Realismus (V4):** Ein Refit auf dem 173er-Pool ist auch ein Daten-Item: Die Fit-Daten (58.500 Hände) stammen aus einem anderen Pool — neue Fit-Daten, neue R²-Angabe, sonst ist "refittet" nur ein Wort.
- **SYNTHETIC-Transparenz:** In Vergleichs-Reports muss stehen, wie viele Spiele Proxy-Karten enthielten — sonst liest man Proxy-Verhalten als Karten-Verhalten.

## Was bewusst NICHT vorgeschlagen wird (mit Grund)

- MCTS / Suche im Piloten: Passt nicht ins Entscheidungs-Budget (Pass-1/2-Erkenntnis, im Handoff: "Suche bei ms-Budget ausgeschlossen").
- Politik/Verhandlung: Kein messbares "besser" im casual/mid-Pod ohne Politik-Modell; wäre ein Forschungsprojekt, kein Issue.
- Externe Priors als harte Filter (Meta PR7 `external_prior`): Ausdrücklich NICHT freigegeben — externe Quellen weisen Wege, filtern nicht hart (Memory 2026-10-25).
- Zweite Rules Engine / heuristische Legalität: Verstoß gegen die stehende Regel, kein Vorschlag, auch nicht "nur für X".
- cEDH-Optimierung: Außerhalb des Pod-Profils.
