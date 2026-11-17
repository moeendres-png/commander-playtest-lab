"use strict";
// Card allocation (#1419): copies bound by saved decks, overbooking and storage locations.
// Display only; nothing is locked. Loaded by app.js (loadAllocation) and shown on the pool
// tiles (allocationTileNote) and in the card window (allocationDetail).

const StudioAllocation = { data: null };

async function loadAllocation(api) {
  try {
    StudioAllocation.data = await api("/api/allocation");
  } catch (error) {
    StudioAllocation.data = null; // the tiles simply show no binding then
  }
}

function allocationOf(cardId) {
  return StudioAllocation.data && StudioAllocation.data.cards ? StudioAllocation.data.cards[cardId] || null : null;
}

function allocationTileNote(h, card) {
  const entry = allocationOf(card.card_id);
  if (!entry || !entry.decks.length) return "";
  const text = ` · in ${StudioUI.num(entry.decks.length, 0)} ${entry.decks.length === 1 ? "Deck" : "Decks"} (${StudioUI.num(entry.bound, 0)} gebunden)`;
  return entry.overbooked
    ? h("span", { class: "warn overbooked", title: `Gebunden ${StudioUI.num(entry.bound, 0)}, frei ${StudioUI.num(entry.available, 0)}: überbucht (Daten-Hinweis, keine Sperre)` }, text + " · überbucht")
    : h("span", { title: entry.decks.map((item) => `${item.deck_name} (${item.branch}): ${StudioUI.num(item.quantity, 0)}`).join("\n") }, text);
}

function allocationDetail(h, card) {
  const data = StudioAllocation.data;
  if (!data) return "";
  const entry = allocationOf(card.card_id);
  const parts = [h("h3", {}, "Belegung")];
  if (!entry || !entry.decks.length) {
    parts.push(h("p", { id: "allocation-free" }, `In keinem gespeicherten Deck gebunden (${StudioUI.num(card.available, 0)} frei).`));
  } else {
    parts.push(h("p", { id: "allocation-summary", class: entry.overbooked ? "warn" : "" },
      `${StudioUI.num(entry.bound, 0)} gebunden von ${entry.available === null ? "unbekannt" : StudioUI.num(entry.available, 0)} freien Exemplaren` + (entry.overbooked ? " – überbucht (Daten-Hinweis, kein Deck wird geändert)." : ".")));
    parts.push(h("ul", { id: "allocation-decks" }, entry.decks.map((item) => h("li", {}, `${StudioUI.num(item.quantity, 0)}× in „${item.deck_name}“ (Variante ${item.branch}, Stand ${item.revision_id})`))));
  }
  if (entry && entry.other_variants.length) {
    parts.push(h("p", { class: "note" }, "Auch in weiteren Varianten (Alternativen, binden nichts): " + entry.other_variants.map((item) => `„${item.deck_name}“ ${item.branch} (${StudioUI.num(item.quantity, 0)}×)`).join(", ")));
  }
  if (card.reserved) parts.push(h("p", { class: "note" }, `${StudioUI.num(card.reserved, 0)} Exemplar(e) sind für Gegner-Decks reserviert und zählen nicht zu den freien.`));
  if (entry && entry.locations) {
    const located = entry.locations.reduce((sum, item) => sum + item.quantity, 0);
    const allExact = entry.locations.every((item) => item.exact && !item.unknown_lots);
    const text = (item) => (item.exact ? `${StudioUI.num(item.quantity, 0)}×` : `mindestens ${StudioUI.num(item.quantity, 0)}×`) + ` ${item.name}` + (item.unknown_lots ? ` (+ ${StudioUI.num(item.unknown_lots, 0)} Posten ohne Anzahl)` : "");
    parts.push(h("p", { id: "allocation-locations" }, `Standort laut Sammlungsdatei (${allExact ? "" : "mindestens "}${StudioUI.num(located, 0)} von ${StudioUI.num(card.owned, 0)} Exemplaren zugeordnet): ` + entry.locations.map(text).join(", ")));
  }
  parts.push(h("p", { class: "note" }, data.binding_rule));
  return h("div", { class: "allocation" }, ...parts);
}
