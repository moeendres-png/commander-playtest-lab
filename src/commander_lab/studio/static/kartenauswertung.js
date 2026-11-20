"use strict";
// "Karten-Auswertung aus Partien" (#1526): per-card win share with the card in the first dealt
// hand versus without, read-only from GET /api/outcomes. Cohort SIMULATED_RESULT only; never
// mixed with usage/tournament figures and never part of the tier list (weight 0).
// DOM only through h() and text nodes; numbers only through StudioUI.num / StudioUI.pct.
// Rendered by app.js (Simulation tab) through renderCardOutcomes(slot, deps).
// Per deck state (#1657): the answer names its known stands (deck_hash) and "Stand unbekannt"
// apart; several stands are only shown stratified (strata = number of stands), never added.

const OUTCOMES_CARD_ORDER = { MEASURED: 0, INSUFFICIENT_SAMPLE: 1 };

const OUTCOMES_QUAL_LABELS = {
  QUALIFIED: "QUALIFIED (qualifiziert)",
  BRIDGE_AHEAD_OF_QUALIFICATION: "BRIDGE_AHEAD_OF_QUALIFICATION (Bridge neuer als Qualifizierung)",
};

const outcomesDeckHash = (revisionId) => {
  if (!revisionId || typeof revisionId !== "string") return "unbekannt";
  const at = revisionId.indexOf("@");
  return at >= 0 && at + 1 < revisionId.length ? revisionId.slice(at + 1) : revisionId;
};

const outcomesPp = (value) =>
  value === null || value === undefined ? "zu wenig Daten" : `${value >= 0 ? "+" : ""}${StudioUI.num(value, 1)} pp`;

const outcomesPpInterval = (ci) =>
  Array.isArray(ci) && ci.length === 2 ? `[${outcomesPp(ci[0])}; ${outcomesPp(ci[1])}]` : "zu wenig Daten";

const outcomesPctInterval = (rate, ci) => {
  if (rate === null || rate === undefined) return "zu wenig Daten";
  const pct = StudioUI.pct(rate);
  if (!Array.isArray(ci) || ci.length !== 2) return pct;
  return `${pct} [${StudioUI.pct(ci[0])}; ${StudioUI.pct(ci[1])}]`;
};

const outcomesRatio = (wins, games) => {
  if (games === null || games === undefined || games <= 0) return "unbekannt";
  const w = Number.isInteger(wins) ? StudioUI.num(wins, 0) : StudioUI.num(wins, 1);
  return `${w} / ${StudioUI.num(games, 0)}`;
};

const outcomesInt = (value) => (typeof value === "number" ? StudioUI.num(value, 0) : "unbekannt");

const outcomesShortHash = (value) =>
  typeof value === "string" && value ? (value.length > 12 ? `${value.slice(0, 12)}…` : value) : "unbekannt";

// The label of an answer that carries deck states (schema 2): which stand(s) the top table is.
function outcomesStandLabel(data, baseRevision) {
  const stands = Array.isArray(data.stands) ? data.stands : [];
  const current = (stand) => Array.isArray(stand.revision_ids) && baseRevision && stand.revision_ids.includes(baseRevision);
  if (!stands.length) return "kein Deck-Stand bekannt (alle Partien: Stand unbekannt)";
  if (stands.length === 1) {
    return `Deck-Stand (Hash): ${outcomesShortHash(stands[0].deck_hash)}${current(stands[0]) ? " (gewählter Stand)" : ""}`;
  }
  const pooled = data.pooling && data.pooling.status === "POOLED";
  return `${StudioUI.num(stands.length, 0)} Deck-Stände ${pooled ? "geschichtet (je Stand eigene Differenz, gewichtet zusammengeführt)" : "nicht zusammengeführt"}`;
}

function outcomesStandNote(h, data) {
  const unknown = data.unknown_stand;
  const unknownText = unknown && typeof unknown.games_total === "number"
    ? `Stand unbekannt: ${outcomesInt(unknown.games_total)} Partien (getrennt gezählt, nie addiert)`
    : "Stand unbekannt: keine Partien";
  const pooling = data.pooling || {};
  const parts = [`Schichten (Deck-Stände): ${outcomesInt(data.strata)}`, unknownText];
  if (pooling.reason) parts.push(`Nicht zusammengeführt: ${pooling.reason}`);
  if (pooling.method) parts.push(`Verfahren: ${pooling.method}`);
  return h("p", { class: "muted" }, parts.join(" · "));
}

const outcomesQueryLabel = (queryId, baseRevision, revHash) =>
  baseRevision && queryId === baseRevision
    ? `Deck-Stand (Hash): ${revHash}`
    : `über Deck-ID ${queryId || "unbekannt"}, Deck-Stand der Partien unbekannt`;

function outcomesCardRow(h, card, deps) {
  const isMeasured = card && card.status === "MEASURED";
  const reasonText = card && card.status === "INSUFFICIENT_SAMPLE"
    ? (card.reason || "zu wenig Daten")
    : "unbekannter Status (zu wenig Daten)";
  // A row over several deck states (#1657): counts are sums, rates exist only per stand.
  const pooledRow = card && typeof card.strata === "number";

  let diffCell;
  if (!isMeasured) {
    diffCell = h("span", { class: "muted" }, reasonText);
  } else {
    const ci = card.difference_ci95_pp;
    const includesZero = Array.isArray(ci) && ci.length === 2 && ci[0] <= 0 && ci[1] >= 0;
    const totalN = typeof card.games_total === "number"
      ? card.games_total
      : (card.games_in_first_hand || 0) + (card.games_not_in_first_hand || 0);
    diffCell = h("div", {},
      h("div", {}, outcomesPp(card.difference_pp)),
      h("div", { class: "muted" }, `95 %-Intervall: ${outcomesPpInterval(ci)}`),
      pooledRow ? h("div", { class: "muted" }, `geschichtet über ${StudioUI.num(card.strata, 0)} Deck-Stände`) : null,
      includesZero ? h("div", { class: "muted" }, `kein Unterschied nachweisbar bei n=${StudioUI.num(totalN, 0)}`) : null);
  }

  const rateNote = (rate, ci) => {
    if (!isMeasured) return "zu wenig Daten";
    if (pooledRow) return "Anteil nur je Deck-Stand";
    return outcomesPctInterval(rate, ci);
  };
  const inCell = h("div", {},
    h("div", {}, outcomesRatio(card.wins_in_first_hand, card.games_in_first_hand)),
    h("div", { class: "muted" }, rateNote(card.rate_in, card.rate_in_ci95)));
  const notCell = h("div", {},
    h("div", {}, outcomesRatio(card.wins_not_in_first_hand, card.games_not_in_first_hand)),
    h("div", { class: "muted" }, rateNote(card.rate_not, card.rate_not_ci95)));

  const nameNode = deps.openCard
    ? h("button", { type: "button", class: "ghost", onclick: () => deps.openCard(card.card) }, card.card)
    : card.card;

  return h("tr", {}, h("td", {}, nameNode), h("td", {}, inCell), h("td", {}, notCell), h("td", {}, diffCell));
}

function outcomesCardTable(h, cards, deps, caption) {
  const sorted = cards.slice().sort((a, b) => {
    const oa = OUTCOMES_CARD_ORDER[a.status] ?? 9;
    const ob = OUTCOMES_CARD_ORDER[b.status] ?? 9;
    return oa !== ob ? oa - ob : String(a.card).localeCompare(String(b.card));
  });
  return h("div", { class: "table-wrap deck-series-scroll" }, h("table", {},
    h("caption", { class: "visually-hidden" }, caption),
    h("thead", {}, h("tr", {},
      h("th", { scope: "col" }, "Karte"),
      h("th", { scope: "col" }, "In Starthand (Siege inkl. Remis / n)"),
      h("th", { scope: "col" }, "Nicht in Starthand (Siege inkl. Remis / n)"),
      h("th", { scope: "col" }, "Differenz & 95 %-Intervall"))),
    h("tbody", {}, sorted.map((card) => outcomesCardRow(h, card, deps)))));
}

// One deck state as its own section: its hash (or "Stand unbekannt"), its own n/N and table.
function outcomesStandSection(h, stand, deps) {
  const known = typeof stand.deck_hash === "string" && stand.deck_hash;
  const revisions = Array.isArray(stand.revision_ids) && stand.revision_ids.length ? stand.revision_ids.join(", ") : "unbekannt";
  const head = known
    ? `Deck-Stand ${outcomesShortHash(stand.deck_hash)} · ${outcomesInt(stand.games_total)} Partien · Stände im Deckbauer: ${revisions}`
    : `Stand unbekannt (Partien ohne Deck-Hash im Protokoll) · ${outcomesInt(stand.games_total)} Partien · nie zu einem bekannten Stand addiert`;
  const cards = Array.isArray(stand.cards) ? stand.cards : [];
  return h("details", {},
    h("summary", {}, head),
    h("p", { class: "muted" },
      `Partien: ${outcomesInt(stand.games_total)} ausgewertet, ohne Starthand: ${outcomesInt(stand.seats_without_opening_hand)} · Seeds: ${outcomesInt(stand.seeds)}`),
    cards.length
      ? outcomesCardTable(h, cards, deps, `Karten-Auswertung eines Deck-Stands (${known ? outcomesShortHash(stand.deck_hash) : "Stand unbekannt"})`)
      : h("p", { class: "muted" }, "Keine Partien mit Starthand-Daten (zu wenig Daten, nicht 0)."));
}

function outcomesMetadataNodes(h, data, queryLabel) {
  const pilots = Array.isArray(data.pilots) && data.pilots.length ? data.pilots.join(", ") : "unbekannt";
  const policies = Array.isArray(data.decision_policies) && data.decision_policies.length ? data.decision_policies.join(", ") : "unbekannt";
  const engines = Array.isArray(data.engine_commits) && data.engine_commits.length ? data.engine_commits.join(", ") : "unbekannt";
  const jars = Array.isArray(data.bridge_jar_sha256s) && data.bridge_jar_sha256s.length
    ? data.bridge_jar_sha256s.map((s) => String(s).slice(0, 12)).join(", ")
    : "unbekannt";
  const pods = Array.isArray(data.pods) && data.pods.length
    ? data.pods.map((p) => `${(p.opponents || []).join(" / ") || "unbekannt"} (${outcomesInt(p.games)})`).join("; ")
    : "unbekannt";
  const qual = Array.isArray(data.bridge_qualification_states) && data.bridge_qualification_states.length
    ? data.bridge_qualification_states.map((q) => OUTCOMES_QUAL_LABELS[q] || q).join(", ")
    : "unbekannt";
  const sealed = data.covered_by_sealed_epoch === true ? "ja" : data.covered_by_sealed_epoch === false ? "nein" : "unbekannt";
  const chanceNote = typeof data.comparisons === "number" && data.comparisons > 0
    ? ` · Vergleiche: ${StudioUI.num(data.comparisons, 0)} (erwartete Zufallsfunde bei 5 %: ${typeof data.expected_chance_findings === "number" ? StudioUI.num(data.expected_chance_findings, 1) : "unbekannt"})`
    : "";

  const nodes = [
    h("p", { class: "muted" },
      `Kohorte: ${data.data_class || "unbekannt"} · ${queryLabel} · Deck-ID im Log: ${data.deck_id || "unbekannt"} · `,
      `Partien: ${outcomesInt(data.games_total)} ausgewertet, ${outcomesInt(data.games_skipped)} übersprungen, ohne Starthand: ${outcomesInt(data.seats_without_opening_hand)} · `,
      `Seeds: ${outcomesInt(data.seeds)} · Mindestzahl je Seite: ${outcomesInt(data.min_exposed)}${chanceNote}`),
    h("p", { class: "muted" },
      `Piloten: ${pilots} · Policies: ${policies} · Pods: ${pods} · Engine: ${engines} · Bridge-JAR: ${jars} · Qualifizierung: ${qual} · Siegel-Epoche: ${sealed}`),
    h("p", { class: "muted" }, `Schätzgröße (Estimand): ${data.estimand || "unbekannt"}`),
  ];

  if (Array.isArray(data.warnings) && data.warnings.length) {
    nodes.push(h("ul", { class: "note note-compact" }, data.warnings.map((w) => h("li", {}, w))));
  }
  return nodes;
}

async function renderCardOutcomes(slot, deps) {
  const { h } = deps;
  const title = "Karten-Auswertung aus Partien (SIMULATED_RESULT)";
  const fixedNote = h("p", { class: "note note-compact" },
    "SIMULATED_RESULT · Herkunftsklasse: in der Engine gemessen · Exposition zufällig (Mischung), Ergebnis pilotabhängig (Sieganteil mit der Karte in der zuerst ausgeteilten Hand gegen ohne). ",
    "Gilt für diese Piloten, diese Pods, diese Engine-Version. Kein Rang, keine Kartennote und kein Teil der Tierliste (Gewicht 0).");
  const revHash = outcomesDeckHash(deps.baseRevision);
  slot.replaceChildren(h("h3", {}, title), fixedNote, h("p", { class: "muted" }, "lädt …"));

  if (!deps.deckId) {
    slot.replaceChildren(h("h3", {}, title), fixedNote, h("p", { class: "muted" }, "Kein Deck gewählt (unbekannt)."));
    return;
  }

  let queryId = deps.deckId;
  try {
    const decksPayload = await deps.api("/api/outcomes/decks");
    const available = new Set((decksPayload && Array.isArray(decksPayload.decks) ? decksPayload.decks : []).map((d) => d.deck_id));
    if (deps.baseRevision && available.has(deps.baseRevision)) {
      queryId = deps.baseRevision;
    }
  } catch (_err) {
    // Fall back to deps.deckId if /api/outcomes/decks is unavailable.
  }

  const queryLabel = outcomesQueryLabel(queryId, deps.baseRevision, revHash);

  let data = null;
  try {
    data = await deps.api(`/api/outcomes?deck_id=${encodeURIComponent(queryId)}`);
  } catch (error) {
    const detailText = error && error.detail
      ? String(error.detail)
      : (typeof StudioUI.germanError === "function" ? StudioUI.germanError(error) : "");
    const detail = detailText ? `: ${detailText}` : "";
    slot.replaceChildren(h("h3", {}, title), fixedNote,
      h("p", { class: "muted" }, `${queryLabel} · Auswertung konnte nicht geladen werden (unbekannt, nicht 0)${detail}.`));
    return;
  }

  const dirtyNote = deps.dirty
    ? h("p", { class: "note note-compact" }, "Hinweis: Der aktuelle Entwurf hat ungespeicherte Änderungen; die Auswertung bezieht sich nur auf den gespeicherten Stand.")
    : null;
  // Schema 2 (#1657) names its deck states; an answer without them keeps the old label.
  const perStand = Array.isArray(data.stands);
  const label = perStand ? `über Deck-ID ${queryId || "unbekannt"} · ${outcomesStandLabel(data, deps.baseRevision)}` : queryLabel;
  const meta = outcomesMetadataNodes(h, data, label);
  const standNote = perStand ? outcomesStandNote(h, data) : null;
  const sections = [];
  if (perStand) {
    if (data.stands.length > 1) data.stands.forEach((stand) => sections.push(outcomesStandSection(h, stand, deps)));
    if (data.unknown_stand) sections.push(outcomesStandSection(h, data.unknown_stand, deps));
  }

  if (data.status === "NOT_POOLED") {
    slot.replaceChildren(...StudioUI.kids(
      h("h3", {}, title), fixedNote, dirtyNote, ...meta, standNote,
      h("p", { class: "muted" }, "Die Deck-Stände werden nicht zusammengeführt (siehe Grund); jeder Stand steht unten mit eigener Zahl."),
      ...sections));
    return;
  }

  if (data.status === "NO_GAMES" || !Array.isArray(data.cards) || !data.cards.length) {
    slot.replaceChildren(...StudioUI.kids(
      h("h3", {}, title), fixedNote, dirtyNote, ...meta, standNote,
      h("p", { class: "muted" }, `Für ${label} liegen noch keine abgeschlossenen Partien mit Starthand-Daten vor (zu wenig Daten, nicht 0).`),
      ...sections));
    return;
  }

  const table = outcomesCardTable(h, data.cards, deps, "Karten-Auswertung aus simulierten Partien (Starthand gegen nicht in Starthand)");
  slot.replaceChildren(...StudioUI.kids(h("h3", {}, title), fixedNote, dirtyNote, ...meta, standNote, table, ...sections));
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    outcomesDeckHash,
    outcomesPp,
    outcomesPpInterval,
    outcomesPctInterval,
    outcomesRatio,
    outcomesShortHash,
    outcomesStandLabel,
    renderCardOutcomes,
  };
}
