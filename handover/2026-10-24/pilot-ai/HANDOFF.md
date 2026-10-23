# Handoff: Pilot-KI besser (und wo sinnvoll schneller) machen — an Claude

Von der Mess-Lane (Muse), 2026-10-24. Auftrag des Owners: alle Spiele und jede
Entscheidung auswerten, extern recherchieren, wie man Commander gut spielt und
wie man dafür eine starke, schnelle KI schreibt, und daraus einen Umsetzungsplan
ableiten. Datengrundlagen in diesem Ordner: `census.json` (Vollzensus),
`RESEARCH.md` (externer Forschungsbericht mit Quellen), dazu die Vorbefunde in
`handover/2026-10-23/game-mining/` (BERICHT.md + VERTIEFUNG.md).

## 1. Leitplanken (nicht verhandelbar)

- **XMage bleibt die einzige Rules Engine.** Der Pilot wählt ausschließlich
  unter den von der Engine angebotenen legalen Optionen. Keine erfundenen
  Aktionen, keine Legalitäts-Heuristik, keine Skips von Engine-Entscheidungen.
- **Determinismus:** Pilot-Entscheidungen müssen aus dem Semantic Replay Tape
  reproduzierbar sein — keine Wanduhr-, keine unkontrollierten Zufallsanteile
  (der vorhandene `rng`-Kanal mit Seed bleibt der einzige).
- **Nur eigene Sicht:** Der Pilot darf nur Informationen verwenden, die sein
  `PilotStateView` aktor-scoped hergibt (Hidden-Information-Audit der
  Transkripte: 0 Verstöße in 1.971 Spielen — so muss es bleiben).
- **Kein Suchverfahren im Entscheidungsbudget** (Begründung in §3).

## 2. Ist-Verhalten, gemessen (Vollzensus, 1.971 Spiele, Pin v11, Pilot 1.0.0)

**6.051.869 Entscheidungen** in 16 Klassen (`census.json`):

| Klasse | Anteil | 1-Option-Anteil | Index-0-Rate | Signatur |
|---|---|---|---|---|
| priority | 72,3 % | 35 % | 93 % (= Pass) | 4.065.714 Pässe |
| mana_payment | 18,6 % | 1 % | 2 % (78 % Index 1) | erstes echtes Zahlungsmittel |
| target | 1,9 % | 18 % | 42 % | Top-Ziel: Gegner-Commander (14.985×) |
| declare_attacker | 1,9 % | 0 % | 29 % | je Kreatur eine binäre Entscheidung |
| choice | 1,6 % | 0 % | 34 % | Top-Wahl „Black" (28.520×) |
| choose_object | 1,1 % | 19 % | 41 % | |
| choose_use | 0,9 % | 0 % | 97 % (= „Yes") | Multikicker-Inkonsistenz (VERTIEFUNG P3) |
| declare_blocker | 0,7 % | 58 % | 61 % | 71,3 % ohne Block |
| trigger_order | 0,4 % | 0 % | 54 % | Engine-Reihenfolge dominiert |
| mode | 0,3 % | 11 % | 37 % | |
| mulligan | 0,2 % | 0 % | 56 % (= Keep) | Ketten: VERTIEFUNG P11 |
| announce_x u. a. | <0,2 % | — | — | X-Modus = 0 |

**26,6 % aller Entscheidungen haben genau eine legale Option** (erzwungen).
Zusammen mit den Pässen sind rund **neun Zehntel aller Entscheidungen
bewertungsfrei beantwortbar** — die Intelligenz muss auf die übrigen ~10 %
konzentriert werden (Hauptphasen-Aktionen, Kampf, Ziele, Stack-Antworten).

Code-Befund am gemessenen Lock (`d48bbe5f2`, `src/commander_lab/agents/pilots.py`):
Der `GenericCommanderPilot` bewertet bereits jede Aktion über
`evaluate_action`/`_base_components` (survival, raw_value, mana_efficiency,
card_advantage, tempo, engine_development u. a.) und wählt in
`_select` deterministisch nach (gerundeter Utility, −Manakosten, action_id).
Die gemessenen Index-Signaturen sind also **emergentes Verhalten dieser
Bewertung** (Gleichstände → action_id-Reihenfolge = Engine-Reihenfolge;
fehlende Komponenten für einzelne Klassen), keine „erste Option"-Regel im Code.
Der Umbau ist damit **Komponenten- und Regelarbeit an einem bestehenden
Utility-Piloten**, kein Neubau.

## 3. Geschwindigkeits-Urteil (Owner-Frage: lohnt Schneller überhaupt?)

Gemessen: Median 44,7 s/Spiel, ~3.070 Entscheidungen/Spiel, **~15,1 ms je
Entscheidung** für die Gesamtpipeline (Engine + Bridge + Pilot). Der
Pilot-Anteil daran ist die Auswertung (`evaluate_action` × Kandidaten +
State-View-Aufbau); selbst eine Verdopplung der Pilot-Rechenzeit bewegte die
Spielzeit nur im einstelligen Prozentbereich. **Fazit: Qualität ist der Hebel,
Geschwindigkeit ist Hygienefaktor.** Budget-Regel für alle Phasen unten:
**+1,5 ms Mediane Entscheidungszeit ist die Richtgröße** (≈ +10 % Wandzeit
am Korpus-Median), gemessen im A/B-Vergleich (§6); die gemessene
Zeit-Zerlegung und die Begründung stehen im Nachtrag (§8) — der Pilot ist
mit ~1 % der Simulationszeit der kleinste Kostenblock, Qualität darf
Rechenzeit kaufen, nur keine Größenordnungen. Suchverfahren sind raus: Die Recherche (RESEARCH.md B1/B3)
zeigt, dass jede ausgelieferte Magic-KI in Sekunden pro Entscheidung rechnet
(Magarena, XMage-MCTS, Forge-Forks bis 60 s); das einzige bei Millisekunden
bewährte Muster ist greedy 1-ply über vorgefilterte Optionen mit linearer
Delta-Bewertung (Hearthstone-AI-Wettbewerb 2018: Platz 2 von 33, gegen MCTS).

Erlaubte/sinnvolle Speed-Maßnahmen (Phase 0, verhaltensneutral):
1. **1-Option-Fast-Path:** Entscheidungen mit genau einer legalen Option
   (26,6 %) ohne `evaluate_action` beantworten (falls der Protokoll-Pfad das
   nicht schon tut — prüfen).
2. **Pass-Fast-Path:** Liegt kein Reaktionskandidat über der vorhandenen
   Schwelle (`should_take_reaction`, threshold 0.5), Pass ohne Vollbewertung
   aller Kandidaten.
3. **State-View-Caching:** Die Bridge liefert je Entscheidung eine
   `public_state_reference`; aufeinanderfolgende Entscheidungen teilen oft
   denselben öffentlichen Zustand. State-Features einmal je Referenz
   berechnen und wiederverwenden (inkrementelle Delta-Bewertung ist das
   Magarena-Muster, RESEARCH.md B5).

## 4. Ziel-Design je Entscheidungsklasse

Quelle je Regel: RESEARCH.md Abschnitt A (Spielstärke) / B (KI-Design) oder
VERTIEFUNG (eigene Messung). Umsetzung jeweils als neue/veränderte
Utility-Komponente oder Regel im bestehenden Gerüst.

### 4.1 priority / Reaktionen (größter Hebel, VERTIEFUNG P2)
- Timing-Gates nach RESEARCH A5 — **Default mit benannten Ausnahmen, keine
  Pauschalregel**: Standard = alles, was den Kampf nicht verändert,
  **postcombat** spielen; Instants ans letztmögliche Fenster; Draw auf den
  End Step des letzten Gegners (Begründung: volle Information über alle drei
  Gegnerzüge, offenes Mana repräsentiert über den ganzen Zyklus Interaktion,
  Karten sind zum direkt folgenden eigenen Zug verfügbar). Ausnahmen, die
  den Default schlagen: precombat alles, was Kampf verändert oder die
  Angriffsentscheidung informiert (Haste, Anthem, Equip, Blocker-Entfernung,
  Hand-Disruption); Draw im eigenen Zug, wenn Gezogenes diesen Zug noch
  spielbar wäre (Land-Drop, Kampf-Antwort); feuern, wenn der relevante
  Gegner ausgetappt ist; Schadens-Removal früh gegen Pump/Hexproof/Bounce.
  Als Gate-Komponente vor der Utility (Optionen außerhalb ihres Fensters
  werden abgewertet, nicht verboten — die Engine bleibt Autorität, der
  Pilot darf sie nur schlecht finden).
- Reaktions-Schwelle (`should_take_reaction`) an die Removal-Feuerregel
  koppeln (A3): reagieren, wenn das Ziel sonst gewinnt oder uns aussperrt;
  sonst halten (letzter Akteur in der Reihenfolge darf eine gewinnende
  Aktion nie „den anderen" überlassen).
- Handlungsrate heute: 5,4 % (früh) → 9,7 % (spät); Ziel ist keine Quote,
  sondern: Reaktionen in fremden Zügen existieren messbar (Folgemetrik §6).

### 4.2 target (VERTIEFUNG P1)
- `target_threat` um die **Bedrohungs-Stufenleiter** (A2) verfeinern —
  universeller Prior über Kartenfunktionen: gewinnt-sofort > Mana-Engine >
  Draw-Engine > gefährlicher Commander > Kombo-Teil > wiederholte
  Interaktion > breites Board > groß+Schutz > groß+Ausweichen > Stax.
  Die Leiter allein ist zu starr; der Score ist ein Produkt:
  `Stufenwert × Besitzer-Uhr-Faktor × Betrifft-mich-Faktor × Unmittelbarkeit`.
  Der Betrifft-mich-Faktor macht Situationsabhängigkeit explizit (Stax nur
  hoch, wenn es UNS sperrt; Rest in Peace tödlich gegen Friedhof-Decks,
  sonst nahe null).
- Multiplikator: Bedrohung **des Besitzers** (dessen Uhren: Lebens-Uhr,
  Commander-Schaden-Uhr `ceil((21−Schaden dieses Commanders)/Stärke)`,
  Kombo-Uhr = fehlende Teile; Minimum zählt). Lebenspunkte gehen
  **ausschließlich über die Lebens-Uhr (Züge bis Lethal)** ein, nie als
  Rohwert: Bei 40 vs. 35 ist Leben fast egal, bei 8 vs. 30 entscheidend;
  dazu ist Leben eine Ressource bestimmter Decks (Ad Nauseam/Necropotence/
  Citadel — deren Besitzer sind Angriffsziele, §4.3).
- **Kein Trotz-/Vergeltungsterm** (Kingmaking-Verbot, A3): Eine Aktion, die
  die eigene Gewinnwahrscheinlichkeit nicht erhöht, wird nicht gespielt.
- Gemessener Startpunkt: Index-0 in 42 %, Spieler werden ggü. ihrem Angebot
  bereits leicht abgewertet — die Leiter ersetzt die implizite Ordnung.

### 4.3 Kampf (VERTIEFUNG P8)
- Die Engine zerlegt Angriffe bereits binär je Kreatur (RESEARCH B3 nennt
  genau das die wirksame Zerlegung) — daran andocken:
- **Angriffs-Fokus — nur für Commander-Schaden:** Commander-Angriffe auf
  EINEN Spieler bündeln, weil Commander-Schaden je Commander-Spieler-Paar
  gezählt wird (Aufteilen verschenkt Fortschritt auf die 21); Zielwechsel
  bei Uhr-/Bedrohungswechsel (ein Spieler steht vor der Kombo, ein anderer
  ist offen lethal). Nicht-Commander-Angriffe dagegen nach Zweck
  **verteilen**: Angriffs-Trigger ernten, mehrere Uhren parallel drücken,
  Crackback-Risiko streuen. Pauschale Bündelung aller Angriffe ist falsch.
  Angriffs-Priorität (A4): lethal/commander-lethal > Leben-als-Ressource-
  Spieler > Snowballer (wenn offen) > Interaktions-Spieler, der unseren
  Gewinn blockt (mit Externalitäts-Check: dessen Antworten gegen den Rest
  nicht leichtfertig entfernen).
- **Crackback-Term** (fehlt heute): Summe der nächsten-Zug-Stärke der
  übrigen Gegner vs. unsere verbleibenden Blocker nach dem Angriff;
  Chip-Schaden nicht gegen nahezu-letale Gegenschläge tauschen.
- **Block-Regel** (A4): Chump nur bei Lethal (Leben oder Commander-Uhr),
  wenn derselbe Angreifer ohnehin in diesem Zyklus gechumpt werden müsste
  (mit der wertärmsten Kreatur) oder wenn der Zug genau den Turn kauft, den
  unser Gewinn braucht; Leben ist nichtlinear (40→34 egal, 3→0 nie).
  Ist: 71,3 % der Blocker-Entscheidungen ohne Block — ohne Zustandsdaten
  nicht als Fehler wertbar, aber die Regel macht das Verhalten prüfbar.

### 4.4 mulligan (VERTIEFUNG P11; Paket `mulligan/` existiert)
- **Keep-Test** (A1, Konjunktion) — als **universeller Algorithmus über der
  Deckliste**, nicht als Handregel je Deck: 2–4 Länder + Farben/Fixierung
  (Pips der Hand gegen die Manabasis) + ein Spielzug an ≥2 der Züge 1–3
  (Mana-Simulation wie in der M4-Castability) + **Development Score** statt
  Freitext-„Plan": Die Simulation sucht eine mit dem Mana der Hand
  kurvenspielbare Zugfolge Richtung Deckziel (Commander bis zu seinem
  Soll-Zug, Engine-Teile, Rollenabdeckung). Das Deck geht über automatisch
  abgeleitete Parameter ein (Commander-Kosten/Soll-Zug, Rollengewichte,
  Kurve); ein Pod-Profil (casual/cEDH) stellt die Strenge ein. In
  Mehrspieler fällt die Latte je Mulligan (erster ist frei), nie unter 5
  Karten; Payoffs ohne Gas und 2-Land-„Kartenhäuser" ablehnen.
- **Bottoming-Reihenfolge** (A1): überschüssige Länder >4 > teuerste
  unspielbare Karte > situative/tote Karten > doppelte Engines; nie die
  einzige Interaktion/Farbquelle/den einzigen Frühspielzug.
- Baseline zum Schlagen: gepoolte Keep-Rate 52,1 % (Position 0), nach einem
  Mulligan nur 47,1 % — 25,3 % aller Eröffnungen landen bei 5 Karten.

### 4.5 choose_use / mode / X / Beträge (VERTIEFUNG P3, P10)
- **Monotonie-Regel** für wiederholte May-Kosten (Multikicker-Befund:
  1× zahlen = 100 % Ja, 2× = 40,9 %): Wer Stufe k zahlt, zahlt auch alle
  Stufen < k, sofern der Grenznutzen je Stufe gleich ist; Abweichungen nur
  über Breakpoints.
- **May-Nein-Bedingungen** (A6): Nein, wenn das Zahlen unser Interaktions-
  Mana vor einem bekannten Gewinnversuch austappt, uns deckt, Draw-Punisher
  füttert oder eine Lebens-Uhr-Schwelle reißt, ohne die eigene Uhr zu
  verbessern. (Ist: „Yes" 97 % pauschal; „Pay {1} and 1 life and draw a
  card?" = 100 % Ja bei 1.317 Fällen.)
- **X-Breakpoints** statt X=0-Modus (Ist: 843 von 2.926 X-Wahlen sind 0):
  X auf den nächsten Wirkungspunkt setzen (lethal, größte Toughness,
  Zielanzahl-Stufen) und Interaktions-Reserve abziehen; im
  `_NumericStrategyMixin` sind Bänder/Bias vorhanden — an Breakpoints
  umparametrieren.
- **Farbwahl** (`choice`, Top-Wahl „Black" 28.520×): Farbe nach Hand- und
  Deckbedarf wählen (fehlende Farbe der spielbaren Karten), kein Fixwert.

### 4.6 mana_payment (VERTIEFUNG P4)
- Zahlungs-Solver als Regel statt Bewertung (Muster RESEARCH B4):
  gleichwertige Quellen deduplizieren; Reihenfolge: Pool-Mana der
  häufigsten Farbe → häufigste Farbe → farblos; **knappste Farbe und
  Interaktions-Farben in der Hand schonen**; Kreaturen, die noch blocken/
  angreifen sollen, zuletzt tappen. Das kodifiziert das gemessene Verhalten
  (Index 1 = erstes echtes Mittel: Pool 525.130×, Land 348.712×) und macht
  es zugleich farbbewusst.

### 4.7 trigger_order
- Eigene Trigger so ordnen, dass der wertvollste **zuletzt gestapelt** wird
  (resolviert zuerst): Wert = Delta-Bewertung der Trigger-Effekte, wo
  verfügbar; sonst Klassenregel (Schaden/Entfernung vor Ziehen vor Kosmetik).
  Ist: Index-0 54 % = Engine-Reihenfolge.

### 4.8 Bewertungsfunktion — Multiplayer-Aggregation (RESEARCH B2)
- Falls die Utility Gegner linear aufsummiert: ersetzen durch
  `meinScore − maxGegner − λ·Mittel(übrige)` mit λ ≈ 0,25–0,5, plus harte
  Overrides: Gegner gewinnt nächsten Zug ⇒ Verlust, außer beantwortbar;
  mein Lethal-Bonus skaliert mit dem Bedrohungsrang des Opfers; eigene
  Überlebens-Uhr ≤ 1 ⇒ Überleben dominiert. Zielgröße ist P(Sieg), nicht
  Platzierung oder Lebensmarge (2. = 4. Platz).

## 5. Instrumentierung (Phase 0, Voraussetzung für ehrliche A/Bs)

Dem `PilotStateView` fehlen für §4 voraussichtlich: Spielphase/Segment,
Stack-Inhalt, je Gegner: erlittener Commander-Schaden je Commander, offenes
Mana, Commander-Uhren. Was davon die Bridge liefern kann, ohne die
Aktor-Scoping-Regel zu brechen, ist zu klären; was nicht lieferbar ist,
wird als UNKNOWN markiert und die zugehörige Regel fällt aus (kein Raten).
Zusätzlich: Pilot-Rechenzeit je Entscheidung als eigene Metrik ins
Transkript (heute nur Gesamt-Wanduhr je Spiel).

## 6. Phasenplan mit Messprotokoll

Messung je Phase wie in M4: gepaarte Seeds, eingefrorener Gegner-Tisch
(M4-Tische + Precon-Pods aus #978), Baseline = aktueller Pilot am selben
Pin; berichtet werden Siegquoten-Delta mit Intervall (Verdikt-Wortlaut wie
in #976: „UNDECIDED, could only see effects of at least X" statt
„kein Unterschied"), Mediane Entscheidungszeit, Entscheidungs-Signaturen
(Index-Raten der geänderten Klasse). Pilot-Änderungen brauchen vor Merge
den Real-Game-Vergleich ≥10 Seeds (Repo-Regel); für Verhaltensphasen
empfehle ich ≥50 Seeds je Tisch, weil die erwarteten Effekte kleiner sind
als Deck-Effekte.

| Phase | Inhalt | Risiko | Erwarteter Effekt |
|---|---|---|---|
| 0 | Instrumentierung (§5) + Fast-Paths (§3) | keins (verhaltensneutral; Twin-Hash muss gleich bleiben, außer Caching ändert Reihenfolgen — dann begründen) | Speed-Hygiene, Messbarkeit |
| 1 | Ziel-Leiter + Besitzer-Uhren (4.2) | klein (eine Komponente) | Zielqualität aller Removal-/Kampfziele |
| 2 | Mulligan-Regel + Bottoming (4.4) | klein | Eröffnungsqualität; an Keep-Raten + Siegquote messbar |
| 3 | Kampf-Paket: Fokus, Crackback, Block-Regel (4.3) | mittel | Kampf ist 2,6 % der Entscheidungen, aber spielentscheidend |
| 4 | Timing-Gates + Reaktions-Schwelle (4.1), May/X/Farbe (4.5) | mittel | Weniger verschenkte Fenster, konsistente Kostenentscheide |
| 5 | Zahlungs-Solver (4.6) + Trigger-Ordnung (4.7) + Aggregation (4.8) | mittel | Konsistenz + Speed in 19 % der Entscheidungen |

## 7. Explizit nicht tun

- Kein MCTS/ISMCTS, keine Simulation im Entscheidungsloop, kein LLM je
  Entscheidung (Kosten: §3; Evidenz RESEARCH B3).
- Keine Politik-/Deal-Logik über Selbstinteresse hinaus; kein Kingmaking,
  kein Trotz-Term (A3).
- Keine Verwendung fremder verdeckter Informationen, auch nicht „nur
  statistisch" aus gegnerischen Decklisten über das hinaus, was der eigene
  State-View legal zeigt.
- Keine Änderung an Engine/Bridge für Pilot-Zwecke in dieser Lane —
  Bridge-Änderungen brauchen Requalifizierung (PB-03 → Seal) wie gehabt.

## Anhang: Herkunft der Zahlen

- Vollzensus: `census.json` + `mine4.py` (dieser Ordner); Vorläufer:
  `handover/2026-10-23/game-mining/BERICHT.md` und `VERTIEFUNG.md`
  (mine_m4/mine2/mine3, aggregates*.json).
- Spiel-Records: `handover/2026-10-23/game-records/` (Manifest aller 2.033
  Transkripte; Vollkorpus lokal, Wege dort beschrieben).
- Externe Evidenz: `RESEARCH.md` (dieser Ordner; Abschnitte A/B, Quellen
  verlinkt; Einordnung: A ist überwiegend Experten-Konsens, B teils
  gemessen/publiziert, teils dokumentiertes Verhalten offener Projekte;
  kein publiziertes System spielt volles 4er-Commander im ms-Budget — die
  Übertragung ist begründete Schlussfolgerung, kein Messwert).


## 8. Nachtrag (24.10., Owner-Rückfrage): Zeit-Zerlegung und weitere Befunde

**Gemessene Zeit-Zerlegung einer Simulation** (ein Pod, 3.588 Entscheidungen,
Pin v11, games-per-jvm 1, cProfile; Pod-Wandzeit 161,4 s, Prozess gesamt
165,7 s; `LOCAL_OBSERVED`, ein Spiel auf dieser Box — Anteile, keine
Universalkonstanten):

| Block | Zeit | Anteil |
|---|---|---|
| Engine (Java-Bridge-Kindprozess, CPU) | 158,3 s | **~96 %** |
| Pilot-Bewertung (`choose_action`/`evaluate_action` kumulativ) | 1,5 s | **~1 %** (0,43 ms/Entscheidung) |
| JSON/Protokoll (Python-Seite, Eigenzeit) | 0,3 s | ~0,2 % |
| Start/Skript/JVM-Boot (außerhalb der Pod-Wandzeit) | ~4,3 s | ~3 % (per Batch amortisiert → ~0) |

Der Python-Elternprozess wartet den Rest der Zeit auf das Kind (Lock-Wartezeit
129 s im Profil). cProfile bläht die Python-Werte eher auf — der Pilot-Anteil
ist also eine Obergrenze. **Konsequenz:** Selbst ein zehnmal so rechenintensiver
Pilot kostete <10 % Wandzeit; ein doppelt so teurer ~1 %. Effizienz-Arbeit
gehört an die Engine-/JVM-Seite (Fork-Lane: Zustands-Kopien in XMage,
Repository-Scan je JVM, GC) — nicht an den Piloten. Suchverfahren bleiben
trotzdem raus: Sie kosten das 100- bis 1000-Fache des Pilot-Budgets, nicht
das 2- bis 4-Fache (§3). Transkript-Schreiben ist zeitlich vernachlässigbar
(0,2 %), bleibt aber ein Speicher-Thema (P7: 3,8 MB/Spiel).

**Weitere Befunde zu Pilot-Intelligenz (aus Zensus + Code-Lektüre):**

- **Gleichstands-Verborgenheit:** `_select` rundet die Utility auf
  `policy.precision` und bricht Gleichstände per `action_id` (= Engine-
  Reihenfolge). Wie oft der Sieg dadurch an die Reihenfolge fällt, ist aus
  Transkripten nicht messbar (Utilities stehen nicht drin) — Instrumentierung:
  Top-2-Utility-Marge je Entscheidung mitschreiben (ergänzt §5).
- **Shortlist-Abschneiden:** `choose_action` kürzt die sortierten Kandidaten
  auf `policy.shortlist`, bevor `_select` wählt. Alles jenseits der Shortlist
  ist unerreichbar — Shortlist-Größe ist ein Qualitätsparameter, Audit lohnt.
- **Konfigurations-Audit:** Der Pilot besitzt `mistake_rate` und einen
  Softmax-Modus; im DETERMINISTIC-Modus sind beide wirkungslos. Welche
  Konfiguration die Produktionsläufe (M4-Korpus) fuhr, ist aus den
  Transkripten nicht ablesbar — vor Phase 1 festhalten und einfrieren.
- **Modus-Wahlen:** `mode` nimmt in 37 % die erste Option; es gibt keinen
  modus-spezifischen Utility-Term (Top-Modus: „exile target player's
  graveyard.", 3.630×). In §4.5 mitbehandeln.
- **Leerwahlen bei `choose_object`:** Häufigste „Wahl" ist die leere Auswahl
  (2.388×) — kann bei optionalen Effekten korrekt sein, gehört aber auf die
  Audit-Liste von §4.5 (May-Verhalten).
- **Erzwungene Entscheidungen sind Protokoll-Overhead, kein Pilot-Thema:**
  26,6 % aller Entscheidungen haben genau eine legale Option; der Fast-Path
  (§3) gehört in den Protokoll-Client (ohne Pilot-Aufruf beantworten), nicht
  in die Bewertungslogik.
