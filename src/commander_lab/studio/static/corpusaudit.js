"use strict";
// "Formale Prüfung der Quelldecks" (#1549): a hint under the cohort comparison of the deck
// builder. Per cohort (source, bracket, variant, each listed on its own, never crossed or added
// up) how many of the counted Chulane source decks have a formal finding: card count not 100,
// Chulane missing in the commander section, a card that is not legal, a card outside the colour
// identity. Decks with a finding stay in every denominator; nothing is removed from the figures
// above. Counts come from GET /api/corpus-audit (the section of the data report), with n of N
// and the date of the card facts; a missing value is "unbekannt", never 0.
// DOM only through h() and text nodes; numbers only through StudioUI.num.
// Rendered by app.js (renderCompare) through mountCorpusAudit(slot, deps).

const CORPUS_AUDIT_COMMANDER = "Chulane, Teller of Tales";
const CORPUS_AUDIT_SCHEMA = "studio-corpus-audit-1";
const CORPUS_AUDIT_REASONS = [
  ["card_count_not_100", "nicht 100 Karten"],
  ["commander_not_chulane", "Chulane nicht in der Commander-Sektion"],
  ["card_not_legal", "Karte nicht legal (auch Spielstein-Zeilen)"],
  ["outside_identity", "Karte außerhalb der Farbidentität"],
];
const CORPUS_AUDIT_DIMENSIONS = [
  ["source", "Nach Quelle"],
  ["bracket", "Nach Bracket"],
  ["variant", "Nach Variante"],
];

// The audit answer of this page load (and the load in flight, so two renders ask once); a failed
// load is not kept, so the next render retries.
let corpusAuditAnswer = null;
let corpusAuditLoading = null;

const corpusAuditCount = (value) => (typeof value === "number" ? StudioUI.num(value, 0) : "unbekannt");
const corpusAuditShare = (count, of) => `${corpusAuditCount(count)} von ${corpusAuditCount(of)}`;

function corpusAuditFacts(data) {
  const date = typeof data.card_facts_snapshot_date === "string" ? data.card_facts_snapshot_date : "unbekannt";
  if (date === "unbekannt") return "Stand der Kartenfakten: unbekannt (die Kartendatei trägt kein belegtes Abrufdatum).";
  const age = typeof data.card_facts_age_days === "number" ? ` (${StudioUI.num(data.card_facts_age_days, 0)} Tage alt)` : "";
  return `Stand der Kartenfakten: ${date}${age}.`;
}

function corpusAuditSummary(h, data) {
  const status = data.status || {};
  const reasons = CORPUS_AUDIT_REASONS.map(([key, label]) => {
    const row = (data.by_reason || {})[key] || {};
    const open = typeof row.not_measurable === "number" && row.not_measurable > 0 ? `, ${StudioUI.num(row.not_measurable, 0)} nicht messbar` : "";
    return h("li", {}, `${label}: ${corpusAuditShare(row.count, row.of)}${open}`);
  });
  return [
    h("p", { id: "corpus-audit-total" },
      `Von ${corpusAuditCount(status.of)} gezählten Quelldecks haben ${corpusAuditCount(status.befund)} einen Befund, ${corpusAuditCount(status.unbekannt)} sind nicht vollständig messbar (unbekannt), ${corpusAuditCount(status.ohne_befund)} ohne Befund.`),
    h("ul", { class: "muted" }, reasons),
    h("p", { class: "note", id: "corpus-audit-facts" }, corpusAuditFacts(data)),
  ];
}

function corpusAuditTable(h, data, cohortName) {
  const rows = [];
  for (const [dimension, title] of CORPUS_AUDIT_DIMENSIONS) {
    const values = (data.by_cohort_dimension || {})[dimension] || {};
    const names = Object.keys(values).sort((a, b) => a.localeCompare(b));
    if (!names.length) continue;
    rows.push(h("tr", { class: "subhead" }, h("th", { colspan: "4" }, title)));
    for (const value of names) {
      const row = values[value];
      rows.push(h("tr", { class: row.befund > 0 ? "low" : "" },
        h("td", {}, value === "unbekannt" ? "ohne Angabe (unbekannt)" : cohortName(`${dimension}:${value}`)),
        h("td", { class: "num" }, corpusAuditCount(row.decks)),
        h("td", { class: "num" }, `davon ${corpusAuditShare(row.befund, row.decks)} mit Befund`),
        h("td", { class: "num" }, corpusAuditCount(row.unbekannt))));
    }
  }
  if (!rows.length) return h("p", { class: "muted" }, "Keine Gruppen: unbekannt.");
  return h("div", { class: "table-wrap" }, h("table", { id: "corpus-audit-table" },
    h("thead", {}, h("tr", {}, h("th", {}, "Gruppe"), h("th", { class: "num" }, "Quelldecks"), h("th", { class: "num" }, "Befund"), h("th", { class: "num" }, "unbekannt"))),
    h("tbody", {}, rows)));
}

function renderCorpusAudit(slot, data, deps) {
  const { h, cohortName } = deps;
  if (!data || data.schema !== CORPUS_AUDIT_SCHEMA || !data.status) {
    slot.replaceChildren(h("p", { class: "muted" }, "Formale Prüfung der Quelldecks: unbekannt (Antwort nicht lesbar)."));
    return;
  }
  slot.replaceChildren(
    h("h3", {}, "Formale Prüfung der Quelldecks (Hinweis)"),
    ...corpusAuditSummary(h, data),
    corpusAuditTable(h, data, cohortName),
    h("p", { class: "note" }, "Nur ein Hinweis: Decks mit Befund bleiben in jeder Zahl oben mitgezählt. Ein Deck kann in mehreren Gruppen derselben Reihe stehen; die Zeilen werden nicht addiert. Gruppen verschiedener Reihen (Quelle, Bracket, Variante) werden nie gemischt."));
}

// Loads the answer once and fills the slot. Only for Chulane: the audit counts the Chulane
// corpus, so for another commander the slot stays empty (no number is shown against it).
async function mountCorpusAudit(slot, deps) {
  if (deps.commander !== CORPUS_AUDIT_COMMANDER) return;
  if (corpusAuditAnswer) {
    renderCorpusAudit(slot, corpusAuditAnswer, deps);
    return;
  }
  slot.replaceChildren(deps.h("p", { class: "muted" }, "Formale Prüfung der Quelldecks wird geladen …"));
  try {
    corpusAuditLoading = corpusAuditLoading || deps.api("/api/corpus-audit");
    corpusAuditAnswer = await corpusAuditLoading;
  } catch (error) {
    corpusAuditLoading = null;
    slot.replaceChildren(deps.h("p", { class: "muted" }, "Formale Prüfung der Quelldecks: unbekannt (nicht geladen)."));
    return;
  }
  renderCorpusAudit(slot, corpusAuditAnswer, deps);
}
