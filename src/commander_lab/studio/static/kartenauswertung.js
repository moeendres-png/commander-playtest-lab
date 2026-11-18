"use strict";
// "Karten-Auswertung aus Partien" (#1526): per-card win share with the card in the first dealt
// hand versus without, read-only from GET /api/outcomes. Cohort SIMULATED_RESULT only; never
// mixed with usage/tournament figures and never part of the tier list (weight 0).
// DOM only through h() and text nodes; numbers only through StudioUI.num / StudioUI.pct.
// Rendered by app.js (Simulation tab) through renderCardOutcomes(slot, deps).

const OUTCOMES_CARD_ORDER = { OK: 0, TOO_FEW: 1, NO_VARIATION: 2, ALL_GAMES: 3, COMMANDER_EXCLUDED: 4 };

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
  if (games === null || games === undefined || games <= 0) return "0 / 0";
  const w = Number.isInteger(wins) ? StudioUI.num(wins, 0) : StudioUI.num(wins, 1);
  return `${w} / ${StudioUI.num(games, 0)}`;
};

function outcomesCardRow(h, card, deps) {
  const few = card.status === "TOO_FEW" || card.status === "NO_VARIATION" || card.status === "ALL_GAMES";
  const label = card.status === "COMMANDER_EXCLUDED"
    ? "Commander (immer verfügbar)"
    : few
      ? "zu wenig Daten"
      : null;

  const diffCell = label !== null
    ? h("span", { class: "muted" }, label)
    : h("div", {}, h("div", {}, outcomesPp(card.difference_pp)), h("div", { class: "muted" }, `95 %-Intervall: ${outcomesPpInterval(card.difference_ci95_pp)}`));

  const inCell = label !== null
    ? h("div", {}, h("div", {}, outcomesRatio(card.wins_in_first_hand, card.games_in_first_hand)), h("div", { class: "muted" }, "zu wenig Daten"))
    : h("div", {}, h("div", {}, outcomesRatio(card.wins_in_first_hand, card.games_in_first_hand)), h("div", { class: "muted" }, outcomesPctInterval(card.rate_in, card.rate_in_ci95)));

  const notCell = label !== null
    ? h("div", {}, h("div", {}, outcomesRatio(card.wins_not_in_first_hand, card.games_not_in_first_hand)), h("div", { class: "muted" }, "zu wenig Daten"))
    : h("div", {}, h("div", {}, outcomesRatio(card.wins_not_in_first_hand, card.games_not_in_first_hand)), h("div", { class: "muted" }, outcomesPctInterval(card.rate_not, card.rate_not_ci95)));

  const nameNode = deps.openCard
    ? h("button", { type: "button", class: "linkish", onclick: () => deps.openCard(card.card) }, card.card)
    : card.card;

  return h("tr", {}, h("td", {}, nameNode), h("td", {}, inCell), h("td", {}, notCell), h("td", {}, diffCell));
}

function outcomesMetadataNodes(h, data, revHash) {
  const pilots = Array.isArray(data.pilots) && data.pilots.length ? data.pilots.join(", ") : "unbekannt";
  const engines = Array.isArray(data.engine_commits) && data.engine_commits.length ? data.engine_commits.join(", ") : "unbekannt";
  const pods = Array.isArray(data.pods) && data.pods.length
    ? data.pods.map((p) => `${(p.opponents || []).join(" / ") || "unbekannt"} (${StudioUI.num(p.games, 0)})`).join("; ")
    : "unbekannt";
  const qual = Array.isArray(data.bridge_qualification_states) && data.bridge_qualification_states.length
    ? data.bridge_qualification_states.join(", ")
    : "unbekannt";
  return [
    h("p", { class: "muted" },
      `Kohorte: ${data.data_class || "SIMULATED_RESULT"} · Deck-Stand (Hash): ${revHash} · Deck-ID im Log: ${data.deck_id || "unbekannt"} · `,
      `Partien: ${StudioUI.num(data.games_total || 0, 0)} ausgewertet, ${StudioUI.num(data.games_skipped || 0, 0)} übersprungen · `,
      `Mindestzahl je Seite: ${StudioUI.num(data.min_exposed || 0, 0)}`),
    h("p", { class: "muted" },
      `Piloten: ${pilots} · Pods: ${pods} · Engine: ${engines} · Qualifizierung: ${qual}`),
  ];
}

async function renderCardOutcomes(slot, deps) {
  const { h } = deps;
  const title = "Karten-Auswertung aus Partien (SIMULATED_RESULT)";
  const fixedNote = h("p", { class: "note note-compact" },
    "SIMULATED_RESULT · Herkunftsklasse: in der Engine gemessen, vom Piloten wenig abhängig (Sieganteil mit der Karte in der zuerst ausgeteilten Hand gegen ohne). ",
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

  let data = null;
  try {
    data = await deps.api(`/api/outcomes?deck_id=${encodeURIComponent(queryId)}`);
  } catch (_error) {
    slot.replaceChildren(h("h3", {}, title), fixedNote,
      h("p", { class: "muted" }, `Deck-Stand (Hash): ${revHash} · Auswertung konnte nicht geladen werden (unbekannt, nicht 0).`));
    return;
  }

  const dirtyNote = deps.dirty
    ? h("p", { class: "note note-compact" }, "Hinweis: Der aktuelle Entwurf hat ungespeicherte Änderungen; die Auswertung bezieht sich nur auf den gespeicherten Stand.")
    : null;
  const meta = outcomesMetadataNodes(h, data, revHash);

  if (data.status === "NO_GAMES" || !Array.isArray(data.cards) || !data.cards.length) {
    slot.replaceChildren(...StudioUI.kids(
      h("h3", {}, title), fixedNote, dirtyNote, ...meta,
      h("p", { class: "muted" }, `Für Deck-Stand ${revHash} liegen noch keine abgeschlossenen Partien mit Starthand-Daten vor (zu wenig Daten, nicht 0).`)));
    return;
  }

  const cards = data.cards.slice().sort((a, b) => {
    const oa = OUTCOMES_CARD_ORDER[a.status] ?? 9;
    const ob = OUTCOMES_CARD_ORDER[b.status] ?? 9;
    return oa !== ob ? oa - ob : String(a.card).localeCompare(String(b.card));
  });

  const table = h("div", { class: "table-wrap deck-series-scroll" }, h("table", {},
    h("thead", {}, h("tr", {},
      h("th", {}, "Karte"),
      h("th", {}, "In Starthand (Siege / n)"),
      h("th", {}, "Nicht in Starthand (Siege / n)"),
      h("th", {}, "Differenz & 95 %-Intervall"))),
    h("tbody", {}, cards.map((card) => outcomesCardRow(h, card, deps)))));

  slot.replaceChildren(...StudioUI.kids(h("h3", {}, title), fixedNote, dirtyNote, ...meta, table));
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    outcomesDeckHash,
    outcomesPp,
    outcomesPpInterval,
    outcomesPctInterval,
    outcomesRatio,
    renderCardOutcomes,
  };
}
