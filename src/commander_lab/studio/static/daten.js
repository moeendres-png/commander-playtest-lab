"use strict";
// Commander Studio: dedicated Data Health & Sources page (#daten).
// Strictly counts-only (n / N, UNKNOWN never 0, no private card-name or deck-URL leakage).

const $ = (id) => document.getElementById(id);
const h = (tag, props, ...children) => StudioUI.h(tag, props, ...children);
const nf = (value) => (value === null || value === undefined ? "unbekannt" : StudioUI.num(value, 0));
const shareText = (obj) => {
  if (!obj || obj.count === null || obj.count === undefined || obj.of === null || obj.of === undefined) {
    return "unbekannt";
  }
  return obj.of ? `${nf(obj.count)} / ${nf(obj.of)} (${StudioUI.pct(obj.count / obj.of, 1)})` : `${nf(obj.count)} / 0`;
};
const unknown = (text = "unbekannt") => h("span", { class: "unknown" }, text);

function simpleTable(heads, rows) {
  return h("div", { class: "table-wrap" }, h("table", {},
    h("thead", {}, h("tr", {}, heads.map((label) => h("th", { scope: "col" }, label)))),
    h("tbody", {}, rows.map((row) => h("tr", {}, row.map((cell) => h("td", {}, cell)))))
  ));
}

function kvTable(pairs) {
  return simpleTable(["Kennzahl", "Wert"], pairs);
}

function renderBridge(report) {
  const host = $("data-bridge");
  const bq = report.bridge_qualification || {};
  const stateCode = bq.state || bq.status || "UNKNOWN";
  const badgeCls = stateCode === "SEALED" ? "good" : "warn";
  const notMeasured = Array.isArray(report.not_measured_here) ? report.not_measured_here : [];
  host.replaceChildren(...[
    h("h2", {}, "System- & Bridge-Status"),
    h("p", { class: "muted" }, report.privacy || "Nur Zählungen: keine Kartennamen, keine Deck-Adressen, keine Notizen."),
    kvTable([
      ["Berichts-Schema", report.schema || "–"],
      ["Erstellt am", report.generated_on || "–"],
      ["Bridge-Qualifikation", h("span", { class: `badge ${badgeCls}` }, String(stateCode))],
      ["Bridge-Hinweis", bq.reason || bq.note || "–"],
    ]),
    notMeasured.length
      ? h("p", { class: "rule" }, `Hier bewusst nicht gemessen: ${notMeasured.join(" · ")}`)
      : null,
  ].filter(Boolean));
}

function renderSources(status) {
  const host = $("data-sources");
  const inv = status.source_inventory || {};
  const layers = Array.isArray(status.source_layers) ? status.source_layers : [];
  const fresh = status.freshness || {};
  const recent = Array.isArray(status.sources) ? status.sources : [];

  const summary = h("p", { class: "muted" },
    `Registrierte Quellen: ${nf(inv.total)} (Verifiziert: ${nf(inv.verified)}, Prüfung: ${nf(inv.review)}, Nicht verfügbar: ${nf(inv.unavailable)}) · Bild-Cache: ${status.image_cache ? `${nf(status.image_cache.cached)}/${nf(status.image_cache.total)}` : "unbekannt"}`);

  const layerRows = layers.map((item) => [
    item.label || item.layer || "–",
    nf(item.rows),
    item.snapshot_date || unknown("kein Stand"),
    item.age_days === null || item.age_days === undefined ? unknown("–") : `${nf(item.age_days)} Tage`,
    item.stale === true ? h("span", { class: "badge warn" }, "veraltet") : item.stale === false ? h("span", { class: "badge good" }, "aktuell") : unknown("–"),
  ]);

  const recentRows = recent.slice(0, 12).map((src) => [
    src.source_id || "–",
    src.kind || "–",
    src.snapshot_date || unknown("–"),
    src.imported_at ? String(src.imported_at).slice(0, 19).replace("T", " ") : "–",
  ]);

  host.replaceChildren(...[
    h("h2", {}, "Quellen-Register & Frische"),
    summary,
    layerRows.length
      ? simpleTable(["Schicht / Quelle", "Zeilen", "Stand", "Alter", "Status"], layerRows)
      : h("p", { class: "muted" }, "Keine Schicht-Metadaten vorhanden."),
    recentRows.length
      ? h("details", {}, h("summary", {}, `Letzte Importe (${nf(recent.length)})`), simpleTable(["Quelle", "Typ", "Snapshot", "Importiert (UTC)"], recentRows))
      : null,
    fresh && fresh.note ? h("p", { class: "rule" }, String(fresh.note)) : null,
  ].filter(Boolean));
}

function renderCollection(report) {
  const host = $("data-collection");
  const col = report.collection || {};
  const scry = report.scryfall_facts || {};
  const rul = report.rulings || {};
  const fallbacks = report.fallbacks_used || {};
  const fbEntries = Object.entries(fallbacks);

  const staleNode = scry.stale === true
    ? h("span", { class: "badge warn" }, `veraltet (> ${nf(scry.stale_after_days)} Tage)`)
    : scry.stale === false
      ? h("span", { class: "badge good" }, "aktuell")
      : unknown("unbekannt");

  host.replaceChildren(
    h("h2", {}, "Sammlung, Scryfall & Import-Hygiene"),
    kvTable([
      ["Sammlungskarten (Zeilen)", nf(col.cards)],
      ["Karten mit Oracle-ID", shareText(col.with_oracle_id)],
      ["Exakte Stückzahl bekannt", shareText(col.quantity_exact)],
      ["Nie verifizierte Stückzahl", shareText(col.never_verified)],
      ["Scryfall Oracle-IDs im Store", nf(scry.oracle_ids)],
      ["Scryfall Snapshot-Datum", h("span", {}, scry.snapshot_date || "unbekannt", " ", staleNode)],
      ["Scryfall-Karten ohne Bild", shareText(scry.without_image)],
      ["Offizielle Rulings (Zeilen / Karten)", `${nf(rul.rows)} / ${nf(rul.cards_with_rulings)}`],
      ["Sammlungskarten mit Ruling", shareText(rul.collection_cards_with_rulings)],
    ]),
    fbEntries.length
      ? h("div", { class: "section" },
          h("h3", {}, "Defensive Feld-Fallbacks (#1453)"),
          simpleTable(["Fallback-Schlüssel", "Anzahl"], fbEntries.map(([k, v]) => [k, nf(v)])))
      : h("p", { class: "rule" }, "Defensive Feld-Fallbacks (#1453): 0 ausgelöst.")
  );
}

function renderRoles(report, roleAudit) {
  const host = $("data-roles");
  const roles = report.roles || {};
  const origins = roles.by_origin || {};
  const originRows = Object.entries(origins).map(([key, val]) => [
    key,
    nf(val.claims),
    nf(val.cards),
  ]);

  const auditNodes = [];
  if (roleAudit && roleAudit.summary) {
    const s = roleAudit.summary;
    auditNodes.push(
      h("h3", {}, "Rollen-Abgleich (Tagger vs. Heuristik)"),
      kvTable([
        ["Poolkarten geprüft", nf(s.pool_cards)],
        ["Mit Tagger-Rolle", `${nf(s.with_tagger)}/${nf(s.pool_cards)}`],
        ["Nur Regel-/Heuristik-Rolle", `${nf(s.only_heuristic)}/${nf(s.pool_cards)}`],
        ["Ohne jede Rolle", `${nf(s.without_role)}/${nf(s.pool_cards)}`],
      ])
    );
  }

  host.replaceChildren(...[
    h("h2", {}, "Rollen- & Taxonomie-Gesundheit"),
    kvTable([
      ["Vokabular-Größe", nf(roles.vocabulary)],
      ["Sammlung mit mindestens einer Rolle", shareText(roles.collection_with_any_role)],
      ["Sammlung ohne Rolle", shareText(roles.collection_without_any_role)],
      ["Tagger-basierte Rollen in Sammlung", shareText(roles.collection_with_tagger_based_role)],
      ["Korpus-Decks mit Rollen-Zählung", shareText(roles.corpus_decks_with_role_counts)],
      ["Rollen-Fingerprint", roles.fingerprint ? String(roles.fingerprint).slice(0, 16) : "–"],
    ]),
    originRows.length ? simpleTable(["Herkunft (role_origin)", "Claims", "Karten"], originRows) : null,
    ...auditNodes,
  ].filter(Boolean));
}

function renderCorpus(report) {
  const host = $("data-corpus");
  const corpus = report.corpus || {};
  const obs = report.observations || {};
  const uni = report.universes || {};
  const cmds = report.commanders || {};
  const alarms = Array.isArray(report.signal_rate_alarms) ? report.signal_rate_alarms : [];

  const cohortRows = Object.entries(corpus.by_cohort || {}).map(([k, v]) => [k, nf(v)]);
  const cmdDetails = Array.isArray(cmds.details) ? cmds.details : [];
  const cmdRows = cmdDetails.map((d) => [
    d.commander || "–",
    d.in_collection ? "ja" : "nein",
    d.pool ? `${nf(d.pool.legal_cards)} (unbek. Legalität: ${nf(d.pool.excluded_legality_unknown)})` : "–",
    Array.isArray(d.signal_rate_alarms) && d.signal_rate_alarms.length
      ? h("span", { class: "badge warn" }, `${nf(d.signal_rate_alarms.length)} Alarme`)
      : h("span", { class: "badge good" }, "0 Alarme"),
  ]);

  host.replaceChildren(...[
    h("h2", {}, "Korpus, Universen & Signal-Alarme"),
    alarms.length
      ? h("div", { class: "section" },
          h("h3", {}, `Aktive Signal-Raten-Alarme (${nf(alarms.length)})`),
          h("ul", {}, ...alarms.map((a) => h("li", { class: "bad" }, a.message || `${a.signal_name} (${a.alarm_type}): ${nf(a.count)}/${nf(a.denominator)}`))))
      : h("p", { class: "rule" }, "Keine aktiven Signal-Raten-Alarme (> 50 % Null/Fehlend)."),
    kvTable([
      ["Korpus-Decks gesamt", nf(corpus.decks)],
      ["Decks ohne Kartenzeilen", shareText(corpus.decks_without_card_rows)],
      ["Mainboard != 99 Karten", shareText(corpus.mainboard_not_99_cards)],
      ["Datum unbekannt", shareText(corpus.date_unknown)],
      ["Kartenzeilen ohne Oracle-ID", shareText(corpus.card_rows_without_oracle_id)],
      ["Beobachtungs-Zeilen (observation)", nf(obs.rows)],
      ["Beobachtungen ohne Zeitstempel", shareText(obs.time_unknown)],
      ["Beobachtungen ohne Nenner", shareText(obs.denominator_missing)],
      ["Gespeicherte Universums-Profile", `${nf(uni.profiles)} (unter Minimum: ${nf(uni.below_min_universe)}/${nf(uni.entries)})`],
      ["Legalität unbekannt in Sammlung", nf(cmds.legality_unknown_in_collection)],
    ]),
    cohortRows.length ? simpleTable(["Korpus-Kohorte", "Decks"], cohortRows) : null,
    cmdRows.length ? simpleTable(["Commander", "In Sammlung", "Pool (legal)", "Alarme"], cmdRows) : null,
  ].filter(Boolean));
}

function renderLayersAndRecipes(commander, layersPayload, conversion) {
  const host = $("data-layers");
  const layerList = layersPayload && Array.isArray(layersPayload.layers) ? layersPayload.layers : [];
  const layerRows = layerList.map((item) => [
    item.label || item.layer || "–",
    nf(item.rows),
    item.pool_total ? `${nf(item.pool_covered)}/${nf(item.pool_total)}` : "–",
    item.status || "–",
    item.command || "–",
  ]);

  const convSummary = conversion && conversion.summary
    ? h("p", { class: "rule" }, `TopDeck-Turnier-Umwandlung (${StudioCommander.shortName(commander)}): ${nf(conversion.summary.matched_cards)}/${nf(conversion.summary.pool_cards)} Poolkarten belegt.`)
    : null;

  const recipes = [
    ["Datenbericht (CLI)", "commander-lab studio data-report"],
    ["Scryfall Bulk aktualisieren", "commander-lab studio import-scryfall --file <oracle-cards.jsonl>"],
    ["Rollen-Audit prüfen", "commander-lab studio roles-audit"],
  ];

  host.replaceChildren(...[
    h("h2", {}, `Schichten für ${StudioCommander.shortName(commander)} & Offline-Befehle`),
    layerRows.length
      ? simpleTable(["Schicht", "Zeilen", "Pool abgedeckt", "Status", "Import-Befehl"], layerRows)
      : h("p", { class: "muted" }, "Keine Schicht-Übersicht für diesen Commander geladen."),
    convSummary,
    h("h3", {}, "Offline-Aktualisierungs-Rezepte (für den Owner-PC)"),
    simpleTable(["Aufgabe", "CLI-Befehl"], recipes.map(([label, cmd]) => [label, h("code", {}, cmd)])),
  ].filter(Boolean));
}

async function loadAll() {
  const commander = $("commander-select").value || StudioCommander.current;
  $("data-summary").textContent = "Lade Datenlage …";
  try {
    const [status, report, layersPayload, roleAudit, conversion] = await Promise.all([
      StudioUI.request("/api/status"),
      StudioUI.request("/api/data-report"),
      StudioUI.request(`/api/layers?commander=${encodeURIComponent(commander)}`).catch(() => null),
      StudioUI.request(`/api/roles/audit?commander=${encodeURIComponent(commander)}`).catch(() => null),
      StudioUI.request(`/api/tournament-conversion?commander=${encodeURIComponent(commander)}`).catch(() => null),
    ]);
    renderBridge(report);
    renderSources(status);
    renderCollection(report);
    renderRoles(report, roleAudit);
    renderCorpus(report);
    renderLayersAndRecipes(commander, layersPayload, conversion);
    const alarmCount = Array.isArray(report.signal_rate_alarms) ? report.signal_rate_alarms.length : 0;
    $("data-summary").textContent = `Stand ${report.generated_on || "–"} · Sammlung ${nf((report.collection || {}).cards)} Karten · Korpus ${nf((report.corpus || {}).decks)} Decks · Alarme: ${nf(alarmCount)}`;
  } catch (err) {
    $("data-summary").textContent = "Fehler beim Laden der Datenlage.";
    StudioUI.fail(StudioUI.germanError(err));
  }
}

async function init() {
  await StudioCommander.fill($("commander-select"));
  $("commander-select").addEventListener("change", () => loadAll());
  $("data-refresh").addEventListener("click", () => loadAll());
  await loadAll();
}

init().catch((err) => StudioUI.fail(StudioUI.germanError(err)));
