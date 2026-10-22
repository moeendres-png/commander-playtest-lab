# M4 — Deck-Verbesserung RogShai & Chulane: Zwischenbericht (Schritte 0–2)

Stand 2026-10-22, Evidenzklassen wie im Auftrag. Source Lock: Lab main
`d48bbe5f290c92769b7d9eb2cba2745fce5defab` (ab Merge PR #967), Engine Pin v11
`456b0e22`, Bridge-JAR sha256 `69aa31eb…` (M3-versiegeltes JAR). Alle Messungen
`LOCAL_OBSERVED` auf dieser VM (2 Worker, games-per-jvm 6), Gegner- und
Sammlungsdaten `EXTERNAL_DATA` aus dem Repo-Stand des Source Lock.

## Schritt 0 — Stand, Kalibrierung, Readiness

- Kalibrierung auf dem Source-Lock-Stand: **182/195 OK** — exakt wie vorgegeben,
  keine Abweichung (calib.json der M4-Messung, Laufzeit ~100 s).
- Kartenidentität korrigiert (eigener Erfassungsfehler aus der Deck-Ablage):
  Die blaue FIN-Karte im RogShai-Deck ist **Louisoix's Sacrifice** ({U},
  eigenständig), nicht ein Tale's-End-Printing. Foto-Befund + Owner bestätigt;
  `handover/2026-10-22/rogshai-deck/` ist korrigiert. Folge: Die erwartete
  Lücke „Tale's End NO_CARD_FACTS" existiert nicht — ein Facts-Re-Export war
  **nicht** nötig.
- Readiness: **RogShai READY, Chulane READY** (deck_readiness.py gegen den
  Facts-Katalog des Source Lock; Importe je 100 Karten aus den abgenommenen
  Handover-Listen, `rogshai.json`/`chulane.json` liegen bei).

## Gegnerauflösung (Schritt 2, mit Einschränkung)

Die Registry-Listen des Szenarios `primary_4p_rogshai` sind als spielbare
Decklisten nicht vorhanden: Morcant liegt nur teilbeobachtet vor (54 bekannte
Karten, Rest synthetisch — auftragsgemäß nicht verwendbar), Cosmic Spider-Man
nur mit 4 bekannten Karten; die Ensembles sind Unsicherheits-Modelle, keine
Listen. Ersatzregel des Auftrags angewendet und hiermit benannt:

| Sitz-Gegner | Verwendete Liste | Readiness |
|---|---|---|
| Doom Prevails | `data/decks/precons/2026_doom_prevails.json` (offiziell) | READY |
| High Perfect Morcant (BG-Elfen) | `data/decks/precons/2021_elven_empire.json` (Lathril, gleiche Farben/Typal) | NOT READY: 57× NO_CARD_FACTS, 1× NO_PILOT_KNOWLEDGE |
| Cosmic Spider-Man (WUBRG) | `data/decks/precons/2022_painbow.json` (Jared Carthalion) | NOT READY: 51× NO_CARD_FACTS, 9× NO_PILOT_KNOWLEDGE |

Hinweis: Der Facts-Katalog (2.104 Karten) wird aus DECK_GLOBS gespeist, die
`data/decks/precons/*.json` nicht umfassen — ein lokaler Re-Export würde diese
Lücken nicht schließen (geprüft, verworfen). Konsequenz: Die Gegner-Piloten
spielen zwei der drei Decks ohne volles Kartenwissen; **absolute Siegquoten
sind dadurch verzerrt, die gepaarten Vergleiche in Schritt 4 (gleicher Tisch,
gleiche Seeds) bleiben aussagekräftig.**

## Schritt 1 — Analytik

- **Chulane-pips-Befund (gemeldet, auftragsgemäß nicht repariert):**
  `mana_castability_report.py` rechnet für Chulane ohne Farbbedingung
  (`pips {}`), die Castability ist dadurch zu optimistisch (20.000 Trials,
  Seed 20261016: E[Cast] play 6,24 / draw 5,93 Züge). Ursache (CODE_DERIVED):
  `fact_deck_profile` bevorzugt das kuratierte Profil aus
  `known_card_profiles`; `apply_card_facts` füllt nur Power-/Finisher-Rolle,
  nie Pips. Gegenproben produktiv korrekt: Ishai `pips {U:1, W:1}`,
  Rograkh `{}`. Der Facts-Katalog selbst führt Chulane korrekt mit
  `{2}{G}{W}{U}`. Alle Chulane-Manabasis-Aussagen unten stammen deshalb aus
  Deck + Facts, nicht aus dem Castability-Report.
- Castability RogShai (korrekt gerechnet): Ishai E[Cast] play 4,67 /
  draw 4,36; Rograkh immer Zug 1 (MV 0).
- Mulligan (mulligan_keep_table, 4.000 Hände, Seed 7, deterministisch):
  beide Decks Keep-Rate 69,3 %, erwartete Mulligans 0,43; Keep 0 % bei
  0/1/6/7 Ländern, ~71–74 % bei 2, ~100 % bei 3–4 (Tabellen liegen bei).
- Manabasis/Kurve aus Deck-JSONs + Facts (Land = Typ LAND; Farbquelle =
  Add-Regel bzw. „any color" → alle Identitätsfarben):
  - Chulane: 36 Länder, 4 Nichtland-Quellen; Farbquellen W13/G18/U15;
    Pip-Bedarf (Nichtländer) G28/W20/U32; Kurve 1:11, 2:18, 3:12, 4:10,
    5:8, 6:3, 7:2.
  - RogShai: 35 Länder, 10 Nichtland-Quellen; Farbquellen W15/U23/R15;
    Pip-Bedarf W12/U32/R31; Kurve 0:1, 1:15, 2:20, 3:12, 4:11, 5:2, 7:4.

## Schritt 2 — Baseline-Spiele (Seeds 1–25, Sitze 1–4, Rotation an)

Methode: `run_full_game_deck_comparison.py`, die Baseline läuft gegen einen
identischen Twin-Arm (`--variant` = dieselbe Datei) — jede Hash-Abweichung
zwischen den Armen wäre ein Stopp-Signal gewesen. Messläufe mit
games-per-jvm 6 / 2 Workern (Batching laut M3-Handover hash-neutral);
fehlgeschlagene Fälle wurden per `--retry-failed` solo (1 Worker)
nachgefahren.

| Kennzahl | RogShai | Chulane |
|---|---|---|
| Spiele je Arm | 100, failed 0 | 100, failed 0 |
| **Twin-Check (Transkript-Hashes)** | **100/100 Paare identisch** | **100/100 Paare identisch** |
| Siegquote Eigendeck | **17 %** | **8 %** |
| je Sitz 1/2/3/4 | 28 / 20 / 4 / 16 % | 16 / 12 / 0 / 4 % |
| Ø Züge | 46,6 | 47,4 |
| Mulligan in … der Spiele | 34 % | 32 % |
| Kommandant gewirkt | Rograkh 100/100, Ishai 95/100 | Chulane 89/100 |
| Pilot-Fallbacks / Engine-Fehler | 0 / 0 | 0 / 0 |

(Ein Startsitz = 25 Spiele; die Sitzquoten sind entsprechend breit
unsicher. Ø Entscheidungen/Spiel ~2.400–3.000.)

- **Timeout-Artefakte (kein Stopp-Fall):** Zwei Fälle endeten unter
  2-Worker-Last mit `BRIDGE_TIMEOUT` (protocol-Klasse): Speed-Test
  RogShai Seed 1/Sitz 4 (Diagnose-SHA `6bd02ba59eb16ad8`) und
  Chulane-Baseline Seed 3/Sitz 2 (SHA `bc519faeb0c72967`). Beide liefen im
  Solo-Retry fehlerfrei durch — Last-Artefakte wie die M3-Timeout-Pods,
  keine Engine-Fehler, keine Pilot-Abbrüche.
- **Tote Karten: keine** — in beiden Decks wurde jede Hauptdeck-Karte
  (nach Namen aggregiert, inkl. Basics) in 100 Spielen mindestens einmal
  gewirkt/ausgespielt. Zähldefinition: angenommene Priority-Entscheidungen
  mit Label „<Name> — Cast/Play …"; Split-Karten über ihre Hälften
  normalisiert (eigene Messkorrektur: Wear // Tear erschien zunächst tot,
  wird tatsächlich über „Wear — Cast Wear" gewirkt, 18 Casts im
  Baseline-Arm). Aktivierte Fähigkeiten (Cycling, Equip …) zählen nicht
  als Cast. Seltenste Karten: RogShai Irrigated Farmland (2× ausgespielt);
  Chulane Negate (5), Whirler Rogue (7), Adrix and Nev, Twincasters (10),
  Wood Elves (11), Arcane Denial (11), Fumigate (12). Vollständige
  Cast-Tabellen in `analysis_rogshai.json` / `analysis_chulane.json`.
- **Kommandanten-Cast-Zug: UNKNOWN** aus diesen Records — die
  Entscheidungs-Transkripte tragen keinen Zug-Stempel je Entscheidung;
  berichtet wird die Cast-Häufigkeit (s. o.), kein Ersatzwert.
- **Abweichung vom Auftragswortlaut (begründet):**
  `pilot_decision_report.py` spielt nur den fest verdrahteten Smoke-Pod
  (alte `rogshai_current.json` + Kaervek/Hosts of Mordor/Lorehold Spirit)
  und nimmt keine fremden Decks/Tische an; `card_synergy_report.py`
  konsumiert dessen Report-JSON. Ein Lauf hätte eine andere Paarung mit
  einer veralteten Liste gemessen. Stattdessen sind Pilot-Verhalten
  (Entscheidungszahlen, Fallbacks, Engine-Fehler) und Karten-Häufigkeiten
  direkt aus den 200 Vergleichs-Records je Deck ausgewertet — dieselben
  Fragen an den richtigen Spielen.

## Einordnung und nächste Schritte

Chulane steht an diesem Tisch deutlich schwächer da als RogShai (8 % vs.
17 % Siegquote bei identischem Gegner-Setup und gleicher
NOT-READY-Verzerrung) — die Paarvergleiche in Schritt 4 messen gegen genau
diese Referenz. Schritt 3 baut jetzt die Swap-Kandidaten aus diesen
Befunden (u. a. selten gespielte Karten, Manabasis-/Kurvenlücken),
prüft jeden per Readiness + `deck_variant_prefilter.py` und meldet
blockierte Kandidaten mit Grund. Spielstil-Präferenz wird erst nach dem
Bau zur Nachprüfung herangezogen, nicht als Filter.

## Beilagen (Rohdaten, alle < 128 KB)

`analysis_rogshai.json`, `analysis_chulane.json` (Aggregate inkl.
Cast-Tabellen + Twin-Check), `castability_rogshai.json`,
`castability_chulane.json`, `mulligan_rogshai.txt`,
`mulligan_chulane.txt`, `rogshai.json`, `chulane.json` (exakte
Mess-Deckstände). Die 400 Spiel-Records (~je 0,5–1 MB) bleiben lokal
unter `~/workspace/tmp/m4/baseline_*/games/`; Hashes und Aggregate oben
sind daraus reproduzierbar.
