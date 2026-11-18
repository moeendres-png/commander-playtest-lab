# Kartenverständnis-Raster v2 (2026-11-18)

Entwurf eines zweiten Kartenratings für den Chulane-Pool (922 Karten): je Karte Fakten, regelabgeleitete
Muster und ein Modellurteil mit Begründung (Kriterien E, F, T, R, K, D, Gesamturteil H, 0 bis 100 in
Schritten von 5). Es ist das "zweite Gesamtrating" aus dem Owner-Entscheid vom 2026-11-18
([#1369-Kommentar](https://github.com/moeendres-png/commander-playtest-lab/issues/1369#issuecomment-6967718221)).
Das Raster v1 (`../chulane_rubric_20261114/`) bleibt unverändert.

**Status: Entwurf + Pilot + Vollauf (922 von 922 Karten bewertet), keine Gewichtung im Index.** Bewertet sind alle
Karten des Pools mit einem Rater-Lauf der großen Stufe (Raster v2.1, 132 Chargen zu 7 Karten, Stand 2026-11-18).
Nicht alle vorab festgelegten Schwellen sind erfüllt: Anker (3a) verfehlt, Drift (5a) verfehlt/offen (Ersatzgröße
T gegen S: im Mittel 5,5 > 5 und 2 von 16 = 12,5 % > 10 %), Zitatregel nur mit Chulane-Text als Quelle erfüllt (Bericht,
Abschnitte 7 und 9). Der Owner-Entscheid zu den Ankern (Frage 7) steht aus; ob die Bewertungen Verwendung finden, ist
nicht entschieden. Ein Drift-Test (49 Karten, zweiter Lauf) ist gelaufen (PILOT_REPORT §10, 5a knapp verfehlt); ein zweiter Lauf für Grenzfälle steht aus.

## Dateien

| Datei | Inhalt |
|---|---|
| `PILOT_REPORT.md` | Pilotbericht: Ergebnisse gegen die vorab festgelegten Schwellen, v2.1, Empfehlung |
| `GUIDE_v2.md`, `calibration_plan.md` | Rater-Guide (Version 2.1); vorab festgelegter Plan mit Schwellen |
| `facts_spec.md`, `patterns_spec.md`, `prompt_template.md` | Spezifikation von Fakten, Mustern, Prompt |
| `anchors.json`, `anchors.md` | Ankerkarten und -werte |
| `output_schema.json`, `example_output.json` | Ausgabeschema; Formatbeispiel mit erfundener Karte |
| `pilot_sample.json` | Pilotstichprobe (63 Karten, Strata, Retest, v1-Werte); nur zur Kalibrierung |
| `pilot_ratings.jsonl` | 318 Pilotbewertungen: `rater`, `rater_tier`, `batch`, `retest`, `version` plus voller Rater-Inhalt |
| `fullrun_ratings.jsonl` | 922 Bewertungen des Vollaufs (Rater F1, `rater_tier` large, `version` v2.1), eine je Karte |
| `fulldrift_ratings.jsonl` | 49 Zweitbewertungen für den Drift-Test (Rater F2, gleiche Rubrik); Auswertung `scripts/drift_eval.py` |
| `audit_result.jsonl`, `audit_claims_index.json` | Handprüfung von 40 Regelbehauptungen |
| `data/` | `facts.jsonl`, `patterns.jsonl` (rater-sichtbar), Benchmarks, Manifeste, Muster-Stichproben |
| `scripts/` | Extraktion, Prompt, Stichprobe, Anker, Chargen, Auswertung |

`version` v2: H1, H2 (`rater_tier` small) und S1, S2 (large), je 63 Karten plus 8 Retest-Karten; v2.1: T1, T2
(17 Karten je Rater) und F1, alle large. Die rohen Rater-Dateien sind nicht einzeln eingecheckt. Die genaue
Modell-Identität der Rater ist im Verlauf der Owner-Session festgehalten, nicht im Repo.

## Blindheits-Regel

Rater sehen nur `facts.jsonl`, `patterns.jsonl` und den Guide, nie Nutzung, Beliebtheit, Preise oder
v1-Werte. `data/usage_holdout.jsonl` wird von `scripts/extract_facts.py` lokal erzeugt, ist nicht
eingecheckt (`.gitignore`) und darf nie in einen Rater-Prompt. `pilot_sample.json` hat keine Zählwerte, aber
die Strata C und D unterscheiden Karten mit und ohne Nutzung (Kategorie); Rater sehen die Datei nicht. Modellwissen über Beliebtheit lässt sich nicht ausschließen.

## Reproduzieren

Aus dem Repository-Stamm, `python3`; nur Schritt 1 braucht den Studio-Code.

1. `scripts/run_all.sh <Store-Kopie> <Checkout>`: Fakten, Muster, Stichprobe, Anker, Prompt-Größe.
2. `python3 scripts/render_prompt.py --card "Sol Ring"` (auch `--check-leave-one-out`).
3. `python3 scripts/make_batches.py --out <Ordner> [--run v2.1|full]` (`make_full.py`, `make_batches21.py`
   sind Kurzaufrufe). Vollauf: Rohdateien in `<Ordner>/out_full/`, außerhalb des Repos, vom Lead gefüllt.
4. `python3 scripts/analyze.py`, `extra.py --batches <Ordner>`, `validate.py [--run v2.1]` lesen
   `pilot_ratings.jsonl`; `validate_full.py --out <Ordner> [--write-ratings <Datei>]` prüft und führt den Vollauf zusammen.
5. `python3 scripts/quote_check.py --run v2|v2.1|full --batches <Ordner>` (Zitatregel); `python3 scripts/full_qa.py
   --ratings <out_full-Ordner|fullrun_ratings.jsonl> --facts data/facts.jsonl [--usage <usage_holdout.jsonl>]` (Vollauf-QA;
   `--usage` nur nach dem Einfrieren, die Datei bleibt lokal).

Chargen-Kartenblöcke und Manifeste sind byte-gleich zu den Läufen. H1 bis S2 liefen mit dem Guide vor v2.1
(Ankerwerte, Zitatregel im Systemteil weichen vom heutigen Guide ab); T1, T2 und F1 sind voll reproduzierbar.
Grenzen: Chargen zu 7 Karten, alle Rater aus einer Modellfamilie, Pilot nur 63 Karten. Refs #1369

## `audit/` (unabhängige Prüfung, PILOT_REPORT §11)
Berichte der Prüfungen (Rating-Audit, Regelclaims, Gutachten Gesamtrating), `audit_A_flagged.jsonl` (35 vom Audit als zweifelhaft markierte Karten mit Prüfer-Spanne), die Bewertungen des unabhängigen Raters (70 Karten) und des Testlaufs Guide v2.2 (70 Karten) samt Stichproben, sowie der Guide-v2.2-Entwurf. Nichts davon ist im Studio-Datensatz; alle Prüfungen sind nutzungsblind.

