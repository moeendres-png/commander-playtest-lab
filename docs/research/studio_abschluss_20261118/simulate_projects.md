# Lane SIMULATE: Wie andere Projekte Commander/MTG-Simulation nutzen — 2026-11-18

**Auftrag:** Nur Web-Recherche, nichts gebaut, nichts gepusht. Suchanfragen generisch gehalten.
**Rahmen:** `research_frame.md` (XMage = Regelautorität; keine neuen Python-Abhängigkeiten; GPL/AGPL nur Ideenquelle; Simulation nie in Tierliste; n/N und Intervall; unbekannt statt 0).
**Vorrecherchen gelesen:** `/home/user/commander-playtest-lab/docs/research/OPEN_SOURCE_LANES_20261117.md` (Abschnitt SIMULATE: Wilson, Fishtest/SPRT, always-valid, OpenSkill, Holm/BH; Forge nur Stichprobe) und `DECKBUILDER_COMPARISON_RESEARCH_20261116.md` (Forge-Verdict-Loop, Monte-Carlo-Goldfish, Preis-/Noten-Tools nicht übernehmen; Goldfish-Mathematik mit hypergeom).

**Kennzeichnung der Belege:**
- **[F]** = Seite per Abruf geprüft (WebFetch am 2026-11-18). Aussage stammt von dort.
- **[S]** = nur Suchtreffer-Snippet gesehen, Seite nicht geöffnet oder nicht abrufbar.
- **Eigenangabe** = Aussage des Projekts oder Autors, nicht von mir nachgerechnet.
- **unbekannt** = auf den abgerufenen Seiten nicht belegt.

---

## 1. Quellen

| # | Quelle | URL | Beleg | Typ / Lizenz (nur was die Seite zeigt) |
|---|---|---|---|---|
| Q1 | Forge Wiki „AI" | https://github.com/Card-Forge/forge/wiki/ai | [F] Seite zuletzt bearbeitet 2026-11-18 | Projekt-Doku; Lizenz auf der Seite **unbekannt** |
| Q2 | Forge-Forum „Headless behavior" / „AI v AI" | https://www.slightlymagic.net/forum/viewtopic.php?p=243768 , …?p=231106 | [S] | Forum, Nutzerberichte |
| Q3 | Cowling, Ward, Powley 2012, IEEE TCIAIG (Ensemble-Determinization MCTS für MTG) | https://eprints.whiterose.ac.uk/75050/1/EnsDetMagic.pdf | [F] PDF heruntergeladen und mit pdftotext gelesen | Paper; Urheberrecht IEEE |
| Q4 | Magarena (Repo) | https://github.com/magarena/magarena | [F] | GPL-3.0 (laut Seite); MCTS-KI laut Acknowledgments |
| Q5 | Magarena-Forum „Magarena 1.37" (Zhang zu Vegas-AI, MCTS) | https://www.slightlymagic.net/forum/viewtopic.php?p=116571 | [S] | Forum |
| Q6 | Zhang, „Building a state of the art AI to play Magic" (Slides) | https://www.slideshare.net/slideshow/building-a-state-of-the-art-ai-to-play-magic-the-gathering/38744310 | [S] (Abruf lieferte nur Fehlerseite) | Slides; Eigenangabe |
| Q7 | Agajanian & Brent, MCTS-MTG-Studentenprojekt (HMC) | https://www.cs.hmc.edu/~jagajanian/cs151/ | [S] | Studentenbericht |
| Q8 | XMage (Repo) | https://github.com/magefree/mage | [F] | MIT (laut Seite); Seite nennt keine MCTS-/Batch-Details; „about 9,000 unit tests" (Eigenangabe) |
| Q9 | XMage-Doku „AI players" (mintlify) | https://mintlify.wiki/magefree/mage/development/ai-players | [S]; Abruf HTTP 404 | Sekundär-Wiki; nur Snippet: `ComputerPlayerMCTS`, Denkzeit `skill * 2.0 s` — **nicht verifiziert** |
| Q10 | Goldfisher (Cadiac, Rust) | https://github.com/Cadiac/goldfisher | [F] | Lizenz **unbekannt**; letzter Commit **unbekannt** |
| Q11 | Hareruyama, Allen Wu, „Using Monte Carlo Simulation to Improve Your Manabases" (2018) | https://article.hareruyamtg.com/article/article_en_405/?lang=en | [F] | Blog, Eigenangabe |
| Q12 | EDHREC, „Simulating available mana beyond the hypergeometric distribution" | https://edhrec.com/articles/simultaing-available-mana-beyond-the-hypergeometric-distribution | [F] | Artikel mit Simulator (Python, „mtg-mana-simulator"); Code-Lizenz **unbekannt** |
| Q13 | teryror, Gist „Rust port" von Karsten-Simulationscode | https://gist.github.com/teryror/57a3099a6566d1ab75bd3fd515ab0380 | [F] | Lizenz **unbekannt**; Attribution auf Karsten/ChannelFireball im Kommentar |
| Q14 | ScrollVault, „How many lands in Commander? 3.75 Million Games" | https://scrollvault.net/guides/commander-land-count-data.html | [S] | **Kommerzielle Seite** (verkauft Rechner), Eigenangabe |
| Q15 | Schulze, „The Math of Landbases in MTG Commander" (Medium) | https://medium.com/@schulze.mtg/the-math-of-landbases-in-magic-the-gathering-commander-3f03aadac92c | [S] | Blog; nennt Abweichung von Multiplayer-Commander |
| Q16 | dylanlott/mtg-sim (Go, Monte Carlo Combo-Anteile) | https://github.com/dylanlott/mtg-sim | [S] | Repo; Aktivität **unbekannt** |
| Q17 | 17lands-Felddefinitionen (MTGA_Draft_17Lands-Doku) | https://unrealities.github.io/MTGA_Draft_17Lands/docs.html | [F] | Doku eines Drittprojekts, nicht 17lands selbst |
| Q18 | 17lands „About" | https://www.17lands.com/about | [F] — Seite lieferte **keinen Inhalt** (nur Titel) | **unbekannt** |
| Q19 | GitHub-Diskussion Bayes-Glättung GIH WR (MTGA_Draft_17Lands #5) | https://github.com/bstaple1/MTGA_Draft_17Lands/issues/5 | [S] | Issue-Diskussion |
| Q20 | Joshy 2024, OpenSkill (arXiv 2401.05451) | https://arxiv.org/abs/2401.05451 | [F] (nur Abstract) | Paper; MIT (Lib, laut Vorrecherche, hier nicht geprüft) |
| Q21 | Playgroup.gg, Turn-Order-Analyse (Stand 2026-11-16) | https://playgroup.gg/commander/turn-order | [F] | Eigenerhebung Casual-Daten, 606.151 Mehrspieler-Partien |
| Q22 | EDHREC, „Does cEDH have a seat order problem?" | https://edhrec.com/articles/does-cedh-have-a-seat-order-problem | [S] | Artikel, qualitativ |
| Q23 | Ward et al. 2020, MTG-Drafting-KI (arXiv 2009.00655) | https://arxiv.org/abs/2009.00655 | [F] (Abstract/Seite) | Paper; Drafting, nicht Spiel |
| Q24 | Miernik & Kowalski 2022, evolvierte Bewertungsfunktionen für CCG-KI (SCITEPRESS) | https://www.scitepress.org/Papers/2022/108069/108069.pdf | [S] | Paper, nicht geöffnet |
| Q25 | NTNU-Masterarbeit „Deckbuilding in MTG using a Genetic Algorithm" | https://ntnuopen.ntnu.no/ntnu-xmlui/handle/11250/2462429?show=full | [S] | Thesis-Eintrag, Inhalt nicht gelesen |
| Q26 | Mahlmann, Togelius, Yannakakis, „Evolving card sets towards balancing Dominion" | https://um.edu.mt/library/oar/bitstream/123456789/22933/1/Evolving_card_sets_towards_balancing_dominion.pdf | [S] | Paper, nicht geöffnet (Brettspiel) |
| Q27 | Forge-Repo, Ordner `forge-gui/res/ai` (AI-Profil-Dateien) | https://github.com/Card-Forge/forge/tree/master/forge-gui/res/ai | [F] Dateinamen gelesen, Inhalt nicht | Lizenz **unbekannt** |
| Q28 | XMage-Repo, Ordner `Mage.Server.Plugins` (Spielmodi und AI-Module) | https://github.com/magefree/mage/tree/master/Mage.Server.Plugins | [F] Ordnernamen gelesen | MIT (Q8) |
| Q29 | neura.market, Architektur-/FAQ-Seite (XMage-MCTS-Prototyp, Stand 2025-12-22) | https://www.neura.market/directories/md-directory/architecture-md-magezero-faq-goals-monpkk87 | [S] | Sekundär, Eigenangabe, nicht geprüft |

Quellen gesamt: **29** (Q1–Q29). Mit Seitenabruf [F] und Inhalt: **14** (Q1, Q3, Q4, Q8, Q10, Q11, Q12, Q13, Q17, Q20, Q21, Q23, Q27, Q28). Q18 wurde abgerufen, lieferte aber keinen Inhalt.

---

## 2. (a) Engine-basierte KI-gegen-KI-Simulation

### Forge (Q1, Q2)
- **Headless-Batch existiert.** [F Q1] Die Wiki beschreibt „sim" im CLI, z. B. `sim -d deck1 deck2 -n 3`; weitere Optionen: `-f` Format, `-t` Bracket/RoundRobin/Swiss, `-p` Spieler, `-m` Best-of, `-c` Zeitlimit in Sekunden (Standard 120). Spiele können sehr lang laufen; Ausgabe landet bei Windows-`.exe` im Log. [S Q2] Nutzerberichte: Reihenfolge der Decks im Befehl hat das Ergebnis verändert (einseitige Ergebnisse), GUI-Läufe waren nicht einseitig. **Eine Seitenreihenfolge-Abhängigkeit ist damit ein bekannter Fehlermodus.**
- **AI-Profile:** [F Q1] Die Wiki-Seite nennt **keine** AI-Profile. [F Q27] Der Ordner `forge-gui/res/ai` listet die Dateien `Cautious.ai`, `Default.ai`, `Experimental.ai`, `Hard.ai`, `Hardest.ai`, `Reckless.ai` (Seite sagt „View all files", evtl. mehr). Inhalt der Profile nicht gelesen → Wirkung je Profil **unbekannt**. Auswahl in Batches: **unbekannt**.
- **Entscheidungslogik:** [F Q1] Keine Simulation und keine Vorhersage in den Entscheidungen; Regeln und Heuristiken, Karten-Hardcoding gilt als „usually not a healthy approach".
- **Stärke (Eigenangabe, Q1):** „Best with Aggro and midrange decks", „Poor to Ok in control decks", „Pretty bad for most combo decks", „can be easy to overcome knowing its weaknesses". Die Einschränkungen gelten auch gegen sich selbst.
- **Lizenz:** auf der Wiki-Seite **unbekannt**. Die Vorrecherche nennt GPL; hier nicht belegt → vor Nutzung prüfen.

### XMage (Q8, Q9)
- [F Q8] MIT-Lizenz, Engine mit „full rules-enforcement", Server kann offline betrieben werden. Die Seite nennt **keine** KI-Klassen und **keinen** Batch-/Headless-Modus.
- [F Q28] Der Repo-Ordner `Mage.Server.Plugins` enthält u. a. `Mage.Player.AI`, `Mage.Player.AI.DraftBot`, `Mage.Player.AI.MAD` und `Mage.Player.AIMCTS`; dazu Spielmodi `Mage.Game.CommanderDuel` und `Mage.Game.CommanderFreeForAll`. **Nur Ordnernamen gelesen.** Dass `AIMCTS` tatsächlich MCTS implementiert, ist aus dem Namen **nicht belegt**; Denkzeit-Skalierung nur [S Q9].
- [S Q9, nicht verifiziert] Snippet nennt `ComputerPlayerMCTS` (Modul `mage-player-aimcts`) und Denkzeit proportional zum Skill (`skill * 2.0 s`). Die Seite selbst war nicht abrufbar (404). **Bewertung: nur als Hinweis, im Repo prüfen.**
- [S Q29] Sekundärquelle, Stand 2025-12-22 (neura.market): Ein Prototyp eines MCTS-Agenten in XMage nutzte einen eigenen Engine-Fork plus lokalen Server; Eigenangabe, nicht geprüft.
- **Folgerung für uns:** XMage als Regelautorität ist MIT und lokal betreibbar. Ob die vorhandenen KI-Klassen für Massenläufe taugen, ist eine **Repo-Frage**, keine Web-Frage.

### Magarena (Q4, Q5, Q6)
- [F Q4] GPL-3.0; die KI ist laut Acknowledgments **MCTS** (Zhang). Headless-/Batch-Modus: auf der Seite **nicht erwähnt**.
- [S Q5] Zhang: frühe Versionen „cheatten" (sahen verdeckte Informationen), später faire Variante; Vegas-AI als Monte-Carlo-Baseline (Eigenangabe, 2013).
- [S Q6] Slides (Abruf fehlgeschlagen): MCTS vs. Minimax bei 1 s vs. 4 s Denkzeit; offene Probleme u. a. schlechtes Spiel, wenn die KI im Rückstand ist. Zahlen **nicht gesehen**.

### Cockatrice
Nur Mensch-gegen-Mensch-Client laut Vorrecherche; keine KI-Simulation. **nicht untersucht** (nicht nötig).

### Akademische Engine-KI: Cowling et al. (Q3) — [F, PDF gelesen]
- Methode: **Ensemble-Determinization** für verdeckte Informationen; Zugerzeugung als binärer Entscheidungsbaum; Gegner: regelbasierte Spieler (Random, „Expert Rules").
- **Zahl 1 (Expert-Regelspieler, nicht MCTS):** „Expert Rules" gewann **63,7 %** gegen die Regelspieler (Random-/Reduced-Varianten) über **10.000 Spiele**, 95 %-KI ±0,94 Pp. (Wald-Formel reproduziert: 1,96·√(0,637·0,363/10.000) = 0,94 Pp., eigene Rechnung).
- **Zahl 2 (Expert-Regelspieler gegen Menschen, nicht MCTS):** 48 von 114 Spielen, **42,1 %**, 7 Menschen (je 10–25 Spiele). Wilson-95-%-KI **33,4–51,3 %** (eigene Rechnung). Als Erstspieler 27/58 = 46,6 % (Wilson 34,3–59,2 %). Das Intervall schließt 50 % ein. Das Paper zieht daraus keine Überlegenheitsaussage; die Zahl wird hier nur als Stichprobe gelesen.
- **Zahl 3 (MCTS, Tabelle VI, „100 K rollouts", 40 Trials):** Die besten MCTS-Varianten (BT+MP) erreichen **51,2–52,0 %** gegen den Expert-Regelspieler bei ~3,2–3,6 s pro Entscheidung; ohne Enhancements **37,3–44,7 %**. Das Paper spricht von „slightly better than the expert player" bzw. „competitive … with a simulation budget of less than one CPU second". **Intervalle für Tabelle VI nicht extrahiert.**
- Relevanz: Die Arbeit zeigt, dass MCTS mit Determinization gegen einen Regelspieler knapp gewinnt; sie zeigt **nicht**, dass eine KI Commander-Entscheidungen menschlich trifft. Das Format ist Zwei-Spieler-MTG mit festen Decks, nicht Commander.

### Muster aus Engine-KI-Batches (Schlussfolgerung)
- Ein KI-gegen-KI-Ergebnis misst **Deck × KI-Spielqualität × Seat × Seed**. Forge selbst sagt, die KI sei bei Combo „pretty bad" → Kombo-Zuverlässigkeit darf **nicht** über Forge-KI gemessen werden.
- Commander-Spezifika (Command Zone, Kommandanten-Steuer, Mulligan-Regel) sind in den abgerufenen Quellen für Forge/XMage **nicht belegt**.

---

## 3. (b) Goldfish-/Solitaire-Simulatoren und Mana-Monte-Carlo

| Projekt | Was es modelliert | Methode / Umfang | Belege | Einordnung |
|---|---|---|---|---|
| Karsten-Methode (über Q13, Q11) | Castability je Zug, Farbquellen | Monte Carlo; Q13: **250.000 Spiele je Konfiguration**, Deckgrößen 40/60/80/99, London-Mulligan, Commander mit Free-Mulligan und Turn-1-Draw; Ausgabe auf 2 Nachkommastellen | [F Q13] | Gute Methodik; **Konfidenzintervall fehlt**; Original-Artikel nicht abgerufen → Koeffizienten unverifiziert |
| Hareruyama (Q11) | Farbverfügbarkeit bis Zug 4 | 100.000 Iterationen, 9 Karten aus 40 als Näherung; keine Mulligans | [F] | Eigenangabe: „Ein paar hunderttausend reichen"; **keine Intervalle**; Näherung ausdrücklich vereinfacht |
| EDHREC-Mana-Simulator (Q12) | verfügbare **Mana-Menge** je Zug, nicht Farbe | Python-Simulator; Agenten: „naive" (nie Mulligan), „smarter" (Mulligan bei < 3 Land, min. 5 Karten); 99-Karten-Beispiel mit 38 Ländern | [F] | Zeigt, wie Mulligan-Policy das Ergebnis verschiebt. **Keine Commander-Regeln** (Kommandant, Steuer), keine Summoning-Sickness, keine Stichprobenzahl, keine CI |
| Goldfisher (Q10) | Schnellster Gewinnzug einer Kombo | Rust, „nicht-interaktive Spiele", Ergebnis: mittlere Gewinnzüge je Version | [F] | Mulligan-Politik **nicht angegeben**; keine Limitationen genannt; Lizenz/Aktivität **unbekannt** → nicht als Beleg nutzbar |
| mtg-sim (Q16) | Kombo-Startblatt-Wahrscheinlichkeit | Go, 10 Mio. Trials (Eigenangabe) | [S] | Beispielwerte (≈0,31 % für 2-Karten-Kombo) nur als Größenordnung |
| ScrollVault (Q14) | Landzahl Commander | „3,75 Mio. Spiele", Schwelle 95 % Castbarkeit, Ramp-Anteil | [S] | Kommerziell, Eigenangabe, Formelkonflikt zwischen eigenen Seiten (siehe §6) → **nicht übernehmen** |
| Schulze (Q15) | Land-Mathematik Commander | Freier Mulligan und Kommandant modelliert | [S] | Selbst: „nicht optimiert für (casual) Multiplayer" |

**Land-Anzahl (Plausibilität):** Mehrere Quellen (Q14, Q15) nennen für 99-Karten-Midrange-Decks um 36–38 Länder. Die exakte Karsten-Formel (`31,42 + 3,13·MV − 0,28·Ramp`) stammt laut Suchsnippet aus Q14 und ist **nicht am Karsten-Original geprüft** → unbelegt.

---

## 4. (c) Akademie: MCTS, Deckoptimierung, Rating

- **MCTS/ISMCTS für MTG:** Q3 (Cowling 2012) ist der belastbarste Beleg (siehe §2). Q7 (Studentenprojekt): MCTS spielte nur „marginally better than random" (Eigenangabe, 2013).
- **Drafting-KI:** Q23 (Ward 2020): >100.000 simulierte menschliche Drafts (Draftsim); Ziel: menschliche Pick-Entscheidungen imitieren (Accuracy), nicht Deckstärke. Ergebnis: tiefes neuronales Netz am besten. **Nicht als Deckqualität übertragbar.**
- **Deckoptimierung per Evolution:** Q25 (NTNU, GA für MTG-Deckbau) und Q24 (SCITEPRESS, evolvierte Bewertungsfunktionen) [S]; Q26 (Dominion-Kartenset-Balancing, Simulation durch KI-Agenten als Fitness) [S]. Gemeinsamer Befund aus Snippets: **Fitnessfunktion ist das Schwierige**; reine Legalitätsfitness liefert legale, aber uninteressante Decks (Medium-Artikel [S]). Ergebnisse der Thesis **nicht gelesen**.
- **Bandit/Bayes-Verfahren für Deckauswahl:** keine belastbare Quelle gefunden → **unbekannt**.
- **Rating Mehrspieler:**
  - Q20 (OpenSkill, Abstract [F]): Enthält Plackett-Luce („among others"); Elo und Glicko-2 seien für 2-Spieler-Spiele gedacht und für Multiplayer „insufficient". Keine Zahlen im Abstract; Vollpaper nicht geöffnet. Die behauptete Geschwindigkeit/Genauigkeit gegenüber TrueSkill ist **Eigenangabe ohne Datensatz im Abstract**. Die Vorrecherche nennt OpenSkill MIT; für uns gilt: Python-Abhängigkeit → nur Eigennachbau der Plackett-Luce-Formel, falls überhaupt.
  - Ein Hinweis aus den Suchergebnissen zu PyPI (Marketing „150 % schneller") ist nicht belegt und wird nicht übernommen.

---

## 5. (d) Datengetriebene Gegenstücke: 17lands und Playgroup

**17lands-Felder** (Q17, Drittdoku; 17lands-Seite selbst lieferte keinen Inhalt, Q18):
- GIH WR: „win rate when the card was drawn or in the opening hand" (Q17).
- IWD = GIHWR − GNSWR (Q17); GNSWR wird nicht definiert. Hohe IWD (> 4,0 %) als „Bomb"-Indikator (Eigenangabe der Doku).
- `samples`-Feld: Anzahl Spiele, zur Einschätzung der Rauschstärke (Q17).
- ALSA/ATA: Pick-Reihenfolge, keine Spielstärke.
- Glättung kleiner Stichproben (Bayes-Mittel): nur als Diskussion [S Q19] — **Priors nicht belegt**.
- Gegenstück-Wert: Spielerdaten, keine Simulation. Confounding (wer zieht welche Karte in welchem Deck) ist **nicht kontrolliert**; das ist das Gegenargument zu unserer kontrollierten Simulation.

**Playgroup (Q21) — Casual-Commander-Daten, Seat-Effekte** [F]:
- 606.151 Mehrspieler-Partien; Einzelsieger-Spiele: 300.240 (4er), 208.640 (3er), 40.184 (5er).
- 4er-Pod, Sitz 1 vs. 4: **29,1 % ±0,16 vs. 21,5 % ±0,15** (Fair Share 25 %). Odds Ratio Sitz 4 vs. 1: 0,67 (0,66–0,68).
- Effekt bleibt bei allen Spiellängen (Gap 6–10 Punkte).
- **Caveats der Quelle:** Casual, Selbstangabe, **Sitzplätze nicht randomisiert**, Mulligan-Daten Selbstangabe (Spieler mulligan eher schlechte Hände).
- Für uns: Seat-Effekt ist **beobachtet** und in Casual-Pods groß. In einer Simulation muss der Sitz **kontrolliert** werden (Rotation/Latin Square), sonst misst man Sitzeffekte als Karteneffekt.

---

## 6. (e) Qualität: Validität, Seeds, Durchsatz, bekannte Fehlinterpretationen

**Was die Quellen zu Validität sagen:**
- **KI-Stärke:** Forge-Wiki (Q1): gut für Aggro/Midrange, schwach für Control und Combo. Das heißt: Ein Deck-Ergebnis kann die **KI-Schwäche** statt die Karte messen. Cowling (Q3) belegt nur relative Stärke ggü. Regelspielern; gegen Menschen 42,1 % (n = 114, KI 33–51 %), also nicht als Stärkebeleg zu werten.
- **Bias-Richtung (Ableitung, nicht aus einer Quelle):** Q1 belegt nur, dass die Forge-KI bei Aggro/Midrange gut und bei Control und Combo schwach ist. Daraus folgt meine Vermutung, dass eine schwache Kombo-KI Kombo-Decks unterschätzt. Wie groß der Effekt ist: **unbekannt**.
- **Simulation vs. Realität:** Hareruyama (Q11) und EDHREC (Q12) benennen die Vereinfachungen selbst (Farbe ignoriert, kein Summoning-Sickness, keine Trigger). Karsten-Ergebnisse gelten für Land-Mathematik, nicht für Spielausgang.

**Seeds und Reproduzierbarkeit:**
- Quellen mit Reproduzierbarkeit: Forge `sim` mit Seed? **Nicht auf der Wiki-Seite** → unbekannt. Q13 und Q11 nennen keinen Seed.
- Die Vorrecherche nennt mtg-replay-notation (Seed + Event-Log + Hash), das deckt die Reproduzierbarkeit ab; keine neue Quelle hier.
- Mana-Monte-Carlo ist mit `random.Random(seed)` und exakter Hypergeometrie (`math.comb`) ohne neue Abhängigkeit reproduzierbar. Das ist unsere Ableitung, nicht aus einer Quelle.

**Durchsatz:**
- Forge: Spiele können sehr lang laufen; `-c` Zeitlimit Standard 120 s (Q1).
- XMage: Denkzeit der MCTS-KI skaliert mit Skill (Q9, [S] unverifiziert) → Denkzeit dominiert Laufzeit.
- Mana-Sims: 100.000–250.000 Iterationen in Quellen üblich (Q11, Q13). **Keine Quelle nennt Spiele/Stunde für Commander-Engine-Läufe.** → unbekannt.

**Bekannte Fehlinterpretationen (mit Beleg):**
1. **KI-Schwäche als Kartenurteil:** Forge-Wiki (Q1) warnt selbst; Q2 (Forum, [S]) berichtet einen Reihenfolge-Effekt bei Decks.
2. **Seat-Effekt als Deckeffekt:** Q21 (Playgroup) zeigt 7,6 Punkte Unterschied zwischen Sitz 1 und 4 ohne Deckänderung.
3. **Kommerzielle Formel als Wahrheit:** Q14 (Commander-Seite) nennt `31,42 + 3,13·MV − 0,28·Ramp`; eine andere ScrollVault-Seite (`how-many-lands`, [S]) nennt `19,59 + 1,90·MV`, eine 60-Karten-Formel. Die Quellen widersprechen sich bzw. verwechseln Formate; Q14 ist Eigenangabe und Werbung für einen Rechner.
4. **Punktschätzung ohne Intervall:** Q11 gibt Prozentwerte ohne Fehlerbalken; Q12 nur Grafiken ohne n.
5. **Relative Stärke als Absolut-Stärke:** Q3 (63,7 % gegen Regelspieler) wird leicht als „stark" gelesen; die Zahl gegen Menschen ist 42,1 % bei n = 114.
6. **Mulligan-Politik unsichtbar:** Q10 gibt keine Politik an; Q12 zeigt, dass Politik die Kurve stark verschiebt.
7. **Präzision über Methode:** Q13 gibt 2 Nachkommastellen aus, Fehlerbalken fehlen.
8. **Mehrspieler-Rating als 2-Spieler-Elo:** Q20 belegt, dass Elo/Glicko-2 für Multiplayer nicht vorgesehen sind.
9. **Drafting-Genauigkeit als Deckqualität:** Q23 misst Imitation menschlicher Picks.

---

## 7. Was für unsere Lage sinnvoll ist (Methoden und Metriken)

Bedingungen: XMage ist Regelautorität; keine neuen Python-Abhängigkeiten; 2–4 Sitze; vorhandene Paar-Serien mit O'Brien-Fleming-Looks; Seed-Reproduzierbarkeit.

1. **Paarweise Serien mit identischem Seed und Sitzrotation.** Jedes Deck in jedem Sitz gleich oft (4er: zyklische Rotation oder Latin Square). Begründung: Q21 belegt einen starken, nicht randomisierten Seat-Effekt. **Ergebnis je Deck und Sitz getrennt ausweisen** (n/N je Zelle).
2. **Proportionen mit Wilson-Intervall** (bereits im Repo). Differenzen zwischen Decks mit Newcombe/Holm wie in der Vorrecherche. Die abgerufenen Fremdquellen geben keine Intervalle an (Q11, Q12) oder nur Wald-artige ± (Q3). **Konsequenz: Intervalle mit Nenner sind gegenüber den geprüften Fremdprojekten der strengere Standard.**
3. **Sequentieller Stopp:** O'Brien-Fleming bleibt **nicht durch Webquellen belegt** (Vorrecherche: „nicht im Web belegt"). Vor Einpflege Lehrbuchquelle prüfen. Die Fishtest-Idee (Paar-Einheit, SPRT) passt zu Paar-Serien; die 4-Sitz-Übertragung ist **nicht belegt**.
4. **Metriken für Deckbau aus einer Goldfish-/Mana-Simulation** (nur als Hilfsgröße, nie Tierliste):
   - Castability-Wahrscheinlichkeit je Zug mit n/N und Wilson-Intervall (Karsten-Methode, bereits umgesetzt).
   - Mulligan-Politik **explizit** als Parameter ausweisen (Q12 zeigt: Politik verschiebt Ergebnis).
   - Commander-Zeit („Zug, an dem Kommandant castbar ist") nur mit definierter Ziehreihenfolge, Free-Mulligan und Kommandant-Steuer; Quellen dazu fehlen → **Eigenbau nötig, Methodik muss selbst validiert werden**.
   - **Tote Handkarten:** keine Quelle definiert eine validierte Metrik → **unbekannt**; nur mit XMage-Zustand definierbar.
5. **Engine-Kombo-Zuverlässigkeit:** nicht über KI-Partien (Forge: schwach gegen Kombo). Sinnvoll: **skriptete Linien in XMage** (Testauswahl), mit Erfolgsquote n/N und festem Setup. Das ist Repo-Arbeit, keine Web-Methode.
6. **Seed-Herkunft je Ergebnis:** Seed, Sitz-Mapping, Log-Hash (Vorrecherche: mtg-replay-notation). Keine Fremdquelle belegt, dass das in Commander-Sims üblich ist.
7. **Rating (Zusatzmetrik, nie Tierliste):** Plackett-Luce ist die Quelle-belegte Option für Rangfolgen mit 3+ Plätzen (Q20). Eigenbau der Formel statt Paket, mit Intervall; **Sitzeffekte werden von Plackett-Luce nicht modelliert** → Sitzrotation ist Voraussetzung.

---

## 8. Nutzbar und belastbar vs. irreführend

| Ergebnis-Typ | Verdikt | Begründung |
|---|---|---|
| Starthand-/Kastbarkeitswahrscheinlichkeit mit exakter Hypergeometrie oder großem MC, Mulligan-Politik angegeben | **übernehmen** (als Hilfsgröße mit n/N und Intervall) | Q13, Q11, Q12 zeigen die Methode; Zahlen aus Fremdprojekten **nicht** gegengeprüft, nur die Methode ist übertragbar |
| Landzahl Commander 36–38 als Bandbreite | **nur als Vergleichswert** | mehrere Quellen, aber kommerziell oder unverifizierte Formel |
| Landzahl-Formel mit Ramp (`31,42 + 3,13·MV − 0,28·Ramp`) | **nein** | Herkunft Werbeseite, nicht am Original geprüft |
| Zeit bis Kommandant (Turn-Zahl) | **nur mit Eigenbau und Policy** | keine validierte Fremdmethode |
| Tote Handkarten | **unbekannt** | keine belastbare Methode in den Quellen |
| Engine-Kombo-Zuverlässigkeit über Forge-KI | **irreführend** | Forge selbst: schwach gegen Kombo |
| Win-Rate zwischen KI-Decks ohne Seat-Kontrolle | **irreführend** | Q2 (Reihenfolge), Q21 (Seat-Effekt 7,6 Punkte) |
| MC-Punktwert ohne Intervall (Q11) | **nur mit Intervall** | n = 100.000 nennt der Autor, aber kein Fehlerbalken |
| Goldfisher-„schnellster Gewinnzug" | **nein** | Lizenz unbekannt, Politik unbekannt, keine Interaktion |
| EDHREC-Mana-Kurve | **Mechanik-Vorbild, kein Befund** | nur Mana-Menge, keine Farbe, keine Commander-Regeln |
| 17lands GIH WR / IWD | **Gegenprobe, kein Simulationsersatz** | Spielerdaten mit Confounding; `samples` nötig |
| Playgroup-Seat-Effekt | **als Beobachtung übernehmen** | groß, aber Casual, nicht randomisiert |
| Cowling 63,7 % (Expert-Regelspieler vs. Regelspieler, n = 10.000) | **nur relativ** | kein MCTS, nicht gegen Menschen |
| Cowling 42,1 % (Expert-Regelspieler vs. Menschen, n = 114) | **als Stärkeindikator unbrauchbar, Intervall 33–51 %** | Intervall enthält 50 %; kein MCTS |
| Cowling MCTS 51,2–52,0 % vs. Expert-Regelspieler (Tabelle VI, 40 Trials) | **nur relativ, 2-Spieler-Format** | Intervalle nicht extrahiert |

---

## 9. Offene Lücken / nicht belegt

- **Forge-AI-Profile**: Namen und Wirkung nicht auf der Wiki-Seite gefunden; Headless-Batch-Parameter (Seed, Profilwahl) **unbekannt**.
- **XMage-KI-Klassen** (`ComputerPlayerMCTS`, Batch-Harness): nur Sekundärsnippet, Doku 404 → im Repo prüfen (`CardTestPlayerBaseAI` und Nachbarn).
- **Magarena**: Batch-Modus nicht gesehen; Zhang-Slides nicht lesbar.
- **Karsten-Original-Artikel** nicht abgerufen; Formel und Konfidenz **unbelegt**.
- **17lands-Definitionen aus Originalquelle** nicht abgerufen (Q18 leer); GNSWR undefiniert.
- **Commander-spezifische Simulationsvalidierung** (Kommandant-Steuer, Command Zone, Free-Mulligan in Engine-Läufen): keine Quelle gefunden.
- **Multiplayer-Sitz-Modell** (Sitzrotation im Rating, Plackett-Luce mit Sitzeffekt): nicht gefunden.
- **Forge/XMage/Magarena Durchsatz** (Spiele pro Stunde, JVM-Reuse, Parallelität): keine Messung gefunden.
- **Akademische Deckoptimierung** (Q24, Q25, Q26): nur Snippets; Ergebnisse unbekannt.
- **Lizenzen** Forge (auf Wiki nicht genannt), Goldfisher, Gist (Q13), EDHREC-Simulator-Code: **unbekannt**.
- **O'Brien-Fleming und Mehrspieler-SPRT**: nicht im Web belegt.
- Keine Aktivitätsdaten (letzter Commit) für Goldfisher, mtg-sim, Magarena belegt.
- Nutzungsbedingungen von Playgroup-Daten für automatisierten Abruf: **unbekannt**; nicht abgerufen, nur gelesen.
