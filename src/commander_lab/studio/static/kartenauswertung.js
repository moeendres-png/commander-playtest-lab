"use strict";
// "Karten-Auswertung aus Partien" (#1526): per-card win share with the card in the first dealt
// hand versus without, read-only from GET /api/outcomes. Cohort SIMULATED_RESULT only; never
// mixed with usage/tournament figures and never part of the tier list (weight 0).
// DOM only through h() and text nodes; numbers only through StudioUI.num / StudioUI.pct.
// Rendered by app.js (Simulation tab) through renderCardOutcomes(slot, deps).
// Per deck state (#1657): the answer names its known stands (deck_hash) and "Stand unbekannt"
// apart; several stands are only shown stratified (strata = number of stands), never added.
// Per table size (#1683): a stratum is (deck state, table size); every stratum names its table
// size, strata of another table size are never combined, and logs without a table size stand
// apart as "Tischgröße unbekannt" with their own n/N (unknown_strata).
// Per table size (#1694): the answer carries one table per table size (cohorts); the deck states
// of one table size are combined stratified in their own section, two table sizes never share
// one. Every stratum is shown once, inside the section of its table size.
// Per pilot fingerprint (#1687): a stratum is (deck state, table size, pilot fingerprint); a
// change of the pilot gives separate strata (no 409), each naming its fingerprint (short hash);
// logs without one stand apart as "Pilot unbekannt". Sections are per table size and pilot
// fingerprint. The axes come from OUTCOMES_AXES, pinned to card_outcomes.STRATUM_AXES by a test.
// Games with a human seat (#1662, PLAYED_GAME) are their own cohort: counted in no figure here,
// named apart with their own n and origin (played_cohort); a missing count reads "unbekannt".

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

// The table size of a stratum (#1683): read from the log header, never guessed.
const outcomesTableSize = (value) =>
  Number.isInteger(value) && value > 0
    ? `Tischgröße: ${StudioUI.num(value, 0)} ${value === 1 ? "Sitz" : "Sitze"}`
    : "Tischgröße unbekannt";

// The strata axes of card_outcomes.STRATUM_AXES in its order (#1687; a test pins field, order,
// pooled and the unknown label to it). `text` names a known value, `detail` explains an unknown one.
const outcomesKnownText = (value) => typeof value === "string" && value !== "";
const OUTCOMES_AXES = [
  {
    field: "deck_hash", name: "Deck-Stand", unknown: "Stand unbekannt", pooled: true,
    detail: "Partien ohne Deck-Hash im Protokoll",
    known: outcomesKnownText, text: (v) => `Deck-Stand ${outcomesShortHash(v)}`,
  },
  {
    field: "table_size", name: "Tischgröße", unknown: "Tischgröße unbekannt", pooled: false,
    detail: "Protokollkopf ohne vollständige Sitzliste",
    known: (v) => Number.isInteger(v) && v > 0, text: (v) => outcomesTableSize(v),
  },
  {
    field: "pilot_fingerprint", name: "Pilot-Fingerabdruck", unknown: "Pilot unbekannt", pooled: false,
    detail: "Protokollkopf ohne Pilot-Fingerabdruck, aus der Zeit vor dem Fingerabdruck",
    known: outcomesKnownText, text: (v) => `Pilot-Fingerabdruck ${outcomesShortHash(v)}`,
  },
];
const OUTCOMES_CELL_AXES = OUTCOMES_AXES.filter((axis) => !axis.pooled);

// "a", "a und b", "a, b und c"
const outcomesAnd = (items) =>
  items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} und ${items[items.length - 1]}`;
const outcomesAxisNames = (axes = OUTCOMES_AXES) => outcomesAnd(axes.map((axis) => axis.name));
const outcomesAxisKnown = (axis, stratum) => axis.known(stratum[axis.field]);
const outcomesAxisText = (axis, stratum, detail = false) => {
  if (outcomesAxisKnown(axis, stratum)) return axis.text(stratum[axis.field]);
  return detail ? `${axis.unknown} (${axis.detail})` : axis.unknown;
};
// The cell of a table (#1687): its value of every axis that is never pooled.
const outcomesCellName = (table) => OUTCOMES_CELL_AXES.map((axis) => outcomesAxisText(axis, table)).join(" · ");

const OUTCOMES_APART_SENTENCE = "Jede Schicht steht unten einzeln mit n/N und Herkunft.";
const OUTCOMES_CELL_SENTENCE = `Deck-Stände derselben Kombination aus ${outcomesAxisNames(OUTCOMES_CELL_AXES)} werden unten in einem eigenen Abschnitt geschichtet zusammengeführt.`;

// Why strata of several table sizes stay apart (#1683), in German: the base win rate differs.
function outcomesTableSizeReason(values) {
  const sizes = Array.isArray(values) ? values.filter((v) => Number.isInteger(v) && v > 0) : [];
  const list = sizes.map((v) => StudioUI.num(v, 0)).join(", ");
  const bases = sizes.map((v) => `bei ${StudioUI.num(v, 0)} Sitzen 1/${StudioUI.num(v, 0)}`).join(", ");
  return `Nicht zusammengeführt: Die Partien stammen von verschiedenen Tischgrößen (${list || "unbekannt"} Sitze). `
    + `Jede Tischgröße hat eine andere Basis-Siegrate${bases ? ` (${bases})` : ""}, deshalb werden sie nie zusammengefasst.`;
}

// Why strata of several pilot fingerprints stay apart (#1687), in German: the pilot changed.
function outcomesPilotReason(values) {
  const prints = Array.isArray(values) ? values.filter(outcomesKnownText) : [];
  const list = prints.map((v) => outcomesShortHash(v)).join(", ");
  return `Nicht zusammengeführt: Der Pilot-Fingerabdruck wechselte (${list || "unbekannt"}). `
    + "Die Partien stammen von verschiedenen Ständen des Piloten (nach einer Änderung an seinem Code oder seinen Daten). "
    + "Der Pilot bestimmt das Ergebnis mit, deshalb werden Partien verschiedener Piloten nie zusammengezählt; "
    + "statt die Auswertung abzulehnen, steht jeder Pilot-Fingerabdruck als eigene Schicht da.";
}

const OUTCOMES_AXIS_REASONS = { table_size: outcomesTableSizeReason, pilot_fingerprint: outcomesPilotReason };

// Why strata were not combined, in German (#1687 review P3-3): the reasons card_outcomes gives
// for pods, provenance and unknown axes; an unforeseen reason is shown as it is.
const OUTCOMES_REASONS_DE = [
  [/^the deck states were played against different pod sets/,
    () => "Die Deck-Stände wurden gegen verschiedene Gegner-Tische (Pods) gespielt; andere Gegner ergeben andere Siegraten, deshalb nicht zusammengeführt."],
  [/^the deck states differ in (.+?) \(or mix it\)/,
    (m) => `Die Deck-Stände unterscheiden sich in der Herkunft (${m[1]}) oder mischen sie; deshalb nicht zusammengeführt.`],
  [/^a deck state has unknown provenance \((.+)\)/,
    (m) => `Ein Deck-Stand hat unbekannte Herkunft (${m[1]}); unbekannt ist nicht gleich, deshalb nicht zusammengeführt.`],
  [/^a stratum has (.+): unknown is not equal/,
    (m) => `Eine Schicht hat eine unbekannte Achse (${m[1]}); unbekannt ist nicht gleich, deshalb nicht zusammengeführt.`],
  [/^no game names /,
    () => `Keine Partie nennt ${outcomesAxisNames()} zugleich; es gibt keine Schicht mit bekannten Achsen, alle Partien stehen unten getrennt.`],
];
function outcomesReasonText(reason) {
  const text = String(reason);
  for (const [pattern, german] of OUTCOMES_REASONS_DE) {
    const match = text.match(pattern);
    if (match) return `Nicht zusammengeführt: ${german(match)}`;
  }
  return `Nicht zusammengeführt: ${text}`;
}

// Logs without a pilot fingerprint (#1687 review P2-1): what happened, why not combining them is
// more honest than before, and what to do.
const OUTCOMES_PILOT_UNKNOWN_TEXT =
  "Pilot unbekannt: Diese Partien wurden vor dem Pilot-Fingerabdruck aufgezeichnet. Welcher Stand des Piloten sie gespielt hat, "
  + "ist nicht belegt: Die alte Pilot-Version blieb immer „1.0.0“, auch wenn sich der Pilot änderte. "
  + "Unbekannt ist nicht gleich: Ihre Zahlen bleiben je Stand unten sichtbar (eigene n/N), sie werden aber nie zu einem bekannten "
  + "Piloten addiert und nicht zu einer Zeile über mehrere Deck-Stände zusammengefasst, weil dabei verschiedene Piloten gemischt "
  + "worden sein könnten. Was tun: mit dem aktuellen Piloten neu spielen; dann tragen die Partien einen Pilot-Fingerabdruck und "
  + "die geschichtete Zeile erscheint wieder.";

// The German reasons of a not-pooled answer whose cell axes differ, or [] (then the raw reason).
function outcomesDifferingReasons(pooling) {
  const listed = Array.isArray(pooling.differing_axes) ? pooling.differing_axes : [];
  const axes = listed.length || !pooling.differing_axis
    ? listed
    : [{ field: pooling.differing_axis, values: pooling.differing_values }];
  const texts = axes
    .filter((axis) => axis && OUTCOMES_AXIS_REASONS[axis.field])
    .map((axis) => OUTCOMES_AXIS_REASONS[axis.field](axis.values));
  return texts.length && texts.length === axes.length ? [...texts, OUTCOMES_APART_SENTENCE, OUTCOMES_CELL_SENTENCE] : [];
}

const outcomesCohorts = (data) => (Array.isArray(data.cohorts) ? data.cohorts : []);

// The base win rate of a table size in words (#1694): 1/n with n seats.
const outcomesBaseRate = (size) =>
  Number.isInteger(size) && size > 0
    ? `Basis-Siegrate bei ${StudioUI.num(size, 0)} ${size === 1 ? "Sitz" : "Sitzen"}: 1/${StudioUI.num(size, 0)}`
    : "Basis-Siegrate unbekannt";

// One cell (table size and pilot fingerprint, #1694/#1687) as its own section: its own strata
// only, combined stratified when they may be, never together with another cell. Every stratum of
// the cell keeps its own section with n/N and provenance; a single stratum is not shown twice.
function outcomesCohortSection(h, cohort, deps) {
  const stands = Array.isArray(cohort.stands) ? cohort.stands : [];
  const pooling = cohort.pooling || {};
  const pooled = pooling.status === "POOLED";
  const count = StudioUI.num(stands.length, 0);
  const what = pooled
    ? `${count} Deck-Stände geschichtet (je Stand eigene Differenz, gewichtet zusammengeführt)`
    : stands.length === 1
      ? "1 Deck-Stand"
      : `${count} Deck-Stände nicht zusammengeführt`;
  const sizeLabel = outcomesCellName(cohort);
  const parts = [
    `Schichten dieses Abschnitts: ${outcomesInt(cohort.strata)}`,
    `Partien: ${outcomesInt(cohort.games_total)}`,
    `${outcomesBaseRate(cohort.table_size)}, nie mit einer anderen Tischgröße oder einem anderen Pilot-Fingerabdruck gemischt`,
  ];
  if (pooling.reason) parts.push(outcomesReasonText(pooling.reason));
  if (pooling.method) parts.push(`Verfahren: ${pooling.method}`);
  const cards = Array.isArray(cohort.cards) ? cohort.cards : [];
  return h("section", {},
    h("h4", {}, `${sizeLabel} · ${what}`),
    h("p", { class: "muted" }, parts.join(" · ")),
    ...(pooled ? outcomesMetadataNodes(h, cohort, `${sizeLabel} · ${what}`, { skipped: false }) : []),
    pooled && cards.length
      ? outcomesCardTable(h, cards, deps, `Karten-Auswertung geschichtet für ${sizeLabel}`)
      : null,
    ...stands.map((stand) => outcomesStandSection(h, stand, deps)));
}

const outcomesUnknownStrata = (data) => (Array.isArray(data.unknown_strata) ? data.unknown_strata : []);

// The name of a stratum: one part per axis (deck state, table size, pilot fingerprint), an
// unknown value by its label ("Stand unbekannt", "Tischgröße unbekannt", "Pilot unbekannt").
const outcomesStratumName = (stratum) => OUTCOMES_AXES.map((axis) => outcomesAxisText(axis, stratum)).join(" · ");

// The label of an answer that carries strata (schema 2+): which stratum or strata the top table is.
function outcomesStandLabel(data, baseRevision) {
  const stands = Array.isArray(data.stands) ? data.stands : [];
  const current = (stand) => Array.isArray(stand.revision_ids) && baseRevision && stand.revision_ids.includes(baseRevision);
  if (!stands.length) return `keine Schicht, in der ${outcomesAxisNames()} bekannt sind (alle Partien getrennt unten)`;
  if (stands.length === 1) {
    return `Deck-Stand (Hash): ${outcomesShortHash(stands[0].deck_hash)}${current(stands[0]) ? " (gewählter Stand)" : ""} · ${outcomesCellName(stands[0])}`;
  }
  const pooled = data.pooling && data.pooling.status === "POOLED";
  return pooled
    ? `${StudioUI.num(stands.length, 0)} Deck-Stände geschichtet (je Stand eigene Differenz, gewichtet zusammengeführt) · ${outcomesCellName(data)}`
    : `${StudioUI.num(stands.length, 0)} Schichten (${outcomesAxisNames()}) nicht zusammengeführt`;
}

function outcomesStandNote(h, data) {
  const unknown = outcomesUnknownStrata(data);
  const unknownTexts = unknown.length
    ? unknown.map((t) => `${outcomesStratumName(t)}: ${outcomesInt(t.games_total)} Partien (getrennt gezählt, nie addiert)`)
    : [`${outcomesAnd(OUTCOMES_AXES.map((axis) => axis.unknown))}: keine Partien`];
  const pooling = data.pooling || {};
  const parts = [`Schichten (${outcomesAxisNames()}): ${outcomesInt(data.strata)}`, ...unknownTexts];
  const pilotAxis = OUTCOMES_AXES.find((axis) => axis.field === "pilot_fingerprint");
  if (unknown.some((t) => !outcomesAxisKnown(pilotAxis, t))) {
    parts.push(OUTCOMES_PILOT_UNKNOWN_TEXT);
  }
  const reasons = outcomesDifferingReasons(pooling);
  if (reasons.length) parts.push(...reasons);
  else if (pooling.reason) parts.push(outcomesReasonText(pooling.reason));
  if (pooling.method) parts.push(`Verfahren: ${pooling.method}`);
  return h("p", { class: "muted" }, parts.join(" · "));
}

// #1662: the games with a human seat, apart; never one number with the simulated games above.
function outcomesPlayedNote(h, data) {
  const played = data && data.played_cohort;
  if (!played || typeof played !== "object") {
    return h("p", { class: "muted" },
      "Mensch-Partien (PLAYED_GAME): unbekannt (Antwort ohne Kohortenangabe) · in keiner Zahl oben enthalten");
  }
  const unknown = typeof played.games_cohort_unknown === "number" && played.games_cohort_unknown > 0
    ? ` · Partien mit unlesbarer Kohorte: ${outcomesInt(played.games_cohort_unknown)} (in keiner Kohorte gezählt)`
    : played.games_cohort_unknown === null || played.games_cohort_unknown === undefined
      ? " · Partien mit unlesbarer Kohorte: unbekannt"
      : "";
  // n counts each game once by its game id, any status; the ended ones are named apart
  const status = typeof played.games === "number"
    ? ` (beendet ${outcomesInt(played.games_finished)}, nicht beendet ${typeof played.games_finished === "number" ? outcomesInt(played.games - played.games_finished) : "unbekannt"})`
    : "";
  return h("p", { class: "muted" },
    `Mensch-Partien (${played.data_class || "PLAYED_GAME"}, je Spiel-ID, jeder Status): n = ${outcomesInt(played.games)}${status} · Herkunft: ${played.source || "unbekannt"} · eigene Kohorte, in keiner Zahl oben enthalten${unknown}`);
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

// One stratum as its own section: every axis by its value or its unknown label with the reason
// ("Stand unbekannt", "Tischgröße unbekannt", "Pilot unbekannt"), its own n/N and table.
function outcomesStandSection(h, stand, deps) {
  const known = outcomesKnownText(stand.deck_hash);
  const revisions = Array.isArray(stand.revision_ids) && stand.revision_ids.length ? stand.revision_ids.join(", ") : "unbekannt";
  const axes = OUTCOMES_AXES.map((axis) => outcomesAxisText(axis, stand, true)).join(" · ");
  const head = `${axes} · ${outcomesInt(stand.games_total)} Partien${known ? ` · Stände im Deckbauer: ${revisions}` : ""}`;
  const apart = OUTCOMES_AXES.some((axis) => !outcomesAxisKnown(axis, stand)) ? " · nie zu einer bekannten Schicht addiert" : "";
  const cards = Array.isArray(stand.cards) ? stand.cards : [];
  // Every stratum, the unknown ones included, names its own provenance, qualification and
  // warnings (BRIDGE_AHEAD among them): its numbers are never shown without them.
  const standLabel = known
    ? `Deck-Stand (Hash): ${outcomesShortHash(stand.deck_hash)} · ${outcomesCellName(stand)}`
    : outcomesStratumName(stand);
  return h("details", {},
    h("summary", {}, head + apart),
    ...outcomesMetadataNodes(h, stand, standLabel, { skipped: false }),
    cards.length
      ? outcomesCardTable(h, cards, deps, `Karten-Auswertung einer Schicht (${outcomesStratumName(stand)})`)
      : h("p", { class: "muted" }, "Keine Partien mit Starthand-Daten (zu wenig Daten, nicht 0)."));
}

function outcomesMetadataNodes(h, data, queryLabel, options = {}) {
  // a fingerprint ("fp:<sha256>", #1658) by its short hash; a version string of an older log as it is
  const pilots = Array.isArray(data.pilots) && data.pilots.length
    ? data.pilots.map((p) => (String(p).startsWith("fp:") ? `Pilot-Fingerabdruck ${outcomesShortHash(String(p).slice(3))}` : p)).join(", ")
    : "unbekannt";
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
      // skipped logs cannot be told apart by deck state: they are counted for the deck only
      `Partien: ${outcomesInt(data.games_total)} ausgewertet, ${options.skipped === false ? "" : `${outcomesInt(data.games_skipped)} übersprungen, `}ohne Starthand: ${outcomesInt(data.seats_without_opening_hand)} · `,
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
  // Schema 2+ (#1657, #1683) names its strata; an answer without them keeps the old label.
  const perStand = Array.isArray(data.stands);
  const label = perStand ? `über Deck-ID ${queryId || "unbekannt"} · ${outcomesStandLabel(data, deps.baseRevision)}` : queryLabel;
  const meta = outcomesMetadataNodes(h, data, label);
  const standNote = perStand ? outcomesStandNote(h, data) : null;
  const playedNote = outcomesPlayedNote(h, data);
  const sections = [];
  const cohorts = perStand ? outcomesCohorts(data) : [];
  if (perStand) {
    // Several cells (#1694, #1687): one section per table size and pilot fingerprint holds its
    // strata; otherwise the strata stand in one list as before.
    if (cohorts.length) cohorts.forEach((cohort) => sections.push(outcomesCohortSection(h, cohort, deps)));
    else if (data.stands.length > 1) data.stands.forEach((stand) => sections.push(outcomesStandSection(h, stand, deps)));
    outcomesUnknownStrata(data).forEach((stratum) => sections.push(outcomesStandSection(h, stratum, deps)));
  }

  if (data.status === "NOT_POOLED") {
    slot.replaceChildren(...StudioUI.kids(
      h("h3", {}, title), fixedNote, dirtyNote, ...meta, standNote, playedNote,
      h("p", { class: "muted" }, cohorts.length
        ? `Verschiedene Werte von ${outcomesAxisNames(OUTCOMES_CELL_AXES)} werden nie zusammengeführt: Unten steht je Kombination ein eigener Abschnitt (${StudioUI.num(cohorts.length, 0)} Abschnitte) mit eigener Tabelle, eigener Zahl und Herkunft.`
        : `Die Schichten (${outcomesAxisNames()}) werden nicht zusammengeführt (siehe Grund); jede Schicht steht unten mit eigener Zahl.`),
      ...sections));
    return;
  }

  if (data.status === "NO_GAMES" || !Array.isArray(data.cards) || !data.cards.length) {
    slot.replaceChildren(...StudioUI.kids(
      h("h3", {}, title), fixedNote, dirtyNote, ...meta, standNote, playedNote,
      h("p", { class: "muted" }, perStand && outcomesUnknownStrata(data).length
        ? `Für ${label} liegen keine Partien vor, in denen ${outcomesAxisNames()} bekannt sind; die übrigen Partien stehen unten unter ${OUTCOMES_AXES.map((axis) => `„${axis.unknown}“`).join(" bzw. ")} (getrennt gezählt, mit eigener Herkunft).`
        : `Für ${label} liegen noch keine abgeschlossenen Partien mit Starthand-Daten vor (zu wenig Daten, nicht 0).`),
      ...sections));
    return;
  }

  const table = outcomesCardTable(h, data.cards, deps, "Karten-Auswertung aus simulierten Partien (Starthand gegen nicht in Starthand)");
  slot.replaceChildren(...StudioUI.kids(h("h3", {}, title), fixedNote, dirtyNote, ...meta, standNote, playedNote, table, ...sections));
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    outcomesDeckHash,
    outcomesPp,
    outcomesPpInterval,
    outcomesPctInterval,
    outcomesRatio,
    outcomesShortHash,
    outcomesBaseRate,
    outcomesStandLabel,
    outcomesStratumName,
    outcomesReasonText,
    outcomesTableSize,
    outcomesPlayedNote,
    OUTCOMES_AXES,
    renderCardOutcomes,
  };
}
