# Determinismus-Zensus (M3) — Zwischenbericht nach Schritt A

Source Lock: Lab `f50a1f754096ac20f30a590f83b66357ee8de3ca` · Engine-Pin `769e6ebbfdf1bd91eb357f63e0e6a3e848ed24b2` (XMage 1.4.62) · Reine Messung und Analyse, kein Fix, kein Repin. Maschine: Muse (2 Kerne, 7 GB RAM), JDK Temurin 17.0.20.1, Maven 3.9.9 (`versions.txt`). Bridge-JAR lokal gebaut, sha256 `868061c9bec25323cfb93c35748a635a6e551fa087b5d59ec50ee5387c83e124` (`jar_sha256.txt`; Claudes JAR `120f3771…` — Byte-Identität laut Auftrag nicht gefordert).

## Schritt 0 — Setup und Kalibrierung (LOCAL_OBSERVED): BESTANDEN

Mage-Artefakte am Pin installiert (BUILD SUCCESS), Bridge per `mvn -B -ntp -DskipTests package` gebaut (BUILD SUCCESS). Kalibrierung (`measure_precon_imports.py --enumerate-missing`, frisches Workdir): **182/195 Decks OK, 31 distinkte fehlende Karten** — exakt die Erwartung, kein STOPP. Rohdaten: `imports.json`.

## Schritt A — Gegenmessung Plan-Seed 6 / Spiel-Seed 6 (LOCAL_OBSERVED)

Befehl (wörtlich): `PYTHONPATH=src python3 scripts/precon_pod_sweep.py --jar <bridge.jar> --out sweep_p6g6_muse.json --import-report imports.json --deck-dir data/decks/precons --plan-seed 6 --game-seed 6 --workers 1` (46 Pods, 1 Spiel/JVM, Laufzeit 46 Min).

Ergebnis: **46/46 Pods ok, 0 failed** auf dieser Maschine. Pod-für-Pod gegen Claudes Referenz (Semantic-Hash-Präfix + Entscheidungszahl): **44 Pods identisch.** Die einzigen zwei Abweichungen sind exakt die von Claude als INSTABIL markierten Pods — **keine neue Abweichung**:

| Pod | Referenz-Hash | Mein Hash | Referenz-Entscheidungen | Meine Entscheidungen | Einordnung |
|---|---|---|---|---|---|
| pod-022 | `8c846626183c` | `a993ad769217` | 3524 | 3524 | bekannt instabil (Referenz) |
| pod-044 | `dbddd7adb46c` | `88c142632960` | 3466 | 3389 | bekannt instabil (Referenz) |

Einordnung der beiden Abweichungen (Zählung, keine Deutung über den Befund hinaus): Bei pod-022 ist die Entscheidungszahl identisch (3524) — der Spielverlauf hat dieselbe Länge, nur der Hash weicht ab; das ist mit Claudes Befund (Kopien-Erzeugung in wechselnder Sitzreihenfolge) verträglich. Bei pod-044 weicht auch die Entscheidungszahl ab (3389 statt 3466) — der Verlauf divergiert inhaltlich, passend zu Claudes Beobachtung wechselnder Angriffswahlen. Die Ursachen-Eingrenzung folgt in Schritt C.

### Pod-für-Pod-Tabelle (alle 46)

| Pod | Status | Semantic (Präfix) | Entscheidungen | Vergleich zur Referenz |
|---|---|---|---|---|
| pod-000 | ok | `c642b667088c` | 1589 | identisch |
| pod-001 | ok | `8bb6e979825f` | 3546 | identisch |
| pod-002 | ok | `2de43efc2e99` | 4307 | identisch |
| pod-003 | ok | `e6ed978264e6` | 1645 | identisch |
| pod-004 | ok | `524d900ffe67` | 3511 | identisch |
| pod-005 | ok | `ea8346cc846d` | 4554 | identisch |
| pod-006 | ok | `d704ac9fdd6a` | 4376 | identisch |
| pod-007 | ok | `e49ba3c68775` | 1620 | identisch |
| pod-008 | ok | `8d8ad3f74121` | 2477 | identisch |
| pod-009 | ok | `8a31292b397c` | 3922 | identisch |
| pod-010 | ok | `bf4a9b13543b` | 2979 | identisch |
| pod-011 | ok | `019a8e98ada2` | 2810 | identisch |
| pod-012 | ok | `7424e2804202` | 2760 | identisch |
| pod-013 | ok | `8edfc06ba135` | 2125 | identisch |
| pod-014 | ok | `52c72b4ff5ee` | 1627 | identisch |
| pod-015 | ok | `dc418b9e9327` | 4393 | identisch |
| pod-016 | ok | `35406771226b` | 2855 | identisch |
| pod-017 | ok | `b94dde258f1e` | 2639 | identisch |
| pod-018 | ok | `6f7855d2c9eb` | 3184 | identisch |
| pod-019 | ok | `4e71b8768656` | 3679 | identisch |
| pod-020 | ok | `d31e7e86f260` | 1977 | identisch |
| pod-021 | ok | `736381fb0598` | 1989 | identisch |
| pod-022 | ok | `a993ad769217` | 3524 | **abweichend (bekannt instabil)** |
| pod-023 | ok | `0543c9890fe3` | 4229 | identisch |
| pod-024 | ok | `549c60c26113` | 2957 | identisch |
| pod-025 | ok | `65c04abcf8fc` | 2150 | identisch |
| pod-026 | ok | `aed08149cfa7` | 3296 | identisch |
| pod-027 | ok | `a82838f9faa1` | 2573 | identisch |
| pod-028 | ok | `2755f46c4cb7` | 1578 | identisch |
| pod-029 | ok | `c0d8f6a1cb66` | 2845 | identisch |
| pod-030 | ok | `ec5379573767` | 2301 | identisch |
| pod-031 | ok | `0ea0d26fd5e6` | 2168 | identisch |
| pod-032 | ok | `7f5bb071a9bb` | 3166 | identisch |
| pod-033 | ok | `e9e997a99b2c` | 5809 | identisch |
| pod-034 | ok | `27f969bd1fce` | 2158 | identisch |
| pod-035 | ok | `3b36a07fddbd` | 3571 | identisch |
| pod-036 | ok | `60d7f23ccdab` | 3800 | identisch |
| pod-037 | ok | `84b054ac111d` | 2638 | identisch |
| pod-038 | ok | `33124fcd018d` | 4294 | identisch |
| pod-039 | ok | `c0fd61803517` | 2297 | identisch |
| pod-040 | ok | `c0c0fd36db45` | 3772 | identisch |
| pod-041 | ok | `bbfe4e6d638b` | 4105 | identisch |
| pod-042 | ok | `004c79636e2c` | 2630 | identisch |
| pod-043 | ok | `761e7120d056` | 4519 | identisch |
| pod-044 | ok | `88c142632960` | 3389 | **abweichend (bekannt instabil)** |
| pod-045 | ok | `6e1f9bb0679e` | 3560 | identisch |

Volle Hashes und alle Felder: `sweep_p6g6_muse.json`.

## Schritt B — alte Linie komplett (Seeds 21–23, Pin 769e6ebb, LOCAL_OBSERVED)

Läufe mit `--games-per-jvm 6 --fast`, je Seed zweimal (x/y). Jeden failed Pod danach einzeln nachgefahren (1 Spiel, frische JVM).

| Seed | Lauf | Pods | ok | failed | Fehlerfamilien |
|---|---|---|---|---|---|
| 21 | x | 46 | 43 | 3 | BRIDGE_TIMEOUT ×1, BLOCK_DECLARATION_REJECTED ×1, BRIDGE_CLOSED ×1 |
| 21 | y | 46 | 44 | 2 | BLOCK_DECLARATION_REJECTED ×1, BRIDGE_CLOSED ×1 |
| 22 | x | 46 | 45 | 1 | XMAGE_ACTION_EXECUTION_FAILED ×1 |
| 22 | y | 46 | 45 | 1 | XMAGE_ACTION_EXECUTION_FAILED ×1 |
| 23 | x | 46 | 45 | 1 | XMAGE_ACTION_EXECUTION_FAILED ×1 |
| 23 | y | 46 | 45 | 1 | XMAGE_ACTION_EXECUTION_FAILED ×1 |

Hash-Vergleiche x gegen y (nur Pods, die in beiden Läufen ok waren):

| Seed | beidseitig ok | davon hash-verschieden | instabile Pods |
|---|---|---|---|
| 21 | 43 | 0 | — |
| 22 | 45 | 1 | pod-004 |
| 23 | 45 | 0 | — |

Instabile Pods im Detail:

- Seed 22 pod-004: x `9605145dc30b` (4671 Entscheidungen), y `1a74a4410b5f` (4671 Entscheidungen). Gleiche Entscheidungszahl bei verschiedenem Hash — Abweichung in einem Zustand, der in der Entscheidungszählung nicht sichtbar ist (Muster wie pod-044). Decks: 2018_nature_s_vengeance, 2018_built_from_scratch, 2020_arcane_maelstrom, 2016_breed_lethality.

Einzelnachläufe der failed Pods (alte Linie):

| Seed | Pod | Sweep-Befund | Solo | Einordnung |
|---|---|---|---|---|
| 21 | pod-000 | BRIDGE_TIMEOUT | kein Solo-Ergebnis | Solo ok mit dem Hash des y-Laufs (`38febad386f7`) → Lastartefakt bestätigt. |
| 21 | pod-010 | BLOCK_DECLARATION_REJECTED | kein Solo-Ergebnis | Solo ebenfalls failed → echt. Zugeordnet: Pilot-Fehler Blockleiter, Fix Lab-PR #956 (auf v11 gemergt). |
| 21 | pod-034 | BRIDGE_CLOSED | kein Solo-Ergebnis | Solo ebenfalls failed (BRIDGE_CLOSED nach 1462 s Solo-Wall; Batch-Walls 278–356 s) → echt. Zugeordnet: Scute-Swarm-Trigger-Explosion, regelkonform, bekannte Familie, kein Fix geplant. |
| 22 | pod-013 | XMAGE_ACTION_EXECUTION_FAILED | kein Solo-Ergebnis | Solo ebenfalls failed → echt auf der alten Linie (Familie XMAGE_ACTION_EXECUTION_FAILED; der Stand enthält Bridge-Änderung #951 und vier Pilot-Fixes nicht — ob der Pod auf v11 durchläuft, zeigen die Seeds 24–30 nicht direkt, da andere Pod-Pläne gelten). |
| 23 | pod-015 | XMAGE_ACTION_EXECUTION_FAILED | kein Solo-Ergebnis | Solo ebenfalls failed → echt auf der alten Linie (gleiche Familie und Einschränkung wie pod-013). |

Rohdaten: `sweep_p21g21_x/y.json`, `sweep_p22g22_x/y.json`, `sweep_p23g23_x/y.json` in diesem Ordner. Damit ist die alte Linie abgeschlossen; es folgen keine weiteren Seeds auf diesem Stand (Nachtrag 1).

## Nächste Schritte

Schritt B (Zensus Seeds 21–30, je zwei Läufe mit `--games-per-jvm 6 --fast`), Schritt C (erste abweichende Entscheidung + Quelltext-Ursache je instabilem Pod, beginnend mit pod-022 und pod-044), Schritt D (statischer Audit). Zwischenberichte nach je drei Seeds; Endbericht ersetzt diese Datei.
