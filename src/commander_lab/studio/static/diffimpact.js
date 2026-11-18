"use strict";
// Counted deltas of the variant comparison (#1414, #1404 option 8): curve, colours, combos,
// overlap and, per swapped card, roles, mana value and source-deck frequency with n/N.
// No score and no verdict on a swap. Rendered from renderDiff in app.js.

function diffSigned(value) { return (Number(value) > 0 ? "+" : "") + StudioUI.num(value, 0); }

function diffCardTable(h, title, items, quantityText, deps) {
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
        h("td", { class: "num" }, freq(item))))))),
  ];
}

function diffImpactNodes(h, diff, deps) {
  const nodes = [];
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
  if (diff.added.length) nodes.push(...diffCardTable(h, `Hinzugefügt (+${StudioUI.num(diff.added.length, 0)})`, diff.added, (item) => "+" + StudioUI.num(item.quantity, 0), deps));
  if (diff.removed.length) nodes.push(...diffCardTable(h, `Entfernt (−${StudioUI.num(diff.removed.length, 0)})`, diff.removed, (item) => "−" + StudioUI.num(item.quantity, 0), deps));
  if (diff.changed.length) nodes.push(...diffCardTable(h, "Mengenänderung", diff.changed, (item) => `${StudioUI.num(item.base_quantity, 0)}→${StudioUI.num(item.target_quantity, 0)}`, deps));
  if (diff.commanders && !diff.commanders.same) nodes.push(h("p", { class: "note" }, `Anderer Commander: Häufigkeiten hinzugefügter Karten aus den Quelldecks von ${diff.commanders.target.join(" + ") || "–"}, entfernter Karten aus denen von ${diff.commanders.base.join(" + ") || "–"}.`));
  if (diff.cohort && diff.cohort.small) nodes.push(h("p", { class: "note warn" }, "Kleine Vergleichsgruppe (unter 30 Decks): " + [diff.cohort.decks, diff.cohort.base_decks].filter((n) => n !== null && n !== undefined).map((n) => StudioUI.num(n, 0)).join(" bzw. ") + " Decks."));
  nodes.push(h("p", { class: "note" }, "Nur gezählte Größen: Spielhäufigkeit heißt, wie viele Quelldecks des Commanders die Karte spielen – keine Aussage, ob ein Tausch besser ist. „unbekannt“: kein Quelldeck nennt die Karte."));
  return nodes;
}
