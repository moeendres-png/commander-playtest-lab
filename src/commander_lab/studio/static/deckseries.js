"use strict";
// "Serien im Verlauf" (#1404): per saved revision of the open deck, the stored paired series in
// which it was base (A) or variant (B). Only the stored fields are shown: counts with n/N, the
// stored difference and intervals, status, seeds, seats and the engine/pilot state. No verdict,
// no ranking; a series that is not completed is named as such and never shown as a result,
// unknown stays text, never 0. Simulation results are never part of the tier list.
// DOM only through h() / StudioUI.h and text nodes; numbers only through StudioUI.num.
// Rendered by app.js (history dialog) through renderDeckSeries(slot, rows, deps).

const DECK_SERIES_STATUS_CLASS = {
  completed: "good", stopped_early: "good", cancelled: "warn", failed: "bad", incomplete: "warn",
};

const deckSeriesPp = (value) =>
  value === null || value === undefined ? "unbekannt" : `${value >= 0 ? "+" : ""}${StudioUI.num(value, 1)} pp`;
const deckSeriesInterval = (ci) =>
  Array.isArray(ci) && ci.length === 2 ? `[${deckSeriesPp(ci[0])}; ${deckSeriesPp(ci[1])}]` : "unbekannt";
const deckSeriesDate = (iso) => (iso ? iso.slice(0, 16).replace("T", " ") : "unbekannt");

function deckSeriesRefLabel(ref, labels) {
  if (labels.has(ref)) return labels.get(ref);
  if (ref.startsWith("repo:")) return `Referenz ${ref.slice(5)}`;
  return "andere Revision";
}

function deckSeriesCells(h, item, role, deps, labels) {
  const other = role === "base" ? item.variant_ref : item.base_ref;
  const planned = item.pairs_planned === null ? "unbekannt" : StudioUI.num(item.pairs_planned);
  const counted = item.counts_as_result;
  const pairs = counted
    ? `${StudioUI.num(item.pairs_completed)} von ${planned} Paaren abgeschlossen`
    : `kein Ergebnis (${StudioUI.num(item.pairs_attempted)} von ${planned} Paaren begonnen)`;
  const figures = counted
    ? [
      h("div", {}, `Differenz (B − A): ${deckSeriesPp(item.difference_pp)}`),
      h("div", {}, `95 %-Intervall: ${deckSeriesInterval(item.difference_ci95_pp)}`),
      h("div", {}, `Look-Intervall${item.decision_level_pct === null ? "" : ` (${StudioUI.num(item.decision_level_pct, 1)} %)`}: ${deckSeriesInterval(item.decision_ci_pp)}`),
      ...(item.pairs_censored ? [h("div", { class: "muted" }, `${StudioUI.num(item.pairs_censored)} Paare zensiert`)] : []),
    ]
    : [h("div", { class: "muted" }, "nicht als Ergebnis gezählt")];
  const seeds = item.seeds.length ? item.seeds.map((s) => StudioUI.num(s)).join(", ") : "unbekannt";
  const seats = item.tested_seats.length ? item.tested_seats.map((s) => StudioUI.num(s + 1)).join(", ") : "unbekannt";
  const sha = item.bridge_jar_sha256s.length ? item.bridge_jar_sha256s.map((s) => s.slice(0, 12)).join(", ") : "unbekannt";
  const qual = item.bridge_qualification_states.length ? item.bridge_qualification_states.join(", ") : "unbekannt";
  return [
    h("td", {}, `${deckSeriesDate(item.created_at)} · als ${role === "base" ? "Basis (A)" : "Variante (B)"} gegen `, h("b", {}, deckSeriesRefLabel(other, labels)), item.pod ? ` · Tisch ${item.pod}` : ""),
    h("td", { class: "num" }, pairs),
    h("td", {}, figures),
    h("td", {}, h("span", { class: `pill ${DECK_SERIES_STATUS_CLASS[item.status] || "warn"}` }, item.status_text),
      item.stop_reason && !/^(DECIDED_|BUDGET_EXHAUSTED)/.test(item.stop_reason) ? h("div", { class: "muted" }, item.stop_reason) : null),
    h("td", {}, h("div", {}, `Seeds: ${seeds}`), h("div", {}, `Sitze${item.seats_planned ? " (geplant)" : ""}: ${seats}`),
      h("div", { class: "muted" }, `Bridge-JAR: ${sha} · Qualifizierung: ${qual}${item.covered_by_sealed_epoch === null ? "" : item.covered_by_sealed_epoch ? " · versiegelt" : " · nicht versiegelt"}`),
      h("div", { class: "muted" }, `Piloten: ${item.pilots.length ? item.pilots.join(", ") : "unbekannt"}`)),
    h("td", {}, h("button", { type: "button", class: "small", onclick: () => deps.open(item.series_id) }, "Serie öffnen")),
  ];
}

function deckSeriesTable(h, data, historyRows, deps) {
  const byId = new Map(data.series.map((item) => [item.series_id, item]));
  const labels = new Map(historyRows.map((row) => [row.revision_id, `Stand ${deckSeriesDate(row.created_at)}${row.branch ? ` (${row.branch})` : ""}`]));
  const rows = [];
  for (const rev of historyRows) {
    const refs = data.by_revision[rev.revision_id] || [];
    const stand = h("td", { rowspan: Math.max(1, refs.length) }, labels.get(rev.revision_id));
    if (!refs.length) {
      rows.push(h("tr", {}, stand, h("td", { colspan: 6, class: "muted" }, "keine gespeicherte Serie")));
      continue;
    }
    refs.forEach((ref, index) => {
      const cells = deckSeriesCells(h, byId.get(ref.series_id), ref.role, deps, labels);
      rows.push(h("tr", {}, ...(index === 0 ? [stand] : []), ...cells));
    });
  }
  return h("div", { class: "deck-series-scroll" }, h("table", {},
    h("thead", {}, h("tr", {}, ["Stand", "Serie", "Paare (n/N)", "Zählwerte der Serie", "Status", "Seeds · Sitze · Stand", ""].map((label) => h("th", {}, label)))),
    h("tbody", {}, rows)));
}

async function renderDeckSeries(slot, historyRows, deps) {
  const { h } = deps;
  slot.replaceChildren(h("h3", {}, "Gespeicherte Paar-Serien je Stand"), h("p", { class: "muted" }, "lädt …"));
  let data = null;
  try {
    data = await deps.api(`/api/decks/${encodeURIComponent(deps.deckId)}/series`);
  } catch (error) {
    slot.replaceChildren(h("h3", {}, "Gespeicherte Paar-Serien je Stand"), h("p", { class: "muted" }, "Serien konnten nicht gelesen werden (unbekannt, nicht 0)."));
    return;
  }
  const note = h("p", { class: "note note-compact" },
    "SIMULATED_RESULT: Zählwerte gespeicherter Serien (gleiche Seeds, Sitze und Gegner-Tisch), kein Urteil und kein Teil der Tierliste (Gewicht 0). Nicht abgeschlossene oder abgebrochene Serien zählen nicht als Ergebnis.",
    data.skipped ? ` ${StudioUI.num(data.skipped)} nicht lesbare oder fremde Ergebnisdateien übersprungen.` : "",
    data.truncated ? " Nur die neuesten 200 Serien." : "",
    data.scan_truncated ? ` Nur die neuesten ${StudioUI.num(data.scan_limit)} Dateien geprüft, ${StudioUI.num(data.scan_truncated)} ältere nicht: eine fehlende Serie ist dann unbekannt.` : "");
  const body = data.series.length
    ? deckSeriesTable(h, data, historyRows, deps)
    : h("p", { class: "muted" }, data.scan_truncated ? "keine Serie in den geprüften Dateien (ältere nicht geprüft)" : "keine gespeicherte Serie");
  slot.replaceChildren(h("h3", {}, "Gespeicherte Paar-Serien je Stand"), note, body);
}
