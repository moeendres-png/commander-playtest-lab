# M4 — Schritt 3: Swap-Kandidaten und Prefilter (Nachtrag zum Zwischenbericht)

Stand 2026-10-22, nach Schritt 2. Pool-Regel eingehalten: Jede B-Karte stammt
aus `data/collections/owner_collection_2026-10-12.txt` (Source Lock) und wurde
zusätzlich gegen die vom Owner im Chat gepostete Sammlung mit Stückzahlen
geprüft (alle B-Karten dort ≥1× vorhanden); jede B-Karte hat Facts, keine
Variante ist NOT READY. Vollständige Begründungen je Swap in `candidates.json`.

## Kandidaten und Prefilter-Urteile

Nachweisgrenze des geplanten Designs (Seeds 1–25, Rotation, 100 Paare je
Variante): **±0,177 Siegquoten-Differenz** (Prefilter-Angabe) — kleinere
Effekte sind mit dieser Spielzahl nicht entscheidbar und enden als UNDECIDED.

| ID | Swap (raus ⇒ rein) | Readiness | Prefilter |
|---|---|---|---|
| R1 | Irrigated Farmland ⇒ Temple of Epiphany | READY | **WARN** |
| R2 | Mana Geyser ⇒ Izzet Signet | READY | PASS_TO_GAMES |
| R3 | Counterspell ⇒ Mana Leak | READY | PASS_TO_GAMES |
| R4 | Winds of Rath ⇒ Make a Stand | READY | PASS_TO_GAMES |
| R5 | Chain Reaction ⇒ Rootborn Defenses | READY | PASS_TO_GAMES |
| R6 | Adarkar Wastes ⇒ Restless Spire | READY | **WARN** |
| C1 | Negate ⇒ Azorius Signet | READY | PASS_TO_GAMES |
| C2 | Arcane Denial ⇒ Simic Signet | READY | PASS_TO_GAMES |
| C3 | Whirler Rogue ⇒ Solemn Simulacrum | READY | PASS_TO_GAMES |
| C4 | Adrix and Nev, Twincasters ⇒ Morska, Undersea Sleuth | READY | PASS_TO_GAMES |
| C5 | Wood Elves ⇒ Selvala, Explorer Returned | READY | PASS_TO_GAMES |
| C6 | Fumigate ⇒ Faerie Mastermind | READY | PASS_TO_GAMES |
| C7 | Simic Growth Chamber ⇒ Glacial Fortress | READY | PASS_TO_GAMES |
| C8 | Azorius Chancery ⇒ Scattered Groves | READY | PASS_TO_GAMES |

Zu den WARNs (R1/R6): Der Prefilter meldet „color(s) lose mana source(s):
U (−1), W (−1)" und flexible_source_delta −1. Die Facts weisen beide
Neukarten ausdrücklich als U/R-Quellen aus (`{T}: Add {U}` / `{T}: Add {R}`,
Temple of Epiphany bzw. Restless Spire) und die entfernten Karten als
W/U-Quellen — nach der Schritt-1-Pip-Zählung (Bedarf W12/U32/R31) ist der
Tausch farblich ein Gewinn, kein Verlust; die Prefilter-Zählung ist an
dieser Stelle nicht nachvollziehbar (vermutlich zählt sie die
„flexiblen" W/U-Quellen der Ist-Karten anders). Die WARNs sind dokumentiert,
aber kein Block — beide Kandidaten gehen in Schritt 4 in die Spiele, die
empirisch entscheiden. Keine weiteren blockierten Kandidaten.

Hinweis zur Prefilter-Castability: Sie erbt für Chulane den in Schritt 1
gemeldeten pips-Bug (Commander ohne Farbbedingung) — Baseline und Varianten
sind gleichermaßen betroffen, der Vergleich bleibt intern konsistent.

## Schritt 4 (läuft)

Drei Läufe mit `--stop-when-decided --look-every 5`, Seeds 1–25, Rotation,
Retry-Durchlauf je Lauf: RogShai (Baseline + R1–R6), Chulane A (Baseline +
C1–C6), Chulane B (Baseline + C7–C8). Offene Varianten werden mit Seeds
26–50 nachgemessen; danach Kombi-Lauf der entschieden besseren Swaps und
Endbericht in diesen Ordner.

## Beilagen

`candidates.json` (Swaps + Begründungen), `prefilter_rogshai.json`,
`prefilter_chulane.json` (volle Prefilter-Ausgaben inkl. Castability und
Struktur-Deltas), `variants/*.json` (die 14 exakten Varianten-Deckstände).
