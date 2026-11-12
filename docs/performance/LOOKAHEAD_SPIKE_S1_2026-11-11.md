# S1: Vorausschau durch Neustart, Messversuch (2026-11-11)

Messung für #1168. Kein Merge-Kandidat, keine Änderung an Piloten, Runner oder Bridge, kein
Beleg für Deck- oder Pilotenstärke. Jede Partie ist ein `SIMULATED_RESULT` mit einem Seed und
einem Satz Piloten. Die Stärke der Vorausschau bleibt **UNDECIDED**.

Skript: `scripts/spike_s1_lookahead.py` (`determinism`, `search`, `game`). Es braucht nur die
Bridge-Jar aus `COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD`.

## Frage

Kann man der KI ohne Änderung an der Engine Vorausschau geben, und was kostet sie? Das
Verfahren: Eine Partie auf dem gepinnten Stand ist für einen Seed und eine Antwortfolge
deterministisch. Für eine Entscheidung startet das Skript je Kandidat eine frische Partie
mit demselben Seed, spielt die aufgezeichneten Antworten bis dahin nach (Replay über die
Optionsabdrücke), antwortet mit dem Kandidaten, lässt die Regel-Piloten vier Züge
(eine Runde am Vierertisch) weiterspielen und bewertet das Brett mit `board_score`. Das ist
eine einfache Brettbewertung aus öffentlichen Zeilen (Kreaturenwerte, andere Permanents,
Handkarten, Leben), keine Regel und kein Stärkemaß.

## Aufbau

| Punkt | Wert |
|---|---|
| Engine | Pin `f4d12f6e80`, Bridge aus dem Repo gebaut |
| Tisch | Chulane (Platz 0) gegen drei Precons (`2013_mind_seize`, `2013_power_hungry`, `2011_heavenly_inferno`), Seeds 1 bis 6, Seed 7 für Vorversuche |
| Suchender Platz | nur Platz 0, nur Prioritätsentscheidungen in einer Hauptphase ab Zug 2 |
| Kandidaten | höchstens 4 verschiedene Zauber- oder Land-Optionen je Entscheidung |
| Suchbudget | höchstens 12 Suchen je Partie, Wechsel der Antwort nur bei Vorsprung von mindestens 0,5 Punkten |
| Parallelität | 3 Rollouts gleichzeitig |
| Vergleich | je Seed dieselbe Partie einmal nur mit Regel-Piloten und einmal mit suchendem Platz 0 |

Wichtig für die Einordnung: Die Rollouts sehen die **echte Reihenfolge der Bibliothek**
(der Replay legt sie fest). Das ist eine Obergrenze dessen, was ein ehrlicher Spieler
wissen kann, nicht ein fairer Vergleich.

## Ergebnisse

Vorversuche (Seed 7, Chulane gegen dieselben drei Precons):

* Determinismus: Zwei Partien mit demselben Seed und denselben Antworten stellten dieselben
  4289 Fragen und endeten mit demselben Sieger. Das Replay trägt also.
* Eine Partie mit Suche: 12 Suchen, 2 Antwortwechsel, 477 s gegen etwa 40 s ohne Suche.

Sechs gepaarte Partien (Seeds 1 bis 6), alle zu Ende gespielt (`game_over`):

| Seed | Sieger Regel | Sieger mit Suche | Entscheidungen Regel / Suche | Zeit s Regel / Suche | Antwortwechsel | Rollouts |
|---|---|---|---|---|---|---|
| 1 | Platz 3 | Platz 1 | 4172 / 3781 | 54,6 / 466,4 | 3 | 48 |
| 2 | Platz 1 | Platz 1 | 3161 / 3994 | 32,6 / 549,3 | 2 | 43 |
| 3 | Platz 3 | Platz 3 | 2679 / 2973 | 22,5 / 486,6 | 1 | 47 |
| 4 | Platz 0 | Platz 0 | 3138 / 2346 | 31,4 / 475,9 | 2 | 46 |
| 5 | Platz 0 | Platz 2 | 4101 / 5224 | 40,4 / 512,0 | 2 | 44 |
| 6 | Platz 1 | Platz 3 | 4270 / 3292 | 45,6 / 449,3 | 5 | 42 |

| Messgröße | Wert |
|---|---|
| Siege von Platz 0, nur Regel-Piloten | 2 von 6 (Wilson 95 %: 0,10 bis 0,70) |
| Siege von Platz 0, mit Suche | 1 von 6 (Wilson 95 %: 0,03 bis 0,56) |
| Zeit je Partie, Regel / mit Suche | 37,9 s / 489,9 s (Faktor 12,9) |
| Gesuchte Entscheidungen / Antwortwechsel | 72 / 15 (21 %) |
| Rollouts | 270, im Mittel 24,5 s je Rollout (Neustart plus Replay plus vier Züge) |
| Zeit je gesuchter Entscheidung | 37,5 s bei 3 parallelen Rollouts |
| Vorsprung der gewählten Option gegenüber der Pilotenwahl (Bewertung der Rollouts) | Mittel 1,92, Minimum 0,50, Maximum 4,97 |

Brettbewertung von Platz 0 an Kontrollpunkten (Anfang von Zug 8, 16, 24), nur dort
verglichen, wo die Partien schon auseinandergelaufen sind:

| Zug | Seeds mit beiden Werten | gleich (noch keine Abweichung) | Mittel der Änderung dort, wo sie abweichen |
|---|---|---|---|
| 8 | 6 | 5 | +1,50 (n = 1) |
| 16 | 6 | 2 | +0,66 (n = 4, einmal negativ) |
| 24 | 6 | 1 | +0,89 (n = 5, zweimal negativ) |

## Lesart

1. **Gewinnrate: kein Signal.** 2 von 6 gegen 1 von 6 bei vollständig überlappenden
   Intervallen sagt nichts. Nach dem ersten Antwortwechsel laufen die Partien anders als die
   Vergleichspartie weiter; ein gepaarter Vergleich pro Seed ist deshalb nur noch gleich
   verteiltes Rauschen, keine Zuordnung der Wirkung zu einem Zug.
2. **Brettbewertung: leicht positiv, nicht einheitlich.** Wo die Suche etwas änderte, ist
   die Bewertung im Mittel um 0,7 bis 0,9 Punkte höher, in zwei von fünf Partien bei Zug 24
   aber niedriger. Die Bewertung ist ein Näherungswert und nicht das Gewinnen.
3. **Die Suche ändert selten etwas.** In 21 % der gesuchten Entscheidungen wählt sie eine
   andere Option als der Regel-Pilot. An den übrigen 79 % ist der Regel-Pilot nach dieser Bewertung
   höchstens 0,5 Punkte schlechter als die beste der Kandidaten (so ist die Schwelle gesetzt).
4. **Kosten: nicht tragbar im bisherigen Verfahren.** 13-fache Partiezeit bei höchstens
   12 Suchen. Ein Neustart mit Replay kostet im Mittel 24,5 s, weil jede Kandidatenpartie
   den ganzen bisherigen Verlauf (bis zu etwa 3000 Entscheidungen) erneut durch eine frische
   Bridge spielen muss. Für Partien, in denen die KI jede Entscheidung suchen soll,
   rechnet sich das nicht, und für viele Partien (#1170) erst recht nicht.

## Empfehlung

* Verfahren "Neustart" nicht weiterentwickeln und nicht als Pilot einbauen.
* Wenn Vorausschau gewollt ist, dann in der JVM: Der Spielzustand wird dort kopiert
  (`Game.copy()` in XMage) und der Rollout läuft ohne Neustart und ohne Replay. Das ist eine
  Änderung an der Java-Bridge. Sie braucht das ausdrückliche Go des Owners und danach die
  Requalifikation (PB-03, Siegel, `current_qualification`). Ohne dieses Go wird nichts davon
  begonnen.
* Vorher klären, ob der Nutzen die Mühe trägt: Die Rollouts hier sehen die echte
  Bibliothek und finden trotzdem nur in einem Fünftel der Fälle eine bessere Option. Ein
  ehrlicher Spieler (gemischte Bibliothek, verdeckte Hände) würde weniger finden.
* #1173 (KI-Stil und Spielplan je Deck) hängt nicht von dieser Suche ab und kann auf den
  Regel-Piloten aufbauen.

## Grenzen

* Sechs Seeds, ein Tisch, ein Deck. Das Ergebnis trägt keine Aussage über Stärke und keine
  über andere Decks.
* Die Bewertung `board_score` ist ein Näherungswert aus öffentlich sichtbaren Zeilen.
* Der Replay stützt sich auf Optionsabdrücke der Engine und ist hier für einen Seed
  nachgewiesen (Seed 7 identisch, 4289 Fragen), nicht für beliebige Partien.
* Zeiten: eine Maschine mit mehreren gleichzeitig laufenden Aufgaben, daher mit Streuung.
* Rohdaten (JSON je Seed) liegen im Arbeitsordner der Messung, nicht im Repository; die
  Tabellen oben sind daraus berechnet (Wilson-Intervalle mit z = 1,96).

Refs #1168
