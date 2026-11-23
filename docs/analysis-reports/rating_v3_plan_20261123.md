# Kartenverständnis H: Vorab-Plan „Bewertung v3“ (Chulane, 2026-11-22)

- **Stand:** Branch `docs/rating-v3-plan-1404`, gebaut auf `main` @ `f4d49ad6`. Refs #1404. Grundlage sind die Phase-Berichte im selben PR: [A1 Forensik](rating_v3_phaseA1_forensik_20261123.md), [A2 Kartenblock-Defekte](rating_v3_phaseA2_kartenblock_defekte_20261123.md), [B Recherche](rating_v3_phaseB_recherche_20261123.md), dazu die Zusammenfassung in #1404, Kommentar 7087797689.
- **Owner-Auftrag (2026-11-22, Wortlaut):** „Da die Bewertung der karten so weit auseinander geht, will ich dass du erst planst wie du am besten die karten bewertest und dir die vergangenen Bewertungen nochmal genau anschaust und schaust wo eventuell fehler oder Ungenauigkeiten sind, plane und recherchiere entsprechend erst wie du die karten am besten bewertest und setze den plan dann entsprechend gründlich und vollständig um“.
- **Was dieser PR tut:** Er legt den Plan fest, **bevor** es einen v3-Lauf gibt. Es gibt keinen Lauf, keine neuen Bewertungen und keine Änderung am Produkt. Schwellen, Mengen, Formeln und Regeln dieses Plans werden nach dem ersten Öffnen einer v3-Ausgabe nicht mehr geändert. Was später abweicht, steht nur in der Abweichungsliste (§9) und heißt „explorativ“.
- **Verbindliche Owner-Vorgaben:** (1) erst planen und prüfen, dann gründlich umsetzen; (2) **keine Paarvergleiche, kein Elo, kein Bradley-Terry**, auch nicht als „relative Kalibrierung“: Jede Bewertung ist ein absoluter Wert je Karte; (3) **keine Nutzungs-, Beliebtheits- oder Preisdaten als Eingabe**, nur als Maßstab der Validierung; (4) H bleibt ein **Modellurteil** („Kartenverständnis“), nie „Wahrheit“; (5) alte Daten werden nie überschrieben; (6) keine Modellnamen in Repo-Dateien: Die Rater heißen „Rater A/B/C“, Stufe und Version stehen im Laufprotokoll im Scratchpad; (7) Familien-Diversität ist nur eingeschränkt möglich (§2, I4); (8) Kontingent mit 5-Stunden-Limits: zuerst der Pilot, volle Läufe in Chargen mit Wiederaufnahme.
- **Bezeichnungen:** **Lauf 1 (F1)** ist der Vollauf vom 2026-11-18 (922 Karten). **Lauf 2 (R2)** ist die zweite Bewertung vom 2026-11-22 (Welle 1 mit 300 Karten, Welle 2 mit 622). **G1** ist der unabhängige Lauf über 70 Karten (`audit/independent_rater_ratings.jsonl`). d = H_R2 − H_F1, N = 922.
- **Herkunft der neuen Vergleichszahlen:** `data/research/chulane_rubric_v3_20261123/phaseA_scripts/v3_baselines.py`, Ausgabe `v3_baselines.json` im selben Ordner. Das Skript rechnet nur auf alten Daten (A1-Paare, G1, A2), mit Seed 20261123 (§10).

## Kurzfassung

1. **Ziel:** H soll zwischen unabhängigen Ratern **reproduzierbarer** werden. Gemessen wird das als Übereinstimmung, Versatz je Kartenart, Konsistenz von H mit den Kriterien, Treffen verdeckter Anker und fehlende Müdigkeit, bei externer Nicht-Unterlegenheit. „Richtiger“ ist nicht belegbar (§0).
2. **Hauptursachen (§1):** Der freie H-Schritt erklärt den Niveau-Versatz −4,67 bei gleichen Kriterien. Die Streuung je Karte kommt zu 77–79 % aus den Kriterien E, F und R. D trägt H nicht (Gewicht ≈ 0). F1 sah bei 36 von 46 Ankerkarten die eigene Ankerzeile. 464 von 922 Kartenblöcken haben einen Defekt, 60 davon sind kaum fair bewertbar.
3. **Eingriffe (§2):** I1 Generator v2 mit den A2-Korrekturen und einem festen Deck-Kontextabsatz. I2 Raster v3: **D entfällt** und wird durch **N „Nachteil/Risiko“** ersetzt, das nur abzieht. Zwei vorab definierte H-Varianten aus **derselben Antwort**: **V3a** (H frei, aber in einem Korridor ±10 um die Formel) und **V3b** (H = 0,3·E + 0,3·F + 0,2·R + 0,1·T + 0,1·K − 0,2·N, vom Skript berechnet). Mittelfeld-Anker 30/40/60/70 aus Konsens-Karten, alle Ankerkarten verdeckt. I3 Chargen mit höchstens 20 Karten, davon 4 verdeckte Ankerplätze, Reihenfolge je Rater mit festem Seed, **ein Wert je Antwortzeile**. I4 drei Rater A/B/C aus verschiedenen Modellstufen, frisch je Charge, ohne Web. I5 Median je Kriterium, keine stille Korrektur. I6 Fehlerprüfung bei Rater-Abstand ≥ 15.
4. **Pilot (§3):** 100 Karten (40 schwer, 30 Kontrolle, 10 Länder, 10 kaum fair bewertbar, 10 Anker verdeckt) in 6 Chargen zu 19 Karten, 3 Rater, also **18 Instanzen, ein Lauf**. V3a und V3b rechnet das Skript aus derselben Antwort.
5. **Erfolgskriterien:** S1 ICC(2,1) ≥ 0,87 mit unterer KI-Grenze ≥ 0,80 · S2 mittlere paarweise |Δ|/SD ≤ 0,35 · S3 Versatz je Kartenart ≤ 0,15 SD · S4 (nur V3a) Korridorbruch > 15 bei höchstens 5 % · S5 MAE der verdeckten Anker ≤ 5 · S6 Positionsdrift ≤ 1,5 je 10 Positionen (Soll) · S7 Spearman mit der Quelldeck-Nutzung höchstens 0,05 unter H_pooled, untere KI-Grenze ≥ −0,15 · S8 0 zählende Verweis-Treffer · S9 Korrelation zweier Kriterien < 0,90.
6. **Entscheidungsregel:** V3b erfüllt alle Muss-Kriterien ⇒ Vollauf mit V3b. Sonst, wenn V3a sie erfüllt, Vollauf mit V3a. Sonst gibt es höchstens **eine** Anpassungsrunde mit einem vorab committeten Plan-Nachtrag und neuer Pilotziehung. Danach folgt der Vollauf oder der Bericht „nicht erfüllt“.
7. **Vollauf (§4):** alle 922 Karten in etwa 54 Chargen × 3 Rater, also **etwa 162 Instanzen**, in Tranchen zu 18 Instanzen mit Freeze und Wiederaufnahme an Chargengrenzen. Retest sind die 90 Pilotkarten, die im Vollauf erneut bewertet werden.
8. **Anzeige (§6):** H_v3 ist nur ein Vorschlag. H_pooled wird nur nach einem Owner-Go ersetzt. Die Stufengrenzen und die Untergrenze ±8 werden **nicht** übertragen, weil die Skala eine andere Lage und Streuung hat.

## §0 Ziel und Messlatte

**Was „besser“ heißt.** Es ist vorab festgelegt und hängt nicht am Ergebnis. Es ist nicht zirkulär, weil keine der Messgrößen die Werte von v3 als Maßstab benutzt:

| Messgröße | Frage | Kriterium |
|---|---|---|
| Reproduzierbarkeit zwischen Ratern | Geben drei unabhängige Rater-Instanzen derselben Karte dasselbe H? | S1, S2 |
| Abweichung je Kartenart | Gibt es einen systematischen Versatz bei Kreaturen, Nicht-Kreatur-Spells oder Ländern? | S3 |
| Inkonsistenz H ↔ Kriterien | Folgt H den eigenen Teilkriterien? | S4 (V3a); in V3b gilt es per Konstruktion |
| Verankerung | Treffen die Rater verdeckt die Ankerwerte der Skala? | S5 |
| Müdigkeit und Position | Driftet die Bewertung innerhalb einer Charge? | S6 |
| Externe Nicht-Unterlegenheit | Wird der Zusammenhang mit der Nutzung (nur Maßstab) nicht deutlich schwächer als beim heutigen H_pooled? | S7 |
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
| Formel mit den gesetzten v3b-Gewichten (I2) und Abzug 0,2·(100 − D) | 16,0 | 0,868 [0,851; 0,884] | 6,36 | 0,399 | (nicht berechnet) | −0,073 / +0,127 / +0,142 |

Folge: Eine Formel **staucht** die Skala (SD 19,7 → etwa 14 bis 16) und senkt allein dadurch die Abstände in Punkten. Deshalb sind S1 und S2 **skalenfrei** (ICC, |Δ|/SD) und **über** der Formel-Bezugsgröße der alten Läufe gesetzt: S1 ≥ 0,87, S2 ≤ 0,35. Ein Raster v3 gilt nur dann als besser, wenn die neuen Rater untereinander besser übereinstimmen, als es die alten Rater unter derselben Formel taten.

## §1 Befunde aus Phase A/B in Kürze

**A1 Forensik** (Bericht A1, Skripte `phaseA_scripts/A1/`, zweimal byte-gleich):
- **Ankerwerte kopiert:** F1 bewertete 36 der 46 Ankerkarten mit ihrer eigenen Ankerzeile im Prompt und übernahm den Ankerwert in **64 von 76** Zeilen exakt (MAE 1,12). Ohne sichtbare Zeile waren es 16 von 46 (MAE 6,87); R2 sah nie die eigene Zeile (exakt 20 von 46 bzw. 23 von 76).
- **Das Niveau sitzt im freien H-Schritt:** Die Kriterien verschieben sich gegenläufig (T −4,70, F −2,77 gegen R +3,06, K +2,89, D +4,39; N = 922). Bei gleichen Kriterien setzt R2 H um **−4,67** tiefer (Lauf-Dummy, R² 0,911). Beobachtet ist ΔH −4,73.
- **Die Streuung kommt aus den Kriterien:** 77 bis 79 % der Varianz von d sind kriterienbedingt (r 0,85, Rest-SD 5,8 bei SD 11,0). Uneinigkeit gibt es vor allem in E, F und R.
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

**Deck- und Manabasis-Kontext als fester Absatz im Guide (nicht im Block):** Nur Zahlen aus `facts_manifest.deck_basis` der Referenzliste (`chulane-current@41f393530bb16ee9`): Kreaturen, häufigste Kreaturtypen mit Anzahl, Artefakte, Instants/Sorceries, Länder, Basics je Typ, {C}-Quellen, Zahl der Landfall- und Lebensgewinn-Karten. **Keine Kartennamen**, damit keine Referenzdeck-Zugehörigkeit durchsickert. Dazu kommt ein Kurzglossar der Grundregeln (Aura und Equipment bei Bounce, Zählmarken gehen beim Bounce verloren, Token-Kopie mit ETB, „put onto the battlefield“ ist kein Wirken, cloak/manifest wird nicht gewirkt).

Prüfbarkeit: Der Generator-PR enthält zu jeder Zeile G1–G12 einen Test auf den genannten Karten. Er zählt die A2-Prüfungen mit `phaseA_scripts/A2/a2_inventory.py` auf `facts_v2` neu (Ziel: 0 bei G1–G5, G7–G9) und legt alle SHA-256 im Manifest ab.

### I2 Raster v3

**D entfällt; neues Kriterium N „Nachteil/Risiko“ (Entscheidung).** Begründung: D misst als „low-cost-ness“ nur die Abwesenheit von Kosten. Eine Karte ohne Wirkung bekommt so ein hohes D und hebt das Kriterienmittel (A1 §3; B: Konstruktfehler). Würde man D nur umdeuten und den Buchstaben behalten, ließen sich alte und neue Werte verwechseln. Darum bekommt das Kriterium einen neuen Buchstaben und eine umgekehrte Richtung:
- **N, Nachteil und Risiko (0 bis 100, 0 = kein nennenswerter Nachteil):** Wrath-Exposition, Symmetrie, Selbstschaden und Lebenszahlung, Farbbelastung, Abhängigkeit von Kreaturen auf dem Feld, Game-Changer-Platz.
- **Regel:** N bewertet nur Kosten, die die Karte **mit sich bringt**. Dass eine Karte nichts tut, ist **kein** Vorteil: Eine Karte ohne Wirkung bekommt N nach ihren tatsächlichen Kosten (meist niedrig), und weil N nur **abzieht**, kann es ihr H nie heben.
- **Anker für N:** die bisherigen D-Anker, mechanisch umgerechnet zu N = 100 − D (Winds of Rath 100, Rites of Flourishing 75, Rampaging Baloths 50, Elvish Mystic 25, Arcane Signet 0; Land-Tabelle ebenso).

**Kriterien E, F, T, R, K** bleiben mit den v2-Definitionen. Dazu kommen Beispiele für die Streitklassen aus A1 §5: „Körper/Token ohne Ressourcengewinn“, Einmal-Blink, Antworten und Schutz (R bei drei Gegnern), Top-End mit Castability, Fixing ohne Ramp. Die Beispiele erklären nur die Kriterien, sie enthalten keine Zahlen für bestimmte Karten.

**Zwei vorab definierte H-Varianten aus derselben Antwort:**

| Variante | H | Regel |
|---|---|---|
| Formel (für beide) | H_ref = 0,3·E + 0,3·F + 0,2·R + 0,1·T + 0,1·K − 0,2·N, auf 0 bis 100 begrenzt, ungerundet | Gewichte vorab gesetzt, **nicht** aus Pilot oder alten Daten gefittet |
| **V3a** „H frei, aber gebunden“ | Der Rater gibt H (Vielfache von 5) und sieht dabei die Formel. H darf **höchstens 10** von H_ref seiner eigenen Kriterien abweichen | Rohwert H_raw wird gespeichert. Für die Aggregation klemmt das Skript H_raw auf H_ref ± 10. Jeder Bruch wird gezählt (S4) |
| **V3b** „H berechnet“ | H_v3b = H_ref, vom Skript aus E, F, T, R, K, N | Der Rater gibt kein H für V3b; das H-Feld der Antwort gehört nur zu V3a |

**Begründung der Gewichte (a priori):** Die H-Frage lautet „wie viel besser wird das Deck?“. Preis und Wirkung (E) und Deckplan (F) sind ihr Kern; R (nützlich, wenn gezogen) folgt. T und K sind Zusatzdimensionen, die für ganze Kartenklassen strukturell niedrig sind: Laut Guide ist T für Länder „almost always 0“, K für Einmaleffekte höchstens 25. Mit je 1/5 Gewicht würden sie Länder auf höchstens etwa 80 deckeln und die Skala stauchen. N zieht höchstens 20 Punkte ab (B: „Abzug 0 bis −20“). Eine Karte, die dem Deck von selbst schadet (N 100, wie Winds of Rath), verliert damit eine volle Bandbreite. **Gegenprobe auf alten Daten, nicht als Grundlage der Wahl:** Mit gleichen Gewichten gegen diese Gewichte ändert sich die ICC F1–R2 nicht (0,868 gegen 0,868), die Spearman-Korrelation von R2 mit der Quelldeck-Zahl kaum (0,558 gegen 0,575; `v3_baselines.json`, n = 922). Die Wahl ist also kein Fit auf einen Gewinn. Gleiche Gewichte (0,2 je E, F, T, R, K, minus 0,2·N) werden im Pilotbericht als **Sensitivitätsanalyse** mitgerechnet, entscheiden aber nichts.

**Ein Lauf, zwei Varianten (Kostenentscheidung):** Beide Varianten lassen sich aus derselben Antwort ableiten (E, F, T, R, K, N und H_raw). Zwei getrennte Läufe (100 Karten × 3 Rater × 2 = 600 Bewertungen) würden nur messen, ob das Wissen um die Formel die Kriterien verändert. Das ist hier keine Entscheidungsfrage. Der Pilot hat deshalb **300 Bewertungen** (plus 72 verdeckte Ankerplätze, §3). Grenze: Weil der Rater die Formel sieht, könnte er in V3b seine Kriterien rückwärts an ein gewünschtes H anpassen. Das prüft S9 (keine Doppelmessung) zusammen mit dem Vergleich der Kriterienverteilungen mit F1/R2 (beschreibend).

**H-Ankertabelle entfällt.** Die alten H-Anker (v1-Bänder, z. B. Counterspell 67) liegen auf der alten H-Skala, die 5 bis 10 Punkte unter dem Kriterienmittel liegt (F1 −5,47, R2 −9,85; `v3_baselines.json`, H_gegen_kriterien). Sie widersprächen dem Korridor von V3a. Anker gibt es in v3 **nur je Kriterium**. Die alten H-Bänder (95–100 … 0–4) beschreiben die alte Skala und werden nicht übertragen (§6).

**Mehr Anker für 30/40/50/60/70 aus Konsens-Karten (Auswahlverfahren, vorab):**
1. Je Kriterium c ∈ {E, F, T, R, K} und Stufe L ∈ {30, 40, 60, 70}; L = 50 nur, wenn die v2-Tabelle für c keinen 50er-Anker hat (heute haben alle einen).
2. Grundmenge: Spells, die keine bisherige Ankerkarte sind.
3. **Stufe 1:** Karten mit G1-Bewertung, bei denen F1, R2 und G1 auf c höchstens 5 auseinanderliegen und der Median genau L ist.
4. **Stufe 2**, nur für Zellen, die nach Stufe 1 leer sind: Karten mit F1_c = R2_c = L.
5. Aus den Kandidaten einer Zelle wird **eine** Karte gezogen, mit `random.Random(20261128)` über die nach Name sortierte Liste. Bevorzugt werden Karten, die noch für keine andere Zelle gewählt sind. Reihenfolge der Zellen: c in E, F, T, R, K, dann L aufsteigend.
6. Leere Zelle nach Stufe 2: Sie bleibt leer, das wird im Guide vermerkt, und es wird nichts erfunden. Kandidatenzahlen aus `v3_baselines.json`: Stufe 1 leer bei F60, T40, T60, T70, K60, K70; Stufe 2 füllt davon T40 (10), T60 (1), K60 (2) und F60 (5). T70 und K70 bleiben voraussichtlich leer.
7. Der Ankerwert ist L. Die Beschreibung in der Tabelle ist eine kurze Funktionsbeschreibung aus dem Kartentext (wie in v2), ohne Beliebtheitsangaben.
8. N-Mittelstufen 30/40/60/70: dasselbe Verfahren auf N = 100 − D, aber nur über Karten mit H_pooled ≥ 28 (Karten, die etwas tun). Grenze: Das alte D enthielt die Nichtwirkungs-Verzerrung; N-Mittelanker sind deshalb als „aus altem D umgerechnet“ markiert.
9. **Grenze:** Konsens-Anker übernehmen das gemeinsame Urteil der alten Rater (mögliche gemeinsame Verzerrung, §7).
10. **Reihenfolge:** Zuerst wird der Ankersatz im Guide-v3-PR festgelegt, **danach** das Pilot-Manifest, das alle Ankerkarten aus den Nicht-Anker-Schichten ausschließt.

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
- **Frisch je Charge:** eine Charge je neuer Instanz ohne Vorkontext, ein Satz Startanweisung („Du bist Rater X, Charge k. Lies `<Rater-Ordner>/v3_rater_instructions.md` und folge ihr.“).
- **Ohne Web:** Werkzeuge technisch beschränkt auf Lesen im Rater-Ordner und Schreiben der eigenen Ausgabedatei. Kein Web-Abruf, keine Websuche, keine Shell. Die Blindheit ist technisch erzwungen, nicht per Selbstauskunft (A1 §6.1).
- **Werkzeug- und Pfadprotokoll:** Jede Instanz protokolliert jeden Werkzeugaufruf mit Pfad. Ein Zugriff außerhalb des Rater-Ordners macht die Charge ungültig (A2-Regel, §5).
- **Laufprotokoll VOR dem Start (Scratchpad, Pflicht):** je Rater Familie, Stufe, Modell-Version, Aufwand und Temperatur (oder „Voreinstellung, nicht setzbar“), Werkzeugliste, Rater-Ordner, Seeds. Das Repo bekommt nur eine Fassung ohne Modellnamen: „Rater A/B/C = Stufe groß/mittel/klein; gleiche Familie“. Fehlt das Protokoll, gilt A3: keine Aussagen über Stufen.

### I5 Aggregation (vorab)

- Je Karte und Kriterium der **Median über A, B und C** (bei drei Werten gleich dem getrimmten Mittel), ungerundet.
- **V3b:** H_v3b = H_ref aus den Kriterien-Medianen. **V3a:** H_v3a = Median der drei geklemmten H-Werte.
- Fehlt ein Rater für eine Karte (ungültig nach §5), gilt das Mittel der zwei übrigen mit Marke `n_rater = 2`. Bei nur einem gültigen Rater geht die Karte nicht in H_v3 ein (Marke `n_rater = 1`).
- **Keine Versatz-Korrektur**, außer der Pilot zeigt auf den verdeckten Ankern einen Versatz je Kartenart (Kreatur, Nicht-Kreatur-Spell, Land) von mehr als 2 Punkten mit einem 95-%-KI ohne 0. Gemessen wird der Versatz als Median-Aggregat minus Ankerwert, gemittelt über die Kriterien mit Ankerzeile. Nur dann wird eine **additive Ankerkorrektur je Kartenart** aus den Vollauf-Ankern berechnet und **nur vorgeschlagen**: beide Fassungen im Bericht, Anwendung nur nach Owner-Go. Keine Quantil-Normalisierung.
- Die Unsicherheit je Karte wird mitgeführt: Spannweite max − min über A/B/C auf H_v3 und je Kriterium.

### I6 Adjudikation

- **Auslöser:** Rater-Abstand (max − min über A/B/C) auf H_v3 der gewählten Variante **≥ 15** ⇒ Marke `abstand_ge15`. Die Karte wird nie gelöscht.
- **Dritter Blick (Fehlerprüfung, keine vierte Meinung):** Eine frische Instanz der größten Stufe sieht den Kartenblock, den Guide v3 und die drei Bewertungen mit Begründungen, ohne Rater-Kennung. Sie prüft je Bewertung nur, ob ein **objektiver Fehler** vorliegt: Kartentext falsch gelesen, Regelfehler gegen Text, Ruling oder Comprehensive Rules, Kriterium falsch angewendet nach Guide-Wortlaut. Jede Feststellung braucht ein wörtliches Zitat.
- **Folge:** Eine Bewertung mit belegtem objektivem Fehler fällt für diese Karte aus der Aggregation; H_v3 ist dann das Mittel der zwei übrigen (Marke `adjudiziert`). Ohne Fehlerbefund bleibt der Median. Einen Geschmacksunterschied entscheidet die Adjudikation nicht.
- Gemeldet werden die Zahl der Karten, der Befunde und der verworfenen Bewertungen je Rater. Die Adjudikation sieht die anderen Ratings, darum ist sie keine unabhängige Messung und zählt in S1 bis S9 nicht (S-Kriterien werden **vor** der Adjudikation gerechnet).
- **Owner-Go (ausdrücklich):** Eine dritte Bewertung oder Adjudikation größerer Abweichungen braucht ein Owner-Go (so der Plan von #1761, §8). Den Owner-Auftrag vom 2026-11-22 „setze den Plan gründlich und vollständig um“ liest der Co-Lead als Go für die Adjudikation **im Rahmen dieses Plans** (Co-Lead-Lesart, bei der Abnahme zu bestätigen).

## §3 Pilot

**Menge: 100 Karten.** Die 90 Nicht-Anker-Karten werden ohne Überschneidung in dieser Reihenfolge gezogen; davor ist der Ankersatz v3 festgelegt (I2), und alle Ankerkarten sind ausgeschlossen. Seed `random.Random(20261127)`. Gezogen wird innerhalb jeder Quote aus der nach `oracle_id` sortierten Liste.

| Schicht | n | Grundmenge (Größe aus `v3_baselines.json`, vor Abzug neuer Anker) | Quoten innerhalb der Schicht |
|---|---|---|---|
| kaum fair bewertbar | 10 | 59 Nicht-Anker-Karten aus `phaseA_unfair_cards.json` | je eine Karte aus jeder vorkommenden Defektklasse (Mechanik, Land-Fakten, Seiten/Spezialtypen/Verweise, Hybrid-Castability), Rest zufällig |
| schwer | 40 | 254 Nicht-Anker-Karten mit \|d\| ≥ 15 | 8 mit Rolle Token, Counter oder Tapper; 8 Kreaturen mit MV ≥ 6; 16 übrige Kreaturen; 8 Nicht-Kreatur-Spells. Zuordnung in dieser Reihenfolge. Ist eine Teilmenge zu klein, wird aus der allgemeinen Schicht aufgefüllt. Die Bandzusammensetzung (Mittelband 28–49) wird berichtet |
| Kontrolle | 30 | 150 Nicht-Land-Nicht-Anker-Karten mit \|d\| < 5 | 15 Kreaturen, 15 Nicht-Kreatur-Spells |
| Länder | 10 | 52 Nicht-Anker-Länder (ohne die schon gezogenen) | zufällig |
| Anker verdeckt | 10 | Ankersatz v3 | 5 alte Anker (3 Spells, 2 Länder), 5 neue Konsens-Anker; `random.Random(20261128)` |

**Chargen:** 6 Chargen zu je 15 Nicht-Anker-Karten plus 4 Ankerplätze, also 19 Karten. Die 24 Ankerplätze füllen die 10 Ankerkarten: jede mindestens zweimal, keine zweimal in derselben Charge. Die erste Platzierung zählt als Bewertung, Wiederholungen dienen als Anker-Retest. Dieselben 6 Chargen gehen an A, B und C (je Rater eigene Reihenfolge). Das ergibt **18 Instanzen**, 300 Bewertungen der 100 Karten und 72 Ankerplätze. Das Manifest `v3_pilot_manifest.json` enthält Seeds, Quell-SHA-256 (Fakten v2, Guide v3 je Charge, Schema, Anweisung), Schichten und die Zuordnung zu den Chargen. Es wird im Guide-v3-PR mit einem Skript erzeugt, zweimal byte-gleich.

**Erfolgskriterien (vorab; S-Kriterien werden für V3a und V3b getrennt gerechnet, auf den 90 Nicht-Anker-Karten, vor der Adjudikation; Intervalle: Bootstrap über Karten, 2000 Ziehungen, `random.Random(20261127)`, 95 % Perzentil):**

| Nr | Muss/Soll | Kriterium | Schwelle | Alte Vergleichswerte (Herkunft, n/N) |
|---|---|---|---|---|
| S1 | Muss | ICC(2,1) zwischen A, B, C auf H_v3 (absolute Übereinstimmung, Einzelrater) | Punkt ≥ **0,87** und untere KI-Grenze ≥ **0,80** | F1–R2 freies H 0,818 [0,793; 0,839]; F1–R2 unter der Formel 0,868 [0,851; 0,884] (922/922, `v3_baselines.json`) |
| S2 | Muss | mittlere paarweise \|Δ\| über die drei Raterpaare, geteilt durch die gepoolte SD aller 3 × 90 Werte | ≤ **0,35** (Punkte zusätzlich berichtet) | freies H 0,465 (9,16 Punkte); Formel 0,396 (5,85 Punkte) (922/922); Welle 1 ohne markierte 8,38 Punkte (265, #1758) |
| S3 | Muss (Schutz) | Versatz je Raterpaar und Kartenart: \|mittlere Δ\| / SD gepoolt, für Kreaturen und Nicht-Kreatur-Spells | ≤ **0,15** je Paar und Art (bei SD 16 etwa 2,4 Punkte); Länder nur berichtet (etwa 12 Karten) | freies H Kreatur −0,382 / Nicht-Kreatur −0,127; Formel −0,063 / +0,139 (922/922). Schutz gegen einen neuen Versatz, kein Verbesserungsbeleg |
| S4 | Muss für V3a | Anteil der Karten mit \|H_raw − H_ref\| > 15, je Rater | ≤ **5 %**; > 10 (Korridorbruch) berichtet | Bezug H gegen M5 (ungewichtet, ohne D): F1 64/922 (6,9 %), R2 254/922 (27,5 %); > 10: F1 297/922, R2 572/922. Alte Guide-Lücke (mit D) > 15: F1 284/922, R2 W1 132/300, W2 457/622 (A1 §3) |
| S5 | Muss | verdeckte Anker: MAE des Median-Aggregats gegen den Ankerwert über alle (Ankerplatz × Kriterium mit Ankerzeile) | ≤ **5**; je Rater berichtet | „v1 fixed“ ohne eigene Zeile: F1 6,87, R2 5,24 (46 Zeilen); übrige Anker R2 8,68 (76 Zeilen) (A1 §2.6, Einzelrater) |
| S6 | Soll | Positionsdrift je Rater: OLS-Steigung von (Raterwert − Median der drei) auf die Position 1–19, über alle Chargen, × 10 | \|·\| ≤ **1,5** je Rater | R2 Charge 6: ρ(Position, d) −0,35 (88 Positionen, A1 §2.4) |
| S7 | Muss | Spearman(H_v3, Quelldeck-Zahl) − Spearman(H_pooled, Quelldeck-Zahl) auf denselben 90 Karten, gepaarter Bootstrap | Punkt ≥ **−0,05** und untere KI-Grenze ≥ **−0,15** | Auf allen 922 Karten: R2 freies H 0,673 gegen R2 unter der gesetzten Formel 0,575 (gleiche Gewichte 0,558); F1 0,504 gegen 0,436 (0,434). KI-Breite der gepaarten Differenz auf 100 Zufallskarten ≈ 0,16 (`v3_baselines.json`, s7_breite). Eine Formel verliert hier auf alten Daten etwa 0,07 bis 0,12; S7 ist für V3b ein echtes Risiko |
| S8 | Muss | Blindheit: zählende Verweis-Treffer nach der Zähl-Regel von #1761 §9; kein Werkzeugzugriff außerhalb des Rater-Ordners laut Protokoll | **0** nach Wiederholungen (§5, A2) | Welle 2: 0 zählende Treffer (#1765-Bericht) |
| S9 | Muss (Schutz) | höchste \|r\| zweier Kriterien (E, F, T, R, K, N) über die Median-Aggregate; je Rater berichtet | < **0,90** | F1 0,673 (F–K), R2 0,752 (E–R) (922/922). Schutz gegen Doppelmessung (B: Faktorkollaps) |

Die Messgröße für S7 ist `deck_list_count` aus `usage_holdout.jsonl`, also Quelldecks über alle Brackets. Die Datei liegt nicht im Repo, ihr SHA-256 `c3d1f693…` steht in A1. Die Rater sehen sie nie. Die Referenzdeck-AUC ist nur beschreibend, weil der Deck-Kontextabsatz aus der Referenzliste stammt (§7).

**Entscheidungsregel (vorab):**
1. **V3b** erfüllt alle Muss-Kriterien (S1, S2, S3, S5, S7, S8, S9) ⇒ Vollauf mit V3b.
2. Sonst: **V3a** erfüllt alle Muss-Kriterien einschließlich S4 ⇒ Vollauf mit V3a.
3. Sonst: höchstens **eine Anpassungsrunde**. Zuerst kommt ein Plan-Nachtrag (Datei `rating_v3_plan_nachtrag1_*.md`) ins Repo, **bevor** neu bewertet wird. Er nennt die Änderung (z. B. Chargengröße 10 bei verfehltem S6, Guide-Präzisierung bei S5) und begründet sie aus dem Pilotbericht. Dann folgt ein neuer Pilot auf einer **frischen Ziehung** derselben Schichten (Seed 20261129, ohne die Karten des ersten Pilots; Ankerkarten dürfen wiederkommen). Bestehen ⇒ Vollauf; sonst Bericht „nicht erfüllt“ und kein Vollauf ohne neuen Owner-Entscheid.
4. S6 (Soll) verfehlt bei sonst erfüllten Muss-Kriterien ⇒ Vollauf mit Chargengröße 10, ohne Anpassungsrunde (vorab so festgelegt), im Bericht vermerkt.

## §4 Vollauf

- **Menge:** alle 922 Karten mit Generator v2, Guide v3 und Schema v3 byte-gleich wie im bestandenen Pilot (SHA-256 im Manifest). Die Pilotbewertungen gehen **nicht** in H_v3 ein; alle 922 werden neu bewertet.
- **Chargen:** höchstens 20 Karten (16 Nicht-Anker plus 4 Ankerplätze; bei S6-Fall 10 Karten mit 2 Ankerplätzen). Zahl der Chargen = ⌈(922 − A)/16⌉ mit A = Zahl der Ankerkarten v3 (46 alte plus höchstens 25 neue); bei A ≈ 70 sind das **54 Chargen**. Jede Ankerkarte steht mindestens einmal verdeckt, die erste Platzierung zählt. Seed `random.Random(20261130)`.
- **Aufwand:** 54 Chargen × 3 Rater = **etwa 162 Instanzen**, dazu die Adjudikation (Karten mit Abstand ≥ 15 in Gruppen zu höchstens 10 je Instanz; erwartet sind etwa 5 bis 10 % der Karten, also etwa 5 bis 10 Instanzen). Der Pilot hat 18 Instanzen.
- **Reihenfolge und Wiederaufnahme:**
  - Tranchen zu 6 Chargen × 3 Rater = 18 Instanzen, innerhalb einer Tranche reihum A, B, C je Charge. Bei einem Limit-Halt sind so alle Rater gleich weit.
  - Eine Charge ist fertig, wenn ihre Ausgabedatei vollständig und gültig ist (mechanischer Validator, der nur Zählungen ausgibt).
  - Halt mitten in einer Charge: Die Teil-Ausgabe wird mit SHA-256 in den Analystenordner verschoben und die Charge mit frischer Instanz **ganz** neu gestartet. Es gibt keine Fortsetzung mitten in der Charge und keine Auswahl einzelner Karten.
  - Ein Fortschrittsprotokoll im Scratchpad hält je Charge und Rater den Status fest (offen / läuft / fertig / verworfen).
- **Freeze je Tranche:** Nach jeder Tranche werden die SHA-256 aller neuen Ausgaben in #1404 gepostet, **bevor** ein Wert gelesen wird.
- **Retest-Teilmenge:** Die 90 Nicht-Anker-Pilotkarten werden im Vollauf erneut bewertet. Das ist Test-Retest je Rater mit unverändertem Guide und Generator, nur beschreibend: ICC und SD/√2. Ändert eine Anpassungsrunde Guide oder Generator, dienen die Karten des zweiten Pilots als Retest. Die wiederholten Ankerplätze geben einen zweiten, kleinen Retest.
- **Bestätigung im Vollauf:** S1 bis S9 werden auf allen Nicht-Anker-Karten erneut berechnet. Untere KI-Grenze von S1 < 0,80 im Vollauf ⇒ „im Vollauf nicht bestätigt“ und kein Owner-Vorschlag zur Anzeige.

## §5 Auswertungskette

- **Wiederverwendung:** Die Kette aus #1761/#1763 bleibt: Freeze → Verweis-Treffer → Klassifikation → Auswertung. Aus `scripts/analysis/rating_second_run_full_eval.py` werden übernommen: `freeze_guard`, `parse_checksums`, `find_hits`/`rater_fields`/`render_hits`, `check_classification`, `icc_set`/`anova2`, `bootstrap_multi`, `fatigue`, `run_log_view`. Neu ist `scripts/analysis/rating_v3_eval.py`: Zusammensetzen der Ein-Wert-Zeilen, I5, I6, ICC(2,1) für drei Rater, S1 bis S9, Entscheidungsregel. Dazu kommen synthetische Tests.
- **Reihenfolge (Pflicht):**
  1. Generator-v2-PR und Guide-v3-PR mit Manifest stehen im Repo; erst dann bekommt der Co-Lead die Pfade.
  2. Das **Auswerteskript wird als eigener PR committet, bevor eine v3-Ausgabe geöffnet wird.** Verpflichtende Rot/Grün-Tests: Ein Mutant mit S1-Schwelle 0,80 statt 0,87 ändert das Urteil auf synthetischen Daten; die V3a-Klemme; Median vor Formel (nicht umgekehrt); `n_rater = 2` und `1`; Entscheidungsregel mit allen drei Ausgängen; S-Kriterien vor der Adjudikation.
  3. Lauf, Laufprotokoll.
  4. Freeze (SHA-256 in #1404).
  5. Das Skript gibt in einem ersten Schritt nur die Verweis-Treffer aus (Karte, Charge, Rater, Feld, Satz), ohne Werte. Jeder Treffer wird von Hand nach der Zähl-Regel von #1761 §9 eingestuft (zählt / zählt nicht a–c, Zweifelsfall zählt), die Liste wird in #1404 gepostet. Daraus folgt die Chargen-Gültigkeit.
  6. Erst dann folgen Auswertung und Bericht.
- **Chargen-Gültigkeit (analog A1–A11 aus #1761):**

| Nr | Auslöser | Folge |
|---|---|---|
| A1 | < 90 % gültige Karten in einer Charge eines Raters (gültig = Kartenzeile plus alle sechs Kriterienzeilen plus H-Zeile, Werte ganzzahlig 0–100, `oracle_id` passt) | Charge für diesen Rater einmal mit frischer Instanz ganz neu; danach fehlende Karten mit `n_rater` < 3 |
| A2 | Blindheitsverstoß: zählender Verweis-Treffer oder Werkzeugzugriff außerhalb des Rater-Ordners | Charge dieses Raters ungültig, Ausgabe verschieben und hashen, einmal neu; zweiter Verstoß: Charge bleibt ohne diesen Rater; Verstöße in zwei Chargen desselben Raters: Rater fällt aus, „kein Schluss“ für S1 |
| A3 | Laufprotokoll fehlt | keine Aussage über Stufen; Kennzeichnung „Stufen ungeprüft“ |
| A4 | Skalenstauchung: SD(H_v3) eines Raters in einer Charge < 0,6 × SD der beiden anderen auf denselben Karten, oder > 40 % gleiche Werte | Charge dieses Raters nicht aggregiert, berichtet |
| A5 | > 5 % Formatfehler (Nicht-Vielfache von 5, fehlende Zeilen) | berichten; Rundung halb nach oben; fehlende Zeilen ungültig |
| A6 | Chargeneffekt: mittlere (Raterwert − Median) einer Charge weicht um > 4 vom Mittel der übrigen Chargen dieses Raters ab | markieren, aggregiert bleibt sie |
| A7 | Instanz bricht ab (Limit, Fehler) | Wiederaufnahme nach §4 (ganze Charge neu) |
| A8 | Schwellen, Mengen oder Formeln müssten nach dem Öffnen geändert werden | nicht ändern; Abweichung in §9, „explorativ“ |
| A10 | Auswerteskript nicht vor dem Öffnen committet oder Hashes nicht vor dem Öffnen gepostet | Ergebnisse nur „explorativ, nicht nach Plan“; kein Owner-Vorschlag |
| A11 | weniger als 5 von 6 Pilotchargen mit allen drei Ratern gültig | „kein Schluss“ zum Pilot; Wiederholung der fehlenden Chargen, keine Anpassungsrunde verbraucht |

- **Regelclaims:** Stichprobe von 60 Claims (20 je Rater, höchstens einer je Karte, `random.Random(20261131)`), blind zur Herkunft geprüft wie in #1761 §9. Grün ≤ 1 von 20 offensichtlich falsch je Rater, rot ≥ 3 von 20. Nur berichtet; rot bei einem Rater ⇒ Leave-one-rater-out als Sensitivität.
- **Sensitivität (nur berichtet):** Leave-one-rater-out; gleiche Gewichte statt der gesetzten; Mittel statt Median; mit und ohne Adjudikation.

## §6 Anzeige

- H_v3 (gewählte Variante) wird als **abgeleiteter Datensatz** geschrieben (vorgeschlagen: `data/card_understanding/card_understanding_h_v3.jsonl`, je Karte `H_v3`, Variante, Kriterien-Mediane, `n_rater`, Spannweite, Marken). Er ist ein **Vorschlag**.
- **Ersatz von H_pooled in Tierliste und Kartenfenster nur nach Owner-Go**, in einem eigenen PR.
- **Skala nicht gleich:** H_v3 hat eine andere Lage und Streuung als das alte H. Auf alten Daten liegt die Formel mit den gesetzten Gewichten im Mittel bei 33,5 (F1) bzw. 33,9 (R2) mit einer gepoolten SD von 16,0; das alte H liegt bei 30,7 bzw. 26,0 mit SD 19,7 (`v3_baselines.json`, n = 922). Stufengrenzen, Bänder und Rundungen der Tierliste werden deshalb **nicht** übertragen; der Owner-Vorschlag nennt die Wirkung jeder Grenzwahl mit n/N.
- **Streuungs-Untergrenze ±8:** Sie ist an den Bericht #1758 (8,1) gebunden und wird **nur bewusst** geändert, mit eigenem Owner-Vorschlag auf Basis der v3-Streuung (Spannweite und SD/√2 aus Retest und Ratern).
- **Alte Daten bleiben:** `fullrun_ratings.jsonl`, `rr_output_*`, `rr2_output_*`, `card_understanding_h_pooled.jsonl` und alle v2-Dateien werden nie überschrieben.

## §7 Risiken und Grenzen

- **Kein Wahrheitsmaßstab:** S1 bis S9 messen Verlässlichkeit und Konsistenz, nicht Richtigkeit. H bleibt ein Modellurteil.
- **Rater verwandt:** A, B und C stammen aus einer Familie. Ihre Übereinstimmung kann geteilte Familienfehler enthalten, und die ICC überschätzt dann die Reproduzierbarkeit gegenüber Ratern anderer Familien. Es gibt keine Aussage „unabhängige Familien“.
- **Pilot klein:** 90 Nicht-Anker-Karten. Die KI sind breit (S7-Differenz etwa ±0,08, `v3_baselines.json`). Die Kartenauswahl ist bewusst schwer (40 von 90 aus \|d\| ≥ 15) und darum für S1/S2 eher streng. Vergleiche „alt gegen neu“ auf diesen Karten sind wegen der Regression zur Mitte verzerrt und gelten nur als Kontext; geprüft wird A/B/C untereinander.
- **Nutzung ≠ Qualität:** S7 ist nur Nicht-Unterlegenheit. Weil der Deck-Kontextabsatz Zahlen aus der Referenzliste nutzt, ist die Referenzdeck-AUC kein unabhängiger Maßstab mehr (nur beschreibend).
- **Überanpassung an alte Daten:** Konsens-Anker und Streitklassen-Beispiele stammen aus F1/R2/G1. Die Gewichte sind a priori gesetzt; alte Daten dienen nur als Gegenprobe. Ein Rest-Risiko bleibt, dass v3 das gemeinsame Urteil der alten Rater erbt.
- **Formel verliert externe Übereinstimmung:** Auf alten Daten korreliert die Formel schwächer mit der Nutzung als das freie H (−0,07 bis −0,12). Ob das ein Beliebtheitsleck im freien H oder echte Information ist, ist nicht trennbar. S7 entscheidet vorab, und V3a ist die Rückfallvariante.
- **Beliebtheitsleck:** Ohne Web-Werkzeuge bleibt nur Modellwissen; das ist nicht ausschließbar. Der Stichwort-Scan ist nur ein Indiz.
- **Rückwärtsanpassung:** Rater, die die Formel sehen, könnten Kriterien an ein gewünschtes H anpassen (I2). Geprüft wird das mit S9 und den Kriterienverteilungen.
- **Formatwechsel:** Der Guide je Charge unterscheidet sich durch die entfernten Ankerzeilen (B: Formatdetails verschieben Werte). Gemessen wird das als Chargeneffekt (A6).
- **Kontingent:** Mit 5-Stunden-Limits kann ein Vollauf mehrere Tage dauern. Modellversionen können sich dazwischen ändern (B: Versionsdrift). Die Version wird je Tranche protokolliert; bei einem Wechsel werden die Kennzahlen je Version getrennt berichtet.

## §8 Schritte und Zuständigkeit

| Nr | PR | Inhalt | Review-Klasse |
|---|---|---|---|
| 1 | **dieser PR** (`docs/rating-v3-plan-1404`) | Plan, drei Phase-Berichte, Analyse-Skripte A1/A2, `v3_baselines.py`, `phaseA_unfair_cards.json` | MATERIAL Klasse B (> 300 Zeilen); Fresh-Context-Review (evidence-reviewer) vor dem Merge; **vor jedem Lauf gemergt** |
| 2 | Generator v2 | `chulane_rubric_v3_20261123/` Skripte v2, `facts_v2`, `patterns_v2`, Glossar, Overrides, Manifest, Tests G1–G12 | Klasse B; Fresh-Context-Review |
| 3 | Guide v3 und Pilot-Eingaben | `GUIDE_v3.md` (N, Formel, Korridor, Deck-Kontext, Grundregeln, Streitklassen), Ankersatz v3 mit Auswahlskript, `output_schema_v3.json`, `v3_rater_instructions.md`, Pilot-Manifest und Eingaben, Tests | Klasse B; evidence-reviewer (Rater-Anweisung, Blindheit) |
| 4 | Auswertung v3 | `scripts/analysis/rating_v3_eval.py` plus Tests; **gemergt vor dem Öffnen** der Pilot-Ausgaben | Klasse B bei > 300 Zeilen; evidence-reviewer (Gate-Logik S1–S9) |
| 5 | Pilotbericht | Ausgaben, Klassifikation, Bericht `rating_v3_pilot_*.md`, Entscheidung nach §3 | Klasse B; evidence-reviewer |
| 5a | nur bei Bedarf: Plan-Nachtrag 1 | vor der Anpassungsrunde | evidence-reviewer |
| 6 | Vollauf | Eingaben (falls nicht in PR 3), Ausgaben, Bericht `rating_v3_full_*.md`, abgeleiteter Datensatz H_v3, Owner-Vorschlag | Klasse B; evidence-reviewer |
| 7 | Anzeige | Tierliste und Kartenfenster lesen H_v3, **nur nach Owner-Go** | Produkt-PR; Fresh-Context-Review; Studio-Guards |

Zuständig ist der Co-Lead als Planer und Adjudikator. Umsetzung, Läufe und Skripte übernimmt der vom Owner für die Sitzung gewählte Worker. Claim in #1404 vor jedem Schritt (AGENTS §11).

## §9 Abweichungsliste

(leer)

## §10 Herkunft und Reproduktion

```
# A1 (Eingaben außerhalb des Repos siehe README):
A1_USAGE=<usage_holdout.jsonl> A1_CORPUS=<chulane_corpus> A1_F1RAW=<F1-Chargenprompts> A1_OUT=<ordner> \
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

Auf `main` @ `f4d49ad6` nachgerechnet: Die A1-Ausgaben sind byte-gleich mit den SHA-256 in A1 §7, die A2-Ausgaben byte-gleich mit den Phase-A-Dateien (6 von 6). Die Ausgabe des letzten Befehls liegt als `data/research/chulane_rubric_v3_20261123/v3_baselines.json` im Repo (zweimal byte-gleich). Sie enthält nur Kennzahlen und Kartennamen, keine Nutzungswerte je Karte. Die Gewichtsprobe in I2 (gleiche gegen gesetzte Gewichte) ist eine Gegenprobe, keine Grundlage der Wahl.
