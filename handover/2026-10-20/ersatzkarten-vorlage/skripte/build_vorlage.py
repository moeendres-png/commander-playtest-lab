#!/usr/bin/env python3
"""Generate VORLAGE.md (M2 decision paper) from the measured artifacts."""
import json
from pathlib import Path

BASE = Path("/home/hatch/workspace/tmp/m2")
slots = json.loads((BASE / "slots.json").read_text())["slots"]
eck = json.loads((BASE / "eckdaten.json").read_text())["cards"]
kand = json.loads((BASE / "kandidaten.json").read_text())
draft_slots = kand["basis"]["slots"]
manifest = kand["sets"]

L = []
L.append("# Entscheidungsvorlage: Ersatzkarten für die 13 Precon-Decks mit fehlenden Karten")
L.append("")
L.append("Stand: 2026-10-20 · Lab `ed2fbae26` (main, Merge #926) · Engine-Pin `043579bb` (XMage 1.4.62)")
L.append("Messung: Muse (Mess-Lane). Diese Vorlage trifft keine Entscheidung und ändert keine Deckdatei.")
L.append("")
L.append("## Zusammenfassung für Hans")
L.append("")
L.append("Am Pin fehlen der Engine **31 Kartennamen in 13 Decks (33 Einträge)**; **182 von 195** Decks sind "
         "importierbar (eigene Nachmessung über den produktiven Importpfad, Deck für Deck identisch zur "
         "Doku-Tabelle in `docs/PRECON_VALIDATION.md`). In **4 Decks fehlt der Commander selbst** "
         "(2024_death_toll, 2024_family_matters, 2024_miracle_worker, 2026_multiverse_reforged) — dort gibt "
         "es nichts zu ersetzen, ohne ein anderes Deck zu bauen. Für die **29 Hauptdeck-Slots in 10 Decks** "
         "liegen je 3 geprüfte Ersatzkandidaten vor (Engine-Existenz per Import bewiesen, Commander-legal, "
         "in der Farbidentität, Singleton, Typ + Manawert nah am Original). Alle 30 Ersatz-Sätze (3 je Deck) "
         "importieren mit Status OK.")
L.append("")
L.append("### Optionenvergleich (nur Fakten)")
L.append("")
L.append("| Option | Ergebnis in Zahlen | Was sie belegt | Was sie nicht belegt | Aufwand (grob, ohne Zusage) |")
L.append("|---|---|---|---|---|")
L.append("| **A) 13 Decks bleiben draußen** | Pool bleibt bei **182 Decks** (Ist-Zustand) | Nichts Neues; die 182 sind spielbar gemessen (M1-Sweeps) | Keine Aussage zu den 13 Decks | 0 h |")
L.append("| **B) Hauptdeck-Slots in Deckkopien ersetzen** | **9 weitere Decks werden vollständig** (Pool 191); 29 Slots ersetzt; Deckgleichheit je Deck 92–99 % (Tabelle unten). 2026_multiverse_reforged bleibt ohne Commander-Entscheid unvollständig | Import aller 30 Sätze OK (gemessen). Die Kopien sind spielbar im selben Sinn wie die 182 | Die Kopien sind **nicht mehr die gedruckten Precons**; Ersatzkarten sind nur importbewiesen, ihre Funktion im Spiel ist nicht eigens geprüft | Sätze liegen fertig vor; Übernahme in Kopien + Nachimport ≈ 1–2 h Datenarbeit. Eine dauerhafte Repo-Änderung wäre ein eigener PR mit eigener Entscheidung |")
L.append("| **C) Ersatzkarten im Fork (SYNTHETIC-Stubs)** | **Alle 13 Decks** würden importierbar (31 Stubs liegen aus der alten Linie vor) | Nur der Import: Die Stubs beweisen Existenz, **keine Kartenfunktion** — Fähigkeiten sind teilweise weggelassen (je Karte unten vermerkt) | Keine Regelevidenz für die 31 Karten. Risiko-Präzedenz: Die 6 vereinfachten Turbulent-Lands der alten Linie **veränderten die Spielsemantik** (Bisektion 2026-10-20) | Stub-Port ≈ 4–8 h, dazu Fork-Push (nur mit deinem Go) und Requalifizierung durch die Claude-Lane (PB-03 → Seal) — der eigentliche Kostenblock, historisch Tage |")
L.append("")
L.append("**Eckdaten-Zuverlässigkeit der Stubs (für Option C):** Alle 31 Stubs treffen Manakosten, Haupttypen, "
         "P/T und Karten-pro-Datei exakt (31× „ja\", gegen Scryfall geprüft). Ihre Schwäche ist nicht die "
         "Eckdaten, sondern die weggelassenen Fähigkeiten.")
L.append("")
L.append("### Commander-Decks (4) — kein Slot-Austausch")
L.append("")
L.append("Fehlt der Commander, ist das Deck ein anderes Deck. Optionen: **Deck weglassen** oder **du wählst "
         "einen Commander** (dann ist es ein neues Deck, kein Precon mehr). Betroffen: 2024_death_toll "
         "(Winter, Cynical Opportunist), 2024_family_matters (Zinnia, Valley's Voice), 2024_miracle_worker "
         "(Aminatou, Veil Piercer), 2026_multiverse_reforged (Jace, Multiverse Architect; dort zusätzlich "
         "6 Hauptdeck-Slots, deren Ersatz oben bewiesen ist — mit Gerüst-Commander Breya, nur als "
         "Importgerüst, nicht als Vorschlag).")
L.append("")
L.append("### Korrekturen zu früheren Angaben")
L.append("")
L.append("- **Dack Fayden, Helping Hand** ist **eine** Karte und **ein** Stub (FRC, {4}{W}{W}, 4/6) — die "
         "Formulierung „eine Datei für zwei Karten\" trifft nicht zu; Stub und Karte decken sich.")
L.append("- **Aminatou, Veil Piercer:** Der Stub ist korrekt — die echte Karte ist laut Scryfall (Set DSC, "
         "Abruf 2026-10-20) eine **Legendary Creature — Human Wizard** ({1}{W}{U}{B}, 2/4), kein "
         "Planeswalker. Weggelassen ist im Stub nur die Miracle-Gewährung. (Meine frühere gegenteilige "
         "Angabe war falsch.)")
L.append("- **Repo-Kartenwissen:** Entgegen der Stichprobe im Auftrag kommen **alle 31** Namen in "
         "`data/cards/*.json` nicht vor (0 von 31, strukturiert + Rohtext geprüft). Eckdaten stammen daher "
         "nur aus den Stubs (SYNTHETIC) und Scryfall (EXTERNAL_DATA).")
L.append("")
L.append("### Meine Einschätzung (als solche markiert, ≤5 Zeilen)")
L.append("")
L.append("Option B ist die einzige, die den Pool ehrlich vergrößert: 191 echte, importbewiesene Decks, "
         "klar als Kopien gekennzeichnet. Option C kauft 4 weitere Decks mit unbeweisbarer Kartenfunktion "
         "und dem Turbulent-Risiko — den Preis (Fork + Requalifizierung) halte ich dafür für zu hoch. "
         "Für die 4 Commander-Decks: draußen lassen, bis du einen Commander wählst oder die Karten regulär "
         "in die Engine kommen.")
L.append("")
L.append("---")
L.append("")
L.append("## Slot-Tabelle (33 Einträge)")
L.append("")
L.append("| Deck | Karte | Zone | Anzahl | Anteil am Deck |")
L.append("|---|---|---|---|---|")
for s in slots:
    L.append(f"| {s['deck']} | {s['card']} | {s['zone']} | {s['quantity']} | {s['share_of_deck']:.0%} |")
L.append("")
L.append("Quelle: `slots.json` — Messung `measure_precon_imports.py --enumerate-missing` (LOCAL_OBSERVED), "
         "Mengen aus den Deckdateien.")
L.append("")
L.append("## Eckdaten je Karte (31)")
L.append("")
L.append("Jeder Wert mit Quelle: Scryfall = EXTERNAL_DATA (Abruf 2026-10-20, URL je Karte in "
         "`eckdaten.json`); Stub = SYNTHETIC (Fork-Patches, `handover/2026-10-19/fork-patches/`). "
         "Repo-Kartenwissen: für alle 31 = nicht vorhanden.")
L.append("")
for c in sorted(eck, key=lambda x: x["name"]):
    sf, st = c["scryfall"], c["stub"]
    pt = f"{sf['power']}/{sf['toughness']}" if sf.get("power") is not None else (
        f"Loyalty {sf['loyalty']}" if sf.get("loyalty") is not None else "—")
    kw = ", ".join(sf.get("keywords") or []) or "—"
    abilities = "; ".join(a.replace("\n", " ")[:110] for a in (st.get("ability_lines") or [])) or "keine (nur Basiswerte)"
    L.append(f"### {c['name']}")
    L.append(f"- **Manakosten:** {sf['mana_cost']} (Scryfall) · Stub: {st['mana_cost']}")
    L.append(f"- **Typ:** {sf['type_line']} (Scryfall) · Stub-Typen: {', '.join(st['types'] or [])}")
    L.append(f"- **P/T:** {pt} (Scryfall) · Stub: {'/'.join(x for x in (st['p_t'] or []) if x is not None) or '—'}")
    L.append(f"- **Keywords:** {kw} (Scryfall)")
    L.append(f"- **Oracle-Text:** {sf['oracle_text']} (Scryfall)")
    L.append(f"- **Set:** {sf['set']} ({sf['set_name']}, {sf['released_at']}) (Scryfall)")
    L.append(f"- **Stub verlässlich (Eckdaten):** {c['stub_reliability']} · **Stub-Fähigkeiten (Auszug):** {abilities}")
    L.append("")
L.append("## Ersatzkandidaten je Hauptdeck-Slot (29)")
L.append("")
L.append("Prüfung je Kandidat: (a) Engine-Existenz per Import des Satzes bewiesen (Status OK, "
         "`import_nachweis/`), (b) Commander-Legalität und (c) Farbidentität per Scryfall "
         "(EXTERNAL_DATA, Abruf 2026-10-20), (d) nicht bereits im Deck (Singleton, aus den Deckdateien), "
         "(e) Typ + Manawert nah am Original; Rolle mechanisch per Stichwort-Abgleich, sonst "
         "„Rolle UNKNOWN\". Häufigkeit = Zahl der Precons (von 195), die die Karte spielen.")
L.append("")
satz_of = {}
for s in manifest["sets"]:
    for orig, pick in s["assignment"].items():
        satz_of[(s["deck"], orig, pick)] = s["satz"]
for s in draft_slots:
    o = s["original"]
    L.append(f"### {s['deck']} — {s['card']} ({o['type_line']}, MV {o['cmc']:.0f}, Farbidentität des Decks: "
             f"{', '.join(s['deck_color_identity']) or 'farblos'})")
    for i, c in enumerate(s["candidates"][:3], 1):
        satz = satz_of.get((s["deck"], s["card"], c["name"]), "—")
        L.append(f"- **{i}. {c['name']}** — MV {c['mana_value']:.0f} (Diff {c['mana_value_diff']:.0f}), "
                 f"{c['type_line_scryfall']}, CI {', '.join(c['color_identity'] or []) or 'farblos'}, "
                 f"legal: {c['commander_legality']}, Precon-Häufigkeit {c['precon_frequency']}, "
                 f"{c['role_verdict']} · Importnachweis: Satz {satz} (OK)")
    L.append("")
L.append("## Deckgleichheit unter Option B")
L.append("")
L.append("| Deck | Ersetzte Slots | Gleichheit | Wird vollständig |")
L.append("|---|---|---|---|")
by_deck = {}
for s in slots:
    if s["zone"] == "mainboard":
        by_deck[s["deck"]] = by_deck.get(s["deck"], 0) + s["quantity"]
for deck, n in sorted(by_deck.items()):
    full = "nein (Commander fehlt)" if deck == "2026_multiverse_reforged" else "ja"
    L.append(f"| {deck} | {n} | {100 - n} % | {full} |")
L.append("")
L.append("## Reproduzierbarkeit")
L.append("")
L.append("- Kalibrierung: `python scripts/measure_precon_imports.py --jar <bridge.jar> --workdir <leer> "
         "--out imports.json --enumerate-missing` → 182 OK / 13 FAILED / 31 Namen / 33 Einträge.")
L.append("- Auswahl, Satzbau, Eckdaten: Skripte in `skripte/` (select_candidates.py, "
         "build_proof_copies.py, build_eckdaten.py, build_slots.py, run_proofs.sh) — alle Eingaben sind "
         "die Messdateien dieser Abgabe plus Scryfall-Abrufe vom 2026-10-20.")
L.append("- Importnachweise: je Satz eine JSON in `import_nachweis/` (Ergebniszeile des Decks, Status OK) "
         "plus Lauf-Log.")
L.append("- Arbeitsbaum `wt-m1-sweep` @ `ed2fbae26`: keine versionierte Datei geändert (alle Kopien und "
         "Skripte liegen außerhalb des Repos); `git status` sauber bis auf Build-Artefakte in "
         "`engine-bridge/target/` (gitignored).")
L.append("")
(BASE / "VORLAGE.md").write_text("\n".join(L), encoding="utf-8")
print("VORLAGE.md lines:", len(L), "| chars:", len("\n".join(L)))
