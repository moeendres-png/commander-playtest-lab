"use strict";
// Counted deltas of the variant comparison (#1414, #1404 option 8): curve, colours, combos,
// overlap and, per swapped card, roles, mana value and source-deck frequency with n/N.
// No score and no verdict on a swap. Rendered from renderDiff in app.js.

function diffSigned(value) { return (value > 0 ? "+" : "") + value; }

function diffCardTable(h, title, items, quantityText, deps) {
  const freq = (item) => {
    if (item.of === null || item.of === undefined) return "keine Quelldecks";
    if (item.decks === null || item.decks === undefined) return `unbekannt / ${item.of}`;
    return `${item.decks} / ${item.of}` + (item.of ? ` (${(100 * item.decks / item.of).toFixed(1).replace(".", ",")} %)` : "");
  };
  return [
    h("h3", {}, title),
    h("table", { class: "diff-cards" },
      h("thead", {}, h("tr", {}, h("th", { class: "num" }, "Anzahl"), h("th", {}, "Karte"), h("th", { class: "num" }, "MW"),
        h("th", {}, "Rollen"), h("th", { class: "num" }, `Quelldecks (${deps.cohortLabel})`))),
      h("tbody", {}, items.map((item) => h("tr", {},
        h("td", { class: "num" }, quantityText(item)),
        h("td", {}, h("a", { href: "#", class: "nm", onclick: (event) => { event.preventDefault(); deps.open(item.card_id); } }, item.name)),
        h("td", { class: "num" }, item.mana_value === null || item.mana_value === undefined ? "unbekannt" : String(item.mana_value)),
        h("td", {}, item.roles && item.roles.length ? item.roles.map(deps.roleName).join(", ") : h("span", { class: "muted" }, "keine Rolle")),
        h("td", { class: "num" }, freq(item)))))),
  ];
}

function diffImpactNodes(h, diff, deps) {
  const nodes = [];
  const overlap = diff.overlap;
  if (overlap) {
    nodes.push(h("p", { id: "diff-overlap" }, `Gemeinsame Kartenplätze: ${overlap.shared_slots} von ${overlap.base_slots} (Basis) bzw. ${overlap.target_slots} (aktuell).`));
  }
  if (diff.curve_deltas) {
    const keys = ["0", "1", "2", "3", "4", "5", "6", "7"];
    nodes.push(h("h3", {}, "Manakurve (ohne Länder)"),
      h("table", { id: "diff-curve" },
        h("thead", {}, h("tr", {}, h("th", {}, "Manawert"), ...keys.map((key) => h("th", { class: "num" }, key === "7" ? "7+" : key)))),
        h("tbody", {},
          h("tr", {}, h("td", {}, "Basis"), ...keys.map((key) => h("td", { class: "num" }, diff.curve_deltas[key].base))),
          h("tr", {}, h("td", {}, "Aktuell"), ...keys.map((key) => h("td", { class: "num" }, diff.curve_deltas[key].target))),
          h("tr", {}, h("td", {}, "Delta"), ...keys.map((key) => {
            const delta = diff.curve_deltas[key].target - diff.curve_deltas[key].base;
            return h("td", { class: "num" + (delta ? " changed" : "") }, delta ? diffSigned(delta) : "0");
          })))));
  }
  const colours = Object.entries(diff.colour_deltas || {});
  if (colours.length) {
    nodes.push(h("h3", {}, "Farben (Basis → aktuell)"),
      h("table", { id: "diff-colours" },
        h("thead", {}, h("tr", {}, h("th", {}, "Farbe"), h("th", { class: "num" }, "Symbole"), h("th", { class: "num" }, "Land-Quellen"))),
        h("tbody", {}, colours.map(([colour, item]) => h("tr", {},
          h("td", {}, h("span", { class: "ms ms-" + colour }, colour)),
          h("td", { class: "num" }, `${item.base_pips} → ${item.target_pips} (${diffSigned(item.target_pips - item.base_pips)})`),
          h("td", { class: "num" }, `${item.base_sources} → ${item.target_sources} (${diffSigned(item.target_sources - item.base_sources)})`))))));
  }
  const combo = diff.combo_delta;
  if (combo) {
    const side = (complete, listed) => listed ? `${complete} von ${listed} gelisteten` : "unbekannt (keine Kombo-Liste)";
    const text = !combo.comparable
      ? `Anderer Commander – nicht vergleichbar. Je Seite gegen die eigene Liste: Basis ${side(combo.base_complete, combo.base_listed)}, aktuell ${side(combo.target_complete, combo.listed)}.`
      : combo.listed
        ? `Vollständige gelistete Kombos: ${combo.base_complete} → ${combo.target_complete} (von ${combo.listed} gelisteten)`
        : "Keine Kombo-Liste für diesen Commander gespeichert: Veränderung unbekannt.";
    nodes.push(h("h3", {}, "Kombos (gespeicherte Liste)"), h("p", { id: "diff-combos" }, text));
    if (combo.now_complete.length) nodes.push(h("p", {}, "Neu vollständig: " + combo.now_complete.map((cards) => cards.join(" + ")).join(" · ")));
    if (combo.no_longer_complete.length) nodes.push(h("p", {}, "Nicht mehr vollständig: " + combo.no_longer_complete.map((cards) => cards.join(" + ")).join(" · ")));
  }
  if (diff.added.length) nodes.push(...diffCardTable(h, `Hinzugefügt (+${diff.added.length})`, diff.added, (item) => "+" + item.quantity, deps));
  if (diff.removed.length) nodes.push(...diffCardTable(h, `Entfernt (−${diff.removed.length})`, diff.removed, (item) => "−" + item.quantity, deps));
  if (diff.changed.length) nodes.push(...diffCardTable(h, "Mengenänderung", diff.changed, (item) => `${item.base_quantity}→${item.target_quantity}`, deps));
  if (diff.commanders && !diff.commanders.same) nodes.push(h("p", { class: "note" }, `Anderer Commander: Häufigkeiten hinzugefügter Karten aus den Quelldecks von ${diff.commanders.target.join(" + ") || "–"}, entfernter Karten aus denen von ${diff.commanders.base.join(" + ") || "–"}.`));
  if (diff.cohort && diff.cohort.small) nodes.push(h("p", { class: "note warn" }, "Kleine Vergleichsgruppe (unter 30 Decks): " + [diff.cohort.decks, diff.cohort.base_decks].filter((n) => n !== null && n !== undefined).join(" bzw. ") + " Decks."));
  nodes.push(h("p", { class: "note" }, "Nur gezählte Größen: Spielhäufigkeit heißt, wie viele Quelldecks des Commanders die Karte spielen – keine Aussage, ob ein Tausch besser ist. „unbekannt“: kein Quelldeck nennt die Karte."));
  return nodes;
}
