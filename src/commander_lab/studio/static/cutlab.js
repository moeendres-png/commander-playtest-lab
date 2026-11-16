"use strict";
// Guided cut to exactly 100 cards (#1418): one suggestion after another (cut, reject, later),
// locks, role minimums as a visible, editable guardrail, a what-if swap, and the final list
// with its ADD/CUT patch. Suggestion order and deltas come from /api/cut-lab (measured figures
// only); the Owner's marks never change the order. Rendered from app.js (renderCutLab).

const CutLab = { deckKey: "", locked: new Set(), rejected: [], deferred: [], minimums: null, start: null, whatIf: null };

function cutLabStorageKey(deckId) { return `studio.cutlab.${deckId || "none"}`; }

function cutLabLoad(deckId) {
  if (CutLab.deckKey === deckId) return;
  CutLab.deckKey = deckId; CutLab.locked = new Set(); CutLab.rejected = []; CutLab.deferred = []; CutLab.minimums = null; CutLab.start = null; CutLab.whatIf = null;
  try {
    const saved = JSON.parse(localStorage.getItem(cutLabStorageKey(deckId)) || "null");
    if (saved && Array.isArray(saved.locked)) CutLab.locked = new Set(saved.locked);
    if (saved && saved.minimums && typeof saved.minimums === "object") CutLab.minimums = saved.minimums;
  } catch (error) { /* view setting only */ }
}

function cutLabSave() {
  try { localStorage.setItem(cutLabStorageKey(CutLab.deckKey), JSON.stringify({ locked: [...CutLab.locked], minimums: CutLab.minimums })); } catch (error) { /* view setting only */ }
}

function cutSigned(value) { return (value > 0 ? "+" : "") + value; }

function cutDeltaList(h, item, deps) {
  const rows = [];
  if (item.curve_bucket !== null && item.curve_bucket !== undefined) rows.push(`Kurve: Manawert ${item.curve_bucket === 7 ? "7+" : item.curve_bucket} −1`);
  if (item.lands_delta) rows.push(`Länder ${cutSigned(item.lands_delta)}`);
  const pips = Object.entries(item.pips_delta || {});
  if (pips.length) rows.push("Farbsymbole " + pips.map(([colour, delta]) => `${colour} ${cutSigned(delta)}`).join(", "));
  for (const [role, change] of Object.entries(item.role_change || {})) {
    rows.push(`${deps.roleName(role)}: ${change.before} → ${change.after}` + (change.minimum !== null && change.minimum !== undefined ? ` (Mindestzahl ${change.minimum})` : ""));
  }
  if (!Object.keys(item.role_change || {}).length) rows.push("keine Rolle bekannt");
  return h("ul", { class: "cut-deltas" }, rows.map((text) => h("li", {}, text)));
}

function cutFreqText(item) {
  if (item.of === null || item.of === undefined) return "keine Quelldecks";
  if (item.decks === null || item.decks === undefined) return `Häufigkeit unbekannt (kein Quelldeck nennt die Karte; Gruppe ${item.of} Decks)`;
  return `${item.decks} / ${item.of} Quelldecks` + (item.of ? ` (${(100 * item.decks / item.of).toFixed(1)} %)` : "");
}

function cutLabMinimumsDefault(deps) {
  const reference = deps.reference() || {};
  const spans = reference.roles || {};
  const out = {};
  for (const [role, span] of Object.entries(spans)) if (span && typeof span.p25 === "number") out[role] = Math.floor(span.p25);
  return out;
}

function renderCutMinimums(h, deps, rerender) {
  const minimums = CutLab.minimums || {};
  const roles = Object.keys(minimums).sort((a, b) => deps.roleName(a).localeCompare(deps.roleName(b)));
  return h("details", { id: "cut-minimums" },
    h("summary", {}, `Rollen-Mindestzahlen (Leitplanke, ${roles.length} Rollen)`),
    h("p", { class: "note" }, "Standard: unteres Quartil der Vergleichsgruppe, abgerundet. Ein Vorschlag, der eine Rolle darunter drückt, kommt später und sagt es. Rollen sind nicht für jede Karte bekannt."),
    h("table", {}, h("tbody", {}, roles.map((role) => h("tr", {},
      h("td", {}, deps.roleName(role)),
      h("td", {}, h("input", { type: "number", min: "0", max: "40", value: String(minimums[role]), "aria-label": `Mindestzahl ${deps.roleName(role)}`,
        onchange: (event) => { const value = Math.max(0, Math.min(40, parseInt(event.target.value, 10) || 0)); CutLab.minimums[role] = value; cutLabSave(); rerender(); } })))))));
}

async function renderWhatIf(h, box, item, deps) {
  const candidates = deps.pool().filter((card) => !card.basic && card.available > 0 && !deps.inDeck(card.card_id));
  const listId = "cut-whatif-list";
  const input = h("input", { type: "search", list: listId, placeholder: "Karte aus dem Pool", "aria-label": "Karte für den Was-wäre-wenn-Tausch" });
  const out = h("div", { id: "cut-whatif-result" });
  const run = async () => {
    const card = candidates.find((entry) => entry.name === input.value);
    if (!card) { out.replaceChildren(h("p", { class: "muted" }, "Bitte eine freie Karte aus dem Pool wählen.")); return; }
    out.replaceChildren(h("p", { class: "muted" }, "Wird berechnet …"));
    try {
      const diff = await deps.api("/api/cut-lab/what-if", "POST", { cards: deps.entries(), cut: item.card_id, add: card.card_id, cohort: deps.cohort() });
      const curve = Object.entries(diff.curve_deltas).filter(([, v]) => v.base !== v.target).map(([k, v]) => `MW ${k === "7" ? "7+" : k}: ${v.base} → ${v.target}`);
      const roles = Object.entries(diff.role_deltas || {}).map(([role, v]) => `${deps.roleName(role)} ${v.base} → ${v.target}`);
      const colours = Object.entries(diff.colour_deltas || {}).filter(([, v]) => v.base_pips !== v.target_pips || v.base_sources !== v.target_sources).map(([c, v]) => `${c}: Symbole ${v.base_pips} → ${v.target_pips}, Land-Quellen ${v.base_sources} → ${v.target_sources}`);
      const added = diff.added[0];
      out.replaceChildren(
        h("ul", {},
          h("li", {}, "Kurve: " + (curve.join(" · ") || "unverändert")),
          h("li", {}, "Rollen: " + (roles.join(" · ") || "unverändert")),
          h("li", {}, "Farben: " + (colours.join(" · ") || "unverändert")),
          h("li", {}, `${card.name}: ` + cutFreqText(added || {}))),
        h("button", { type: "button", class: "primary", onclick: () => { deps.swap(item.card_id, card.card_id); } }, `Tausch übernehmen: ${item.name} raus, ${card.name} rein`));
    } catch (error) { out.replaceChildren(h("p", { class: "warn" }, "Der Tausch konnte nicht berechnet werden.")); deps.fail(error); }
  };
  box.append(h("h4", {}, "Was, wenn stattdessen …"),
    h("datalist", { id: listId }, candidates.slice(0, 1500).map((card) => h("option", { value: card.name }))),
    h("div", { class: "actions" }, input, h("button", { type: "button", onclick: run }, "Zahlen zeigen")), out);
}

async function renderCutLab(body, deps) {
  const { h } = deps;
  cutLabLoad(deps.deckId());
  if (CutLab.minimums === null) { CutLab.minimums = cutLabMinimumsDefault(deps); }
  const total = deps.total();
  if (CutLab.start === null && total > 100) CutLab.start = deps.entries();
  const rerender = () => deps.rerender();
  const box = h("div", { id: "cut-lab" });
  body.append(box);
  box.append(h("p", { id: "cut-counter", class: total === 100 ? "" : "warn" }, `${total} / 100 Karten` + (total > 100 ? ` · noch ${total - 100} zu kürzen` : total < 100 ? ` · ${100 - total} fehlen` : " · genau 100")));
  const basics = deps.deckCards().filter((card) => card.basic);
  if (basics.length) {
    box.append(h("p", { id: "cut-basics" }, "Standardländer: ", ...basics.flatMap((card) => [
      `${card.name} ${deps.qty(card.card_id)}× `,
      h("button", { type: "button", class: "small", "aria-label": `${card.name} −1`, onclick: () => { deps.remove(card); } }, "−"), " ",
      h("button", { type: "button", class: "small", "aria-label": `${card.name} +1`, onclick: () => { deps.add(card); } }, "+"), "  "])));
  }
  if (CutLab.locked.size) {
    box.append(h("p", { id: "cut-locked" }, `Gesperrt (${CutLab.locked.size}): `, ...[...CutLab.locked].flatMap((cardId, index) => {
      const card = deps.card(cardId);
      return [index ? ", " : "", card ? card.name : cardId, " ", h("button", { type: "button", class: "small", "aria-label": "Sperre lösen", onclick: () => { CutLab.locked.delete(cardId); cutLabSave(); rerender(); } }, "×")];
    })));
  }
  box.append(renderCutMinimums(h, deps, rerender));
  if (total === 100 && CutLab.start) {
    const finish = await deps.api("/api/cut-lab/finish", "POST", { start: CutLab.start, cards: deps.entries() });
    box.append(h("h3", {}, "Abschluss: genau 100 Karten"),
      h("h4", {}, "Änderungen gegenüber dem Start (ADD/CUT)"), h("textarea", { id: "cut-patch", rows: "8", readonly: true }, finish.patch_text),
      h("h4", {}, "Liste"), h("textarea", { id: "cut-list", rows: "8", readonly: true }, finish.list_text),
      h("div", { class: "actions" },
        h("button", { type: "button", class: "primary", onclick: () => { deps.saveRevision(); CutLab.start = null; } }, "Als Stand speichern"),
        h("button", { type: "button", onclick: () => { CutLab.start = null; CutLab.rejected = []; CutLab.deferred = []; rerender(); } }, "Neu beginnen")));
    return;
  }
  if (total <= 100) {
    box.append(h("p", { class: "muted" }, "Das Kürzen beginnt, wenn die Liste mehr als 100 Karten hat."));
    return;
  }
  const token = deps.token();
  let result;
  try {
    result = await deps.api("/api/cut-lab", "POST", { cards: deps.entries(), locked: [...CutLab.locked], rejected: CutLab.rejected, deferred: CutLab.deferred, role_minimums: CutLab.minimums || {}, cohort: deps.cohort() });
  } catch (error) { if (deps.isCurrent(token)) { box.append(h("p", { class: "warn" }, "Vorschläge konnten nicht berechnet werden.")); deps.fail(error); } return; }
  if (!deps.isCurrent(token)) return;
  const item = result.suggestions[0];
  if (!item) {
    box.append(h("p", { id: "cut-none" }, "Kein Vorschlag übrig: alle Karten sind gesperrt, abgelehnt oder Standardländer."),
      h("button", { type: "button", onclick: () => { CutLab.rejected = []; CutLab.deferred = []; rerender(); } }, "Abgelehnte wieder vorschlagen"));
    return;
  }
  const card = deps.card(item.card_id);
  const suggestion = h("div", { class: "sim-box", id: "cut-suggestion" },
    h("p", { class: "muted" }, `Vorschlag 1 von ${result.suggestions.length}` + (item.group === "unknown" ? " · Häufigkeit unbekannt" : "") + (item.deferred ? " · zurückgestellt" : "")),
    h("h3", {}, h("a", { href: "#", class: "nm", onclick: (event) => { event.preventDefault(); if (card) deps.openCard(card); } }, item.name), item.quantity > 1 ? ` (${item.quantity}× im Deck)` : ""),
    h("p", {}, cutFreqText(item) + (result.cohort.small ? " · kleine Gruppe (unter 30)" : "")),
    item.below_minimum.length ? h("p", { class: "warn" }, "Unter der Mindestzahl: " + item.below_minimum.map(deps.roleName).join(", ")) : "",
    item.combo_parts.length ? h("p", { class: "note" }, h("span", { class: "chip", style: "cursor:default" }, "Kombo-Teil"), " " + item.combo_parts.map((cards) => cards.join(" + ")).join(" · ")) : "",
    cutDeltaList(h, item, deps),
    h("div", { class: "actions" },
      h("button", { type: "button", class: "primary", id: "cut-accept", onclick: () => { if (card) deps.remove(card); } }, "Kürzen"),
      h("button", { type: "button", id: "cut-reject", onclick: () => { CutLab.rejected.push(item.card_id); rerender(); } }, "Ablehnen"),
      h("button", { type: "button", id: "cut-defer", onclick: () => { CutLab.deferred = CutLab.deferred.filter((id) => id !== item.card_id).concat([item.card_id]); rerender(); } }, "Später"),
      h("button", { type: "button", id: "cut-lock", onclick: () => { CutLab.locked.add(item.card_id); cutLabSave(); rerender(); } }, "Sperren")));
  box.append(suggestion);
  await renderWhatIf(h, suggestion, item, deps);
  box.append(h("p", { class: "note" }, result.order));
}
