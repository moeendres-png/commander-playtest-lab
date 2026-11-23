# Phase A: Analyse-Skripte zur Kartenbewertung H (Vorbereitung Bewertung v3)

Gehört zum Vorab-Plan `docs/analysis-reports/rating_v3_plan_20261123.md` (Refs #1404) und zu den
Phase-Berichten `docs/analysis-reports/rating_v3_phaseA1_forensik_20261123.md` und
`docs/analysis-reports/rating_v3_phaseA2_kartenblock_defekte_20261123.md`. Die Skripte lesen nur
alte Daten und rechnen. Sie bewerten keine Karte neu und ändern weder Produkt noch Daten im Repo.
Nur Standardbibliothek und numpy; Zufall nur mit festen Seeds.

Die Ausgaben gehören in einen Ordner **außerhalb** des Repos. Ausnahme sind die beiden kleinen
Ergebnisdateien eine Ebene höher (unten).

## Inhalt

| Datei | Zweck |
|---|---|
| `A1/run_all.sh` | A1-Forensik in fester Reihenfolge: `a1_parity` → `a1_decomp` → `a1_struct` → `a1_external` → `a1_extra` → `a1_top30`; gibt die SHA-256 der Ausgaben aus |
| `A1/a1_common.py`, `A1/a1_stats.py` | Lader (F1, R2 Welle 1 und 2, Retest, Fakten, Manifeste) und Statistik (ICC(2,1), Spearman, gepaarter Bootstrap, AUC, OLS) |
| `A2/a2_inventory.py` | Prüfungen der Kartenblöcke (Layouts, Mechaniken, Verweise, Spezialtypen, Castability, Peers, Pattern-Hits, Rulings, Land-Fakten) und Handstichprobe (Seed 20261122) |
| `A2/a2_uncertainty.py` | Rater-Meldungen mit Zuversicht low/medium, Tags nach Ursache |
| `A2/a2_summary.py` | Gruppen, Scores, Gesamtzahlen; Liste „kaum fair bewertbar“ (`unfair_ids`) |
| `A2/a2_hand_sample_verdicts.json` | Handurteile zur Stichprobe (von Hand geschrieben, Eingabe) |
| `v3_baselines.py` | Vergleichswerte des Plans aus alten Daten (Formel-Bezugsgrößen einschließlich V3c ohne N, alte Werte zu S4/S5/S9, N-Anker-Kandidaten, Offenlegung der vier angesehenen Gewichtungen, Konsens-Anker-Kandidaten, Pilot-Schichten, KI-Breite zu S7, pilotförmiger Trockenlauf der Schwellen S1/S2/S3 (gleichmäßig und differenziell) und S7 gegen H_pooled) |
| `../v3_baselines.json` | Ausgabe von `v3_baselines.py` (nur Kennzahlen und Kartennamen) |
| `../phaseA_unfair_cards.json` | die 60 Karten „kaum fair bewertbar“ (oracle_id, Name, Defektklassen), damit die Pilot-Schicht ohne XMage-Checkout reproduzierbar ist |

## Eingaben, die nicht im Repo liegen

| Variable / Option | Inhalt | Herkunft | Gebraucht von |
|---|---|---|---|
| `A1_USAGE`, `--usage` | `usage_holdout.jsonl`, SHA-256 `c3d1f693…` | lokal von `chulane_rubric_v2_20261118/scripts/extract_facts.py` erzeugte Hold-out-Datei mit Nutzungszahlen (nur Maßstab, nie Rater-Eingabe) | `a1_external`, `a1_extra`, `v3_baselines` (nur S7-Teil; ohne `--usage` entfällt er) |
| `A1_F1RAW` | Original-Chargenprompts von Lauf 1 (`F1_b*.md`, 132 Dateien) | Scratchpad des Laufs vom 2026-11-18 | `a1_parity` (Gegenprobe: Neubau mit `make_batches.py` byte-gleich) |
| `--mage` | XMage-Quelltext-Checkout; gerechnet mit `/home/user/mage` @ `16dc17ea` | Rückseiten-P/T der Transform-Karten | `a2_inventory` (ohne `--mage` fehlt diese Prüfung) |

`A1_CORPUS` ist der Decklisten-Korpus `data/research/chulane_corpus` **im Repo** (nur Gegenprobe zur Nutzungszählung in `a1_external`); er muss nur gesetzt werden, weil `run_all.sh` den Pfad ausdrücklich verlangt. Die ursprüngliche A1-Rechnung nutzte einen Checkout mit Stand `1a70f41f`; die Nachrechnung auf diesem Repo-Stand ergab dieselben Ausgaben.

Alle übrigen Eingaben liegen im Repo unter `data/research/chulane_rubric_v2_20261118/`: F1, R2
Welle 1 und 2 mit Retest, Manifeste, Fakten, Muster, Anker, Guide, G1 und die Prüfer-Marken.

## Aufruf

```
# A1 (A1_REPO: Standard ist dieser Checkout; A1_OUT: Ausgabeordner, Standard ./work_a1)
A1_USAGE=<usage_holdout.jsonl> A1_CORPUS=data/research/chulane_corpus A1_F1RAW=<F1-Chargenprompts> A1_OUT=<ordner_a1> \
  bash data/research/chulane_rubric_v3_20261123/phaseA_scripts/A1/run_all.sh

# A2
PYTHONPATH=src python3 data/research/chulane_rubric_v3_20261123/phaseA_scripts/A2/a2_inventory.py \
  --repo . --mage <xmage-checkout> --out <ordner_a2>
python3 data/research/chulane_rubric_v3_20261123/phaseA_scripts/A2/a2_uncertainty.py --repo . --out <ordner_a2>
python3 data/research/chulane_rubric_v3_20261123/phaseA_scripts/A2/a2_summary.py --out <ordner_a2>

# Vergleichswerte des Plans
python3 data/research/chulane_rubric_v3_20261123/phaseA_scripts/v3_baselines.py \
  --pairs <ordner_a1>/pairs.jsonl --a2 <ordner_a2> --usage <usage_holdout.jsonl> \
  --out data/research/chulane_rubric_v3_20261123/v3_baselines.json \
  --unfair-out data/research/chulane_rubric_v3_20261123/phaseA_unfair_cards.json
```

## Reproduktion (geprüft 2026-11-23, Klon von `main` @ `f4d49ad6`)

- A1: alle sieben Ausgaben byte-gleich (erneut geprüft in Review-Runde 1 mit `A1_CORPUS=data/research/chulane_corpus`) mit den SHA-256 in Bericht A1 §7, also mit dem ursprünglichen Scratchpad-Lauf (`parity.json` `6391dbfc…`, `decomp.json` `83f5b08f…`, `pairs.jsonl` `89f85818…`, `struct.json` `562adc0b…`, `external.json` `45ffe987…`, `extra.json` `1996b94c…`, `top30.json` `055e4836…`).
- A2: alle sechs Ausgaben byte-gleich mit den Phase-A-Dateien (`A2_metrics.json`, `A2_summary.json`, `A2_low_confidence_cards.jsonl`, `A2_hand_sample.txt`, `A2_uncertainty_stats.json`, `A2_uncertainty_precision_sample.txt`).
- `v3_baselines.py`: zweimal byte-gleich; die Ausgaben stimmen mit den eingecheckten Dateien überein.
- Die Pfade wurden parametrisiert und die Lint-Regeln des Repos angewendet (`strict=False` an `zip`, `noqa` an Ausgabetexten). Danach wurde alles erneut gerechnet; die Ergebnisse blieben byte-gleich.

Die A2-Ausgaben `A2_low_confidence_cards.jsonl` und `A2_hand_sample.txt` enthalten Rater-Texte und
Kartenblöcke. Sie bleiben außerhalb des Repos und lassen sich mit den Befehlen oben neu erzeugen.
