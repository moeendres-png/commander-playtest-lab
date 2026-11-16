"use strict";
// Card duel in the card window (#1404 option 3, "A oder B?"): two cards side by side with roles,
// mana value, source-deck frequency n/N and the observed fit with the rest of the deck against
// the group's baseline. An observation, never "better". Rendered from app.js (openCard).

function duelPct(value) { return value === null || value === undefined ? "unbekannt" : (100 * value).toFixed(1) + " %"; }

function duelTable(h, data, deps) {
  const a = data.a, b = data.b;
  const freq = (side) => side.decks === null ? `unbekannt / ${side.of}` : `${side.decks} / ${side.of} (${duelPct(side.share)})`;
  const fit = (side) => side.fit === null ? "unbekannt (kein Quelldeck spielt die Karte)" : `${duelPct(side.fit)} in ${side.fit_decks} Decks` + (side.small ? " · kleine Gruppe" : "");
  const roles = (side) => side.roles.length ? side.roles.map(deps.roleName).join(", ") : "keine Rolle bekannt";
  const row = (label, left, right) => h("tr", {}, h("th", { scope: "row" }, label), h("td", {}, left), h("td", {}, right));
  return h("table", { id: "duel-table" },
    h("thead", {}, h("tr", {}, h("th", {}, ""), h("th", {}, a.name), h("th", {}, b.name))),
    h("tbody", {},
      row("Im Deck", a.in_deck ? "ja" : "nein", b.in_deck ? "ja" : "nein"),
      row("Typ", deps.groupName(a.group), deps.groupName(b.group)),
      row("Manawert", a.mana_value === null ? "unbekannt" : String(a.mana_value), b.mana_value === null ? "unbekannt" : String(b.mana_value)),
      row("Rollen", roles(a), roles(b)),
      row("Spielen sie (Quelldecks)", freq(a), freq(b)),
      row("Passung zu deinen übrigen Karten", fit(a), fit(b))));
}

function renderDuelBox(into, card, deps) {
  const { h } = deps;
  const candidates = deps.pool().filter((other) => other.card_id !== card.card_id && !other.basic);
  const listId = "duel-list";
  const input = h("input", { type: "search", list: listId, placeholder: "Karte zum Vergleich", "aria-label": "Karte für das Karten-Duell" });
  const out = h("div", { id: "duel-result" });
  let request = 0; // only the newest comparison may fill the box
  const run = async () => {
    const mine = ++request;
    const other = candidates.find((entry) => entry.name === input.value);
    if (!other) { out.replaceChildren(h("p", { class: "muted" }, "Bitte eine Karte aus dem Pool wählen.")); return; }
    out.replaceChildren(h("p", { class: "muted" }, "Wird verglichen …"));
    try {
      const data = await deps.api("/api/card-duel", "POST", { commander: deps.commander, deck_card_ids: deps.deckCardIds(), card_a: card.card_id, card_b: other.card_id, cohort: deps.cohort() });
      if (mine !== request) return;
      out.replaceChildren(
        duelTable(h, data, deps),
        h("p", { class: "note" }, `Grundwert: Ø ${duelPct(data.baseline)} deiner ${data.other_cards} übrigen Karten je Quelldeck in „${deps.cohortLabel()}“ (${data.cohort.decks} Decks${data.cohort.small ? ", kleine Gruppe" : ""}).` + (data.shared_roles.length ? ` Gemeinsame Rollen: ${data.shared_roles.map(deps.roleName).join(", ")}.` : " Keine gemeinsame Rolle.")),
        h("p", { class: "note" }, data.meaning));
    } catch (error) { if (mine !== request) return; out.replaceChildren(h("p", { class: "warn" }, "Das Duell konnte nicht berechnet werden.")); deps.fail(error); }
  };
  into.replaceChildren(
    h("h3", {}, "Karten-Duell"),
    h("datalist", { id: listId }, candidates.slice(0, 1500).map((entry) => h("option", { value: entry.name }))),
    h("div", { class: "actions" }, input, h("button", { type: "button", id: "duel-run", onclick: run }, "Vergleichen")),
    out);
}
