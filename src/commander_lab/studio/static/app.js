"use strict";
// Commander Studio deck builder. All text from data is set as text, never as HTML.

const COMMANDER = "Chulane, Teller of Tales";
const GROUPS = ["Creature", "Planeswalker", "Battle", "Artifact", "Enchantment", "Instant", "Sorcery", "Land", "Other"];
const GROUP_NAMES = { Creature: "Kreaturen", Planeswalker: "Planeswalker", Battle: "Schlachten", Artifact: "Artefakte", Enchantment: "Verzauberungen", Instant: "Spontanzauber", Sorcery: "Hexereien", Land: "Länder", Other: "Sonstige" };
const COHORT_NAMES = {
  all: "alle Quelldecks",
  community: "Community",
  turnier_cedh: "Turnier cEDH",
  community_cedh: "Community cEDH",
  unklassifiziert: "unklassifiziert",
  c087_945: "C087-Basis (945)",
  new_2026_11_10: "Neu 10.11.2026",
  koma_in_99: "mit Koma im 99er",
  no_koma_in_99: "ohne Koma im 99er",
  koma_31: "Koma-C084 (31)",
};
const ROLE_NAMES = { ramp: "Ramp", mana_rock: "Manastein", mana_dork: "Mana-Kreatur", land_ramp: "Land-Ramp", card_draw: "Karten ziehen", card_advantage: "Kartenvorteil", cantrip: "Cantrip", tutor: "Tutor", removal: "Entfernung", board_wipe: "Massenentfernung", counterspell: "Konter", bounce: "Bounce", flicker: "Blink", recursion: "Rückholen", protection: "Schutz", graveyard_hate: "Friedhofshass", lifegain: "Lebensgewinn" };
const roleName = (key) => ROLE_NAMES[key] || key;
const ISSUE_NAMES = { deck_size: "Deckgröße", commander_count: "Commander", commander_type: "Commander-Typ", color_identity: "Farbidentität", singleton: "Mehrfach", legality_unknown: "Legalität unbekannt", not_legal: "Nicht legal", not_owned: "Nicht in der Sammlung", not_available: "Nicht frei" };

const state = {
  pool: [], byId: new Map(), cohorts: {}, small: 30, commanderIds: [],
  decks: [], deckId: null, branch: "main", baseRevision: null,
  list: new Map(), dirty: false, issues: [], shape: null, deckRoles: {}, roles: [], shapes: [],
  simulations: [], diffBaseRev: null, diffData: null, activeBatch: null, batchPollTimer: null,
  view: "grid", tab: "list", shown: 120, sortKey: "freq", sortDir: -1, cohort: "all",
  colors: new Set(), columns: new Set(["img", "name", "mana_cost", "type_line", "available", "freq", "edhrec"]),
};

const $ = (id) => document.getElementById(id);
function h(tag, props, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(props || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") el.className = value;
    else if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else if (key === "dataset") Object.assign(el.dataset, value);
    else if (key in el && key !== "list") el[key] = value;
    else el.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return el;
}
async function api(path, method = "GET", body) {
  const options = { method, headers: { "X-Studio": "1" } };
  if (body !== undefined) { options.headers["Content-Type"] = "application/json"; options.body = JSON.stringify(body); }
  const response = await fetch(path, options);
  if (!response.ok) {
    let detail = response.statusText;
    try { detail = (await response.json()).detail || detail; } catch (error) { /* keep status text */ }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return response.json();
}
let toastTimer = 0;
function toast(text) {
  const box = $("toast"); box.textContent = text; box.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { box.hidden = true; }, 3500);
}
const cohortName = (key) => COHORT_NAMES[key] || key;
function mana(cost) {
  const span = h("span", {});
  for (const match of String(cost || "").matchAll(/\{([^}]+)\}|(\/\/)/g)) {
    if (match[2]) { span.append(" // "); continue; }
    const symbol = match[1];
    const color = ["W", "U", "B", "R", "G"].find((letter) => symbol.split("/").includes(letter));
    span.append(h("span", { class: "ms" + (color ? " ms-" + color : "") }, symbol));
  }
  return span;
}
function freq(card, cohort = state.cohort) {
  const total = state.cohorts[cohort] || 0;
  const hits = (card.decks && card.decks[cohort]) || 0;
  return { hits, total, share: total ? hits / total : null };
}
function freqText(card, cohort = state.cohort) {
  const f = freq(card, cohort);
  return f.total ? `${f.hits}/${f.total} · ${(100 * f.share).toFixed(0)} %` : "unbekannt";
}
const qty = (id) => state.list.get(id) || 0;
const deckTotal = () => state.commanderIds.length + [...state.list.values()].reduce((a, b) => a + b, 0);
function maxCopies(card) {
  if (card.basic || /A deck can have any number of cards named/.test(card.text)) return Math.max(card.available, 0);
  return Math.min(1, Math.max(card.available, 0));
}

// ---------- pool ----------
function filtered() {
  const words = $("q").value.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const type = $("type-filter").value;
  const role = $("role-filter").value;
  const min = $("mv-min").value === "" ? null : Number($("mv-min").value);
  const max = $("mv-max").value === "" ? null : Number($("mv-max").value);
  const free = $("f-free").checked, notIn = $("f-notin").checked, fav = $("f-fav").checked, showExcluded = $("f-excl").checked;
  const simReady = $("f-sim") && $("f-sim").checked;
  const rows = state.pool.filter((card) => {
    if (state.commanderIds.includes(card.card_id)) return false;
    if (free && card.available < 1) return false;
    if (notIn && qty(card.card_id)) return false;
    if (fav && !card.favorite) return false;
    if (!showExcluded && card.excluded) return false;
    if (simReady && card.sim_status !== "OK") return false;
    if (type && card.group !== type) return false;
    if (role === "-" ? card.roles.length > 0 : role && !card.roles.includes(role)) return false;
    if (min !== null && !(card.mana_value >= min)) return false;
    if (max !== null && !(card.mana_value <= max)) return false;
    if (state.colors.size) {
      const colorless = card.colors === "";
      if (!(colorless ? state.colors.has("C") : [...card.colors].some((letter) => state.colors.has(letter)))) return false;
    }
    if (words.length) {
      const hay = (card.name + "\n" + card.type_line + "\n" + card.text).toLowerCase();
      if (!words.every((word) => hay.includes(word))) return false;
    }
    return true;
  });
  const key = state.sortKey, dir = state.sortDir;
  const value = (card) => {
    if (key === "freq") return freq(card).hits;
    if (key === "edhrec") return card.edhrec ? card.edhrec.pct : -1;
    if (key === "edhrec_rank") return card.edhrec_rank === null ? Infinity : card.edhrec_rank;
    if (key === "playgroup") return card.playgroup && card.playgroup.live_inclusion_pct !== null ? card.playgroup.live_inclusion_pct : -1;
    return card[key];
  };
  rows.sort((a, b) => {
    const x = value(a), y = value(b);
    if (x === y) return a.name.localeCompare(b.name);
    return (x > y ? 1 : -1) * dir;
  });
  return rows;
}
function image(card, cls, face = "front") {
  return h("img", { class: cls, loading: "lazy", alt: card.name, src: `/img/${encodeURIComponent(card.card_id)}?face=${face}` });
}
function hoverPreview(el, card) {
  if (!card.has_image) return;
  el.addEventListener("mouseenter", (event) => {
    const box = $("preview"); box.firstChild.src = `/img/${encodeURIComponent(card.card_id)}`; box.hidden = false; movePreview(event);
  });
  el.addEventListener("mousemove", movePreview);
  el.addEventListener("mouseleave", () => { $("preview").hidden = true; });
}
function movePreview(event) {
  const box = $("preview");
  const left = event.clientX + 290 > innerWidth ? event.clientX - 280 : event.clientX + 20;
  box.style.left = left + "px"; box.style.top = Math.min(event.clientY - 40, innerHeight - 380) + "px";
}
function tile(card) {
  const count = qty(card.card_id);
  const face = card.has_image
    ? image(card, "")
    : h("div", { class: "fallback" }, h("b", {}, card.name), mana(card.mana_cost), h("span", { class: "muted" }, card.type_line), h("span", {}, card.text));
  face.addEventListener("click", () => openCard(card));
  const f = freq(card);
  return h("div", { class: "tile" + (count ? " in" : "") + (card.available < 1 ? " none" : "") },
    face, card.favorite && h("span", { class: "star" }, "★"),
    h("div", { class: "bar" },
      h("button", { class: "small", type: "button", title: "ins Deck", disabled: count >= maxCopies(card), onclick: () => add(card) }, "+"),
      count ? h("button", { class: "small", type: "button", title: "aus dem Deck", onclick: () => remove(card) }, "−") : null,
      count ? h("b", {}, count + "×") : null,
      h("span", { class: "spacer" }),
      h("span", { class: "freq" + (f.total && f.total < state.small ? " low" : ""), title: "Decks der Vergleichsgruppe mit dieser Karte" }, f.total ? `${f.hits}/${f.total}` : "–")));
}
const COLUMNS = [
  ["img", "Bild", null], ["name", "Karte", "name"], ["mana_cost", "Kosten", "mana_value"], ["mana_value", "Manawert", "mana_value"],
  ["type_line", "Typ", "type_line"], ["text", "Text", null], ["pt", "S/W", null], ["available", "frei", "available"], ["owned", "Besitz", "owned"],
  ["reserved", "reserviert", "reserved"], ["freq", "Quelldecks", "freq"], ["edhrec", "EDHREC", "edhrec"], ["edhrec_rank", "EDHREC-Rang", "edhrec_rank"],
  ["playgroup", "Playgroup", "playgroup"],
  ["roles", "Rollen", null], ["produced_mana", "erzeugt Mana", null], ["sim_status", "Simulator", "sim_status"], ["note", "Notiz", null],
];
function cell(card, key) {
  if (key === "img") return h("td", {}, card.has_image ? image(card, "thumb") : null);
  if (key === "name") { const td = h("td", { class: "name", onclick: () => openCard(card) }, (card.favorite ? "★ " : "") + card.name); hoverPreview(td, card); return td; }
  if (key === "mana_cost") return h("td", {}, mana(card.mana_cost));
  if (key === "text") return h("td", { class: "text" }, card.text);
  if (key === "roles") return h("td", {}, card.roles.map(roleName).join(", "));
  if (key === "pt") return h("td", {}, card.power !== null ? `${card.power}/${card.toughness}` : "");
  if (key === "freq") { const f = freq(card); return h("td", { class: "num" + (f.total && f.total < state.small ? " low" : "") }, freqText(card)); }
  if (key === "edhrec") {
    if (!card.edhrec) return h("td", { class: "num muted" }, "unbekannt");
    const e = card.edhrec;
    return h("td", { class: "num" + (e.denominator < state.small ? " low" : ""), title: "EDHREC-Seite: " + e.page }, `${e.numerator}/${e.denominator} · ${Number(e.pct).toFixed(0)} %`);
  }
  if (key === "playgroup") {
    if (!card.playgroup) return h("td", { class: "num muted" }, "unbekannt");
    const p = card.playgroup;
    const gap = p.observed_winrate_gap_pp !== null ? `${p.observed_winrate_gap_pp > 0 ? "+" : ""}${p.observed_winrate_gap_pp.toFixed(1)} pp` : "–";
    const turn = p.median_cast_turn !== null ? `T${p.median_cast_turn.toFixed(1)}` : "–";
    return h("td", { class: "num" + (p.insufficient_sample ? " low" : ""), title: `Playgroup Live: Cast-Turn ${turn}, Winrate-Gap ${gap}` }, `${p.live_inclusion_pct !== null ? p.live_inclusion_pct.toFixed(0) + " %" : "–"} · ${turn} · ${gap}`);
  }
  const value = card[key];
  return h("td", { class: typeof value === "number" ? "num" : "" }, value === null || value === undefined ? "" : value);
}
function renderPool() {
  const rows = filtered();
  $("pool-count").textContent = `${rows.length} von ${state.pool.length - state.commanderIds.length} Karten`;
  const body = $("pool-body"); body.replaceChildren();
  const part = rows.slice(0, state.shown);
  if (state.view === "grid") {
    body.append(h("div", { class: "grid" }, part.map(tile)));
  } else {
    const columns = COLUMNS.filter(([key]) => state.columns.has(key));
    const head = h("tr", {}, h("th", {}, ""), columns.map(([key, label, sortKey]) => h("th", {
      class: ["available", "owned", "reserved", "freq", "edhrec", "edhrec_rank", "mana_value"].includes(key) ? "num" : "",
      onclick: sortKey ? () => { state.sortDir = state.sortKey === sortKey ? -state.sortDir : (["name", "type_line", "edhrec_rank", "mana_value"].includes(sortKey) ? 1 : -1); state.sortKey = sortKey; $("sort").value = ""; renderPool(); } : null,
    }, label + (state.sortKey === sortKey && sortKey ? (state.sortDir > 0 ? " ▲" : " ▼") : ""))));
    const lines = part.map((card) => {
      const count = qty(card.card_id);
      return h("tr", { class: count ? "in" : "" },
        h("td", {}, count
          ? h("button", { class: "small", type: "button", onclick: () => remove(card) }, "−")
          : h("button", { class: "small", type: "button", disabled: maxCopies(card) < 1, onclick: () => add(card) }, "+")),
        columns.map(([key]) => cell(card, key)));
    });
    body.append(h("table", {}, h("thead", {}, head), h("tbody", {}, lines)));
  }
  if (rows.length > part.length) {
    body.append(h("p", {}, h("button", { type: "button", onclick: () => { state.shown += 240; renderPool(); } }, `Weitere anzeigen (${rows.length - part.length})`)));
  }
}

// ---------- deck ----------
function add(card) {
  const count = qty(card.card_id);
  if (count >= maxCopies(card)) { toast(card.available < 1 ? "Keine freie Kopie in der Sammlung." : "Schon im Deck."); return; }
  state.list.set(card.card_id, count + 1); changed();
}
function remove(card) {
  const count = qty(card.card_id);
  if (count <= 1) state.list.delete(card.card_id); else state.list.set(card.card_id, count - 1);
  changed();
}
function entries() {
  const cards = state.commanderIds.map((id) => ({ card_id: id, quantity: 1, zone: "commander" }));
  for (const [id, quantity] of state.list) cards.push({ card_id: id, quantity, zone: "main" });
  return cards;
}
let saveTimer = 0;
function changed() {
  state.dirty = true; renderAll();
  clearTimeout(saveTimer); saveTimer = setTimeout(syncDraft, 500);
}
async function syncDraft() {
  try {
    const cards = entries();
    const [result] = await Promise.all([
      api("/api/check", "POST", { cards, owned_only: true }),
      state.dirty ? api(`/api/decks/${encodeURIComponent(state.deckId)}/branches/${encodeURIComponent(state.branch)}/draft`, "PUT", { cards, base_revision_id: state.baseRevision }) : null,
    ]);
    state.issues = result.issues; state.shape = result.shape; state.deckRoles = result.roles || {};
    $("save-state").textContent = state.dirty ? "Entwurf gesichert, noch nicht als Stand gespeichert" : "gespeichert";
    renderHeader(); renderDeck();
  } catch (error) { toast("Fehler: " + error.message); }
}
function renderHeader() {
  const total = deckTotal();
  const counter = $("counter"); counter.textContent = `${total} / 100`;
  counter.className = "pill " + (total === 100 ? "good" : total > 100 ? "bad" : "warn");
  const errors = state.issues.filter((issue) => issue.severity === "error").length;
  const warnings = state.issues.length - errors;
  const pill = $("check-pill");
  pill.textContent = errors ? `${errors} Fehler` : warnings ? `${warnings} Hinweise` : "Datenprüfung ohne Befund";
  pill.className = "pill " + (errors ? "bad" : warnings ? "warn" : "good");
  $("save").disabled = !state.dirty;
}
function deckCards() {
  return [...state.list.keys()].map((id) => state.byId.get(id)).filter(Boolean);
}
function renderList(body) {
  const problems = new Set(state.issues.map((issue) => issue.card_id).filter(Boolean));
  for (const id of state.commanderIds) {
    const card = state.byId.get(id);
    if (!card) continue;
    body.append(h("div", { class: "commander" }, card.has_image ? image(card, "") : null,
      h("div", {}, h("b", {}, card.name), h("div", { class: "muted" }, "Commander"), h("div", {}, mana(card.mana_cost)),
        h("div", { class: "note" }, `Farbidentität ${card.colors || "farblos"}`))));
  }
  const cards = deckCards();
  if (!cards.length) body.append(h("p", { class: "muted" }, "Noch keine Karten. Wähle links Karten aus deiner Sammlung aus."));
  for (const group of GROUPS) {
    const members = cards.filter((card) => card.group === group).sort((a, b) => a.mana_value - b.mana_value || a.name.localeCompare(b.name));
    if (!members.length) continue;
    const count = members.reduce((sum, card) => sum + qty(card.card_id), 0);
    const box = h("div", { class: "group" }, h("h3", {}, `${GROUP_NAMES[group]} (${count})`));
    for (const card of members) {
      const name = h("span", { class: "nm", onclick: () => openCard(card) }, card.name);
      hoverPreview(name, card);
      box.append(h("div", { class: "row" + (problems.has(card.card_id) ? " problem" : "") },
        h("span", { class: "qty" }, qty(card.card_id)), name, mana(card.mana_cost),
        card.basic ? h("button", { class: "small", type: "button", disabled: qty(card.card_id) >= maxCopies(card), onclick: () => add(card) }, "+") : null,
        h("button", { class: "small", type: "button", onclick: () => remove(card) }, "−")));
    }
    body.append(box);
  }
}
function bars(values, labels) {
  const top = Math.max(1, ...values);
  return [h("div", { class: "bars" }, values.map((value) => h("div", { style: `height:${(100 * value) / top}%` }, h("span", {}, value)))),
    h("div", { class: "axis" }, labels.map((label) => h("span", {}, label)))];
}
function renderNumbers(body) {
  const shape = state.shape;
  if (!shape) { body.append(h("p", { class: "muted" }, "Wird berechnet.")); return; }
  body.append(h("h3", {}, "Manakurve (ohne Länder)"), ...bars([0, 1, 2, 3, 4, 5, 6, 7].map((key) => shape.curve[String(key)] || 0), ["0", "1", "2", "3", "4", "5", "6", "7+"]),
    h("p", {}, `Durchschnittlicher Manawert der Nichtland-Karten: ${shape.mana_value === null ? "unbekannt" : shape.mana_value}`));
  const types = h("table", {}, h("tbody", {}, GROUPS.filter((group) => shape.types[group]).map((group) => h("tr", {}, h("td", {}, GROUP_NAMES[group]), h("td", { class: "num" }, shape.types[group])))));
  body.append(h("h3", {}, "Kartentypen"), types);
  const colors = h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Farbe"), h("th", { class: "num" }, "Farbsymbole in Kosten"), h("th", { class: "num" }, "Karten, die die Farbe erzeugen"))),
    h("tbody", {}, ["W", "U", "B", "R", "G", "C"].filter((letter) => shape.pips[letter] || shape.mana_sources[letter]).map((letter) =>
      h("tr", {}, h("td", {}, h("span", { class: "ms ms-" + letter }, letter)), h("td", { class: "num" }, shape.pips[letter] || 0), h("td", { class: "num" }, shape.mana_sources[letter] || 0)))));
  if (state.roles.length) {
    const reference = state.shapes.find((row) => row.cohort === state.cohort) || {};
    const spans = reference.roles || {};
    body.append(h("h3", {}, "Rollen"), h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Rolle"), h("th", { class: "num" }, "Dein Deck"), h("th", { class: "num" }, cohortName(state.cohort)))),
      h("tbody", {}, state.roles.map((role) => h("tr", {}, h("td", {}, roleName(role)), h("td", { class: "num" }, state.deckRoles[role] || 0), h("td", { class: "num" }, span(spans[role])))))),
      h("p", { class: "note" }, "Rollen sind öffentliche Marken der Scryfall-Gemeinschaft (Tagger). Eine Karte kann mehrere Rollen haben, und nicht jede Karte ist markiert. Vergleich: Median und mittlere Hälfte der gewählten Vergleichsgruppe."));
  }
  body.append(h("h3", {}, "Farben"), colors, h("p", { class: "note" }, "Gezählt aus den Kartendaten: Symbole in den Manakosten und Karten, die Mana dieser Farbe erzeugen können. Das ist eine Zählung, keine Bewertung."));
  const dp = shape.draw_probabilities;
  if (dp && dp.opening_7) {
    const pct = (v) => (v === null || v === undefined ? "unbekannt" : (100 * v).toFixed(1) + " %");
    const probTable = h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, "Ziehfenster"), h("th", { class: "num" }, "Karten (n)"), h("th", { class: "num" }, "≥ 2 Länder"), h("th", { class: "num" }, "3–4 Länder"), h("th", { class: "num" }, "≥ 3 Länder"), h("th", { class: "num" }, "≥ 4 Länder"))),
      h("tbody", {},
        h("tr", {}, h("td", {}, "Starthand"), h("td", { class: "num" }, dp.opening_7.draws), h("td", { class: "num" }, pct(dp.opening_7.at_least_2_lands)), h("td", { class: "num" }, pct(dp.opening_7.between_3_and_4_lands)), h("td", { class: "num" }, pct(dp.opening_7.at_least_3_lands)), h("td", { class: "num" }, pct(dp.opening_7.at_least_4_lands))),
        h("tr", {}, h("td", {}, "Bis Zug 3"), h("td", { class: "num" }, dp.turn_3_draw_9.draws), h("td", { class: "num" }, "–"), h("td", { class: "num" }, "–"), h("td", { class: "num" }, pct(dp.turn_3_draw_9.at_least_3_lands)), h("td", { class: "num" }, pct(dp.turn_3_draw_9.at_least_4_lands))),
        h("tr", {}, h("td", {}, "Bis Zug 4"), h("td", { class: "num" }, dp.turn_4_draw_10.draws), h("td", { class: "num" }, "–"), h("td", { class: "num" }, "–"), h("td", { class: "num" }, pct(dp.turn_4_draw_10.at_least_3_lands)), h("td", { class: "num" }, pct(dp.turn_4_draw_10.at_least_4_lands)))));
    body.append(h("h3", {}, `Land-Ziehwahrscheinlichkeiten (${dp.lands} Länder in ${dp.main_cards} Maindeck-Karten)`), probTable,
      h("p", { class: "note" }, "Exakte hypergeometrische Kombinatorik (DERIVED_DESCRIPTIVE) ohne Mulligan-Heuristik."));
  }
}
function renderCheck(body) {
  if (!state.issues.length) { body.append(h("p", {}, "Die Datenprüfung findet nichts.")); }
  for (const issue of state.issues) {
    body.append(h("div", { class: "issue " + issue.severity }, h("b", {}, ISSUE_NAMES[issue.code] || issue.code), h("div", {}, issue.message)));
  }
  body.append(h("p", { class: "note" }, "Diese Prüfung liest gespeicherte Kartendaten: 100 Karten, Commander, Farbidentität, Einzelkarten-Regel, Legalität, Besitz und freie Kopien. Verbindlich für das Spiel ist erst die Prüfung durch die Regel-Engine."));
  const currentCards = [...state.commanderIds.map((id) => state.byId.get(id)), ...deckCards()].filter(Boolean);
  const notReady = currentCards.filter((card) => card.sim_status && card.sim_status !== "OK");
  body.append(h("h3", {}, "Simulator-Bereitschaft (CODE_DERIVED)"));
  if (!notReady.length) {
    body.append(h("p", {}, `Alle ${currentCards.length} eindeutigen Karten im aktuellen Deck haben XMage-Card-Facts und Pilot-Wissen (OK).`));
  } else {
    body.append(h("p", {}, `${notReady.length} Karte(n) im aktuellen Deck sind im Simulator-Vorfilter noch nicht vollständig hinterlegt:`),
      h("div", {}, notReady.map((card) => h("div", { class: "issue warning" },
        h("b", {}, card.sim_status),
        h("div", {}, `${card.name}: Status ${card.sim_status} (deck_readiness).`)))));
  }
}
function span(entry) { return entry ? `${entry.median} (${entry.p25} bis ${entry.p75})` : "unbekannt"; }
function renderCompare(body) {
  const shape = state.shape || {};
  const table = h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Gruppe"), h("th", { class: "num" }, "Decks"), h("th", { class: "num" }, "Länder"), h("th", { class: "num" }, "Kreaturen"), h("th", { class: "num" }, "Ø Manawert"))),
    h("tbody", {}, h("tr", {}, h("td", {}, h("b", {}, "Dein Deck")), h("td", {}), h("td", { class: "num" }, shape.lands ?? ""), h("td", { class: "num" }, shape.creatures ?? ""), h("td", { class: "num" }, shape.mana_value ?? "")),
      state.shapes.map((row) => h("tr", { class: row.decks < state.small ? "low" : "" }, h("td", {}, cohortName(row.cohort)), h("td", { class: "num" }, row.decks_counted === row.decks ? row.decks : `${row.decks_counted} von ${row.decks}`),
        h("td", { class: "num" }, span(row.lands)), h("td", { class: "num" }, span(row.creatures)), h("td", { class: "num" }, span(row.mana_value))))));
  body.append(h("h3", {}, "Aufbau im Vergleich"), table, h("p", { class: "note" }, "Median und mittlere Hälfte der Quelldecks. Gelb: Gruppe mit weniger als 30 Decks, sehr unsicher. Länder nach Vorderseite gezählt."));
  const name = cohortName(state.cohort);
  const candidates = state.pool.filter((card) => !qty(card.card_id) && !state.commanderIds.includes(card.card_id) && card.available > 0 && !card.excluded && !card.basic)
    .sort((a, b) => freq(b).hits - freq(a).hits).slice(0, 20);
  const rare = deckCards().filter((card) => !card.basic).sort((a, b) => freq(a).hits - freq(b).hits).slice(0, 20);
  const listing = (cards, withAdd) => h("div", {}, cards.map((card) => {
    const label = h("span", { class: "nm", onclick: () => openCard(card) }, card.name); hoverPreview(label, card);
    return h("div", { class: "row" }, label, h("span", { class: "muted" }, freqText(card)),
      withAdd ? h("button", { class: "small", type: "button", onclick: () => add(card) }, "+") : h("button", { class: "small", type: "button", onclick: () => remove(card) }, "−"));
  }));
  body.append(h("h3", {}, `Oft gespielt (${name}), frei in deiner Sammlung, nicht im Deck`), listing(candidates, true),
    h("h3", {}, `Im Deck, selten gespielt (${name})`), listing(rare, false),
    h("p", { class: "note" }, "Häufigkeit sagt, was andere spielen, nicht, was stärker ist."));
}
async function renderDiff(body) {
  const deck = state.decks.find((item) => item.deck_id === state.deckId);
  const branches = deck ? deck.branches : [];
  if (!state.diffBaseRev && state.baseRevision) state.diffBaseRev = state.baseRevision;
  const select = h("select", {
    onchange: async (event) => {
      state.diffBaseRev = event.target.value;
      state.diffData = null;
      renderDeck();
    },
  }, ...branches.map((b) => h("option", { value: b.revision_id, selected: b.revision_id === state.diffBaseRev }, `Variante: ${b.branch} (${b.revision_id.slice(0, 20)})`)));
  body.append(h("div", { class: "actions" }, h("label", {}, "Vergleichsbasis: ", select)));
  if (!state.diffBaseRev) {
    body.append(h("p", { class: "muted" }, "Keine gespeicherte Variante als Vergleichsbasis vorhanden."));
    return;
  }
  const box = h("div", {}, h("p", { class: "muted" }, "Berechnet Differenz..."));
  body.append(box);
  try {
    const diff = await api("/api/diff", "POST", { base_revision_id: state.diffBaseRev, cards: entries() });
    box.replaceChildren();
    box.append(h("p", {}, `Neu: +${diff.added_slots} Slots (${diff.added.length} Karten) · Entfernt: −${diff.removed_slots} Slots (${diff.removed.length} Karten)`));
    const bs = diff.base_shape || {}, ts = diff.target_shape || {};
    const shapeTable = h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, "Kennzahl"), h("th", { class: "num" }, "Basis"), h("th", { class: "num" }, "Aktuell"), h("th", { class: "num" }, "Delta"))),
      h("tbody", {},
        [["Länder", bs.lands ?? 0, ts.lands ?? 0], ["Kreaturen", bs.creatures ?? 0, ts.creatures ?? 0], ["Nichtländer", bs.nonland ?? 0, ts.nonland ?? 0]].map(([label, bVal, tVal]) =>
          h("tr", {}, h("td", {}, label), h("td", { class: "num" }, bVal), h("td", { class: "num" }, tVal), h("td", { class: "num" }, (tVal - bVal > 0 ? "+" : "") + (tVal - bVal)))),
        h("tr", {}, h("td", {}, "Ø Manawert"), h("td", { class: "num" }, bs.mana_value ?? "–"), h("td", { class: "num" }, ts.mana_value ?? "–"),
          h("td", { class: "num" }, bs.mana_value !== null && ts.mana_value !== null ? ((ts.mana_value - bs.mana_value >= 0 ? "+" : "") + (ts.mana_value - bs.mana_value).toFixed(2)) : "–"))));
    box.append(h("h3", {}, "Struktur-Delta (DERIVED_DESCRIPTIVE)"), shapeTable);
    const bdp = bs.draw_probabilities && bs.draw_probabilities.opening_7 ? bs.draw_probabilities : null;
    const tdp = ts.draw_probabilities && ts.draw_probabilities.opening_7 ? ts.draw_probabilities : null;
    if (bdp && tdp) {
      const pct = (v) => (v === null || v === undefined ? "–" : (100 * v).toFixed(1) + " %");
      const dpDelta = (bVal, tVal) => (bVal === null || tVal === null || bVal === undefined || tVal === undefined ? "–" : ((tVal - bVal >= 0 ? "+" : "") + (100 * (tVal - bVal)).toFixed(1) + " %"));
      const probDiffTable = h("table", {},
        h("thead", {}, h("tr", {}, h("th", {}, "Land-Ziehfenster"), h("th", { class: "num" }, "Basis"), h("th", { class: "num" }, "Aktuell"), h("th", { class: "num" }, "Delta"))),
        h("tbody", {},
          [["Starthand ≥ 3 Länder (7)", bdp.opening_7.at_least_3_lands, tdp.opening_7.at_least_3_lands],
           ["Starthand 3–4 Länder (7)", bdp.opening_7.between_3_and_4_lands, tdp.opening_7.between_3_and_4_lands],
           ["Bis Zug 4 ≥ 4 Länder (10)", bdp.turn_4_draw_10.at_least_4_lands, tdp.turn_4_draw_10.at_least_4_lands]].map(([label, bV, tV]) =>
            h("tr", {}, h("td", {}, label), h("td", { class: "num" }, pct(bV)), h("td", { class: "num" }, pct(tV)), h("td", { class: "num" }, dpDelta(bV, tV))))));
      box.append(h("h3", {}, "Land-Ziehwahrscheinlichkeiten-Delta (DERIVED_DESCRIPTIVE)"), probDiffTable);
    }
    if (diff.role_deltas && Object.keys(diff.role_deltas).length) {
      const roleRows = Object.entries(diff.role_deltas).sort((a, b) => roleName(a[0]).localeCompare(roleName(b[0])));
      const roleDiffTable = h("table", {},
        h("thead", {}, h("tr", {}, h("th", {}, "Rolle (Tagger)"), h("th", { class: "num" }, "Basis"), h("th", { class: "num" }, "Aktuell"), h("th", { class: "num" }, "Delta"))),
        h("tbody", {}, roleRows.map(([rKey, vals]) => h("tr", {},
          h("td", {}, roleName(rKey)),
          h("td", { class: "num" }, vals.base),
          h("td", { class: "num" }, vals.target),
          h("td", { class: "num" }, (vals.delta > 0 ? "+" : "") + vals.delta)))));
      box.append(h("h3", {}, "Rollen-Delta (DERIVED_DESCRIPTIVE)"), roleDiffTable);
    }
    if (diff.added.length) {
      box.append(h("h3", {}, `Hinzugefügt (+${diff.added.length})`), h("div", {}, diff.added.map((item) => h("div", { class: "row" }, h("span", { class: "qty" }, "+" + item.quantity), h("span", { class: "nm", onclick: () => { const c = state.byId.get(item.card_id); if (c) openCard(c); } }, item.name), h("span", { class: "muted" }, GROUP_NAMES[item.group] || item.group)))));
    }
    if (diff.removed.length) {
      box.append(h("h3", {}, `Entfernt (−${diff.removed.length})`), h("div", {}, diff.removed.map((item) => h("div", { class: "row" }, h("span", { class: "qty" }, "−" + item.quantity), h("span", { class: "nm", onclick: () => { const c = state.byId.get(item.card_id); if (c) openCard(c); } }, item.name), h("span", { class: "muted" }, GROUP_NAMES[item.group] || item.group)))));
    }
    if (diff.changed.length) {
      box.append(h("h3", {}, "Mengenänderung"), h("div", {}, diff.changed.map((item) => h("div", { class: "row" }, h("span", { class: "qty" }, `${item.base_quantity}→${item.target_quantity}`), h("span", {}, item.name)))));
    }
    const pfBox = h("div", {});
    const pfBtn = h("button", {
      type: "button",
      onclick: async () => {
        pfBtn.disabled = true;
        pfBox.replaceChildren(h("p", { class: "muted" }, "Berechnet Commander-Castability & Manabasis-Vorfilter (2000 MC-Läufe, Seed 20261016)..."));
        try {
          const pf = await api("/api/prefilter", "POST", { base_revision_id: state.diffBaseRev, cards: entries(), trials: 2000 });
          pfBox.replaceChildren();
          if (!pf.comparable) {
            pfBox.append(h("p", { class: "muted" }, pf.reason || "Vorfilter benötigt zwei vollständige 100-Karten-Listen."));
          } else {
            pfBox.append(h("h3", {}, "Vorfilter & Commander-Castability (HEURISTIC_MODEL)"),
              h("p", {}, h("b", {}, `Urteil: ${pf.verdict}`), ` — ${pf.verdict_reason}`),
              h("p", { class: "note" }, `Simulator-Bereitschaft: Basis=${pf.baseline_ready ? "OK" : "Lücken"}, Aktuell=${pf.variant_ready ? "OK" : "Lücken (" + (pf.variant_not_ready_cards || []).join(", ") + ")"} · Manabasis-Delta: Länder ${pf.land_count_delta >= 0 ? "+" : ""}${pf.land_count_delta}, sicher getappt ${pf.definitely_tapped_land_delta >= 0 ? "+" : ""}${pf.definitely_tapped_land_delta}, bedingt getappt ${pf.conditionally_tapped_land_delta >= 0 ? "+" : ""}${pf.conditionally_tapped_land_delta}`));
            if (pf.castability && pf.castability.length) {
              const fmtPct = (v) => (v === null || v === undefined ? "–" : (100 * v).toFixed(1) + " %");
              const fmtDelta = (v) => (v === null || v === undefined ? "–" : (v >= 0 ? "+" : "") + (100 * v).toFixed(1) + " %");
              const castRows = [];
              for (const c of pf.castability) {
                const bp = c.baseline_probability || {};
                const vp = c.variant_probability || {};
                const dp = c.probability_delta || {};
                for (const t of ["3", "4", "5", "6"]) {
                  const pB = bp.play ? bp.play[t] : null;
                  const pV = vp.play ? vp.play[t] : null;
                  const pD = dp.play ? dp.play[t] : null;
                  const dB = bp.draw ? bp.draw[t] : null;
                  const dV = vp.draw ? vp.draw[t] : null;
                  const dD = dp.draw ? dp.draw[t] : null;
                  castRows.push(h("tr", {},
                    h("td", {}, `${c.name} (Zug ${t})`),
                    h("td", { class: "num" }, `${fmtPct(pB)} → ${fmtPct(pV)} (${fmtDelta(pD)})`),
                    h("td", { class: "num" }, `${fmtPct(dB)} → ${fmtPct(dV)} (${fmtDelta(dD)})`)));
                }
                const be = c.baseline_expected_turn || {}, ve = c.variant_expected_turn || {}, de = c.expected_turn_delta || {};
                if (be.play !== undefined && ve.play !== undefined) {
                  const fmtTurn = (v) => (v === null || v === undefined ? "–" : Number(v).toFixed(2));
                  const fmtTurnDelta = (v) => (v === null || v === undefined ? "–" : (v >= 0 ? "+" : "") + Number(v).toFixed(2));
                  castRows.push(h("tr", {},
                    h("td", {}, `${c.name} (Ø Zug)`),
                    h("td", { class: "num" }, `${fmtTurn(be.play)} → ${fmtTurn(ve.play)} (${fmtTurnDelta(de.play)})`),
                    h("td", { class: "num" }, `${fmtTurn(be.draw)} → ${fmtTurn(ve.draw)} (${fmtTurnDelta(de.draw)})`)));
                }
              }
              pfBox.append(h("table", {},
                h("thead", {}, h("tr", {}, h("th", {}, "Commander / Zug"), h("th", { class: "num" }, "On the Play (Basis → Aktuell)"), h("th", { class: "num" }, "On the Draw (Basis → Aktuell)"))),
                h("tbody", {}, castRows)),
                h("p", { class: "note" }, "Modellrechnung (HEURISTIC_MODEL, 2000 Läufe, Seed 20261016): prüft Manabasis und Farbquellen ohne volle Spielsimulation."));
            }
          }
        } catch (err) {
          pfBox.replaceChildren(h("p", { class: "muted" }, "Vorfilter-Fehler: " + err.message));
        } finally {
          pfBtn.disabled = false;
        }
      },
    }, "Vorfilter & Commander-Castability berechnen (HEURISTIC_MODEL)");
    box.append(h("div", { class: "actions", style: "margin-top:10px" }, pfBtn), pfBox);
  } catch (error) {
    box.replaceChildren(h("p", { class: "muted" }, "Differenz nicht lesbar: " + error.message));
  }
}
function pollBatch(batchId) {
  if (state.batchPollTimer) clearTimeout(state.batchPollTimer);
  state.batchPollTimer = setTimeout(async () => {
    try {
      const batch = await api("/api/simulations/batch/" + encodeURIComponent(batchId));
      state.activeBatch = batch;
      if (batch.status === "completed" || batch.status === "cancelled" || batch.status === "failed") {
        const [sims, recordedGames] = await Promise.all([
          api("/api/simulations").catch(() => []),
          api("/api/games").catch(() => []),
        ]);
        state.simulations = sims || [];
        state.recordedGames = recordedGames || [];
        if (state.tab === "sim") renderDeck();
      } else {
        pollBatch(batchId);
        if (state.tab === "sim") renderDeck();
      }
    } catch (err) {
      console.warn("Poll batch error:", err);
    }
  }, 1200);
}
function renderSimulations(body) {
  body.append(h("div", { class: "actions" }, h("a", { class: "nav", href: "partie.html" }, "Partien-Ansicht & Neue Einzelpartie →")));

  // Batch simulation launcher & live monitor
  const bBox = h("div", { class: "sim-box" },
    h("h3", { style: "margin-top:0" }, "Neue Simulationsserie starten (M5 Batch-Simulation)"),
    h("p", { class: "note" }, "Spielt mehrere vollständige 4-Spieler-Partien nacheinander in prozessisolierten Durchläufen mit deterministischen Seeds. Berechnet Siegrate mit Nenner und 95%-Wilson-Konfidenzintervall.")
  );

  const curRev = state.baseRevision || (state.deckId ? `rev@${state.deckId}/main/current` : "rev@chulane/main/current");
  const revInput = h("input", { type: "text", value: curRev, style: "width:240px", title: "Deck-Revision" });
  const podSelect = h("select", {},
    h("option", { value: "precon" }, "Precon (Lorehold, Animated Army, Token Triumph)"),
    h("option", { value: "mixed" }, "Mixed (Kaervek, Animated Army, Lorehold)"),
    h("option", { value: "optimized" }, "Optimized (Eldrazi, Kaervek, Hosts of Mordor)")
  );
  const countSelect = h("select", {},
    h("option", { value: "5" }, "5 Partien"),
    h("option", { value: "10", selected: true }, "10 Partien"),
    h("option", { value: "20" }, "20 Partien"),
    h("option", { value: "30" }, "30 Partien"),
    h("option", { value: "50" }, "50 Partien")
  );
  const seedInput = h("input", { type: "number", value: "1000", style: "width:90px" });

  const startBtn = h("button", { type: "submit", class: "primary" }, "Serie starten");
  const form = h("form", {
    class: "sim-form",
    onsubmit: async (e) => {
      e.preventDefault();
      startBtn.disabled = true;
      try {
        const res = await api("/api/simulations/batch", "POST", {
          revision_id: revInput.value.trim(),
          pod: podSelect.value,
          games_count: parseInt(countSelect.value, 10),
          base_seed: parseInt(seedInput.value, 10),
        });
        state.activeBatch = {
          batch_id: res.batch_id,
          status: res.status,
          pod: podSelect.value,
          games_planned: parseInt(countSelect.value, 10),
          games_completed: 0,
          games_failed: 0,
          games: [],
        };
        pollBatch(res.batch_id);
        renderDeck();
      } catch (err) {
        alert("Fehler beim Starten: " + err.message);
        startBtn.disabled = false;
      }
    }
  },
    h("label", {}, "Revision", revInput),
    h("label", {}, "Gegnertisch (Pod)", podSelect),
    h("label", {}, "Anzahl", countSelect),
    h("label", {}, "Basis-Seed", seedInput),
    startBtn
  );
  bBox.append(form);

  if (state.activeBatch) {
    const b = state.activeBatch;
    const isRunning = b.status === "running" || b.status === "pending";
    const statusText = isRunning ? "Läuft..." : b.status === "completed" ? "Abgeschlossen" : b.status === "cancelled" ? "Abgebrochen" : "Fehler: " + (b.error || "Unbekannt");
    const pct = b.games_planned > 0 ? Math.round((b.games_completed / b.games_planned) * 100) : 0;

    const monitor = h("div", { style: "margin-top:12px;padding-top:10px;border-top:1px solid var(--line)" },
      h("div", { style: "display:flex;justify-content:space-between;align-items:center;margin-bottom:6px" },
        h("b", {}, `Serie „${b.pod}“: ${b.games_completed} von ${b.games_planned} Partien abgeschlossen (${pct} %)`),
        h("span", { class: "pill " + (isRunning ? "warn" : b.status === "completed" ? "good" : "bad") }, statusText)
      ),
      h("progress", { value: b.games_completed, max: b.games_planned })
    );

    if (isRunning) {
      const cancelBtn = h("button", {
        type: "button",
        class: "danger",
        style: "margin-top:8px",
        onclick: async () => {
          cancelBtn.disabled = true;
          try {
            await api("/api/simulations/batch/" + encodeURIComponent(b.batch_id) + "/cancel", "POST");
            pollBatch(b.batch_id);
          } catch (err) {
            console.warn(err);
          }
        }
      }, "Serie abbrechen");
      monitor.append(cancelBtn);
    }

    if (b.summary) {
      const s = b.summary;
      const ci = s.confidence_interval_95 || {};
      const sumBox = h("div", { style: "margin-top:10px;background:var(--panel);padding:10px;border-radius:6px" },
        h("h4", { style: "margin:0 0 6px" }, "Ergebnis der Serie (SIMULATED_RESULT)"),
        h("div", { style: "display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px" },
          h("div", {}, h("span", { class: "muted" }, "Siege: "), h("b", {}, `${s.wins_fractional} / ${s.games_completed}`)),
          h("div", {}, h("span", { class: "muted" }, "Siegrate: "), h("b", {}, s.win_rate !== null ? `${s.win_rate_percent} %` : "–")),
          h("div", {}, h("span", { class: "muted" }, "95 %-CI (Wilson): "), h("b", {}, ci.lower_percent !== undefined ? `[${ci.lower_percent} %, ${ci.upper_percent} %]` : "–")),
          h("div", {}, h("span", { class: "muted" }, "Ø Runden: "), h("b", {}, s.mean_rounds ?? "–"))
        ),
        b.run_id ? h("p", { class: "note", style: "margin:6px 0 0" }, `Dauerhaft im Store hinterlegt unter ID: `, h("code", {}, b.run_id)) : null
      );
      monitor.append(sumBox);
    }

    if (b.games && b.games.length) {
      const bTable = h("table", { style: "margin-top:8px" },
        h("thead", {}, h("tr", {}, h("th", {}, "Partie"), h("th", { class: "num" }, "Seed"), h("th", { class: "num" }, "Runden"), h("th", {}, "Ergebnis"), h("th", {}, ""))),
        h("tbody", {}, b.games.map((g) => {
          const outcome = g.status === "finished" ? (g.candidate_won ? "Sieg Sitz 1" : `Niederlage (Sieger: Sitz ${(g.winner_seats || []).map((x) => x + 1).join(", ") || "–"})`) : "Fehlgeschlagen";
          return h("tr", {},
            h("td", {}, h("code", {}, g.game_id)),
            h("td", { class: "num" }, g.seed),
            h("td", { class: "num" }, g.rounds || "–"),
            h("td", {}, outcome),
            h("td", {}, h("a", { href: `partie.html?partie=${encodeURIComponent(g.game_id)}` }, "Ansehen →"))
          );
        }))
      );
      monitor.append(bTable);
    }

    bBox.append(monitor);
  }

  body.append(bBox);
  if (state.recordedGames && state.recordedGames.length) {
    const gTable = h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, "Partie"), h("th", { class: "num" }, "Seed"), h("th", { class: "num" }, "Entscheidungen"), h("th", {}, "Status / Sieger"), h("th", {}, ""))),
      h("tbody", {}, state.recordedGames.slice(0, 15).map((g) => {
        const hdr = g.header || {};
        const end = g.running ? "läuft" : g.result && g.result.status === "finished" ? `Sieger Sitz ${((g.result.winner_seats || []).map((s) => s + 1)).join(", ") || "keiner"}` : "abgebrochen";
        return h("tr", {},
          h("td", {}, h("code", {}, g.game_id)),
          h("td", { class: "num" }, hdr.seed ?? "–"),
          h("td", { class: "num" }, g.frames ?? 0),
          h("td", {}, end),
          h("td", {}, h("a", { href: `partie.html?partie=${encodeURIComponent(g.game_id)}` }, "Ansehen →")));
      })));
    body.append(h("h3", {}, "Aufgezeichnete Einzelpartien (SIMULATED_RESULT)"), gTable);
  }
  if (!state.simulations || !state.simulations.length) {
    body.append(h("p", { class: "muted" }, "Keine Batch-Simulationsläufe (SIMULATED_RESULT) im Store hinterlegt."));
    return;
  }
  const runTable = h("table", {},
    h("thead", {}, h("tr", {}, h("th", {}, "Pod"), h("th", {}, "Engine-Pin"), h("th", {}, "Pilot"), h("th", { class: "num" }, "Spiele"), h("th", { class: "num" }, "Siege"), h("th", { class: "num" }, "Siegrate"), h("th", { class: "num" }, "Ø Runden"))),
    h("tbody", {}, state.simulations.map((run) => h("tr", {},
      h("td", {}, h("b", {}, run.pod)),
      h("td", {}, h("code", {}, run.engine_pin)),
      h("td", {}, run.pilot_policy),
      h("td", { class: "num" }, `${run.games_completed}/${run.games_planned}`),
      h("td", { class: "num" }, run.wins_fractional),
      h("td", { class: "num" }, run.win_rate === null ? "unbekannt" : `${(100 * run.win_rate).toFixed(1)} %`),
      h("td", { class: "num" }, run.mean_rounds ?? "unbekannt")))));
  body.append(h("h3", {}, "4P-Simulationsläufe (SIMULATED_RESULT)"), runTable,
    h("p", { class: "note" }, "Ergebnisse aus echten XMage-Regelkern-Spielen, gebunden an Deck, Engine-Pin, Pilot-Policy und Seeds. Kein Beleg für reale Tisch-Siegraten. Exakte Handverweildauer: unbekannt (nicht gemessen)."));
  for (const run of state.simulations) {
    const inDeckCards = (run.cards || []).filter((c) => !c.card_id || qty(c.card_id) > 0 || state.commanderIds.includes(c.card_id));
    if (!inDeckCards.length) continue;
    const cTable = h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, "Karte"), h("th", { class: "num" }, "Spiele angeboten"), h("th", { class: "num" }, "Spiele gewirkt"), h("th", { class: "num" }, "ungespielt geblieben"), h("th", { class: "num" }, "Ø 1. Runde"))),
      h("tbody", {}, inDeckCards.slice(0, 25).map((c) => h("tr", {},
        h("td", { class: "name", onclick: () => { const card = c.card_id ? state.byId.get(c.card_id) : null; if (card) openCard(card); } }, c.card_name),
        h("td", { class: "num" }, `${c.games_offered}/${c.games_completed}`),
        h("td", { class: "num" }, `${c.games_cast_after_offer}/${c.games_offered}`),
        h("td", { class: "num" }, c.games_rotted),
        h("td", { class: "num" }, c.mean_first_cast_round === null ? "–" : Number(c.mean_first_cast_round).toFixed(1))))));
    body.append(h("h3", {}, `Karten-Angebote im Pod „${run.pod}“ (${run.games_completed} Spiele)`), cTable);
  }
}
function renderDeck() {
  const tabs = [["list", "Liste"], ["numbers", "Zahlen"], ["check", "Prüfung"], ["compare", "Vergleich"], ["diff", "Varianten-Diff"], ["sim", "Simulation"]];
  $("deck-tabs").replaceChildren(...tabs.map(([key, label]) => h("span", { class: "chip" + (state.tab === key ? " on" : ""), onclick: () => { state.tab = key; renderDeck(); } }, label)));
  const body = $("deck-body"); body.replaceChildren();
  ({ list: renderList, numbers: renderNumbers, check: renderCheck, compare: renderCompare, diff: renderDiff, sim: renderSimulations })[state.tab](body);
}
function renderAll() { renderHeader(); renderPool(); renderDeck(); }

// ---------- card window ----------
function closeModal() { $("modal").hidden = true; }
async function openCard(card) {
  const box = $("modal-box"); box.className = ""; box.replaceChildren();
  let face = "front";
  const picture = card.has_image ? image(card, "big") : h("div", { class: "muted" }, "Kein Bild in den Kartendaten.");
  const left = h("div", {}, picture, card.has_back ? h("div", { class: "actions" }, h("button", { type: "button", onclick: () => { face = face === "front" ? "back" : "front"; picture.src = `/img/${encodeURIComponent(card.card_id)}?face=${face}`; } }, "Rückseite / Vorderseite")) : null);
  const note = h("textarea", { placeholder: "Deine Notiz zur Karte" }); note.value = card.note;
  const saveMark = async (change) => {
    Object.assign(card, change);
    try { await api(`/api/cards/${encodeURIComponent(card.card_id)}/mark`, "PUT", { favorite: card.favorite, excluded: card.excluded, note: card.note }); renderPool(); openCard(card); }
    catch (error) { toast("Fehler: " + error.message); }
  };
  const count = qty(card.card_id);
  const frequencies = h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Quelldecks"), h("th", { class: "num" }, "mit Karte"), h("th", { class: "num" }, "Decks"), h("th", { class: "num" }, "Anteil"))),
    h("tbody", {}, Object.keys(state.cohorts).map((key) => { const f = freq(card, key); return h("tr", { class: f.total < state.small ? "low" : "" }, h("td", {}, cohortName(key)), h("td", { class: "num" }, f.hits), h("td", { class: "num" }, f.total), h("td", { class: "num" }, f.total ? (100 * f.share).toFixed(1) + " %" : "unbekannt")); })));
  const extra = h("div", {}, h("p", { class: "muted" }, "Lädt EDHREC-Zeilen."));
  const right = h("div", {},
    h("h2", {}, card.name), h("div", {}, mana(card.mana_cost), " ", h("span", { class: "muted" }, card.type_line), card.power !== null ? ` · ${card.power}/${card.toughness}` : ""),
    h("p", { style: "white-space:pre-line" }, card.text),
    card.roles.length ? h("p", {}, card.roles.map((role) => h("span", { class: "chip", style: "cursor:default;margin-right:4px" }, roleName(role)))) : null,
    h("p", { class: "note" }, `Sammlung: ${card.owned} im Besitz, ${card.available} frei` + (card.reserved ? `, ${card.reserved} reserviert` : "") + ` · Kartendaten: ${card.fact_source === "scryfall" ? "Scryfall" : "deine Tabelle"}` + (card.edhrec_rank ? ` · EDHREC-Rang ${card.edhrec_rank}` : "") + (card.game_changer ? " · Game Changer" : "") + ` · Simulator: ${card.sim_status || "unbekannt"}`),
    h("div", { class: "actions" },
      h("button", { type: "button", class: "primary", disabled: count >= maxCopies(card), onclick: () => { add(card); openCard(card); } }, "Ins Deck"),
      count ? h("button", { type: "button", onclick: () => { remove(card); openCard(card); } }, `Aus dem Deck (${count})`) : null,
      h("button", { type: "button", onclick: () => saveMark({ favorite: !card.favorite }) }, card.favorite ? "★ Favorit" : "☆ Favorit"),
      h("button", { type: "button", onclick: () => saveMark({ excluded: !card.excluded }) }, card.excluded ? "Ausschluss aufheben" : "Ausschließen"),
      h("button", { type: "button", onclick: closeModal }, "Schließen")),
    note, h("div", { class: "actions" }, h("button", { type: "button", onclick: () => saveMark({ note: note.value }) }, "Notiz speichern")),
    h("h3", {}, "Häufigkeit in den Quelldecks"), frequencies, h("p", { class: "note" }, "Gelb: Gruppe mit weniger als 30 Decks."), extra);
  box.append(left, right); $("modal").hidden = false;
  try {
    const detail = await api(`/api/cards/${encodeURIComponent(card.card_id)}?cohort=${encodeURIComponent(state.cohort)}`);
    const parts = [];
    if (detail.used_in && detail.used_in.length) {
      parts.push(h("h3", {}, "Verwendet in gespeicherten Varianten"),
        h("p", {}, detail.used_in.map((u) => `${u.name} (${u.branch})`).join(" · ")));
    }
    if (detail.cooccurrence && detail.cooccurrence.cards && detail.cooccurrence.cards.length) {
      const co = detail.cooccurrence;
      const coRows = co.cards.filter((item) => {
        const other = state.byId.get(item.card_id);
        return !other || !other.basic;
      });
      parts.push(h("h3", {}, `Zusammen gespielt in Quelldecks (${cohortName(co.cohort)}, Nenner: ${co.card_decks} Decks mit dieser Karte)`),
        h("table", {},
          h("thead", {}, h("tr", {}, h("th", {}, "Karte in deiner Sammlung (ohne Standardländer)"), h("th", { class: "num" }, "gemeinsam / Nenner"), h("th", { class: "num" }, "Anteil"), h("th", {}, ""))),
          h("tbody", {}, coRows.map((item) => {
            const other = state.byId.get(item.card_id);
            return h("tr", { class: co.card_decks < state.small ? "low" : "" },
              h("td", { class: "name", onclick: () => { if (other) openCard(other); } }, item.name),
              h("td", { class: "num" }, `${item.both_hits}/${item.card_decks}`),
              h("td", { class: "num" }, `${(100 * item.share).toFixed(1)} %`),
              h("td", {}, other && !qty(other.card_id) && maxCopies(other) > 0 ? h("button", { class: "small", type: "button", onclick: () => { add(other); openCard(card); } }, "+") : null));
          }))),
        h("p", { class: "note" }, "Reine Zählung (DERIVED_DESCRIPTIVE): wie oft eine andere Karte deiner Sammlung in denselben Quelldecks vorkommt."));
    }
    if (detail.neutral_boards && detail.neutral_boards.sections && detail.neutral_boards.sections.length) {
      const nb = detail.neutral_boards;
      parts.push(h("h3", {}, "Neutrale Nicht-Mainboard-Sektionen (Batch-Quellen)"),
        h("table", {},
          h("thead", {}, h("tr", {}, h("th", {}, "Sektion"), h("th", { class: "num" }, "Quellen mit Karte / Sektions-Quellen"), h("th", { class: "num" }, "Batch-Gesamt"), h("th", { class: "num" }, "Anteil in Sektion"))),
          h("tbody", {}, nb.sections.map((sec) => h("tr", {},
            h("td", {}, sec.section),
            h("td", { class: "num" }, `${sec.hits}/${sec.section_sources}`),
            h("td", { class: "num" }, sec.batch_sources),
            h("td", { class: "num" }, `${(100 * sec.share_of_section).toFixed(1)} %`))))),
        h("p", { class: "note" }, "Neutrale Quellkategorie der Deckautoren (Maybeboard = Überlegung, Cuts = vom Autor separiert). Keine negative Bewertung und niemals mit Mainboard-Frequenzen vermischt."));
    }
    if (detail.simulations && detail.simulations.length) {
      parts.push(h("h3", {}, "Simulationsergebnisse (SIMULATED_RESULT)"),
        h("table", {},
          h("thead", {}, h("tr", {}, h("th", {}, "Pod (Pin)"), h("th", { class: "num" }, "Spiele angeboten"), h("th", { class: "num" }, "Spiele gewirkt"), h("th", { class: "num" }, "ungespielt"), h("th", { class: "num" }, "Ø 1. Runde"), h("th", {}, "Handverweildauer"))),
          h("tbody", {}, detail.simulations.map((s) => h("tr", {},
            h("td", {}, `${s.pod} (${s.engine_pin})`),
            h("td", { class: "num" }, `${s.games_offered}/${s.games_completed}`),
            h("td", { class: "num" }, `${s.games_cast_after_offer}/${s.games_offered}`),
            h("td", { class: "num" }, s.games_rotted),
            h("td", { class: "num" }, s.mean_first_cast_round === null ? "unbekannt" : Number(s.mean_first_cast_round).toFixed(1)),
            h("td", { class: "muted" }, s.hand_dwell_status === "UNKNOWN" ? "unbekannt (nicht gemessen)" : s.hand_dwell_status))))));
    }
    const rows = detail.observations.filter((row) => row.metric === "inclusion_pct");
    const lift = new Map(detail.observations.filter((row) => row.metric === "lift").map((row) => [row.cohort, row.value]));
    const synergy = new Map(detail.observations.filter((row) => row.metric === "synergy_pct").map((row) => [row.cohort, row.value]));
    parts.push(h("h3", {}, "EDHREC-Seiten (getrennte Kohorten, nicht addierbar)"),
      rows.length ? h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Kohorte / Seite"), h("th", { class: "num" }, "Zähler/Nenner"), h("th", { class: "num" }, "Anteil"), h("th", { class: "num" }, "Lift"), h("th", { class: "num" }, "Synergy %"))),
        h("tbody", {}, rows.map((row) => h("tr", { class: row.denominator !== null && row.denominator < state.small ? "low" : "" },
          h("td", { title: row.snapshot || "" }, row.cohort.replace(/^edhrec:/, "")),
          h("td", { class: "num" }, row.denominator !== null ? `${row.numerator}/${row.denominator}` : `${row.numerator ?? "?"}/unbekannt`),
          h("td", { class: "num" }, row.value === null ? "unbekannt" : Number(row.value).toFixed(1) + " %"),
          h("td", { class: "num" }, lift.get(row.cohort) === null || lift.get(row.cohort) === undefined ? "unbekannt" : Number(lift.get(row.cohort)).toFixed(2)),
          h("td", { class: "num" }, synergy.get(row.cohort) === null || synergy.get(row.cohort) === undefined ? "unbekannt" : Number(synergy.get(row.cohort)).toFixed(1) + " %")))))
        : h("p", { class: "muted" }, "Keine EDHREC-Zeile gespeichert: unbekannt, nicht null."));
    if (detail.playgroup) {
      const pg = detail.playgroup;
      const pgRows = [];
      pgRows.push(
        h("tr", {}, h("td", {}, "Live Inclusion"), h("td", { class: "num" }, pg.live_inclusion_pct !== null ? `${Number(pg.live_inclusion_pct).toFixed(1)} %` : "unbekannt")),
        h("tr", {}, h("td", {}, "Times Brought / Decks Running"), h("td", { class: "num" }, `${pg.times_brought ?? "?"} / ${pg.decks_running ?? "?"}`)),
        h("tr", {}, h("td", {}, "Medianer Cast-Turn"), h("td", { class: "num" }, pg.median_cast_turn !== null ? `T${Number(pg.median_cast_turn).toFixed(1)}` : "unbekannt")),
        h("tr", {}, h("td", {}, "Drawn-to-Played Rate"), h("td", { class: "num" }, pg.drawn_to_played_pct !== null ? `${Number(pg.drawn_to_played_pct).toFixed(1)} %` : "unbekannt")),
        h("tr", {}, h("td", {}, "Winrate when cast"), h("td", { class: "num" }, pg.winrate_when_cast_pct !== null ? `${Number(pg.winrate_when_cast_pct).toFixed(1)} % (n=${pg.winrate_when_cast_n ?? "?"})` : "unbekannt")),
        h("tr", {}, h("td", {}, "Winrate in library"), h("td", { class: "num" }, pg.winrate_when_in_library_pct !== null ? `${Number(pg.winrate_when_in_library_pct).toFixed(1)} % (n=${pg.winrate_when_in_library_n ?? "?"})` : "unbekannt")),
        h("tr", {}, h("td", {}, "Observed Winrate-Gap"), h("td", { class: "num" }, pg.observed_winrate_gap_pp !== null ? `${pg.observed_winrate_gap_pp > 0 ? "+" : ""}${Number(pg.observed_winrate_gap_pp).toFixed(1)} pp` : "unbekannt")),
        h("tr", {}, h("td", {}, "95% Konfidenzintervall"), h("td", { class: "num" }, pg.ci_95_lower_pp !== null && pg.ci_95_upper_pp !== null ? `[${pg.ci_95_lower_pp > 0 ? "+" : ""}${Number(pg.ci_95_lower_pp).toFixed(1)} pp; ${pg.ci_95_upper_pp > 0 ? "+" : ""}${Number(pg.ci_95_upper_pp).toFixed(1)} pp]` : "unbekannt")),
        h("tr", {}, h("td", {}, "Konservativer Schätzer"), h("td", { class: "num" }, pg.conservative_ranking_indicator || "unbekannt")),
      );
      if (pg.quality_warnings && pg.quality_warnings.length) {
        pgRows.push(h("tr", { class: "low" }, h("td", {}, "Qualitätshinweise"), h("td", { class: "num" }, pg.quality_warnings.join(" · "))));
      }
      parts.push(
        h("h3", {}, `Playgroup Card Atlas (${pg.attribution || "Playgroup.gg, CC BY 4.0"})`),
        h("table", {}, h("tbody", {}, pgRows)),
        h("p", { class: "note" }, pg.disclosure || "Live-Korrelation (Playgroup.gg), keine kausale Kartenstärke.")
      );
    }
    extra.replaceChildren(...parts);
  } catch (error) { extra.replaceChildren(h("p", { class: "muted" }, "Zusatzdaten nicht lesbar: " + error.message)); }
}

// ---------- decks, variants, saving ----------
async function loadDecks() {
  state.decks = await api("/api/decks");
  if (!state.decks.length) {
    const created = await api("/api/decks", "POST", { name: "Chulane", commander_card_ids: state.commanderIds });
    state.deckId = created.deck_id; state.decks = await api("/api/decks");
  }
  if (!state.decks.some((deck) => deck.deck_id === state.deckId)) state.deckId = state.decks[0].deck_id;
  const deck = state.decks.find((item) => item.deck_id === state.deckId);
  if (!deck.branches.some((item) => item.branch === state.branch)) state.branch = deck.branches[0].branch;
  $("deck-select").replaceChildren(...state.decks.map((item) => h("option", { value: item.deck_id, selected: item.deck_id === state.deckId }, item.name)));
  $("branch-select").replaceChildren(...deck.branches.map((item) => h("option", { value: item.branch, selected: item.branch === state.branch }, `${item.branch} (${item.cards})${item.has_draft ? " *" : ""}`)));
}
function useCards(cards) {
  state.list = new Map();
  for (const entry of cards) if (entry.zone === "main" && state.byId.has(entry.card_id)) state.list.set(entry.card_id, entry.quantity);
}
async function loadBranch() {
  const deck = state.decks.find((item) => item.deck_id === state.deckId);
  const branch = deck.branches.find((item) => item.branch === state.branch);
  state.baseRevision = branch.revision_id;
  const [revision, draft] = await Promise.all([
    api(`/api/revisions/${encodeURIComponent(branch.revision_id)}`),
    api(`/api/decks/${encodeURIComponent(state.deckId)}/branches/${encodeURIComponent(state.branch)}/draft`),
  ]);
  if (draft.draft) { useCards(draft.draft.cards); state.dirty = true; }
  else { useCards(revision.cards); state.dirty = false; state.issues = revision.issues; state.shape = revision.shape; state.deckRoles = revision.roles || {}; }
  renderAll(); await syncDraft();
}
async function saveRevision(branch = state.branch) {
  const note = prompt("Kurze Notiz zu diesem Stand (darf leer sein):", "");
  if (note === null) return;
  try {
    const result = await api(`/api/decks/${encodeURIComponent(state.deckId)}/revisions`, "POST", { cards: entries(), branch, note, parent_revision_id: state.baseRevision });
    if (branch !== state.branch) await api(`/api/decks/${encodeURIComponent(state.deckId)}/branches/${encodeURIComponent(state.branch)}/draft`, "DELETE");
    state.branch = branch; state.baseRevision = result.revision_id; state.dirty = false;
    await loadDecks(); renderHeader(); $("save-state").textContent = "gespeichert"; toast("Stand gespeichert.");
  } catch (error) { toast("Fehler: " + error.message); }
}
async function showHistory() {
  const rows = await api(`/api/decks/${encodeURIComponent(state.deckId)}/history`);
  const box = $("modal-box"); box.className = "plain"; box.replaceChildren(h("h2", {}, "Verlauf"),
    h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Gespeichert"), h("th", { class: "num" }, "Karten"), h("th", {}, "Notiz"), h("th", {}, ""))),
      h("tbody", {}, rows.map((row) => h("tr", {}, h("td", {}, row.created_at.replace("T", " ").replace("Z", "")), h("td", { class: "num" }, row.cards), h("td", {}, row.note),
        h("td", {}, h("button", { type: "button", class: "small", onclick: async () => { const revision = await api(`/api/revisions/${encodeURIComponent(row.revision_id)}`); useCards(revision.cards); closeModal(); changed(); toast("Alter Stand geladen. Er wird erst mit Speichern zum aktuellen Stand."); } }, "Laden")))))),
    h("div", { class: "actions" }, h("button", { type: "button", onclick: closeModal }, "Schließen")));
  $("modal").hidden = false;
}
function showExport() {
  if (state.dirty) { toast("Bitte zuerst als Stand speichern. Exportiert wird immer ein gespeicherter Stand."); return; }
  const base = `/api/revisions/${encodeURIComponent(state.baseRevision)}/export`;
  const box = $("modal-box"); box.className = "plain"; box.replaceChildren(h("h2", {}, "Export"),
    h("p", {}, "Exportiert wird der gespeicherte Stand ", h("code", {}, state.baseRevision), "."),
    h("div", { class: "actions" }, h("a", { href: base + "?format=txt", target: "_blank", rel: "noopener" }, "Deckliste als Text"), h("a", { href: base + "?format=json", target: "_blank", rel: "noopener" }, "Deck für die Simulation (JSON)")),
    h("div", { class: "actions" }, h("button", { type: "button", onclick: closeModal }, "Schließen")));
  $("modal").hidden = false;
}

// ---------- start ----------
function setupControls() {
  $("color-filter").replaceChildren(...["W", "U", "G", "C"].map((letter) => h("span", { class: "chip", title: letter === "C" ? "farblos" : "", onclick: (event) => {
    if (state.colors.has(letter)) state.colors.delete(letter); else state.colors.add(letter);
    event.currentTarget.classList.toggle("on"); state.shown = 120; renderPool();
  } }, letter)));
  $("type-filter").replaceChildren(h("option", { value: "" }, "alle Typen"), ...GROUPS.map((group) => h("option", { value: group }, GROUP_NAMES[group])));
  $("role-filter").replaceChildren(h("option", { value: "" }, "alle Rollen"), ...state.roles.map((role) => h("option", { value: role }, roleName(role))), h("option", { value: "-" }, "ohne Rollenmarke"));
  $("cohort").replaceChildren(...Object.entries(state.cohorts).map(([key, size]) => h("option", { value: key }, `${cohortName(key)} (${size})`)));
  const sorts = [["freq:-1", "Häufigkeit in Quelldecks"], ["name:1", "Name"], ["mana_value:1", "Manawert"], ["edhrec:-1", "EDHREC-Anteil"], ["edhrec_rank:1", "EDHREC-Rang"], ["available:-1", "freie Kopien"]];
  $("sort").replaceChildren(...sorts.map(([value, label]) => h("option", { value }, label)), h("option", { value: "" }, "Spaltenkopf"));
  $("sort").addEventListener("change", () => { if (!$("sort").value) return; const [key, dir] = $("sort").value.split(":"); state.sortKey = key; state.sortDir = Number(dir); renderPool(); });
  $("cohort").addEventListener("change", () => { state.cohort = $("cohort").value; renderPool(); renderDeck(); });
  for (const id of ["q", "type-filter", "role-filter", "mv-min", "mv-max", "f-free", "f-notin", "f-fav", "f-excl", "f-sim"]) if ($(id)) $(id).addEventListener("input", () => { state.shown = 120; renderPool(); });
  const views = [["grid", "Bilder"], ["table", "Tabelle"]];
  const drawViews = () => $("view-toggle").replaceChildren(...views.map(([key, label]) => h("span", { class: "chip" + (state.view === key ? " on" : ""), onclick: () => { state.view = key; drawViews(); renderPool(); } }, label)));
  drawViews();
  $("columns").addEventListener("click", () => { $("column-menu").hidden = !$("column-menu").hidden; });
  $("column-menu").replaceChildren(...COLUMNS.map(([key, label]) => h("label", {}, h("input", { type: "checkbox", checked: state.columns.has(key), onchange: (event) => {
    if (event.target.checked) state.columns.add(key); else state.columns.delete(key);
    try { localStorage.setItem("studio-columns", JSON.stringify([...state.columns])); } catch (error) { /* view setting only */ }
    state.view = "table"; drawViews(); renderPool();
  } }), " " + label)));
  $("save").addEventListener("click", () => saveRevision());
  $("history").addEventListener("click", showHistory);
  $("export").addEventListener("click", showExport);
  $("new-branch").addEventListener("click", () => { const name = prompt("Name der neuen Variante:", ""); if (name && name.trim()) saveRevision(name.trim().slice(0, 60)); });
  $("deck-select").addEventListener("change", async () => { state.deckId = $("deck-select").value; await loadDecks(); await loadBranch(); });
  $("branch-select").addEventListener("change", async () => { state.branch = $("branch-select").value; await loadBranch(); });
  $("modal").addEventListener("click", (event) => { if (event.target === $("modal")) closeModal(); });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeModal(); });
}
async function start() {
  try {
    const stored = JSON.parse(localStorage.getItem("studio-columns") || "null");
    if (Array.isArray(stored)) state.columns = new Set(stored);
  } catch (error) { /* view setting only */ }
  try {
    const [pool, shapes, sims, recordedGames] = await Promise.all([api("/api/pool?commander=" + encodeURIComponent(COMMANDER)), api("/api/cohorts"), api("/api/simulations"), api("/api/games").catch(() => [])]);
    state.pool = pool.cards; state.byId = new Map(pool.cards.map((card) => [card.card_id, card]));
    state.roles = (pool.roles || []).sort((x, y) => roleName(x).localeCompare(roleName(y))); state.cohorts = pool.cohorts; state.small = pool.small_denominator; state.commanderIds = pool.commander_ids; state.shapes = shapes; state.simulations = sims || []; state.recordedGames = recordedGames || [];
    setupControls(); await loadDecks(); await loadBranch();
  } catch (error) {
    $("pool-body").replaceChildren(h("p", {}, "Das Studio konnte die Daten nicht laden: " + error.message), h("p", { class: "muted" }, "Sind Sammlung und Kartendaten importiert?"));
  }
}
start();
