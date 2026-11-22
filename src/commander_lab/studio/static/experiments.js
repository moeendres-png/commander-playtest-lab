"use strict";
// Experiments of the open deck (B2b, #1658): the list comes from the deck's series answer
// (/api/decks/{id}/series), the detail from GET /api/experiments/{id}. Shown is what the answers
// hold: plan, arms with hashes, seeds, purpose (Erkundung / Bestätigung / Kontrolle), plan state,
// provenance, the finding with n/N and its maturity. The maturity, the state relation and the
// "empfehlungsfähig" flag are taken from the route as they are; nothing is computed here, no
// figure is added up over the arms or over series. A figure of the deck's series is shown only
// through the number contract (zahl.js, class SIMULIERT) and only when the route counts the
// result. Unknown stays text, never 0. SIMULATED_RESULT, never mixed with EDHREC, Playgroup or
// tournament figures, never part of the tier list.
// "Übernehmen" / "Verwerfen" only after an explicit click on the confirmation panel, which names
// the consequences; the decision goes to the B2a routes (POST /api/experiments/{id}/decision).
// Rejecting keeps the state, plan, series and finding; only the decision is recorded. No deck
// file is written. The list is keyed by the experiment id, never by the series id (two index
// rows can name the same series).
// DOM only through h() and text nodes; numbers only through StudioUI.num.

const EXPERIMENT_PURPOSE_TEXT = { exploration: "Erkundung", confirmation: "Bestätigung", control: "Kontrolle" };
const EXPERIMENT_KIND_TEXT = { package: "Paket", axis: "Bauachse", single_swap: "Einzeltausch" };
const EXPERIMENT_PLAN_STATE = {
  intact: ["pill good", "Plan intakt (Plan-SHA passt zum Index)"],
  mismatch: ["pill bad", "Plan-Datei passt nicht zum Index: der Befund zählt nicht"],
  missing: ["pill bad", "Plan-Datei fehlt: der Befund zählt nicht"],
  legacy: ["pill warn", "Alt-Serie ohne Plan (vor #1658)"],
};
const EXPERIMENT_SIMULATED = "SIMULATED_RESULT: simuliert mit gleichen Seeds, Sitzen und Gegner-Tisch; nie mit EDHREC-, Playgroup- oder Turnier-Zahlen zusammengezählt, kein Teil der Tierliste.";

const experimentPurpose = (value) => EXPERIMENT_PURPOSE_TEXT[value] || "Zweck unbekannt";
const experimentShort = (sha) => (typeof sha === "string" && sha ? sha.slice(0, 12) : "unbekannt");
const experimentText = (value) => (typeof value === "string" && value ? value : "unbekannt");
const experimentDate = (iso) => (iso ? iso.slice(0, 16).replace("T", " ") : "unbekannt");
const experimentPp = (value) =>
  value === null || value === undefined ? "unbekannt" : `${value >= 0 ? "+" : ""}${StudioUI.num(value, 1)} pp`;

function experimentStand(revisionId, labels) {
  if (!revisionId) return "unbekannt";
  return labels && labels.has(revisionId) ? labels.get(revisionId) : `Stand ${revisionId}`;
}

// The cut of the legacy scan, as the series answer states it: "≥ N" when files stayed unread.
function experimentLegacyNote(data) {
  const shown = data.legacy_series_shown;
  const found = data.legacy_series_found;
  if (data.legacy_series_found_lower_bound || data.scan_truncated) {
    return `Alt-Serien ohne Index: ${StudioUI.num(shown)} gezeigt von ≥ ${StudioUI.num(found)} gefunden; ${StudioUI.num(data.scan_truncated)} ältere Dateien nicht geprüft, Gesamtzahl unbekannt.`;
  }
  if (typeof shown === "number" && typeof found === "number" && shown < found) {
    return `Alt-Serien ohne Index: gekürzt, ${StudioUI.num(shown)}/${StudioUI.num(found)} gezeigt.`;
  }
  return null;
}

// Pairs of one series as the answer counts them (completed / planned); never a sum.
function experimentPairs(result) {
  if (!result) return "Paare unbekannt";
  if (!result.counts_as_result) return `kein Ergebnis (${StudioUI.num(result.pairs_attempted)} von ${StudioUI.num(result.pairs_planned)} Paaren begonnen)`;
  return `n/N ${StudioUI.num(result.pairs_completed)} / ${StudioUI.num(result.pairs_planned)} Paare (abgeschlossen / geplant)`;
}

function experimentRows(data) {
  return data.series.map((entry) => ({
    key: entry.experiment ? entry.experiment.experiment_id : entry.series_id,
    entry,
  }));
}

// The table of a listed series (#1661): 4-, 5- and 6-seat runs of the same question are separate
// cohorts, so each row names its size; a size the played games do not prove is named as such.
const EXPERIMENT_TABLE_CHECK_TEXT = {
  mismatch: "Tischgröße unbekannt (Plan und gespielte Partien weichen ab)",
  unreadable: "Tischgröße unbekannt (Sitzzahl der gespielten Partien nicht lesbar)",
};
function experimentEntryTable(entry) {
  if (EXPERIMENT_TABLE_CHECK_TEXT[entry.table_size_check]) return EXPERIMENT_TABLE_CHECK_TEXT[entry.table_size_check];
  if (!Number.isInteger(entry.table_size) || entry.table_size < 2) return "Tischgröße unbekannt";
  return `${StudioUI.num(entry.table_size, 0)} Sitze${entry.table_size_check === "unobserved" ? " (geplant, nicht an Partien geprüft)" : ""}`;
}

function experimentListTable(h, data, onOpen) {
  const rows = experimentRows(data).map(({ key, entry }) => {
    const exp = entry.experiment;
    return h("tr", {},
      h("td", {}, experimentDate(entry.created_at)),
      h("td", {}, exp ? exp.question : "Alt-Serie ohne Plan"),
      h("td", {}, exp ? experimentPurpose(exp.purpose) : "Zweck unbekannt"),
      h("td", {}, experimentEntryTable(entry)),
      h("td", { class: "num" }, experimentPairs(entry)),
      h("td", {}, entry.status_text),
      h("td", {}, exp ? exp.decision_text : "keine Entscheidung (Alt-Serie)"),
      h("td", {}, h("button", { type: "button", class: "small", onclick: () => onOpen(key) }, "Ansehen")));
  });
  return h("div", { class: "table-wrap" }, h("table", {},
    h("thead", {}, h("tr", {}, ["Angelegt", "Frage", "Zweck", "Tisch", "Paare (n/N)", "Status", "Entscheidung", ""].map((label) => h("th", {}, label)))),
    h("tbody", {}, rows)));
}

function experimentMaturity(h, detail) {
  const befund = detail.reifegrad;
  if (!befund) return h("div", { class: "muted" }, `Reifegrad: ${detail.reifegrad_hinweis || "kein Befund (unbekannt)"}`);
  const other = !befund.stand || befund.stand.bezug !== "aktuell";
  const pairs = befund.n === null || befund.N === null ? "Paare unbekannt" : `n/N ${StudioUI.num(befund.n)} / ${StudioUI.num(befund.N)} ${befund.bezug}`;
  return h("div", { class: "evidence-row" },
    befund.stufe ? h("span", { class: "pill" }, befund.stufe_text) : h("span", { class: "muted" }, befund.stufe_text),
    h("div", {}, `Ergebnis (simuliert): ${befund.urteil_text} · ${pairs} · ${typeof befund.tisch_text === "string" && befund.tisch_text ? befund.tisch_text : "Tischgröße unbekannt"}`),
    h("div", { class: other ? "muted" : "" },
      other ? h("span", { class: "pill warn" }, "anderer Stand") : null,
      other ? " " : "",
      befund.stand ? befund.stand.text : "Stand unbekannt"),
    befund.empfehlungsfaehig
      ? h("div", {}, h("span", { class: "pill good" }, "empfehlungsfähig"))
      : h("div", { class: "muted" }, `nicht empfehlungsfähig: ${(befund.empfehlungsfaehig_gruende || []).join("; ") || "Grund unbekannt"}`),
    ...(befund.hinweise || []).map((note) => h("div", { class: "muted" }, note)));
}

function experimentFinding(h, detail, zahlen) {
  const result = detail.result;
  const counted = Boolean(result && result.counts_as_result);
  const zahl = counted && zahlen ? zahlen.get(`series.${result.series_id}.difference_pp`) : undefined;
  const figure = !counted
    ? h("div", { class: "muted" }, `nicht als Ergebnis gezählt (${result ? result.status_text : "Status unbekannt"})`)
    : zahl
      ? h("div", {}, "Differenz (B − A): ", StudioZahl.knoten(h, zahl))
      : h("div", { class: "muted" }, "Differenz (B − A): unbekannt (keine gültige Zahl im Zahl-Vertrag)");
  return h("div", {},
    h("h4", {}, "Befund"),
    h("p", { class: "note note-compact" }, EXPERIMENT_SIMULATED),
    h("div", {}, experimentPairs(result)),
    figure,
    experimentMaturity(h, detail),
    h("div", { class: "muted" }, `Herkunft: Plan ${experimentText(detail.sources && detail.sources.plan)} · Ergebnis ${experimentText(detail.sources && detail.sources.result)} · ${experimentText(detail.sources && detail.sources.index)}`));
}

// The table of the plan (#1661): its seat count from the resolved table; 4-, 5- and 6-seat
// experiments are separate cohorts (own Holm family, own base win rate 1/N). Unknown stays text.
function experimentTableText(detail) {
  const seats = detail && detail.table ? detail.table.seats : null;
  return Number.isInteger(seats) && seats >= 2
    ? `Tisch: ${StudioUI.num(seats, 0)} Sitze (Zufallsbasis 1/${StudioUI.num(seats, 0)}, eigene Kohorte)`
    : "Tisch: Tischgröße unbekannt";
}

function experimentPlan(h, detail) {
  const plan = detail.plan;
  const [cls, text] = EXPERIMENT_PLAN_STATE[detail.plan_state] || ["pill warn", "Plan-Zustand unbekannt"];
  const seeds = detail.seeds || {};
  const seedText = seeds.first === null || seeds.first === undefined
    ? "unbekannt"
    : `${String(seeds.first)} bis ${seeds.last === null || seeds.last === undefined ? "unbekannt" : String(seeds.last)} (${StudioUI.num(seeds.count)} Seeds)`; // seeds are ids: no thousands dots
  const items = [
    h("div", {}, h("span", { class: cls }, text)),
    h("div", {}, `Zweck: ${experimentPurpose(detail.purpose)}`),
    h("div", {}, `Seeds: ${seedText}`),
    h("div", {}, experimentTableText(detail)),
    h("div", {}, `Sitze getestet: ${Array.isArray(detail.tested_seats) ? detail.tested_seats.map((seat) => StudioUI.num(seat + 1)).join(", ") : "unbekannt"}`),
    h("div", {}, `Tisch-Hash: ${experimentShort(detail.table_hash)}`),
  ];
  if (plan) {
    items.push(
      h("div", {}, `Art: ${EXPERIMENT_KIND_TEXT[plan.question_kind] || "unbekannt"}`),
      h("div", {}, `Budget: ${StudioUI.num(plan.budget_pairs)} Paare · Look alle ${StudioUI.num(plan.look_every_pairs)} Paare · Stopp-Regel ${experimentText(plan.stop_rule)}`),
      h("div", {}, `Schwelle: ${experimentPp(plan.threshold_pp)} · Niveau ${StudioUI.num(plan.significance_level, 3)}`));
  } else {
    items.push(h("div", { class: "muted" }, "Plan nicht angezeigt (nicht intakt oder Alt-Serie)."));
  }
  return h("div", {}, h("h4", {}, "Plan"), ...items);
}

function experimentArms(h, detail, labels) {
  const roleText = { base: "Basis (A)", variant: "Variante (B)" };
  return h("div", {}, h("h4", {}, "Arme"), h("div", { class: "table-wrap" }, h("table", {},
    h("thead", {}, h("tr", {}, ["Rolle", "Stand", "Deck-Hash"].map((label) => h("th", {}, label)))),
    h("tbody", {}, (detail.arms || []).map((arm) => h("tr", {},
      h("td", {}, roleText[arm.role] || "unbekannt"),
      h("td", {}, experimentStand(arm.revision_id, labels)),
      h("td", {}, experimentShort(arm.deck_hash))))))));
}

function experimentProvenance(h, detail) {
  const p = detail.provenance || {};
  return h("div", { class: "muted" },
    `Engine-Pin: ${experimentShort(p.engine_pin)} · Bridge-JAR: ${experimentShort(p.bridge_jar_sha256)} · Bridge-Zustand: ${experimentText(p.bridge_state)} · Pilot-Fingerabdruck: ${experimentShort(p.pilot_fingerprint)}`);
}

// Whether the route already says the server will refuse the adoption (main moved off the base).
function experimentAdoptRefused(detail) {
  const base = (detail.arms || []).find((arm) => arm.role === "base");
  return !base || detail.current_main_revision_id !== base.revision_id;
}

// The consequences of a decision, only from fields of the route.
function experimentConsequences(decision, detail, labels) {
  const arms = detail.arms || [];
  const base = arms.find((arm) => arm.role === "base");
  const variant = arms.find((arm) => arm.role === "variant");
  if (decision === "rejected") {
    return [
      `Die Variante ${experimentStand(variant && variant.revision_id, labels)} bleibt als abgelehnter Stand erhalten.`,
      "Plan, Serie und Befund bleiben gespeichert; nur die Entscheidung wird vermerkt.",
      "main und die Deck-Dateien bleiben unverändert.",
    ];
  }
  const lines = [
    `main zeigt danach auf den Variantenstand ${experimentStand(variant && variant.revision_id, labels)}.`,
    "Der Klick gilt als Owner-Entscheid zur Basis (E15 Q2); keine Deck-Datei wird geschrieben.",
  ];
  if (!detail.result || !detail.result.counts_as_result) lines.push("Ohne gezählten Befund wird die Übernahme als „ungetestet“ vermerkt.");
  if (experimentAdoptRefused(detail)) {
    lines.push("main steht nicht mehr auf der Basis dieses Experiments: der Server lehnt die Übernahme ab, nichts wird überschrieben.");
  }
  return lines;
}

// Adopting moves main: an unsaved draft on main (this tab or stored on the server) would later
// put the old base back. While one exists, or the server will refuse anyway, "Ja, übernehmen"
// stays disabled and the panel says why.
async function experimentCheckDraft(detail, deps, lines, done) {
  const h = deps.h;
  const reasons = [];
  if (experimentAdoptRefused(detail)) reasons.push("Übernehmen ist gesperrt, solange main nicht auf der Basis steht.");
  let open = Boolean(deps.localMainDraft && deps.localMainDraft());
  if (!open) {
    try {
      const found = await deps.api(`/api/decks/${encodeURIComponent(detail.deck_id)}/branches/main/draft`);
      open = Boolean(found && found.draft);
    } catch (error) {
      reasons.push(`Entwurf auf main nicht prüfbar (${StudioUI.germanError(error)}): Übernehmen bleibt gesperrt.`);
    }
  }
  if (open) reasons.push("Es gibt einen ungespeicherten Entwurf auf main; erst speichern oder verwerfen.");
  for (const reason of reasons) lines.append(h("li", { class: "bad" }, reason));
  done(reasons.length === 0);
}

function experimentDecision(h, detail, labels, deps) {
  const exp = detail.experiment;
  if (!exp) return h("div", {}, h("h4", {}, "Entscheidung"), h("p", { class: "muted" }, "Alt-Serie ohne Plan: keine Entscheidung möglich."));
  if (exp.decision !== "open") {
    return h("div", {}, h("h4", {}, "Entscheidung"),
      h("p", {}, `${exp.decision_text} am ${experimentDate(exp.decision_at)}`),
      exp.decision_note ? h("p", { class: "muted" }, `Notiz: ${exp.decision_note}`) : null);
  }
  const box = h("div", {});
  const showChoice = () => box.replaceChildren(h("div", { class: "actions" },
    h("button", { type: "button", onclick: () => confirmPanel("adopted") }, "Übernehmen …"),
    h("button", { type: "button", onclick: () => confirmPanel("rejected") }, "Verwerfen …")));
  function confirmPanel(decision) {
    const note = h("textarea", { name: "experiment-decision-note", rows: 2, "aria-label": "Notiz zur Entscheidung (darf leer sein)", placeholder: "Notiz (darf leer sein)" });
    const status = h("p", { class: "muted", role: "status" });
    const lines = h("ul", {}, experimentConsequences(decision, detail, labels).map((line) => h("li", {}, line)));
    let sending = false;
    let blocked = decision === "adopted"; // until the draft check below has answered
    const cancel = h("button", { type: "button", onclick: () => { if (!sending) showChoice(); } }, "Abbrechen");
    const yes = h("button", {
      type: "button",
      class: decision === "adopted" ? "primary" : "",
      disabled: blocked,
      onclick: async () => {
        if (sending || blocked) return; // one POST per confirmation, never while blocked
        sending = true;
        yes.disabled = true;
        cancel.disabled = true;
        try {
          await deps.api(`/api/experiments/${encodeURIComponent(detail.experiment_id)}/decision`, "POST", { decision, note: note.value || "" });
        } catch (error) {
          sending = false;
          yes.disabled = false;
          cancel.disabled = false;
          status.replaceChildren(StudioUI.germanError(error));
          return;
        }
        try {
          await deps.onDecided(decision);
        } catch (error) { // recorded on the server; only reloading the view failed
          status.replaceChildren(`Entscheidung gespeichert, Ansicht nicht neu geladen: ${StudioUI.germanError(error)}`);
        }
      },
    }, decision === "adopted" ? "Ja, übernehmen" : "Ja, verwerfen");
    box.replaceChildren(h("div", { class: "note", role: "group", "aria-label": "Entscheidung bestätigen" },
      h("b", {}, decision === "adopted" ? "Variante übernehmen?" : "Variante verwerfen?"),
      lines,
      note,
      h("div", { class: "actions" }, yes, cancel),
      status));
    if (decision === "adopted") return experimentCheckDraft(detail, deps, lines, (ok) => { blocked = !ok; yes.disabled = !ok; });
    return null;
  }
  showChoice();
  return h("div", {}, h("h4", {}, "Entscheidung"), h("p", { class: "muted" }, "offen: nichts wird automatisch übernommen oder verworfen."), box);
}

function experimentDetailView(h, detail, ctx) {
  return h("div", { class: "experiment-detail" },
    h("h3", {}, detail.question),
    experimentPlan(h, detail),
    experimentArms(h, detail, ctx.labels),
    experimentProvenance(h, detail),
    experimentFinding(h, detail, ctx.zahlen),
    experimentDecision(h, detail, ctx.labels, ctx));
}

async function experimentOpen(target, key, ctx) {
  const { h } = ctx;
  const token = (ctx.openSeq.n += 1); // a late answer for an earlier click never covers a later one
  target.replaceChildren(h("p", { class: "muted" }, "lädt …"));
  let detail = null;
  try {
    detail = await ctx.api(`/api/experiments/${encodeURIComponent(key)}`);
  } catch (error) {
    if (token !== ctx.openSeq.n) return;
    target.replaceChildren(h("p", { class: "muted" }, error && error.status === 404
      ? "nicht im Index (ältere Serie): erst nach einem Neuaufbau des Index sichtbar; nichts wird automatisch neu aufgebaut."
      : StudioUI.germanError(error)));
    return;
  }
  if (token !== ctx.openSeq.n) return;
  target.replaceChildren(experimentDetailView(h, detail, ctx));
}

async function renderExperiments(slot, historyRows, deps) {
  const { h } = deps;
  const title = h("h3", {}, "Experimente dieses Decks");
  const labels = new Map((historyRows || []).map((row) => [row.revision_id, `Stand ${experimentDate(row.created_at)}${row.branch ? ` (${row.branch})` : ""}`]));
  const load = async () => {
    slot.replaceChildren(title, h("p", { class: "muted" }, "lädt …"));
    let data = null;
    try {
      data = await deps.api(`/api/decks/${encodeURIComponent(deps.deckId)}/series`);
    } catch (error) {
      slot.replaceChildren(title, h("p", { class: "muted" }, `Experimente konnten nicht gelesen werden (unbekannt, nicht 0): ${StudioUI.germanError(error)}`));
      return;
    }
    const detailBox = h("div", {});
    const ctx = { ...deps, labels, zahlen: StudioZahl.index(data.zahlen), openSeq: { n: 0 } };
    const legacy = experimentLegacyNote(data);
    slot.replaceChildren(title,
      h("p", { class: "note note-compact" }, EXPERIMENT_SIMULATED, legacy ? ` ${legacy}` : ""),
      data.series.length ? experimentListTable(h, data, (key) => experimentOpen(detailBox, key, ctx)) : h("p", { class: "muted" }, "kein Experiment gespeichert"),
      detailBox);
  };
  slot.replaceChildren(title, h("button", { type: "button", class: "small", onclick: load }, "Experimente anzeigen"));
}

if (typeof module !== "undefined") {
  module.exports = { renderExperiments, experimentDetailView, experimentListTable, experimentLegacyNote, experimentConsequences, experimentPairs, experimentOpen, experimentTableText, experimentEntryTable };
}
