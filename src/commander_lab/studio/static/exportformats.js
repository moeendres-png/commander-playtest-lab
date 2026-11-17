"use strict";
// Text export of a deck list with the commander zone marked (#1404). Same output as the server
// route /api/revisions/{id}/export?format=...: commander zone first, then names in code-point
// order, equal names summed, names exactly as the store holds them. No amounts of money, no
// ratings. Opened from the export dialog by app.js.

const EXPORT_TEXT_FORMATS = [
  { id: "moxfield", label: "Moxfield / Archidekt (Block Commander und Deck)" },
  { id: "plain", label: "Einfach (Commander zuerst, eine Karte je Zeile)" },
];

function exportFormatLines(zone) {
  const sums = new Map();
  for (const item of zone) sums.set(item.name, (sums.get(item.name) || 0) + item.quantity);
  return [...sums.entries()].sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0)).map(([name, quantity]) => `${quantity} ${name}`);
}
// commanders, main: arrays of { name, quantity }
function exportFormatText(format, commanders, main) {
  const commander = exportFormatLines(commanders);
  const deck = exportFormatLines(main);
  if (format === "plain") return [...commander, ...deck].join("\n") + "\n";
  return ["Commander", ...commander, "", "Deck", ...deck].join("\n") + "\n";
}
function exportFormatDraft(state) {
  const commanders = (state.commanderIds || []).map((id) => state.byId.get(id)).filter(Boolean).map((card) => ({ name: card.name, quantity: 1 }));
  const main = [...state.list.entries()].map(([id, quantity]) => ({ card: state.byId.get(id), quantity })).filter((item) => item.card).map((item) => ({ name: item.card.name, quantity: item.quantity }));
  return { commanders, main };
}
async function exportFormatCopy(text, deps, area) {
  try { await navigator.clipboard.writeText(text); area.hidden = true; deps.toast("Text kopiert."); } catch (error) {
    area.value = text; area.hidden = false; area.select(); deps.toast("Kopieren nicht erlaubt: der Text steht unten zum Markieren.", "error");
  }
}
// deps: { h, state, toast, download(filename, content, mime), slug }
function exportFormatsSection(deps) {
  const { h, state } = deps;
  const select = h("select", { id: "export-format", name: "export-format", "aria-label": "Textformat" },
    EXPORT_TEXT_FORMATS.map((format) => h("option", { value: format.id }, format.label)));
  const area = h("textarea", { id: "export-copy-text", readonly: true, hidden: true, "aria-label": "Exporttext" });
  const draftText = () => { const draft = exportFormatDraft(state); return exportFormatText(select.value, draft.commanders, draft.main); };
  const savedText = async () => {
    const response = await fetch(`/api/revisions/${encodeURIComponent(state.baseRevision)}/export?format=${encodeURIComponent(select.value)}`);
    if (!response.ok) throw new Error(`export ${response.status}`);
    return response.text();
  };
  const run = (source, action) => async () => {
    try {
      const text = await source();
      if (action === "copy") await exportFormatCopy(text, deps, area);
      else deps.download(`${deps.slug}-${select.value}.txt`, text, "text/plain;charset=utf-8");
    } catch (error) { deps.toast("Export nicht möglich.", "error"); }
  };
  const group = (title, source, id) => h("div", { class: "actions" }, h("span", { class: "note" }, title),
    h("button", { type: "button", id: `${id}-copy`, onclick: run(source, "copy") }, "In die Zwischenablage kopieren"),
    h("button", { type: "button", id: `${id}-download`, onclick: run(source, "download") }, "Als Textdatei laden"));
  const nodes = [h("h3", {}, "Textformat"), h("label", {}, "Format: ", select)];
  if (state.dirty || !state.baseRevision) nodes.push(group("Entwurf (nicht gespeichert)", async () => draftText(), "export-draft"));
  if (state.baseRevision) nodes.push(group(state.dirty ? "Zuletzt gespeicherter Stand" : "Gespeicherter Stand", savedText, "export-saved"));
  nodes.push(area);
  return nodes;
}
