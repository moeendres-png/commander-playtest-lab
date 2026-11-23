# Phase B – Recherche: LLM als Bewerter für absolute Kartenbewertungen (Commander)

> Phase-Bericht zum Vorab-Plan [Bewertung v3](rating_v3_plan_20261123.md) (Refs #1404). Ins Repo übernommen am 2026-11-23 aus dem Scratchpad; inhaltlich unverändert bis auf Modell- und Anbieternamen in Zitaten und Titeln (AGENTS §12; gekürzt, die URLs bleiben).

Stand: 2026-11-22. Nur öffentliche Quellen, nur gelesen, nichts im Repo geändert.
Kennzeichnung: **[P]** Primärquelle (Paper/offizielle Seite), **[Ü]** Übersichtsarbeit/Leitfaden, **[B]** Blog/Community/Sekundärbericht, **UNBELEGT** = keine Quelle gefunden oder nur eigene Schlussfolgerung.
Hinweis zur Zitierweise: Abstracts wurden über ein Abrufwerkzeug gelesen, das paraphrasiert. Aussagen sind daher als „laut Abstract“ sinngemäß wiedergegeben, nicht als wörtliche Zitate. Ausnahme: Koo & Li 2016 (Schwellen und Mindestgrößen), deren Werte über PMC wörtlich übernommen wurden.

## Kurzfassung (15 Zeilen)

1. LLM-Bewerter streuen auch bei identischer Eingabe zwischen Läufen (geringe Intra-Rater-Reliabilität; Haldar & Hockenmaier 2025 [P]); euer σ ≈ 8 ist also erwartbar, kein Ausreißer.
2. Strenge/Milde unterscheidet sich stark zwischen Modellen und sogar Modellversionen (Sunkavalli 2026 [P, Einzelautor-Preprint]; Thakur et al. 2025 [P]: Hang zur Milde). Euer Spell-Versatz −4,9 ist ein typischer Strenge-Offset.
3. Mittelwertbildung über k Rater senkt nur zufällige Streuung: Spearman-Brown aus ICC(2,1)=0,82 ergibt k=2 → 0,90, k=3 → 0,93 (Rechnung). Systematische Versätze bleiben erhalten.
4. Klare Bewertungskriterien sind der wichtigste Hebel für Reliabilität; CoT bringt bei klaren Kriterien wenig (Yamauchi et al. 2025 [P]).
5. Zerlegung in Teilkriterien kann helfen (FLASK, Ye et al. 2024 [P]), aber auch kollabieren: Kriterien korrelieren > 0,93 und messen dasselbe (Feuer et al. 2025 [P]).
6. Euer D-Problem ist ein Konstruktfehler: „kein Risiko“ ist Abwesenheit eines Nachteils, kein Nutzen. Im ungewichteten Mittel hebt es nutzlose Karten an (Domänenschluss, UNBELEGT als Einzelbefund).
7. Rubrik-Details (Reihenfolge der Stufenbeschreibungen, Skalen-IDs, Referenzwert) verschieben Scores messbar (Li et al. 2025, „Evaluating Scoring Bias“ [P]) → Prompt und Rubrik einfrieren.
8. Familien-Diversität: Panel aus drei Familien schlägt einen großen Einzelrichter und zeigt weniger Selbstpräferenz (Verga et al. 2024 [P]); Selbstpräferenz ist belegt (Panickssery et al. 2024 [P]), für Kartenbewertung aber weniger relevant (keine selbst erzeugten Texte).
9. Mehrere Labels in einer Ausgabe erzeugen Ankereffekte (Stureborg et al. 2024 [P]); große Chargen verschlechtern Genauigkeit (Cheng et al. 2023 [P]; BatchPrompt, Lin et al. 2023 [P]).
10. Reliabilität: ICC mit 95 %-KI berichten, absolute Übereinstimmung UND Konsistenz; ≥ 30 heterogene Objekte, ≥ 3 Rater als Minimum (Koo & Li 2016 [Ü]); Krippendorff-α ≥ 0,80 als Konvention [Ü].
11. Domäne: Das offizielle Bracket-System stammt von WotC (11.02.2025), nicht vom Commander Rules Committee (aufgelöst 30.09.2024); es bewertet Decks/Spielerlebnis, nicht Einzelkartenstärke [P].
12. „Stärke allgemein“ vs. „Wert in diesem Deck“ ist die Kernmehrdeutigkeit; EDHREC trennt Beliebtheit von Commander-Bezug über Synergy/Lift [B/P-nah].
13. Empfehlung Rubrik: H fest aus Kriterien ableiten, D nur als Abzug/Gate, Mittelfeld-Anker 30/40/50/60/70 ergänzen.
14. Empfehlung Design: 3 Rater aus 3 Familien, feste Modellversionen, kleine Chargen (≈ 10–20) mit 3–5 festen Ankerkarten (absolut bewertet), Reihenfolge randomisiert; Aggregation Median (vorab festgelegt).
15. Pilot: 60–100 Karten stratifiziert (Mittelfeld überrepräsentiert), Erfolg = ICC(A,1)-Gewinn mit Bootstrap-KI über Karten, Offset |Δ| < 2, keine Verschlechterung der Konstruktkorrelation.

---

## (1) Zuverlässigkeit von LLM-as-a-judge bei absoluten Skalenbewertungen

### 1.1 Bekannte Verzerrungen

| Verzerrung | Befund | Quelle / Typ | Relevanz für euch |
|---|---|---|---|
| Inkonsistenz zwischen Läufen | LLM-Richter haben laut Abstract geringe Intra-Rater-Reliabilität über Läufe; Abschalten des Samplings macht Werte stabil, senkt aber die Übereinstimmung mit Menschen | Haldar & Hockenmaier 2025 [P] | σ ≈ 7–9 ist plausibles Rauschen eines Einzellaufs |
| Inkonsistenz, Anker, Verteilungsschiefe | Geringe Übereinstimmung zwischen Ziehungen, Empfindlichkeit für unerhebliche Prompt-Änderungen, schiefe Score-Verteilung (Bevorzugung runder Zahlen), Ankereffekte wenn mehrere Labels in einer Ausgabe vorhergesagt werden, Vertrautheitsbias (niedrige Perplexität) | Stureborg, Alikaniotis & Suhara 2024 [P] | 5er-Schritte + mehrere Kriterien pro Antwort = Anker- und Rundungseffekte wahrscheinlich |
| Milde (Leniency) | Fehleranalyse zeigt Neigung zu milder Bewertung; selbst beste Richter weichen bis 5 Punkte von Menschen ab; reine Prozent-Übereinstimmung verdeckt große Score-Unterschiede | Thakur et al. 2025 [P] | Spricht für Bericht von absoluter Übereinstimmung, nicht nur Rangkorrelation |
| Strenge-Unterschiede, Versionsdrift | Strenge variiert stark zwischen Richtern; alle fünf Versionswechsel verschoben die Strenge signifikant; Halo der LLM-Richter laut Abstract nicht nachweislich größer als bei trainierten Menschen | Sunkavalli 2026 [P, Einzelautor-Preprint, schwach] | Modellversion je Rater protokollieren |
| Positionsbias | Reihenfolge der Kandidaten ändert Urteile | Wang et al. 2024 [P]; Zheng et al. 2023 [P] | Nur Hintergrund (betrifft Paarvergleich, den ihr nicht nutzt); analog: Reihenfolge in Chargen randomisieren |
| Längenbias (Verbosity) | Längere Antworten werden bevorzugt | Zheng et al. 2023 [P] | Übertragung auf Kartentextlänge UNBELEGT; billiger Check: Korrelation Score vs. Oracle-Textlänge je Rater |
| Selbstpräferenz | Modelle erkennen und bevorzugen eigene Texte; Erkennung korreliert linear mit Präferenzstärke | Panickssery, Bowman & Feng 2024 [P] | Gering, da Karten keine Modellausgaben sind; relevant, falls Rater eigene Begründungen früherer Läufe sehen |
| Rubrik-Formatbias | Reihenfolge der Stufenbeschreibungen, Art der Skalen-IDs (Zahlen/Buchstaben) und ein beigefügter Referenzwert verschieben Scores | Li et al. 2025, „Evaluating Scoring Bias in LLM-as-a-Judge“ [P, Preprint] | Rubrik und Ankertabelle wortgleich einfrieren; Umstellungen = neue Messung |
| Zentralisierungstendenz | Speziell für LLM-Richter keine Primärquelle gefunden; indirekt: schiefe Verteilungen (Stureborg 2024) | UNBELEGT als eigener Befund | Euer Mittelfeld 28–71 ist genau die Zone größter Uneinigkeit |

Übersicht/Hintergrund: Zheng et al. 2023 fanden zugleich > 80 % Übereinstimmung des stärksten Modellrichters mit Menschen, also auf Menschenniveau, und hielten einige Biases für gering oder mitigierbar [P]. Weitere jüngere, von mir nicht geprüfte Preprints zu Inkonsistenz bei Temperatur 0 und Kriterien-Reihenfolge existieren (nur Suchtreffer, nicht zitierfähig).

### 1.2 Rubriken mit verhaltensverankerten Stufen (BARS)

- BARS gehen auf Smith & Kendall 1963 zurück („Retranslation of expectations: an approach to the construction of unambiguous anchors for rating scales“, Journal of Applied Psychology) [P, Volltext nicht gelesen; Existenz über Sekundärquellen bestätigt, z. B. DTIC-Bericht https://apps.dtic.mil/sti/pdfs/ADA239969.pdf]. Kern: konkrete Beispielverhalten je Stufe, von Experten zurückübersetzt („retranslation“).
- Für LLMs: Prometheus (Kim et al. 2024) gibt pro Stufe 1–5 eine Beschreibung plus Referenzantwort; das feinabgestimmte Modell erreicht laut Paper Pearson 0,897 mit Menschen auf 45 Rubriken [P]. Das stützt Stufenbeschreibungen, ist aber kein sauberer Vergleich „mit vs. ohne Anker“.
- Yamauchi, Yano & Oyamada 2025: Bewertungskriterien sind laut Abstract entscheidend für die Reliabilität [P]. Die oft zitierte Aussage „nur höchste und niedrigste Stufe beschreiben ist am zuverlässigsten“ fand ich nur als Suchtreffer-Snippet → UNBELEGT.
- Evidenz für „Anker-Stufen helfen“: **mittel** (konsistente Richtung, wenige saubere Ablationen).

### 1.3 Zerlegung in Teilkriterien mit festem Aggregationsschema

- Pro: FLASK (Ye et al. 2024, ICLR) – feinkörnige Bewertung nach 12 Fertigkeiten verbessert laut Autoren Interpretierbarkeit und Reliabilität und erhöht die Korrelation Modell/Mensch [P; keine unabhängige Replikation gefunden].
- Contra: Feuer et al. 2025 zeigen an Arena-Hard-Auto eine „Faktorkollaps“-Situation: fünf Kriterien korrelieren > 0,93, ein großer Teil der Varianz ist durch das Schema nicht erklärt [P, Preprint]. Teilkriterien können also nur scheinbar unabhängig sein.
- Kriterien-Mittel vs. Gesamtwert: Wenn ein Kriterium eine andere Richtung hat (hier D = Abwesenheit eines Nachteils), erzeugt das ungewichtete Mittel einen systematischen Bias zugunsten „harmloser, nutzloser“ Karten. Das ist genau euer Befund. Als allgemeines Prinzip (Formativ-/Kompensationsproblem kompensatorischer Mittelwerte) **mittel** begründbar; als empirischer Befund für LLM-Kartenbewertung UNBELEGT.
- Halo zwischen Kriterien: Sunkavalli 2026 findet laut Abstract keinen Halo über dem Menschenniveau [P, schwach]. Kein Beleg, dass getrennte Aufrufe je Kriterium Halo halbieren (Snippet nicht verifiziert → UNBELEGT).

### 1.4 Begründung vor Wert (CoT) vs. Wert vor Begründung

- G-Eval (Liu et al. 2023): erst Bewertungsschritte (CoT), dann Formular-Score, Score als wahrscheinlichkeitsgewichtete Summe [P]; Spearman 0,514 mit Menschen bei Zusammenfassungen.
- Chiang & Lee 2023: Das Modell seine Bewertung erklären zu lassen verbessert die Korrelation mit Menschen; Varianten „rate-explain“ und „analyze-rate“ beide besser als Score allein [P]. Exakte Zahlen nur aus Snippet.
- Wang et al. 2024 (MEC): erst Evidenz, dann Score, mehrfach ziehen und mitteln [P] – Kontext Paarvergleich, Prinzip übertragbar.
- Yamauchi et al. 2025: CoT bringt wenig, wenn klare Kriterien vorliegen [P].
- Fazit: Begründung vor Wert ist Standard und schadet nicht nachweislich; der Zusatznutzen ist bei guter Rubrik klein. Evidenz **mittel**.

### 1.5 Temperatur und Mehrfachziehung (Self-Consistency)

- Self-Consistency (Wang et al. 2023, ICLR; arXiv 2203.11171): mehrere Denkpfade ziehen, Mehrheitsantwort nehmen, klare Gewinne bei Rechen-/Common-Sense-Aufgaben [P]. Übertragung auf Skalenbewertung: Mittelwert/Median mehrerer Ziehungen.
- Yamauchi et al. 2025: Nicht-deterministisches Sampling stimmt besser mit Menschen überein als deterministisches [P]. Haldar & Hockenmaier 2025: Temperatur 0 stabilisiert, senkt aber Menschenübereinstimmung [P].
- Folgerung: Temperatur > 0 und k Ziehungen mitteln, statt Temperatur 0 als „Reproduzierbarkeit“ zu verkaufen. Evidenz **mittel**.

### 1.6 Anzahl der Rater und Aggregation

- Spearman-Brown (Standardformel, psychometrisches Lehrbuchwissen [Ü]): ρ_k = k·ρ / (1 + (k−1)·ρ). Mit eurem ICC(2,1)=0,82: k=2 → 0,90; k=3 → 0,93; k=4 → 0,95 (eigene Rechnung). Zufallsstreuung je Wert sinkt grob von σ≈8 auf 5,7 (k=2), 4,6 (k=3).
- Gilt nur für zufälligen Fehler. Der Spell-Offset −4,9 ist systematisch und mittelt sich nicht weg (er verschiebt nur das Niveau des Mittels).
- Mittel vs. Median vs. getrimmtes Mittel: Verga et al. 2024 nutzten Mittelwert-Pooling bzw. Abstimmung [P]. Eine direkte Vergleichsstudie Mittel/Median/getrimmt für LLM-Rater fand ich nicht → UNBELEGT. Allgemein-statistisch: Median robust gegen einen Ausreißer-Rater; bei k=3 ist der Median das getrimmte Mittel.

### 1.7 Familien-Diversität

- Verga et al. 2024 („Replacing Judges with Juries“): Panel aus drei kleineren Modellen dreier verschiedener Anbieter übertrifft einen großen Einzelrichter, zeigt weniger modellinternen Bias, ca. 7× billiger [P]. Evidenz für „Diversität reduziert korrelierte Fehler“: **mittel** (eine Hauptstudie, Textbewertung).
- Sunkavalli 2026: Strenge-Spreizung zwischen Richtern groß [P, schwach] → verschiedene Familien bringen verschiedene Niveaus; Aggregation braucht dann Offsetkontrolle.

### 1.8 Kalibrierung gegen Referenzwerte

- Ankerkarten im selben Lauf: absolut bewertete Karten mit festgelegtem Sollwert, die in jeder Charge mitlaufen; daraus Rater-Offset schätzen (Ist − Soll) und ggf. abziehen. Das ist klassische Testgleichsetzung über Ankeritems; eine LLM-spezifische Studie dazu fand ich nicht → UNBELEGT (Prinzip plausibel). Wichtig: Ankerkarten werden absolut gegen die Rubrik bewertet, nicht „im Vergleich zu“ anderen Karten.
- Regression auf Ankerwerte (linear, Steigung+Achsenabschnitt je Rater): korrigiert Strenge und Spreizung. Braucht ≥ 10–15 Anker über die Skala verteilt, sonst instabil (UNBELEGT, Faustregel).
- Quantil-Normalisierung: erzwingt identische Verteilungen und löscht damit auch echte Unterschiede zwischen Läufen. UNBELEGT als Methode für LLM-Rater; höchstens als Sensitivitätsanalyse.
- Achtung: Ein beigefügter Referenzwert im Prompt kann selbst Bias erzeugen (Li et al. 2025, Referenzantwort-Score-Bias [P]). Ankerkarten daher nicht mit sichtbarem Sollwert in die Bewertungscharge geben, sondern blind mitbewerten und nachträglich auswerten.

### 1.9 Reliabilitätsmaße und Mindestgrößen

- Koo & Li 2016 [Ü] (über PMC, wörtlich): < 0,5 schlecht, 0,5–0,75 mäßig, 0,75–0,9 gut, > 0,90 exzellent, beurteilt am 95 %-KI, nicht am Punktwert; „at least 30 heterogeneous samples and involve at least 3 raters whenever possible“. Für Inter-Rater mit zufällig gezogenen Ratern: zweifaktoriell zufällig; „absolute agreement“, wenn gleiche Werte gefordert, „consistency“, wenn ein Offset tolerierbar ist; Einzel- vs. Mittel-ICC je nach späterer Nutzung. Immer Modell, Typ, Definition, Software und KI berichten.
- Shrout & Fleiss 1979 [P] (Grundlage der sechs ICC-Formen); ten Hove, Jorgensen & van der Ark 2022 [P] (Updates für unvollständige Designs, Generalisierbarkeitstheorie).
- Krippendorff-α: Konvention ≥ 0,800 belastbar, 0,667–0,800 nur vorläufig [Ü, Wikipedia/Hayes & Krippendorff 2007]. Vorteil: verkraftet fehlende Werte und mehr als 2 Rater.
- Euer Fall: ICC(A,1) und ICC(C,1) nebeneinander berichten; die Differenz quantifiziert den systematischen Offset. ICC(2,1)=0,82 ist „gut“, aber die Untergrenze des KI zählt.
- Mindestgrößen über Formeln (Walter/Eliasziw/Donner) nicht recherchiert → UNBELEGT; praktisch: Bootstrap über Karten.

## (2) Chargenbewertung

- Mehrere Labels in einer Ausgabe → Ankereffekte (Stureborg et al. 2024 [P]).
- Batch Prompting (Cheng, Kasai & Yu 2023, EMNLP Industry): bis zu 5× Kostenersparnis bei 6 Proben je Charge; Leistung hängt von Chargengröße und Aufgabenkomplexität ab [P]. BatchPrompt (Lin et al. 2023): mit wachsender Chargengröße sinkt die Genauigkeit [P].
- BatchEval (Yuan et al. 2024, ACL) bewertet bewusst in Chargen mit In-Batch-Vergleich und berichtet bessere Korrelation [P]. Das ist faktisch relative Bewertung und widerspricht der Owner-Vorgabe → nur Hintergrund, keine Empfehlung. Es zeigt aber: In einer Charge beeinflussen sich die Karten gegenseitig (Kontrasteffekt). Genau das macht Charge-Zusammensetzung und Reihenfolge zu Störgrößen.
- Konkrete Grenzen für „Ermüdung“/Kontextdrift bei 10, 20 oder 50 Karten: keine belastbare Primärquelle gefunden → UNBELEGT. Allgemein dokumentiert ist Positionsabhängigkeit in langen Kontexten (Hintergrund; nicht spezifisch recherchiert).
- Empfehlungen: kleine Chargen (≈ 10–20 Karten; UNBELEGT als exakte Zahl, Richtung durch Cheng/Lin gestützt, **schwach**), 3–5 feste Ankerkarten je Charge (blind, absolut bewertet; **schwach/UNBELEGT**), Reihenfolge und Chargen-Zusammensetzung je Rater randomisieren und Seed protokollieren (**mittel**, Analogie zu Positionsbias, Wang et al. 2024 / Zheng et al. 2023), Chargen nach Kartentyp mischen (sonst hängt der Spell-Offset womöglich an der Charge statt am Rater; UNBELEGT, prüfbar).

## (3) Domänenwissen: Wie bewertet die Magic-Community Kartenstärke?

- **Limited-Skalen (0–5):** Gängige Set-Reviews nutzen eine 0–5-Skala mit verhaltensnahen Stufenbeschreibungen, z. B. 5,0 = „praktisch unschlagbar, sofort beantworten oder aufgeben“, 4,0 = „großartige Rares, beste Uncommons, Premium-Removal, gern First Pick“ (MTGAZone, Set-Review [B]; Aetherhub-Ratings mit ähnlichen Stufen [B]). Das ist im Kern eine BARS-artige Skala. LSVs Originalskala (ChannelFireball) konnte ich nicht verifizieren → UNBELEGT.
- **Commander-Brackets:** Das System wurde am 11.02.2025 von Wizards of the Coast eingeführt (fünf Stufen: Exhibition, Core, Upgraded, Optimized, cEDH; Kriterien: Game Changers, Massen-Landzerstörung, Extrazüge, frühe Zwei-Karten-Combos, Tutoren, erwartete Spiellänge). WotC schreibt sinngemäß, man wolle weniger auf Power Level und mehr auf das Spielerlebnis fokussieren und das System ersetze die „Power Level 1–10“-Skala durch etwas Nützlicheres [P, https://magic.wizards.com/en/news/announcements/introducing-commander-brackets-beta]. Updates: 22.04.2025, 21.10.2025 (Tutor-Beschränkung entfernt, 10 Game Changers gestrichen), 09.02.2026 [P, WotC-Seiten; Inhalte teils über Sekundärquellen].
- **Korrektur der Annahme im Auftrag:** Das Bracket-System stammt nicht vom Commander Rules Committee. Das RC hat die Formatverwaltung am 30.09.2024 an WotC übergeben (Commanders Herald, OpenCritic u. a. [B]); WotC führt das Format mit dem Commander Format Panel.
- **Folgerung:** Brackets bewerten Decks und Absicht, nicht Einzelkarten; die Game-Changers-Liste ist eine binäre Markierung besonders spielbestimmender Karten, kein Score. Taugt als Konstrukt-Check (Game Changers sollten hohe Werte erhalten), nicht als Skala.
- **Synergie vs. Kraft:** EDHREC trennte über „Synergy“ (Inklusionsrate beim Commander vs. allgemeine Beliebtheit) und ersetzt dies inzwischen durch „Lift“ (Co-Occurrence relativ zum Zufall) [B/P-nah, EDHREC-Artikel „From Synergy to Lift“, https://edhrec.com/articles/from-synergy-to-lift-the-math-behind-edhrecs-new-era]. Das ist eine Nutzungsmetrik → nur als externer Maßstab, nicht als Eingabe.
- **Gut definierte Dimensionen** (operationalisierbar, eigene Einschätzung, UNBELEGT als Konsens): Mana-Effizienz (Kosten vs. Effekt, Referenz zu Standard-Rates), Kartenvorteil (Netto-Karten), Interaktion (Ziele, Geschwindigkeit, Instant/Sorcery), Resilienz (übersteht Removal/Wipes?).
- **Notorisch mehrdeutig:** „Wie gut im Deck“ vs. „wie stark allgemein“ (WotC selbst trennt Power und Spielerlebnis [P]; EDHREC trennt Beliebtheit und Commander-Bezug [B]); „Synergie“ (Bezug: Commander, Deckplan oder Paket?); „Risiko/Downside“ (Abwesenheit eines Nachteils ist kein Vorteil – euer D).
- Für LLM-Kartenbewertung allgemein: Eine Arbeit von 2025 (LoRA-feinabgestimmte LLMs, Quelle 31) testet LLMs bei Draft-Picks [P, Zahlen nicht gelesen]; ein nicht-LLM-Modell sagt 55 % menschlicher Picks auf unbekannten Karten voraus (Univ. Alberta, COG 2024 [P]) – Hinweis, dass auch Menschen hier nur mäßig übereinstimmen.

## (4) Validierung ohne Wahrheit

- **Test-Retest:** gleicher Rater, gleiche Karten, neue Ziehung/neuer Tag; ICC zweifaktoriell gemischt, absolute Übereinstimmung (Koo & Li 2016 [Ü]). Haldar & Hockenmaier 2025 zeigen, dass dies bei LLMs nicht trivial hoch ist [P].
- **Inter-Rater:** ICC(A,1), ICC(C,1), Krippendorff-α, je mit KI; zusätzlich mittlere Differenz je Kartentyp (Offset-Tabelle).
- **Konstruktvalidität:** konvergent – hohe Werte für anerkannte Staples/Game Changers [P, WotC-Liste], niedrige für offensichtlich unpassende Karten; diskriminant – Teilkriterien sollen nicht > 0,9 korrelieren (Faktorkollaps-Check nach Feuer et al. 2025 [P]); D sollte nicht positiv mit „nutzlos fürs Deck“ zusammenhängen.
- **Externe Gültigkeit gegen Nutzungsdaten (Maßstab, nicht Eingabe):** Spearman mit EDHREC-Inklusionsrate/Lift für den Commander [B]. Vorsicht: Nutzung misst auch Beliebtheit, Preis, Verfügbarkeit; mäßige Korrelation ist erwartbar und kein Zielwert an sich (UNBELEGT als Schwelle). Rater dürfen diese Daten nicht im Prompt sehen.
- **Sensitivitätsanalyse:** Ergebnis (z. B. Top-N-Auswahl) unter Varianten neu berechnen: Mittel vs. Median, mit/ohne Offset-Korrektur, Rater weglassen (leave-one-rater-out), D-Gewicht 0/aktuell. Stabile Top-N = robust.
- **Bootstrap über Karten:** Karten mit Zurücklegen ziehen (≥ 1000 Replikate), KI für ΔICC, Δρ und Offset zwischen alter und neuer Rubrik; Stratifizierung nach Kartentyp/Wertbereich [Ü, Standardstatistik].
- **Mindestkriterien „besser“ (Vorschlag, UNBELEGT als Norm):** (i) Untergrenze 95 %-KI der Differenz ICC(A,1)_neu − ICC(A,1)_alt > 0; (ii) |mittlerer Offset je Kartentyp| < 2 Punkte; (iii) Konstrukt-/Nutzungs-Korrelation nicht schlechter (KI überlappt mindestens); (iv) Top-N-Überschneidung zwischen Ratern steigt.

## (5) Konkrete Empfehlungen für euer Projekt

### (a) Rubrik-Änderungen
1. **H nicht frei urteilen lassen, sondern fest aus Kriterien ableiten** (Formel vorab dokumentiert); freies H höchstens als zweites, getrennt berichtetes Feld zur Plausibilitätsprüfung. Evidenz: **mittel** (FLASK [P] für Zerlegung; Feuer 2025 [P] als Warnung → Kriterien vorher auf Redundanz prüfen).
2. **D umdefinieren:** D wirkt nur als Abzug (z. B. 0 bis −20) oder wird durch Relevanz gegated (kein D-Beitrag, wenn E/F/T unter Schwelle). Alternativ D ganz aus dem Mittel nehmen und als Risikoflag führen. Evidenz: Prinzip **mittel** (kompensatorisches Mittel + Konstruktlogik), konkrete Formel **UNBELEGT** → im Pilot testen.
3. **Mittelfeld-Anker ergänzen:** je Kriterium verhaltensverankerte Beispiele für 30/40/50/60/70 mit echten Karten (BARS-Prinzip, Smith & Kendall 1963 [P]; Prometheus [P]). Evidenz: **mittel**.
4. **Rubrik einfrieren** (Reihenfolge der Stufenbeschreibungen, Skalen-Labels, Formulierung) und versionieren; jede Änderung = neue Messung. Evidenz: **mittel** (Li et al. 2025 [P]).
5. Begründung vor Wert beibehalten, kurz halten. Evidenz: **mittel** (Chiang & Lee 2023; Liu 2023; Yamauchi 2025: Zusatznutzen klein).

### (b) Rater-Design
1. **3 Rater aus 3 verschiedenen Familien**, exakte Modell-ID und Version je Lauf protokollieren (aktuell „vermutlich verschiedene Familien“ = UNBELEGT). Evidenz: **mittel** (Verga 2024 [P]; Spearman-Brown; Versionsdrift Sunkavalli 2026 [P, schwach]).
2. Temperatur > 0 belassen; optional 2 Ziehungen je Rater, wenn Budget erlaubt. Evidenz: **mittel** (Yamauchi 2025; Haldar & Hockenmaier 2025).
3. **Chargengröße ≈ 10–20 Karten**, Kartentypen gemischt. Evidenz: **schwach** (Richtung Cheng 2023/Lin 2023; Zahl UNBELEGT).
4. **3–5 feste Ankerkarten je Charge**, verteilt über die Skala, blind und absolut bewertet, Sollwerte nicht im Prompt. Evidenz: **schwach/UNBELEGT** (Testgleichsetzungs-Analogie; Referenzwert-Bias spricht gegen sichtbare Sollwerte, Li 2025 [P]).
5. **Reihenfolge und Chargen-Zusammensetzung je Rater randomisieren**, Seed speichern. Evidenz: **mittel** (Analogie Positionsbias).
6. Keine Sicht auf Werte/Begründungen anderer Rater oder früherer Läufe (Unabhängigkeit; Selbstpräferenz-Risiko Panickssery 2024 [P]). Evidenz: **mittel**.

### (c) Aggregationsregel vorab festlegen
- Endwert je Karte = **Median der 3 Rater** pro Teilkriterium, dann H nach fester Formel. Offset-Korrektur über Ankerkarten nur, wenn im Pilot ein Rater-Offset > 2 Punkte mit KI ≠ 0 nachgewiesen ist; Korrektur = additiver Offset je Rater (nicht Quantil-Normalisierung). Unsicherheit je Karte (Spannweite der Rater) mitführen; Karten mit Spannweite > 20 gesondert prüfen. Evidenz: Median-Wahl **schwach/UNBELEGT** (robust, bei k=3 = getrimmtes Mittel), Vorab-Festlegung **stark** als Methodenstandard gegen Forking-Paths (allgemeiner Methodenkonsens; keine spezifische Quelle recherchiert → formal UNBELEGT).

### (d) Pilotgröße und Erfolgskriterien
- **60–100 Karten**, stratifiziert nach Kartentyp und bisherigem Wertbereich, Mittelfeld 28–71 überrepräsentiert; inklusive 10–15 Ankerkarten. Minimum laut Koo & Li: ≥ 30 heterogene Objekte, ≥ 3 Rater [Ü]. Evidenz: Untergrenze **mittel**, Zahl 60–100 **schwach/UNBELEGT**.
- Alte und neue Rubrik auf denselben Karten mit denselben Ratern laufen lassen, plus ein Test-Retest-Lauf eines Raters.
- Erfolg: Kriterien aus (4) – ΔICC(A,1)-KI > 0; Offset je Kartentyp < 2; Teilkriterien-Interkorrelation < 0,9; Konstrukt-/Nutzungskorrelation nicht schlechter; D-Effekt bei „nutzlosen“ Karten verschwunden. Bootstrap über Karten. Evidenz: **mittel** (Methoden), Schwellen **UNBELEGT** (Vorschlag).

### (e) Was ihr NICHT tun solltet
1. Nicht Temperatur 0 als Reproduzierbarkeit ausgeben (stabil ≠ gültig; Haldar & Hockenmaier 2025). **mittel**
2. Nicht Rubrik/Prompt während des Hauptlaufs ändern oder Modellversion wechseln (Li 2025; Sunkavalli 2026). **mittel**
3. Nicht Nutzungs-/Beliebtheitsdaten (EDHREC) in den Prompt geben – sonst ist die externe Validierung zirkulär. **stark** (Logik der Validierung; kein Zitat nötig, formal UNBELEGT)
4. Nicht nur Spearman berichten – Rangkorrelation verdeckt Offsets; ICC(A,1) mit KI (Koo & Li 2016; Thakur 2025). **stark**
5. Nicht Quantil-Normalisierung als Hauptkorrektur einsetzen (löscht echte Unterschiede; UNBELEGT). **schwach**
6. Nicht annehmen, dass mehr Rater systematische Fehler (Spell-Offset, D-Bias) beheben – nur Rubrik/Kalibrierung tut das (Spearman-Brown-Logik). **stark** (mathematisch)
7. Keine Paarvergleiche, Elo, Bradley-Terry oder In-Batch-Vergleichsbewertung (BatchEval-Stil) – vom Owner abgelehnt; hier nur als Hintergrund erwähnt.
8. Nicht sehr große Chargen (z. B. 50+ Karten) mit allen Kriterien in einer Antwort (Stureborg 2024; Cheng 2023). **schwach–mittel**

---

## Quellenliste mit Zitierbarkeit

| # | Autor(en), Jahr, Titel | URL | Typ | Zitierbarkeit |
|---|---|---|---|---|
| 1 | Zheng et al., 2023, Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena (NeurIPS D&B) | https://arxiv.org/abs/2306.05685 | P | gut (peer-reviewed) |
| 2 | Wang, P. et al., 2024, Large Language Models are not Fair Evaluators (ACL) | https://arxiv.org/abs/2305.17926 | P | gut; nur Hintergrund (Paarvergleich) |
| 3 | Verga et al., 2024, Replacing Judges with Juries: Evaluating LLM Generations with a Panel of Diverse Models | https://arxiv.org/abs/2404.18796 | P | Preprint, viel zitiert |
| 4 | Chiang & Lee, 2023, A Closer Look into Automatic Evaluation Using Large Language Models (Findings EMNLP) | https://aclanthology.org/2023.findings-emnlp.599 | P | gut; Zahlen nur aus Snippet |
| 5 | Liu et al., 2023, G-Eval: NLG-Evaluation mit einem großen Sprachmodell und besserer Übereinstimmung mit Menschen (EMNLP; Titel gekürzt wiedergegeben) | https://arxiv.org/abs/2303.16634 | P | gut |
| 6 | Stureborg, Alikaniotis & Suhara, 2024, Large Language Models are Inconsistent and Biased Evaluators | https://arxiv.org/abs/2405.01724 | P | Preprint |
| 7 | Panickssery, Bowman & Feng, 2024, LLM Evaluators Recognize and Favor Their Own Generations (NeurIPS) | https://arxiv.org/abs/2404.13076 | P | gut |
| 8 | Kim et al., 2024, Prometheus: Inducing Fine-grained Evaluation Capability in Language Models (ICLR) | https://arxiv.org/abs/2310.08491 | P | gut |
| 9 | Ye et al., 2024, FLASK: Fine-grained Language Model Evaluation based on Alignment Skill Sets (ICLR) | https://arxiv.org/abs/2307.10928 | P | gut; keine Replikation gefunden |
| 10 | Feuer et al., 2025, When Judgment Becomes Noise: How Design Failures in LLM Judge Benchmarks Silently Undermine Validity | https://arxiv.org/abs/2509.20293 | P | Preprint |
| 11 | Haldar & Hockenmaier, 2025, Rating Roulette: Self-Inconsistency in LLM-As-A-Judge Frameworks (Findings EMNLP) | https://arxiv.org/abs/2510.27106 | P | gut |
| 12 | Yamauchi, Yano & Oyamada, 2025, An Empirical Study of LLM-as-a-Judge: How Design Choices Impact Evaluation Reliability | https://arxiv.org/abs/2506.13639 | P | Preprint; nur Abstract-Aussagen verwendet |
| 13 | Thakur et al., 2025, Judging the Judges: Evaluating Alignment and Vulnerabilities in LLMs-as-Judges (GEM² Workshop) | https://aclanthology.org/2025.gem-1.33 | P | gut |
| 14 | Li, Dou, Shao, Chen & Hu, 2025, Evaluating Scoring Bias in LLM-as-a-Judge | https://arxiv.org/abs/2506.22316 | P | Preprint |
| 15 | Sunkavalli, 2026, LLM Judges as Raters: A Pre-Registered Audit of Severity, Halo, Reliability, and Version Instability in LLM Essay Scoring on Public Corpora | https://arxiv.org/abs/2608.29517 | P | Einzelautor-Preprint, schwach |
| 16 | Wang, X. et al., 2023, Self-Consistency Improves Chain of Thought Reasoning in Language Models (ICLR) | https://arxiv.org/abs/2203.11171 | P | gut |
| 17 | Cheng, Kasai & Yu, 2023, Batch Prompting: Efficient Inference with Large Language Model APIs (EMNLP Industry) | https://aclanthology.org/2023.emnlp-industry.74 | P | gut |
| 18 | Lin et al., 2023, BatchPrompt: Accomplish more with less | https://arxiv.org/abs/2309.00384 | P | Preprint |
| 19 | Yuan et al., 2024, BatchEval: Towards Human-like Text Evaluation (ACL) – nur Hintergrund | https://aclanthology.org/2024.acl-long.846 | P | gut; relative Methode, nicht empfohlen |
| 20 | Koo & Li, 2016, A Guideline of Selecting and Reporting Intraclass Correlation Coefficients for Reliability Research | https://pmc.ncbi.nlm.nih.gov/articles/PMC4913118/ | Ü | gut (Schwellen wörtlich) |
| 21 | Shrout & Fleiss, 1979, Intraclass correlations: uses in assessing rater reliability | https://pubmed.ncbi.nlm.nih.gov/18839484/ | P | gut (Klassiker; nicht im Volltext gelesen) |
| 22 | ten Hove, Jorgensen & van der Ark, 2022, Updated guidelines on selecting an intraclass correlation coefficient for interrater reliability | https://research.vu.nl/en/publications/updated-guidelines-on-selecting-an-intraclass-correlation-coeffic/ | P/Ü | gut (nicht im Volltext gelesen) |
| 23 | Krippendorff's alpha (Konventionen 0,800 / 0,667) | https://en.wikipedia.org/wiki/Krippendorff%27s_alpha ; Hayes & Krippendorff 2007: https://www.asc.upenn.edu/sites/default/files/2021-03/Answering%20the%20Call%20for%20a%20Standard%20Reliability%20Measure%20for%20Coding%20Data.pdf | Ü | Wikipedia sekundär; Hayes & Krippendorff primär (nicht gelesen) |
| 24 | Smith & Kendall, 1963, Retranslation of expectations: an approach to the construction of unambiguous anchors for rating scales (J. Appl. Psych.) | Sekundär: https://apps.dtic.mil/sti/pdfs/ADA239969.pdf | P (nicht gelesen) | Existenz/Inhalt sekundär bestätigt |
| 25 | Wizards of the Coast, 2025, Introducing Commander Brackets Beta | https://magic.wizards.com/en/news/announcements/introducing-commander-brackets-beta | P | gut (offiziell) |
| 26 | Wizards of the Coast, 2025/2026, Commander Brackets Beta Updates (22.04.2025, 21.10.2025, 09.02.2026) | https://magic.wizards.com/en/news/announcements/commander-brackets-beta-update-october-21-2025 | P | Inhalte teils über Sekundärquellen |
| 27 | Commanders Herald, 2024, Commander Rules Committee Dissolves | https://commandersherald.com/commander-rules-committee-dissolves/ | B | Sekundärbericht |
| 28 | EDHREC, From Synergy to Lift: The Math Behind EDHREC's New Era of Recommendations | https://edhrec.com/articles/from-synergy-to-lift-the-math-behind-edhrecs-new-era | B | Betreiberartikel |
| 29 | MTGAZone, Reality Fracture (FRA) Limited Set Review: Multicolor (0–5-Skala) | https://mtgazone.com/reality-fracture-fra-limited-set-review-multicolor/ | B | Blog |
| 30 | Aetherhub, Strixhaven Limited Ratings (0–5-Skala) | https://aetherhub.com/Limited/DraftCardRatings/STX | B | Community |
| 31 | LoRA-Tuned Large Language Models for Card Selection in Collectible Card Games, 2025 (Haupttitel gekürzt) | https://arxiv.org/abs/2508.08382 | P | Preprint; Zahlen nicht gelesen |
| 32 | Univ. Alberta, 2024, Magic Drafting (COG 2024) | https://webdocs.cs.ualberta.ca/~mmueller/ps/2024/COG24_Magic_Drafting.pdf | P | nur Snippet (55 %) |

Eigene Rechnungen (Spearman-Brown, σ/√k) sind als solche gekennzeichnet und keine Quellen.
