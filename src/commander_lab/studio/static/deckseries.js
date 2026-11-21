"use strict";
// "Serien im Verlauf" (#1404): per saved revision of the open deck, the stored paired series in
// which it was base (A) or variant (B). Only the stored fields are shown: counts with n/N, the
// stored difference and intervals, status, seeds, seats and the engine/pilot state. No verdict,
// no ranking; a series that is not completed is named as such and never shown as a result,
// unknown stays text, never 0. Simulation results are never part of the tier list.
// DOM only through h() / StudioUI.h and text nodes; numbers only through StudioUI.num.
// Rendered by app.js (history dialog) through renderDeckSeries(slot, rows, deps).
// The difference B − A is shown through the number contract (zahl.js, #1659) as SIMULIERT, with
// n/N pairs, the deck hashes of both states and the pilot origin; without a contract the old text.
// Q1-c (#1666): under the figures one evidence row per series from data.reifegrad (maturity.py):
// the maturity R0-R3 only when the answer names one (no badge without proof; R0 exploration is a
// neutral pill, only a confirmed level R1-R3 is green), the four-step
// verdict with n/N pairs, the state the finding is about (a finding of another state is named as
// such, never as current) and "empfehlungsfähig" only when the answer says so. Nothing is added
// to another figure; no EDHREC, Playgroup or tournament figure shares this row.

// The verdict text follows the field belegt, never urteil alone: a decided step below R1 is only
// a hint (urteil stays belegt_besser/belegt_schlechter there, belegt is false).
function deckSeriesVerdictText(befund) {
  if (befund.belegt === true) return befund.urteil_text;
  if (befund.urteil === "belegt_besser" || befund.urteil === "belegt_schlechter") {
    return `Hinweis ${befund.urteil === "belegt_besser" ? "besser" : "schlechter"} (nicht belegt, unbestätigt; B gegenüber A)`;
  }
  return befund.urteil_text;
}

function deckSeriesEvidence(h, befund) {
  if (!befund) return h("div", { class: "muted evidence-row" }, "Reifegrad: kein Reifegrad (kein Befund)");
  const pairs = befund.n === null || befund.N === null ? "Paare unbekannt" : `n/N ${StudioUI.num(befund.n)} / ${StudioUI.num(befund.N)} ${befund.bezug}`;
  return h("div", { class: "evidence-row" },
    befund.stufe ? h("span", { class: befund.stufe === "R0" ? "pill" : "pill good" }, befund.stufe_text) : h("span", { class: "muted" }, befund.stufe_text),
    h("div", {}, `Ergebnis (simuliert): ${deckSeriesVerdictText(befund)} · ${pairs}`),
    h("div", { class: befund.stand.bezug === "aktuell" ? "" : "muted" }, befund.stand.text),
    befund.empfehlungsfaehig
      ? h("div", {}, h("span", { class: "pill good" }, "empfehlungsfähig"))
      : h("div", { class: "muted" }, `nicht empfehlungsfähig: ${befund.empfehlungsfaehig_gruende.join("; ")}`),
    ...befund.hinweise.map((note) => h("div", { class: "muted" }, note)));
}

const DECK_SERIES_STATUS_CLASS = {
  completed: "good", stopped_early: "good", cancelled: "warn", failed: "bad", incomplete: "warn",
};

const deckSeriesPp = (value) =>
  value === null || value === undefined ? "unbekannt" : `${value >= 0 ? "+" : ""}${StudioUI.num(value, 1)} pp`;
const deckSeriesInterval = (ci) =>
  Array.isArray(ci) && ci.length === 2 ? `[${deckSeriesPp(ci[0])}; ${deckSeriesPp(ci[1])}]` : "unbekannt";
const deckSeriesDate = (iso) => (iso ? iso.slice(0, 16).replace("T", " ") : "unbekannt");
// slot_alignment_state of deck_series.py: unaligned (older) series are marked, never pooled.
const DECK_SERIES_ALIGNMENT_TEXT = {
  aligned: "Bibliotheksplätze an Basis ausgerichtet",
  not_congruent: "Bibliotheksplätze nicht deckungsgleich (Kartenzahl verschieden)",
  not_aligned_legacy: "nicht ausgerichtet (ältere Serie, nicht mit ausgerichteten zusammenzählen)",
};

function deckSeriesRefLabel(ref, labels) {
  if (labels.has(ref)) return labels.get(ref);
  if (ref.startsWith("repo:")) return `Referenz ${ref.slice(5)}`;
  return "andere Revision";
}

function deckSeriesCells(h, item, role, deps, labels, zahlen, befund) {
  const zahl = zahlen ? zahlen.get(`series.${item.series_id}.difference_pp`) : undefined;
  const other = role === "base" ? item.variant_ref : item.base_ref;
  const planned = item.pairs_planned === null ? "unbekannt" : StudioUI.num(item.pairs_planned);
  const counted = item.counts_as_result;
  const pairs = counted
    ? `${StudioUI.num(item.pairs_completed)} von ${planned} Paaren abgeschlossen`
    : `kein Ergebnis (${StudioUI.num(item.pairs_attempted)} von ${planned} Paaren begonnen)`;
  const figures = counted
    ? [
      zahl ? h("div", {}, "Differenz (B − A): ", StudioZahl.knoten(h, zahl)) : h("div", {}, `Differenz (B − A): ${deckSeriesPp(item.difference_pp)}`),
      h("div", {}, `95 %-Intervall: ${deckSeriesInterval(item.difference_ci95_pp)}`),
      h("div", {}, `Look-Intervall${item.decision_level_pct === null ? "" : ` (${StudioUI.num(item.decision_level_pct, 1)} %)`}: ${deckSeriesInterval(item.decision_ci_pp)}`),
      ...(item.pairs_censored ? [h("div", { class: "muted" }, `${StudioUI.num(item.pairs_censored)} Paare zensiert`)] : []),
    ]
    : [h("div", { class: "muted" }, "nicht als Ergebnis gezählt")];
  figures.push(deckSeriesEvidence(h, befund));
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
      h("div", { class: "muted" }, `Piloten: ${item.pilots.length ? item.pilots.join(", ") : "unbekannt"}`),
      h("div", { class: "muted" }, DECK_SERIES_ALIGNMENT_TEXT[item.slot_alignment_state] || "Ausrichtung unbekannt")),
    h("td", {}, h("button", { type: "button", class: "small", onclick: () => deps.open(item.series_id) }, "Serie öffnen")),
  ];
}

function deckSeriesTable(h, data, historyRows, deps) {
  const byId = new Map(data.series.map((item) => [item.series_id, item]));
  const zahlen = StudioZahl.index(data.zahlen);
  const befunde = (data.reifegrad && data.reifegrad.befunde) || {};
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
      const cells = deckSeriesCells(h, byId.get(ref.series_id), ref.role, deps, labels, zahlen, befunde[ref.series_id]);
      rows.push(h("tr", {}, ...(index === 0 ? [stand] : []), ...cells));
    });
  }
  return h("div", { class: "table-wrap deck-series-scroll" }, h("table", {},
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
    "SIMULATED_RESULT: Zählwerte gespeicherter Serien (gleiche Seeds, Sitze und Gegner-Tisch) mit Reifegrad R0–R3 und Ergebnis in vier Stufen je Serie (simuliert, nie mit EDHREC-, Playgroup- oder Turnier-Zahlen summiert), kein Teil der Tierliste. Nicht abgeschlossene oder abgebrochene Serien zählen nicht als Ergebnis und tragen keinen Reifegrad.",
    data.reifegrad && data.reifegrad.tam_sperre ? ` ${data.reifegrad.tam_sperre}.` : "",
    data.reifegrad ? ` ${data.reifegrad.luecken.join(" ")}` : "",
    data.skipped ? ` ${StudioUI.num(data.skipped)} nicht lesbare oder fremde Ergebnisdateien übersprungen.` : "",
    data.truncated ? " Nur die neuesten 200 Serien." : "",
    data.scan_truncated ? ` Nur die neuesten ${StudioUI.num(data.scan_limit)} Dateien geprüft, ${StudioUI.num(data.scan_truncated)} ältere nicht: eine fehlende Serie ist dann unbekannt.` : "");
  const body = data.series.length
    ? deckSeriesTable(h, data, historyRows, deps)
    : h("p", { class: "muted" }, data.scan_truncated ? "keine Serie in den geprüften Dateien (ältere nicht geprüft)" : "keine gespeicherte Serie");
  slot.replaceChildren(h("h3", {}, "Gespeicherte Paar-Serien je Stand"), note, body);
}

// The series answer for the diff: null when it cannot be read, never an empty list (an empty list
// would read as "keine gespeicherte Serie" instead of "nicht gelesen").
async function deckSeriesLoad(api, deckId) {
  try {
    return await api(`/api/decks/${encodeURIComponent(deckId)}/series`);
  } catch (error) {
    return null;
  }
}

// Q1-c Paket 2 (#1666): the same evidence row in the diff of two saved states. Only a stored
// series whose two states are exactly the two compared states counts (A and B in either order);
// the answer of /api/decks/{id}/series (data) supplies series and data.reifegrad. No such series,
// an unsaved opened state or an unreadable answer is "kein Befund" (unknown), never 0 and never
// a finding of another pair of states. The opened state is "geöffneter Stand": "aktueller Stand"
// in the finding's own text means main, so each series names that reference and its table.
function deckSeriesDiffEvidence(h, data, baseRev, targetRev) {
  const title = h("h3", {}, "Simulation zu diesem Vergleich (SIMULIERT)");
  const note = h("p", { class: "note note-compact" }, "SIMULATED_RESULT: gespeicherte Serie genau dieser beiden Stände, nicht Teil der Tierliste und nie mit anderen Zahlen summiert.");
  if (!data) return h("div", { id: "diff-evidence" }, title, note, h("p", { class: "muted" }, "kein Befund: Serien konnten nicht gelesen werden (unbekannt, nicht 0)."));
  if (!targetRev) return h("div", { id: "diff-evidence" }, title, note, h("p", { class: "muted" }, "kein Befund: der geöffnete Stand ist nicht gespeichert (unbekannt, nicht 0)."));
  if (!Array.isArray(data.series)) return h("div", { id: "diff-evidence" }, title, note, h("p", { class: "muted" }, "kein Befund: die Antwort enthält keine Serienliste (unbekannt, nicht 0)."));
  const side = (ref) => (ref === baseRev ? "Vergleichsbasis" : "geöffneter Stand");
  const befunde = (data.reifegrad && data.reifegrad.befunde) || {};
  const found = data.series.filter((item) => (item.base_ref === baseRev && item.variant_ref === targetRev) || (item.base_ref === targetRev && item.variant_ref === baseRev));
  const incomplete = data.truncated || data.scan_truncated ? " (ältere Serien nicht geprüft)" : "";
  if (!found.length) return h("div", { id: "diff-evidence" }, title, note, h("p", { class: "muted" }, `kein Befund: keine gespeicherte Serie für genau diese beiden Stände${incomplete} (unbekannt, nicht 0).`));
  return h("div", { id: "diff-evidence" }, title, note, ...found.map((item) => h("div", { class: "diff-evidence-series" },
    h("p", { class: "muted" }, `Serie vom ${deckSeriesDate(item.created_at)} · Tisch ${item.pod || "unbekannt"}: A = ${side(item.base_ref)}, B = ${side(item.variant_ref)}`),
    h("p", { class: "muted" }, "Stand-Bezug des Befunds darunter: gemessen an main bzw. dessen direktem Vorgänger, unabhängig davon, welcher Stand geöffnet ist."),
    deckSeriesEvidence(h, befunde[item.series_id]))));
}

// Cutting and swapping: Simulation is stored per pair of saved states, never per card or per
// swap, so a single card has no finding. The extra column says so instead of showing a figure.
function deckSeriesCardEvidence(h) {
  return h("span", { class: "muted evidence-card" }, "kein Befund (keine Serie je Karte gespeichert; unbekannt, nicht 0)");
}
