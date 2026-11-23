# A2: Defekte und Lücken in den Kartenblöcken (`card_block`) der Kartenbewertung H (Chulane)

> Phase-Bericht zum Vorab-Plan [Bewertung v3](rating_v3_plan_20261123.md) (Refs #1404). Ins Repo übernommen am 2026-11-23 aus dem Scratchpad; inhaltlich unverändert bis auf Pfade, die Bezeichnung der Läufe und die Angaben zur Modellfamilie (im Repo: unbelegt).

Stand 2026-11-22. Nur gelesen: keine Bewertungsläufe, nichts committet oder gepusht.

**Quelle.** Der vorgesehene Klon im Scratchpad ließ sich nicht anlegen, weil auf dem Datenträger nur etwa 590 MB frei waren; der Teilklon wurde wieder gelöscht. Stattdessen wurde ein vorhandener lokaler Worktree (HEAD `4ca953f65`) gelesen. Sein Verzeichnis `data/research/chulane_rubric_v2_20261118/` ist byte-gleich mit `origin/main` `f4d49ad61`, geprüft mit `git diff --stat HEAD origin/main`, das leer blieb. `src/commander_lab/studio/understanding_field.py` weicht auf main ab. Die Datei wurde per `git show origin/main:` gelesen: Sie zeigt nur Bewertungen im Studio an und spielt für `card_block` keine Rolle. Die Werte der Rückseiten stammen aus einem lokalen XMage-Quelltext-Checkout, die Loyalty aus `data/cards/xmage_card_facts.json` im Repo. Das Netz wurde nicht benutzt.

**Grundgesamtheit.** 922 verschiedene oracle_ids stehen in 972 Eingabezeilen: Welle 1 `rr_input_1..3` mit 300 Zeilen, Welle 2 `rr2_input_1..8` mit 672 Zeilen. Davon sind 50 Retest-Karten doppelt. Die Rater-Ausgaben: R2 mit 972 Bewertungen, F1 (`fullrun_ratings.jsonl`) mit 922 Bewertungen.

---

## 1. Kurzfassung

**Wer erzeugt die Blöcke?** Erzeugt werden sie in `data/research/chulane_rubric_v2_20261118/scripts/render_prompt.py::card_block(f, pat)`. Die Fakten stammen aus `data/facts.jsonl`, das `scripts/extract_facts.py` aus der Studio-View `card_fact` baut (Tabelle `scryfall_card`). Diese View hat **kein Feld für Loyalty, Defense oder P/T je Seite**.

**Lauf 1 (F1) und Lauf 2 (R2) sehen denselben Block (h).** Für alle 922 Karten ist der Block in F1, in R2-Welle 1 und in R2-Welle 2 byte-gleich:

- Neu gerendert gegen die Eingaben: 0 Abweichungen.
- Die 50 doppelten Karten: 0 Abweichungen.
- F1 benutzt `user_prompt` und damit denselben Block mit einer Kopfzeile davor: 0 Abweichungen.
- `render_prompt.py`, die Fakten, die Muster und der Guide haben nur einen Commit (`fbb456953`).

Unterschiede zwischen F1 und R2 liegen nur im Systemteil (Anker-Auslassung je Charge), in der Chargengröße (7 gegen etwa 89) und in den Anweisungen. Folge: **Jede Behebung im Generator braucht eine neue Fakten- bzw. Generator-Version und eine neue Welle.** `rating_second_run_full_inputs.build()` bricht nämlich ab, sobald ein Welle-1-Block nicht mehr byte-gleich rendert.

**Wo steht der Chulane-Text (e)?** Er steht wörtlich und korrekt in allen 8 `rr2_guide_*.md` und in `rr_guide_v2_1_rendered.md`, aber **in keinem der 922 Blöcke**.

- Die Rater hatten ihn also.
- Die Prüfer sahen nur Block und Claim und hatten ihn nicht (#1404, Kommentar 7085540409).
- In 461 von 922 Karten zitiert mindestens ein Rater-Claim Chulanes Text, der nicht im Block steht (R2: 231 Karten mit 249 Claims; F1: 353 Karten mit 369 Claims).

### Top-10 nach Häufigkeit × Auswirkung

Score = n × Auswirkung (ja = 1, unklar = 2, nein = 3, Zwischenwerte für gemischte Gruppen). Die Gruppen und Scores stammen aus `a2_summary.py`; sortiert ist nach Score, die Spalte „Prio“ ist ein eigenes Urteil. Zeilen mit „Rater-gemeldet“ beruhen auf Unsicherheitstexten, nicht auf einer Prüfung des Blocks.

| # | Defekt | n/922 | fair ohne? | Score | Behebung (kurz) | Prio |
|---|---|---|---|---|---|---|
| 1 | **Chulane-Text nicht im Block.** Prüfer-Seite: strukturell 922; Claims mit Chulane-Zitat in 461 Karten. Für Rater kein Defekt (der Text steht im Guide). | 461 | Rater ja, Prüfer unklar | 922 | Zeile `Commander (Chulane) Oracle: …` in `card_block`, oder Prüfer bekommen den Guide-Kopf | hoch (billig) |
| 2 | **Deck- und Manabasis-Kontext fehlt** (Zahl der Kreaturen und Typen, Artefakte, Instants/Sorceries, Basics, Land-Typen, {C}-Quellen). Rater-gemeldet; Lücke von Guide und Kontext, kein Blockfehler. Deck 376, Manabasis 49. | 391 | unklar | 782 | Kontextblock in den Guide, Zahlen aus der Referenzliste (`facts_manifest.deck_basis`) | hoch |
| 3 | **Rulings abgeschnitten**: höchstens 4 gezeigt (118 Karten haben mehr), Text bei 240 Zeichen gekappt (239 Karten). Bei gleichem Datum ist die Auswahl willkürlich (95). | 268 | meist ja; bei neuen Mechaniken nein | 402 | `RULINGS_SHOWN`/`RULING_CHARS` lockern, nach Relevanz sortieren | hoch |
| 4 | **Pattern-Hits irreführend**: etb_own auf Nicht-Kreaturen (40), Beleg ist ein Rollenlabel statt einer Textzeile (104). Rater urteilten in 89 Karten „irrelevant“ und in 19 „wrong“. | 137 | ja | 137 | `extract_patterns.py`: etb_own nur für Kreaturen, Beleg als Textzeile | mittel |
| 5 | **Allgemeine Regeln fehlen**: Aura oder Equipment bei Bounce, Token-Kopie löst ETB aus, Zählmarken gehen beim Bounce verloren, cloak ist kein Wirken usw. Rater-gemeldet. | 79 | unklar/ja | 118 | Kurzglossar der Grundregeln im Guide | mittel |
| 6 | **Peer-Rollen auf 3 gekürzt** (dazu 89 Nichtländer ohne Rolle, daher ohne Rollen-Peer) | 115 | ja | 115 | Alle Rollen zeigen, oder die Hauptrolle plus die zwei größten Gruppen | niedrig |
| 7 | **Castability falsch oder unvollständig**: Hybrid (17: Kostensymbole doppelt, zugleich „no coloured symbol“ mit P = 1,0), X bei 0 nicht gesagt (14), Verbilligung ignoriert (23: convoke, affinity, improvise, delve, evoke, „costs {N} less“) | 53 | unklar/ja | 80 | `fmt_pips`, Castability-Zusätze, Hybrid in `extract_facts` rechnen | mittel |
| 8 | **Doppelkarten, Spezialtypen, Verweise**: P/T der Rückseite fehlt (4), Planeswalker-Loyalty fehlt (4), Spacecraft-P/T ohne „erst ab 8+“ (1), Keywords bzw. Mana der Rückseite ohne Seitenangabe (3 + 1), „card named X“ ohne Text (3), Token ohne Reminder (5) | 19 | nein/unklar | 48 | Store-Import um `card_faces[*].power/toughness/loyalty/defense` erweitern, `split_faces`, Verweistext beilegen | hoch für 4 PW + 4 DFC + 3 named |
| 9 | **Neue Mechaniken unerklärt**: prepare/prepared (9 Karten; Definitions-Ruling bei 0 von 8 vollständig sichtbar), goad und cloak (1), Adventure (1), Ki/Flip (1), Loyalty-Fähigkeiten ohne Startloyalty (4). Rater meldeten 27 Karten wegen „Mechanik unbekannt“, darunter alle 9 Empower-Karten trotz Reminder. | 16 | nein | 40 | Glossarzeile je Mechanik ohne ausreichenden Reminder in `card_block` | hoch |
| 10 | **Land-Fakten falsch**: „fetches a land: no“ bei 6 Fetch-Ländern; „makes no of the deck's colours“ bei 15 Fetch-Ländern; „enters: untapped“, obwohl das geholte Land getappt kommt (10) | 15 | unklar (R/D) | 30 | Regex in `extract_facts.py`, Zeile 378; holbare Farben | hoch (billig) |

Unter der Top-10: Pattern-Hit von einem Rater als „wrong“ beurteilt (19, Score 19); Körper-Benchmark ignoriert ETB-Zählmarken oder fehlt (17 + 2, Score 19).

### Gesamtzahlen

| Kennzahl | n/922 |
|---|---|
| Karten mit mindestens einem automatisch gefundenen Blockdefekt (alle Gruppen außer Chulane, einschließlich weicher Punkte wie Pattern-Rauschen und auf 3 gekürzter Peer-Rollen) | **464** |
| davon ohne die weichen Punkte (Rulings, Castability, Land, Mechanik, Doppelkarten, Verweise) | 323 |
| **Risiko „unfair ohne Information“** (Auswirkung unklar oder nein, automatisch gefunden: Mechanik einschließlich prepare und Adventure, Hybrid-Castability, Land-Fakten, Doppelkarten, Spezialtypen, Verweise) | **60** |
| Rater meldeten low/medium mit blockbedingter Lücke (Mechanik, Regel, Token oder Verweis, Combo, Benchmark, Seite, gekappte Rulings; ohne Deck und Manabasis) | 139 |
| Vereinigung beider Zeilen | **170** |
| Rater meldeten low/medium wegen irgendeiner fehlenden Information (einschließlich Deck und Manabasis; Datei `A2_low_confidence_cards.jsonl`) | 448 |
| davon nur Kontext (Deck und Manabasis) | 309 |
| Irgendein Problem (Block oder Kontext), ohne Chulane | **636** |
| Chulane-Text fehlt im Block (strukturell, nur Prüfer) | 922 |

---

## 2. Tabellen je Prüffrage

### (a) Doppelkarten und Layouts: 12 Karten mit mehreren Seiten

Layouts: normal 910, prepare 6, transform 4, flip 1, adventure 1. Split, MDFC, Saga, Class, Leveler und Battle kommen nicht vor.

| Defekt | n | Beispiele | fair ohne? | Behebung | Prio |
|---|---|---|---|---|---|
| P/T der Rückseite fehlt. Die Zeile heißt „Power/toughness (front face)“, und die Rückseite hat keine P/T-Angabe. Der Guide verspricht dagegen „every face's … power and toughness“. | 4 | Faithful Squire // Kaiso (3/4), Brigid // Brigid, Doun's Mind (3/2), Thraben Sentry // Thraben Militia (5/4), Grizzled Outcasts // Krallenhorde Wantons (7/7) | nein: Rater schrieben „back face P/T not shown“ (Thraben Sentry H 5/10, Grizzled H 5/15) | Store `scryfall_card` um `card_faces` (power, toughness, loyalty, defense, je Seite) erweitern; `extract_facts.split_faces` übernimmt sie; `card_block` gibt sie in der „Face i“-Zeile aus | hoch |
| Keywords aus der Rückseite ohne Seitenangabe | 3 | Faithful Squire („Flying“ gehört Kaiso), Thraben Sentry („Trample“), Soul Seizer („Enchant“) | ja (Text vorhanden), aber irreführend | Keywords je Seite ausgeben | niedrig |
| „Produces mana“ stammt von der Rückseite | 1 | Brigid („G“; die Rückseite erzeugt G oder W) | ja | `produced_mana` je Seite | niedrig |
| Adventure-Regel nicht erklärt (nur „Layout: adventure“, kein Reminder) | 1 | Brazen Borrower | unklar (Rater leitete sie aus dem Layout ab; zählt zu Top 9 und zum Risiko-Satz) | Glossarzeile für Adventure | mittel |
| Kosten und Typen der Rückseiten | 0 | Kosten und Typzeile stehen bei allen 12 | – | – | – |

### (b) Mechaniken und Schlüsselwörter

Ausgeschlossen waren Evergreen- und lange bekannte Keywords; die Liste steht in `a2_inventory.py::EVERGREEN`. Ability Words mit „—“ erklären sich selbst: Vivid 6, Parley 2, Alliance, Opus, Magecraft, Coven, Lieutenant, Formidable, Nosh/Share, Lizard Formula.

| Mechanik | n | Reminder im Text? | im Guide? | Rater-Signal |
|---|---|---|---|---|
| Prepared/prepare (einschließlich Biblioplex Tomekeeper, Skycoach Waypoint, Infinite Coursework) | 9 Karten mit dem Keyword, 8 mit „prepare“ im Text | nur ein Kurz-Reminder („you may cast a copy of its spell“) bei 4; keiner bei Prudent Fateseer, Dirgur Focusmage, Infinite Coursework | nur „prepare cards: judge the face cast from hand“ | 9 von 9 Karten mit Unsicherheit, 3 low (R2: Prudent Fateseer, Biblioplex Tomekeeper, Dirgur Focusmage) |
| Prepare-Definitions-Ruling („…creates a copy … in exile … may cast that copy …“, 448 Zeichen) | 8 | – | – | bei **0 von 8** vollständig sichtbar: 2 gekappt bei 240 Zeichen, 4 hinter der Grenze von 4 Rulings, 2 nicht in den Daten |
| Empower Jace | 9 | ja | nein | bei 9 von 9 Karten nennt ein Rater die Mechanik neu oder unbekannt (Campus Crier low); Jace-Token-Regeln (Loyalty-Aktivierung) unklar |
| Station (Spacecraft) | 1 | ja | nein | low: Das Stufen-Layout (welche Zeile zu 8+ gehört) geht in der Textwiedergabe verloren |
| Goad, Cloak | 1 (Ransom Note) | nein | nein | Rater nahmen goad an bzw. ließen es weg |
| Loyalty-Fähigkeiten (+N/−N) ohne Startloyalty | 4 | – | – | alle 4 Planeswalker: „starting loyalty not shown“ |
| Ki-Zähler/Flip | 1 | nein | nein | – |
| Weitere seltene Keywords mit Reminder (in Ordnung) | Changeling 8, Living weapon 5, Multikicker 5, Reinforce 4, Heal 3, Behold 3, Blight 3, Improvise, Unearth, Battle Cry, Retrace, Cleave, Bargain, Soulbond, Demonstrate, Devoid, Gravestorm, Detain, Ascend, Web-slinging, Choose a background | ja | – | vereinzelt |

Behebung: In `render_prompt.card_block` eine Zeile „Mechanics (rules summary): …“ für jedes Keyword ohne Reminder und für gescannte Begriffe (prepared, goad, cloak, adventure, station-Stufen, emblem, loyalty). Die Texte kommen aus einem kuratierten Glossar in Kurzform nach CR 702.x bzw. 701.x, als neue Datei `data/mechanics_glossary.json`. Der Guide-Abschnitt „New or unfamiliar cards“ verweist darauf.

### (c) Verweise auf andere Karten, Token oder Embleme

| Defekt | n | Beispiele | fair ohne? | Behebung |
|---|---|---|---|---|
| „card named X“ ohne Text von X | 3 | Angel's Herald (Empyrial Archangel), Arachnus Spinner (Arachnus Web), Scepter of Empires (Crown/Throne of Empires) | nein: Rater: „named card's text is not in my block“ | `extract_facts`: Oracle-Text der genannten Karte als „Referenced card“-Zeile (aus `scryfall_card` nach Name) |
| Vordefinierte Token ohne Reminder (Clue, Food, Treasure) | 5 | Killer Service, An Offer You Can't Refuse, Graf Mole, Sophia, Dogged Detective, Academy Manufactor | meist ja; bei Academy Manufactor wurde low gemeldet | Glossarzeile für Token |
| Benannte Token, inline definiert (in Ordnung) | 4 | Hexhaven Battalion (Cadet), Peer Review (Cadet), Koma, Witness Protection | – | – |
| Embleme inline definiert (in Ordnung) | 2 | Tezzeret, Elspeth | – | – |
| Kopie-Effekte (ETB der Kopie nicht in Rulings) | 9 | Replication Technique, Rite of Replication, Omni-Changeling, Clever Impersonator, Mechanized Production | unklar (Rater: „inferred, not in rulings“) | Grundregel ins Glossar |

### (d) Spezialtypen

| Defekt | n | Beispiele | fair ohne? | Behebung |
|---|---|---|---|---|
| Planeswalker ohne Loyalty | 4 von 4 | Tezzeret, Betrayer of Flesh (4), Gideon Jura (6), Narset, Parter of Veils (5), Elspeth, Knight-Errant (4) | nein. H streut F1 gegen R2 stark: Elspeth 60/30, Tezzeret 25/5 | `scryfall_card.loyalty` importieren, Zeile „Loyalty: N“ |
| Spacecraft: P/T 4/4 ohne „Kreatur erst ab 8+“; Stufenstruktur verloren | 1 | Exploration Broodship | unklar (low) | Stufenzeilen „STATION 3+ / 8+“ erhalten, P/T mit Bedingung |
| Fahrzeuge ohne Crew | 0 von 3 | – | – | – |
| Battle/Defense, Saga, Leveler, Class | 0 | – | – | – |

### (e) Chulane-Interaktion

| Befund | n | Bemerkung |
|---|---|---|
| Chulane-Text in einem Block | 0 von 922 | steht in allen 9 Guide-Dateien (Zeilen 15–19, wörtlich korrekt) |
| Karten, deren Claims Chulane zitieren (Zitat nicht im Block) | 461 (R2 231, F1 353) | Bei strenger Lesart der Prüfer („nur aus dem Block“) wären diese Claims „unscharf“. Prüfer 1 betraf das bei 17 von 50 Claims. |
| Kartentext nennt „commander“ | 9 | Command Tower, Arcane Signet, Path of Ancestry u. a.: ohne Commander-Daten (Farben, Typen Human/Druid) nur mit Guide bewertbar |

Behebung: In `card_block` eine Zeile `Commander: Chulane, Teller of Tales {2}{G}{W}{U} 2/4 — Vigilance. Whenever you cast a creature spell, draw a card, then you may put a land card from your hand onto the battlefield. {3}, {T}: Return target creature you control to its owner's hand.` ergänzen, etwa 60 Token je Karte. Alternativ bekommen die Prüfer den Guide-Kopf mit.

### (f) Castability, Peer-Benchmarks, Pattern-Hits

| Defekt | n | Beispiele | fair ohne? | Behebung |
|---|---|---|---|---|
| Hybrid: „Cost symbols W x3, G x3 …, 3 hybrid“ (doppelt gezählt) und zugleich „(cost has no coloured symbol)“ mit P(colours) = 1,0 | 17 | Wilt-Leaf Liege {1}{G/W}{G/W}{G/W}, Judge's Familiar, Prudent Fateseer, Emergency Phytomedic, Tam, Mindful First-Year | unklar (Widerspruch im Block) | `render_prompt.fmt_pips`: Hybrid getrennt zählen („G/W x3“); Castability: Hybrid als „eine der Farben“ rechnen oder `hybrid_or_phyrexian_left_out` ausgeben |
| X-Kosten bei X = 0 gerechnet, nicht gesagt (`x_cost` wird nicht gerendert) | 14 | Pest Infestation, Primordial Hydra, Tyvar's Stand, Untamed Might, Primal Might (Blue Sun's Zenith: Rater-Hinweis) | ja/unklar | Zusatz „(X counted as 0)“ |
| Alternativkosten oder Selbstverbilligung ignoriert (convoke, affinity, improvise, delve, evoke, „costs {N} less“; Cascade-Reminder und Inspiring Statuary von Hand ausgeschlossen) | 23 | Treasure Cruise, Dig Through Time, Gate Colossus, Conclave Phalanx, Merrow Skyswimmer | ja | Zusatz „(cost reduction in text not modelled)“ |
| Castability fehlt bei Spells | 0 | – | – | – |
| Peer-Arithmetik (cheaper + equal + dearer = n; p25 ≤ median ≤ p75) | 0 Fehler | – | – | – |
| Peer-Rollen auf 3 gekürzt | 115 | Veil of Summer (6 Rollen), Solemn Simulacrum (5) | ja | – (niedrig) |
| Keine Rolle (Nichtland), daher kein Rollen-Peer | 89 | Grizzled Outcasts, Chrome Steed, Vanillas | ja | – |
| Körper-Benchmark nach gedrucktem P/T, ETB-Zählmarken ignoriert | 17 | Burdened Stoneback, Primordial Hydra 0/0, Hydroid Krasis, Enclave Elite, Protean Hydra | ja (Text) | Zusatz „printed P/T; enters with counters“ |
| Körper-Benchmark fehlt bei Kreatur | 2 | Darksteel Colossus (keine Peers), Psychosis Crawler (*/*) | ja | – |
| etb_own-Hit auf Nicht-Kreatur (Land, Aura, Artefakt: Chulane-Bounce kann es nicht wiederholen) | 40 | Selesnya Sanctuary, Simic Growth Chamber, Stalactite Dagger, Divine Favor, Stasis Snare | ja | `extract_patterns.py`: etb_own auf Kreaturen beschränken oder `etb_own_noncreature` einführen |
| Pattern-Beleg ist ein Rollenlabel („roles by text: …“), kein Kartentext (noncreature_draw_or_ramp) | 104 | Veil of Summer, Talisman of Progress, Cultivate, Consider | ja | Beleg als Textzeile |
| Von einem Rater als „irrelevant“ bzw. „wrong“ beurteilt (R2 + F1) | 89 / 19 | Präzision je Regel siehe `A2_metrics.json → pattern_verdicts`, z. B. irrelevant: etb_other_permanent in R2 8 von 8, self_cost_reduction in R2 11 von 25, etb_own in R2 + F1 72 von 316 (dazu 5 wrong) | ja | wie oben |
| Land-Fakten falsch (siehe Top 10) | 15 | Cabaretti Courtyard, Krosan Verge, Jund Panorama, Mountain Valley, Riveteers Overlook, Rocky Tar Pit (fetches: no); Evolving Wilds, Fabled Passage u. a. („makes no“) | unklar. Beide Rater bei Cabaretti und Krosan: „fact contradicts text, I follow the text“ | `extract_facts.py` Zeile 378: Regex `search your library for[^.\n]*land` erkennt „basic Forest or Plains card“ nicht. Erweitern auf Land-Typen; `wug_colours_produced` für Fetch-Länder um holbare Farben ergänzen; „enters“ des geholten Landes |

**Handstichprobe**: 40 Karten, Seed 20261122, Datei `A2_hand_sample.txt`, Urteile in `data/research/chulane_rubric_v3_20261123/phaseA_scripts/A2/a2_hand_sample_verdicts.json`.

- Castability fehlt: 0. Peer-Zahlen unplausibel oder falsch: 0.
- 2 harte Fehler: Grizzled Outcasts (Rückseite 7/7 fehlt; das einzige Ruling ist nur ein Verweis auf einen Artikel) und Cabaretti Courtyard (Land-Fakten falsch, land_onto_battlefield_effect nicht getroffen).
- Weich: 4 etb_own auf Nicht-Kreaturen, 7 Belege als Rollenlabel, 1 zweifelhafte Rolle (Cryotheory Adept: combat_trick).
- 30 Karten ohne Befund.

### (g) Rulings

518 Karten haben Rulings.

| Defekt | n | Beispiele | fair ohne? | Behebung |
|---|---|---|---|---|
| Mehr als 4 Rulings, Rest unsichtbar | 118 | Autumn's Veil (4 von 7), Gideon Jura (4 von 10), prepare-Karten (4 von 15–18) | meist ja; bei prepare nein | `card_block`: Auswahl nach Relevanz statt nach ältestem Datum (Rulings, die eine Mechanik der Karte nennen, zuerst), bis 6 oder nach Zeichenbudget |
| Ruling-Text bei 240 Zeichen gekappt („…“) | 239 | Veil of Summer, Escape Tunnel, Glacial Fortress, Studious First-Year (Definition) | unklar (15 Karten mit Rater-Hinweis „rulings cut off/truncated“) | `RULING_CHARS` auf etwa 600 anheben oder ganz streichen |
| Auswahl bei gleichem Datum willkürlich (stabile Sortierung nach Quellreihenfolge) | 95 | Autumn's Veil, Nettlecyst, Detective of the Month | – | Tie-Break nach Relevanz |
| Inhaltsleeres Ruling (nur ein Artikelverweis) | 1 | Grizzled Outcasts | – | filtern |
| Veraltete Formulierung („comes into play“) in gezeigten Rulings | 0 | – | – | – |

### (h) F1 gegen R2

- Feld-Diff des Blocks über alle 922 Karten: **0 Unterschiede**, ebenso bei den 50 Karten, die in beiden Wellen von R2 stehen. Die Eingaben von F1 sind nicht als Datei eingecheckt. Sie sind über `make_batches.py`, `rp.user_prompt` und denselben `card_block` reproduzierbar, und das Neu-Rendern gegen die heutigen Fakten ergab 0 Abweichungen.
- Anders waren nur Guide und Systemteil (Anker-Auslassung je Charge; `instructions_wave1_vs_wave2.diff`) und die Chargengröße.
- Zuversicht für dieselbe Karte, F1 gegen R2 (erste R2-Bewertung):

  | F1 \ R2 | high | medium | low |
  |---|---|---|---|
  | high | 362 | 61 | – |
  | medium | 195 | 297 | 6 |
  | low | – | 1 | – |

  F1 war insgesamt unsicherer (499 von 922 low/medium, R2 387 von 972).
- Blockbedingte Lücken (ohne Deck und Manabasis) nannten F1 und R2 übereinstimmend bei 33 Karten, nur F1 bei 55, nur R2 bei 51. Die Meldungen hängen also stark vom einzelnen Rater ab. Die harten Defekte (prepare, Loyalty, Rückseiten-P/T, Land-Fakten, named card) melden beide Läufe aber konsistent.

---

## 3. Rater-Meldungen (Zuversicht low/medium)

Datei: `A2_low_confidence_cards.jsonl` (Ausgabe von `a2_uncertainty.py`, nicht im Repo), eine Zeile je oracle_id mit allen Bewertungen (Quelle R2w1:k, R2w2:k oder F1), Zuversicht, Unsicherheitstext, Tags sowie den Feldern `block_caused`, `only_context` und `any_low`.

- 560 Karten haben mindestens eine low/medium-Bewertung; 448 davon wegen fehlender Information.
- Davon blockbedingt: 139. Nur Kontext (Deck-Liste und/oder Manabasis): 309.
- 111 Texte bekamen kein Tag, weil die Ursache Spiel, Tisch oder Pod war oder nicht erkannt wurde.

| Tag (Karten) | n | Beispiele |
|---|---|---|
| deck_list_not_visible (Kontext) | 376 | Abolish, Tributary Vaulter, Fierce Empath, Trinket Mage |
| rules_corner_not_in_rulings | 79 | Curiosity, Guardian Zendikon, Aerial Extortionist, Angelic Destiny |
| mana_base_not_visible (Kontext) | 49 | Arbor Elf (Forest-Typen), Canopy Vista (Basics), World Breaker ({C}) |
| mechanic_unexplained | 27 | prepare-Karten, Arcane Amphisbaena, Campus Crier, Exploration Broodship |
| benchmark_or_castability_mismatch | 21 | Burdened Stoneback, Blue Sun's Zenith, Angel of Salvation |
| rulings_cut_off | 15 | Dirgur Focusmage, Brazen Borrower, Icy Manipulator |
| token_or_reference_undefined | 9 | Angel's Herald, Academy Manufactor, Elspeth |
| other_face_or_layout | 7 | Brazen Borrower, Grizzled Outcasts, Brigid |
| combo_partners_not_shown | 6 | Shrieking Drake, Lonis, Tireless Provisioner. Der Combo-Hinweis (7 Karten) nennt nur die Zahl der Linien, keine Partner. |

Alle 7 low-Bewertungen, von Hand gelesen:

- Academy Manufactor: Combo-Partner und Token-Erzeuger unbekannt.
- Campus Crier: Empower Jace.
- Prudent Fateseer: prepare.
- Biblioplex Tomekeeper: prepare.
- Dirgur Focusmage: prepare, Ruling gekappt.
- Exploration Broodship: Station-Layout.
- Treasure Mage (F1): Deck-Liste.

6 von 7 sind blockbedingt.

Präzision der Regex-Tags: Hand-Check von 30 Texten in der ersten Fassung, 36 von 41 Tags richtig, also etwa 88 %. Danach wurde nachgeschärft: „flip“, „do not know how many“ und „rules point“; die Datei `A2_uncertainty_precision_sample.txt` zeigt die aktuelle Fassung. Die Zahlen sind daher ±10 % zu lesen.

---

## 4. Behebung im Generator

Konkret je Datei. Jede Änderung braucht `facts-2` bzw. einen neuen Generator und eine neue Welle, weil der Drift-Check in `rating_second_run_full_inputs.build()` Byte-Gleichheit verlangt.

1. **Store und Import** (`scryfall_card`, Importer `scripts/import_scryfall_oracle_tags.py` bzw. der Scryfall-Oracle-Import des Studios): `loyalty`, `defense` und `card_faces[*].{power,toughness,loyalty,defense,oracle_text,mana_cost,type_line}` speichern; die View `card_fact` gibt sie weiter. Das behebt (a) Rückseiten-P/T und (d) Loyalty an der Quelle. Übergangsweise kann `data/cards/xmage_card_facts.json` die Loyalty liefern, Rückseiten aber nicht.
2. **`scripts/extract_facts.py`**:
   - `split_faces`: P/T und Loyalty je Seite übernehmen.
   - `land.fetches_land` (Zeile 378): Regex auf Land-Typen erweitern.
   - `wug_colours_produced`: holbare Farben bei Fetch-Ländern ergänzen.
   - `enters_tapped` für das geholte Land.
   - Keywords und `produced_mana` je Seite.
   - Für „card named X“ den Oracle-Text von X als `referenced_cards` beilegen.
3. **`scripts/render_prompt.py::card_block`**:
   - Zeile `Commander (Chulane) Oracle: …`.
   - Zeile `Loyalty: N` bzw. P/T je Seite in der „Face i“-Zeile.
   - „Mechanics (rules summary)“ aus einem Glossar für Keywords ohne Reminder und für gescannte Begriffe (prepared, goad, cloak, adventure, station, Token).
   - `fmt_pips`: Hybrid getrennt zählen.
   - Castability-Zusätze `x_cost`, `hybrid_or_phyrexian_left_out` und „cost reduction not modelled“.
   - Rulings: `RULING_CHARS` mindestens 600, Auswahl nach Relevanz mit stabilem Tie-Break, `RULINGS_SHOWN` nach Zeichenbudget; inhaltsleere Verweise filtern.
   - Körper-Benchmark: Hinweis auf ETB-Zählmarken.
   - Station-Stufen als eigene Zeilen.
4. **`scripts/extract_patterns.py`**: etb_own nur für Kreaturen (sonst `etb_own_noncreature`); noncreature_draw_or_ramp mit Textzeile statt Rollenlabel.
5. **`GUIDE_v2.md`**: Deck-Kontextblock mit Zahlen aus der Referenzliste `deck_basis` (`chulane-current@41f393530bb16ee9`), also Kreaturen, Typen, Artefakte, Instants/Sorceries, Basics und Land-Typen. Dazu ein Kurzglossar der Grundregeln: Aura/Equipment bei Bounce, Zählmarken weg, Token-Kopie mit ETB, „put onto the battlefield“ ist kein Wirken, cloak/manifest wird nicht gewirkt.

---

## 5. Reproduktion

```
PYTHONPATH=<repo>/src python3 data/research/chulane_rubric_v3_20261123/phaseA_scripts/A2/a2_inventory.py --repo <repo> --mage <xmage-checkout> --out <ordner>
python3 data/research/chulane_rubric_v3_20261123/phaseA_scripts/A2/a2_uncertainty.py --repo <repo> --out <ordner>
python3 data/research/chulane_rubric_v3_20261123/phaseA_scripts/A2/a2_summary.py --out <ordner>
```

`<repo>` = ein Checkout von `main` @ `f4d49ad6` (Original: lokaler Worktree, siehe Quelle; am 2026-11-23 aus dem Repo-Ordner auf einem frischen Klon von `f4d49ad6` erneut gerechnet, alle 6 Ausgaben byte-gleich). Die Skripte schreiben `A2_metrics.json` (alle Prüfungen mit ID-Listen und Pattern-Urteilen), `A2_hand_sample.txt`, `A2_uncertainty_stats.json`, `A2_low_confidence_cards.jsonl`, `A2_uncertainty_precision_sample.txt` und `A2_summary.json`. Zufall gibt es nur mit festen Seeds (20261122 und 7).

**Grenzen.**

- Mechanik-, Token- und Verbilligungs-Erkennung arbeiten mit Regex und sind konservativ; die Evergreen-Liste ist ein Urteil.
- Rückseiten-P/T stammen aus dem XMage-Quelltext, nicht aus Scryfall.
- Die Auswirkung „fair ohne?“ ist eine Einschätzung.
- Kategorien aus den Rater-Meldungen messen, was Rater angaben, nicht, was ihnen objektiv fehlte.
