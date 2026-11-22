"use strict";
// Counted deltas of the variant comparison (#1414, #1404 option 8): curve, colours, combos,
// overlap and, per swapped card, roles, mana value and source-deck frequency with n/N.
// No score and no verdict on a swap. Rendered from renderDiff in app.js.
// The source-deck share is a GEZÄHLT column of the number contract (zahl.js, #1659): the figure
// comes from diff.zahlen ("freq.<group>.<card_id>"); without a contract the old text stays.
// WP-5 (#1404): the mana base before/after (diff.manabase): per requirement the exact colour
// access of both lists and the delta in pp, the opening hand, the colour access per colour,
// the lands per tapped class and the commander on curve; "unbekannt" where a side is not
// computable, never 0.

function diffSigned(value) { return (Number(value) > 0 ? "+" : "") + StudioUI.num(value, 0); }

function diffCardTable(h, title, items, quantityText, deps, group) {
  const freq = (item) => {
    if (item.of === null || item.of === undefined) return "keine Quelldecks";
    if (item.decks === null || item.decks === undefined) return `unbekannt / ${StudioUI.num(item.of, 0)}`;
    return `${StudioUI.num(item.decks, 0)} / ${StudioUI.num(item.of, 0)}` + (item.of ? ` (${StudioUI.num(100 * item.decks / item.of, 1)} %)` : "");
  };
  return [
    h("h3", {}, title),
    h("div", { class: "table-wrap" }, h("table", { class: "diff-cards" },
      h("thead", {}, h("tr", {}, h("th", { class: "num" }, "Anzahl"), h("th", {}, "Karte"), h("th", { class: "num" }, "MW"),
        h("th", {}, "Rollen"), h("th", { class: "num" }, `Quelldecks (${deps.cohortLabel})`))),
      h("tbody", {}, items.map((item) => h("tr", {},
        h("td", { class: "num" }, quantityText(item)),
        h("td", {}, h("a", { href: "#", class: "nm", onclick: (event) => { event.preventDefault(); deps.open(item.card_id); } }, item.name)),
        h("td", { class: "num" }, item.mana_value === null || item.mana_value === undefined ? "unbekannt" : StudioUI.numFlex(item.mana_value, 2)),
        h("td", {}, item.roles && item.roles.length ? item.roles.map(deps.roleName).join(", ") : h("span", { class: "muted" }, "keine Rolle")),
        diffFreqCell(h, item, group, deps, freq)))))),
  ];
}

function diffFreqCell(h, item, group, deps, freq) {
  const zahl = deps.zahlen ? deps.zahlen.get(`freq.${group}.${item.card_id}`) : undefined;
  if (!zahl) return h("td", { class: "num" }, freq(item));
  return StudioZahl.zelle(h, zahl, "GEZÄHLT", { class: "num" });
}

function diffPct(value) { return value === null || value === undefined ? "unbekannt" : StudioUI.pct(value, 1); }
function diffPp(value) {
  if (value === null || value === undefined) return "unbekannt";
  return `${value > 0 ? "+" : ""}${StudioUI.num(value, 1)} pp`;
}
function diffPpCell(h, value) {
  return h("td", { class: "num" + (value ? " changed" : "") }, diffPp(value));
}

// WP-5: mana base before/after, every figure exact on both lists, deltas in pp.
function diffManabaseNodes(h, mb) {
  if (!mb) return [];
  const lists = mb.lists || {};
  const head = (labels) => h("thead", {}, h("tr", {}, ...labels.map((label, index) => h("th", index ? { class: "num" } : {}, label))));
  // One cell per figure in the form of the colour table: "Basis → aktuell (Delta)".
  const pair = (base, target, delta) => `${diffPct(base)} → ${diffPct(target)} (${diffPp(delta)})`;
  const reqRows = (mb.requirements || []).map((item) => {
    const only = item.in_base && item.in_target ? "" : (item.in_base ? " · nur in Basis" : " · nur aktuell");
    return h("tr", {},
      h("td", { class: "nowrap" }, item.label, ` Zug ${StudioUI.num(item.turn, 0)}`, only ? h("span", { class: "note" }, only) : ""),
      h("td", { class: "num" + (item.delta_pp.p_colours_given_lands ? " changed" : "") }, pair(item.base.p_colours_given_lands, item.target.p_colours_given_lands, item.delta_pp.p_colours_given_lands)),
      diffPpCell(h, item.delta_pp.p_colours_given_lands_with_search),
      diffPpCell(h, item.delta_pp.p_on_curve));
  });
  const nodes = [h("h3", {}, "Manabasis vorher/nachher (exakt)"),
    h("p", { class: "note" }, `Basis: ${StudioUI.num(lists.base ? lists.base.lands : 0, 0)} Länder in ${StudioUI.num(lists.base ? lists.base.main_cards : 0, 0)} Karten; aktuell: ${StudioUI.num(lists.target ? lists.target.lands : 0, 0)} Länder in ${StudioUI.num(lists.target ? lists.target.main_cards : 0, 0)} Karten (ohne Commander). ${mb.assumptions.delta}`)];
  if (reqRows.length) {
    nodes.push(h("div", { class: "table-wrap" }, h("table", { id: "diff-manabase" },
      head(["Anforderung", "Farben direkt* (Basis → aktuell)", "Delta mit Suchland*", "Delta auf Kurve"]),
      h("tbody", {}, reqRows))),
    h("p", { class: "note" }, "* Farben: Anteil mit den nötigen farbigen Quellen unter den Ziehungen mit genug Land-Drops bis zum Zug des Manawerts (Karsten 2022; jedes Farbsymbol braucht ein eigenes Land). „mit Suchland“ unter der Rechenannahme der Länderklassen. „Auf Kurve“ = Land-Drops und Farben zusammen, direkt."));
  }
  const hand = mb.opening_hand;
  if (hand) nodes.push(h("p", { id: "diff-opening-hand" }, `Spielbare Starthand (${hand.rule}): ${diffPct(hand.base)} → ${diffPct(hand.target)} (${diffPp(hand.delta_pp)}).`));
  const access = mb.colour_access || [];
  if (access.length) {
    const range = (low, high) => (low === null || low === undefined || high === null || high === undefined) ? "unbekannt" : (low === high ? diffPct(low) : `${diffPct(low)} – ${diffPct(high)}`);
    const rangePp = (low, high) => (low === null || low === undefined || high === null || high === undefined) ? "unbekannt" : (low === high ? diffPp(low) : `${diffPp(low)} / ${diffPp(high)}`);
    const cell = (base, target, deltaLow, deltaHigh, lowKey, highKey) => h("td", { class: "num" },
      `${range(base[lowKey], base[highKey])} → ${range(target[lowKey], target[highKey])} (${rangePp(deltaLow, deltaHigh)})`);
    nodes.push(h("h3", {}, "Ungetappte Quelle früh (Basis → aktuell)"),
      h("p", { id: "diff-access-note", class: "note warn" }, "Keine Grenze des Farbzugriffs: getappte Länder aus Zug 1, die in Zug 2 schon Mana geben, sind nicht gezählt. „Exakt“ gilt nur für das genannte Ereignis (ungetappte direkte Quelle); die zwei Werte sind Grenzen nur wegen bedingt getappter und unbekannter Länder."));
    nodes.push(h("div", { class: "table-wrap" }, h("table", { id: "diff-colour-access" },
      head(["Farbe", "Starthand (Basis → aktuell)", "ungetappte Quelle direkt Zug 1", "ungetappte Quelle direkt Zug 2"]),
      h("tbody", {}, access.map((item) => h("tr", {},
        h("td", {}, h("span", { class: "ms ms-" + item.colour }, item.colour), item.in_base && item.in_target ? "" : h("span", { class: "note" }, item.in_base ? " nur in Basis gebraucht" : " nur aktuell gebraucht")),
        cell(item.base, item.target, item.delta_pp.hand, item.delta_pp.hand_high, "hand", "hand_high"),
        cell(item.base, item.target, item.delta_pp.turn1_low, item.delta_pp.turn1_high, "turn1_low", "turn1_high"),
        cell(item.base, item.target, item.delta_pp.turn2_low, item.delta_pp.turn2_high, "turn2_low", "turn2_high")))))),
    h("p", { class: "note" }, h("strong", {}, mb.assumptions.access), " ", mb.assumptions.access_rule, " Zwei Werte: untere / obere Grenze."));
  }
  const tapped = mb.tapped;
  if (tapped) {
    const keys = ["immer_getappt", "bedingt_getappt", "ungetappt", "unbekannt"];
    const labels = { immer_getappt: "immer getappt", bedingt_getappt: "bedingt getappt", ungetappt: "ungetappt", unbekannt: "unbekannt" };
    nodes.push(h("div", { class: "table-wrap" }, h("table", { id: "diff-tapped" },
      head(["Getappt-Klasse (Regeltext)", "Basis", "aktuell", "Delta"]),
      h("tbody", {}, keys.map((key) => h("tr", {},
        h("td", {}, labels[key]),
        h("td", { class: "num" }, `${StudioUI.num(tapped.base[key], 0)} von ${StudioUI.num(tapped.base_of, 0)}`),
        h("td", { class: "num" }, `${StudioUI.num(tapped.target[key], 0)} von ${StudioUI.num(tapped.target_of, 0)}`),
        h("td", { class: "num" + (tapped.delta[key] ? " changed" : "") }, tapped.delta[key] ? diffSigned(tapped.delta[key]) : "0")))))));
  }
  const cmd = mb.commander;
  if (cmd && cmd.rows && cmd.rows.length) {
    nodes.push(h("div", { class: "table-wrap" }, h("table", { id: "diff-commander" },
      head(["Commander auf Kurve", "Basis", "aktuell", "Delta auf Kurve", "Delta Land-Drops", "Delta Farben"]),
      h("tbody", {}, cmd.rows.map((row) => h("tr", {},
        h("td", {}, row.name),
        h("td", { class: "num" }, row.base ? diffPct(row.base.p_on_curve) : "unbekannt"),
        h("td", { class: "num" }, row.target ? diffPct(row.target.p_on_curve) : "unbekannt"),
        ...(row.delta_pp
          ? [diffPpCell(h, row.delta_pp.p_on_curve), diffPpCell(h, row.delta_pp.p_land_drops), diffPpCell(h, row.delta_pp.p_colours_given_lands)]
          : [h("td", { colspan: 3, class: "note" }, cmd.same ? "unbekannt" : "kein Delta: anderer Commander")])))))));
  }
  return nodes;
}

function diffImpactNodes(h, diff, deps) {
  const nodes = [];
  deps = { ...deps, zahlen: StudioZahl.index(diff.zahlen) };
  const overlap = diff.overlap;
  if (overlap) {
    nodes.push(h("p", { id: "diff-overlap" }, `Gemeinsame Kartenplätze: ${StudioUI.num(overlap.shared_slots, 0)} von ${StudioUI.num(overlap.base_slots, 0)} (Basis) bzw. ${StudioUI.num(overlap.target_slots, 0)} (aktuell).`));
  }
  if (diff.curve_deltas) {
    const keys = ["0", "1", "2", "3", "4", "5", "6", "7"];
    nodes.push(h("h3", {}, "Manakurve (ohne Länder)"),
      h("div", { class: "table-wrap" }, h("table", { id: "diff-curve" },
        h("thead", {}, h("tr", {}, h("th", {}, "Manawert"), ...keys.map((key) => h("th", { class: "num" }, key === "7" ? "7+" : key)))),
        h("tbody", {},
          h("tr", {}, h("td", {}, "Basis"), ...keys.map((key) => h("td", { class: "num" }, StudioUI.num(diff.curve_deltas[key].base, 0)))),
          h("tr", {}, h("td", {}, "Aktuell"), ...keys.map((key) => h("td", { class: "num" }, StudioUI.num(diff.curve_deltas[key].target, 0)))),
          h("tr", {}, h("td", {}, "Delta"), ...keys.map((key) => {
            const delta = diff.curve_deltas[key].target - diff.curve_deltas[key].base;
            return h("td", { class: "num" + (delta ? " changed" : "") }, delta ? diffSigned(delta) : "0");
          }))))));
  }
  const colours = Object.entries(diff.colour_deltas || {});
  if (colours.length) {
    nodes.push(h("h3", {}, "Farben (Basis → aktuell)"),
      h("div", { class: "table-wrap" }, h("table", { id: "diff-colours" },
        h("thead", {}, h("tr", {}, h("th", {}, "Farbe"), h("th", { class: "num" }, "Symbole"), h("th", { class: "num" }, "Land-Quellen"))),
        h("tbody", {}, colours.map(([colour, item]) => h("tr", {},
          h("td", {}, h("span", { class: "ms ms-" + colour }, colour)),
          h("td", { class: "num" }, `${StudioUI.num(item.base_pips, 0)} → ${StudioUI.num(item.target_pips, 0)} (${diffSigned(item.target_pips - item.base_pips)})`),
          h("td", { class: "num" }, `${StudioUI.num(item.base_sources, 0)} → ${StudioUI.num(item.target_sources, 0)} (${diffSigned(item.target_sources - item.base_sources)})`)))))));
  }
  const combo = diff.combo_delta;
  if (combo) {
    const side = (complete, listed) => listed ? `${StudioUI.num(complete, 0)} von ${StudioUI.num(listed, 0)} gelisteten` : "unbekannt (keine Kombo-Liste)";
    const text = !combo.comparable
      ? `Anderer Commander – nicht vergleichbar. Je Seite gegen die eigene Liste: Basis ${side(combo.base_complete, combo.base_listed)}, aktuell ${side(combo.target_complete, combo.listed)}.`
      : combo.listed
        ? `Vollständige gelistete Kombos: ${StudioUI.num(combo.base_complete, 0)} → ${StudioUI.num(combo.target_complete, 0)} (von ${StudioUI.num(combo.listed, 0)} gelisteten)`
        : "Keine Kombo-Liste für diesen Commander gespeichert: Veränderung unbekannt.";
    nodes.push(h("h3", {}, "Kombos (gespeicherte Liste)"), h("p", { id: "diff-combos" }, text));
    if (combo.now_complete.length) nodes.push(h("p", {}, "Neu vollständig: " + combo.now_complete.map((cards) => cards.join(" + ")).join(" · ")));
    if (combo.no_longer_complete.length) nodes.push(h("p", {}, "Nicht mehr vollständig: " + combo.no_longer_complete.map((cards) => cards.join(" + ")).join(" · ")));
  }
  nodes.push(...diffManabaseNodes(h, diff.manabase));
  if (diff.added.length) nodes.push(...diffCardTable(h, `Hinzugefügt (+${StudioUI.num(diff.added.length, 0)})`, diff.added, (item) => "+" + StudioUI.num(item.quantity, 0), deps, "added"));
  if (diff.removed.length) nodes.push(...diffCardTable(h, `Entfernt (−${StudioUI.num(diff.removed.length, 0)})`, diff.removed, (item) => "−" + StudioUI.num(item.quantity, 0), deps, "removed"));
  if (diff.changed.length) nodes.push(...diffCardTable(h, "Mengenänderung", diff.changed, (item) => `${StudioUI.num(item.base_quantity, 0)}→${StudioUI.num(item.target_quantity, 0)}`, deps, "changed"));
  if (diff.commanders && !diff.commanders.same) nodes.push(h("p", { class: "note" }, `Anderer Commander: Häufigkeiten hinzugefügter Karten aus den Quelldecks von ${diff.commanders.target.join(" + ") || "–"}, entfernter Karten aus denen von ${diff.commanders.base.join(" + ") || "–"}.`));
  if (diff.cohort && diff.cohort.small) nodes.push(h("p", { class: "note warn" }, "Kleine Vergleichsgruppe (unter 30 Decks): " + [diff.cohort.decks, diff.cohort.base_decks].filter((n) => n !== null && n !== undefined).map((n) => StudioUI.num(n, 0)).join(" bzw. ") + " Decks."));
  nodes.push(h("p", { class: "note" }, "Nur gezählte Größen: Spielhäufigkeit heißt, wie viele Quelldecks des Commanders die Karte spielen – keine Aussage, ob ein Tausch besser ist. „unbekannt“: kein Quelldeck nennt die Karte."));
  return nodes;
}
