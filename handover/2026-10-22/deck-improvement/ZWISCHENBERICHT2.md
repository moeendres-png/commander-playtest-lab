# M4 — Zwischenbericht 2 (Schritt 3 nach Nachtrag 1, Stand vor Schritt 4)

Stand 2026-10-22 abends. Dieser Bericht ersetzt die Schritt-3-Fassung aus
`SCHRITT3.md` nach den Auflagen aus Nachtrag 1 (§2, §5). Source Lock
unverändert Lab `d48bbe5f2`, Pin v11, JAR `69aa31eb…`. Alle Zahlen
LOCAL_OBSERVED, Erwartungen MODELED, Unbekanntes UNKNOWN.

## 0. Umstellungen nach Nachtrag 1

- Die laufenden Einzeltausch-Läufe wurden gestoppt (66 Teil-Records des
  RogShai-Laufs bleiben lokal als Beleg, werden nicht ausgewertet).
  Begründung übernommen: Nachweisgrenze der Einzelläufe ±0,177 (Prefilter)
  liegt weit über jedem plausiblen Einzelkarten-Effekt; die erwarteten
  Urteile wären UNDECIDED gewesen (MODELED). Stattdessen Bündel nach §2.4.
- Sammlungsregel neu (§2.1/§5.5): Maßgeblich ist allein
  `sammlung-2026-09-19-flach.txt` mit frei = Anzahl − Exemplare in RogShai
  − Exemplare in Chulane. **Diese Datei ist bei mir nicht angekommen**
  (Chat-Anhang, Repo, Handover-Branch und Dateisystem durchsucht) — der
  Owner ist informiert und um erneutes Anhängen gebeten. Bis dahin sind
  alle frei-Werte unten **vorläufig**, gerechnet gegen die vom Owner im
  Chat gepostete Sammlungsliste; sie deckt sich mit den drei von Claude
  aus der maßgeblichen Datei bestätigten Werten (Faerie Mastermind frei 0,
  Glacial Fortress frei 0, Azorius Signet frei 1). Endprüfung folgt bei
  Dateieingang, Abweichungen werden korrigiert gemeldet.
- Wegen frei = 0 ausgeschieden: **3 Karten** — Faerie Mastermind und
  Glacial Fortress (Einzeltausche C6/C7, von Claude bestätigt) sowie
  Port Town (im Bündelbau für Chulane-CA verworfen: 1 Sammlung −
  1 Exemplar in RogShai).

## 1. Spielanteile statt Cast-Summen (§2.2)

Neuauswertung der Baseline-Records: je Karte der Anteil der 100 Spiele
(Baseline-Arm), in denen sie mindestens einmal gewirkt/ausgespielt wurde,
dazu die Zahl der Spiele, in denen sie als legale Option angeboten wurde.
Volle Tabellen: `share_rogshai.json`, `share_chulane.json`.

Reaktive Gruppe (eigene Zählung; niedriger Anteil ist dort kein Mangel):
- RogShai: An Offer You Can't Refuse 16 %, Brush Off 15 % (Schutz),
  Chain Reaction 12 % (Wipe), Counterspell 13 %, Dovin's Veto 15 %,
  Louisoix's Sacrifice (Counter-Modus, Anteil aus Cast-Tabelle),
  Negate 16 %, Wash Away 14 %, Whirlwind Denial, Winds of Rath 12 %
  (Wipe), Blasphemous Act (Wipe), Path to Exile, Swords to Plowshares,
  Chaos Warp, Reality Shift, Vandalblast (Entfernung/Interaktion).
- Chulane: Arcane Denial 11 %, Negate 5 %, Fumigate 12 % (Wipe),
  Farewell 14 % (Wipe), Silence 41 %, Swords to Plowshares,
  Brazen Borrower (Bounce), Voracious Greatshark (Counter-Kreatur),
  Tyvar's Stand und Veil of Summer (Schutz).

Nicht reaktive Karten unter 10 % Spielanteil: **nur Irrigated Farmland
(2 %)** — beide Decks sonst ≥ 7 % (Chulane: Whirler Rogue 7 %).

## 2. Irrigated Farmland (§2.3): Pilot-Befund, kein Deckmangel

Farmland wurde in 13 der 100 Spiele als Spieloption angeboten, in 2
gespielt — und in **allen 11** übrigen Fällen stattdessen **gecyclet**
(angenommene Cycling-Aktivierung im selben Spiel). Beispiel:
`custom/rogshai|seed=20|seat=1` (weitere: Seeds 25/2, 19/2, 3/2, 13/3).
Der Pilot nutzt die Karte als Cantrip und zieht sie der Land-Ablage vor,
solange andere Länder verfügbar sind. Die Karte erfüllt damit eine
Funktion; ihr niedriger Spielanteil misst Pilot-Verhalten. **R1 ist als
Deckbefund hinfällig**; die Karte wird in keinem Bündel angetastet.
Gleiche Prüfung für alle nicht reaktiven Karten < 10 %: außer Farmland
keine (Chulane-Minimum sonst Whirler Rogue 7 %, angeboten 23 — dort liegt
kein Cycling-/Alternativgebrauch vor; der Anteil ist ein echter
Niedrigwert und Rogue steht regelkonform in Bündel C-B).

## 3. Einzeltausche: verworfen (§2.4, §5.4)

Alle 14 Einzeltausche aus SCHRITT3.md sind gestrichen: Nachweisgrenze
±0,177 bei 100 Paaren gegenüber einem plausiblen Einzelkarten-Effekt von
wenigen Prozentpunkten (MODELED) — die Läufe hätten keine entscheidbare
Aussage geliefert. Zusätzlich waren C6/C7 nicht baubar (frei = 0) und
C1/C2/C6/R3 verstießen gegen §2.2 (reaktive A-Seiten). Die Prefilter-
Wiederholung nach Merge von Lab-PR #968 steht noch aus (PR offen, Head
`e96abac00`, Stand 19:40); sie wird mit neuem Source Lock nachgeholt und
die Deltas werden im Endbericht neu benannt.

## 4. Die Bündel (je Deck 3, je 3–4 Tausche, alle READY)

Nachweisgrenze des Bündel-Designs (Seeds 1–50, Rotation, 200 Paare je
Variante, Prefilter): **±0,125** für jedes Bündel.

RogShai (Manabasis-Befund: R 15 Quellen bei 31 Pips, W 13 bei 12):
- **R-A Manabasis** — Adarkar Wastes ⇒ Temple of Epiphany,
  Prairie Stream ⇒ Restless Spire, Skycloud Expanse ⇒ Swiftwater Cliffs
  (drei W/U- ⇒ U/R-Quellen). Prefilter **WARN**: Ishai-Castwahrschein-
  lichkeit T4 (play) 0,589 → 0,535 (W-Verlust) — der Zielkonflikt ist der
  Gegenstand der Messung, kein Block.
- **R-B Schwächste nicht reaktive (gleiche MV)** — Mana Geyser (12 %) ⇒
  Pyromancer's Goggles (MV5), Veyran, Voice of Duality (12 %) ⇒ Rootha,
  Mercurial Artist (MV3), Kediss, Emberclaw Familiar (16 %) ⇒ Sram,
  Senior Edificer (MV2). Prefilter **WARN** (R −1 nach alter Zählung,
  Wiederholung nach #968 ausstehend). Vorbehalt: Veyran und Kediss sind
  Motor-Karten; ihr Spielanteil (Legenden, Einzel-Exemplare, entfernte
  Permanents) misst ihre Wirkung in liegenden Spielen nicht — die
  Tausche testen funktionale Alternativen auf denselben Slots, die
  Auswahl folgt der Sortierregel aus §2.2/§2.4.
- **R-C Kurve** — Furygale Flocking (MV10) ⇒ Goldspan Dragon (MV5),
  Dig Through Time (MV8) ⇒ Jace's Ingenuity (MV5), Mana Geyser (MV5) ⇒
  Izzet Signet (MV2). Prefilter PASS_TO_GAMES.

Chulane (Manabasis-Befund: nur 4 Nichtland-Quellen, U 15 Quellen bei
32 Pips, W 13 bei 20; Kommandant in 11/100 Spielen nie gewirkt):
- **C-A Manabasis** — Mechanized Production (14 %) ⇒ Simic Signet,
  Noxious Newt (14 %) ⇒ Azorius Signet, Wilderness Reclamation (12 %) ⇒
  Talisman of Unity, Azorius Chancery ⇒ Tranquil Cove (Bounce-Land gegen
  Tapland ohne Rückschritt). Drei neue Nichtland-Quellen (4 → 7).
  Prefilter PASS_TO_GAMES.
- **C-B Schwächste nicht reaktive (gleiche MV)** — Whirler Rogue (7 %)
  ⇒ Solemn Simulacrum, Adrix and Nev (10 %) ⇒ Alandra, Sky Dreamer,
  Wood Elves (11 %) ⇒ Selvala, Explorer Returned, Wilderness
  Reclamation (12 %) ⇒ Teferi's Ageless Insight (alle MV4/MV3 wie die
  A-Seiten). Prefilter PASS_TO_GAMES.
- **C-C Kurve** — Rampaging Baloths (MV6) ⇒ Augur of Autumn (MV3),
  Aerial Extortionist (MV5) ⇒ Morska, Undersea Sleuth (MV3),
  Psychosis Crawler (MV5) ⇒ Mischievous Mystic (MV2); MV-Summe −8.
  Prefilter PASS_TO_GAMES.

Alle B-Karten frei (vorläufig) ≥ 1, alle Bündel-Decks READY
(deck_readiness.py). Bündel-JSONs liegen bei (`bundles/`).

## 5. Weiteres Vorgehen (Schritt 4)

1. Bündel-Läufe je Deck (Baseline + 3 Bündel, Seeds 1–50, Rotation,
   stop-when-decided, look-every 5, Retry-Durchlauf). Nur ein entschieden
   besseres Bündel wird in Einzeltausche zerlegt; UNDECIDED bleibt
   UNDECIDED.
2. Nebenkennzahlen je Variante (ohne Urteil): Mulligan-Anteil, Anteil
   Spiele mit Kommandanten-Cast, Zug des ersten Kommandanten-Casts (§2.5,
   Wegwerfskript über bench._setup, Zeitbox ~1 h, sonst UNKNOWN).
3. Tisch-Sensitivität (§2.6): Das beste Bündel je Deck läuft zusätzlich
   an einem Tisch aus drei READY-Precons (Auswahl per deck_readiness,
   Farbprofil nah an den Zielgegnern; die drei Listen werden im
   Endbericht benannt).
4. Nach Merge von #968: Prefilter-Wiederholung auf neuem Source Lock.

Beilagen: `share_rogshai.json`, `share_chulane.json` (Spielanteile +
Angeboten-Zahlen aller Karten), `prefilter_bundles_rogshai.json`,
`prefilter_bundles_chulane.json`, `bundles/*.json` (6 Bündel-Decks),
`bundles.json` (Bündel-Definitionen mit A/B-Paaren).
