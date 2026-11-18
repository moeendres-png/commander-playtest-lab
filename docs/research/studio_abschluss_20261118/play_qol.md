# Lane play_qol: Wie lösen Open-Source- und Web-MTG-Projekte "wirklich spielbar" (Commander, 3–4 Spieler)?

**Stand:** Abrufdatum 2026-11-18 (alle Seiten-Abrufe an diesem Tag). **Nur Recherche**, kein Bau, nichts gepostet.
**Vorrecherchen gelesen:** `docs/research/OPEN_SOURCE_LANES_20261117.md` (PLAY-Abschnitt: Ideen 1–5 Klick/Zielpfeil/Stack-Schiene/Tastatur/Inspektor, Bild-Dämpfung nur per Overlay; Branch `play/board-click`, Objekt-IDs in der Bridge) und `docs/research/DECKBUILDER_COMPARISON_RESEARCH_20261116.md` (Deckbau, nur Kontext; kaum PLAY-Bezug).

**Kennzeichnung:** [S] = Seite abgerufen und gelesen (Eigenangabe des Projekts, nicht von uns nachgemessen). [T] = nur Suchtreffer/Drittquelle, nicht selbst gelesen. "unbekannt" = in den Quellen nicht belegt, nicht geraten.

**Rahmen (aus research_frame):** XMage ist Regelautorität; keine neuen Python-Abhängigkeiten; GPL/AGPL nur Ideenquelle; Simulation fließt nie in die Tierliste.

---

## 1. Projekte und Quellen (Tabelle)

| Projekt | Quelle / Abruf | Lizenz (belegt?) | Kernidee fürs Spielen | Nutzen für uns | Bewertung |
|---|---|---|---|---|---|
| XMage | github.com/magefree/mage [S]; Wiki-Seite "Supported deck formats" [S] | MIT [S] | Server-autoritatives Regelwerk, 2–10 Spieler inkl. Commander, Java | unsere Engine; Client-UI-Details im Web nicht belegt (Lücke) | Referenz / Regelautorität |
| Forge | github.com/Card-Forge/forge [S]; Wiki "Advanced Yield Options" [S] | GPL-3.0 [S] | Ausführlichstes dokumentiertes Yield-Modell (siehe §2) | Yield-Logik als Muster | nur Idee |
| Cockatrice | github.com/Cockatrice/Cockatrice [S] | GPL-2.0 [S] | Client + Server (Servatrice); Server verhindert Manipulation; Protobuf-Protokoll; Oracle als getrennter Kartendaten-Fetcher | Server-autoritativ bei verdeckten Informationen | nur Idee |
| Magarena | github.com/magarena/magarena [S] | GPL-3.0 [S] | Einzelspieler gegen MCTS-KI; Touch-Patch; Bilder on demand | Touch- und Bild-Lade-Muster | nur Idee |
| phase.rs | github.com/phase-rs/phase [S] | Apache-2.0/MIT [S] | Engine in Rust/WASM; Client mit transport-neutralem `EngineAdapter` (WASM, Tauri, WebSocket, P2P); Stack, Zielwahl-Overlays, Mana-Bezahlung, Animationen | Adapter-Muster für Client-Engine-Trennung | Muster übernehmbar (MIT/Apache, React); Rust-Engine irrelevant |
| Ironsmith | github.com/Chiplis/ironsmith [S] | AGPL-3.0 **plus** BSL-1.1-Datei im Repo [S] | Oracle-Text-Compiler, Zielwahl mit Submit/Next/Skip, Stack-Schiene, Tastatur, Inspektor mit Regeltext, Keep/Mulligan, nur "Undo tap" | viele konkrete UX-Muster (siehe §2) | nur Idee; Engine-Kompilierung widerspricht Regelautorität |
| Manabrew | github.com/witchesofthehill/manabrew [S] | AGPL-3.0-or-later [S]; vendored Forge GPL-3.0+ [S]; Protokoll-Doku CC-BY-4.0 [S] | Wahl zwischen Forge-Java und Rust-Port; Agent-Protokoll-DTOs; Parity-Harness Rust vs. Java mit gleichem Seed und Entscheidungen (als "deprecated, not functioning" markiert) | Engine-Austausch-Architektur; Parity-Idee als Golden-Replay-Analogon | nur Idee; Pre-Release, 82 Sterne [S] |
| untap.in | untap.in [S] | unbekannt (Dienst) | Browser-Tisch, Undo eines Fehlklicks, Replay eines beendeten Spiels Zug für Zug, Deck-Import per URL aus 80+ Seiten, PWA; FAQ: "It does not enforce the rules" | Undo-/Replay-Muster; Gegenbeispiel "ohne Regelprüfung" | Idee; kein Regelmaßstab |
| Archidekt | archidekt.com [S, nur Startseite] | — | Sandbox, Commander-Preset; Playtest nur als News ("Playtester interaction simulator") | Ideen zu Sandbox | niedrig; Funktionen nicht belegt |
| Moxfield | moxfield.com [S, HTTP 403] | — | — | — | unbekannt (nicht abrufbar) |
| Wizards Commander-Format | magic.wizards.com/en/formats/commander [S] | — | Command Zone; Tax +2 je früherer Cast aus der Command Zone; Commander-Schaden 21 Kampfschaden; 40 Leben; 7 Karten | Regel-Beleg für Tax/Commander-Damage-Anzeige | Regeltext als Beleg; Engine bleibt Autorität |
| Wizards Regelseite | magic.wizards.com/en/rules [S] | — | Verweis auf Comprehensive Rules (DOCX/PDF/TXT) | Regelnummern nicht abgerufen | Lücke |
| MTGJSON | github.com/mtgjson/mtgjson [S] | Code MIT; README nennt Daten MIT; Rechte an Kartentext ungeklärt [S] | Stammdaten | nur Datenquelle nach Klärung | bereits bekannt |
| Playwright toHaveScreenshot | playwright.dev/docs/test-snapshots [S] | nicht auf der Seite geprüft | Baselines, `threshold` (Default 0.2), `maxDiffPixels`, Maus wegbewegen, `stylePath` | Visuelle Regression für Board | Owner-Entscheid (Abhängigkeit) |
| WCAG 2.2 Quick Reference | w3.org/WAI/WCAG22/quickref [S] | W3C | 1.4.11, 2.1.1, 2.1.2, 2.4.7, 2.5.7, 2.5.8, 1.4.1, 2.2.1 | Prüfkatalog für Board-UI | Muss, nicht Projekt-Code |
| SpellTable (WotC) | Suchtreffer [T] (magic.gg-News; Drittquellen) | — | Webcam-Spiel mit physischen Karten, max. 4 Spieler, keine digitalen Tokens/Counter | keine Regelautorität | nein |
| Tabletop-Simulator-Commander-Mods | Suchtreffer [T] (Steam Workshop, Nexus) | — | Tisch ohne Regelengine, Commander-Schaden-Anzeige in Community-Mods | nur als Abgrenzung | nein |
| commander2tts | Suchtreffer [T] (github.com/firkemancer/commander2tts) | unbekannt | Moxfield-Liste → TTS-JSON | Nische | nein |
| mtg-replay-notation | Suchtreffer [T] (Spiegel gh.r-mj.com/killriam/mtg-replay-notation) | unbekannt in dieser Lane | JSON; L1 = verlustfreier Event-Log; L2 = Entscheidungssicht; Spec 1.0.0 (2025-12-20), aktuell 1.1.0 (Suchtreffer) | Replay-Format-Idee | Idee; Stand nicht selbst geprüft |
| Argentum Engine | Suchtreffer [T] (github.com/rwaldron/argentum-engine) | unbekannt | Gymnasium-Env, HTTP-Transport, LLM-KI über OpenAI-kompatible API | KI-Transparenz-Idee (Zustand + begründete Wahl) | unbekannt; nur Idee |
| MTG-Causal-RL (arXiv 2605.06066) | Suchtreffer [T], Preprint, nicht peer-reviewed geprüft | unbekannt | kausale Interventions-Traces für Interpretierbarkeit | KI-Transparenz (Forschung) | nur Idee, nicht übernehmen |
| Playgroup Live | playgroup.gg [Abruf fehlgeschlagen: Host nicht auflösbar] | — | laut Suchtreffer: Voice, Spielstatistik | — | unbekannt |

Zusätzlich gesichtet (Suchtreffer, nicht abgerufen): TableCommander (Werbeseite eines Wettbewerbers), Draftsim-Vergleich Jan. 2026. Diese Aussagen sind Sekundärquellen und nur Orientierung.

---

## 2. Befunde nach Feature-Bereich

**Priorität/Stack/Auto-Yield (am besten belegt: Forge [S]).**
- Auto-Pass als Umschalter (Taste P) ohne Stop-Regel; Yield-Marker pro Spieler *und* Phase (Rechtsklick/Langdruck auf die Phasenleiste); nur ein Marker aktiv.
- "Yield to stack" läuft bis der Stack leer ist, aber Interrupts können stoppen. "Resolve entire stack" ist **nicht unterbrechbar**.
- Interrupt-Standards: Angreifer gegen dich: AN; Gegner castet Zauber: AN; du/deine Permanents werden angezielt: AUS; Massenräumung: AUS; Trigger auf dem Stack: AUS. "Auto-pass respects interrupts" ist separat und standardmäßig aus.
- Vorschläge werden auf dem eigenen Zug unterdrückt (Default AN). Kein dediziertes "stop on my/opp turn"; Phasenmarker übernehmen das.
- Verzögerungen (200 ms pro Phase, 400 ms pro Stack-Element) abschaltbar.
- Ironsmith [S] hat "Hold priority" und "Auto-pass" als Stack-Steuerung, ohne Details.

**Zielwahl [S Ironsmith].** Legale Ziele werden hervorgehoben; Klick auf Karte oder Spieler; Knöpfe "Submit Targets", "Next requirement", "Skip"; Esc bricht ab. Enter drückt den Hauptknopf, Pfeiltasten wandern zwischen Karten und Zielen.

**Stack-Anzeige [S Ironsmith].** Schiene neben den Zonen, neuester oben, zeigt auch angekündigte Trigger; Klick zeigt Eintrag und Ziele. Entspricht Idee 3 aus der Vorrecherche.

**Inspektor/Kartentext [S Ironsmith, Forge].** Hover/Klick zeigt Regeltext, Marken, Anhänge, aktivierbare Fähigkeiten; mobil als Sheet. Der Text kommt bei uns bereits aus dem Store (Scryfall), Regelhinweise bleiben XMage-Sache.

**Mulligan/Starthand [S Ironsmith; WotC].** Ironsmith: "Keep hand" / "Mulligan" zu Beginn. WotC: 7 Karten, 40 Leben. London-Mulligan-Details: **unbekannt** (nicht belegt).

**Mana-Zahlung [S Ironsmith].** Nur "Undo tap" (Land-Tap rückgängig während der Bezahlung) ist belegt. Auto-Tap vs. manuell bei den anderen Projekten: unbekannt.

**Undo/Rollback [S untap.in, Ironsmith].** untap.in: Fehlklick rückgängig; beendete Spiele Zug für Zug wiederholbar. Ironsmith: nur Tap-Undo. Keine Quelle belegt eine Rollback-Politik bei verdeckten Informationen. Für uns: nur Bezahlungs-Undo, kein Rollback von Spielzügen (Server-Autorität, Regelautorität).

**Kampf-Zuweisung, mehrere Blocker, Trample [unbekannt].** In keiner abgerufenen Seite belegt. **Lücke** (siehe unten).

**Tempo/Animationen [S phase.rs, Forge].** phase.rs: Animationen und Audio; Forge: Verzögerungsregler. Keine Quelle belegt eine Animations-Politik mit Messung.

**Log/Replay [S Forge, Cockatrice; T mtg-replay-notation].** Forge: Seed plus zeitgesteuerte Aktionen (Suchtreffer-Quelle, nicht geöffnet). Muster: Seed + Entscheidungs-Log + Hash je Ergebnis (Vorrecherche-Idee). Replay-Spec mit verlustfreiem Event-Log vorhanden (T).

**Zonen-Ansicht [S Ironsmith].** Zonen-Stapel neben dem Feld, Stack als Schiene. Mehr nicht belegt.

**Mobil/Touch [S Magarena, Forge, Ironsmith, untap.in, phase.rs].** Touch-Patches (Magarena); Langdruck als Marker-Setzung (Forge); Inspektor als Sheet (Ironsmith); PWA (untap.in); Android/Tablet-Builds (phase.rs). Keine Messung.

**Barrierefreiheit [S WCAG 2.2; projektspezifisch unbekannt].** Kriterien für das Board: Tastatur (2.1.1), keine Tastaturfalle (2.1.2), sichtbarer Fokus (2.4.7), Farbe nicht allein (1.4.1), nicht-textueller Kontrast (1.4.11), Zielgröße (2.5.8), Ziehen mit Alternative (2.5.7), Timer einstellbar (2.2.1). Keine Spiel-Quelle belegt, dass diese Kriterien umgesetzt sind.

**Fehlersuche/Reproduzierbarkeit [S Forge-Hinweis, T Manabrew].** Manabrew: Parity-Harness, gleicher Seed und gleiche Entscheidungen; als deprecated markiert. Forge: "Currently, Forge functions best in Human vs. AI matches." Ein Entwicklungs-Testmodus (XMage Wiki "Development Testing Tools") existiert, Inhalt nicht gelesen.

**KI-Gegner und Transparenz [S Forge, Magarena; T Argentum, MTG-Causal-RL].** Forge: KI für Commander; Qualität nicht gemessen. Magarena: MCTS. phase.rs: KI mit Entscheidungslogik pro Karte, Baum-Suche und Heuristiken (README, [S]). KI-Begründung ("warum hat die KI das gespielt"): nur Forschungsvorschläge (kausale Traces, LLM mit Begründung); kein Produkt-Beleg für Erklärbarkeit im Spiel.

**Spielstand speichern/fortsetzen, Deck-Import/Export [S XMage Wiki].** XMage: Import/Export .dck, .dck_info, .mtga, .dek; nur Import .dec, .mwDeck, .txt, .draft, .cod, .o8d. Wiki-Seite zuletzt 2020 bearbeitet, ggf. veraltet; Moxfield/Archidekt nicht gelistet. Spielstand: unbekannt.

**Architektur [S phase.rs, Manabrew, Cockatrice, XMage].**
- Server-autoritativ mit Client-Adapter (phase.rs: `EngineAdapter`, mehrere Transporte; Manabrew: Relay-Server plus Node-Runtime, Agent-Protokoll-DTOs).
- Verdeckte Information: Cockatrice: Server erzwingt; Ironsmith: Mental-Poker-Kryptografie (für uns nicht relevant).
- Engine-Austausch (Forge-Java vs. Rust) bei Manabrew: für uns nicht übertragbar, da XMage die einzige Regelquelle ist.

**Test-Strategie [S Playwright].** toHaveScreenshot: Baseline im Repo, Standard-`threshold` 0.2, `maxDiffPixels` optional, Maus vor Aufnahme wegbewegen, `stylePath` für dynamische Elemente; Rendering hängt an OS, Browser, Headless. Golden-Replay (Seed + Entscheidungen) als Gegenstück für die Logik.

---

## 3. Empfehlungen für uns

Ausgangslage: Studio PLAY (Mensch gegen KI), XMage-Bridge liefert Objekt-IDs und Priority-Punkte; Branch `play/board-click` ist unfertig (Vorrecherche).

| Priorität | Aufwand (grob) | Empfehlung | Quelle |
|---|---|---|---|
| hoch | mittel | Yield-Modell wie Forge: Auto-Pass-Umschalter, Yield-to-Stack, nicht unterbrechbares "Resolve Stack", Interrupt-Standards wie oben. Serverseitig bleibt XMage Autorität, der Client setzt nur Stop-Regeln. Vorbedingung: prüfen, ob die Bridge Priority-Passes und Stack-Stände sauber liefert. | Forge [S] |
| hoch | klein–mittel | Zielwahl-UX: legale Ziele hervorheben, Submit / Next requirement / Skip, Esc bricht ab. Baut direkt auf den Objekt-IDs auf. | Ironsmith [S] |
| hoch | klein | Stack-Schiene, neuester oben, Klick zeigt Ziele. | Ironsmith [S] |
| hoch | klein | Commander-Anzeige: Tax und Commander-Schaden (21) sichtbar, Werte nur aus XMage übernehmen, nie im Client rechnen. | WotC [S] |
| mittel–hoch | mittel | Tastatur (Enter, Pfeile, Esc) und sichtbarer Fokus; Prüfkriterien 2.1.1 und 2.4.7. | Ironsmith [S], WCAG [S] |
| mittel | klein | Inspektor mit Regeltext bei Hover/Klick, Text aus dem Store; Regelhinweise nur aus XMage. | Ironsmith [S] |
| mittel | mittel | Replay/Log: Seed + Entscheidungs-Log + Herkunftsfeld je Ergebnis; Zug-für-Zug-Replay eines beendeten Spiels. | untap.in [S], mtg-replay-notation [T] |
| mittel | mittel | Undo nur für Mana-Bezahlung ("Undo tap"); kein Spielzug-Rollback. | Ironsmith [S] |
| mittel | mittel | Playwright-Screenshot-Test für das Board (feste Viewports, Maus wegbewegen). Owner-Entscheid wegen Abhängigkeit. | Playwright [S] |
| mittel | klein | Deck-Import: XMage-Formate .dck/.mtga/.dek sind belegt; Import aus Textlisten prüfen. | XMage Wiki [S] |
| niedrig–mittel | klein | Touch: Langdruck für Marker, Inspektor als Sheet. | Forge, Ironsmith [S] |
| niedrig | mittel | KI-Begründung: Kandidatenliste und Wahl je Entscheidung anzeigen, sobald XMage/Bridge die Daten liefert. Keine Aussage über KI-Güte ohne Messung. | Argentum/Causal-RL [T] |
| niedrig | — | Parity-Harness Rust vs. Java (Manabrew): für uns nur als Golden-Replay-Idee. | Manabrew [S] |

**Nicht übernehmen, und warum:**
- Ironsmith-Oracle-Compiler oder Manabrew-Rust-Engine: zweites Regelwerk, verletzt die Regelautorität XMage; Ironsmith zusätzlich BSL-Datei, Manabrew AGPL plus Forge-GPL.
- Code aus Forge, Cockatrice, Magarena, Ironsmith, Manabrew: GPL/AGPL, nur Ideenquelle.
- untap.in- oder SpellTable-Modell (ohne Regelprüfung, Webcam): widerspricht dem Anspruch "wirklich spielbar mit Regelautorität".
- TTS-Mods: keine Regelengine.
- Hidden-Information-Kryptografie (Ironsmith): kein Bedarf.

---

## 4. Offene Lücken / Nicht belegt

- **XMage-Client-Features nicht belegt:** Auto-Yield-Details, Kampf-Zuweisung, Trample, Mulligan-UI, Mana-Auto-Tap, Undo, Zonen-Ansicht. Die XMage-Wiki-Seiten (Hauptseite, Home) enthalten keine Client-Beschreibung. Empfehlung: lokalen XMage-Client-Code lesen (nicht Teil dieser Web-Lane).
- Kampf-Zuweisung bei mehreren Blockern und Trample: in keiner Quelle belegt.
- London-Mulligan-Regeln: nicht auf der WotC-Seite; Comprehensive Rules nicht gelesen (Regelnummern unbekannt).
- Moxfield nicht abrufbar (403/404), Archidekt nur Startseite, Playgroup Live nicht auflösbar. Deren Playtest-Funktionen: unbekannt.
- Letzter Commit/Aktivität: für Forge, Cockatrice, Magarena, phase.rs und XMage unbekannt (aus den abgerufenen Seiten nicht ersichtlich). Lizenzangaben in der Tabelle stammen aus den abgerufenen Seiten; Sterne wurden nicht erhoben.
- mtg-replay-notation, Argentum Engine, MTG-Causal-RL, SpellTable, TTS-Mods: nur Suchtreffer, nicht selbst gelesen.
- Ironsmith-Commit-Stand, Ironsmith-BSL-Inhalt: nur Dateiname gesehen.
- KI-Qualität: keine vergleichbare Messung in den Quellen.
- Animationen/Tempo: keine messbaren Aussagen.
- Barrierefreiheit spezifisch für MTG-Clients: nicht gefunden; nur allgemeine WCAG-Kriterien.
- Owner-Fragen: (1) Playwright-Abhängigkeit für Board-Screenshots erlauben? (2) Soll ein Mensch die Lizenz der Replay-Notation prüfen, bevor ein Format übernommen wird?
