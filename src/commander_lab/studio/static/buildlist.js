"use strict";
// Build list by storage location (#1404): the deck's cards grouped by where they lie, to put
// a deck together physically. Facts only: counts with their origin, unknown stays "Standort
// unbekannt", never 0; no rating; marks are not read. The tick boxes live only in
// this browser (localStorage, per deck state). Opened from the export dialog by app.js.

const BUILD_LIST_NF = new Intl.NumberFormat("de-DE");

function buildListDigest(entries) {
  // An unsaved draft has no revision: its ticks are keyed by the list itself, so two drafts never share them.
  const text = entries.map((e) => `${e.card_id}:${e.zone}:${e.quantity}`).sort().join("|");
  let hash = 5381;
  for (let i = 0; i < text.length; i += 1) hash = ((hash * 33) ^ text.charCodeAt(i)) >>> 0;
  return hash.toString(16);
}
function buildListKey(deps) {
  const revision = deps.state.baseRevision && !deps.state.dirty ? deps.state.baseRevision : `entwurf-${buildListDigest(deps.entries())}`;
  return `buildlist:${deps.state.deckId || "entwurf"}:${revision}`;
}
function buildListTickId(group, item) {
  return `${group.location_id === null ? "unknown" : group.location_id}:${item.card_id}`;
}
function buildListLoadTicks(key) {
  try { return new Set(JSON.parse(localStorage.getItem(key) || "[]")); } catch (error) { return new Set(); }
}
function buildListSaveTicks(key, ticks) {
  try { localStorage.setItem(key, JSON.stringify([...ticks])); } catch (error) { /* only a convenience */ }
}

function buildListAmount(item) {
  const part = item.needed !== item.quantity ? `${BUILD_LIST_NF.format(item.quantity)} von ${BUILD_LIST_NF.format(item.needed)}×` : `${BUILD_LIST_NF.format(item.quantity)}×`;
  if (item.exact === false) return `${part} (Bestand mindestens${item.unknown_lots ? `, + ${item.unknown_lots} Posten ohne Anzahl` : ""})`;
  return part;
}

function buildListGroupTitle(data, group) {
  return `${group.name} (${BUILD_LIST_NF.format(group.count)} ${group.count === 1 ? "Karte" : "Karten"})`;
}

function buildListText(data, deckName) {
  const lines = [`Bauliste ${deckName} (${BUILD_LIST_NF.format(data.totals.list_size)} Karten)`, ""];
  if (data.commander.length) {
    lines.push(`Commander (${data.commander.length})`);
    for (const item of data.commander) lines.push(`1 ${item.name}` + (item.placements.length ? ` – ${item.placements.map((p) => p.name).join(", ")}` : " – Standort unbekannt") + (item.note ? ` – ${item.note}` : ""));
    lines.push("");
  }
  for (const group of data.groups) {
    lines.push(`${buildListGroupTitle(data, group)}`);
    for (const item of group.cards) lines.push(`${item.quantity} ${item.name}` + (item.exact === false ? " (Bestand mindestens)" : "") + (item.note ? ` – ${item.note}` : ""));
    lines.push("");
  }
  if (data.basic_lands.cards.length) {
    lines.push(`Standardländer (${BUILD_LIST_NF.format(data.basic_lands.count)} Karten)`);
    for (const item of data.basic_lands.cards) lines.push(`${item.quantity} ${item.name}`);
    lines.push("");
  }
  lines.push(`Summe ${BUILD_LIST_NF.format(data.totals.counted)} von ${BUILD_LIST_NF.format(data.totals.list_size)} Karten`);
  if (data.error) lines.push(data.error);
  return lines.join("\n") + "\n";
}

function buildListTable(h, data, group, ticks, onTick) {
  const rows = group.cards.map((item) => {
    const id = `bl-${group.location_id || "unknown"}-${item.card_id}`;
    const box = h("input", { type: "checkbox", id, checked: ticks.has(buildListTickId(group, item)), "aria-label": `${item.name} eingesteckt`, onchange: (event) => onTick(buildListTickId(group, item), event.target.checked) });
    return h("tr", {}, h("td", { class: "tick" }, box), h("td", { class: "num" }, buildListAmount(item)), h("td", {}, h("label", { for: id }, item.name)),
      h("td", { class: "note" }, item.note || ""));
  });
  return h("table", { class: "bl-table" }, h("tbody", {}, rows));
}

function buildListPrint() {
  // The print rules apply only while this class is set, so printing any other view stays untouched.
  const done = () => document.body.classList.remove("printing-buildlist");
  document.body.classList.add("printing-buildlist");
  window.addEventListener("afterprint", done, { once: true });
  try { window.print(); } finally { done(); }
}

// deps: { h, api, state, entries, closeModal, toast, fail }
async function showBuildList(deps) {
  const { h, $ } = { h: deps.h, $: (id) => document.getElementById(id) };
  const box = $("modal-box");
  box.className = "plain wide buildlist";
  box.replaceChildren(h("h2", {}, "Bauliste nach Standort"), h("p", { class: "muted" }, "Wird berechnet …"));
  $("modal").hidden = false;
  let data;
  try {
    data = await deps.api("/api/build-list", "POST", { cards: deps.entries(), owned_only: true, deck_id: deps.state.deckId || null });
  } catch (error) {
    box.replaceChildren(h("h2", {}, "Bauliste nach Standort"), h("p", { class: "warn" }, "Die Bauliste konnte nicht berechnet werden."), h("div", { class: "actions" }, h("button", { type: "button", onclick: deps.closeModal }, "Schließen")));
    deps.fail(error);
    return;
  }
  const key = buildListKey(deps);
  const ticks = buildListLoadTicks(key);
  const deck = deps.state.decks.find((item) => item.deck_id === deps.state.deckId);
  const deckName = (deck && deck.name) || deps.state.deckId || "Entwurf";
  const onTick = (cardId, on) => { if (on) ticks.add(cardId); else ticks.delete(cardId); buildListSaveTicks(key, ticks); };
  const status = data.card_status;
  const copyText = h("textarea", { id: "buildlist-copy-text", readonly: true, hidden: true, "aria-label": "Bauliste als Text" });
  const copy = h("button", { type: "button", id: "buildlist-copy", onclick: async () => {
    const text = buildListText(data, deckName);
    copyText.value = text;
    try { await navigator.clipboard.writeText(text); copyText.hidden = true; deps.toast("Bauliste als Text kopiert."); } catch (error) {
      copyText.hidden = false; copyText.select(); deps.toast("Kopieren nicht erlaubt: der Text steht unten zum Markieren.", "error");
    }
  } }, "Als Text kopieren");
  const nodes = [
    h("h2", {}, `Bauliste nach Standort – ${deckName}`),
    h("p", { id: "buildlist-summary", class: "note" },
      `${BUILD_LIST_NF.format(status.of)} Nichtland-Karten (ohne Commander und Standardländer): ${BUILD_LIST_NF.format(status.exact)} mit vollständig exaktem Standort, ${BUILD_LIST_NF.format(status.lower_bound)} nur mit „mindestens“-Bestand, ${BUILD_LIST_NF.format(status.partly_unknown)} teils und ${BUILD_LIST_NF.format(status.unknown)} ganz ohne bekannten Standort. `, data.origin),
    data.error ? h("p", { id: "buildlist-error", class: "warn" }, data.error) : "",
    h("div", { class: "actions no-print" }, copy, h("button", { type: "button", id: "buildlist-print", onclick: buildListPrint }, "Drucken"), h("button", { type: "button", onclick: deps.closeModal }, "Schließen")),
    copyText,
  ];
  if (data.commander.length) {
    nodes.push(h("h3", {}, `Commander (${data.commander.length})`), h("ul", { class: "bl-commander" }, data.commander.map((item) =>
      h("li", {}, item.name, " – ", item.placements.length ? item.placements.map((p) => `${p.name}${p.exact ? "" : " (mindestens)"}`).join(", ") : "Standort unbekannt", item.unknown && item.placements.length ? `, ${item.unknown} von ${item.needed} Standort unbekannt` : "", item.note ? ` – ${item.note}` : ""))));
  }
  for (const group of data.groups) {
    const unknown = group.location_id === null;
    nodes.push(h("h3", { class: unknown ? "bl-unknown" : "" }, buildListGroupTitle(data, group)), buildListTable(h, data, group, ticks, onTick));
    if (unknown) nodes.push(h("p", { class: "note" }, "Für diese Exemplare nennt die Sammlungsdatei keinen Standort (oder nur „Unbekannt / nicht direkt belegt“)."));
  }
  if (data.basic_lands.cards.length) {
    nodes.push(h("h3", {}, `Standardländer (${BUILD_LIST_NF.format(data.basic_lands.count)} Karten)`), h("p", { class: "note" }, "Ohne Standortzwang."),
      h("table", { class: "bl-table" }, h("tbody", {}, data.basic_lands.cards.map((item) => h("tr", {}, h("td", { class: "num" }, `${BUILD_LIST_NF.format(item.quantity)}×`), h("td", {}, item.name))))));
  }
  nodes.push(h("p", { id: "buildlist-total", class: data.error ? "warn" : "note" }, `Summe: ${BUILD_LIST_NF.format(data.totals.counted)} von ${BUILD_LIST_NF.format(data.totals.list_size)} Karten (Commander ${BUILD_LIST_NF.format(data.totals.commander)}, Standorte ${BUILD_LIST_NF.format(data.totals.in_groups)}, Standardländer ${BUILD_LIST_NF.format(data.totals.basic_lands)}).`));
  box.replaceChildren(...nodes);
}
