# Deep Research: Was gute Commander-Spieler bei Entscheidungen einbeziehen — und was davon unser Pilot lernen kann

- **Stand:** 2026-10-25. **Neue Datei, neues Verzeichnis:** Dieser Bericht liegt ausschließlich unter `~/workspace/tmp/pilot-decision-research/REPORT.md`. Der alte Pilot-AI-Handoff (`handover/2026-10-24/pilot-ai/`) und alle anderen alten Berichte wurden nur gelesen, nie ergänzt, überschrieben oder angehängt (Hans-Vorgabe, AGENTS.md Nr. 14).
- **Grundlagen (nur gelesen, nichts verändert):**
  - Teil 1 (externe Landkarte): [part1_external.md](sandbox://workspace/tmp/pilot-decision-research/part1_external.md) — Evidenzklasse: **externe Quelle**, nie eigene Messung.
  - Teil 2 (Pilot-Ist-Stand): [part2_pilot_state.md](sandbox://workspace/tmp/pilot-decision-research/part2_pilot_state.md) — Evidenzklasse: **CODE_DERIVED**, gelesen aus Worktree `wt-maxreview2` @ `217c34d95` (#1007); Haupt-Clone `4f3af5ea7` enthält die #1007-Pilot-Dateien nicht.
  - Soll-Vergleich: Pilot-AI-Handoff `handover/2026-10-24/pilot-ai/HANDOFF.md` §§2–4 + `RESEARCH.md` (nur gelesen).
- **Vorschläge in Teil 3 sind VORSCHLÄGE**, keine Umsetzung, keine Messung. Jede Zahl, die als gemessen klänge, wäre falsch — hier steht keine.
- **Feste Leitplanken für alle Vorschläge (gesetzt, nicht verhandelbar in diesem Bericht):**
  - XMage ist die einzige Rules Engine; der Pilot wählt nur unter engine-angebotenen legalen Optionen, nur mit aktor-scopeden Informationen (kein Handlesen, keine versteckten Informationen).
  - Kein MCTS / keine Suche: bei ms-Budget ausgeschlossen (Handoff-Urteil, doppelt belegt).
  - Keine Deals, kein Kingmaking-, Trotz- oder Vergeltungs-Term (Handoff §7-Leitplanke) — Politics wird nur als Ausrichtung/Sichtbarkeit modelliert, nie als bindender Deal.
  - Band-Trennung: Unsere Pods sind High-Power-Casual (RogShai-/Chulane-Zieldecks, Real-Pod, Precon-Pods) — **keine cEDH-Regeln ungefiltert importieren** (insbesondere nicht: cEDH-Default-Mulligan, cEDH-Counter-Sparen nur für Win-Versuche, frühes Countern jeder Draw-Engine).
  - Determinismus: Jede neue Komponente muss deterministisch bleiben (Semantic Replay Tape); keine Zufalls- oder Zeit-Abhängigkeit in der Entscheidung.

---

## 1. Entscheidungs-Landkarte (kondensiert aus Teil 1)

Was starke Spieler einbeziehen — pro Dimension, mit der schärfsten Quelle. Band in Klammern.

| # | Dimension | Was Profis einbeziehen (Kern) | Schärfste Quelle |
|---|---|---|---|
| 0 | Rollen (Beatdown / Control / Scavenger) | Wer hat Inevitability (gewinnt das lange Spiel)? Rolle zuerst bestimmen, dann jede Einzelentscheidung daran ausrichten; Rollenwechsel, sobald sich die Late-Game-Balance dreht; im Multiplayer dritte Rolle Scavenger (zurücklehnen, andere sich abnutzen lassen, Reste einsammeln); angefangene Kills zu Ende bringen, nicht zu viele Spieler anstupsen | Flores „Who's the Beatdown?" (1999); SCG Multiplayer-Erweiterung (Archiv, Abruf 2026-10-25) — **keine moderne Commander-Neufassung** (Lücke L6) |
| 1 | Threat Assessment + Leiter | Nicht „meiste Leben", sondern: Wer gewinnt, wenn ihn niemand stoppt? Leiter (Casual/High-Power, AetherHub 2025-06-03): gewinnt-sofort > Mana-Engine > Draw-Engine > mächtiger Commander > Teil-Combo > wiederholbare Interaktion > Stax (trotz niedriger Nummer: „sooner rather than later") > breites Board > große Kreatur mit Schutz > große Kreatur mit Evasion. Karten- und Mana-Rate vor Lebensstand und Boardgröße; Leben ist nur die Uhr | AetherHub 2025-06-03; EDHREC 2026-01-13; cEDH-Verschärfung: Learn cEDH (6 Leitfragen, laut vs. leise, Phase, geteilte Verantwortung) |
| 2 | Ressourcen | Leben als Ressource (nur der letzte Punkt zählt; Leben gegen Karten/Mana tauschen, solange die Uhr es zulässt); Karten-Vorteil, Tempo, Mana-Effizienz (im selben Zug entwickeln UND Interaktion offenhalten); eigene Antworten sind knapp (~12 Single-Target + ~5 Massen als Richtwert) — nicht der einzige Antwortende sein | EDHRECast 383; EDHREC 2026-01-13; Sperling/TopDeck (Mana als Engpass, cEDH) |
| 3 | Combat | Blocker = Value-Verweigerung (nicht nur Lebensschutz): Combat-Trigger, Treasures, Commander-Schaden verweigern; Toughness 4 als Sweet Spot, First Strike + Deathtouch als Trade-Maschinen; Crackback: wer ohne Blocker voll ausschwingt, lädt Gegenschaden ein; cEDH: Naus-Spieler per Combat unter Druck setzen (Leben = Naus-Treibstoff), Spieler-Entfernung als stärkste Interaktion; Commander-Schaden als zweite Uhr (21, kumulativ, Lifegain löscht nicht) | Card Kingdom 2024-02-12 (Casual); Commander's Herald „Combat in cEDH" 2024-10-26. **Keine quantitative Crackback-Formel in der Literatur** (Lücke L2) |
| 4 | Politics | Deals als Tausch mit Gegenleistung (nie als Gefallen); Deal-Treue (wer bricht, bekommt keine mehr); Blame-Shifting („Was ist die größte Bedrohung?" — Antwortender wird Zielgeber); Aggro-Verteilung: fokussieren und zu Ende bringen (SCG) vs. streuen, um nicht als Threat zu gelten (EDHREC) — **ohne Auflösungsregel** (Lücke L9); Kingmaking-Verbot; Archenemy-Effekt (wer zuerst scary wird, gewinnt selten) | AetherHub Politik-Guide; Culture of Gaming; SCG Multiplayer |
| 5 | Timing | „Playing it cool" (Noise-Modell, EDHREC 2025-11-27): Lautstärke managen — nicht so laut wie der Führende, aber lauter als die übrigen; nach der Recovery-Phase schließen. cEDH-„Window": gewinnen, wenn Gegner ausgetappt / Interaktion verbraucht ist, nicht so früh wie möglich; Prioritäts-Disziplin (nicht vorschnell countern, damit ein Gegner seine Interaktion ausgibt); Ausnahme „play to your outs" (einziger Antwortender muss antworten). Boardwipe-Timing: nicht wipen, wenn man vorn ist; auf Value warten; nach dem Wipe sofort wieder aufbauen | EDHREC 2025-11-27; Learn cEDH „The Window"; EDHREC Intro to cEDH; KrakenTheMeta/DraftSim (Wipes) |
| 6 | Ziel-Priorisierung | Muss weg (sofort): gewinnt-sofort, Mana-/Draw-Engine, späte Win-Vorboten. Soll bald weg: Teil-Combo, wiederholbare Interaktion, Stax, aktiver Commander. Kann bleiben: breites Board ohne Finisher (Wipe-beantwortbar), einzelne blockbare Kreatur, Bedrohung, die primär einen anderen Gegner trifft (ihn antworten lassen). Deck-Kenntnis schlägt Kartenstärke; Hedging in Turn-Order, aber nicht auf fremde Antworten pokern | AetherHub 2025-06-03; CoolStuffInc „The Problem with Removal" (2024-10-23); EDHREC-cEDH-Interaktionsleitlinie 2026-01-13 |
| 7 | Mulligan | Casual: Funktionalität zuerst (2–4 Länder, Sweet Spot 3; Farben bis Zug 3/4; frühe Plays Zug 1–3; Plan-Förderung; keine Wincon in der Starthand nötig). cEDH (NICHT übertragbar): Default ist Mulligan; Keep-Rangliste Sperling: Truly Broken > Development > (Breakpoint) > Interaction > Card Advantage; Non-Functional-Avoidance ist KEIN Keep-Grund | EDHMeta; MTGComboTrainer; CoolStuffInc 2013-08-05 (Casual) vs. Sperling/TopDeck (cEDH, schärfster Band-Gegensatz im ganzen Material) |
| 8 | Trigger-Ordnung | Nur APNAP-Regel (aktiver Spieler zuerst, LIFO; eigene Trigger selbst ordnen) + Andeutung („time combos on opponents' turns"). **Keine Prioritätenlehre** für typische Paare (Draw-vor-Sacrifice, Drain-vor-Rekursion, May-Reihenfolge) — Lücke L4. May-Entscheidungen: keine eigene Literatur (nur Steuer-Abwägung ohne Schwelle, Gefangenendilemma bei Gegner-May) — Lücke L5 | DraftSim „The Stack"; CopyProgramming Stack-Guide; CR 603/117 (Stand Jan 2026) |
| 9 | Zahlung / X | Nur Regeltexte (X annoncieren, X=0 bei kostenlosen Casts) + ein Maßhalte-Prinzip (Necro 10 statt 25/30 — dosiert, nicht maximal). **Keine X-Breakpoint-Lehre, keine Pay-any-amount-Lehre, keine Mana-Zahlungsreihenfolge, keine Kicker-Lehre** — Lücke L3 | MTG Wiki / CR 107.3; Sperling (Maßhalten) |
| 10 | Combo-Erkennung / -Disruption | Teil im Spiel = Signal (proaktiv entfernen, Casual) bzw. Win-Versuch abwarten (cEDH: Counter nicht zu früh verbrauchen); Vorboten (Silence, Grand Abolisher, Ranger-Captain) = sofort interagieren; Deck-Kenntnis (Citadel + Reservoir in K'rrik = muss weg); Ressourcen-Signale (viele gezogene Karten + Tutoren = Setup); Redundanz-Regel (zweiter Versuch nach gestopptem ersten aufbauen) | AetherHub 2025-06-03; Learn cEDH; CoolStuffInc; ProxyKing |
| 11 | Wincon-Bewertung | Eigene: Plan + Alternative (linearer Plan brickt → Alternativ-Wincon nötig, Hipsters 2019); Closer passend zur Strategie; Midgame-Check, ob die Linie noch trägt. Fremde: Uhr lesen, nicht Board lesen (Hand, offenes Mana, Tutoren, Friedhof); „Game Winner" (eine Antwort stoppt ihn, wenn man die ermöglichende Ressource trifft) vs. „Game Changer" (strukturell, nicht mit einer Antwort erledigt). Abwägung: fremden Gewinner racen oder verlangsamen — wenn Störung billig, stören; wenn teuer, auf eigene Strategie fokussieren | Hipsters of the Coast 2019-09; Culture of Gaming 2026-01-19; AetherHub „When You're The Threat" 2025-06-03; EDHREC Philosophie |
| 12 | Risiko | Fünf qualitative Abwägungen, keine Formel: Overextension vs. verpasste Value; Archenemy-Risiko vs. Tempo-Verlust; Antworten verbrauchen vs. sparen; auf fremde Antworten wetten vs. selbst antworten; Leben als Risiko-Budget. **Keine Wahrscheinlichkeiten, keine Schwellen, keine Erwartungswerte** — Lücke L8 | SCG Multiplayer; EDHREC Playing it Cool 2025-11-27; EDHREC Intro to cEDH; CoolStuffInc Mass-Removal |

---

## 2. Ist-vs.-Soll-Mapping (Pilot heute vs. Landkarte)

Status: **MODELLIERT** = eigene Regel/Komponente mit benannten Inputs; **HEURISTISCH** = Proxy-Term/Schwelle, kein eigenes Modell; **FEHLT** = in den gelesenen Dateien nicht gefunden. Details + Zeilenbelege in Teil 2.

| Dimension | Ist-Stand (CODE_DERIVED) | Lücke zum Soll |
|---|---|---|
| Threat / Leiter | HEURISTISCH: `player_threat` = Board*0,35 + Power*0,25 + Länder*0,15 + Hand*0,3, × (0,6+0,4·Life/40); Archenemy nur bei ≥4,0 und ≥25 % über Zweitem | Keine Funktions-Leiter, keine Uhren (Leben / Commander-Schaden / Kombo), kein Betrifft-mich-Faktor, keine `meinScore − maxGegner − λ·Mittel`-Aggregation |
| Ressourcen | MODELLIERT (Utility): 11 Komponenten (`survival`, `mana_efficiency`, `card_advantage`, `tempo`, `engine_development`, `interaction_reserve`, `commander_value`, `threat_reduction`, `win_progress`, `political_visibility`, `rebuild_capacity`); Leben linear, keine Mehr-Züge-Planung | Keine Planung über Züge (Mana-/Karten-Budget), Leben als Ressource (Bezahlen mit Leben) kein Modell außer Withhold-Gates |
| Combat Angriff | MODELLIERT: `attack_score` („Imagine the Worst"), Lethal +3,0, Fokus-Verteidiger +0,6 | Fokus gilt für ALLE Angriffe (keine Commander-Bündelung vs. Verteilen); Crackback nur boolesches Gate (−1,2), kein summierter Term |
| Combat Block | MODELLIERT: `BlockRound` (Urgent/settled, Commander-Lethal ab 21, Anti-Doppel-Chump, Fail-closed-Leiter) | Dritter Handoff-Ast („Chump kauft genau den Gewinn-Zug") nicht als Regel gefunden |
| Politics / Aggro | HEURISTISCH: `political_visibility` (Negativgewicht −0,15/−0,5/−0,7/−0,85); Aggro nur via `focus_defender` | Kein positives Politics-Modell (bewusst: kein Deal-/Trotz-Term per Leitplanke); keine relative Noise-Modellierung, keine Ausrichtungs-Erkennung |
| Ziel-Priorisierung | MODELLIERT (Seite + Wert + Commander-Uhr): Seite ±8, Wert ±0,5×, Commander-Uhr-Bonus 6,0·min(1,taken/21) + 8,0 bei nächstem Hit = 21, `life_clock` quadratisch, Removal-Worth 3,0, Counter-Worth (Commander 10,0) | Keine Funktions-Leiter, kein Betrifft-mich-Faktor (Stax nur hoch, wenn es den Akteur sperrt), Commander-Uhr nur additiver Bonus, kein allgemeiner Ziel-Score |
| Timing | HEURISTISCH: `_instant_timing` (−0,5 eigene Main / +0,6 Gegner-End-Step), `_curve_bonus` (bis +1,0), Pass floor 0,15, `interaction_reserve`-Bonus, `should_take_reaction`-Schwelle fix 0,5 | Keine Postcombat-Gates, keine letzten-Fenster-Gates, keine Wipe-Timing-Regel (nicht wipen, wenn vorn; auf Value warten; Rebuild-Vergleich), keine Window-Erkennung (ausgetappte Gegner) |
| Mulligan | MODELLIERT (Worktree-Stand, Phase 2): Castability-Modell (Least Squares, 58.500 Hände, R² 0,33), Keep-Marge 1,0, Land-Staffel-Bottoming, Forced-Keep ab 3 Mulligans | Kein Development Score (Kurve Richtung Deckziel, Commander-Soll-Zug), keine Deck-Parameter außer Commander-Farben, kein Pod-Profil; Haupt-Clone hat noch die ältere landzahl-lastige Fassung |
| Trigger-Ordnung | FEHLT: nur Label-Wortsuche in `_decide_semantic_option` (Rollen aus Wörtern, floor 0,4) | Keine „wertvollster Trigger zuletzt"-Regel, keine Klassenregel, keine Delta-Bewertung |
| Zahlung / X | MODELLIERT: Knappste-Farbe-Ordnung, Vervollständigungs-Solver (DFS, 20.000-Node-Cap), X-Budget `(Budget−Restkosten)//Symbole`, X=0-Zurückhaltung (Phase 4b), Multikicker-Mana-Kappe | Keine Interaktions-Reserve im X, keine X-Breakpoints (Toughness / Leben-minus-Blocker / Reserve), keine Tap-Kosten-Schonung (Blocker/Angreifer), keine May-Nein-Bedingungen, keine Monotonie-Regel bei Stufen |
| Combo | FEHLT: kein Combo-Modell, keine Teil-Erkennung, keine fehlende-Teile-Uhr (nur Paket-Label im Deckbau + Infinite-Loop-Guard) | Nur indirekt via Counter/Removal/Threat; kuratierte Deck-Synergien (Korvold/RogShai `specialist_bonus`) sind keine generische Erkennung |
| Wincon | HEURISTISCH: `win_progress`-Terme (FINISHER, COMBAT_PAYOFF, `expected_lethals`·1,35 gedeckelt 4,5, `protected_finish` +0,9) — **aber die Metadaten werden im Full-Game-Pfad nirgends gesetzt** (Defaults: lethals 0, finish_prob 1,0, protected False) | Kein P(Sieg)-Modell, keine „Gegner gewinnt nächsten Zug ⇒ Verlust außer beantwortbar"-Regel, keine Pfad-Bewertung (Combat / Combo / Value / Commander-Schaden), keine Lethal-Bündelung über Angriffe |
| Risiko | HEURISTISCH: Terme vorhanden (`boardwipe_risk`, `stack_pressure`, `turn_cycle_risk`, `uncertainty_pressure`, `exposure_before_next_turn`) — **aber Full-Game-Inputs teils Konstanten** (Unsicherheiten = 1,0; `commander_denial_risk` ungesetzt = 0; `tokens`/`ramp_mana` = 0; keine Sitzpositions-Rechnung) | Keine Überlebens-Uhr-Regel als Override („eigene Uhr ≤ 1 ⇒ Überleben dominiert"), keine gemessenen Schätzer hinter den Risiko-Term en |
| Querschnitt | `PilotStateView` hat keine Felder für Phase/Step, Stack-Inhalt, Commander-Schaden je gegnerischem Commander, offenes Gegner-Mana, Gegner-Uhren, Deck-/Wincon-Identität | Generische Utility sieht diese Inputs nicht; nur Spezialregeln lesen den rohen State-Dict — jede neue Dimension braucht erst diese Sichtbarkeit, sonst rechnet sie auf Defaults |

---

## 3. „Beibringen"-Mapping (priorisiert, nur Vorschläge)

**Priorisierungs-Logik:** P0 = größter Hebel bei kleinstem Risiko und ohne neue Sichtbarkeits-Architektur (oder mit kleiner, klar umrissener). P1 = großer Hebel, mittlerer Aufwand/Risiko. P2 = theoretisch wichtig, aber schwer validierbar oder risikobehaftet — später, nur mit Messung. Aufwand: S = Tage, M = 1–3 Wochen, L = länger/mehrere PRs (Schätzung, keine Zusage). **Jeder Vorschlag braucht zuerst die Messung aus §4 — ohne sie ist er kein Fortschritt, sondern eine Behauptung.**

### P0 — zuerst (kleiner Aufwand, kleines Risiko, schaltet Vorhandenes frei)

**P0-1 — Wincon-/Risiko-Inputs im Full-Game-Pfad tatsächlich setzen (statt neue Modelle zu erfinden).**
- Was: Die bereits existierenden Utility-Terme mit echten Werten füttern: `expected_lethals`, `finish_probability`, `protected_finish`, `commander_damage_pressure` je gegnerischem Commander, offenes Gegner-Mana, `commander_denial_risk`, `tokens`, `ramp_mana`, Sitzpositions-`exposure_before_next_turn` — alles aus dem rohen State-Dict, das die Spezialregeln heute schon lesen.
- Wie: Schreiber in `full_game_pilot_views.py`/`state.py` ergänzen (keine neue Entscheidungsklasse, keine neue Komponente); Defaults bleiben als Fallback.
- Warum P0: Der Code rechnet heute mit Defaults/Konstanten, obwohl die Daten da sind — das ist der billigste echte Hebel im ganzen Mapping.
- Risiko: Niedrig (nur Sichtbarkeit, keine neuen Gewichte); Fehlschätzung einzelner Inputs dämpft sich über bestehende Caps.
- Messen: Term-Aktivierungsraten (wie oft weichen die neuen Inputs von Defaults ab) + gepaarte Spiele (§4); Erfolg = Aktivierung > 0 ohne Verschlechterung der 17 Metriken, kein Wall-Time-Anstieg über +1 ms/Entscheidung.

**P0-2 — Bedrohungs-Leiter als Ziel-/Threat-Komponente (kategorial, nicht numerologisch).**
- Was: `player_threat` (flache Linearkombination) und Ziel-Score um eine Funktions-Leiter ergänzen, direkt aus Teil 1 §1.2/§6.1: gewinnt-sofort > Mana-Engine > Draw-Engine > aktiver Commander > Teil-Combo > wiederholbare Interaktion > Stax-nur-wenn-es-mich-sperrt > breites Board > große Kreatur. Plus Uhren als Multiplikatoren: Lebens-Uhr (Züge bis Lethal), Commander-Schaden-Uhr (21 − taken), Kombo-Uhr (Teile auf dem Board). Plus Betrifft-mich-Faktor (Stax, das mich nicht sperrt, wird heruntergestuft; Bedrohung, die primär einen anderen Gegner trifft, wird heruntergestuft — „ihn antworten lassen").
- Wie: Neue Klassifikation in `views.py` (Funktions-Tags je Permanent aus Katalog-Rollen + Board-Mustern: wiederholbare Mana-/Draw-Fähigkeiten, Combo-Teil-Kandidaten aus Spellbook-Paketen als Offline-Metadaten) + Leiterwert × Uhr × Betrifft-mich als Term in Threat- und Ziel-Bewertung. Band: Casual-/High-Power-Leiter (AetherHub); cEDH-Verschärfung (sofort vs. sparen) NICHT übernehmen.
- Warum P0: Größte qualitative Lücke im Ist-Stand bei gleichzeitig vorhandener Literatur (Leiter ist kategorial belegt, keine erfundene Formel nötig).
- Risiko: Mittel-niedrig — Fehlklassifikation einzelner Permanents; Gegenmaßnahme: Leiter nur als Bonus/Malus innerhalb bestehender Caps, nie als harter Override; „kann bleiben"-Kategorie explizit (breites Board ohne Finisher, blockbare Einzelkreatur).
- Messen: Geparte Spiele; zusätzlich gezielte Szenario-Fixtures (Board mit Engine vs. Board mit großer Kreatur — Pilot muss die Engine wählen) als Unit-/Integrations-Test, nicht nur Win-Rate.

**P0-3 — Trigger-Ordnung als Klassenregel (klein, regelbasiert, deterministisch).**
- Was: Eigene Trigger so stapeln, dass der wertvollste zuerst resolvt (also zuletzt gestapelt): Klassenordnung Schaden/Entfernung > Ziehen/Selektion > Token/Rekursion > Kosmetik; May-Trigger nur nehmen, wenn ihr Wert-Score ≥ 0 (mit den aus §9 bekannten May-Nein-Bedingungen als Startpunkt: Interaktions-Mana, Deckung, Draw-Punisher, Lebens-Uhr).
- Wie: Neue Spezialregel in `choices.py`/`policy.py` für `trigger_order` (heute nur Label-Wortsuche); Wert aus bestehenden `entry_value`- und Rollen-Daten, keine neue Sichtbarkeit nötig.
- Warum P0: Rein regelbasiert, klein, keine Literatur nötig (APNAP ist Regelwissen) — die Literatur-Lücke L4 ist hier kein Hindernis, sondern der Grund, warum eine einfache Klassenregel der richtige Start ist.
- Risiko: Niedrig; falsche Klassenordnung kostet einzelne Trigger, keine Spiele.
- Messen: Szenario-Fixtures (Trigger-Paare mit bekannter optimaler Ordnung) + gepaarte Spiele (Trigger-Klasse als eigene Metrik in der Auswertung, nicht nur Win-Rate).

**P0-4 — Crackback als summierter Term (statt booleschem Gate).**
- Was: Erwarteter Gegenschaden des nächsten Zuges = Summe über alle übrigen Gegner (offene Angreifer-Power, Evasion, Commander-Uhren) minus eigene verbleibende Blocker nach dem Angriff; dazu Angriffs-Verteilung: Commander-Schaden auf einen Spieler bündeln, Nicht-Commander-Schaden verteilen (Handoff §4.3-Unterscheidung, im Code heute nicht vorhanden).
- Wie: Term in `attack_score` (ersetzt/ergänzt `_crack_back_danger`-Gate); Inputs aus Board-State (bereits lesbar). Keine Literatur-Formel nötig — die Literatur liefert nur Heuristiken (Lücke L2), der Term ist also explizit ein Modell, kein Literatur-Zitat, und muss als solches gemessen werden.
- Warum P0: Combat ist modelliert, aber der Gegenschaden ist die gröbste Vereinfachung darin; der Term nutzt nur vorhandene Inputs.
- Risiko: Mittel-niedrig — Überschätzung von Crackback macht den Piloten passiv; Gegenmaßnahme: Term gedeckelt, Lethal-Angriffe ausgenommen (wie heute beim Gate).
- Messen: Geparte Spiele mit Combat-Metriken (attacks, blocks, Lebensverlust durch Crackback, Win-Rate); Szenario-Fixtures (Angriff mit/ohne Blocker-Reserve).

### P1 — danach (mittlerer Aufwand, klarer Hebel)

**P1-1 — Combo-Teil-Erkennung + Disruptions-Timing (band-bewusst).**
- Was: Teil-Combo auf dem Board erkennen (Spellbook-Pakete als Offline-Metadaten, Meta-Lane PR5-Snapshots als Quelle; kein Laufzeit-API) → Dringlichkeits-Bonus für Removal/Counter gegen das Teil + „fehlende-Teile-Uhr" (wie viele Züge hat der Gegner statistisch, das zweite Teil zu finden — aus Draw-Rate, nicht aus Handwissen). Timing band-bewusst: In unseren Pods proaktiv auf das Teil (Casual-Regel, AetherHub), NICHT die cEDH-Regel (Win-Versuch abwarten, Counter sparen) übernehmen.
- Wie: Neue Erkennung in `views.py` (Board-Muster gegen Paket-Liste) + Bonus in Ziel-/Counter-Wertung; Vorboten-Regel (Silence/Grand-Abolisher-ähnliche Effekte vor Win-Versuch = sofort interagieren) als Spezialfall.
- Risiko: Mittel — False Positives (harmlose Synergie als Combo lesen) führen zu verschwendeter Interaktion; Gegenmaßnahme: Bonus nur bei zwei unabhängigen Signalen (Teil + Vorbote/Draw-Rate) oder bei Deck-Kenntnis aus dem Meta-Wissen.
- Messen: Geparte Spiele; Szenario-Fixtures (Teil auf dem Board → Pilot entfernt es vor Value-Karten); Fehlalarm-Rate in Replays (wie oft wurde ein Nicht-Combo-Teil als Combo behandelt).

**P1-2 — Timing-Gates (Postcombat-Default, letzte Fenster, Wipe-Timing).**
- Was: (a) Sorcery-speed, nicht-dringende Plays defaultmäßig postcombat (Ausnahmen: Haste/Anthem/Equip/Blocker-Entfernung precombat, Handoff-Ausnahmenliste); (b) Draw auf den letzten Gegner-End-Step, Feuern bei ausgetapptem Gegner (Window-Erkennung light: offenes Gegner-Mana + Interaktions-Vermutung, keine Handinformation); (c) Wipe-Timing: nicht wipen, wenn man vorn ist; auf Value warten (Anzahl getroffener Kreaturen); Rebuild-Vergleich (wer baut nach dem Wipe schneller wieder auf — Mana-/Karten-Vorsprung).
- Wie: Gates in `priority.py`/`views.py` (Phase/Step sind im rohen State-Dict lesbar; `PilotStateView` braucht sie nicht, wenn die Gates als Spezialregeln laufen — sonst P0-1-Erweiterung um Phase/Step).
- Risiko: Mittel — zu starre Gates kosten Tempo; Gegenmaßnahme: Gates als Defaults mit Override bei Dringlichkeit (Lethal, Win-Versuch, Archenemy-Druck).
- Messen: Geparte Spiele mit Timing-Metriken (`bad_idle_main_with_castable_spell`, `bad_idle_main_with_unplayed_land`, spells/player-round, Wipe-Qualität: getroffene Kreaturen je Wipe, Rebuild-Züge).

**P1-3 — Interaktions-Disziplin / geteilte Verantwortung (ohne Deals, ohne Kingmaking).**
- Was: „Nicht der einzige Antwortende sein" als Regel: Wenn eine Bedrohung primär einen anderen Gegner trifft UND dieser in Turn-Order vor dem Akteur noch antworten kann UND der Akteur nicht der einzige Antwortende ist, passt der Pilot (lässt den anderen antworten). Ausnahme „play to your outs": Ist der Akteur der einzige plausible Antwortende, muss er antworten. Keine Deals, keine Absprachen, keine Rache — nur Turn-Order- und Betroffenheits-Logik aus öffentlichen Informationen.
- Wie: Term/Gate in der Priority-Entscheidung (Betroffenheit je Gegner aus Leiter × Uhr; Turn-Order aus Sitzposition + Phase).
- Risiko: Mittel — wenn alle passen, gewinnt der Bedrohende; Gegenmaßnahme: die „play to your outs"-Ausnahme + Dringlichkeitsschwelle (gewinnt-sofort wird immer beantwortet, egal wer sonst könnte).
- Messen: Geparte Spiele (`counters_cast`, `removal_targets`, verbrauchte vs. gesparte Interaktion, Win-Rate); Szenario-Fixtures (Bedrohung trifft Gegner A, Pilot ist nicht dran → Pass; Pilot ist einziger Antwortender → Counter).

**P1-4 — X-Breakpoints + Pay-any-amount-Dosierung (statt Budget-Maximum).**
- Was: X nicht nach „so viel wie möglich", sondern nach Breakpoints bemessen: X = Toughness des Ziels / Leben des Gegners minus Blocker / Mana, das für Interaktion zurückbleiben muss (Reserve abziehen, heute: keine Reserve im X). Pay-any-amount dosiert (Necro-Prinzip: so viel wie nötig, um den Plan zu sichern und danach handlungsfähig zu bleiben, nicht maximal).
- Wie: Erweiterung von `_announce_x_affordable_max` / `_decide_numeric` um Breakpoint- und Reserve-Logik; Reserve aus Hand-Interaktionskosten (lesbar) statt aus nichts.
- Risiko: Niedrig-mittel — zu kleine X verlieren Value; Gegenmaßnahme: Breakpoints nur, wenn sie aus öffentlichen Informationen ableitbar sind (Ziel-Toughness, Leben, Blocker), sonst Budget-Maximum als Fallback.
- Messen: Geparte Spiele (X-Zauber-Ergebnisse, Pay-any-Completions, abgebrochene Casts); Szenario-Fixtures (X = Toughness, X mit Reserve).

**P1-5 — Mulligan: Development Score + Pod-Profil (Phase-2-Modell erweitern, NICHT cEDH-Default).**
- Was: Zum Castability-Modell (Phase 2) einen Development Score ergänzen: Kurvenspielbarkeit der Hand Richtung Deckziel (Commander-Soll-Zug, frühe Plays Zug 1–3, Plan-Förderung) + Pod-Profil (Casual/High-Power-Regel „funktional = keep" — ausdrücklich NICHT Sperlings cEDH-Rangliste und NICHT „Default ist Mulligan").
- Wie: Neue Features in `should_keep_opening_hand` (Deckziel aus Meta-Wissen/Commander, Kurven-Features aus Hand); Parameter aus eigenen Replay-Analysen kalibrieren (wie Phase 2: Least Squares auf gezogenen Händen), nicht aus cEDH-Literatur übernehmen.
- Risiko: Mittel — Mulligan-Fehler kosten ganze Spiele; Gegenmaßnahme: neue Features zuerst als kleine Gewichte neben dem bewährten Castability-Modell, A/B gegen Phase-2-Baseline.
- Messen: Lineal (195 Precons × 100 Hände, wie Phase 2) + gepaarte echte Spiele (Mulligans/Spieler, Commander bis T6, spells/player-round, Win-Rate); kein Merge ohne Lineal- UND Spiel-Vergleich (Pilot-Regel: ≥10 Seeds Real-Game-Vergleich).

**P1-6 — Relative Noise / Sichtbarkeits-Modell (statt flacher Visibility-Strafe).**
- Was: `political_visibility` (heute: flache Strafe für auffällige Aktionen) durch ein relatives Modell ersetzen: Lautstärke je Spieler (Board + Engines + letzte Aktionen); Zielkorridor = lauter als die übrigen, leiser als der Führende; nach der Recovery-Phase (Führender gestoppt) darf der Pilot laut werden und schließen. Kein Deal-, kein Rache-Term (Leitplanke bleibt).
- Wie: Noise-Score je Spieler in `views.py` + relativer Term in der Utility (Abstand zum Führenden, Abstand zum Rest).
- Risiko: Mittel-hoch — soziale Dynamik ist im 4-Spieler-Sim schwer zu validieren; Noise ist ein Modell, kein Literatur-Zitat mit Zahlen (EDHREC liefert nur das Konzept, keine Gewichte).
- Messen: Geparte Spiele (Archenemy-Häufigkeit: wie oft wird der Pilot zum Führenden und dann fokussiert; Win-Rate; „erster Scary-Spieler gewinnt selten"-Check in Replays).

### P2 — später, nur mit Messung (theoretisch wichtig, schwer validierbar)

**P2-1 — Rollen-Modell (Beatdown / Control / Scavenger) als Meta-Policy.**
- Was: Rolle aus Inevitability (eigene Late-Game-Engine vs. Gegner-Engines) + Deckgeschwindigkeit bestimmen; Rolle treibt Aggro-Fokus (Beatdown: fokussieren + zu Ende bringen), Zurückhaltung (Control: nur echte Bedrohungen beantworten, kleine Hits einstecken) oder Scavenger-Verhalten (Abschreckung legen, andere sich abnutzen lassen); Rollenwechsel, sobald sich die Balance dreht.
- Warum nur P2: Flores warnt selbst — Fehlzuweisung der Rolle = Spielverlust; und es gibt keine moderne Commander-Neufassung (Lücke L6). Ein falsches Rollen-Modell schadet mehr als kein Modell.
- Wie (wenn): Rolle als Meta-Parameter, der Gewichte in `_base_components` (Tempo vs. Survival vs. Win-Progress) und `focus_defender` moduliert; Rollenwechsel nur bei klaren Schwellen (Inevitability-Wechsel), mit Hysterese (kein Flattern).
- Messen: Geparte Spiele + Rollen-Logs (wie oft wechselt die Rolle, korreliert Wechsel mit Win-Rate); Abbruch-Kriterium: Rollen-Modell ohne Win-Rate-Verbesserung = verwerfen, nicht behalten.

**P2-2 — Externe Priors als Startwerte (EDHREC-Synergie, Playgroup-Tiers, Expertenrankings) — nur mit Meta-Lane-Guardrails.**
- Was: Externe Priors als kleine, gedeckelte Startwerte für Funktions-/Ziel-Priors und Mulligan-Features (Meta-Lane-Design: Tier A ≤0,45, Tier B ≤0,30, Tier C = 0,0; nie im Scoring als harter Wert; Veto-Regel: eigene gepaarte Spiele schlagen jeden Prior; Stale-Flag nach 12 Monaten).
- Warum nur P2: Popularität ≠ Stärke, Band-Bleed (cEDH-Daten in Casual-Empfehlungen), Veraltung — die Guardrails existieren als Design (Meta-Lane Phase 1), sind aber noch nicht implementiert (PR1–PR7). Priors ohne Guardrails sind ein Risiko, kein Hebel.
- Messen: Wie P1-5 (Lineal + gepaarte Spiele); zusätzlich Prior-Ablation (mit/ohne Prior bei sonst gleichem Piloten).

**P2-3 — Risiko-Quantifizierung (Erwartungswerte statt Heuristiken).**
- Was: Die fünf qualitativen Risiko-Abwägungen aus Teil 1 §12 in Schätzer übersetzen (Wipe-Wahrscheinlichkeit aus Gegner-Hand + Mana, Crackback-Erwartung aus P1-4-Term, Archenemy-Wahrscheinlichkeit aus Noise-Modell P1-6).
- Warum nur P2: Die Literatur liefert keine Wahrscheinlichkeiten (Lücke L8) — jede Zahl wäre ein Modell, das erst aus eigenen Replays kalibriert werden müsste (Kalibrierungs-Paare, Beobachtungs-Zählungen). Ohne Kalibrierung ist das Raten mit Zahlen.
- Messen: Kalibrierungs-Güte zuerst (vorhergesagte vs. beobachtete Häufigkeiten in Replays), dann gepaarte Spiele.

### Explizit NICHT zu lehren (mit Begründung)

| Nicht lehren | Warum |
|---|---|
| cEDH-Default-Mulligan („Mulligan ist Default, Keep braucht Grund") | Band-Fehler: Unsere Pods sind High-Power-Casual; dort gilt „funktional = keep". Sperlings Rangliste würde in unseren Pods systematisch zu viele Hände wegwerfen. |
| cEDH-Counter-Sparen („nur Win-Versuche countern, sonst sparen") | Band-Fehler: In langsameren Pods ist frühes Beantworten von Engines richtig (AetherHub-Leiter); striktes Sparen lässt Engines ungestört wachsen. |
| Deals / bindende Absprachen / Kingmaking-/Rache-Terme | Handoff-Leitplanke §7 + nicht modellierbar ohne Kommunikation (der Pilot spielt ohne Chat/Deals); Ausrichtung über öffentliche Informationen (P1-3) ist der legitime Ersatz. |
| MCTS / Suche / Rollouts | Budget: bei ms-Budget ausgeschlossen (gesetzt, doppelt belegt); alle Vorschläge oben sind O(1)-Terme oder kleine Solver mit Caps (wie der bestehende 20.000-Node-Cap). |
| Handlesen / versteckte Informationen | Regel: Pilot sieht nur aktor-scopede Informationen; Bedrohungseinschätzung aus öffentlichen Informationen (Board, Friedhof, Mana, Leben, Uhren) — nie aus Gegner-Hand. |
| Karten-spezifische Prioritätenlisten („entferne X vor Y") | Die Literatur liefert keine (Teil 1 §6.1); eine solche Liste wäre erfunden. Stattdessen: Funktions-Leiter (P0-2) + Deck-Kenntnis aus Meta-Wissen. |

---

## 4. Messprotokoll (wie man zeigt, dass ein Vorschlag hilft)

Übernommen aus dem M4-/Phasen-Protokoll (Handoff §§5–6, M4-Erkenntnisse), angepasst auf Entscheidungs-Lehren:

1. **Gepaarte Seeds, gleiches JAR, gleiche Pods:** Jede Änderung wird gegen die unveränderte Baseline auf denselben Seeds und Pods gespielt (Real-Pod + Precon-Pods); CRN-Effekt beachten (gepaarte Seeds = Common Random Numbers — jede Pfadänderung verschiebt den Draw-Index, Divergenzrate ist Pflicht-Metrik, nicht nur Win-Rate).
2. **Semantischer Hash:** Bit-Identität pro Seed als erste Metrik (wie viele Seeds ändern sich überhaupt); Divergenzrate berichten, nicht verschweigen.
3. **17 Vergleichs-Metriken + Holm** (wie `pilot_decision_report.py compare`: turns, decisions, forced_priority, wall_s, pilot_s, spells_cast, own_turns, bad_idle-Metriken, removal_targets, bad_removal_on_own_permanent, wipes_cast, bad_wipes_while_ahead, counters_cast, attacks, blocks, spells_per_player_round).
4. **Win-Rate nur mit Power:** M4-Lektion — 200 Paare sehen nur Effekte ≥ ~5 Punkte; kleine Effekte brauchen Finish-Order als primären Endpunkt (R-12) oder größere n. Win-Rate UNDECIDED ist ein legitimes Ergebnis, kein Fehlschlag.
5. **Klassen-Metriken je Vorschlag** (nicht nur Win-Rate): Trigger-Ordnung → Szenario-Fixtures; Ziel-Leiter → Engine-vs.-Kreatur-Fixtures; Crackback → Combat-Metriken; Timing → bad_idle-Metriken; Mulligan → Lineal (195 Precons × 100 Hände) + echte Spiele; Combo → Fehlalarm-Rate in Replays.
6. **Budget-Regel:** +1 ms/Entscheidung als Obergrenze für neue Terme (Handoff-Urteil: Pilot-Anteil klein, Qualität ist der Hebel, aber nicht umsonst); Wall-Time je Änderung berichten.
7. **Pilot-Regel vor Merge:** ≥10 Seeds Real-Game-Vergleich auf dem PR; keine Merge ohne ihn. Unit-Tests für neue Regeln (Szenario-Fixtures) sind Pflicht, kein Ersatz für Spiele — und umgekehrt.
8. **Abbruch-Kriterium:** Ein Vorschlag ohne messbare Verbesserung (oder mit Verschlechterung) wird verworfen, nicht behalten — auch P2-Vorschläge.

---

## 5. Ehrliche Lücken (wo weder Literatur noch Pilot etwas Belastbares haben)

- **L1–L10 aus Teil 1** gelten unverändert: keine quantitative Threat-Formel, keine Crackback-Formel, keine X-/Pay-/Kicker-Lehre, keine Trigger-Prioritätenlehre, keine May-Lehre, keine moderne Multiplayer-Rollenlehre, Casual-Tiefe nur als Einführung (Tiefe fast nur cEDH), keine Risiko-Quantifizierung, keine Spread-vs.-Focus-Auflösung, keine datengestützten Entscheidungsregeln (alles Experten-Heuristiken, Evidenzklasse externe Quelle, nicht Messung).
- **Pilot-seitig:** Die größten Lücken sind nicht fehlende Ideen, sondern fehlende Sichtbarkeit (P0-1: Metadaten ungesetzt, Inputs konstant) und fehlende Modelle dort, wo die Literatur ebenfalls schweigt (Trigger, Combo, X-Breakpoints). Das heißt: Für P0-3, P1-1, P1-4 gibt es keine Literatur zum Abschreiben — sie müssen aus eigenen Replays und Szenario-Fixtures entwickelt und gemessen werden.
- **Band-Lücke:** Für High-Power-Casual (unser Band) gibt es keine tiefe Entscheidungslehre — Casual-Literatur ist einführend, cEDH-Literatur ist tief, aber band-fremd. Jede Übernahme aus cEDH braucht eine Band-Prüfung (Abschnitt 3, „Explizit NICHT zu lehren").
- **Mess-Lücke:** „Bessere Entscheidungen" ist ohne Ground Truth schwer zu messen: Win-Rate ist schwach gepowert, Szenario-Fixtures brauchen handgeprüfte Optima, Replay-Labeling braucht Annotatoren. Das Messprotokoll (§4) mildert das, löst es nicht.
- **Scope-Lücken dieser Recherche:** Keine Engine-/Bridge-Code-Lektüre (nur Pilot-Dateien), keine erneute Messung von Spielverhalten (Handoff-Zahlen nur zitiert), keine Video-/Podcast-Transkripte als Text greifbar (Teil 1), keine Reddit-/MTGSalvation-Aggregate als Belege (Foren-Säule leer als Befund, wie im Precon-Deepdive).
