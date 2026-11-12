"use strict";
// Commander Studio tier list. Shows the evidence per card; it never rates a card.
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
  NO_SIMULATION: "nicht simuliert",
  SMALL_GAME_SAMPLE: "kleine Spielstichprobe",
};
const SORTS = [
  ["name", "Name"],
  ["mv", "Manawert"],
  ["strength", "Stärke-Index (Schätzung, zu wenig Daten zuletzt)"],
  ["layers", "Anzahl vorhandener Schichten"],
  ["corpus", "Anteil in Quelldecks (nur Lesehilfe)"],
  ["edhrec", "EDHREC Inclusion (nur Lesehilfe)"],
  ["games", "Partien mit der Karte (nur Lesehilfe)"],
  ["research", "Forschungsbedarf (Heuristik)"],
];
const POLICY_TEXT = "Ein Tier braucht eine vorab festgelegte Zielgröße, ein kalibriertes Modell und Belege außerhalb der Trainingsdaten. Ein solches Modell gibt es noch nicht, deshalb ist jede Karte unbewertet. Häufigkeit in Decks, EDHREC-Werte, deine Markierungen und reine Zählungen setzen nie allein ein Tier. Fehlende Belege sind nie ein niedriger Tier.";
const GAME_NOTES = {
  PRESENT: "Beobachteter Zusammenhang mit Verzerrung durch Pilot, Runde und Spielverlauf. Kein kausaler Effekt.",
  NONE_RECORDED: "Die Spielquelle hat für diese Karte keine verwertbare Zeile.",
  NOT_COLLECTED: "Noch keine Spielquelle importiert (Playgroup Card Atlas).",
};
const SPREAD_LABEL = "Verbreitung (gezählt)";
const NO_UNIVERSE = "kein Universum gewählt";
const SPREAD_NOTE = "Gezählt: in wie vielen Decks des gewählten Universums die Karte steht. Das ist keine Kartenstärke und kein Tier. Favoriten, Ausschlüsse und Notizen ändern keine Zählung.";
const REASON_NAMES = { SHARE_CUT: "Anteil erreicht die Schwelle", BELOW_LOWEST_CUT: "Anteil unter der niedrigsten Schwelle", UNIVERSE_TOO_SMALL: "Universum kleiner als das Minimum", DENOMINATOR_MISSING: "Nenner fehlt", NAME_NOT_FOUND_IN_UNIVERSE: "Name kommt im Universum nicht vor (unbekannt, nicht null)" };
const UNIVERSE_KEY = "studio.universe.profile";
const STRENGTH_KEY = "studio.strength.settings";
const STRENGTH_NOTE = "Der Stärke-Index ist eine Schätzung aus Nutzungssignalen (wie oft die Karte bei diesem Commander, im Bracket, in den gewählten Decklisten und in Turnierlisten gespielt wird). Er ist keine gemessene Siegrate. Eine Karte, die eine Quelle nicht nennt, senkt die Abdeckung, nie die Karte. Favoriten, Ausschlüsse und Notizen fließen nicht ein.";
const UNKNOWN_TIER = "zu wenig Daten";
const BRACKET_NAMES = { core: "Core (Bracket 1–2)", upgraded: "Upgraded (Bracket 3)", optimized: "Optimized (Bracket 4)", cedh: "cEDH (Bracket 5)", none: "kein Bracket" };
const COMPONENT_STATUS = { PRESENT: ["vorhanden", "good"], NO_VALUE: ["kein Wert (fehlende Beobachtung)", "warn"], NOT_COLLECTED: ["Quelle nicht importiert", "dim"] };
const SMALL_FIRST = new Set(["name", "mv"]);

const state = {
  view: "commander", tab: "cards", data: null, marks: new Map(), decks: [],
  universe: { profiles: [], name: "", summary: null, spread: null },
  strength: { meta: null, settings: null, profiles: [], result: null, map: null, ticket: 0 },
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
  if (key === "strength") { const item = strengthItem(card); return item && item.tier !== "U" ? item.index : null; } // tier U sorts last
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
  const free = $("f-free").checked, fav = $("f-fav").checked, showExcluded = $("f-excl").checked;
  let rows = state.data.cards.filter((card) => {
    const mark = state.marks.get(card.card_id) || {};
    if (state.view === "deck" && !(state.deckCards && state.deckCards.has(card.card_id))) return false;
    if (type && card.group !== type) return false;
    if (role && !cardRoles(card).includes(role)) return false;
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
  const counted = item.matched ? `${item.hits}/${item.denominator}` : "unbekannt";
  const title = `${SPREAD_LABEL}: ${REASON_NAMES[item.reason] || item.reason}. Universum ${universe.profile}, ${universe.denominator} Decks, Stand ${universe.snapshot_id}.`;
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
  const head = ["Tier", "Stärke-Index", SPREAD_LABEL, "Karte", "MW", "Mechanik", "Rollen", ...(commander ? ["Quelldecks", "EDHREC Inclusion", "Echte Spiele", "Simulation"] : ["Beliebtheit (global)", "Echte Spiele"]), "Schichten", ...(state.view === "deck" ? ["im Deck"] : [])];
  const rows = cards.slice(0, state.shown).map((card) => {
    const mark = state.marks.get(card.card_id) || {};
    const rank = (layer(card, "observed_deck").items || []).find((item) => item.kind === "edhrec_rank_global");
    return h("tr", {},
      h("td", {}, h("span", { class: "tier", title: "Kein Modell mit Ergebnisdaten: unbewertet" }, "Unbewertet")),
      h("td", {}, strengthCell(card)),
      h("td", {}, spreadCell(card)),
      h("td", { class: "cardcell name", onclick: () => openCard(card) }, thumb(card), mark.favorite ? h("span", { class: "star" }, "★ ") : null, card.name),
      h("td", { class: "num" }, card.mana_value),
      h("td", {}, featureBadges(card)),
      h("td", {}, roleBadges(card)),
      ...(commander ? [h("td", {}, corpusCell(card)), h("td", {}, edhrecCell(card)), h("td", {}, gameCell(card)), h("td", {}, simCell(card))] : [h("td", { class: "num" }, rank ? `Rang ${rank.rank}` : unknown("unbekannt")), h("td", {}, gameCell(card))]),
      h("td", { title: card.coverage.present.map((name) => LAYER_NAMES[name]).join(", ") }, `${presentCount(card)}/5`),
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
    h("div", { title: `${policy.version}: ${policy.rule}` }, h("b", {}, "Noch kein Tier vergeben. "), POLICY_TEXT),
    h("div", { class: "summary" }, `${summary.cards} Karten in dieser Ansicht. `, ["observed_deck", "observed_game", "simulated_result"].map(line).join(" · ")),
    bindingLine());
  $("tier-pill").textContent = `${summary.unrated} von ${summary.cards} unbewertet`;
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
  const box = h("div", { class: "layer" }, h("h3", {}, "Stärke-Index (Schätzung)",
    item ? h("span", { class: `strength lvl-${item.tier}` }, item.tier === "U" ? UNKNOWN_TIER : h("span", {}, h("span", { class: "level" }, item.tier), item.index.toFixed(1))) : null),
    h("p", {}, STRENGTH_NOTE));
  if (!item) { box.append(h("p", {}, state.view === "global" ? "Der Index wird je Commander berechnet." : "Für diese Karte liegt keine Berechnung vor.")); return box; }
  box.append(h("p", {}, `Abdeckung ${(100 * item.coverage).toFixed(0)} % (Gewicht der vorhandenen Signale an allen gewichteten). ${item.tier === "U" ? "Zu wenig Daten für eine Stufe: das sagt nichts über die Stärke der Karte." : ""}`));
  box.append(table(["Signal", "Wert", "Zähler/Nenner", "Wilson-Untergrenze", "Perzentil", "Gewicht", "Status"], item.components.map((c) => {
    const [text, kind] = COMPONENT_STATUS[c.status] || [c.status, "dim"];
    return [h("span", { title: c.signal }, c.label), c.value === null ? unknown() : Number(c.value.toPrecision(4)), c.denominator ? `${c.numerator}/${c.denominator}` : unknown("–"), c.wilson === null ? unknown("–") : c.wilson.toFixed(4), c.percentile === null ? unknown("–") : c.percentile.toFixed(3), c.weight, h("span", { class: `badge ${kind}` }, text)];
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
  return table(["Karte", "Decks zusammen", "Anteil der Decks mit dieser Karte"], data.pairs.map((pair) => [pair.card_name, `${pair.decks_together}/${data.decks_with_card}`, pct(pair.decks_together, data.decks_with_card)]));
}
async function universeBox(card) {
  const uni = state.universe;
  const box = h("div", { class: "layer universe-box" }, h("h3", {}, SPREAD_LABEL));
  if (!uni.name) { box.append(h("p", {}, NO_UNIVERSE + ". Wähle oben ein Universum, um die gezählte Verbreitung zu sehen.")); return box; }
  const data = await api(`/api/cards/${encodeURIComponent(card.card_id)}/universe?profile=${encodeURIComponent(uni.name)}&commander=${encodeURIComponent(COMMANDER)}`);
  const item = data.cards[0], universe = data.universe;
  box.append(h("p", {}, spreadBadge(item, universe), " ", item.matched ? `${item.hits} von ${item.denominator} Decks (${pct(item.hits, item.denominator)})` : "unbekannt: kein Deck des Universums nennt diese Karte unter einem bekannten Namen"));
  box.append(h("p", {}, `Grund: ${REASON_NAMES[item.reason] || item.reason}. Universum ${universe.profile} (${universe.data_class}), Stand ${universe.snapshot_id}.`));
  box.append(h("p", {}, `Schwellen: Universum mindestens ${data.params.min_universe} Decks; ${data.params.cuts.map(([tier, cut]) => `${tier} ab ${(100 * cut).toFixed(0)} %`).join(", ")}; darunter ${data.params.fallback_tier}; ohne Datenbasis U. Nur Lesehilfe für die Häufigkeit, keine Stärke.`));
  if (item.spellings.length > 1) box.append(h("p", { class: "spellings" }, "Mehrere Schreibweisen kommen vor und werden nie addiert; gezeigt wird die größte: ", item.spellings.map((s) => `${s.name}: ${s.hits}`).join(" · ")));
  const parts = (label, map) => `${label}: ${Object.entries(map).map(([key, n]) => `${key} ${n}`).join(", ") || "–"}`;
  box.append(h("p", { class: "rule" }, parts("Nenner nach Plattform", universe.denominator_by_platform), " · ", parts("nach Bracket", universe.denominator_by_bracket)));
  box.append(h("p", { class: "rule" }, data.meaning));
  const result = h("div", {});
  const button = h("button", { type: "button", onclick: async () => {
    button.disabled = true;
    try {
      const co = await api(`/api/cards/${encodeURIComponent(card.card_id)}/cooccurrence?profile=${encodeURIComponent(uni.name)}&limit=25&commander=${encodeURIComponent(COMMANDER)}`);
      result.replaceChildren(...(co.decks_with_card === null ? [h("p", {}, "unbekannt: die Karte kommt im Universum nicht vor")] : [h("p", {}, `${co.decks_with_card_label}: ${co.decks_with_card}; ${co.denominator_label}: ${co.denominator}.`), pairsTable(co)]));
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
      h("div", { class: "policy" }, h("b", {}, "Tier: unbewertet. "), `Grund: ${full.rating.reason}. Fehlende Beobachtung ist nie ein niedriger Tier. Favoriten, Ausschlüsse und Notizen fließen nicht ein.`),
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
function renderUniversePanel() {
  const uni = state.universe, panel = $("universe-panel"), summary = uni.summary;
  const spec = summary ? summary.spec : {};
  const field = (label, id, value, type = "text") => h("label", {}, label, h("input", { id, type, value: value ?? "" }));
  const form = h("form", { id: "universe-form", onsubmit: async (event) => {
    event.preventDefault();
    const name = $("u-name").value.trim();
    if (!name) { toast("Name des Universums fehlt"); return; }
    const body = {};
    if (listText($("u-platforms").value).length) body.platforms = listText($("u-platforms").value);
    if (listText($("u-cohorts").value).length) body.cohorts = listText($("u-cohorts").value);
    if ($("u-from").value) body.date_from = $("u-from").value;
    if ($("u-to").value) body.date_to = $("u-to").value;
    if ($("u-min").value !== "") body.min_main_cards = Number($("u-min").value);
    try {
      await api(`/api/universe/profiles/${encodeURIComponent(name)}?commander=${encodeURIComponent(COMMANDER)}`, body, "PUT");
      uni.profiles = await api("/api/universe/profiles");
      fillUniverseSelect(name);
      await selectUniverse(name);
      toast(`Universum „${name}“ gespeichert`);
    } catch (error) { toast(`Universum nicht gespeichert: ${error.message}`); }
  } },
    field("Name", "u-name", uni.name),
    field("Plattformen (Komma)", "u-platforms", (spec.platforms || []).join(", ")),
    field("Kohorten (Komma, z. B. bracket:3)", "u-cohorts", (spec.cohorts || []).join(", ")),
    field("Datum ab", "u-from", spec.date_from, "date"),
    field("Datum bis", "u-to", spec.date_to, "date"),
    field("Mindestgröße Hauptdeck", "u-min", spec.min_main_cards, "number"),
    h("button", { type: "submit" }, "Universum speichern"));
  const facts = !uni.name || !summary
    ? h("div", { class: "facts" }, h("b", {}, NO_UNIVERSE), h("span", { class: "muted" }, uni.profiles.length ? "Wähle oben ein gespeichertes Universum." : "Noch keines gespeichert. Lege unten eines an. Ohne Filter zählt es alle importierten Quelldecks."))
    : h("div", { class: "facts" },
      h("b", {}, uni.name),
      h("span", {}, `${summary.denominator} Decks (Nenner)`),
      breakdown("Plattform", summary.denominator_by_platform),
      breakdown("Bracket", summary.denominator_by_bracket),
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
  const wanted = rememberedUniverse();
  const name = uni.profiles.some((p) => p.name === wanted) ? wanted : "";
  fillUniverseSelect(name);
  $("universe-select").addEventListener("change", () => selectUniverse($("universe-select").value).catch((error) => toast(error.message)));
  await selectUniverse(name).catch((error) => { toast(error.message); renderUniversePanel(); });
}

// ---------- strength index ----------
function rememberStrength() { try { localStorage.setItem(STRENGTH_KEY, JSON.stringify(state.strength.settings)); } catch (error) { /* private mode: no memory */ } }
function rememberedStrength() { try { const raw = localStorage.getItem(STRENGTH_KEY); return raw ? JSON.parse(raw) : null; } catch (error) { return null; } }
function readStrengthSettings() {
  const weights = {};
  for (const component of state.strength.meta.components) weights[component.key] = Number($(`sw-${component.key}`).value);
  return {
    weights,
    bracket: $("s-bracket").value,
    universe_profile: state.universe.name || null,
    min_coverage: Number($("s-mincov").value) / 100,
    min_components: Number($("s-mincomp").value),
    tier_cuts: state.strength.settings.tier_cuts,
  };
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
  const counts = s.result.tier_counts;
  const universe = s.result.universe ? `Universum ${s.result.universe.profile} (${s.result.universe.denominator} Decks)` : "kein Decklisten-Universum";
  box.replaceChildren(
    ...["S", "A", "B", "C", "D"].map((tier) => h("span", { class: `strength lvl-${tier}` }, h("span", { class: "level" }, tier), counts[tier])),
    h("span", { class: "strength lvl-U" }, `${UNKNOWN_TIER} ${counts.U}`),
    h("span", { class: "muted" }, `von ${s.result.cards.length} Karten · ${universe} · Quellen vorhanden: ${s.result.collected.length}/${s.meta.components.length - 1}`));
}
async function applyStrength(settings, remember = true) {
  state.strength.settings = { ...settings, universe_profile: state.universe.name || null };
  if (remember) rememberStrength();
  renderStrengthPanel();
  await refreshStrength();
}
function renderStrengthPanel() {
  const s = state.strength, panel = $("strength-panel");
  if (!s.meta || !s.settings) return;
  const cur = s.settings;
  const presetSelect = h("select", { id: "s-preset", title: "Voreinstellung laden" }, h("option", { value: "" }, "Voreinstellung …"), s.meta.presets.map((p) => h("option", { value: p.name }, p.name)));
  presetSelect.addEventListener("change", () => { const p = s.meta.presets.find((x) => x.name === presetSelect.value); if (p) applyStrength(p.settings).catch((error) => toast(error.message)); });
  const bracketSelect = h("select", { id: "s-bracket" }, s.meta.brackets.map((b) => h("option", { value: b }, BRACKET_NAMES[b] || b)));
  bracketSelect.value = cur.bracket;
  const weightField = (c) => h("label", { title: `Gewicht 0 schaltet das Signal ab. Signal: ${c.key}` }, c.label, h("input", { id: `sw-${c.key}`, type: "number", min: 0, max: 100, step: 0.5, value: cur.weights[c.key] }));
  const saved = h("select", { id: "s-saved" }, h("option", { value: "" }, "gespeicherte Einstellung …"), s.profiles.map((p) => h("option", { value: p.name }, p.name)));
  saved.addEventListener("change", () => { const p = s.profiles.find((x) => x.name === saved.value); if (p) { $("s-name").value = p.name; applyStrength(p.settings).catch((error) => toast(error.message)); } });
  const apply = h("button", { type: "button", onclick: () => applyStrength(readStrengthSettings()).catch((error) => toast(error.message)) }, "Berechnen");
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
  panel.replaceChildren(
    h("details", { open: true },
      h("summary", {}, "Stärke-Index (Schätzung aus Nutzungssignalen)"),
      h("div", { class: "muted" }, STRENGTH_NOTE),
      h("div", { id: "strength-summary", class: "facts" }),
      h("div", { class: "strength-form" },
        h("label", {}, "Voreinstellung", presetSelect),
        h("label", {}, "Bracket-Signal", bracketSelect),
        h("label", {}, "Universum (oben gewählt)", h("input", { type: "text", readOnly: true, value: state.universe.name || "keines" })),
        s.meta.components.map(weightField),
        h("label", {}, "Mindest-Abdeckung (%)", h("input", { id: "s-mincov", type: "number", min: 0, max: 100, step: 5, value: Math.round(cur.min_coverage * 100) })),
        h("label", {}, "Mindestzahl Signale", h("input", { id: "s-mincomp", type: "number", min: 0, max: s.meta.components.length, step: 1, value: cur.min_components })),
        apply),
      h("div", { class: "strength-form" },
        h("label", {}, "Name", h("input", { id: "s-name", type: "text", maxLength: 80, placeholder: "z. B. Mein Index" })), save,
        h("label", {}, "Laden", saved), remove)));
  renderStrengthSummary();
}
async function initStrength() {
  const s = state.strength;
  try {
    [s.meta, s.profiles] = await Promise.all([api("/api/strength/presets"), api("/api/strength/profiles")]);
  } catch (error) { toast(`Stärke-Index nicht verfügbar: ${error.message}`); return; }
  const wanted = rememberedStrength();
  const base = wanted && typeof wanted === "object" ? wanted : s.meta.defaults;
  s.settings = { ...base, universe_profile: state.universe.name || null };
  renderStrengthPanel();
  try { await refreshStrength(); } catch (error) { toast(error.message); }
  if (!s.result && wanted) { // remembered settings no longer valid: start from the defaults
    s.settings = { ...s.meta.defaults, universe_profile: state.universe.name || null };
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
  for (const id of ["q", "type-filter", "role-filter", "f-free", "f-fav", "f-excl"]) $(id).addEventListener("input", () => { state.shown = 150; render(); });
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
