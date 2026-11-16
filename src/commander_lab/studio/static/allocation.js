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
  const text = ` · in ${entry.decks.length} ${entry.decks.length === 1 ? "Deck" : "Decks"} (${entry.bound} gebunden)`;
  return entry.overbooked
    ? h("span", { class: "warn overbooked", title: `Gebunden ${entry.bound}, frei ${entry.available}: überbucht (Daten-Hinweis, keine Sperre)` }, text + " · überbucht")
    : h("span", { title: entry.decks.map((item) => `${item.deck_name} (${item.branch}): ${item.quantity}`).join("\n") }, text);
}

function allocationDetail(h, card) {
  const data = StudioAllocation.data;
  if (!data) return "";
  const entry = allocationOf(card.card_id);
  const parts = [h("h3", {}, "Belegung")];
  if (!entry || !entry.decks.length) {
    parts.push(h("p", { id: "allocation-free" }, `In keinem gespeicherten Deck gebunden (${card.available} frei).`));
  } else {
    parts.push(h("p", { id: "allocation-summary", class: entry.overbooked ? "warn" : "" },
      `${entry.bound} gebunden von ${entry.available === null ? "unbekannt" : entry.available} freien Exemplaren` + (entry.overbooked ? " – überbucht (Daten-Hinweis, kein Deck wird geändert)." : ".")));
    parts.push(h("ul", { id: "allocation-decks" }, entry.decks.map((item) => h("li", {}, `${item.quantity}× in „${item.deck_name}“ (Variante ${item.branch}, Stand ${item.revision_id})`))));
  }
  if (entry && entry.other_variants.length) {
    parts.push(h("p", { class: "note" }, "Auch in weiteren Varianten (Alternativen, binden nichts): " + entry.other_variants.map((item) => `„${item.deck_name}“ ${item.branch} (${item.quantity}×)`).join(", ")));
  }
  if (card.reserved) parts.push(h("p", { class: "note" }, `${card.reserved} Exemplar(e) sind für Gegner-Decks reserviert und zählen nicht zu den freien.`));
  if (entry && entry.locations) {
    parts.push(h("p", { id: "allocation-locations" }, "Standort laut Sammlungsdatei: " + entry.locations.map((item) => `${item.quantity}× ${item.name}`).join(", ")));
  }
  parts.push(h("p", { class: "note" }, data.binding_rule));
  return h("div", { class: "allocation" }, ...parts);
}
