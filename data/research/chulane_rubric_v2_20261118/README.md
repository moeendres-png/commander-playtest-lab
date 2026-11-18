# Kartenverständnis-Raster v2 (2026-11-18)

Entwurf eines zweiten Kartenratings für den Chulane-Pool (922 Karten): je Karte drei Schichten
(deterministische Fakten, regelabgeleitete Muster mit Regelversion, Modellurteil mit Begründung),
sechs Kriterien E, F, T, R, K, D und ein Gesamturteil H (0 bis 100, Vielfache von 5). Es ist das
"neue zweite Gesamtrating" aus dem Owner-Entscheid vom 2026-11-18
([#1369-Kommentar](https://github.com/moeendres-png/commander-playtest-lab/issues/1369#issuecomment-6967718221)).
Das Raster v1 (`../chulane_rubric_20261114/`) bleibt unverändert.

**Status: Entwurf + Pilot, keine Gewichtung im Index.** Bewertet sind nur die 63 Pilotkarten; die
922 Karten sind nicht gelaufen. Der Pilot hat die Schwellen nicht alle erreicht (siehe Bericht);
Owner-Entscheid zu den Ankern (Frage 7) und Freigabe des Vollaufs stehen aus.

## Dateien

| Datei | Inhalt |
|---|---|
| `PILOT_REPORT.md` | Pilotbericht: Ergebnisse gegen die vorab festgelegten Schwellen, v2.1, Empfehlung |
| `GUIDE_v2.md` | Der Rater-Guide (Version 2.1) |
| `calibration_plan.md` | Vorab festgelegter Kalibrierungsplan mit Schwellen |
| `facts_spec.md`, `patterns_spec.md`, `prompt_template.md` | Spezifikation der Fakten, Muster und des Prompts |
| `anchors.json`, `anchors.md` | Ankerkarten und -werte (10 feste v1-Anker, Konsensanker) |
| `output_schema.json`, `example_output.json` | Ausgabeschema; Formatbeispiel mit erfundener Karte |
| `pilot_sample.json` | Pilotstichprobe (63 Karten, Strata, Retest-Karten, v1-Werte); nur zur Kalibrierung |
| `pilot_ratings.jsonl` | 318 Pilotbewertungen, je Zeile eine: `rater`, `batch`, `retest`, `version`, dazu der volle Rater-Inhalt |
| `audit_result.jsonl`, `audit_claims_index.json` | Handprüfung von 40 Regelbehauptungen und deren Index |
| `data/` | `facts.jsonl`, `patterns.jsonl` (rater-sichtbar), `pool_benchmarks.json`, Manifeste, Mustersichten, Token-Schätzung |
| `scripts/` | Extraktion, Prompt, Stichprobe, Anker, Chargen, Auswertung (siehe unten) |

`pilot_ratings.jsonl`: `version` ist `v2` für H1, H2, S1, S2 (H = untere, S = höhere Modellstufe,
je 63 Karten plus 8 Retest-Karten) und `v2.1` für T1, T2 (höhere Stufe, Guide v2.1, 17 Karten je
Rater). Die rohen Rater-Dateien (46 Stück) sind nicht einzeln eingecheckt; sie sind hier vollständig
zusammengeführt.

## Blindheits-Regel

Rater sehen nur `facts.jsonl`, `patterns.jsonl` und den Guide, nie Nutzung, Beliebtheit, Preise oder
v1-Werte. `data/usage_holdout.jsonl` wird von `scripts/extract_facts.py` lokal erzeugt, ist nicht
eingecheckt (`.gitignore`) und darf nie in einen Rater-Prompt. `pilot_sample.json` enthält keine
Nutzungsfelder; Strata wie "Stufe D mit Nutzung" sind nur Kategorien. Ein Schlüssel-Guard in
`extract_facts.py` und `extract_patterns.py` bricht bei Nutzungs-Schlüsseln in den Rater-Dateien ab.
Modellwissen über Beliebtheit lässt sich nicht ausschließen (siehe Bericht, Blindheits-Scan).

## Reproduzieren

Aus dem Repository-Stamm; `python3`, kein Zusatzpaket außer dem Studio-Code für Schritt 1.

1. Fakten, Muster, Stichprobe, Anker, Prompt-Größe aus einer Kopie des Studio-Stores:
   `scripts/run_all.sh <Store-Kopie> <Checkout>` (schreibt `data/usage_holdout.jsonl` lokal).
2. Prompt prüfen: `python3 scripts/render_prompt.py --card "Sol Ring"` oder `--check-leave-one-out`.
3. Chargen-Prompts: `python3 scripts/make_batches.py --out <Ordner> [--run v2.1]`.
4. Auswertung: `python3 scripts/analyze.py`, `python3 scripts/extra.py --batches <Ordner>`,
   `python3 scripts/validate.py [--run v2.1]` (lesen `pilot_ratings.jsonl`).

Stand der Reproduktion: Kartenblöcke und Manifeste der Chargen sind byte-gleich zu den Läufen; die
Läufe H1 bis S2 liefen mit dem Guide vor v2.1, ihr Systemteil (Ankerwerte, Zitatregel) entspricht
daher nicht dem heutigen `GUIDE_v2.md`; die Läufe T1, T2 sind vollständig reproduzierbar.
`analyze.py` und `extra.py` geben die Zahlen des Berichts wieder.

Grenzen: Raterläufe sind Chargen zu 7 Karten, alle Rater stammen aus einer Modellfamilie, der
Pilot hat 63 Karten. Refs #1369

## Stand 2026-11-18 (Arbeitsstand, WIP)
- Vollauf mit Sonnet (v2.1): 50 von 132 Chargen (350 von 922 Karten) bewertet, gespeichert in `fullrun_partial_ratings.jsonl`; der Lauf wurde vom Wochenlimit unterbrochen (Rückkehr ab 2026-11-21 00:00 UTC). Die Skripte `scripts/make_full.py`, `make_batches21.py`, `validate_full.py` enthalten noch absolute Pfade der Arbeitsumgebung und sind nicht pfadunabhängig.
- Die Gate-Tests des Repos (hygiene, tree, docs, ruff) sind für diesen Stand noch nicht gelaufen.
