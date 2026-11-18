# SIMULATE-Methodik: belastbare Deckbau-Analysen aus Commander-Simulationen

Lane `simulate_methods`. Abrufdatum aller Quellen: **2026-11-18**. Nur Webrecherche und eigene Rechnung (stdlib-Python, Skripte unter `calc/` in diesem Ordner), nichts gebaut oder gepostet. Ergänzt `OPEN_SOURCE_LANES_20261117.md` (dort schon: Wilson/Jeffreys, statsmodels, Fishtest/SPRT, always-valid, OpenSkill, Herkunftsfeld-Idee) und wiederholt es nicht, sondern schließt die dort als "nicht im Web belegt" markierten Lücken (McNemar/gepaarter Bootstrap, Control Variates/CRN, Power-Planung, alpha-spending, Sitzeffekte).

**Belegstatus je Quelle** (Frame: Eigenangabe vs. geprüft): **[S]** = Seite/PDF abgerufen und gelesen; **[A]** = nur Abstract-Seite abgerufen; **[T]** = nur Suchtreffer-Text, Seite selbst nicht gelesen. Abruf-Werkzeug fasst Seiten per Kleinmodell zusammen; PDFs habe ich lokal mit `pdftotext` selbst gelesen, wo markiert (**[S-lokal]**).

---

## 1. Quellenliste (19 Quellen; 13 mit Seitenabruf)

| # | Quelle | URL | Status |
|---|---|---|---|
| 1 | Owen, *Monte Carlo theory, methods and examples*, Kap. 8 "Variance Reduction" (§8.6 Common random numbers, Gl. 8.19-8.21; Antithetic §8.2; Control variates §8.9) | https://artowen.su.domains/mc/Ch-var-basic.pdf (Index: https://artowen.su.domains/mc/) | **[S-lokal]** (Fußzeile: "do not distribute": nur zitieren, nicht kopieren) |
| 2 | Newcombe 1998, *Improved confidence intervals for the difference between binomial proportions based on paired data*, Stat. Med. 17, 2635-2650 | https://www.site.uottawa.ca/~nat/Courses/csi5388/Newcombe.1998.pdf | **[S-lokal]** (Methoden 8-10, Abschn. 4 und 6) |
| 3 | Berg-Kirkpatrick/Burkett/Klein 2012, *An Empirical Investigation of Statistical Significance in NLP* (gepaarter Bootstrap) | https://nlp.cs.berkeley.edu/pubs/BergKirkpatrick-Burkett-Klein_2012_Significance_paper.pdf | **[S-lokal]** |
| 4 | Benjamini/Hochberg 1995, *Controlling the False Discovery Rate*, JRSS B 57(1) | https://www.dcscience.net/Benjamini-Hochberg-1995-FDR.pdf | **[S-lokal]** (Summary, Einleitung, Theorem 1) |
| 5 | Sargent, *Verification, Validation, and Accreditation of Simulation Models*, WSC 2000 | https://www.informs-sim.org/wsc00papers/009.PDF | **[S-lokal]** (§7 Operational validity, 7.2 Konfidenzintervalle, Hypothesentests, Operating-Characteristic-Kurve) |
| 6 | NumPy-Doku "Parallel Random Number Generation" (`SeedSequence.spawn`) | https://numpy.org/doc/stable/reference/random/parallel.html | **[S]** |
| 7 | Fishtest Mathematics (Wiki; Pentanomial, GSPRT) | https://github.com/official-stockfish/fishtest/wiki/Fishtest-mathematics (Spiegel: https://official-stockfish.github.io/docs/fishtest-wiki/Fishtest-Mathematics.html) | **[S]**: nennt die fünf Paar-Kategorien (ll, ld, dd/wl, wd, ww) und GSPRT, **enthält keine Varianzformel** und nennt keine Unabhängigkeitsannahme |
| 8 | Burch/Schmid/Moravčík/Bowling, *AIVAT* (arXiv 1612.06915, AAAI-17-Workshop) | https://arxiv.org/abs/1612.06915 | **[A]**: "provably unbiased", "mehr als Faktor 10 weniger Hände" (Heads-up-No-Limit-Poker); die Seite nennt die Technik nicht "control variates" |
| 9 | Johari/Pekelis/Walsh, *Always Valid Inference* (arXiv 1512.04922) | https://arxiv.org/abs/1512.04922 | **[A]**: Seite nennt weder mSPRT noch Annahmen |
| 10 | Playgroup.gg "Commander · Turn Order" (Sitzgewinnraten, Stand 2026-11-16) | https://playgroup.gg/commander/turn-order | **[S]** |
| 11 | Playgroup.gg Experiment-Seite (Regelfix gegen Erstspieler-Vorteil, vorab registriertes Kriterium) | https://playgroup.gg/commander/turn-order/experiment | **[S]** |
| 12 | TopDeck.gg, Spielrahoo, *Turn order win rates in cEDH Swiss* (2023-01-26) | https://topdeck.gg/articles/first-player-adv-silicon-dynasty | **[S]** |
| 13 | EDHREC, *Simulating Available Mana (Beyond the Hypergeometric Distribution)* | https://edhrec.com/articles/simultaing-available-mana-beyond-the-hypergeometric-distribution | **[S]** |
| 14 | Hareruya, *Using Monte Carlo Simulation to Improve Your Manabases* | https://article.hareruyamtg.com/article/article_en_405/?lang=en | **[S]** |
| 15 | Ramos, *Embarrassingly Causal* (17Lands-Daten, Confounding/Selektion), arXiv 2604.18314 | https://arxiv.org/abs/2604.18314 | **[A]** (Abstract: "substantial confounding, selection effects, and post treatment conditioning"); Aussage zu GIHWR-Bias stammt aus Suchtreffern, nicht aus dieser Seite |
| 16 | Weng/Lin 2011, *A Bayesian Approximation Method for Online Ranking*, JMLR 12 | https://www.jmlr.org/papers/v12/weng11a.html | **[A]**: Mehrteam-/Mehrspieler-Ranking; Seite nennt BT/PL nicht |
| 17 | Hunter 2004, *MM algorithms for generalized Bradley-Terry models*, Ann. Statist. 32(1) | https://projecteuclid.org/journals/annals-of-statistics/volume-32/issue-1/MM-algorithms-for-generalized-Bradley-Terry-models/10.1214/aos/1079120141.full | **[A]** (dünn: BT, Unentschieden, Heimvorteil, Plackett-Luce) |
| 18 | Brown/Cai/DasGupta 2001, *Interval Estimation for a Binomial Proportion*, Stat. Sci. 16(2) | https://projecteuclid.org/download/pdf_1/euclid.ss/1009213286 | **[T]**: Abruf lieferte leeren Text; Empfehlung (Wilson/Jeffreys für kleines n, Agresti-Coull für größeres n, Wald unzuverlässig) nur aus Suchtreffer |
| 19 | Howard/Ramdas/McAuliffe/Sekhon 2021, *Time-uniform, nonparametric, nonasymptotic confidence sequences*, Ann. Statist. 49(2) | https://arxiv.org/pdf/1810.08240 | **[T]** |

Weitere nur als Suchtreffer **[T]**, nicht tragend: Lan/DeMets-Spending (O'Brien-Fleming-Funktion nur über Rechner-Seite metricgate, `ldbounds`-Handbuch lieferte HTTP 403); Holm 1979, Scand. J. Statist. 6, 65-70 (nur Literaturangabe); Cowling/Ward/Powley 2012, IEEE TCIAIG (MCTS für Magic, nur gegen Bots, https://eprints.whiterose.ac.uk/75050/); Hearthstone-/LOCM-Arbeiten zu Deckbau-und-Spielagent-Kopplung (https://arxiv.org/pdf/2001.01326, https://www.sbgames.org/proceedings2021/CTDMestrado/218333.pdf); Fishtest-Forumsbeiträge zur Paar-Korrelation (https://talkchess.com/viewtopic.php?p=785326, Forum, kein Beleg).

---

## 2. Eigene Rechnungen (stdlib, reproduzierbar: `calc/calc.py`, `crn.py`, `mde.py` in diesem Ordner)

Gemeinsame Annahmen: 95 % zweiseitig (z=1,96), Power 80 % (z=0,84), Gewinnwahrscheinlichkeit des Fokusdecks p=0,25 (gleichstarke Decks, 4er-Pod, ein Sieger, keine Unentschieden). Jede Partie liefert **eine** 0/1-Beobachtung für das Fokusdeck (Bernoulli). Das gilt nur, wenn Partien unabhängig sind; siehe §4 (Blöcke).

### 2.1 Partien für einen Anteil (Halbbreite ±3 Prozentpunkte, p=0,25)
n = z²·p(1−p)/d² = 1,96²·0,1875/0,03² = **800** Partien (Wald-Formel; exakte Wilson-Halbbreite ≤ 3 pp bei n=799, praktisch gleich). Bei 99 %: ca. 1380. Weitere Werte: ±5 pp: 288; ±2 pp: 1801; ±1 pp: 7203.
Lesart: Ein einzelner Anteil braucht ~800 Partien für ±3 pp. Ein **Unterschied** zwischen zwei Decks braucht mehr (2.3).

### 2.2 Varianzgewinn durch gemeinsame Seeds (Common Random Numbers)
Nach Owen Gl. 8.21: Var(D_gemeinsam) = (σ_f²+σ_g²−2ρσ_fσ_g)/n, Var(D_unabhängig) = (σ_f²+σ_g²)/n. Bei gleichem σ: Verhältnis = **1−ρ**, Gewinn **1/(1−ρ)**.

| ρ (angenommen) | 0,1 | 0,3 | 0,5 | 0,7 | 0,9 |
|---|---|---|---|---|---|
| Varianzfaktor | 0,90 | 0,70 | 0,50 | 0,30 | 0,10 |
| Partien-Ersparnis | 1,11x | 1,43x | 2,0x | 3,3x | 10x |

Owen §8.6 selbst: "There is no guarantee that ρ > 0"; und sobald f/g weitere Zufallsquellen nutzen, braucht der Erhalt gemeinsamer Zufallszahlen "considerable care in synchronization", die Komplexität kann den Vorteil aufheben. **Die Tabelle zeigt, was ρ wert wäre, nicht welches ρ wir haben. ρ ist aus Pilotblöcken zu messen, nie anzunehmen.**

Spielzeugmodell (Plackett-Luce über Gumbel-Max, 4 Sitze, Variante B mit p=0,28 statt 0,25, Anteil q der Partien mit identischem Glück, 200 000 Partien je Zeile): diskordanter Anteil t und Varianzgewinn:

| q (Glück geteilt) | t | Gewinn |
|---|---|---|
| 0 (unabhängig) | 0,388 | 1,00x |
| 0,5 | 0,209 | 1,87x |
| 0,8 | 0,101 | 3,88x |
| 0,95 | 0,048 | 8,2x |
| 1,0 | 0,030 | 13,4x |

**Das ist eine Obergrenze, keine Schätzung**: Es nimmt an, dass das Glück über die ganze Partie geteilt bleibt. In einer echten Engine (Würfe, KI-Entscheidungen, Zufallsziele) driftet der Zufallsstrom nach der ersten abweichenden Entscheidung auseinander. Ob XMage Mischen, Spielzufall und KI-Zufall trennt, ist **unbekannt** (offene Lücke).

### 2.3 Gepaart vs. unabhängig: Partien für +3 pp (p₁=0,25 → p₂=0,28)
Unabhängig (zwei Arme): n = (z_α+z_β)²[p₁q₁+p₂q₂]/δ² = **3393 je Arm, 6787 Partien gesamt**.
Gepaart (McNemar-Näherung, Diskordanzanteil t): n_Paare = [z_α√t + z_β√(t−δ²)]²/δ². Das ist eine Standardformel (Connor 1987), **Quelle nicht abgerufen**; die Rechnung ist meine.
Bei Unabhängigkeit ist t = p₁(1−p₂)+p₂(1−p₁) = **0,39**; dort ist Pairing wertlos (Spielzeugmodell: 1,00x). Nur t < 0,39 bedeutet positive Korrelation und Gewinn:

| t (Diskordanz) | Paare | Partien gesamt | Ersparnis ggü. 6787 |
|---|---|---|---|
| 0,39 (= unabhängig) | 3399 | 6798 | 1,0x |
| 0,30 | 2614 | 5228 | 1,3x |
| 0,20 | 1742 | 3484 | 1,9x |
| 0,10 | 870 | 1739 | 3,9x |

(Ein t > 0,39 hieße negative Korrelation, "Pairing schadet"; Owen erlaubt das ausdrücklich.)

### 2.4 Kleinster nachweisbarer Effekt (MDE) bei realistischem Budget
Das ist die zentrale Anti-Scheinpräzisions-Zahl (95 %, Power 80 %, Basis p=0,25):

| Budget je Arm / Paare | unabhängig | gepaart t=0,39 | t=0,30 | t=0,20 | t=0,10 |
|---|---|---|---|---|---|
| 500 | 8,0 pp | 7,8 | 6,8 | 5,6 | 4,0 |
| 1000 | 5,6 pp | 5,5 | 4,8 | 4,0 | 2,8 |
| 2000 | 3,9 pp | 3,9 | 3,4 | 2,8 | 2,0 |
| 5000 | 2,5 pp | 2,5 | 2,2 | 1,8 | 1,3 |

Folgerung: Mit 1000 Partien je Variante liegt der MDE bei ~5,5 pp (unabhängig) bzw. ~4 pp (gepaart, t=0,2). Ein einzelner Karten-Tausch in einem 99-Karten-Deck wirkt typischerweise deutlich kleiner. **Das Ergebnis lautet dann "kein Effekt nachweisbar bei n=…, MDE=x pp", nie "Karte ist egal".** (Die Annahme "typisch kleiner" ist meine Einschätzung, nicht belegt.)

### 2.5 Mehrfachvergleiche (50 Karten-Swaps)
Bonferroni/Holm im ungünstigsten Fall: z steigt von 1,96 auf 3,29 (m=50) bzw. 3,48 (m=100); Partienbedarf bei gleicher Halbbreite x2,8 bzw. x3,2. Holm (Holm 1979 **[T]**) ist FWER-kontrollierend und mindestens so stark wie Bonferroni; BH 1995 kontrolliert die FDR und ist **für unabhängige Teststatistiken bewiesen** (Theorem 1, [S-lokal]); Erweiterungen auf Abhängigkeit habe ich nicht abgerufen.

### 2.6 Wiederholtes Hinsehen (Peeking) ohne Korrektur
Simulation, faire Nullhypothese p=0,25, nominal 5 %, n_final=800, naiver z-Test bei jedem Blick (4000 Wiederholungen je Zeile): 1 Blick 4,9 %; 2 Blicke 8,8 %; 5 Blicke **13,7 %**; 10 Blicke 18,9 %; 20 Blicke 23,6 %. Das begründet vorab festgelegte Stopp-Regeln.
O'Brien-Fleming-artige alpha-Ausgabe (Lan/DeMets, Formel α*(t)=2[1−Φ(z_{α/2}/√t)], nur über Rechner-Seite **[T]**): kumulativ ausgegebenes α bei Informationsanteil t=0,2/0,4/0,6/0,8/1,0 = 0,00001 / 0,0019 / 0,0114 / 0,0284 / 0,05. Frühe Zwischenblicke sind also fast "kostenlos", aber auch fast nie signifikant. (Die exakten Grenzen erfordern Rekursion; nicht gerechnet.)

---

## 3. Antworten je Themenfeld

### (1) Gepaarte Vergleiche, CRN, Antithetic, Control Variates
- **CRN** (Owen §8.6, [S-lokal]): Differenz zweier Varianten mit gleichen Zufallszahlen hat Varianz (σ_f²+σ_g²−2ρσ_fσ_g)/n; ρ>0 ist die Voraussetzung, nicht garantiert; Synchronisation der Zufallsströme ist der schwierige Teil.
- **Antithetic** (Owen §8.2): Gewinn nur, wenn die Funktion monoton im Zufall ist; für Kartenspiel-Ausgang (Mischen → Sieg) nicht plausibel monoton → **nicht empfohlen**, nur Idee (mein Urteil, kein Beleg).
- **Control Variates** (Owen §8.9): Varianz sinkt um Faktor (1−ρ²) mit einer korrelierten Hilfsgröße bekannten Erwartungswerts (Owen Gl. 8.15 zeigt die analoge Formel für Stratifikation, [S-lokal]). Für uns: exakt berechenbare Größen (z. B. hypergeometrische Starthand-Verteilung, Anzahl Länder in den ersten 10 Karten) als Hilfsgröße für den Sieg. Das ist meine Übertragung.
- **AIVAT** (Quelle 8 [A]): Kartenglück und Entscheidungen bekannter Strategien herausrechnen, "mehr als Faktor 10" im Poker; verlangt bekannte Strategie und Wertheuristik. Für XMage-KI nur denkbar, wenn deren Entscheidungsverteilung loggbar ist: Idee, nicht übernehmen.
- **Praktisch**: Swap-in-place (Ersatzkarte am selben Listenindex, gleicher Seed → Bibliotheksreihenfolge sonst identisch) maximiert die gemeinsame Zufallsbasis. ρ bzw. t aus Pilotblöcken messen.

### (2) Mehrspieler-Pods
- **Sitzeffekt ist real und groß**: Playgroup (Stand 2026-11-16, [S]): 300 240 Einzelsieger-Partien mit 4 Spielern, Sitz 1/2/3/4 = 29,1 / 25,7 / 23,6 / 21,5 % (Fair-Anteil 25,0 %), 95-%-Intervalle angegeben (±0,16 pp bei Sitz 1), Odds-Ratios aus logistischer Regression. Caveats der Seite: selbstberichtet, Casual (kein cEDH), Sitz = Startspieler, "Seating is not randomized by us", Unentschieden ausgeschlossen. (Suchtreffer nannte 243 938 Partien und 29,2 %; die abgerufene Seite ist aktueller. Immer die abgerufene Zahl zitieren.) TopDeck/cEDH ([S]): 648 Pods, Sitz 1 = 31,5 % (Wald-artiges 95-%-Intervall 27,8-35,1 %), Sitz 4 = 20,2 %; Unentschieden/Byes ausgeschlossen, Spielstärke nicht kontrolliert.
- **Konsequenz für unser Design**: Jede verglichene Deckkonfiguration muss je Seed-Block **alle vier Sitze** durchlaufen (balanciertes Latin-Square-artiges Design); Sitz als eigenen Faktor berichten. Referenzanteil 25 % nur bei Sitzbalance und gleichstarker Tischrunde.
- **Plackett-Luce / Bradley-Terry**: Hunter 2004 [A] (MM-Algorithmen für BT inkl. Heimvorteil und PL-Mehrfachvergleiche); Weng/Lin 2011 [A] (Online-Ranking für Mehrteam-Spiele, Näherung); Hinweis aus Suchtreffer: Maximum Likelihood überfittet bei dünnen Daten (Guiver/Snelson, [T]). PL liefert nur Stärke-Skalen; **Sitz-, Seed-Block- und Pilot-Effekte sind nicht modelliert**, wenn man sie nicht als Kovariaten einbaut. Nur Zusatzmetrik mit Unsicherheit, nie Tierliste.
- **Platzierungs- vs. Siegmetrik**: Beim Commander-Pod mit einem Sieger enthält "Sieg" nur ~0,81 bit/Spiel Information (p=0,25); Platzierung/Eliminationsrunde enthält mehr, aber Eliminationsreihenfolge ist KI-/Regelartefakt-anfällig. Meine Einordnung, nicht belegt: Sieg als Primärmetrik, Platz/Überlebenszeit als Sekundärmetrik mit eigener Unsicherheit.
- **Intervalle**: Wilson/Jeffreys statt Wald (Brown et al. [T]). Differenz gepaarter Anteile: Newcombe 1998, **Methode 10** = Wilson-Score-Intervalle der beiden Randanteile, kombiniert über den Phi-Koeffizienten der 2×2-Tabelle (Formel Methode 8: d = √(dl²−2φ·dl·du+du²)); in Methode 10 mit Kontinuitätskorrektur am φ-Zähler max(eh−fg−n/2,0)). Newcombes Fazit [S-lokal]: Wald und "exakte" bedingte Methoden sind "highly unsatisfactory"; Methode 10 hat Überdeckung ähnlich Methode 6, ist aber teils deutlich schmaler. Alternative: gepaarter Bootstrap (Berg-Kirkpatrick 2012: Paar-Bootstrap, b=10⁶; ähnlichere Systeme erreichen Signifikanz mit kleineren Gewinnen, weil ihre Ausgaben korrelierter sind; i.i.d.-Annahme hält über Domänen hinweg nicht). McNemar = exakter Binomialtest auf die diskordanten Paare (Suchtreffer UMass-Vorlesung [T]); Permutationstest: nicht als eigene Quelle abgerufen.
- **Unabhängigkeits-Falle**: Siehe §4. Mehrere Sitzrotationen derselben Seeds sind **nicht unabhängig**; Intervalle über 4n Partien als wären sie unabhängig wären falsch klein.

### (3) Sequentielle Tests / Stopp
- **Fishtest** [S]: Pentanomial (5 Paar-Kategorien), GSPRT mit Grenzen in normalisiertem Elo; die Wiki-Seite enthält **keine Formeln** und keine Annahmen. Forumsbeiträge (Quelle [T]) behaupten Varianzreduktion bei korrelierten Paaren, aber auch, dass die Paar-Korrelation "vollständig durch das Elo-Modell erklärbar" sei: **Forum, kein Beleg**.
- **Always-valid / mSPRT** (Johari et al. [A]; Howard et al. [T]): Intervalle, die bei beliebigem datenabhängigem Stopp gültig bleiben; Kosten: breitere Intervalle bei festem n. Annahmen (Unabhängigkeit, Verteilungsform) stehen nicht auf den abgerufenen Seiten.
- **alpha-spending (Lan/DeMets, O'Brien-Fleming-artig)**: Siehe 2.6; nur Rechner-Seite abgerufen [T].
- **Übertragung auf 4 Sitze: nicht gegeben (kein Beleg), aber ableitbar (eigene Übertragung, kein Quellenbeleg)**: Der Fishtest-Gedanke "Einheit = zusammengehöriges Paar" wird zu "Einheit = Seed-Block". Bei Deck A und B in je allen vier Sitzen über denselben Seed ist die Blockdifferenz (Siege B − Siege A) ganzzahlig in −4..+4. Ihre Verteilung wird wie bei der Pentanomial-Zählung empirisch geschätzt (Häufigkeit je Wert, Varianz aus den Blockhäufigkeiten). Dann gelten Stopp-/Intervallregeln auf der Blockebene (Normal-/Bootstrap-Näherung oder GSPRT mit Blockvarianz). Voraussetzung: Blöcke untereinander unabhängig (frische Seeds). Ob die Blockverteilung eine einfache Form hat (wie Fishtests 5 Werte) ist ungeprüft.

### (4) Ceteris-paribus-Kartenablation (Leave-one-out / Swap)
Methodik: Deckliste D gegen D' mit einer getauschten Karte, gleiche Seeds, gleiche Sitzrotation, gleiche Gegner-Pods; Auswertung gepaart. Fallen (Quellen soweit abgerufen):
1. **KI-Pilot-Schwäche**: Das Ergebnis misst "Karte × dieser Pilot", nicht "Karte × Mensch". Deckbau- und Spielagent-Qualität sind verschränkt (LOCM-/Hearthstone-Arbeiten, [T]; keine Studie fand ich, die den Anteil direkt misst). Mit Pilot-Fehlerbericht (§6) paaren.
2. **Interaktion mit dem Rest des Decks**: Ein Swap misst den **marginalen** Effekt gegeben die restliche Liste. Synergien (Kombo-Teile) erscheinen als "tot", wenn nur eines von zwei Teilen getauscht wird. Faktorielles Design (A/B getrennt und gemeinsam) nötig; mein Urteil.
3. **Selektionsbias / Winner's Curse**: Wer 50 Swaps testet und den besten behält, überschätzt dessen Effekt, auch nach Holm. Gegenmittel: Screening-Seeds und frische Bestätigungs-Seeds; BH 1995 beschreibt den Selektionseffekt ("researchers tend to select the (statistically) significant ones for emphasis", Einleitung, [S-lokal]).
4. **Confounding bei Beobachtungsdaten**: Für Echtdaten-Kartenwinraten (17Lands-Muster) zeigt arXiv 2604.18314 [A] "substantial confounding, selection effects, and post treatment conditioning" → Kartenwertungen aus Echtdaten sind nicht kausal; Simulation mit kontrolliertem Swap ist dafür besser, aber nur im Pilotrahmen (1.).
5. **Nicht-i.i.d. über Domänen**: Berg-Kirkpatrick [S-lokal]: Signifikanz unter i.i.d. hält bei geänderter Verteilung (Gegnerpool) schlecht; Ergebnisse nur für den getesteten Gegnerpool aussagen.

### (5) Nicht-Gewinn-Metriken
- **Exakt statt simuliert, wo möglich**: Starthand-/Mulligan-Verteilungen und Land-Drop-Wahrscheinlichkeiten ohne Entscheidungen sind hypergeometrisch berechenbar (Hareruya [S] prüft seine Monte-Carlo-Zahl gegen einen Hypergeometrie-Rechner). Simulieren nur, was von Engine/Entscheidungen abhängt (Mulligan-Policy, Spielreihenfolge, Zugzeit der ersten Beschwörung).
- **Wie berichten Fremdwerkzeuge?** EDHREC-Artikel [S]: Monte-Carlo-Mana-Simulation in Python, Anzahl der Läufe nicht genannt, **keine Intervalle**, nur "Gesetz der großen Zahlen"; Mulligan-Politik: naiv nie, "fortgeschritten" bei <3 Ländern bis 5 Karten; Farben, Beschwörungskrankheit, Trigger nicht modelliert. Hareruya [S]: 100 000 Läufe, Zahlen wie 35,4 % → 43,7 % → ca. 50 %, **keine Intervalle**, keine Mulligan-/Spielentscheidungen, Hinweis "Wiederholläufe prüfen". Das ist die Messlatte, die wir übertreffen müssen: n/N, Intervall, Policy-Angabe.
- **Zensur**: "Zug der ersten Beschwörung" oder "Zug der Erstkombo", nur über Partien gemittelt, in denen es geschah, ist überlebensverzerrt. Immer "nicht erreicht" als n/N getrennt ausweisen und zensurbewusst schätzen (Kaplan-Meier/Quantile mit "nicht erreicht"; Kaplan-Meier nicht als Quelle abgerufen, Standardverfahren). Intervall für Quantile per Block-Bootstrap.
- **Weitere**: tote Karten (nie gespielt trotz Verfügbarkeit, Anteil n/N), Mana-Screw/Flood (Schwellen vorab definieren, sonst Wahl der Schwelle = Freiheitsgrad), Ressourcenkurven (Median + Quantile je Zug, nicht nur Mittel). Karsten-Methode: bereits bekannt (Vorrecherche); Hinweis aus Suchtreffer: Karstens Originalcode nutzte feste Paris-Mulligan-Policy, die London-Regel macht die Policy komplizierter ([T], neverdraftingagain-Blog), also Policy immer offenlegen.
- Sitzabhängigkeit auch hier prüfen (Erstspieler hat eine Karte weniger gesehen).

### (6) KI-Validitätsprüfung
- **Rahmen**: Sargent 2000 [S-lokal]: vier Validitätskomponenten (konzeptionell, Verifikation, operational, Daten); operationale Validität = Vergleich Modell- vs. Systemausgabe per (1) Grafiken (am häufigsten), (2) Konfidenzintervalle, (3) Hypothesentests; "Modellgenauigkeitsbereich" aus Intervallen; **Operating-Characteristic-Kurve** zeigt, wie die Stichprobengröße die Annahmewahrscheinlichkeit eines gültigen Modells bestimmt; Nutzerrisiko (Typ-II) ist "extremely important". Weitere dort genannte Techniken: Historical Data Validation, Turing-Tests, Face Validity, interne Validität über Replikationen.
- **Billige, konkrete Prüfung: Sitzkurve**. Die simulierte Sitz-Gewinnkurve der KI (Sitz 1-4) gegen Playgroup (29,1/25,7/23,6/21,5 %) und TopDeck (31,5/24,2/24,1/20,2 %) vergleichen. Aufwand: ~900 Partien reichen, um Sitz 1 gegen 25 % zu unterscheiden (Rechnung: Power 80 %, 29,1 % vs. 25 %). Dies ist eine **Plausibilitätsprüfung**, keine Kalibrierung: andere Population (Menschen, Casual vs. cEDH), Sitz nicht randomisiert, nur Einzelsieger-Partien. Kein automatisierter Abruf (Nutzungsbedingungen unklar, Frame).
- **Weitere Prüfungen**: Stichprobe von Partien durch Menschen auf offensichtliche Pilot-Fehler lesen (Fehlerquote als n/N berichten, "Pilot-Fehlerbericht"); Replay-Treue (Idee mage-go/oracle-replay aus Vorrecherche); Vergleich KI-Entscheidungen mit Mensch bei identischer Lage (Turing-artig). Eine Studie, die den Anteil Deck vs. Pilot an der Siegquote misst, habe ich **nicht gefunden**.
- **Aussageform**: Ergebnisse als "gilt für Pilot X in Konfiguration Y" kennzeichnen; MCTS-Arbeiten für Magic (Cowling et al. [T]) testen gegen Bots, nicht gegen Menschen.

### (7) Reproduzierbarkeit / Herkunftsfelder
- NumPy-Doku [S]: hochentropiger Root-Seed (z. B. `secrets.randbits`, 128 Bit), unabhängige Ströme über `SeedSequence.spawn` oder Seed-**Liste** [Worker-ID, Root-Seed]; **keine Seed-Arithmetik** (`root_seed + id` → überlappende Ströme bei nahen Root-Seeds); IDs müssen eindeutig und deterministisch sein. Übertragen: Block-ID als Listenelement, getrennte Ströme für Mischen / Spielzufall / KI.
- Pflichtfelder je Ergebnis (eigene Ableitung aus Frame + Quellen): Root-Seed, Block-ID, Engine-Commit, KI-/Pilot-Konfiguration, Deck-Hashes (beider Varianten), Sitz-Zuordnung je Partie, Log-Hash, Stichprobe n/N, Zensur-/Abbruchzahlen (Timeouts, Unentschieden, Abstürze als eigene Kategorien), Policy-Version (Mulligan, KI).

---

## 4. Einheit der Analyse: der Seed-Block
Wenn ein Seed vier Sitzrotationen (oder zwei Decks) antreibt, sind diese Partien korreliert. Alle Intervalle, Bootstrap-Resamplings, Tests und Stopp-Regeln müssen **je Block** zählen und resamplen (Cluster-Bootstrap), nie je Einzelpartie. Beispiel: 1000 Blöcke × 4 Sitze = 4000 Partien, aber effektive Stichprobe für Blockstatistiken = 1000; ein Wilson-Intervall über 4000 Partien wäre ~2x zu schmal, falls die Partien in einem Block stark korreliert sind (Faktor hängt vom Intra-Block-ρ ab; nicht gemessen). Das ist die Übertragung des Fishtest-Paargedankens, **ausdrücklich meine, nicht von einer Quelle gesagt**.

---

## 5. Mindeststandard für SIMULATE-Ergebnisse im Studio (≤12 Punkte)

1. **Einheit = Seed-Block.** Jede Zahl, jedes Intervall, jeder Bootstrap und jede Stopp-Regel zählt je Block (je Seed), nicht je Einzelpartie; effektives n = Blöcke. *(Fishtest-Paarprinzip [Q7] als Idee, Owen §8.6 [Q1]; Übertragung auf 4 Sitze = eigene Ableitung.)*
2. **Jede Zahl mit n/N und Herkunft; "unbekannt" statt 0**; Timeouts, Unentschieden, Abstürze, Abbrüche als eigene Kategorien ausweisen, nie stillschweigend streichen. *(Frame; Playgroup und TopDeck schließen Unentschieden aus [Q10, Q12]: eine zu nennende Einschränkung.)*
3. **Anteile mit Wilson- oder Jeffreys-Intervall, nie Wald.** *(Brown/Cai/DasGupta [Q18, nur Suchtreffer]; Newcombe zeigt Wald-Probleme beim Paardifferenz-Fall [Q2].)*
4. **Deckvergleiche gepaart auf Blockebene**: Differenz mit Newcombe-Methode 10 (paired) oder gepaartem Block-Bootstrap; Tabelle der diskordanten Blöcke (b, c) mitliefern. *(Q2, Q3.)*
5. **Gemeinsame Seeds nur mit Swap-in-place und gemessener Wirkung**: ρ bzw. Diskordanzanteil t aus Pilotblöcken ausweisen; Vorteil nur beanspruchen, wenn t deutlich unter dem Unabhängigkeitswert liegt (hier 0,39). *(Owen §8.6 [Q1]; eigene Rechnung 2.2/2.3.)*
6. **Vorab Stichprobenplanung, im Ergebnis MDE ausweisen**: Formulierung "kein nachweisbarer Effekt bei n=…, MDE=x pp (95 %/80 %)", nie "Karte ist egal". Referenz: ±3 pp bei p=0,25 ≈ 800 Partien je Anteil; MDE bei 1000/Arm ≈ 5,5 pp. *(Eigene Rechnung 2.1/2.4; Sargent-OC-Kurve [Q5].)*
7. **Balancierte Sitzrotation + Sitz als eigener Faktor**: jede Variante je Block in allen vier Sitzen; Sitzkurve mitberichten; Referenzanteil 25 % nur bei Balance. *(Playgroup [Q10], TopDeck [Q12].)*
8. **Mehrfachvergleiche**: Familie vorab festlegen; Bestätigung mit Holm (FWER), Exploration höchstens mit BH (FDR; bewiesen für unabhängige Statistiken); **Screening auf anderen Seeds als Bestätigung** (Winner's Curse). *(BH 1995 [Q4]; Holm [T].)*
9. **Stopp-Regel vorab registrieren**: feste Blockzahl oder alpha-spending / always-valid; kein freies Nachsehen (naives 5-maliges Peeking ≈ 13,7 % statt 5 % Fehlalarm). *(Johari et al. [Q9, A]; Howard et al. [Q19, T]; Lan/DeMets [T]; eigene Simulation 2.6. Playgroup macht es vor: Kriterium und Lesezeitpunkte vorab festgelegt [Q11].)*
10. **Nicht-Gewinn-Metriken**: exakt (hypergeometrisch) wo möglich, simuliert nur Engine-/Entscheidungsabhängiges; immer mit Intervall und offengelegter Mulligan-/Spiel-Policy; Zeit-bis-Ereignis zensurbewusst mit "nicht erreicht" als n/N. *(Messlatte: EDHREC [Q13] und Hareruya [Q14] berichten keine Intervalle.)*
11. **KI-Gültigkeit als Aussagegrenze**: Ergebnisse nur "für Pilot X in Konfiguration Y"; mitliefern: Pilot-Fehlerquote aus manueller Stichprobe (n/N) und Sitzkurven-Plausibilitätsprüfung gegen Echtdaten (mit Populations-Caveats); Ceteris-paribus-Swaps nur als marginaler Effekt gegeben den Rest des Decks. *(Sargent [Q5]; Playgroup/TopDeck [Q10, Q12]; Confounding-Warnung [Q15, A].)*
12. **Herkunftsfelder je Ergebnis**: Root-Seed (hochentropisch) + Block-ID als Liste (keine Seed-Arithmetik), getrennte Ströme, Engine-Commit, KI-Konfiguration, Deck-Hashes, Sitz-Zuordnung, Log-Hash. **Ergebnisse fließen nie in Tierliste oder Kartenbewertung.** *(NumPy-Doku [Q6]; Frame.)*

---

## 6. Offene Lücken / nicht belegt
- **Fishtest-Formeln** (Pentanomial-Varianz, Normalized-Elo-Herleitung): Wiki liefert sie nicht; Quelle (PDF-Notizen von M. Van den Bergh) nicht abgerufen. Alle Aussagen zur Paar-Varianzreduktion stammen aus Forum-Suchtreffern (kein Beleg).
- **Übertragung der Pentanomialidee auf 4 Sitze**: keine Quelle; nur meine Ableitung (Blockdifferenz −4..+4). Verteilungsform und Intra-Block-Korrelation ungemessen.
- **ρ/Diskordanz in echter Engine**: unbekannt. Ob XMage Mischzufall, Spielzufall und KI-Zufall trennt (Voraussetzung für Synchronisation), unbekannt.
- **McNemar-/Connor-Formel, Kaplan-Meier, Permutationstest, Holm 1979, Agresti-Coull**: nicht als Primärseite abgerufen. Brown/Cai/DasGupta-Seite lieferte leeren Text; Empfehlung nur aus Suchtreffer.
- **Lan/DeMets-Grenzen**: nur Spending-Formel über Rechner-Seite; `ldbounds`-Handbuch: HTTP 403; exakte Grenzen nicht berechnet; **GSPRT-/mSPRT-Annahmen** (Unabhängigkeit, Varianzform): auf den abgerufenen Seiten nicht genannt.
- **Plackett-Luce/BT**: nur Abstracts (Hunter 2004 dünn; Weng/Lin nennt BT/PL nicht). Keine Quelle für Sitz-/Positionseffekt-Modelle in Mehrspieler-PL.
- **Deck-vs-Pilot-Anteil an der Siegquote**: keine Studie gefunden (nur indirekte Hinweise, Suchtreffer).
- **Playgroup-Zahlen**: Seite ist zeitabhängig (Suchtreffer 243 938 Partien/29,2 % vs. abgerufen 300 240 Einzelsieger-4er-Partien/29,1 %); Intervallmethode der Seite nicht definiert. TopDeck nutzt Binomialvarianz (Wald-artig, laut Seite nicht benannt). Nutzungsbedingungen beider Dienste für automatisierten Abruf **unklar**.
- **17Lands-GIHWR-Details** (Definition, Bias): nur aus Suchtreffern; Seite selbst nicht abgerufen.
- **Stichproben-/Effektgrößen für Karten-Swaps** in Commander: keine empirische Quelle; "typisch unter MDE" ist Annahme.
- Lizenzfrage: Owen-Kapitel "do not distribute": nur zitiert. Sonst reine Methodenquellen, keine Code-Übernahme; ein Eigennachbau von Wilson/Newcombe/Block-Bootstrap in stdlib genügt (keine neuen Abhängigkeiten, Frame).
