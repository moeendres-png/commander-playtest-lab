"use strict";
// Commander Studio deck builder. All text from data is set as text, never as HTML.

const COMMANDER = StudioCommander.current;
const GROUPS = ["Creature", "Planeswalker", "Battle", "Artifact", "Enchantment", "Instant", "Sorcery", "Land", "Other"];
const GROUP_NAMES = { Creature: "Kreaturen", Planeswalker: "Planeswalker", Battle: "Schlachten", Artifact: "Artefakte", Enchantment: "Verzauberungen", Instant: "Spontanzauber", Sorcery: "Hexereien", Land: "Länder", Other: "Sonstige" };
const COHORT_NAMES = {
  all: "alle Quelldecks",
  tuned: "B4+5 (Tuned)",
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
const roleName = (key) => ROLE_NAMES[key] || key;
const ISSUE_NAMES = { deck_size: "Deckgröße", commander_count: "Commander", commander_type: "Commander-Typ", color_identity: "Farbidentität", singleton: "Mehrfach", legality_unknown: "Legalität unbekannt", not_legal: "Nicht legal", not_owned: "Nicht in der Sammlung", not_available: "Nicht frei" };

const state = {
  pool: [], byId: new Map(), cohorts: {}, small: 30, commanderIds: [],
  universe: "", universeInfo: null, countedUniverse: null, gcBand: "", gcBandData: null,
  decks: [], deckId: null, branch: "main", baseRevision: null,
  list: new Map(), dirty: false, draftUpdatedAt: "", draftConflict: false, baseStale: false, needsDraftPut: false, issues: [], shape: null, deckRoles: {}, combos: null, roles: [], shapes: [],
  simulations: [], diffBaseRev: null, diffData: null, deckFacts: null, castability: null, activeBatch: null, batchPollTimer: null,
  activePaired: null, pairedPollTimer: null, pairedHistory: [], readinessAudit: null,
  view: "grid", tab: "list", shown: 120, sortKey: "freq", sortDir: -1, cohort: "all",
  subset: null, subsetNames: [], subsetWanted: null, strength: null, showTier: true, changeSeq: 0, savedSeq: 0, layers: null, diffDefault: null,
  includeUnowned: false, superfriendsFilter: "",
  cardTrend: null, cardTrendDays: 180, cardTrendBracket: "", cardTrendSource: "edhrec", cardTrendReq: null,
  colors: new Set(), columns: new Set(["img", "name", "mana_cost", "type_line", "available", "freq", "edhrec"]),
};

const $ = (id) => document.getElementById(id);
// replaceChildren shows a null argument as the text "null": drop empty children.
const kids = (...items) => items.filter((item) => item !== null && item !== undefined && item !== false);
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
// One row of "Aufgezeichnete Einzelpartien" (SIMULATE).
function recordedGameRow(g) {
  const hdr = g.header || {};
  const end = g.running ? "läuft" : g.result && g.result.status === "finished" ? `Sieger Sitz ${((g.result.winner_seats || []).map((s) => s + 1)).join(", ") || "keiner"}` : "abgebrochen";
  const jarShort = hdr.bridge_jar_sha256 ? String(hdr.bridge_jar_sha256).slice(0, 12) : "–";
  const jarTitle = [hdr.bridge_jar_sha256 ? `SHA-256: ${hdr.bridge_jar_sha256}` : null, hdr.bridge_qualification_state ? `Stand: ${hdr.bridge_qualification_state}` : null].filter(Boolean).join(" · ");
  // The cohort comes from the server (game log header); a game a human played, or one whose
  // origin is unknown, carries its mark and is never listed as a simulation (#1662).
  const cohortMark = StudioCohort.mark(g);
  return h("tr", {},
    h("td", {}, h("code", {}, g.game_id), cohortMark && " ", cohortMark && h("span", { class: cohortMark.cohort === StudioCohort.PLAYED ? "pill good" : "pill warn", title: cohortMark.title }, cohortMark.text)),
    h("td", { class: "num" }, hdr.seed == null ? "–" : StudioUI.num(hdr.seed, 0)),
    h("td", { class: "num" }, StudioUI.num(g.frames ?? 0, 0)),
    h("td", {}, h("code", { title: jarTitle }, jarShort)),
    h("td", {}, end),
    h("td", {}, h("a", { href: `partie.html?partie=${encodeURIComponent(g.game_id)}` }, "Ansehen →")));
}
const api = StudioUI.request;
const toast = (text) => StudioUI.toast(text);
const fail = (error, asText = false) => {
  const msg = StudioUI.germanError(error);
  if (asText) return msg;
  StudioUI.fail(msg);
  return msg;
};
// Cohort keys of the corpus ("bracket:3", "source:edhrec", "variant:cedh") in plain words.
const COHORT_PREFIX = { bracket: "Bracket", source: "Quelle", variant: "Variante", commander: "Commander", theme: "Thema", tag: "Marke" };
const COHORT_VALUES = { cedh: "cEDH", core: "Core", upgraded: "Upgraded", optimized: "Optimized", exhibition: "Exhibition", edhrec: "EDHREC", archidekt: "Archidekt", moxfield: "Moxfield", topdeck: "TopDeck" };
const cohortName = (key) => {
  if (COHORT_NAMES[key]) return COHORT_NAMES[key];
  const at = String(key).indexOf(":");
  if (at < 0 || !COHORT_PREFIX[key.slice(0, at)]) return key;
  const value = key.slice(at + 1);
  return `${COHORT_PREFIX[key.slice(0, at)]} ${COHORT_VALUES[value] || value.charAt(0).toUpperCase() + value.slice(1)}`;
};
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
  if (card.decks_known === false) return { hits: null, total, share: null };
  const hits = (card.decks && card.decks[cohort]) || 0;
  return { hits, total, share: total ? hits / total : null };
}
function freqText(card, cohort = state.cohort) {
  const f = freq(card, cohort);
  if (f.hits === null) return "unbekannt";
  return f.total ? `${StudioUI.num(f.hits, 0)}/${StudioUI.num(f.total, 0)} · ${StudioUI.num(100 * f.share, 0)} %` : "unbekannt";
}
function isRedundantCohort(key) {
  if (key === "all") return false;
  const allSize = state.cohorts.all || 0;
  if (!allSize) return false;
  if (String(key).startsWith("commander:") && state.cohorts[key] === allSize) return true;
  if (key === "community" && state.cohorts.community === allSize) return true;
  return false;
}
function visibleCohortEntries() {
  return Object.entries(state.cohorts).filter(([key]) => !isRedundantCohort(key));
}
// The active counted scope (universe profile or Game-Changer-Band), decided in one place
// (gcband.js); null means the legacy cohort figures of state.cohort.
const activeScope = () => StudioGcBand.activeScope(state);
// With a universe profile or a Game-Changer-Band chosen, the pool shows that scope's counted
// spread (same snapshot as the tier list) instead of the legacy cohort figures. A card the
// scope does not name is "unbekannt" (hits null), never 0.
function displayFreq(card) {
  if (state.subset) {
    // Only the decks that contain every chosen card: the denominator is the subset. A chosen
    // card is in all of them by definition (Filterkarte, no count); no deck listing a card
    // means unknown, never 0.
    const item = state.subset.map.get(card.card_id);
    if (item) return { hits: item.filter_card ? null : item.hits, total: item.denominator, share: item.share, filter: Boolean(item.filter_card) };
  }
  // A card the universe's card filter requires is in every deck of the subset by
  // definition: it has no count to show, only the label "Filterkarte".
  const scoped = StudioGcBand.scopedFreq(card, activeScope(), state.universeInfo ? state.universeInfo.denominator : 0);
  if (scoped) return scoped;
  // No local deck lists and no chosen universe: the counted deck-list universe the server picked
  // automatically (the same choice as the tier list). A card without a row is a counted zero.
  if (state.countedUniverse && card.counted && !(state.cohorts[state.cohort] || 0)) {
    return { hits: card.counted.hits, total: card.counted.denominator, share: card.counted.share, filter: false };
  }
  return freq(card);
}
const countedName = () => state.countedUniverse ? `Verbreitung (gezählt): ${state.countedUniverse.short_label}` : "";
function displayFreqText(card) {
  const f = displayFreq(card);
  if (f.filter) return "Filterkarte";
  if (f.hits === null) return "unbekannt";
  return f.total ? `${StudioUI.num(f.hits, 0)}/${StudioUI.num(f.total, 0)} · ${StudioUI.num(100 * f.share, 0)} %` : "unbekannt";
}

const qty = (id) => state.list.get(id) || 0;
const deckTotal = () => state.commanderIds.length + [...state.list.values()].reduce((a, b) => a + b, 0);
function maxCopies(card) {
  if (state.includeUnowned && typeof StudioWishlist !== "undefined" && StudioWishlist.isUnowned(card)) {
    if (card.basic || /A deck can have any number of cards named/.test(card.text)) return 99;
    return 1;
  }
  if (card.basic || /A deck can have any number of cards named/.test(card.text)) return Math.max(card.available, 0);
  return Math.min(1, Math.max(card.available, 0));
}

// ---------- pool ----------
const sortValue = (card, key) => {
  if (key === "freq") return displayFreq(card).hits;
  if (key === "edhrec") return card.edhrec && card.edhrec.pct !== null && card.edhrec.pct !== undefined ? card.edhrec.pct : null;
  if (key === "edhrec_rank") return card.edhrec_rank === null || card.edhrec_rank === undefined ? null : card.edhrec_rank;
  if (key === "playgroup") return card.playgroup && card.playgroup.live_inclusion_pct !== null ? card.playgroup.live_inclusion_pct : null;
  if (key === "synergy") return card.signals && card.signals.synergy ? card.signals.synergy.value : null;
  if (key === "strength") { const item = state.strength && state.strength.map.get(card.card_id); return item && item.tier !== "U" && item.tier !== "N" ? item.index : null; }
  if (key === "trend") return cardTrendSortValue(state.cardTrend, card.card_id);
  const value = card[key];
  return value === undefined ? null : value;
};
function filtered() {
  const query = $("q").value.trim();
  const parsed = StudioSearch.parseQuery(query);
  state.searchErrors = parsed.errors || [];
  if (state.searchErrors.length) return [];
  const type = $("type-filter").value;
  const role = $("role-filter").value;
  const label = $("label-filter").value;
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
    if (state.superfriendsFilter && typeof StudioWishlist !== "undefined" && !StudioWishlist.matchesSuperfriendsFilter(card, state.superfriendsFilter)) return false;
    if (type && card.group !== type) return false;
    if (label === "-" ? card.labels.length > 0 : label && !card.labels.some((item) => item.toLowerCase() === label.toLowerCase())) return false;
    if (role === "-" ? card.roles.length > 0 : role && !card.roles.includes(role)) return false;
    if (min !== null && !(card.mana_value >= min)) return false;
    if (max !== null && !(card.mana_value <= max)) return false;
    if (state.colors.size) {
      const colorless = card.colors === "";
      if (!(colorless ? state.colors.has("C") : [...card.colors].some((letter) => state.colors.has(letter)))) return false;
    }
    return !query || StudioSearch.rank(card, parsed) !== null;
  });
  // A search with freetext terms ranks by how well the name fits; pure field filters or empty search use the chosen sort.
  if (query && parsed.textQuery) return StudioSearch.sortByRank(rows, parsed);
  const key = state.sortKey, dir = state.sortDir;
  const keyed = rows.map((card) => [sortValue(card, key), card]);
  keyed.sort((a, b) => {
    const x = a[0], y = b[0]; // unknown values sort last in both directions
    if (x === null && y === null) return a[1].name.localeCompare(b[1].name);
    if (x === null) return 1;
    if (y === null) return -1;
    if (x === y) return a[1].name.localeCompare(b[1].name);
    return (x > y ? 1 : -1) * dir;
  });
  return keyed.map((item) => item[1]);
}
function cardImageUrl(card, face = "front") {
  if (face === "back") return card.image_url_back || `/img/${encodeURIComponent(card.card_id)}?face=back`;
  return card.image_url_front || `/img/${encodeURIComponent(card.card_id)}?face=front`;
}
function image(card, cls, face = "front") {
  const img = h("img", { class: cls, loading: "lazy", referrerpolicy: "no-referrer", alt: card.name, src: cardImageUrl(card, face) });
  img.addEventListener("error", () => img.replaceWith(h("span", { class: "muted", title: "Kein Bild geladen (offline)" }, card.name)), { once: true });
  return img;
}
// The card picture, or its name and text when there is no image or it cannot be loaded.
function cardFace(card, onclick) {
  const fallback = () => h("div", { class: "fallback", title: "Kein Bild vorhanden", onclick }, h("b", {}, card.name), mana(card.mana_cost), h("span", { class: "muted" }, card.type_line), h("span", {}, card.text));
  if (!card.has_image) return fallback();
  const picture = h("img", { class: "", loading: "lazy", referrerpolicy: "no-referrer", alt: card.name, src: cardImageUrl(card, "front") });
  picture.addEventListener("click", onclick);
  picture.addEventListener("error", () => picture.replaceWith(fallback()), { once: true });
  return picture;
}
function hoverPreview(el, card) {
  if (!card.has_image) return;
  el.addEventListener("mouseenter", (event) => {
    const box = $("preview");
    const img = box.firstChild;
    img.referrerPolicy = "no-referrer";
    img.onerror = () => { box.hidden = true; };
    img.src = cardImageUrl(card, "front");
    box.hidden = false;
    movePreview(event);
  });
  el.addEventListener("mousemove", movePreview);
  el.addEventListener("mouseleave", () => { $("preview").hidden = true; });
}
function movePreview(event) {
  const box = $("preview");
  const left = event.clientX + 290 > innerWidth ? event.clientX - 280 : event.clientX + 20;
  box.style.left = left + "px"; box.style.top = Math.min(event.clientY - 40, innerHeight - 380) + "px";
}
function wishlistBadge(card) {
  if (typeof StudioWishlist === "undefined" || !StudioWishlist.isUnowned(card)) return null;
  return h("span", { class: "pill warn" }, "Zukauf (0 im Besitz)");
}
function tile(card) {
  const count = qty(card.card_id);
  const face = cardFace(card, () => openCard(card));
  const f = displayFreq(card);
  const subsetTitle = state.subset ? ` (${state.subset.info.label})` : "";
  const unownedBadge = wishlistBadge(card);
  return h("div", { class: "tile" + (count ? " in" : "") + (card.available < 1 ? " none" : "") },
    face, card.favorite && h("span", { class: "star" }, "★"), tierMark(card, " corner"),
    h("div", { class: "bar" },
      h("button", { class: "small", type: "button", title: "ins Deck", "aria-label": `${card.name} ins Deck`, disabled: count >= maxCopies(card), onclick: () => add(card) }, "+"),
      h("b", { class: "count", title: "Kopien im Deck" }, count ? count + "×" : "0×"),
      h("button", { class: "small", type: "button", title: "aus dem Deck", "aria-label": `${card.name} aus dem Deck`, disabled: !count, onclick: () => remove(card) }, "−"),
      h("span", { class: "spacer" }),
      h("span", { class: "freq" + (f.total && f.total < state.small ? " low" : ""), title: (activeScope() ? `${activeScope().label}: Decks mit dieser Karte` : state.countedUniverse ? `${countedName()}: Decks mit dieser Karte` : "Decks der Vergleichsgruppe mit dieser Karte") + subsetTitle }, f.filter ? "Filterkarte" : f.hits === null ? "unbekannt" : f.total ? `${StudioUI.num(f.hits, 0)}/${StudioUI.num(f.total, 0)}` : "–")),
    unownedBadge
      ? h("div", { class: "own" }, unownedBadge)
      : h("div", { class: "own" }, "Besitz ", h("b", {}, card.owned), " · frei ", h("b", {}, card.available), card.reserved ? ` · reserviert ${card.reserved}` : "", allocationTileNote(h, card)));
}
const COLUMNS = [
  ["img", "Bild", null], ["name", "Karte", "name"], ["mana_cost", "Kosten", "mana_value"], ["mana_value", "Manawert", "mana_value"],
  ["type_line", "Typ", "type_line"], ["text", "Text", null], ["pt", "S/W", null], ["available", "frei", "available"], ["owned", "Besitz", "owned"],
  ["reserved", "reserviert", "reserved"], ["freq", "Quelldecks", "freq"], ["trend", "Trend (jung vs. alt)", "trend"], ["edhrec", "EDHREC", "edhrec"], ["edhrec_rank", "EDHREC-Rang", "edhrec_rank"], ["synergy", "Synergie", "synergy"], ["strength", "Stärke-Index", "strength"],
  ["playgroup", "Playgroup", "playgroup"],
  ["roles", "Rollen", null], ["labels", "Archetyp-Marken", null], ["produced_mana", "erzeugt Mana", null], ["sim_status", "Simulator", "sim_status"], ["note", "Notiz", null],
];
// The current tier of a card as a small mark (tiles, deck list, card window). Shown only
// while "Stufe zeigen" is on and the index is loaded; U and N are named, never hidden as a low tier.
const TIER_WORDS = { U: "zu wenig Daten für eine Stufe", N: "nicht bewertet (Commander oder Standardland)" };
function tierMark(card, extra = "") {
  if (!state.showTier || !state.strength) return null;
  const item = state.strength.map.get(card.card_id);
  if (!item) return null;
  const known = !TIER_WORDS[item.tier];
  return h("span", { class: `tier-mark t-${item.tier}${extra}`, title: known ? `Stufe ${item.tier}, Stärke-Index ${StudioUI.num(item.index, 1)} (Schätzung aus Nutzungsdaten, keine Siegrate)` : TIER_WORDS[item.tier] }, known ? item.tier : "–");
}
function tierBadge(tier, text) {
  return h("span", { class: `tier-badge t-${tier}`, title: `Stufe ${tier}: Schätzung aus Nutzungsdaten` }, h("span", { class: "letter" }, tier), text);
}
function cell(card, key) {
  if (key === "img") return h("td", {}, card.has_image ? image(card, "thumb") : null);
  if (key === "name") {
    const badge = wishlistBadge(card);
    const td = h("td", { class: "name", onclick: () => openCard(card) }, (card.favorite ? "★ " : "") + card.name, badge ? " " : null, badge);
    hoverPreview(td, card);
    return td;
  }
  if (key === "mana_cost") return h("td", {}, mana(card.mana_cost));
  if (key === "text") return h("td", { class: "text" }, card.text);
  if (key === "roles") return h("td", {}, card.roles.map(roleName).join(", "));
  if (key === "labels") return h("td", { class: "labels" }, card.labels.join(", "));
  if (key === "sim_status") return h("td", { title: card.sim_status || "" }, StudioUI.simStatusLabel(card.sim_status));
  if (key === "pt") return h("td", {}, card.power !== null ? `${card.power}/${card.toughness}` : "");
  if (key === "freq") { const f = displayFreq(card); return h("td", { class: "num" + (f.total && f.total < state.small ? " low" : "") }, displayFreqText(card)); }
  if (key === "trend") return cardTrendCell(h, state.cardTrend, card.card_id);
  if (key === "edhrec") {
    const e = card.edhrec;
    if (!e || e.pct === null || e.pct === undefined) return h("td", { class: "num muted" }, "unbekannt");
    const count = e.denominator ? `${StudioUI.num(e.numerator, 0)}/${StudioUI.num(e.denominator, 0)} · ` : "";
    return h("td", { class: "num" + (e.denominator !== null && e.denominator < state.small ? " low" : ""), title: (e.origin === "signal" ? "Gespeichertes Signal (import-signals): " : "EDHREC-Seite: ") + e.page + (e.denominator ? "" : ". Nenner unbekannt") }, `${count}${StudioUI.num(e.pct, 0)} %`);
  }
  if (key === "synergy") {
    const v = sortValue(card, "synergy");
    return h("td", { class: "num" + (v === null ? " muted" : ""), title: "EDHREC-Synergie dieses Commanders (gespeichertes Signal)" }, v === null ? "unbekannt" : `${v > 0 ? "+" : ""}${StudioUI.num(100 * v, 0)} %`);
  }
  if (key === "strength") {
    if (!state.strength) return h("td", { class: "num muted", title: "Wähle die Sortierung „Stärke-Index“ oder lade ihn mit dem Knopf unter dem Pool" }, "–");
    const item = state.strength.map.get(card.card_id);
    if (!item || item.tier === "N") return h("td", { class: "num muted" }, "nicht bewertet");
    if (item.tier === "U") return h("td", { class: "num muted" }, "zu wenig Daten");
    return h("td", { class: "num", title: "Schätzung aus Nutzungsdaten, keine Siegrate" }, tierBadge(item.tier, StudioUI.num(item.index, 1)));
  }
  if (key === "playgroup") {
    if (!card.playgroup) return h("td", { class: "num muted" }, "unbekannt");
    const p = card.playgroup;
    const gap = p.observed_winrate_gap_pp !== null ? `${p.observed_winrate_gap_pp > 0 ? "+" : ""}${StudioUI.num(p.observed_winrate_gap_pp, 1)} pp` : "–";
    const turn = p.median_cast_turn !== null ? `T${StudioUI.num(p.median_cast_turn, 1)}` : "–";
    return h("td", { class: "num" + (p.insufficient_sample ? " low" : ""), title: `Playgroup Live: Cast-Turn ${turn}, Winrate-Gap ${gap}` }, `${p.live_inclusion_pct !== null ? StudioUI.num(p.live_inclusion_pct, 0) + " %" : "–"} · ${turn} · ${gap}`);
  }
  const value = card[key];
  return h("td", { class: typeof value === "number" ? "num" : "" }, value === null || value === undefined ? "" : typeof value === "number" ? StudioUI.numFlex(value, 2) : value);
}
// The second filter row folds away on small windows; the chip keeps the active ones in sight.
const FILTER_OPEN_KEY = "studio.builder.filters-open";
function activeSecondaryFilters() {
  const on = [$("type-filter").value, $("role-filter").value, $("label-filter").value].filter((value) => value !== "").length
    + ($("mv-min").value !== "" || $("mv-max").value !== "" ? 1 : 0)
    + ($("f-free").checked ? 0 : 1)
    + (state.superfriendsFilter ? 1 : 0)
    + ["f-notin", "f-fav", "f-excl", "f-sim", "f-unowned"].filter((id) => $(id) && $(id).checked).length;
  return on;
}
function updateFilterChip() {
  const chip = $("filter-count"), n = activeSecondaryFilters();
  chip.hidden = n === 0;
  chip.textContent = `${StudioUI.num(n)} aktiv`;
  chip.title = `${StudioUI.num(n)} Filter in der eingeklappten Leiste aktiv`;
}
function setFiltersOpen(open) {
  $("filters-more").hidden = !open;
  $("filter-toggle").setAttribute("aria-expanded", open ? "true" : "false");
}
function setupFilterToggle() {
  const small = window.matchMedia && window.matchMedia("(max-height: 800px), (max-width: 1400px)").matches;
  const stored = StudioUI.recall(FILTER_OPEN_KEY, "");
  setFiltersOpen(stored === "1" || stored === "0" ? stored === "1" : !small);
  $("filter-toggle").addEventListener("click", () => {
    const open = $("filters-more").hidden;
    setFiltersOpen(open); StudioUI.remember(FILTER_OPEN_KEY, open ? "1" : "0");
  });
}
function renderPool() {
  updateFilterChip();
  const rows = filtered();
  $("pool-count").textContent = `${StudioUI.num(rows.length, 0)} von ${StudioUI.num(state.pool.length - state.commanderIds.length, 0)} Karten` + ($("q").value.trim() ? " · nach Treffer sortiert" : "") + ($("q").value.trim() && state.germanNames === false ? " · deutsche Namen nicht verfügbar" : "") + (state.subset ? ` · ${state.subset.info.label}` : "");
  const body = $("pool-body"); body.replaceChildren();
  if (state.searchErrors && state.searchErrors.length) {
    body.append(h("div", { id: "search-syntax-error", class: "empty" },
      h("b", {}, "Hinweis zur Such-Syntax:"),
      ...state.searchErrors.map((msg) => h("p", {}, msg)),
      h("p", { class: "muted" }, 'Beispiele: t:creature · mv<=2 · r:ramp · c:gu · id<=gwu · -t:land · "draw a card"')));
    return;
  }
  if (!rows.length) {
    body.append(h("div", { class: "empty" }, h("b", {}, "Keine Karte passt zu diesen Filtern."), "Lockere einen Filter oder lösche die Suche."));
    return;
  }
  const part = rows.slice(0, state.shown);
  if (state.view === "grid") {
    body.append(h("div", { class: "grid" }, part.map(tile)));
  } else {
    const columns = COLUMNS.filter(([key]) => state.columns.has(key));
    const head = h("tr", {}, h("th", {}, ""), columns.map(([key, label, sortKey]) => h("th", {
      class: ["available", "owned", "reserved", "freq", "trend", "edhrec", "edhrec_rank", "mana_value", "synergy", "strength"].includes(key) ? "num" : "",
      onclick: sortKey ? () => { state.sortDir = state.sortKey === sortKey ? -state.sortDir : (["name", "type_line", "edhrec_rank", "mana_value"].includes(sortKey) ? 1 : -1); state.sortKey = sortKey; $("sort").value = ""; if (sortKey === "strength") loadStrength(); if (sortKey === "trend") loadCardTrend(); renderPool(); } : null,
    }, (key === "trend" ? cardTrendHeaderLabel(state.cardTrend, state.cardTrendSource, state.cardTrendBracket) : key === "freq" && state.subset ? label + " (Teilmenge)" : key === "freq" && state.countedUniverse && !activeScope() ? "Verbreitung (gezählt)" : label) + (state.sortKey === sortKey && sortKey ? (state.sortDir > 0 ? " ▲" : " ▼") : ""))));
    const lines = part.map((card) => {
      const count = qty(card.card_id);
      return h("tr", { class: count ? "in" : "" },
        h("td", {}, count
          ? h("button", { class: "small", type: "button", onclick: () => remove(card) }, "−")
          : h("button", { class: "small", type: "button", disabled: maxCopies(card) < 1, onclick: () => add(card) }, "+")),
        columns.map(([key]) => cell(card, key)));
    });
    body.append(h("div", { class: "table-wrap" }, h("table", {}, h("thead", {}, head), h("tbody", {}, lines))));
  }
  if (rows.length > part.length) {
    body.append(h("p", {}, h("button", { type: "button", onclick: () => { state.shown += 240; renderPool(); } }, `Weitere anzeigen (${StudioUI.num(rows.length - part.length, 0)})`)));
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
function renderSaveState() {
  const box = $("save-state");
  // B2b (#1658), #1727: the saved state under this draft moved (an adoption, another tab):
  // saving into this variant is refused; the work can be kept as a new variant, or the draft is
  // discarded and the current state loaded. The notice stays until one of the two is done.
  if (state.baseStale) {
    box.replaceChildren(
      h("span", { class: "pill bad" }, "Entwurf ist veraltet: der Stand darunter wurde inzwischen geändert. Als neue Variante speichern behält die Arbeit; Verwerfen und neu laden löscht sie"),
      " ",
      h("button", { type: "button", class: "small", onclick: () => openNewBranchModal() }, "Als neue Variante speichern"),
      " ",
      h("button", { type: "button", class: "small", onclick: () => discardStaleDraft().catch((error) => fail(error)) }, "Entwurf verwerfen und aktuellen Stand laden"),
    );
    return;
  }
  if (state.draftConflict) {
    box.replaceChildren(
      h("span", { class: "pill bad" }, "Konflikt: Entwurf in anderem Tab geändert"),
      " ",
      h("button", { type: "button", class: "small", onclick: () => {
        if (committing) { toast("Speichern läuft schon, bitte warten."); return; } // a load now would be dropped by the save
        loadDecks().then(loadBranch).catch((error) => fail(error));
      } }, "Aktuellen Stand laden"),
    );
    return;
  }
  box.textContent = state.dirty ? "Entwurf gesichert, noch nicht als Stand gespeichert" : "gespeichert";
}
function changed() {
  state.dirty = true; state.needsDraftPut = true; state.changeSeq += 1; renderAll();
  clearTimeout(saveTimer); saveTimer = setTimeout(syncDraft, 500);
}
// One save after the other: two saves in the air could reach the server in the wrong order
// and leave the older list stored.
let syncQueue = Promise.resolve();
function syncDraft() {
  syncQueue = syncQueue.then(syncDraftNow, syncDraftNow); // a failed save never blocks the next one
  return syncQueue;
}
async function syncDraftNow() {
  const seq = state.changeSeq; // the list as of this change is what this call saves
  try {
    const cards = entries();
    const shouldPut = state.needsDraftPut && state.dirty;
    const [result, putRes] = await Promise.all([
      api("/api/check", "POST", { cards, owned_only: !state.includeUnowned }),
      shouldPut
        ? api(`/api/decks/${encodeURIComponent(state.deckId)}/branches/${encodeURIComponent(state.branch)}/draft`, "PUT", {
            cards,
            base_revision_id: state.baseRevision,
            expected_updated_at: state.draftUpdatedAt || null,
            expected_base_revision_id: state.baseRevision,
            check_conflict: true,
          })
        : null,
    ]);
    if (putRes) {
      state.draftUpdatedAt = putRes.updated_at || "";
      if (state.changeSeq === seq) state.needsDraftPut = false;
      state.draftConflict = false;
    }
    state.savedSeq = Math.max(state.savedSeq, seq); // only a save that reached the server counts
    state.issues = result.issues; state.shape = result.shape; state.deckRoles = result.roles || {}; state.combos = result.combos || null;
    renderSaveState();
    renderHeader(); renderDeck();
  } catch (error) {
    if (error && error.status === 409) {
      state.draftConflict = true;
      renderSaveState();
      toast(StudioUI.germanError(error), "error");
      return;
    }
    fail(error);
  }
}
// Another page (the tier list's "+ Deck") may have changed the working list while this tab
// was in the background: when the tab is looked at again, the stored draft wins over the list
// held here, unless a change of this tab has not reached the server (still waiting, being
// sent, or failed): changes are counted, and only a tab whose every change is saved adopts.
async function adoptForeignDraft() {
  const seq = state.changeSeq;
  if (committing) return; // a save is in the air; it drops the server draft, so nothing is adopted now
  if (document.hidden || !state.deckId || state.savedSeq !== seq) return; // an edit of this tab is unsent (or its save failed)
  try {
    const found = await api(`/api/decks/${encodeURIComponent(state.deckId)}/branches/${encodeURIComponent(state.branch)}/draft`);
    if (!found.draft || state.changeSeq !== seq) return; // edited while the question was on its way
    const key = (cards) => JSON.stringify(cards.filter((card) => card.zone === "main").map((card) => [card.card_id, card.quantity]).sort());
    if (key(found.draft.cards) === key(entries())) {
      state.draftUpdatedAt = found.draft.updated_at || "";
      return;
    }
    state.draftUpdatedAt = found.draft.updated_at || "";
    state.draftConflict = false;
    state.needsDraftPut = false;
    await ensureUnownedLoadedFor(found.draft.cards);
    useCards(found.draft.cards); state.dirty = true; renderAll(); await syncDraft();
    toast("Das Deck wurde auf einer anderen Seite geändert (zum Beispiel in der Tierliste). Die Liste hier ist jetzt aktuell.");
  } catch (error) { /* the next look at the tab tries again */ }
}
document.addEventListener("visibilitychange", adoptForeignDraft);
window.addEventListener("focus", adoptForeignDraft);
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
  renderPlayButton();
}
// The Partien page takes the saved revision, never the draft: an unsaved draft says so on the
// button instead of silently playing an older state.
function playAddress(revisionId) {
  return `partie.html?neu=1&revision=${encodeURIComponent(revisionId)}`;
}
function renderPlayButton() {
  const button = $("play-state");
  const unsaved = state.dirty || !state.baseRevision;
  button.textContent = unsaved ? "Erst als Stand speichern, dann spielen" : "Mit diesem Stand eine Partie spielen";
  button.classList.toggle("warn", unsaved);
  button.disabled = false;
}
function deckCards() {
  return [...state.list.keys()].map((id) => state.byId.get(id)).filter(Boolean);
}
function copyWishlist(ownership) {
  if (typeof StudioWishlist === "undefined" || !ownership || !ownership.missing) return;
  const text = StudioWishlist.formatWishlistText(ownership.missingCards);
  if (!text) return;
  const openFallbackModal = () => {
    const box = $("modal-box"); box.className = "plain";
    const area = h("textarea", { rows: 12, readonly: true, "aria-label": "Zukauf-Liste" }, text);
    box.replaceChildren(
      h("h2", {}, `Zukauf-Liste (${StudioUI.num(ownership.missing, 0)} fehlende Karten)`),
      h("p", { class: "note" }, "Reine Kartenliste (nur fehlende Karten aus diesem Deck)."),
      area,
      h("div", { class: "actions" }, h("button", { type: "button", onclick: closeModal }, "Schließen"))
    );
    $("modal").hidden = false;
    area.select();
  };
  if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
    navigator.clipboard.writeText(text).then(
      () => toast(`Zukauf-Liste (${StudioUI.num(ownership.missing, 0)} Karten) kopiert.`),
      openFallbackModal
    );
  } else {
    openFallbackModal();
  }
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
  if (typeof StudioWishlist !== "undefined") {
    const ownership = StudioWishlist.summarizeDeckOwnership(entries(), state.byId);
    if (ownership.missing > 0) {
      body.append(h("div", { class: "actions", id: "wishlist-summary" },
        h("span", { class: "pill warn", title: "Kopien dieser Deckliste samt Commander (ein Commander-Deck hat 100): im Besitz laut Sammlung (Untergrenze), Zukauf = fehlende Kopien" }, `Im Besitz: ${StudioUI.num(ownership.owned, 0)}/100 · Zukauf: ${StudioUI.num(ownership.missing, 0)}/100`),
        h("button", { type: "button", class: "small", id: "copy-wishlist", onclick: () => copyWishlist(ownership) }, "Zukauf-Liste kopieren")));
    }
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
        h("span", { class: "qty" }, qty(card.card_id)), tierMark(card), name, wishlistBadge(card), mana(card.mana_cost),
        !card.basic && card.roles && card.roles.length ? h("button", { class: "small", type: "button", title: "Tausch-Helfer: Karten mit gleicher Rolle", onclick: () => openCard(card, "replace") }, "⇄") : null,
        card.basic ? h("button", { class: "small", type: "button", disabled: qty(card.card_id) >= maxCopies(card), onclick: () => add(card) }, "+") : null,
        h("button", { class: "small", type: "button", onclick: () => remove(card) }, "−")));
    }
    body.append(box);
  }
}
function bars(values, labels) {
  const top = Math.max(1, ...values);
  return [h("div", { class: "bars" }, values.map((value) => {
    const pct = Math.max(0, Math.min(100, Math.round((100 * value) / top)));
    return h("div", { class: `bh-${pct}` }, h("span", {}, value));
  })),
  h("div", { class: "axis" }, labels.map((label) => h("span", {}, label)))];
}
// ---------- deck filter: only source decks that contain all chosen cards ----------
const poolNames = () => new Map(state.pool.filter((card) => !state.commanderIds.includes(card.card_id)).map((card) => [card.name.toLowerCase(), card.name]));
// The list the filter is heading for: two quick adds both count, even before the first answer is in.
const wantedNames = () => (state.subsetWanted || state.subsetNames);
let subsetTicket = 0;
async function applySubset(names) {
  const ticket = ++subsetTicket;
  state.subsetWanted = [...names];
  if (!names.length) { state.subset = null; state.subsetNames = []; state.subsetWanted = null; renderAll(); return; }
  const query = `commander=${encodeURIComponent(COMMANDER)}` + names.map((name) => `&card=${encodeURIComponent(name)}`).join("") + (state.universe ? `&profile=${encodeURIComponent(state.universe)}` : "");
  try {
    if (state.gcBand) {
      // The deck filter counts over all decks (or a universe), not inside a band: clear the
      // band explicitly instead of showing the band's label over other numbers.
      Object.assign(state, pickView(StudioGcBand.select(state, "subset", names)));
      await loadPool();
      if (ticket !== subsetTicket) return;
    }
    const info = await api("/api/deck-filter?" + query);
    if (ticket !== subsetTicket) return;
    state.subset = { info, map: new Map(info.cards.map((item) => [item.card_id, item])) };
    state.subsetNames = [...names];
    state.subsetWanted = null;
    renderAll();
  } catch (error) { if (ticket === subsetTicket) state.subsetWanted = null; fail(error); } // the last valid filter stays
}
// The filter control is built once and refreshed in place, so text typed into it survives a redraw.
let deckFilterNode = null;
function deckFilterControl() {
  const names = poolNames();
  if (!deckFilterNode) {
    const input = h("input", { id: "df-card", list: "df-card-list", placeholder: "Karte aus dem Pool …", autocomplete: "off", "aria-label": "Karte für den Deckfilter" });
    const add = () => {
      const value = input.value.trim();
      if (!value) return;
      const name = deckFilterNode.names.get(value.toLowerCase());
      if (!name) { toast(`„${value}“ steht nicht im Kartenpool dieses Commanders. Wähle eine Karte aus der Vorschlagsliste.`); return; }
      input.value = "";
      const chosen = wantedNames();
      if (!chosen.includes(name)) applySubset([...chosen, name]);
    };
    input.addEventListener("keydown", (event) => { if (event.key === "Enter") { event.preventDefault(); add(); } });
    input.addEventListener("change", () => { if (deckFilterNode.names.has(input.value.trim().toLowerCase())) add(); });
    const chips = h("span", { class: "chips", id: "df-chips" });
    const list = h("datalist", { id: "df-card-list" });
    const clear = h("button", { type: "button", id: "df-clear", onclick: () => applySubset([]) }, "Filter löschen");
    const label = h("p", { class: "note", id: "df-label" });
    const root = h("div", { class: "sim-box", id: "deck-filter" },
      h("b", {}, "Nur Decks mit diesen Karten"),
      h("div", { class: "actions" }, input, list, h("button", { type: "button", id: "df-add", onclick: add }, "hinzufügen"), clear),
      chips, label);
    deckFilterNode = { root, chips, list, clear, label, names };
  }
  const node = deckFilterNode;
  node.names = names;
  const chosen = state.subsetNames;
  node.list.replaceChildren(...[...names.values()].map((name) => h("option", { value: name })));
  node.chips.replaceChildren(...chosen.map((name) => h("button", { type: "button", class: "chip on", title: `${name} aus dem Filter nehmen`, onclick: () => applySubset(wantedNames().filter((item) => item !== name)) }, `${name} ✕`)));
  node.clear.disabled = !chosen.length;
  node.label.textContent = state.subset
    ? `${state.subset.info.label}. Die Zahlen unten zählen nur diese Decks. Die gewählten Karten sind „Filterkarte“ und werden nicht gerankt.`
    : "Kein Filter: die Zahlen zählen alle Quelldecks dieses Commanders. Nur Karten aus dem Pool sind wählbar.";
  return node.root;
}
function layerCommand(key) {
  const layer = state.layers && state.layers.layers.find((item) => item.key === key);
  return layer ? layer.command : null;
}
// Without source decks there is no frequency, so no list may look like a ranking.
function emptyDecks(what) {
  const command = layerCommand("decklists");
  return h("div", { class: "empty", id: "no-decks" }, h("b", {}, `${what}: keine Quelldecks vorhanden`),
    `Für ${StudioCommander.shortName(COMMANDER)} sind keine Quelldecks gespeichert. Ohne sie gibt es keine Häufigkeit, und eine Liste nach Namen wäre kein Ranking. Es fehlen die Decklisten.`,
    command ? h("div", {}, h("code", { class: "cmd" }, command)) : null);
}
function sourceDecks() {
  if (state.subset) return state.subset.info.decks;
  if (activeScope()) return state.universeInfo ? state.universeInfo.denominator : 0;
  if (state.countedUniverse && !(state.cohorts[state.cohort] || 0)) return state.countedUniverse.denominator;
  return state.cohorts[state.cohort] || 0;
}
function similarCacheKey() {
  return `${state.deckId || ""}|${state.branch || ""}|${state.changeSeq}|${state.cohort}|${Boolean(state.similarIncludeUnowned)}`;
}
function loadSimilarDecks() {
  const incUnowned = Boolean(state.similarIncludeUnowned);
  const key = similarCacheKey();
  if (state.similarDecks && state.similarDecks.key === key) return;
  if (state.similarDecksBusy === key) return;
  state.similarDecksBusy = key;
  api("/api/similar-decks", "POST", {
    commander: COMMANDER,
    deck_card_ids: [...state.list.keys()],
    cohort: state.cohort,
    n: 20,
    include_unowned: incUnowned,
  }).then((data) => {
    state.similarDecks = { key, data };
    if (state.tab === "similar" || state.tab === "numbers") renderDeck();
  }, (error) => { state.similarDecksBusy = null; fail(error); });
}
function renderDeckStatusBox(body) {
  loadSimilarDecks();
  const shape = state.shape;
  const reference = (state.shapes || []).find((row) => row.cohort === state.cohort) || {};
  const ownNonlandCards = deckCards().filter((card) => card.group !== "Land");
  const ownNonlandTotal = ownNonlandCards.reduce((sum, card) => sum + qty(card.card_id), 0);
  const ownWithRole = ownNonlandCards.filter((card) => card.roles && card.roles.length).reduce((sum, card) => sum + qty(card.card_id), 0);
  const simKey = similarCacheKey();
  const simData = state.similarDecks && state.similarDecks.key === simKey ? state.similarDecks.data : null;
  const simSummary = !simData ? "wird berechnet …"
    : !simData.decks_considered ? "keine Quelldecks in dieser Gruppe"
    : simData.nearest && simData.nearest.length
      ? `Nächstes Quelldeck: ${StudioUI.num(100 * simData.nearest[0].similarity, 1)} % Übereinstimmung (${StudioUI.num(simData.nearest[0].shared, 0)} gemeinsame Karten) · Median über ${StudioUI.num(simData.decks_considered, 0)} Decks: ${simData.median_similarity_all !== null ? StudioUI.pct(simData.median_similarity_all, 1) : "unbekannt"}`
      : "keine Übereinstimmung";
  const combos = state.combos;
  const comboSummary = combos && combos.listed
    ? `${StudioUI.num(combos.complete.length, 0)} vollständig im Deck · ${StudioUI.num(combos.one_missing.length, 0)} mit genau einer fehlenden Karte (von ${StudioUI.num(combos.listed, 0)} gelisteten Kombos)`
    : "keine Kombo-Liste gespeichert";
  const landMed = reference.lands ? `Median ${span(reference.lands)} in „${cohortName(state.cohort)}“ (${StudioUI.num(reference.decks_counted || 0, 0)} Decks)` : "keine Vergleichsdaten";
  const roleMed = reference.role_coverage_median !== undefined && reference.role_coverage_median !== null
    ? `Median ${StudioUI.numFlex(reference.role_coverage_median, 1)} in „${cohortName(state.cohort)}“`
    : "keine Vergleichsdaten";
  body.append(h("div", { class: "sim-box", id: "deck-status-box" },
    h("div", { class: "sim-monitor-head" },
      h("b", {}, "Deck-Zustand (Beobachtung, keine Gesamtnote)"),
      h("button", { type: "button", class: "small", onclick: () => { state.tab = "state"; renderDeck(); } }, "Zustand auf 1 Seite →")),
    h("div", { class: "table-wrap" }, h("table", {}, h("tbody", {},
      h("tr", {}, h("td", {}, "Karten & Länder"), h("td", {}, `${StudioUI.num(deckTotal(), 0)} / 100 Karten · ${StudioUI.num(shape ? shape.lands : 0, 0)} Länder (${landMed})`)),
      h("tr", {}, h("td", {}, "Rollen-Abdeckung"), h("td", {}, `${StudioUI.num(ownWithRole, 0)} von ${StudioUI.num(ownNonlandTotal, 0)} Nicht-Land-Karten mit Rolle (${roleMed})`)),
      h("tr", {}, h("td", {}, "Ähnlichkeit zu Quelldecks"), h("td", {}, simSummary)),
      h("tr", {}, h("td", {}, "Kombos (Spellbook)"), h("td", {}, comboSummary)))))));
}
async function openSourceDeckModal(deckId) {
  try {
    const incUnowned = Boolean(state.similarIncludeUnowned);
    const detail = await api(`/api/deck-browser/source:${encodeURIComponent(deckId)}`);
    const box = $("modal-box"); box.className = "plain";
    const cards = detail.cards || [];
    const ownedRows = cards.filter((c) => c.in_collection);
    const unownedRows = cards.filter((c) => !c.in_collection);
    const makeRow = (c) => {
      const poolCard = c.card_id ? state.byId.get(c.card_id) : null;
      return h("tr", {},
        h("td", { class: "num" }, StudioUI.num(c.quantity || 1, 0)),
        h("td", {}, c.name),
        h("td", {}, c.section || "main"),
        h("td", {}, c.in_collection ? (c.available > 0 ? `im Pool (${StudioUI.num(c.available, 0)} frei)` : "im Pool (0 frei)") : "nicht in Sammlung"),
        h("td", {}, poolCard && poolCard.available > 0 && !qty(poolCard.card_id) ? h("button", { class: "small", type: "button", onclick: () => add(poolCard) }, "+") : null));
    };
    box.replaceChildren(...kids(
      h("h2", {}, detail.name || `Quelldeck ${deckId}`),
      h("p", { class: "note" }, `Plattform: ${detail.platform || "–"} · Kohorte: ${cohortName(detail.cohort || "all")} · Karten: ${StudioUI.num(cards.length, 0)} (${StudioUI.num(ownedRows.length, 0)} in deiner Sammlung, ${StudioUI.num(unownedRows.length, 0)} außerhalb)`),
      detail.url ? h("p", {}, h("a", { href: detail.url, target: "_blank", rel: "noopener noreferrer" }, "Quelldeck extern öffnen ↗")) : null,
      h("h3", {}, `Karten in deiner Sammlung (${StudioUI.num(ownedRows.length, 0)})`),
      h("div", { class: "table-wrap" }, h("table", {},
        h("thead", {}, h("tr", {}, h("th", { class: "num" }, "Anz."), h("th", {}, "Karte"), h("th", {}, "Sektion"), h("th", {}, "Sammlung"), h("th", {}, ""))),
        h("tbody", {}, ownedRows.map(makeRow)))),
      incUnowned && unownedRows.length ? h("details", {},
        h("summary", {}, `Karten außerhalb deiner Sammlung (${StudioUI.num(unownedRows.length, 0)})`),
        h("div", { class: "table-wrap" }, h("table", {},
          h("thead", {}, h("tr", {}, h("th", { class: "num" }, "Anz."), h("th", {}, "Karte"), h("th", {}, "Sektion"), h("th", {}, "Sammlung"), h("th", {}, ""))),
          h("tbody", {}, unownedRows.map(makeRow))))) : null,
      h("div", { class: "actions" }, h("button", { type: "button", onclick: closeModal }, "Schließen"))
    ));
    $("modal").hidden = false;
  } catch (error) { fail(error); }
}
function renderSimilarDecks(body) {
  renderDeckStatusBox(body);
  body.append(h("h3", {}, `Ähnliche Quelldecks (${cohortName(state.cohort)})`));
  loadSimilarDecks();
  const incUnowned = Boolean(state.similarIncludeUnowned);
  const toggleInput = h("input", {
    type: "checkbox",
    id: "similar-include-unowned",
    checked: incUnowned,
    onchange: (event) => {
      state.similarIncludeUnowned = event.target.checked;
      renderDeck();
    },
  });
  body.append(
    h("p", { class: "note", id: "similar-disclosure" }, "Ähnlich heißt gleiche Karten (ohne Standardländer und Commander, Jaccard-Übereinstimmung), nicht erfolgreich. Zeigt, welche Quelldecks deiner aktuellen Liste am nächsten liegen."),
    h("div", { class: "actions" },
      h("label", {}, toggleInput, " Auch Karten außerhalb deiner Sammlung zeigen (nur Ansicht)"),
      h("a", { class: "nav", href: "decks.html" }, "Deck-Browser öffnen →")));
  const key = similarCacheKey();
  const found = state.similarDecks && state.similarDecks.key === key ? state.similarDecks.data : null;
  if (!found) {
    body.append(h("p", { class: "muted", id: "similar-wait" }, "Wird berechnet …"));
    return;
  }
  if (found.empty_reason || !found.decks_considered) {
    body.append(h("p", { class: "muted", id: "similar-empty" }, found.empty_reason || "Keine Quelldecks in dieser Vergleichsgruppe."));
    return;
  }
  if (found.decks_considered < (state.small || 30)) {
    body.append(h("p", { class: "pill warn", id: "similar-small" }, `Kleine Stichprobe: nur ${StudioUI.num(found.decks_considered, 0)} Quelldecks in „${cohortName(state.cohort)}“ (unter ${StudioUI.num(state.small || 30, 0)}).`));
  }
  const simDecks = found.nearest || [];
  if (simDecks.length) {
    body.append(h("div", { class: "table-wrap" }, h("table", { id: "similar-decks-table" },
      h("thead", {}, h("tr", {},
        h("th", {}, "Quelldeck"),
        h("th", {}, "Kohorte"),
        h("th", { class: "num" }, "Übereinstimmung"),
        h("th", { class: "num" }, "Gemeinsam"),
        h("th", { class: "num" }, "Karten (ohne Standardländer)"),
        h("th", {}, ""))),
      h("tbody", {}, simDecks.map((d) => h("tr", {},
        h("td", {}, h("b", {}, d.deck_id), h("span", { class: "muted" }, ` (${d.platform || "Korpus"})`)),
        h("td", {}, cohortName(d.bracket || d.cohort)),
        h("td", { class: "num" }, `${StudioUI.num(100 * d.similarity, 1)} %`),
        h("td", { class: "num" }, StudioUI.num(d.shared, 0)),
        h("td", { class: "num" }, StudioUI.num(d.size, 0)),
        h("td", {}, h("button", { class: "small", type: "button", onclick: () => openSourceDeckModal(d.deck_id) }, "Ansehen"))))))));
  }
  const theyPlay = found.they_play_you_dont || [];
  body.append(h("h4", {}, `In diesen ${StudioUI.num(simDecks.length, 0)} ähnlichen Decks oft gespielt, fehlt in deinem Deck`));
  if (theyPlay.length) {
    body.append(h("div", { class: "table-wrap" }, h("table", { id: "similar-they-play" },
      h("thead", {}, h("tr", {},
        h("th", {}, "Karte"),
        h("th", { class: "num" }, "In ähnlichen Decks (n/N)"),
        h("th", { class: "num" }, "Anteil"),
        h("th", {}, "Sammlung"),
        h("th", {}, ""))),
      h("tbody", {}, theyPlay.map((item) => {
        const poolCard = item.card_id ? state.byId.get(item.card_id) : null;
        const nameEl = h("span", { class: poolCard ? "nm" : "", onclick: () => { if (poolCard) openCard(poolCard); } }, item.name);
        if (poolCard) hoverPreview(nameEl, poolCard);
        return h("tr", {},
          h("td", {}, nameEl),
          h("td", { class: "num" }, `${StudioUI.num(item.hits, 0)}/${StudioUI.num(item.of, 0)}`),
          h("td", { class: "num" }, `${StudioUI.num(100 * item.share, 0)} %`),
          h("td", {}, item.in_pool ? (item.available > 0 ? `frei (${StudioUI.num(item.available, 0)})` : "0 frei") : "nicht in Sammlung"),
          h("td", {}, poolCard && poolCard.available > 0 && !qty(poolCard.card_id) ? h("button", { class: "small", type: "button", onclick: () => add(poolCard) }, "+") : null));
      })))));
  } else {
    body.append(h("p", { class: "muted" }, "Keine weiteren Karten in den ähnlichen Decks."));
  }
  const youPlay = found.you_play_they_dont || [];
  body.append(h("h4", {}, `In deinem Deck, aber selten in diesen ${StudioUI.num(simDecks.length, 0)} ähnlichen Decks`));
  if (youPlay.length) {
    body.append(h("div", { class: "table-wrap" }, h("table", { id: "similar-you-play" },
      h("thead", {}, h("tr", {},
        h("th", {}, "Karte"),
        h("th", { class: "num" }, "In ähnlichen Decks (n/N)"),
        h("th", { class: "num" }, "Anteil"),
        h("th", {}, ""))),
      h("tbody", {}, youPlay.map((item) => {
        const poolCard = item.card_id ? state.byId.get(item.card_id) : null;
        const nameEl = h("span", { class: poolCard ? "nm" : "", onclick: () => { if (poolCard) openCard(poolCard); } }, item.name);
        if (poolCard) hoverPreview(nameEl, poolCard);
        return h("tr", {},
          h("td", {}, nameEl),
          h("td", { class: "num" }, `${StudioUI.num(item.hits, 0)}/${StudioUI.num(item.of, 0)}`),
          h("td", { class: "num" }, `${StudioUI.num(100 * item.share, 0)} %`),
          h("td", {}, poolCard ? h("button", { class: "small", type: "button", onclick: () => remove(poolCard) }, "−") : null));
      })))));
  } else {
    body.append(h("p", { class: "muted" }, "Keine Abweichungen angezeigt."));
  }
}
function renderNumbers(body) {
  renderDeckStatusBox(body);
  body.append(deckFilterControl());
  const shape = state.shape;
  if (!shape) { body.append(h("p", { class: "muted" }, "Wird berechnet.")); return; }
  body.append(h("h3", {}, "Manakurve (ohne Länder)"), ...bars([0, 1, 2, 3, 4, 5, 6, 7].map((key) => shape.curve[String(key)] || 0), ["0", "1", "2", "3", "4", "5", "6", "7+"]),
    h("p", {}, `Durchschnittlicher Manawert der Nichtland-Karten: ${StudioUI.num(shape.mana_value, 2)}`));
  const types = h("div", { class: "table-wrap" }, h("table", {}, h("tbody", {}, GROUPS.filter((group) => shape.types[group]).map((group) => h("tr", {}, h("td", {}, GROUP_NAMES[group]), h("td", { class: "num" }, StudioUI.num(shape.types[group], 0)))))));
  body.append(h("h3", {}, "Kartentypen"), types);
  const colors = h("div", { class: "table-wrap" }, h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Farbe"), h("th", { class: "num" }, "Farbsymbole in Kosten"), h("th", { class: "num" }, "Karten, die die Farbe erzeugen"))),
    h("tbody", {}, ["W", "U", "B", "R", "G", "C"].filter((letter) => shape.pips[letter] || shape.mana_sources[letter]).map((letter) =>
      h("tr", {}, h("td", {}, h("span", { class: "ms ms-" + letter }, letter)), h("td", { class: "num" }, StudioUI.num(shape.pips[letter] || 0, 0)), h("td", { class: "num" }, StudioUI.num(shape.mana_sources[letter] || 0, 0)))))));
  if (state.roles.length) {
    const reference = state.shapes.find((row) => row.cohort === state.cohort) || {};
    const spans = reference.roles || {};
    const ownNonlandCards = deckCards().filter((card) => card.group !== "Land");
    const ownNonlandTotal = ownNonlandCards.reduce((sum, card) => sum + qty(card.card_id), 0);
    const ownWithRole = ownNonlandCards.filter((card) => card.roles && card.roles.length).reduce((sum, card) => sum + qty(card.card_id), 0);
    const poolWithRole = state.pool.filter((card) => card.roles && card.roles.length).length;
    const poolPct = state.pool.length ? StudioUI.num(100 * poolWithRole / state.pool.length, 1) : "0,0";
    const refMed = reference.role_coverage_median !== undefined && reference.role_coverage_median !== null
      ? `Median ${StudioUI.numFlex(reference.role_coverage_median, 1)} Nicht-Land-Karten mit bekannter Rolle pro Quelldeck (${StudioUI.num(reference.decks_counted || 0, 0)} gezählte Decks)`
      : "keine Vergleichsdaten";
    const poolRoleCounts = {};
    for (const c of state.pool) {
      for (const r of (c.roles || [])) poolRoleCounts[r] = (poolRoleCounts[r] || 0) + 1;
    }
    const poolTotalN = state.pool.length;
    body.append(h("h3", {}, "Rollen"),
      h("p", { class: "note", id: "roles-coverage-note" }, `Rollen-Abdeckung: In deinem Deck tragen ${StudioUI.num(ownWithRole, 0)} von ${StudioUI.num(ownNonlandTotal, 0)} Nicht-Land-Karten mindestens eine Rolle · Vergleichsgruppe „${cohortName(state.cohort)}“: ${refMed} · Kartenpool gesamt: ${StudioUI.num(poolWithRole, 0)} von ${StudioUI.num(poolTotalN, 0)} Karten (${poolPct} %).`),
      h("div", { class: "table-wrap" }, h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Rolle"), h("th", { class: "num" }, "Dein Deck"), h("th", { class: "num" }, cohortName(state.cohort)), h("th", { class: "num" }, "Im Pool belegt (n/N)"))),
        h("tbody", {}, state.roles.map((role) => h("tr", {}, h("td", {}, roleName(role)), h("td", { class: "num" }, StudioUI.num(state.deckRoles[role] || 0, 0)), h("td", { class: "num" }, span(spans[role])), h("td", { class: "num" }, `${StudioUI.num(poolRoleCounts[role] || 0, 0)}/${StudioUI.num(poolTotalN, 0)}`)))))),
      h("p", { class: "note" }, "Rollen sind öffentliche Marken der Scryfall-Gemeinschaft (Tagger). Eine Karte kann mehrere Rollen haben, und nicht jede Karte ist markiert. Vergleich: Median und mittlere Hälfte der gewählten Vergleichsgruppe."));
  }
  body.append(h("h3", {}, "Farben"), colors, h("p", { class: "note" }, "Gezählt aus den Kartendaten: Symbole in den Manakosten und Karten, die Mana dieser Farbe erzeugen können. Das ist eine Zählung, keine Bewertung."));
  const dp = shape.draw_probabilities;
  if (dp && dp.opening_7) {
    const pct = (v) => (v === null || v === undefined ? "unbekannt" : StudioUI.pct(v, 1));
    const probTable = h("div", { class: "table-wrap" }, h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, "Ziehfenster"), h("th", { class: "num" }, "Karten (n)"), h("th", { class: "num" }, "≥ 2 Länder"), h("th", { class: "num" }, "3–4 Länder"), h("th", { class: "num" }, "≥ 3 Länder"), h("th", { class: "num" }, "≥ 4 Länder"))),
      h("tbody", {},
        h("tr", {}, h("td", {}, "Starthand"), h("td", { class: "num" }, StudioUI.num(dp.opening_7.draws, 0)), h("td", { class: "num" }, pct(dp.opening_7.at_least_2_lands)), h("td", { class: "num" }, pct(dp.opening_7.between_3_and_4_lands)), h("td", { class: "num" }, pct(dp.opening_7.at_least_3_lands)), h("td", { class: "num" }, pct(dp.opening_7.at_least_4_lands))),
        h("tr", {}, h("td", {}, "Bis Zug 3"), h("td", { class: "num" }, StudioUI.num(dp.turn_3_draw_9.draws, 0)), h("td", { class: "num" }, "–"), h("td", { class: "num" }, "–"), h("td", { class: "num" }, pct(dp.turn_3_draw_9.at_least_3_lands)), h("td", { class: "num" }, pct(dp.turn_3_draw_9.at_least_4_lands))),
        h("tr", {}, h("td", {}, "Bis Zug 4"), h("td", { class: "num" }, StudioUI.num(dp.turn_4_draw_10.draws, 0)), h("td", { class: "num" }, "–"), h("td", { class: "num" }, "–"), h("td", { class: "num" }, pct(dp.turn_4_draw_10.at_least_3_lands)), h("td", { class: "num" }, pct(dp.turn_4_draw_10.at_least_4_lands))))));
    body.append(h("h3", {}, `Land-Ziehwahrscheinlichkeiten (${StudioUI.num(dp.lands, 0)} Länder in ${StudioUI.num(dp.main_cards, 0)} Maindeck-Karten)`), probTable,
      h("p", { class: "note" }, "Exakte hypergeometrische Kombinatorik ohne Mulligan-Heuristik."));
  }
  renderCastability(body, deckDeps("numbers"));
  renderLandAdvisor(body);
  renderCombos(body);
}
// Land advisor: an observation of the mana base against the coloured symbols, next to the
// figures of the chosen comparison group. It never says what to add or cut.
function loadLandAdvisor() {
  const key = `${state.deckId || ""}|${state.branch || ""}|${state.changeSeq}|${state.cohort}`;
  if (state.landAdvisor && state.landAdvisor.key === key) return;
  if (state.landAdvisorBusy === key) return;
  state.landAdvisorBusy = key;
  api("/api/land-advisor", "POST", { cards: entries(), owned_only: true, cohort: state.cohort, min_share: 0.20 }).then((data) => {
    state.landAdvisor = { key, seq: state.changeSeq, cohort: state.cohort, data };
    if (state.tab === "numbers") renderDeck();
  }, (error) => { state.landAdvisorBusy = null; fail(error); });
}
function renderLandAdvisor(body) {
  body.append(h("h3", {}, "Länder im Vergleich zu den Farbsymbolen"));
  loadLandAdvisor();
  const key = `${state.deckId || ""}|${state.branch || ""}|${state.changeSeq}|${state.cohort}`;
  const found = state.landAdvisor && state.landAdvisor.key === key ? state.landAdvisor : null;
  if (!found) { body.append(h("p", { class: "muted", id: "land-advisor-wait" }, "Wird berechnet.")); return; }
  const deck = found.data.deck;
  const group = found.data.groups.find((item) => item.cohort === state.cohort);
  const spanText = (entry, digits = 1) => entry ? `${StudioUI.num(entry.median, digits)} (${StudioUI.num(entry.p25, digits)}–${StudioUI.num(entry.p75, digits)})` : "unbekannt";
  const percent = (value) => value === null || value === undefined ? "keine Symbole" : `${StudioUI.num(100 * value, 0)} %`;
  const shareSpan = (entry) => entry ? `${StudioUI.num(100 * entry.median, 0)} % (${StudioUI.num(100 * entry.p25, 0)}–${StudioUI.num(100 * entry.p75, 0)})` : "unbekannt";
  const groupName = cohortName(state.cohort);
  const swatch = (entry) => h("td", {}, h("span", { class: "ms ms-" + entry.colour }, entry.colour), entry.in_identity ? "" : h("span", { class: "muted", title: "Diese Farbe liegt außerhalb der Farbidentität des Commanders" }, " außerhalb"));
  const own = h("div", { class: "table-wrap" }, h("table", { id: "land-advisor" }, h("thead", {}, h("tr", {}, h("th", {}, "Farbe"), h("th", { class: "num", title: "Farbsymbole in den Kosten der Nicht-Land-Karten" }, "Symbole"), h("th", { class: "num", title: "Anteil an allen Farbsymbolen" }, "Anteil"),
    h("th", { class: "num", title: "Länder, die diese Farbe erzeugen können" }, "Länder"), h("th", { class: "num", title: "Quellen, die keine Länder sind" }, "andere"))),
    h("tbody", {}, deck.colours.map((entry) => h("tr", {}, swatch(entry), h("td", { class: "num" }, StudioUI.num(entry.pips, 0)), h("td", { class: "num" }, percent(entry.pip_share)),
      h("td", { class: "num" }, StudioUI.num(entry.land_sources, 0)), h("td", { class: "num" }, StudioUI.num(entry.other_sources, 0) + (entry.modal_sources ? ` (+${StudioUI.num(entry.modal_sources, 0)} mit Landseite)` : "")))))));
  const compare = group ? h("div", { class: "table-wrap" }, h("table", { id: "land-advisor-group" }, h("thead", {}, h("tr", {}, h("th", {}, "Farbe"), h("th", { class: "num" }, "Symbole"), h("th", { class: "num" }, "Anteil"), h("th", { class: "num" }, "Länder"))),
    h("tbody", {}, deck.colours.map((entry) => {
      const figures = group.colours[entry.colour];
      return h("tr", {}, swatch(entry), h("td", { class: "num" }, figures ? spanText(figures.pips) : "0"),
        h("td", { class: "num" }, figures ? shareSpan(figures.pip_share) : (Object.keys(group.colours).length ? "0 %" : "unbekannt")),
        h("td", { class: "num" }, figures ? spanText(figures.land_sources) : "0"));
    })))) : null;
  const landLine = group && group.lands ? `${StudioUI.num(deck.lands, 0)} Länder im Deck. Vergleich „${groupName}“: Median ${spanText(group.lands)} (in Klammern die mittlere Hälfte), gezählt in ${StudioUI.num(group.decks_counted, 0)} Decks.` : `${StudioUI.num(deck.lands, 0)} Länder im Deck. Für „${groupName}“ liegen keine Vergleichszahlen vor.`;
  body.append(h("p", { id: "land-advisor-lands" }, landLine));
  if (group && group.small) body.append(h("p", { class: "pill warn", id: "land-advisor-small" }, `Nur ${StudioUI.num(group.decks_counted, 0)} Decks in dieser Gruppe (unter ${StudioUI.num(found.data.small_group, 0)}): die Vergleichszahlen sind unsicher.`));
  body.append(own);
  if (compare) body.append(h("p", { class: "note", id: "land-advisor-group-title" }, `Vergleichsgruppe: ${groupName} (Median, mittlere Hälfte in Klammern)`), compare);
  const commanderPips = Object.entries(deck.commander_pips || {});
  body.append(h("p", { id: "land-advisor-commander" }, commanderPips.length ? `Farbsymbole der Kosten des Commanders: ${commanderPips.map(([colour, count]) => `${colour} ${StudioUI.num(count, 0)}`).join(", ")} (nicht in den Zahlen des Decks).` : "Der Commander hat keine Farbsymbole in seinen Kosten (nicht in den Zahlen des Decks)."));
  if (deck.lands_no_mana) body.append(h("p", { class: "note", id: "land-advisor-nomana" }, `Länder, die selbst kein Mana erzeugen: ${StudioUI.num(deck.lands_no_mana, 0)} (laut Kartendaten, zum Beispiel Fetchländer). Sie stehen bei keiner Farbe.`));
  if (deck.lands_unknown_colours) body.append(h("p", { class: "note", id: "land-advisor-unknown" }, `Länder ohne Angabe: ${StudioUI.num(deck.lands_unknown_colours, 0)} (keine Kartendaten zum erzeugten Mana). Unbekannt, nicht als null gezählt.`));
  const landCands = found.data.land_candidates || [];
  body.append(h("h4", {}, `Freie Nicht-Standardländer in deiner Sammlung (≥ 20 % in „${groupName}“, nicht im Deck)`));
  if (landCands.length) {
    const candTable = h("div", { class: "table-wrap" }, h("table", { id: "land-advisor-candidates" },
      h("thead", {}, h("tr", {}, h("th", {}, "Land"), h("th", {}, "Erzeugte Farben"), h("th", { class: "num" }, "Quelldecks (n/N)"), h("th", { class: "num" }, "Anteil"), h("th", { class: "num" }, "frei"), h("th", {}, ""))),
      h("tbody", {}, landCands.map((cand) => {
        const poolCard = state.byId.get(cand.card_id);
        const nameEl = h("span", { class: "nm", onclick: () => { if (poolCard) openCard(poolCard); } }, cand.name);
        if (poolCard) hoverPreview(nameEl, poolCard);
        const colCell = cand.colours === null ? h("span", { class: "muted" }, "unbekannt")
          : cand.colours.length ? cand.colours.map((c) => h("span", { class: "ms ms-" + c }, c))
          : h("span", { class: "muted" }, "farblos / keine");
        return h("tr", { class: cand.small_group ? "low" : "" },
          h("td", {}, nameEl),
          h("td", {}, colCell),
          h("td", { class: "num" }, cand.decks === null ? "unbekannt" : `${StudioUI.num(cand.decks, 0)}/${StudioUI.num(cand.of, 0)}`),
          h("td", { class: "num" }, cand.share === null ? "unbekannt" : `${StudioUI.num(100 * cand.share, 0)} %`),
          h("td", { class: "num" }, StudioUI.num(cand.available, 0)),
          h("td", {}, poolCard ? h("button", { class: "small", type: "button", onclick: () => add(poolCard) }, "+") : null));
      }))));
    body.append(candTable);
  } else {
    body.append(h("p", { class: "muted", id: "land-advisor-candidates-empty" }, "Keine weiteren freien Nicht-Standardländer ab 20 % in dieser Vergleichsgruppe."));
  }
  const lc = found.data.land_cycles;
  if (lc && Array.isArray(lc.cycles)) {
    body.append(
      h("h4", {}, "Länder-Zyklen in Farbidentität (Deck & Pool)"),
      h("p", { class: "note", id: "land-advisor-cycles-summary" }, `Gezählte Zyklus-Länder in der Farbidentität: ${StudioUI.num(lc.in_deck_total, 0)} / ${StudioUI.num(lc.legal_lands_total, 0)} im Deck · ${StudioUI.num(lc.in_pool_extra_total, 0)} / ${StudioUI.num(lc.legal_lands_total, 0)} weitere frei im Pool (${StudioUI.num(lc.in_pool_total, 0)} / ${StudioUI.num(lc.legal_lands_total, 0)} gesamt in Sammlung). Rein deskriptive Bestandszählung über ${StudioUI.num(lc.cycles_total, 0)} gepinnte Zyklen.`));
    const cycleRows = lc.cycles.map((cycle) => {
      const cardNodes = (cycle.cards || []).map((c) => {
        const poolCard = c.card_id ? state.byId.get(c.card_id) : null;
        const nameEl = h("span", { class: poolCard ? "nm" : "", onclick: () => { if (poolCard) openCard(poolCard); } }, c.name);
        if (poolCard) hoverPreview(nameEl, poolCard);
        const colSpans = (c.colours || []).map((col) => h("span", { class: "ms ms-" + col }, col));
        const pillClass = c.in_deck ? "pill good" : c.in_pool_extra ? "pill" : c.in_pool ? "pill warn" : "pill muted";
        const addBtn = c.in_pool_extra && poolCard && !qty(poolCard.card_id)
          ? h("button", { class: "small", type: "button", onclick: () => add(poolCard) }, "+")
          : null;
        return h("span", { class: "cycle-card-item" }, ...colSpans, " ", nameEl, " ", h("span", { class: pillClass }, c.status), addBtn ? " " : null, addBtn);
      });
      return h("tr", {},
        h("td", {}, h("b", {}, cycle.label), h("div", { class: "muted" }, cycle.description)),
        h("td", { class: "num" }, `${StudioUI.num(cycle.in_deck, 0)} / ${StudioUI.num(cycle.total, 0)}`),
        h("td", { class: "num" }, `${StudioUI.num(cycle.in_pool_extra, 0)} / ${StudioUI.num(cycle.total, 0)}`),
        h("td", { class: "num" }, `${StudioUI.num(cycle.in_pool_total, 0)} / ${StudioUI.num(cycle.total, 0)}`),
        h("td", {}, cardNodes.length ? h("div", { class: "chips" }, ...cardNodes) : h("span", { class: "muted" }, "0 / 0 in Farbidentität")));
    });
    body.append(h("div", { class: "table-wrap" }, h("table", { id: "land-advisor-cycles" },
      h("thead", {}, h("tr", {},
        h("th", {}, "Zyklus"),
        h("th", { class: "num" }, "Im Deck (n/N)"),
        h("th", { class: "num" }, "Weitere frei im Pool (n/N)"),
        h("th", { class: "num" }, "Gesamt in Sammlung (n/N)"),
        h("th", {}, "Karten in Farbidentität"))),
      h("tbody", {}, cycleRows))));
  }
  body.append(h("p", { class: "note" }, "Beobachtung, keine Vorschrift. Farbsymbole stehen in den Manakosten der Nicht-Land-Karten; ein Hybrid-Symbol zählt für beide Farben, Generisches und X zählen nicht, eine geteilte Karte zählt beide Hälften. Die Kosten des Commanders zählen nicht mit. Ein Land zählt für jede Farbe, die es erzeugt. Quellen, die keine Länder sind (Manasteine, Kreaturen), stehen getrennt. Vergleich: Median und mittlere Hälfte der Quelldecks der gewählten Vergleichsgruppe."));
}
// Listed combos of the commander against the deck: complete, or one card short. A count
// over the source's list, never a rating; without a stored list the section says so.
function comboLine(combo) {
  return combo.cards.map((name) => name === combo.missing ? `[fehlt: ${name}]` : name).join(" + ");
}
function renderCombos(body) {
  const combos = state.combos;
  body.append(h("h3", {}, "Kombos im Deck"));
  if (combos && !(combos.commanders || []).length) {
    body.append(h("p", { class: "muted", id: "combos-empty" }, "Kein Commander gewählt. Die Kombo-Liste gehört zu einem Commander."));
    return;
  }
  const poolShells = (combos && combos.pool_shells) || [];
  const tplSlots = (combos && combos.template_slots) || [];
  if (!combos || (!combos.listed && !poolShells.length && !tplSlots.length)) {
    body.append(h("p", { class: "muted", id: "combos-empty" }, "Für diesen Commander ist keine Kombo-Liste gespeichert. Das heißt nicht, dass das Deck keine Kombos hat."));
    return;
  }
  const names = poolNames();
  const row = (combo) => {
    const known = combo.missing ? names.has(combo.missing.toLowerCase()) : null;
    const card = known ? state.pool.find((item) => item.name.toLowerCase() === combo.missing.toLowerCase()) : null;
    const where = combo.missing === undefined ? null
      : !known ? "nicht in deiner Sammlung"
      : card && card.available > 0 ? "im Pool, frei" : "im Pool, keine freie Kopie";
    return h("tr", {},
      h("td", {}, comboLine(combo), where === null ? null : h("div", { class: "muted" }, `Fehlende Karte: ${where}`)),
      h("td", { class: "num" }, StudioUI.num(combo.num_decks, 0)),
      h("td", {}, card && card.available > 0 && !qty(card.card_id) ? h("button", { class: "small", type: "button", title: `${card.name} ins Deck nehmen`, onclick: () => add(card) }, "+") : null));
  };
  const compCands = (combos && combos.completion_candidates) || [];
  if (compCands.length) {
    body.append(
      h("h4", {}, `Kombo-Vervollständiger (${StudioUI.num(compCands.length, 0)} freie Pool-Karten ergänzen 1-Karten-Lücken)`),
      h("div", { class: "table-wrap" }, h("table", { id: "combos-completion-assistant" },
        h("thead", {}, h("tr", {},
          h("th", {}, "Freie Pool-Karte"),
          h("th", { class: "num" }, "Ergänzte Kombos"),
          h("th", { class: "num" }, "Ergänzte Shells"),
          h("th", { class: "num" }, "Max. Spellbook-Decks"),
          h("th", {}, ""))),
        h("tbody", {}, compCands.slice(0, 15).map((cand) => {
          const pCard = state.byId.get(cand.card_id);
          return h("tr", {},
            h("td", { class: pCard ? "name" : "", onclick: () => { if (pCard) openCard(pCard); } }, cand.name),
            h("td", { class: "num" }, StudioUI.num(cand.completed_combos_count, 0)),
            h("td", { class: "num" }, StudioUI.num(cand.completed_shells_count, 0)),
            h("td", { class: "num" }, StudioUI.num(cand.max_num_decks, 0)),
            h("td", {}, pCard && pCard.available > 0 && !qty(pCard.card_id) ? h("button", { type: "button", class: "small", onclick: () => add(pCard) }, "+") : null));
        }))))
    );
  }
  if (combos.listed) {
    body.append(h("p", {}, `${StudioUI.num(combos.complete.length, 0)} von ${StudioUI.num(combos.listed, 0)} gelisteten Kombos sind vollständig im Deck, bei ${StudioUI.num(combos.one_missing.length, 0)} fehlt genau eine Karte.`));
    if (combos.complete.length) {
      body.append(h("div", { class: "table-wrap" }, h("table", { id: "combos-complete" }, h("thead", {}, h("tr", {}, h("th", {}, "Vollständig im Deck"), h("th", { class: "num" }, "Commander Spellbook global (alle Commander)"), h("th", {}, ""))), h("tbody", {}, combos.complete.map(row)))));
    }
    if (combos.one_missing.length) {
      const inPool = [];
      const outsidePool = [];
      for (const combo of combos.one_missing) {
        const known = combo.missing ? names.has(combo.missing.toLowerCase()) : false;
        if (known) inPool.push(combo); else outsidePool.push(combo);
      }
      inPool.sort((a, b) => {
        const ca = state.pool.find((item) => item.name.toLowerCase() === a.missing.toLowerCase());
        const cb = state.pool.find((item) => item.name.toLowerCase() === b.missing.toLowerCase());
        const fa = ca && ca.available > 0 ? 0 : 1;
        const fb = cb && cb.available > 0 ? 0 : 1;
        return fa - fb || b.num_decks - a.num_decks;
      });
      if (inPool.length) {
        body.append(h("div", { class: "table-wrap" }, h("table", { id: "combos-missing" }, h("thead", {}, h("tr", {}, h("th", {}, "Es fehlt genau eine Karte (in deiner Sammlung)"), h("th", { class: "num" }, "Commander Spellbook global (alle Commander)"), h("th", {}, ""))), h("tbody", {}, inPool.map(row)))));
      }
      if (outsidePool.length) {
        body.append(h("details", { id: "combos-missing-unowned" },
          h("summary", {}, `Fehlende Karte nicht in deiner Sammlung (${StudioUI.num(outsidePool.length, 0)} Kombos)`),
          h("div", { class: "table-wrap" }, h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Es fehlt genau eine Karte (nicht in deiner Sammlung)"), h("th", { class: "num" }, "Commander Spellbook global (alle Commander)"), h("th", {}, ""))), h("tbody", {}, outsidePool.map(row))))));
      }
    }
    const sources = combos.sources || [];
    body.append(h("p", { class: "note", id: "combos-source" }, sources.length ? `Quelle der Kombo-Liste: ${sources.map((item) => item.title + (item.snapshot_date ? ` (Stand ${item.snapshot_date})` : ` (eingelesen ${item.imported_at.slice(0, 10)})`)).join("; ")}.` : "Quelle der Kombo-Liste: nicht bekannt."));
    body.append(h("p", { class: "note" }, combos.meaning));
  }
  if (poolShells.length) {
    body.append(h("h4", {}, `Spellbook Pool-Shells (${StudioUI.num(poolShells.length, 0)} vollständig im legalen Pool)`),
      h("div", { class: "table-wrap" }, h("table", { id: "combos-pool-shells" },
        h("thead", {}, h("tr", {}, h("th", {}, "Shell / Karten"), h("th", {}, "Status im Deck"), h("th", {}, "Ergebnis"))),
        h("tbody", {}, poolShells.map((sh) => h("tr", {},
          h("td", {}, `#${sh.shell_id}: ${(sh.uses || []).join(" + ")}`),
          h("td", {}, sh.complete_in_deck ? h("span", { class: "pill good" }, "vollständig")
            : (sh.missing_from_deck || []).map((name) => {
              const info = (sh.available_missing || {})[name];
              const card = info && info.card_id ? state.byId.get(info.card_id) : null;
              return h("span", { class: "inline-item mr-2" }, `fehlt: ${name}`, card && info.available > 0 && !qty(card.card_id) ? h("button", { type: "button", class: "small ml-1", onclick: () => add(card) }, "+") : null);
            })),
          h("td", {}, (sh.produces || []).slice(0, 3).join("; ") || "–")))))));
  }
  if (tplSlots.length) {
    const shownTpl = tplSlots.slice(0, 30);
    const formatN = (obj) => obj && obj.hits !== null && obj.hits !== undefined ? `${StudioUI.num(obj.hits, 0)}/${StudioUI.num(obj.total, 0)}` : `unbekannt (N=${obj && obj.total !== undefined ? StudioUI.num(obj.total, 0) : "?"})`;
    const tplRows = [];
    for (const sh of shownTpl) {
      for (const slot of sh.slots || []) {
        const concrete = (sh.uses || []).map((u) => (sh.in_deck || []).includes(u) ? u : `[fehlt: ${u}]`).join(" + ");
        const statusEl = slot.status === "UNKNOWN"
          ? h("span", { class: "pill warn", title: slot.reason || "Query offline nicht auswertbar" }, "Erfüllung unbekannt")
          : slot.fulfilled_in_deck ? h("span", { class: "pill good", title: slot.partially_checked ? "Commander-/Zonen-Bedingung nicht geprüft" : "" }, slot.partially_checked ? "im Deck erfüllt (nur Kartentext-Abfrage geprüft)" : "im Deck erfüllt")
          : h("span", { class: "pill" }, `im Deck < ${StudioUI.num(slot.quantity, 0)}`);
        const matchesEl = slot.status === "OK" && slot.matches_in_pool && slot.matches_in_pool.length
          ? h("details", {}, h("summary", {}, `${StudioUI.num(slot.matches_in_pool_total, 0)} Treffer im Pool`),
            h("div", {}, slot.matches_in_pool.slice(0, 10).map((m) => {
              const card = state.byId.get(m.card_id);
              return h("span", { class: "inline-item mr-2" },
                m.name,
                card && !m.in_deck && m.available > 0 && !qty(card.card_id)
                  ? h("button", { type: "button", class: "small ml-1", onclick: () => add(card) }, "+") : null);
            })))
          : null;
        tplRows.push(h("tr", {},
          h("td", {}, `#${sh.shell_id}: ${concrete}`, h("div", { class: "muted" }, `${slot.name} (×${StudioUI.num(slot.quantity, 0)})`)),
          h("td", {}, statusEl, slot.scryfall_query ? h("div", { class: "muted" }, slot.scryfall_query) : null, matchesEl),
          h("td", { class: "num" }, formatN(slot.deck)),
          h("td", { class: "num" }, formatN(slot.pool)),
          h("td", { class: "num" }, formatN(slot.collection))));
      }
    }
    body.append(h("h4", {}, `Kombo-Template-Slots (#1417 · ${StudioUI.num(tplSlots.length, 0)} Shells im Pool)`),
      h("div", { class: "table-wrap" }, h("table", { id: "combos-template-slots" },
        h("thead", {}, h("tr", {}, h("th", {}, "Shell & Template-Slot"), h("th", {}, "Status & Treffer"), h("th", { class: "num" }, "Deck (n/N)"), h("th", { class: "num" }, "Pool (n/N)"), h("th", { class: "num" }, "Sammlung (n/N)"))),
        h("tbody", {}, tplRows))),
      h("p", { class: "note" }, "Offline-Auswertung der Template-Queries gegen gespeicherte Kartendaten. Fehlende oder nicht unterstützte Query-Operatoren werden ausdrücklich als „Erfüllung unbekannt“ ausgewiesen (nie als 0)."));
  }
}
const ENGINE_STATUS = { PASS: ["good", "bestanden"], FAIL: ["bad", "nicht bestanden"], UNKNOWN: ["warn", "nicht geprüft"] };
async function runEngineCheck() {
  const seq = state.changeSeq;
  state.engineCheck = { busy: true };
  renderDeck();
  try {
    const result = await api("/api/engine-check", "POST", { cards: entries(), owned_only: true });
    state.engineCheck = { result, seq };
  } catch (error) { state.engineCheck = null; fail(error); }
  renderDeck();
}
function renderEngineCheck(body) {
  const check = state.engineCheck;
  const box = h("section", { id: "engine-check" }, h("h3", {}, "Prüfung durch die Engine"));
  body.append(box);
  box.append(h("button", { type: "button", id: "engine-check-run", disabled: !!(check && check.busy), onclick: runEngineCheck }, check && check.busy ? "Wird geprüft ..." : "Gegen die Engine-Kartenliste prüfen"));
  if (!check || check.busy) {
    box.append(h("p", { class: "note" }, "Prüft vor einer Partie, was der Spielstarter prüft, und gleicht das Deck mit der gespeicherten Kartenliste der Engine ab (keine Live-Abfrage der Engine; Java und Bridge-Datei werden auf Vorhandensein geprüft). Den Deck-Import selbst macht die Engine erst beim Spielstart. Es wird keine Partie gestartet."));
    return;
  }
  const result = check.result;
  const [tone, word] = ENGINE_STATUS[result.status] || ["warn", "nicht geprüft"];
  box.append(h("p", { class: "pill " + tone, id: "engine-check-status" }, result.status === "UNKNOWN" ? result.headline : `${word}: ${result.headline}`));
  if (check.seq !== state.changeSeq) box.append(h("p", { class: "note", id: "engine-check-stale" }, "Das Deck wurde seit dieser Prüfung geändert. Bitte noch einmal prüfen."));
  if (!result.engine_ready) box.append(h("p", { class: "note" }, `Die Engine ist auf diesem Rechner nicht bereitgestellt. Ein Deck ohne Befund gilt dann nicht als geprüft. ${result.engine_reason || ""}`));
  const construction = result.construction;
  if (result.precondition_failures.length) box.append(h("div", { class: "issue error", id: "engine-check-preconditions" }, h("b", {}, "Voraussetzung nicht erfüllt"), h("div", {}, result.precondition_failures.join(" ")), h("div", {}, "Der Spielstarter kann dieses Deck nicht prüfen, solange das so ist.")));
  if (construction.status === "FAIL") box.append(h("div", { class: "issue error" }, h("b", {}, "Deck-Aufbau"), h("div", {}, construction.text)));
  else if (construction.status === "NOT_CHECKED") { if (!result.precondition_failures.length) box.append(h("div", { class: "issue warning" }, h("b", {}, "Deck-Aufbau nicht geprüft"), h("div", {}, construction.text))); }
  else box.append(h("p", {}, "Deck-Aufbau (Prüfsumme, Einzelkarten, Farbidentität): ohne Befund."));
  if (!result.cards_consulted) box.append(h("div", { class: "issue warning" }, h("b", {}, "Kartenliste der Engine nicht lesbar"), h("div", {}, "Welche Karten die Engine nicht laden kann, ist unbekannt.")));
  if (result.unsupported_by_engine.length) box.append(h("div", { class: "issue error" }, h("b", {}, "Die Engine kann diese Karten nicht laden"), h("div", {}, result.unsupported_by_engine.join(", "))));
  if (result.unknown_to_pilots.length) box.append(h("div", { class: "issue error" }, h("b", {}, "Dem Kartenwissen der Spieler-KI fehlen diese Karten"), h("div", {}, result.unknown_to_pilots.join(", "))));
  box.append(h("p", { class: "note" }, result.meaning));
}
function renderCheck(body) {
  body.append(h("h3", {}, "Datenprüfung (gespeicherte Fakten)"));
  if (!state.issues.length) { body.append(h("p", {}, "Die Datenprüfung findet nichts.")); }
  for (const issue of state.issues) {
    body.append(h("div", { class: "issue " + issue.severity }, h("b", {}, ISSUE_NAMES[issue.code] || issue.code), h("div", {}, issue.message)));
  }
  body.append(h("p", { class: "note" }, "Diese Prüfung liest gespeicherte Kartendaten: 100 Karten, Commander, Farbidentität, Einzelkarten-Regel, Legalität, Besitz und freie Kopien. Verbindlich für das Spiel ist erst die Prüfung durch die Regel-Engine."));
  renderEngineCheck(body);
  const currentCards = [...state.commanderIds.map((id) => state.byId.get(id)), ...deckCards()].filter(Boolean);
  const notReady = currentCards.filter((card) => card.sim_status && card.sim_status !== "OK");
  body.append(h("h3", {}, "Simulator-Bereitschaft"));
  if (!notReady.length) {
    body.append(h("p", {}, `Alle ${StudioUI.num(currentCards.length, 0)} eindeutigen Karten im aktuellen Deck haben XMage-Card-Facts und Pilot-Wissen (OK).`));
  } else {
    body.append(h("p", {}, `${StudioUI.num(notReady.length, 0)} Karte(n) im aktuellen Deck sind im Simulator-Vorfilter noch nicht vollständig hinterlegt:`),
      h("div", {}, notReady.map((card) => h("div", { class: "issue warning" },
        h("b", { title: card.sim_status }, StudioUI.simStatusLabel(card.sim_status)),
        h("div", {}, `${card.name}: ${StudioUI.simStatusLabel(card.sim_status)}.`)))));
  }
}
function span(entry) { return entry ? `${StudioUI.numFlex(entry.median)} (${StudioUI.numFlex(entry.p25)} bis ${StudioUI.numFlex(entry.p75)})` : "unbekannt"; }
function renderCompare(body) {
  body.append(deckFilterControl());
  const shape = state.shape || {};
  const visibleShapes = state.shapes.filter((row) => !isRedundantCohort(row.cohort));
  const table = h("div", { class: "table-wrap" }, h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Gruppe"), h("th", { class: "num" }, "Decks"), h("th", { class: "num" }, "Länder"), h("th", { class: "num" }, "Kreaturen"), h("th", { class: "num" }, "Ø Manawert"))),
    h("tbody", {}, h("tr", {}, h("td", {}, h("b", {}, "Dein Deck")), h("td", {}), h("td", { class: "num" }, shape.lands == null ? "" : StudioUI.num(shape.lands, 0)), h("td", { class: "num" }, shape.creatures == null ? "" : StudioUI.num(shape.creatures, 0)), h("td", { class: "num" }, shape.mana_value == null ? "" : StudioUI.num(shape.mana_value, 2))),
      visibleShapes.map((row) => h("tr", { class: row.decks < state.small ? "low" : "" }, h("td", {}, cohortName(row.cohort)), h("td", { class: "num" }, row.decks_counted === row.decks ? StudioUI.num(row.decks, 0) : `${StudioUI.num(row.decks_counted, 0)} von ${StudioUI.num(row.decks, 0)}`),
        h("td", { class: "num" }, span(row.lands)), h("td", { class: "num" }, span(row.creatures)), h("td", { class: "num" }, span(row.mana_value)))))));
  body.append(h("h3", {}, "Aufbau im Vergleich"), table, h("p", { class: "note" }, "Median und mittlere Hälfte der Quelldecks. Gelb: Gruppe mit weniger als 30 Decks, sehr unsicher. Länder nach Vorderseite gezählt."));
  const auditSlot = h("div", { id: "corpus-audit-slot" });
  body.append(auditSlot);
  if (typeof mountCorpusAudit === "function") mountCorpusAudit(auditSlot, { h, api, cohortName, commander: StudioCommander.current });
  const scope = activeScope();
  const counted = !scope && !state.subset && state.countedUniverse && !(state.cohorts[state.cohort] || 0);
  const name = (scope ? scope.label : counted ? countedName() : cohortName(state.cohort)) + (state.subset ? `, ${state.subset.info.label}` : "");
  if (!sourceDecks()) { body.append(emptyDecks("Oft gespielt und selten gespielt")); return; }
  // Only cards with a known count are ranked; a card without a count is not "rarely played".
  const candidates = state.pool.filter((card) => !qty(card.card_id) && !state.commanderIds.includes(card.card_id) && card.available > 0 && !card.excluded && !card.basic && displayFreq(card).hits !== null && displayFreq(card).hits > 0)
    .sort((a, b) => displayFreq(b).hits - displayFreq(a).hits || a.name.localeCompare(b.name)).slice(0, 20);
  // Ascending by hits, but a card with unknown hits (no count, or a filter card) is not "rarely
  // played": it sorts last and is labelled unknown by displayFreqText.
  const byRarity = (a, b) => {
    const x = displayFreq(a).hits, y = displayFreq(b).hits;
    if (x === null && y === null) return a.name.localeCompare(b.name);
    if (x === null) return 1;
    if (y === null) return -1;
    return x - y;
  };
  const rare = deckCards().filter((card) => !card.basic).sort(byRarity).slice(0, 20);
  const listing = (cards, withAdd) => h("div", {}, cards.map((card) => {
    const label = h("span", { class: "nm", onclick: () => openCard(card) }, card.name); hoverPreview(label, card);
    return h("div", { class: "row" }, label, h("span", { class: "muted" }, displayFreqText(card)),
      withAdd ? h("button", { class: "small", type: "button", onclick: () => add(card) }, "+") : h("button", { class: "small", type: "button", onclick: () => remove(card) }, "−"));
  }));
  body.append(h("h3", {}, `Oft gespielt (${name}), frei in deiner Sammlung, nicht im Deck`), candidates.length ? listing(candidates, true) : h("p", { class: "muted" }, "Keine freie Karte mit bekannter Häufigkeit."),
    h("h3", {}, `Im Deck, selten gespielt (${name})`), listing(rare, false),
    h("p", { class: "note" }, "Häufigkeit sagt, was andere spielen, nicht, was stärker ist. Unbekannte Werte stehen am Ende der Liste „selten gespielt“: unbekannt ist nicht selten."),
    ...(state.universeInfo && state.universeInfo.subset_note ? [h("p", { class: "note" }, state.universeInfo.subset_note)] : []));
}
// The base of the variant diff: the previous revision of this variant, else the latest
// revision of the main variant. Never the revision that is open itself.
async function diffCandidates() {
  const deck = state.decks.find((item) => item.deck_id === state.deckId);
  const branches = deck ? deck.branches : [];
  const options = [];
  let historyRows = null;
  try {
    const rows = await api(`/api/decks/${encodeURIComponent(state.deckId)}/history`);
    historyRows = rows;
    const current = rows.find((row) => row.revision_id === state.baseRevision);
    if (current && current.parent_revision_id) options.push({ rev: current.parent_revision_id, label: `Vorheriger Stand der Variante ${state.branch}` });
  } catch (error) { /* without history only the variants are offered */ }
  try {
    const baseResp = await api(`/api/diff-baselines?${StudioCommander.query}`);
    for (const item of baseResp.baselines || []) {
      options.push({ rev: item.revision_id, label: item.label });
    }
  } catch (error) { /* optional repo baselines */ }
  const main = branches.find((item) => item.branch === "main");
  if (state.branch !== "main" && main) options.push({ rev: main.revision_id, label: "Neuester Stand der Variante main" });
  for (const item of branches) if (item.revision_id !== state.baseRevision || state.dirty) options.push({ rev: item.revision_id, label: `Variante ${item.branch} (aktuell gespeichert)` });
  if (historyRows) {
    for (const row of historyRows) options.push({ rev: row.revision_id, label: `Gespeicherter Stand ${row.created_at ? row.created_at.slice(0, 16).replace("T", " ") : ""}${row.note ? " – " + row.note : ""}` });
  }
  for (const other of state.decks) {
    if (other.deck_id === state.deckId) continue;
    for (const item of other.branches || []) options.push({ rev: item.revision_id, label: `Anderes Deck: ${other.name || other.deck_id} (${item.branch})` });
  }
  const seen = new Set();
  return options.filter((item) => !seen.has(item.rev) && seen.add(item.rev) && (item.rev !== state.baseRevision || state.dirty));
}
async function renderDiff(body) {
  const token = state.renderToken;
  const options = await diffCandidates();
  if (token !== state.renderToken) return;
  if (!options.length) {
    body.append(h("div", { class: "empty", id: "no-diff" }, h("b", {}, "Es gibt nichts zu vergleichen"),
      "Diese Variante hat noch keinen früheren Stand, und es gibt keine andere Variante. Speichere einen Stand oder lege mit „Neue Variante“ eine zweite an."));
    return;
  }
  if (!options.some((item) => item.rev === state.diffBaseRev)) state.diffBaseRev = options[0].rev;
  const select = h("select", {
    id: "diff-base",
    onchange: async (event) => {
      state.diffBaseRev = event.target.value;
      state.diffData = null;
      renderDeck();
    },
  }, ...options.map((item) => h("option", { value: item.rev, selected: item.rev === state.diffBaseRev }, `${item.label} (${item.rev.slice(0, 20)})`)));
  body.append(h("div", { class: "actions" }, h("label", {}, "Vergleichsbasis: ", select)));
  const box = h("div", {}, h("p", { class: "muted" }, "Berechnet Differenz..."));
  body.append(box);
  try {
    const diff = await api("/api/diff", "POST", { base_revision_id: state.diffBaseRev, cards: entries(), cohort: state.cohort });
    box.replaceChildren();
    box.append(h("p", {}, `Neu: +${StudioUI.num(diff.added_slots, 0)} Slots (${StudioUI.num(diff.added.length, 0)} Karten) · Entfernt: −${StudioUI.num(diff.removed_slots, 0)} Slots (${StudioUI.num(diff.removed.length, 0)} Karten)`));
    const bs = diff.base_shape || {}, ts = diff.target_shape || {};
    const shapeTable = h("div", { class: "table-wrap" }, h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, "Kennzahl"), h("th", { class: "num" }, "Basis"), h("th", { class: "num" }, "Aktuell"), h("th", { class: "num" }, "Delta"))),
      h("tbody", {},
        [["Länder", bs.lands ?? 0, ts.lands ?? 0], ["Kreaturen", bs.creatures ?? 0, ts.creatures ?? 0], ["Nichtländer", bs.nonland ?? 0, ts.nonland ?? 0]].map(([label, bVal, tVal]) =>
          h("tr", {}, h("td", {}, label), h("td", { class: "num" }, StudioUI.num(bVal, 0)), h("td", { class: "num" }, StudioUI.num(tVal, 0)), h("td", { class: "num" }, (tVal - bVal > 0 ? "+" : "") + StudioUI.num(tVal - bVal, 0)))),
        h("tr", {}, h("td", {}, "Ø Manawert"), h("td", { class: "num" }, bs.mana_value == null ? "–" : StudioUI.num(bs.mana_value, 2)), h("td", { class: "num" }, ts.mana_value == null ? "–" : StudioUI.num(ts.mana_value, 2)),
          h("td", { class: "num" }, bs.mana_value !== null && ts.mana_value !== null ? ((ts.mana_value - bs.mana_value >= 0 ? "+" : "") + StudioUI.num(ts.mana_value - bs.mana_value, 2)) : "–")))));
    box.append(h("h3", {}, "Struktur-Delta"), shapeTable);
    const bdp = bs.draw_probabilities && bs.draw_probabilities.opening_7 ? bs.draw_probabilities : null;
    const tdp = ts.draw_probabilities && ts.draw_probabilities.opening_7 ? ts.draw_probabilities : null;
    if (bdp && tdp) {
      const pct = (v) => (v === null || v === undefined ? "–" : StudioUI.pct(v, 1));
      const dpDelta = (bVal, tVal) => (bVal === null || tVal === null || bVal === undefined || tVal === undefined ? "–" : ((tVal - bVal >= 0 ? "+" : "") + StudioUI.pct(tVal - bVal, 1)));
      const probDiffTable = h("div", { class: "table-wrap" }, h("table", {},
        h("thead", {}, h("tr", {}, h("th", {}, "Land-Ziehfenster"), h("th", { class: "num" }, "Basis"), h("th", { class: "num" }, "Aktuell"), h("th", { class: "num" }, "Delta"))),
        h("tbody", {},
          [["Starthand ≥ 3 Länder (7)", bdp.opening_7.at_least_3_lands, tdp.opening_7.at_least_3_lands],
           ["Starthand 3–4 Länder (7)", bdp.opening_7.between_3_and_4_lands, tdp.opening_7.between_3_and_4_lands],
           ["Bis Zug 4 ≥ 4 Länder (10)", bdp.turn_4_draw_10.at_least_4_lands, tdp.turn_4_draw_10.at_least_4_lands]].map(([label, bV, tV]) =>
            h("tr", {}, h("td", {}, label), h("td", { class: "num" }, pct(bV)), h("td", { class: "num" }, pct(tV)), h("td", { class: "num" }, dpDelta(bV, tV)))))));
      box.append(h("h3", {}, "Land-Ziehwahrscheinlichkeiten-Delta"), probDiffTable);
    }
    if (diff.role_deltas && Object.keys(diff.role_deltas).length) {
      const roleRows = Object.entries(diff.role_deltas).sort((a, b) => roleName(a[0]).localeCompare(roleName(b[0])));
      const roleDiffTable = h("div", { class: "table-wrap" }, h("table", {},
        h("thead", {}, h("tr", {}, h("th", {}, "Rolle (Tagger)"), h("th", { class: "num" }, "Basis"), h("th", { class: "num" }, "Aktuell"), h("th", { class: "num" }, "Delta"))),
        h("tbody", {}, roleRows.map(([rKey, vals]) => h("tr", {},
          h("td", {}, roleName(rKey)),
          h("td", { class: "num" }, StudioUI.num(vals.base, 0)),
          h("td", { class: "num" }, StudioUI.num(vals.target, 0)),
          h("td", { class: "num" }, (vals.delta > 0 ? "+" : "") + StudioUI.num(vals.delta, 0)))))));
      box.append(h("h3", {}, "Rollen-Delta"), roleDiffTable);
    }
    box.append(...diffImpactNodes(h, diff, {
      cohortLabel: cohortName(state.cohort), roleName,
      open: (cardId) => { const c = state.byId.get(cardId); if (c) openCard(c); },
    }));
    const seriesData = await deckSeriesLoad(api, state.deckId);
    if (token !== state.renderToken) return;
    box.append(deckSeriesDiffEvidence(h, seriesData, state.diffBaseRev, state.dirty ? null : state.baseRevision));
  } catch (error) {
    box.replaceChildren(h("p", { class: "muted" }, "Differenz nicht lesbar: " + StudioUI.germanError(error)));
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
          api("/api/simulations?" + StudioCommander.query).catch(() => []),
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
function pairedDeps() {
  return {
    h,
    api,
    entries,
    fail,
    toast,
    openCard,
    poolCardById: (id) => state.byId.get(id),
    commander: COMMANDER,
    commanderQuery: StudioCommander.query,
    decks: () => state.decks,
    currentDeckId: () => state.deckId,
    currentRevision: () => state.baseRevision,
    activePaired: () => state.activePaired,
    setActivePaired: (v) => { state.activePaired = v; },
    pairedHistory: () => state.pairedHistory,
    readinessAudit: () => state.readinessAudit,
    setReadinessAudit: (v) => { state.readinessAudit = v; },
    pollPaired,
    rerender: () => { if (state.tab === "sim") renderDeck(); },
    token: () => state.renderToken,
    isCurrent: (tok) => tok === state.renderToken && state.tab === "sim",
  };
}
function pollPaired(seriesId) {
  if (state.pairedPollTimer) clearTimeout(state.pairedPollTimer);
  state.pairedPollTimer = setTimeout(async () => {
    try {
      const job = await api("/api/simulations/paired/" + encodeURIComponent(seriesId));
      state.activePaired = job;
      if (job.status === "completed" || job.status === "cancelled" || job.status === "failed") {
        const [pairedList, recordedGames] = await Promise.all([
          api("/api/simulations/paired").catch(() => []),
          api("/api/games").catch(() => []),
        ]);
        state.pairedHistory = pairedList || [];
        state.recordedGames = recordedGames || [];
        if (state.tab === "sim") {
          if (typeof refreshPairedSlots === "function" && document.getElementById("paired-monitor-slot")) {
            refreshPairedSlots(pairedDeps());
          } else {
            renderDeck();
          }
        }
      } else {
        pollPaired(seriesId);
        if (state.tab === "sim") {
          if (typeof refreshPairedSlots === "function" && document.getElementById("paired-monitor-slot")) {
            refreshPairedSlots(pairedDeps());
          } else {
            renderDeck();
          }
        }
      }
    } catch (err) {
      console.warn("Poll paired error:", err);
    }
  }, 1200);
}
function renderSimulations(body) {
  body.append(h("div", { class: "actions" }, h("a", { class: "nav", href: "partie.html" }, "Partien-Ansicht & Neue Einzelpartie →")));

  if (typeof renderPairedComparisonSection === "function") {
    renderPairedComparisonSection(body, pairedDeps());
  }

  const outcomesSlot = h("div", { id: "card-outcomes-slot" });
  body.append(outcomesSlot);
  if (typeof renderCardOutcomes === "function") {
    renderCardOutcomes(outcomesSlot, {
      h,
      api,
      deckId: state.deckId,
      baseRevision: state.baseRevision,
      dirty: state.dirty,
      openCard: (name) => {
        const card = Array.from(state.byId.values()).find((c) => c.name === name);
        if (card) {
          openCard(card);
        } else {
          toast(`„${name}“ ist im aktuellen Deck-Katalog nicht geladen.`);
        }
      },
    });
  }

  // Batch simulation launcher & live monitor
  const bBox = h("div", { class: "sim-box" },
    h("h3", { class: "mt-0" }, "Neue Simulationsserie starten"),
    h("p", { class: "note" }, "Spielt mehrere vollständige 4-Spieler-Partien nacheinander in prozessisolierten Durchläufen mit deterministischen Seeds. Berechnet Siegrate mit Nenner und 95%-Wilson-Konfidenzintervall.")
  );

  const curRev = state.baseRevision || (state.deckId ? `rev@${state.deckId}/main/current` : "rev@deck/main/current");
  const revInput = h("input", { type: "text", value: curRev, class: "rev-input", title: "Deck-Revision" });
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
  const seedInput = h("input", { type: "number", value: "1000", class: "seed-input" });

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
        fail(err);
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

    const monitor = h("div", { class: "sim-monitor" },
      h("div", { class: "sim-monitor-head" },
        h("b", {}, `Serie „${b.pod}“: ${StudioUI.num(b.games_completed, 0)} von ${StudioUI.num(b.games_planned, 0)} Partien abgeschlossen (${StudioUI.num(pct, 0)} %)`),
        h("span", { class: "pill " + (isRunning ? "warn" : b.status === "completed" ? "good" : "bad") }, statusText)
      ),
      // the bar follows the games the engine has played (plus failed ones); the headline counts finished results
      h("progress", { value: b.games_played !== null && b.games_played !== undefined && Number.isFinite(Number(b.games_played)) ? Math.min(b.games_planned, Number(b.games_played) + Number(b.games_failed || 0)) : b.games_completed, max: b.games_planned, title: "Fortschrittsbalken: gespielte plus gescheiterte Partien" }),
      h("p", { class: "note note-compact" }, seriesPlayedText(b.games_played, b.games_planned, b.games_completed, false, isRunning))
    );

    if (b.bridge_qualification && b.bridge_qualification.status === "BRIDGE_AHEAD_OF_QUALIFICATION") {
      monitor.append(h("div", { class: "mt-2" }, h("span", { class: "pill warn pill-inline", title: ["Rohcode: BRIDGE_AHEAD_OF_QUALIFICATION", b.bridge_qualification.reason].filter(Boolean).join(" · ") }, "Bridge: Engine-Stand noch nicht qualifiziert · nicht durch versiegelte Epoche abgedeckt")));
    }

    if (isRunning) {
      const cancelBtn = h("button", {
        type: "button",
        class: "danger mt-2",
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
      const qualStates = s.bridge_qualification_states || (b.bridge_qualification && b.bridge_qualification.status ? [b.bridge_qualification.status] : []);
      const bridgeSha = s.bridge_jar_sha256 || b.bridge_jar_sha256 || null;
      const epochLabel = s.covered_by_sealed_epoch ? "versiegelt" : (qualStates.join(", ") || "nicht versiegelt");
      const sumBox = h("div", { class: "sim-summary" },
        h("h4", {}, "Ergebnis der Serie"),
        h("div", { class: "sim-grid" },
          h("div", {}, h("span", { class: "muted" }, "Siege: "), h("b", {}, `${StudioUI.numFlex(s.wins_fractional, 1)} / ${StudioUI.num(s.games_completed, 0)}`)),
          h("div", {}, h("span", { class: "muted" }, "Siegrate: "), h("b", {}, s.win_rate !== null ? `${StudioUI.num(s.win_rate_percent, 1)} %` : "–")),
          h("div", {}, h("span", { class: "muted" }, "95 %-CI (Wilson): "), h("b", {}, ci.lower_percent !== undefined ? `[${StudioUI.num(ci.lower_percent, 1)} %, ${StudioUI.num(ci.upper_percent, 1)} %]` : "–")),
          h("div", {}, h("span", { class: "muted" }, "Ø Runden: "), h("b", {}, s.mean_rounds == null ? "–" : StudioUI.numFlex(s.mean_rounds, 1))),
          h("div", {}, h("span", { class: "muted" }, "Bridge-JAR: "), h("code", { title: bridgeSha || "" }, bridgeSha ? String(bridgeSha).slice(0, 12) : "–")),
          h("div", {}, h("span", { class: "muted" }, "Epoche: "), h("b", {}, epochLabel))
        ),
        b.run_id ? h("p", { class: "note note-compact" }, `Dauerhaft im Store hinterlegt unter ID: `, h("code", {}, b.run_id)) : null
      );
      monitor.append(sumBox);
    }

    if (b.games && b.games.length) {
      const bTable = h("div", { class: "table-wrap" }, h("table", { class: "mt-2" },
        h("thead", {}, h("tr", {}, h("th", {}, "Partie"), h("th", { class: "num" }, "Seed"), h("th", { class: "num" }, "Runden"), h("th", {}, "Ergebnis"), h("th", {}, ""))),
        h("tbody", {}, b.games.map((g) => {
          const outcome = g.status === "finished" ? (g.candidate_won ? "Sieg Sitz 1" : `Niederlage (Sieger: Sitz ${(g.winner_seats || []).map((x) => x + 1).join(", ") || "–"})`) : "Fehlgeschlagen";
          return h("tr", {},
            h("td", {}, h("code", {}, g.game_id)),
            h("td", { class: "num" }, StudioUI.num(g.seed, 0)),
            h("td", { class: "num" }, g.rounds ? StudioUI.num(g.rounds, 0) : "–"),
            h("td", {}, outcome),
            h("td", {}, h("a", { href: `partie.html?partie=${encodeURIComponent(g.game_id)}` }, "Ansehen →"))
          );
        }))
      ));
      monitor.append(bTable);
    }

    bBox.append(monitor);
  }

  body.append(bBox);
  if (state.recordedGames && state.recordedGames.length) {
    const gTable = h("div", { class: "table-wrap" }, h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, "Partie"), h("th", { class: "num" }, "Seed"), h("th", { class: "num" }, "Entscheidungen"), h("th", {}, "Bridge-JAR"), h("th", {}, "Status / Sieger"), h("th", {}, ""))),
      h("tbody", {}, state.recordedGames.slice(0, 15).map(recordedGameRow))));
    body.append(h("h3", {}, "Aufgezeichnete Einzelpartien"), gTable);
  }
  if (!state.simulations || !state.simulations.length) {
    body.append(h("p", { class: "muted" }, "Keine Batch-Simulationsläufe im Store hinterlegt."));
    return;
  }
  const byPod = new Map();
  for (const run of state.simulations) {
    // one row per pod, opponent set and table size (#1688): two tables under one pod name are two rows
    const pod = String(run.pod || "unbekannt");
    const pKey = JSON.stringify([pod, run.opponent_set_hash || null, run.table_size ?? null]);
    const table = run.opponent_set_hash ? `${(run.opponent_ids || []).join(", ")} · ${run.table_size ?? "?"} Sitze` : null;
    if (!byPod.has(pKey)) byPod.set(pKey, { pod, table, known: Boolean(run.opponent_set_hash), runs: 0, planned: 0, completed: 0, wins: 0, roundsNum: 0, roundsDen: 0, allSealed: true, states: new Set() });
    const agg = byPod.get(pKey);
    agg.runs += 1;
    agg.planned += Number(run.games_planned || 0);
    const gc = Number(run.games_completed || 0);
    agg.completed += gc;
    agg.wins += Number(run.wins_fractional || 0);
    if (run.mean_rounds != null && gc > 0) { agg.roundsNum += Number(run.mean_rounds) * gc; agg.roundsDen += gc; }
    if (!run.covered_by_sealed_epoch) agg.allSealed = false;
    agg.states.add(String(run.bridge_qualification_state || "UNKNOWN"));
  }
  const podRows = [...byPod.values()].sort((a, b) => a.pod.localeCompare(b.pod, "de") || Number(b.known) - Number(a.known) || String(a.table || "").localeCompare(String(b.table || ""), "de")).map((agg) => {
    const wr = agg.completed > 0 ? `${StudioUI.num((100 * agg.wins) / agg.completed, 1)} %` : "unbekannt";
    const mr = agg.roundsDen > 0 ? StudioUI.numFlex(agg.roundsNum / agg.roundsDen, 1) : "unbekannt";
    const ep = agg.allSealed ? "versiegelt" : (agg.states.has("BRIDGE_AHEAD_OF_QUALIFICATION") ? "Engine-Stand noch nicht qualifiziert" : [...agg.states].join(", "));
    return h("tr", {},
      h("td", {}, h("b", {}, agg.pod), " · ", agg.known ? agg.table : unknownOpponentsCaveat(agg.runs)),
      h("td", { class: "num" }, StudioUI.num(agg.runs, 0)),
      h("td", { class: "num" }, `${StudioUI.num(agg.completed, 0)} / ${StudioUI.num(agg.planned, 0)}`),
      h("td", { class: "num" }, StudioUI.numFlex(agg.wins, 1)),
      h("td", { class: "num" }, wr),
      h("td", { class: "num" }, mr),
      h("td", {}, ep));
  });
  const podMatrixTable = h("div", { class: "table-wrap" }, h("table", { id: "pod-matchup-matrix" },
    h("thead", {}, h("tr", {}, h("th", {}, "Pod / Tisch"), h("th", { class: "num" }, "Läufe"), h("th", { class: "num" }, "Spiele (n / N)"), h("th", { class: "num" }, "Siege"), h("th", { class: "num" }, "Siegrate"), h("th", { class: "num" }, "Ø Runden"), h("th", {}, "Epochen-Stand"))),
    h("tbody", {}, podRows)));
  body.append(h("h3", {}, "Pod-Matchup-Übersicht (aggregiert je Tisch)"), podMatrixTable,
    h("p", { class: "note" }, "Eine Zeile je Pod, Gegnersatz und Tischgröße: Läufe gegen verschiedene Tische werden nie zusammengezählt. Läufe ohne gespeicherten Gegnersatz (vor #1688) stehen in einer eigenen Zeile „Gegnersatz unbekannt“: das ist keine Kohorte, ihre Läufe können gegen verschiedene Gegner gespielt haben; Läufe vor #1658 spielten möglicherweise gegen einen Ersatz-Tisch."));
  const runTable = h("div", { class: "table-wrap" }, h("table", {},
    h("thead", {}, h("tr", {}, h("th", {}, "Pod"), h("th", {}, "Engine-Pin"), h("th", {}, "Bridge-JAR"), h("th", {}, "Epoche"), h("th", {}, "Pilot"), h("th", { class: "num" }, "Spiele"), h("th", { class: "num" }, "Siege"), h("th", { class: "num" }, "Siegrate"), h("th", { class: "num" }, "Ø Runden"))),
    h("tbody", {}, state.simulations.map((run) => h("tr", {},
      h("td", {}, h("b", {}, run.pod)),
      h("td", {}, h("code", {}, run.engine_pin)),
      h("td", {}, h("code", { title: run.bridge_jar_sha256 || "" }, run.bridge_jar_sha256 ? String(run.bridge_jar_sha256).slice(0, 12) : "–")),
      h("td", {}, run.covered_by_sealed_epoch ? "versiegelt" : (run.bridge_qualification_state || "unbekannt")),
      h("td", {}, run.pilot_policy),
      h("td", { class: "num" }, `${StudioUI.num(run.games_completed, 0)}/${StudioUI.num(run.games_planned, 0)}`),
      h("td", { class: "num" }, StudioUI.numFlex(run.wins_fractional, 1)),
      h("td", { class: "num" }, run.win_rate === null ? "unbekannt" : `${StudioUI.num(100 * run.win_rate, 1)} %`),
      h("td", { class: "num" }, run.mean_rounds == null ? "unbekannt" : StudioUI.numFlex(run.mean_rounds, 1)))))));
  body.append(h("h3", {}, "4P-Simulationsläufe"), runTable,
    h("p", { class: "note" }, "Ergebnisse aus echten XMage-Regelkern-Spielen, gebunden an Deck, Engine-Pin, Bridge-JAR, Pilot-Policy und Seeds. Läufe mit BRIDGE_AHEAD_OF_QUALIFICATION oder UNKNOWN sind nicht von der versiegelten Epoche abgedeckt. Kein Beleg für reale Tisch-Siegraten. Exakte Handverweildauer: unbekannt (nicht gemessen)."));
  for (const run of state.simulations) {
    const inDeckCards = (run.cards || []).filter((c) => !c.card_id || qty(c.card_id) > 0 || state.commanderIds.includes(c.card_id));
    if (!inDeckCards.length) continue;
    const cTable = h("div", { class: "table-wrap" }, h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, "Karte"), h("th", { class: "num" }, "Spiele angeboten"), h("th", { class: "num" }, "Spiele gewirkt"), h("th", { class: "num" }, "ungespielt geblieben"), h("th", { class: "num" }, "Ø 1. Runde"))),
      h("tbody", {}, inDeckCards.slice(0, 25).map((c) => h("tr", {},
        h("td", { class: "name", onclick: () => { const card = c.card_id ? state.byId.get(c.card_id) : null; if (card) openCard(card); } }, c.card_name),
        h("td", { class: "num" }, `${StudioUI.num(c.games_offered, 0)}/${StudioUI.num(c.games_completed, 0)}`),
        h("td", { class: "num" }, `${StudioUI.num(c.games_cast_after_offer, 0)}/${StudioUI.num(c.games_offered, 0)}`),
        h("td", { class: "num" }, StudioUI.num(c.games_rotted, 0)),
        h("td", { class: "num" }, c.mean_first_cast_round === null ? "–" : StudioUI.num(c.mean_first_cast_round, 1)))))));
    body.append(h("h3", {}, `Karten-Angebote im Pod „${run.pod}“ (${StudioUI.num(run.games_completed, 0)} Spiele)`), cTable);
  }
}
// the reservation of a row of runs without a stored opponent set (#1688; builder.unknown_opponents_caveat)
function unknownOpponentsCaveat(runs) {
  return runs === 1 ? "Gegnersatz unbekannt: ein Lauf, Gegner nicht gespeichert" : "Gegnersatz unbekannt: mehrere Läufe, möglicherweise verschiedene Gegner";
}
function renderDeck() {
  state.renderToken = (state.renderToken || 0) + 1;
  const tabs = [
    ["list", "Liste"],
    ["state", "Zustand"],
    ["numbers", "Zahlen"],
    ["evidence", "Belege"],
    ["plan", "Bauplan"],
    ["packages", "Pakete & Upgrade"],
    ["check", "Prüfung"],
    ["facts", "Bracket & Lücken"],
    ["tokens", "Tokens"],
    ["compare", "Vergleich"],
    ["similar", "Ähnliche Decks"],
    ["diff", "Varianten-Diff"],
    ["modules", "Module"],
    ["primer", "Primer"],
    ["cut", "Kürzen"],
    ["sim", "Simulation"],
  ];
  // Two groups keep tabs readable: looking at the deck (Analyse) and working on it (Arbeiten).
  const workTabs = new Set(["compare", "similar", "diff", "modules", "primer", "cut", "sim"]);
  const tabButton = ([key, label]) => h("button", { type: "button", class: "chip" + (state.tab === key ? " on" : ""), "aria-pressed": state.tab === key, onclick: () => { state.tab = key; renderDeck(); } }, label);
  const tabGroup = (name, items) => h("div", { class: "tab-group", role: "group", "aria-label": name }, h("span", { class: "tab-group-label" }, name), ...items.map(tabButton));
  $("deck-tabs").replaceChildren(
    tabGroup("Analyse", tabs.filter(([key]) => !workTabs.has(key))),
    tabGroup("Arbeiten", tabs.filter(([key]) => workTabs.has(key))));
  const body = $("deck-body"); body.replaceChildren();
  const planPkgDeps = (tabKey) => ({
    h, api, entries, fail, roleName, openCard, add, remove, cohortName,
    poolCardById: (id) => state.byId.get(id),
    cohort: () => state.cohort,
    commander: COMMANDER,
    token: () => state.renderToken,
    isCurrent: (tok) => tok === state.renderToken && state.tab === tabKey,
  });
  ({
    list: renderList,
    state: renderOverview,
    numbers: renderNumbers,
    plan: (b) => renderBuildPlanTab(b, planPkgDeps("plan")),
    packages: (b) => renderPackagesUpgradeTab(b, planPkgDeps("packages")),
    check: renderCheck,
    facts: renderFacts,
    tokens: renderTokens,
    evidence: renderEvidence,
    compare: renderCompare,
    similar: renderSimilarDecks,
    diff: renderDiff,
    modules: renderModules,
    primer: renderPrimer,
    cut: renderCut,
    sim: renderSimulations,
  })[state.tab](body);
}
function renderTokens(body) {
  const tok = state.renderToken;
  const wrap = h("div", { class: "section" });
  body.append(wrap);
  const currentCards = entries();
  if (!currentCards.length) {
    wrap.replaceChildren(
      h("h3", {}, "Token-Übersicht (lokaler Scryfall-Snapshot)"),
      h("p", { class: "muted" }, "Keine Karten im aktuellen Deck.")
    );
    return;
  }
  wrap.replaceChildren(
    h("h3", {}, "Token-Übersicht (lokaler Scryfall-Snapshot)"),
    StudioUI.loading("Token-Verknüpfungen laden …")
  );
  api("/api/tokens", "POST", { cards: currentCards, owned_only: state.ownedOnly }).then((res) => {
    if (tok !== state.renderToken || state.tab !== "tokens") return;
    const c = res.counts || {};
    const oracleCnt = c.deck_cards_with_oracle || { numerator: 0, denominator: 0 };
    const creatorCnt = c.resolved_creator_cards || { numerator: 0, denominator: 0 };
    const tokenList = res.tokens || [];
    const unresolved = res.unresolved_creators || [];

    const summaryBar = h("div", { class: "summary-bar" },
      h("span", {}, `Karten mit Oracle-Daten: ${StudioUI.num(oracleCnt.numerator, 0)} / ${StudioUI.num(oracleCnt.denominator, 0)}`),
      h("span", {}, `Aufgelöste Erzeuger: ${StudioUI.num(creatorCnt.numerator, 0)} / ${StudioUI.num(creatorCnt.denominator, 0)}`),
      h("span", {}, `Erzeugte Token-Typen: ${StudioUI.num(c.distinct_tokens || 0, 0)}`),
      h("span", {}, `Nicht ableitbare Erzeuger (unbekannt): ${StudioUI.num(c.unresolved_creator_cards || 0, 0)}`)
    );

    let onlyCreatureCreators = Boolean(state.tokenCreatureOnly);
    const bodyHost = h("div", {});

    const drawTokensBody = () => {
      const shownTokens = onlyCreatureCreators
        ? tokenList.filter((t) => Boolean(t.has_creature_creator))
        : tokenList;

      const filterBar = h("div", { class: "chips", role: "group", "aria-label": "Token-Erzeuger filtern" },
        h("button", {
          type: "button",
          class: "chip" + (onlyCreatureCreators ? " on" : ""),
          "aria-pressed": String(onlyCreatureCreators),
          title: "Zeigt nur Token-Typen, die mindestens eine Kreatur im Deck erzeugt (relevant für Kreaturen-Zauber-Auslöser wie Chulane)",
          onclick: () => {
            onlyCreatureCreators = !onlyCreatureCreators;
            state.tokenCreatureOnly = onlyCreatureCreators;
            drawTokensBody();
          },
        }, "nur Kreaturen-Erzeuger"),
        onlyCreatureCreators
          ? h("span", { class: "muted" }, `${StudioUI.num(shownTokens.length, 0)} von ${StudioUI.num(tokenList.length, 0)} Token-Typen`)
          : null
      );

      const tokenSection = shownTokens.length
        ? h("div", { class: "table-wrap" }, h("table", {},
            h("thead", {}, h("tr", {},
              h("th", {}, "Token"),
              h("th", {}, "Typ"),
              h("th", { class: "num" }, "P/T"),
              h("th", {}, "Farben"),
              h("th", {}, "Regeltext"),
              h("th", {}, "Auslöser"),
              h("th", {}, "Erzeugende Karten im Deck")
            )),
            h("tbody", {}, ...shownTokens.map((t) => {
              const totalCreators = Number(t.creator_count || (t.creating_cards || []).length || 0);
              const creatureCreators = Number(t.creature_creator_count || 0);
              const triggerText = creatureCreators > 0
                ? `Kreatur (${StudioUI.num(creatureCreators, 0)}/${StudioUI.num(totalCreators, 0)})`
                : `Nicht-Kreatur (0/${StudioUI.num(totalCreators, 0)})`;
              return h("tr", {},
                h("td", {}, h("b", {}, t.name)),
                h("td", {}, t.type_line || "–"),
                h("td", { class: "num" }, t.pt || "–"),
                h("td", {}, t.colors || "farblos"),
                h("td", { class: "muted" }, t.oracle_text || (t.detail_status === "PARTIAL_ALL_PARTS" ? "Detaildaten nicht im lokalen Token-Bestand" : "–")),
                h("td", { title: creatureCreators > 0 ? "Mindestens ein Erzeuger ist ein Kreaturen-Zauberspruch" : "Kein Erzeuger ist ein Kreaturen-Zauberspruch" },
                  h("span", { class: "badge" + (creatureCreators > 0 ? "" : " dim") }, triggerText)
                ),
                h("td", {}, ...(t.creating_cards || []).map((cr, idx) => {
                  const cardObj = state.byId.get(cr.card_id);
                  const label = `${cr.name}${cr.quantity > 1 ? ` (${StudioUI.num(cr.quantity, 0)}x)` : ""}${cr.is_creature ? " [Kreatur]" : ""}`;
                  const link = h("button", {
                    type: "button",
                    class: "link",
                    title: cr.is_creature ? "Kreaturen-Zauberspruch" : "Kein Kreaturen-Zauberspruch",
                    onclick: () => { if (cardObj) openCard(cardObj); },
                  }, label);
                  return idx > 0 ? h("span", {}, ", ", link) : link;
                }))
              );
            }))
          ))
        : h("p", { class: "muted" }, onlyCreatureCreators
            ? "Keine Token-Verknüpfung durch eine Kreaturen-Karte im aktuellen Deck."
            : "Keine aufgelösten Token-Verknüpfungen für die aktuellen Deck-Karten im lokalen Scryfall-Snapshot.");

      const unresolvedSection = unresolved.length
        ? h("div", { class: "section" },
            h("h4", {}, `Nicht ableitbare Token-Erzeuger (${StudioUI.num(unresolved.length, 0)} Karten — Status: unbekannt)`),
            h("div", { class: "table-wrap" }, h("table", {},
              h("thead", {}, h("tr", {},
                h("th", {}, "Karte"),
                h("th", { class: "num" }, "Menge"),
                h("th", {}, "Status"),
                h("th", {}, "Grund")
              )),
              h("tbody", {}, ...unresolved.map((u) => {
                const cardObj = state.byId.get(u.card_id);
                return h("tr", {},
                  h("td", { class: "name", onclick: () => { if (cardObj) openCard(cardObj); } }, u.name),
                  h("td", { class: "num" }, StudioUI.num(u.quantity, 0)),
                  h("td", {}, "unbekannt"),
                  h("td", { class: "muted" }, u.reason)
                );
              }))
            ))
          )
        : h("p", { class: "muted" }, "Keine unaufgelösten Token-Erzeuger im aktuellen Deck (0 Karten mit Status unbekannt).");

      bodyHost.replaceChildren(filterBar, tokenSection, unresolvedSection);
    };

    drawTokensBody();
    wrap.replaceChildren(
      h("h3", {}, "Token-Übersicht (lokaler Scryfall-Snapshot)"),
      h("p", { class: "muted" }, "Abgeleitet aus den all_parts-Token-Verknüpfungen und Token-Datensätzen des lokalen Scryfall-Snapshots (offline, ohne Netz-Abfrage). Karten ohne ableitbare Verknüpfung werden als unbekannt ausgewiesen und nie geraten."),
      summaryBar,
      bodyHost
    );
  }).catch((err) => {
    wrap.replaceChildren(h("p", { class: "bad" }, StudioUI.germanError(err)));
  });
}
function renderMarkdownSafe(text) {
  const clean = String(text || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n").trim();
  if (!clean) return [h("p", { class: "muted" }, "Noch kein Primer-Text eingetragen.")];
  const nodes = [];
  let listItems = [];
  let codeLines = null;
  const flushList = () => {
    if (listItems.length) {
      nodes.push(h("ul", {}, ...listItems.map((it) => h("li", {}, it))));
      listItems = [];
    }
  };
  for (const rawLine of clean.split("\n")) {
    const trimmed = rawLine.trim();
    if (trimmed.startsWith("```")) {
      flushList();
      if (codeLines === null) codeLines = [];
      else {
        nodes.push(h("pre", {}, h("code", {}, codeLines.join("\n"))));
        codeLines = null;
      }
      continue;
    }
    if (codeLines !== null) {
      codeLines.push(rawLine);
      continue;
    }
    if (!trimmed) {
      flushList();
      continue;
    }
    if (trimmed.startsWith("### ")) {
      flushList();
      nodes.push(h("h5", {}, trimmed.slice(4)));
    } else if (trimmed.startsWith("## ")) {
      flushList();
      nodes.push(h("h4", {}, trimmed.slice(3)));
    } else if (trimmed.startsWith("# ")) {
      flushList();
      nodes.push(h("h3", {}, trimmed.slice(2)));
    } else if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      listItems.push(trimmed.slice(2));
    } else {
      flushList();
      nodes.push(h("p", {}, rawLine));
    }
  }
  flushList();
  if (codeLines !== null && codeLines.length) {
    nodes.push(h("pre", {}, h("code", {}, codeLines.join("\n"))));
  }
  return nodes;
}
function renderPrimer(body) {
  if (!state.deckId) {
    body.append(h("p", { class: "muted" }, "Wähle oder erstelle zuerst ein Deck, um den Primer zu bearbeiten."));
    return;
  }
  const tok = state.renderToken;
  const wrap = h("div", { class: "section" });
  body.append(wrap);
  wrap.replaceChildren(h("h3", {}, "Deck-Primer (Spielplan & Notizen)"), StudioUI.loading("Primer lädt …"));
  api(`/api/decks/${encodeURIComponent(state.deckId)}/primer`).then((res) => {
    if (tok !== state.renderToken || state.tab !== "primer") return;
    state.primerText = res.content || "";
    const previewBox = h("div", { class: "card-box" }, ...renderMarkdownSafe(state.primerText));
    const area = h("textarea", {
      id: "primer-editor",
      rows: 10,
      placeholder: `# Spielplan\n- Frühe Mana-Entwicklung\n- ${StudioCommander.shortName(COMMANDER)} schützen & Kartenfluss sichern`,
      "aria-label": "Deck-Primer (Markdown)",
      oninput: () => {
        previewBox.replaceChildren(...renderMarkdownSafe(area.value));
      },
    }, state.primerText);
    const metaSpan = h("span", { class: "muted" }, res.updated_at ? `Zuletzt gespeichert: ${res.updated_at}` : "Noch nicht gespeichert");
    const saveBtn = h("button", { type: "button", class: "primary", onclick: async () => {
      try {
        const saved = await api(`/api/decks/${encodeURIComponent(state.deckId)}/primer`, "PUT", { content: area.value });
        state.primerText = saved.content || "";
        metaSpan.textContent = `Zuletzt gespeichert: ${saved.updated_at} (${StudioUI.num(state.primerText.length, 0)} Zeichen)`;
        toast("Primer gespeichert.");
      } catch (err) { fail(err); }
    } }, "Primer speichern");
    wrap.replaceChildren(
      h("h3", {}, "Deck-Primer (Spielplan & Notizen)"),
      h("p", { class: "muted" }, "Der Primer ist am Deck verankert (bleibt über alle neuen Stände und Varianten hinweg erhalten) und beeinflusst weder Tierliste noch Stärke-Index. Im Export-Dialog kann er optional als //-Kommentarblock vorangestellt werden."),
      area,
      h("div", { class: "actions" }, saveBtn, metaSpan),
      h("h4", {}, "Vorschau (Markdown)"),
      previewBox
    );
  }).catch((err) => {
    wrap.replaceChildren(h("p", { class: "bad" }, StudioUI.germanError(err)));
  });
}
function renderModules(body) {
  if (!state.deckId) {
    body.append(h("p", { class: "muted" }, "Wähle oder erstelle zuerst ein Deck, um Deck-Module zu verwalten."));
    return;
  }
  const tok = state.renderToken;
  const wrap = h("div", { class: "section" });
  body.append(wrap);
  const reload = async () => {
    wrap.replaceChildren(h("h3", {}, "Deck-Module (Kern + Strategie-Pakete)"), StudioUI.loading("Module laden …"));
    try {
      const res = await api(`/api/decks/${encodeURIComponent(state.deckId)}/modules`);
      if (tok !== state.renderToken || state.tab !== "modules") return;
      const mods = res.modules || [];
      if (!state.selectedModuleIds) {
        const firstCore = mods.find((m) => m.role === "core");
        const firstPkg = mods.find((m) => m.role === "package");
        state.selectedModuleIds = new Set([firstCore && firstCore.module_id, firstPkg && firstPkg.module_id].filter(Boolean));
      } else {
        const validIds = new Set(mods.map((m) => m.module_id));
        state.selectedModuleIds = new Set([...state.selectedModuleIds].filter((id) => validIds.has(id)));
      }
      const nameInput = h("input", { type: "text", placeholder: "Modulname (z. B. Kern oder Paket A)", "aria-label": "Modulname" });
      const roleSelect = h("select", { "aria-label": "Modul-Rolle" },
        h("option", { value: "core" }, "Kern-Modul (core)"),
        h("option", { value: "package" }, "Strategie-Paket (package)"));
      const saveBtn = h("button", { type: "button", class: "chip", onclick: async () => {
        const name = nameInput.value.trim();
        if (!name) { toast("Bitte einen Modulnamen eingeben."); return; }
        try {
          const saved = await api(`/api/decks/${encodeURIComponent(state.deckId)}/modules`, "POST", {
            name,
            role: roleSelect.value,
            cards: entries(),
          });
          if (saved.module && saved.module.module_id) state.selectedModuleIds.add(saved.module.module_id);
          toast(`Modul „${name}“ gespeichert (${StudioUI.num(deckTotal(), 0)} Karten).`);
          reload();
        } catch (err) { fail(err); }
      } }, "Arbeitsliste als Modul speichern");
      const seedBtn = h("button", { type: "button", class: "chip", onclick: async () => {
        try {
          const seeded = await api(`/api/decks/${encodeURIComponent(state.deckId)}/modules/seed`, "POST", {
            cards: entries(),
            core_name: "Kern",
            package_name: "Paket A",
          });
          state.selectedModuleIds = new Set((seeded.modules || []).map((m) => m.module_id));
          toast("Arbeitsliste in „Kern“ (Commander + Länder) und „Paket A“ (Nicht-Länder) aufgeteilt.");
          reload();
        } catch (err) { fail(err); }
      } }, "Arbeitsliste in Kern + Paket A aufteilen");

      const loadCompiledIntoDiff = (comp) => {
        if (!comp || !Array.isArray(comp.cards) || !comp.cards.length) {
          toast("Kompilierte Liste ist leer.");
          return;
        }
        state.list.clear();
        state.commanderIds = [];
        for (const c of comp.cards) {
          if (c.zone === "commander") state.commanderIds.push(c.card_id);
          else state.list.set(c.card_id, Number(c.quantity || 1));
        }
        if (state.baseRevision) state.diffBaseRev = state.baseRevision;
        markDirty();
        state.tab = "diff";
        renderAll();
        toast(`Kompilierte Liste (${StudioUI.num(comp.total_cards, 0)} Karten) in Varianten-Diff geladen.`);
      };

      const compileOut = h("div", { class: "section" });
      const runCompile = async (saveRev, openInDiff = false) => {
        const chosen = [...state.selectedModuleIds];
        if (!chosen.length) { toast("Bitte mindestens ein Kern-Modul und ein Paket auswählen."); return; }
        compileOut.replaceChildren(StudioUI.loading("Kompiliere Module …"));
        try {
          const comp = await api(`/api/decks/${encodeURIComponent(state.deckId)}/modules/compile`, "POST", {
            module_ids: chosen,
            owned_only: $("f-free") ? $("f-free").checked : true,
            save: Boolean(saveRev),
          });
          if (openInDiff) {
            loadCompiledIntoDiff(comp);
            return;
          }
          const statusCls = comp.valid ? "ok" : "bad";
          const statusTxt = comp.valid
            ? `Gültiges 100-Karten-Deck (${StudioUI.num(comp.total_cards, 0)} / ${StudioUI.num(comp.target_cards, 0)} Karten)`
            : `Prüfung fehlgeschlagen (${StudioUI.num(comp.total_cards, 0)} / ${StudioUI.num(comp.target_cards, 0)} Karten)`;
          const issueNodes = (comp.issues || []).map((iss) =>
            h("li", { class: iss.severity === "error" ? "bad" : "warn" }, `${iss.message}`));
          const exportArea = h("textarea", { rows: 6, readonly: true, "aria-label": "Kompilierte Deckliste" }, comp.export ? comp.export.moxfield : "");
          compileOut.replaceChildren(
            h("h4", {}, "Kompilierungs-Ergebnis"),
            h("p", {},
              h("span", { class: "pill " + statusCls }, statusTxt),
              " ",
              h("span", { class: "muted" }, `Ziel-Variante: ${comp.branch}`),
              comp.saved && comp.revision_id ? h("span", { class: "pill ok ml-1" }, `Gespeichert: ${comp.revision_id}`) : ""),
            issueNodes.length ? h("ul", {}, ...issueNodes) : h("p", { class: "muted" }, "Keine Konstruktions- oder Kollisionsfehler gefunden."),
            h("div", { class: "actions" },
              h("button", { type: "button", class: "chip", onclick: () => loadCompiledIntoDiff(comp) }, "Mit aktuellem Stand vergleichen")
            ),
            h("label", {}, "Text-Export (Moxfield / Studio-Import):", exportArea)
          );
          if (comp.saved) {
            toast(`Kompiliertes Deck als Variante „${comp.branch}“ gespeichert.`);
            await loadDecks();
          }
        } catch (err) {
          compileOut.replaceChildren();
          fail(err);
        }
      };

      const modTable = mods.length
        ? h("div", { class: "table-wrap" }, h("table", {},
            h("thead", {}, h("tr", {},
              h("th", {}, "Wahl"),
              h("th", {}, "Modul"),
              h("th", {}, "Rolle"),
              h("th", { class: "num" }, "Karten"),
              h("th", {}, "Aktionen"))),
            h("tbody", {}, ...mods.map((m) => h("tr", {},
              h("td", {}, h("input", {
                type: "checkbox",
                checked: state.selectedModuleIds.has(m.module_id),
                "aria-label": `Modul ${m.name} wählen`,
                onchange: (ev) => {
                  if (ev.target.checked) state.selectedModuleIds.add(m.module_id);
                  else state.selectedModuleIds.delete(m.module_id);
                },
              })),
              h("td", { class: "name" }, m.name),
              h("td", {}, h("span", { class: "pill " + (m.role === "core" ? "ok" : "") }, m.role === "core" ? "Kern" : "Paket")),
              h("td", { class: "num" }, `${StudioUI.num(m.total_cards, 0)} (${StudioUI.num(m.commander_cards, 0)} Cmd)`),
              h("td", { class: "actions" },
                h("button", { type: "button", class: "chip", onclick: () => {
                  state.list.clear();
                  state.commanderIds = [];
                  for (const c of m.cards || []) {
                    if (c.is_commander) state.commanderIds.push(c.card_id);
                    else state.list.set(c.card_id, c.qty);
                  }
                  if (!state.commanderIds.length && state.decks) {
                    const curDeck = state.decks.find((d) => d.deck_id === state.deckId);
                    if (curDeck && curDeck.commanders) {
                      for (const cmdName of curDeck.commanders) {
                        const found = state.pool.find((p) => p.oracle_name === cmdName);
                        if (found) state.commanderIds.push(found.card_id);
                      }
                    }
                  }
                  markDirty();
                  renderAll();
                  toast(`Modul „${m.name}“ in die Arbeitsliste geladen.`);
                } }, "In Liste laden"),
                h("button", { type: "button", class: "chip", onclick: async () => {
                  try {
                    await api(`/api/decks/${encodeURIComponent(state.deckId)}/modules`, "POST", {
                      module_id: m.module_id,
                      name: m.name,
                      role: m.role,
                      sort_order: m.sort_order,
                      cards: entries(),
                    });
                    toast(`Modul „${m.name}“ aktualisiert.`);
                    reload();
                  } catch (err) { fail(err); }
                } }, "Überschreiben"),
                h("button", { type: "button", class: "chip", onclick: async () => {
                  try {
                    await api(`/api/decks/${encodeURIComponent(state.deckId)}/modules/${encodeURIComponent(m.module_id)}`, "DELETE");
                    state.selectedModuleIds.delete(m.module_id);
                    toast(`Modul „${m.name}“ gelöscht.`);
                    reload();
                  } catch (err) { fail(err); }
                } }, "Löschen")))))))
        : h("p", { class: "muted" }, "Noch keine Module für dieses Deck hinterlegt. Teile die aktuelle Arbeitsliste auf oder speichere sie als Modul.");

      wrap.replaceChildren(
        h("h3", {}, "Deck-Module (Kern + Strategie-Pakete)"),
        h("p", { class: "muted" }, "Ein Deck besteht aus genau 1 geteilten Kern-Modul (z. B. Commander + Länder + Basis) und mindestens 1 austauschbaren Strategie-Paket. Mehrfach vorkommende Nicht-Standardländer werden als Kollision gemeldet und nie still zusammengeführt."),
        h("div", { class: "actions" }, nameInput, roleSelect, saveBtn, seedBtn),
        modTable,
        mods.length ? h("div", { class: "actions" },
          h("button", { type: "button", class: "chip", onclick: () => runCompile(false) }, "Gewählte Module prüfen & kompilieren"),
          h("button", { type: "button", class: "chip", onclick: () => runCompile(false, true) }, "Mit aktuellem Stand vergleichen"),
          h("button", { type: "button", class: "primary", onclick: () => runCompile(true) }, "Auf 100 Karten kompilieren & als Variante speichern")) : "",
        compileOut
      );
    } catch (err) {
      wrap.replaceChildren(h("p", { class: "bad" }, StudioUI.germanError(err)));
    }
  };
  reload();
}
function renderOverview(body) {
  if (typeof renderDeckOverview !== "function") {
    body.append(h("p", { class: "muted" }, "Übersicht nicht geladen."));
    return;
  }
  const reference = (state.shapes || []).find((row) => row.cohort === state.cohort) || {};
  renderDeckOverview(body, {
    h, api, entries, fail, cohortName, roleName, bars, qty, deckTotal, add,
    poolCardById: (id) => state.byId.get(id),
    openCard: (cardId) => { const card = typeof cardId === "string" ? state.byId.get(cardId) : cardId; if (card) openCard(card); },
    deckCards,
    commanderCards: () => state.commanderIds.map((id) => state.byId.get(id)).filter(Boolean),
    shape: state.shape,
    reference,
    deckRoles: state.deckRoles,
    pool: state.pool,
    small: state.small,
    cohort: state.cohort,
    combos: state.combos,
    issues: state.issues,
    dirty: state.dirty,
    deckId: state.deckId,
    branch: state.branch,
    changeSeq: state.changeSeq,
    commander: COMMANDER,
    getLandAdvisor: () => state.landAdvisor,
    setLandAdvisor: (v) => { state.landAdvisor = v; },
    getCastability: () => state.castability,
    setCastability: (v) => { state.castability = v; },
    getDeckFacts: () => state.deckFacts,
    setDeckFacts: (v) => { state.deckFacts = v; },
    getDeckDoctor: () => state.deckDoctor,
    setDeckDoctor: (v) => { state.deckDoctor = v; },
    getLayers: () => state.layers,
    setLayers: (v) => { state.layers = v; },
    token: () => state.renderToken,
    isCurrent: (tok) => tok === state.renderToken && state.tab === "state",
  });
}
function renderCut(body) {
  renderCutLab(body, {
    h, api, entries, fail, roleName, openCard, add, remove, qty, deckCards,
    token: () => state.renderToken,
    isCurrent: (token) => token === state.renderToken && state.tab === "cut",
    deckId: () => `${state.deckId}::${state.branch}`, // the cut state belongs to one variant
    commanderIds: () => state.commanderIds,
    total: deckTotal,
    card: (cardId) => state.byId.get(cardId),
    pool: () => state.pool,
    inDeck: (cardId) => qty(cardId) > 0,
    cohort: () => state.cohort,
    reference: () => (state.shapes || []).find((row) => row.cohort === state.cohort),
    saveRevision: () => saveRevision(),
    rerender: () => renderDeck(),
    swap: (cutId, addId) => { const out = state.byId.get(cutId); const into = state.byId.get(addId); if (out && into) { remove(out); add(into); } },
  });
}
// Shared hooks for the deck tabs kept in their own files (deckfacts.js, castability.js).
function deckDeps(tab) {
  return {
    h, api, entries, fail, roleName,
    open: (cardId) => { const card = state.byId.get(cardId); if (card) openCard(card); },
    token: () => state.renderToken,
    isCurrent: (token) => token === state.renderToken && state.tab === tab,
  };
}
function renderFacts(body) { renderDeckFacts(body, deckDeps("facts")); }
function renderEvidence(body) { renderDeckEvidence(body, { ...deckDeps("evidence"), cohort: state.cohort, cohortName }); }
function renderAll() { renderHeader(); renderPool(); renderDeck(); }

async function renderSwapBox(into, card, initialMode = null) {
  const inDeck = qty(card.card_id) > 0;
  let mode = initialMode || (inDeck ? "replace" : "cut");
  let sortBy = "hits";
  const load = async () => {
    into.replaceChildren(h("h3", {}, "Tausch-Helfer (gleiche Rolle)"), h("p", { class: "muted" }, "Lädt Kandidaten …"));
    try {
      const res = await api("/api/swap", "POST", {
        commander: COMMANDER,
        deck_card_ids: [...state.list.keys()],
        card_id: card.card_id,
        mode,
        cohort: state.cohort,
        universe: state.universe || null,
        exclude_marked: true,
        sort_by: sortBy,
        ...(state.deckId ? { deck_id: state.deckId, branch: state.branch || "main" } : {}),
      });
      const modeSwitch = h("div", { class: "actions" },
        h("button", { type: "button", class: "chip" + (mode === "replace" ? " on" : ""), onclick: () => { mode = "replace"; load(); } }, inDeck ? "Ersatz im Pool suchen" : "Andere Pool-Karten dieser Rolle"),
        h("button", { type: "button", class: "chip" + (mode === "cut" ? " on" : ""), onclick: () => { mode = "cut"; load(); } }, inDeck ? "Streichkandidaten im Deck" : "Was im Deck streichen?"),
        h("button", { type: "button", class: "chip" + (sortBy === "hits" ? " on" : ""), onclick: () => { sortBy = "hits"; load(); } }, "Sort: Häufigkeit"),
        h("button", { type: "button", class: "chip" + (sortBy === "lift" ? " on" : ""), onclick: () => { sortBy = "lift"; load(); } }, "Sort: Lift"));
      if (!res.roles || !res.roles.length) {
        into.replaceChildren(h("h3", {}, "Tausch-Helfer (gleiche Rolle)"), modeSwitch, h("p", { class: "muted" }, res.note || "Keine Rolle für diese Karte hinterlegt."));
        return;
      }
      const roleBadges = res.roles.map((r) => roleName(r)).join(", ");
      const fmtDe = StudioUI.num;
      const fmtInt = (v) => StudioUI.num(Number(v), 0);
      const headerNote = h("p", { class: "note" },
        `Rollen: ${roleBadges} · Sortiert nach ${sortBy === "lift" ? "Lift (gegen globale EDHREC-Verbreitung)" : "Häufigkeit"} in „${cohortName(res.source_label)}“ (Nenner: ${fmtInt(res.of)} Decks). `,
        res.small_sample ? h("span", { class: "pill low" }, `Kleine Stichprobe (< ${fmtInt(state.small)} Decks)`) : null,
        res.unknown_count ? ` · ${fmtInt(res.unknown_count)} Karte(n) mit unbekanntem Wert stehen am Ende (unbekannt ist nie „selten gespielt“).` : "",
        ` Lift wird erst ab ${fmtInt(res.lift_min_n)} Quelldecks mit der Karte in der Gruppe und bekanntem globalem Anteil ausgewiesen.`,
        res.history && res.history.truncated ? ` Frühere Revisionen: nur die letzten ${fmtInt(res.history.revisions_checked)} geprüft.` : "");
      const orderNote = res.order_rule ? h("p", { class: "muted" }, res.order_rule) : null;
      const compare = res.compare_groups || [];
      const compareKeys = compare.map((g) => g.key);
      const showOwnGroup = compare.length > 0 && !compareKeys.includes(res.source_label);
      const fmtGroup = (fig) => (fig && fig.decks !== null && fig.decks !== undefined && fig.of ? `${fmtInt(fig.decks)}/${fmtInt(fig.of)}` : "unbekannt");
      if (!res.candidates || !res.candidates.length) {
        into.replaceChildren(h("h3", {}, "Tausch-Helfer (gleiche Rolle)"), modeSwitch, ...[headerNote, orderNote].filter(Boolean), h("p", { class: "muted" }, "Keine passenden Karten mit gleicher Rolle gefunden."));
        return;
      }
      const shown = res.candidates.slice(0, 10);
      const tbl = h("div", { class: "table-wrap" }, h("table", {},
        h("thead", {}, h("tr", {},
          h("th", {}, mode === "replace" ? "Ersatz-Kandidat (frei im Pool)" : "Kandidat im Deck (zum Streichen)"),
          h("th", {}, `Gemeinsame Rollen (k von ${fmtInt(res.target_role_count || (res.roles || []).length)})`),
          ...(compare.length ? compare.map((g) => h("th", { class: "num" }, `Decks ${g.key} n/N (N=${g.decks ? fmtInt(g.decks) : "unbekannt"})`)) : []),
          ...(!compare.length || showOwnGroup ? [h("th", { class: "num" }, `Decks ${cohortName(res.source_label)} n/N`)] : []),
          h("th", { class: "num" }, `Anteil (${cohortName(res.source_label)})`),
          h("th", { class: "num" }, `Lift (${cohortName(res.source_label)}, n ≥ ${fmtInt(res.lift_min_n)})`),
          h("th", {}, "Simulation (SIMULIERT, Reifegrad)"),
          h("th", {}, ""))),
        h("tbody", {}, shown.map((cand) => {
          const other = state.byId.get(cand.card_id);
          const freqText = cand.decks_known && cand.decks !== null && cand.of ? `${fmtInt(cand.decks)}/${fmtInt(cand.of)}` : "unbekannt";
          const pctText = cand.decks_known && cand.share !== null ? `${fmtDe(100 * cand.share, 1)} %` : "unbekannt";
          const liftThin = cand.decks_known && cand.decks !== null && cand.decks < res.lift_min_n;
          const liftText = cand.lift === null || cand.lift === undefined
            ? (liftThin ? `unbekannt (${fmtInt(cand.decks)} von ${fmtInt(cand.of)} < ${fmtInt(res.lift_min_n)})` : "unbekannt")
            : fmtDe(cand.lift, 2);
          const removed = cand.removed_before
            ? h("div", { class: "muted" }, `zuletzt in Revision ${cand.removed_before.revision_id} enthalten${cand.removed_before.created_at ? " (" + cand.removed_before.created_at.slice(0, 16).replace("T", " ") + ")" : ""}`)
            : null;
          let actionBtn = null;
          if (mode === "replace" && other) {
            if (inDeck && maxCopies(other) > 0) {
              actionBtn = h("button", { type: "button", class: "small", onclick: () => { remove(card); add(other); openCard(other, "replace"); } }, "Tauschen");
            } else if (!inDeck && maxCopies(other) > 0) {
              actionBtn = h("button", { type: "button", class: "small", onclick: () => { add(other); openCard(card, mode); } }, "+");
            }
          } else if (mode === "cut" && other) {
            if (!inDeck && maxCopies(card) > 0) {
              actionBtn = h("button", { type: "button", class: "small", onclick: () => { remove(other); add(card); openCard(card, "replace"); } }, "Gegen diese tauschen");
            } else if (inDeck) {
              actionBtn = h("button", { type: "button", class: "small", onclick: () => { remove(other); openCard(card, "cut"); } }, "Streichen");
            }
          }
          return h("tr", { class: res.small_sample ? "low" : "" },
            h("td", { class: "name", onclick: () => { if (other) openCard(other); } }, cand.name, removed),
            h("td", {}, `${fmtInt(cand.shared_role_count)} von ${fmtInt(cand.target_role_count)}: ` + (cand.shared_roles || []).map((r) => roleName(r)).join(", ")),
            ...(compare.length ? compare.map((g) => h("td", { class: "num" }, fmtGroup(cand.groups && cand.groups[g.key]))) : []),
            ...(!compare.length || showOwnGroup ? [h("td", { class: "num" }, freqText)] : []),
            h("td", { class: "num" }, pctText),
            h("td", { class: "num", title: cand.lift_unknown_reason || "" }, liftText,
              !liftThin && cand.lift_unknown_reason && (cand.lift === null || cand.lift === undefined)
                ? h("div", { class: "note note-compact" }, cand.lift_unknown_reason) : null),
            h("td", {}, deckSeriesCardEvidence(h)),
            h("td", {}, actionBtn));
        }))));
      into.replaceChildren(h("h3", {}, "Tausch-Helfer (gleiche Rolle)"), modeSwitch, ...[headerNote, orderNote, tbl].filter(Boolean));
    } catch (error) {
      into.replaceChildren(h("h3", {}, "Tausch-Helfer (gleiche Rolle)"), h("p", { class: "muted" }, "Tausch-Kandidaten nicht lesbar: " + StudioUI.germanError(error)));
    }
  };
  await load();
}

// ---------- card window ----------
function closeModal() { $("modal").hidden = true; }
async function openCard(card) {
  const initialSwapMode = arguments.length > 1 ? arguments[1] : null;
  const box = $("modal-box"); box.className = ""; box.replaceChildren();
  let face = "front";
  const picture = card.has_image ? image(card, "big") : h("div", { class: "muted" }, "Kein Bild in den Kartendaten.");
  const left = h("div", {}, picture, card.has_back ? h("div", { class: "actions" }, h("button", { type: "button", onclick: () => { face = face === "front" ? "back" : "front"; picture.src = cardImageUrl(card, face); } }, "Rückseite / Vorderseite")) : null);
  const note = h("textarea", { placeholder: "Deine Notiz zur Karte" }); note.value = card.note;
  const saveMark = async (change) => {
    Object.assign(card, change);
    try { await api(`/api/cards/${encodeURIComponent(card.card_id)}/mark`, "PUT", { favorite: card.favorite, excluded: card.excluded, note: card.note }); renderPool(); openCard(card, initialSwapMode); }
    catch (error) { fail(error); }
  };
  const labelInput = h("input", { type: "text", id: "card-labels", placeholder: "Archetyp-Marken, mit Komma getrennt", maxlength: "400" }); labelInput.value = card.labels.join(", ");
  const saveLabels = async () => {
    try {
      const done = await api(`/api/cards/${encodeURIComponent(card.card_id)}/labels`, "PUT", { labels: labelList(labelInput.value) });
      card.labels = done.labels; renderLabelFilter(); renderPool(); openCard(card, initialSwapMode);
    } catch (error) { fail(error); }
  };
  const count = qty(card.card_id);
  const frequencies = h("div", { class: "table-wrap" }, h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Quelldecks"), h("th", { class: "num" }, "mit Karte"), h("th", { class: "num" }, "Decks"), h("th", { class: "num" }, "Anteil"))),
    h("tbody", {}, visibleCohortEntries(state.cohorts).map(([key]) => { const f = freq(card, key); return h("tr", { class: f.total < state.small ? "low" : "" }, h("td", {}, cohortName(key)), h("td", { class: "num" }, f.hits === null ? "unbekannt" : StudioUI.num(f.hits, 0)), h("td", { class: "num" }, StudioUI.num(f.total, 0)), h("td", { class: "num" }, f.hits !== null && f.total ? StudioUI.pct(f.share, 1) : "unbekannt")); }))));
  const swapBox = h("div", { id: "swap-helper-box" });
  const duelBox = h("div", { id: "card-duel-box" });
  const trendBox = h("div", { id: "card-trend-box" });
  const strengthBox = h("div", { id: "card-strength-box" });
  const extra = h("div", {}, h("p", { class: "muted" }, "Lädt EDHREC-Zeilen."));
  const right = h("div", {},
    h("h2", {}, card.name, " ", tierMark(card)), h("div", {}, mana(card.mana_cost), " ", h("span", { class: "muted" }, card.type_line), card.power !== null ? ` · ${card.power}/${card.toughness}` : ""),
    h("p", { class: "pre-line" }, card.text),
    card.roles.length ? h("p", {}, card.roles.map((role) => h("span", { class: "chip chip-static mr-1" }, roleName(role)))) : null,
    h("p", { class: "note" }, `Sammlung: ${StudioUI.num(card.owned, 0)} im Besitz, ${StudioUI.num(card.available, 0)} frei` + (card.reserved ? `, ${StudioUI.num(card.reserved, 0)} reserviert` : "") + ` · Kartendaten: ${card.fact_source === "scryfall" ? "Scryfall" : "deine Tabelle"}` + (card.edhrec_rank ? ` · EDHREC-Rang ${StudioUI.num(card.edhrec_rank, 0)}` : "") + (card.game_changer ? " · Game Changer" : "") + ` · Simulator: ${StudioUI.simStatusLabel(card.sim_status)}`),
    allocationDetail(h, card),
    h("div", { class: "actions" },
      h("button", { type: "button", class: "primary", disabled: count >= maxCopies(card), onclick: () => { add(card); openCard(card); } }, "Ins Deck"),
      count ? h("button", { type: "button", onclick: () => { remove(card); openCard(card); } }, `Aus dem Deck (${StudioUI.num(count, 0)})`) : null,
      h("button", { type: "button", onclick: () => saveMark({ favorite: !card.favorite }) }, card.favorite ? "★ Favorit" : "☆ Favorit"),
      h("button", { type: "button", onclick: () => saveMark({ excluded: !card.excluded }) }, card.excluded ? "Ausschluss aufheben" : "Ausschließen"),
      h("button", { type: "button", onclick: closeModal }, "Schließen")),
    note, h("div", { class: "actions" }, h("button", { type: "button", onclick: () => saveMark({ note: note.value }) }, "Notiz speichern")),
    swapBox,
    duelBox,
    h("h3", {}, "Archetyp-Marken"),
    card.labels.length ? h("p", { id: "card-label-chips" }, card.labels.map((name) => h("span", { class: "chip chip-static mr-1" }, name))) : h("p", { class: "muted" }, "Keine Marken. Sie ordnen deine Karten und zählen nirgends als Wertung."),
    h("div", { class: "actions" }, labelInput, h("button", { type: "button", id: "card-labels-save", onclick: saveLabels }, "Marken speichern")),
    h("h3", {}, "Häufigkeit in den Quelldecks"), frequencies, h("p", { class: "note" }, "Gelb: Gruppe mit weniger als 30 Decks."),
    h("p", {}, h("a", { href: `decks.html?commander=${encodeURIComponent(COMMANDER)}&must=${encodeURIComponent(card.name)}`, class: "chip" }, "Quelldecks mit dieser Karte im Deck-Browser öffnen →")),
    trendBox,
    card.universe && activeScope() ? h("p", { class: "note" }, `Im ${activeScope().label}: ${card.universe.filter_card ? "Filterkarte des Universums (steht per Definition in jedem Deck der Teilmenge, ohne Zählung)" : card.universe.matched ? `${StudioUI.num(card.universe.hits, 0)}/${StudioUI.num(card.universe.denominator, 0)} Decks (Verbreitung gezählt, keine Stärke)` : card.in_collection === false ? `unbekannt (${card.universe.reason})` : "unbekannt (kein Deck des Universums nennt diese Karte unter einem bekannten Namen)"}`) : null,
    card.universe && state.universeInfo && state.universeInfo.subset_note ? h("p", { class: "note" }, state.universeInfo.subset_note) : null, strengthBox, extra);
  box.append(left, right); $("modal").hidden = false;
  if (!state.commanderIds.includes(card.card_id) && !card.basic) renderSwapBox(swapBox, card, initialSwapMode);
  if (!state.commanderIds.includes(card.card_id) && !card.basic) renderDuelBox(duelBox, card, {
    h, api, fail, roleName, commander: COMMANDER,
    groupName: (group) => GROUP_NAMES[group] || group,
    pool: () => state.pool,
    deckCardIds: () => [...state.commanderIds, ...state.list.keys()],
    cohort: () => state.cohort,
    cohortLabel: () => cohortName(state.cohort),
  });
  renderCardTrendBox(trendBox, card, {
    h,
    loadTrend: () => loadCardTrend(),
    onSettingsChange: (days, bracket, source) => {
      state.cardTrendDays = days;
      state.cardTrendBracket = bracket;
      state.cardTrendSource = source;
      state.cardTrend = null;
      state.cardTrendReq = null;
      loadCardTrend();
    },
  });
  showStrengthBreakdown(strengthBox, card);
  try {
    const detail = await api(`/api/cards/${encodeURIComponent(card.card_id)}?${StudioCommander.query}&cohort=${encodeURIComponent(state.cohort)}`);
    const parts = [];
    if (detail.used_in && detail.used_in.length) {
      parts.push(h("h3", {}, "Verwendet in gespeicherten Varianten"),
        h("p", {}, detail.used_in.map((u) => `${u.name} (${u.branch})`).join(" · ")));
    }
    if (state.universe || state.subset) {
      try {
        const co = await api(`/api/cards/${encodeURIComponent(card.card_id)}/cooccurrence?limit=25&commander=${encodeURIComponent(COMMANDER)}` + (state.universe ? `&profile=${encodeURIComponent(state.universe)}` : "") + state.subsetNames.map((name) => `&must_contain=${encodeURIComponent(name)}`).join(""));
        if (co.decks_with_card === null) {
          parts.push(h("h3", {}, `Zusammen gespielt im Universum ${co.profile || "alle Decks"}`), h("p", { class: "muted" }, "unbekannt: die Karte kommt im Universum nicht vor"));
        } else {
          const smallCo = co.decks_with_card < state.small;
          parts.push(h("h3", {}, `Zusammen gespielt im Universum ${co.profile || "alle Decks"} (Nenner: ${StudioUI.num(co.decks_with_card, 0)} Decks mit dieser Karte, ${co.subset_note ? "Teilmenge" : "Universum"}: ${StudioUI.num(co.denominator, 0)} Decks) `, smallCo ? h("span", { class: "pill low" }, `Kleine Stichprobe (< ${StudioUI.num(state.small, 0)} Decks)`) : null),
            h("div", { class: "table-wrap" }, h("table", {},
              h("thead", {}, h("tr", {}, h("th", {}, "Karte"), h("th", { class: "num" }, "gemeinsam / mit Karte"), h("th", { class: "num" }, "Anteil"), h("th", { class: "num" }, "Lift"), h("th", {}, "Kombo-Partner"))),
              h("tbody", {}, co.pairs.map((pair) => h("tr", { class: smallCo ? "low" : "" },
                h("td", {}, pair.card_name),
                h("td", { class: "num" }, `${StudioUI.num(pair.decks_together, 0)}/${StudioUI.num(co.decks_with_card, 0)}`),
                h("td", { class: "num" }, `${StudioUI.num(100 * pair.decks_together / co.decks_with_card, 1)} %`),
                h("td", { class: "num" }, pair.lift === null ? "unbekannt" : StudioUI.num(pair.lift, 2)),
                h("td", {}, pair.combo_partner ? "ja (Spellbook-Kombo)" : "–")))))),
            h("p", { class: "note" }, "Reine Zählung im gewählten Universum. Lift: Anteil unter den Decks mit dieser Karte geteilt durch den Anteil im ganzen Universum; über 1 heißt überproportional oft zusammen gespielt. Kombo-Partner: beide Karten stehen in einer geprüften Spellbook-Kombo dieses Commanders." + (co.excluded_no_date ? ` ${StudioUI.num(co.excluded_no_date, 0)} Decks ohne Zeitstempel fallen durch den Datumsfilter heraus.` : "")),
            ...(co.subset_note ? [h("p", { class: "note" }, `${co.subset_note}. Der Nenner ${StudioUI.num(co.denominator, 0)} ist diese Teilmenge, nicht alle Decks des Commanders.${co.filter_card ? " Diese Karte ist eine Filterkarte: sie steht in allen Decks der Teilmenge." : ""}`)] : []));
        }
      } catch (error) { parts.push(h("p", { class: "muted" }, "Universum-Kookkurrenz nicht lesbar: " + StudioUI.germanError(error))); }
    }
    if (!state.universe && !state.subset && detail.cooccurrence && detail.cooccurrence.cards && detail.cooccurrence.cards.length) {
      const co = detail.cooccurrence;
      const smallCo = co.card_decks < state.small;
      const coRows = co.cards.filter((item) => {
        const other = state.byId.get(item.card_id);
        return !state.commanderIds.includes(item.card_id) && (!other || !other.basic);
      });
      parts.push(h("h3", {}, `Zusammen gespielt in Quelldecks (${cohortName(co.cohort)}, Nenner: ${StudioUI.num(co.card_decks, 0)} Decks mit dieser Karte) `, smallCo ? h("span", { class: "pill low" }, `Kleine Stichprobe (< ${StudioUI.num(state.small, 0)} Decks)`) : null),
        h("div", { class: "table-wrap" }, h("table", {},
          h("thead", {}, h("tr", {}, h("th", {}, "Karte in deiner Sammlung (ohne Standardländer)"), h("th", { class: "num" }, "gemeinsam / Nenner"), h("th", { class: "num" }, "Anteil"), h("th", { class: "num" }, "Lift"), h("th", {}, "Kombo-Partner"), h("th", {}, ""))),
          h("tbody", {}, coRows.map((item) => {
            const other = state.byId.get(item.card_id);
            const liftVal = item.lift === null || item.lift === undefined ? "unbekannt" : StudioUI.num(item.lift, 2);
            return h("tr", { class: smallCo ? "low" : "" },
              h("td", { class: "name", onclick: () => { if (other) openCard(other); } }, item.name),
              h("td", { class: "num" }, `${StudioUI.num(item.both_hits, 0)}/${StudioUI.num(item.card_decks, 0)}`),
              h("td", { class: "num" }, `${StudioUI.num(100 * item.share, 1)} %`),
              h("td", { class: "num" }, liftVal),
              h("td", {}, item.combo_partner ? "ja (Spellbook)" : "–"),
              h("td", {}, other && !qty(other.card_id) && maxCopies(other) > 0 ? h("button", { class: "small", type: "button", onclick: () => { add(other); openCard(card); } }, "+") : null));
          })))),
        h("p", { class: "note" }, "Reine Zählung in den Quelldecks dieser Gruppe. Lift: Anteil mit dieser Karte geteilt durch den Gruppen-Anteil; Kombo-Partner laut geprüfter Spellbook-Liste."));
    }
    if (detail.neutral_boards && detail.neutral_boards.sections && detail.neutral_boards.sections.length) {
      const nb = detail.neutral_boards;
      parts.push(h("h3", {}, "Neutrale Nicht-Mainboard-Sektionen (Batch-Quellen)"),
        h("div", { class: "table-wrap" }, h("table", {},
          h("thead", {}, h("tr", {}, h("th", {}, "Sektion"), h("th", { class: "num" }, "Quellen mit Karte / Sektions-Quellen"), h("th", { class: "num" }, "Batch-Gesamt"), h("th", { class: "num" }, "Anteil in Sektion"))),
          h("tbody", {}, nb.sections.map((sec) => h("tr", {},
            h("td", {}, sec.section),
            h("td", { class: "num" }, `${StudioUI.num(sec.hits, 0)}/${StudioUI.num(sec.section_sources, 0)}`),
            h("td", { class: "num" }, StudioUI.num(sec.batch_sources, 0)),
            h("td", { class: "num" }, `${StudioUI.num(100 * sec.share_of_section, 1)} %`)))))),
        h("p", { class: "note" }, "Neutrale Quellkategorie der Deckautoren (Maybeboard = Überlegung, Cuts = vom Autor separiert). Keine negative Bewertung und niemals mit Mainboard-Frequenzen vermischt."));
    }
    if (detail.simulations && detail.simulations.length) {
      parts.push(h("h3", {}, "Simulationsergebnisse"),
        h("div", { class: "table-wrap" }, h("table", {},
          h("thead", {}, h("tr", {}, h("th", {}, "Pod (Pin)"), h("th", { class: "num" }, "Spiele angeboten"), h("th", { class: "num" }, "Spiele gewirkt"), h("th", { class: "num" }, "ungespielt"), h("th", { class: "num" }, "Ø 1. Runde"), h("th", {}, "Handverweildauer"))),
          h("tbody", {}, detail.simulations.map((s) => h("tr", {},
            h("td", {}, `${s.pod} (${s.engine_pin})`),
            h("td", { class: "num" }, `${StudioUI.num(s.games_offered, 0)}/${StudioUI.num(s.games_completed, 0)}`),
            h("td", { class: "num" }, `${StudioUI.num(s.games_cast_after_offer, 0)}/${StudioUI.num(s.games_offered, 0)}`),
            h("td", { class: "num" }, StudioUI.num(s.games_rotted, 0)),
            h("td", { class: "num" }, s.mean_first_cast_round === null ? "unbekannt" : StudioUI.num(s.mean_first_cast_round, 1)),
            h("td", { class: "muted" }, s.hand_dwell_status === "UNKNOWN" ? "unbekannt (nicht gemessen)" : s.hand_dwell_status)))))));
    }
    const rows = detail.observations.filter((row) => row.metric === "inclusion_pct");
    const lift = new Map(detail.observations.filter((row) => row.metric === "lift").map((row) => [row.cohort, row.value]));
    const synergy = new Map(detail.observations.filter((row) => row.metric === "synergy_pct").map((row) => [row.cohort, row.value]));
    parts.push(h("h3", {}, "EDHREC-Seiten (getrennte Kohorten, nicht addierbar)"),
      rows.length ? h("div", { class: "table-wrap" }, h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Kohorte / Seite"), h("th", { class: "num" }, "Zähler/Nenner"), h("th", { class: "num" }, "Anteil"), h("th", { class: "num" }, "Lift"), h("th", { class: "num" }, "Synergy %"))),
        h("tbody", {}, rows.map((row) => h("tr", { class: row.denominator !== null && row.denominator < state.small ? "low" : "" },
          h("td", { title: row.snapshot || "" }, row.cohort.replace(/^edhrec:/, "")),
          h("td", { class: "num" }, row.denominator !== null ? `${StudioUI.num(row.numerator, 0)}/${StudioUI.num(row.denominator, 0)}` : `${row.numerator != null ? StudioUI.num(row.numerator, 0) : "?"}/unbekannt`),
          h("td", { class: "num" }, row.value === null ? "unbekannt" : StudioUI.num(row.value, 1) + " %"),
          h("td", { class: "num" }, lift.get(row.cohort) === null || lift.get(row.cohort) === undefined ? "unbekannt" : StudioUI.num(lift.get(row.cohort), 2)),
          h("td", { class: "num" }, synergy.get(row.cohort) === null || synergy.get(row.cohort) === undefined ? "unbekannt" : StudioUI.num(synergy.get(row.cohort), 1) + " %"))))))
        : h("p", { class: "muted" }, "Keine EDHREC-Zeile gespeichert: unbekannt, nicht null."));
    if (detail.playgroup) {
      const pg = detail.playgroup;
      const pgRows = [];
      pgRows.push(
        h("tr", {}, h("td", {}, "Live-Aufnahmequote (Live Inclusion)"), h("td", { class: "num" }, pg.live_inclusion_pct !== null ? `${StudioUI.num(pg.live_inclusion_pct, 1)} %` : "unbekannt")),
        h("tr", {}, h("td", {}, "Eingesetzt / Decks im Einsatz (Times Brought / Decks Running)"), h("td", { class: "num" }, `${pg.times_brought != null ? StudioUI.num(pg.times_brought, 0) : "?"} / ${pg.decks_running != null ? StudioUI.num(pg.decks_running, 0) : "?"}`)),
        h("tr", {}, h("td", {}, "Medianer Cast-Turn"), h("td", { class: "num" }, pg.median_cast_turn !== null ? `T${StudioUI.num(pg.median_cast_turn, 1)}` : "unbekannt")),
        h("tr", {}, h("td", {}, "Gezogen und gespielt (Drawn-to-Played)"), h("td", { class: "num" }, pg.drawn_to_played_pct !== null ? `${StudioUI.num(pg.drawn_to_played_pct, 1)} %` : "unbekannt")),
        h("tr", {}, h("td", {}, "Siegrate, wenn gewirkt"), h("td", { class: "num" }, pg.winrate_when_cast_pct !== null ? `${StudioUI.num(pg.winrate_when_cast_pct, 1)} % (n=${pg.winrate_when_cast_n != null ? StudioUI.num(pg.winrate_when_cast_n, 0) : "?"})` : "unbekannt")),
        h("tr", {}, h("td", {}, "Siegrate, wenn in der Bibliothek"), h("td", { class: "num" }, pg.winrate_when_in_library_pct !== null ? `${StudioUI.num(pg.winrate_when_in_library_pct, 1)} % (n=${pg.winrate_when_in_library_n != null ? StudioUI.num(pg.winrate_when_in_library_n, 0) : "?"})` : "unbekannt")),
        h("tr", {}, h("td", {}, "Beobachtete Siegraten-Differenz"), h("td", { class: "num" }, pg.observed_winrate_gap_pp !== null ? `${pg.observed_winrate_gap_pp > 0 ? "+" : ""}${StudioUI.num(pg.observed_winrate_gap_pp, 1)} pp` : "unbekannt")),
        h("tr", {}, h("td", {}, "95% Konfidenzintervall"), h("td", { class: "num" }, pg.ci_95_lower_pp !== null && pg.ci_95_upper_pp !== null ? `[${pg.ci_95_lower_pp > 0 ? "+" : ""}${StudioUI.num(pg.ci_95_lower_pp, 1)} pp; ${pg.ci_95_upper_pp > 0 ? "+" : ""}${StudioUI.num(pg.ci_95_upper_pp, 1)} pp]` : "unbekannt")),
        h("tr", {}, h("td", {}, "Konservativer Schätzer"), h("td", { class: "num" }, pg.conservative_ranking_indicator || "unbekannt")),
      );
      if (pg.quality_warnings && pg.quality_warnings.length) {
        pgRows.push(h("tr", { class: "low" }, h("td", {}, "Qualitätshinweise"), h("td", { class: "num" }, pg.quality_warnings.map(playgroupWarningText).join(" · "))));
      }
      parts.push(
        h("h3", {}, `Playgroup Card Atlas (${pg.attribution || "Playgroup.gg, CC BY 4.0"})`),
        h("div", { class: "table-wrap" }, h("table", {}, h("tbody", {}, pgRows))),
        h("p", { class: "note" }, pg.disclosure || "Live-Korrelation (Playgroup.gg), keine kausale Kartenstärke.")
      );
    }
    extra.replaceChildren(...parts);
  } catch (error) { extra.replaceChildren(h("p", { class: "muted" }, "Zusatzdaten nicht lesbar: " + StudioUI.germanError(error))); }
}
function _strengthStatusText(c) {
  if (c.status === "PRESENT") return "vorhanden";
  if (c.status === "ZERO_COUNT") return "gezählt 0 von N (ZERO_COUNT)";
  if (c.status === "NOT_COLLECTED") return "nicht erhoben";
  if (c.status === "NOT_RANKED") return "nicht bewertet";
  if (c.status === "FILTER_CARD") return "Filterkarte";
  if (c.status === "NO_VALUE") return c.reason ? `kein Wert (${c.reason})` : "kein Wert";
  return c.status || "unbekannt";
}
async function showStrengthBreakdown(into, card) {
  if (!state.strength) {
    into.replaceChildren(h("h3", {}, "Stärke-Index-Aufschlüsselung (v3)"), h("p", { class: "muted" }, "Lädt Signale …"));
    await loadStrength();
    if (!into.isConnected) return;
  }
  const st = state.strength && state.strength.map ? state.strength.map.get(card.card_id) : null;
  if (!st) {
    into.replaceChildren(h("h3", {}, "Stärke-Index-Aufschlüsselung (v3)"), h("p", { class: "muted" }, "Kein Stärke-Index für diese Karte geladen."));
    return;
  }
  const nodes = [h("h3", {}, "Stärke-Index-Aufschlüsselung (v3 · Schätzung aus Nutzungsdaten)")];
  const idxText = st.index !== null && st.index !== undefined ? StudioUI.num(st.index, 1) : "unbekannt";
  const covText = st.coverage !== null && st.coverage !== undefined ? `${StudioUI.num(100 * st.coverage, 0)} %` : "–";
  const confText = st.confidence !== null && st.confidence !== undefined ? `${st.confidence_level || ""} (${StudioUI.num(st.confidence, 2)})` : "–";
  nodes.push(h("p", {},
    `Stufe ${st.tier} · Index ${idxText} · Datenlage ${covText} · Konfidenz ${confText}`,
    st.borderline ? h("span", { class: "pill warn ml-1" }, `grenzwertig (${StudioUI.num(st.cut_distance, 1)} Pkt zu ${StudioUI.numFlex(st.borderline_cut, 1)})`) : null));
  const rankEntries = st.role_ranks ? Object.entries(st.role_ranks) : [];
  if (rankEntries.length) {
    nodes.push(h("p", {}, "Rang in der Funktion: ",
      ...rankEntries.map(([r, info]) => h("span", { class: "chip chip-static mr-1" }, `${roleName(r)}: #${StudioUI.num(info.rank, 0)}/${StudioUI.num(info.total, 0)}`))));
  }
  const comps = st.components || [];
  if (comps.length) {
    nodes.push(h("div", { class: "table-wrap" }, h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, "Signal"), h("th", { class: "num" }, "Zähler/Nenner"), h("th", { class: "num" }, "Rohwert"), h("th", { class: "num" }, "Score 0–100"), h("th", { class: "num" }, "Gewicht (wirksam)"), h("th", {}, "Status"))),
      h("tbody", {}, comps.map((c) => {
        const countStr = c.denominator ? (c.numerator === null || c.numerator === undefined ? `n = ${StudioUI.num(c.denominator, 0)}` : `${StudioUI.num(c.numerator, 0)}/${StudioUI.num(c.denominator, 0)}`) : "–";
        const rawStr = c.value === null || c.value === undefined ? "unbekannt" : StudioUI.numSig(c.value, 4);
        const scoreStr = c.percentile === null || c.percentile === undefined ? "–" : `${StudioUI.num(100 * c.percentile, 1)}`;
        return h("tr", {},
          h("td", { title: c.signal || "" }, c.label || c.component),
          h("td", { class: "num" }, countStr),
          h("td", { class: "num" }, rawStr),
          h("td", { class: "num" }, scoreStr),
          h("td", { class: "num" }, c.weight == null ? "–" : StudioUI.numFlex(c.weight)),
          h("td", {}, _strengthStatusText(c)));
      })))));
  }
  nodes.push(h("p", { class: "note" }, "Schätzung aus Nutzungssignalen (keine Siegrate). Eigene Markierungen (Favorit/Ausschluss/Notiz) und Simulationen zählen mit Gewicht 0 / gar nicht."));
  into.replaceChildren(...nodes);
}

// ---------- Stärke-Index for the sort (the tier page's function, never a copy of its scoring) ----------
function strengthRequest() {
  let settings = null;
  try { settings = JSON.parse(StudioUI.recall("studio.strength.settings", "null")); } catch (error) { settings = null; }
  return api("/api/strength", "POST", settings ? { commander: COMMANDER, settings } : { commander: COMMANDER });
}
async function loadStrength() {
  if (state.strength) return state.strength;
  if (state.strengthPromise) return state.strengthPromise;
  state.strengthLoading = true;
  state.strengthPromise = (async () => {
    try {
      const early = state.strengthPrefetch; // started by start() beside the pool request
      state.strengthPrefetch = null;
      let result;
      try { result = await (early || strengthRequest()); }
      catch (error) { result = await api("/api/strength", "POST", { commander: COMMANDER }); } // remembered settings may be outdated
      state.strength = { result, map: new Map(result.cards.map((item) => [item.card_id, item])) };
      if (state.sortKey === "strength") toast("Stärke-Index geladen (Schätzung aus Nutzungsdaten, Einstellungen der Tierliste).");
      renderPool(); if (state.deckId) renderDeck();
      return state.strength;
    } catch (error) { fail(error); return null; }
    finally { state.strengthLoading = false; state.strengthPromise = null; }
  })();
  return state.strengthPromise;
}
async function loadCardTrend() {
  if (state.cardTrend) return state.cardTrend;
  if (state.cardTrendReq) return state.cardTrendReq;
  const query = `${StudioCommander.query}&recent_days=${encodeURIComponent(state.cardTrendDays)}`
    + `&source=${encodeURIComponent(state.cardTrendSource)}`
    + (state.cardTrendBracket ? `&bracket=${encodeURIComponent(state.cardTrendBracket)}` : "");
  state.cardTrendReq = (async () => {
    try {
      const result = await api("/api/card-trend?" + query);
      state.cardTrend = { ...result, map: new Map((result.cards || []).map((item) => [item.card_id, item])) };
      renderPool();
      return state.cardTrend;
    } finally {
      state.cardTrendReq = null;
    }
  })();
  return state.cardTrendReq;
}
function renderSimReadiness() {
  const info = state.simReadiness, box = $("f-sim"), text = $("f-sim-text");
  if (!info || !box) return;
  if (!info.available) {
    box.disabled = true; box.checked = false;
    text.textContent = "Simulator-bereit (nicht verfügbar)";
    $("f-sim-label").title = "Die Kartendaten des Simulators (xmage_card_facts.json, pilot_card_knowledge.json) sind hier nicht lesbar, deshalb gibt es keine Bereitschaft.";
    return;
  }
  // Collection and Zukauf cards are counted separately (never one mixed figure, #1648).
  const extra = state.simReadinessUnowned;
  text.textContent = extra
    ? `Simulator-bereit (Sammlung ${StudioUI.num(info.ready, 0)} von ${StudioUI.num(info.total, 0)} · außerhalb ${StudioUI.num(extra.ready, 0)} von ${StudioUI.num(extra.total, 0)})`
    : `Simulator-bereit (${StudioUI.num(info.ready, 0)} von ${StudioUI.num(info.total, 0)})`;
  const missing = info.total - info.ready + (extra ? extra.total - extra.ready : 0);
  $("f-sim-label").title = !missing
    ? "Alle Karten des Pools sind für den Simulator bereit: der Filter ändert nichts."
    : `${StudioUI.num(missing, 0)} Karten haben keine vollständigen Simulator-Kartendaten (Status laut deck_readiness).`;
}
// Every card of the pool, collection and Zukauf cards, is ready for the simulator.
function simAllReady() {
  const info = state.simReadiness, extra = state.simReadinessUnowned;
  return Boolean(info && info.available && info.ready === info.total && (!extra || extra.ready === extra.total));
}

// ---------- pool loading (with the chosen universe profile) ----------
function renderUniverseInfo() {
  const box = $("universe-info");
  if (!box) return;
  const u = state.universeInfo;
  const c = state.countedUniverse;
  if (!u && c && !state.universe) {
    if ((state.cohorts.all || 0) > 0) {
      box.textContent = `Aktive Quelldeck-Gruppe: ${cohortName(state.cohort)} (${StudioUI.num(state.cohorts[state.cohort] ?? 0, 0)} Decks) · zusätzlich gezähltes Universum: ${countedName()} (Stand ${c.snapshot_id}).`;
    } else {
      box.textContent = `${countedName()} · Stand ${c.snapshot_id} · automatisch gewählt, weil keine Quelldecks gespeichert sind (${c.reason.replace(/^automatisch gewählt: /, "")}). Eine Karte ohne Zeile steht in keinem Deck (gezählte Null).`;
    }
    return;
  }
  if (!u) { box.textContent = ""; return; }
  if (u.gc_band) {
    box.textContent = StudioGcBand.infoText(u);
    return;
  }
  const parts = [`Universum ${u.profile} (Version ${u.version}): ${StudioUI.num(u.denominator, 0)} Decks (Nenner), Stand ${u.snapshot_id}`];
  if (u.subset_note) parts.push(u.subset_note);
  if (u.excluded_no_date) parts.push(`${StudioUI.num(u.excluded_no_date, 0)} ohne Zeitstempel ausgeschlossen`);
  if (u.below_min_universe) parts.push(`unter dem Mindest-Universum ${StudioUI.num(u.min_universe, 0)}: alle Stufen U`);
  box.textContent = parts.join(" · ");
}
// Only the view fields of a StudioGcBand.select result go into state.
const pickView = (next) => ({ universe: next.universe, gcBand: next.gcBand, cohort: next.cohort });
function renderGcBandBar() {
  const disabled = Boolean(state.universe);
  StudioGcBand.renderBar($("gc-band-bar"), state.gcBandData, state.gcBand, disabled, async (band) => {
    const next = StudioGcBand.select(state, "gc_band", band);
    Object.assign(state, pickView(next));
    if ($("cohort")) $("cohort").value = state.cohort;
    if (next.clearSubset && (state.subset || state.subsetNames.length)) { subsetTicket++; state.subset = null; state.subsetNames = []; state.subsetWanted = null; }
    try { await loadPool(); renderAll(); } catch (error) { fail(error); }
  });
}
function renderBracketBar() {
  const bar = $("bracket-bar");
  if (!bar) return;
  const disabled = Boolean(state.universe) || (Boolean(state.countedUniverse) && !(state.cohorts.all || 0));
  const b5Key = state.cohorts["bracket:5"] !== undefined ? "bracket:5" : (state.cohorts.cedh !== undefined ? "cedh" : "bracket:5");
  const originTip = StudioGcBand.bracketOriginText(state.gcBandData);
  const items = [
    ["all", "Alle"],
    ["bracket:1", "B1"],
    ["bracket:2", "B2"],
    ["bracket:3", "B3"],
    ["bracket:4", "B4"],
    [b5Key, "B5 (cEDH)"],
    ["tuned", "B4+5 (Tuned)"],
  ];
  bar.replaceChildren(
    h("span", { class: "muted", title: originTip || "Erklärte Brackets (Selbstauskunft der Quelldecks)" }, "Bracket:"),
    ...items.map(([key, label]) => {
      const count = state.cohorts[key] ?? 0;
      const isLow = count > 0 && count < state.small;
      const active = !disabled && !state.gcBand && state.cohort === key;
      return h("button", {
        type: "button",
        class: "chip" + (active ? " on" : "") + (isLow ? " low" : ""),
        disabled: disabled || (key !== "all" && count === 0),
        title: (isLow ? `Kleine Stichprobe (${StudioUI.num(count, 0)} Decks < ${StudioUI.num(state.small, 0)})` : `${cohortName(key)}: ${StudioUI.num(count, 0)} Decks`) + (originTip ? ` · ${originTip}` : ""),
        onclick: async () => {
          const hadBand = Boolean(state.gcBand);
          Object.assign(state, pickView(StudioGcBand.select(state, "cohort", key)));
          if ($("cohort")) $("cohort").value = state.cohort;
          if (hadBand) {
            try { await loadPool(); renderAll(); } catch (error) { fail(error); }
            return;
          }
          renderBracketBar(); renderUniverseInfo(); renderPool(); renderDeck();
        },
      }, `${label} (${StudioUI.num(count, 0)})`);
    })
  );
}
function applyPool(pool) {
  const previous = state.byId || new Map();
  const nextById = new Map(pool.cards.map((card) => [card.card_id, card]));
  for (const id of state.list.keys()) {
    if (!nextById.has(id) && previous.has(id)) nextById.set(id, previous.get(id));
  }
  state.pool = pool.cards; state.byId = nextById;
  state.roles = (pool.roles || []).sort((x, y) => roleName(x).localeCompare(roleName(y)));
  state.cohorts = pool.cohorts; state.small = pool.small_denominator; state.commanderIds = pool.commander_ids;
  state.universeInfo = pool.universe || null;
  state.germanNames = pool.german_names_available !== false;
  state.countedUniverse = pool.counted_universe || null;
  state.simReadiness = pool.sim_readiness || null;
  state.simReadinessUnowned = pool.sim_readiness_unowned || null;
  renderUniverseInfo(); renderBracketBar(); renderGcBandBar(); renderSimReadiness(); renderLabelFilter();
}
// Archetype labels are the Owner's own words for ordering cards and decks: a filter and a
// display, never a rating.
const labelList = (text) => text.split(",").map((item) => item.trim()).filter(Boolean);
function renderLabelFilter() {
  const select = $("label-filter"), wanted = select.value;
  const seen = new Map();
  for (const card of state.pool) for (const item of card.labels) seen.set(item.toLowerCase(), item);
  const names = [...seen.values()].sort((x, y) => x.localeCompare(y));
  select.replaceChildren(h("option", { value: "" }, "alle Marken"), ...names.map((name) => h("option", { value: name }, name)), h("option", { value: "-" }, "ohne Marke"));
  select.value = names.some((name) => name === wanted) || wanted === "-" ? wanted : "";
}
function renderDeckLabels() {
  const deck = state.decks.find((item) => item.deck_id === state.deckId);
  const names = deck && deck.labels ? deck.labels : [];
  $("deck-labels").textContent = names.length ? `Marken: ${names.join(", ")}` : "Marken: keine";
}
// Quality notes of the Playgroup source are stored in English in the data files; show them in German
// with the numbers kept. Unknown notes are shown as they are.
function playgroupWarningText(text) {
  const brought = /^Brought count discrepancy: Times Brought = (\d+) vs Funnel Brought = (\d+)$/.exec(text);
  if (brought) return `Abweichende Zählung der Quelle: „Times Brought“ = ${StudioUI.num(Number(brought[1]), 0)}, „Funnel Brought“ = ${StudioUI.num(Number(brought[2]), 0)}`;
  const curve = /^On-curve calculation discrepancy: reported ([\d.]+)% but (\d+)\/(\d+) = ([\d.]+)%$/.exec(text);
  if (curve) return `Abweichung bei „On-curve“: Quelle meldet ${StudioUI.numFlex(Number(curve[1]), 2)} %, nachgerechnet ${StudioUI.num(Number(curve[2]), 0)}/${StudioUI.num(Number(curve[3]), 0)} = ${StudioUI.numFlex(Number(curve[4]), 2)} %`;
  return text;
}
function openInputModal({ title, description, placeholder, initialValue = "", multiline = false, submitText = "Speichern", onSubmit }) {
  const box = $("modal-box"); box.className = "plain";
  const input = multiline
    ? h("textarea", { placeholder, rows: "10", "aria-label": title })
    : h("input", { type: "text", placeholder, maxlength: "240", "aria-label": title });
  input.value = initialValue;
  const statusBox = h("div", {});
  const runSubmit = async () => {
    try { await onSubmit(input.value, statusBox); } catch (error) { fail(error); }
  };
  box.replaceChildren(...kids(
    h("h2", {}, title),
    description ? h("p", { class: "note" }, description) : null,
    input,
    statusBox,
    h("div", { class: "actions" },
      h("button", { type: "button", class: "primary", onclick: runSubmit }, submitText),
      h("button", { type: "button", onclick: closeModal }, "Abbrechen"))
  ));
  $("modal").hidden = false;
  input.focus();
}
function editDeckLabels() {
  const deck = state.decks.find((item) => item.deck_id === state.deckId);
  if (!deck) return;
  openInputModal({
    title: "Archetyp-Marken des Decks",
    description: "Mit Komma getrennt (leer löscht sie). Marken ordnen deine Decks und zählen nirgends als Wertung.",
    placeholder: "z. B. Combo, Blink, Tokens",
    initialValue: (deck.labels || []).join(", "),
    submitText: "Marken speichern",
    onSubmit: async (text) => {
      const done = await api(`/api/decks/${encodeURIComponent(deck.deck_id)}/labels`, "PUT", { labels: labelList(text) });
      deck.labels = done.labels; renderDeckLabels(); closeModal();
    },
  });
}
function openNewDeckModal() {
  openInputModal({
    title: "Neues Deck anlegen",
    description: `Legt ein neues leeres Deck für ${COMMANDER} an.`,
    placeholder: "Name des neuen Decks",
    initialValue: `${StudioCommander.shortName(COMMANDER)} Neu`,
    submitText: "Deck anlegen",
    onSubmit: async (name) => {
      const trimmed = (name || "").trim();
      if (!trimmed) { toast("Bitte einen Decknamen eingeben."); return; }
      const created = await api("/api/decks", "POST", { name: trimmed.slice(0, 80), commander_card_ids: state.commanderIds });
      state.deckId = created.deck_id; state.branch = "main";
      closeModal();
      await loadDecks(); await loadBranch();
      toast(`Deck „${trimmed}“ angelegt.`);
    },
  });
}
function openImportDecklistModal() {
  openInputModal({
    title: "Deckliste einfügen",
    description: "Füge eine Text- oder CSV-Deckliste ein (Plain, Arena, MTGO, Moxfield, Archidekt, Deckstats, CSV). Schritt 1 prüft die Liste gegen Sammlung und Farbidentität; erst nach Bestätigung wird dein Entwurf überschrieben.",
    placeholder: "1 Sol Ring\n1x Eternal Witness (2X2) 145\n...",
    multiline: true,
    submitText: "Liste prüfen",
    onSubmit: async (text, statusBox) => {
      if (!(text || "").trim()) { toast("Bitte eine Deckliste einfügen."); return; }
      const parsed = await api("/api/decklist-parse", "POST", { commander: COMMANDER, text });
      const cards = (parsed.in_collection || []).map((row) => ({ card_id: row.card_id, quantity: row.quantity, zone: "main" }));
      const missing = parsed.not_in_collection || [];
      const illegal = parsed.outside_color_identity || [];
      const badLines = parsed.unrecognized_lines || [];
      const unclear = parsed.ambiguous || [];
      const noGerman = parsed.german_names_available === false;
      const applyImport = () => {
        useCards(cards);
        changed();
        closeModal();
        toast(`${StudioUI.num(parsed.summary.in_collection_cards, 0)} Karten in den Entwurf übernommen.`);
      };
      statusBox.replaceChildren(...kids(
        h("p", {}, h("b", {}, `Erkanntes Format: ${parsed.detected_format || "plain"}`), ` · ${StudioUI.num(parsed.summary.in_collection_cards, 0)} Karten in Sammlung gefunden`),
        h("div", { class: "actions" },
          h("button", { type: "button", class: "primary", onclick: applyImport }, `In Entwurf übernehmen (${StudioUI.num(parsed.summary.in_collection_cards, 0)} Karten)`),
          h("button", { type: "button", onclick: closeModal }, "Verwerfen")),
        illegal.length ? h("div", {},
          h("h3", {}, `Außerhalb Farbidentität / Legalität (${StudioUI.num(illegal.length, 0)})`),
          h("ul", {}, illegal.map((m) => h("li", {}, `${StudioUI.num(m.quantity, 0)}x ${m.name}${m.reason ? ` — ${m.reason}` : ""}`)))) : null,
        missing.length ? h("div", {},
          h("h3", {}, `Nicht in deiner Sammlung (${StudioUI.num(missing.length, 0)})`),
          h("ul", {}, missing.map((m) => h("li", {}, `${StudioUI.num(m.quantity, 0)}x ${m.name} — nicht in deiner Sammlung`)))) : null,
        noGerman ? h("p", { class: "muted" }, "Deutsche Namen nicht verfügbar: nur englische Namen werden erkannt.") : null,
        unclear.length ? h("div", {},
          h("h3", {}, `Mehrdeutige Namen, nicht übernommen (${StudioUI.num(unclear.length, 0)})`),
          h("ul", {}, unclear.map((m) => h("li", {}, `Zeile ${StudioUI.num(m.line, 0)}: ${StudioUI.num(m.quantity, 0)}x ${m.name} — bezeichnet mehrere Karten: ${m.candidates.map((c) => c.name).join(" / ")}`)))) : null,
        badLines.length ? h("div", {},
          h("h3", {}, `Nicht erkannte Zeilen (${StudioUI.num(badLines.length, 0)})`),
          h("ul", {}, badLines.slice(0, 15).map((b) => h("li", {}, `Zeile ${StudioUI.num(b.line, 0)}: ${b.raw} (${b.reason})`)))) : null
      ));
    },
  });
}
// The universe source and bracket the tier list remembers: the builder asks for the same counted universe.
function strengthQuery() {
  try {
    const raw = localStorage.getItem("studio.strength.settings");
    const settings = raw ? JSON.parse(raw) : null;
    if (!settings || typeof settings !== "object") return "";
    const parts = [];
    if (typeof settings.universe_source === "string" && settings.universe_source) parts.push(`strength_universe=${encodeURIComponent(settings.universe_source)}`);
    if (typeof settings.bracket === "string" && settings.bracket) parts.push(`strength_bracket=${encodeURIComponent(settings.bracket)}`);
    return parts.length ? "&" + parts.join("&") : "";
  } catch (error) { return ""; }
}
async function loadPool() {
  const query = StudioCommander.query + strengthQuery() + StudioGcBand.scopeQuery(state) + (state.includeUnowned ? "&include_unowned=true" : "");
  applyPool(await api("/api/pool?" + query));
  try { localStorage.setItem("studio.universe.profile", state.universe); } catch (error) { /* view setting only */ }
  if ($("cohort")) $("cohort").disabled = Boolean(state.universe) || Boolean(state.gcBand) || (Boolean(state.countedUniverse) && !(state.cohorts.all || 0));
  renderBracketBar();
  renderGcBandBar();
}

// ---------- decks, variants, saving ----------
const variantKey = (part) => `studio.builder.${COMMANDER}.${part}`;
function rememberVariant() {
  StudioUI.remember(variantKey("deck"), state.deckId || "");
  StudioUI.remember(variantKey("branch"), state.branch || "");
}
async function loadDecks() {
  loadAllocation(api).then(() => renderPool()); // saved decks may have changed: bindings follow
  // Only the decks of the chosen commander; a deck never changes its commander here.
  const mine = (decks) => decks.filter((deck) => (deck.commanders || []).includes(COMMANDER));
  state.decks = mine(await api("/api/decks"));
  if (!state.decks.length) {
    const created = await api("/api/decks", "POST", { name: StudioCommander.shortName(COMMANDER), commander_card_ids: state.commanderIds });
    state.deckId = created.deck_id; state.decks = mine(await api("/api/decks"));
  }
  if (!state.deckId) { // first load after opening the page: reopen the variant that was open
    const wantedDeck = StudioUI.recall(variantKey("deck"), "");
    if (state.decks.some((deck) => deck.deck_id === wantedDeck)) {
      state.deckId = wantedDeck;
      const wantedBranch = StudioUI.recall(variantKey("branch"), "");
      const wanted = state.decks.find((deck) => deck.deck_id === wantedDeck);
      if (wanted.branches.some((item) => item.branch === wantedBranch)) state.branch = wantedBranch;
    }
  }
  if (!state.decks.some((deck) => deck.deck_id === state.deckId)) state.deckId = state.decks[0].deck_id;
  const deck = state.decks.find((item) => item.deck_id === state.deckId);
  if (!deck.branches.some((item) => item.branch === state.branch)) state.branch = deck.branches[0].branch;
  renderDeckLabels();
  $("deck-select").replaceChildren(...state.decks.map((item) => h("option", { value: item.deck_id, selected: item.deck_id === state.deckId }, item.name)));
  $("branch-select").replaceChildren(...deck.branches.map((item) => h("option", { value: item.branch, selected: item.branch === state.branch }, `${item.branch} (${StudioUI.num(item.cards, 0)})${item.has_draft ? " *" : ""}`)));
}
async function ensureUnownedLoadedFor(cards) {
  if (state.includeUnowned || !Array.isArray(cards)) return;
  const hasMissing = cards.some((entry) => entry && entry.zone === "main" && !state.byId.has(entry.card_id));
  if (!hasMissing) return;
  state.includeUnowned = true;
  if ($("f-unowned")) $("f-unowned").checked = true;
  await loadPool();
}
function useCards(cards) {
  state.list = new Map();
  let mainEntries = 0;
  let dropped = 0;
  for (const entry of cards) {
    if (entry.zone !== "main") continue;
    mainEntries += 1;
    if (state.byId.has(entry.card_id)) state.list.set(entry.card_id, entry.quantity);
    else dropped += 1;
  }
  // A card outside the pool (not owned and below the Zukauf selection) is not taken over; say so
  // instead of dropping it silently (#1648).
  if (dropped) toast(`${StudioUI.num(dropped, 0)} von ${StudioUI.num(mainEntries, 0)} Karten sind nicht im Pool (Sammlung oder Zukauf-Auswahl) und wurden nicht übernommen.`);
}
let discardingStaleDraft = false;
async function discardStaleDraft() {
  if (discardingStaleDraft) return; // one DELETE per click series
  if (committing) { toast("Speichern läuft schon, bitte warten."); return; } // the save decides first
  discardingStaleDraft = true;
  try {
    await api(`/api/decks/${encodeURIComponent(state.deckId)}/branches/${encodeURIComponent(state.branch)}/draft`, "DELETE");
    await loadDecks();
    await loadBranch();
  } finally {
    discardingStaleDraft = false;
  }
}
async function loadBranch() {
  const deck = state.decks.find((item) => item.deck_id === state.deckId);
  const branch = deck.branches.find((item) => item.branch === state.branch);
  state.baseRevision = branch.revision_id;
  state.baseStale = false;
  state.diffBaseRev = null;
  rememberVariant();
  const [revision, draft] = await Promise.all([
    api(`/api/revisions/${encodeURIComponent(branch.revision_id)}`),
    api(`/api/decks/${encodeURIComponent(state.deckId)}/branches/${encodeURIComponent(state.branch)}/draft`),
  ]);
  state.savedSeq = state.changeSeq; // the list comes from the server: nothing of this tab is unsent
  state.draftConflict = false;
  state.needsDraftPut = false;
  if (draft.draft) {
    // a draft written on another saved state (main moved by an adoption) keeps its own base:
    // saving it would put that old base back, so it is named stale and saving is refused
    if (draft.draft.base_revision_id && draft.draft.base_revision_id !== branch.revision_id) {
      state.baseRevision = draft.draft.base_revision_id;
      state.baseStale = true;
    }
    state.draftUpdatedAt = draft.draft.updated_at || "";
    await ensureUnownedLoadedFor(draft.draft.cards);
    useCards(draft.draft.cards); state.dirty = true;
  } else {
    state.draftUpdatedAt = "";
    await ensureUnownedLoadedFor(revision.cards);
    useCards(revision.cards); state.dirty = false; state.issues = revision.issues; state.shape = revision.shape; state.deckRoles = revision.roles || {}; state.combos = revision.combos || null;
  }
  renderSaveState();
  renderAll(); await syncDraft();
}
// The saved state of `branch` now, from the server; null when the branch does not exist yet.
async function currentBranchRevision(branch, deckId = state.deckId) {
  const fresh = await api("/api/decks");
  const deck = fresh.find((item) => item.deck_id === deckId);
  const row = deck && (deck.branches || []).find((item) => item.branch === branch);
  return row ? row.revision_id : null;
}
const STALE_DRAFT_TEXT = "Entwurf ist veraltet: der Stand darunter wurde inzwischen geändert. Nichts gespeichert. „Neue Variante“ behält die Arbeit; Neu laden verwirft sie.";
const cardsKey = (cards) => JSON.stringify(cards.map((card) => [card.card_id, card.zone, card.quantity]).sort());
let committing = false;
// While a save is in the air the deck and variant selectors stay locked, so the editor keeps
// showing the list that is being saved.
function setSwitchLocked(locked) {
  for (const id of ["deck-select", "branch-select"]) { const box = $(id); if (box) box.disabled = locked; }
}
// #1727: every save names the head it expects (`expected_parent`): the base of this draft for
// the own variant, null for a new variant (with the base as `parent_revision_id`). A 409 from
// the server means the variant moved: nothing is retried, the draft is named stale, and the
// work can still be saved as a new variant. The target branch is read fresh from the server,
// never from `state.decks`. The deck and variant of the click are kept: when another one is
// open once an answer arrives, that editor state is left as it is and only the list refreshes.
async function commitRevision(branch = state.branch, note = "") {
  if (committing) { toast("Speichern läuft schon, bitte warten."); return; } // one POST per click series
  committing = true;
  setSwitchLocked(true);
  const seq = state.changeSeq;
  const deckId = state.deckId;
  const fromBranch = state.branch;
  const base = state.baseRevision;
  const isNew = branch !== fromBranch;
  const stillHere = () => state.deckId === deckId && state.branch === fromBranch;
  const left = async (text) => { await loadDecks(); toast(`${text} Die Ansicht bleibt bei der inzwischen gewählten Variante.`); };
  try {
    const current = await currentBranchRevision(branch, deckId);
    const cards = entries();
    let result = null;
    let already = false;
    if (current !== null && (isNew || current !== base)) {
      // the branch holds another state than expected: if it holds exactly this list, an earlier
      // save went through; that is reported as saved, not as stale or as a taken name
      const head = await api(`/api/revisions/${encodeURIComponent(current)}`);
      if (cardsKey(head.cards || []) === cardsKey(cards)) {
        result = { revision_id: current }; already = true;
      } else if (isNew) {
        toast(`Variante „${branch}“ gibt es schon: nichts gespeichert, bitte einen anderen Namen wählen.`);
        return;
      } else {
        if (!stillHere()) { await left(`Die Variante „${fromBranch}“ hat sich geändert, nichts gespeichert.`); return; }
        state.baseStale = true;
        renderSaveState();
        toast(STALE_DRAFT_TEXT);
        return;
      }
    }
    if (!result) {
      try {
        result = await api(`/api/decks/${encodeURIComponent(deckId)}/revisions`, "POST", {
          cards, branch, note, parent_revision_id: base, expected_parent: isNew ? null : base,
        });
      } catch (error) {
        if (error && error.status === 409) {
          if (isNew) { toast(StudioUI.germanError(error)); return; }
          if (!stillHere()) { await left(`Die Variante „${fromBranch}“ hat sich geändert, nichts gespeichert.`); return; }
          state.baseStale = true;
          renderSaveState();
          toast(STALE_DRAFT_TEXT);
          return;
        }
        throw error;
      }
    }
    const hints = [];
    if (result.hinweis) hints.push(result.hinweis);
    if (isNew) {
      // the work moved to the new variant; the old draft goes, and a failure is only named
      try {
        await api(`/api/decks/${encodeURIComponent(deckId)}/branches/${encodeURIComponent(fromBranch)}/draft`, "DELETE");
      } catch (error) {
        hints.push(`Der alte Entwurf in „${fromBranch}“ konnte nicht verworfen werden (${StudioUI.germanError(error)}); bitte dort verwerfen, nicht erneut speichern.`);
      }
    } else if (!already && result.revision_id === base) {
      // the same content as the head: the server keeps a draft on that head (#1733); this
      // tab's draft is that content, so it goes, otherwise it would block "Ja, übernehmen"
      try {
        const found = await api(`/api/decks/${encodeURIComponent(deckId)}/branches/${encodeURIComponent(branch)}/draft`);
        if (found.draft && found.draft.base_revision_id === base && cardsKey(found.draft.cards) === cardsKey(cards)) {
          await api(`/api/decks/${encodeURIComponent(deckId)}/branches/${encodeURIComponent(branch)}/draft`, "DELETE");
        }
      } catch (error) {
        hints.push(`Der unveränderte Entwurf konnte nicht verworfen werden (${StudioUI.germanError(error)}).`);
      }
    }
    const where = ` in Variante „${branch}“`;
    const done = already ? `Dieser Stand war schon gespeichert${where}.` : "Stand gespeichert.";
    if (!stillHere()) { await left([already ? done : `Stand gespeichert${where}.`, ...hints].join(" ")); return; }
    state.branch = branch; state.baseRevision = result.revision_id; state.baseStale = false; state.savedSeq = Math.max(state.savedSeq, seq);
    // the list now in the editor may differ from the one saved (an edit made while the save was
    // on its way, or a list loaded meanwhile): that is an unsaved draft on the NEW base, never saved
    state.dirty = state.changeSeq !== seq || cardsKey(entries()) !== cardsKey(cards);
    state.draftUpdatedAt = ""; state.draftConflict = false; state.needsDraftPut = state.dirty;
    rememberVariant();
    await loadDecks(); renderHeader(); renderSaveState(); toast([done, ...hints].join(" "));
    if (state.dirty) syncDraft();
  } catch (error) { fail(error); } finally { committing = false; setSwitchLocked(false); }
}
function saveRevision(branch = state.branch) {
  openInputModal({
    title: "Als Stand speichern",
    description: `Speichert den aktuellen Entwurf in Variante „${branch}“.`,
    placeholder: "Kurze Notiz zu diesem Stand (darf leer sein)",
    initialValue: "",
    submitText: "Stand speichern",
    onSubmit: async (note) => {
      closeModal();
      await commitRevision(branch, note || "");
    },
  });
}
function openNewBranchModal() {
  openInputModal({
    title: "Neue Variante anlegen",
    description: "Speichert die aktuelle Liste als eigenen Varianten-Zweig dieses Decks.",
    placeholder: "Name der neuen Variante",
    initialValue: "",
    submitText: "Variante speichern",
    onSubmit: async (name) => {
      const trimmed = (name || "").trim().slice(0, 60);
      if (!trimmed) { toast("Bitte einen Namen für die Variante eingeben."); return; }
      closeModal();
      await commitRevision(trimmed, "");
    },
  });
}
async function showHistory() {
  const rows = await api(`/api/decks/${encodeURIComponent(state.deckId)}/history`);
  const box = $("modal-box"); box.className = "plain"; box.replaceChildren(h("h2", {}, "Verlauf"),
    h("div", { class: "table-wrap" }, h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Gespeichert"), h("th", {}, "Variante"), h("th", { class: "num" }, "Karten"), h("th", {}, "Notiz"), h("th", {}, ""))),
      h("tbody", {}, rows.map((row) => h("tr", {},
        h("td", {}, row.created_at.replace("T", " ").replace("Z", "")),
        h("td", {}, row.branch || "–"),
        h("td", { class: "num" }, StudioUI.num(row.cards, 0)),
        h("td", {}, row.note),
        h("td", {}, h("div", { class: "actions" },
          h("button", { type: "button", class: "small", onclick: async () => { const revision = await api(`/api/revisions/${encodeURIComponent(row.revision_id)}`); await ensureUnownedLoadedFor(revision.cards); useCards(revision.cards); closeModal(); changed(); toast("Alter Stand geladen. Er wird erst mit Speichern zum aktuellen Stand."); } }, "Laden"),
          h("button", { type: "button", class: "small", onclick: () => { state.diffBaseRev = row.revision_id; state.tab = "diff"; closeModal(); renderDeck(); } }, "Vergleichen")))))))),
    h("div", { id: "deck-series-slot" }),
    h("div", { id: "experiment-slot" }),
    h("div", { class: "actions" }, h("button", { type: "button", onclick: closeModal }, "Schließen")));
  $("modal").hidden = false;
  if (typeof renderDeckSeries === "function") {
    box.className = "plain wide";
    renderDeckSeries($("deck-series-slot"), rows, { h, api, deckId: state.deckId, open: openSeriesFromHistory });
  }
  if (typeof renderExperiments === "function") {
    renderExperiments($("experiment-slot"), rows, {
      h, api, deckId: state.deckId, onDecided: afterExperimentDecision,
      localMainDraft: () => state.branch === "main" && (state.dirty || state.baseStale),
    });
  }
}
// B2b (#1658): after an explicit decision the view reads everything again. An adoption moves
// main on the server; a clean editor on main loads it, a draft is kept and named as outdated.
async function afterExperimentDecision(decision) {
  if (decision !== "adopted") { await showHistory(); return; }
  await loadDecks(); // while the dialog is open: a failure is shown there
  closeModal();
  if (state.branch !== "main") { toast("Variante übernommen: main zeigt jetzt den Variantenstand."); return; }
  if (state.dirty) { state.baseStale = true; renderSaveState(); return; }
  await loadBranch();
  toast("Variante übernommen: main zeigt jetzt den Variantenstand.");
}
async function openSeriesFromHistory(seriesId) {
  state.activePaired = await api(`/api/simulations/paired/${encodeURIComponent(seriesId)}`);
  state.tab = "sim"; closeModal(); renderDeck();
}
function _draftExportText() {
  const lines = ["Commander"];
  for (const cid of state.commanderIds || []) {
    const card = state.byId.get(cid);
    if (card) lines.push(`1 ${card.name}`);
  }
  lines.push("", "Deck");
  const sorted = deckCards().slice().sort((a, b) => a.name.localeCompare(b.name));
  for (const card of sorted) {
    lines.push(`${state.list.get(card.card_id) || 1} ${card.name}`);
  }
  return lines.join("\n") + "\n";
}
function _draftExportSnapshot() {
  const commanders = (state.commanderIds || []).map((cid) => (state.byId.get(cid) || {}).name || cid);
  const deck = state.decks.find((item) => item.deck_id === state.deckId);
  const cards = (state.commanderIds || []).map((cid) => ({ oracle_name: (state.byId.get(cid) || {}).name || cid, quantity: 1, zone: "commander" }));
  for (const card of deckCards().slice().sort((a, b) => a.name.localeCompare(b.name))) {
    cards.push({ oracle_name: card.name, quantity: state.list.get(card.card_id) || 1, zone: "main" });
  }
  return JSON.stringify({
    deck_id: state.deckId || "draft",
    name: `${(deck && deck.name) || state.deckId || "Entwurf"} (Entwurf)`,
    studio_revision_id: state.baseRevision || null,
    commander: { commanders, uses_partner: commanders.length > 1, commander_identity_override: null },
    cards,
  }, null, 2) + "\n";
}
function _downloadBlob(filename, content, mime) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const link = h("a", { href: url, download: filename });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function showExport() {
  const box = $("modal-box"); box.className = "plain";
  const slug = (state.deckId || "deck").replace(/[^a-zA-Z0-9_-]+/g, "_");
  const nodes = [h("h2", {}, "Export")];
  if (state.dirty || !state.baseRevision) {
    nodes.push(
      h("p", { class: "note" }, "Aktueller Entwurf (noch nicht als Stand gespeichert) — kann direkt als Textdatei oder JSON heruntergeladen werden."),
      h("div", { class: "actions" },
        h("button", { type: "button", class: "primary", onclick: () => _downloadBlob(`${slug}-entwurf.txt`, _draftExportText(), "text/plain;charset=utf-8") }, "Entwurf als Text (.txt)"),
        h("button", { type: "button", onclick: () => _downloadBlob(`${slug}-entwurf.json`, _draftExportSnapshot(), "application/json;charset=utf-8") }, "Entwurf als Lab-Datei (.json)"))
    );
  }
  if (state.baseRevision) {
    const base = `/api/revisions/${encodeURIComponent(state.baseRevision)}/export`;
    const dossierUrl = `/api/revisions/${encodeURIComponent(state.baseRevision)}/dossier`;
    nodes.push(
      h("p", {}, state.dirty ? "Zuletzt gespeicherter Stand " : "Gespeicherter Stand ", h("code", {}, state.baseRevision), ":"),
      h("div", { class: "actions" },
        h("a", { href: base + "?format=txt", target: "_blank", rel: "noopener" }, "Gespeicherter Stand als Text"),
        h("a", { href: base + "?format=json", target: "_blank", rel: "noopener" }, "Gespeicherter Stand als Lab-Datei (JSON)"),
        h("a", { id: "export-dossier-link", href: dossierUrl, target: "_blank", rel: "noopener" }, "Deck-Dossier (.md)"),
        h("button", { type: "button", id: "export-dossier-download", onclick: async () => {
          try {
            const resp = await fetch(dossierUrl);
            if (!resp.ok) throw new Error(String(resp.status));
            const md = await resp.text();
            _downloadBlob(`${slug}-dossier.md`, md, "text/markdown;charset=utf-8");
          } catch (_) { toast("Dossier konnte nicht geladen werden.", "error"); }
        } }, "Dossier herunterladen (.md)"))
    );
  }
  nodes.push(...exportFormatsSection({ h, state, toast, slug, download: _downloadBlob }));
  nodes.push(h("div", { class: "actions" }, h("button", { type: "button", id: "buildlist-open", title: "Karten dieser Liste nach Lagerort gruppiert", onclick: () => showBuildList({ h, api, state, entries, closeModal, toast, fail }) }, "Bauliste nach Standort"), h("button", { type: "button", onclick: closeModal }, "Schließen")));
  box.replaceChildren(...nodes);
  $("modal").hidden = false;
}

// ---------- start ----------
function setupControls() {
  $("color-filter").replaceChildren(...["W", "U", "B", "R", "G", "C"].map((letter) => h("button", { type: "button", class: "chip", title: letter === "C" ? "farblos" : letter, onclick: (event) => {
    if (state.colors.has(letter)) state.colors.delete(letter); else state.colors.add(letter);
    event.currentTarget.classList.toggle("on"); state.shown = 120; renderPool();
  } }, letter)));
  $("type-filter").replaceChildren(h("option", { value: "" }, "alle Typen"), ...GROUPS.map((group) => h("option", { value: group }, GROUP_NAMES[group])));
  $("role-filter").replaceChildren(h("option", { value: "" }, "alle Rollen"), ...state.roles.map((role) => h("option", { value: role }, roleName(role))), h("option", { value: "-" }, "ohne Rollenmarke"));
  $("cohort").replaceChildren(...visibleCohortEntries(state.cohorts).map(([key, size]) => h("option", { value: key }, `${cohortName(key)} (${StudioUI.num(size, 0)})`)));
  $("universe").replaceChildren(h("option", { value: "" }, "kein Universum"), ...(state.universeProfiles || []).map((p) => h("option", { value: p.name, selected: p.name === state.universe }, p.name)));
  $("universe").addEventListener("change", async () => {
    Object.assign(state, pickView(StudioGcBand.select(state, "universe", $("universe").value)));
    try { await loadPool(); if (state.subsetNames.length) await applySubset(state.subsetNames); else renderAll(); } catch (error) { fail(error); }
  });
  $("cohort").disabled = Boolean(state.universe) || Boolean(state.gcBand) || (Boolean(state.countedUniverse) && !(state.cohorts.all || 0));
  renderBracketBar();
  renderGcBandBar();
  const sorts = [["freq:-1", "Häufigkeit in Quelldecks"], ["name:1", "Name"], ["mana_value:1", "Manawert"], ["edhrec:-1", "EDHREC-Anteil"], ["synergy:-1", "Synergie"], ["strength:-1", "Stärke-Index"], ["edhrec_rank:1", "EDHREC-Rang"], ["available:-1", "freie Kopien"]];
  $("sort").replaceChildren(...sorts.map(([value, label]) => h("option", { value }, label)), h("option", { value: "" }, "Spaltenkopf"));
  const savedSort = StudioUI.recall("studio.builder.sort", "");
  if (savedSort && sorts.some((item) => item[0] === savedSort)) { const [key, dir] = savedSort.split(":"); state.sortKey = key; state.sortDir = Number(dir); $("sort").value = savedSort; if (key === "strength") loadStrength(); }
  $("sort").addEventListener("change", () => { if (!$("sort").value) return; const [key, dir] = $("sort").value.split(":"); state.sortKey = key; state.sortDir = Number(dir); StudioUI.remember("studio.builder.sort", $("sort").value); if (key === "strength") loadStrength(); renderPool(); });
  $("cohort").addEventListener("change", () => {
    const hadBand = Boolean(state.gcBand);
    Object.assign(state, pickView(StudioGcBand.select(state, "cohort", $("cohort").value)));
    if (hadBand) { loadPool().then(renderAll).catch(fail); return; }
    renderBracketBar(); renderUniverseInfo(); renderPool(); renderDeck(); });
  for (const id of ["q", "type-filter", "role-filter", "label-filter", "mv-min", "mv-max", "f-free", "f-notin", "f-fav", "f-excl", "f-sim"]) if ($(id)) $(id).addEventListener("input", () => { state.shown = 120; renderPool(); });
  if (typeof StudioSearch !== "undefined" && StudioSearch.attachSyntaxHelper && $("q")) {
    StudioSearch.attachSyntaxHelper($("q"), () => { state.shown = 120; renderPool(); });
  }
  // "Stufe zeigen": the current tier on every card (view setting, on unless switched off).
  state.showTier = StudioUI.recall("studio.builder.show-tier", "1") !== "0";
  $("f-tier").checked = state.showTier;
  if (state.showTier) loadStrength();
  $("f-tier").addEventListener("change", () => {
    state.showTier = $("f-tier").checked; StudioUI.remember("studio.builder.show-tier", state.showTier ? "1" : "0");
    if (state.showTier) loadStrength();
    renderPool(); renderDeck();
  });
  const views = [["grid", "Bilder"], ["table", "Tabelle"]];
  const drawViews = () => $("view-toggle").replaceChildren(...views.map(([key, label]) => h("button", { type: "button", class: "chip" + (state.view === key ? " on" : ""), "aria-pressed": state.view === key, onclick: () => { state.view = key; drawViews(); renderPool(); } }, label)));
  drawViews();
  const applyBuilderFilterPreset = async (cfg) => {
    $("q").value = cfg.q || "";
    $("type-filter").value = cfg.type || "";
    $("role-filter").value = cfg.role || "";
    $("mv-min").value = cfg.mvMin || "";
    $("mv-max").value = cfg.mvMax || "";
    $("f-free").checked = cfg.free !== false;
    $("f-notin").checked = Boolean(cfg.notin);
    $("f-fav").checked = Boolean(cfg.fav);
    $("f-excl").checked = Boolean(cfg.excl);
    state.superfriendsFilter = cfg.superfriends || "";
    state.colors = new Set(Array.isArray(cfg.colors) ? cfg.colors : []);
    for (const btn of $("color-filter").querySelectorAll("button")) btn.classList.toggle("on", state.colors.has(btn.textContent));
    state.shown = 120;
    if (state.superfriendsFilter === "missing") {
      $("f-free").checked = false;
      if (!state.includeUnowned) {
        state.includeUnowned = true;
        if ($("f-unowned")) $("f-unowned").checked = true;
        try { await loadPool(); renderAll(); } catch (error) { fail(error); }
        return;
      }
    }
    renderPool();
  };
  const renderQuickFilterPresets = () => {
    if (!$("quick-filter-presets")) return;
    const toggleSuperfriends = async (kind) => {
      const next = state.superfriendsFilter === kind ? "" : kind;
      state.superfriendsFilter = next;
      if (next === "missing") {
        $("f-free").checked = false;
        if (!state.includeUnowned) {
          state.includeUnowned = true;
          if ($("f-unowned")) $("f-unowned").checked = true;
          state.shown = 120;
          renderQuickFilterPresets();
          try { await loadPool(); renderAll(); } catch (error) { fail(error); }
          return;
        }
      }
      state.shown = 120;
      renderQuickFilterPresets();
      renderPool();
    };
    const sfChip = (kind, label, title) => h("button", {
      type: "button",
      class: "chip" + (state.superfriendsFilter === kind ? " on" : ""),
      "aria-pressed": state.superfriendsFilter === kind,
      title,
      onclick: () => toggleSuperfriends(kind),
    }, label);
    $("quick-filter-presets").replaceChildren(
      h("button", { type: "button", class: "chip", onclick: () => { applyBuilderFilterPreset({ free: true }); renderQuickFilterPresets(); } }, "Standardfilter"),
      h("button", { type: "button", class: "chip", onclick: () => { applyBuilderFilterPreset({ free: true, notin: true }); renderQuickFilterPresets(); } }, "Frei & nicht im Deck"),
      h("button", { type: "button", class: "chip", onclick: () => { applyBuilderFilterPreset({ free: true, mvMax: "2" }); renderQuickFilterPresets(); } }, "Frühe Aktionen (MV ≤ 2)"),
      h("button", { type: "button", class: "chip", onclick: () => { applyBuilderFilterPreset({ free: true, type: "Creature" }); renderQuickFilterPresets(); } }, "Kreaturen (frei)"),
      h("button", { type: "button", class: "chip", onclick: () => { applyBuilderFilterPreset({ free: true, role: "-" }); renderQuickFilterPresets(); } }, "Ohne Rollenmarke"),
      sfChip("planeswalker", "Planeswalker", "Filtert wörtlich nach Typzeile „Planeswalker“."),
      sfChip("proliferate", "Proliferate", "Filtert wörtlich nach „Proliferate“ im Oracle-Text."),
      sfChip("counters", "Counter/Loyalty", "Filtert wörtlich nach „counter(s)“ als Marke (nicht das Kartenwort „counter target spell“) oder „loyalty“ im Oracle-Text."),
      sfChip("boardwipe", "Boardwipes", "Filtert nach der Tagger-Rolle „board_wipe“ (öffentliche Scryfall-Tagger-Marke, nicht vollständig). Karten ohne Rollendaten sind unbekannt und erscheinen hier nicht."),
      sfChip("fixing5c", "5C-Fixierung", "Filtert nach Karten, deren erzeugtes Mana (Scryfall „produced_mana“) alle fünf Farben W, U, B, R und G enthält."),
      sfChip("missing", "Nur Zukauf (fehlt)", "Zeigt nur fehlende Karten außerhalb deiner Sammlung (aktiviert den Zukauf-Pool)."),
      h("button", { type: "button", class: "chip", onclick: () => {
        const snapshot = { q: $("q").value, type: $("type-filter").value, role: $("role-filter").value, mvMin: $("mv-min").value, mvMax: $("mv-max").value, free: $("f-free").checked, notin: $("f-notin").checked, fav: $("f-fav").checked, excl: $("f-excl").checked, superfriends: state.superfriendsFilter, colors: [...state.colors] };
        StudioUI.remember("studio.builder.savedPreset", JSON.stringify(snapshot));
        toast("Filteransicht gespeichert.");
      } }, "Ansicht merken"),
      h("button", { type: "button", class: "chip", onclick: () => {
        try {
          const raw = StudioUI.recall("studio.builder.savedPreset", "");
          if (!raw) { toast("Noch keine Filteransicht gespeichert."); return; }
          applyBuilderFilterPreset(JSON.parse(raw));
          renderQuickFilterPresets();
        } catch (_) { toast("Gespeicherte Filteransicht konnte nicht geladen werden."); }
      } }, "Gemerkte Ansicht")
    );
  };
  renderQuickFilterPresets();
  if ($("f-unowned")) {
    $("f-unowned").checked = Boolean(state.includeUnowned);
    $("f-unowned").addEventListener("change", async () => {
      state.includeUnowned = $("f-unowned").checked;
      if (state.includeUnowned) {
        $("f-free").checked = false;
      } else if (state.superfriendsFilter === "missing") {
        state.superfriendsFilter = "";
        renderQuickFilterPresets();
      }
      state.shown = 120;
      try { await loadPool(); renderAll(); } catch (error) { fail(error); }
    });
  }
  setupFilterToggle();
  $("columns").addEventListener("click", () => { $("column-menu").hidden = !$("column-menu").hidden; });
  $("column-menu").replaceChildren(...COLUMNS.map(([key, label]) => h("label", {}, h("input", { type: "checkbox", checked: state.columns.has(key), onchange: (event) => {
    if (event.target.checked) state.columns.add(key); else state.columns.delete(key);
    try { localStorage.setItem("studio-columns", JSON.stringify([...state.columns])); } catch (error) { /* view setting only */ }
    if (key === "trend" && event.target.checked) loadCardTrend().catch(() => {});
    state.view = "table"; drawViews(); renderPool();
  } }), " " + label)));
  $("f-sim").addEventListener("change", () => {
    const info = state.simReadiness;
    if ($("f-sim").checked && simAllReady()) toast(`Alle ${StudioUI.num(info.total + (state.simReadinessUnowned ? state.simReadinessUnowned.total : 0), 0)} Karten des Pools sind für den Simulator bereit: der Filter ändert nichts.`);
  });
  $("play-state").addEventListener("click", () => {
    if (state.dirty || !state.baseRevision) { toast("Der Entwurf ist noch nicht als Stand gespeichert. Speichere ihn zuerst mit „Als Stand speichern“; gespielt wird immer der gespeicherte Stand."); return; }
    location.href = playAddress(state.baseRevision);
  });
  $("save").addEventListener("click", () => saveRevision());
  $("history").addEventListener("click", showHistory);
  $("export").addEventListener("click", showExport);
  $("deck-labels").addEventListener("click", editDeckLabels);
  if ($("new-deck")) $("new-deck").addEventListener("click", openNewDeckModal);
  if ($("import-text")) $("import-text").addEventListener("click", openImportDecklistModal);
  $("new-branch").addEventListener("click", openNewBranchModal);
  $("deck-select").addEventListener("change", async () => { state.deckId = $("deck-select").value; await loadDecks(); await loadBranch(); });
  $("branch-select").addEventListener("change", async () => { state.branch = $("branch-select").value; await loadBranch(); });
  $("modal").addEventListener("click", (event) => { if (event.target === $("modal")) closeModal(); });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeModal(); });
}
async function start() {
  $("pool-body").replaceChildren(StudioUI.loading("Kartenpool lädt …"));
  await StudioCommander.fill($("commander-select"));
  // The layer figures and the data-state box ask side by side (the server computes them once and
  // shares the answer), not one after the other.
  api(`/api/layers?commander=${encodeURIComponent(COMMANDER)}`).then((layers) => { state.layers = layers; if (state.tab === "compare") renderDeck(); }).catch(() => {});
  StudioUI.dataState($("data-state"), COMMANDER).catch(() => {});
  try {
    const stored = JSON.parse(localStorage.getItem("studio-columns") || "null");
    if (Array.isArray(stored)) state.columns = new Set(stored);
  } catch (error) { /* view setting only */ }
  if (state.columns.has("trend")) loadCardTrend().catch(() => {});
  try {
    let remembered = "";
    try { remembered = localStorage.getItem("studio.universe.profile") || ""; } catch (error) { /* view setting only */ }
    state.universeProfiles = await api("/api/universe/profiles").catch(() => []);
    state.universe = state.universeProfiles.some((p) => p.name === remembered) ? remembered : "";
    const poolQuery = StudioCommander.query + strengthQuery() + (state.universe ? `&profile=${encodeURIComponent(state.universe)}` : "");
    // The requests do not depend on each other, so they run side by side: the pool (the first
    // thing the page shows), the cohort figures, the simulations, the recorded games and the tier
    // list. What is applied, and in which order, is unchanged below.
    if (StudioUI.recall("studio.builder.show-tier", "1") !== "0" || StudioUI.recall("studio.builder.sort", "").startsWith("strength:")) {
      state.strengthPrefetch = strengthRequest();
      state.strengthPrefetch.catch(() => {}); // loadStrength reads the outcome (and retries without remembered settings)
    }
    const poolRequest = api("/api/pool?" + poolQuery).catch(async (error) => {
      if (!state.universe) throw error; // a remembered profile of another commander must not block the builder
      state.universe = "";
      return api("/api/pool?" + StudioCommander.query);
    });
    const otherRequests = Promise.all([api("/api/cohorts?" + StudioCommander.query), api("/api/simulations?" + StudioCommander.query), api("/api/games").catch(() => []), api("/api/simulations/paired").catch(() => []), api("/api/universe/gc-bands?" + StudioCommander.query).catch(() => null)]);
    otherRequests.catch(() => {}); // awaited after the pool: the pool's own error is shown first
    const pool = await poolRequest;
    const [shapes, sims, recordedGames, pairedList, gcBandData] = await otherRequests;
    state.gcBandData = gcBandData;
    applyPool(pool);
    state.shapes = shapes; state.simulations = sims || []; state.recordedGames = recordedGames || [];
    state.pairedHistory = pairedList || [];
    const runningPaired = state.pairedHistory.find((j) => j.status === "running" || j.status === "pending");
    if (runningPaired) { state.activePaired = runningPaired; pollPaired(runningPaired.series_id); }
    setupControls(); await loadDecks(); await loadBranch();
  } catch (error) {
    $("pool-body").replaceChildren(h("p", {}, "Das Studio konnte die Daten nicht laden: " + StudioUI.germanError(error)), h("p", { class: "muted" }, `Gewählter Commander: ${COMMANDER}. Er muss in der Sammlung stehen; sonst oben einen anderen Commander wählen. Sind Sammlung und Kartendaten importiert?`));
  }
}
start();
