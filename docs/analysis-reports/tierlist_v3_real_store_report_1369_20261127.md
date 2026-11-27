# Tierliste v3: Messbericht am echten Store und `oracle_id`-Prüfung (Issue #1369)

- **Datum:** 2026-11-27
- **Repository-Stand (`origin/main`):** `f13666f2c2288ab242fba7e4681a15e55ea0466b`
- **Branch:** `docs/tierlist-v3-real-store-report-1369`
- **Commander-Fokus:** `Chulane, Teller of Tales`
- **Evidenzklasse:** `DIRECTLY_VERIFIED` (Messungen lokal auf isolierter WSL-Kopie des echten Owner-Stores gegen frisch gebauten Repo-Store; echte Store-Quelle unverändert)
- **Datenschutz (`AGENTS.md` §12):** Es wurden ausschließlich aggregierte Kennzahlen mit Zähler/Nenner (`n/N`) und Herkunft erhoben; keine Sammlungsbestände, Notizen, Favoriten, Ausschlüsse oder Rohzeilen verlassen den Rechner.

---

## 1. Messaufbau und Provenienz

| Merkmal | Echter Store (isolierte WSL-Kopie) | Frischer Repo-Store (Referenz auf `origin/main`) |
|---|---|---|
| Quelle | Kopie von `%LOCALAPPDATA%\CommanderStudio\studio.sqlite3` (Owner-PC, Stand 2026-11-25 21:59) | Frisch gebaut per `import-all --commander "Chulane, Teller of Tales" --from-repo --expect-pool 927` |
| Speicherort (außerhalb Repo) | `$HOME/studio-analyse/real_store_copy/studio.sqlite3` | `$HOME/studio-analyse/repo_store_fresh/studio.sqlite3` |
| SHA-256 (Kopie vor Messung) | `7882815f8ca6f918ffdd0abe02d30d8aaaeba62a01526d083cd303d58b22724c` (265.969.664 Bytes) | Neu erstellt |
| Scryfall-Basis (`--scryfall`) | Bereitgestellt im Owner-Store (`35.420` `scryfall_card`-Zeilen) | `oracle_cards.cleaned.jsonl.gz` (Stand 2026-11-24, SHA-256 `deac5cd128c0b01a22b4d5e22b3b1df271012f06b3f27bc88d881fd06ce98046`, `35.420` `scryfall_card`-Zeilen) |
| Tier-Snapshot (`Ausgewogen`) | Epoche `2e6e5e60759e` (`stale: true` gegenüber aktueller Store-Epoche `d2ea3a30cfde`, erstellt `2026-11-25T11:21:20Z`) | Epoche `06d04f1a5214` (`stale: false`, erstellt `2026-11-27T13:02:33Z`) |

---

## 2. A1 — `oracle_id`-Prüfung und Join-Integrität

| Prüfung | Echter Store (Kopie) | Frischer Repo-Store | Delta (Echt − Repo) | Befund |
|---|---:|---:|---:|---|
| Karten in `card` | `1.655` | `1.655` | `0` | identisch |
| Synthetische / fehlende `oracle_id` (`NULL`, `''`, `synthetic:%`, `synth%`) | `0 / 1.655` (`0,0 %`) | `0 / 1.655` (`0,0 %`) | `0` | **kein Bruch** (Vergleichswert Repo: `0 / 1.655`) |
| Join `card JOIN card_role ON oracle_id` (alle Karten) | `1.409 / 1.655` (`85,1 %`) | `1.409 / 1.655` (`85,1 %`) | `0` | identisch |
| Join `card JOIN card_role ON oracle_id` (Chulane-Pool) | `818 / 927` (`88,2 %`) | `818 / 927` (`88,2 %`) | `0` | identisch |
| Join `card JOIN playgroup_card_atlas ON oracle_id` (alle Karten) | `1.655 / 1.655` (`100,0 %`) | `1.655 / 1.655` (`100,0 %`) | `0` | identisch |
| Join `card JOIN playgroup_card_atlas ON oracle_id` (Chulane-Pool) | `927 / 927` (`100,0 %`) | `927 / 927` (`100,0 %`) | `0` | identisch |
| `corpus_deck_card` mit `oracle_id` | `912.890 / 913.063` (`99,98 %`) | `912.890 / 913.063` (`99,98 %`) | `0` | identisch |
| `corpus_deck` gesamt / kanonisch | `10.551` / `10.150` | `10.551` / `10.150` | `0` / `0` | identisch |

**Ergebnis A1:** **Kein Bruch.** Weder `card_role` noch `playgroup_card_atlas` brechen am echten Store; der Anteil synthetischer oder fehlender `oracle_id`s beträgt `0 / 1.655`. Ein Name-Fallback-PR ist nicht erforderlich.

---

## 3. A2 & A3 — Messbericht je Preset und Vergleich Echter Store vs. Repo-Store

### 3.1 Karten- und Invarianten-Vergleich (Echter Store vs. Repo-Store)

- **Direkter Kartenvergleich über alle 927 Pool-Karten:**
  - `Ausgewogen`: `0 / 927` Tier-Abweichungen, `0 / 927` Index-Abweichungen (`max |Δindex| = 0,0`).
  - `Commander-nah`: `0 / 927` Tier-Abweichungen, `0 / 927` Index-Abweichungen (`max |Δindex| = 0,0`).
  - `Turniernah`: `0 / 927` Tier-Abweichungen, `0 / 927` Index-Abweichungen (`max |Δindex| = 0,0`).
- **Owner-Markierungen (`card_mark`):** Im echten Store existieren `79` Einträge in `card_mark` auf `1.655` Karten (im Repo-Store `0 / 1.655`). Gegenprobe auf einer temporären Kopie mit geleerter `card_mark`-Tabelle ergab `0 / 927` Änderungen bei Stufe und Index über alle drei Presets (`Ausgewogen`, `Commander-nah`, `Turniernah`).
- **Entfernte Gewichte (E15 Q1 / `#1696`):** `rubric` und `simulation` sind nicht mehr in `strength.COMPONENTS` enthalten (`False` / `False`).
- **Kartenverständnis (`understanding_field` / `H_pooled`, E17/E19):** Separate Spalte `URTEIL` in `POST /api/strength` (`0 / 922` in `strength_view.compute`, da erst auf API-Antwortebene aus `data/card_understanding/` angehängt); nicht sortierbar, ohne Tier und ohne Index-Gewicht.

### 3.2 Verteilungen, Plausibilität und Qualitätsmerkmale je Preset

Alle Kennzahlen (außer `tier_snapshot`-Zeitstempel/Epoche) stimmen zwischen echtem Store und frischem Repo-Store bitgleich überein (`Delta = 0`). Poolgröße `N = 927`, gerankt `922` (`S..D`), nicht bewertet `N = 5` (Commander + 4 Standardländer), `U = 0`. Der Nenner `28` bei „Stammkarten unten“ bezeichnet die `28` Pool-Karten mit `> 30 %` Anteil in den gezählten Korpus-Listen.

| Preset | S (`Zauber/Land`) | A (`Zauber/Land`) | B (`Zauber/Land`) | C (`Zauber/Land`) | D (`Zauber/Land`) | U | N | Plausibilität Spearman (Alle / Zauber / Länder, `n = 10.128` Decks) | Randkarten oben (`< 5 %` in S/A) | Stammkarten unten (`> 30 %` in C/D) | Dünne Datenlage oben (`< 5` Signale in S/A) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Ausgewogen** (Echt & Repo, Δ = 0) | `39` (`26/13`, `33,3 %`) | `33` (`22/11`, `33,3 %`) | `48` (`38/10`, `20,8 %`) | `185` (`172/13`, `7,0 %`) | `617` (`599/18`, `2,9 %`) | `0` | `5` (`1/4`) | `0,9544` (`922/922`) / `0,9476` (`857/857`) / `0,9941` (`65/65`) | `0 / 72` | `0 / 28` | `0 / 72` (`7 Sig: 59`, `8 Sig: 13`) |
| **Commander-nah** (Echt & Repo, Δ = 0) | `39` (`27/12`, `30,8 %`) | `39` (`27/12`, `30,8 %`) | `45` (`35/10`, `22,2 %`) | `166` (`154/12`, `7,2 %`) | `633` (`614/19`, `3,0 %`) | `0` | `5` (`1/4`) | `0,9625` (`922/922`) / `0,9570` (`857/857`) / `0,9935` (`65/65`) | `2 / 78` (`Vizier of the Menagerie`, `Koma, Cosmos Serpent`) | `0 / 28` | `0 / 78` (`5 Sig: 1`, `6 Sig: 64`, `7 Sig: 13`) |
| **Turniernah** (Echt & Repo, Δ = 0) | `28` (`22/6`, `21,4 %`) | `29` (`17/12`, `41,4 %`) | `47` (`35/12`, `25,5 %`) | `122` (`109/13`, `10,7 %`) | `696` (`674/22`, `3,2 %`) | `0` | `5` (`1/4`) | `0,9570` (`922/922`) / `0,9509` (`857/857`) / `0,9921` (`65/65`) | `0 / 57` | `0 / 28` | `0 / 57` (`6 Sig: 44`, `7 Sig: 13`) |

### 3.3 Gegenproben (Bracket 5 und EDHTop16)

Hinweis zur Stichprobengröße Bracket 5: Die ältere Angabe `B5 n = 265` aus `#1369` stammt vom kleineren Korpusstand vor der Erweiterung (`2.823` kanonische Decks). Im aktuellen kanonischen Korpus (`10.128` Tier-Universums-Decks) beträgt der Nenner der Bracket-5-Gegenprobe `n = 256` (Echter Store = Repo-Store, Δ = 0).

| Preset | Referenz | Nenner | Überlappend: Alle / Zauber / Länder | Ohne Überlappung (`held_out`, genullte Komponenten) |
|---|---|---:|---|---|
| **Ausgewogen** | Korpus B5 | `256` | `0,6275` (`922/922`) / `0,5789` (`857/857`) / `0,9146` (`65/65`) | `0,6361` (`736/736`) / `0,5857` (`672/672`) / `0,8995` (`64/64`) — genullt: `deck_universe, corpus_tuned, tournament, corpus_bracket_slope` |
| **Ausgewogen** | EDHTop16 | `48` | `0,5934` (`16/922`) / `0,5934` (`16/857`) / `unbekannt` (`0/65`) | `0,5845` (`16/922`) / `0,5845` (`16/857`) / `unbekannt` (`0/65`) — genullt: `tournament` |
| **Commander-nah** | Korpus B5 | `256` | `0,6246` (`922/922`) / `0,5756` (`857/857`) / `0,9148` (`65/65`) | `0,6256` (`736/736`) / `0,5769` (`672/672`) / `0,8844` (`64/64`) — genullt: `deck_universe, corpus_tuned, corpus_bracket_slope` |
| **Commander-nah** | EDHTop16 | `48` | `0,5554` (`16/922`) / `0,5554` (`16/857`) / `unbekannt` (`0/65`) | `NOT_RUN` (`tournament` hat Gewicht `0` im Preset) |
| **Turniernah** | Korpus B5 | `256` | `0,6449` (`922/922`) / `0,5961` (`857/857`) / `0,9276` (`65/65`) | `0,6312` (`736/736`) / `0,5797` (`672/672`) / `0,8903` (`64/64`) — genullt: `deck_universe, corpus_tuned, tournament, corpus_bracket_slope` |
| **Turniernah** | EDHTop16 | `48` | `0,8154` (`16/922`) / `0,8154` (`16/857`) / `unbekannt` (`0/65`) | `0,7173` (`16/922`) / `0,7173` (`16/857`) / `unbekannt` (`0/65`) — genullt: `tournament` |

### 3.4 Leave-One-Out-Stabilität (LOO) je aktivem Signal

In allen drei Presets (Echter Store = Repo-Store, Δ = 0) ist `deck_universe` das Signal mit dem größten Einzel-Einfluss; `commander_inclusion` und `bracket_inclusion` stehen unter Gewichtsregel `CORPUS_ZERO` (lokaler Korpus `10.128 >= 30` Decks) wirksam auf `0`.

| Signal | Ausgewogen (Gewicht → Wechsel) | Commander-nah (Gewicht → Wechsel) | Turniernah (Gewicht → Wechsel) |
|---|---|---|---|
| `deck_universe` | `4.0` → **`124 / 927`** | `4.5` → **`152 / 927`** | `2.5` → **`95 / 927`** |
| `corpus_tuned` | `1.5` → `38 / 927` | `1.0` → `29 / 927` | `2.5` → `54 / 927` |
| `corpus_log_lift` | `1.0` → `55 / 927` | `2.0` → `107 / 927` | `0.5` → `15 / 927` |
| `corpus_bracket_slope` | `1.0` → `43 / 927` | `0.5` → `18 / 927` | `2.0` → `60 / 927` |
| `tournament` | `0.5` → `16 / 927` | `0.0` (inaktiv) | `2.0` → `42 / 927` |
| `edhrec_theme_reach` | `0.5` → `11 / 927` | `1.0` → `26 / 927` | `0.0` (inaktiv) |
| `global_inclusion` | `1.0` → `72 / 927` | `0.5` → `32 / 927` | `0.5` → `35 / 927` |
| `combos` | `0.5` → `1 / 927` | `0.5` → `1 / 927` | `1.0` → `2 / 927` |

### 3.5 Redundanz (`r > 0,90`) und Log-Skala-Sensitivität (`k = 100 / 150 / 200`)

- **Redundanz-Prüfung (Plan-Revision #2 in `#1363`):** In allen drei Presets `0` Paare mit `r > 0,90` (`REDUNDANT: kein Paar`). Insbesondere `deck_universe` vs. `corpus_tuned` liegt bei `r = 0,8129` (`n = 922`, unter der Schwelle `0,90`); `deck_universe` vs. `global_inclusion` bei `r = 0,8407` (`n = 922`).
- **Sensitivität (`k = 100 / 150 / 200` vs. Standard `k = 150`):**
  - `Ausgewogen`: `k=100` → `57 / 927` Wechsel (Spearman `0,9530`), `k=200` → `48 / 927` Wechsel (Spearman `0,9555`).
  - `Commander-nah`: `k=100` → `48 / 927` Wechsel (Spearman `0,9566`), `k=200` → `37 / 927` Wechsel (Spearman `0,9644`).
  - `Turniernah`: `k=100` → `49 / 927` Wechsel (Spearman `0,9563`), `k=200` → `27 / 927` Wechsel (Spearman `0,9587`).
- **Empirisches Bayes (Plan-Revision #3, Nenner `< 500`):** Aktiv für `tournament` (`prior_mean = 0,018982`, `prior_strength = 2,0`, `922` Karten, `max_denominator = 500`).

### 3.6 Abdeckung je Signal (Pool `N = 927`, `NOT_RANKED = 5`, Echter Store = Repo-Store, Δ = 0)

| Signal | `PRESENT` | `ZERO_COUNT` | `NO_VALUE` | `NOT_RANKED` |
|---|---:|---:|---:|---:|
| `global_inclusion` | `922` | `0` | `0` | `5` |
| `deck_universe` | `736` | `186` | `0` | `5` |
| `corpus_log_lift` | `736` | `0` | `186` | `5` |
| `corpus_tuned` | `340` | `582` | `0` | `5` |
| `corpus_bracket_slope` | `286` | `0` | `636` | `5` |
| `playgroup_observed` | `183` | `0` | `739` | `5` |
| `tournament` | `160` | `762` | `0` | `5` |
| `edhrec_theme_reach` | `115` | `0` | `807` | `5` |
| `commander_inclusion` | `68` | `0` | `854` | `5` |
| `bracket_inclusion` | `64` | `0` | `858` | `5` |
| `synergy` | `38` | `0` | `884` | `5` |
| `combos` | `13` | `0` | `909` | `5` |
| `tournament_lists` | `0` | `0` | `922` | `5` |

---

## 4. MTGJSON-Abweichungen (`#1367`) und Sub-Archetyp-Befund (`#1368`)

### 4.1 MTGJSON-Gegenprobe (`#1367`)

- **Abgleich Echter Store vs. Repo-Store (`card_signal` für `edhrec_global_inclusion`):** `1.655 / 1.655` Zeilen exakt identisch (`0` Abweichungen, `1` Zeile mit Wert `NULL` gemäß `NULL`-Regel bei nicht-positivem Nenner).
- **Befund aus `docs/research/MTGJSON_GLOBAL_INCLUSION_CHECK_20261115.md`:** Gegen `AtomicCards.json.bz2` (Stand 2026-11-14, SHA-256 `16786d88158d507bcd6e1bc9ec740c8777d16acbad2bd3323ad2464485734317`) liegt Spearman-ρ der Popularitäts-Perzentile über `922 / 922` gerankte Karten bei **`0,9659`** (Salt-Gegenprobe `0,9997`). Alle `12 / 922` Abweicher mit `|Δ Perzentil| > 0,25` weisen in dieselbe positive Richtung und erklären sich durch das farbspezifische `potential_decks`-Universum gegen den ungeteilten MTGJSON-Globalrang; kein Codepfad in `src/commander_lab` liest MTGJSON (`tests/unit/test_studio_mtgjson_guard.py`).

### 4.2 Sub-Archetypen (`#1368`) auf dem aktuellen Store (`10.128` kanonische Decks)

Der Lauf von `scripts/subarchetype_analysis.py` auf beiden Stores liefert exakt identische Ergebnisse (Echter Store = Repo-Store, Δ = 0):
- **Kanonische Decks:** `10.128` (`2.616 / 10.128` mit Bracket-Tag: `B1: 59`, `B2: 606`, `B3: 887`, `B4: 812`, `B5: 252`; `7.512 / 10.128` ohne Bracket-Tag).
- **Tag-Umfang:** `landfall: 2.651`, `blink_bounce: 5.543`, `big_mana: 2.249`, `clue_artifact: 2.014`, `cedh_combo: 5.449`.
- **Spearman gegen Gesamtkorpus (Auswahl):**
  - `deck_universe`: `0,8819` (`landfall`) bis `0,9441` (`blink_bounce`).
  - `corpus_log_lift`: `0,7962` (`clue_artifact`) bis `0,8979` (`blink_bounce`).
  - `corpus_tuned`: `0,7801` (`landfall`) bis `0,9350` (`blink_bounce`).
  - `corpus_bracket_slope`: `0,5090` (`big_mana`) bis `0,7726` (`blink_bounce`) — die stärkere Streuung der Steigung entsteht weiterhin auf kleinen Schnittmengen (`big_mana ∩ B5 = 4 / 252` Decks, `landfall ∩ B5 = 6 / 252` Decks).
- **Einordnung:** Die Empfehlung aus `docs/research/SUBARCHETYPE_ANALYSIS_1368_20261115.md` (**kein Index-Eingriff / kein Archetyp-Filter**) bleibt auch auf dem `10.128`-Deck-Korpus unverändert gültig.

---

## 5. Bilanz aller Änderungen gegenüber E1 bis E6 und Plan-Revision `#1363`

| Punkt | Plan / Plan-Revision (`#1363`) | Aktueller Stand auf `origin/main` (`f13666f2c`) | Abweichung / Status |
|---|---|---|---|
| **E1.a** (Plan-Revision #1) | Raster-Gewicht auf `0` (Umkehrung von 2026-11-14) | `rubric` und `simulation` komplett aus `strength.COMPONENTS` entfernt (`E15 Q1`, `#1696`); Rubrik v2 nur als getrennte Spalte `Kartenverständnis (Modellurteil)` (`URTEIL`, `#1678`, `E17`/`E19`) | Weiterentwickelt per Owner-Entscheid `E15 Q1` |
| **E2.a** | EDHREC-Aufnahme-Gewichte `0`, wenn lokaler Korpus (`>= 30` Decks) vorliegt; Fallback sonst | Aktiv (`rule = CORPUS_ZERO` bei `10.128` Decks) | Umgesetzt & bestätigt |
| **E3.a** | Empirisches Signal-Portfolio | `13` Komponenten in `strength.COMPONENTS`, ohne `rubric`/`simulation`/`tournament_conversion` | Bereinigt per `E15 Q1` |
| **E4.b** | Gezählte `0/N` (`ZERO_COUNT`) als Tier `D` (`E4.a` umschaltbar auf `U`) | `zero_count_tier = 'D'` in allen 3 Presets aktiv | Umgesetzt & bestätigt |
| **E5.a** | `log_share` mit `k = 150`; geplante Cuts `72/50/28/14` | `k = 150` aktiv; Cuts in `#1366` (PR `#1383`) auf `54/35/20/5` rekalibriert | Rekalibriert & bestätigt |
| **E6.a** | UI-Trennung `U`, Datenklassen, Nenner, Konfidenz | In `#1365` umgesetzt; zusätzlich `E15 Q1` (`#1676`–`#1680`): Gesamtrating v1, Layer, Turnier-Conversion und zweite S–D-Skala entfernt | Weiterentwickelt per `E15 Q1` |
| **Plan-Revision #2** | Redundanz `r > 0,90` für `deck_universe` vs. `corpus_tuned` | Gemessen `r = 0,8129` (alle 3 Presets `0` Paare `> 0,90`) | Eingehalten (`kein Paar`) |
| **Plan-Revision #3** | Empirical Bayes im Rechenkern für Nenner `< 500` | Aktiv für `tournament` (`max_denominator = 500`) | Umgesetzt & bestätigt |
| **Plan-Revision #4** | Lokaler MTGJSON-Abgleich (`#1367`) & echter Store (`#1369`) | `#1367` abgeschlossen (`ρ = 0,9659`); `#1369` am echten Store hiermit vorgelegt (`0` Diffs zum Repo-Store) | Erledigt (wartet auf Review & Freigabe durch den Owner) |

---

## 6. Offene Punkte (`UNKNOWN` / `NOT_RUN`) und nächster Schritt

- **`UNKNOWN` / `NOT_RUN`:**
  - `kartenverstaendnis` (`H_pooled`, `n = 922`) wurde in `strength_view.compute` nicht separat abgefragt (wird erst durch `understanding_field.py` auf `POST /api/strength` angehängt); seine Anzeige im Browser am Owner-PC ist hier `NOT_RUN`.
  - `edhtop16` ohne Überlappung im Preset `Commander-nah`: `NOT_RUN`, da `tournament` dort ohnehin Gewicht `0` hat.
- **Nächster Schritt:** Unabhängiges Review dieses PRs abwarten; **danach Stopp bis zur Freigabe durch den Owner** (gemäß `#1369`). Issue `#1369` bleibt bis dahin offen.
