"use strict";
// Colour castability (#1415, #1404 option 2): exact, conditioned on land drops (Karsten).
// Every probability names its condition; no land count advice. Rendered from renderNumbers.

function castPct(value) { return value === null || value === undefined ? "unbekannt" : StudioUI.pct(value, 1); }

function castabilityNodes(h, data, open) {
  const pipLabel = (label) => h("span", {}, ...label.split("").map((letter) => h("span", { class: "ms ms-" + letter }, letter)));
  const names = (cards) => h("span", {}, ...cards.flatMap((card, index) => [index ? ", " : "",
    h("a", { href: "#", class: "nm", onclick: (event) => { event.preventDefault(); open(card.card_id); } }, card.name)]));
  const rows = data.requirements.flatMap((item) => [
    h("tr", { class: "facts-row" },
      h("td", { class: "nowrap" }, pipLabel(item.label), ` Zug ${item.turn}`),
      h("td", { class: "num" }, Object.entries(item.sources).map(([colour, count]) => `${colour} ${count}`).join(" · ")),
      h("td", { class: "num", title: `mindestens ${item.turn} Länder unter ${item.draws} Karten` }, castPct(item.p_land_drops)),
      h("td", { class: "num", title: item.condition }, castPct(item.p_colours_given_lands))),
    h("tr", { class: "facts-basis" }, h("td", { colspan: 4, class: "note" }, names(item.cards))),
  ]);
  const hand = data.opening_hand;
  const notes = [];
  if (data.lands_without_coloured_mana) notes.push(`${data.lands_without_coloured_mana} Länder erzeugen laut Kartendaten kein farbiges Mana (z. B. Fetch-Länder) und zählen nicht als Quelle.`);
  if (data.lands_unknown_colours) notes.push(`${data.lands_unknown_colours} Länder ohne Kartendaten: Farben unbekannt, nicht als Quelle gezählt – die Farbwerte sind darum eher zu niedrig.`);
  if (data.cards_unknown_mana_value) notes.push(`${data.cards_unknown_mana_value} Karten mit unbekanntem Manawert: ohne eigene Farbanforderung, in den Ziehungen als Karten ohne frühe Aktion gezählt.`);
  if (data.hybrid_or_phyrexian_cards.length) notes.push(`Hybrid- und Phyrexia-Symbole nicht eingerechnet bei: ${data.hybrid_or_phyrexian_cards.join(", ")}.`);
  return [
    h("h3", {}, "Farben auf Kurve (bedingt auf Land-Drops)"),
    h("p", { class: "note" }, `Je Farbanforderung: Wahrscheinlichkeit, bis zum Zug des Manawerts genug Länder zu haben (Land-Drops), und – nur unter diesen Ziehungen – die nötigen Quellen der Farbe(n). ${data.lands} Länder in ${data.main_cards} Karten.`),
    h("table", { id: "castability" },
      h("thead", {}, h("tr", {}, h("th", {}, "Kosten"), h("th", { class: "num" }, "Quellen"),
        h("th", { class: "num" }, "Land-Drops"), h("th", { class: "num", title: "nur unter den Ziehungen mit genug Land-Drops" }, "Farben*"))),
      h("tbody", {}, rows)),
    h("p", { class: "note" }, "* Farben: Anteil mit den nötigen farbigen Quellen unter den Ziehungen, die bis zum Zug genug Länder haben. Quellen: nur Länder."),
    h("p", { id: "opening-hand" }, `Spielbare Starthand (${hand.rule}): ${castPct(hand.p_keepable)} – aus ${hand.lands} Ländern, ${hand.early_actions} frühen Aktionen und ${hand.other_cards} weiteren Karten, 7 Karten, ohne Mulligan.`),
    notes.length ? h("ul", { class: "note" }, notes.map((text) => h("li", {}, text))) : "",
    h("p", { class: "note" }, data.method + " ", h("a", { href: data.source, target: "_blank", rel: "noreferrer noopener", referrerpolicy: "no-referrer" }, "Methodik (Karsten 2022)")),
  ];
}

// deps: { h, api, entries, fail, open(card_id), token(), isCurrent(token) }
async function renderCastability(body, deps) {
  const { h } = deps;
  const box = h("div", { id: "castability-box" }, h("p", { class: "muted" }, "Farben auf Kurve werden berechnet …"));
  body.append(box);
  const token = deps.token();
  try {
    const data = await deps.api("/api/castability", "POST", { cards: deps.entries() });
    if (!deps.isCurrent(token)) return;
    box.replaceChildren(...castabilityNodes(h, data, deps.open));
  } catch (error) {
    if (!deps.isCurrent(token)) return;
    box.replaceChildren(h("p", { class: "warn" }, "Die Farb-Wahrscheinlichkeiten konnten nicht berechnet werden."));
    deps.fail(error);
  }
}
