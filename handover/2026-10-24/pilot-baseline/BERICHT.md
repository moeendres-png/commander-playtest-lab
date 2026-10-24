# Pilot-Baseline auf dem neuen Lock — Messbericht zu #999

**Source Lock (verifiziert):** Lab `main` `73b5df50613025ea07fd28c88221f8faab92eb01`
(nach #997/#998) · Fork-Pin v13 `90f5c4d3f8` (aus `config/rules_engines.json` gelesen) ·
Bridge-JAR lokal gebaut, sha256 `87ece5e47e25642a99f22bcd37e72491440fafcb69c11045203cf323b8490430`,
Funktion per Smoke-Pod mit den auf v13 neu echten Decks (2024_death_toll, 2024_family_matters)
bewiesen. Evidenzklasse der Messungen: DIRECTLY_VERIFIED (eigene Läufe auf diesem Lock).
Nicht angefasst: Pilot-Code, `engine-bridge/**`, Decks.

## Kontrolle des Messinstruments (Wrong-Reason-Test)

Der parametrisierte Zensus (mine4-Logik) über den ALTEN Korpus
(`~/workspace/tmp/m4/**/games/*.json`, 2.033 Records) reproduziert die Handoff-Werte:
**6.051.869 Entscheidungen exakt** · Priorität Index-0 **0,9296 ≈ 93,0 %** ·
Mulligan-Keep gesamt **0,5562 ≈ 56 %** (3.020/5.429). Die Pipeline misst,
wofür sie gebaut wurde; die neuen Zahlen unten sind mit denselben Definitionen
erhoben (Skript `census999.py`, Kontrolle `control_v11.json`).

## M1 — Frische Baseline (100 Spiele, neuer Lock)

Korpus: Precon-Pod-Plan Seed 1 wie `precon_pod_sweep` (186 Originale + 9
SYNTHETIC-Proxies = 195 Decks, 49 Pods) × Spiel-Seeds 1 und 2 = 98 Spiele +
Real-Pod × Seeds 1–2 = 2 Spiele. **100/100 abgeschlossen, 0 Fehler**,
317.212 Entscheidungen. Voller Zensus in `baseline_v13.json` (Anhang);
Gegenüberstellung alt/neu in `VERGLEICH.md` (Anhang). Kopfwerte:

- Priorität: 230.087 Entscheidungen (72,5 %), Pass-Anteil (Index 0) **92,5 %**
  (alt 93,0 %) — davon Fenster mit genau einer legalen Option **41,2 %** (alt 35,1 %).
- Mulligan-Keep gesamt **59,2 %** (400/676; alt 55,6 %). Achtung Population:
  alt = M4-Spiele um zwei Custom-Decks, neu = reine Precon-Pods — die Differenz
  ist kein Pilot-Effekt-Nachweis, nur die geforderte Nebeneinanderstellung.
- Cancelled Payments **3,79 je 1.000** Entscheidungen (alt 4,30).

## M2 — Mulligan-Hand im Mitschnitt: NEIN (Fundstelle + kleinste Änderung)

Die gespeicherten `answer`-Mitschnitte enthalten die Hand **nicht**: der
Mulligan-Anfrage-Frame trägt nur actor_seat, Options-Labels, Prompt und
`public_state_reference`; ein rekursiver Key-Scan über einen vollständigen
M4-Spiel-Record findet 0 Hand-bezogene Schlüssel. Die Frames sind
Bridge-autoriert (Java-Seite), Python speichert sie nur.
Die Hand **existiert zur Entscheidungszeit Python-seitig**:
`PilotStateView.hand_names` (+ `hand_size`) — `src/commander_lab/models/pilots.py`.
Kleinste protokoll-erweiternde Änderung, falls der Owner sie will (Python-only,
wird hier NICHT gebaut): Sidecar-Datei zur Tape, geschrieben an derselben
Stelle, an der `pilot_decision_report.recording()` die Requests abgreift;
Schlüssel (game_id, sequence, actor_seat); Inhalt `hand_names` bzw. abgeleitet
Länderzahl + Farbdeckung; nur für Mulligan-Entscheidungen.

## M3 — Power-Kalibrierung (McNemar, gepaarte Spiele)

Formel an den M4-Ergebnissen validiert: die Formel-Spanne der CI-Halbbreiten
**[3,4–4,8] Punkte** trifft den berichteten M4-Bereich (Bootstrap) — 4 von 6
Bündeln exakt, R-C/C-C haben asymmetrische Bootstrap-CIs. Gepoolte Diskordanz
q = 0,0908 (109/1.200 Paare). Benötigte Paarzahlen (80 % Power, α = 5 %):

| Ziel-Effekt | Paare (gepoolt) | RogShai (q=0,097) | Chulane (q=0,085) |
|---|---|---|---|
| 2 Punkte | **1.783** | 1.897 | 1.668 |
| 3 Punkte | **793** | 844 | 742 |
| 5 Punkte | **286** | 304 | 267 |

Konsequenz für Phase-Messungen: 200 Spiele je Arm sehen nur Effekte ≥ ~5
Punkte; für 2–3-Punkte-Aussagen sind 800–1.800 Paare einzuplanen.

## P7 — Kompakt-Transkript (nur Design + gemessene Größe)

Schema (1 Seite): pro Frame eine Index-Zeile
`[sequence, kind, actor_seat, option_count, selected_count, option_ids_hash]`
plus ein einziges Options-Verzeichnis je Spiel (option_id → Label/Typ einmalig).
Rekonstruktion der Entscheidungs-Semantik bleibt möglich (welche Option war
verfügbar/gewählt), der volle State-View entfällt; Tiefe (P/T, Leben) steht
weiter im Live-Mitschnitt (M5-Weg), nicht in der Tape.
Gemessen an 20 Baseline-Spielen: volles Transkript Median **2,16 MB/Spiel**
(Summe 76,5 MB); Kompakt-Indexform Median **192 KB/Spiel = 5,5 %** der
Vollgröße (gzip der Vollform: ~5 % — die Kompaktform erreicht Kompressions-
niveau ohne Entpacken und bleibt zeilenweise auswertbar).

## M7 — Hash-Twin-Basis auf dem neuen Lock (aus der Gegenprüfung)

Die 49 Pod-Spiele des M1-Plans (Seed 1) plus das Real-Pod-Spiel wurden ein
zweites Mal identisch gespielt: **49 von 50 Paaren hash-identisch**. Einzige
Divergenz: **pod-025|seed=1** (Decks: 2022_heads_i_win__tails_you_lose,
2022_the_ruinous_powers_collector_s_edition, 2018_wade_into_battle,
2024_squirreled_away) — auch Pin v13 hat also mindestens einen
nicht-deterministischen Pod im Precon-Plan; die E1-Twin-Basis für
Vorher/Nachher-Vergleiche ist mit 49 stabilen Paaren gelegt (Ablage:
`m7_twin.json`; zwei erste Twin-Versuche endeten in Bridge-Timeouts und
wurden per Retry abgeschlossen — Timeout-Klasse, keine Engine-Fehler).

## M4 — Prioritätsfenster: Aktion angeboten vs. Pass

Live-Mitschnitt (recording-Hook von `pilot_decision_report.py`), 26 Spiele,
64.901 Prioritätsfenster. „Nicht-Mana-Aktion" = mindestens eine legale Option,
die weder `pass_priority` noch `mana_ability` ist (Typ `activated_ability`,
enthält Land-Spiele und Casts; ~0,5 % dieser Optionen sind Mana-Fähigkeiten,
die die Bridge als activated_ability typisiert — Messnote, kein eigener Typ).

- Gesamt: Nur **12,4 %** aller Fenster bieten überhaupt eine Nicht-Mana-Aktion;
  gepasst wird in **92,7 %** aller Fenster — und in **41,9 %** der Fenster
  MIT angebotener Aktion trotzdem.
- Precombat Main (n=16.190): Aktion in 21,2 % angeboten, Pass-trotz-Aktion nur
  18,7 % — im eigenen Main spielt der Pilot, wenn er kann.
- Upkeep (n=12.040): Aktion in 24,3 % angeboten, Pass-trotz-Aktion 42,7 %.
- Kampf-/End-Schritte (n≈1.800–5.700 je Schritt): Aktion in nur 3–5 %
  angeboten, Pass-Rate 99,5–100 % — tote Fenster, wie zu erwarten.
Volltabelle nach Phase/Schritt in `m456.json`.

## M5 — Kampf-Mitschnitt: P/T und Leben aus demselben Frame

26 Spiele, Mitschnitt wie M4. Angriffs-Anfragen sind **pro Kreatur** gestellt
(jede Anfrage = genau 1 Kreatur, Optionen Angriff/Halten): 3.716
Kreatur-Entscheidungen, **38,6 %** werden angreifend deklariert;
Angreifer-Power/Toughness-Median 3/3. (Die „immer genau ein Angreifer"-
Signatur aus dem Alt-Zensus ist damit als Protokollform erklärt, nicht als
Pilot-Verhalten.) Verteidiger-Leben steht für Angreifer nicht im Frame
(die Verteidiger-Wahl ist eine eigene spätere Entscheidung) — für Blocker
liegt alles im selben Frame:
- 598 Blocker-Entscheidungen, **270 gewählte Block-Zuweisungen — alle 270
  mit beiden P/T-Werten und Verteidiger-Leben im selben Frame (100 %)**.
- Block tötet den Angreifer, ohne den Blocker zu verlieren: **27,0 %**.
- Blocker stirbt: **56,3 %** — davon bei Verteidiger-Leben > 20: **16,3 %
  aller Blocks** (44 Fälle: Chump-Blocks bei hohem Leben).
- Abtausch (beide sterben): 16,7 %.

## M6 — Pilot-Zeit je Entscheidungsklasse (20 Spiele)

`pilot_s` aus demselben recording-Hook (gleiche Messstelle wie
`pilot_decision_report.py`), Median/p90 in Millisekunden:
Priorität (n=48.042) 0,72/1,58 · Mana-Zahlung (n=12.245) 0,19/0,48 ·
Angreifer (n=3.154) 2,08/6,64 · Ziel (n=1.164) 1,51/8,82 ·
Choice (n=1.018) 7,67/27,6 · Trigger-Ordnung (n=899) 10,2/29,3 ·
Blocker (n=452) 0,17/0,28. Volltabelle in `m456.json`.
Die teuersten Klassen sind Choice und Trigger-Ordnung — nicht Priorität.

## P9 — Die 147 v11-instabilen Szenario-Keys auf Pin v13

Alle 147 Keys wurden als exakte Cases der M4-Vergleichs-Maschinerie
(Baseline + Bündel-Dateien, Gegner-Tabelle Doom Prevails/Elven Empire/Painbow,
Sitz aus dem Key) auf dem neuen Lock **zweimal** gespielt: **146 von 147
stabil, 1 divergiert** — `custom/rogshai#variant1|seed=3|seat=3`.
Die v13-Hashes liegen alle außerhalb der v11-Hashmengen (erwartet: neuer
Engine-Stand = neue Hash-Basis; Divergenz wird innerhalb des Pins gemessen,
nicht gegen v11-Werte).
Erste abweichende Entscheidung, bestimmt nach Probe-Methode (UUIDs und
Anzeige-Suffixe `[d54]`-Art aus Prompts normalisiert; State-View-Hashes
allein zählen nicht, sie rauschen ab Frame 0):
- **P9-Fall** (Frame 1240, Seq 1241): `choose_use`, Sitz 2 — „Commander in die
  Command Zone oder im GRAVEYARD lassen?" Lauf 1 fragt **Rograkh**, Lauf 2
  **Ishai**. Symptom: Reihenfolge der Commander-Ersatz-Abfragen vertauscht
  (Iterationsordnungs-Klasse, vgl. M3-Welle/Asche-Befund) — Ursache im Code
  hier nicht isoliert, nur das Symptom belegt.
- **Zweiter Fall (M7 pod-025)** (Frame 3246, Seq 3247): `choose_object`,
  „Select a creature", Sitz 0 — Lauf 1 bietet nur **Taurean Mauler**, Lauf 2
  **Lucius the Eternal + Taurean Mauler**. Hier divergiert die legale
  Optionsmenge selbst: tiefer als reines Ordnungsrauschen; der Zustand ist
  vor Frame 3246 auseinander gelaufen, ohne dass die Entscheidungsfolge es
  früher gezeigt hätte. Ebenfalls Ursache offen, Symptom belegt.
Fazit: v13 ist deutlich stabiler als v11 (147→1 instabile Keys), aber nicht
vollständig deterministisch — Restrate in der Größenordnung 1–2 % der Spiele
(M7: 1/50, P9: 1/147).

## Testkommando (vom Issue gefordert)

`python -m pytest tests/unit -q -k "pilot_decision_report or determinism_probe"`
in wt-999 (Lab `73b5df50`): **90 passed, 2849 deselected**.

## Anhang-Dateien

`baseline_v13.json` (M1-Zensus, 100 Spiele) · `control_v11.json` (Kontrolle)
· `m3.json` (Power-Tafel) · `m7_twin.json` (Twin-Vergleich) · `m456.json`
(M4/M5/M6-Aggregate) · `p9_divergence.json` (P9-Zählung) · `VERGLEICH.md`
(Alt/Neu-Tabellen) · Skripte: `census999.py`, `m3_power.py`,
`run_baseline.py`, `run_live.py`, `p9_replay.py`.
Spiele-Records selbst bleiben lokal (Größe); die Aggregate sind vollständig.


