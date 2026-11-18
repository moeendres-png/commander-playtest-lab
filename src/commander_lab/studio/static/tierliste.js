"use strict";
// Commander Studio tier list. Shows the evidence per card and two clearly separate things:
// the "Stärke-Index (Schätzung aus Nutzungsdaten)" and the "Ergebnis aus Partien (noch nicht bewertet)".
// All text from data is set as text, never as HTML.

const COMMANDER = StudioCommander.current;
const VIEW_NAMES = { commander: StudioCommander.shortName(COMMANDER), global: "Global (ohne Commander)", deck: "Aktuelle Deckrevision" };
const ROLE_NAMES = {
  ramp: "Ramp", mana_rock: "Manastein", mana_dork: "Mana-Kreatur", land_ramp: "Land-Ramp",
  card_draw: "Karten ziehen", card_advantage: "Kartenvorteil", cantrip: "Cantrip",
  card_selection: "Kartenauswahl", tutor: "Tutor", removal: "Entfernung",
  board_wipe: "Massenentfernung", counterspell: "Konter", bounce: "Bounce", flicker: "Blink",
  recursion: "Rückholen", protection: "Schutz", graveyard_hate: "Friedhofshass",
  lifegain: "Lebensgewinn", evasion: "Umgehung (Evasion)", hate: "Störung (Hate)",
  tax: "Steuer / Bremse (Tax)", combat_trick: "Kampftrick", counters: "+1/+1-Marken",
  token_production: "Spielsteine", utility_land: "Funktionsland", mana_sink: "Mana-Senke",
  mill: "Millen", tapper: "Tappen", untapper: "Enttappen", sacrifice_outlet: "Opferquelle",
  anthem: "Gruppenstärkung (Anthem)", landfall: "Landfall", copy: "Kopie",
  cost_reduction: "Kostenreduktion",
};
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
// Plain German for every raw code the server sends (data classes, coverage grades, reasons). The raw code
// stays readable in the title of the node (codeNode), never as the label.
const CODE_NAMES = {
  ORIGINAL_SOURCE: "Originalquelle", NORMALIZED_SOURCE: "Quelle, vereinheitlicht", DERIVED_DESCRIPTIVE: "abgeleitet, beschreibend",
  SUBJECTIVE_RATING: "subjektive Einschätzung", SIMULATED_RESULT: "Simulation", OBSERVED_GAME: "beobachtete Spiele",
  COMPLETE: "vollständig", PARTIAL: "teilweise", SPARSE: "dünn belegt", UNOBSERVED_IN_CORPUS: "im Korpus nicht beobachtet",
  BELOW_MIN_DENOMINATOR: "Nenner unter dem Mindestwert", NEGATIVE_NEUTRAL: "negativer Wert, neutral gewertet", NOT_LISTED: "von der Quelle nicht gelistet",
  GROUP_TOO_SMALL: "Vergleichsgruppe zu klein", ZERO_COUNT: "gezählt: 0", VALUE_UNKNOWN: "Quelle nennt keinen Wert", MISSING_AS_LOWEST: "als niedrigster Rang gezählt",
  NOT_RANKED_BASIC_LAND: "Standardland, nicht bewertet", NOT_RANKED_COMMANDER: "Commander, nicht bewertet", NOT_RANKED_OTHER_COMMANDER: "andere Commander-Karte, nicht bewertet",
  ENOUGH_DATA: "genug Daten", NOT_COLLECTED: "nicht erhoben", NO_VALUE: "kein Wert", PRESENT: "vorhanden", NOT_RANKED: "nicht bewertet",
};
const codeLabel = (code) => CODE_NAMES[code] || code;
const codeNode = (code) => h("span", { title: code }, codeLabel(code));
// Raw codes inside a server sentence become plain words (the sentence itself stays the server's).
const plainCodes = (text) => String(text).replace(/\b[A-Z]{3,}(?:_[A-Z0-9]+)+\b/g, (code) => REASON_SHORT[code] || codeLabel(code));
const TYPE_NAMES = { Land: "Land", Creature: "Kreatur", Planeswalker: "Planeswalker", Battle: "Schlacht", Artifact: "Artefakt", Enchantment: "Verzauberung", Instant: "Spontanzauber", Sorcery: "Hexerei" };
const typeLabel = (group) => TYPE_NAMES[group] || group;
// Component names in plain words for the "Warum hier" sentences (the long labels stay in the detail table).
const SIGNAL_SHORT = {
  deck_universe: "Quelldecks", corpus_tuned: "getunte Decks (Bracket 4 und 5)", corpus_log_lift: "Korpus-Lift", corpus_bracket_slope: "Bracket-Neigung",
  tournament: "Turnier", edhrec_theme_reach: "EDHREC-Themen", global_inclusion: "EDHREC insgesamt", combos: "Kombos",
  commander_inclusion: "EDHREC beim Commander", bracket_inclusion: "EDHREC im Bracket", synergy: "Synergie", playgroup_observed: "Playgroup", tournament_lists: "Turnierlisten", tournament_conversion: "Turnier-Conversion",
};
const CONF_WORDS = { high: "solide", medium: "dünn", low: "sehr dünn" };
const SORTS = [
  ["name", "Name"],
  ["mv", "Manawert"],
  ["strength", "Stärke-Index (Schätzung, zu wenig Daten zuletzt)"],
  ["confidence", "Konfidenz (Datenlage, Zähler)"],
  ["spread", "Verbreitung (gezählt): Anteil im Universum"],
  ["spread_level", "Verbreitung (gezählt): Stufe im Universum"],
  ["layers", "Anzahl vorhandener Schichten"],
  ["corpus", "Anteil in Quelldecks (nur Lesehilfe)"],
  ["edhrec", "Aufnahme in EDHREC (nur Lesehilfe)"],
  ["games", "Partien mit der Karte (nur Lesehilfe)"],
  ["research", "Forschungsbedarf (Heuristik)"],
  ["rolerank", "Rang in der Funktion (mit Rollenfilter diese Rolle, sonst der beste Rang)"],
  ["textfit", "Textfit (Chulane-Regeln, Gewicht 0)"],
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
const METRIC_NAMES = { inclusion: "Aufnahme", lift: "Lift", synergy: "Synergie" };
// Cohort keys of the source rows in plain words ("all" -> all decks, "bracket:4" -> Bracket 4).
function cohortName(cohort) {
  if (cohort === "all") return "alle Decks";
  const bracket = /^bracket:(\d)$/.exec(String(cohort));
  return bracket ? `Bracket ${bracket[1]}` : String(cohort);
}
// Server sentences carry bare digit runs (10128): group them the German way, dates stay as they are.
const groupDigits = (text) => String(text).replace(/(?<![\d.,-])\d{4,}(?![\d-])/g, (digits) => nf(Number(digits)));
const LEVEL_RANK = { S: 5, A: 4, B: 3, C: 2, D: 1, U: 0 };
const NO_UNIVERSE = "kein Universum gewählt";
const FILTER_LABEL = "Filterkarte";
const SPREAD_NOTE = "Gezählt: in wie vielen Decks des gewählten Universums die Karte steht. Das ist keine Kartenstärke und kein Tier. Favoriten, Ausschlüsse und Notizen ändern keine Zählung.";
const REASON_NAMES = { FILTER_CARD: "Filterkarte des Universums", SHARE_CUT: "Anteil erreicht die Schwelle", BELOW_LOWEST_CUT: "Anteil unter der niedrigsten Schwelle", UNIVERSE_TOO_SMALL: "Universum kleiner als das Minimum", DENOMINATOR_MISSING: "Nenner fehlt", NAME_NOT_FOUND_IN_UNIVERSE: "Name kommt im Universum nicht vor (unbekannt, nicht null)", UNIVERSE_EMPTY: "Universum ist leer (0 Decks)", NO_SOURCE_DECKS_FOR_COMMANDER: "Für diesen Commander sind keine Quelldecks importiert", FILTERS_EXCLUDE_ALL_DECKS: "Die Filter des Universums lassen kein Deck übrig" };
const UNIVERSE_KEY = "studio.universe.profile";
const STRENGTH_KEY = "studio.strength.settings";
const SORT_KEY = "studio.tier.sort";
const PRESET_KEY = "studio.tier.preset";
const COMPARE_KEY = "studio.tier.compare";
const TIER_MODE_KEY = "studio.tier.mode";
const METHOD_KEY = "studio.tier.method-open";
const COMPACT_BELOW = 1500; // px: narrower windows start with the compact column set
const STRENGTH_NOTE = "Der Stärke-Index ist eine Schätzung aus Nutzungssignalen (wie oft die Karte bei diesem Commander, im Bracket, in den gewählten Decklisten und in Turnierlisten gespielt wird). Er ist keine gemessene Siegrate. Eine Karte, die eine Quelle nicht nennt, senkt die Datenlage, nie die Karte. Favoriten, Ausschlüsse und Notizen fließen nicht ein.";
const UNKNOWN_TIER = "zu wenig Daten";
const COMPONENT_STATUS = {
  PRESENT: ["vorhanden", "good"],
  NO_VALUE: ["kein Wert (fehlende Beobachtung)", "warn"],
  NOT_COLLECTED: ["Quelle nicht importiert", "dim"],
  FILTER_CARD: ["Filterkarte (nicht gerankt)", "dim"],
  NOT_RANKED: ["nicht bewertet", "dim"],
  MISSING_AS_LOWEST: ["nicht gelistet, als niedrigster Rang gezählt", "warn"],
  ZERO_COUNT: ["gezählt 0 von N (Befund, keine fehlende Beobachtung)", "warn"],
};
// A row without a value: NOT_LISTED (the source does not list the card) is told apart from a counted zero.
// Returns [plain German text, badge kind, raw code for the title].
function componentStatus(c) {
  if (c.status === "NO_VALUE" && c.reason === "NOT_LISTED") return ["nicht gelistet: fehlende Beobachtung", "warn", "NOT_LISTED"];
  if (c.status === "NO_VALUE" && c.reason) return [`kein Wert: ${codeLabel(c.reason)}`, "warn", c.reason];
  if (c.status === "NOT_COLLECTED") return ["nicht erhoben", "dim", "NOT_COLLECTED"];
  const known = COMPONENT_STATUS[c.status];
  return known ? [known[0], known[1], c.status] : [codeLabel(c.status), "dim", c.status];
}
const STRENGTH_TIERS = ["S", "A", "B", "C", "D", "U", "N"];
const nf = (value) => StudioUI.num(value, 0);
const CONFIDENCE_NAMES = { high: "hoch", medium: "mittel", low: "niedrig" };
const CONFIDENCE_TEXT = "Konfidenz = Datenlage mal Verlässlichkeit des Zählers k (k / (k + 30), gewichtet); bei gezählter Null zählt der Nenner N. Ein Hinweis auf die Belege, nicht auf die Karte; sie ändert weder Index noch Stufe.";
const REASON_SHORT = { ZERO_COUNT_ONLY: "nur gezählte Nullen", TOO_LITTLE_DATA: "zu wenig Daten", NO_COMMANDER_SIGNAL: "kein Commander-Signal", NO_SOURCE_FOR_COMMANDER: "keine Quelle für den Commander", NO_POSITIVE_WEIGHT: "alle Gewichte 0" };
const TIER_FILTER_NAMES = { U: "zu wenig Daten", N: "nicht bewertet" };
const PERCENTILE_SORT = "pct:";
const LAYER_SORT = "layer:";
const LAYER_COLUMNS_KEY = "studio.tier.layer-columns";
const LAYER_KIND_SHORT = { measured: "gemessen", derived: "abgeleitet" };
const LAYER_NOTE = "Bewertungsebenen sind eigene Spalten neben dem Stärke-Index. Sie ändern die Stufe nur, wenn du ihnen unter „Zusätzliche Ebenen“ ein Gewicht gibst (empfohlen: 0). Ein unbekannter Wert steht als „–“ mit Grund und ist nie 0.";
const SMALL_FIRST = new Set(["name", "mv", "rolerank"]);

const state = {
  view: "commander", tab: "cards", data: null, marks: new Map(), decks: [],
  universe: { profiles: [], name: "", summary: null, spread: null, options: null },
  strength: { meta: null, settings: null, profiles: [], counted: [], result: null, map: null, ticket: 0, tiers: new Set(), selectedProfile: "", good: null, note: "", draft: { fields: {}, name: "" }, status: "loading" },
  deckCards: new Map(), deckRoles: {}, pool: new Map(), ticket: 0, need: "", sortKey: "strength", sortDir: -1, shown: 150,
  layerCols: new Set(), podFilter: "", roleAudit: null, conversion: null, conversionFilter: "",
  preset: "detail", funcMode: false, lastFocus: null, lastFocusCard: "",
};

const $ = (id) => document.getElementById(id);
// The one DOM builder of the Studio (also makes name/chip click targets keyboard-operable).
function h(tag, props, ...children) { return StudioUI.h(tag, props, ...children); }
const api = (path, body, method) => StudioUI.request(path, method || (body === undefined ? "GET" : "POST"), body);
const toast = (text, kind = "") => StudioUI.toast(text, kind);
const fail = (error) => StudioUI.fail(StudioUI.germanError(error));
const roleName = (key) => ROLE_NAMES[key] || key;
const unknown = (text = "unbekannt") => h("span", { class: "unknown" }, text);
const pct = (part, of) => (of ? `${StudioUI.num(100 * part / of, 0)} %` : "");

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
// Rank within the function: the chosen role of the role filter, else the best rank over the card's roles;
// no role or no stage means no rank (sorts last, never 0).
function roleRankValue(card) {
  const item = strengthItem(card);
  const ranks = item && item.role_ranks ? item.role_ranks : null;
  if (!ranks) return null;
  const role = $("role-filter") ? $("role-filter").value : "";
  if (role) return ranks[role] ? ranks[role].rank : null;
  const all = Object.values(ranks).map((entry) => entry.rank);
  return all.length ? Math.min(...all) : null;
}
function sortValue(card, key) {
  if (key === "name") return card.name.toLowerCase();
  if (key === "mv") return card.mana_value;
  if (key === "strength") { const item = strengthItem(card); return item && item.tier !== "U" && item.tier !== "N" ? item.index : null; } // tier U sorts last
  if (key === "spread") { const item = state.universe.spread ? state.universe.spread.get(card.card_id) : undefined; return item && item.share !== null && item.share !== undefined ? item.share : null; }
  if (key === "spread_level") { const item = state.universe.spread ? state.universe.spread.get(card.card_id) : undefined; return item && !item.filter_card ? (LEVEL_RANK[item.level] ?? 0) + (item.share || 0) : null; }
  if (key === "confidence") { const item = strengthItem(card); return item && item.confidence !== null && item.confidence !== undefined ? item.confidence : null; }
  if (key.startsWith(PERCENTILE_SORT)) { // percentile of one single component; no value sorts last
    const item = strengthItem(card);
    const row = item ? item.components.find((c) => c.component === key.slice(PERCENTILE_SORT.length)) : null;
    return row && row.percentile !== null && row.percentile !== undefined ? row.percentile : null;
  }
  if (key.startsWith(LAYER_SORT)) { // percentile of one rating layer; no value sorts last
    const item = layerItem(card, key.slice(LAYER_SORT.length));
    return item && item.status === "OK" && item.percentile !== null ? item.percentile : null;
  }
  if (key === "layers") return presentCount(card);
  if (key === "corpus") { const c = corpusAll(card); return c && c.decks_known !== false && c.decks !== null && c.of ? c.decks / c.of : null; }
  if (key === "edhrec") { const w = widest(card); return w ? w.value : null; }
  if (key === "games") { const a = layer(card, "observed_game").atlas; return a && a.status === "OK" ? a.times_brought : null; }
  if (key === "research") { const r = card.coverage.research_priority; return r ? r.score : null; }
  if (key === "rolerank") return roleRankValue(card);
  if (key === "textfit") { const tf = textfitOf(card); return tf ? tf.matched_count : null; }
  return null;
}

// ---------- rating layers (Bewertungsebenen) ----------
const layerMetas = () => (state.strength.meta ? state.strength.meta.layers : []);
function layerItem(card, key) { const item = strengthItem(card); return item && item.layers ? item.layers[key] || null : null; }
function podClass(card) { const item = layerItem(card, "pod_scaling"); return item && item.status === "OK" ? item.detail.class : null; }
const shownLayers = () => layerMetas().filter((meta) => state.layerCols.has(meta.key));
function sortBy(key) {
  if (state.sortKey === key) state.sortDir = -state.sortDir;
  else { state.sortKey = key; state.sortDir = SMALL_FIRST.has(key) ? 1 : -1; }
  StudioUI.remember(SORT_KEY, state.sortKey);
  if ([...$("sort").options].some((option) => option.value === key)) $("sort").value = key;
  render(false);
}
// A sortable column head: a real button inside the th, aria-sort on the sorted column only.
function sortHead(label, key, cls = "", title = "") {
  const active = state.sortKey === key;
  const arrow = active ? (state.sortDir > 0 ? " ▲" : " ▼") : "";
  return h("th", { scope: "col", class: cls, title, "aria-sort": active ? (state.sortDir > 0 ? "ascending" : "descending") : null },
    h("button", { type: "button", class: "th-sort", onclick: () => sortBy(key) }, label, h("span", { "aria-hidden": "true" }, arrow)));
}
const plainHead = (label, cls = "", title = "") => h("th", { scope: "col", class: cls, title }, label);
function layerHead(meta) {
  return sortHead(`${meta.label} (${LAYER_KIND_SHORT[meta.kind] || meta.kind})`, LAYER_SORT + meta.key, "layer-head", `${meta.description} Quelle: ${meta.source}. Nenner: ${meta.denominator}. Klicken sortiert nach dem Perzentil.`);
}
function layerCell(card, meta) {
  if (state.view === "global") return h("span", { class: "unknown", title: "Die Ebenen werden je Commander berechnet." }, "–");
  return StudioUI.layerNode(meta, layerItem(card, meta.key));
}
function rememberLayerColumns() { StudioUI.remember(LAYER_COLUMNS_KEY, JSON.stringify([...state.layerCols])); }
function recallLayerColumns(metas) {
  const all = metas.map((meta) => meta.key);
  try {
    const stored = JSON.parse(StudioUI.recall(LAYER_COLUMNS_KEY, "null"));
    if (Array.isArray(stored)) return new Set(stored.filter((key) => all.includes(key)));
  } catch (error) { /* unreadable memory: show every layer */ }
  return new Set(all);
}
// Column menu (preset Kompakt/Detail and the rating-layer columns) and the Großpod filter. The host span sits
// in the filter bar from the start, so nothing moves when the strength metadata arrives.
function setPreset(preset) {
  state.preset = preset === "compact" ? "compact" : "detail";
  StudioUI.remember(PRESET_KEY, state.preset);
  renderLayerControls();
  render();
}
function renderLayerControls() {
  const host = $("layer-controls");
  if (!host) return;
  const metas = layerMetas();
  const compact = state.preset === "compact";
  const presetButtons = [["compact", "Kompakt"], ["detail", "Detail"]].map(([key, label]) => h("button", { type: "button", class: "chip" + (state.preset === key ? " on" : ""), "aria-pressed": String(state.preset === key), onclick: () => setPreset(key), title: key === "compact" ? "Stufe, Karte, Rolle, Manawert und Quelldecks" : "Alle Spalten" }, label));
  const layerChecks = metas.length
    ? h("div", { class: "col-layers", title: LAYER_NOTE },
      h("div", { class: "muted" }, compact ? "Bewertungsebenen (nur in der Ansicht Detail)" : "Bewertungsebenen als Spalten"),
      metas.map((meta) => h("label", { title: `${meta.description} (${LAYER_KIND_SHORT[meta.kind] || meta.kind})` },
        h("input", { type: "checkbox", value: meta.key, checked: state.layerCols.has(meta.key), disabled: compact, onchange: (event) => { if (event.target.checked) state.layerCols.add(meta.key); else state.layerCols.delete(meta.key); rememberLayerColumns(); render(); } }), ` ${meta.label}`)))
    : null;
  const menu = h("details", { class: "col-menu", id: "col-menu" },
    h("summary", {}, `Spalten: ${compact ? "Kompakt" : "Detail"}`),
    h("div", { class: "col-menu-body" }, h("div", { class: "chips", role: "group", "aria-label": "Spaltenauswahl" }, ...presetButtons), layerChecks));
  const nodes = [menu];
  if (!metas.length) nodes.push(h("select", { id: "pod-filter", "aria-label": "Großpod-Wirkung filtern", title: "wird geladen", disabled: true }, h("option", {}, "Großpod-Wirkung: alle Klassen"))); // keeps the place until the metadata is there
  if (metas.length) {
    const classes = state.strength.meta.pod_classes;
    const filter = h("select", { id: "pod-filter", "aria-label": "Großpod-Wirkung filtern", title: `Nach Großpod-Wirkung filtern. ${state.strength.meta.pod_derived_note}.` },
      h("option", { value: "" }, "Großpod-Wirkung: alle Klassen"),
      classes.map((item) => h("option", { value: item.key, title: item.help }, `Großpod-Wirkung: ${item.label}`)),
      h("option", { value: "NONE" }, "Großpod-Wirkung: unbekannt"));
    filter.value = state.podFilter;
    filter.addEventListener("input", () => { state.podFilter = filter.value; state.shown = 150; render(false); });
    nodes.push(filter);
  }
  const wasOpen = $("col-menu") ? $("col-menu").open : false;
  host.replaceChildren(...nodes);
  if (wasOpen) $("col-menu").open = true;
}

// ---------- filters and sorting ----------
function cardRoles(card) { return layer(card, "fact").roles.map((claim) => claim.role); }
function baseCards() {
  return state.view === "deck" ? state.data.cards.filter((card) => state.deckCards && state.deckCards.has(card.card_id)) : state.data.cards;
}
function visibleCards() {
  const query = $("q").value.trim();
  const parsed = StudioSearch.parseQuery(query);
  state.searchErrors = parsed.errors || [];
  if (state.searchErrors.length) return [];
  const type = $("type-filter").value, role = $("role-filter").value;
  const landKind = $("land-filter") ? $("land-filter").value : "";
  const spreadLevel = $("spread-filter") ? $("spread-filter").value : "";
  const free = $("f-free").checked, fav = $("f-fav").checked, showExcluded = $("f-excl").checked;
  let rows = state.data.cards.filter((card) => {
    const mark = state.marks.get(card.card_id) || {};
    if (state.view === "deck" && !(state.deckCards && state.deckCards.has(card.card_id))) return false;
    if (type && card.group !== type) return false;
    if (landKind === "lands" && card.group !== "Land") return false;
    if (landKind === "spells" && card.group === "Land") return false;
    if (role && !cardRoles(card).includes(role)) return false;
    if (state.podFilter && state.view !== "global") { const cls = podClass(card); if (state.podFilter === "NONE" ? cls !== null : cls !== state.podFilter) return false; }
    if (state.strength.tiers.size && state.strength.map) { const item = state.strength.map.get(card.card_id); if (!item || !state.strength.tiers.has(item.tier)) return false; }
    if (spreadLevel && state.universe.spread) { const item = state.universe.spread.get(card.card_id); if (!item || item.level !== spreadLevel) return false; }
    if (free && state.view !== "deck" && !(card.available > 0)) return false; // a deck is always shown whole
    if (fav && !mark.favorite) return false;
    if (!showExcluded && mark.excluded) return false;
    if (!query) return true;
    return StudioSearch.rank({ ...card, favorite: Boolean(mark.favorite), excluded: Boolean(mark.excluded) }, parsed) !== null;
  });
  const key = state.sortKey, dir = state.sortDir;
  // A typed search puts the better name matches (StudioSearch rank: name, name word, text) before the strength
  // order; a pure syntax query (t:..., mv<=2) has no text part, every rank is 0 and nothing is reordered.
  const byName = Boolean(query) && key === "strength" && (parsed.isPlainFreetext || Boolean(parsed.textQuery));
  rows = rows.map((card) => [sortValue(card, key), card, byName ? StudioSearch.rank(card, parsed) ?? 99 : 0]);
  rows.sort((a, b) => {
    if (a[2] !== b[2]) return a[2] - b[2];
    if (a[0] === null && b[0] === null) return a[1].name.localeCompare(b[1].name);
    if (a[0] === null) return 1;
    if (b[0] === null) return -1;
    return (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : a[1].name.localeCompare(b[1].name)) * dir;
  });
  state.nameSorted = byName && rows.length > 1 && rows.some((row) => row[2] !== rows[0][2]);
  return rows.map((row) => row[1]);
}
// The filters that are on, in words: explains why "927 Karten" becomes "926 von 927".
function activeFilterNames() {
  const out = [];
  const q = $("q").value.trim(), type = $("type-filter").value, role = $("role-filter").value;
  const landKind = $("land-filter") ? $("land-filter").value : "", spreadLevel = $("spread-filter") ? $("spread-filter").value : "";
  if (q) out.push(`Suche „${q}“`);
  if (type) out.push(`Typ ${typeLabel(type)}`);
  if (landKind) out.push(landKind === "lands" ? "nur Länder" : "nur Zauber");
  if (role) out.push(`Rolle ${roleName(role)}`);
  if (state.podFilter && state.view !== "global") out.push("Großpod-Wirkung");
  if (state.strength.tiers.size) out.push(`Stufe ${[...state.strength.tiers].join(", ")}`);
  if (spreadLevel) out.push(`Verbreitung ${spreadLevel}`);
  const base = baseCards();
  if ($("f-free").checked && state.view !== "deck" && base.some((card) => !(card.available > 0))) out.push("nur freie");
  if ($("f-fav").checked) out.push("Favoriten");
  if (!$("f-excl").checked && base.some((card) => (state.marks.get(card.card_id) || {}).excluded)) out.push("ohne Ausgeschlossene");
  return out;
}
function countLine(shown) {
  const total = baseCards().length;
  const names = activeFilterNames();
  const what = state.view === "deck" ? "Deckkarten" : "Karten";
  if (shown === total) return `${nf(total)} ${what}`;
  return `${nf(shown)} von ${nf(total)} ${what}${names.length ? ` · Filter: ${names.join(", ")}` : ""}`;
}

// ---------- cells ----------
function cardImageUrl(card, face = "front") {
  if (face === "back") return card.image_url_back || `/img/${encodeURIComponent(card.card_id)}?face=back`;
  return card.image_url_front || `/img/${encodeURIComponent(card.card_id)}`;
}
function thumb(card) {
  if (!card.has_image) return h("span", { class: "thumb" });
  const img = h("img", { class: "thumb", loading: "lazy", referrerpolicy: "no-referrer", alt: "", src: cardImageUrl(card, "front") });
  img.addEventListener("error", () => img.replaceWith(h("span", { class: "thumb", title: "Kein Bild geladen (offline)" })), { once: true });
  return img;
}
function featureBadges(card) {
  return layer(card, "fact").features.filter((f) => f.holds).map((f) => h("span", { class: "badge dim", title: f.rule }, FEATURE_NAMES[f.feature] || f.feature));
}
function textfitOf(card) {
  const item = strengthItem(card);
  return item && item.chulane_textfit ? item.chulane_textfit : null;
}
function textfitCell(card) {
  const tf = textfitOf(card);
  if (!tf) return unknown("–");
  const badges = (tf.matches || []).map((m) => h("span", { class: "badge", title: `${m.rule_id}: ${m.matched_phrase}` }, m.label));
  if (tf.foreign_trigger) {
    badges.push(h("span", { class: "badge dim", title: `Fremd-ETB-Trigger (nicht eigener ETB): ${tf.foreign_phrase || ""}` }, "Fremd-ETB"));
  }
  return h("span", { class: "tcell", title: `Regelstand ${tf.version} · Gewicht im Stärke-Index: ${nf(tf.weight_in_index)}` },
    h("span", { class: tf.matched_count ? "nowrap" : "unknown nowrap" }, `${nf(tf.matched_count)}/${nf(tf.total_rules)}`),
    ...badges);
}
// One badge per role (several sources can claim the same role); the rank k of n only as tooltip.
function roleBadges(card) {
  const claims = layer(card, "fact").roles;
  if (!claims.length) return unknown("keine Rolle erfasst");
  const item = strengthItem(card);
  const ranks = item && item.role_ranks ? item.role_ranks : {};
  const origins = new Map();
  for (const claim of claims) {
    if (!origins.has(claim.role)) origins.set(claim.role, []);
    const name = ORIGIN_NAMES[claim.origin] || claim.origin;
    if (!origins.get(claim.role).includes(name)) origins.get(claim.role).push(name);
  }
  return [...origins].map(([role, from]) => {
    const rInfo = ranks[role];
    const title = `Herkunft: ${from.join(", ")}` + (rInfo ? ` · Rang ${nf(rInfo.rank)} von ${nf(rInfo.total)} in der Funktion ${roleName(role)} (nach dem Index im Gesamtpool)` : "");
    return h("span", { class: "badge", title }, roleName(role));
  });
}
// Rank k of n within each function of the card, without a tier letter (mode "Gleiche Funktion").
function functionRankCell(card) {
  const item = strengthItem(card);
  if (!item) return unknown("–");
  const ranks = Object.entries(item.role_ranks || {});
  if (!ranks.length) return unknown(cardRoles(card).length ? "kein Rang (ohne Stufe)" : "keine Rolle: kein Rang");
  const chosen = $("role-filter") ? $("role-filter").value : "";
  ranks.sort((a, b) => (a[0] === chosen ? -1 : b[0] === chosen ? 1 : a[1].rank - b[1].rank));
  return h("div", { class: "rankcell" }, ranks.map(([role, rInfo]) => h("div", { class: "rank-line" + (role === chosen ? " sel" : ""), title: `Rang ${nf(rInfo.rank)} von ${nf(rInfo.total)} Karten mit Stufe in der Funktion ${roleName(role)}, nach dem Index im Gesamtpool` }, `${roleName(role)}: Rang ${nf(rInfo.rank)} von ${nf(rInfo.total)}`)));
}
function corpusCell(card) {
  const item = corpusAll(card);
  if (!item) return unknown(layer(card, "observed_deck").status === "NOT_COLLECTED" ? "keine Quelle" : "unbekannt");
  if (item.decks_known === false || item.decks === null) return unknown("unbekannt (kein Quelldeck nennt diese Karte)");
  const text = `${nf(item.decks)}/${nf(item.of)} · ${pct(item.decks, item.of)}`;
  return h("span", { class: item.decks ? "nowrap" : "unknown nowrap", title: item.decks ? "Quelldecks mit der Karte, ohne Duplikate" : "0 in einem bekannten Korpus: fehlende Beobachtung, keine Schwäche" }, text);
}
function edhrecCell(card) {
  const w = widest(card);
  if (!w) return unknown(layer(card, "observed_deck").edhrec ? "keine Beobachtung" : "keine Quelle");
  const den = w.denominator === null ? "Nenner unbekannt" : `${nf(w.numerator)}/${nf(w.denominator)}`;
  return h("span", { title: `Ansicht ${cohortName(w.cohort)}; Datenklasse ${codeLabel(w.data_class)}` }, `${den}`, w.small_denominator ? h("span", { class: "badge warn" }, "n < 30") : null, w.snapshot_known ? null : h("span", { class: "badge dim" }, "Zeit unbekannt"));
}
function gameCell(card) {
  const game = layer(card, "observed_game"), atlas = game.atlas;
  if (game.status !== "PRESENT" || !atlas) return unknown(game.status === "NOT_COLLECTED" ? "keine Quelle" : "keine Beobachtung");
  const brought = atlas.times_brought === null ? "n unbekannt" : `n = ${nf(atlas.times_brought)}`;
  const gap = atlas.observed_winrate_gap_pp === null ? null : `Differenz ${atlas.observed_winrate_gap_pp > 0 ? "+" : ""}${StudioUI.numFlex(atlas.observed_winrate_gap_pp, 2)} Pp`;
  const ci = atlas.ci_95_lower_pp === null || atlas.ci_95_upper_pp === null ? null : ` (95 %: ${StudioUI.numFlex(atlas.ci_95_lower_pp, 2)} bis ${StudioUI.numFlex(atlas.ci_95_upper_pp, 2)})`;
  const turn = atlas.median_cast_turn === null || atlas.median_cast_turn === undefined ? null : `Zug ~${StudioUI.numFlex(atlas.median_cast_turn, 1)}`;
  return h("span", { title: "Playgroup.gg (CC BY 4.0), alle Commander, nur Live-Partien. Beobachteter Zusammenhang (mit Zug-Timing gegen Survival-Verzerrung), keine kausale Kartenstärke." }, brought, gap ? ` · ${gap}` : "", ci || "", turn ? ` · ${turn}` : "", atlas.insufficient_sample ? h("span", { class: "badge warn" }, "kleine Stichprobe") : null);
}
function simCell(card) {
  const sim = layer(card, "simulated_result");
  if (sim.status === "NOT_APPLICABLE") return unknown("–");
  if (!sim.totals) return unknown("nicht simuliert");
  return `${nf(sim.totals.games_cast_after_offer)}/${nf(sim.totals.games_offered)} Partien`;
}
function strengthItem(card) { const map = state.strength.map; return map ? map.get(card.card_id) || null : null; }
const neutral = (text, title) => h("span", { class: "badge-neutral", title }, text);
function tierBadge(tier, text, title) {
  return h("span", { class: `tier-badge t-${tier}`, title }, h("span", { class: "level letter" }, tier), text);
}
// Cell of a tier U card: never a score, never "0.0". A counted zero names its count (0/N), a gap names
// the reason code.
function unknownCell(card, item) {
  const zero = item.components.find((c) => c.status === "ZERO_COUNT" && c.denominator);
  const code = item.reason || "TOO_LITTLE_DATA";
  const text = item.reason === "ZERO_COUNT_ONLY" && zero ? `unbekannt (0/${nf(zero.denominator)})` : "unbekannt (zu wenig Daten)";
  const why = `${REASON_SHORT[code] || code} (${code})`;
  return h("span", { class: "ucell" }, neutral(text, `Zu wenig Daten für eine Stufe: ${why}. Das sagt nichts über die Stärke der Karte.`), h("span", { class: "rule reason-code" }, REASON_SHORT[code] || code));
}
// The deck-list count behind the index: n of N source decks (the "Decklisten-Universum" signal).
function deckCounts(item) {
  const c = item.components.find((x) => x.component === "deck_universe" && x.denominator);
  return c && c.numerator !== null && c.numerator !== undefined ? { n: c.numerator, N: c.denominator } : null;
}
function confidenceText(item) {
  if (item.confidence_basis === "gezaehlte_null") { // field of the counted-numerator confidence (when the server sends it)
    const zero = deckCounts(item);
    return `hoch (gezählte Abwesenheit: 0 von ${zero ? nf(zero.N) : "N"} Decks)`;
  }
  const word = CONF_WORDS[item.confidence_level] || codeLabel(item.confidence_level);
  const counts = deckCounts(item);
  return counts ? `${nf(counts.n)} von ${nf(counts.N)} Quelldecks, ${word}` : word;
}
function confidenceMark(item) {
  if (item.confidence === null || item.confidence === undefined) return null;
  const level = CONFIDENCE_NAMES[item.confidence_level] || item.confidence_level;
  const dots = item.confidence_level === "high" ? "●●●" : item.confidence_level === "medium" ? "●●○" : "●○○";
  return h("span", { class: `conf conf-${item.confidence_level}`, title: `Datenlage: ${confidenceText(item)}. Konfidenz ${level} (${StudioUI.num(item.confidence, 2)}). ${CONFIDENCE_TEXT}`, "aria-label": `Datenlage: ${confidenceText(item)}` }, dots);
}
function borderlineMark(item) {
  if (!item.borderline) return null;
  return h("span", { class: "borderline", title: `grenzwertig: ${StudioUI.num(item.cut_distance, 1)} Punkte von der Grenze ${StudioUI.numFlex(item.borderline_cut, 1)}. Eine kleine Änderung der Gewichte kann die Stufe ändern.` }, "grenzwertig");
}
function unsharpMark(item) {
  if (!item.unscharf) return null;
  const alts = (item.tier_alternatives || []).map((a) => `${a.tier}: ${nf(a.count)}/${nf(item.tier_stability_variants)}`).join(", ");
  const stab = item.tier_stability !== null && item.tier_stability !== undefined ? `${StudioUI.pct(item.tier_stability, 0)} (${nf(item.tier_stability_kept)}/${nf(item.tier_stability_variants)})` : "";
  return h("span", { class: "unsharp", title: `unscharf: Stufe bleibt nur in ${stab} der Gewichtsvarianten${alts ? ` (${alts})` : ""}.` }, "unscharf");
}
// One plain sentence per row (tooltip of the tier badge): tier, source-deck share, best function rank, data situation.
function rowSummary(item) {
  const parts = [`Stufe ${item.tier}${item.relative_tier && item.relative_tier !== item.tier ? ` (relativ im Pool ${item.relative_tier})` : ""}, Index ${StudioUI.num(item.index, 1)}`];
  const counts = deckCounts(item);
  if (counts) parts.push(`in ${nf(counts.n)} von ${nf(counts.N)} Quelldecks (${StudioUI.pct(counts.n / counts.N, 1)})`);
  const best = Object.entries(item.role_ranks || {}).sort((a, b) => a[1].rank - b[1].rank)[0];
  if (best) parts.push(`Rang ${nf(best[1].rank)} von ${nf(best[1].total)} in der Funktion ${roleName(best[0])}`);
  if (item.confidence !== null && item.confidence !== undefined) parts.push(`Datenlage ${CONF_WORDS[item.confidence_level] || item.confidence_level}`);
  if (item.unscharf && item.tier_stability !== null && item.tier_stability !== undefined) parts.push(`unscharf (${StudioUI.pct(item.tier_stability, 0)})`);
  return `${parts.join("; ")}.`;
}
function strengthCell(card) {
  if (state.view === "global") return neutral("nur je Commander", "Der Stärke-Index wird je Commander berechnet.");
  const item = strengthItem(card);
  if (!item) return state.strength.status === "loading" && !state.strength.map
    ? neutral("wird berechnet …", "Der Stärke-Index wird gerade berechnet.")
    : neutral("nicht berechnet", "Für diese Karte liegt keine Berechnung vor.");
  const title = `${rowSummary(item)} Schätzung aus Nutzungssignalen, keine Siegrate. Abdeckung ${StudioUI.num(100 * item.coverage, 0)} %, ${nf(item.present)} Signale vorhanden.`;
  if (item.tier === "N") return neutral(item.note, `${item.note}: Commander und Standardländer bekommen keine Stufe.`);
  if (item.tier === "U") return unknownCell(card, item);
  const shownTier = state.tierMode === "relative" && item.relative_tier ? item.relative_tier : item.tier;
  const relNote = state.tierMode === "relative" && item.relative_tier ? h("span", { class: "rule", title: `Absolute Stufe: ${item.tier}` }, `abs ${item.tier}`) : null;
  return h("span", { class: "tcell" }, tierBadge(shownTier, StudioUI.num(item.index, 1), title), relNote, confidenceMark(item), borderlineMark(item), unsharpMark(item));
}
function datenlageCell(card) {
  const item = strengthItem(card);
  if (!item || item.tier === "U" || item.tier === "N" || item.confidence === null || item.confidence === undefined) return unknown("–");
  // short form in the cell (one line); the full sentence is in the tooltip and the aria-label
  const counts = deckCounts(item);
  const short = item.confidence_basis === "gezaehlte_null" ? "hoch · gezählte 0" : counts ? `${nf(counts.n)}/${nf(counts.N)} · ${CONF_WORDS[item.confidence_level] || item.confidence_level}` : confidenceText(item);
  return h("span", { class: "nowrap", title: `${confidenceText(item)}. ${CONFIDENCE_TEXT}`, "aria-label": `Datenlage: ${confidenceText(item)}` }, short);
}
function spreadCell(card) {
  const uni = state.universe;
  if (!uni.name || !uni.spread) return neutral(NO_UNIVERSE, "Wähle oben ein Universum, um die gezählte Verbreitung zu sehen.");
  const item = uni.spread.get(card.card_id);
  if (!item) return neutral("unbekannt", "Keine Zählung für diese Karte.");
  return spreadBadge(item, uni.spread.universe);
}
function spreadBadge(item, universe) {
  const subset = universe.subset_note ? ` ${universe.subset_note}.` : "";
  if (item.filter_card) {
    return neutral(FILTER_LABEL, `${FILTER_LABEL}: das Universum verlangt diese Karte, sie steht per Definition in jedem Deck der Teilmenge (ohne Zählung, ohne Stufe). Universum ${universe.profile}.${subset}`);
  }
  const label = item.level_name || item.level;
  const counted = item.matched ? `${nf(item.hits)}/${nf(item.denominator)}` : "unbekannt";
  const title = `${SPREAD_LABEL}: ${label} (${REASON_NAMES[item.reason] || item.reason}). Universum ${universe.profile}, ${nf(universe.denominator)} Decks, Stand ${universe.snapshot_id}.${subset}`;
  if (counted === "unbekannt") return neutral(item.level && item.level !== "U" ? `${label} (unbekannt)` : "unbekannt", title);
  return neutral(`${label} · ${counted}`, title);
}
function statusBadge(status) {
  const [text, kind] = STATUS_NAMES[status] || [status, "dim"];
  return h("span", { class: `badge ${kind}` }, text);
}
function needBadges(card) {
  return card.coverage.needs.map((need) => h("span", { class: "badge warn" }, NEED_NAMES[need] || need));
}

// ---------- tables ----------
// Columns of the card table. "Kompakt" keeps the tier, card, marks, rank, mana value, roles and source decks;
// "Detail" adds the rating layers, spread, mechanics, EDHREC, games and layers. Tier and card stay sticky.
function tableColumns() {
  const commander = state.view !== "global";
  const compact = state.preset === "compact";
  const metas = compact ? [] : shownLayers();
  // The counted spread is its own column only while a stored universe is chosen. There is no
  // outcome column: no card has a result from games ("Unbewertet"), the pill above says so.
  const spread = !compact && Boolean(state.universe.name && state.universe.spread);
  const cell = (cls, build) => (card) => h("td", { class: cls }, build(card));
  return [
    { head: () => sortHead("Stufe", "strength", "stick-1", "Stufe aus dem Stärke-Index: Schätzung aus Nutzungsdaten in Commander-Decks, keine Spielstärke. Klick sortiert."), cell: cell("stick-1", strengthCell) },
    { head: () => sortHead("Karte", "name", "stick-2"), cell: (card) => {
      const mark = state.marks.get(card.card_id) || {};
      return h("td", { class: "cardcell name stick-2", "data-card-id": card.card_id, onclick: () => openCard(card) }, thumb(card), mark.favorite ? h("span", { class: "star" }, "★ ") : null, card.name);
    } },
    { head: () => plainHead("Favorit / Deck"), cell: cell("acts", markButtons) },
    ...(state.funcMode && commander ? [{ head: () => sortHead("Rang in Funktion", "rolerank", "", "Rang k von n Karten mit Stufe in der gleichen Funktion (Rolle), nach dem Index im Gesamtpool. Die Stufe bleibt die Stufe im Gesamtpool."), cell: cell("", functionRankCell) }] : []),
    ...(compact || !commander ? [] : [{ head: () => sortHead("Datenlage", "confidence", "", CONFIDENCE_TEXT), cell: cell("", datenlageCell) }]),
    ...metas.map((meta) => ({ head: () => layerHead(meta), cell: cell("", (card) => layerCell(card, meta)) })),
    ...(spread ? [{ head: () => sortHead(SPREAD_LABEL, "spread"), cell: cell("", spreadCell) }] : []),
    { head: () => sortHead("MW", "mv", "num", "Manawert"), cell: (card) => h("td", { class: "num" }, StudioUI.numFlex(card.mana_value, 2)) },
    ...(compact ? [] : [{ head: () => plainHead("Mechanik"), cell: cell("", featureBadges) }]),
    ...(compact || !(state.strength.result && state.strength.result.chulane_textfit_version)
      ? []
      : [{ head: () => sortHead("Textfit (Chulane)", "textfit", "", "Deterministische Chulane-Regeltext-Prüfung (Gewicht im Stärke-Index: 0)."), cell: cell("", textfitCell) }]),
    { head: () => plainHead("Rollen"), cell: cell("", roleBadges) },
    ...(commander
      ? [{ head: () => sortHead("Quelldecks", "corpus"), cell: cell("", corpusCell) }, ...(compact ? [] : [{ head: () => sortHead("Aufnahme (EDHREC)", "edhrec"), cell: cell("", edhrecCell) }])]
      : [{ head: () => plainHead("Beliebtheit (global)"), cell: (card) => {
        const rank = (layer(card, "observed_deck").items || []).find((item) => item.kind === "edhrec_rank_global");
        return h("td", { class: "num" }, rank ? `Rang ${nf(rank.rank)}` : unknown("unbekannt"));
      } }]),
    ...(compact ? [] : [{ head: () => sortHead("Echte Spiele", "games"), cell: cell("", gameCell) }]),
    ...(compact ? [] : [{ head: () => sortHead("Schichten", "layers"), cell: (card) => h("td", { title: card.coverage.present.map((name) => LAYER_NAMES[name]).join(", ") }, `${nf(presentCount(card))}/4`) }]),
    ...(state.view === "deck" ? [{ head: () => plainHead("im Deck"), cell: (card) => h("td", { class: "num" }, nf(state.deckCards.get(card.card_id))) }] : []),
  ];
}
// A sort key whose column is not on screen (compact column set, or the function rank outside its mode) says so.
function hiddenSortNote() {
  const key = state.sortKey, option = $("sort").selectedOptions && $("sort").selectedOptions[0];
  const label = option ? option.textContent : key;
  if (key === "rolerank" && !state.funcMode) return `Sortiert nach „${label}“: Spalte nur im Vergleich „Gleiche Funktion“ sichtbar`;
  const detailOnly = key === "confidence" || key === "spread" || key === "edhrec" || key === "games" || key === "layers" || key === "textfit" || key.startsWith(LAYER_SORT);
  if (detailOnly && state.preset === "compact") return `Sortiert nach „${label}“ (Spalte im Kompakt ausgeblendet)`;
  return "";
}
function sortCaption() {
  const option = $("sort").selectedOptions && $("sort").selectedOptions[0];
  return `${option ? option.textContent : state.sortKey}, ${state.sortDir > 0 ? "aufsteigend" : "absteigend"}`;
}
function cardsTable(cards) {
  const columns = tableColumns();
  const rows = cards.slice(0, state.shown).map((card) => h("tr", {}, columns.map((column) => column.cell(card))));
  return h("div", { class: "table-wrap" }, h("table", { id: "tier-table" },
    h("caption", { class: "visually-hidden" }, `Tierliste für ${VIEW_NAMES.commander}: ${countLine(cards.length)}, sortiert nach ${sortCaption()}`),
    h("thead", {}, h("tr", {}, columns.map((column) => column.head()))),
    h("tbody", {}, rows)));
}
function researchTable(cards) {
  const wanted = state.need || "";
  const rows = cards.filter((card) => card.coverage.needs.length && (!wanted || card.coverage.needs.includes(wanted))).slice(0, 200).map((card) => {
    const priority = card.coverage.research_priority;
    return h("tr", {},
      h("td", { class: "cardcell name", "data-card-id": card.card_id, onclick: () => openCard(card) }, thumb(card), card.name),
      h("td", { class: "num", title: "Heuristik für die Reihenfolge der Recherche, keine Kartenstärke" }, priority ? StudioUI.num(priority.score, 2) : unknown("–")),
      h("td", {}, card.coverage.gap_grade ? codeNode(card.coverage.gap_grade) : unknown("–")),
      h("td", {}, needBadges(card)),
      h("td", {}, roleBadges(card)));
  });
  return h("div", { class: "table-wrap" }, h("table", {},
    h("caption", { class: "visually-hidden" }, `Forschungsliste für ${VIEW_NAMES.commander}: Karten mit offenen Lücken, nach Forschungspriorität`),
    h("thead", {}, h("tr", {}, ["Karte", "Priorität (Heuristik)", "Abdeckung", "Was fehlt", "Rollen"].map((label) => h("th", { scope: "col" }, label)))),
    h("tbody", {}, rows)));
}
// An empty table always says why (and, where it helps, what to do).
function emptyState(cards) {
  const marked = [...state.marks.values()].some((mark) => mark.favorite);
  if ($("f-fav").checked && !marked) return h("p", { class: "empty-note", id: "empty-note" }, "Keine Favoriten markiert. Markiere Karten in der Tabelle mit ☆, dann erscheinen sie hier.");
  const names = activeFilterNames();
  return h("div", { class: "empty-note", id: "empty-note" },
    h("p", {}, names.length ? `Keine Karte passt zu den Filtern (${names.join(", ")}).` : "Keine Karte in dieser Ansicht."),
    names.length ? h("button", { type: "button", onclick: resetFilters }, "Filter zurücksetzen") : null);
}
function resetFilters() {
  $("q").value = ""; $("type-filter").value = ""; $("role-filter").value = "";
  if ($("land-filter")) $("land-filter").value = "";
  if ($("spread-filter")) $("spread-filter").value = "";
  $("f-fav").checked = false; $("f-free").checked = true; $("f-excl").checked = false;
  state.podFilter = ""; state.strength.tiers.clear();
  if ($("pod-filter")) $("pod-filter").value = "";
  state.shown = 150;
  renderTierBar();
  render(false);
}

function render(keepScroll = true) {
  const body = $("pool-body");
  const top = body.scrollTop, left = body.scrollLeft;
  body.replaceChildren();
  if (!state.data) return;
  const cards = visibleCards();
  $("count").textContent = `${countLine(cards.length)}${state.nameSorted ? " · Treffer nach Name zuerst" : ""}`;
  body.setAttribute("aria-label", state.tab === "research" ? "Forschungsliste" : "Tierliste: Kartentabelle");
  const sortNote = hiddenSortNote();
  $("sort-note").textContent = sortNote;
  $("sort-note").hidden = !sortNote;
  if (state.searchErrors && state.searchErrors.length) {
    body.append(h("div", { id: "search-syntax-error", class: "empty" },
      h("b", {}, "Hinweis zur Such-Syntax:"),
      ...state.searchErrors.map((msg) => h("p", {}, msg)),
      h("p", { class: "muted" }, 'Beispiele: t:creature · mv<=2 · r:ramp · c:gu · id<=gwu · -t:land · "draw a card"')));
    return;
  }
  if (state.tab === "research") {
    if (state.view === "global") { body.append(h("p", { class: "note" }, `Der Forschungsbedarf wird je Commander berechnet. Wähle die Ansicht ${VIEW_NAMES.commander}.`)); return; }
    const needs = [...new Set(state.data.cards.flatMap((card) => card.coverage.needs))].sort();
    const select = h("select", { id: "need-filter", onchange: () => { state.need = select.value; render(false); } }, h("option", { value: "" }, "alle Lücken"), needs.map((need) => h("option", { value: need }, NEED_NAMES[need] || need)));
    const previous = needs.includes(state.need) ? state.need : "";
    state.need = previous;
    body.append(h("p", { class: "note" }, "Reihenfolge aus fehlender Evidenz mal Deck-Relevanz. Eine Lücke ist kein schlechtes Urteil über die Karte."), h("label", {}, "Lücke ", select));
    select.value = previous;
    body.append(researchTable(cards));
    return;
  }
  if (!cards.length) { body.append(emptyState(cards)); return; }
  body.append(cardsTable(cards));
  if (cards.length > state.shown) body.append(h("p", {}, h("button", { type: "button", onclick: () => { state.shown += 200; render(); } }, `weitere ${nf(Math.min(200, cards.length - state.shown))} zeigen`)));
  if (keepScroll) { body.scrollTop = top; body.scrollLeft = left; }
}

// ---------- notice ----------
// Source decks are counted per commander only; decks of another commander or without one are named, never added.
function bindingLine() {
  const binding = state.data.corpus_binding;
  if (state.view === "global" || !binding) return null;
  const parts = [`Quelldecks für ${VIEW_NAMES.commander}: ${nf(binding.bound_decks)}`];
  if (binding.other_commander_decks) parts.push(`${nf(binding.other_commander_decks)} gehören zu anderen Commandern und zählen hier nicht`);
  if (binding.unbound_decks) parts.push(`${nf(binding.unbound_decks)} ohne Commander-Zuordnung zählen nirgends`);
  return h("div", { class: "summary" }, parts.join(" · "), binding.bound_decks ? "" : " · Für diesen Commander sind noch keine Quelldecks importiert: fehlende Beobachtung, keine Schwäche.");
}
// Per source: how many cards sit in which state. Every card is in exactly one column, so the row adds up to the pool.
const STATUS_COLUMNS = {
  PRESENT: "mit Beleg", ABSENT_IN_KNOWN_CORPUS: "gezählt 0 (fehlende Beobachtung, keine Schwäche)", NONE_RECORDED: "nichts erfasst",
  NOT_COLLECTED: "Quelle noch nicht importiert", NOT_APPLICABLE: "in dieser Ansicht nicht anwendbar",
};
function layerStatusTable(status) {
  const names = ["observed_deck", "observed_game"];
  const keys = [...new Set(names.flatMap((name) => Object.keys(status[name] || {})))];
  const sum = (counts) => Object.values(counts || {}).reduce((total, n) => total + n, 0);
  return h("div", { class: "table-wrap" }, h("table", { class: "dist", id: "layer-status" },
    h("caption", { class: "visually-hidden" }, "Karten je Quelle und Beleglage"),
    h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Quelle"), keys.map((key) => h("th", { scope: "col", class: "num", title: key }, STATUS_COLUMNS[key] || key)), h("th", { scope: "col", class: "num" }, "Summe"))),
    h("tbody", {}, names.map((name) => h("tr", {}, h("th", { scope: "row" }, LAYER_NAMES[name]), keys.map((key) => h("td", { class: "num" }, nf((status[name] || {})[key] || 0))), h("td", { class: "num" }, nf(sum(status[name]))))))));
}
function renderNotice() {
  const summary = state.data.summary, policy = state.data.tier_policy;
  const status = summary.layer_status;
  const inDeckCount = state.data.cards.filter((card) => state.deckCards.has(card.card_id)).length;
  const viewSummary = state.view === "deck"
    ? `${nf(inDeckCount)} im Deck von ${nf(summary.cards)} legalen Karten. `
    : `Kartenpool dieser Ansicht: ${nf(summary.cards)} Karten. `;
  $("notice").replaceChildren(
    h("details", { id: "tier-explain", class: "explain", title: `${policy.version}: ${policy.rule}` },
      h("summary", {}, "Was bedeuten die Stufen?"),
      h("p", {}, h("b", {}, `${INDEX_HEADING}: `), INDEX_TEXT),
      h("p", {}, h("b", {}, `${OUTCOME_HEADING}: `), OUTCOME_TEXT)),
    h("div", { class: "summary" }, viewSummary, "Jede Karte steht je Quelle in genau einer Spalte; die Summe ist die Zahl der Karten im Pool."),
    layerStatusTable(status),
    ...[bindingLine()].filter(Boolean));
  $("tier-pill").textContent = "Stufen: Schätzung aus Nutzungsdaten · Ergebnis aus Partien: Unbewertet";
  updateMethodHint();
}

// ---------- evidence drawer ----------
function table(heads, rows) {
  return h("div", { class: "table-wrap" }, h("table", {}, h("thead", {}, h("tr", {}, heads.map((x) => h("th", { scope: "col" }, x)))), h("tbody", {}, rows.map((row) => h("tr", {}, row.map((cell) => h("td", {}, cell)))))));
}
function drawer(card) {
  const box = [];
  const heading = (name, status) => h("h3", {}, LAYER_NAMES[name], statusBadge(status));
  const fact = layer(card, "fact");
  const tf = textfitOf(card);
  const tfNodes = tf ? [
    h("p", {}, `Chulane-Textfit (${tf.version}, Gewicht im Stärke-Index: ${nf(tf.weight_in_index)}): ${nf(tf.matched_count)}/${nf(tf.total_rules)} Regeln erfüllt`),
    tf.matches && tf.matches.length
      ? table(["Regel", "Beleg / Phrase"], tf.matches.map((m) => [m.label, h("span", { class: "rule" }, m.matched_phrase)]))
      : h("p", { class: "rule" }, "Keine Chulane-Textfit-Regel erfüllt."),
    ...(tf.foreign_trigger ? [h("p", { class: "rule" }, `Fremd-ETB-Trigger (nicht als eigener ETB gezählt): ${tf.foreign_phrase || "–"}`)] : []),
  ] : [];
  box.push(h("div", { class: "layer" }, heading("fact", fact.status),
    h("p", {}, `Manawert ${StudioUI.numFlex(fact.mana_value, 2)} · ${fact.type_line} · Quelle der Fakten: ${fact.fact_source} · Regelstand ${fact.rules_version}`),
    table(["Merkmal", "trifft zu", "Regel"], fact.features.map((f) => [FEATURE_NAMES[f.feature] || f.feature, f.holds ? "ja" : "nein", h("span", { class: "rule" }, f.rule)])),
    ...tfNodes,
    h("p", {}, "Rollen mit Herkunft (Tagger-Rollen sind Community-Einordnungen):"),
    fact.roles.length ? fact.roles.map((c) => h("span", { class: "badge", title: [c.original_tag, c.mapping_rule].filter(Boolean).join(" · ") }, `${roleName(c.role)} · ${ORIGIN_NAMES[c.origin] || c.origin}`)) : unknown("keine Rolle erfasst")));

  const deck = layer(card, "observed_deck");
  const corpus = (deck.items || []).filter((item) => item.kind === "corpus");
  const rank = (deck.items || []).find((item) => item.kind === "edhrec_rank_global");
  const deckBox = h("div", { class: "layer" }, heading("observed_deck", deck.status));
  if (rank) deckBox.append(h("p", {}, `Globale Beliebtheit (Scryfall, EDHREC-Rang): ${nf(rank.rank)}. Niedriger ist beliebter. Das ist kein Stärkemaß.`));
  if (corpus.length) deckBox.append(h("p", {}, "Quelldecks nach Gruppe, jeweils mit eigenem Nenner. Die Gruppen überlappen: nie addieren."), table(["Gruppe", "Decks mit Karte", "von", "Anteil", ""], corpus.map((item) => { const known = item.decks_known !== false && item.decks !== null; return [cohortName(item.cohort), known ? nf(item.decks) : unknown(), nf(item.of), known ? pct(item.decks, item.of) : unknown("–"), item.small_denominator ? h("span", { class: "badge warn" }, "n < 30") : ""]; })));
  if (deck.edhrec_rows && deck.edhrec_rows.length) {
    deckBox.append(h("p", {}, "EDHREC-Beobachtungen. Inclusion, Lift und Synergy sind verschiedene Maße und nie ein gemeinsamer Wert."), table(["Ansicht", "Maß", "Wert", "Decks/Nenner", "Stand", "Datenklasse"], deck.edhrec_rows.map((row) => [cohortName(row.cohort), METRIC_NAMES[row.metric] || row.metric, row.value === null ? unknown() : StudioUI.numFlex(row.value, 4), row.denominator_known ? `${row.numerator !== null && row.numerator !== undefined ? nf(row.numerator) : "?"}/${nf(row.denominator)}${row.small_denominator ? " (n < 30)" : ""}` : unknown("Nenner unbekannt"), row.snapshot_known ? row.snapshot : unknown("Zeit unbekannt"), codeNode(row.data_class)])));
  } else if (state.view !== "global") {
    deckBox.append(h("p", {}, "Keine EDHREC-Beobachtung für diese Karte."));
  }
  if (state.view === "global" && !rank) deckBox.append(h("p", {}, "Für die globale Ansicht ist noch keine commanderunabhängige Deck-Quelle importiert."));
  box.push(deckBox);

  const game = layer(card, "observed_game");
  const atlas = game.atlas;
  const val = (x, suffix = "", digits = 2) => (x === null || x === undefined ? unknown() : `${typeof x === "number" ? StudioUI.numFlex(x, digits) : x}${suffix}`);
  box.push(h("div", { class: "layer" }, heading("observed_game", game.status), h("p", {}, GAME_NOTES[game.status] || game.note),
    atlas && game.status === "PRESENT" ? [
      h("p", {}, `Quelle: Playgroup.gg Card Atlas (CC BY 4.0). Grundgesamtheit: alle Commander, nur Playgroup-Live-Partien.`),
      table(["Messwert", "Wert"], [
        ["Mitgebracht (Partien)", val(atlas.times_brought, "", 0)],
        ["Live-Inclusion", val(atlas.live_inclusion_pct, " %")],
        ["Median Zug des ersten Wirkens", val(atlas.median_cast_turn)],
        ["Siegrate, wenn gewirkt", val(atlas.winrate_when_cast_pct, " %")],
        ["Differenz gewirkt gegen Bibliothek", val(atlas.observed_winrate_gap_pp, " Pp")],
        ["95-%-Intervall der Differenz", atlas.ci_95_lower_pp === null || atlas.ci_95_upper_pp === null ? unknown() : `${StudioUI.numFlex(atlas.ci_95_lower_pp, 2)} bis ${StudioUI.numFlex(atlas.ci_95_upper_pp, 2)} Pp`],
        ["Stichprobe", atlas.insufficient_sample ? h("span", { class: "badge warn" }, "zu klein") : "ausreichend laut Import"],
      ]),
      h("p", {}, "Die Differenz vergleicht Partien, in denen die Karte gewirkt wurde, mit Partien, in denen sie in der Bibliothek blieb. Wer eine Karte wirken kann, steht oft schon besser da. Das ist kein Beweis für Kartenstärke."),
    ] : null));
  const combo = layer(card, "combo_verified");
  box.push(h("div", { class: "layer" }, heading("combo_verified", combo.status), combo.note ? h("p", {}, "Eine gelistete Kombo ist kein Beleg für Stärke und kein bestandener Engine-Test.") : null));
  const sim = layer(card, "simulated_result");
  box.push(h("div", { class: "layer" }, heading("simulated_result", sim.status), sim.totals ? h("p", {}, `${nf(sim.totals.runs)} Läufe: in ${nf(sim.totals.games_cast_after_offer)} von ${nf(sim.totals.games_offered)} Partien nach dem Angebot gespielt (${nf(sim.totals.cast_count)} Zauber). Simulierte Ergebnisse stehen für sich und werden nie mit echten Spielen verrechnet.`) : null));

  const cov = card.coverage;
  box.push(h("div", { class: "layer" }, h("h3", {}, "Abdeckung und Forschungsbedarf"),
    h("p", {}, `Vorhanden: ${cov.present.map((name) => LAYER_NAMES[name]).join(", ") || "nichts"}.`),
    cov.needs.length ? h("div", {}, needBadges(card)) : h("p", {}, "Keine offene Lücke."),
    cov.gap_grade ? h("p", {}, `Lückenklasse: ${codeLabel(cov.gap_grade)}. Forschungspriorität (Heuristik, keine Kartenstärke): ${StudioUI.num(cov.research_priority.score, 2)}${cov.research_priority.long_tail ? ", Long-Tail-Kandidat" : ""}.`) : null));
  return box;
}
function strengthBox(card) {
  const item = strengthItem(card);
  const label = item && item.tier === "N" ? item.note : item && item.tier === "U" ? UNKNOWN_TIER : null;
  const box = h("div", { class: "layer" }, h("h3", {}, INDEX_HEADING,
    item ? (label !== null ? neutral(label, STRENGTH_NOTE) : tierBadge(item.tier, StudioUI.num(item.index, 1), "Schätzung aus Nutzungsdaten")) : null),
    h("p", {}, STRENGTH_NOTE));
  if (!item) { box.append(h("p", {}, state.view === "global" ? "Der Index wird je Commander berechnet." : "Für diese Karte liegt keine Berechnung vor.")); return box; }
  if (item.tier === "N") {
    const reasonText = item.reason === "NOT_RANKED_COMMANDER"
      ? "der Commander bekommt keine Stufe und nimmt keinem Rang einen Platz weg. Die Einstellung „Commander und Standardländer bewerten“ ändert das."
      : item.reason === "NOT_RANKED_OTHER_COMMANDER"
      ? "eine Karte, die im Studio selbst ein Commander ist, bekommt keine Stufe und nimmt keinem Rang einen Platz weg. Die Einstellung „Andere Commander-Karten im Pool ranken“ ändert das."
      : "ein Standardland bekommt keine Stufe und nimmt keinem Rang einen Platz weg. Die Einstellung „Commander und Standardländer bewerten“ ändert das.";
    box.append(h("p", {}, `${item.note}: ${reasonText}`));
  } else {
    const reasonText = item.reason === "NO_COMMANDER_SIGNAL"
      ? `Zu wenig Daten für eine Stufe: ${item.note}. Allgemeine Signale (z. B. „Aufnahme überhaupt“, Playgroup oder Spellbook-Kombos) reichen allein nicht.`
      : item.reason === "ZERO_COUNT_ONLY"
      ? `Zu wenig Daten für eine Stufe: der einzige Beleg zu diesem Commander sind gezählte Nullen (${item.note}). Einstellung „Stufe bei nur gezählten Nullen“.`
      : item.reason === "NO_POSITIVE_WEIGHT"
      ? "Alle Signalgewichte stehen auf 0: ohne positives Gewicht wird kein Index berechnet."
      : item.reason === "NO_SOURCE_FOR_COMMANDER"
      ? "Für diesen Commander liegt bei keinem gewichteten Signal ein Wert im Pool vor."
      : "Zu wenig Daten für eine Stufe: das sagt nichts über die Stärke der Karte.";
    box.append(h("p", {}, `Datenlage ${StudioUI.num(100 * item.coverage, 0)} % (Gewicht der Signale mit Wert an allen gewichteten). ${item.tier === "U" ? reasonText : ""}`));
  }
  const used = state.strength.result && state.strength.result.universe_choice;
  if (used && used.kind !== "none") box.append(h("p", { class: "rule" }, `Decklisten-Universum: ${universeLine(used)}`));
  const universe = state.strength.result && state.strength.result.universe;
  if (universe && universe.subset_note) box.append(h("p", { class: "rule" }, `Decklisten-Universum ${universe.profile}: ${nf(universe.denominator)} Decks. ${universe.subset_note}.`));
  box.append(...strengthDetail(item));
  return box;
}
// One signal row of the detail table (#1365): raw value, numerator/denominator, score 0..100, effective
// weight, status and data class.
function signalRow(c) {
  const [text, kind, raw] = componentStatus(c);
  const score = c.percentile === null ? unknown("–") : `${StudioUI.num(100 * c.percentile, 1)}${c.group_fallback ? " (Rang im ganzen Pool (Gruppe zu klein))" : c.group ? ` (Gruppe ${groupLabel(c.group)}${c.group_size ? `, ${nf(c.group_size)}` : ""})` : ""}`;
  const requested = state.strength.result && state.strength.result.settings.weights[c.component];
  const weightText = requested !== undefined && Math.abs(requested - c.weight) > 1e-9 ? `${StudioUI.numFlex(c.weight, 2)} (angefragt ${StudioUI.numFlex(requested, 2)})` : `${StudioUI.numFlex(c.weight, 2)}`;
  const counted = c.denominator ? (c.numerator === null || c.numerator === undefined ? `n = ${nf(c.denominator)}` : `${nf(c.numerator)}/${nf(c.denominator)}`) : unknown("–");
  return [h("span", { title: c.signal }, c.label), c.value === null ? unknown() : StudioUI.numSig(c.value, 4), counted, score, weightText, h("span", { class: `badge ${kind}`, title: raw }, text), codeNode(c.data_class), c.note ? h("span", { class: "rule" }, c.note) : ""];
}
const SIGNAL_HEADS = ["Signal", "Rohwert", "Zähler/Nenner", "Score 0 bis 100", "Gewicht (wirksam)", "Status", "Datenklasse", "Hinweis"];
function strengthDetail(item) {
  const subjective = item.components.filter((c) => c.component === "rubric");
  const simulation = item.components.filter((c) => c.component === "simulation");
  const objective = item.components.filter((c) => c.component !== "rubric" && c.component !== "simulation");
  const out = [];
  if (item.confidence !== null && item.confidence !== undefined) {
    const level = CONFIDENCE_NAMES[item.confidence_level] || item.confidence_level;
    out.push(h("p", { id: "confidence-line" }, `Konfidenz ${level} (${StudioUI.num(item.confidence, 2)}). ${CONFIDENCE_TEXT}`));
  }
  if (item.borderline) out.push(h("p", { id: "borderline-detail" }, h("span", { class: "borderline" }, "grenzwertig"), ` Der Index ${StudioUI.num(item.index, 1)} liegt ${StudioUI.num(item.cut_distance, 1)} Punkte von der Grenze ${StudioUI.numFlex(item.borderline_cut, 1)}.`));
  const roleRanks = item.role_ranks ? Object.entries(item.role_ranks) : [];
  if (roleRanks.length) {
    out.push(h("p", { id: "role-ranks-line" }, "Rang in der Funktion (nach dem aktuellen Index): ",
      ...roleRanks.map(([role, rInfo]) => h("span", { class: "badge mr-1", title: `Rang ${nf(rInfo.rank)} von ${nf(rInfo.total)} Karten mit Stufe in der Funktion ${roleName(role)}` }, `${roleName(role)}: Rang ${nf(rInfo.rank)} von ${nf(rInfo.total)}`))));
  }
  out.push(h("h4", {}, "Objektive Signale (zählen mit Gewicht)"), table(SIGNAL_HEADS, objective.map(signalRow)));
  if (subjective.length) out.push(h("div", { class: "block-subjective", id: "block-subjective" }, h("h4", {}, subjective[0].weight > 0 ? `Subjektiv, Gewicht ${StudioUI.numFlex(subjective[0].weight, 2)}: zählt mit (Einstellung)` : "Subjektiv, Gewicht 0: zählt nicht"), h("p", {}, subjective[0].weight > 0 ? "Die Raster-Bewertung ist eine persönliche Einschätzung, kein objektives Signal. Dieses Profil gibt ihr ein Gewicht; die Empfehlung ist 0." : "Die Raster-Bewertung ist eine persönliche Einschätzung, kein objektives Signal. Sie fließt nicht in Index und Stufe ein."), table(SIGNAL_HEADS, subjective.map(signalRow))));
  if (simulation.length) out.push(h("div", { class: "block-simulation", id: "block-simulation" }, h("h4", {}, "Simulation: Gewicht 0, nicht erhoben"), h("p", {}, "Ergebnisse aus Simulationen sind keine Beobachtung aus echten Partien und fließen nie in den Index."), table(SIGNAL_HEADS, simulation.map(signalRow))));
  return out;
}
// Comparison group of a signal row; under "gleiche Funktion" the role keys get German names.
function groupLabel(group) {
  const settings = state.strength.result && state.strength.result.settings;
  if (!settings || settings.rank_group !== "function") return group;
  return group.split(" + ").map((part) => roleName(part)).join(" + ");
}
function layersBox(card) {
  const box = h("div", { class: "layer" }, h("h3", {}, "Bewertungsebenen"));
  const item = strengthItem(card), result = state.strength.result;
  if (state.view === "global" || !item || !item.layers) { box.append(h("p", {}, "Die Ebenen werden je Commander berechnet.")); return box; }
  box.append(h("p", {}, LAYER_NOTE), StudioUI.layerTable(item.layers, layerMetas()));
  const pod = item.layers.pod_scaling;
  if (pod && pod.status === "OK") box.append(h("p", { class: "rule" }, `Großpod-Wirkung ${pod.detail.label}${pod.detail.phrases.length ? `: erkannt an ${pod.detail.phrases.map((phrase) => `„${phrase}“`).join(", ")}` : ""}${pod.detail.flag_label ? `; ${pod.detail.flag_label}` : ""}. ${pod.detail.help} Aus dem Regeltext abgeleitet, keine Messung.`));
  if (result && result.layer_summary) box.append(h("p", { class: "rule" }, `${result.layer_summary.measured_note} ${result.layer_summary.pod_note}`));
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
    StudioUI.numFlex(item.card.mana_value, 2),
    item.mana_value_delta === 0 ? "gleich" : `${item.mana_value_delta > 0 ? "+" : ""}${StudioUI.numFlex(item.mana_value_delta, 2)}`,
    item.shared_roles.map(roleName).join(", "),
    item.missing_roles.map(roleName).join(", ") || "nichts",
    item.only_candidate_roles.map(roleName).join(", ") || "nichts",
    corpusCell(item.card),
    gameCell(item.card),
  ])));
  if (data.total > data.alternatives.length) box.append(h("p", {}, `${nf(data.total - data.alternatives.length)} weitere nicht gezeigt.`));
  return box;
}
function pairsTable(data) {
  return table(["Karte", "Decks zusammen", "Anteil der Decks mit dieser Karte", "Lift", "Kombo-Partner"], data.pairs.map((pair) => [
    pair.card_name,
    `${nf(pair.decks_together)}/${nf(data.decks_with_card)}`,
    pct(pair.decks_together, data.decks_with_card),
    pair.lift === null || pair.lift === undefined ? unknown("–") : StudioUI.num(pair.lift, 2),
    pair.combo_partner ? "ja (Spellbook-Kombo)" : "–",
  ]));
}
async function universeBox(card) {
  const uni = state.universe;
  const box = h("div", { class: "layer universe-box" }, h("h3", {}, SPREAD_LABEL));
  if (!uni.name) { box.append(h("p", {}, NO_UNIVERSE + ". Wähle oben ein Universum, um die gezählte Verbreitung zu sehen.")); return box; }
  const data = await api(`/api/cards/${encodeURIComponent(card.card_id)}/universe?profile=${encodeURIComponent(uni.name)}&commander=${encodeURIComponent(COMMANDER)}`);
  const item = data.cards[0], universe = data.universe;
  if (universe.subset_note) box.append(h("p", { class: "policy" }, `${universe.subset_note}. Der Nenner ${nf(universe.denominator)} ist diese Teilmenge, nicht alle Decks des Commanders.`));
  if (item.filter_card) box.append(h("p", {}, h("b", {}, `${FILTER_LABEL}: `), "das Universum verlangt diese Karte; sie steht in jedem Deck der Teilmenge und bekommt deshalb keinen Anteil und keine Stufe."));
  box.append(h("p", {}, spreadBadge(item, universe), " ", item.filter_card ? "" : item.matched ? `${nf(item.hits)} von ${nf(item.denominator)} Decks (${pct(item.hits, item.denominator)})` : "unbekannt: kein Deck des Universums nennt diese Karte unter einem bekannten Namen"));
  box.append(h("p", {}, `Grund: ${REASON_NAMES[item.reason] || item.reason}. Universum ${universe.profile} (${universe.data_class}), Stand ${universe.snapshot_id}.`));
  box.append(h("p", {}, `Schwellen (Modell ${data.model_version || "unbekannt"}): Universum mindestens ${nf(data.params.min_universe)} Decks; ${data.params.cuts.map(([tier, cut]) => `${tier} ab ${StudioUI.num(100 * cut, 0)} %`).join(", ")}; darunter ${data.params.fallback_tier}; ohne Datenbasis U. Nur Lesehilfe für die Häufigkeit, keine Stärke.`));
  if (universe.excluded_by_card_filter) box.append(h("p", { class: "rule" }, `${nf(universe.excluded_by_card_filter)} Decks fallen durch den Kartenfilter heraus und zählen nicht im Nenner.`));
  if (universe.excluded_no_date) box.append(h("p", { class: "rule" }, `${nf(universe.excluded_no_date)} Decks ohne Zeitstempel fallen durch den Datumsfilter des Universums heraus und zählen nicht im Nenner.`));
  if (item.spellings.length > 1) box.append(h("p", { class: "spellings" }, "Mehrere Schreibweisen kommen vor und werden nie addiert; gezeigt wird die größte: ", item.spellings.map((s) => `${s.name}: ${nf(s.hits)}`).join(" · ")));
  const parts = (label, map) => `${label}: ${Object.entries(map).map(([key, n]) => `${key} ${nf(n)}`).join(", ") || "–"}`;
  box.append(h("p", { class: "rule" }, parts("Nenner nach Plattform", universe.denominator_by_platform), " · ", parts("nach Bracket", universe.denominator_by_bracket)));
  box.append(h("p", { class: "rule" }, data.meaning));
  const result = h("div", {});
  const button = h("button", { type: "button", onclick: async () => {
    button.disabled = true;
    try {
      const co = await api(`/api/cards/${encodeURIComponent(card.card_id)}/cooccurrence?profile=${encodeURIComponent(uni.name)}&limit=25&commander=${encodeURIComponent(COMMANDER)}`);
      result.replaceChildren(...(co.decks_with_card === null ? [h("p", {}, "unbekannt: die Karte kommt im Universum nicht vor")] : [h("p", {}, `${co.decks_with_card_label}: ${nf(co.decks_with_card)}; ${co.denominator_label}: ${nf(co.denominator)}.`), co.subset_note ? h("p", { class: "rule" }, `${co.subset_note}. Der Nenner ${nf(co.denominator)} ist diese Teilmenge, nicht alle Decks des Commanders.${co.filter_card ? " Diese Karte ist eine Filterkarte: sie steht in allen Decks der Teilmenge." : ""}`) : null, pairsTable(co)].filter(Boolean)));
    } catch (error) { result.replaceChildren(h("p", {}, `Fehler: ${StudioUI.germanError(error)}`)); button.disabled = false; }
  } }, "Zusammen gespielt mit");
  box.append(button, result);
  return box;
}
// How the index adds up: weight * score per signal over the signals that count, divided by the sum of those
// weights. The points must add up to the shown index (checked; if not, nothing is split). Shares are taken of
// the TRUE sum of the points, never of the rounded index. `detail` says whether numbers may be shown: the
// index is at least 5, every shown row is above 0,0 points when rounded to one decimal, and the rounded
// percentages (three rows plus the rest) add up to 100 +- 1; otherwise only the order of the signals is shown.
function indexShares(item) {
  const used = item.components.filter((c) => c.weight > 0 && c.percentile !== null && c.percentile !== undefined);
  const total = used.reduce((sum, c) => sum + c.weight, 0);
  if (!used.length || !(total > 0) || !(item.index > 0)) return null;
  const rows = used.map((c) => ({ key: c.component, label: c.label, points: 100 * c.weight * c.percentile / total })).filter((row) => row.points > 0);
  const sum = rows.reduce((acc, row) => acc + row.points, 0);
  if (!rows.length || Math.abs(sum - item.index) > 0.06) return null;
  rows.sort((a, b) => b.points - a.points);
  for (const row of rows) row.percent = 100 * row.points / sum;
  const shown = rows.slice(0, 3), rest = rows.slice(3);
  const restPercent = rest.reduce((acc, row) => acc + row.percent, 0);
  const roundedSum = shown.reduce((acc, row) => acc + Math.round(row.percent), 0) + Math.round(restPercent);
  const detail = item.index >= 5 && shown.every((row) => Math.round(row.points * 10) > 0) && Math.abs(roundedSum - 100) <= 1;
  return { rows, shown, restPercent, detail };
}
// "Warum hier?": two to four plain sentences from numbers the payload already holds (n of N everywhere).
function whyBox(card) {
  const item = strengthItem(card);
  const box = h("div", { class: "layer why", id: "why-box" }, h("h3", {}, "Warum hier?"));
  if (state.view === "global") { box.append(h("p", {}, "Der Index wird je Commander berechnet. Wähle die Ansicht " + VIEW_NAMES.commander + ".")); return box; }
  if (!item) { box.append(h("p", {}, state.strength.status === "loading" ? "Die Stufe wird noch berechnet …" : "Für diese Karte liegt keine Berechnung vor.")); return box; }
  if (item.tier === "N") { box.append(h("p", {}, `${item.note}: diese Karte bekommt keine Stufe.`)); return box; }
  if (item.tier === "U") { box.append(h("p", {}, `Zu wenig Daten für eine Stufe (${REASON_SHORT[item.reason] || codeLabel(item.reason)}). Das sagt nichts über die Stärke der Karte.`)); return box; }
  const lines = [];
  const counts = deckCounts(item);
  lines.push(counts
    ? `Stufe ${item.tier} (Index ${StudioUI.num(item.index, 1)}): ${nf(counts.n)} von ${nf(counts.N)} Quelldecks für ${VIEW_NAMES.commander} enthalten die Karte (${StudioUI.pct(counts.n / counts.N, 1)}).`
    : `Stufe ${item.tier} (Index ${StudioUI.num(item.index, 1)}). Für das Decklisten-Universum liegt kein Zähler vor.`);
  const ranks = Object.entries(item.role_ranks || {}).sort((a, b) => a[1].rank - b[1].rank).slice(0, 3);
  if (ranks.length) lines.push(`In der Funktion: ${ranks.map(([role, rInfo]) => `${roleName(role)} Rang ${nf(rInfo.rank)} von ${nf(rInfo.total)}`).join("; ")} (nach dem Index im Gesamtpool).`);
  const shares = indexShares(item);
  if (shares && shares.detail) {
    const top = shares.shown.map((row) => `${SIGNAL_SHORT[row.key] || row.label} ${StudioUI.num(row.points, 1)} Punkte (${StudioUI.num(row.percent, 0)} %)`).join(", ");
    lines.push(`Beitrag zum Index (die Punkte ergeben zusammen ${StudioUI.num(item.index, 1)}): ${top}${shares.rows.length > 3 ? `, weitere Signale ${StudioUI.num(shares.restPercent, 0)} %` : ""}.`);
  } else if (shares) {
    const order = shares.shown.map((row) => SIGNAL_SHORT[row.key] || row.label).join(", ");
    lines.push(item.index < 5 ? `Index unter 5: die Aufteilung in Punkte wäre zu ungenau. Größte Beiträge, ohne Zahlen: ${order}.` : `Größte Beiträge, ohne Zahlen: ${order}.`);
  }
  lines.push(`Datenlage: ${confidenceText(item)}.${item.borderline ? ` Grenzwertig: ${StudioUI.num(item.cut_distance, 1)} Punkte von der Grenze ${StudioUI.numFlex(item.borderline_cut, 1)}.` : ""}`);
  if (item.relative_tier) lines.push(`Relativ im Commander-Pool: Stufe ${item.relative_tier} (im Vergleich zu S–F nach Perzentilen im Pool).`);
  if (item.tier_stability !== null && item.tier_stability !== undefined) {
    const alts = (item.tier_alternatives || []).length > 1
      ? ` Alternativen: ${item.tier_alternatives.map((a) => `${a.tier} (${nf(a.count)}/${nf(item.tier_stability_variants)})`).join(", ")}.`
      : "";
    lines.push(`Stabilität bei Gewichts-Variation: ${StudioUI.pct(item.tier_stability, 0)} (${nf(item.tier_stability_kept)}/${nf(item.tier_stability_variants)} Varianten)${item.unscharf ? " — unscharf (< 80 %)" : ""}.${alts}`);
  }
  box.append(h("ul", { class: "why-list" }, lines.map((line) => h("li", {}, line))), h("p", { class: "rule" }, "Die Stufe zeigt Nutzung in Decks, keine Spielstärke."));
  return box;
}
// Evidence window as a dialog: focus moves in and returns to the card that opened it, Tab stays inside,
// the table behind does not scroll (class modal-open), Escape and "Schließen" close it.
const FOCUSABLE = 'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
function closeModal() {
  const modal = $("modal");
  if (modal.hidden) return;
  modal.hidden = true;
  document.body.classList.remove("modal-open");
  let target = state.lastFocus;
  if (!target || !target.isConnected) target = state.lastFocusCard ? document.querySelector(`td.name[data-card-id="${CSS.escape(state.lastFocusCard)}"]`) : null;
  if (!target) target = $("pool-body");
  state.lastFocus = null; state.lastFocusCard = "";
  target.focus();
}
function trapModalFocus(event) {
  const modal = $("modal");
  if (modal.hidden) return;
  if (event.key === "Escape") { closeModal(); return; }
  if (event.key !== "Tab") return;
  const items = [...$("modal-box").querySelectorAll(FOCUSABLE)].filter((node) => node.offsetParent !== null);
  if (!items.length) { event.preventDefault(); $("modal-box").focus(); return; }
  const first = items[0], last = items[items.length - 1], active = document.activeElement;
  if (!$("modal-box").contains(active)) { event.preventDefault(); first.focus(); }
  else if (event.shiftKey && (active === first || active === $("modal-box"))) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && active === last) { event.preventDefault(); first.focus(); }
}
async function openCard(card) {
  const modal = $("modal"), content = $("modal-box");
  if (modal.hidden) {
    state.lastFocus = document.activeElement;
    const owner = state.lastFocus && state.lastFocus.closest ? state.lastFocus.closest("td.name") : null;
    state.lastFocusCard = owner ? owner.getAttribute("data-card-id") || "" : "";
  }
  content.replaceChildren(h("h2", { id: "modal-title" }, card.name), h("p", { class: "muted", role: "status" }, "lädt …"));
  modal.hidden = false;
  document.body.classList.add("modal-open");
  if (!content.contains(document.activeElement)) content.focus();
  try {
    const query = state.view === "global" ? "view=global" : `view=commander&commander=${encodeURIComponent(COMMANDER)}`;
    const detail = await api(`/api/cards/${encodeURIComponent(card.card_id)}/evidence?${query}`);
    const full = detail.card;
    const strengthSection = strengthBox(card);
    let face = "front";
    const picture = full.has_image ? h("img", { class: "big", loading: "lazy", referrerpolicy: "no-referrer", alt: full.name, src: cardImageUrl(full, "front") }) : h("div", { class: "muted" }, "Kein Bild in den Kartendaten.");
    if (full.has_image) picture.addEventListener("error", () => picture.replaceWith(h("div", { class: "muted" }, "Kein Bild geladen (offline).")), { once: true });
    const picBox = h("div", {}, picture, full.has_back ? h("div", { class: "actions" }, h("button", { type: "button", onclick: () => { face = face === "front" ? "back" : "front"; picture.src = cardImageUrl(full, face); } }, "Rückseite / Vorderseite")) : null);
    const hadFocus = content.contains(document.activeElement) && document.activeElement !== content;
    content.replaceChildren(
      h("div", { class: "actions" }, ...markButtons(card, () => openCard(card)), h("button", { type: "button", id: "modal-close", onclick: closeModal }, "Schließen")),
      h("h2", { id: "modal-title" }, full.name),
      h("p", { class: "muted" }, full.type_line),
      whyBox(card),
      picBox,
      h("div", { class: "policy" }, h("b", {}, `${OUTCOME_HEADING}. `), "Es gibt kein geprüftes Modell mit Partiedaten. Fehlende Beobachtung ist nie ein niedriger Tier. Favoriten, Ausschlüsse und Notizen fließen nicht ein."),
      strengthSection,
      layersBox(card),
      ...drawer(full));
    if (!hadFocus) content.focus();
    try { content.append(await universeBox(full)); } catch (error) { content.append(h("p", {}, `Verbreitung nicht ladbar: ${StudioUI.germanError(error)}`)); }
    if (state.view !== "global") content.append(await alternativesBox(full));
  } catch (error) { content.append(h("p", {}, `Fehler: ${StudioUI.germanError(error)}`)); }
}

// ---------- deck universe ----------
function rememberUniverse(name) { try { localStorage.setItem(UNIVERSE_KEY, name); } catch (error) { /* private mode: no memory */ } }
function rememberedUniverse() { try { return localStorage.getItem(UNIVERSE_KEY) || ""; } catch (error) { return ""; } }
const listText = (text) => text.split(",").map((part) => part.trim()).filter(Boolean);
function breakdown(label, map) {
  const entries = Object.entries(map || {});
  return h("span", {}, `${label}: `, entries.length ? entries.map(([key, n]) => `${key} ${nf(n)}`).join(", ") : unknown("–"));
}
function optionChecks(id, options, selected) {
  const box = h("div", { class: "checks", id });
  if (!options) { box.append(h("span", { class: "muted" }, "Werte nicht verfügbar")); return box; }
  if (!options.length) { box.append(h("span", { class: "muted" }, "keine Werte im Bestand")); return box; }
  for (const option of options) {
    box.append(h("label", {}, h("input", { type: "checkbox", value: option.value, checked: selected.includes(option.value) }), ` ${option.value} (${nf(option.decks)} Decks)`));
  }
  return box;
}
const checkedValues = (id) => [...document.querySelectorAll(`#${id} input:checked`)].map((input) => input.value);
function renderUniversePanel() {
  const uni = state.universe, panel = $("universe-panel"), summary = uni.summary;
  const spec = summary ? summary.spec : {};
  const field = (label, id, value, type = "text", limits = null) => {
    const input = h("input", { id, type, value: value ?? "" });
    if (limits) StudioUI.limitNumber(input, limits[0], limits[1], limits[2]);
    return h("label", {}, label, input);
  };
  const cardPicker = () => {
    const options = (uni.options && uni.options.cards) || [];
    const known = new Map(options.map((option) => [option.value.toLowerCase(), option.value]));
    const chosen = [...(spec.must_contain || [])];
    const chips = h("span", { class: "chips" });
    const draw = () => chips.replaceChildren(...chosen.map((name) => h("button", { type: "button", class: "chip", title: `${name} entfernen`, onclick: () => { chosen.splice(chosen.indexOf(name), 1); draw(); } }, `${name} ✕`)));
    const input = h("input", { id: "u-card", "aria-label": "Karte aus dem Bestand", list: "u-card-list", placeholder: "Karte aus dem Bestand …", autocomplete: "off" });
    const add = () => {
      const value = input.value.trim();
      if (!value) return;
      const name = known.get(value.toLowerCase());
      if (!name) { fail(new Error(options.length ? `„${value}“ steht nicht im Kartenpool dieses Commanders. Wähle eine Karte aus der Vorschlagsliste.` : "Es gibt keine Vorschläge: der Kartenpool konnte nicht geladen werden. Lade die Seite neu.")); return; }
      if (!chosen.includes(name)) { chosen.push(name); draw(); }
      input.value = "";
    };
    // Enter only adds the card as a chip (it must not save the whole universe); a typed value
    // is added when it names a card of the pool, by choosing from the suggestions or typing it.
    input.addEventListener("keydown", (event) => { if (event.key === "Enter") { event.preventDefault(); event.stopPropagation(); add(); } });
    input.addEventListener("change", () => { if (known.has(input.value.trim().toLowerCase())) add(); });
    draw();
    return {
      chosen: () => [...chosen],
      node: h("span", {}, input,
        h("datalist", { id: "u-card-list" }, ...options.map((option) => h("option", { value: option.value }, `${nf(option.decks)} Decks`))),
        h("button", { type: "button", onclick: add }, "hinzufügen"), chips),
    };
  };
  const picker = cardPicker();
  const form = h("form", { id: "universe-form", onsubmit: async (event) => {
    event.preventDefault();
    const name = $("u-name").value.trim();
    if (!name) { fail(new Error("Der Name des Universums fehlt. Schreibe ihn in das Feld „Name“.")); return; }
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
    } catch (error) { toast(`Universum nicht gespeichert: ${StudioUI.germanError(error)}`); }
  } },
    field("Name", "u-name", uni.name),
    h("span", {}, "Plattformen", optionChecks("u-platforms", uni.options && uni.options.platforms, spec.platforms || [])),
    h("span", {}, "Kohorten", optionChecks("u-cohorts", uni.options && uni.options.cohorts, spec.cohorts || [])),
    h("span", {}, "Muss enthalten (alle, im Hauptdeck)", picker.node),
    field("Datum ab", "u-from", spec.date_from, "date"),
    field("Datum bis", "u-to", spec.date_to, "date"),
    field("Mindestgröße Hauptdeck", "u-min", spec.min_main_cards, "number", [0, 100, 1]),
    field("Mindest-Universum (Nenner für Stufen)", "u-minuni", spec.min_universe, "number", [1, 100000, 1]),
    h("button", { type: "submit", class: "primary" }, "Universum speichern"),
    uni.name ? h("button", { type: "button", class: "danger", onclick: async () => {
      const name = uni.name;
      try {
        await api(`/api/universe/profiles/${encodeURIComponent(name)}`, undefined, "DELETE");
        state.universe.profiles = await api("/api/universe/profiles");
        fillUniverseSelect("");
        await selectUniverse("");
        toast(`Universum „${name}“ gelöscht`);
      } catch (error) { toast(`Universum nicht gelöscht: ${StudioUI.germanError(error)}`); }
    } }, "Universum löschen") : null);
  const facts = !uni.name || !summary
    ? h("div", { class: "facts" }, h("b", {}, NO_UNIVERSE), h("span", { class: "muted" }, uni.profiles.length ? "Wähle oben ein gespeichertes Universum." : "Noch keines gespeichert. Lege unten eines an. Ohne Filter zählt es alle importierten Quelldecks."))
    : h("div", { class: "facts" },
      h("b", {}, uni.name),
      h("span", { class: "muted" }, `Version ${summary.version}`),
      h("span", {}, `${nf(summary.denominator)} Decks (Nenner)`),
      breakdown("Plattform", summary.denominator_by_platform),
      breakdown("Bracket", summary.denominator_by_bracket),
      summary.empty ? h("span", { id: "universe-empty", class: "badge warn badge-text" }, REASON_NAMES[summary.empty_reason] || summary.empty_reason || "Universum ist leer (0 Decks)") : null,
      summary.subset_note ? h("span", { class: "badge warn badge-text" }, summary.subset_note) : null,
      summary.excluded_no_date ? h("span", { class: "muted" }, `${nf(summary.excluded_no_date)} Decks ohne Zeitstempel durch den Datumsfilter ausgeschlossen`) : null,
      summary.below_min_universe ? h("span", { class: "badge warn badge-text" }, `unter dem Mindest-Universum (${nf(summary.min_universe)} Decks): alle Karten U`) : null,
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
  if (!s.settings) return;
  // Selecting a stored profile at the top means universe_source "profile"; clearing it returns
  // that choice to the automatic one. Other sources (counted, none, auto) stay as they are.
  const source = state.universe.name ? "profile" : s.settings.universe_source === "profile" ? "auto" : s.settings.universe_source;
  if ((s.settings.universe_profile || "") === (state.universe.name || "") && source === s.settings.universe_source) return;
  s.settings = { ...s.settings, universe_profile: state.universe.name || null, universe_source: source };
  rememberStrength();
  renderStrengthPanel();
  await refreshStrength();
}
async function initUniverse() {
  const uni = state.universe;
  uni.ticket = 0;
  try { uni.profiles = await api("/api/universe/profiles"); } catch (error) { fail(error); uni.profiles = []; }
  try { uni.options = await api(`/api/universe/options?commander=${encodeURIComponent(COMMANDER)}`); } catch (error) { uni.options = null; }
  const wanted = rememberedUniverse();
  const name = uni.profiles.some((p) => p.name === wanted) ? wanted : "";
  fillUniverseSelect(name);
  $("universe-select").addEventListener("change", () => selectUniverse($("universe-select").value).catch((error) => fail(error)));
  await selectUniverse(name).catch((error) => { fail(error); renderUniversePanel(); });
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
  if (key.startsWith("weights.") || key.startsWith("layer_weights.")) return { type: "number", min: 0, max: 100, step: 0.5, scale: 1 };
  if (key === "pod_size") return { type: "number", min: 2, max: 6, step: 1, scale: 1, integer: true };
  if (key === "min_denominators.deck_universe") return { type: "readonly" };
  if (key.startsWith("min_denominators.")) return { type: "number", min: 0, max: 100000, step: 1, scale: 1 };
  if (key === "min_coverage") return { type: "number", min: 0, max: 100, step: 5, scale: 100 };
  if (key === "min_components") return { type: "number", min: 0, max: meta.components.length, step: 1, scale: 1 };
  if (key === "borderline_distance") return { type: "number", min: 0, max: 50, step: 0.5, scale: 1 };
  if (key.startsWith("tier_cuts.")) return { type: "number", min: 0, max: 100, step: 1, scale: 1 };
  if (key === "universe_source") return { type: "choice", choices: [...meta.panel.choices.universe_source, ...state.strength.counted.map((item) => ({ value: item.value, label: item.label, recommended: false }))] };
  const choices = meta.panel.choices[key];
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
    const limited = Math.min(kind.max, Math.max(kind.min, number)); // never send a value the server refuses
    const clamped = kind.integer ? Math.round(limited) : limited;
    if (clamped !== number) input.value = clamped;
    pathSet(out, key, clamped / kind.scale);
  }
  out.universe_profile = state.universe.name || null;
  return out;
}
async function refreshStrength() {
  const s = state.strength, ticket = ++s.ticket;
  if (!s.settings) return;
  const panel = $("strength-panel");
  panel.classList.add("working");
  for (const button of panel.querySelectorAll("button")) button.disabled = true;
  try {
    const result = await api("/api/strength", { commander: COMMANDER, settings: s.settings });
    if (ticket !== s.ticket) return;
    s.result = result;
    s.status = "ready";
    s.map = new Map(result.cards.map((item) => [item.card_id, item]));
    s.good = clone(s.settings);
  } catch (error) {
    if (ticket !== s.ticket) return;
    // A failed calculation keeps the last valid result and the last valid settings on screen.
    fail(error);
    if (s.good) { s.settings = clone(s.good); rememberStrength(); renderStrengthPanel(); }
    else { s.result = null; s.map = null; s.status = "error"; }
  } finally {
    if (ticket === s.ticket) { panel.classList.remove("working"); for (const button of panel.querySelectorAll("button")) button.disabled = false; }
  }
  renderStrengthSummary();
  syncRankGroupToggle();
  render();
}
// Which deck lists and which denominator the index used, and whether the choice was automatic.
function universeLine(choice) {
  const verb = choice.automatic ? "automatisch gewählt" : "gewählt";
  if (choice.kind === "none") return `kein Decklisten-Universum (${choice.reason})`;
  const what = choice.kind === "counted" ? `Verbreitung (gezählt): ${choice.short_label}` : choice.label;
  return groupDigits(`${what} · Nenner ${nf(choice.denominator)} Decks · ${verb}${choice.reason ? ` (${choice.reason.replace(/^automatisch gewählt: /, "")})` : ""}`);
}
// Tier header (#1365): S to D, U split into counted zeros and missing data, N; spells and lands counted
// apart; the counted corpus (universe and denominator) always in view.
function corpusLine(result) {
  const corpus = result.corpus;
  if (!corpus) return "Korpus: keine Angabe";
  if (!corpus.available) return `Kein gezählter Korpus: ${nf(corpus.decks)} lokale Decklisten, Minimum ${nf(corpus.min_universe)}. Die EDHREC-Gewichte gelten als Rückfall.`;
  const cohorts = corpus.cohorts.map((item) => `${item.label} ${nf(item.denominator)}`).join(" · ");
  return `Korpus-Universum: ${nf(corpus.decks)} gezählte Decklisten (Nenner)${cohorts ? ` · ${cohorts}` : ""}`;
}
function distributionTable(result) {
  const kinds = result.tier_counts_by_kind;
  const cols = STRENGTH_TIERS;
  const row = (label, counts) => h("tr", {}, h("th", { scope: "row" }, label), cols.map((tier) => h("td", { class: "num" }, nf(counts[tier] || 0))), h("td", { class: "num" }, nf(cols.reduce((sum, tier) => sum + (counts[tier] || 0), 0))));
  const note = result.settings.separate_lands ? "Länder und Zauber werden getrennt gerankt." : "Länder und Zauber werden gemeinsam gerankt (Einstellung); die Zählung ist trotzdem getrennt.";
  return h("div", { class: "dist-wrap" },
    h("table", { class: "dist", id: "tier-distribution", title: note },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Karten"), cols.map((tier) => h("th", { scope: "col", class: "num", title: TIER_FILTER_NAMES[tier] || `Stufe ${tier}` }, tier)), h("th", { scope: "col", class: "num" }, "Σ"))),
      h("tbody", {}, row("Zauber", kinds.spells), row("Länder", kinds.lands), row("Alle", result.tier_counts))),
    h("div", { class: "rule" }, note));
}
function tierHeader(result) {
  const counts = result.tier_counts, u = result.unknown_breakdown;
  const unknownText = `unbekannt (U) ${nf(counts.U)}`;
  const zeroText = u.denominator === null ? "nur gezählte Nullen" : `gezählt 0 von ${nf(u.denominator)} Decks`;
  const breakdown = `${zeroText}: ${nf(u.zero_count)} Karten · fehlende Daten: ${nf(u.missing_data)} Karten`;
  const codes = Object.entries(u.by_reason).map(([code, n]) => `${REASON_SHORT[code] || codeLabel(code)} ${nf(n)}`).join(", ");
  return [h("div", { class: "tier-block" },
    h("div", { class: "tier-head", id: "tier-head" },
      ...["S", "A", "B", "C", "D"].map((tier) => tierBadge(tier, nf(counts[tier]), `Stufe ${tier}: ${nf(counts[tier])} Karten`)),
      h("span", { class: "u-split", id: "u-split" }, neutral(unknownText, `Keine Stufe, weil Belege fehlen: das sagt nichts über die Stärke. ${codes}`), h("span", { class: "rule" }, breakdown)),
      neutral(`N ${nf(counts.N || 0)}`, "nicht bewertet: Commander und Standardländer, wenn sie nicht bewertet werden")),
    distributionTable(result),
    h("div", { class: "rule", id: "corpus-line" }, corpusLine(result)),
    h("div", { class: "rule", id: "borderline-line" }, `grenzwertig (näher als ${StudioUI.numFlex(result.settings.borderline_distance, 3)} Punkte an einer Stufengrenze): ${nf(result.borderline_count)} Karten${result.stability ? ` · unscharf (< 80 % der Varianten): ${nf(result.stability.unscharf_count)}/${nf(result.stability.evaluated_cards)}` : ""}. ${CONFIDENCE_TEXT}`))];
}
function snapshotBadge(result) {
  const snap = result.snapshot;
  if (!snap) return null;
  if (snap.status === "STALE") {
    return h("span", { id: "snapshot-status", class: "badge warn badge-text", title: `Snapshot-Epoche ${(snap.snapshot_epoch || "").slice(0, 12)} ungleich aktueller Epoche ${(snap.current_epoch || "").slice(0, 12)}` }, "Snapshot veraltet, Neuberechnung läuft");
  }
  if (snap.status === "HIT") {
    const stamp = snap.created_at ? `${snap.created_at.slice(0, 19).replace("T", " ")} UTC` : "–";
    const epochShort = snap.data_epoch ? snap.data_epoch.slice(0, 12) : "–";
    return h("span", { id: "snapshot-status", class: "badge good badge-text", title: `Snapshot ${snap.profile_name || ""} (${snap.spec_version || ""})` }, `Snapshot: Stand ${stamp} · Epoche ${epochShort}`);
  }
  if (snap.status === "MISSING") {
    const epochShort = snap.current_epoch ? snap.current_epoch.slice(0, 12) : "–";
    return h("span", { id: "snapshot-status", class: "badge dim badge-text" }, `Live berechnet (kein Snapshot · Epoche ${epochShort})`);
  }
  return null;
}
function renderStrengthSummary() {
  const s = state.strength, box = $("strength-summary");
  renderTierBar();
  if (!box) return;
  if (!s.result) { box.replaceChildren(unknown(s.status === "loading" ? "wird berechnet …" : "noch nicht berechnet")); updateMethodHint(); return; }
  const result = s.result, counts = result.tier_counts, universe = result.universe;
  const choice = result.universe_choice;
  const universeWeight = result.settings.weights.deck_universe;
  const universeText = `Index berechnet mit: ${choice ? universeLine(choice) : "kein Decklisten-Universum"}${universe && universe.subset_note ? `; ${universe.subset_note}` : ""}${choice && choice.kind !== "none" ? (universeWeight > 0 ? `; zählt in die Stufe mit Gewicht ${StudioUI.numFlex(universeWeight, 3)}` : "; Gewicht 0: zählt nicht in die Stufe") : ""}`;
  // Sources that can exist for these settings: no simulation (not collected), no bracket source without a
  // bracket, no deck universe without one.
  const possible = s.meta.components.filter((c) => c.key !== "simulation" && !(c.key === "bracket_inclusion" && result.settings.bracket === "none") && !(c.key === "deck_universe" && !(result.universe_choice && result.universe_choice.kind !== "none")) && !(c.key === "rubric" && !result.collected.includes("rubric"))).length;
  const snapNode = snapshotBadge(result);
  const snapStale = result.snapshot && result.snapshot.status === "STALE";
  const notices = (result.notices || [])
    .filter((text) => !(snapStale && text === "Snapshot veraltet, Neuberechnung läuft"))
    .map((text) => h("div", { class: "badge warn badge-text" }, text));
  const ambiguous = result.ambiguous_names || [];
  const shown = ambiguous.slice(0, 10).map((item) => `${item.name} (${item.candidates.join(" / ")})`).join("; ");
  const families = Array.isArray(result.weight_families) ? result.weight_families.filter((f) => f.share > 0) : [];
  box.replaceChildren(
    ...tierHeader(result),
    snapNode,
    h("span", { class: "muted" }, `von ${nf(result.cards.length)} Karten · ${universeText} · Quellen vorhanden: ${nf(result.collected.length)}/${nf(possible)}`),
    ...(families.length ? [h("div", { class: "rule", id: "weight-families-line" }, `Gewichtungs-Familien: ${families.map((f) => `${f.label} ${StudioUI.pct(f.share, 0)}`).join(" · ")}`)] : []),
    ...notices,
    ...(result.layer_summary ? result.layer_summary.layers.filter((item) => item.source_discrepancies > 0).map((item) => h("div", { class: "rule" }, `${item.label}: bei ${nf(item.source_discrepancies)} Karten nennt die Quelle einen anderen Prozentwert als Zähler/Nenner; die Zelle zeigt Zähler/Nenner, der genannte Wert steht im Tooltip.`)) : []),
    ...(result.layer_summary ? [h("div", { class: "rule", title: `${result.layer_summary.measured_note} ${result.layer_summary.pod_note}` }, `Ebenen (eigene Spalten): ${result.layer_summary.layers.map((item) => `${item.label} ${nf(item.with_value)}/${nf(item.pool_cards)} (${LAYER_KIND_SHORT[item.kind] || item.kind})`).join(" · ")}${result.layer_summary.weighted.length ? `. Im Index mit Gewicht: ${result.layer_summary.weighted.map((key) => (layerMetas().find((meta) => meta.key === key) || { label: key }).label).join(", ")}` : ". Keine Ebene hat ein Gewicht: die Stufen entsprechen dem Index ohne Ebenen"}`)] : []),
    ...(ambiguous.length ? [h("div", { class: "rule" }, `Mehrdeutige Namen in den Quelldaten, keiner Karte zugeordnet: ${shown}${ambiguous.length > 10 ? ` und ${nf(ambiguous.length - 10)} weitere` : ""}`)] : []));
  updateMethodHint();
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
  s.status = "ready";
  s.map = new Map(result.cards.map((item) => [item.card_id, item]));
  rememberStrength();
  if (wanted !== (state.universe.name || "")) {
    state.universe.profiles = await api("/api/universe/profiles");
    fillUniverseSelect(wanted);
    await selectUniverse(wanted).catch((error) => toast(`Universum „${wanted}“ konnte nicht gewählt werden: ${StudioUI.germanError(error)}`));
  }
  renderStrengthPanel();
  render();
}
function strengthField(key) {
  const s = state.strength, panel = s.meta.panel, kind = fieldKind(key), id = fieldId(key);
  const current = pathGet(s.settings, key), drafted = s.draft.fields[key];
  let input;
  if (kind.type === "readonly") input = h("input", { id, type: "text", readOnly: true, value: `${nf(universeMinimum())} Decks` });
  else if (kind.type === "choice") {
    input = h("select", { id }, kind.choices.map((item) => h("option", { value: String(item.value) }, groupDigits(item.label))));
    input.value = drafted !== undefined ? drafted : String(current);
  } else {
    input = h("input", { id, type: "number", value: drafted !== undefined ? drafted : current === undefined ? "" : Math.round(current * kind.scale * 1000) / 1000, placeholder: StudioUI.numFlex(pathGet(s.meta.recommended, key) * kind.scale, 3) });
    StudioUI.limitNumber(input, kind.min, kind.max, kind.step);
  }
  if (kind.type !== "readonly") input.addEventListener("input", () => { s.draft.fields[key] = input.value; });
  input.addEventListener("input", updateDeviations);
  input.addEventListener("change", updateDeviations);
  return h("div", { class: "setting", title: plainCodes(panel.help[key]) }, h("label", { for: id }, panel.labels[key]), input, h("span", { class: "help" }, plainCodes(panel.help[key])));
}
// Settings that differ from the recommendation, read from the form without changing it.
function deviationCount() {
  const s = state.strength;
  let count = 0;
  for (const key of settingKeys()) {
    const kind = fieldKind(key), input = $(fieldId(key));
    if (kind.type === "readonly" || !input) continue;
    const recommended = pathGet(s.meta.recommended, key);
    if (kind.type === "choice") { if (input.value !== String(recommended)) count += 1; continue; }
    if (input.value.trim() === "") continue; // empty means "recommended"
    if (Math.abs(Number(input.value) / kind.scale - recommended) > 1e-9) count += 1;
  }
  return count;
}
function updateDeviations() {
  const box = $("deviations");
  if (!box) return;
  const n = deviationCount();
  box.textContent = n === 0 ? "Alle Einstellungen entsprechen der Empfehlung." : n === 1 ? "1 Einstellung weicht von der Empfehlung ab." : `${nf(n)} Einstellungen weichen von der Empfehlung ab.`;
  box.classList.toggle("changed", n > 0);
}
const SETTING_GROUPS = [
  ["Gewichte", (key) => key.startsWith("weights.")],
  ["Zusätzliche Ebenen", (key) => key.startsWith("layer_weights.") || key === "pod_size"],
  ["Decklisten-Universum", (key) => key === "universe_source" || key === "edhrec_with_corpus"],
  ["Vergleich", (key) => key === "bracket" || key === "combo_source" || key === "rank_group" || key === "separate_lands" || key === "share_measure" || key === "share_scale" || key === "rank_commander_and_basics" || key === "rank_other_commanders" || key.startsWith("missing_value.")],
  ["Mindestdaten", (key) => key.startsWith("min_denominators.") || key === "min_coverage" || key === "min_components" || key === "require_commander_signal" || key === "zero_count_tier"],
  ["Tier-Grenzen", (key) => key.startsWith("tier_cuts.") || key === "borderline_distance"],
];
const OPEN_GROUPS_KEY = "studio.strength.open-groups";
const SETTINGS_OPEN_KEY = "studio.strength.settings-open";
// Tier chips: the filter and the counters in one place (S 39 ... N 5), apart from the column menu.
// Disabled with a placeholder until the strength result is there, so the bar never jumps.
function functionTotal(role) {
  const result = state.strength.result;
  const found = result ? result.cards.find((item) => item.role_ranks && item.role_ranks[role]) : null;
  return found ? found.role_ranks[role].total : null;
}
function compareHint() {
  const s = state.strength, out = [];
  if (state.funcMode && state.view !== "global") {
    const role = $("role-filter") ? $("role-filter").value : "";
    const total = role ? functionTotal(role) : null;
    const group = role ? `Gruppe: Funktion ${roleName(role)}${total ? ` (${nf(total)} Karten mit Stufe)` : ""}.` : "Gruppe: jede Karte in ihren Rollen (Spalte „Rang in Funktion“); Karten ohne Rolle oder ohne Stufe haben keinen Rang.";
    out.push(h("span", { id: "compare-hint", class: "hint", role: "status" }, `Vergleich in der gleichen Funktion: Rang k von n, keine neue Stufe; die Stufe bleibt die Stufe im Gesamtpool. ${group}`));
  }
  if (s.settings && s.settings.rank_group === "function") {
    out.push(h("span", { id: "compare-warning", class: "hint warn-hint" }, "In den Einstellungen ist „Vergleichsgruppe: gleiche Funktion“ gewählt: Index und Stufen sind je Funktion neu berechnet und fallen höher aus; sie sind nicht mit der Stufe im Gesamtpool vergleichbar. ",
      h("button", { type: "button", class: "small", onclick: () => setQuickRankGroup("pool").catch((error) => fail(error)) }, "Auf Gesamtpool zurück")));
  }
  return out;
}
function renderTierBar() {
  const s = state.strength, bar = $("tier-bar");
  if (!bar) return;
  const label = h("span", { class: "toggle-label" }, "Stufe:");
  if (!s.result) {
    bar.replaceChildren(label, h("span", { class: "muted", role: "status" }, s.status === "error" ? "Stufen nicht verfügbar" : "Stufen werden berechnet …"));
    return;
  }
  const counts = s.result.tier_counts;
  const apply = () => { state.shown = 150; renderTierBar(); render(false); };
  const chips = STRENGTH_TIERS.map((tier) => h("button", { type: "button", class: "chip tier-chip" + (s.tiers.has(tier) ? " on" : ""), "aria-pressed": String(s.tiers.has(tier)), title: `${TIER_FILTER_NAMES[tier] || `Stufe ${tier}`}: ${nf(counts[tier] || 0)} Karten im Pool. Klick filtert (Mehrfachauswahl).`, "data-tier": tier,
    onclick: () => { if (s.tiers.has(tier)) s.tiers.delete(tier); else s.tiers.add(tier); apply(); } },
  h("span", { class: `tier-badge t-${tier}` }, h("span", { class: "level letter" }, tier), nf(counts[tier] || 0))));
  const reset = s.tiers.size ? h("button", { type: "button", class: "small", onclick: () => { s.tiers.clear(); apply(); } }, "Filter aufheben") : null;
  bar.replaceChildren(label, ...chips, ...(reset ? [reset] : []), ...compareHint());
}
// The number of notes in the closed method panel, shown in its summary line.
function updateMethodHint() {
  const hint = $("method-hint");
  if (!hint) return;
  const n = document.querySelectorAll("#oracle-banner, #strength-summary .badge-text.warn, #universe-panel .facts .badge-text.warn, #data-state details.datastate[open]").length;
  hint.textContent = n ? `· ${nf(n)} ${n === 1 ? "Hinweis" : "Hinweise"}` : "";
}
function fillSortOptions() {
  const meta = state.strength.meta;
  const previous = $("sort").value;
  const percentile = meta ? meta.components.map((c) => [PERCENTILE_SORT + c.key, `Teil-Score 0 bis 100: ${c.label}`]) : [];
  const rating = meta ? meta.layers.map((c) => [LAYER_SORT + c.key, `Ebene: ${c.label} (Perzentil, ${LAYER_KIND_SHORT[c.kind] || c.kind})`]) : [];
  $("sort").replaceChildren(...[...SORTS, ...percentile, ...rating].map(([key, label]) => h("option", { value: key }, label)));
  $("sort").value = [...$("sort").options].some((option) => option.value === previous) ? previous : state.sortKey;
}
function renderStrengthPanel() {
  const s = state.strength, panel = $("strength-panel");
  if (!s.meta || !s.settings) return;
  const run = (work) => work().catch((error) => fail(error));
  const presetSelect = h("select", { id: "s-preset", title: "Voreinstellung laden" }, h("option", { value: "" }, "Voreinstellung …"), s.meta.presets.map((p) => h("option", { value: p.name }, p.name)));
  presetSelect.addEventListener("change", () => {
    const p = s.meta.presets.find((x) => x.name === presetSelect.value);
    if (!p) return;
    // A preset replaces every setting and recalculates at once: say so.
    s.selectedProfile = "";
    s.draft.name = "";
    s.note = `Voreinstellung „${p.name}“ geladen und berechnet`;
    toast("Voreinstellung geladen und berechnet", "ok");
    run(() => applyStrength(p.settings));
  });
  const profileLabel = (p) => `${p.name}${p.valid ? (p.universe_missing ? " (Universum fehlt)" : "") : " (ungültig)"}`;
  // The chosen saved setting stays chosen (and its name stays in the name field) when the panel is redrawn.
  const saved = h("select", { id: "s-saved" }, h("option", { value: "" }, "gespeicherte Einstellung …"), s.profiles.map((p) => h("option", { value: p.name, selected: p.name === s.selectedProfile }, profileLabel(p))));
  saved.value = s.profiles.some((p) => p.name === s.selectedProfile) ? s.selectedProfile : "";
  if (!saved.value) s.selectedProfile = "";
  saved.addEventListener("change", () => {
    const p = s.profiles.find((x) => x.name === saved.value);
    s.selectedProfile = p ? p.name : "";
    if (!p) return;
    if (!p.valid) { fail(new Error(`Die Einstellung „${p.name}“ ist nicht mehr gültig: ${p.reason}`)); return; }
    if (p.universe_missing) toast(`Das Universum „${p.universe_missing}“ dieser Einstellung gibt es nicht mehr: sie läuft mit „kein Universum“.`);
    s.draft.name = p.name;
    s.note = `Gespeicherte Einstellung „${p.name}“ geladen und berechnet`;
    loadSavedProfile(p).catch((error) => toast(StudioUI.germanError(error)));
  });
  const nameInput = h("input", { id: "s-name", type: "text", maxLength: 80, placeholder: "z. B. Mein Index", value: s.draft.name });
  nameInput.addEventListener("input", (event) => { s.draft.name = event.target.value; });
  const apply = h("button", { type: "button", class: "primary", id: "s-apply", onclick: () => run(() => { s.note = ""; return applyStrength(readStrengthSettings()); }) }, "Berechnen");
  const reset = h("button", { type: "button", id: "s-reset", title: "Alle Einstellungen auf die empfohlenen Werte setzen", onclick: () => run(() => { s.selectedProfile = ""; s.draft.name = ""; s.note = ""; return applyStrength(s.meta.recommended); }) }, "Empfohlene Werte");
  const save = h("button", { type: "button", id: "s-save", onclick: () => run(async () => {
    const name = nameInput.value.trim();
    if (!name) { fail(new Error("Der Name der Einstellung fehlt. Schreibe ihn in das Feld „Name“.")); return; }
    const settings = readStrengthSettings();
    await api(`/api/strength/profiles/${encodeURIComponent(name)}`, { settings }, "PUT");
    s.profiles = await api("/api/strength/profiles");
    s.selectedProfile = name; s.draft.name = name;
    await applyStrength(settings);
    toast(`Einstellung „${name}“ gespeichert`, "ok");
  }) }, "Speichern");
  const remove = h("button", { type: "button", class: "danger", id: "s-delete", onclick: () => run(async () => {
    const name = s.selectedProfile || $("s-saved").value;
    if (!name) { fail(new Error("Wähle zuerst eine gespeicherte Einstellung aus der Liste „Laden“.")); return; }
    await api(`/api/strength/profiles/${encodeURIComponent(name)}`, undefined, "DELETE");
    s.profiles = await api("/api/strength/profiles");
    s.selectedProfile = ""; s.draft.name = ""; s.note = "";
    renderStrengthPanel();
    toast(`Einstellung „${name}“ gelöscht`, "ok");
  }) }, "Löschen");
  let openGroups = [];
  try { openGroups = JSON.parse(StudioUI.recall(OPEN_GROUPS_KEY, "[]")) || []; } catch (error) { openGroups = []; }
  const keys = settingKeys();
  const groups = SETTING_GROUPS.map(([title, test]) => {
    const members = keys.filter(test);
    if (!members.length) return null;
    const box = h("details", { class: "sgroup", open: openGroups.includes(title) || openGroups.length === 0 }, h("summary", {}, title), h("div", { class: "settings" }, members.map(strengthField)));
    box.addEventListener("toggle", () => {
      const now = new Set(openGroups.length ? openGroups : SETTING_GROUPS.map((g) => g[0]));
      if (box.open) now.add(title); else now.delete(title);
      openGroups = [...now];
      StudioUI.remember(OPEN_GROUPS_KEY, JSON.stringify(openGroups));
    });
    return box;
  }).filter(Boolean);
  panel.replaceChildren(
    h("div", { class: "strength-head" }, h("b", {}, INDEX_HEADING), h("div", { id: "strength-summary", class: "facts" })),
    h("details", { id: "strength-settings", open: StudioUI.recall(SETTINGS_OPEN_KEY, "") === "1", ontoggle: (event) => StudioUI.remember(SETTINGS_OPEN_KEY, event.currentTarget.open ? "1" : "") },
      h("summary", {}, "Einstellungen: was wie stark gezählt werden soll (mit empfohlenen Werten)"),
      h("div", { class: "muted" }, STRENGTH_NOTE),
      h("div", { class: "strength-form" },
        h("label", {}, "Voreinstellung", presetSelect),
        h("label", {}, "Universum (oben gewählt)", h("input", { type: "text", readOnly: true, value: state.universe.name || "keines" })),
        apply, reset),
      h("div", { id: "preset-note", class: "note", role: "status" }, s.note),
      h("div", { class: "deviation-line" }, h("span", { id: "deviations" }), h("button", { type: "button", class: "small", id: "s-reset2", onclick: () => run(() => { s.selectedProfile = ""; s.draft.name = ""; s.note = ""; return applyStrength(s.meta.recommended); }) }, "Auf Empfehlung zurücksetzen")),
      groups,
      h("div", { class: "strength-form" },
        h("label", {}, "Name", nameInput), save,
        h("label", {}, "Laden", saved), remove)));
  updateDeviations();
  renderStrengthSummary();
  syncRankGroupToggle();
}
async function initStrength() {
  const s = state.strength;
  s.status = "loading";
  try {
    [s.meta, s.profiles] = await Promise.all([api("/api/strength/presets"), api("/api/strength/profiles")]);
    s.counted = await api(`/api/universe/counted?commander=${encodeURIComponent(COMMANDER)}`).catch(() => []);
  } catch (error) { toast(`Stärke-Index nicht verfügbar: ${StudioUI.germanError(error)}`); s.status = "error"; renderTierBar(); syncRankGroupToggle(); render(); return; }
  fillSortOptions();
  state.layerCols = recallLayerColumns(s.meta.layers);
  renderLayerControls();
  const wanted = rememberedStrength();
  // An earlier version of the quick toggle stored "function" as the setting and so inflated the tiers: that
  // choice becomes the view mode now and the setting returns to the whole pool.
  if (wanted && typeof wanted === "object" && wanted.rank_group === "function") {
    wanted.rank_group = "pool";
    state.funcMode = true;
    StudioUI.remember(COMPARE_KEY, "function");
    try { localStorage.setItem(STRENGTH_KEY, JSON.stringify(wanted)); } catch (error) { /* private mode: no memory */ }
    toast("Die gespeicherte Einstellung „Vergleichsgruppe: gleiche Funktion“ (auch eine bewusste Wahl im Einstellungs-Panel) wurde in die Anzeige „Gleiche Funktion“ umgewandelt: Rang je Funktion. Die Einstellung steht jetzt auf Gesamtpool, die Stufe ist die Stufe im Gesamtpool.");
  }
  const base = wanted && typeof wanted === "object" ? wanted : s.meta.recommended;
  s.settings = { ...withDefaults(base), universe_profile: state.universe.name || null };
  renderStrengthPanel();
  try { await refreshStrength(); } catch (error) { fail(error); }
  if (!s.result && wanted) { // remembered settings no longer valid: start from the recommended values
    s.settings = { ...withDefaults(s.meta.recommended), universe_profile: state.universe.name || null };
    renderStrengthPanel();
    await refreshStrength();
  }
}

// ---------- data state banner ----------
// Only a real finding shows a banner (#1365): a source layer the index needs is empty, or deck-list rows
// have no real oracle_id (they cannot be matched to a card). Otherwise there is none.
async function dataBanner() {
  const host = $("data-state");
  let report = null;
  try { report = await api("/api/data-report"); } catch (error) { report = null; }
  const rows = report && report.corpus ? report.corpus.card_rows_without_oracle_id : null;
  await StudioUI.dataState(host, COMMANDER, { only: ["inventory", "scryfall", "decklists"] });
  if (rows && rows.count > 0) {
    host.append(h("div", { class: "badge warn badge-text", id: "oracle-banner", role: "status" }, `Datenbefund: ${nf(rows.count)} von ${nf(rows.of)} Deckkarten-Zeilen haben keine echte Oracle-Kennung und werden keiner Karte zugeordnet (fehlende Beobachtung, keine Schwäche).`));
  }
  updateMethodHint();
}

// ---------- loading ----------
async function loadEvidence() {
  const apiView = state.view === "global" ? "global" : "commander";
  const query = apiView === "global" ? "view=global" : `view=commander&commander=${encodeURIComponent(COMMANDER)}`;
  const ticket = ++state.ticket;
  const data = await api(`/api/evidence?${query}`);
  if (ticket !== state.ticket) return; // a newer view was chosen meanwhile
  state.data = data;
  if (apiView === "commander") {
    state.pool.clear();
    for (const card of data.cards) state.pool.set(card.card_id, card);
  }
  const groups = [...new Set(state.data.cards.map((card) => card.group))].sort((a, b) => typeLabel(a).localeCompare(typeLabel(b), "de"));
  const roles = [...new Set(state.data.cards.flatMap(cardRoles))].sort((a, b) => roleName(a).localeCompare(roleName(b)));
  $("type-filter").replaceChildren(h("option", { value: "" }, "alle Typen"), ...groups.map((group) => h("option", { value: group }, typeLabel(group))));
  $("role-filter").replaceChildren(h("option", { value: "" }, "alle Rollen"), ...roles.map((role) => h("option", { value: role }, roleName(role))));
  renderNotice();
  render();
}
async function loadDeck() {
  const deck = state.decks.find((entry) => entry.deck_id === $("deck-select").value);
  const branch = deck && deck.branches.find((entry) => entry.branch === $("branch-select").value);
  state.deckCards = new Map();
  if (branch) {
    // The working list (draft) wins over the saved state: it is what the builder shows.
    const [revision, draft] = await Promise.all([
      api(`/api/revisions/${encodeURIComponent(branch.revision_id)}`),
      api(`/api/decks/${encodeURIComponent(deck.deck_id)}/branches/${encodeURIComponent(branch.branch)}/draft`),
    ]);
    for (const entry of (draft.draft ? draft.draft.cards : revision.cards)) if (entry.zone !== "commander") state.deckCards.set(entry.card_id, entry.quantity);
    state.deckRoles = revision.roles || {};
    StudioUI.remember(`studio.builder.${COMMANDER}.deck`, deck.deck_id);
    StudioUI.remember(`studio.builder.${COMMANDER}.branch`, branch.branch);
  }
  if (state.data) renderNotice();
  render();
}
// The target deck of "ins Deck": the deck and variant the builder had open, else the first.
async function initDecks() {
  try {
    state.decks = (await api("/api/decks")).filter((deck) => (deck.commanders || []).includes(COMMANDER));
    const wantedDeck = StudioUI.recall(`studio.builder.${COMMANDER}.deck`, "");
    $("deck-select").replaceChildren(...state.decks.map((deck) => h("option", { value: deck.deck_id, selected: deck.deck_id === wantedDeck }, deck.name)));
    fillBranches();
    const wantedBranch = StudioUI.recall(`studio.builder.${COMMANDER}.branch`, "");
    if ([...$("branch-select").options].some((option) => option.value === wantedBranch)) $("branch-select").value = wantedBranch;
    $("deck-pick").hidden = !state.decks.length;
    $("deck-pick").classList.remove("pending");
    await loadDeck();
  } catch (error) { $("deck-pick").hidden = true; fail(error); }
}
// ---------- marks and deck from the table (marks never change a rating) ----------
async function toggleFavorite(card) {
  // Only the favorite is sent: the note and the exclusion stay as the server holds them,
  // also for a card this page has no mark of (a card outside the commander's pool).
  const mark = state.marks.get(card.card_id) || {};
  try {
    const next = await api(`/api/cards/${encodeURIComponent(card.card_id)}/favorite`, { favorite: !mark.favorite }, "PUT");
    state.marks.set(card.card_id, { favorite: next.favorite, excluded: next.excluded, note: next.note });
    toast(next.favorite ? `${card.name} ist jetzt Favorit. Die Bewertung ändert sich dadurch nicht.` : `${card.name} ist kein Favorit mehr.`);
    render();
  } catch (error) { fail(error); }
}
let deckQueue = Promise.resolve(); // one deck change after the other, in click order
function changeDeck(card, delta) {
  deckQueue = deckQueue.then(() => changeDeckNow(card, delta));
  return deckQueue;
}
// "+ Deck" only for a card of this commander's pool: the target decks belong to this commander.
const inPool = (card) => state.pool.has(card.card_id);
async function changeDeckNow(card, delta) {
  const deckId = $("deck-select").value, branch = $("branch-select").value;
  if (!deckId || !branch) { toast("Für diesen Commander gibt es noch kein Deck. Öffne einmal den Deckbau, dort wird es angelegt."); return; }
  try {
    const result = await api(`/api/decks/${encodeURIComponent(deckId)}/branches/${encodeURIComponent(branch)}/draft/card`, { card_id: card.card_id, delta });
    if (result.quantity) state.deckCards.set(card.card_id, result.quantity); else state.deckCards.delete(card.card_id);
    toast(delta > 0 ? `${card.name} liegt im Deck (${nf(result.deck_cards)} von 100 Karten). Gesichert als Entwurf, im Deckbau speicherst du den Stand.` : `${card.name} ist aus dem Deck genommen (${nf(result.deck_cards)} von 100 Karten).`);
    if (state.data) renderNotice();
    render();
  } catch (error) { fail(error); }
}
function markButtons(card, after) {
  const mark = state.marks.get(card.card_id) || {};
  const count = state.deckCards.get(card.card_id) || 0;
  const then = (work) => async () => { await work(); if (after) after(); };
  return [
    h("button", { type: "button", class: "small fav" + (mark.favorite ? " on" : ""), title: mark.favorite ? "Favorit entfernen" : "Als Favorit markieren (ändert keine Bewertung)", "aria-label": `${card.name} Favorit`, "aria-pressed": mark.favorite ? "true" : "false", onclick: then(() => toggleFavorite(card)) }, mark.favorite ? "★" : "☆"),
    count
      ? h("button", { type: "button", class: "small indeck", title: "Im Ziel-Deck. Klick nimmt die Karte wieder heraus.", "aria-label": `${card.name} aus dem Deck`, onclick: then(() => changeDeck(card, -1)) }, count > 1 ? `✓ ${nf(count)}× im Deck` : "✓ im Deck")
      : h("button", { type: "button", class: "small", title: !state.decks.length ? "Noch kein Deck für diesen Commander" : !inPool(card) ? "Diese Karte gehört nicht zum Pool dieses Commanders (Farbidentität, Legalität oder nicht in der Sammlung)" : "In das Ziel-Deck legen (oben wählbar)", "aria-label": `${card.name} ins Deck`, disabled: !(card.available > 0) || !state.decks.length || !inPool(card), onclick: then(() => changeDeck(card, 1)) }, "+ Deck"),
  ];
}
function fillBranches() {
  const deck = state.decks.find((entry) => entry.deck_id === $("deck-select").value);
  $("branch-select").replaceChildren(...(deck ? deck.branches : []).map((entry) => h("option", { value: entry.branch }, entry.branch)));
}
// ---------- quick comparison toggle, role audit (#1413) & TopDeck Mit/Ohne (#1412) ----------
// "Gleiche Funktion" is a view mode: the index and the tier stay those of the whole pool (rank_group "pool"),
// the table adds the rank k of n per function. Nothing is recalculated, so no tier is inflated.
function syncRankGroupToggle() {
  const box = $("rank-group-toggle");
  if (!box) return;
  const ready = state.strength.status === "ready" && Boolean(state.strength.settings) && state.view !== "global";
  for (const btn of box.querySelectorAll("button[data-rank-group]")) {
    const active = (btn.getAttribute("data-rank-group") === "function") === state.funcMode;
    btn.classList.toggle("on", active);
    btn.setAttribute("aria-pressed", active ? "true" : "false");
    btn.disabled = !ready;
  }
}
async function setQuickRankGroup(group) {
  const s = state.strength;
  if (!s.settings || state.view === "global" || s.status !== "ready") return;
  const funcMode = group === "function";
  StudioUI.remember(COMPARE_KEY, funcMode ? "function" : "pool");
  const stale = s.settings.rank_group === "function"; // set in the settings (or remembered): the tiers themselves were recalculated
  if (stale) {
    s.settings = { ...s.settings, rank_group: "pool" };
    s.draft.fields.rank_group = "pool";
    rememberStrength();
  }
  state.funcMode = funcMode;
  syncRankGroupToggle();
  renderTierBar();
  if (stale) { renderStrengthPanel(); await refreshStrength(); return; }
  render(false);
}
function renderRoleAuditPanel() {
  const panel = $("role-audit-panel");
  if (!panel) return;
  const data = state.roleAudit;
  if (!data) { panel.replaceChildren(); return; }
  const rows = Array.isArray(data.roles) ? data.roles : [];
  const scoped = data.pool_total !== undefined && data.pool_total !== null;
  let taggerTotal = 0, oracleTotal = 0, bothTotal = 0, taggerOnlyTotal = 0, oracleOnlyTotal = 0;
  for (const r of rows) {
    taggerTotal += scoped ? (r.pool_tagger_total || 0) : (r.tagger_total || 0);
    oracleTotal += scoped ? (r.pool_oracle_total || 0) : (r.oracle_total || 0);
    bothTotal += scoped ? (r.pool_both || 0) : (r.both || 0);
    taggerOnlyTotal += scoped ? (r.pool_tagger_only || 0) : (r.tagger_only || 0);
    oracleOnlyTotal += scoped ? (r.pool_oracle_only || 0) : (r.oracle_only || 0);
  }
  const summaryParts = [];
  if (scoped) {
    const share = data.pool_total ? ` (${pct(data.pool_tagged, data.pool_total)})` : "";
    summaryParts.push(h("b", {}, "Rollen-Abdeckung im Pool:"));
    summaryParts.push(h("span", {}, `${nf(data.pool_tagged)}/${nf(data.pool_total)} Karten${share} mit Rolle`));
    summaryParts.push(h("span", { class: "muted" }, `${nf(data.pool_untagged)} ohne Rolle`));
  } else {
    summaryParts.push(h("b", {}, "Rollen-Herkunft (global):"));
  }
  summaryParts.push(h("span", { class: "muted" }, `Tagger ${nf(taggerTotal)} · Oracle-Text ${nf(oracleTotal)} · Übereinstimmung ${nf(bothTotal)} · nur Tagger ${nf(taggerOnlyTotal)} · nur Oracle ${nf(oracleOnlyTotal)}`));
  const shownRows = rows.filter((r) => (scoped ? (r.pool_count || r.pool_tagger_total || r.pool_oracle_total) : (r.tagger_total || r.oracle_total)));
  const detailTable = shownRows.length
    ? h("div", { class: "audit-table-wrap" }, table(
      scoped
        ? ["Rolle", "Pool (n/N)", "Tagger", "Oracle-Text", "Beide", "Nur Tagger", "Nur Oracle"]
        : ["Rolle", "Tagger", "Oracle-Text", "Beide", "Nur Tagger", "Nur Oracle"],
      shownRows.map((r) => scoped
        ? [roleName(r.role), `${nf(r.pool_count || 0)}/${nf(data.pool_total)}`, nf(r.pool_tagger_total || 0), nf(r.pool_oracle_total || 0), nf(r.pool_both || 0), nf(r.pool_tagger_only || 0), nf(r.pool_oracle_only || 0)]
        : [roleName(r.role), nf(r.tagger_total || 0), nf(r.oracle_total || 0), nf(r.both || 0), nf(r.tagger_only || 0), nf(r.oracle_only || 0)]),
    ))
    : h("p", { class: "muted" }, "Keine Rollen-Belege im aktuellen Ausschnitt.");
  panel.replaceChildren(
    h("div", { class: "facts" }, ...summaryParts),
    h("details", {}, h("summary", {}, `Rollen-Audit nach Herkunft (${nf(shownRows.length)} aktive Rollen)`), detailTable),
  );
}
async function loadRoleAudit() {
  const url = state.view === "global"
    ? "/api/roles/audit"
    : `/api/roles/audit?commander=${encodeURIComponent(COMMANDER)}`;
  try {
    state.roleAudit = await api(url);
  } catch (error) {
    state.roleAudit = null;
  }
  renderRoleAuditPanel();
}
function formatGroupCell(converted, known, rate, low, high) {
  const counts = `${nf(converted)}/${nf(known)}`;
  if (rate === null || rate === undefined) {
    return h("span", { title: `${counts}: unter dem Mindest-N, kein Prozentwert (nie 0)` }, `${counts} · `, h("span", { class: "badge warn" }, "zu wenig Daten"));
  }
  const ci = low !== null && low !== undefined && high !== null && high !== undefined
    ? ` (95 %: ${StudioUI.num(100 * low, 1)}–${StudioUI.num(100 * high, 1)} %)`
    : "";
  return `${counts} · ${StudioUI.num(100 * rate, 1)} %${ci}`;
}
function renderTournamentConversionPanel() {
  const panel = $("topdeck-conversion-panel");
  if (!panel) return;
  const data = state.conversion;
  if (!data) { panel.replaceChildren(); return; }
  const cohortLabel = data.cohort || "Bracket 5 (Turnier)";
  const header = [
    h("b", {}, `TopDeck Turnier-Conversion (Mit/Ohne · ${cohortLabel}):`),
  ];
  const cards = Array.isArray(data.cards) ? data.cards : [];
  const comparableCount = cards.filter((c) => c.status === "OK").length;
  if (data.status === "INSUFFICIENT_DATA") {
    header.push(h("span", {}, `${nf(data.total_known_decks)} von ${nf(data.total_decks)} Listen mit bekanntem Top-Cut`));
    header.push(h("span", { class: "badge warn", title: data.reason || "" }, `${data.reason ? codeLabel(data.reason) : "zu wenig Daten"} (Mindest-N: ${nf(data.min_sample)})`));
  } else {
    header.push(h("span", {}, `${nf(data.total_converted_decks)}/${nf(data.total_known_decks)} Top-Cut-Conversions (${StudioUI.num(100 * data.baseline_conversion_rate, 1)} %, 95-%-Wilson ${StudioUI.num(100 * data.baseline_ci_low, 1)}–${StudioUI.num(100 * data.baseline_ci_high, 1)} %)`));
    header.push(h("span", { class: "muted", title: data.data_class }, `${nf(comparableCount)} Karten mit Mit/Ohne je ≥ ${nf(data.min_sample)} Listen · ${codeLabel(data.data_class)}`));
  }
  const countEl = h("span", { class: "muted" });
  const tableWrap = h("div", { class: "audit-table-wrap" });
  const updateFilteredRows = () => {
    const q = (state.conversionFilter || "").trim().toLowerCase();
    const filtered = q ? cards.filter((c) => c.card_name.toLowerCase().includes(q)) : cards;
    countEl.textContent = `${nf(filtered.length)} von ${nf(cards.length)} Karten`;
    tableWrap.replaceChildren(table(
      ["Karte", "Mit Karte (n/N)", "Ohne Karte (n/N)", "Differenz (Pp)", "Status"],
      filtered.slice(0, 120).map((row) => [
        row.card_name,
        formatGroupCell(row.with_converted, row.with_known, row.with_rate, row.with_ci_low, row.with_ci_high),
        formatGroupCell(row.without_converted, row.without_known, row.without_rate, row.without_ci_low, row.without_ci_high),
        row.diff_pp === null || row.diff_pp === undefined ? h("span", { class: "unknown" }, "zu wenig Daten") : `${row.diff_pp > 0 ? "+" : ""}${StudioUI.num(row.diff_pp, 1)} Pp`,
        row.status === "OK" ? h("span", { class: "badge good", title: "OK" }, "auswertbar") : h("span", { class: "badge warn", title: row.reason || "" }, row.reason ? codeLabel(row.reason) : "zu wenig Daten"),
      ]),
    ));
  };
  const searchInput = h("input", {
    type: "search",
    placeholder: "Karte im Turnier-Vergleich filtern …",
    "aria-label": "Karte im Turnier-Vergleich filtern",
    value: state.conversionFilter,
    oninput: (event) => {
      state.conversionFilter = event.target.value;
      updateFilteredRows();
    },
  });
  updateFilteredRows();
  const detailContent = cards.length
    ? [
      h("p", { class: "rule" }, `Kohorte: ${cohortLabel} (${codeLabel(data.data_class)}). Nur beschreibend, keine Kausalität. Unter ${nf(data.min_sample)} bekannten Listen bleibt das Feld „zu wenig Daten“ (nie 0).`),
      h("div", { class: "conv-filter-row" }, searchInput, countEl),
      tableWrap,
    ]
    : [h("p", { class: "muted" }, `Keine TopDeck-Turnierlisten für ${COMMANDER} in dieser Auswertung (${data.reason ? codeLabel(data.reason) : "zu wenig Daten"}).`)];
  panel.replaceChildren(
    h("div", { class: "facts" }, ...header),
    h("details", {}, h("summary", {}, `TopDeck Mit/Ohne-Übersicht (${nf(cards.length)} Karten)`), ...detailContent),
  );
}
async function loadTournamentConversion() {
  try {
    state.conversion = await api(`/api/tournament-conversion?commander=${encodeURIComponent(COMMANDER)}`);
  } catch (error) {
    state.conversion = null;
  }
  renderTournamentConversionPanel();
}

async function setView(view) {
  state.view = view;
  renderCoreLine();
  syncRankGroupToggle();
  await loadEvidence();
  if (view === "deck") await loadDeck();
  loadRoleAudit().catch(() => {});
}

function renderTabs() {
  $("tabs").replaceChildren(...[["cards", "Karten"], ["research", "Forschungsliste"]].map(([key, label]) => h("button", { type: "button", class: "chip" + (state.tab === key ? " on" : ""), "aria-pressed": String(state.tab === key), onclick: () => { state.tab = key; renderTabs(); render(false); } }, label)));
}
function renderCoreLine() {
  $("core-line").textContent = state.view === "global"
    ? "Ohne Commander gibt es keine Stufe: gezeigt wird die globale Beliebtheit, keine Spielstärke."
    : `Stufe = Nutzung in ${VIEW_NAMES.commander}-Decks, keine Spielstärke.`;
}

async function init() {
  $("view").replaceChildren(...Object.entries(VIEW_NAMES).map(([key, label]) => h("option", { value: key }, label)));
  $("sort").replaceChildren(...SORTS.map(([key, label]) => h("option", { value: key }, label)));
  $("view").addEventListener("change", () => setView($("view").value).catch((error) => fail(error)));
  $("deck-select").addEventListener("change", () => { fillBranches(); loadDeck().catch((error) => fail(error)); });
  $("branch-select").addEventListener("change", () => loadDeck().catch((error) => fail(error)));
  $("sort").value = state.sortKey;
  const storedPreset = StudioUI.recall(PRESET_KEY, "");
  state.preset = storedPreset === "compact" || storedPreset === "detail" ? storedPreset : window.innerWidth < COMPACT_BELOW ? "compact" : "detail";
  state.funcMode = StudioUI.recall(COMPARE_KEY, "") === "function";
  const method = $("method-panel");
  method.open = StudioUI.recall(METHOD_KEY, "") === "1";
  method.addEventListener("toggle", () => StudioUI.remember(METHOD_KEY, method.open ? "1" : ""));
  renderCoreLine();
  renderLayerControls();
  renderTierBar();
  syncRankGroupToggle();
  const savedSort = StudioUI.recall(SORT_KEY, "");
  if (savedSort && (SORTS.some((item) => item[0] === savedSort) || savedSort.startsWith(PERCENTILE_SORT) || savedSort.startsWith(LAYER_SORT))) { state.sortKey = savedSort; state.sortDir = SMALL_FIRST.has(savedSort) ? 1 : -1; $("sort").value = savedSort; }
  $("sort").addEventListener("change", () => { state.sortKey = $("sort").value; state.sortDir = SMALL_FIRST.has(state.sortKey) ? 1 : -1; StudioUI.remember(SORT_KEY, state.sortKey); render(false); });
  for (const id of ["q", "type-filter", "land-filter", "role-filter", "spread-filter", "f-free", "f-fav", "f-excl"]) $(id).addEventListener("input", () => { state.shown = 150; if (id === "role-filter") renderTierBar(); render(false); });
  if (typeof StudioSearch !== "undefined" && StudioSearch.attachSyntaxHelper && $("q")) {
    StudioSearch.attachSyntaxHelper($("q"), () => { state.shown = 150; render(false); });
  }
  const applyTierFilterPreset = (cfg) => {
    $("q").value = cfg.q || "";
    $("type-filter").value = cfg.type || "";
    $("land-filter").value = cfg.land || "";
    $("role-filter").value = cfg.role || "";
    $("spread-filter").value = cfg.spread || "";
    $("f-free").checked = cfg.free !== false;
    $("f-fav").checked = Boolean(cfg.fav);
    $("f-excl").checked = Boolean(cfg.excl);
    state.strength.tiers = new Set((Array.isArray(cfg.tiers) ? cfg.tiers : []).filter((tier) => STRENGTH_TIERS.includes(tier)));
    state.shown = 150;
    if (cfg.columns === "compact" || cfg.columns === "detail") { if (cfg.columns !== state.preset) { setPreset(cfg.columns); renderTierBar(); return; } }
    renderTierBar(); render(false);
  };
  if ($("tier-quick-presets")) {
    $("tier-quick-presets").replaceChildren(
      h("button", { type: "button", class: "chip", onclick: () => applyTierFilterPreset({ free: true }) }, "Standardfilter"),
      h("button", { type: "button", class: "chip", onclick: () => applyTierFilterPreset({ free: true, land: "spells" }) }, "Nur Zauber (frei)"),
      h("button", { type: "button", class: "chip", onclick: () => applyTierFilterPreset({ free: false, spread: "U" }) }, "Verbreitung unbekannt (U)"),
      h("button", { type: "button", class: "chip", onclick: () => {
        const snap = { q: $("q").value, type: $("type-filter").value, land: $("land-filter").value, role: $("role-filter").value, spread: $("spread-filter").value, free: $("f-free").checked, fav: $("f-fav").checked, excl: $("f-excl").checked, tiers: [...state.strength.tiers], columns: state.preset };
        StudioUI.remember("studio.tierlist.savedPreset", JSON.stringify(snap));
        toast("Tierlisten-Filteransicht gespeichert.");
      } }, "Ansicht merken"),
      h("button", { type: "button", class: "chip", onclick: () => {
        try {
          const raw = StudioUI.recall("studio.tierlist.savedPreset", "");
          if (!raw) { toast("Noch keine Filteransicht gespeichert."); return; }
          applyTierFilterPreset(JSON.parse(raw));
        } catch (_) { toast("Gespeicherte Filteransicht konnte nicht geladen werden."); }
      } }, "Gemerkte Ansicht")
    );
  }
  for (const btn of document.querySelectorAll("#rank-group-toggle button[data-rank-group]")) {
    btn.addEventListener("click", () => setQuickRankGroup(btn.getAttribute("data-rank-group")).catch((error) => fail(error)));
  }
  const syncTierMode = () => {
    for (const btn of document.querySelectorAll("#tier-mode-toggle button[data-tier-mode]")) {
      const active = btn.getAttribute("data-tier-mode") === state.tierMode;
      btn.classList.toggle("on", active);
      btn.setAttribute("aria-pressed", String(active));
    }
  };
  syncTierMode();
  for (const btn of document.querySelectorAll("#tier-mode-toggle button[data-tier-mode]")) {
    btn.addEventListener("click", () => {
      state.tierMode = btn.getAttribute("data-tier-mode") === "relative" ? "relative" : "absolute";
      StudioUI.remember(TIER_MODE_KEY, state.tierMode);
      syncTierMode();
      render(false);
    });
  }
  document.addEventListener("keydown", trapModalFocus);
  renderTabs();
  $("pool-body").replaceChildren(StudioUI.loading("Tierliste lädt …"));
  await StudioCommander.fill($("commander-select"));
  dataBanner().catch(() => {});
  loadTournamentConversion().catch(() => {});
  try {
    const marks = await api("/api/marks");
    for (const [cardId, mark] of Object.entries(marks)) state.marks.set(cardId, { favorite: mark.favorite, excluded: mark.excluded, note: mark.note || "" });
  } catch (error) { fail(error); }
  await Promise.all([setView("commander"), initUniverse()]);
  await initDecks();
  await initStrength();
}
init().catch((error) => fail(error));
