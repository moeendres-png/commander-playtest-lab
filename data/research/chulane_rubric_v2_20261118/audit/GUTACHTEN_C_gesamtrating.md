# Gutachten C: Gesamtrating gegen Nutzungs-Index (Chulane, 922 Karten, 2026-11-18)

Grundlage: nur die genannten Dateien plus die mitgeteilten Gate-Messwerte. Eigene Rechnungen (nur lesend) aus `fullrun_ratings.jsonl` (n=922) und den 60 Karten in `rangabweichungen.md`. Kennzeichnung: **[M]** gemessen/nachgerechnet, **[S]** Schätzung mit genannter Annahme, **[E]** Empfehlung. Indexwerte für alle 922 Karten lagen mir nicht vor (`measure.json` war nicht im Leseumfang); poolweite Aussagen zur Nutzungsachse sind darum [S].

## 1. Gewichtungsschema

**Formel geprüft [M]:** Gesamt = 0,30·Index + 0,70·V (V = gewichtetes Mittel aus H, F, E, T, R, D, K) reproduziert 60 von 60 Tabellenkarten (größte Abweichung 0,05 = Rundung).

**Doppelzählung [M].** H ist zu 90 % eine lineare Funktion der sechs Teilkriterien (R² 0,905, Rest-SD 5,8; n=922). V und H ordnen fast gleich: Spearman 0,988, Top-100 teilen 90 von 100 Karten (Jaccard 0,818). Die Teilkriterien sind also keine unabhängige Evidenz, sondern eine zweite Gewichtung derselben Rater-Meinung. Tatsächliche Wirkung je Punkt (direkt + über H): F 0,24; E 0,20; R 0,14; T 0,08; K 0,08; D 0,03. Beitrag je Standardabweichung zum Gesamtrating: H 5,6; F 2,8; E 1,8; R 0,9; T 0,8; K 0,5; D 0,4 Punkte. D und K (je 0,025) sind in der Formel Dekoration; D wirkt auch im H des Raters praktisch nicht (standardisiertes Beta 0,02).
Folgerung [E]: Die Doppelzählung verändert die Rangfolge wenig, ist aber falsch beschriftet. Entweder (a) V = H allein und E/F/T/R/K/D nur als Profil zeigen, oder (b) Mischung behalten und offen sagen: „H enthält die Teilkriterien bereits; ihre Extra-Gewichte sind eine bewusste Betonung von Synergie und Effizienz.“ Ich rate zu (b): Der Owner will sichtbare Einzelwerte, die Zerlegung bleibt exakt, und das Mittel aus sieben Werten glättet das Rater-Rauschen (H hat nur 19 Stufen, größte Gleichstandsgruppe 108 Karten; V hat 325 verschiedene Werte).

**Skalenproblem [M/S].** Aus den 36 Rang/Index-Stützpunkten der Tabelle rekonstruiert: Median des Index etwa 2; rund 620 von 922 Karten haben Index ≤ 5 (passt zu Stufe D: 431 + 186 = 617). Dort trägt die Nutzungsachse höchstens 1,5 Punkte, ihre Streuung ist 0,4 Punkte gegen 10,9 Punkte Streuung des Urteilsteils (0,70·SD(V) = 0,70·15,6). Für zwei Drittel des Pools ist das „Gesamtrating“ also praktisch 0,7·V: reines Modellurteil. Das deckt sich mit der Gate-Messung (Null-Gruppe: Spearman Gesamt gegen H 0,98). Oben (Index bis 100) trägt die Achse bis 30 Punkte. Das Nenngewicht 0,30 beschreibt die Wirkung nirgends richtig.

| Variante der Nutzungsachse | Streuung des Beitrags, untere 617 Karten | gesamt | Bewertung |
|---|---:|---:|---|
| Index roh (v1) | 0,4 [M/S] | ca. 5,4–6,0 [S, Top 90 interpoliert] | wirkt nur in S–B |
| Perzentil/Mittelrang | – | 8,7 | Index 0,0 gegen 0,3 wird zu Perzentil 1,8 gegen 22,4 = 6,2 Punkte Gesamtrating für einen Unterschied von wenigen Decks; oben staucht es Index 29 gegen 100 auf 3 Punkte. **Abgelehnt**: verstärkt Rauschen unten, verschenkt Signal oben, macht 777 Gleichstände zu Scheinabständen |
| Log: 100·ln(1+Index)/ln(101) | 3,4 (max. 11,6) | ca. 8,1–8,3 [S] | **empfohlen**: monoton, keine Anpassung an Daten, Index 0,1→2; 1→15; 5→39; 18→64; 100→100 |

Wirkung an fünf Beispielkarten [M] (Namen und Indexwerte aus dem Prüfbericht für den Repo-Eintrag entfernt, da Nutzungsdaten je Karte nicht eingecheckt werden): bei gleichem Gewicht 0,30 steigen Karten mit mittlerem bis hohem Index und niedrigem Urteil von rund 6,8–21 (linear) auf rund 19–35 (log); Karten mit Index nahe 0 ändern sich um weniger als 1 Punkt bis etwa 3 Punkte. Oft gespielte Karten mit niedrigem Urteil fallen so nicht mehr ans Tabellenende, sondern in die Mitte, wo ein Widerspruch zwischen Daten und Urteil hingehört.

**Weitere Optionen.** „Nutzung nur als Tiebreaker“: abgelehnt, das wirft das einzige extern verankerte Signal weg (Referenzdeck-AUC H allein 0,819 gegen Index 0,919). Umgekehrt („Index-Reihenfolge, Gleichstände nach V“) ist die konservative Alternative: Sie löst die 777 Gleichstände, ohne eine gemessene Reihenfolge zu ändern. Sie taugt als Rückfall, falls die Validierung (Abschnitt 2) gegen das Gesamtrating ausfällt. Ein H-informierter Bayes-Prior für die Nutzung wäre elegant, macht H aber zum Nutzungs-Prädiktor und verletzt „nichts angepasst“.
**Empfehlung overall-v2 [E]:** Gewichte unverändert (Owner-Setzung), nur die Nutzungsachse log-skaliert; Anzeige des Rohindex bleibt. Zur Owner-Wahl: schlankere Setzung Nutzung 0,35 / H 0,40 / F 0,15 / E 0,10, übrige Kriterien nur als Profil.

**Zwei Befunde im Code [M]:** (1) Fehlt die Nutzungsachse, wird renormalisiert: Die Karte erhält V statt 0,7·V und steht bis zu 43 % höher als eine Karte mit bekanntem Index 0 (Beispiel einer Karte aus der Null-Gruppe: 32,2 mit Index 0, 46,1 ohne Achse). Solche Karten gehören nicht in dieselbe Rangliste. (2) `with_overall` prüft den Commander, nicht das Bracket: H ist nur für Bracket 3 definiert, die Nutzungsachse folgt der Kohorte der Anfrage.

## 2. Deutung des Gate-Befunds (0,471 gegen 0,636)

- **Zirkulär im Ziel:** Der B5-Anteil ist Nutzung. Dass ein Nutzungsmaß ein anderes Nutzungsmaß besser vorhersagt als ein Urteil, ist erwartbar (gemeinsame Ursachen: Staples, Verfügbarkeit, Bekanntheit). Die Reihe 0,636 / 0,471 / 0,343 / 0,313 folgt mechanisch dem Nutzungsanteil der Maße; 0,471 liegt zwischen den Polen, weil 30 % Nutzung beigemischt sind.
- **Falsches Konstrukt:** H ist ausdrücklich für Bracket 3 definiert (GUIDE: K wird für schnelle Kombos auf 50 gedeckelt). Eine niedrige Korrelation mit Bracket 5 ist teils gewollt.
- **Blind am entscheidenden Ort:** 576 von 736 Zielwerten sind 0, in Stufe D 427 von 431. Der Hold-out kann die Ordnung innerhalb von D nicht beurteilen, also genau dort nicht, wo Gesamtrating und Index am stärksten auseinandergehen (alle 30 größten Aufwertungen stehen in D).
- **Ergebnis:** Der Befund ist kein Beleg gegen das Gesamtrating als Qualitätsurteil und kein Beleg dafür. Belegt ist nur: Das Gesamtrating ist als Nutzungs-Prädiktor schlechter. Sein Mehrwert über die Nutzung hinaus ist ungemessen.

**Fairere, machbare Validierung [E]** (ohne Dienste, ohne Simulation im Ranking; Schwellen vorab festlegen):
1. **Deck-Split in derselben Kohorte:** Index aus 80 % der 10.128 Decks, Ziel = Vorkommen in den übrigen 20 % (5 Faltungen, Bootstrap über Decks). Erst die Rauschobergrenze bestimmen (Index aus Hälfte A gegen Hälfte B), dann den Zusatznutzen: Sagt V **innerhalb gleicher Index-Gruppen** (partielle Rangkorrelation, geschichtet nach Gleichstandsgruppe) das Vorkommen im Rest voraus? Das prüft genau die Behauptung „H bricht Gleichstände sinnvoll“. Grenze: bleibt ein Nutzungsziel; für die 186 Null-Karten nicht prüfbar.
2. **Zeit-Split**, falls Deckdaten ein Datum tragen: Index bis Stichtag, Ziel = Zuwachs danach. Einziger Nutzungstest, der „Urteil erkennt gute Karten vor der Menge“ misst.
3. **Blinde Paarvergleiche des Owners** (möglichst ein zweiter Spieler): 120 Paare, je 40 aus den Widersprüchen der Rangabweichungs-Tabelle, aus Index-Gleichstandsgruppen und zufällig; ohne Sicht auf beide Werte. Kennzahl: Anteil der Paare, die jede Rangliste wie der Mensch ordnet (Wilson-Intervall). Etwa eine Stunde Aufwand und die einzige nutzungsfreie Referenz für „unser Kartenverständnis“.
4. **Konsistenz ohne Nutzung:** funktionsnahe Kartengruppen müssen nahe beieinander liegen. Stichprobe [M]: 11 Gruppen, 28 Karten (z. B. Tranquil Cove/Blossoming Sands/Thornwood Falls 25/25/25; Swords/Path 85/85; Bounce-Länder 75/70/75): größte H-Spanne je Gruppe 5 Punkte. Das stützt die Verlässlichkeit, nicht die Gültigkeit. Systematisch ausbauen, dazu „streng besser“-Paare.

## 3. Kommunikation in der Ansicht und Default

**Beschriftung [E]:** drei immer sichtbare Spalten mit Herkunft im Namen: „Nutzung (gemessen, n von 10.128 Decks)“, „Kartenverständnis (Modell-Urteil, 1 Lauf)“, „Gesamtrating (Setzung: 30 % Nutzung, 70 % Urteil)“. Das Wort „Stärke“ für keines der beiden ohne Zusatz. Die Stufen S–D gehören dem Nutzungs-Index: als „Nutzungs-Stufe“ beschriften, nicht als Stufe der Gesamt-Sortierung ausgeben.
**Hinweistext (Vorschlag):** „Das Gesamtrating ist eine festgelegte Mischung, keine Messung. Die Nutzung ist gezählt. Das Kartenverständnis ist das Urteil eines Modells nach dem Regeltext (ein Lauf je Karte, nicht von Menschen geprüft). Bei wenig gespielten Karten bestimmt fast nur das Urteil den Wert. Beide Listen teilen 61 der 100 besten Karten. Unterschiede unter etwa 5 Punkten sind nicht belastbar.“
**Je Zeile:** Beleg-Kennzeichen „Nutzung belegt (n Decks)“ / „nur Urteil (0 von 10.128 Decks)“ / „Widerspruch Daten–Urteil“ (z. B. Nutzungs-Stufe C oder besser bei H ≤ 15, oder Rangabstand ≥ 200) / „unscharf“. Gesamtrating ohne Nachkommastelle anzeigen. Rauschen [S]: mittlere |ΔH| 5,1 entspricht etwa 4,5 Punkten Fehler je Einzelwert und damit 1,6 (unabhängige Fehler) bis 3,2 (gleichgerichtete Fehler) Punkten im Gesamtrating; `unscharf` (52 von 922) misst nur Gewichtsempfindlichkeit, nicht dieses Rauschen.

**Default-Empfehlung [E]: Gesamtrating als Default ist vertretbar, weil es eine offen deklarierte Owner-Setzung ist und als einziges Maß die zwei Drittel des Pools in Stufe D überhaupt ordnet. Aber erst, wenn vier Bedingungen erfüllt sind; bis dahin bleibt Nutzung Default und das Gesamtrating ein gleichrangiger zweiter Reiter.**
1. Nutzungsachse log-skaliert (overall-v2), oder der Hinweis sagt wörtlich, dass unterhalb Stufe C faktisch nur das Modellurteil sortiert.
2. Index, Nutzungs-Stufe, n Decks und H stehen in jeder Zeile neben dem Gesamtrating; Umschalten der Sortierung mit einem Klick; Beleg- und Widerspruchs-Kennzeichen vorhanden.
3. Owner-Entscheid zu Frage 7 (Anker) liegt vor; die verfehlten Schwellen (3a, 5a) stehen im Infotext; Gesamtrating nur für die Bracket-3-Kohorte, Karten ohne Nutzungsachse außerhalb der Rangfolge.
4. Länder mit eigenem Rang („k von 65 Ländern“) oder eigenem Reiter.
Rücknahme-Regel vorab: Ordnet das Gesamtrating in den Widerspruchs-Paaren (Validierung 3) schlechter als der Index, geht der Default zurück auf Nutzung mit V als Gleichstandsbrecher.

## 4. Risiken und Lücken

- **Ein Modell, keine Mensch-Referenz:** Pilot-ICC 0,97 und Drift-ICC 0,93 messen Wiederholbarkeit derselben Modellfamilie, nicht Richtigkeit; gemeinsame Fehler bleiben unsichtbar. Regelbehauptungen 38 von 40 richtig, eine falsche (Open the Armory) zeigt den Fehlertyp.
- **Beliebtheits-Leck:** Spearman H gegen Deckanzahl 0,504; 3 echte Beliebtheitsaussagen in 922 Ausgaben. Urteil und Nutzung sind nicht unabhängig; „Fakten plus Verständnis“ zählt einen Teil derselben Information doppelt. Nicht trennbar ohne Mensch-Referenz oder Zeit-Split.
- **Gleichstände:** 777 von 922 Indexwerten; im Gesamtrating entscheidet dort V allein, mit Rauschen von einigen Punkten. Ränge auf Einzelplätze sind Scheingenauigkeit; Bänder oder Rangspannen zeigen.
- **Bracket:** H gilt für Bracket 3; kein Bracket-Prüfschritt im Code. Der B5-Hold-out ist als Gate für dieses Konstrukt ungeeignet.
- **Länder gegen Zauber [M]:** 65 Länder (7 % des Pools), bewertet gegen eigene Anker, also auf eigener Skala. T ist bei 58 von 65 Ländern 0 (Mittel 1,2 gegen 25,7), dadurch V 32,9 gegen 37,5 bei fast gleichem H (28,8 gegen 30,9). Länder stellen 8 der 30 größten Abwertungen (27 %). Ihre Nutzung folgt Manabasis und Kartenbestand, nicht Kartenstärke im Slot-Vergleich.
- **Drift und Einzellauf:** 5a knapp verfehlt (5,10; 3 von 49 mit Differenz ab 15, größte 30). 498 von 922 Bewertungen tragen nur Vertrauen „mittel“. Chargen zu 7 Karten: Ankereffekt in der Charge möglich, nicht gemessen.
- **Anker:** 3a verfehlt (MAE 10,35; Counterspell 32 Punkte daneben), Frage 7 offen; laut README ist nicht entschieden, ob die Bewertungen überhaupt verwendet werden. Ein Default auf dieser Grundlage braucht diesen Entscheid.
- **Skala ohne absolute Bedeutung:** H liegt im Mittel 10,2 Punkte unter dem Mittel der Teilkriterien (Median H 30); „50 = Durchschnitt“ gilt nicht. Die Zahl taugt zum Ordnen, nicht als Note.
- **Neue Karten:** Index 0 heißt bei alten Karten „niemand spielt sie“, bei neuen „noch keine Daten“. Kartenalter fehlt; für junge Karten sollte die Nutzungsachse „unbekannt“ sein, aber dann gilt der Renormalisierungs-Befund aus Abschnitt 1.

**Die drei wichtigsten nächsten Schritte [E]:**
1. **overall-v2 bauen und dem Owner zur Setzung vorlegen:** Log-Skalierung der Nutzungsachse, Länder-Rang, Bracket-Prüfung, Karten ohne Nutzungsachse aus der Rangfolge, Beleg- und Widerspruchs-Kennzeichen, Texte aus Abschnitt 3. Dazu die Rangabweichungen mit den vollen Indexwerten neu rechnen (hier nur an 60 Karten möglich).
2. **Faire Validierung mit vorab festgelegten Schwellen:** Deck-Split mit Zusatznutzen-Test innerhalb der Index-Gruppen und 120 blinde Paarvergleiche des Owners. Erst danach den Default endgültig festlegen.
3. **Zweiter Rater-Lauf gezielt** (PILOT_REPORT §8 sieht ihn vor): Widerspruchs-Karten, Top 150 des Gesamtratings und `unscharf`-Karten, Mittel beider Läufe; zusammen mit dem Owner-Entscheid zu Frage 7.
