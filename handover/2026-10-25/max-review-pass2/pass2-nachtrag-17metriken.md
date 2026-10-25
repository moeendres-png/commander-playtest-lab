# Nachtrag zum Max-Review Pass 2 — 17-Metriken-Vergleiche + #1004-Eigenaussage-Abgleich

- **Status:** Nachtrag, 2026-10-25. Diese Datei ERGÄNZT den gepushten Pass-2-Bericht
  (`handover/2026-10-25/max-review-pass2/`, Commit `76bb6818`) — sie verändert ihn
  nicht, sie wird nicht gepusht. Was dort als offen stand („17-Metriken-Vergleiche
  nicht gerechnet", „#1004-Eigenaussage nicht geprüft"), wird hier geschlossen,
  soweit die Artefakte es zulassen.
- **Lock:** Lab-Main `217c34d95` (#1007), Pin v13 `90f5c4d3f8`, JAR `bridge_pass2.jar`
  (sha256 `6ba47e02…`) — derselbe Stand wie der Pass-2-Bericht.
- **Evidenzklassen:** DIRECTLY_VERIFIED = aus den Ketten-Dateien neu gerechnet;
  CODE_DERIVED = aus gelesenen Skripten abgeleitet; UNKNOWN = aus den vorliegenden
  Artefakten nicht prüfbar, niemals PASS. Jede Zahl unten trägt ihre Klasse
  (implizit: alle Vergleichszahlen DIRECTLY_VERIFIED, außer wo UNKNOWN steht).

## §1 Warum die offiziellen 17 Metriken nicht direkt laufen

Das offizielle Werkzeug ist `scripts/pilot_decision_report.py compare`
(Worktree `wt-maxreview2` @ `217c34d95`). Es nimmt zwei Report-JSONs
(`{"games": [...]}` mit den von `summarize()` berechneten Metrikfeldern) und
paart Spiele nach (pod, seed). Auf die Transkript-Verzeichnisse direkt
angewendet, scheitert es — Befehl und Fehler, exakt:

```
PYTHONPATH=~/workspace/github/wt-maxreview2/src python3 scripts/pilot_decision_report.py \
  compare ~/workspace/tmp/max-review/pass2-c-base ~/workspace/tmp/max-review/pass2-c-head
IsADirectoryError: [Errno 21] Is a directory: '.../pass2-c-base'
```

`compare` liest Dateien (`args.a.read_text()`), keine Verzeichnisse. Aber auch
einzelne `real_seed*.json`-Dateien wären keine gültigen Reports: `summarize()`
braucht pro Entscheidung einen vollen Record mit `request.pilot_state`
(Zugnummer, Phase, Hand/Board-Sicht), `pilot_s` (Pilot-Zeit) und
Options-Metadaten (`ability_type`, `source_name`, Kartenrollen). Die
reduzierten phase4b-Transkripte enthalten nur Entscheidungs-Frames
(`decision_requested`/`decision_accepted` mit Prompt, legalen und gewählten
Labels) — keine Zeiten, keine Zugnummern, keine Phasen, keine
Options-Metadaten. Es gibt im Skript keinen Import-Pfad für dieses Format
(CODE_DERIVED, `summarize()` Zeilen 204 ff., `compare()` Zeilen 1289 ff.).
**Folge: Die vollen 17 offiziellen Metriken sind aus den Pass-2-Transkripten
nicht ableitbar.** Wer sie will, braucht die vollen Game-Records (wie sie
`pilot_decision_report.py run` live schreibt) oder ein neues
Replay-Protokoll — aus den vorliegenden Artefakten sind 13 der 17 Metriken
UNKNOWN, nicht „same".

**Falle, ausdrücklich benannt:** Füttert man `compare_reports` mit Reports,
die nur einen Teil der Metriken enthalten, liefert `.get(key, 0)` für die
fehlenden Metriken 0-vs-0-Deltas. Die CLI druckt dann „0 of 17 metrics"
geflaggt — das ist KEIN Befund über 17 Metriken, sondern 4 Messungen plus 13
Null-Artefakte. In diesem Nachtrag werden nur die 4 gemessenen Proxies als
Ergebnis berichtet; die 13 anderen stehen als NOT_RUN, nie als „same".

## §2 Was stattdessen gemessen wurde: 4 Transkript-Proxies, offizielle Statistik

Vier Metriken lassen sich aus den reduzierten Frames definieren, exakt so wie
`summarize()` sie zählt (CODE_DERIVED, Abgleich der Zählregeln im Skript):

| Proxy | Definition aus den Frames (= offizielle Zählregel) |
|---|---|
| `decisions` | Anzahl `decision_requested`-Frames (= Anzahl `decision_accepted`-Frames). `summarize` zählt jeden Record einmal. |
| `forced_priority` | `priority`-requested-Frames mit genau 1 legalem Label. `summarize`: priority mit `len(options)==1` → forced. |
| `attacks` | Accepted `declare_attacker`-Frames mit `selected_option_types == ("declare_attacker",)`. `summarize`: chosen options mit `option_type == "declare_attacker"`; `hold_attacker` zählt nicht. |
| `blocks` | Summe der gewählten Labels in accepted `declare_blocker`-Frames. `summarize`: jede chosen option = ein Block (in diesen Daten max. 1 Label/Frame). |

Verglichen wurde mit der offiziellen Funktion `compare_reports` aus
`pilot_decision_report.py` (importiert wie in
`tests/unit/test_pilot_decision_report_compare.py`): gepaarte Seeds, 95 %
Bootstrap-CI, Sign-Flip-p, Holm über die bewegten Metriken. **Holm-Familie
hier = die 4 Proxies** (die 13 fehlenden Metriken haben überall Delta 0 und
fallen aus der Familie — dieselbe Regel wie bei Phase 2/4b, kleinere Familie).
Kein `--primary` (keine Metrik war vor den Spielen benannt), alle Proxies
explorativ. Paarung je Kette 24/24, keine unpaired, keine Warnungen
(DIRECTLY_VERIFIED).

**Kontrollen (Aufwandsregel: Kontrolle aus dem falschen Grund):**
- **Identitäts-Kontrolle:** `pass2-c-base` gegen sich selbst → alle 4 Proxies
  Delta exakt 0,00, kein CI schließt 0 aus, nichts geflaggt. Das Werkzeug
  meldet auf identischen Eingaben keine Änderung. DIRECTLY_VERIFIED.
- **Negativkontrolle (bekannter Fall → bekannte Zahl):** Blocks Kette B,
  Summen über die 24 Spiele: Base 139 → Head 154 — exakt #1006s
  „Blocks 139 → 154" aus dem Pass-2-Bericht. Der Extraktor liefert die
  bekannte Zahl, bevor den neuen Zahlen geglaubt wird. DIRECTLY_VERIFIED.
- **Stolperstein, dokumentiert:** Der erste Builder-Lauf stürzte auf
  `pass2-b/real_seed19_failed_first.json` ab (`transcript: None`) — das ist
  der aufbewahrte fehlgeschlagene Erstversuch von Seed 19 (BRIDGE_TIMEOUT),
  kein Spiel. Korrekt gehandhabt: nur Dateien `real_seed<N>.json` zählen;
  der erfolgreiche Retry `real_seed19.json` ist das 24. Spiel. Die
  Pass-2-Aussage „24/24 ok nach Retry" bleibt bestehen.

## §3 Ergebnisse je Kette (alle 4 Proxies: „same" — nichts bewegt sich)

Mittelwerte je Spiel, Base → Head; Delta = Head − Base; CI = 95 %
Bootstrap-Intervall; „geflaggt" = CI schließt 0 aus; „signifikant" =
Holm-adjustiertes p < 0,05. mde80 = kleinste Änderung, die 24 Paare mit
80 % Power bei 5 % sehen (Planungsgröße, kein Befund).

### Kette A — #1007 (Phase 5), Seeds 1–24, Base `abort24/` → Head `pass2-a/`

| Proxy | Base | Head | Delta | CI95 | p | p_adj (Holm) | Urteil |
|---|---|---|---|---|---|---|---|
| decisions | 3582,58 | 3618,50 | +35,92 | [−327,46, +493,88] | 0,888 | 1,000 | same |
| forced_priority | 948,79 | 938,54 | −10,25 | [−79,46, +66,08] | 0,807 | 1,000 | same |
| attacks | 41,21 | 41,83 | +0,62 | [−2,33, +4,00] | 0,731 | 1,000 | same |
| blocks | 6,42 | 5,83 | −0,58 | [−2,17, +0,88] | 0,507 | 1,000 | same |

Lesart: Keine Proxy-Metrik bewegt sich. Vorsicht bei `decisions`: mde80
601,99 — die Streuung zwischen den Paaren ist so groß, dass nur sehr große
Änderungen sichtbar wären; „same" heißt hier „nichts Großes gesehen", nicht
„nichts verändert". DIRECTLY_VERIFIED.

### Kette B — #1006 (Phase 3), Seeds 1–24, Base `pass2-b/` → Head `abort24/`

| Proxy | Base | Head | Delta | CI95 | p | p_adj (Holm) | Urteil |
|---|---|---|---|---|---|---|---|
| decisions | 3575,00 | 3582,58 | +7,58 | [−78,04, +87,71] | 0,863 | 0,981 | same |
| forced_priority | 942,71 | 948,79 | +6,08 | [−1,46, +17,25] | 0,448 | 0,981 | same |
| attacks | 39,83 | 41,21 | +1,38 | [−0,25, +3,54] | 0,327 | 0,981 | same |
| blocks | 5,79 | 6,42 | +0,62 | [−0,08, +1,58] | 0,187 | 0,746 | same |

Lesart: Auch hier bewegt sich kein Proxy nach Holm. **Wichtige Nuance zu
`blocks`:** Die Summen 139 → 154 sind exakt bestätigt (§2), aber der
gepaarte Test flaggt den Anstieg NICHT (CI berührt fast 0 von unten, mde80
1,20 > Delta 0,62 — 24 Paare lösen +0,62 Blöcke/Spiel nicht auf). Totale
und gepaarter Test widersprechen sich nicht: die Totals sind ein
Summenbefund, der Test eine Signifikanzaussage. #1006s eigene Aussage war
eine Totals-Aussage („Blocks 139 → 154"), keine Signifikanz-Aussage —
kein Widerspruch. DIRECTLY_VERIFIED.

### Kette C — #1004 (Target-Seiten), Seeds 1–24, Base `pass2-c-base/` → Head `pass2-c-head/`

| Proxy | Base | Head | Delta | CI95 | p | p_adj (Holm) | Urteil |
|---|---|---|---|---|---|---|---|
| decisions | 3489,38 | 3575,00 | +85,62 | [−149,42, +316,62] | 0,508 | 1,000 | same |
| forced_priority | 944,04 | 942,71 | −1,33 | [−60,29, +55,25] | 0,966 | 1,000 | same |
| attacks | 43,33 | 39,83 | −3,50 | [−7,58, +0,71] | 0,127 | 0,509 | same |
| blocks | 5,96 | 5,79 | −0,17 | [−1,08, +0,83] | 0,825 | 1,000 | same |

Lesart: Kein Proxy bewegt sich nach Holm. Am nächsten an einer Bewegung ist
`attacks` (−3,50/Spiel, p roh 0,127, nach Holm 0,509) — ausdrücklich kein
Befund, nur die größte (nicht signifikante) Verschiebung der vier Ketten.
Dass eine Target-Seiten-Änderung Angriffe/Blöcke/Entscheidungszahlen nicht
messbar verschiebt, ist plausibel: sie ändert WOHIN gezielt wird, nicht WIE
OFT angegriffen/geblockt wird — aber die eigentlich betroffenen Metriken
(`removal_targets`, `bad_removal_on_own_permanent`) sind gerade die, die aus
den Transkripten nicht ableitbar sind (§4). DIRECTLY_VERIFIED.

### Kette D — #1007 (Phase 5), Seeds 25–48, Base `pass2-d-base/` → Head `pass2-d-head/`

| Proxy | Base | Head | Delta | CI95 | p | p_adj (Holm) | Urteil |
|---|---|---|---|---|---|---|---|
| decisions | 3194,54 | 3155,38 | −39,17 | [−236,79, +147,25] | 0,707 | 1,000 | same |
| forced_priority | 851,92 | 881,88 | +29,96 | [−10,12, +75,21] | 0,215 | 0,861 | same |
| attacks | 37,17 | 37,67 | +0,50 | [−2,42, +3,42] | 0,778 | 1,000 | same |
| blocks | 5,67 | 4,88 | −0,79 | [−2,21, +0,42] | 0,308 | 0,924 | same |

Lesart: Kein Proxy bewegt sich. Zusammen mit Kette A: #1007 verändert in den
vier prüfbaren Proxies nichts Messbares — konsistent mit #1007s Profil
(Zahlungs-Plan: weniger Cancels, gleiche Spielform). Die #1007-Kernzahlen
(Cancels 136 → 82) stehen im Pass-2-Bericht und werden hier nicht erneut
behauptet. DIRECTLY_VERIFIED.

**Gesamtbild §3:** In allen 4 Ketten × 4 Proxies = 16 Vergleichen ist kein
einziger Proxy nach Holm signifikant und kein einziges CI schließt 0 aus.
Das heißt NICHT „die Änderungen wirken nicht" — Hash-Divergenz (A 12/24,
B 14/24, C 23/24, D 13/24) und Sieger-Wechsel belegen Verhaltensänderung.
Es heißt: Die vier groben Zähl-Proxies (wie oft entschieden/gepasst/
angegriffen/geblockt) fangen die Änderungen nicht ein. Die feinen Metriken
dazu sind die 13 nicht ableitbaren (§4).

## §4 Die 13 nicht ableitbaren offiziellen Metriken (NOT_RUN, mit Grund)

Alle Gründe folgen aus demselben Defizit: Die reduzierten Transkripte haben
keine `pilot_state`, keine Zeiten, keine Options-Metadaten, keine
Kartenrollen (CODE_DERIVED aus `summarize()`):

| Metrik | Warum aus den Transkripten nicht ableitbar |
|---|---|
| `turns`, `own_turns` | Keine Zugnummern in den Frames (`pilot_state.turn_number` fehlt). |
| `wall_s`, `pilot_s` | Keine Zeiten in den Dateien (weder Top-Level noch pro Frame). |
| `spells_cast` | Zauber haben in den reduzierten Frames keinen eigenen Optionstyp: Priority-Auswahlen sind nur `pass_priority`/`activated_ability`/`mana_ability`; die Zauber-Erkennung in `summarize` läuft über `ability_type == "spell"` in den Options-Metadaten, die hier fehlen. |
| `removal_targets`, `bad_removal_on_own_permanent` | Brauchen Kartenrollen (Removal?) + Ziel-Eigentümerschaft aus dem State; Labels tragen nur Kartennamen, keine Rollen, keine Besitzverhältnisse. |
| `counters_cast`, `wipes_cast` | Brauchen Kartenrollen (Counter? Wipe?) aus `card_facts`/`card_roles` + State — beides fehlt. |
| `bad_idle_main_with_castable_spell`, `bad_idle_main_with_unplayed_land` | Brauchen Phase (Main?) + Hand/Land-Stand aus `pilot_state` — beides fehlt. |
| `bad_wipes_while_ahead` | Braucht Board-Bewertung („vorn?") aus dem State — fehlt. |
| `spells_per_player_round` | Braucht `spells_cast` UND Runden — beides fehlt. |

`bad_attacks_into_killer` und `bad_needless_chump_blocks` sind ohnehin
„not compared" im offiziellen Tool (sie zählen mit dem Pilot-Score selbst,
ein Pilot, der ihm folgt, zeigt nie einen) — sie gehören nicht zu den 17.

## §5 #1004-Eigenaussage-Abgleich (Body gelesen, Urteil je Claim)

Quelle: PR #1004 „Pilot Phase 1: aim targets by side, gift to the weakest,
life and commander clock", state closed, gelesen per GitHub-API
(`list_pull_requests`, state=all — `get_pull_request` ist auf dem MCP-Server
nicht advertiziert, der Listen-Weg lieferte den vollständigen Body).
DIRECTLY_VERIFIED (Body-Text). Trennung: Replay-Aussagen vs. Real-Game-Aussagen.

| # | Claim im Body (Real-Game, wörtlich sinngemäß) | Urteil | Beleg |
|---|---|---|---|
| 1 | „Real games, 24 paired seeds, real pod, same jar as main: all 24 complete." | **BESTÄTIGT** | Kette C: 24/24 ok (Pass-2-Bericht + dieser Nachtrag, gleiche Dateien). Vorbehalt: Mein Lauf nutzte `bridge_pass2.jar` (Lab `217c34d95` + Pin v13), nicht #1004s Originallauf-JAR. Die Bridge-Diffs des Paares `c0e5f7f1..053708e56` sind leer (Pass-2-Bericht §1), daher ist kein Verhaltensunterschied durch das JAR zu erwarten — formal bleibt es ein anderes JAR. |
| 2 | „No metric is flagged after Holm correction except `wall_s` in the final run (+12.8 s, taken while the unit suite ran on the same machine; the first run without load: +2.8 s, 'same')." | **TEILWEISE BESTÄTIGT / TEILWEISE OFFEN** | Für die 4 prüfbaren Proxies gilt der erste Halbsatz: nichts geflaggt nach Holm (C: alle p_adj ≥ 0,509, kein CI schließt 0 aus — §3). `wall_s` selbst ist aus den Transkripten NICHT prüfbar (keine Zeiten) → OFFEN, nicht widerlegt. Die übrigen 12 offiziellen Metriken ebenfalls OFFEN (§4), nicht „same". Die +12,8-s-/+2,8-s-Angaben sind Last-Artefakte des Originallaufs und aus diesen Dateien weder bestätig- noch widerlegbar. |
| 3 | „Games diverge early as expected (1 of 24 transcript hashes equal, 11 of 24 winners differ)." | **EXAKT BESTÄTIGT** | Kette C: 1/24 Hash bit-identisch (nur Seed 17), Sieger gleich 13/24 = 11 differieren (Wechsel-Seeds 4, 5, 7, 8, 9, 10, 12, 15, 16, 22, 24). Beide Zahlen stimmen exakt mit dem Body überein. Vorbehalt: Der Body nennt keine Seed-Nummern — ob es dieselben Seeds 1–24 sind, steht dort nicht; die Zahlenübereinstimmung ist exakt, die Seed-Identität nicht belegt. |
| 4 | „Win rate: UNDECIDED, with 24 pairs and this discordance only effects of about 25 points or more would show." | **KEIN WIDERSPRUCH** | Dieser Nachtrag macht keine neue Win-Rate-Aussage; 24 Paare tragen weiterhin keine Win-Rate. Die methodische Aussage bleibt stehen. |
| 5 | Replay-Sign-off: falsche Seiten 76/279 → 21/279 (Pods 48/153 → 17/153, Real-Pod 28/126 → 4/126); Gifts an den schwächsten Gegner 2/26 → 26/26; 102/453 Pod- und 48/~1.500 Real-Pod-Antworten ändern sich. | **REPLAY, NICHT REAL-GAME — NICHT NACHGEPRÜFT** | Diese Zahlen stammen aus dem Replay aufgezeichneter Anfragen, nicht aus echten Spielen. Der Replay-Harness liegt nicht im Repo (B-20-Muster, Pass-2-Bericht §4). Aus den Transkripten sind sie nicht ableitbar (keine Seiten-/Ziel-Information in den Frames, §4). Weder bestätigt noch widerlegt. |
| 6 | „The sign-off is the behaviour signatures on 15 games above (at least 10 required), not a win rate." | **METHODISCHE AUSSAGE, KEIN WIDERSPRUCH** | Die 15-Spiele-Signatur selbst ist Replay (s. Nr. 5). Als Methode (Signatur statt Win-Rate) steht sie im Einklang mit diesem Nachtrag: Auch hier wird keine Win-Rate behauptet. |

**Fazit des Abgleichs:** Der Pass-2-Vermerk „#1004-Eigenaussage nicht geprüft"
ist hiermit überholt: Alle drei prüfbaren Real-Game-Aussagen des Bodies
(24/24 vollständig; nichts geflaggt außer `wall_s`; 1/24 Hash-identisch,
11/24 Sieger-Wechsel) stimmen mit den gemessenen C-Zahlen überein — die
erste und dritte exakt, die zweite für den prüfbaren Teil. Was offen bleibt,
ist ausschließlich das, was die Artefakte prinzipiell nicht hergeben:
`wall_s`, die 12 weiteren offiziellen Metriken und der Replay-Sign-off.
Das ist eine Eingrenzung des Offenen, kein neuer Vorwurf an #1004: Der
PR-Body selbst trennt Real-Game- und Replay-Aussagen sauber, und die
Real-Game-Aussagen halten.

## §6 Was weiterhin offen ist

1. Die 13 offiziellen Metriken (§4) für alle vier Ketten — brauchen volle
   Game-Records oder ein Replay-Protokoll. Insbesondere für #1004 sind das
   genau die Metriken, die die Änderung zeigen würden (`removal_targets`,
   `bad_removal_on_own_permanent`).
2. `wall_s` für #1004 (Originallauf: +12,8 s unter Last / +2,8 s ohne Last) —
   aus den Transkripten nicht prüfbar; eine Wiederholung mit Zeitmessung
   wäre nötig, um die Last-Erklärung zu prüfen.
3. Der #1004-Replay-Sign-off (76/279 → 21/279 u. a.) — Harness nicht im Repo
   (B-20); ohne ihn UNKNOWN, nicht widerlegt.
4. Ob #1004s Originallauf dieselben Seeds 1–24 nutzte wie Kette C — der Body
   nennt keine Seed-Nummern; die exakte Zahlenübereinstimmung spricht
   dafür, beweist es nicht.
5. Mechanismus-Analyse der divergierenden Seeds (warum genau weicht Seed X
   ab?) — in diesem Nachtrag nicht geleistet; Hash-Divergenz ist nur der
   Nachweis, dass etwas abweicht, nicht warum.
6. Die Pass-2-Aussage „17-Metriken-Vergleiche nicht gerechnet" ist durch
   diesen Nachtrag ersetzt durch: 4 Proxies gerechnet (alle „same"), 13
   Metriken NOT_RUN mit Grund. Eine volle 17-Metriken-Aussage gibt es
   weiterhin nicht — wer sie zitiert, muss die Einschränkung mitzitieren.

## Anhang: Reproduktion

Venv aktivieren, Worktree-Stand `wt-maxreview2` @ `217c34d95`,
`PYTHONPATH=<worktree>/src` (sonst lädt das Skript aus der installierten
Venv, nicht aus dem Worktree):

```
source ~/workspace/venvs/commander-lab/bin/activate
export PYTHONPATH=~/workspace/github/wt-maxreview2/src
python3 scripts/pilot_decision_report.py compare --json /tmp/c_cli.json \
  /tmp/proxy_reports/pass2-c-base.json /tmp/proxy_reports/pass2-c-head.json
```

Extraktor (aus den reduzierten Transkripten, nur `real_seed<N>.json`;
`real_seed19_failed_first.json` in `pass2-b/` ist ein aufbewahrter
Fehlversuch, kein Spiel):

```python
import json
from pathlib import Path

def metrics(path: Path) -> dict:
    d = json.loads(path.read_text())
    t = d["transcript"]
    req = [f for f in t if f.get("kind") == "decision_requested"]
    acc = [f for f in t if f.get("kind") == "decision_accepted"]
    forced = sum(1 for f in req if f.get("decision_class") == "priority"
                 and len(f.get("legal_option_labels") or []) == 1)
    attacks = sum(1 for f in acc if f.get("decision_class") == "declare_attacker"
                  and tuple(f.get("selected_option_types") or []) == ("declare_attacker",))
    blocks = sum(len(f.get("selected_option_labels") or []) for f in acc
                 if f.get("decision_class") == "declare_blocker")
    return {"pod": d.get("pod"), "seed": d.get("seed"), "players": 4,
            "status": d.get("status"), "decisions": len(req),
            "forced_priority": forced, "attacks": attacks, "blocks": blocks}
```

Vergleich (Modul-Import wie die Unit-Tests, nicht CLI, damit die Reports
als Objekte vorliegen):

```python
import importlib.util, json
from pathlib import Path
spec = importlib.util.spec_from_file_location(
    "pdr", "/home/hatch/workspace/github/wt-maxreview2/scripts/pilot_decision_report.py")
pdr = importlib.util.module_from_spec(spec); spec.loader.exec_module(pdr)
load = lambda n: json.loads(Path(f"/tmp/proxy_reports/{n}.json").read_text())
r = pdr.compare_reports(load("pass2-c-base"), load("pass2-c-head"))
# r["metrics"][k] je Proxy: before_mean, after_mean, mean_delta, ci95,
# changed, p, p_adjusted, significant, mde80; paired_games == 24
```

Kontrollen: `compare_reports(load("pass2-c-base"), load("pass2-c-base"))` →
alle Deltas 0, nichts geflaggt. Blocks Kette B: Summen 139 → 154.
CLI-Gegenprobe auf den Proxy-Reports (Kette C, Blocks): before 5,9583 →
after 5,7917, Delta −0,1667, changed False, significant False — identisch
zum Modul-Lauf. Offizielle CLI auf Transkript-Verzeichnisse: IsADirectoryError (§1).

## §7 Anhang: §6-Follow-up (2026-10-25)

Dieser Anhang schließt die fünf Arbeits-Punkte aus §6 (in der Reihenfolge des
Auftrags: 1 Mechanismus, 2 Metrik-Audit, 3 Seed-Identität, 4 Replay-Spezifikation,
5 wall_s-Wiederholung; sie entsprechen §6-Items 5, 1, 4, 3, 2). Er wurde auf
ausdrücklichen Auftrag von Hans direkt an diese Datei angehängt; keine andere
Datei wurde verändert, nichts gepusht, nichts gemergt. Detail-Entwürfe der
vier Analyse-Arbeiten liegen unter `~/workspace/tmp/max-review/`
(`section7-p1-draft.md`, `section7-p2-draft.md`, `section7-p3-draft.md`,
`section7-p4-draft.md`); die wall_s-Kette liegt unter
`pass2-c-wall-base/` / `pass2-c-wall-head/` (neue Verzeichnisse, Originale
`pass2-c-base/` / `pass2-c-head/` unberührt). Alle Worktrees nachher sauber
(`git status` leer). Evidenzklassen wie im Nachtrag: DIRECTLY_VERIFIED =
gemessen/gelesen, CODE_DERIVED = aus gelesenen Definitionen abgeleitet,
UNKNOWN = nicht prüfbar, niemals PASS.

### §7.1 Punkt 1: Mechanismus-Analyse der divergierenden Seeds

**Ergebnis (DIRECTLY_VERIFIED aus den Transkript-Dateien):** Kette C (#1004,
Base `c0e5f7f1` vs Head `053708e56`, Seeds 1–24, Real-Pod) divergiert zuerst
fast ausschließlich bei Ziel-Entscheidungen: `target` 22 Paare, `target_amount`
1 Paar (Seed 5), bit-identisch 1 Paar (Seed 17). Kein einziges Paar divergiert
zuerst bei Priority, Mulligan, Mana oder Kampf. Untertypen der 23
Erst-Divergenzen: Spieler-/Gegner-Ziele 11, Kreaturen-/Permanent-Ziele 11,
Mehrfach-Ziel 1. Bei Kreaturen-Zielen wählt der Head in 9/11 Fällen Rograkh
(6×) oder Ishai (3×); Ausnahmen Seeds 8 (Curiosity) und 20 (Chandra). Am
Divergenz-Frame sind die legalen Optionen in allen 23 Paaren identisch — nur
die Wahl unterscheidet sich. Siegerwechsel in 11/24 Paaren; Erst-Divergenz-Index
247–3099, Median 826.

**Methode:** Nur `decision_accepted`-Frames, ordinal aligniert (i-ter gegen
i-ten), `selected_option_labels` (+ `numeric_choice`) verglichen; bei
Längenunterschied nur das gemeinsame Präfix. Für Kette C verifiziert: Im
Vor-Fenster stimmen `sequence`, Klasse, Sitz, Prompt (nach Normalisierung
lauf-spezifischer Karten-Instanz-IDs in Mana-Prompts) und legale Optionen in
allen 24 Paaren exakt überein — Ordinal-Alignierung = Sequenz-Alignierung ist
dort belegt, nicht nur angenommen. Grenze: Transkripte enthalten keine Leben,
keine Power/Toughness, keine Zeiten, keine verdeckten Zustände — die erste
Wahl-Divergenz ist die erste *beobachtbare* Divergenz, nicht bewiesenermaßen
die erste Engine-Differenz.

**Drei Seeds im Detail:**
- **Seed 1** (sauberste, in den Labels selbst belegte Kaskade): Prompt „Select
  a creature you control", Base wählt Psychosis Crawler, Head wählt Rograkh,
  Son of Rohgahh. Schon 13 Frames später lautet der Prompt „Choose attack for
  Rograkh…" statt „…Psychosis Crawler"; Angriff auf denselben Sitz 4. Sieger
  gleich (1 → 1).
- **Seed 2** (latente Kaskade): Spieler-Ziel Seat 1 → Seat 4, danach 1928
  Frames gleiche Prompts, Sieger gleich — die Divergenz wirkt zunächst nicht
  weiter, bleibt aber als Zustandsdifferenz bestehen.
- **Seed 5** (einziger `target_amount`-Fall): Beide Schritte der Mehrfachwahl
  divergieren (Base Seat 2, Head Seat 1); erste Prompt-Abweichung bei der
  Kampfdeklaration; Sieger 3 → 1.

**Ketten A, B, D (nur Verteilung, gleiche Methode):**
- A (#1007, Seeds 1–24): `mana_payment` 9 (2, 3, 4, 10, 11, 12, 13, 18, 23),
  `choice` 3 (8, 16, 20 — alles Mana-Farbwahlen), identisch 12.
- B (#1006, Seeds 1–24): `declare_blocker` 14 (1, 2, 6, 7, 8, 11, 13, 15, 16,
  17, 20, 21, 23, 24), identisch 10. Fehlversuch `real_seed19_failed_first.json`
  ignoriert (kein Spiel).
- D (#1007, Seeds 25–48): `mana_payment` 8, `choice` 5 (alles Mana-Farbwahlen),
  identisch 11.
- Kernbefund: Jede Kette hat genau eine Erst-Divergenz-Signatur aus einer
  Familie (Ziele / Mana / Blocker), keine streut über Familien.

**Weiterhin offen (UNKNOWN):** Ob Head-Spieler-Ziele jeweils der „schwächste"
Spieler sind (keine Leben in den Transkripten prüfbar); warum der Head
Rograkh/Ishai bevorzugt; kausale Zuschreibung einzelner Siegerwechsel (außer
Seed-1-Prompt-Beleg); Zustandsdifferenzen vor der ersten Wahl-Divergenz.

### §7.2 Punkt 2: Metrik-Ableitbarkeits-Audit der 13 NOT_RUN-Metriken

**Ergebnis (CODE_DERIVED aus den gelesenen Definitionen in
`scripts/pilot_decision_report.py`, Worktree `wt-maxreview2` @ `217c34d95`):
0 von 13 exakt ableitbar, 6 teilweise (Proxy/Teilmenge, Bias UNKNOWN),
7 nicht.** Das verfeinert §4 des Nachtrags (dort standen alle 13 als „nicht
ableitbar"): Die 6 teilweisen sind keine offiziellen Metrik-Werte, sondern
Proxies, deren Abweichung von der offiziellen Zählung unbekannt ist. Für #1004
bleibt NOT_RUN für die offizielle Metrik bestehen.

| # | Metrik | Urteil | Grund (kurz; volle Definition: Datei:Zeile im Entwurf) |
|---|---|---|---|
| 1 | `turns` | nicht | Keine `turn_number`, keine Turn-Grenze in den Frames. |
| 2 | `wall_s` | nicht | Kein Zeitwert in den Transkripten. |
| 3 | `pilot_s` | nicht | Kein `pilot_s`-Feld. |
| 4 | `spells_cast` | teilweise (Label-Heuristik) | Gewählte Priority-Labels mit „ — Cast " zählbar (Seed 1: 71); `ability_type` fehlt, alle Casts sind in den reduzierten Typen nur `activated_ability`; Casts außerhalb von Priority-Fenstern UNKNOWN. |
| 5 | `own_turns` | nicht | Weder `active_player_id` noch `turn_number` — Paar (Seat, Zug) nicht bildbar. |
| 6 | `bad_idle_main_with_castable_spell` | teilweise (Proxy, stark überzählend) | Pass + Cast-Angebot aus Labels zählbar; eigener Zug, Postcombat-Main, leerer Stack fehlen. |
| 7 | `bad_idle_main_with_unplayed_land` | teilweise (Proxy, stark überzählend) | Wie Nr. 6, mit Play-Angebot statt Cast-Angebot; gleiche drei fehlenden Bedingungen. |
| 8 | `removal_targets` | nicht | Siehe Vertiefung unten. |
| 9 | `bad_removal_on_own_permanent` | teilweise (Teilmenge, nicht exakt) | Siehe Vertiefung unten. |
| 10 | `wipes_cast` | teilweise (Label + Katalog) | Cast-Name aus Label + Rollen-Lookup im selben Kartenkatalog wie das offizielle Tool; nur mit Katalog, Label-Parsing- und Abdeckungsvorbehalt. |
| 11 | `bad_wipes_while_ahead` | nicht | „Vorn"-Bedingung braucht Board-Power je Spieler — in den Frames vollständig abwesend. |
| 12 | `counters_cast` | teilweise (Label + Katalog) | Wie Nr. 10, Counter-Rolle = Oracle-Text enthält „counter target". |
| 13 | `spells_per_player_round` | nicht | Erbt nicht-ableitbaren Zähler (Nr. 4, nur teilweise) und nicht-ableitbaren Nenner (Nr. 1). |

**Vertiefung removal (die #1004 zeigen würden):** Aus Target-Labels allein
zählbar sind nur Target-Klassen-Paare und deren Prompt-Texte (Seed 1: 81
Paare, 76 Karten-/sonstige Labels, 5 Spieler-Labels); die Prompts sind
neutral („Select a creature" u. ä.) und nennen keine Wirkung.
`removal_targets` daher nicht exakt — alle Target-Ziele zählen ergibt
höchstens eine Obergrenze, der detriment-Permanent-Anteil ist UNKNOWN. Drei
je für sich blockierende Lücken: `context.outcome` fehlt; Quellzauber/-fähigkeit
fehlt (Sequenz-Nähe zum vorherigen Priority-Frame ist keine Quellenverknüpfung
— 59/81 folgen auf Priority, oft ETB-Trigger statt Cast); Objektidentität fehlt
(nur Namen, keine `object_id`; Kopien/Token/Staples nicht unterscheidbar).
Entscheidend: `permanent_owner` liefert die *kontrollierende* Spieler-ID, die
Metrik prüft Kontrolle, nicht Besitz. Eine Approximation über Commander-Namen
bzw. deck-eindeutige Namen aus dem Pod-Input ist daher nur eine Teilmenge mit
Fehlerquellen (Kontrollwechsel falsch-positiv wie falsch-negativ,
Namenskollisionen/Token), und die zweite Bedingung (fremdes Ziel wurde
angeboten) ist aus Namen prinzipiell nicht prüfbar. Fazit: Für #1004 bleibt
NOT_RUN; die Approximation taugt höchstens als manuell geprüfte Stichprobe,
nicht als Metrik-Vergleich.

**Feldgenaue Spezifikation (was ein voller Game-Record / Replay-Protokoll
enthalten müsste, keine Implementierung):** Minimal = exakt die
`recording()`-Eingabe von `summarize()`. Je Spiel: pod/seed/players,
status/winners, Wandzeit-Spanne. Je Frame: `pilot_s`, `turn_number`, `seat` +
`actor_id`, `active_player_id`, `phase` + `step` (Postcombat/Main2-Unterscheidung
nötig, bloßes „Main"-Flag reicht nicht), Stack-Leer-Flag, volle
Options-Metadaten (`ability_type`, `source_name`, `source_object_id`,
`object_id`), `context.outcome` für Target-Klassen, Board-Auszug (`player_id`,
Battlefield mit `object_id`/`name`/`power`) sowie versionsgebundener
Kartenkatalog für Rollen. Ausdrücklich *nicht* nötig für die 13: Leben,
Toughness, Hand, Friedhof, Command Zone. Ein Replay-Protokoll mit nur Labels +
Hashes erfüllt die Bedingung nicht — `public_state_reference` ist ein opaker
Hash, kein dekodierbarer State.

**Weiterhin offen (UNKNOWN):** Bias-Größe aller Proxies, Trefferquote der
Bad-Removal-Approximation, Casts außerhalb von Priority-Fenstern,
Seed-Übertragbarkeit der Seed-1-Beobachtungen. Die Urteile selbst hängen davon
nicht ab, da sie aus den Definitionen und dem nachgewiesenen Fehlen der Felder
folgen.

### §7.3 Punkt 3: Seed-Identität des #1004-Originallaufs

**Urteil: Belegt — #1004s Originallauf nutzte Seeds 1–24, Pod `real`.**
Nicht durch die Zahlenübereinstimmung mit Kette C (die zählt per Nachtrag
ausdrücklich nicht), sondern durch eine Dokument- + Tool-Belegkette.
Evidenzklasse: CODE_DERIVED + DIRECTLY_VERIFIED (Prämissen); nicht
RUNTIME_VERIFIED, weil die PR-Rohdatei selbst nicht vorlag (s. unten).
Der Koordinator hat beide Prämissen selbst nachgelesen und bestätigt.

**Belegkette:**
1. `docs/performance/REFERENCE_36_SEEDS_2026-10-24.md` §1 (gelesen in
   `wt-maxreview2` @ `217c34d95`): „Seeds 1-24 of this run against 24-seed runs
   of earlier states of `main` (same pod, same pin,
   `benchmark_xmage_full_games.py compare`)". Die drei Stufen sind
   Mulligan-Regel (#1002), Betrags-/Kostenregeln (#1003) und Target-Leiter
   (#1004); Zeile 3: „`main` with the target ladder (the run measured on its
   pull request) | 24 of 24 | 24 of 24", dazu „the hashes agree seed by seed".
   „Its pull request" der Target-Leiter ist PR #1004.
2. `scripts/benchmark_xmage_full_games.py`, Funktion `compare` (gelesen):
   `_games_by_key` schlüsselt nach `(pod, seed)`; der Nenner von „identical
   N/M" ist die Schnittmenge der Keys (`keys = sorted(a.keys() & b.keys())`).
   Unter der Lesart des Dokumentsatzes (Referenzseite auf Seeds 1–24
   eingeschränkt) erfordert „24 of 24", dass der PR-Lauf alle 24 Keys
   `(real, 1)` … `(real, 24)` enthält — bei einem 24-Seed-Lauf also exakt diese
   Menge, dieselbe, die Kette C fährt (`seq 1 24`, `--pod real`, Base
   `c0e5f7f1`, Head `053708e56`).
3. Referenz-Datei selbst (reine JSON-Lektüre):
   `docs/performance/measurements-2026-10-24/real36_main_053708e56_run1.json`
   = 36 Spiele, Pod exakt `real`, Seeds exakt 1–36, alle `status ok` — die
   „Seeds 1–24 of this run" sind damit konkret `(real, 1)` … `(real, 24)`.

**Benannte Prämisse (ehrlich):** Die Lesart, dass der Dokument-Vergleich die
Referenzseite auf Seeds 1–24 einschränkt, stützt sich auf den Dokumentsatz
selbst; der exakte `compare`-Aufruf steht dort nicht. Würde man stattdessen
die volle 36-Seed-Datei gegen die 24-Seed-PR-Datei vergleichen, bewiese „24 of
24" nur PR-Keys ⊆ {1–36}. Diese alternative Lesart ist durch nichts belegt,
widerspricht aber dem Dokumentsatz — sie bleibt als Rest-UNKNOWN vermerkt,
ändert am Urteil nichts, solange der Dokumentsatz gilt.

**Vollständiger Suchpfad (was sonst geprüft wurde):** PR-#1004-Body per
GitHub-API vollständig gelesen (4.228 Zeichen; `get_pull_request` nicht
advertiziert, `list_pull_requests` lieferte #1004 vollständig): einzige
Seed-Aussagen sind „Real games, 24 paired seeds, real pod, same jar as main:
all 24 complete", „1 of 24 transcript hashes equal, 11 of 24 winners differ"
und „In 15 recorded games (9 random four-deck precon pods, 6 real-pod
seeds)" — keine einzige Seed-Nummer. Verworfene Fehlbelege: „seed 9"
(Einzelanekdote), Dateiname `phase1_pr_24seeds.json` (nur Anzahl 24).
PR-Kommentare/Reviews per Lesepfad nicht erreichbar (`pull_request_read` /
`issue_read` blockiert, Write-Freigabe im Nur-Lesen-Auftrag nicht benutzt) —
UNKNOWN, ob dort Seed-Listen stehen. Verlinkte Artefakte `pilot-ai/…`
existieren im Repo unter `053708e56` per API nicht — die Rohdatei liegt im
„shared project folder", außerhalb des Repos. Repo-Grep: kein `pilot-ai/`,
keine `PHASE1_ZIELE`/`phase1_pr`-Treffer; `#1004` in md/py/txt/sh: 0 Treffer in
`wt-1004head`, genau 1 in `wt-maxreview2` (das Referenz-Dokument selbst).
Merge `053708e56` = nur 8 Code/Test/Fixture-Dateien, keine Seed-Liste.
`pass2-notes.md`: abort24 ist ein Seeds-1–24-Real-Pod-Korpus, aber Stand
`ee47312a7` (nach #1006, nicht #1004) — Kontext, kein #1004-Beleg.
Nebenklärung: PR-Branch-Head `e3388338…` ≠ Squash-Merge `053708e56`
(1 Parent `c0e5f7f1`, Message „… (#1004)").

**Härtung (nicht Teil dieses Auftrags, keine JVM nötig):**
`pilot-ai/phase1_pr_24seeds.json` aus dem „shared project folder" beschaffen
und per `scripts/benchmark_xmage_full_games.py compare` (reiner JSON-Vergleich)
gegen `real36_main_053708e56_run1.json` laufen lassen. Erwartung bei
Bestätigung: `identical 24/24` ohne `MISSING`. Das höbe den Beleg auf
DIRECTLY_VERIFIED.

### §7.4 Punkt 4: Replay-Harness-Spezifikation für den #1004-Sign-off

**Befund (CODE_DERIVED): Es existiert kein Replay-Harness im Repo, der
76/279 → 21/279 erzeugen kann.** Sucht in `wt-maxreview2` @ `217c34d95` und
`wt-1004head` @ `053708e56` nach `replay`, `279`, `wrong side`,
`target_side`-Verwendungen in `scripts/`: kein Skript zählt Antwort-Seiten.
Der #1004-Diff (8 Dateien) enthält Regel + Tests + neu aufgezeichneten Korpus,
aber kein Zählskript. Schärfster Beleg: Der eingecheckte Korpus
`tests/fixtures/pilot_real_requests/real_pod_v1.jsonl.gz` hat nur 390 Zeilen /
**40 Target-Requests** — der Nenner 279 ist daraus unmöglich. Die 279 muss aus
einem `record --all`-Full-Dump stammen, dessen Docstring selbst sagt: „several
MB, not for the repository". Der Dump liegt nicht im Repo; ob er anderswo
existiert, ist UNKNOWN. Pass-2-Transkripte ebenfalls ungeeignet (nur Prompt +
Labels + `public_state_reference`-Hash, keine Options-IDs, kein Outcome, kein
`pilot_state`).

**Nahe Verwandte, die den Sign-off nicht erzeugen können (je mit Begründung
im Entwurf):** `pilot_request_corpus.py diff` (zählt nur geänderte, nicht
falsche-Seiten-Antworten — aber richtige Basis für den Neubau),
`XmageFullGameReplayExportTest` / `Main full-game-replay` (füttert aufgezeichnete
Wahlen ein, fragt den Piloten nicht), semantisches Replay-Tape (verifiziert
legale Mengen, keine Seiten), Twin-/Hash-Vergleiche (Spielausgänge, keine
Einzelantworten), `test_pilot_target_sides.py` (Regel-Tests, kein Replay).

**Spezifikation (baufertig ohne Rückfrage, keine Implementierung hier):**
- **Prinzip (ehrlich):** Es gibt keine Bridge-Schnittstelle „beantworte diese
  aufgezeichnete Entscheidung in diesem Zustand" — nur Live-Spiel
  (`XmageFullGameRunner.run`) und Ganzspiel-Export-Replay. Der Harness replayt
  daher aufgezeichnete Requests offline durch `policy.decide()`; der Zustand
  steckt bereits in `request.pilot_state` (Pflichtfeld in `policy.py:60`),
  keine Wiederherstellung nötig. Bridge nur einmal: beim Aufzeichnen per
  `record --all` auf gepinntem JAR, Dump per SHA256 einfrieren.
- **Regel nicht neu erfunden:** `target_side()` aus
  `full_game_pilot_targets.py` importieren (Own-/Opponent-Outcome-Listen,
  Terastodon-/Collective-Effort-Overrides, Corpse-Augur-Friedhofs-Ausnahme,
  neutrale/copy/put-in-play-Outcomes = keine Seite); Geschenk-Definition aus
  `choices.py` (drawcard + nur gegnerische Spieler → schwächster per
  `target_threat`); Seiten-Bestimmung per `permanent_owner()`; Leben-/
  Commander-Uhr ausdrücklich aus X/N herausgehalten (rankt nur innerhalb der
  richtigen Seite).
- **Nenner auditierbar:** 6-stufige Filterkette mit Zählern (Target →
  targeted → Outcome hat Seite → beide Seiten angeboten → abzüglich
  nicht-klassifizierbar); Mehrfachziel-Regel als gekennzeichnete
  Spezifikationsentscheidung (falsch, sobald eine gewählte Option falsch liegt;
  zusätzlich pro-Option-Zählung) — Original-Zählmodus dafür UNKNOWN.
- **Ausgaben:** Zählung im Format `base X/N, head X/N` + Pod-Split + Geschenke
  `G/G_total` + geänderte Antworten + `frozen_inputs` +
  `reproduces_original_claim`; Divergenz-JSONL mit vollständigem Feldkatalog;
  Übergangsmatrix (wrong→right etc.).
- **Akzeptanz:** Positivkontrolle (Destroy-Fall Token vs. Birds of Paradise,
  Geschenk-Fall aus den Unit-Tests), Negativkontrollen (Neutral-only-Dump →
  Nenner 0; invertierte Seiten-Labels → Zahl muss sich bewegen; geänderte
  Tabelle → Filterkette muss sich ändern), Determinismus-Doppellauf
  (byte-identisch), Original-Claim-Kontrolle nur bei Vorliegen des
  Original-Dumps.
- **Ehrliche Grenze:** Ohne Original-Dump kann der Neubau 76/279 → 21/279 nicht
  retroaktiv verifizieren, sondern nur ein neues, eingefrorenes Zahlenpaar
  liefern; die Ausgabe muss `reproduces_original_claim: false` tragen, solange
  der Dump fehlt.

**Weiterhin offen:** Original-Dump auffinden (sonst kein retroaktiver Nachweis);
Original-Zählmodus für Mehrfachziele (UNKNOWN); #1004-Kommentare per
Write-Freigabe lesen (Lesepfad blockiert, s. §7.3).

### §7.5 Punkt 5: wall_s-Wiederholung Kette C (JVM-Kette, sequenziell, ohne Last)

**Methode (DIRECTLY_VERIFIED):** Kette C erneut gespielt, Base
(`wt-1004base` @ `c0e5f7f1`) dann Head (`wt-1004head` @ `053708e56`), je Seeds
1–24, Real-Pod, Treiber `~/workspace/tmp/phase4b/phase4b_play.py`, JAR
`~/workspace/tmp/max-review/bridge_pass2.jar` (Bridge-Diffs des Paares leer,
JAR gültig), CWD je Worktree mit `.runtime`, Venv aktiviert. Jede
Spielausführung extern mit Wandzeit gemessen (Wrapper loggt Start/Ende je
Spiel in `wall-c-timings.log` — die Transkript-JSONs enthalten keine Zeiten).
Strikt sequenziell, 1 JVM gleichzeitig, keine parallelen Ketten. Ablauf:
Base Seeds 1–17, dann Runtime-Restart (Kette gekillt, kein Verlust — pro Spiel
sofort geschrieben), Resume ab Seed 18 (fertige Spiele übersprungen), dann
Head Seeds 1–24. Neue Ausgabeverzeichnisse `pass2-c-wall-base/` /
`pass2-c-wall-head/`; Timing-Zeilen 48/48.

**Konsistenzprüfung (DIRECTLY_VERIFIED, Voraussetzung für Vergleichbarkeit):**
Wall-Wiederholung vs Original-Kette C: Hash identisch 24/24 (Base) und 24/24
(Head), Sieger gleich 24/24 und 24/24 — die Wiederholung spielt exakt dieselben
Spiele; die wall_s-Differenz ist damit auf denselben Spielen gemessen, nicht
auf einer anderen Stichprobe.

**Ergebnis (DIRECTLY_VERIFIED, je Seite n=24, alle `status ok`):**

| Seite | Summe | Median | Mittel | Min | Max |
|---|---|---|---|---|---|
| Base | 1673,9 s | 63,6 s | 69,7 s | 46,8 s | 117,6 s |
| Head | 1688,5 s | 67,2 s | 70,4 s | 52,2 s | 125,0 s |

Differenz Head − Base (Summe): **+14,6 s (+0,9 %)**. Gepaarte Differenz je
Seed: Median +2,9 s, Mittel +0,6 s; Head langsamer in 14/24 Seeds — kein
Muster, das auf einen systematischen Effekt deutet (14/24 ist mit Zufall
verträglich).

**Urteil:** Kein Beleg für einen systematischen wall_s-Effekt von #1004. Die
+14,6 s (+0,9 %) liegen weit unter der bekannten Run-zu-Run-Streuung: Das
Referenz-Dokument (`REFERENCE_36_SEEDS_2026-10-24.md` §2) berichtet für
Zwillingsläufe 5,5 % Wandzeit-Unterschied — auf diese Summen umgerechnet rund
90 s, ein Vielfaches der gemessenen Differenz. Die Originallauf-Angabe +2,8 s
(ohne Last) wird damit weder bestätigt noch widerlegt — beide Zahlen sind mit
Rauschen verträglich und in derselben Größenordnung wie Rauschen; ein
systematischer Effekt in dieser Größe ist mit 24 Paaren nicht von Rauschen zu
trennen. Die Messung vergleicht Summen je Spielaufruf (inkl. Interpreter- und
Setup-Anteil, beide Seiten gleich) — absolute Summen sind mit den
`wall_s`-Summen des Originallaufs nicht direkt vergleichbar, die Differenz
schon (Overhead kürzt sich im Mittel heraus).

**Nicht geprüft, per Design (kein Verstoß gegen die Sequenz-Regel):** Die
Last-Zahl (+12,8 s unter Last) wurde NICHT reproduziert. Eine Last-Reproduktion
(parallele Ketten) würde die Sequenz-Regel brechen und Timing gerade
verfälschen — sie ist mit diesem Protokoll prinzipiell nicht prüfbar. Wer die
Last-Erklärung prüfen will, braucht ein anderes Protokoll (z.B. kontrollierte
Hintergrundlast statt zweiter Kette), das hier nicht gefahren wurde.

**Weiterhin offen:** Schärfere wall_s-Aussage bräuchte wiederholte
No-Load-Läufe als Rausch-Baseline (Twin-Varianz quantifizieren) und/oder
deutlich mehr Paare; Last-Erklärung ungeprüft (s. oben).

### §7.6 Was weiterhin offen ist (nach diesem Anhang)

1. **Volle 17-Metriken-Aussage gibt es weiterhin nicht** — wer sie zitiert,
   muss die Einschränkung mitzitieren: 4 Proxies gerechnet (alle „same"), 13
   Metriken: 0 exakt ableitbar, 6 teilweise (Proxy, Bias UNKNOWN), 7 nicht
   (§7.2). Volle Game-Records nach der Feldliste in §7.2 oder ein
   Replay-Protokoll mit diesen Feldern wären nötig.
2. **Replay-Sign-off 76/279 → 21/279 retroaktiv nicht verifizierbar** ohne den
   Original-`record --all`-Dump (§7.4); Neubau liefert nur ein neues,
   eingefrorenes Zahlenpaar mit `reproduces_original_claim: false`.
3. **wall_s-Last-Erklärung (+12,8 s) ungeprüft** (§7.5); No-Load-Zahl +2,8 s
   weder bestätigt noch widerlegt (Rauschen).
4. **Mechanismus:** Ob Head-Spieler-Ziele jeweils der „schwächste" Spieler
   sind, braucht Leben-Daten (§7.1); kausale Sieger-Zuschreibung je Seed
   (außer Seed 1) bleibt UNKNOWN.
5. **Seed-Härtung:** `phase1_pr_24seeds.json` beschaffen + JSON-`compare` gegen
   die Referenz-Datei laufen lassen (§7.3) — hebt den Seed-Beleg auf
   DIRECTLY_VERIFIED.
6. **#1004-Kommentare** per Write-Freigabe lesen (Lesepfad blockiert) — könnte
   §7.3/§7.4 ergänzen, ändert an den dokumentierten Belegen nichts.
