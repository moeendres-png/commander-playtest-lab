# Kartenverständnis H: Vorab-Plan „Bewertung v3“ (Chulane, 2026-11-22)

- **Stand:** Branch `docs/rating-v3-plan-1404`, gebaut auf `main` @ `f4d49ad6`. Refs #1404. Grundlage sind die Phase-Berichte im selben PR: [A1 Forensik](rating_v3_phaseA1_forensik_20261123.md), [A2 Kartenblock-Defekte](rating_v3_phaseA2_kartenblock_defekte_20261123.md), [B Recherche](rating_v3_phaseB_recherche_20261123.md), dazu die Zusammenfassung in #1404, Kommentar 7087797689.
- **Owner-Auftrag (2026-11-22, Wortlaut):** „Da die Bewertung der karten so weit auseinander geht, will ich dass du erst planst wie du am besten die karten bewertest und dir die vergangenen Bewertungen nochmal genau anschaust und schaust wo eventuell fehler oder Ungenauigkeiten sind, plane und recherchiere entsprechend erst wie du die karten am besten bewertest und setze den plan dann entsprechend gründlich und vollständig um“.
- **Was dieser PR tut:** Er legt den Plan fest, **bevor** es einen v3-Lauf gibt. Es gibt keinen Lauf, keine neuen Bewertungen und keine Änderung am Produkt. Schwellen, Mengen, Formeln und Regeln dieses Plans werden nach dem ersten Öffnen einer v3-Ausgabe nicht mehr geändert. Was später abweicht, steht nur in der Abweichungsliste (§9) und heißt „explorativ“.
- **Verbindliche Owner-Vorgaben:** (1) erst planen und prüfen, dann gründlich umsetzen; (2) **keine Paarvergleiche, kein Elo, kein Bradley-Terry**, auch nicht als „relative Kalibrierung“: Jede Bewertung ist ein absoluter Wert je Karte; (3) **keine Nutzungs-, Beliebtheits- oder Preisdaten als Eingabe**, nur als Maßstab der Validierung; (4) H bleibt ein **Modellurteil** („Kartenverständnis“), nie „Wahrheit“; (5) alte Daten werden nie überschrieben; (6) keine Modellnamen in Repo-Dateien: Die Rater heißen „Rater A/B/C“, Stufe und Version stehen im Laufprotokoll im Scratchpad; (7) Familien-Diversität ist nur eingeschränkt möglich (§2, I4); (8) Kontingent mit 5-Stunden-Limits: zuerst der Pilot, volle Läufe in Chargen mit Wiederaufnahme.
- **Bezeichnungen:** **Lauf 1 (F1)** ist der Vollauf vom 2026-11-18 (922 Karten). **Lauf 2 (R2)** ist die zweite Bewertung vom 2026-11-22 (Welle 1 mit 300 Karten, Welle 2 mit 622). **G1** ist der unabhängige Lauf über 70 Karten (`audit/independent_rater_ratings.jsonl`). d = H_R2 − H_F1, N = 922.
- **Review-Runde 1 (Head `a5b0efc6`):** Zwei Fresh-Context-Reviews (Hygiene/Reproduktion; Methodik) mit den Entscheidungen des Co-Leads sind in diese Fassung eingearbeitet (Blindheit je Rater und Charge, Anker im Nachtrag nur streichen, S3 differenziell, A4 nur markieren, Anzeige-Bedingung, V3c ohne N, Laufprotokoll-Hash, offene Owner-Fragen, kein 10er-Rückfall, S5-Rechenregel). Review-Runde 2 (Head `79b6ae15`): S3-Muss nur Kreatur gegen Nicht-Kreatur mit Bonferroni, S6 mit Bonferroni, Gesamt-Fehlalarm des Pilots simuliert und offen genannt, Variantenwahl nach dem Vollauf mit Rangfolge V3b, V3a, V3c und Anzeige-Bedingung, korrigierte Bezugszahlen, Anker-Streichkriterium, Transkript-Regeln. Review-Runde 3 (Head `76ff7c3e`): S2 wird Soll, S7 ist im Pilot nur Frühwarnung und Muss erst im Vollauf, der Pilot-Entscheid hängt nur an V3b, der Gesamt-Fehlalarm ist mit Raterversatz neu simuliert, S6 nutzt ein t-Quantil, die Adjudikation misst auf V3b. Alles steht vor dem ersten v3-Lauf fest.
- **Herkunft der neuen Vergleichszahlen:** `data/research/chulane_rubric_v3_20261123/phaseA_scripts/v3_baselines.py`, Ausgabe `v3_baselines.json` im selben Ordner. Das Skript rechnet nur auf alten Daten (A1-Paare, G1, A2), mit Seed 20261123 (§10).

## Kurzfassung

1. **Ziel:** H soll zwischen unabhängigen Ratern **reproduzierbarer** werden. Gemessen wird das als Übereinstimmung, Versatz je Kartenart, Konsistenz von H mit den Kriterien, Treffen verdeckter Anker und fehlende Müdigkeit, bei externer Nicht-Unterlegenheit. „Richtiger“ ist nicht belegbar (§0).
2. **Hauptursachen (§1):** Der freie H-Schritt erklärt den Niveau-Versatz −4,67 bei gleichen Kriterien. Die Streuung je Karte kommt zu 72–73 % aus den Kriterien, vor allem E, F und R. D trägt H nicht (Gewicht ≈ 0). F1 sah bei 36 von 46 Ankerkarten die eigene Ankerzeile. 464 von 922 Kartenblöcken haben einen Defekt, 60 davon sind kaum fair bewertbar.
3. **Eingriffe (§2):** I1 Generator v2 mit den A2-Korrekturen und einem festen Deck-Kontextabsatz. I2 Raster v3: **D entfällt** und wird durch **N „Nachteil/Risiko“** ersetzt, das nur abzieht. Drei vorab definierte H-Varianten aus **derselben Antwort**: **V3b** (H = 0,3·E + 0,3·F + 0,2·R + 0,1·T + 0,1·K − 0,2·N, vom Skript berechnet), **V3a** (H frei, aber in einem Korridor ±10 um die Formel) und **V3c** (wie V3b ohne N); gewählt wird nach dem Vollauf in dieser Rangfolge. Mittelfeld-Anker 30/40/60/70 aus Konsens-Karten, alle Ankerkarten verdeckt. I3 Chargen mit höchstens 20 Karten, davon 4 verdeckte Ankerplätze, Reihenfolge je Rater mit festem Seed, **ein Wert je Antwortzeile**. I4 drei Rater A/B/C aus verschiedenen Modellstufen (Owner-Go 2026-11-23), frisch je Charge, je Rater und Charge ein eigener Ordner, ohne Web; S8 aus dem Harness-Transkript. I5 Median je Kriterium, keine stille Korrektur. I6 Fehlerprüfung bei Rater-Abstand ≥ 15.
4. **Pilot (§3):** 100 Karten (40 schwer, 30 Kontrolle, 10 Länder, 10 kaum fair bewertbar, 10 Anker verdeckt) in 6 Chargen zu 19 Karten, 3 Rater, also **18 Instanzen, ein Lauf**. V3a, V3b und V3c rechnet das Skript aus derselben Antwort.
5. **Erfolgskriterien:** S1 ICC(2,1) ≥ 0,87 mit unterer KI-Grenze ≥ 0,80 · S2 (Soll, nur berichtet) mittlere paarweise |Δ|/SD ≤ 0,39 · S3 kein Versatz Kreatur gegen Nicht-Kreatur über 0,15 SD (Bonferroni über 3 Raterpaare; Land-Kontraste S3c nur berichtet) · S4 (nur V3a) grober Korridorbruch (> 15) bei höchstens 5 % · S5 MAE der verdeckten Anker (erste Platzierung) ≤ 6 · S6 Positionsdrift ≤ 1,5 je 10 Positionen (Bonferroni über 3 Rater) · S7 (Muss im Vollauf, im Pilot Frühwarnung) Spearman mit der Quelldeck-Nutzung höchstens 0,05 unter den alten Läufen unter derselben H-Definition, untere KI-Grenze ≥ −0,15 · S8 0 zählende Verweis-Treffer · S9 Korrelation zweier Kriterien < 0,90. Die Schwellen sind vorab an alten Daten und synthetisch geprüft (§3). **Offen genannt:** Der Pilot verwirft einen echten Verbesserungseffekt (wahre ICC 0,90) in **16 %** der Fälle ohne Raterversatz und bis **26 %** bei einem um 0,2 SD strengeren Rater (Simulation, §3).
6. **Entscheidungsregel:** Der Pilot-Entscheid hängt **nur an V3b**: Erfüllt V3b alle Muss-Kriterien des Pilots (S1, S3, S5, S6, S8, S9), folgt der Vollauf. V3a und V3c werden im Pilot nur berichtet. Sonst gibt es höchstens **eine** Anpassungsrunde mit einem vorab committeten Plan-Nachtrag und neuer Pilotziehung, danach den Vollauf oder den Bericht „nicht erfüllt“. **Die Variante wird erst nach dem Vollauf gewählt** (Rangfolge V3b, V3a, V3c; §4, §6).
7. **Vollauf (§4):** alle 922 Karten in 54 bis 56 Chargen × 3 Rater, also **162 bis 168 Instanzen**, in Tranchen zu 18 Instanzen mit Freeze und Wiederaufnahme an Chargengrenzen. Retest sind die 90 Pilotkarten, die im Vollauf erneut bewertet werden.
8. **Anzeige (§6):** H_v3 ist nur ein Vorschlag. H_pooled wird nur nach einem Owner-Go ersetzt. Vorgeschlagen wird die erste Variante in der Reihenfolge V3b, V3a, V3c, die im Vollauf alle Muss-Kriterien (S1, S3, S5–S9; V3a zusätzlich S4) erfüllt **und** gegen H_pooled höchstens 0,10 Spearman verliert. V3b verliert auf alten Daten erwartungsgemäß etwa 0,09. Die Stufengrenzen und die Untergrenze ±8 werden **nicht** übertragen, weil die Skala eine andere Lage und Streuung hat.

## §0 Ziel und Messlatte

**Was „besser“ heißt.** Es ist vorab festgelegt und hängt nicht am Ergebnis. Es ist nicht zirkulär, weil keine der Messgrößen die Werte von v3 als Maßstab benutzt:

| Messgröße | Frage | Kriterium |
|---|---|---|
| Reproduzierbarkeit zwischen Ratern | Geben drei unabhängige Rater-Instanzen derselben Karte dasselbe H? | S1, S2 |
| Abweichung je Kartenart | Gibt es einen systematischen Versatz bei Kreaturen, Nicht-Kreatur-Spells oder Ländern? | S3 |
| Inkonsistenz H ↔ Kriterien | Folgt H den eigenen Teilkriterien? | S4 (V3a); in V3b gilt es per Konstruktion |
| Verankerung | Treffen die Rater verdeckt die Ankerwerte der Skala? | S5 |
| Müdigkeit und Position | Driftet die Bewertung innerhalb einer Charge? | S6 |
| Externe Nicht-Unterlegenheit | Wird der Zusammenhang mit der Nutzung (nur Maßstab) nicht deutlich schwächer als bei den alten Läufen unter **derselben** H-Definition? Der Vergleich mit dem heutigen H_pooled ist eine eigene, vorab gesetzte Anzeige-Bedingung (§6) | S7; Anzeige-Bedingung §6 |
| Blindheit und Konstrukt | Keine Verweise auf frühere Bewertungen; keine doppelt messenden Kriterien | S8, S9 |

**Was NICHT belegbar ist:**
- dass H_v3 die „wahre“ Stärke einer Karte trifft (es gibt keinen Wahrheitsmaßstab);
- dass die drei Rater **unabhängige Modellfamilien** sind: Alle stammen aus einer Familie in verschiedenen Stufen (I4). Übereinstimmung zwischen ihnen kann geteilte Familienfehler enthalten;
- dass eine höhere Korrelation mit der Nutzung eine bessere Bewertung bedeutet (Nutzung ≠ Qualität). Darum wird S7 nur als Nicht-Unterlegenheit geprüft, nicht als Ziel;
- dass v3 „richtiger“ ist als F1 oder R2. Belegt werden kann nur „verlässlicher nach S1 bis S9“.

**Wichtige Bezugsgröße.** Schon die alten Läufe stimmen besser überein, wenn man H aus ihren Kriterien rechnet statt das freie H zu nehmen (`v3_baselines.json`, n = 922/922):

| H-Fassung (F1 gegen R2) | SD gepoolt | ICC(2,1) [95 %] | mittl. \|d\| | mittl. \|d\|/SD | \|d\| ≥ 15 | Versatz Kreatur / Nicht-Kreatur / Land (in SD) |
|---|---|---|---|---|---|---|
| freies H (heute) | 19,7 | 0,818 [0,793; 0,839] | 9,16 | 0,465 | 266 von 922 | −0,382 / −0,127 / +0,144 |
| ungewichtetes Mittel E, F, T, R, K | 13,8 | 0,864 [0,846; 0,881] | 5,53 | 0,400 | 42 von 922 | −0,132 / +0,084 / +0,120 |
| Formel mit gleichen Gewichten und Abzug 0,2·(100 − D) | 14,8 | 0,868 [0,851; 0,884] | 5,85 | 0,396 | 60 von 922 | −0,063 / +0,139 / +0,131 |
| Formel mit den gesetzten v3b-Gewichten (I2) und Abzug 0,2·(100 − D) | 16,0 | 0,868 [0,851; 0,884] | 6,36 | 0,399 | 70 von 922 | −0,073 / +0,127 / +0,142 |
| V3c: gesetzte Gewichte **ohne** N-Abzug (Sensitivität) | 14,9 | 0,864 [0,845; 0,880] | 6,05 | 0,405 | 58 von 922 | −0,139 / +0,075 / +0,131 |

Folge: Eine Formel **staucht** die Skala (SD 19,7 → etwa 14 bis 16) und senkt allein dadurch die Abstände in Punkten. Deshalb sind S1 und S2 **skalenfrei** (ICC, |Δ|/SD). Die Schwellen folgen einer festen Regel: **besser als die Formel-Bezugsgröße der alten Läufe auf allen 922 Karten und besser als 95 % der pilotförmigen Ziehungen der alten Läufe** (Trockenlauf, §3). Daraus folgen S1 ≥ 0,87 (Trockenlauf: 9 von 200 Ziehungen erreichen es) und S2 ≤ 0,39 (2 von 200). Ein Raster v3 gilt nur dann als besser, wenn die neuen Rater untereinander besser übereinstimmen, als es die alten Rater unter derselben Formel taten.

## §1 Befunde aus Phase A/B in Kürze

**A1 Forensik** (Bericht A1, Skripte `phaseA_scripts/A1/`, zweimal byte-gleich):
- **Ankerwerte kopiert:** F1 bewertete 36 der 46 Ankerkarten mit ihrer eigenen Ankerzeile im Prompt und übernahm den Ankerwert in **64 von 76 Ankerzeilen** exakt (MAE 1,12). Bei den 46 Ankerzeilen ohne sichtbare eigene Zeile („v1 fixed“) waren es 16 von 46 (MAE 6,87); R2 sah nie die eigene Zeile (exakt 20 von 46 bzw. 23 von 76 Ankerzeilen). Zählbasis sind Ankerzeilen (Karte × Kriterium, `anchor_visibility` in `struct.json`), nicht Karten.
- **Das Niveau sitzt im freien H-Schritt:** Die Kriterien verschieben sich gegenläufig (T −4,70, F −2,77 gegen R +3,06, K +2,89, D +4,39; N = 922). Bei gleichen Kriterien setzt R2 H um **−4,67** tiefer (Lauf-Dummy, R² 0,911). Beobachtet ist ΔH −4,73.
- **Die Streuung kommt aus den Kriterien:** 72 bis 73 % der Varianz von d sind kriterienbedingt: r(d, aus den Kriterien vorhergesagt) 0,852–0,856, also r² 0,726–0,733; Rest-SD 5,7–5,8 bei SD 11,0 (`extra.json`, `decomp`). Korrektur gegenüber der Scratchpad-Fassung von A1: Dort stand 77–79 %; das war Var(Vorhersage)/Var(d) (`var_share_pred`), nicht der erklärte Anteil. Uneinigkeit gibt es vor allem in E, F und R.
- **D-Gewicht ≈ 0:** In allen Läufen liegt das OLS-Gewicht von D in H zwischen −0,12 und +0,08 (F1 0,02, R2 W2 0,03; R² ohne D sinkt um höchstens 0,006). Eine Karte ohne Wirkung bekommt hohes D (H ≤ 10 mit D ≥ 75: F1 55 von 180, R2 W2 94 von 227). Das Kriterienmittel liegt 4 bis 17 Punkte über H.
- **Kreaturen:** d −7,53 (n = 478) gegen Nicht-Kreatur-Spells −2,49 (n = 379) und Länder +2,85 (n = 65). Bei Mana-Wert 6 und mehr etwa −10 (n = 66). Bei Token-, Counter- und Tapper-Rollen −13,75 / −11,89 / −10,59 (n = 44 / 37 / 17).
- **Mittelband:** Im Band H 28–49 (Mittel beider Läufe) ist die mittlere |d| 11,7 (n = 299); 125 der 266 Karten mit |d| ≥ 15 liegen dort.
- **Externer Maßstab:** R2 korreliert stärker mit der Quelldeck-Nutzung als F1 (0,673 gegen 0,504). Das entscheidet nicht, welcher Lauf näher an der Qualität ist, weil bei R2 ein Beliebtheitsleck über den Webzugriff möglich war.
- **Eingabe:** Die Kartenblöcke waren byte-gleich (922/922). Verschieden waren Anker-Ausblendung, Kartenzahl je Aufruf (7 gegen 88 bis 100), Rahmen und Arbeitsweise. Modell, Temperatur und Aufwand von F1 sind im Repo unbelegt, die Familie ebenfalls.

**A2 Kartenblock-Defekte** (Bericht A2, Skripte `phaseA_scripts/A2/`, Ausgaben byte-gleich nachgerechnet):
- **464 von 922** Karten haben mindestens einen automatisch gefundenen Blockdefekt, 323 ohne die weichen Punkte. **60 von 922** sind ohne die fehlende Information kaum fair bewertbar (Liste: `phaseA_unfair_cards.json`).
- **Top-Defekte:**
  - Rulings abgeschnitten: höchstens 4, Text bei 240 Zeichen gekappt (268);
  - irreführende Pattern-Hits: etb_own auf Nicht-Kreaturen, Rollenlabel als Beleg (137);
  - Peer-Rollen gekürzt (115);
  - Castability falsch oder unvollständig (53, davon 17 Hybrid-Karten mit Widerspruch);
  - Doppelkarten, Spezialtypen und Verweise (19);
  - unerklärte Mechaniken (16; prepare bei 0 von 8 vollständig erklärt);
  - falsche Land-Fakten (15; Regex `extract_facts.py:378`).
- **Kontext:** Den fehlenden Deck- und Manabasis-Kontext meldeten Rater bei 391 Karten. Der Chulane-Text steht nur im Guide, nicht im Block; den Ratern fehlte er nicht, wohl aber den Regelclaim-Prüfern.

**B Recherche** (Bericht B, 32 Quellen mit Typ und Zitierbarkeit):
- **stark:** Mehr Rater senken nur den Zufallsfehler, nicht systematische Versätze (Spearman-Brown); ICC immer mit 95-%-KI berichten, mindestens 30 Objekte und 3 Rater (Koo & Li 2016); Nutzungsdaten nie in den Prompt, sonst wird die Validierung zirkulär.
- **mittel:** Klare Kriterien und verhaltensverankerte Stufen sind der größte Hebel; Rubrik und Format einfrieren, weil Formatdetails Werte verschieben; ein Panel mehrerer Familien schlägt einen Einzelrichter; Strenge-Versätze zwischen Modellstufen und Versionen; Temperatur > 0 ist kein Fehler.
- **schwach oder UNBELEGT:** genaue Chargengröße 10–20, Zahl der Ankerkarten je Charge, Median statt Mittel. Diese Werte sind Setzungen dieses Plans und werden im Pilot geprüft.

## §2 Eingriffe (Befund → Eingriff → Prüfbarkeit)

### I1 Generator und Faktenversion v2

Befund: A2 (464 von 922 Karten mit Blockdefekt, 60 kaum fair bewertbar); F1 und R2 sahen dieselben defekten Blöcke.

Eingriff: Es entstehen neue Dateien unter `data/research/chulane_rubric_v3_20261123/`: kopierte und geänderte Skripte `extract_facts_v2.py`, `extract_patterns_v2.py` und `render_prompt_v2.py`, dazu `facts_v2.jsonl`, `patterns_v2.jsonl` und `facts_v2_manifest.json`. **Die v2-Dateien unter `chulane_rubric_v2_20261118/` bleiben unverändert** (Vorgabe 5; sie halten F1/R2 reproduzierbar). Der Studio-Store und das Produkt werden **nicht** geändert. Fehlende Seitenwerte kommen aus einer kuratierten Datei mit Quelle und Datum.

| Nr | Korrektur | Datei / Funktion (v2-Vorlage) | Prüfung (Test im Generator-PR) |
|---|---|---|---|
| G1 | Fetch-Länder: Regex erkennt „basic Forest or Plains card“ usw.; holbare Farben in `wug_colours_produced`; „enters“ des geholten Landes | `extract_facts.py:378` (`land.fetches_land`), `wug_colours_produced`, `enters_tapped_class` | die 15 Länder aus A2 (u. a. Krosan Verge, Evolving Wilds, Fabled Passage) bekommen `fetches_land` wahr und die holbaren Farben; Gegenprobe: Nicht-Fetch-Länder unverändert |
| G2 | Hybrid-Castability: Hybrid getrennt zählen („G/W x3“), kein „no coloured symbol“ mit P = 1,0; Castability je Hybrid-Symbol mit der günstigeren Farbe, als solche gekennzeichnet | `render_prompt.fmt_pips`, Castability-Zeile in `card_block` | die 17 Hybrid-Karten (u. a. Wilt-Leaf Liege) ohne Widerspruch; Doppelzählung 0 |
| G3 | Castability-Zusätze: „X counted as 0“; „cost reduction in text not modelled“ (convoke, affinity, improvise, delve, evoke, „costs {N} less“) | `card_block` | 14 bzw. 23 Karten aus A2 tragen den Zusatz |
| G4 | **Rulings nicht abschneiden:** alle Rulings in voller Länge, nach Datum und bei gleichem Datum nach Text sortiert; inhaltsleere Verweise (nur Artikel-Link) gefiltert | `card_block` (`RULINGS_SHOWN`, `RULING_CHARS` entfallen) | 0 Karten mit „…“ oder fehlendem Ruling gegenüber `facts_v2`; Token-Zuwachs im Manifest (`prompt_token_stats`) |
| G5 | **Pattern-Hits ohne Rollenlabel-Belege:** etb_own nur für Kreaturen (sonst `etb_own_noncreature`, nicht gezeigt); Hits, deren Beleg „roles by text: …“ ist, werden nicht gezeigt | `extract_patterns.py` (Zeilen 335–348, 612) | 0 gezeigte Hits mit Rollenlabel-Beleg; 0 etb_own auf Nicht-Kreaturen |
| G6 | **Mechanik-Erklärungen:** Zeile „Mechanics (rules summary)“ aus `mechanics_glossary.json` (Kurzform nach CR 701/702) für prepare/prepared, goad, cloak, Adventure, Loyalty-Fähigkeiten, Station-Stufen, Empower, Ki/Flip und jedes Keyword ohne Reminder | neue Datei; `card_block` | alle 16 Karten aus A2 und alle 9 prepare-Karten mit Glossarzeile |
| G7 | **Rückseiten-P/T** und Keywords/Mana je Seite; „Power/toughness“ je Seite in der „Face i“-Zeile | `split_faces`, `card_block`; Werte aus `face_overrides.json` (öffentliche Kartendaten, Quelle und Datum je Zeile) | die 4 Transform-Karten aus A2 (u. a. Grizzled Outcasts 7/7) |
| G8 | **Planeswalker-Loyalty:** Zeile „Loyalty: N“ | aus `data/cards/xmage_card_facts.json` (Repo), sonst `face_overrides.json` | 4 von 4 Planeswalkern |
| G9 | **„card named X“:** Zeile „Referenced card: X — <Oracle-Text>“ | `extract_facts_v2` (Quelle: öffentliche Kartendaten, im Manifest) | Angel's Herald, Arachnus Spinner, Scepter of Empires |
| G10 | **Token-Erklärungen:** Clue, Food, Treasure, Blood usw. als Glossarzeile; Kopie-Grundregel (Kopie löst ETB aus) | `mechanics_glossary.json` | die 5 Karten aus A2 und die 9 Kopie-Karten |
| G11 | Körper-Benchmark: Zusatz „printed P/T; enters with counters“ | `card_block` | 17 Karten aus A2 |
| G12 | Kommandantenzeile `Commander: Chulane, Teller of Tales …` in jedem Block (etwa 60 Token; für Regelclaim-Prüfer) | `card_block` | 922/922 |

**Deck- und Manabasis-Kontext als fester Absatz im Guide (nicht im Block):** Nur Zahlen der Referenzliste (`chulane-current@41f393530bb16ee9`). `facts_manifest.deck_basis` enthält heute nur Länder (36), Nichtländer (63) und die Farbgruppen der Länder. Die übrigen Zahlen (Kreaturen, häufigste Kreaturtypen mit Anzahl, Artefakte, Instants/Sorceries, Basics je Typ, {C}-Quellen, Landfall- und Lebensgewinn-Karten) zählt ein Skript im Guide-v3-PR aus der Kartenliste dieser Revision und `facts_v2` (Typzeile, Rollen) und legt sie mit SHA-256 im Manifest ab. **Keine Kartennamen**, damit keine Referenzdeck-Zugehörigkeit durchsickert. Dazu kommt ein Kurzglossar der Grundregeln (Aura und Equipment bei Bounce, Zählmarken gehen beim Bounce verloren, Token-Kopie mit ETB, „put onto the battlefield“ ist kein Wirken, cloak/manifest wird nicht gewirkt).

Prüfbarkeit: Der Generator-PR enthält zu jeder Zeile G1–G12 einen Test auf den genannten Karten. Er zählt die A2-Prüfungen mit `phaseA_scripts/A2/a2_inventory.py` auf `facts_v2` neu (Ziel: 0 bei G1–G5, G7–G9) und legt alle SHA-256 im Manifest ab.

### I2 Raster v3

**D entfällt; neues Kriterium N „Nachteil/Risiko“ (Entscheidung).** Begründung: D misst als „low-cost-ness“ nur die Abwesenheit von Kosten. Eine Karte ohne Wirkung bekommt so ein hohes D und hebt das Kriterienmittel (A1 §3; B: Konstruktfehler). Würde man D nur umdeuten und den Buchstaben behalten, ließen sich alte und neue Werte verwechseln. Darum bekommt das Kriterium einen neuen Buchstaben und eine umgekehrte Richtung:
- **N, Nachteil und Risiko (0 bis 100, 0 = kein nennenswerter Nachteil):** Wrath-Exposition, Symmetrie, Selbstschaden und Lebenszahlung, Farbbelastung, Abhängigkeit von Kreaturen auf dem Feld, Game-Changer-Platz.
- **Regel:** N bewertet nur Kosten, die die Karte **mit sich bringt**. Dass eine Karte nichts tut, ist **kein** Vorteil: Eine Karte ohne Wirkung bekommt N nach ihren tatsächlichen Kosten (meist niedrig), und weil N nur **abzieht**, kann es ihr H nie heben.
- **Anker für N:** die bisherigen D-Anker, mechanisch umgerechnet zu N = 100 − D (Winds of Rath 100, Rites of Flourishing 75, Rampaging Baloths 50, Elvish Mystic 25, Arcane Signet 0; Land-Tabelle ebenso).

**Kriterien E, F, T, R, K** bleiben mit den v2-Definitionen. Dazu kommen Beispiele für die Streitklassen aus A1 §5: „Körper/Token ohne Ressourcengewinn“, Einmal-Blink, Antworten und Schutz (R bei drei Gegnern), Top-End mit Castability, Fixing ohne Ramp. Die Beispiele erklären nur die Kriterien, sie enthalten keine Zahlen für bestimmte Karten.

**Drei vorab definierte H-Varianten aus derselben Antwort (Rangfolge für die Variantenwahl: V3b, V3a, V3c):**

| Variante | H | Regel |
|---|---|---|
| Formel (für beide) | H_ref = 0,3·E + 0,3·F + 0,2·R + 0,1·T + 0,1·K − 0,2·N, auf 0 bis 100 begrenzt, ungerundet | Gewichte vorab gesetzt: **aus den alten Daten abgeleitet und gerundet** (normierte OLS-Gewichte von F1), nie aus dem Pilot |
| **V3a** „H frei, aber gebunden“ | Der Rater gibt H (Vielfache von 5) und sieht dabei die Formel. H darf **höchstens 10** von H_ref seiner eigenen Kriterien abweichen (Korridor) | Rohwert H_raw wird gespeichert. Für die Aggregation klemmt das Skript H_raw auf H_ref ± 10. **Korridorbruch** = \|H_raw − H_ref\| > 10 (gezählt, berichtet); **grober Korridorbruch** = > 15 (S4, höchstens 5 %) |
| **V3b** „H berechnet“ (erster Rang) | H_v3b = H_ref, vom Skript aus E, F, T, R, K, N | Der Rater gibt kein H für V3b; das H-Feld der Antwort gehört nur zu V3a |
| V3c „ohne N“ (dritte Variante) | H_v3c = 0,3·E + 0,3·F + 0,2·R + 0,1·T + 0,1·K aus derselben Antwort | dritter Rang in der Variantenwahl (§4, §6); die Kriterien gelten für V3c wie für V3b |

**Begründung der Gewichte (aus alten Daten abgeleitet, gerundet, inhaltlich geprüft):** Die gesetzten Gewichte sind die gerundeten, normierten OLS-Gewichte, mit denen F1 sein freies H implizit bildete (E 0,27, F 0,25, R 0,25, T 0,09, K 0,15; nachgerechnet aus A1 `extra.json`, `decomp.F1.weights`). Sie sind also **aus alten Daten abgeleitet**, nicht a priori. Inhaltlich passen sie zur Guide-Frage: Die H-Frage lautet „wie viel besser wird das Deck?“. Preis und Wirkung (E) und Deckplan (F) sind ihr Kern; R (nützlich, wenn gezogen) folgt. T und K sind Zusatzdimensionen, die für ganze Kartenklassen strukturell niedrig sind: Laut Guide ist T für Länder „almost always 0“, K für Einmaleffekte höchstens 25. Mit je 1/5 Gewicht würden sie Länder auf höchstens etwa 80 deckeln und die Skala stauchen. N zieht höchstens 20 Punkte ab (B: „Abzug 0 bis −20“). Eine Karte, die dem Deck von selbst schadet (N 100, wie Winds of Rath), verliert damit eine volle Bandbreite. **Offenlegung:** Vor der Festlegung wurden vier Gewichtungen auf alten Daten angesehen (`v3_baselines.json`, `gewichte_offenlegung`, n = 922, jeweils minus 0,2·(100 − D)):

| Gewichte E / F / R / T / K | ICC(2,1) F1–R2 | mittl. \|d\|/SD | SD | Spearman Quelldecks R2 / F1 |
|---|---|---|---|---|
| 0,2 / 0,2 / 0,2 / 0,2 / 0,2 (gleich) | 0,868 | 0,396 | 14,8 | 0,558 / 0,434 |
| **0,3 / 0,3 / 0,2 / 0,1 / 0,1 (gesetzt)** | 0,868 | 0,399 | 16,0 | 0,575 / 0,436 |
| 0,3 / 0,3 / 0,3 / 0,05 / 0,05 | 0,866 | 0,402 | 16,6 | 0,576 / 0,427 |
| 0,25 / 0,25 / 0,25 / 0,125 / 0,125 | 0,867 | 0,400 | 15,5 | 0,572 / 0,435 |

Die vier unterscheiden sich kaum; die Wahl bringt keinen messbaren Gewinn auf alten Daten, und sie ist nicht aus dem Pilot gewonnen. Gleiche Gewichte (0,2 je E, F, T, R, K, minus 0,2·N) werden vorab als **Sensitivitätsanalyse** festgelegt und im Pilot- und Vollauf-Bericht mitgerechnet; sie entscheiden nichts.

**N bleibt (Entscheidung mit Offenlegung):** Auf alten Daten (Näherung N = 100 − D) senkt der Abzug die Spearman-Korrelation mit der Quelldeck-Zahl: R2 0,619 → 0,575, F1 0,466 → 0,436. Die ICC ändert sich kaum (0,864 → 0,868; `v3_baselines.json`, `gesetzt_ohne_N_V3c`, n = 922). N bleibt trotzdem, aus zwei Gründen:
- Ohne N trägt **kein** Kriterium Farbbelastung, Symmetrie, Selbstschaden und Wrath-Exposition. E schließt die Farbkosten laut Guide ausdrücklich aus. Eine symmetrische Karte (etwa Rites of Flourishing) könnte dann nur über E, F und T bewertet werden, also so, als hätte sie keinen Nachteil. Das widerspricht der H-Frage „wie viel besser wird das Deck?“.
- Der Verlust (0,03–0,04) liegt deutlich unter der KI-Breite eines Pilotvergleichs (≈ 0,17), und Nutzung ist nicht Qualität. Ob Beliebtheit Nachteile übersieht, ist aus den Daten nicht trennbar.

V3c (ohne N) steht darum vorab als **dritte** Variante in der Rangfolge der Variantenwahl (§4): Sie wird nur vorgeschlagen, wenn V3b und V3a ein Muss-Kriterium des Vollaufs oder die Anzeige-Bedingung verfehlen.

**Ein Lauf, zwei Varianten (Kostenentscheidung):** Beide Varianten lassen sich aus derselben Antwort ableiten (E, F, T, R, K, N und H_raw). Zwei getrennte Läufe (100 Karten × 3 Rater × 2 = 600 Bewertungen) würden nur messen, ob das Wissen um die Formel die Kriterien verändert. Das ist hier keine Entscheidungsfrage. Der Pilot hat deshalb **342 Kartenbewertungen** in einem Lauf (6 Chargen × 19 Karten × 3 Rater: 270 für die Nicht-Anker-Karten, 72 auf den verdeckten Ankerplätzen; §3). Grenze: Weil der Rater die Formel sieht, könnte er in V3b seine Kriterien rückwärts an ein gewünschtes H anpassen. Das prüft S9 (keine Doppelmessung) zusammen mit dem Vergleich der Kriterienverteilungen mit F1/R2 (beschreibend).

**H-Ankertabelle entfällt.** Die alten H-Anker (v1-Bänder, z. B. Counterspell 67) liegen auf der alten H-Skala, die 5 bis 10 Punkte unter dem Kriterienmittel liegt (F1 −5,47, R2 −9,85; `v3_baselines.json`, H_gegen_kriterien). Sie widersprächen dem Korridor von V3a. Anker gibt es in v3 **nur je Kriterium**. Die alten H-Bänder (95–100 … 0–4) beschreiben die alte Skala und werden nicht übertragen (§6).

**Mehr Anker für 30/40/50/60/70 aus Konsens-Karten (Auswahlverfahren, vorab):**
1. Je Kriterium c ∈ {E, F, T, R, K} und Stufe L ∈ {30, 40, 60, 70}; L = 50 nur, wenn die v2-Tabelle für c keinen 50er-Anker hat (heute haben alle einen).
2. Grundmenge: Spells, die keine bisherige Ankerkarte sind.
3. **Stufe 1:** Karten mit G1-Bewertung, bei denen F1, R2 und G1 auf c höchstens 5 auseinanderliegen und der Median genau L ist.
4. **Stufe 2**, nur für Zellen, die nach Stufe 1 leer sind: Karten mit F1_c = R2_c = L.
5. Aus den Kandidaten einer Zelle wird **eine** Karte gezogen, mit `random.Random(20261128)` über die nach Name sortierte Liste. Bevorzugt werden Karten, die noch für keine andere Zelle gewählt sind. Reihenfolge der Zellen: c in E, F, T, R, K, dann L aufsteigend.
6. Leere Zelle nach Stufe 2: Sie bleibt leer, das wird im Guide vermerkt, und es wird nichts erfunden. Kandidatenzahlen aus `v3_baselines.json` (`anker_kandidaten`, nur Spells ohne bisherige Anker): Stufe 1 leer bei F30, F60, T40, T60, T70, K60 und K70 (R50 ist ebenfalls leer, wird aber nicht gebraucht, weil R schon einen 50er-Anker hat). Stufe 2 füllt F30 (21 Kandidaten), F60 (5), T40 (10), T60 (1) und K60 (2). **T70 und K70 bleiben leer.** Damit sind 18 Zellen besetzt, es kommen also höchstens 18 neue Ankerkarten für E–K dazu.
7. Der Ankerwert ist L. Die Beschreibung in der Tabelle ist eine kurze Funktionsbeschreibung aus dem Kartentext (wie in v2), ohne Beliebtheitsangaben.
8. N-Mittelstufen 30/40/60/70: dasselbe Verfahren auf N = 100 − D, aber nur über Spells mit H_pooled ≥ 28 (Karten, die etwas tun). Kandidaten (`anker_kandidaten.N_mittelstufen`): Stufe 1 N30 4, N40 1, N60 und N70 leer; Stufe 2 N60 1, N70 0. **N70 bleibt leer**, es kommen also höchstens 3 N-Anker dazu. Grenze: Das alte D enthielt die Nichtwirkungs-Verzerrung; N-Mittelanker sind deshalb als „aus altem D umgerechnet“ markiert.
9. **Grenze:** Konsens-Anker übernehmen das gemeinsame Urteil der alten Rater (mögliche gemeinsame Verzerrung, §7).
10. **Streichkriterium (vorab, für den Pilot):** Eine Ankerzeile (Karte × Kriterium) wird im Nachtrag gestrichen, wenn bei der ersten Platzierung das Mittel der drei Rater mehr als 10 Punkte vom Ankerwert abweicht **oder** weniger als 2 von 3 Ratern den Ankerwert innerhalb ±10 treffen. Eine Karte ohne verbleibende Ankerzeile wird im Vollauf als gewöhnliche Karte bewertet. Andere Gründe zum Streichen gibt es nicht.
11. **Ankerwerte stammen ausschließlich aus den alten Läufen** (Konsens wie oben bzw. die v2-Tabelle). Sie werden **nie** aus v3-Ausgaben gesetzt oder geändert. Ein Plan-Nachtrag (§3, Anpassungsrunde) darf Ankerkarten nur **streichen**; eine gestrichene Karte kommt nicht zurück, und kein Wert wird neu gesetzt. Sonst wäre S5 per Konstruktion bestehbar.
12. **Reihenfolge:** Zuerst wird der Ankersatz im Guide-v3-PR festgelegt, **danach** das Pilot-Manifest, das alle Ankerkarten aus den Nicht-Anker-Schichten ausschließt.

**Ankersatz v3:** die alten Ankerkarten mit mindestens einer Kriterienzeile (E, F, T, R, K oder D→N), das sind **40** (46 minus 6, die nur in der H-Tabelle stehen: Avacyn's Pilgrim, Cryptic Caves, Negate, Reality Shift, Tatyova, Benthic Druid, Temple of Plenty; `anker_mae_alt_kriterienzeilen`). Dazu kommen die neuen Konsens-Anker (höchstens 18 für E–K und 3 für N, zusammen höchstens 21), also A ≤ 61 Ankerkarten. Die 6 nur-H-Karten werden in v3 als gewöhnliche Karten bewertet.

**Alle Ankerkarten verdeckt bewertet:** Jede Ankerkarte (alte und neue, auch Länder) wird nur mit einem Guide bewertet, aus dem **alle** ihre Ankerzeilen entfernt sind (leave-one-anchor-out je Charge, wie R2, Ganzwort-Prüfung im Manifest). Im Guide sind Anker nur als Tabelle sichtbar, mit Wert und Kurzbeschreibung. Der Rater bewertet eine Ankerkarte nur dann, wenn sie verdeckt in seiner Charge steht (I3).

### I3 Chargen

| Regel | Festlegung | Befund / Quelle |
|---|---|---|
| Größe | höchstens **20 Karten je Instanz**: 15 bis 16 Nicht-Anker-Karten plus **4 verdeckte Ankerplätze** (3 Spells, 1 Land) | R2: 88 bis 100 je Instanz mit leichtem Positionseffekt (A1 §2.4); B: große Chargen verschlechtern (mittel), Zahl UNBELEGT |
| Mischung | Nicht-Anker-Karten werden reihum über die Schichten auf die Chargen verteilt; Kartenarten gemischt | B §2 (Chargeneffekt sonst nicht trennbar) |
| Reihenfolge | **je Rater** eigene Permutation innerhalb der Charge, `random.Random(Seed + Rater-Index)`; gleiche Chargen-Zusammensetzung für A, B und C | Position und Karte trennbar (S6) |
| Lesen | in 10er-Blöcken: Karten 1–10 lesen und beantworten, dann 11–20 | wie R2 |
| Antwortformat | **ein Wert je Antwortzeile**. Die Ausgabedatei ist JSON Lines. Je Karte kommt zuerst eine Kartenzeile (`reason`, `confidence`, `uncertainty`, `rule_claims`, `pattern_check`), dann je Kriterium eine Zeile in fester Reihenfolge E, F, T, R, K, N (`criterion`, `note`, `value`; die Notiz vor dem Wert), zuletzt die H-Zeile (V3a). Keine Sammelzeile mit mehreren Werten oder Karten | B: Ankereffekte bei mehreren Labels in einer Ausgabe (Stureborg 2024) |
| Schema | `output_schema_v3.json` im Guide-v3-PR; das Auswerteskript setzt die Zeilen je Karte zusammen | |

### I4 Rater

- **Drei Rater-Instanzen A, B und C aus drei verschiedenen Modellstufen.** Ausdrücklich: Verfügbar sind **nur Modelle einer Familie in verschiedenen Stufen**; ein Rater außerhalb dieser Familie ist nicht beschaffbar. Der Plan leitet deshalb **keine Aussage „unabhängige Familien“** ab. Übereinstimmung zwischen A, B und C ist Übereinstimmung innerhalb einer Familie (B: Panel-Vorteil durch Familien-Diversität hier nicht erreichbar).
- **Owner-Entscheid (Stufen), beantwortet 2026-11-23: „Ja, drei Stufen (Empfehlung)“ (§8).** Hintergrund: Nach AGENTS §7 erben Helfer Stufe und Aufwand des Leads; nur der Owner darf das ändern. Eine Co-Lead-Lesart reicht dafür nicht; bis zum 2026-11-23 lag keine solche Owner-Aussage vor. Seit dem 2026-11-23 liegt sie vor (Wortlaut in §8). **Der Pilot startet erst nach der Antwort des Owners auf die Rater-Stufen** (Owner-Frage 2, §8; erfüllt am 2026-11-23).
- **Frisch je Charge, ein Ordner je (Rater, Charge):** Jede Charge eines Raters läuft in einer neuen Instanz ohne Vorkontext, mit einem Satz Startanweisung („Du bist Rater X, Charge k. Lies `<Ordner>/v3_rater_instructions.md` und folge ihr.“). Der Ordner liegt im Scratchpad **außerhalb** des Repo-Klons. Er enthält **nur** Guide, Anweisung, Schema und Eingabe **dieser** Charge, also keine Guides anderer Chargen (mit deren verdeckten Ankerzeilen), keine früheren Ausgaben und keine Manifeste. Die Ausgabe wird nach Abschluss mit SHA-256 in den Analystenordner verschoben, bevor die nächste Instanz startet.
- **Wiederholungen** (Anker-Wiederholungen in anderen Chargen, Pilot-Retest im Vollauf) laufen in einer eigenen frischen Instanz mit eigenem Ordner, in dem **keine** frühere Ausgabe liegt.
- **Werkzeuge:** Die Rater-Instanz bekommt eine Agent-Definition mit der Werkzeugliste **nur Read und Write**. Ausgeschlossen sind Bash bzw. Shell, Web-Abruf, Websuche, Glob/Grep und das Starten weiterer Agenten. Die Anweisung verbietet, außerhalb des eigenen Ordners zu lesen oder zu schreiben. **UNBELEGT** ist, dass die Pfadsperre technisch erzwungen wird: Read kann jeden Pfad öffnen. Deshalb gilt der nächste Punkt.
- **S8 aus dem Harness-Transkript, nicht aus Selbstauskunft:** Nach jeder Charge scannt ein Skript das Transkript der Instanz, das der Harness schreibt. Der Scan gibt **nur Werkzeugname und Pfad** jedes Aufrufs aus, nie den Inhalt eines Write-Aufrufs. Jeder Aufruf eines nicht erlaubten Werkzeugs und jeder Pfad außerhalb des eigenen Ordners zählt als Blindheitsverstoß (A2). Eine Selbstauskunft der Instanz zählt nicht als Beleg. Fehlt das Transkript, ist die Charge ungültig (A2). Weitere Regeln:
  - Das Transkript enthält alle Bewertungen ein zweites Mal; sein **SHA-256 gehört in den Freeze** (§4, §5) neben den Ausgaben.
  - Die Zuordnung Instanz → Agent-ID wird im Laufprotokoll festgehalten.
  - Modell und Aufwand je Instanz werden aus den Metadaten der Instanz (`.meta.json` des Harness) übernommen, nicht aus Selbstauskunft.
  - Der Ordnername kann Nachbarpfade verraten (Schema der Ordner). Dass eine Instanz einen Nachbarordner nicht öffnet, ist **UNBELEGT**; nur der Transkript-Scan fängt einen solchen Zugriff, und zwar nachträglich.
- **Laufprotokoll VOR dem Start (Pflicht):** je Rater Familie, Stufe, Modell-Version, Aufwand und Temperatur (oder „Voreinstellung, nicht setzbar“), Agent-Definition mit Werkzeugliste, Ordnerschema, Seeds. Ablauf:
  - Der **Inhalt des Laufprotokolls und sein SHA-256 werden vor dem ersten Start als Kommentar in #1404 gepostet**; dort dürfen Modell-IDs stehen. Der Kommentar ist der dauerhafte, datierte Beleg; die Datei liegt zusätzlich im Scratchpad.
  - Im Repo steht nur eine Fassung ohne Modellnamen („Rater A/B/C = Stufe groß/mittel/klein; gleiche Familie“), mit Verweis auf den Kommentar.
  - Fehlt das Protokoll oder der Hash-Kommentar, gilt A3: keine Aussagen über Stufen.
- **Pflichtmessung Kontingent:** Je Instanz werden Dauer und Verbrauch (Token bzw. Kontingentanteil, soweit der Harness ihn zeigt) protokolliert. Der Pilotbericht leitet daraus die Tranchengröße und den Zeitplan des Vollaufs ab.

### I5 Aggregation (vorab)

- Je Karte und Kriterium der **Median über A, B und C** (bei drei Werten gleich dem getrimmten Mittel), ungerundet.
- **V3b:** H_v3b = H_ref aus den Kriterien-Medianen. **V3a:** H_v3a = Median der drei geklemmten H-Werte.
- Fehlt ein Rater für eine Karte (ungültig nach §5), gilt das Mittel der zwei übrigen mit Marke `n_rater = 2`. Bei nur einem gültigen Rater geht die Karte nicht in H_v3 ein (Marke `n_rater = 1`).
- **Keine Versatz-Korrektur**, außer der Pilot zeigt auf den verdeckten Ankern einen Versatz je Kartenart (Kreatur, Nicht-Kreatur-Spell, Land) von mehr als 2 Punkten mit einem 95-%-KI ohne 0. Gemessen wird der Versatz als Median-Aggregat minus Ankerwert, gemittelt über die Kriterien mit Ankerzeile. Nur dann wird eine **additive Ankerkorrektur je Kartenart** aus den Vollauf-Ankern berechnet und **nur vorgeschlagen**: beide Fassungen im Bericht, Anwendung nur nach Owner-Go. Keine Quantil-Normalisierung.
- Die Unsicherheit je Karte wird mitgeführt: Spannweite max − min über A/B/C auf H_v3 und je Kriterium.

### I6 Adjudikation

- **Auslöser:** Rater-Abstand (max − min über A/B/C) auf **H_v3b** je Karte, also auf der Variante mit dem ersten Rang, **≥ 15** ⇒ Marke `abstand_ge15`. Der Abstand im freien H (V3a-Rohwert) wird zusätzlich berichtet, löst aber nichts aus. Gemessen wird so schon vor der Variantenwahl. Die Karte wird nie gelöscht.
- **Dritter Blick (Fehlerprüfung, keine vierte Meinung):** Eine frische Instanz der größten Stufe sieht den Kartenblock, den Guide v3 und die drei Bewertungen mit Begründungen, ohne Rater-Kennung. Sie prüft je Bewertung nur, ob ein **objektiver Fehler** vorliegt: Kartentext falsch gelesen, Regelfehler gegen Text, Ruling oder Comprehensive Rules, Kriterium falsch angewendet nach Guide-Wortlaut. Jede Feststellung braucht ein wörtliches Zitat.
- **Folge:** Eine Bewertung mit belegtem objektivem Fehler fällt für diese Karte aus der Aggregation; H_v3 ist dann das Mittel der zwei übrigen (Marke `adjudiziert`). Ohne Fehlerbefund bleibt der Median. Einen Geschmacksunterschied entscheidet die Adjudikation nicht.
- Gemeldet werden die Zahl der Karten, der Befunde und der verworfenen Bewertungen je Rater. Die Adjudikation sieht die anderen Ratings, darum ist sie keine unabhängige Messung und zählt in S1 bis S9 nicht (S-Kriterien werden **vor** der Adjudikation gerechnet).
- **Selbstpräferenz:** Der Adjudikator hat dieselbe Stufe wie Rater A (B: Selbstpräferenz belegt). **Owner-Bestätigung erteilt am 2026-11-23 (Owner-Frage 1, §8: „Ja, bestätigen (Empfehlung)“):** Die Folge oben gilt. Befunde mit Beteiligung von Rater A werden in einer eigenen Spalte „Befund der Stufe von Rater A über Rater A“ gesondert ausgewiesen.
- **Owner-Go (ausdrücklich):** Eine dritte Bewertung oder Adjudikation größerer Abweichungen braucht ein Owner-Go (so der Plan von #1761, §8). Den Owner-Auftrag vom 2026-11-22 „setze den Plan gründlich und vollständig um“ las der Co-Lead als Go für die Adjudikation **im Rahmen dieses Plans**; der Owner hat das am 2026-11-23 bestätigt: „Ja, bestätigen (Empfehlung)“ (§8).

## §3 Pilot

**Menge: 100 Karten.** Die 90 Nicht-Anker-Karten werden ohne Überschneidung in dieser Reihenfolge gezogen; davor ist der Ankersatz v3 festgelegt (I2), und alle Ankerkarten sind ausgeschlossen. Seed `random.Random(20261127)`. Gezogen wird innerhalb jeder Quote aus der nach `oracle_id` sortierten Liste.

| Schicht | n | Grundmenge (Größe aus `v3_baselines.json`, vor Abzug neuer Anker) | Quoten innerhalb der Schicht |
|---|---|---|---|
| kaum fair bewertbar | 10 | 59 Nicht-Anker-Karten aus `phaseA_unfair_cards.json` | je eine Karte aus jeder vorkommenden Defektklasse (Mechanik, Land-Fakten, Seiten/Spezialtypen/Verweise, Hybrid-Castability), Rest zufällig |
| schwer | 40 | 254 Nicht-Anker-Karten mit \|d\| ≥ 15 | 8 mit Rolle Token, Counter oder Tapper; 8 Kreaturen mit MV ≥ 6; 16 übrige Kreaturen; 8 Nicht-Kreatur-Spells. Zuordnung in dieser Reihenfolge. Ist eine Teilmenge zu klein, wird aus der allgemeinen Schicht aufgefüllt. Die Bandzusammensetzung (Mittelband 28–49) wird berichtet |
| Kontrolle | 30 | 150 Nicht-Land-Nicht-Anker-Karten mit \|d\| < 5 | 15 Kreaturen, 15 Nicht-Kreatur-Spells |
| Länder | 10 | 52 Nicht-Anker-Länder (ohne die schon gezogenen) | zufällig |
| Anker verdeckt | 10 | Ankersatz v3 (A ≤ 61) | 5 der 40 alten Anker mit Kriterienzeilen (3 Spells, 2 Länder), 5 neue Konsens-Anker; `random.Random(20261128)` |

**Chargen:** 6 Chargen zu je 15 Nicht-Anker-Karten plus 4 Ankerplätze, also 19 Karten. Die 24 Ankerplätze füllen die 10 Ankerkarten: jede mindestens zweimal, keine zweimal in derselben Charge. Die erste Platzierung (in der Chargen-Reihenfolge 1–6) zählt als Bewertung und geht in S5 ein. Wiederholungen sind Anker-Retest und werden nur berichtet. Dieselben 6 Chargen gehen an A, B und C (je Rater eigene Reihenfolge). Das ergibt **18 Instanzen** und 342 Kartenbewertungen (270 Nicht-Anker, 72 Ankerplätze). Das Manifest `v3_pilot_manifest.json` enthält Seeds, Quell-SHA-256 (Fakten v2, Guide v3 je Charge, Schema, Anweisung), Schichten und die Zuordnung zu den Chargen. Es wird im Guide-v3-PR mit einem Skript erzeugt, zweimal byte-gleich.

**Erfolgskriterien (vorab; S-Kriterien werden für V3a und V3b getrennt gerechnet, auf den 90 Nicht-Anker-Karten, vor der Adjudikation; Intervalle: Bootstrap über Karten, 2000 Ziehungen, `random.Random(20261127)`, 95 % Perzentil):**

| Nr | Muss | Kriterium | Schwelle | Alte Vergleichswerte (Herkunft, n/N) |
|---|---|---|---|---|
| S1 | Muss | ICC(2,1) zwischen A, B, C auf H_v3 (absolute Übereinstimmung, Einzelrater) | Punkt ≥ **0,87** und untere KI-Grenze ≥ **0,80** | F1–R2 freies H 0,818 [0,793; 0,839]; F1–R2 unter der Formel 0,868 [0,851; 0,884] (922/922). Trockenlauf V3b: Median 0,827, 5–95 % [0,781; 0,867], erfüllt in 9 von 200 Ziehungen |
| S2 | **Soll** (nur berichtet, nicht abbruchrelevant; misst fast dasselbe wie S1 mit strengerer Schwelle) | mittlere paarweise \|Δ\| über die drei Raterpaare, geteilt durch die gepoolte SD aller 3 × 90 Werte | ≤ **0,39** (Punkte zusätzlich berichtet) | freies H 0,465 (9,16 Punkte); Formel 0,396 bis 0,399 (5,85 bis 6,36 Punkte) (922/922); Welle 1 ohne markierte 8,38 Punkte (265, #1758). Trockenlauf V3b: Median 0,463, 5–95 % [0,409; 0,528], erfüllt in 2 von 200 Ziehungen |
| S3 | Muss (Schutz) | **differenzieller** Versatz Kreatur gegen Nicht-Kreatur-Spell je Raterpaar: (mittlere Δ der Kreaturen − mittlere Δ der Nicht-Kreatur-Spells) / SD gepoolt, 3 Tests (A–B, A–C, B–C). KI analytisch (Welch-Standardfehler), Bonferroni über die 3 Tests: kritischer Wert 2,50 (1 − 0,05/3 mit t-Näherung bei etwa 40 Freiheitsgraden). **S3c** (nur berichtet): Kreatur–Land und Nicht-Kreatur–Land mit etwa 12 Ländern. **S3b** (nur berichtet): gleichmäßiger Versatz je Raterpaar | **verfehlt**, wenn für ein Raterpaar \|·\| > **0,15** SD (bei SD 16 etwa 2,4 Punkte) **und** der Kontrast den kritischen Wert überschreitet | Formel auf 922 Karten: Kreatur −0,073 / Nicht-Kreatur +0,127 SD, differenziell 0,20 SD. **Simulation ohne Versatz** (`pilot_simulation_ohne_defekt`, 51/27/12 Karten, SD 16, 1000 Wiederholungen): Fehlalarm 4,4 % / 4,3 % / 2,5 % bei ICC 0,87 / 0,90 / 0,93. **Teststärke** (ein Rater verschiebt nur Kreaturen): bei 0,15 SD 20 % / 25 % / 35 %, bei 0,25 SD 51 % / 64 % / 81 %. S3 erkennt also nur deutliche Versätze sicher. Begründung der Beschränkung: Mit allen 9 Kontrasten lag der Fehlalarm im Review bei 31–33 % |
| S4 | Muss für V3a | Anteil der Karten mit grobem Korridorbruch \|H_raw − H_ref\| > 15, je Rater | ≤ **5 %**; Korridorbrüche (> 10) berichtet | Bezug H gegen M5 (ungewichtet, ohne D): F1 64/922 (6,9 %), R2 254/922 (27,5 %); > 10: F1 297/922, R2 572/922. Alte Guide-Lücke (mit D) > 15: F1 284/922, R2 W1 132/300, W2 457/622 (A1 §3) |
| S5 | Muss | verdeckte Anker: MAE des Median-Aggregats gegen den Ankerwert über die **erste Platzierung** jeder verdeckten Ankerkarte × **alle** ihre Kriterien mit Ankerzeile (E, F, T, R, K, N). Beispiel: Kor Skyfisher hat Ankerzeilen E 75 und R 75; bei der ersten Platzierung sind die Mediane E 70 und R 80, das ergibt zwei Terme mit Fehler 5 und 5. S5 ist das Mittel aller Terme der 10 Ankerkarten | ≤ **6**; je Rater und getrennt für alte und neue Anker berichtet; Wiederholungen nur als Retest | blinder Einzelrater R2 auf Kriterienzeilen: „v1 fixed“ 4,58 (36 Zeilen), übrige 8,63 (51), zusammen 6,95 (87) (`anker_mae_alt_kriterienzeilen`; F1 sah die übrigen Zeilen und ist nicht blind). Die Schwelle liegt unter dem blinden Einzelrater. Die hohe MAE der übrigen alten Anker weist auf schwer reproduzierbare Ankerwerte hin; solche Anker darf ein Nachtrag nur streichen (I2 Nr. 10 und 11) |
| S6 | Muss | Positionsdrift je Rater: OLS-Steigung von (Raterwert − Median der drei) auf die Position 1–19, über alle 90 Nicht-Anker-Karten, × 10. KI analytisch (OLS-Standardfehler), Bonferroni über die 3 Rater: kritischer Wert **2,44** = t-Quantil 1 − 0,05/6 bei 88 Freiheitsgraden | **verfehlt**, wenn für einen Rater \|·\| > **1,5** Punkte je 10 Positionen **und** die Steigung den kritischen Wert überschreitet | R2 Charge 6: ρ(Position, d) −0,35 (88 Positionen, A1 §2.4). **Simulation ohne Drift, 20 000 Läufe je ICC** (`s6_fehlalarm_20000`): Fehlalarm mit t-Quantil 2,44 **4,9 % / 4,8 % / 4,6 %** (ICC 0,87 / 0,90 / 0,93); mit dem Normalquantil 2,394 wären es 5,5 % / 5,5 % / 5,1 %, darum das t-Quantil. Schwelle 1,5: Die Fehlalarmrate liegt bei allen drei ICC ≤ 5 %, und kleinere Driften als 1,5 Punkte je 10 Positionen (unter 3 Punkten über eine Charge) sind für die Reihenfolge der Karten unerheblich. **Teststärke** (Drift bei einem Rater): 1,5 Punkte je 10 Positionen 10–20 %, 3,0 Punkte 36–64 % |
| S7 | **Muss im Vollauf**; im Pilot nur Frühwarnung (berichtet, nicht abbruchrelevant) | Spearman(H_v3, Quelldeck-Zahl) − Spearman(H_alt,gleich, Quelldeck-Zahl) auf denselben Karten (Pilot: 90, Vollauf: alle Nicht-Anker-Karten), gepaarter Bootstrap. **H_alt,gleich** = Mittel von F1 und R2 unter **derselben** H-Definition wie die geprüfte Variante: für V3b die gesetzte Formel mit N = 100 − D, für V3a das auf H_ref ± 10 geklemmte freie H | Punkt ≥ **−0,05** und untere KI-Grenze ≥ **−0,15**; für V3c ist H_alt,gleich die gesetzte Formel ohne N. Der Vergleich gegen H_pooled ist die Anzeige-Bedingung in §6 (im Pilot nur Frühwarnung) | Auf allen 922 Karten: R2 freies H 0,673 gegen R2 unter der gesetzten Formel 0,575; F1 0,504 gegen 0,436. KI-Breite der gepaarten Differenz auf 100 Zufallskarten ≈ 0,17 (`s7_breite`). Trockenlauf gegen H_pooled: V3b Median −0,138 (0 von 200 Ziehungen ≥ −0,05), V3a-Analogon −0,028 (199 von 200). Begründung unter der Tabelle |
| S8 | Muss | Blindheit: zählende Verweis-Treffer nach der Zähl-Regel von #1761 §9 **und** kein nicht erlaubtes Werkzeug und kein Pfad außerhalb des eigenen Ordners im **Harness-Transkript** der Instanz (I4) | **0** nach Wiederholungen (§5, A2) | Welle 2: 1 Treffer, eingestuft „zählt nicht (a)“, also 0 zählende (`docs/analysis-reports/rating_full_second_run_20261122.md` §2) |
| S9 | Muss (Schutz) | höchste \|r\| zweier Kriterien (E, F, T, R, K, N) über die Median-Aggregate; je Rater berichtet | < **0,90** | F1 0,673 (F–K), R2 0,752 (E–R) (922/922). Schutz gegen Doppelmessung (B: Faktorkollaps) |

**Trockenlauf auf alten Daten (vorab, `v3_baselines.json`, `trockenlauf_pilotfoermig`):** 200 pilotförmige Ziehungen nach den Schichten oben (ohne Anker, Seed 20261124) mit F1 und R2 als zwei Rater. Sie dienen nur als Orientierung, weil die schwere Schicht nach alter Uneinigkeit gezogen ist; die alten Rater sehen auf diesen Karten darum schlechter aus, als sie sind (Regression zur Mitte).
- **V3b (gesetzte Formel):** S1 Median 0,827, S2 0,463, S3b gleichmäßiger Kreatur-Versatz 0,238 SD, größter differenzieller Punktwert 0,428 SD (einschließlich Land-Kontraste).
- **V3a-Analogon (freies H, auf H_ref ± 10 geklemmt):** S1 0,737, S2 0,534, S3b Kreatur 0,517 SD, differenziell 0,672 SD. Die Klemme lässt den H-Schritt-Versatz zum Teil stehen.
- **Lesart:** Neue Rater, die nicht besser sind als die alten, verfehlen S1 und S2 erwartungsgemäß. Genau das soll die Messlatte leisten.
- **Begründung zu S7:** Gegen H_pooled würde V3b S7 schon wegen der Formel verfehlen. Die Formel kostet auf allen 922 Karten **0,068 bis 0,115** an Übereinstimmung mit der Nutzung (F1 0,068–0,070, R2 0,098–0,115, gesetzte bzw. gleiche Gewichte), gleich welche Rater; im Trockenlauf gegen H_pooled sind es −0,138. Ob das freie H dabei ein Beliebtheitsleck oder echte Information trägt, ist nicht trennbar (§7). Ein Vergleich gegen H_pooled würde also die Formel prüfen, nicht die Bewertung. Darum vergleicht S7 mit den alten Läufen unter derselben H-Definition. Der Vergleich gegen H_pooled ist eine **eigene, vorab gesetzte Anzeige-Bedingung** (§6).

**Gesamt-Fehlalarm des Pilots (synthetisch, vorab, `pilot_simulation_ohne_defekt`):** Simuliert ist ein Pilot **ohne Qualitätsdefekt**: wahre Werte plus unabhängiger Raterfehler, keine Drift, Ankerwerte richtig. Rater A bewertet entweder ohne Versatz oder um 0,1 / 0,15 / 0,2 SD strenger. S7 ist als Normalverteilung mit der KI-Breite aus `s7_breite` modelliert, S8 und S9 gelten als erfüllt. Es zählt der Anteil der Piloten, die mindestens ein Muss-Kriterium des Pilots verfehlen; 1000 Wiederholungen je Zelle.

Geltende Regeln (Muss im Pilot: S1, S3, S5, S6, S8, S9; S2 Soll; S7 Frühwarnung). Anteil gescheiterter Piloten:

| wahre ICC | ohne Versatz | 0,1 SD | 0,15 SD | 0,2 SD |
|---|---|---|---|---|
| 0,87 | 54,5 % | 58,4 % | 66,4 % | 73,0 % |
| **0,90** | **15,9 %** | **17,7 %** | **19,1 %** | **26,4 %** |
| 0,93 | 7,6 % | 10,5 % | 9,4 % | 9,3 % |

Zum Vergleich die Regeln von Runde 2 (S2 und S7 Muss im Pilot): bei ICC 0,90 36,1 % / 38,3 % / 45,0 % / 51,8 %, bei 0,93 21,7–23,3 %. Die Einzelraten je Kriterium stehen in `v3_baselines.json`; bei ICC 0,90 ohne Versatz sind es S1 6,8 %, S2 18,2 %, S3 4,3 %, S5 0 %, S6 5,3 %, S7 13,4 %. Die Methodik-Review rechnete unabhängig etwa 15 / 17 / 22 / 26 % bei ICC 0,90 und 9 % bei 0,93. Alle eigenen Werte liegen innerhalb von 3 Punkten davon, mit der Runde-2-Zahl ohne Versatz knapp darüber (36,1 % gegen 35,5–37,7 %).

**Der Pilot verwirft einen echten Verbesserungseffekt** (wahre ICC 0,90, also besser als die alten Läufe unter der Formel) **in 16 % der Fälle ohne Raterversatz und in 18 bis 26 % mit einem um 0,1 bis 0,2 SD strengeren Rater.** Bei wahrer ICC 0,93 sind es 8–11 %. Das Ziel „höchstens 20 % bei ICC 0,90“ ist ohne und mit kleinem Versatz erreicht, bei 0,2 SD Versatz nicht. S2 und S7 wurden dafür aus dem Pilot-Abbruch genommen, nicht gelockert: S2 misst fast dasselbe wie S1, und S7 wird im Vollauf auf allen Karten mit viel engerem KI geprüft (Vergleichsbasis unverändert, wie vom Owner bestätigt). Folgen, offen genannt:
- **Risiko eines falsch negativen Pilots:** Auch einwandfreie Rater verfehlen den Pilot in etwa jedem sechsten Fall, mit Raterversatz in jedem vierten. Die Anpassungsrunde ist **keine unabhängige** zweite Chance: Dieselben Rater mit demselben Versatz bewerten erneut, und ihre Fehlschläge hängen zusammen. Eine Gesamtrate für beide Runden wird deshalb nicht angegeben.
- Ein „nicht erfüllt“ heißt darum nicht, dass v3 schlechter ist. Der Pilotbericht nennt diese Fehlalarmrate neben dem Ergebnis.
- Bei einer wahren ICC von 0,87 (genau die Schwelle) scheitert der Pilot meist; das ist beabsichtigt, weil S1 „besser als die alten Läufe“ verlangt.

Die Messgröße für S7 ist `deck_list_count` aus `usage_holdout.jsonl`, also Quelldecks über alle Brackets. Die Datei liegt nicht im Repo, ihr SHA-256 `c3d1f693…` steht in A1. Die Rater sehen sie nie. Die Referenzdeck-AUC ist nur beschreibend, weil der Deck-Kontextabsatz aus der Referenzliste stammt (§7).

**Entscheidungsregel (vorab):**
1. Der Pilot-Entscheid hängt **nur an V3b**: V3b erfüllt alle Muss-Kriterien des Pilots (S1, S3, S5, S6, S8, S9) ⇒ Vollauf. V3a (mit S4) und V3c werden im Pilot berichtet und sind erst für den Owner-Vorschlag nach dem Vollauf relevant. Gewählt wird im Pilot keine Variante; der Vollauf erhebt immer alle Teilkriterien **und** den freien H in einer Antwort.
2. **S2** (Soll), **S7** und die Anzeige-Bedingung (§6) werden im Pilot nur als **Frühwarnung** berichtet, nicht als Abbruch.
3. Verfehlt V3b ein Muss-Kriterium des Pilots: höchstens **eine Anpassungsrunde**. Zuerst kommt ein Plan-Nachtrag (Datei `rating_v3_plan_nachtrag1_*.md`) ins Repo, **bevor** neu bewertet wird. Er nennt die Änderung (z. B. Guide-Präzisierung oder Streitklassen-Beispiele bei S1/S2; bei S5 nur das **Streichen** von Ankerkarten nach dem Streichkriterium I2 Nr. 10, nie ein neuer Wert) und begründet sie aus dem Pilotbericht. Die Chargengröße bleibt höchstens 20. Dann folgt ein neuer Pilot auf einer **frischen Ziehung** derselben Schichten (Seed `random.Random(20261129)` für die Nicht-Anker-Karten, ohne die Nicht-Anker-Karten des ersten Pilots; Seed `random.Random(20261132)` für die 10 verdeckten Anker und ihre Plätze). Nicht gestrichene Ankerkarten bleiben im Ankersatz und dürfen mit unverändertem Wert wieder verdeckt stehen; gestrichene kommen **nie** wieder. Bestehen ⇒ Vollauf; sonst Bericht „nicht erfüllt“ und kein Vollauf ohne neuen Owner-Entscheid.
4. Einen Rückfall auf 10er-Chargen gibt es nicht; er würde nie pilotiert und brauchte etwa doppelt so viele Instanzen. Verfehltes S6 zählt wie jedes Muss-Kriterium: Anpassungsrunde nach Punkt 3 oder „nicht erfüllt“.

## §4 Vollauf

- **Menge:** alle 922 Karten mit Generator v2, Guide v3 und Schema v3 byte-gleich wie im bestandenen Pilot (SHA-256 im Manifest). Die Pilotbewertungen gehen **nicht** in H_v3 ein; alle 922 werden neu bewertet.
- **Chargen:** höchstens 20 Karten (16 Nicht-Anker plus 4 Ankerplätze). Zahl der Chargen = ⌈(922 − A)/16⌉ mit A = Zahl der Ankerkarten v3 (40 alte plus höchstens 21 neue); bei A zwischen 40 und 61 sind das **54 bis 56 Chargen**. Jede Ankerkarte steht mindestens einmal verdeckt, die erste Platzierung zählt. Seed `random.Random(20261130)`.
- **Aufwand:** 54 bis 56 Chargen × 3 Rater = **162 bis 168 Instanzen**, dazu die Adjudikation (Karten mit Abstand ≥ 15 in Gruppen zu höchstens 10 je Instanz; Bezug: unter der gesetzten Formel hatten F1 und R2 bei 70 von 922 Karten |d| ≥ 15; mit drei Ratern ist die Spannweite größer, geschätzt 10 bis 15 % der Karten, also etwa 10 bis 14 Instanzen). Der Pilot hat 18 Instanzen.
- **Reihenfolge und Wiederaufnahme:**
  - Tranchen zu 6 Chargen × 3 Rater = 18 Instanzen, innerhalb einer Tranche reihum A, B, C je Charge. Bei einem Limit-Halt sind so alle Rater gleich weit.
  - Eine Charge ist fertig, wenn ihre Ausgabedatei vollständig und gültig ist (mechanischer Validator, der nur Zählungen ausgibt).
  - Halt mitten in einer Charge: Die Teil-Ausgabe wird mit SHA-256 in den Analystenordner verschoben und die Charge mit frischer Instanz **ganz** neu gestartet. Es gibt keine Fortsetzung mitten in der Charge und keine Auswahl einzelner Karten.
  - Ein Fortschrittsprotokoll im Scratchpad hält je Charge und Rater den Status fest (offen / läuft / fertig / verworfen).
- **Freeze je Tranche:** Nach jeder Tranche werden die SHA-256 aller neuen Ausgaben **und der zugehörigen Harness-Transkripte** in #1404 gepostet, **bevor** ein Wert gelesen wird.
- **Retest-Teilmenge:** Die 90 Nicht-Anker-Pilotkarten werden im Vollauf erneut bewertet. Das ist Test-Retest je Rater mit unverändertem Guide und Generator, nur beschreibend: ICC und SD/√2. Ändert eine Anpassungsrunde Guide oder Generator, dienen die Karten des zweiten Pilots als Retest. Die wiederholten Ankerplätze geben einen zweiten, kleinen Retest.
- **Variantenwahl nach dem Vollauf (vorab festgelegt):** S1 bis S9 werden mit denselben Schwellen auf allen Nicht-Anker-Karten für V3b, V3a und V3c berechnet (S5 auf der ersten Platzierung jeder Ankerkarte, S4 nur für V3a). **Muss-Kriterien des Vollaufs:** S1, S3, S5, S6, S7, S8, S9, für V3a zusätzlich S4; S2 wird berichtet. Vorgeschlagen wird die **erste Variante in der Reihenfolge V3b, V3a, V3c**, die alle Muss-Kriterien des Vollaufs erfüllt **und** die Anzeige-Bedingung (§6) auf den Vollauf-Karten. Erfüllt keine Variante beides, wird nur berichtet, ohne Vorschlag („im Vollauf nicht bestätigt“), mit allen Kriterien je Variante und n/N.

## §5 Auswertungskette

- **Wiederverwendung:** Die Kette aus #1761/#1763 bleibt: Freeze → Verweis-Treffer → Klassifikation → Auswertung. Aus `scripts/analysis/rating_second_run_full_eval.py` werden übernommen: `freeze_guard`, `parse_checksums`, `find_hits`/`rater_fields`/`render_hits`, `check_classification`, `icc_set`/`anova2`, `bootstrap_multi`, `fatigue`, `run_log_view`. Neu ist `scripts/analysis/rating_v3_eval.py`: Zusammensetzen der Ein-Wert-Zeilen, I5, I6, ICC(2,1) für drei Rater, S1 bis S9, Entscheidungsregel. Dazu kommen synthetische Tests.
- **Reihenfolge (Pflicht):**
  1. Generator-v2-PR und Guide-v3-PR mit Manifest stehen im Repo; erst dann bekommt der Co-Lead die Pfade.
  2. Das **Auswerteskript wird als eigener PR committet, bevor eine v3-Ausgabe geöffnet wird.** Verpflichtende Rot/Grün-Tests: Ein Mutant mit S1-Schwelle 0,80 statt 0,87 ändert das Urteil auf synthetischen Daten; die V3a-Klemme; Median vor Formel (nicht umgekehrt); `n_rater = 2` und `1`; Pilot-Entscheidungsregel mit allen Ausgängen; Rangfolge V3b, V3a, V3c mit Anzeige-Bedingung nach dem Vollauf; S3 nur mit dem Kreatur-gegen-Nicht-Kreatur-Kontrast und Bonferroni (ein Mutant mit allen 9 Kontrasten wird rot); S6 mit Bonferroni; der Transkript-Scan gibt keinen Write-Inhalt aus; S-Kriterien vor der Adjudikation.
  3. Lauf, Laufprotokoll.
  4. Freeze (SHA-256 der Ausgaben und Transkripte in #1404).
  5. Das Skript gibt in einem ersten Schritt nur die Verweis-Treffer aus (Karte, Charge, Rater, Feld, Satz), ohne Werte. Jeder Treffer wird von Hand nach der Zähl-Regel von #1761 §9 eingestuft (zählt / zählt nicht a–c, Zweifelsfall zählt), die Liste wird in #1404 gepostet. Daraus folgt die Chargen-Gültigkeit.
  6. Erst dann folgen Auswertung und Bericht.
- **Chargen-Gültigkeit (analog A1–A11 aus #1761):**

| Nr | Auslöser | Folge |
|---|---|---|
| A1 | < 90 % gültige Karten in einer Charge eines Raters (gültig = Kartenzeile plus alle sechs Kriterienzeilen plus H-Zeile, Werte ganzzahlig 0–100, `oracle_id` passt) | Charge für diesen Rater einmal mit frischer Instanz ganz neu; danach fehlende Karten mit `n_rater` < 3 |
| A2 | Blindheitsverstoß: zählender Verweis-Treffer oder Werkzeugzugriff außerhalb des Rater-Ordners | Charge dieses Raters ungültig, Ausgabe verschieben und hashen, einmal neu; zweiter Verstoß: Charge bleibt ohne diesen Rater; Verstöße in zwei Chargen desselben Raters: Rater fällt aus, „kein Schluss“ für S1 |
| A3 | Laufprotokoll fehlt | keine Aussage über Stufen; Kennzeichnung „Stufen ungeprüft“ |
| A4 | Skalenstauchung: SD(H_v3) eines Raters in einer Charge < 0,6 × SD der beiden anderen auf denselben Karten, oder > 40 % gleiche Werte | **nur markieren** (`skalenstauchung`) und berichten. Die Charge bleibt aggregiert, und S1–S9 werden immer auf allen gültigen Zeilen gerechnet (kein ergebnisabhängiger Ausschluss) |
| A5 | > 5 % Formatfehler (Nicht-Vielfache von 5, fehlende Zeilen) | berichten; Rundung halb nach oben; fehlende Zeilen ungültig |
| A6 | Chargeneffekt: mittlere (Raterwert − Median) einer Charge weicht um > 4 vom Mittel der übrigen Chargen dieses Raters ab | markieren, aggregiert bleibt sie |
| A7 | Instanz bricht ab (Limit, Fehler) | Wiederaufnahme nach §4 (ganze Charge neu) |
| A8 | Schwellen, Mengen oder Formeln müssten nach dem Öffnen geändert werden | nicht ändern; Abweichung in §9, „explorativ“ |
| A9 | Tranchen- oder Versionseffekt im Vollauf: mittlere (Raterwert − Median) eines Raters in einer Tranche weicht um > 3 vom Mittel seiner übrigen Tranchen ab, oder die Modellversion eines Raters wechselt zwischen Tranchen | je Tranche bzw. Version getrennt berichten; keine Korrektur; bei einem Versionswechsel keine gemeinsame Aussage „ein Rater“ über die Tranchen hinweg |
| A10 | Auswerteskript nicht vor dem Öffnen committet oder Hashes nicht vor dem Öffnen gepostet | Ergebnisse nur „explorativ, nicht nach Plan“; kein Owner-Vorschlag |
| A11 | weniger als 5 von 6 Pilotchargen mit allen drei Ratern gültig (gültig nach A1/A2; A4 markiert nur und macht eine Charge **nicht** ungültig) | „kein Schluss“ zum Pilot; Wiederholung der fehlenden Chargen, keine Anpassungsrunde verbraucht |

- **Regelclaims:** Stichprobe von 60 Claims (20 je Rater, höchstens einer je Karte, `random.Random(20261131)`), blind zur Herkunft geprüft wie in #1761 §9. Grün ≤ 1 von 20 offensichtlich falsch je Rater, rot ≥ 3 von 20. Nur berichtet; rot bei einem Rater ⇒ Leave-one-rater-out als Sensitivität.
- **Sensitivität (nur berichtet, vorab festgelegt):** Leave-one-rater-out; gleiche Gewichte statt der gesetzten; Mittel statt Median; mit und ohne Adjudikation.

## §6 Anzeige

- H_v3 (die nach dem Vollauf gewählte Variante, §4; alle drei Varianten stehen als Spalten daneben) wird als **abgeleiteter Datensatz** geschrieben (vorgeschlagen: `data/card_understanding/card_understanding_h_v3.jsonl`, je Karte `H_v3`, Variante, Kriterien-Mediane, `n_rater`, Spannweite, Marken). Er ist ein **Vorschlag**.
- **Ersatz von H_pooled in Tierliste und Kartenfenster nur nach Owner-Go**, in einem eigenen PR.
- **Anzeige-Bedingung (vorab, eigene Regel):** Gegen H_pooled darf die vorgeschlagene Variante auf den **Vollauf-Karten** höchstens **0,10** Spearman bei der Quelldeck-Zahl verlieren (Punktwert; KI berichtet). Die Bedingung ist mit der Variantenwahl verzahnt (§4: erste Variante in der Reihenfolge V3b, V3a, V3c, die alle Muss-Kriterien des Vollaufs **und** diese Bedingung erfüllt). Im Pilot ist sie nur Frühwarnung.
- **Bezugszahlen auf alten Daten** (`anzeige_bedingung_alt`, Mittel von F1 und R2 unter der jeweiligen H-Definition gegen H_pooled):

  | Variante | 922 Karten | Bootstrap-Anteil unter −0,10 (922) | pilotförmig, Median | pilotförmig, Anteil ≥ −0,10 |
  |---|---|---|---|---|
  | V3b | **−0,092** | 21,9 % | −0,133 | 16,0 % |
  | V3a-Analogon | −0,016 | 0 % | −0,026 | 100 % |
  | V3c | −0,052 | 0 % | −0,076 | 81,5 % |

- **Begründung von 0,10 (nach den Daten):** Maßgeblich ist der Verlust auf allen Karten, weil die Bedingung im Vollauf geprüft wird; dort verliert die gesetzte Formel auf alten Daten 0,092. 0,10 lässt diesen bekannten Formelverlust zu, aber kaum mehr. V3b besteht die Bedingung mit Ratern auf dem alten Niveau nur knapp (bei 21,9 % der Bootstrap-Ziehungen läge sie darunter); dann greifen V3a oder V3c. Eine Schwelle von 0,12 würde V3b sicherer durchlassen, ließe aber zusätzliche Verluste durch schlechtere Bewertungen zu. Darum bleibt 0,10.
- **Dem Owner wird im Vorschlag offen genannt:** V3b verliert erwartungsgemäß etwa 0,09 Spearman gegen H_pooled. Ob das ein Beliebtheitsleck im freien H oder echte Information ist, ist nicht trennbar.
- **Skala nicht gleich:** H_v3 hat eine andere Lage und Streuung als das alte H. Auf alten Daten liegt die Formel mit den gesetzten Gewichten im Mittel bei 33,5 (F1) bzw. 33,9 (R2) mit einer gepoolten SD von 16,0; das alte H liegt bei 30,7 bzw. 26,0 mit SD 19,7 (`v3_baselines.json`, n = 922). Stufengrenzen, Bänder und Rundungen der Tierliste werden deshalb **nicht** übertragen; der Owner-Vorschlag nennt die Wirkung jeder Grenzwahl mit n/N.
- **Streuungs-Untergrenze ±8:** Sie ist an den Bericht #1758 (8,1) gebunden und wird **nur bewusst** geändert, mit eigenem Owner-Vorschlag auf Basis der v3-Streuung (Spannweite und SD/√2 aus Retest und Ratern).
- **Alte Daten bleiben:** `fullrun_ratings.jsonl`, `rr_output_*`, `rr2_output_*`, `card_understanding_h_pooled.jsonl` und alle v2-Dateien werden nie überschrieben.

## §7 Risiken und Grenzen

- **Kein Wahrheitsmaßstab:** S1 bis S9 messen Verlässlichkeit und Konsistenz, nicht Richtigkeit. H bleibt ein Modellurteil.
- **Rater verwandt:** A, B und C stammen aus einer Familie. Ihre Übereinstimmung kann geteilte Familienfehler enthalten, und die ICC überschätzt dann die Reproduzierbarkeit gegenüber Ratern anderer Familien. Es gibt keine Aussage „unabhängige Familien“.
- **Pilot klein:** 90 Nicht-Anker-Karten. Die KI sind breit (S7-Differenz etwa ±0,08, `v3_baselines.json`). Die Kartenauswahl ist bewusst schwer (40 von 90 aus \|d\| ≥ 15) und darum für S1/S2 eher streng. Vergleiche „alt gegen neu“ auf diesen Karten sind wegen der Regression zur Mitte verzerrt und gelten nur als Kontext; geprüft wird A/B/C untereinander.
- **Nutzung ≠ Qualität:** S7 ist nur Nicht-Unterlegenheit. Weil der Deck-Kontextabsatz Zahlen aus der Referenzliste nutzt, ist die Referenzdeck-AUC kein unabhängiger Maßstab mehr (nur beschreibend).
- **Überanpassung an alte Daten:** Konsens-Anker und Streitklassen-Beispiele stammen aus F1/R2/G1. Die Gewichte sind aus den alten OLS-Gewichten abgeleitet und gerundet; gleiche Gewichte laufen als vorab festgelegte Sensitivität mit. Ein Rest-Risiko bleibt, dass v3 das gemeinsame Urteil der alten Rater erbt.
- **Formel verliert externe Übereinstimmung:** Auf alten Daten korreliert die Formel schwächer mit der Nutzung als das freie H (0,068 bis 0,115 auf 922 Karten; im Trockenlauf gegen H_pooled −0,138). Davon gehen 0,03–0,04 auf den N-Abzug (V3c). Ob das ein Beliebtheitsleck im freien H oder echte Information ist, ist nicht trennbar. S7 vergleicht darum mit derselben H-Definition (§3); gegen H_pooled gilt die Anzeige-Bedingung (§6).
- **Messlatte streng, falsch negativer Pilot möglich:** Im Trockenlauf verfehlen die alten Rater S1 und S2 fast immer. Auch einwandfreie Rater mit wahrer ICC 0,90 verfehlen den Pilot in der Simulation zu 16 %, mit Raterversatz bis 26 % (0,93: 8–11 %). Die Anpassungsrunde ist keine unabhängige zweite Chance (§3). Ein „nicht erfüllt“ ist darum kein Beleg, dass v3 schlechter ist.
- **Beliebtheitsleck:** Ohne Web-Werkzeuge bleibt nur Modellwissen; das ist nicht ausschließbar. Der Stichwort-Scan ist nur ein Indiz.
- **Pfadsperre nicht technisch erzwungen:** Read kann jeden Pfad öffnen (UNBELEGT, dass eine Sperre greift). Abgedeckt wird das durch einen Ordner je (Rater, Charge) ohne fremde Dateien und durch die Prüfung des Harness-Transkripts (I4, S8).
- **Rückwärtsanpassung:** Rater, die die Formel sehen, könnten Kriterien an ein gewünschtes H anpassen (I2). Geprüft wird das mit S9 und den Kriterienverteilungen.
- **Formatwechsel:** Der Guide je Charge unterscheidet sich durch die entfernten Ankerzeilen (B: Formatdetails verschieben Werte). Gemessen wird das als Chargeneffekt (A6).
- **Kontingent:** Mit 5-Stunden-Limits kann ein Vollauf mehrere Tage dauern. Dauer und Verbrauch je Instanz werden im Pilot gemessen (I4) und bestimmen die Tranchenplanung. Modellversionen können sich dazwischen ändern (B: Versionsdrift). Die Version wird je Tranche protokolliert; bei einem Wechsel werden die Kennzahlen je Version getrennt berichtet.

## §8 Schritte und Zuständigkeit

| Nr | PR | Inhalt | Review-Klasse |
|---|---|---|---|
| 1 | **dieser PR** (`docs/rating-v3-plan-1404`) | Plan, drei Phase-Berichte, Analyse-Skripte A1/A2, `v3_baselines.py` mit `v3_baselines.json`, `phaseA_unfair_cards.json` | MATERIAL Klasse B (> 300 Zeilen); Fresh-Context-Review (evidence-reviewer) vor dem Merge; **vor jedem Lauf gemergt** |
| 2 | Generator v2 | `chulane_rubric_v3_20261123/` Skripte v2, `facts_v2`, `patterns_v2`, Glossar, Overrides, Manifest, Tests G1–G12 | Klasse B; Fresh-Context-Review |
| 3 | Guide v3 und Pilot-Eingaben | `GUIDE_v3.md` (N, Formel, Korridor, Deck-Kontext, Grundregeln, Streitklassen), Ankersatz v3 mit Auswahlskript, `output_schema_v3.json`, `v3_rater_instructions.md`, Pilot-Manifest und Eingaben, Tests | Klasse B; evidence-reviewer (Rater-Anweisung, Blindheit) |
| 4 | Auswertung v3 | `scripts/analysis/rating_v3_eval.py` plus Tests; **gemergt vor dem Öffnen** der Pilot-Ausgaben | Klasse B bei > 300 Zeilen; evidence-reviewer (Gate-Logik S1–S9) |
| 5 | Pilotbericht | Ausgaben, Klassifikation, Bericht `rating_v3_pilot_*.md`, Entscheidung nach §3 | Klasse B; evidence-reviewer |
| 5a | nur bei Bedarf: Plan-Nachtrag 1 | vor der Anpassungsrunde | evidence-reviewer |
| 6 | Vollauf | Eingaben (falls nicht in PR 3), Ausgaben, Bericht `rating_v3_full_*.md`, abgeleiteter Datensatz H_v3, Owner-Vorschlag | Klasse B; evidence-reviewer |
| 7 | Anzeige | Tierliste und Kartenfenster lesen H_v3, **nur nach Owner-Go** | Produkt-PR; Fresh-Context-Review; Studio-Guards |

**Owner-Fragen: beantwortet am 2026-11-23** ([#1404, Kommentar 7089197223](https://github.com/moeendres-png/commander-playtest-lab/issues/1404#issuecomment-7089197223), Niederschrift des Co-Leads aus dem Session-Chat). Die Antworten sind wörtlich zitiert; die Fragen bleiben zur Nachvollziehbarkeit stehen.
1. **Adjudikation (I6):** Gilt der Owner-Auftrag vom 2026-11-22 „setze den Plan gründlich und vollständig um“ als Go für eine dritte Bewertung bzw. Adjudikation bei Rater-Abstand ≥ 15, obwohl der Adjudikator die Stufe von Rater A hat? Empfehlung: ja; Befunde über Rater A gesondert ausweisen. **Antwort des Owners: „Ja, bestätigen (Empfehlung)“.** Damit gilt die Folge aus I6 (Bewertung mit belegtem objektivem Fehler fällt aus der Aggregation). Befunde mit Beteiligung von Rater A, also Befunde über Rater A und Karten, bei denen Rater A die abweichende Bewertung hat, werden weiter gesondert ausgewiesen.
2. **Rater-Stufen (AGENTS §7):** Dürfen die drei Rater aus drei verschiedenen Modellstufen stammen, statt Stufe und Aufwand des Leads zu erben? Nur der Owner darf das entscheiden; eine Co-Lead-Lesart reicht nicht. **Der Pilot startet erst nach der Antwort des Owners auf die Rater-Stufen** (erfüllt am 2026-11-23). Empfehlung: ja; nur so gibt es drei verschiedene Rater, weil echte Familien-Diversität nicht verfügbar ist. **Antwort des Owners: „Ja, drei Stufen (Empfehlung)“.** Stufe, Version und Aufwand werden vor dem Start im Laufprotokoll in #1404 festgehalten (I4).
3. **S7-Vergleich und Gewichte:** (a) Darf S7 mit den alten Läufen unter derselben H-Definition vergleichen, während der Vergleich gegen H_pooled nur in der Anzeige-Bedingung gilt (Verlust ≤ 0,10 auf den Vollauf-Karten; V3b verliert auf alten Daten etwa 0,09)? (b) Sind die aus den alten OLS-Gewichten abgeleiteten, gerundeten Gewichte 0,3/0,3/0,2/0,1/0,1 mit N-Abzug in Ordnung, statt gleicher Gewichte? Empfehlung: (a) ja, (b) ja. Gleiche Gewichte laufen als Sensitivität mit, V3c steht als dritte Variante bereit. **Antwort des Owners: „Ja, so festlegen (Empfehlung)“.** *Hinweis für den Owner zu Änderungen nach dieser Antwort (Review-Runde 3):* Vergleichsbasis von S7 und Gewichte bleiben wie bestätigt. Geändert hat sich die Rolle im Ablauf: S7 ist im Pilot nur Frühwarnung und Muss erst im Vollauf; S2 ist Soll (nur berichtet). Die Stellen: §3 (S2- und S7-Zeile, Entscheidungsregel, Gesamt-Fehlalarm) und §4 (Muss-Kriterien des Vollaufs).

Zuständig ist der Co-Lead als Planer und Adjudikator. Umsetzung, Läufe und Skripte übernimmt der vom Owner für die Sitzung gewählte Worker. Claim in #1404 vor jedem Schritt (AGENTS §11).

## §9 Abweichungsliste

(leer)

## §10 Herkunft und Reproduktion

```
# A1 (Eingaben außerhalb des Repos siehe README):
A1_USAGE=<usage_holdout.jsonl> A1_CORPUS=data/research/chulane_corpus A1_F1RAW=<F1-Chargenprompts> A1_OUT=<ordner> \
  bash data/research/chulane_rubric_v3_20261123/phaseA_scripts/A1/run_all.sh
# A2:
PYTHONPATH=src python3 data/research/chulane_rubric_v3_20261123/phaseA_scripts/A2/a2_inventory.py --repo . --mage <xmage-checkout> --out <ordner>
python3 data/research/chulane_rubric_v3_20261123/phaseA_scripts/A2/a2_uncertainty.py --repo . --out <ordner>
python3 data/research/chulane_rubric_v3_20261123/phaseA_scripts/A2/a2_summary.py --out <ordner>
# Vergleichswerte dieses Plans:
python3 data/research/chulane_rubric_v3_20261123/phaseA_scripts/v3_baselines.py --pairs <A1_OUT>/pairs.jsonl \
  --a2 <ordner> --usage <usage_holdout.jsonl> --out <ordner>/v3_baselines.json \
  --unfair-out data/research/chulane_rubric_v3_20261123/phaseA_unfair_cards.json
```

Auf `main` @ `f4d49ad6` nachgerechnet: Die A1-Ausgaben sind byte-gleich mit den SHA-256 in A1 §7, die A2-Ausgaben byte-gleich mit den Phase-A-Dateien (6 von 6). Die Ausgabe des letzten Befehls liegt als `data/research/chulane_rubric_v3_20261123/v3_baselines.json` im Repo (zweimal byte-gleich). Sie enthält nur Kennzahlen und Kartennamen, keine Nutzungswerte je Karte. Die Gewichtsprobe in I2 ist eine Offenlegung; die Gewichte selbst sind die gerundeten OLS-Gewichte von F1.
