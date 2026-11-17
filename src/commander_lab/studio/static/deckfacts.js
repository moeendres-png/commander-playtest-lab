"use strict";
// Deck facts tab of the builder (#1404 options 1 and 10): the bracket check and the data gaps
// of the current list. Counts with names and their origin, never a verdict; unknown stays
// "unbekannt", never 0. Rendered by app.js through renderDeckFacts(body, deps).

const DECK_FACTS_LIMIT_TEXT = { passt: "passt", "über der Grenze": "über der Grenze", unbekannt: "unbekannt (Game-Changer-Feld fehlt)" };

function deckFactsNames(h, items, open) {
  if (!items || !items.length) return h("span", { class: "muted" }, "–");
  return h("span", {}, ...items.flatMap((item, index) => [
    index ? ", " : "",
    h("a", { href: "#", class: "nm", onclick: (event) => { event.preventDefault(); open(item.card_id); } },
      item.name + (item.quantity > 1 ? ` (${item.quantity}×)` : "") + (item.rule ? ` – ${item.rule}` : "")),
  ]));
}

function renderBracketFacts(h, bracket, open) {
  const gc = bracket.game_changers;
  const tut = bracket.tutors;
  const combos = bracket.two_card_combos;
  const gcCount = `${gc.count} von ${gc.of} Karten` + (gc.unknown ? ` (dazu ${gc.unknown} unbekannt)` : "");
  const tutCount = `${tut.count} von ${tut.of} Nicht-Land-Karten` + (tut.land_search ? ` (davon ${tut.land_search} Land-Suche)` : "");
  const textCount = (group) => `${group.count} von ${group.of} Karten mit Kartentext` + (group.text_unknown ? ` (${group.text_unknown} ohne Kartentext: unbekannt)` : "");
  const gcNames = gc.unknown_cards && gc.unknown_cards.length
    ? h("span", {}, deckFactsNames(h, gc.cards, open), h("br"), h("span", { class: "muted" }, "unbekannt: "), deckFactsNames(h, gc.unknown_cards, open))
    : deckFactsNames(h, gc.cards, open);
  const comboCount = combos.count === null ? "unbekannt (keine Kombo-Liste gespeichert)" : `${combos.count} von ${combos.listed} gelisteten Kombos`;
  const comboNames = combos.combos && combos.combos.length
    ? h("span", {}, combos.combos.map((item) => item.cards.join(" + ")).join(" · "))
    : h("span", { class: "muted" }, "–");
  const row = (label, count, names, method, note) => [
    h("tr", { class: "facts-row" }, h("td", {}, h("b", {}, label)), h("td", { class: "num" }, count), h("td", {}, names)),
    h("tr", { class: "facts-basis" }, h("td", { colspan: 3, class: "note" }, "Grundlage: " + method + (note ? ` · ${note}` : ""))),
  ];
  const table = h("table", { id: "bracket-facts" },
    h("thead", {}, h("tr", {}, h("th", {}, "Gruppe"), h("th", { class: "num" }, "Anzahl"), h("th", {}, "Karten"))),
    h("tbody", {},
      ...row("Game Changer", gcCount, gcNames, gc.method, ""),
      ...row("Extrazüge", textCount(bracket.extra_turns), deckFactsNames(h, bracket.extra_turns.cards, open), bracket.extra_turns.method, bracket.extra_turns.note),
      ...row("Massen-Landzerstörung", textCount(bracket.mass_land_denial), deckFactsNames(h, bracket.mass_land_denial.cards, open), bracket.mass_land_denial.method, bracket.mass_land_denial.note),
      ...row("Tutoren", tutCount, deckFactsNames(h, tut.cards, open), `${tut.method}; Rollen-Daten für ${tut.role_data.with_roles} von ${tut.role_data.of} Nicht-Land-Karten (ohne Rolle: unbekannt)`, tut.note),
      ...row("2-Karten-Kombos", comboCount, comboNames, combos.method, combos.note)));
  const limits = h("table", { id: "bracket-limits" },
    h("thead", {}, h("tr", {}, h("th", {}, "Bracket"), h("th", { class: "num" }, "Game Changer erlaubt"), h("th", {}, "Dein Deck"))),
    h("tbody", {}, gc.limits.map((item) => h("tr", {},
      h("td", {}, item.bracket), h("td", { class: "num" }, item.limit === null ? "ohne Grenze" : `höchstens ${item.limit}`),
      h("td", { class: item.status === "über der Grenze" ? "warn" : "" }, DECK_FACTS_LIMIT_TEXT[item.status] || item.status)))));
  const sources = h("p", { class: "note" }, "Quellen: ", ...bracket.sources.flatMap((source, index) => [
    index ? " · " : "", h("a", { href: source.url, target: "_blank", rel: "noreferrer noopener", referrerpolicy: "no-referrer" }, source.title)]));
  return [
    h("h3", {}, "Bracket-Fakten"),
    h("p", { class: "note" }, bracket.meaning),
    table,
    h("h4", {}, "Veröffentlichte Game-Changer-Grenzen"),
    limits,
    sources,
  ];
}

const DECK_FACTS_COHORT_TEXT = { tuned: "Bracket 4 und 5", all: "alle Quelldecks" };

function thinText(thin) {
  return "dünn belegt (" + thin.map((t) => `${t.n} von ${t.of} in Gruppe ${DECK_FACTS_COHORT_TEXT[t.cohort] || t.cohort}`).join("; ") + ")";
}

function renderDataGaps(h, gaps, open) {
  const labels = gaps.reason_labels;
  const reasonRows = Object.entries(gaps.by_reason).map(([key, value]) => h("tr", {},
    h("td", {}, labels[key] || key), h("td", { class: "num" }, `${value.count} / ${value.of}`)));
  const thinCount = gaps.cards_with_thin ? ` Dazu ${gaps.cards_with_thin} Karten dünn belegt (Hinweis auf die Stichprobe, keine fehlende Angabe).` : "";
  const missing = (gaps.sources_missing || []).map((key) => h("li", {}, `${labels[key] || key}: für diesen Commander ist keine solche Quelle im Store – für alle Karten unbekannt.`));
  const list = gaps.gaps.length
    ? h("table", { id: "data-gaps-list" },
      h("thead", {}, h("tr", {}, h("th", {}, "Karte"), h("th", {}, "Was fehlt"))),
      h("tbody", {}, gaps.gaps.map((item) => h("tr", {},
        h("td", {}, h("a", { href: "#", class: "nm", onclick: (event) => { event.preventDefault(); open(item.card_id); } }, item.name)),
        h("td", {}, item.reasons.map((key) => labels[key] || key).concat(item.thin && item.thin.length ? [thinText(item.thin)] : []).join(" · "))))))
    : h("p", { class: "muted", id: "data-gaps-none" }, "Zu keiner Karte fehlen geprüfte Daten.");
  return [
    h("h3", {}, "Datenlücken"),
    h("p", { id: "data-gaps-summary" }, `${gaps.cards_with_gaps} von ${gaps.cards_checked} Karten (ohne Commander) mit mindestens einer Lücke.` + thinCount),
    h("table", { id: "data-gaps-reasons" }, h("thead", {}, h("tr", {}, h("th", {}, "Grund"), h("th", { class: "num" }, "Karten / geprüft"))), h("tbody", {}, reasonRows)),
    missing.length ? h("ul", { class: "note" }, missing) : "",
    list,
    h("p", { class: "note" }, gaps.meaning),
  ];
}

// deps: { h, api, entries, open(card_id), token(), isCurrent(token) }
async function renderDeckFacts(body, deps) {
  const { h } = deps;
  const box = h("div", { id: "deck-facts" }, h("p", { class: "muted" }, "Wird berechnet …"));
  body.append(box);
  const token = deps.token();
  try {
    const facts = await deps.api("/api/deck-facts", "POST", { cards: deps.entries() });
    if (!deps.isCurrent(token)) return;
    box.replaceChildren(...renderBracketFacts(h, facts.bracket, deps.open), ...renderDataGaps(h, facts.data_gaps, deps.open));
  } catch (error) {
    if (!deps.isCurrent(token)) return;
    box.replaceChildren(h("p", { class: "warn" }, "Die Deck-Fakten konnten nicht berechnet werden."));
    deps.fail(error);
  }
}
