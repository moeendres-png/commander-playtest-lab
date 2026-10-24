# Max-Review — Pass D: Recherche

Stand: 2026-10-24 (Recherche-Datum). Jede Quelle mit URL + Abrufdatum + Version,
soweit verfügbar. **Belegt** = selbst gelesen (Primärquelle oder Volltext/Abstract).
**Gehört** = nur aus Sekundärquelle/Erinnerung, nicht verifiziert — keine
Projektentscheidung darf darauf allein stehen. Nichts hier ersetzt die
Rules-Autorität XMage (stehende Regel) oder eine Messung im eigenen Repo.

## Quellen-Tabelle

| # | Quelle | URL | Datum/Version | Status |
|---|--------|-----|---------------|--------|
| Q1 | XMage-Fork, KI-Plugins (lokaler Clone wt-mage-v13) | `Mage.Server.Plugins/Mage.Player.AI(.MAD/.AIMCTS)/` | Pin v13 `90f5c4d3f8` | Belegt (Code gelesen) |
| Q2 | Ward/Cowling/Powley, „Monte Carlo search applied to card selection in MTG" | https://www.researchgate.net/publication/224603720_Monte_Carlo_search_applied_to_card_selection_in_Magic_The_Gathering | IEEE CIG 2009, S. 9–16 | Belegt (Abstract + Zitation) |
| Q3 | Cowling/Ward/Powley, „Ensemble determinization in MCTS for MTG" | IEEE Trans. CI Games 4(4), 2012, S. 241–257 (via Q4-Referenzen) | 2012 | Belegt (Referenzliste in Q4) |
| Q4 | „Monte Carlo Tree Search Experiments in Hearthstone" (MCTS + Expertenwissen) | https://fenix.tecnico.ulisboa.pt/downloadFile/1970719973966524/paper.pdf | o. J. (zitiert Q2, Q3) | Belegt (Volltext-Auszug) |
| Q5 | Agajanian/Brent, „Tree Search — MTG AI" (MCTS-Varianten) | https://www.cs.hmc.edu/~jagajanian/cs151/ | 2013-05-10 | Belegt (Abstract + Implementierung) |
| Q6 | Buffalo/Pearson/Klein, „Realizing Common Random Numbers" (CRN) | https://arxiv.org/pdf/2603.11084 | arXiv:2603.11084v1, März 2026 | Belegt (Abstract) |
| Q7 | Law, Simulation Modeling and Analysis (CRN, Control Variates) | Lehrbuch, McGraw-Hill 2015 (via Q8-Referenzen) | 2015 | Gehört (nur Referenzliste) |
| Q8 | „Optimizing Simulations with Common Random Numbers" | https://www.numberanalytics.com/blog/optimizing-simulations-common-random-numbers | Abruf 2026-10-24 | Belegt (Formel Var(X−Y)) |
| Q9 | Group-Sequential-Designs, Alpha-Spending (Lan–DeMets 1983 u. a.) | https://zhaowenguo.quarto.pub/zhaowen-guo/statistics/sequential-testing/index.html | Abruf 2026-10-24 | Belegt (Übersichtstabelle) |
| Q10 | Commander Spellbook (EDHREC-Guide, >100.000 Combos) | https://edhrec.com/guides/how-to-use-commander-spellbook-the-combo-search-engine | Abruf 2026-10-24 | Belegt (Guide-Text) |
| Q11 | Mulligan-Mathematik (hypergeometrisch, London-Regel) | https://mathgathering.substack.com/p/the-math-behind-the-mulligan | Abruf 2026-10-24 | Belegt (Methode; Daten: 17lands 2019) |
| Q12 | Java HashSet: keine Iterationsreihenfolge-Garantie | https://www.digitalocean.com/community/tutorials/collections-in-java-tutorial | Abruf 2026-10-24 | Belegt (Tutorial, sekundär zu JDK-Doku) |
| Q13 | Forge-AI (cardforge/forge) | https://github.com/cardforge/forge (API: 404 am 2026-10-24) | — | NICHT VERIFIZIERT |
| Q14 | Cockatrice (keine KI, nur virtueller Tisch) | https://github.com/Cockatrice/Cockatrice | Abruf 2026-10-24 | Belegt (README: Client/Server/Oracle, keine KI-Komponente) |
| Q15 | Magarena (KI-Gegner, begrenzter Kartenpool) | https://cdn-b.saashub.com/compare-cockatrice-vs-magarena | Abruf 2026-10-24 | Gehört (Vergleichsportal, keine Primärquelle) |

## D1 — Pilot/KI in anderen Magic-Engines

### XMage-eigene KI (Q1, belegt)

Der Fork enthält **drei** KI-Plugins, alle im Clone `wt-mage-v13` gelesen:

- `Mage.Player.AI/ComputerPlayer.java` (1.368 Zeilen) — die klassische
  heuristische KI.
- `Mage.Player.AI.MAD/ComputerPlayer6.java` (1.220 Zeilen) — „MAD"-KI:
  simuliert bis `MAX_SIMULATED_NODES_PER_CALC = 5000` Knoten pro Berechnung
  und bewertet Stellungen mit `GameStateEvaluator2` (Score-Modell, kein MCTS).
- `Mage.Player.AIMCTS/ComputerPlayerMCTS.java` (344 Zeilen) — MCTS-KI auf
  `MCTSPlayer`, mit Thread-Pool über alle Kerne und
  `THINK_TIME_MULTIPLIER = 2.0` (Denkzeit = Skill × 2, Einheit im Code
  nicht weiter belegt).

**Folge für uns:** XMage hat MCTS bereits — aber als *Spieler im Server*,
nicht als externe Piloten-Bibliothek. Das Lab nutzt keine dieser KIs
(Grep über `wt-maxreview/src/` und `engine-bridge/src/` leer); der Lab-Pilot
ist bewusst extern und entscheidet nur über die Bridge. Eine Wiederverwendung
der XMage-MCTS für den Lab-Piloten würde bedeuten: Spielzustand aus der Bridge
zurück in XMage-Spielerobjekte zu spiegeln — das ist ein zweiter, versteckter
Pfad neben der Bridge und bricht die Architektur (einziger Pilot = Bridge-
Entscheider). **Reuse-Urteil: nein, nicht übernehmen; als Referenz für
Score-Komponenten (MAD) lesenswert.**

### MCTS-Literatur (Q2–Q5, belegt)

- Q2 (2009): MCTS für Kartenauswahl in MTG, UCT. Zentrales Hindernis schon
  damals: **unbekannte Information (Gegnerhand) + Stochastik (Ziehen)**.
- Q3 (2012): Ensemble-Determinisierung — mehrere determinisierte Welten
  (verdeckte Karten geraten) + MCTS je Welt, Ergebnisse aggregiert.
- Q4 (Hearthstone): **MCTS mit Expertenwissen schlägt Vanilla-MCTS in allen
  Situationen, oft deutlich** — Domänenwissen (Deck-Datenbank gegen
  Imperfect Information + Heuristik zur Baumführung) ist der Hebel, nicht
  mehr Simulationen allein.
- Q5 (2013): Vereinfachtes MTG (2 Spieler, 60 Karten, nur Main/Attack/Block),
  20 Zufallssimulationen je Folgestellung. Heuristisch geführte Varianten:
  schneller, aber **deutlich schwächer** — der Trade-off ist dokumentiert,
  nicht nur vermutet. Eine „heuristically guided swarm tree search" war
  **zu langsam, um je zu terminieren**.

**Folge für uns:** Bestätigt die Owner-Entscheidung (kein Zeitbudget,
MCTS draußen) aus unabhängiger Literatur: Bei unserem Budget (~1 ms/Pilot-
Entscheidung, gemessen 2026-10-24) ist MCTS nicht „knapp daneben", sondern
um Größenordnungen außerhalb — selbst die 2013er Mini-Variante brauchte
Sekunden. Der dokumentierte Hebel ist dagegen exakt unser Weg:
**Expertenwissen in der Bewertung** (Zielleiter, Block-als-Ganzes,
Mulligan-Regel), nicht Suche. Q4 stützt zusätzlich R-02 (Sonderfall-Register
als explizites Expertenwissen) und R-08 (Guides als Wissensquelle).

### Forge (Q13, NICHT VERIFIZIERT)

Der Forge-Quellcode war am 2026-10-24 per GitHub-API nicht erreichbar
(`cardforge/forge` → 404, auch auf Repo-Root-Ebene). Sekundärbelege
(Forum: Auto-Pay nutzt dieselbe Logik wie die KI; SaaSHub: Single-Player
gegen KI in mehreren Schwierigkeitsgraden; Neo-Forge-Ankündigung 2026-09-26:
33.000+ Karten, Commander bis 4 Spieler gegen KI) sind **gehört, nicht
belegt**. Keine Aussage über Forge-AI-Interna (Angriff/Block/Zahlung) steht
in diesem Review auf Forge-Quellen. **Offen:** Forge-AI-Code lesen, sobald
der Pfad geklärt ist (vermutlich Repo umgezogen) — dann als Ergänzung zu
Q1, nicht als Ersatz.

### Cockatrice, Magarena, Arena/MTGO (Q14, Q15)

- Cockatrice: virtueller Tisch (Client + Server + Oracle-Kartendatenbank),
  **keine Regeln-Engine, keine KI** — für Pilot-Fragen irrelevant, für
  Kartenmetadaten allenfalls als Datenquelle (Scryfall ist besser).
- Magarena: eigene KI, aber **begrenzter Kartenpool** und kein
  Commander-Schwerpunkt (Q15, gehört) — kein Reuse-Kandidat.
- Arena/MTGO: geschlossene Systeme, keine Quellen — nicht weiter verfolgt.

## D2 — Commander-Wissen: Bedrohung, Politik, typische Bot-Fehler

**Belegt:**

- Commander Spellbook (Q10): >100.000 katalogisierte Combos, EDHREC-
  Guide, MIT-lizenzierte Datenbank (Discord-About: „database and source
  code completely free and open source under the MIT license"). **Reuse:**
  Als *Metadatenquelle* für Guide-Generierung (welche Karten comboen)
  brauchbar; als *Regelwissen* unbrauchbar (Katalog sagt nicht, ob die
  Engine die Combo ausführen kann — das entscheidet allein XMage).
- Mulligan-Mathematik (Q11): Eröffnungshände folgen der hypergeometrischen
  Verteilung; London-Regel (7 ziehen, n auf den Boden). Die Arbeit leitet
  eine optimale Stoppregel ab und nutzt 17lands-Bo3-Daten (2019) als
  Mulligan-Steuer. **Folge:** Stützt Phase 2 methodisch (Castbarkeit statt
  Landzahl ist eine Verfeinerung derselben Frage: „Kann ich kurven?"),
  aber die 17lands-Daten sind Limited/60-Karten, **nicht** Commander —
  keine Zahl daraus darf in Commander-Regeln übernommen werden.

**Gehört (nicht belegt, keine Entscheidung darauf):**

- „Typische Bot-Fehler" (Geschenke an den Falschen, Blocken ohne Plan,
  Wipes während man führt) sind in unseren eigenen Transkripten gemessen
  (Phase-1-Body: Geschenke 2/26→26/26; Phase-3a-Body: Blockrunden mit
  tödlichem Rest 19→15) — das ist unser Beleg, keine Literatur.
- Commander-Politik (Drohungsbewertung, „wer ist vorn", Absprachen) hat
  **keine belastbare formale Quelle** in dieser Recherche gefunden:
  EDHREC/Spellbook katalogisieren Karten und Combos, keine Politik-
  Modelle. Das Multiplayer-Aggregationsziel aus dem Pilot-Handoff
  (meinScore − maxGegner − λ·Mittel) bleibt damit eine **eigene
  Modellannahme (MODELED)**, keine übernommene Theorie — in 03 als solche
  zu kennzeichnen. Kein Paper, kein Buch, keine Engine-Doku belegt eine
  bewährte Commander-Bedrohungsleiter.

## D3 — Statistik für wenige, teure, gepaarte Spiele

Das ist das Feld mit dem direktesten Ertrag für R-11/R-12.

### Common Random Numbers — und ihre Bruchstelle (Q6, belegt)

Gepaarte Seeds sind die Simulations-Technik **Common Random Numbers**:
gleiche Zufallsströme für beide Varianten → Var(X−Y) = Var(X)+Var(Y)−2Cov,
positive Kovarianz senkt die Varianz der Differenz (Q8, Formel belegt).
Q6 (arXiv März 2026, Abstract gelesen) zeigt die Bruchstelle, die exakt
unsere Situation trifft: Bei zustandsbehafteten PRNGs **verschiebt jede
Pfadänderung (eine andere Pilot-Entscheidung) den Draw-Index aller
folgenden Ereignisse**. Gepaarte Vergleiche sind dann nicht mehr „gleiche
Welt, andere Regel", sondern „andere Regel + neu gemischte Zukunft".
Abhilfe laut Q6: Counter-basierte RNGs (Philox/Threefry) mit
Ereignis-Identifikatoren statt Draw-Index.

**Folge für uns (wichtig, neu):** Unsere 23/24-bit-identischen Real-Pod-
Paare (Phase 2/4b) zeigen, dass die Divergenz in der Praxis klein ist —
aber sie ist nicht null, und sie wächst mit der Effektstärke der Änderung.
Regel für künftige Vergleiche: **Neben der Differenz immer die
Divergenzrate berichten** (Anteil Paare, die nach der ersten abweichenden
Entscheidung auseinanderlaufen), und bei großen Effekten die CRN-Annahme
explizit als verletzt markieren. Das ist keine Statistik-Kosmetik, sondern
die saubere Lesart unserer eigenen Twin-Hash-Ergebnisse.

### Control Variates (Q7 gehört, Q8 belegt)

Kontrollvariable = Größe mit bekanntem Erwartungswert, korreliert mit der
Zielgröße; Schätzer Y − b(X − E[X]) mit b = Cov/Var. Kandidaten bei uns:
Lineal-Kennzahlen (billig, offline) als Kontrolle für teure
Echtspiel-Maße — **ungeprüfte Idee**, kein Beleg, dass die Korrelation
ausreicht. Gehört in R-11 als Experiment, nicht als Verfahren.

### Sequentielle Designs (Q9, belegt)

Group-Sequential-Designs mit Alpha-Spending (Pocock, O'Brien-Fleming,
Lan–DeMets 1983): vorab geplante Zwischenanalysen mit vorab verteiltem
α — frühes Stoppen bei starkem Effekt **ohne** α-Inflation, aber nur wenn
die Looks vorab definiert sind. **Folge:** Unsere Praxis („24 Seeds, dann
schauen") ist genau das, was Alpha-Spending verbietet, wenn man danach
noch „signifikant" sagen will. Da wir ohnehin „UNDECIDED" statt
Signifikanz-Claims berichten, ist das kein Verstoß — aber ein
vorab definierter Stopp-Plan (z. B. Look nach 12/24/48 mit
O'Brien-Fleming-Grenzen) würde aus „UNDECIDED" ein „geplant UNDECIDED"
machen und ist billig umzusetzen (R-11).

### Was Holm leistet — und was nicht (eigene Messung, kein Zitat nötig)

Holm korrigiert multiples Testen über die 17 Metriken. Er korrigiert
**nicht**: CRN-Bruch (s. o.), Pod-Abhängigkeit (Real-Pod ≠ Precon-Pod),
und die Tatsache, dass „same" bei n=24 nur „Effekt kleiner als
Nachweisgrenze" heißt. Das steht so in 03/R-11; die Literatur (Q6, Q9)
stützt es jetzt von außen.

## D4 — Reuse-first (§9): Was ersetzt ein ganzes Arbeitspaket?

Geprüfte Kandidaten, Urteil je Kandidat:

| Kandidat | Ersetzt | Urteil |
|----------|---------|--------|
| XMage MAD/MCTS (Q1) | Eigenen Piloten | **Nein.** Architekturbruch (s. D1). Nur Score-Ideen lesenswert. |
| Forge-AI (Q13) | Eigenen Piloten / Kampf-Logik | **Unbekannt.** Code nicht erreichbar; selbst bei Verfügbarkeit: zweite Rules-Engine → Verstoß gegen stehende Regel. |
| Commander Spellbook (Q10) | Guide-Recherche, Combo-Wissen | **Ja, als Metadaten.** MIT-lizenziert; in Guide-Pipeline einsetzbar, nie als Regelquelle. |
| Scryfall (bereits genutzt) | Kartenmetadaten | **Ja, bereits Standard.** Keine Änderung. |
| Cockatrice (Q14) | Nichts | Nein — keine Engine, keine KI. |
| Magarena (Q15) | Nichts | Nein — kleiner Pool, kein Commander-Fokus (gehört). |
| MCTS-Literatur (Q2–Q5) | Suche als Pilot-Hebel | **Nein, bestätigt Ausschluss.** Suche ist dokumentiert zu langsam; Expertenwissen ist der Hebel. |
| CRN/Counter-RNG (Q6) | Paarungs-Methodik | **Teilweise.** Counter-RNG wäre ein Engine-Eingriff (Fork, Go nötig); kurzfristig: Divergenzrate berichten (kein Code). |
| Alpha-Spending (Q9) | Auswertungs-Protokoll | **Ja, billig.** Reines Protokoll, kein Engine-Code. |

**Feld-7-Fazit (Reuse):** Kein Kandidat ersetzt ein Arbeitspaket vollständig.
Die größten Reuse-Gewinne sind Protokoll (Alpha-Spending) und Metadaten
(Spellbook) — beides ohne Engine-Eingriff. Das ist ein Befund, kein
Versäumnis: Die Single-Engine-Regel schließt die naheliegenden
„einfach übernehmen"-Kandidaten bewusst aus.

## D5 — XMage/Java-Performance für unsere Last

**Belegt (Q12, sekundär):** `HashSet`/`HashMap` geben **keine
Iterationsreihenfolge** — sie hängt von Hashverteilung, Kapazität und
Rehashing ab. Das ist die externe Bestätigung der #1001-Ursachen (a) und
(b): `SacrificeAllEffect`-HashSet und `ChaosMutation.toSet()` sind keine
„seltenen Bugs", sondern die dokumentierte Konsequenz einer
unspezifizierten Ordnung. Der Fix-Typ (`LinkedHashSet` /
`Collectors.toList()`, Reihenfolge erhalten) ist der kanonische aus der
JDK-Praxis — P-A/P-B in R-16 sind damit nicht nur „Patch-Text", sondern
Standard-Reparatur.

**Eigene Messung (kein Zitat nötig):** Engine ~96 % der Pipeline-Zeit,
Pilot ~1 % (M4/Pilot-Handoff). Externe Java-Performance-Literatur wurde
nicht weiter verfolgt: Die Engpässe sind projektspezifisch (getPlayable-
Kopien, View-Erzeugung) und nur per Profiling im eigenen Code zu belegen
— allgemeine JVM-Tuning-Ratschläge wären hier Rauschen. **Offen:** Ein
gezieltes Profiling (E1/E3) bleibt Teil von R-10, keine Literatur-Lücke.

## Was diese Recherche an 03 ändert (Diff, ehrlich)

1. R-11 wird schärfer: CRN-Bruch (Q6) als explizite Annahme + Divergenzrate
   als Pflicht-Metrik; Alpha-Spending (Q9) als billiger Protokoll-Gewinn.
2. R-08/R-02 gestützt: Q4 belegt, dass Expertenwissen (nicht Suche) der
   Hebel ist — Guides und Sonderfall-Register sind Literatur-konform.
3. MCTS-Ausschluss jetzt doppelt belegt: Owner-Entscheidung + Q2–Q5.
4. D2-Lücke bleibt: Keine belastbare Commander-Politik-Theorie gefunden —
   das Aggregationsziel bleibt MODELED und wird in 03 so gekennzeichnet.
5. Forge bleibt offen (Q13) — kein Urteil, kein Zitat, nur die Lücke.
