# Issue #1029 — Pilot game-mining: what is left of P1-P11 after the pilot phases, ranked

FINAL (Dumps + Zählungen 2026-10-26, abends). Source lock: Lab main
`6fb26071b`, Engine-Pin v13 `90f5c4d3f8d3b799b15b6675fcce40bb0dd4738e`.
Bridge-JAR: `wt-1029/engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar`,
sha256 `eca822d295a3f3340db1e9dc0c1acbd9d45accad6f6468325fa1285e178948fa`
(gebaut 2026-10-26 13:12 UTC aus dem v13-Fork-Install). Alle 11 Phasen-PRs
sind Vorfahren von Main (per `git merge-base --is-ancestor` geprüft).
Report only — kein Pilot-Code geändert. Pod-Profil: casual/mid, Real-Pod.

Dump-Serien (beide: `record --all`, Real-Pod, gleiche JAR, gleiche
Corpus-Version 1):

- **Main** (Pilot auf Main 6fb26071b, Worktree wt-1029): Seeds 1–24,
  24 Spiele, 70.874 Entscheidungen, 2.953/Spiel (Median 2.842), 65,37 MB.
- **Pre** (Pilot vor #1010, Worktree wt-1029-pre1010 @ 77a643737 =
  #1009-Merge, d. h. Pilot ohne #1010-Gates): Seeds 1–6, 6 Spiele,
  24.105 Entscheidungen, 4.018/Spiel (Median 3.478), 18,56 MB.
  Seed 1 = der intakte Smoke-Dump vom Nachmittag (3.693 Zeilen).

Alle Zählungen: `analyze_dump.py <mergedump>` (liegt diesem Bericht bei).
Jede Zahl trägt ihre Zählregel; was sich aus dem Dump nicht zählen lässt,
steht als NOT_COUNTABLE, nie als Null.

## 1. Status-Tabelle

Legende: merged = PR gemergt, in Main enthalten. partly = Teil gemergt,
Rest offen. open = nichts davon gemergt. dropped = gemessen und verworfen
(mit Messung zitiert). in flight = Arbeit läuft, kein PR.

### Block A — P1-P11 aus handover/2026-10-23/game-mining/ (11 Zeilen)

| # | Finding (Klasse) | Status | Beleg / was bleibt |
|---|---|---|---|
| P1 | Ziel-Scoring (target) | partly | #1004: falsche Seite 76/279 → 21/279 (Pods 48/153 → 17/153, Real-Pod 28/126 → 4/126); Geschenke an schwächsten Gegner 2/26 → 26/26. Rest: 21 = benannte Ausnahmen (Ziel ist Karte/Friedhof, falsches Engine-Label); Kampf-Ziele + Focus-Fire explizit ausserhalb von #1004. |
| P2 | Prioritäts-Politik (priority) | partly | #1010: eigene Upkeep/Draw-Instants 186/313 → 29; eigene-Main-Instants 35 → 182; Gegner-Angriffs-Instants 1 → 40; Spells/Spieler-Runde 1,22 → 1,34 (+0,12, +0,07..+0,17, p 0,0002). Rest: Mana für Instants zurückhalten (von #1010 als „next" benannt, = Phase 4a-2, in flight, s. Block D); Postcombat-Deployment von Sorcery-Permanents nicht implementiert. |
| P3 | choose_use-Audit (choose_use) | partly | #1003: Cancels/1000 Entscheidungen 3,44 → 2,41; Ketten-Folgen 26 → 7; X=0-Casts 1/18 → 0/22; Pay-any 0/4 → 4/4. #1009: Cancels 82 → 46 (ab erstem Prompt unbezahlbar 78 → 42); Shriekmaw 17 → 0. Rest: bepreiste May-Fähigkeiten (z. B. „Pay {1} and 1 life and draw a card?" 100 % Ja, 1.317×) — #1003: „Not changed: May answers". |
| P4 | Mana-Zahlungs-Fast-Path (mana_payment) | partly | Korrektheit via #1007 (Cancels 136/2.948 → 82/3.122; ab erstem Prompt vermeidbar 56 → 4), #1009 (82 → 46), #1027 (43 → 20). Rest: der Fast-Path selbst (feste Regel, keine volle Optionsbewertung) ist NICHT gebaut — die Volumen-Ersparnis ist nicht realisiert, der Solver bewertet weiter. Frischer Wert: 16,3 % aller Entscheidungen (s. §2), ältere Schätzung ~19 %. |
| P5 | Zustands-Profiling (alle Klassen) | open | Kein Profiling-PR. #1004s wall_s-Notiz ist Last-Rauschen, kein Profiling. Aus dem Dump nicht zählbar (keine Wandzeit je Entscheidung). |
| P6 | Instrumentierung Hand/Zustand (—) | open | Transkripte enthalten weiter nur Entscheidungen; der Corpus zeichnet Requests auf, keine Hand-/Zustandsmerkmale. |
| P7 | Kompaktes Transkript-Schema (Infrastruktur) | open | #1008 hat In-Memory-Aggregate verschlankt, nicht das Transkript-Schema auf Platte (Korpus 7,7 GB / 2.033 Spiele unverändert adressiert). Frischer Wert: 922,4 gzip-Bytes/Entscheidung, 2.953 Entscheidungen/Spiel (s. §2). |
| P8 | Kampf-Politik (declare_attacker, declare_blocker) | partly | #1006: Runden mit stehendem Lethal (Replay) 19 → 15 (vermeidbar 6 → 2); echte Spiele 19 (6) → 16 (4); Blocks 139/86 → 154/97; Chumps 28 (24 lethal) → 43 (37). #1019: Gleichstände nach Attack-Score, dann RNG (435 Gleichstände in 24 Spielen). #1022: Commander-Druck gesetzt, fast wirkungslos (42/48 bit-identisch). Rest: Ob-überhaupt-Angreifen (von #1019 unberührt); sequenzielle Blocker-Frage (früher Blocker sieht spätere engere Optionen nicht). |
| P9 | Determinismus-Replikation (Hash, alle Klassen) | partly | v13-Twin-Basis steht (Max-Review Pass 2: 49/50 Twin-Paare hash-identisch auf v13). Rest: gezielte Replikation der 147 abweichenden Duplikat-Keys auf v13 nicht getan; ohne Ergebnis-Effekt (M4: Duplikate ergebnisgleich) → niedrige Priorität. |
| P10 | X-Wert-Politik (announce_x, multi_amount) | partly | #1003: X=0-Zurückhaltung (s. P3). Rest: X-Breakpoints (Toughness / Leben-minus-Blocker / Reserve) + Pay-any-Dosierung (P1-4) nicht implementiert. |
| P11 | Mulligan-Regel (mulligan) | partly | #1002: Lineal (195 Precons × 100 Hände) Mana T1-6 16,49 → 16,69; farbblockierte Züge 0,467 → 0,362; Züge ohne Spruch 1,32 % → 0,69 %; Mulligans/Hand 0,654 → 0,446; Commander bis T6 85,1 % → 85,7 %. Echte Spiele: Mulligans/Spieler 0,510 → 0,448 (nicht signifikant). Rest: Development Score + Pod-Profil (P1-5). |

### Block B — Weitere Pilot-Items aus der Research (13 Zeilen)

| # | Item (Klasse) | Status | Beleg / was bleibt |
|---|---|---|---|
| P0-1 | Wincon-/Risiko-Inputs setzen (priority/target/declare_attacker) | partly | Genau EIN Input gesetzt: #1022 (commander_damage_pressure, Cap 21). Rest weiter Defaults: expected_lethals, finish_probability, protected_finish, offenes Gegner-Mana, commander_denial_risk, tokens, ramp_mana, exposure. |
| P0-2 | Bedrohungs-Leiter (target, priority) | open | player_threat weiter flache Linearkombination; #1004 ist Seite+Wert, keine Funktions-Leiter; keine Uhren, kein Betrifft-mich-Faktor. |
| P0-3 | Trigger-Ordnung Klassenregel (trigger_order) | open | Weiter Label-Wortsuche (Ist-Stand der Research); keine Klassenregel. |
| P0-4 | Crackback summierter Term (declare_attacker) | dropped | S. Block C. |
| P1-1 | Combo-Teil-Erkennung (priority/target) | open | Kein Combo-Modell; Spellbook-Pakete sind Deckbau-Metadaten (PR5), keine Board-Erkennung. Aus dem Dump nicht direkt zählbar (braucht Paket-Abgleich). |
| P1-2 | Timing-Gates Postcombat/letzte Fenster/Wipe (priority) | partly | #1010 (Fenster). Rest: Postcombat-Default für Sorcery-Permanents (von #1010 explizit nicht implementiert), Last-Window-Draw, Wipe-Timing-Regel. |
| P1-3 | Interaktions-Disziplin / geteilte Verantwortung (priority) | open | Kein Gate („nicht der einzige Antwortende sein"). Teilt sich die Fenster mit dem P2-Rest (gegnerische Züge, Pass trotz Instant-Angebot). |
| P1-4 | X-Breakpoints + Dosierung (announce_x, multi_amount) | open | Gleicher Rest wie P10. |
| P1-5 | Mulligan Development Score + Pod-Profil (mulligan) | open | Gleicher Rest wie P11. |
| P1-6 | Relative Noise / Sichtbarkeit (priority/declare_attacker) | open | Visibility weiter flache Strafe, kein relatives Modell. |
| P2-1 | Rollen-Modell (Meta-Policy) | open | Per Design zurückgestellt (P2: erst messen). Aus dem Dump nicht zählbar. |
| P2-2 | Externe Priors als Startwerte (Deckbau) | open + Owner-Block | PR7 (external_prior) von Hans ausdrücklich NICHT freigegeben; ohne Guardrail-Implementierung kein Hebel. |
| P2-3 | Risiko-Quantifizierung (Modell) | open | Braucht erst Kalibrierung aus eigenen Replays (Lücke L8: keine Wahrscheinlichkeiten in der Literatur). |

### Block C — Gemessen und verworfen (mit Messung)

| Item (Klasse) | Messung |
|---|---|
| Attack-Planning (declare_attacker) | Kein Hebel gefunden (Phasen-Messungen; #1022: „as with the attack planning measured earlier" — der Attack-Score entscheidet fast jedes Angriffsziel bereits). |
| Crackback-Term (declare_attacker) | Ca. 0,17 Leben pro gegnerischem Power-Punkt; 11 von 380 Runden endeten bei 5 Leben oder weniger; keine Metrik bewegt. (Quelle: Issue-#1029-Brief / Phasen-Messungen; Messdateien liegen im Shared-Project-Ordner, nicht im Repo.) |
| Commander-Hit im Angriff (declare_attacker) | 0 verpasste Hits in 24 Spielen. (Quelle wie oben.) |
| Verpasste Land-Drops (priority) | Mining: nur 138 von 87.008 Prioritätsfenstern mit spielbarem Land gepasst (0,16 %). |
| Cast-Sieg-Korrelation (Deck-Entscheidung) | Mining: mit Decklisten-Filter max. \|Δ\| +5,3 Punkte (Scorched Geyser, RogShai, n=174) — im Binomial-Rauschen; keine Deck-Entscheidung daraus. |
| Startspieler-Vorteil (Regel) | Mining: Sieger relativ zum Startspieler 25,2 / 26,4 / 25,0 / 23,4 % (n=1.971) — keine Regeländerung begründbar. |
| Abwurf-Verhalten (—) | Mining: unauffällig (meist Basis-Länder spät im Spiel) — kein Vorschlag. |

### Block D — In flight

| Item (Klasse) | Status |
|---|---|
| Phase 4a-2: Mana für Counterspells/Removal auf der Hand zurückhalten (priority) | In flight — PR folgt aus dem Dirigent-Thread; am 2026-10-26 kein offener PR im Repo. #1010 nennt es als „next: hold mana for instants". Aus dem Dump nicht zählbar (Handinhalt steht nicht im Dump). NICHT parallel neu starten — die Fenster dieser Zeile teilen sich mit P1-3/P2-Rest. |

### Block E — Gemergt ohne eigene P-Zeile (Defekt-Familie: alphabetische Tie-Breaks + Zahlungskorrektheit)

| PR | Was (Klasse) | Messung |
|---|---|---|
| #1015 | Länder/Land-Suchen/Planeswalker nach Urteil statt Namen (priority/choice) | Gleichstand nach Alphabet ersetzt; Footprint ohne JVM 441/81.530 Antworten ändern (Land-Spiele 276, Walker-Fähigkeiten 76, Suchen 89). Vorher: Minus-Fähigkeit 83/83, Quintorius -4 ohne Spirit 43/63, 203 Land-Suchen (Swamp 79, Plains 64, Mountain 8, Island/Forest nie). |
| #1019 | Angriffs-Tie-Break (declare_attacker) | Gleichstände nach Attack-Score, dann RNG. Vorher: 435 Gleichstände in 24 Spielen, höchster „Full Game Seat N" gewann 328/328 Spieler-Gleichstände. |
| #1027 | Rabatt-Ziele nur wo bezahlbar (target/priority) | Bitter-Downfall-Cancels 23 → 0 (bezahlte Casts bleiben 9); alle Cancels 43 → 20 (von 2.044 → 1.941 Entscheidungen). Rest: vier weitere Karten mit ziel-bedingtem Rabatt nicht abgedeckt. |

Arithmetik: 11 (Block A) + 13 (Block B) + 7 (Block C) + 1 (Block D) + 3
(Block E) = 35 Zeilen. Die 6 „Explizit NICHT zu lehren"-Items der Research
(cEDH-Default-Mulligan, cEDH-Counter-Sparen, Deals/Kingmaking, MCTS,
Handlesen, karten-spezifische Prioritätenlisten) sind Leitplanken, keine
Findings, und werden nicht als Zeilen gezählt.

## 2. Reichweite der offenen Zeilen (frischer Full-Dump, echter Pod)

Basis: Main-Serie, 24 Spiele, 70.874 Entscheidungen. Klassen (gesamt):
priority 53.562, mana_payment 11.570, declare_attacker 1.337, target 1.134,
choice 774, choose_object 697, choose_use 644, declare_blocker 555,
trigger_order 184, mulligan 139, announce_x 80, multi_amount 68,
target_amount 54, mode 60, amount 11, pile 5. Kommando: s. Anhang §5.

| Zeile | Reichweite (Main, 24 Spiele) | Zählregel |
|---|---|---|
| P1-Rest (target-Ausnahmen, Kampf-Ziele, Focus-Fire) | target gesamt 1.134 (47,3/Spiel), davon 884 mit ≥2 Optionen; Sub-Reste NOT_COUNTABLE (keine Ausnahmen-Labels im Dump) | target-Entscheidungen; multi = ≥2 legale Optionen |
| P2-Rest: Postcombat-Deployment (P1-2) | 1.186 Kandidaten (49,4/Spiel) + Wipe-Angebote 45 | in eigener precombat_main gewählte Spells ohne instant-speed (Katalog); Wipe = angebotener Spell mit „destroy all"/„exile all" im Oracle-Text |
| P2-Rest: Gegner-Züge, Pass trotz Instant (teilt Fenster mit P1-3, 4a-2 in flight) | 363 (15,1/Spiel) | gegnerischer Zug, Akteur passt, obwohl instant-speed Spell angeboten |
| P3-Rest: bepreiste May-Fähigkeiten | 79 von 644 choose_use (12,3 %; 3,3/Spiel) | choose_use mit Kostenwörtern (pay/life/sacrifice) im Prompt |
| P4: Fast-Path-Volumen | 11.570 mana_payment = 16,3 % aller Entscheidungen (482,1/Spiel) | mana_payment-Entscheidungen (Volumen, das der Fast-Path nicht mehr bewerten würde) |
| P5: Profiling | NOT_COUNTABLE (keine Wandzeit je Entscheidung); Ersatz: Dump 65,37 MB, 2.953 Entscheidungen/Spiel | — |
| P6: Instrumentierung | NOT_COUNTABLE (künftige Läufe) | — |
| P7: Transkript-Volumen | 922,4 gzip-Bytes/Entscheidung, 2.953 Entscheidungen/Spiel (≈2,72 MB/Spiel) | Dump-Grösse je Spiel |
| P8-Rest: ob-überhaupt-angreifen + sequenzielle Blocker | declare_attacker 1.337 (55,7/Spiel) + declare_blocker 555 (23,1/Spiel) = 1.892 | Angriffs-/Block-Entscheidungen (Obergrenze: nicht jede ist der Rest) |
| P9: Replikations-Rest | NOT_COUNTABLE aus einem einzelnen Dump (braucht Duplikat-Keys über Läufe) | — |
| P10/P1-4: X-Breakpoints + Dosierung | announce_x 80 + multi_amount 68 = 148 (6,2/Spiel), davon X>0: 32 | announce_x-/multi_amount-Entscheidungen; positiv = numeric_choice > 0 |
| P11/P1-5: Mulligan DevScore | 139 mulligan-Entscheidungen (5,8/Spiel) | mulligan-Entscheidungen (DevScore selbst braucht Handmerkmale → hängt an P6) |
| P0-1: ungesetzte Inputs | NOT_COUNTABLE direkt (die Inputs fehlen per Definition) | — |
| P0-2: Bedrohungs-Leiter | target 1.134, davon 884 multi-option (s. P1) | Leiter wirkt auf Ziel-Score |
| P0-3: Trigger-Ordnung | 184 trigger_order, davon 184 multi-option (100 %) | trigger_order-Entscheidungen |
| P1-1: Combo-Erkennung | NOT_COUNTABLE direkt (braucht Paket-Abgleich); Proxy 53.098 priority mit ≥1 gegnerischem Permanent auf dem Board = 99,1 % aller priority — der Proxy diskriminiert nicht, er ist nur eine Obergrenze | Proxy wie in der Regel genannt |
| P1-6: relatives Noise-Modell | NOT_COUNTABLE direkt; Proxy declare_attacker 1.337 | Fokus-Wahl als Proxy |
| P2-1: Rollen-Modell | NOT_COUNTABLE (Meta-Policy, keine Entscheidungsklasse) | — |
| P2-2: externe Priors | NOT_COUNTABLE (Deckbau-Zeit) + Owner-Block (PR7 nicht freigegeben) | — |
| P2-3: Risiko-Quantifizierung | NOT_COUNTABLE direkt (Modell-Inputs, keine eigene Klasse) | — |
| 4a-2 (in flight) | NOT_COUNTABLE (Handinhalt steht nicht im Dump; nur hand_count sichtbar) | — |

Lesart: Die grössten zählbaren Hebel sind P4 (16,3 % aller
Entscheidungen), P8 (1.892 Kampf-Entscheidungen), P1-2 (1.186
Postcombat-Kandidaten) und P0-2/P1 (1.134 Ziel-Entscheidungen). Die
kleinen, scharfen Hebel sind P0-3 (184, alle mit Wahl), P10 (148) und
P3 (79). NOT_COUNTABLE-Zeilen sind keine Nullen: Sie brauchen
Instrumentierung (P6), Läufe über Läufe (P9), Paket-Abgleich (P1-1)
oder eine Owner-Entscheidung (P2-2).

## 3. Phase-4a-Reproduktion (Wrong-Reason-Kontrolle)

Zählregel (identisch für beide Serien, aus `analyze_dump.py`):
Gewählte Spell-Option mit `is_instant_speed` aus dem Repo-Katalog
(`data/cards/pilot_card_knowledge.json` via `CardFacts`, keine
Zirkularität aus Pilot-Entscheidungen); early = Step upkeep/draw UND
Akteur == aktiver Spieler. Katalog-unbekannte Typen werden separat
gezählt und aus Zähler wie Nenner ausgeschlossen.

| Serie | Spiele | Instant-Casts gesamt | davon eigene Upkeep/Draw | Anteil early | unbekannter Typ |
|---|---|---|---|---|---|
| Pre (#1010 fehlt) | 6 | 89 | 61 | 68,5 % | 3 |
| Main (#1010 drin) | 24 | 230 | 19 | 8,3 % | 14 |
| #1010-Messung (Soll) | unbekannt | 313 | 186 → 29 | 59,4 % → ~9,3 % | — |

Urteil: **Kontrolle BESTANDEN (Profil reproduziert, Integers erklärt).**
Die Regel misst, was #1010 gemessen hat: Vor den Gates ist die
Mehrheit der Instant-Casts früh (68,5 % hier, 59,4 % bei #1010), nach
den Gates ist sie selten (8,3 % hier, ~9,3 % bei #1010). Der
Post-Absolutwert (19 hier vs. 29 bei #1010) liegt in derselben
Grössenordnung bei vergleichbarer Spielzahl; die exakten Integers
186/313 sind nicht reproduzierbar, weil die Spielmengen verschieden
sind (andere Seeds, #1010s exakte Seed-Menge steht nicht im Issue) —
das ist die erklärte Abweichung, kein Regel-Fehler. Zwei
Einschränkungen, offen gelegt: (1) #1010s Nenner 313 ist im Issue
nicht definiert (gesamte Instant-Casts vs. frühe Fenster); der
Anteilsvergleich setzt gesamte Instant-Casts voraus — unter der
anderen Lesart bleibt der Kontrast (Mehrheit → selten) trotzdem
bestehen. (2) Die Pre-Serie hat längere Spiele (Median 3.478 vs.
2.842 Entscheidungen), was den Pre-Anteil nach oben ziehen kann;
der Kontrast von ~60 Prozentpunkten ist davon nicht erklärbar.
Fazit für die Zählregel: Sie ist gegen #1010 validiert; die
Reichweiten in §2 stehen auf derselben Regel.

## 4. Ranking Top 5 (Reichweite × Machbarkeit)

Massstab: Python-only, auf aufgezeichneten Requests testbar, auf
gepaarten echten Spielen messbar. Win-Rate wird nur berichtet, wenn
gepaarte Power sie trägt, sonst „UNDECIDED, could only see effects
of at least X" (Bezugsgrössen: 24 Paare → Win-Rate nur Effekte ab ca.
25 Punkten sichtbar (#1004); Spells/Spieler-Runde ab ca. 0,07
(#1010)). Pod-Profil casual/mid. 4a-2 (Mana-Hold) wird NICHT neu
empfohlen — es läuft bereits (Block D). P2-2 wird NICHT empfohlen —
Owner-Block (PR7 nicht freigegeben).

### 1. P4 — Mana-Zahlungs-Fast-Path (mana_payment)

Reichweite: 11.570 Entscheidungen (16,3 %, 482/Spiel) — mit Abstand
der grösste zählbare Hebel. Python-only (Pilot-Politik, keine
Engine-Änderung). Aufgezeichnet testbar: Die 11.570
mana_payment-Zeilen mit der Regel beantworten und gegen die
Solver-Antworten vergleichen (Agreement-Rate).
Kleinster erster Schritt: Formen-Zensus auf den 11.570 Zeilen, dann
feste Regel für die häufigste Zahlungsform (keine volle
Optionsbewertung für diese Form).
Messung: vermiedene Solver-Bewertungen + gepaarte Spiele (Wall-Time
ist Last-Rauschen — primär Entscheidungsvolumen, nicht Zeit).
Win-Rate: UNDECIDED erwartet (Geschwindigkeits-, keine
Qualitätsänderung); ändert die Regel Antworten, ist das eine
Korrektheitsfrage, kein Speed-Gewinn.
Dead-End: häufigste Form deckt <20 % der Zeilen ab (Fragmentierung)
oder Agreement mit dem Solver <99 % (Korrektheitsrisiko).

### 2. P0-2 — Bedrohungs-Leiter statt flacher Linearkombination (target)

Reichweite: 1.134 Ziel-Entscheidungen, 884 mit Wahl (36,9/Spiel).
Python-only (Ziel-Score). Aufgezeichnet testbar: Die 884
Multi-Options-Zeilen mit Leiter vs. aktuellem Combo bewerten,
geänderte Sieger zählen.
Kleinster erster Schritt: Leiter für genau eine Dimension (Uhren/
Dringlichkeit — von P0-2 explizit als fehlend benannt), Rest bleibt
Linearkombination.
Messung: Ziel-Fehler-Metrik à la #1004 (falsche Seite, Geschenke an
den Schwächsten) auf gepaarten Spielen; Win-Rate UNDECIDED, sofern
der Effekt nicht ≥25 Punkte erreicht.
Dead-End: geänderte Sieger <5 % der Multi-Options-Zeilen, oder die
Ziel-Fehler-Metrik bewegt sich auf gepaarten Spielen nicht.

### 3. P1-2 — Postcombat-Default für Sorcery-Permanents (priority)

Reichweite: 1.186 Kandidaten (49,4/Spiel) + 45 Wipe-Angebote.
Python-only (Timing-Politik, #1010-Familie). Aufgezeichnet NICHT
voll validierbar (Verschiebung ändert den Zustand) — gepaarte
Spiele sind Pflicht.
Kleinster erster Schritt: Postcombat-Default nur für
Sorcery-Permanents (das von #1010 explizit nicht implementierte
Stück); Last-Window-Draw und Wipe-Timing bleiben draussen.
Messung: Spells/Spieler-Runde + bad-idle-main à la #1010 (24 Paare
sehen ab ca. 0,07); Win-Rate UNDECIDED unterhalb ~25 Punkte.
Dead-End: Spells/Runde bewegt sich <0,07, oder bad-idle-main
verschlechtert sich. Hinweis: Der Mana-Hold-Teil dieser Familie
ist 4a-2 (in flight) — nicht doppelt bauen.

### 4. P8-Rest — Ob-überhaupt-angreifen + sequenzielle Blocker (declare_attacker/blocker)

Reichweite: 1.892 Entscheidungen (78,8/Spiel). Python-only.
Aufgezeichnet nur teilweise validierbar (Angriffs-/Block-Wahl
ändert den Zustand).
Kleinster erster Schritt: nur das Ob-überhaupt-Angreifen als ein
Gate (nicht das volle sequenzielle Blocker-Redesign).
Messung: Lethal-Runden + Blocks/Chumps à la #1006 auf gepaarten
Spielen; Win-Rate UNDECIDED unterhalb ~25 Punkte.
Dead-End-Risiko, explizit: Die Familie hat bisher kaum geliefert
(#1022: 42/48 bit-identisch; Attack-Planning: kein Hebel gefunden).
Dead-End: gepaarte Spiele ≥80 % bit-identisch, oder keine Metrik
bewegt sich — dann ist der Rest ebenfalls zu verwerfen, nicht
weiter zu verfolgen.

### 5. P0-3 — Trigger-Ordnung als Klassenregel statt Label-Wortsuche (trigger_order)

Reichweite: 184 Entscheidungen (7,7/Spiel), alle mit Wahl (100 %
multi-option) — klein, aber scharf. Python-only, klar umrissen.
Aufgezeichnet voll testbar: Alle 184 Zeilen mit Klassenregel vs.
aktuelle Wortsuche beantworten, Abweichungen zählen.
Kleinster erster Schritt: Klassenregel für die häufigste
Trigger-Klasse in den 184 Zeilen (Zensus zuerst).
Messung: primär Replay-Abweichung + gezielte Unit-Tests (eine
Spiel-Metrik für Trigger-Ordnung gibt es nicht); Win-Rate
UNDECIDED. Leitplanke: Die Regel muss klassenbasiert bleiben —
karten-spezifische Listen sind per Research explizit nicht zu
lehren.
Dead-End: Wortsuche stimmt auf >95 % der Zeilen mit der
Klassenregel überein (kein Raum), oder die Regel braucht doch
karten-spezifische Listen.

### Nächste Reihe (nicht Top 5, aber benannt)

- P3 bepreiste May-Fähigkeiten: 79 Zeilen (3,3/Spiel) — klein,
  scharf, replay-testbar; nach P0-3 der nächste Kandidat.
- P10/P1-4 X-Breakpoints: 148 Zeilen, davon 32 mit X>0 —
  Dosierung hängt an denselben 32 + multi_amount.
- P11/P1-5 Mulligan DevScore: 139 Zeilen, aber blockiert ohne P6
  (Handmerkmale fehlen im Dump) — erst P6, dann DevScore.
- P5/P6/P7 (Profiling, Instrumentierung, Transkript-Schema):
  Infrastruktur, keine Spiel-Hebel — P6 ist Voraussetzung für
  P11-DevScore und für jede künftige Hand-Messung (inkl. 4a-2).

## 5. Anhang: Kommandos, Dump-Inventar, Tests

### Kommandos (alle gesehen, wt-1029 @ 6fb26071b, sofern nicht anders genannt)

Tests (Issue-Vorgabe):

```
PYTHONPATH=src TMPDIR=~/workspace/tmp/pytest-tmp python -m pytest tests/unit -q -k "pilot_request_corpus or pilot_reach_report"
→ 15 passed, 3228 deselected (gesehen 2026-10-26, wt-1029)
```

Aufnahme, je Seed (Skripte liegen diesem Bericht bei:
`run_seed.sh`, `chain-1029.sh`):

```
bash run_seed.sh <worktree> <jar> <tag> <seed>
# = PYTHONPATH=src python -u scripts/pilot_request_corpus.py record --all \
#     --jar <jar> --seeds <seed> --out ~/workspace/tmp/1029/dump-<tag>-seed<seed>.jsonl.gz
# worktree: wt-1029 (tag main) bzw. wt-1029-pre1010 (tag pre)
# jar: wt-1029/engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar (sha eca822d2…)
# Kette: pre 2–6, dann main 2–24, strikt sequenziell, je Seed eigenes Log,
#   resume-fähig (vorhandene Dumps werden übersprungen), gzip-Check je Seed.
#   Ketten-Log: chain-1029.log; 28/28 Seeds OK, 0 FEHLT.
```

Merge + Zählung:

```
python3 merge_dumps.py dump-main-merged.jsonl.gz dump-main-seed{1..24}.jsonl.gz
python3 merge_dumps.py dump-pre-merged.jsonl.gz dump-pre-smoke.jsonl.gz dump-pre-seed{2..6}.jsonl.gz
PYTHONPATH=src python3 analyze_dump.py dump-main-merged.jsonl.gz   # → analysis-main.json
PYTHONPATH=src python3 analyze_dump.py dump-pre-merged.jsonl.gz    # → analysis-pre.json
# Merge asserts: gleiche jar_sha256 + gleiche corpus_version über alle Scheiben (beide OK).
```

### Dump-Inventar (lokal, NICHT mitgepusht — 84 MB gzip, binär; die
Kommandos oben reproduzieren sie)

- `dump-main-merged.jsonl.gz`: 24 Spiele (Seeds 1–24), 70.874
  Entscheidungen, 65,37 MB, jar eca822d2…, corpus v1, pod real.
  Einzelseeds: 1.886–4.556 Entscheidungen/Spiel (Median 2.842).
- `dump-pre-merged.jsonl.gz`: 6 Spiele (Seeds 1–6), 24.105
  Entscheidungen, 18,56 MB, jar eca822d2…, corpus v1, pod real.
  Einzelseeds: 2.307–8.029 Entscheidungen/Spiel (Median 3.478;
  Seed 3 mit 8.029 ist ein sehr langes Spiel, kein Fehler).
- Preflight: Main Seed 1 vor der Kette einzeln aufgenommen (Exit 0,
  2.947 Entscheidungen, Phase-4a-Profil post-#1010) — erst danach
  startete die Kette.
- Katalog-Lücken (`instant_casts_unknown_type`): Main 14 von 244
  Instant-Casts (5,7 %), Pre 3 von 92 (3,3 %) — aus Zähler und
  Nenner der Phase-4a-Regel ausgeschlossen, kein Setup-Fehler.

### Was NICHT getan wurde

- Kein Pilot-Code geändert (Report only, Vorgabe des Issues).
- Keine `engine-bridge/**`-, `qualification/`-, `config/`- oder
  Workflow-Änderungen; keine Collection-Daten gelesen oder zitiert.
- Keine exakte 186/313-Reproduktion auf denselben Spielen (andere
  Seeds — s. §3, erklärte Abweichung).
- Keine Merges. Merge = Hans' Schritt (gilt auch für Folge-PRs aus
  diesem Ranking).
