# BUILDER-Audit Chulane + TAM: Stand, Lücken, Arbeitsplan (2026-11-21)

## 0. Ergebnis zuerst
- **Der Builder trägt.** Für Chulane sind von 21 geprüften Zeilen (Abschnitt 2) 15 FUNKTIONIERT, 3 TEILWEISE, 1 DEFEKT, 1 UNKNOWN (Tokens: Test-Store ohne Token-Daten), 1 korrekt abwesend (Preise). Für TAM: Deckbau und Zukauf-Pool gehen, Preise FEHLEN, Vergleichsdaten sind im Klon UNKNOWN (TAM-Korpus liegt nur im Drive).
- **1 echter Defekt (laut `git log -S` seit #1671 auf main):** Tab „Simulation“ → „Karten-Auswertung aus Partien“ bleibt bei „lädt …“, Seitenfehler `TypeError: Function.prototype.apply was called on undefined` in `static/kartenauswertung.js:450/460/470`: `StudioUI.kids` gibt es nicht (`static/ui.js:335` exportiert es nicht; `kids` ist nur lokal in `app.js:52`). Die Tests bestehen, weil sie `StudioUI.kids` selbst stubben (`tests/unit/test_studio_card_outcomes.py:1475`). Betrifft Chulane und TAM, alle drei Antwortpfade.
- **Tierliste:** Rechnung und Herkunft stimmen, die Darstellung nicht: die Spalte „Kartenverständnis“ zeigt nur H (1 von 7 Kriterien; E/F/T/R/K/D, Begründung und Regelclaims liegen für 922 von 922 Karten im Repo, werden aber nicht ausgeliefert), ohne Unsicherheit (`intervall: null`), und wiederholt den Herkunftstext in jeder Zeile (3 bis 4 Karten je Bildschirm bei 1600×1000, `10_tierliste.png`).
- **Länder:** Exakte Karsten-Rechnung ist da, aber drei Lücken verfälschen sie messbar: Suchländer zählen als 0 Quellen (Chulane-Basis: Farbzugriff 1,8 bis 11,1 pp zu niedrig, Mittel 5,5 pp über 26 Anforderungen), getappt eintretende Länder werden nicht modelliert (8 von 36 immer, 2 von 36 bedingt getappt), der Commander selbst steht nicht in der Kurve. Für TAM fehlt die Zukauf-Seite der Länderwahl ganz.
- **Plan:** 9 Pakete sofort baubar (≈ 17–24 Agent-Tage, Schätzung ±40 %), 5 brauchen Owner-Daten oder -Entscheid, 5 bewusst später. Reihenfolge: WP-1 → WP-2/3/4 → WP-5 → WP-6 → WP-7/8 → WP-10a.

**Grundlage und Grenzen.** `main` @ `d2ecbe89`, frischer Klon (nach dem Audit gelöscht). Studio lokal auf 127.0.0.1, Playwright 1600×1000. Store: Kopie eines Repo-Imports vom 2026-11-19 (Schema 21, 1.655 Karten, 10.551 Quelldecks), kein frischer `import-all` (keine Scryfall-Bulk-Datei im Container, CPU-Schonung); dazu ein leerer Store. Keine Testsuite, kein Engine-Lauf. Lastmittel ≈ 6 auf 4 Kernen: Ladezeiten sind keine Messung. Echte TAM-Daten (`tam:active_91`, 381, EDHREC-78), Owner-Store und alle Simulationsserien: **UNKNOWN**. Belege: `/tmp/claude-0/-home-user/ef006e8b-893c-5ebd-80a1-8743a09c7458/scratchpad/fa_shots/` (unten nur Dateiname).

## 1. SOLL-Katalog (Quelle: R = `docs/OWNER_DECISIONS_STUDIO_20261118.md`, R12 = `…_20261112.md`)
| # | Gewolltes Feature | Chulane | TAM | Quelle |
|---|---|---|---|---|
| F1 | Deck anlegen, laden, Varianten, Stand speichern, Verlauf, Export/Dossier | ja | ja | R:78 (E1), #1404 D5, Scope §BUILD |
| F2 | Deckliste einfügen (Text/CSV) | ja | ja | #1404 Vorschlag 7 |
| F3 | Pool aus Sammlung, Filter, Suche, freie Kopien | ja | ja | R12:32 (B1), #1187 P0 |
| F4 | Tierliste = Nutzung, eine Skala 54/35/20/5, n/N je Komponente | ja | Nutzung je Kohorte, keine Wertung | R12:41 (B10), R:392 (Q1), #1187 Kopf |
| F5 | Kartenverständnis (Modellurteil) mit Einzelwertung | ja, nur Chulane | nie | R:220-235 (E6), R:392-396, #1666 |
| F6 | Vorschläge als eigene Klasse VORSCHLAG, „Übernehmen“ = Owner-Entscheid | ja | ja | R:397 (Q2), Charta §5 Q2 |
| F7 | Tausch-Helfer, Kürzen, Bauplan, Lücken-Ausgleich, ähnliche Decks | ja | ja | #1404 Vorschläge 2–4, 10 |
| F8 | Manabasis: Länder-Vergleich, Farbquellen, Karsten-Kurve, Starthand | ja | Fünffarben-Länderbericht mit ETB | #1404 Vorschlag 1, #1187 P1, R12:60 (S6) |
| F9 | Landzahl-Achse 33/36/39 mit exakter Gegenprobe | ja | – | R:115 (G-SIM 5), #1528 |
| F10 | Zukauf-Modus: Schalter, Kennzeichnung, Zukauf-Liste | Standard aus | ja | R:350-382 (E14, T2), #1636 |
| F11 | Preise nur TAM-Zukauf: Anzeige, Summe, Sortierung, Budgetfilter; Quelle + Zeitstempel; nie in Wertung | nein | ja | R:499-520, #1637 |
| F12 | Evidenz R0–R3 im Verlauf, Diff, Kürzen/Tauschen; `SIMULATED_RESULT` | ja | gesperrt bis Sim-Bereitschaft | #1666, R:399 (Q3) |
| F13 | Experimente planen, Übernehmen/Verwerfen | ja | – | R:402 (Q4), #1658 |
| F14 | Kohorten nie gemischt, unbekannt nie 0, jede Zahl n/N | ja | ja (`tam:active_91` Standard) | R12:22-23 (A4, A5), R:399 |
| F15 | Start „Partie spielen“ / Serie aus dem Deckbauer | ja | – | Scope §Abschlusskriterien 3 |

## 2. IST je Feature (Browser + API, Beleg in Klammern)
| Feature | Chulane | TAM | Beleg / Befund |
|---|---|---|---|
| Deck laden, Variante, Entwurf, Stand | FUNKTIONIERT | FUNKTIONIERT | `01_index.png`; 100/100, „Datenprüfung ohne Befund“ |
| Neues Deck | FUNKTIONIERT | TEILWEISE | `21_tam_newdeck.png`; Commander-Wahl legt ungefragt ein gespeichertes 1-Karten-Deck an (`app.js:2929`) |
| Deckliste einfügen | TEILWEISE | TEILWEISE | `31_import.png` (Zukauf-Schalter aus): „Nicht Existierende Karte“ und „Hallowed Fountain“ stehen beide unter „nicht in deiner Sammlung“, übernommen 4 von 7 Zeilen; mit Schalter an: UNKNOWN (nicht geprüft) |
| Karten ändern, Zähler, Prüfung | FUNKTIONIERT | FUNKTIONIERT | 101/100 → „1 Fehler“, Entwurf gesichert |
| Tierliste Nutzung | FUNKTIONIERT | TEILWEISE | `10_tierliste.png` (S39/A33/B48/C185/D617/N5); TAM im Klon: 39 von 1.654 mit Stufe, 1.608 U, „S 100,0“ aus Perzentil einer 29er-Gruppe (`28_tam_tierliste.png`); echte Kohorte UNKNOWN |
| Kartenverständnis | TEILWEISE | korrekt abwesend | nur H, 922 von 927; `understanding_field.py:36,76-91`; im Deckbauer-Kartenfenster gar nicht (`cardmodal.txt`) |
| Tausch-Helfer | FUNKTIONIERT | UNKNOWN (kein Korpus) | `04_swap.png`: Path to Exile Platz 1 (4.346/10.128), Lift erst ab n 30 |
| Kürzen | FUNKTIONIERT | FUNKTIONIERT (leer) | `06_kuerzen101.png`: „Vorschlag 1 von 80“, Rollen-Leitplanke, Reife-Zeile |
| Bauplan, Zustand, Lücken-Ausgleich | FUNKTIONIERT | TEILWEISE | `03_zustand_wait.png`; mit Zukauf-Schalter verschiedene Nenner (Bauplan 1.408/1.654, Zustand 1.675/2.201), Kandidaten nur aus Sammlung |
| Pakete, Kombos, ähnliche Decks, Diff | FUNKTIONIERT | UNKNOWN | `03_pakete.png`, `tab_10.txt`, `tab_11.txt` |
| Manabasis / Länder | TEILWEISE | TEILWEISE | Abschnitt 4 |
| Zukauf-Pool, Schnellfilter | FUNKTIONIERT | FUNKTIONIERT | `24_tam_planeswalker.png`: 2.200 Karten (API: 547 ohne Besitz); Planeswalker 320; Chips Proliferate, Boardwipes, 5C-Fixierung, Nur Zukauf |
| Zukauf-Liste | FUNKTIONIERT | FUNKTIONIERT | `25_tam_liste.png`: „Im Besitz: 1/100 · Zukauf: 3/100“, Kopieren `1 <Name>` (`wishlist.js:61`) |
| Preise | korrekt keine | **FEHLT** | #1637 offen; laut Register entfernt `sources.py:157` Preisfelder beim Import |
| Evidenz/Reife | FUNKTIONIERT (formal) | gesperrt (`maturity.py:92`) | `07_verlauf.png`: „R2 und R3 sind nicht erreichbar“, „kein Befund … unbekannt, nicht 0“; echter Befund UNKNOWN |
| Experimente | FUNKTIONIERT (leer) | – | `07_experimente.png`: „kein Experiment gespeichert“; Lauf nicht geprüft (kein Engine-Lauf) |
| Karten-Auswertung aus Partien | **DEFEKT** | **DEFEKT** | Abschnitt 0 |
| Serien-Planer | FUNKTIONIERT (Anzeige) | – | `tab_15.txt`: 40 Paare weisen erst 31,3–41,5 pp nach; für 5 pp 1.254–2.195 Paare |
| Daten-Banner | FUNKTIONIERT | **DEFEKT (Darstellung)** | `20_tam_select.png`: Tabelle füllt den ganzen Bildschirm, „Gezählt für Tam“ über „Quelldecks 10.551 von 10.551“ (Chulane-Decks); Filterleiste überlappt die Tabelle (`24_tam_planeswalker.png`); Importhinweis nennt `import-all --decklists` statt `scripts/import_tam_drive.py` |
| Tokens | UNKNOWN | UNKNOWN | „0 / 16 aufgelöst“, Tabellen `scryfall_token` leer im Test-Store |
| Leerer Store | FUNKTIONIERT | – | `30_empty.png`: Import-Befehle je Schicht, 404 statt Absturz |

## 3. Tierliste und Kartenbewertung
**Stand der Methode (Repo, `data/research/chulane_rubric_v2_20261118/`).** Gesamtrating ist seit E15 Q1 entfernt. Kartenverständnis v2.1: ein Rater-Lauf, 922 Karten. Referenzdeck-AUC (79 gegen 843 Karten): H 0,819, Rubrik v1 0,845, Quelldeck-Anzahl 0,924. Hold-out Bracket 5 (n=736): Gesamtrating 0,471 gegen Index 0,636, vorab festgelegtes Kriterium verfehlt; 576 von 736 Zielwerten sind 0, das Ziel ist selbst Nutzung. Drift (n=49): mittlere |ΔH| 5,10, 3 von 49 ≥ 15. Unabhängiger Rater (n=70): |ΔH| 7,9, 13 von 70 ≥ 15. Audit: 29 von 230 zweifelhaft, Regelclaims 100 von 100. Guide v2.2 (n=70): 20 von 35 markierten in der Prüfer-Spanne (vorher 2), Kontrollen 6 von 35 mit |ΔH| ≥ 15.
**Eigene Messung am Test-Store (API `/api/strength`):** 922 Karten mit Index, nur 250 verschiedene Werte; 777 von 922 stehen in Gleichstandsgruppen (größte 99 Karten bei 0,1); 622 von 922 haben Index ≤ 5; 167 grenzwertig, 29 unscharf. H: 19 verschiedene Werte, größte Gruppe 108 Karten.

| # | Verbesserung | Beleg | Messplan (Metrik · Datensatz · Abbruch) | Owner nötig |
|---|---|---|---|---|
| T1 | H mit gemessener Streuung zeigen („± rund 5 bis 8, 1 Lauf“), Herkunft in Kopf/Tooltip | `intervall: null`; Drift n=49, Rater n=70 | Karten im Sichtfeld vorher/nachher (heute 3 bis 4) · Playwright 1600×1000 · Ziel ≥ 15 | nein |
| T2 | Einzelwertung E/F/T/R/K/D, Begründung, Regelclaims im Detail | 1 von 7 Kriterien ausgeliefert, Daten 922/922 | Abdeckung n/N je Kriterium in der Antwort · Datensatz v2.1 · fehlende Zeile = „unbekannt“ | nein (E6 will sie) |
| T3 | Audit-Markierung „vom Prüfer bezweifelt“ | `audit_A_flagged.jsonl` 35 Zeilen | Anteil markierter Karten mit Kennzeichen = 35/35 | nein |
| T4 | Gleichstände ehrlich: Rangband statt Dezimalstelle in Stufe D | 777/922 | Anteil Karten mit Scheinrang vorher/nachher | nein |
| T5 | Länder-H als eigene Skala kennzeichnen | Gutachten §4: 65 Länder, T = 0 bei 58 von 65 | Kennzeichen an 65/65 | nein |
| T6 | Deck-Split: bricht H Gleichstände sinnvoll? | Gutachten §2 Nr. 1 | partielle Rangkorrelation von H mit Vorkommen im 20-%-Rest, je Index-Gruppe · 10.128 Quelldecks, 5 Faltungen, Bootstrap über Decks · zuerst Rauschobergrenze (Hälfte A gegen B); ist sie nicht von 0 trennbar, kein Schluss | nein |
| T7 | Zeit-Split: erkennt H Karten vor der Menge? | 10.551 von 10.551 Decks datiert (2024-11-13 bis 2026-11-15) | Index bis Stichtag gegen Zuwachs danach · Abbruch bei < 30 Decks nach Stichtag je Gruppe | nein |
| T8 | Blinde Paarvergleiche (≈ 120 Paare, ≈ 1 h) | einzige nutzungsfreie Referenz | Anteil gleich geordneter Paare je Rangliste, Wilson · je 40 Widerspruch/Gleichstand/Zufall · Schwelle vorab | **ja (Owner-Zeit)** |
| T9 | Guide v2.2 abgeschwächt auf Teilmenge, zweiter Lauf für 498 Karten „mittel“ | Überkorrektur 6/35 | Anteil in Prüfer-Spanne und Kontroll-Drift ≤ 10 % · Abbruch bei Kontroll-Drift > 10 % | **ja (neuer Rater-Lauf)** |
| T10 | Messbericht am echten Store (#1369) | Repo-Store ≠ Owner-Store | Abweichung je Kennzahl | **ja (Owner-PC)** |

## 4. Länder, Mana-Basis, Fünffarben
**Vorhanden:** Länder-Vergleich Deck gegen Kohorte (Median, mittlere Hälfte, n=10.092), Farbsymbole gegen Quellen je Farbe, 14 gepinnte Zyklen (Fetch, Shock, Dual, Triome, Verge … `land_advisor.py:488`), freie Länder ab 20 % Kohortenanteil mit n/N, exakte Land-Ziehwahrscheinlichkeiten, „Farben auf Kurve“ nach Karsten 2022 als ein gemeinsames Ereignis, bedingt auf Land-Drops (`castability.py`), spielbare Starthand 68,9 %, Rollen in der Starthand, Beispielhand mit London-Mulligan, Diff mit Land-Zieh-Delta. Für eine 0-Länder-Liste steht korrekt „unbekannt“.

| # | Lücke | Beleg (n/N, Herkunft) | Nutzen | Tage | Risiko | Abhängig | Messplan |
|---|---|---|---|---|---|---|---|
| L1 | Suchländer zählen als 0 Quellen | `castability.py:17-19`; Chulane: 3 von 36 (Fabled Passage, Evolving Wilds, Terramorphic Expanse); mit Zählung als W/U/G: UU Zug 3 65,2 → 76,4 %, Mittel +5,5 pp (26 Anforderungen, exakt); synthetische TAM-Probe: 5 von 34 | hoch, für TAM entscheidend (Fetch + Shock/Triome) | 2–3 | Suchbarkeit aus Kartentext ist eine Rechenannahme, kein Regelurteil | – | Erkennungsquote n/N der Suchländer im Pool; Gegenrechnung per Voll-Enumeration auf Mini-Decks; Abbruch < 95 % erkannt |
| L2 | Getappt eintretende Länder nicht modelliert | Textmuster am Store: 8 von 36 immer, 2 von 36 bedingt getappt | hoch (Tempo) | 3–4 | Reihenfolge der Landdrops braucht Annahme | L1 | Stufe 1 nur Klassen zählen (n/N, „unbekannt“ eigene Klasse); Stufe 2 exakt „ungetappte Quelle in Zug 1/2“; Abbruch, wenn Stufe 2 eine Spielannahme braucht, die nicht in einem Satz erklärbar ist |
| L3 | Commander nicht in der Kurve | vorhandene Funktion: Chulane 2GWU Zug 5 = 45,6 % Land-Drops × 92,8 % Farben = 42,4 % | mittel | 1 | gering | – | Wert gleich `colour_probability` (Test) |
| L4 | Ramp und Manasteine fehlen in der Kurve | „Quellen: nur Länder“; Deck: 22 Ramp, 5 Mana-Kreaturen, 4 Steine | mittel | 3–5 | Modell wird schnell Spiel-Heuristik | L1–L3 | nur Verbundereignis „k Länder und ≥ 1 Ramp mit MV ≤ 2“ exakt; sonst später |
| L5 | Kein Vorher/Nachher der Manabasis | `deck_diff.py:70` vergleicht nur Quellenzahl | hoch (Länderwahl) | 2 | gering | L1–L3 | Delta je Anforderung in pp, beide Stände exakt |
| L6 | Keine Landzahl-Tabelle 30–40 | nicht im Code gefunden (grep) | mittel, Gegenprobe für #1528 | 1 | gering | – | Hypergeometrie je Landzahl, Test gegen Handrechnung |
| L7 | Länderwahl kennt keine Zukauf-Länder | `land_advisor.py:386`, `app.js:958` (`owned_only: true`); 49 Zukauf-Länder im TAM-Pool nur über die Kartensuche | hoch für TAM | 2–3 | Nenner-Mix Sammlung/Zukauf | – | getrennte Zeilen Sammlung/Zukauf, Test „nie eine gemischte Zahl“ |
| L8 | TAM-Vergleichsgruppe leer | Klon: „alle Quelldecks (0)“ | hoch | 0,5 + Owner | Privatdaten bleiben lokal | Owner-PC | Median Länder, Quellen je Farbe, Zyklen n von 91 |
| L9 | Mulligan nur als Beispielhand | Tabellen „ohne Mulligan“ | gering | 2–3 | Annahme „wann behalten“ | – | später |
| L10 | Kosten der TAM-Länder | #1637 | hoch für TAM | in WP-10 | Preiswächter | WP-10 | nur Zukauf-Ansicht |

## 5. Owner-Entscheide hinterfragt (Empfehlungen, nichts davon vollzogen)
| Entscheid (Quelle) | Dafür | Dagegen | Empfehlung · was der Owner tun müsste |
|---|---|---|---|
| Gesamtrating entfernt (R:392, Q1) | Hold-out 0,471 gegen 0,636 (n=736); für 2/3 des Pools reines Modellurteil; 1 Rater-Lauf | Owner wollte „Einzelwertung unbedingt“ und Tierliste „mainly darauf“ (R:220-235); Index ordnet 777/922 nicht | **behalten**, aber Einzelwertung zeigen (WP-6); „Index, Gleichstände nach H“ als wählbare Sortierung erst nach T6/T8 · Ja/Nein nach den Messungen |
| Standard „Nutzung“ (R:268, C6) | AUC 0,924 gegen 0,819 | – | **behalten** |
| Guide v2.2 nicht ausrollen (R:268) | Kontrollen 6/35 überkorrigiert | 20/35 statt 2/35 getroffen | **ändern**: abgeschwächte Fassung auf Teilmenge testen (T9) · Go für einen Rater-Lauf |
| Paarvergleich „optional“ (R:269) | kostet 1 h | einzige Referenz ohne Nutzung und ohne Modell | **ändern: machen** (T8) · 1 Stunde am PC |
| Anker-Frage 7 „gewolltes Urteil“ (R:268) | v1-Anker bilden Beliebtheit ab | Command Tower 74 statt 100, Counterspell 45 statt 67 (n=10 Anker, MAE 10,8) | **behalten**, Länder-H als eigene Skala kennzeichnen (T5) |
| Landzahl-Achse 33/36/39 als erste Frage (R:115) | wenig pilotabhängig, exakt gegenprüfbar | Planer: 40 Paare weisen erst > 31 pp nach, 5 pp brauchen 1.254–2.195 Paare; Kohorte liegt bei 36 (34–38) | **behalten als Methodentest**, vorher L6 liefern und „kein nachweisbarer Unterschied“ als erwartetes Ergebnis festhalten · drei Tauschkarten benennen |
| Reihenfolge: Builder-Oberfläche in Phase 3 (Charta §4, Planung, kein Owner-Entscheid) | Kreislauf zuerst | WP-1 bis WP-8 hängen weder an Bridge noch an Schema 22 | **ändern**: Builder-Pakete vorziehen · ein Satz „Builder zuerst“ |
| Preisgrenze „nie in Vorschläge/Kürzen-Tauschen“ (R:511-520, Einordnung Co-Lead) | Wertung bleibt objektiv | Owner-Ziel ist günstiger Kauf; „günstigere Karte gleicher Rolle“ wäre heute verboten | **behalten** für Tierliste/Ranking/Simulation; **Owner fragen**, ob die Zukauf-Ansicht Alternativen gleicher Rolle mit Preis nebeneinander zeigen darf (Reihenfolge weiter nach Häufigkeit); Owner-Vorbehalt AGENTS §8 |
| TAM ohne Tierliste/Wertung (#1187 Kopf) gegen Produkt | objektive Daten | main zeigt für TAM Stufen S–D aus 39 Karten | **klären**: bis `tam:active_91` geladen ist nur „Nutzung n/N“, keine Buchstaben · Ja/Nein |
| Kartenverständnis nie für TAM (#1666) | nicht validiert | TAM-Kauf von Planeswalkern bräuchte genau das | **zurückstellen** bis T6/T8 für Chulane vorliegen |
| Zukauf-Schalter auch bei Chulane (`index.html:53`) | E14 erlaubt es, Standard aus | Fokus-Datei: Zukauf für Chulane unnötig | **behalten**; Preise per Wächter nur bei Commander TAM |

## 6. Arbeitsplan (Tage = Agent-Tage, Schätzung ±40 %; Klasse nach AGENTS §10)
Vorschlag Besetzung: Builder = Implementierungs-Helfer auf der Standard-Helfer-Stufe (Owner-Vorgabe in `.claude/settings.json` gilt), Effort medium (WP-2, 4, 6, 10a: high). Reviewer = frischer Kontext auf der Lead-Stufe (AGENTS §7); bei Klasse A zusätzlich das zweite Review auf anderem Modell (Ausnahme 2026-11-21). Vor jedem Paket Claim in #1167.

**(a) Sofort baubar, ohne Owner**
| WP | Ziel | Akzeptanz (prüfbar) | Dateien | Tage | Klasse | Nach |
|---|---|---|---|---|---|---|
| 1 | Karten-Auswertung rendert wieder | Browser-Test lädt echte `ui.js` und sieht Tabelle oder „zu wenig Daten“ in allen 3 Pfaden; Test fällt ohne Fix; kein Stub von `StudioUI` mehr | `static/ui.js`, `static/kartenauswertung.js`, `tests/unit/test_studio_card_outcomes.py` | 0,5 | klein; Review, weil SIM-Anzeige | – |
| 2 | Suchländer als Quellen (L1) | getrennte Spalten „direkt“ / „über Suchland“; Erkennung ≥ 95 % n/N; Chulane-Werte gleich Handrechnung; unbekannt bleibt unbekannt | `castability.py`, `land_advisor.py`, `static/castability.js`, Tests | 2–3 | B | – |
| 3 | Commander in der Kurve (L3) + Landzahl-Tabelle 30–40 (L6) | Chulane Zug 5 = 42,4 % am Basis-Stand; TAM 1GU; Tabelle exakt | `castability.py`, `static/castability.js`, `overview.js` | 1,5 | B | – |
| 4 | Getappt-Klassen und Tempo-Kennzahl (L2) | je Land Klasse mit Regeltext-Zitat; 8/36 und 2/36 am Basis-Stand; „unbekannt“ eigene Klasse | `land_advisor.py`, `castability.py`, UI, Tests | 3–4 | B | 2 |
| 5 | Manabasis vorher/nachher (L5) | Diff zeigt je Anforderung pp-Delta, Starthand, getappte Länder, Commander | `deck_diff.py`, `static/diffimpact.js` | 2 | B | 2–4 |
| 6 | Tierliste ehrlich und lesbar (T1–T5) | ≥ 15 Karten im Sichtfeld; Band und Quelle an jeder H-Zahl; 7/7 Kriterien im Detail; 35/35 Audit-Marken; Mutationsproben rot | `understanding_field.py`, `card_understanding.py`, `static/tierliste.js`, `static/zahl.js` | 2–3 | A (Rating-Text) | – |
| 7 | Zukauf in Länderwahl, Bauplan, Tausch, Import (L7) | Schalter wirkt in allen 5 Ansichten; Sammlung und Zukauf nie in einer Zahl; Import trennt „unbekannte Karte“ von „nicht im Besitz“ | `land_advisor.py`, `packages.py`, `swap.py`, `decks.py`, `app.js`, `wishlist.js` | 3–4 | B | – |
| 8 | TAM-Ansicht aufräumen | Banner eingeklappt und je Commander gezählt; keine Überlappung bei 1366 und 1600 px; richtiger Importhinweis; gleiche Nenner in Bauplan und Zustand | `static/app.js`, `app.css`, `data_report.py` | 1–1,5 | klein | – |
| 9 | Validierung T6 + T7 (Bericht, kein Produktcode) | Plan mit Schwellen vor der Rechnung committet; Bericht mit n/N und Intervallen | `scripts/`, `docs/analysis-reports/` | 2–3 | B | – |
| 10a | Preise TAM Stufe 1: Richtwert aus lokaler Scryfall-Datei | nur Commander TAM, nur Zukauf-Ansicht; Quelle + Zeitstempel; fehlend „unbekannt“; Summe, Sortierung, Budgetfilter; Wächtertest: kein Preisfeld in strength, swap, cut-lab, Vorschlägen; Kennzeichnung „Richtwert, nicht DE/EX“ | `sources.py`, `builder.py`, `wishlist.js`, Wächterliste im Register-Abschnitt „Preise für TAM“ | 3–4 | A | 7 |

**(b) Braucht Owner-Daten oder -Entscheid**
| WP | Was | Owner-Beitrag | Empfehlung |
|---|---|---|---|
| 11 | Paarvergleich-Werkzeug + Auswertung (T8), 1,5 T | ≈ 1 h blinde Vergleiche | machen, vor jeder Sortier-Entscheidung |
| 12 | Rater-Lauf v2.2-abgeschwächt (T9), 2 T + Laufzeit | Go für neuen Lauf | erst nach WP-9/11 |
| 13 | TAM-Kohorte laden, Fünffarben-Länderbericht (L8), 1 T | Import am PC, Zahlen zurück (ohne Kartennamen) | jetzt, WP-2 bis 5 wirken dann sofort für TAM |
| 14 | Landzahl-Achse #1528 | Tauschkarten, Nachtserien | nach WP-3 |
| 10b | Cardmarket-Zielgröße (DE, mind. EX) | API-Schlüssel lokal oder Verzicht | zuerst 10a + Wants-Export, API nur bei Bedarf |

**(c) Bewusst später:** Ramp-/Mulligan-Modell (L4, L9); Kartenverständnis für TAM; TAM-Simulation (Q3); Evidenz R2/R3-Erfassung (#1666 Folgepakete); Sortierbares Kartenverständnis.

## 7. Offene Owner-Fragen (mit Empfehlung)
1. Builder-Pakete vor Phase-2/3-Arbeit ziehen? **Ja.**
2. Eine Stunde blinde Paarvergleiche? **Ja**, das ist die einzige Prüfung des Kartenverständnisses ohne Nutzung.
3. TAM-Tierliste ohne Stufen-Buchstaben, bis `tam:active_91` geladen ist? **Ja.**
4. Preise: zuerst Richtwert aus Scryfall (klar gekennzeichnet) und Export für Cardmarkets Wants-Liste, API später? **Ja.**
5. Darf die Zukauf-Ansicht Alternativen gleicher Rolle mit Preis nebeneinander zeigen? **Ja, nur dort, Reihenfolge weiter nach Häufigkeit.**
6. TAM-Import am PC ausführen und die Kennzahlen zurückgeben? **Ja**, sonst bleibt der Fünffarben-Bericht UNKNOWN.
