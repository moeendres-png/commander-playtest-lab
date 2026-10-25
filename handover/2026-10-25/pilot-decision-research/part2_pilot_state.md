# Teilrecherche 2: Ist-Stand des Commander-Piloten — Entscheidungs-Dimensionen

Stand der Recherche: 2026-10-25. Evidenzklasse: **CODE_DERIVED** (nur aus gelesenen
Dateien; keine Spiele gespielt, keine Repo-Änderungen, keine Pushes, keine
Sammlungsdaten aus `data/collections/**` oder `data/coverage_decks/collection/**`
gelesen). Diese Datei ist neu angelegt; der alte Pilot-AI-Handoff und alle anderen
alten Berichte wurden nur gelesen, nicht verändert.

## Quellen und Checkouts (je Datei vermerkt)

Soll-Vergleich: Pilot-AI-Handoff auf Branch `muse/claude-handover`
(`handover/2026-10-24/pilot-ai/HANDOFF.md`, §§2–4, und `RESEARCH.md` Abschnitte A/B),
per GitHub-API gelesen. Der Handoff beschreibt das Ziel-Design; alles unter
„Ist" unten ist dagegen der gelesene Code-Stand — nicht das Handoff-Ziel.

Code-Checkouts (alle Pfade relativ zu `src/commander_lab/`):

- Haupt-Clone `~/workspace/github/commander-playtest-lab`, Head `4f3af5ea7`:
  `agents/pilots.py` (1.743 Zeilen) und `engine/rules/full_game_pilot/` (nur
  `choices.py`, `combat.py`, `common.py`, `payment.py`, `policy.py`, `priority.py`,
  `state.py`, `__init__.py`) vorhanden.
- Worktree `~/workspace/github/wt-maxreview2`, Head `217c34d95` („Pilot Phase 5",
  #1007): **alle** unten zitierten Pilot-Dateien gelesen, inkl. der im
  Haupt-Clone fehlenden `engine/rules/full_game_pilot_blocks.py` (233 Zeilen),
  `engine/rules/full_game_pilot_payment_plan.py` (402 Zeilen),
  `engine/rules/full_game_pilot_targets.py` (202 Zeilen) und
  `engine/rules/full_game_pilot_views.py` (1.756 Zeilen) sowie
  `agents/pilots.py` (1.806 Zeilen). Wo Haupt-Clone und Worktree sich bei
  `agents/pilots.py` unterscheiden, ist das unten bei Mulligan vermerkt
  (Phase-2-Castability-Modell nur im Worktree).
- Gemeinsame Basis beider Checkouts: `models/pilots.py` (`PilotStateView`,
  `PilotActionView`, `PilotUtilityBreakdown`).

## Architektur in einem Absatz (gelesener Ist-Stand)

Zwei Ebenen. (1) Der generische Utility-Pilot `GenericCommanderPilot`
(`agents/pilots.py`, `BasePilot.evaluate_action` / `_base_components` /
`_select` / `choose_action`): 11 Utility-Komponenten
(`survival`, `mana_efficiency`, `card_advantage`, `tempo`, `engine_development`,
`interaction_reserve`, `commander_value`, `threat_reduction`, `win_progress`,
`political_visibility`, `rebuild_capacity`) plus `specialist_bonus`, gewichtet je
`PilotStrength` (`_GENERIC_WEIGHTS`, `pilots.py:53–108`; z. B. NEAR_OPTIMAL:
`survival 1.35`, `threat_reduction 1.3`, `win_progress 1.4`,
`political_visibility −0.85`). Auswahl in `_select` (`pilots.py:639–668`):
deterministisch nach (gerundeter Utility, −Manakosten, `action_id`); vorher
kürzt `choose_action` (`pilots.py:538–565`) auf die Shortlist
(`_StrengthPolicy`: WEAK 8 / AVERAGE 6 / STRONG 4 / NEAR_OPTIMAL 3).
(2) Der Full-Game-Policy-Adapter `ExternalPilotDecisionPolicy`
(`engine/rules/full_game_pilot/policy.py:22`, `decide`), der 17
Entscheidungsklassen auf den Piloten bzw. auf Spezialregeln abbildet
(`policy.py:31–48`: priority, target, choose_object, target_amount, mulligan,
choose_use, choice, pile, mana_payment, announce_x, amount, multi_amount,
replacement_effect, trigger_order, mode, declare_attacker, declare_blocker).
Spezialregeln (Gates, Filter, Solver) stehen in `priority.py`, `combat.py`,
`payment.py`, `choices.py` und den Modulen `full_game_pilot_blocks.py`,
`full_game_pilot_payment_plan.py`, `full_game_pilot_targets.py`,
`full_game_pilot_views.py`. Kartenwissen kommt aus dem Katalog
(`agents/card_knowledge.py`: `card_facts` — Rollen, Manakosten, kuratierte
Profile) und aus dem Engine-State-Dict (Spieler, Battlefields, Stack,
`commander_status`); die Engine bleibt die einzige Legalitäts-Autorität.

Status-Begriffe: **MODELLIERT** = eigene Regel/Komponente mit benannten Inputs;
**NUR HEURISTISCH** = nur ein Proxy-Term, ein Schwellwert oder eine
Seiten-/Wert-Heuristik, kein eigenes Modell der Dimension;
**FEHLT** = in den gelesenen Dateien nicht gefunden (mit Suchhinweis; nicht als
bewiesen-abwesend über den gelesenen Umfang hinaus behauptet).

## 1. Threat Assessment / Bedrohungs-Leiter — NUR HEURISTISCH

- `engine/rules/full_game_pilot_views.py:438–466` `player_threat(player, state)`:
  `board_value*0.35 + creature_power*0.25 + lands*0.15 + hand_count*0.3`,
  multipliziert mit `(0.6 + 0.4 * min(1, life/40))` — ein Spieler nahe Tod
  „droht weniger". `board_value` = Summe `entry_value` (max. 12 je Permanent,
  `views.py:395–412`, aus Katalog + P/T + Commander-Flag).
- `engine/rules/full_game_pilot/state.py:684–694` `_card_threat` /
  `_player_threat`; `state.py:494–541` `_target_action` kombiniert
  `combined_threat = card_threat*0.7 + player_threat*0.3`.
- `views.py:713–727` `archenemy(state)`: nur wenn der Führende ≥4.0 Threat hat
  und ≥25 % über dem Zweiten liegt; sonst kein Archenemy. Bonus in
  `pilots.py` (`threat_reduction`, Archenemy-Ziel: `+0.45 + min(0.55,
  target_threat*0.05)`).
- Was fehlt gegenüber Handoff §4.2: keine Stufenleiter (gewinnt-sofort >
  Mana-Engine > Draw-Engine > Commander > Kombo-Teil > …), keine
  Besitzer-Uhren (Lebens-Uhr, Commander-Schaden-Uhr, Kombo-Uhr), kein
  Produkt aus Stufenwert × Uhr × Betrifft-mich-Faktor × Unmittelbarkeit.
  Leben geht als Rohwert-Faktor (life/40) ein, nicht ausschließlich als
  Züge-bis-Lethal. `PilotStateView.max_opponent_threat`
  (`models/pilots.py:194–196`) ist nur das Maximum der Gegner-Threats —
  keine `meinScore − maxGegner − λ·Mittel`-Aggregation (Handoff §4.8).

## 2. Ressourcen-Management (Leben, Karten-Vorteil, Tempo, Mana) — MODELLIERT (als Utility-Komponenten, ohne Mehr-Züge-Planung)

- `agents/pilots.py:670–910` `_base_components`, gelesen im Worktree:
  - Leben: `life_pressure = max(0, (22 − life)/10)` treibt `survival`
    (Protection, Wipe, Removal, Counter); `lethal_pressure =
    max(0, (22 − lowest_opponent_life)/7)` treibt `win_progress`.
    Leben ist linear in diesen Termen; nichtlinear nur in der
    Ziel-Bewertung (s. §5, `life_clock`).
  - Karten-Vorteil: `card_advantage` = DRAW `*1.5` bei Hand ≤4, sonst `*0.9`,
    plus SELECTION `*0.8`, RECURSION (skaliert mit Friedhofsgröße), ENGINE `*0.45`.
  - Tempo: `tempo` = `immediate_impact` (Pass: `*0.35`, sonst `*1.15`) +
    billige-Karten-Bonus + Removal-/Counter-/Ramp-Terme − `turn_cycle_risk*0.7`.
  - Mana: `mana_efficiency` = Wert/Manakosten (Pass und reine Ziele: 0),
    Ramp-Bonus fällt mit der Runde (`1.7 − turn*0.14`); `interaction_reserve`
    mit `reserve_mana_target` je Stärke (0.5 / 1.0 / 1.5 / 2.0,
    `pilots.py:25–49`).
- Leben als Ressource (z. B. Bezahlen mit Leben) ist kein eigenes Modell:
  nur Withhold-Gates für lebensgefährliche Casts
  (`views.py`, `_life_cost_withhold_reason`: Flashback-/Zusatz-Lebenskosten,
  die den Akteur auf 0 bringen, werden nicht angeboten).
- Keine Planung über mehrere Züge: kein Mana-/Karten-Budget über die
  nächsten Züge, keine „Development Score"-Kurve (nur Mulligan, s. §7).

## 3. Combat — MODELLIERT (Angriff, Block, Crackback als boolesches Gate)

Angriff (`engine/rules/full_game_pilot/combat.py:32–90` `_decide_attack`,
`views.py:1466–1586` `attack_score`):

- Pro Kreatur eine binäre Entscheidung; Optionen mit `attack_score ≤ 0`
  werden gar nicht erst angeboten, sonst „Hold" (`floor_value 0.1`).
- `attack_score` = „Imagine the Worst" (schlimmste Blocks angenommen):
  sicherer Angriff `0.6 + power*0.08`; Angreifer, den ein Blocker tötet
  und überlebt: `−0.8` (ohne First/Double Strike); Power 0: `−1.0`;
  Lethal durch leeres/evadiertes Board: `+3.0`; niedrige Verteidiger-Life:
  `+max(0, 20−life)*0.03`; Desperation-Bonus (nur wenn Leben ≤10 UND
  Tempo < −0.3 UND max. Gegner-Threat ≥20, `views.py:523–574`).
- Aggro-Fokus: `views.py:1444–1464` `focus_defender` (Threat + Finish-Bonus
  `max(0,40−life)*0.12 + max(0,20−life)*0.25`, Ties → niedrigere Life, dann
  Spieler-ID); Angriff auf den Fokus-Verteidiger: `+0.6`. Der Fokus gilt
  für **alle** Angriffe — keine Commander-Schaden-Bündelung auf einen
  Spieler vs. Verteilen bei Nicht-Commandern (Handoff §4.3 unterscheidet
  das; im Code nicht gefunden).

Block (`combat.py:92–193` `_decide_blocks`,
`engine/rules/full_game_pilot_blocks.py`, `views.py:1587–...` `block_score`):

- `block_score`: überlebt + tötet: `2.0 + attacker_value*0.1`; überlebt:
  `0.8`; tötet: `0.3 + (attacker_value − blocker_value)*0.2`; Chump sonst
  nur `1.5` bei Lethal/nahezu-Lethal (Schaden ≥ Life oder Life−Schaden ≤5),
  sonst `−1.0`; Trample-Chump: `−1.0`; Menace allein: `−1.0`.
- Deklarations-weite Logik (Phase 3, #989): `BlockRound`
  (`blocks.py:40–51`) merkt Angreifer-Schaden (Double Strike ×2, Trample-,
  Menace-, Commander-Lethal-Markierung ab 21); `is_pressing` = unblocked
  Schaden ≥ Life oder Commander-Lethal-Angreifer offen; dann
  `urgent_scores` (Schaden-vom-Tisch `1.0 + 0.1/Schaden` + `5.0`
  Commander-Urgency), sonst `settled_scores` (kein Doppel-Chump auf
  denselben Angreifer). Zusätzlich Block-Frame-Ladder bei Engine-Re-Asks
  (`combat.py:194–266`, Ask 1 = Urteil, Ask 2 = maximal, ab Ask 3 =
  leere/Einzel-Deklarationen, dann Fail-closed).
- Die Handoff-Block-Regel („Chump nur bei Lethal / wenn derselbe Angreifer
  ohnehin gechumpt werden müsste / wenn der Zug genau den Turn kauft, den
  der Gewinn braucht") ist damit in den ersten beiden Ästen abgebildet,
  der dritte Ast („kauft den Gewinn-Zug") nicht als eigene Regel gefunden.

Crackback (`views.py:1577–1586` `_crack_back_danger`):

- Nur boolesch: max. gegnerische Kreaturen-Power bringt den Akteur auf
  ≤5 Life → Angriffswert `−1.2` für Nicht-Vigilance-Kreaturen mit
  Toughness ≥2, außer der Angriff ist lethal. **Kein** aufsummierter
  Crackback-Term (nächste-Zug-Stärke aller übrigen Gegner vs. eigene
  verbleibende Blocker nach dem Angriff), wie ihn Handoff §4.3 fordert.

## 4. Politics / Aggro-Verteilung — NUR HEURISTISCH

- `political_visibility` (`pilots.py`): ENGINE `*(1 − immediate_impact*0.35)`
  + PAYOFF `*0.75` + FINISHER `*0.8` + Power-über-4 `*0.13` +
  Multiplayer-Skalierung + `board_exposure`; Gewicht je Stärke negativ
  (−0.15 / −0.5 / −0.7 / −0.85): auffällige Aktionen werden abgewertet,
  nicht modelliert, wer darauf reagiert.
- Einzige Aggro-Verteilung: `focus_defender` (s. §3) — Schaden wird auf
  einen Spieler konzentriert (Threat + niedrige Life), nicht nach Zweck
  (Trigger ernten / Uhren parallel drücken / Crackback streuen) verteilt.
- Kein Deal-, Trotz-/Vergeltungs- oder Kingmaking-Term gefunden
  (Suche: `crackback|combo|politic|aggro|kingmak|retaliat|revenge|grudge`
  über `agents/pilots.py`, `full_game_pilot/`, `full_game_pilot_*.py`,
  `models/pilots.py` — Treffer nur `political_visibility` und BREAD-„Aggro"
  als Draft-Heuristik `views.py:576–617`). Das entspricht der
  Handoff-Leitplanke „kein Kingmaking, kein Trotz-Term" (§7), ist aber
  kein positives Politics-Modell.

## 5. Ziel-Priorisierung (Removal-Targets) — MODELLIERT (Seite + Wert + Commander-Uhr, keine Funktions-Leiter)

- Seite: `engine/rules/full_game_pilot_targets.py:31–66` `target_side`
  (Outcome-Mengen `_OWN_SIDE` / `_OPPONENT_SIDE`, z. B. `destroypermanent`,
  `exile`, `damage` → Gegner-Seite; `boostcreature`, `gainlife`, `drawcard`
  → eigene Seite; Ausnahmen Collective Effort / Terastodon).
- Rang: `choices.py:122–305` `_decide_targets`: Score =
  `evaluate_action` + `_target_alignment` (`state.py:598–636`: ±8.0 je nach
  Seite, nur wenn beide Seiten angeboten werden) + `target_object_bonus`
  (`views.py:1390–...`: ± `min(12, entry_value)*0.5`, vorteilhaft → eigenes
  wertvollstes, nachteilig → gegnerisches wertvollstes) +
  `commander_clock_bonus` (`targets.py:171–202`: `6.0 * min(1, taken/21)`,
  +`8.0` wenn der nächste Hit 21 erreicht, nur für Removal-Outcomes gegen
  gegnerische Commander).
- Leben als Zielkriterium: `targets.py:119–128` `life_clock` (quadratisch
  unter 20 Life, Skala 12) — nur für `damage`/`loselife`-Outcomes gegen
  Spieler-Ziele (`_target_alignment`).
- Sonderfälle: Gifts (`drawcard` nur an Gegner) gehen an den
  **schwächsten** Gegner (`choices.py`: `strongest − target_threat`);
  „Benefit"-Outcomes nehmen `max_selections`, sonst bei `min_selections=0`
  nur Ziele mit Score ≥0.
- Vorfilter in `views.py` `priority_view_fields`: Removal nur, wenn ein
  lohnendes Ziel existiert (`best_removal_target_value`,
  Schwellwert `_REMOVAL_WORTH = 3.0`); Counter nur, wenn das oberste
  Gegner-Objekt auf dem Stack es wert ist (`counter_target_worth`,
  Commander = 10.0, Wipe/Finisher/Removal ≥3.0, sonst Manakosten).
- Fehlt: Funktions-Leiter (Mana-Engine vs. Draw-Engine vs. Stax vs. …),
  Betrifft-mich-Faktor (Stax nur hoch, wenn es den Akteur sperrt),
  Besitzer-Uhr als Multiplikator — die Commander-Uhr existiert nur als
  additiver Bonus für Removal gegen Commander, nicht als allgemeiner
  Ziel-Score.

## 6. Timing (spielen / halten / passen) — NUR HEURISTISCH

- `views.py:892–913` `_instant_timing`: nur für Instant-Speed-Karten mit
  reaktiven Rollen (oder Kreaturen) und leerem Stack: eigene Main-Phase
  `−0.5` auf `immediate_impact`, gegnerische End-Phase `+0.6`, sonst 0.
  Kein Postcombat-Default, keine „letzte Fenster"-Gates, keine
  Ausnahmenliste (Haste/Anthem/Equip/Blocker-Entfernung precombat,
  Draw auf letzten Gegner-End-Step, Feuern bei ausgetapptem Gegner).
- `views.py:914–931` `_curve_bonus`: bis `+1.0` `immediate_impact` für
  Karten, die in der eigenen Main-Phase viel des verfügbaren Manas nutzen.
- Passen: Pass-Option in `priority.py` mit `floor_value 0.15`;
  `interaction_reserve` in `pilots.py` belohnt Passen bei Interaktion auf
  der Hand (Stärke-Bonus 0.0 / 0.3 / 0.55 / 1.2 × Threat-Kontext
  `min(1.35, 0.35 + max_opponent_threat*0.08 + turn*0.025)`), plus
  `flexible_interaction`-Bonus, wenn der Stack nicht leer ist
  (`priority.py`: `metadata flexible_interaction = bool(stack)`).
- `pilots.py:567–584` `should_take_reaction`: fester Schwellwert
  `threshold = 0.5` auf die Gesamt-Utility; keine Kopplung an eine
  Removal-Feuerregel („reagieren, wenn das Ziel sonst gewinnt oder uns
  aussperrt", Handoff §4.1). In der Full-Game-Priority-Entscheidung wird
  nicht `should_take_reaction` aufgerufen, sondern die Pass-Option als
  normale Aktion mitbewertet (`priority.py`, `choose_action` über alle
  Aktionen inkl. Pass).
- Strukturelle Lücke (Handoff §5): `PilotStateView` (`models/pilots.py`)
  enthält **keine** Phase/Step/Stack-Felder; Phase/Step werden nur im
  rohen State-Dict in `views.py`/`priority.py` gelesen (z. B. für
  `_instant_timing`, `_curve_bonus`, No-Progress-Guard), nicht in der
  Utility-Bewertung selbst.

## 7. Mulligan — MODELLIERT (Castability-Modell, Worktree-Stand; Bottoming-Regel enthalten)

- Full-Game-Pfad: `choices.py:86–121` `_decide_mulligan` ruft
  `BasePilot.should_keep_opening_hand` mit `free_first=True`; harte Kappe:
  ab 3 Mulligans wird immer gehalten (geloggter Forced-Keep). Bottoming
  bei London: `choices.py:130–170` (nur wenn die Optionen Handkarten sind)
  ruft `choose_bottom_cards`.
- Keep-Modell (`agents/pilots.py:355–453`, **nur im Worktree-Stand
  217c34d95 = Phase 2, #1002**; der Haupt-Clone `4f3af5ea7` hat noch die
  ältere, landzahl-lastigere Fassung — Diff belegt: `_OPENING_CELLS`
  u. a. nur im Worktree): erwartetes Mana über 6 Züge aus einer
  Least-Squares-Anpassung (58.500 Hände, 195 Precons, R² 0.33) als
  Funktion von Ländern (0–6) × billigen, mit den Ländern bezahlbaren
  Zaubern (0–3), plus Farb-Lücke (`−0.66` × Anteil bis-MV-4-Zauber, deren
  Farben die Länder nicht machen), Commander-Farb-Lücke (`−3.85`),
  erstem/zweitem billigen Ramp (`+2.93` / `+1.71`), Early-Velocity
  (`+0.09`, max 2), teuren Karten (`−0.03`), Flood (`−3.0` ab 6 Ländern),
  Land-Light (`−3.0` bei ≤1 Land); Vergleich gegen frische 7 (`15.18`),
  Keep-Marge `1.0`, pro Mulligan nach dem ersten fällt die Latte um
  `1.2`, Stärke-Offsets `0.4` je Stufe (schwächere Piloten halten mehr).
- Bottoming (`pilots.py:455–488` `choose_bottom_cards`,
  `489–522` `opening_card_value`): eine Karte nach der anderen gegen die
  schrumpfende Hand bewertet; Länder: 1.–3. Land `6.0` (nie bottomen),
  4. Land `1.5`, ab 5. Land `0.4`; Zauber: `floor_value +
  immediate_impact` + billige Rollen-Boni (Ramp `*1.4`, Draw `*0.8`,
  Selection `*0.7`, Removal `*0.45`, Counter/Protection `*0.35`) −
  teure-Karten-Abzug − `turn_cycle_risk*0.25`.
- Fehlt gegenüber Handoff §4.4: kein Development Score (kurvenspielbare
  Zugfolge Richtung Deckziel, Commander-Soll-Zug), keine Deck-abgeleiteten
  Parameter außer Commander-Farben, kein Pod-Profil (casual/cEDH),
  keine Bottoming-Regel „teuerste unspielbare > situative/tote >
  doppelte Engines, nie einzige Interaktion/Farbquelle/Frühspielzug"
  (die Land-Staffel + Wert-Formel approximiert nur den ersten Teil).
  Das separate Paket `src/commander_lab/mulligan/` (`canonical.py`,
  `lab.py`) ist ein Auswertungs-/Lab-Werkzeug, nicht der
  Entscheidungs-Pfad des Full-Game-Piloten.

## 8. Trigger-Ordnung — FEHLT (nur generische Label-Heuristik)

- `policy.py:169–170`: `replacement_effect` und `trigger_order` werden
  beide auf `_decide_semantic_option` (`choices.py:306–337`) abgebildet.
- `_decide_semantic_option` baut über `state.py:561–578`
  `_semantic_action` eine `PilotActionView` nur aus dem Label-Text:
  Rollen per Wortsuche („draw" → DRAW, „destroy/exile/damage/counter
  target" → REMOVAL, „create/token" → TOKEN_SOURCE, „return/graveyard"
  → RECURSION), `floor_value 0.4`, `immediate_impact 0.4 + 0.15/Rolle`
  (max +0.5). Danach normale Utility-Wahl.
- Keine Regel „wertvollster Trigger zuletzt stapeln (resolviert zuerst)",
  keine Delta-Bewertung von Trigger-Effekten, keine Klassenregel
  (Schaden/Entfernung vor Ziehen vor Kosmetik) wie in Handoff §4.7.
  Suchhinweis: `policy.py:169`, `choices.py:306`, `state.py:561`;
  „trigger_order" kommt in den Pilot-Dateien sonst nur als
  Klassenname und in Guard-Kommentaren vor.

## 9. Zahlung / X-Entscheidungen — MODELLIERT (Solver + Budget, keine X-Breakpoints)

Mana-Zahlung (`payment.py`, `full_game_pilot_payment_plan.py`):

- Quellen-Ordnung (`payment.py:936–1007` `_choose_mana_option`-Hilfslogik):
  knappste benötigte Farbe zuerst, dann am wenigsten flexible Quelle,
  dann generische Zahler (am wenigsten flexibel zuerst); Pool-Mana der
  häufigsten Farbe zuerst (Handoff §4.6: „knappste Farbe und
  Interaktions-Farben schonen" ist nur als Knappheits-Ordnung, nicht als
  Hand-Interaktions-Schonung umgesetzt — die Regel liest nur das Angebot
  und die unbezahlten Kosten, nicht die Hand).
- Vervollständigungs-Solver (`payment_plan.py:331–366`
  `completing_options`, `367–402` `completing_outcomes`): DFS über
  Pool + Mana-Fähigkeiten (Node-Cap 20.000, `None` = nicht beurteilbar →
  alte Wahl bleibt); `_complete_payment` (`payment.py:578–624`) ersetzt
  eine Wahl, die die Zahlung stranden ließe, durch eine vervollständigende
  (nie durch Cancel). Farb-Wahlen und „any combination"-Splits werden
  gegen denselben Solver korrigiert (`_colours_that_complete`,
  `_vector_that_completes`).
- Reihenfolge-Sonderfälle: Pool vor Fähigkeiten, Convoke/Delve/
  Improvise erst, wenn keine Mana-Fähigkeit mehr zahlt
  (`_mana_before_alternate_payments`); No-Progress-Guard (3× identisches
  Angebot → Cancel).
- Was **nicht** modelliert ist: welche Kreatur noch blocken/angreifen
  soll (Tap-Kosten-Schonung) — nur die o. g. Quellen-Ordnung; keine
  Reserve für spätere Aktionen in der Zahlung selbst.

X / Beträge / May (`payment.py:1008–...` `_decide_numeric`,
`_decide_multi_amount`; `agents/pilots.py:133–289` `_NumericStrategyMixin`):

- X-Budget (`payment.py:1315–...` `_announce_x_affordable_max`):
  `(sichtbares Budget − Nicht-X-Kosten) // X-Symbole`, nie unter 0;
  Budget = Pool + je 1 pro ungetapptem Permanent mit Mana-Fähigkeit
  (`_mana_budget`). Nur echte Mana-X (Prompt = nur `{X}`-Symbole);
  Tap-/Counter-X bekommen eigene Caps (`x_tap_prompt_cap`,
  `option_x_counter_cap`).
- Strategie im Band: deterministisch Benefit → Maximum, Detriment →
  Minimum, neutral → Mittelpunkt (`pilots.py:160–176`
  `deterministic_number`); stochastisch Gleichverteilung im Band.
  Keine Interaktions-Reserve wird vom X abgezogen.
- X=0-Schutz (Phase 4b, #1003): `_x_spell_without_x`
  (`payment.py:1263–...`) hält in der Priority-Entscheidung X-Zauber
  zurück, deren sichtbares Mana nach den Restkosten nichts für X lässt.
  Ausnahmen (laut Vorwissen aus dem Projektgedächtnis: Chalice of the
  Void, Engineered Explosives) wurden im gelesenen Code-Ausschnitt nicht
  separat verifiziert und werden hier nicht als Code-Beleg behauptet.
- Wiederholte May-Kosten: Multikicker-Kette wird nur durch die
  sichtbare-Mana-Kappe begrenzt (`choices.py:669–695`
  `_boolean_yes_cap`: `(verfügbares Mana − Zauber-Grundkosten) //
  Kosten-je-Zahlung`, mind. 1); Phyrexian-Lebens-Versprechen und
  Life-Dig-Cap als Liveness-/Legalitäts-Guards. Keine
  Monotonie-Regel („wer Stufe k zahlt, zahlt auch < k") und keine
  May-Nein-Bedingungen (Interaktions-Mana, Deckung, Draw-Punisher,
  Lebens-Uhr) — die generelle Boolean-Wahl (`choices.py:386–...`)
  bewertet Yes/No nur über Outcome-Alignment (`floor 0.8/0.35`,
  `impact 0.45/0.15`).
- Farbwahl (`choices.py:840–907` `_decide_choice`,
  `views.py` `color_choice_rank`): offene Kosten zuerst (`*10` je
  benötigtem Pip), dann Hand-Bedarf (`*1` je Pip in Handkarten),
  dann Commander-Identität (`+0.5`); Schutz-Farben nach
  Gegner-Board-Häufigkeit, Kreaturtypen nach eigenem Board
  (`named_choice_rank`). Keine „fehlende Farbe der spielbaren Karten"
  über die Hand hinaus (kein Deck-Bedarf).

## 10. Combo-Erkennung / -Disruption — FEHLT

- Suche über alle gelesenen Pilot-Dateien (`combo`, `win_condition`,
  `infinite`): kein Combo-Modell, keine Kombo-Teil-Erkennung, keine
  „fehlende Teile"-Uhr, keine Disruptions-Priorität für Kombo-Teile.
  Einzige Treffer: `models/packages.py` `COMBO = "combo"` als
  Paket-Rollen-Label (Deckbau-Klassifikation, kein Pilot-Entscheidungs-
  Pfad) und der Infinite-Loop-Prompt-Guard in `choices.py` (Liveness,
  keine Strategie).
- Indirekt vorhanden, aber kein Combo-Modell: Counter-/Removal-Rollen,
  `counter_target_worth`, `stack_pressure`, Threat-Scores — sie
  bewerten einzelne Karten/Stacks, erkennen keine Kombinationen.
  Deck-spezifische Synergie-Pakete (`KorvoldPilot` /
  `RogShaiPilot` `specialist_bonus`, z. B. `korvold-land-sacrifice-
  recursion`, `rogshai-protection-counter`) sind kuratierte
  Deck-Synergien, keine generische Combo-Erkennung.
  Suchhinweis: `grep -rni "combo" agents/pilots.py
  engine/rules/full_game_pilot/ engine/rules/full_game_pilot_*.py`.

## 11. Wincon-Bewertung — NUR HEURISTISCH

- `win_progress` (`pilots.py`): FINISHER `*(1.3 + lethal_pressure)` +
  COMBAT_PAYOFF `*(0.6 + 0.8 falls Commander online)` + PAYOFF `*0.45` +
  `base_power*0.12` + `multiplayer_scaling * Gegnerzahl * 0.25` +
  TABLE_DAMAGE-/FINISHER_COMPRESSION-Mechanik-Boni +
  `expected_lethals` (Metadatum) `*1.35`, gedeckelt auf `4.5`, +
  `0.9` bei `protected_finish`; FINISHER ohne erwartete Lethals und mit
  `finish_probability < 0.2`: `−1.8`.
- Entscheidende Einschränkung im Full-Game-Pfad: Die Metadaten
  `expected_lethal_opponents`, `protected_finish_window`,
  `finish_probability`, `known_win_attempt` werden in **keiner**
  gelesenen Full-Game-View-Datei gesetzt (Grep über
  `full_game_pilot/*.py`, `full_game_pilot_views.py`,
  `full_game_pilot_blocks.py`, `full_game_pilot_targets.py`,
  `full_game_pilot_payment_plan.py` ohne Treffer als Schreiber; nur
  Leser in `pilots.py` und den Spezial-Piloten). Sie fallen dort auf
  Defaults zurück (`expected_lethals 0`, `finish_probability 1.0`,
  `protected_finish False`). `commander_damage_pressure` (für
  `combat_target`-Win-Progress, `*0.18`) wird im Full-Game-Pfad
  ebenfalls nicht gesetzt (`_combat_action`, `state.py:541–560`, setzt
  nur `target_life`); es wird nur in der älteren Structural-Simulator-
  Lane geschrieben.
- Kein explizites Wincon-Modell: keine Gewinnwahrscheinlichkeit P(Sieg),
  keine „Gegner gewinnt nächsten Zug ⇒ Verlust außer beantwortbar"-Regel,
  keine Commander-Lethal-Bündelung über mehrere Angriffe (s. §3),
  keine Bewertung, welcher Wincon-Pfad (Combat / Combo / Value /
  Commander-Schaden) gerade realistisch ist. Lethal wird nur als
  lokaler Bonus (Angriffs-Lethal `+3.0`, `lethal_pressure`) abgebildet.

## 12. Risiko-Abwägung — NUR HEURISTISCH (Terme vorhanden, Inputs im Full-Game-Pfad teils Konstanten)

Vorhandene Risiko-Terme (`pilots.py` `_base_components`):

- `boardwipe_risk` (`views.py:728–760`): aus eigenem Board-Vorsprung
  gegenüber Gegner-Durchschnitt × Gegner-Handkarten (0..1); dämpft
  Commander-Casts und board-exponierende Aktionen
  (`* board_exposure * 0.8` bzw. `0.55`).
- `commander_denial_risk` und `boardwipe_risk` als
  `PilotStateView`-Felder (`models/pilots.py:171–175`); `uncertainty_pressure`
  = `hidden*0.45 + intent*0.30 + unknown_fraction*0.25`;
  `exposure_before_next_turn` (Gegner vor dem nächsten eigenen Zug);
  `stack_pressure` (`views.py:776–786`: gegnerische Stack-Objekte,
  Manakosten-summe / 8, gedeckelt 1.0); `turn_cycle_risk` je Karte
  (Katalog); `all_in_exposure` / `increases_board_exposure` als
  Aktions-Metadaten.
- Input-Vorbehalt im Full-Game-Pfad (`state.py:338–454`
  `_pilot_state`): `hidden_information_uncertainty = 1.0`,
  `opponent_intent_uncertainty = 1.0`, `unknown_opponent_fraction = 1.0`
  werden als **Konstanten** gesetzt; `commander_denial_risk` wird gar
  nicht gesetzt (Default 0.0); `tokens = 0.0`, `ramp_mana = 0.0`;
  `opponents_to_act_before_next_turn = pod_size − 1` (keine
  Sitzpositions-Rechnung). Die Risiko-Terme rechnen also mit
  maximaler Unsicherheit bzw. Null-Risiko, nicht mit gemessenen
  Schätzern. Keine Überlebens-Uhr-Regel („eigene Uhr ≤ 1 ⇒ Überleben
  dominiert", Handoff §4.8) als harter Override — nur die weichen
  `survival`-Terme mit `life_pressure`.

## Querschnitt: Was die Utility gar nicht sieht

- `PilotStateView` hat keine Felder für: Phase/Step, Stack-Inhalt,
  Commander-Schaden je Gegner-Commander (nur `commander_damage_from_actor`
  je Gegner in `PilotOpponentView`, d. h. ausgeteilten Schaden, nicht
  erlittenen je gegnerischem Commander), offenes Gegner-Mana,
  Gegner-Uhren, Deck-/Wincon-Identität. Der rohe State-Dict in den
  Full-Game-Modulen enthält Stack und `commander_status` — die
  Spezialregeln (`targets.py`, `blocks.py`, `views.py`) lesen sie
  direkt, die generische Utility (`_base_components`) nicht.
- Spezial-Piloten (`agents/pilots.py:919–1806`): `KorvoldPilot`,
  `RogShaiPilot` (+ Varianten), `AggroPilot`, `ControlPilot`,
  `EnginePilot`/`GraveyardPilot`/`ArtifactPilot`,
  `GenericCommanderPilot` (`pilots.py:1671`) und
  `KaervekOpponentPilot` — sie ändern nur Gewichte und
  `specialist_bonus` (Deck-Synergien, Schutz-Fenster, Sacrifice-Material),
  keine Entscheidungs-Dimension zusätzlich.
- Nicht gelesen / nicht Teil dieser Recherche: Engine-/Bridge-Code,
  Tests, Qualifikations-Artefakte, Spiele/Transkripte. Aussagen über
  tatsächliches Spielverhalten (z. B. Index-Signaturen aus dem Handoff)
  sind hier nicht erneut gemessen, sondern nur als Handoff-Zitat
  wiedergegeben.
