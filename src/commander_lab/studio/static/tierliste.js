"use strict";
// Commander Studio tier list. Shows the evidence per card and two clearly separate things:
// the "Stärke-Index (Schätzung aus Nutzungsdaten)" and the "Ergebnis aus Partien (noch nicht bewertet)".
// All text from data is set as text, never as HTML.

const COMMANDER = StudioCommander.current;
const VIEW_NAMES = { commander: StudioCommander.shortName(COMMANDER), global: "Global (ohne Commander)", deck: "Aktuelle Deckrevision" };
const ROLE_NAMES = { ramp: "Ramp", mana_rock: "Manastein", mana_dork: "Mana-Kreatur", land_ramp: "Land-Ramp", card_draw: "Karten ziehen", card_advantage: "Kartenvorteil", cantrip: "Cantrip", tutor: "Tutor", removal: "Entfernung", board_wipe: "Massenentfernung", counterspell: "Konter", bounce: "Bounce", flicker: "Blink", recursion: "Rückholen", protection: "Schutz", graveyard_hate: "Friedhofshass", lifegain: "Lebensgewinn" };
const ORIGIN_NAMES = { SCRYFALL_TAGGER_ORIGINAL: "Tagger", CROSSWALK_NORMALIZED: "Zuordnung", ORACLE_TEXT_REVIEW: "Oracle-Text", LEGACY_UNSPECIFIED: "Altbestand" };
const FEATURE_NAMES = { creature_spell: "Kreaturenzauber", land: "Land", enters_trigger_text: "ETB-Text", produces_mana: "erzeugt Mana" };
const LAYER_NAMES = { fact: "Fakten und Mechanik", observed_deck: "In Decks beobachtet", observed_game: "In echten Spielen beobachtet", combo_verified: "Geprüfte Kombos", simulated_result: "Simulation (XMage)" };
const STATUS_NAMES = {
  PRESENT: ["vorhanden", "good"],
  ABSENT_IN_KNOWN_CORPUS: ["0 im bekannten Korpus (fehlende Beobachtung, keine Schwäche)", "warn"],
  NONE_RECORDED: ["nichts erfasst", "dim"],
  NOT_COLLECTED: ["Quelle noch nicht importiert", "warn"],
  NOT_APPLICABLE: ["in dieser Ansicht nicht anwendbar", "dim"],
};
const NEED_NAMES = {
  NO_GAME_EVIDENCE: "keine Spielbelege",
  NOT_OBSERVED_IN_CORPUS: "nicht im Korpus beobachtet",
  SMALL_DENOMINATOR: "kleiner Nenner",
  EDHREC_TIME_UNKNOWN: "EDHREC-Zeit unbekannt",
  NO_ROLE_CLAIM: "keine Rolle erfasst",
  SMALL_GAME_SAMPLE: "kleine Spielstichprobe",
};
const SORTS = [
  ["name", "Name"],
  ["mv", "Manawert"],
  ["strength", "Stärke-Index (Schätzung, zu wenig Daten zuletzt)"],
  ["spread", "Verbreitung (gezählt): Anteil im Universum"],
  ["spread_level", "Verbreitung (gezählt): Stufe im Universum"],
  ["layers", "Anzahl vorhandener Schichten"],
  ["corpus", "Anteil in Quelldecks (nur Lesehilfe)"],
  ["edhrec", "EDHREC Inclusion (nur Lesehilfe)"],
  ["games", "Partien mit der Karte (nur Lesehilfe)"],
  ["research", "Forschungsbedarf (Heuristik)"],
];
const INDEX_HEADING = "Stärke-Index (Schätzung aus Nutzungsdaten)";
const OUTCOME_HEADING = "Ergebnis aus Partien (noch nicht bewertet)";
const INDEX_TEXT = "Die Stufen S bis D und „zu wenig Daten“ kommen aus dem Stärke-Index: eine Schätzung aus Nutzungsdaten (EDHREC, gezählte Decklisten, Turnierlisten, Kombos). Sie ist keine gemessene Siegrate.";
const OUTCOME_TEXT = "Ein Ergebnis-Tier aus Partien braucht eine vorab festgelegte Zielgröße, ein kalibriertes Modell und Belege außerhalb der Trainingsdaten. Ein solches Modell gibt es noch nicht, deshalb hat keine Karte ein Ergebnis aus Partien. Häufigkeit in Decks, EDHREC-Werte, deine Markierungen und reine Zählungen setzen nie allein ein Ergebnis-Tier. Fehlende Belege sind nie ein niedriger Tier.";
const GAME_NOTES = {
  PRESENT: "Beobachteter Zusammenhang mit Verzerrung durch Pilot, Runde und Spielverlauf. Kein kausaler Effekt.",
  NONE_RECORDED: "Die Spielquelle hat für diese Karte keine verwertbare Zeile.",
  NOT_COLLECTED: "Noch keine Spielquelle importiert (Playgroup Card Atlas).",
};
const SPREAD_LABEL = "Verbreitung (gezählt)";
const LEVEL_RANK = { S: 5, A: 4, B: 3, C: 2, D: 1, U: 0 };
const NO_UNIVERSE = "kein Universum gewählt";
const FILTER_LABEL = "Filterkarte";
const SPREAD_NOTE = "Gezählt: in wie vielen Decks des gewählten Universums die Karte steht. Das ist keine Kartenstärke und kein Tier. Favoriten, Ausschlüsse und Notizen ändern keine Zählung.";
const REASON_NAMES = { FILTER_CARD: "Filterkarte des Universums", SHARE_CUT: "Anteil erreicht die Schwelle", BELOW_LOWEST_CUT: "Anteil unter der niedrigsten Schwelle", UNIVERSE_TOO_SMALL: "Universum kleiner als das Minimum", DENOMINATOR_MISSING: "Nenner fehlt", NAME_NOT_FOUND_IN_UNIVERSE: "Name kommt im Universum nicht vor (unbekannt, nicht null)" };
const UNIVERSE_KEY = "studio.universe.profile";
const STRENGTH_KEY = "studio.strength.settings";
const STRENGTH_NOTE = "Der Stärke-Index ist eine Schätzung aus Nutzungssignalen (wie oft die Karte bei diesem Commander, im Bracket, in den gewählten Decklisten und in Turnierlisten gespielt wird). Er ist keine gemessene Siegrate. Eine Karte, die eine Quelle nicht nennt, senkt die Abdeckung, nie die Karte. Favoriten, Ausschlüsse und Notizen fließen nicht ein.";
const UNKNOWN_TIER = "zu wenig Daten";
const BRACKET_NAMES = { core: "Core (Bracket 1–2)", upgraded: "Upgraded (Bracket 3)", optimized: "Optimized (Bracket 4)", cedh: "cEDH (Bracket 5)", none: "kein Bracket" };
const COMPONENT_STATUS = {
  PRESENT: ["vorhanden", "good"],
  NO_VALUE: ["kein Wert (fehlende Beobachtung)", "warn"],
  NOT_COLLECTED: ["Quelle nicht importiert", "dim"],
  FILTER_CARD: ["Filterkarte (nicht gerankt)", "dim"],
  NOT_RANKED: ["nicht bewertet", "dim"],
  MISSING_AS_LOWEST: ["nicht gelistet, als niedrigster Rang gezählt", "warn"],
};
const STRENGTH_TIERS = ["S", "A", "B", "C", "D", "U", "N"];
const TIER_FILTER_NAMES = { U: "zu wenig Daten", N: "nicht bewertet" };
const PERCENTILE_SORT = "pct:";
const SMALL_FIRST = new Set(["name", "mv"]);

const state = {
  view: "commander", tab: "cards", data: null, marks: new Map(), decks: [],
  universe: { profiles: [], name: "", summary: null, spread: null, options: null },
  strength: { meta: null, settings: null, profiles: [], result: null, map: null, ticket: 0, tiers: new Set(), draft: { fields: {}, name: "" } },
  deckCards: null, deckRoles: {}, ticket: 0, need: "", sortKey: "name", sortDir: 1, shown: 150,
};

const $ = (id) => document.getElementById(id);
function h(tag, props, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(props || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") el.className = value;
    else if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else if (key in el && key !== "list") el[key] = value;
    else el.setAttribute(key, value);
  }
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return el;
}
async function api(path, body, method) {
  const options = { headers: { "X-Studio": "1" } };
  if (body !== undefined) { options.method = method || "POST"; options.headers["Content-Type"] = "application/json"; options.body = JSON.stringify(body); }
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
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { box.hidden = true; }, 4000);
}
const roleName = (key) => ROLE_NAMES[key] || key;
const unknown = (text = "unbekannt") => h("span", { class: "unknown" }, text);
const pct = (part, of) => (of ? `${(100 * part / of).toFixed(0)} %` : "");

// ---------- evidence accessors ----------
const layer = (card, name) => card.layers[name];
function corpusAll(card) {
  const items = layer(card, "observed_deck").items || [];
  return items.find((item) => item.kind === "corpus" && item.cohort === "all") || null;
}
function widest(card) {
  const edhrec = layer(card, "observed_deck").edhrec;
  return edhrec ? edhrec.widest_inclusion : null;
}
const presentCount = (card) => card.coverage.present.length;
function sortValue(card, key) {
  if (key === "name") return card.name.toLowerCase();
  if (key === "mv") return card.mana_value;
  if (key === "strength") { const item = strengthItem(card); return item && item.tier !== "U" && item.tier !== "N" ? item.index : null; } // tier U sorts last
  if (key === "spread") { const item = state.universe.spread ? state.universe.spread.get(card.card_id) : undefined; return item && item.share !== null && item.share !== undefined ? item.share : null; }
  if (key === "spread_level") { const item = state.universe.spread ? state.universe.spread.get(card.card_id) : undefined; return item && !item.filter_card ? (LEVEL_RANK[item.level] ?? 0) + (item.share || 0) : null; }
  if (key.startsWith(PERCENTILE_SORT)) { // percentile of one single component; no value sorts last
    const item = strengthItem(card);
    const row = item ? item.components.find((c) => c.component === key.slice(PERCENTILE_SORT.length)) : null;
    return row && row.percentile !== null && row.percentile !== undefined ? row.percentile : null;
  }
  if (key === "layers") return presentCount(card);
  if (key === "corpus") { const c = corpusAll(card); return c && c.of ? c.decks / c.of : null; }
  if (key === "edhrec") { const w = widest(card); return w ? w.value : null; }
  if (key === "games") { const a = layer(card, "observed_game").atlas; return a && a.status === "OK" ? a.times_brought : null; }
  if (key === "research") { const r = card.coverage.research_priority; return r ? r.score : null; }
  return null;
}

// ---------- filters and sorting ----------
function cardRoles(card) { return layer(card, "fact").roles.map((claim) => claim.role); }
function visibleCards() {
  const words = $("q").value.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const type = $("type-filter").value, role = $("role-filter").value;
  const spreadLevel = $("spread-filter") ? $("spread-filter").value : "";
  const free = $("f-free").checked, fav = $("f-fav").checked, showExcluded = $("f-excl").checked;
  let rows = state.data.cards.filter((card) => {
    const mark = state.marks.get(card.card_id) || {};
    if (state.view === "deck" && !(state.deckCards && state.deckCards.has(card.card_id))) return false;
    if (type && card.group !== type) return false;
    if (role && !cardRoles(card).includes(role)) return false;
    if (state.strength.tiers.size && state.strength.map) { const item = state.strength.map.get(card.card_id); if (!item || !state.strength.tiers.has(item.tier)) return false; }
    if (spreadLevel && state.universe.spread) { const item = state.universe.spread.get(card.card_id); if (!item || item.level !== spreadLevel) return false; }
    if (free && state.view !== "deck" && !(card.available > 0)) return false; // a deck is always shown whole
    if (fav && !mark.favorite) return false;
    if (!showExcluded && mark.excluded) return false;
    const hay = `${card.name} ${card.type_line}`.toLowerCase();
    return words.every((word) => hay.includes(word));
  });
  const key = state.sortKey, dir = state.sortDir;
  rows = rows.map((card) => [sortValue(card, key), card]);
  rows.sort((a, b) => {
    if (a[0] === null && b[0] === null) return a[1].name.localeCompare(b[1].name);
    if (a[0] === null) return 1;
    if (b[0] === null) return -1;
    return (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : a[1].name.localeCompare(b[1].name)) * dir;
  });
  return rows.map((row) => row[1]);
}

// ---------- cells ----------
function thumb(card) {
  if (!card.has_image) return h("span", { class: "thumb" });
  return h("img", { class: "thumb", loading: "lazy", alt: "", src: `/img/${encodeURIComponent(card.card_id)}` });
}
function featureBadges(card) {
  return layer(card, "fact").features.filter((f) => f.holds).map((f) => h("span", { class: "badge dim", title: f.rule }, FEATURE_NAMES[f.feature] || f.feature));
}
function roleBadges(card) {
  const claims = layer(card, "fact").roles;
  if (!claims.length) return unknown("keine Rolle erfasst");
  return claims.map((claim) => h("span", { class: "badge", title: `Herkunft: ${ORIGIN_NAMES[claim.origin] || claim.origin}` }, `${roleName(claim.role)} · ${ORIGIN_NAMES[claim.origin] || claim.origin}`));
}
function corpusCell(card) {
  const item = corpusAll(card);
  if (!item) return unknown(layer(card, "observed_deck").status === "NOT_COLLECTED" ? "keine Quelle" : "unbekannt");
  const text = `${item.decks}/${item.of} · ${pct(item.decks, item.of)}`;
  return h("span", { class: item.decks ? "" : "unknown", title: item.decks ? "Quelldecks mit der Karte, ohne Duplikate" : "0 in einem bekannten Korpus: fehlende Beobachtung, keine Schwäche" }, text);
}
function edhrecCell(card) {
  const w = widest(card);
  if (!w) return unknown(layer(card, "observed_deck").edhrec ? "keine Beobachtung" : "keine Quelle");
  const den = w.denominator === null ? "Nenner unbekannt" : `${w.numerator}/${w.denominator}`;
  return h("span", { title: `Ansicht ${w.cohort}; Datenklasse ${w.data_class}` }, `${den}`, w.small_denominator ? h("span", { class: "badge warn" }, "n < 30") : null, w.snapshot_known ? null : h("span", { class: "badge dim" }, "Zeit unbekannt"));
}
function gameCell(card) {
  const game = layer(card, "observed_game"), atlas = game.atlas;
  if (game.status !== "PRESENT" || !atlas) return unknown(game.status === "NOT_COLLECTED" ? "keine Quelle" : "keine Beobachtung");
  const brought = atlas.times_brought === null ? "n unbekannt" : `n = ${atlas.times_brought}`;
  const gap = atlas.observed_winrate_gap_pp === null ? null : `Differenz ${atlas.observed_winrate_gap_pp > 0 ? "+" : ""}${atlas.observed_winrate_gap_pp} Pp`;
  const ci = atlas.ci_95_lower_pp === null || atlas.ci_95_upper_pp === null ? null : ` (95 %: ${atlas.ci_95_lower_pp} bis ${atlas.ci_95_upper_pp})`;
  return h("span", { title: "Playgroup.gg (CC BY 4.0), alle Commander, nur Live-Partien. Beobachteter Zusammenhang, keine kausale Kartenstärke." }, brought, gap ? ` · ${gap}` : "", ci || "", atlas.insufficient_sample ? h("span", { class: "badge warn" }, "kleine Stichprobe") : null);
}
function simCell(card) {
  const sim = layer(card, "simulated_result");
  if (sim.status === "NOT_APPLICABLE") return unknown("–");
  if (!sim.totals) return unknown("nicht simuliert");
  return `${sim.totals.games_cast_after_offer}/${sim.totals.games_offered} Partien`;
}
function strengthItem(card) { const map = state.strength.map; return map ? map.get(card.card_id) || null : null; }
function strengthCell(card) {
  if (state.view === "global") return h("span", { class: "strength none" }, "nur je Commander");
  const item = strengthItem(card);
  if (!item) return h("span", { class: "strength none" }, state.strength.map ? "nicht berechnet" : "–");
  const title = `Schätzung aus Nutzungssignalen, keine Siegrate. Abdeckung ${(100 * item.coverage).toFixed(0)} %, ${item.present} Signale vorhanden.`;
  if (item.tier === "N") return h("span", { class: "strength lvl-N", title: item.note }, item.note);
  if (item.tier === "U") return h("span", { class: "strength lvl-U", title }, UNKNOWN_TIER);
  return h("span", { class: `strength lvl-${item.tier}`, title }, h("span", { class: "level" }, item.tier), item.index.toFixed(1));
}
function spreadCell(card) {
  const uni = state.universe;
  if (!uni.name || !uni.spread) return h("span", { class: "spread none" }, NO_UNIVERSE);
  const item = uni.spread.get(card.card_id);
  if (!item) return h("span", { class: "spread lvl-U" }, "unbekannt");
  return spreadBadge(item, uni.spread.universe);
}
function spreadBadge(item, universe) {
  const subset = universe.subset_note ? ` ${universe.subset_note}.` : "";
  if (item.filter_card) {
    return h("span", { class: "spread lvl-F", title: `${FILTER_LABEL}: das Universum verlangt diese Karte, sie steht per Definition in jedem Deck der Teilmenge (ohne Zählung, ohne Stufe). Universum ${universe.profile}.${subset}` }, FILTER_LABEL);
  }
  const counted = item.matched ? `${item.hits}/${item.denominator}` : "unbekannt";
  const title = `${SPREAD_LABEL}: ${REASON_NAMES[item.reason] || item.reason}. Universum ${universe.profile}, ${universe.denominator} Decks, Stand ${universe.snapshot_id}.${subset}`;
  return h("span", { class: `spread lvl-${item.level}`, title }, h("span", { class: "level" }, item.level), counted);
}
function statusBadge(status) {
  const [text, kind] = STATUS_NAMES[status] || [status, "dim"];
  return h("span", { class: `badge ${kind}` }, text);
}
function needBadges(card) {
  return card.coverage.needs.map((need) => h("span", { class: "badge warn" }, NEED_NAMES[need] || need));
}

// ---------- tables ----------
function cardsTable(cards) {
  const commander = state.view !== "global";
  const head = ["Ergebnis aus Partien", "Stärke-Index (Schätzung)", SPREAD_LABEL, "Karte", "MW", "Mechanik", "Rollen", ...(commander ? ["Quelldecks", "EDHREC Inclusion", "Echte Spiele", "Simulation"] : ["Beliebtheit (global)", "Echte Spiele"]), "Schichten", ...(state.view === "deck" ? ["im Deck"] : [])];
  const rows = cards.slice(0, state.shown).map((card) => {
    const mark = state.marks.get(card.card_id) || {};
    const rank = (layer(card, "observed_deck").items || []).find((item) => item.kind === "edhrec_rank_global");
    return h("tr", {},
      h("td", {}, h("span", { class: "tier", title: "Ergebnis aus Partien: noch nicht bewertet. Es gibt kein Modell mit Ergebnisdaten." }, "Unbewertet")),
      h("td", {}, strengthCell(card)),
      h("td", {}, spreadCell(card)),
      h("td", { class: "cardcell name", onclick: () => openCard(card) }, thumb(card), mark.favorite ? h("span", { class: "star" }, "★ ") : null, card.name),
      h("td", { class: "num" }, card.mana_value),
      h("td", {}, featureBadges(card)),
      h("td", {}, roleBadges(card)),
      ...(commander ? [h("td", {}, corpusCell(card)), h("td", {}, edhrecCell(card)), h("td", {}, gameCell(card)), h("td", {}, simCell(card))] : [h("td", { class: "num" }, rank ? `Rang ${rank.rank}` : unknown("unbekannt")), h("td", {}, gameCell(card))]),
      h("td", { title: card.coverage.present.map((name) => LAYER_NAMES[name]).join(", ") }, `${presentCount(card)}/4`),
      ...(state.view === "deck" ? [h("td", { class: "num" }, state.deckCards.get(card.card_id))] : []));
  });
  return h("table", {}, h("thead", {}, h("tr", {}, head.map((label) => h("th", {}, label)))), h("tbody", {}, rows));
}
function researchTable(cards) {
  const wanted = state.need || "";
  const rows = cards.filter((card) => card.coverage.needs.length && (!wanted || card.coverage.needs.includes(wanted))).slice(0, 200).map((card) => {
    const priority = card.coverage.research_priority;
    return h("tr", {},
      h("td", { class: "cardcell name", onclick: () => openCard(card) }, thumb(card), card.name),
      h("td", { class: "num", title: "Heuristik für die Reihenfolge der Recherche, keine Kartenstärke" }, priority ? priority.score.toFixed(2) : unknown("–")),
      h("td", {}, card.coverage.gap_grade || unknown("–")),
      h("td", {}, needBadges(card)),
      h("td", {}, roleBadges(card)));
  });
  return h("table", {}, h("thead", {}, h("tr", {}, ["Karte", "Priorität (Heuristik)", "Abdeckung", "Was fehlt", "Rollen"].map((label) => h("th", {}, label)))), h("tbody", {}, rows));
}

function render() {
  const body = $("pool-body");
  body.replaceChildren();
  if (!state.data) return;
  const cards = visibleCards();
  $("count").textContent = `${cards.length} Karten`;
  if (state.tab === "research") {
    if (state.view === "global") { body.append(h("p", { class: "note" }, `Der Forschungsbedarf wird je Commander berechnet. Wähle die Ansicht ${VIEW_NAMES.commander}.`)); return; }
    const needs = [...new Set(state.data.cards.flatMap((card) => card.coverage.needs))].sort();
    const select = h("select", { id: "need-filter", onchange: () => { state.need = select.value; render(); } }, h("option", { value: "" }, "alle Lücken"), needs.map((need) => h("option", { value: need }, NEED_NAMES[need] || need)));
    const previous = needs.includes(state.need) ? state.need : "";
    state.need = previous;
    body.append(h("p", { class: "note" }, "Reihenfolge aus fehlender Evidenz mal Deck-Relevanz. Eine Lücke ist kein schlechtes Urteil über die Karte."), h("label", {}, "Lücke ", select));
    select.value = previous;
    body.append(researchTable(cards));
    return;
  }
  body.append(cardsTable(cards));
  if (cards.length > state.shown) body.append(h("p", {}, h("button", { type: "button", onclick: () => { state.shown += 200; render(); } }, `weitere ${Math.min(200, cards.length - state.shown)} zeigen`)));
}

// ---------- notice ----------
// Source decks are counted per commander only; decks of another commander or without one are named, never added.
function bindingLine() {
  const binding = state.data.corpus_binding;
  if (state.view === "global" || !binding) return null;
  const parts = [`Quelldecks für ${VIEW_NAMES.commander}: ${binding.bound_decks}`];
  if (binding.other_commander_decks) parts.push(`${binding.other_commander_decks} gehören zu anderen Commandern und zählen hier nicht`);
  if (binding.unbound_decks) parts.push(`${binding.unbound_decks} ohne Commander-Zuordnung zählen nirgends`);
  return h("div", { class: "summary" }, parts.join(" · "), binding.bound_decks ? "" : " · Für diesen Commander sind noch keine Quelldecks importiert: fehlende Beobachtung, keine Schwäche.");
}
function renderNotice() {
  const summary = state.data.summary, policy = state.data.tier_policy;
  const status = summary.layer_status;
  const line = (name) => `${LAYER_NAMES[name]}: ${Object.entries(status[name]).map(([key, n]) => `${n} ${(STATUS_NAMES[key] || [key])[0]}`).join(", ")}`;
  $("notice").replaceChildren(
    h("div", { title: `${policy.version}: ${policy.rule}` }, h("b", {}, `${INDEX_HEADING}: `), INDEX_TEXT),
    h("div", { title: `${policy.version}: ${policy.rule}` }, h("b", {}, `${OUTCOME_HEADING}: `), OUTCOME_TEXT),
    h("div", { class: "summary" }, `${summary.cards} Karten in dieser Ansicht. `, ["observed_deck", "observed_game", "simulated_result"].map(line).join(" · ")),
    ...[bindingLine()].filter(Boolean));
  $("tier-pill").textContent = `Ergebnis aus Partien: ${summary.unrated} von ${summary.cards} noch nicht bewertet`;
}

// ---------- evidence drawer ----------
function table(heads, rows) {
  return h("table", {}, h("thead", {}, h("tr", {}, heads.map((x) => h("th", {}, x)))), h("tbody", {}, rows.map((row) => h("tr", {}, row.map((cell) => h("td", {}, cell))))));
}
function drawer(card) {
  const box = [];
  const heading = (name, status) => h("h3", {}, LAYER_NAMES[name], statusBadge(status));
  const fact = layer(card, "fact");
  box.push(h("div", { class: "layer" }, heading("fact", fact.status),
    h("p", {}, `Manawert ${fact.mana_value} · ${fact.type_line} · Quelle der Fakten: ${fact.fact_source} · Regelstand ${fact.rules_version}`),
    table(["Merkmal", "trifft zu", "Regel"], fact.features.map((f) => [FEATURE_NAMES[f.feature] || f.feature, f.holds ? "ja" : "nein", h("span", { class: "rule" }, f.rule)])),
    h("p", {}, "Rollen mit Herkunft (Tagger-Rollen sind Community-Einordnungen):"),
    fact.roles.length ? fact.roles.map((c) => h("span", { class: "badge", title: [c.original_tag, c.mapping_rule].filter(Boolean).join(" · ") }, `${roleName(c.role)} · ${ORIGIN_NAMES[c.origin] || c.origin}`)) : unknown("keine Rolle erfasst")));

  const deck = layer(card, "observed_deck");
  const corpus = (deck.items || []).filter((item) => item.kind === "corpus");
  const rank = (deck.items || []).find((item) => item.kind === "edhrec_rank_global");
  const deckBox = h("div", { class: "layer" }, heading("observed_deck", deck.status));
  if (rank) deckBox.append(h("p", {}, `Globale Beliebtheit (Scryfall, EDHREC-Rang): ${rank.rank}. Niedriger ist beliebter. Das ist kein Stärkemaß.`));
  if (corpus.length) deckBox.append(h("p", {}, "Quelldecks nach Gruppe, jeweils mit eigenem Nenner. Die Gruppen überlappen: nie addieren."), table(["Gruppe", "Decks mit Karte", "von", "Anteil", ""], corpus.map((item) => [item.cohort, item.decks, item.of, pct(item.decks, item.of), item.small_denominator ? h("span", { class: "badge warn" }, "n < 30") : ""])));
  if (deck.edhrec_rows && deck.edhrec_rows.length) {
    deckBox.append(h("p", {}, "EDHREC-Beobachtungen. Inclusion, Lift und Synergy sind verschiedene Maße und nie ein gemeinsamer Wert."), table(["Ansicht", "Maß", "Wert", "Decks/Nenner", "Stand", "Datenklasse"], deck.edhrec_rows.map((row) => [row.cohort, row.metric, row.value === null ? unknown() : row.value, row.denominator_known ? `${row.numerator ?? "?"}/${row.denominator}${row.small_denominator ? " (n < 30)" : ""}` : unknown("Nenner unbekannt"), row.snapshot_known ? row.snapshot : unknown("Zeit unbekannt"), row.data_class])));
  } else if (state.view !== "global") {
    deckBox.append(h("p", {}, "Keine EDHREC-Beobachtung für diese Karte."));
  }
  if (state.view === "global" && !rank) deckBox.append(h("p", {}, "Für die globale Ansicht ist noch keine commanderunabhängige Deck-Quelle importiert."));
  box.push(deckBox);

  const game = layer(card, "observed_game");
  const atlas = game.atlas;
  const val = (x, suffix = "") => (x === null || x === undefined ? unknown() : `${x}${suffix}`);
  box.push(h("div", { class: "layer" }, heading("observed_game", game.status), h("p", {}, GAME_NOTES[game.status] || game.note),
    atlas && game.status === "PRESENT" ? [
      h("p", {}, `Quelle: Playgroup.gg Card Atlas (CC BY 4.0). Grundgesamtheit: alle Commander, nur Playgroup-Live-Partien.`),
      table(["Messwert", "Wert"], [
        ["Mitgebracht (Partien)", val(atlas.times_brought)],
        ["Live-Inclusion", val(atlas.live_inclusion_pct, " %")],
        ["Median Zug des ersten Wirkens", val(atlas.median_cast_turn)],
        ["Siegrate, wenn gewirkt", val(atlas.winrate_when_cast_pct, " %")],
        ["Differenz gewirkt gegen Bibliothek", val(atlas.observed_winrate_gap_pp, " Pp")],
        ["95-%-Intervall der Differenz", atlas.ci_95_lower_pp === null || atlas.ci_95_upper_pp === null ? unknown() : `${atlas.ci_95_lower_pp} bis ${atlas.ci_95_upper_pp} Pp`],
        ["Stichprobe", atlas.insufficient_sample ? h("span", { class: "badge warn" }, "zu klein") : "ausreichend laut Import"],
      ]),
      h("p", {}, "Die Differenz vergleicht Partien, in denen die Karte gewirkt wurde, mit Partien, in denen sie in der Bibliothek blieb. Wer eine Karte wirken kann, steht oft schon besser da. Das ist kein Beweis für Kartenstärke."),
    ] : null));
  const combo = layer(card, "combo_verified");
  box.push(h("div", { class: "layer" }, heading("combo_verified", combo.status), combo.note ? h("p", {}, "Eine gelistete Kombo ist kein Beleg für Stärke und kein bestandener Engine-Test.") : null));
  const sim = layer(card, "simulated_result");
  box.push(h("div", { class: "layer" }, heading("simulated_result", sim.status), sim.totals ? h("p", {}, `${sim.totals.runs} Läufe: in ${sim.totals.games_cast_after_offer} von ${sim.totals.games_offered} Partien nach dem Angebot gespielt (${sim.totals.cast_count} Zauber). Simulierte Ergebnisse stehen für sich und werden nie mit echten Spielen verrechnet.`) : null));

  const cov = card.coverage;
  box.push(h("div", { class: "layer" }, h("h3", {}, "Abdeckung und Forschungsbedarf"),
    h("p", {}, `Vorhanden: ${cov.present.map((name) => LAYER_NAMES[name]).join(", ") || "nichts"}.`),
    cov.needs.length ? h("div", {}, needBadges(card)) : h("p", {}, "Keine offene Lücke."),
    cov.gap_grade ? h("p", {}, `Lückenklasse: ${cov.gap_grade}. Forschungspriorität (Heuristik, keine Kartenstärke): ${cov.research_priority.score.toFixed(2)}${cov.research_priority.long_tail ? ", Long-Tail-Kandidat" : ""}.`) : null));
  return box;
}
function strengthBox(card) {
  const item = strengthItem(card);
  const label = item && item.tier === "N" ? item.note : item && item.tier === "U" ? UNKNOWN_TIER : null;
  const box = h("div", { class: "layer" }, h("h3", {}, INDEX_HEADING,
    item ? h("span", { class: `strength lvl-${item.tier}` }, label !== null ? label : h("span", {}, h("span", { class: "level" }, item.tier), item.index.toFixed(1))) : null),
    h("p", {}, STRENGTH_NOTE));
  if (!item) { box.append(h("p", {}, state.view === "global" ? "Der Index wird je Commander berechnet." : "Für diese Karte liegt keine Berechnung vor.")); return box; }
  if (item.tier === "N") { box.append(h("p", {}, `${item.note}: ${item.reason === "NOT_RANKED_COMMANDER" ? "der Commander" : "ein Standardland"} bekommt keine Stufe und nimmt keinem Rang einen Platz weg. Die Einstellung „Commander und Standardländer bewerten“ ändert das.`)); }
  else box.append(h("p", {}, `Abdeckung ${(100 * item.coverage).toFixed(0)} % (Gewicht der vorhandenen Signale an allen gewichteten). ${item.tier === "U" ? "Zu wenig Daten für eine Stufe: das sagt nichts über die Stärke der Karte." : ""}`));
  const universe = state.strength.result && state.strength.result.universe;
  if (universe && universe.subset_note) box.append(h("p", { class: "rule" }, `Decklisten-Universum ${universe.profile}: ${universe.denominator} Decks. ${universe.subset_note}.`));
  box.append(table(["Signal", "Wert", "Zähler/Nenner", "Wilson-Untergrenze", "Perzentil", "Gewicht", "Status", "Hinweis"], item.components.map((c) => {
    const [text, kind] = COMPONENT_STATUS[c.status] || [c.status, "dim"];
    const percentile = c.percentile === null ? unknown("–") : c.group_fallback ? `${c.percentile.toFixed(3)} (Rang im ganzen Pool (Gruppe zu klein))` : `${c.percentile.toFixed(3)}${c.group ? ` (Gruppe ${c.group}, ${c.group_size})` : ""}`;
    return [h("span", { title: c.signal }, c.label), c.value === null ? unknown() : Number(c.value.toPrecision(4)), c.denominator ? `${c.numerator}/${c.denominator}` : unknown("–"), c.wilson === null ? unknown("–") : c.wilson.toFixed(4), percentile, c.weight, h("span", { class: `badge ${kind}` }, text), c.note ? h("span", { class: "rule" }, c.note) : ""];
  })));
  return box;
}
async function alternativesBox(card) {
  const inDeck = state.view === "deck" && state.deckCards ? [...state.deckCards.keys()] : [];
  const data = await api(`/api/cards/${encodeURIComponent(card.card_id)}/alternatives`, { commander: [COMMANDER], in_deck: inDeck, skip: [...state.marks].filter(([, mark]) => mark.excluded).map(([id]) => id) });
  const box = h("div", { class: "layer" }, h("h3", {}, "Funktionsalternativen (Tauschvergleich)"));
  if (data.status === "NO_ROLE_CLAIM") { box.append(h("p", {}, "Für diese Karte ist keine Rolle erfasst. Ohne Rolle gibt es keinen Funktionsvergleich.")); return box; }
  const shown = data.alternatives.filter((item) => !(state.marks.get(item.card.card_id) || {}).excluded);
  box.append(h("p", {}, `Freie Karten mit mindestens einer gleichen Rolle${inDeck.length ? ", die nicht im gewählten Deck sind" : ""}. Reihenfolge: mehr gemeinsame Rollen, dann kleinerer Unterschied im Manawert, dann Name. Das ist ein Vergleich der Funktion. Ohne Ergebnisdaten wird kein Tausch als Verbesserung bezeichnet.`));
  if (!shown.length) { box.append(h("p", {}, "Keine freie Karte mit gleicher Rolle gefunden.")); return box; }
  box.append(table(["Karte", "Manawert", "Unterschied", "Gemeinsame Rollen", "Fehlt gegenüber dieser Karte", "Zusätzlich", "Quelldecks", "Echte Spiele"], shown.map((item) => [
    h("span", { class: "name", onclick: () => openCard(item.card) }, (state.marks.get(item.card.card_id) || {}).favorite ? h("span", { class: "star" }, "★ ") : null, item.card.name),
    item.card.mana_value,
    item.mana_value_delta === 0 ? "gleich" : `${item.mana_value_delta > 0 ? "+" : ""}${item.mana_value_delta}`,
    item.shared_roles.map(roleName).join(", "),
    item.missing_roles.map(roleName).join(", ") || "nichts",
    item.only_candidate_roles.map(roleName).join(", ") || "nichts",
    corpusCell(item.card),
    gameCell(item.card),
  ])));
  if (data.total > data.alternatives.length) box.append(h("p", {}, `${data.total - data.alternatives.length} weitere nicht gezeigt.`));
  return box;
}
function pairsTable(data) {
  return table(["Karte", "Decks zusammen", "Anteil der Decks mit dieser Karte", "Lift", "Kombo-Partner"], data.pairs.map((pair) => [
    pair.card_name,
    `${pair.decks_together}/${data.decks_with_card}`,
    pct(pair.decks_together, data.decks_with_card),
    pair.lift === null || pair.lift === undefined ? unknown("–") : pair.lift.toFixed(2),
    pair.combo_partner ? "ja (Spellbook-Kombo)" : "–",
  ]));
}
async function universeBox(card) {
  const uni = state.universe;
  const box = h("div", { class: "layer universe-box" }, h("h3", {}, SPREAD_LABEL));
  if (!uni.name) { box.append(h("p", {}, NO_UNIVERSE + ". Wähle oben ein Universum, um die gezählte Verbreitung zu sehen.")); return box; }
  const data = await api(`/api/cards/${encodeURIComponent(card.card_id)}/universe?profile=${encodeURIComponent(uni.name)}&commander=${encodeURIComponent(COMMANDER)}`);
  const item = data.cards[0], universe = data.universe;
  if (universe.subset_note) box.append(h("p", { class: "policy" }, `${universe.subset_note}. Der Nenner ${universe.denominator} ist diese Teilmenge, nicht alle Decks des Commanders.`));
  if (item.filter_card) box.append(h("p", {}, h("b", {}, `${FILTER_LABEL}: `), "das Universum verlangt diese Karte; sie steht in jedem Deck der Teilmenge und bekommt deshalb keinen Anteil und keine Stufe."));
  box.append(h("p", {}, spreadBadge(item, universe), " ", item.filter_card ? "" : item.matched ? `${item.hits} von ${item.denominator} Decks (${pct(item.hits, item.denominator)})` : "unbekannt: kein Deck des Universums nennt diese Karte unter einem bekannten Namen"));
  box.append(h("p", {}, `Grund: ${REASON_NAMES[item.reason] || item.reason}. Universum ${universe.profile} (${universe.data_class}), Stand ${universe.snapshot_id}.`));
  box.append(h("p", {}, `Schwellen (Modell ${data.model_version || "unbekannt"}): Universum mindestens ${data.params.min_universe} Decks; ${data.params.cuts.map(([tier, cut]) => `${tier} ab ${(100 * cut).toFixed(0)} %`).join(", ")}; darunter ${data.params.fallback_tier}; ohne Datenbasis U. Nur Lesehilfe für die Häufigkeit, keine Stärke.`));
  if (universe.excluded_by_card_filter) box.append(h("p", { class: "rule" }, `${universe.excluded_by_card_filter} Decks fallen durch den Kartenfilter heraus und zählen nicht im Nenner.`));
  if (universe.excluded_no_date) box.append(h("p", { class: "rule" }, `${universe.excluded_no_date} Decks ohne Zeitstempel fallen durch den Datumsfilter des Universums heraus und zählen nicht im Nenner.`));
  if (item.spellings.length > 1) box.append(h("p", { class: "spellings" }, "Mehrere Schreibweisen kommen vor und werden nie addiert; gezeigt wird die größte: ", item.spellings.map((s) => `${s.name}: ${s.hits}`).join(" · ")));
  const parts = (label, map) => `${label}: ${Object.entries(map).map(([key, n]) => `${key} ${n}`).join(", ") || "–"}`;
  box.append(h("p", { class: "rule" }, parts("Nenner nach Plattform", universe.denominator_by_platform), " · ", parts("nach Bracket", universe.denominator_by_bracket)));
  box.append(h("p", { class: "rule" }, data.meaning));
  const result = h("div", {});
  const button = h("button", { type: "button", onclick: async () => {
    button.disabled = true;
    try {
      const co = await api(`/api/cards/${encodeURIComponent(card.card_id)}/cooccurrence?profile=${encodeURIComponent(uni.name)}&limit=25&commander=${encodeURIComponent(COMMANDER)}`);
      result.replaceChildren(...(co.decks_with_card === null ? [h("p", {}, "unbekannt: die Karte kommt im Universum nicht vor")] : [h("p", {}, `${co.decks_with_card_label}: ${co.decks_with_card}; ${co.denominator_label}: ${co.denominator}.`), co.subset_note ? h("p", { class: "rule" }, `${co.subset_note}. Der Nenner ${co.denominator} ist diese Teilmenge, nicht alle Decks des Commanders.${co.filter_card ? " Diese Karte ist eine Filterkarte: sie steht in allen Decks der Teilmenge." : ""}`) : null, pairsTable(co)].filter(Boolean)));
    } catch (error) { result.replaceChildren(h("p", {}, `Fehler: ${error.message}`)); button.disabled = false; }
  } }, "Zusammen gespielt mit");
  box.append(button, result);
  return box;
}
async function openCard(card) {
  const modal = $("modal"), content = $("modal-box");
  content.replaceChildren(h("h2", {}, card.name), h("p", { class: "muted" }, "lädt …"));
  modal.hidden = false;
  try {
    const query = state.view === "global" ? "view=global" : `view=commander&commander=${encodeURIComponent(COMMANDER)}`;
    const detail = await api(`/api/cards/${encodeURIComponent(card.card_id)}/evidence?${query}`);
    const full = detail.card;
    const strengthSection = strengthBox(card);
    content.replaceChildren(
      h("div", { class: "actions" }, h("button", { type: "button", onclick: () => { modal.hidden = true; } }, "Schließen")),
      h("h2", {}, full.name),
      h("p", { class: "muted" }, full.type_line),
      h("div", { class: "policy" }, h("b", {}, `${OUTCOME_HEADING}. `), `Grund: ${full.rating.reason}. Fehlende Beobachtung ist nie ein niedriger Tier. Favoriten, Ausschlüsse und Notizen fließen nicht ein.`),
      strengthSection,
      ...drawer(full));
    try { content.append(await universeBox(full)); } catch (error) { content.append(h("p", {}, `Verbreitung nicht ladbar: ${error.message}`)); }
    if (state.view !== "global") content.append(await alternativesBox(full));
  } catch (error) { content.append(h("p", {}, `Fehler: ${error.message}`)); }
}

// ---------- deck universe ----------
function rememberUniverse(name) { try { localStorage.setItem(UNIVERSE_KEY, name); } catch (error) { /* private mode: no memory */ } }
function rememberedUniverse() { try { return localStorage.getItem(UNIVERSE_KEY) || ""; } catch (error) { return ""; } }
const listText = (text) => text.split(",").map((part) => part.trim()).filter(Boolean);
function breakdown(label, map) {
  const entries = Object.entries(map || {});
  return h("span", {}, `${label}: `, entries.length ? entries.map(([key, n]) => `${key} ${n}`).join(", ") : unknown("–"));
}
function optionChecks(id, options, selected) {
  const box = h("div", { class: "checks", id });
  if (!options) { box.append(h("span", { class: "muted" }, "Werte nicht verfügbar")); return box; }
  if (!options.length) { box.append(h("span", { class: "muted" }, "keine Werte im Bestand")); return box; }
  for (const option of options) {
    box.append(h("label", {}, h("input", { type: "checkbox", value: option.value, checked: selected.includes(option.value) }), ` ${option.value} (${option.decks} Decks)`));
  }
  return box;
}
const checkedValues = (id) => [...document.querySelectorAll(`#${id} input:checked`)].map((input) => input.value);
function renderUniversePanel() {
  const uni = state.universe, panel = $("universe-panel"), summary = uni.summary;
  const spec = summary ? summary.spec : {};
  const field = (label, id, value, type = "text") => h("label", {}, label, h("input", { id, type, value: value ?? "" }));
  const cardPicker = () => {
    const options = (uni.options && uni.options.cards) || [];
    const chosen = [...(spec.must_contain || [])];
    const chips = h("span", { class: "chips" });
    const draw = () => chips.replaceChildren(...chosen.map((name) => h("button", { type: "button", class: "chip", title: `${name} entfernen`, onclick: () => { chosen.splice(chosen.indexOf(name), 1); draw(); } }, `${name} ✕`)));
    const input = h("input", { id: "u-card", list: "u-card-list", placeholder: "Karte aus dem Bestand …", autocomplete: "off" });
    const add = () => {
      const value = input.value.trim();
      if (!value) return;
      const hit = options.find((option) => option.value.toLowerCase() === value.toLowerCase());
      const name = hit ? hit.value : value;
      if (!chosen.includes(name)) { chosen.push(name); draw(); }
      input.value = "";
    };
    input.addEventListener("change", add);
    draw();
    return {
      chosen: () => [...chosen],
      node: h("span", {}, input,
        h("datalist", { id: "u-card-list" }, ...options.map((option) => h("option", { value: option.value }, `${option.decks} Decks`))),
        h("button", { type: "button", onclick: add }, "hinzufügen"), chips),
    };
  };
  const picker = cardPicker();
  const form = h("form", { id: "universe-form", onsubmit: async (event) => {
    event.preventDefault();
    const name = $("u-name").value.trim();
    if (!name) { toast("Name des Universums fehlt"); return; }
    // Fields the form does not edit (the commanders of the stored spec) are kept when the same
    // profile is saved again, so a re-save never drops them silently.
    const body = name === uni.name && spec.commanders && spec.commanders.length ? { commanders: [...spec.commanders] } : {};
    if (checkedValues("u-platforms").length) body.platforms = checkedValues("u-platforms");
    if (checkedValues("u-cohorts").length) body.cohorts = checkedValues("u-cohorts");
    if ($("u-from").value) body.date_from = $("u-from").value;
    if ($("u-to").value) body.date_to = $("u-to").value;
    if ($("u-min").value !== "") body.min_main_cards = Number($("u-min").value);
    if ($("u-minuni").value !== "") body.min_universe = Number($("u-minuni").value);
    if (picker.chosen().length) body.must_contain = picker.chosen();
    try {
      await api(`/api/universe/profiles/${encodeURIComponent(name)}?commander=${encodeURIComponent(COMMANDER)}`, body, "PUT");
      uni.profiles = await api("/api/universe/profiles");
      fillUniverseSelect(name);
      await selectUniverse(name);
      toast(`Universum „${name}“ gespeichert`);
    } catch (error) { toast(`Universum nicht gespeichert: ${error.message}`); }
  } },
    field("Name", "u-name", uni.name),
    h("span", {}, "Plattformen", optionChecks("u-platforms", uni.options && uni.options.platforms, spec.platforms || [])),
    h("span", {}, "Kohorten", optionChecks("u-cohorts", uni.options && uni.options.cohorts, spec.cohorts || [])),
    h("span", {}, "Muss enthalten (alle, im Hauptdeck)", picker.node),
    field("Datum ab", "u-from", spec.date_from, "date"),
    field("Datum bis", "u-to", spec.date_to, "date"),
    field("Mindestgröße Hauptdeck", "u-min", spec.min_main_cards, "number"),
    field("Mindest-Universum (Nenner für Stufen)", "u-minuni", spec.min_universe, "number"),
    h("button", { type: "submit" }, "Universum speichern"),
    uni.name ? h("button", { type: "button", onclick: async () => {
      const name = uni.name;
      try {
        await api(`/api/universe/profiles/${encodeURIComponent(name)}`, {}, "DELETE");
        state.universe.profiles = await api("/api/universe/profiles");
        fillUniverseSelect("");
        await selectUniverse("");
        toast(`Universum „${name}“ gelöscht`);
      } catch (error) { toast(`Universum nicht gelöscht: ${error.message}`); }
    } }, "Universum löschen") : null);
  const facts = !uni.name || !summary
    ? h("div", { class: "facts" }, h("b", {}, NO_UNIVERSE), h("span", { class: "muted" }, uni.profiles.length ? "Wähle oben ein gespeichertes Universum." : "Noch keines gespeichert. Lege unten eines an. Ohne Filter zählt es alle importierten Quelldecks."))
    : h("div", { class: "facts" },
      h("b", {}, uni.name),
      h("span", { class: "muted" }, `Version ${summary.version}`),
      h("span", {}, `${summary.denominator} Decks (Nenner)`),
      breakdown("Plattform", summary.denominator_by_platform),
      breakdown("Bracket", summary.denominator_by_bracket),
      summary.subset_note ? h("span", { class: "badge warn" }, summary.subset_note) : null,
      summary.excluded_no_date ? h("span", { class: "muted" }, `${summary.excluded_no_date} Decks ohne Zeitstempel durch den Datumsfilter ausgeschlossen`) : null,
      summary.below_min_universe ? h("span", { class: "badge warn" }, `unter dem Mindest-Universum (${summary.min_universe} Decks): alle Karten U`) : null,
      h("span", { class: "muted", title: summary.snapshot_id }, `Stand ${summary.snapshot_id.slice(0, 28)}`),
      h("span", { class: "muted", title: summary.data_class }, "gezählt, Teilmengen addieren sich zum Nenner"));
  panel.replaceChildren(facts, h("div", { class: "muted" }, SPREAD_NOTE), h("details", {}, h("summary", {}, uni.name ? "Universum ändern oder neu anlegen" : "Universum anlegen"), form));
}
function fillUniverseSelect(selected) {
  $("universe-select").replaceChildren(h("option", { value: "" }, "kein Universum"), ...state.universe.profiles.map((p) => h("option", { value: p.name }, p.name)));
  $("universe-select").value = selected || "";
}
async function selectUniverse(name) {
  const uni = state.universe, ticket = ++uni.ticket;
  if (!name) { Object.assign(uni, { name: "", summary: null, spread: null }); rememberUniverse(""); renderUniversePanel(); render(); await universeChanged(); return; }
  const [summary, spread] = await Promise.all([api(`/api/universe/profiles/${encodeURIComponent(name)}/summary?commander=${encodeURIComponent(COMMANDER)}`), api(`/api/universe/spread?profile=${encodeURIComponent(name)}&commander=${encodeURIComponent(COMMANDER)}`)]);
  if (ticket !== uni.ticket) return;
  const map = new Map(spread.cards.map((item) => [item.card_id, item]));
  map.universe = spread.universe;
  Object.assign(uni, { name, summary, spread: map });
  rememberUniverse(name);
  renderUniversePanel();
  render();
  await universeChanged();
}
async function universeChanged() {
  const s = state.strength;
  if (!s.settings || (s.settings.universe_profile || "") === (state.universe.name || "")) return;
  s.settings = { ...s.settings, universe_profile: state.universe.name || null };
  rememberStrength();
  renderStrengthPanel();
  await refreshStrength();
}
async function initUniverse() {
  const uni = state.universe;
  uni.ticket = 0;
  try { uni.profiles = await api("/api/universe/profiles"); } catch (error) { toast("Universen konnten nicht geladen werden: " + error.message); uni.profiles = []; }
  try { uni.options = await api(`/api/universe/options?commander=${encodeURIComponent(COMMANDER)}`); } catch (error) { uni.options = null; }
  const wanted = rememberedUniverse();
  const name = uni.profiles.some((p) => p.name === wanted) ? wanted : "";
  fillUniverseSelect(name);
  $("universe-select").addEventListener("change", () => selectUniverse($("universe-select").value).catch((error) => toast(error.message)));
  await selectUniverse(name).catch((error) => { toast(error.message); renderUniversePanel(); });
}

// ---------- strength index ----------
function rememberStrength() { try { localStorage.setItem(STRENGTH_KEY, JSON.stringify(state.strength.settings)); } catch (error) { /* private mode: no memory */ } }
function rememberedStrength() { try { const raw = localStorage.getItem(STRENGTH_KEY); return raw ? JSON.parse(raw) : null; } catch (error) { return null; } }
const clone = (value) => JSON.parse(JSON.stringify(value));
const pathGet = (object, path) => path.split(".").reduce((node, key) => (node === undefined || node === null ? undefined : node[key]), object);
function pathSet(object, path, value) {
  const keys = path.split(".");
  let node = object;
  for (const key of keys.slice(0, -1)) { node[key] = { ...(node[key] || {}) }; node = node[key]; }
  node[keys[keys.length - 1]] = value;
}
// Settings with every key the server knows: a remembered or saved setting from before a key existed
// takes the recommended value for it. The recommended values come from the server only.
function withDefaults(settings) {
  const base = clone(state.strength.meta.recommended);
  for (const [key, value] of Object.entries(settings || {})) {
    base[key] = value && typeof value === "object" && !Array.isArray(value) ? { ...base[key], ...value } : value;
  }
  return base;
}
function fieldKind(key) {
  const meta = state.strength.meta;
  if (key.startsWith("weights.")) return { type: "number", min: 0, max: 100, step: 0.5, scale: 1 };
  if (key === "min_denominators.deck_universe") return { type: "readonly" };
  if (key.startsWith("min_denominators.")) return { type: "number", min: 0, max: 100000, step: 1, scale: 1 };
  if (key === "min_coverage") return { type: "number", min: 0, max: 100, step: 5, scale: 100 };
  if (key === "min_components") return { type: "number", min: 0, max: meta.components.length, step: 1, scale: 1 };
  if (key.startsWith("tier_cuts.")) return { type: "number", min: 0, max: 100, step: 1, scale: 1 };
  const choices = key.startsWith("missing_value.") ? meta.panel.choices.missing_value : meta.panel.choices[key];
  return { type: "choice", choices };
}
const settingKeys = () => state.strength.meta.panel.groups.flatMap((group) => group.keys);
const fieldId = (key) => `sf-${key.replace(/\./g, "-")}`;
function universeMinimum() {
  const summary = state.universe.summary;
  return summary ? summary.min_universe : state.strength.meta.panel.universe_minimum;
}
function readStrengthSettings() {
  const s = state.strength, out = clone(s.settings);
  for (const key of settingKeys()) {
    const kind = fieldKind(key), input = $(fieldId(key));
    if (kind.type === "readonly" || !input) continue; // stored fields the form does not show stay as they are
    if (kind.type === "choice") {
      const choice = kind.choices.find((item) => String(item.value) === input.value);
      pathSet(out, key, choice ? choice.value : pathGet(s.meta.recommended, key));
      continue;
    }
    let number = input.value.trim() === "" ? NaN : Number(input.value);
    if (!Number.isFinite(number)) { // an empty field means "use the recommended value": show it
      const recommended = pathGet(s.meta.recommended, key) * kind.scale;
      input.value = recommended;
      number = recommended;
    }
    pathSet(out, key, number / kind.scale);
  }
  out.universe_profile = state.universe.name || null;
  return out;
}
async function refreshStrength() {
  const s = state.strength, ticket = ++s.ticket;
  if (!s.settings) return;
  try {
    const result = await api("/api/strength", { commander: COMMANDER, settings: s.settings });
    if (ticket !== s.ticket) return;
    s.result = result;
    s.map = new Map(result.cards.map((item) => [item.card_id, item]));
  } catch (error) {
    if (ticket !== s.ticket) return;
    s.result = null; s.map = null;
    toast(`Stärke-Index nicht berechnet: ${error.message}`);
  }
  renderStrengthSummary();
  render();
}
function renderStrengthSummary() {
  const s = state.strength, box = $("strength-summary");
  if (!box) return;
  if (!s.result) { box.replaceChildren(unknown("noch nicht berechnet")); return; }
  const result = s.result, counts = result.tier_counts, universe = result.universe;
  const universeText = `Index berechnet mit: ${universe ? `Universum ${universe.profile} (${universe.denominator} Decks${universe.subset_note ? `; ${universe.subset_note}` : ""})` : "kein Decklisten-Universum"}`;
  // Sources that can exist for these settings: no simulation (not collected), no bracket source without a
  // bracket, no deck universe without one.
  const possible = s.meta.components.filter((c) => c.key !== "simulation" && !(c.key === "bracket_inclusion" && result.settings.bracket === "none") && !(c.key === "deck_universe" && !universe)).length;
  const notices = (result.notices || []).map((text) => h("div", { class: "badge warn" }, text));
  const ambiguous = result.ambiguous_names || [];
  const shown = ambiguous.slice(0, 10).map((item) => `${item.name} (${item.candidates.join(" / ")})`).join("; ");
  box.replaceChildren(
    ...["S", "A", "B", "C", "D"].map((tier) => h("span", { class: `strength lvl-${tier}` }, h("span", { class: "level" }, tier), counts[tier])),
    h("span", { class: "strength lvl-U" }, `${UNKNOWN_TIER} ${counts.U}`),
    h("span", { class: "strength lvl-N", title: "Commander und Standardländer, wenn sie nicht bewertet werden" }, `nicht bewertet ${counts.N || 0}`),
    h("span", { class: "muted" }, `von ${result.cards.length} Karten · ${universeText} · Quellen vorhanden: ${result.collected.length}/${possible}`),
    ...notices,
    ...(ambiguous.length ? [h("div", { class: "rule" }, `Mehrdeutige Namen in den Quelldaten, keiner Karte zugeordnet: ${shown}${ambiguous.length > 10 ? ` und ${ambiguous.length - 10} weitere` : ""}`)] : []));
}
async function applyStrength(settings, remember = true) {
  state.strength.settings = { ...withDefaults(settings), universe_profile: state.universe.name || null };
  state.strength.draft.fields = {}; // the typed values are now the settings (or were replaced on purpose)
  if (remember) rememberStrength();
  renderStrengthPanel();
  await refreshStrength();
}
// A saved profile is computed by the server (``profile=``): it names the universe the profile
// stores, falls back to no universe with a notice when that universe was deleted, and echoes the
// settings it used. The page then selects exactly that universe, so the text shown is what was computed.
async function loadSavedProfile(profile) {
  const s = state.strength, ticket = ++s.ticket;
  const result = await api("/api/strength", { commander: COMMANDER, profile: profile.name });
  if (ticket !== s.ticket) return;
  const wanted = (result.settings && result.settings.universe_profile) || "";
  s.settings = { ...withDefaults(result.settings), universe_profile: wanted || null };
  s.draft = { fields: {}, name: profile.name };
  s.result = result;
  s.map = new Map(result.cards.map((item) => [item.card_id, item]));
  rememberStrength();
  if (wanted !== (state.universe.name || "")) {
    state.universe.profiles = await api("/api/universe/profiles");
    fillUniverseSelect(wanted);
    await selectUniverse(wanted).catch((error) => toast(`Universum „${wanted}“ konnte nicht gewählt werden: ${error.message}`));
  }
  renderStrengthPanel();
  render();
}
function strengthField(key) {
  const s = state.strength, panel = s.meta.panel, kind = fieldKind(key), id = fieldId(key);
  const current = pathGet(s.settings, key), drafted = s.draft.fields[key];
  let input;
  if (kind.type === "readonly") input = h("input", { id, type: "text", readOnly: true, value: `${universeMinimum()} Decks` });
  else if (kind.type === "choice") {
    input = h("select", { id }, kind.choices.map((item) => h("option", { value: String(item.value) }, item.label)));
    input.value = drafted !== undefined ? drafted : String(current);
  } else input = h("input", { id, type: "number", min: kind.min, max: kind.max, step: kind.step, value: drafted !== undefined ? drafted : current === undefined ? "" : Math.round(current * kind.scale * 1000) / 1000, placeholder: `${pathGet(s.meta.recommended, key) * kind.scale}` });
  if (kind.type !== "readonly") input.addEventListener("input", () => { s.draft.fields[key] = input.value; });
  return h("label", { title: panel.help[key] }, panel.labels[key], input, h("span", { class: "help" }, panel.help[key]));
}
function renderStrengthFilters() {
  const s = state.strength;
  const previous = $("strength-filter");
  if (previous) previous.remove();
  const box = h("span", { id: "strength-filter", class: "tier-filter", title: "Nach Stärke-Index-Stufe filtern (Mehrfachauswahl; keine Auswahl zeigt alle)" }, "Stufe: ",
    STRENGTH_TIERS.map((tier) => h("label", { title: TIER_FILTER_NAMES[tier] || `Stufe ${tier}` }, h("input", { type: "checkbox", value: tier, checked: s.tiers.has(tier), onchange: (event) => { if (event.target.checked) s.tiers.add(tier); else s.tiers.delete(tier); state.shown = 150; render(); } }), ` ${tier}`)));
  $("filters").insertBefore(box, $("sort").parentElement);
}
function fillSortOptions() {
  const meta = state.strength.meta;
  const previous = $("sort").value;
  const percentile = meta ? meta.components.map((c) => [PERCENTILE_SORT + c.key, `Perzentil: ${c.label}`]) : [];
  $("sort").replaceChildren(...[...SORTS, ...percentile].map(([key, label]) => h("option", { value: key }, label)));
  $("sort").value = [...$("sort").options].some((option) => option.value === previous) ? previous : state.sortKey;
}
function renderStrengthPanel() {
  const s = state.strength, panel = $("strength-panel");
  if (!s.meta || !s.settings) return;
  const presetSelect = h("select", { id: "s-preset", title: "Voreinstellung laden" }, h("option", { value: "" }, "Voreinstellung …"), s.meta.presets.map((p) => h("option", { value: p.name }, p.name)));
  presetSelect.addEventListener("change", () => { const p = s.meta.presets.find((x) => x.name === presetSelect.value); if (p) applyStrength(p.settings).catch((error) => toast(error.message)); });
  const profileLabel = (p) => `${p.name}${p.valid ? (p.universe_missing ? " (Universum fehlt)" : "") : " (ungültig)"}`;
  const saved = h("select", { id: "s-saved" }, h("option", { value: "" }, "gespeicherte Einstellung …"), s.profiles.map((p) => h("option", { value: p.name }, profileLabel(p))));
  saved.addEventListener("change", () => {
    const p = s.profiles.find((x) => x.name === saved.value);
    if (!p) return;
    if (!p.valid) { toast(`Einstellung „${p.name}“ ist nicht mehr gültig: ${p.reason}`); return; }
    if (p.universe_missing) toast(`Das Universum „${p.universe_missing}“ dieser Einstellung gibt es nicht mehr: sie läuft mit „kein Universum“.`);
    loadSavedProfile(p).catch((error) => toast(error.message));
  });
  const apply = h("button", { type: "button", onclick: () => applyStrength(readStrengthSettings()).catch((error) => toast(error.message)) }, "Berechnen");
  const reset = h("button", { type: "button", title: "Alle Einstellungen auf die empfohlenen Werte setzen", onclick: () => applyStrength(s.meta.recommended).catch((error) => toast(error.message)) }, "Empfohlene Werte");
  const save = h("button", { type: "button", onclick: async () => {
    const name = $("s-name").value.trim();
    if (!name) { toast("Name der Einstellung fehlt"); return; }
    try {
      const settings = readStrengthSettings();
      await api(`/api/strength/profiles/${encodeURIComponent(name)}`, { settings }, "PUT");
      s.profiles = await api("/api/strength/profiles");
      await applyStrength(settings);
      toast(`Einstellung „${name}“ gespeichert`);
    } catch (error) { toast(`Nicht gespeichert: ${error.message}`); }
  } }, "Speichern");
  const remove = h("button", { type: "button", onclick: async () => {
    const name = $("s-saved").value;
    if (!name) { toast("Wähle eine gespeicherte Einstellung"); return; }
    try {
      await api(`/api/strength/profiles/${encodeURIComponent(name)}`, {}, "DELETE");
      s.profiles = await api("/api/strength/profiles");
      renderStrengthPanel();
      toast(`Einstellung „${name}“ gelöscht`);
    } catch (error) { toast(`Nicht gelöscht: ${error.message}`); }
  } }, "Löschen");
  const groups = s.meta.panel.groups.map((group) => h("fieldset", { class: "sgroup" }, h("legend", {}, group.title), h("div", { class: "strength-form" }, group.keys.map(strengthField))));
  panel.replaceChildren(
    h("details", { open: true },
      h("summary", {}, `${INDEX_HEADING}: Einstellungen (was wie gezählt werden soll)`),
      h("div", { class: "muted" }, STRENGTH_NOTE),
      h("div", { id: "strength-summary", class: "facts" }),
      h("div", { class: "strength-form" },
        h("label", {}, "Voreinstellung", presetSelect),
        h("label", {}, "Universum (oben gewählt)", h("input", { type: "text", readOnly: true, value: state.universe.name || "keines" })),
        apply, reset),
      groups,
      h("div", { class: "strength-form" },
        h("label", {}, "Name", h("input", { id: "s-name", type: "text", maxLength: 80, placeholder: "z. B. Mein Index", value: s.draft.name, oninput: (event) => { s.draft.name = event.target.value; } })), save,
        h("label", {}, "Laden", saved), remove)));
  renderStrengthSummary();
}
async function initStrength() {
  const s = state.strength;
  try {
    [s.meta, s.profiles] = await Promise.all([api("/api/strength/presets"), api("/api/strength/profiles")]);
  } catch (error) { toast(`Stärke-Index nicht verfügbar: ${error.message}`); return; }
  renderStrengthFilters();
  fillSortOptions();
  const wanted = rememberedStrength();
  const base = wanted && typeof wanted === "object" ? wanted : s.meta.recommended;
  s.settings = { ...withDefaults(base), universe_profile: state.universe.name || null };
  renderStrengthPanel();
  try { await refreshStrength(); } catch (error) { toast(error.message); }
  if (!s.result && wanted) { // remembered settings no longer valid: start from the recommended values
    s.settings = { ...withDefaults(s.meta.recommended), universe_profile: state.universe.name || null };
    renderStrengthPanel();
    await refreshStrength();
  }
}

// ---------- loading ----------
async function loadEvidence() {
  const apiView = state.view === "global" ? "global" : "commander";
  const query = apiView === "global" ? "view=global" : `view=commander&commander=${encodeURIComponent(COMMANDER)}`;
  const ticket = ++state.ticket;
  const data = await api(`/api/evidence?${query}`);
  if (ticket !== state.ticket) return; // a newer view was chosen meanwhile
  state.data = data;
  const groups = [...new Set(state.data.cards.map((card) => card.group))].sort();
  const roles = [...new Set(state.data.cards.flatMap(cardRoles))].sort((a, b) => roleName(a).localeCompare(roleName(b)));
  $("type-filter").replaceChildren(h("option", { value: "" }, "alle Typen"), ...groups.map((group) => h("option", { value: group }, group)));
  $("role-filter").replaceChildren(h("option", { value: "" }, "alle Rollen"), ...roles.map((role) => h("option", { value: role }, roleName(role))));
  renderNotice();
  render();
}
async function loadDeck() {
  const deck = state.decks.find((entry) => entry.deck_id === $("deck-select").value);
  const branch = deck && deck.branches.find((entry) => entry.branch === $("branch-select").value);
  state.deckCards = new Map();
  if (branch) {
    const revision = await api(`/api/revisions/${encodeURIComponent(branch.revision_id)}`);
    for (const entry of revision.cards) if (entry.zone !== "commander") state.deckCards.set(entry.card_id, entry.quantity);
    state.deckRoles = revision.roles || {};
  }
  render();
}
function fillBranches() {
  const deck = state.decks.find((entry) => entry.deck_id === $("deck-select").value);
  $("branch-select").replaceChildren(...(deck ? deck.branches : []).map((entry) => h("option", { value: entry.branch }, entry.branch)));
}
async function setView(view) {
  state.view = view;
  $("deck-pick").hidden = view !== "deck";
  if (view === "deck" && !state.decks.length) {
    state.decks = (await api("/api/decks")).filter((deck) => (deck.commanders || []).includes(COMMANDER));
    $("deck-select").replaceChildren(...state.decks.map((deck) => h("option", { value: deck.deck_id }, deck.name)));
    fillBranches();
  }
  await loadEvidence();
  if (view === "deck") await loadDeck();
}

function renderTabs() {
  $("tabs").replaceChildren(...[["cards", "Karten"], ["research", "Forschungsliste"]].map(([key, label]) => h("span", { class: "chip" + (state.tab === key ? " on" : ""), onclick: () => { state.tab = key; renderTabs(); render(); } }, label)));
}

async function init() {
  $("view").replaceChildren(...Object.entries(VIEW_NAMES).map(([key, label]) => h("option", { value: key }, label)));
  $("sort").replaceChildren(...SORTS.map(([key, label]) => h("option", { value: key }, label)));
  $("view").addEventListener("change", () => setView($("view").value).catch((error) => toast(error.message)));
  $("deck-select").addEventListener("change", () => { fillBranches(); loadDeck().catch((error) => toast(error.message)); });
  $("branch-select").addEventListener("change", () => loadDeck().catch((error) => toast(error.message)));
  $("sort").addEventListener("change", () => { state.sortKey = $("sort").value; state.sortDir = SMALL_FIRST.has(state.sortKey) ? 1 : -1; render(); });
  for (const id of ["q", "type-filter", "role-filter", "spread-filter", "f-free", "f-fav", "f-excl"]) $(id).addEventListener("input", () => { state.shown = 150; render(); });
  $("modal").addEventListener("click", (event) => { if (event.target === $("modal")) $("modal").hidden = true; });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") $("modal").hidden = true; });
  renderTabs();
  await StudioCommander.fill($("commander-select"));
  try {
    const pool = await api(`/api/pool?commander=${encodeURIComponent(COMMANDER)}`);
    for (const card of pool.cards) state.marks.set(card.card_id, { favorite: card.favorite, excluded: card.excluded });
  } catch (error) { toast("Markierungen konnten nicht geladen werden: " + error.message); }
  await Promise.all([setView("commander"), initUniverse()]);
  await initStrength();
}
init().catch((error) => toast(error.message));
