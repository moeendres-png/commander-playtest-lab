"use strict";
// Colour castability (#1415, #1404 option 2): exact, conditioned on land drops (Karsten).
// Every probability names its condition; no land count advice. Rendered from renderNumbers.
// WP-2/WP-3 (#1404): sources "direkt" and "über Suchland" (calculation assumption shown on the
// page), the commander on curve and the exact land count table 30-40.
// The opening-hand figure is shown through the number contract (zahl.js, #1659) as EXAKT.
// WP-4 (#1404): tapped classes per land from the rules text with the quoted sentence (n of N,
// "unbekannt" is its own class) and the colour access of stage 2 (exact, lower/upper bound,
// one assumption shown on the page).

function castPct(value) { return value === null || value === undefined ? "unbekannt" : StudioUI.pct(value, 1); }

// Starting-hand chance per role (#1404): P(>= 1 card of the role) in 7 cards and after 1-3 more.
function handRoleNodes(h, hr, roleName) {
  const head = ["Start", "Zug 1", "Zug 2", "Zug 3"];
  const out = [h("h3", {}, "Rollen in der Starthand"),
    h("p", { class: "note" }, `Rollendaten bei ${StudioUI.num(hr.cards_with_role_data)} von ${StudioUI.num(hr.library)} Karten im Deck (Nichtland: ${StudioUI.num(hr.nonland_with_role_data)} von ${StudioUI.num(hr.nonland_cards)}${hr.modal_land_cards ? `, davon ${StudioUI.num(hr.modal_land_cards)} Modal-Land-Karten mit Land-Rückseite` : ""}). ${hr.assumption}`)];
  if (!hr.roles_known) return [...out, h("p", { id: "hand-roles", class: "warn" }, "Für diese Karten sind keine Rollen bekannt: keine Wahrscheinlichkeit berechnet (unbekannt, nicht 0).")];
  const sorted = [...hr.roles].sort((a, b) => roleName(a.role).localeCompare(roleName(b.role), "de"));
  const rows = sorted.flatMap((item) => [
    h("tr", { class: "facts-row" },
      h("td", {}, h("div", {}, roleName(item.role)), h("div", { class: "note" }, `Karten im Deck: ${StudioUI.num(item.cards)} von ${StudioUI.num(item.of)}`)),
      ...item.hands.map((hand) => h("td", { class: "num", title: `${StudioUI.num(hand.draws)} Karten: mindestens eine Karte der Rolle` }, StudioUI.pct(hand.p_at_least_1, 1)))),
    h("tr", { class: "facts-basis" },
      h("td", { class: "note" }, "keine Karte"),
      ...item.hands.map((hand) => h("td", { class: "num muted", title: `${StudioUI.num(hand.draws)} Karten: keine Karte der Rolle` }, StudioUI.pct(hand.p_none, 1)))),
  ]);
  return [...out,
    h("div", { class: "table-wrap" }, h("table", { id: "hand-roles" },
      h("thead", {}, h("tr", {}, h("th", {}, "Rolle"),
        ...head.map((text) => h("th", { class: "num", title: "Start 7 Karten, Zug 1 8, Zug 2 9, Zug 3 10 (Ziehen in Zug 1)" }, text)))),
      h("tbody", {}, rows))),
    h("p", { class: "note" }, "Karten in der Hand: Start 7, nach Zug 1 8, Zug 2 9, Zug 3 10. Je Rolle: obere Zeile mindestens eine Karte der Rolle, untere Zeile keine Karte der Rolle (zusammen 100 %, durch Rundung bis 0,1 Prozentpunkt Abweichung). Rollen sind öffentliche Marken (Tagger); eine Karte zählt für jede ihrer Rollen.")];
}

// Sources per colour as "U 17" (direct) or "U 20 (+3)" (with search lands).
function castSources(sources, direct) {
  return Object.entries(sources || {}).map(([colour, count]) => {
    const plus = direct && direct[colour] !== undefined && count > direct[colour] ? ` (+${StudioUI.num(count - direct[colour], 0)})` : "";
    return `${colour} ${StudioUI.num(count, 0)}${plus}`;
  }).join(" · ") || "–";
}

// WP-2: land classes from card data and rules text, with n/N and the calculation assumption.
function landClassNodes(h, classes) {
  if (!classes) return [];
  const c = classes.counts || {};
  const out = [h("p", { id: "land-classes", class: "note" },
    `Länderklassen (${classes.origin}): direkt ${StudioUI.num(c.direkt || 0, 0)}, Suchland ${StudioUI.num(c.suchland || 0, 0)}, ohne farbiges Mana ${StudioUI.num(c.ohne_farbe || 0, 0)}, unbekannt ${StudioUI.num(c.unbekannt || 0, 0)} – Klasse bestimmt für ${StudioUI.num(classes.classified, 0)} von ${StudioUI.num(classes.of, 0)} Ländern.`)];
  const search = classes.search_lands || [];
  if (search.length) {
    out.push(h("ul", { id: "search-lands", class: "note" }, search.map((land) => h("li", {},
      `${land.name}${land.quantity > 1 ? ` (${StudioUI.num(land.quantity, 0)}×)` : ""}: sucht ${land.searches_for}; `,
      land.reach.length ? `passende Länder im Deck: ${StudioUI.num(land.targets, 0)}, erreichbare Farben ${land.reach.join("")}` : `kein passendes Land im Deck (${StudioUI.num(land.targets || 0, 0)}): Quelle keiner Farbe (bekannt, nicht unbekannt)`))));
  }
  const unknown = classes.unknown || [];
  if (unknown.length) {
    out.push(h("p", { id: "land-classes-unknown", class: "warn" }, `Unbekannt (weder direkt noch über Suchland gezählt, nicht 0): ${unknown.map((land) => `${land.name} – ${land.reason}`).join("; ")}.`));
  }
  out.push(h("p", { id: "search-assumption", class: "note" }, h("strong", {}, "Annahme: "), classes.assumption));
  return out;
}

// The stage-2 event is "an untapped direct source", not the colour access: said at the table (#1755 review).
const ACCESS_NOTE = "Keine Grenze des Farbzugriffs: getappte Länder aus Zug 1, die in Zug 2 schon Mana geben, sind nicht gezählt. „Exakt“ gilt nur für das genannte Ereignis (ungetappte direkte Quelle); die zwei Werte sind Grenzen nur wegen bedingt getappter und unbekannter Länder.";
const TAP_LABELS = { immer_getappt: "immer getappt", bedingt_getappt: "bedingt getappt", ungetappt: "ungetappt", unbekannt: "unbekannt" };

// A lower and an upper bound as one value when they agree, else "a – b".
function castRange(low, high) {
  if (low === null || low === undefined || high === null || high === undefined) return "unbekannt";
  return low === high ? castPct(low) : `${castPct(low)} – ${castPct(high)}`;
}

// WP-4 stage 1 and 2: tapped classes (n of N, quoted rules text) and the colour access.
function tappedNodes(h, tapped, access) {
  if (!tapped) return [];
  const c = tapped.counts || {};
  const out = [h("h3", {}, "Getappte Länder (Tempo)"),
    h("p", { id: "tapped-classes" }, `Von ${StudioUI.num(tapped.of, 0)} Ländern: immer getappt ${StudioUI.num(c.immer_getappt || 0, 0)} von ${StudioUI.num(tapped.of, 0)}, bedingt getappt ${StudioUI.num(c.bedingt_getappt || 0, 0)} von ${StudioUI.num(tapped.of, 0)}, ungetappt ${StudioUI.num(c.ungetappt || 0, 0)} von ${StudioUI.num(tapped.of, 0)}, unbekannt ${StudioUI.num(c.unbekannt || 0, 0)} von ${StudioUI.num(tapped.of, 0)} – Klasse bestimmt für ${StudioUI.num(tapped.classified, 0)} von ${StudioUI.num(tapped.of, 0)} Ländern.`),
    h("p", { class: "note" }, `Herkunft: ${tapped.origin}. Regel: ${tapped.rule}`)];
  const quoted = (tapped.lands || []).filter((land) => land.class !== "ungetappt" || land.fetch_quote);
  if (quoted.length) {
    out.push(h("div", { class: "table-wrap" }, h("table", { id: "tapped-lands" },
      h("thead", {}, h("tr", {}, h("th", {}, "Land"), h("th", {}, "Klasse"), h("th", {}, "Regeltext (Zitat)"))),
      h("tbody", {}, quoted.map((land) => h("tr", { class: land.class === "unbekannt" ? "warn" : "" },
        h("td", {}, land.name, land.quantity > 1 ? ` (${StudioUI.num(land.quantity, 0)}×)` : ""),
        h("td", {}, TAP_LABELS[land.class] || land.class),
        h("td", { class: "note" }, land.quote ? `„${land.quote}“` : (land.class === "unbekannt" ? land.reason : "kein Satz zum getappten Eintritt"),
          land.fetch_quote ? h("div", {}, `Geholtes Land: „${land.fetch_quote}“`) : "")))))));
  }
  if (!access || !access.colours || !access.colours.length) return out;
  out.push(h("h3", {}, "Ungetappte Quelle früh"),
    h("p", { id: "access-note", class: "note warn" }, ACCESS_NOTE),
    h("div", { class: "table-wrap" }, h("table", { id: "colour-access" },
      h("thead", {}, h("tr", {}, h("th", {}, "Farbe"),
        h("th", { class: "num", title: "mindestens eine direkte Quelle der Farbe, gleich welcher Klasse, unter 7 Karten" }, "Starthand (7 Karten)"),
        ...[1, 2].map((turn) => h("th", { class: "num", title: `mindestens ein ungetapptes Land mit eigener Farbe unter ${StudioUI.num(7 + turn, 0)} Karten (nur direkte Quellen)` }, `ungetappte Quelle direkt Zug ${StudioUI.num(turn, 0)} (${StudioUI.num(7 + turn, 0)} Karten)`)),
        h("th", { class: "num" }, "Quellen direkt (davon ungetappt)"))),
      h("tbody", {}, access.colours.map((item) => h("tr", {},
        h("td", {}, h("span", { class: "ms ms-" + item.colour }, item.colour)),
        h("td", { class: "num" }, castRange(item.opening_hand.p, item.opening_hand.p_high)),
        ...item.turns.map((turn) => h("td", { class: "num" }, castRange(turn.p_low, turn.p_high))),
        h("td", { class: "num" }, `${StudioUI.num(item.sources, 0)} (${item.untapped_low === item.untapped_high ? StudioUI.num(item.untapped_low, 0) : `${StudioUI.num(item.untapped_low, 0)} – ${StudioUI.num(item.untapped_high, 0)}`})`)))))),
    h("p", { id: "access-assumption", class: "note" }, h("strong", {}, access.assumption), " ", access.rule,
      access.lands_unknown_colours ? ` ${StudioUI.num(access.lands_unknown_colours, 0)} Länder ohne Farbdaten: nur in der oberen Grenze.` : ""));
  return out;
}

// WP-3: the commander's own cost on curve from the command zone.
function commanderNodes(h, commanders) {
  if (!commanders || !commanders.length) return [];
  const rows = commanders.map((cmd) => {
    if (!cmd.known) return h("tr", {}, h("td", {}, cmd.name), h("td", { colspan: 5, class: "note" }, `unbekannt (${cmd.reason})`));
    const ws = cmd.with_search || {};
    return h("tr", { class: "facts-row" },
      h("td", { class: "nowrap" }, cmd.name, h("div", { class: "note" }, `${cmd.mana_cost || "ohne Kosten"} · Zug ${StudioUI.num(cmd.turn, 0)}${cmd.hybrid_or_phyrexian ? " · Hybrid/Phyrexia nicht eingerechnet" : ""}`)),
      h("td", { class: "num", title: "Land-Drops und Farben zusammen, direkt" }, castPct(cmd.p_on_curve)),
      h("td", { class: "num", title: "Land-Drops und Farben zusammen, mit Suchland" }, castPct(ws.p_on_curve)),
      h("td", { class: "num", title: `mindestens ${StudioUI.num(cmd.turn, 0)} Länder unter ${StudioUI.num(cmd.draws, 0)} Karten` }, castPct(cmd.p_land_drops)),
      h("td", { class: "num", title: cmd.condition }, castPct(cmd.p_colours_given_lands)),
      h("td", { class: "num", title: cmd.condition }, castPct(ws.p_colours_given_lands)));
  });
  return [
    h("h3", {}, "Commander auf Kurve"),
    h("div", { class: "table-wrap" }, h("table", { id: "commander-curve" },
      h("thead", {}, h("tr", {}, h("th", {}, "Commander"),
        h("th", { class: "num" }, "auf Kurve direkt"), h("th", { class: "num" }, "auf Kurve mit Suchland"),
        h("th", { class: "num" }, "Land-Drops"), h("th", { class: "num" }, "Farben direkt*"), h("th", { class: "num" }, "Farben mit Suchland*"))),
      h("tbody", {}, rows))),
    h("p", { class: "note" }, "Commander aus der Kommandozone im Zug seines Manawerts: Bibliothek = Deck ohne Commander, erster Wurf ohne Commander-Steuer. „Auf Kurve“ = Land-Drops und Farben zusammen (Land-Drops × Farben). Jedes Farbsymbol braucht ein eigenes Land."),
    h("p", { id: "commander-start-note", class: "note" }, commanders.filter((cmd) => cmd.known).map((cmd) => `Gerechnet für den Nichtstartspieler (zieht in Zug 1): in Zug ${StudioUI.num(cmd.turn, 0)} ${StudioUI.num(cmd.draws, 0)} Karten; ein Startspieler sieht in Zug ${StudioUI.num(cmd.turn, 0)} nur ${StudioUI.num(cmd.draws - 1, 0)} Karten.`).join(" ")),
  ];
}

// WP-3: exact land count table 30-40 (and the deck's own count), no advice.
function landCountNodes(h, table) {
  if (!table || !table.rows || !table.rows.length) return [];
  return [
    h("h3", {}, "Landzahl-Tabelle (30–40 Länder, exakt)"),
    h("div", { class: "table-wrap" }, h("table", { id: "land-count-table" },
      h("thead", {}, h("tr", {}, h("th", {}, ""), h("th", { class: "num", colspan: table.rows[0].cells.length, id: "land-count-player" }, "Nichtstartspieler (zieht in Zug 1); Startspieler: Spalte einen Zug früher")),
        h("tr", {}, h("th", { class: "num" }, "Länder"),
        ...table.rows[0].cells.map((cell) => h("th", { class: "num", title: `mindestens ${StudioUI.num(cell.turn, 0)} Länder unter ${StudioUI.num(cell.draws, 0)} Karten` }, `Zug ${StudioUI.num(cell.turn, 0)} · ${StudioUI.num(cell.draws, 0)} Karten`)))),
      h("tbody", {}, table.rows.map((row) => h("tr", { class: row.deck ? "facts-row land-count-deck" : "" },
        h("td", { class: "num" }, StudioUI.num(row.lands, 0), row.deck ? " (Deck)" : ""),
        ...row.cells.map((cell) => h("td", { class: "num" }, castPct(cell.p)))))))),
    h("p", { class: "note" }, `Je Zeile: Anteil der Ziehungen mit mindestens so vielen Ländern wie der Zug. ${table.rule} Zählweise wie „Farben auf Kurve“ (7 + Zug Karten); die Land-Zieh-Tabelle weiter oben zählt für den Startspieler (zieht in Zug 1 nicht), dort steht derselbe Wert einen Zug später.`),
  ];
}

function castabilityNodes(h, data, open, roleName) {
  const pipLabel = (label) => h("span", {}, ...label.split("").map((letter) => h("span", { class: "ms ms-" + letter }, letter)));
  const names = (cards) => h("span", {}, ...cards.flatMap((card, index) => [index ? ", " : "",
    h("a", { href: "#", class: "nm", onclick: (event) => { event.preventDefault(); open(card.card_id); } }, card.name)]));
  const rows = data.requirements.flatMap((item) => {
    const ws = item.with_search || {};
    return [
      h("tr", { class: "facts-row" },
        h("td", { class: "nowrap" }, pipLabel(item.label), ` Zug ${StudioUI.num(item.turn, 0)}`),
        h("td", { class: "num", title: `mindestens ${StudioUI.num(item.turn, 0)} Länder unter ${StudioUI.num(item.draws, 0)} Karten` }, castPct(item.p_land_drops)),
        h("td", { class: "num", title: item.condition }, castPct(item.p_colours_given_lands)),
        h("td", { class: "num", title: `${item.condition}; Suchländer unter der Annahme unten` }, castPct(ws.p_colours_given_lands)),
        h("td", { class: "num" }, castSources(item.sources)),
        h("td", { class: "num" }, castSources(ws.sources, item.sources))),
      h("tr", { class: "facts-basis" }, h("td", { colspan: 6, class: "note" }, names(item.cards))),
    ];
  });
  const hand = data.opening_hand;
  const keepable = StudioZahl.index(data.zahlen).get("cast.opening_hand.p_keepable");
  const notes = [];
  const searchCount = data.land_classes && data.land_classes.counts ? data.land_classes.counts.suchland || 0 : 0;
  if (data.lands_without_coloured_mana) notes.push(`${StudioUI.num(data.lands_without_coloured_mana, 0)} Länder erzeugen laut Kartendaten kein farbiges Mana; direkt zählen sie nicht als Quelle${searchCount ? `, davon ${StudioUI.num(searchCount, 0)} Suchländer in „mit Suchland“` : ""}.`);
  if (data.lands_unknown_colours) notes.push(`${StudioUI.num(data.lands_unknown_colours, 0)} Länder ohne Kartendaten: Farben unbekannt, nicht als Quelle gezählt – die Farbwerte sind darum eher zu niedrig.`);
  if (data.cards_unknown_mana_value) notes.push(`${StudioUI.num(data.cards_unknown_mana_value, 0)} Karten mit unbekanntem Manawert: ohne eigene Farbanforderung, in den Ziehungen als Karten ohne frühe Aktion gezählt.`);
  if (data.hybrid_or_phyrexian_cards.length) notes.push(`Hybrid- und Phyrexia-Symbole nicht eingerechnet bei: ${data.hybrid_or_phyrexian_cards.join(", ")}.`);
  return [
    h("h3", {}, "Farben auf Kurve (bedingt auf Land-Drops)"),
    h("p", { class: "note" }, `Je Farbanforderung: Wahrscheinlichkeit, bis zum Zug des Manawerts genug Länder zu haben (Land-Drops), und – nur unter diesen Ziehungen – die nötigen Quellen der Farbe(n), einmal direkt und einmal mit Suchländern. ${StudioUI.num(data.lands, 0)} Länder in ${StudioUI.num(data.main_cards, 0)} Karten.`),
    ...commanderNodes(h, data.commander),
    h("div", { class: "table-wrap" }, h("table", { id: "castability" },
      h("thead", {}, h("tr", {}, h("th", {}, "Kosten"),
        h("th", { class: "num" }, "Land-Drops"), h("th", { class: "num", title: "nur unter den Ziehungen mit genug Land-Drops, ohne Suchländer" }, "Farben direkt*"),
        h("th", { class: "num", title: "nur unter den Ziehungen mit genug Land-Drops, Suchländer als Quelle (Annahme unten)" }, "Farben mit Suchland*"),
        h("th", { class: "num" }, "Quellen direkt"), h("th", { class: "num", title: "Länder mit eigener Farbe plus Suchländer (Annahme unten)" }, "Quellen über Suchland"))),
      h("tbody", {}, rows))),
    h("p", { class: "note" }, "* Farben: Anteil mit den nötigen farbigen Quellen unter den Ziehungen, die bis zum Zug genug Länder haben. Quellen: nur Länder. „direkt“: Länder mit eigener Farbe; „mit Suchland“: zusätzlich Suchländer unter der Annahme unten."),
    ...landClassNodes(h, data.land_classes),
    ...tappedNodes(h, data.tapped, data.colour_access),
    h("p", { id: "opening-hand" }, `Spielbare Starthand (${hand.rule}): `, keepable ? StudioZahl.knoten(h, keepable) : castPct(hand.p_keepable), ` – aus ${StudioUI.num(hand.lands, 0)} Ländern, ${StudioUI.num(hand.early_actions, 0)} frühen Aktionen und ${StudioUI.num(hand.other_cards, 0)} weiteren Karten, 7 Karten, ohne Mulligan.`),
    notes.length ? h("ul", { class: "note" }, notes.map((text) => h("li", {}, text))) : "",
    ...landCountNodes(h, data.land_count_table),
    ...(data.hand_roles ? handRoleNodes(h, data.hand_roles, roleName || ((key) => key)) : []),
    h("p", { class: "note" }, data.method + " ", h("a", { href: data.source, target: "_blank", rel: "noreferrer noopener", referrerpolicy: "no-referrer" }, "Methodik (Karsten 2022)")),
  ];
}

// deps: { h, api, entries, fail, open(card_id), token(), isCurrent(token) }
async function renderCastability(body, deps) {
  const { h } = deps;
  const box = h("div", { id: "castability-box" }, h("p", { class: "muted" }, "Farben auf Kurve werden berechnet …"));
  const handSection = h("div", { id: "sample-hand-section" });
  body.append(box, handSection);
  const token = deps.token();
  try {
    const data = await deps.api("/api/castability", "POST", { cards: deps.entries() });
    if (!deps.isCurrent(token)) return;
    box.replaceChildren(...castabilityNodes(h, data, deps.open, deps.roleName));
  } catch (error) {
    if (!deps.isCurrent(token)) return;
    box.replaceChildren(h("p", { class: "warn" }, "Die Farb-Wahrscheinlichkeiten konnten nicht berechnet werden."));
    deps.fail(error);
  }
  const st = { seed: 1, mulligans: 0, drawSteps: 0, bottom: [] };
  async function loadSampleHand() {
    try {
      const res = await deps.api("/api/sample-hand", "POST", { cards: deps.entries(), seed: st.seed, mulligans: st.mulligans, draw_steps: st.drawSteps, bottom_indices: st.bottom });
      if (deps.isCurrent(token)) renderSampleHandUI(res);
    } catch (_) {
      if (deps.isCurrent(token)) handSection.replaceChildren(h("p", { class: "warn" }, "Beispielhand konnte nicht gezogen werden."));
    }
  }
  function renderSampleHandUI(res) {
    const sum = res.summary || {};
    const sourcesStr = Object.entries(sum.kept_land_sources || {}).filter(([, cnt]) => cnt > 0).map(([col, cnt]) => `${col} ${StudioUI.num(cnt, 0)}`).join(" · ") || "keine";
    const rows = (res.hand || []).map((c) => {
      const isBot = Boolean(c.bottomed);
      const statusTxt = c.is_land ? `Land (${(c.produced_colours || []).join("") || "farblos/unbekannt"})` : (c.castable_from_kept_lands === true ? "Länder & Farben in Hand" : (c.castable_from_kept_lands === false ? "Quelle/Land fehlt noch" : "unbekannt"));
      return h("tr", { class: isBot ? "muted" : "" },
        h("td", {}, h("a", { href: "#", class: "nm", onclick: (e) => { e.preventDefault(); deps.open(c.card_id); } }, c.name), isBot ? " " : "", isBot ? h("span", { class: "badge" }, "unter Bibliothek") : ""),
        h("td", { class: "note" }, c.mana_cost || "—"), h("td", { class: "note" }, c.type_line || "—"), h("td", { class: "note" }, statusTxt),
        h("td", {}, h("button", { type: "button", class: "secondary", onclick: () => { const idx = Number(c.index); st.bottom = st.bottom.includes(idx) ? st.bottom.filter((x) => x !== idx) : [...st.bottom, idx]; loadSampleHand(); } }, isBot ? "Behalten" : "Unter Bibliothek")));
    });
    const extraRows = (res.extra_draws || []).map((c) => h("tr", {},
      h("td", {}, `Zug ${StudioUI.num(c.turn_drawn, 0)}: `, h("a", { href: "#", class: "nm", onclick: (e) => { e.preventDefault(); deps.open(c.card_id); } }, c.name)),
      h("td", { class: "note" }, c.mana_cost || "—"), h("td", { class: "note" }, c.type_line || "—"),
      h("td", { class: "note" }, c.is_land ? `Land (${(c.produced_colours || []).join("") || "farblos"})` : (c.castable_by_turn_drawn ? "wirfbar mit gezogenen Ländern" : "Quelle/Land fehlt noch")),
      h("td", { class: "note" }, "gezogen")));
    handSection.replaceChildren(
      h("h3", {}, "Starthand- & London-Mulligan-Simulator (Modellrechnung)"),
      h("p", { class: "note" }, `${res.assumption || ""} Bibliothek: ${StudioUI.num(res.library_size || 0, 0)} Karten.`),
      h("div", { class: "row" },
        h("label", { class: "note" }, "Seed: ", h("input", { id: "sample-hand-seed", type: "number", min: "0", value: String(st.seed), onchange: (e) => { st.seed = Math.max(0, parseInt(e.target.value, 10) || 0); st.mulligans = 0; st.drawSteps = 0; st.bottom = []; loadSampleHand(); } })),
        h("button", { id: "sample-hand-new", type: "button", onclick: () => { st.seed += 1; st.mulligans = 0; st.drawSteps = 0; st.bottom = []; loadSampleHand(); } }, "Neue Starthand (Seed +1)"),
        h("button", { id: "sample-hand-mulligan", type: "button", class: "secondary", onclick: () => { st.mulligans = Math.min(7, st.mulligans + 1); st.drawSteps = 0; st.bottom = []; loadSampleHand(); } }, `London-Mulligan (${StudioUI.num(st.mulligans, 0)})`),
        h("button", { id: "sample-hand-draw", type: "button", class: "secondary", onclick: () => { st.drawSteps = Math.min(10, st.drawSteps + 1); loadSampleHand(); } }, `+1 Karte ziehen (${StudioUI.num(st.drawSteps, 0)})`)),
      h("p", { id: "sample-hand-summary", class: "note" },
        `Behalten: ${StudioUI.num(sum.kept_cards || 0, 0)} Karten (Pflicht unter Bibliothek bei Mulligan ${StudioUI.num(res.mulligans || 0, 0)}: ${StudioUI.num(res.bottom_required || 0, 0)}, gewählt: ${StudioUI.num((res.bottom_indices || []).length, 0)}) · Länder: ${StudioUI.num(sum.lands_in_kept || 0, 0)} (Quellen: ${sourcesStr}) · Frühe Aktionen (MV ≤ 2): ${StudioUI.num(sum.early_actions_in_kept || 0, 0)} · Aus Handländern gedeckte Nichtländer: ${StudioUI.num(sum.castable_nonlands_in_kept || 0, 0)} / ${StudioUI.num(sum.nonlands_in_kept || 0, 0)}`),
      h("div", { class: "table-wrap" }, h("table", { id: "sample-hand-table" },
        h("thead", {}, h("tr", {}, h("th", {}, "Karte"), h("th", {}, "Kosten"), h("th", {}, "Typ"), h("th", {}, "Quellen-Check"), h("th", {}, "Mulligan-Auswahl"))),
        h("tbody", {}, [...rows, ...extraRows]))));
  }
  await loadSampleHand();
}

