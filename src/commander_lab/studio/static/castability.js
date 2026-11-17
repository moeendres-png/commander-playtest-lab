"use strict";
// Colour castability (#1415, #1404 option 2): exact, conditioned on land drops (Karsten).
// Every probability names its condition; no land count advice. Rendered from renderNumbers.

function castPct(value) { return value === null || value === undefined ? "unbekannt" : StudioUI.pct(value, 1); }

// Starting-hand chance per role (#1404): P(>= 1 card of the role) in 7 cards and after 1-3 more.
function handRoleNodes(h, hr, roleName) {
  const head = ["Start", "Zug 1", "Zug 2", "Zug 3"];
  const out = [h("h3", {}, "Rollen in der Starthand"),
    h("p", { class: "note" }, `Rollendaten bei ${StudioUI.num(hr.cards_with_role_data)} von ${StudioUI.num(hr.library)} Karten im Deck (Nichtland: ${StudioUI.num(hr.nonland_with_role_data)} von ${StudioUI.num(hr.nonland_cards)}). ${hr.assumption}`)];
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
    h("table", { id: "hand-roles" },
      h("thead", {}, h("tr", {}, h("th", {}, "Rolle"),
        ...head.map((text) => h("th", { class: "num", title: "Start 7 Karten, Zug 1 8, Zug 2 9, Zug 3 10 (Ziehen in Zug 1)" }, text)))),
      h("tbody", {}, rows)),
    h("p", { class: "note" }, "Karten in der Hand: Start 7, nach Zug 1 8, Zug 2 9, Zug 3 10. Je Rolle: obere Zeile mindestens eine Karte der Rolle, untere Zeile keine Karte der Rolle (zusammen 100 %, durch Rundung bis 0,1 Prozentpunkt Abweichung). Rollen sind öffentliche Marken (Tagger); eine Karte zählt für jede ihrer Rollen.")];
}

function castabilityNodes(h, data, open, roleName) {
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
    ...(data.hand_roles ? handRoleNodes(h, data.hand_roles, roleName || ((key) => key)) : []),
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
    box.replaceChildren(...castabilityNodes(h, data, deps.open, deps.roleName));
  } catch (error) {
    if (!deps.isCurrent(token)) return;
    box.replaceChildren(h("p", { class: "warn" }, "Die Farb-Wahrscheinlichkeiten konnten nicht berechnet werden."));
    deps.fail(error);
  }
}
