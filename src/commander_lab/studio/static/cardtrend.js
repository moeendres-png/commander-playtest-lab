"use strict";
// Per-card corpus trend from stored deck dates (#1550): recent vs. older deduplicated decks.
// Separate from EDHREC, playgroup, tournament and strength-index figures (weight 0).
// DOM only through h() and text nodes; numbers only through StudioUI.num / StudioUI.pct.

const CARD_TREND_WINDOWS = [
  { days: 90, label: "90 Tage" },
  { days: 180, label: "180 Tage (Standard)" },
  { days: 365, label: "365 Tage" },
];

const CARD_TREND_BRACKETS = [
  { value: "", label: "Ganzer Korpus (Standard)" },
  { value: "bracket:1", label: "Bracket 1 (kleine Kohorte)" },
  { value: "bracket:2", label: "Bracket 2 (kleine Kohorte)" },
  { value: "bracket:3", label: "Bracket 3 (kleine Kohorte)" },
  { value: "bracket:4", label: "Bracket 4 (kleine Kohorte)" },
  { value: "bracket:5", label: "Bracket 5 (kleine Kohorte)" },
];

function cardTrendPp(diff) {
  if (diff === null || diff === undefined) return "unbekannt";
  const pp = diff * 100;
  return `${pp > 0 ? "+" : ""}${StudioUI.num(pp, 1)} pp`;
}

function cardTrendInterval(low, high) {
  if (low === null || low === undefined || high === null || high === undefined) return "unbekannt";
  const a = low * 100;
  const b = high * 100;
  const left = `${a > 0 ? "+" : ""}${StudioUI.num(a, 1)}`;
  const right = `${b > 0 ? "+" : ""}${StudioUI.num(b, 1)}`;
  return `[${left}; ${right}] pp`;
}

function cardTrendRatio(hits, total) {
  if (total === null || total === undefined || total <= 0) return "unbekannt";
  return `${StudioUI.num(hits, 0)} / ${StudioUI.num(total, 0)}`;
}

function cardTrendSortValue(trendState, cardId) {
  if (!trendState || !trendState.map) return null;
  const item = trendState.map.get(cardId);
  if (!item || item.status !== "ok" || item.diff === null || item.diff === undefined) return null;
  return item.diff;
}

function cardTrendCell(h, trendState, cardId) {
  if (!trendState || !trendState.map) {
    return h("td", { class: "num muted", title: "Trend aus dem Deck-Datum des eigenen Korpus lädt …" }, "–");
  }
  const item = trendState.map.get(cardId);
  if (!item || item.status === "unknown") {
    return h("td", { class: "num muted", title: "Mindestens ein Zeitfenster enthält 0 Decks (unbekannt)." }, "unbekannt");
  }
  if (item.status === "too_few_data") {
    const tip = `Zu wenig Daten (jung: ${cardTrendRatio(item.recent_hits, item.recent_total)}, alt: ${cardTrendRatio(item.older_hits, item.older_total)}; Mindestzahl je Fenster: ${StudioUI.num(trendState.min_decks_per_window, 0)}).`;
    return h("td", { class: "num muted", title: tip }, "zu wenig Daten");
  }
  const dirLabel = item.direction === "rising"
    ? "steigend (95 %-Intervall > 0)"
    : item.direction === "falling"
      ? "fallend (95 %-Intervall < 0)"
      : "Intervall enthält 0";
  const tip = `Jung: ${cardTrendRatio(item.recent_hits, item.recent_total)} (${StudioUI.pct(item.recent_share, 1)}) · `
    + `Alt: ${cardTrendRatio(item.older_hits, item.older_total)} (${StudioUI.pct(item.older_share, 1)}) · `
    + `95 %-Intervall (Newcombe): ${cardTrendInterval(item.ci_low, item.ci_high)} · ${dirLabel} · `
    + `Datenstand ${trendState.data_as_of || "unbekannt"} · Verbreitung ist nicht Stärke`;
  const cls = item.excludes_zero ? "num" : "num muted";
  return h("td", { class: cls, title: tip }, `${cardTrendPp(item.diff)} ${cardTrendInterval(item.ci_low, item.ci_high)}`);
}

async function renderCardTrendBox(slot, card, deps) {
  const { h, loadTrend } = deps;
  slot.replaceChildren(
    h("h3", {}, "Trend im eigenen Korpus (jung vs. alt)"),
    h("p", { class: "muted" }, "Lädt Trenddaten aus dem Deck-Datum des eigenen Korpus …"),
  );

  let data;
  try {
    data = await loadTrend();
  } catch (error) {
    slot.replaceChildren(
      h("h3", {}, "Trend im eigenen Korpus (jung vs. alt)"),
      h("p", { class: "muted" }, "Trenddaten nicht lesbar: " + StudioUI.germanError(error)),
    );
    return;
  }

  const item = data && data.map ? data.map.get(card.card_id) : null;
  const windowSelect = h(
    "select",
    {
      "aria-label": "Fenstergrenze für den Trend",
      onchange: (event) => {
        const days = Number(event.target.value);
        deps.onSettingsChange(days, data.bracket || "");
        renderCardTrendBox(slot, card, deps);
      },
    },
    CARD_TREND_WINDOWS.map((opt) =>
      h("option", { value: String(opt.days), selected: opt.days === data.recent_days }, opt.label)),
  );
  const bracketSelect = h(
    "select",
    {
      "aria-label": "Bracket-Filter für den Trend",
      onchange: (event) => {
        deps.onSettingsChange(data.recent_days, event.target.value);
        renderCardTrendBox(slot, card, deps);
      },
    },
    CARD_TREND_BRACKETS.map((opt) =>
      h("option", { value: opt.value, selected: opt.value === (data.bracket || "") }, opt.label)),
  );

  const controls = h(
    "div",
    { class: "actions" },
    h("label", {}, "Jung-Fenster ", windowSelect),
    h("label", {}, "Korpus ", bracketSelect),
  );

  let diffText;
  let intervalText;
  let statusNote;
  if (!item || item.status === "unknown") {
    diffText = "unbekannt";
    intervalText = "unbekannt";
    statusNote = "Mindestens ein Zeitfenster enthält 0 Decks (unbekannt).";
  } else if (item.status === "too_few_data") {
    diffText = "zu wenig Daten";
    intervalText = "zu wenig Daten";
    statusNote = `Unter der Mindestzahl von ${StudioUI.num(data.min_decks_per_window, 0)} Decks je Fenster.`;
  } else {
    diffText = cardTrendPp(item.diff);
    intervalText = cardTrendInterval(item.ci_low, item.ci_high);
    statusNote = item.direction === "rising"
      ? "95 %-Intervall (Newcombe) liegt vollständig über 0 (steigend)."
      : item.direction === "falling"
        ? "95 %-Intervall (Newcombe) liegt vollständig unter 0 (fallend)."
        : "95 %-Intervall (Newcombe) schließt 0 ein (kein eindeutiger Unterschied).";
  }

  const recentHits = item ? item.recent_hits : 0;
  const recentTotal = item ? item.recent_total : data.recent_total;
  const recentShare = item ? item.recent_share : null;
  const olderHits = item ? item.older_hits : 0;
  const olderTotal = item ? item.older_total : data.older_total;
  const olderShare = item ? item.older_share : null;

  const table = h(
    "div",
    { class: "table-wrap" },
    h(
      "table",
      {},
      h(
        "thead",
        {},
        h(
          "tr",
          {},
          h("th", {}, "Zeitfenster"),
          h("th", { class: "num" }, "mit Karte / Decks"),
          h("th", { class: "num" }, "Anteil"),
        ),
      ),
      h(
        "tbody",
        {},
        h(
          "tr",
          { class: recentTotal > 0 && recentTotal < data.min_decks_per_window ? "low" : "" },
          h("td", {}, data.cutoff_date ? `Jung (ab ${data.cutoff_date})` : "Jung"),
          h("td", { class: "num" }, cardTrendRatio(recentHits, recentTotal)),
          h("td", { class: "num" }, recentShare === null ? "unbekannt" : StudioUI.pct(recentShare, 1)),
        ),
        h(
          "tr",
          { class: olderTotal > 0 && olderTotal < data.min_decks_per_window ? "low" : "" },
          h("td", {}, data.cutoff_date ? `Alt (vor ${data.cutoff_date})` : "Alt"),
          h("td", { class: "num" }, cardTrendRatio(olderHits, olderTotal)),
          h("td", { class: "num" }, olderShare === null ? "unbekannt" : StudioUI.pct(olderShare, 1)),
        ),
        h(
          "tr",
          {},
          h("td", {}, "Differenz (jung − alt) · 95 %-Intervall"),
          h("td", { class: "num" }, diffText),
          h("td", { class: "num" }, intervalText),
        ),
      ),
    ),
  );

  const provenance = h(
    "p",
    { class: "note" },
    `${data.origin_note} Datenstand: ${data.data_as_of || "unbekannt"}`
    + (data.cutoff_date ? ` · Fenstergrenze: ${data.cutoff_date} (${StudioUI.num(data.recent_days, 0)} Tage)` : "")
    + ` · Mindestzahl je Fenster: ${StudioUI.num(data.min_decks_per_window, 0)}. ${statusNote}`,
  );

  const warningList = Array.isArray(data.warnings) && data.warnings.length
    ? h("ul", { class: "note" }, data.warnings.map((w) => h("li", {}, w)))
    : null;

  const limits = Array.isArray(data.limitations) && data.limitations.length
    ? h("ul", { class: "note" }, data.limitations.map((text) => h("li", {}, text)))
    : null;

  slot.replaceChildren(
    ...([
      h("h3", {}, "Trend im eigenen Korpus (jung vs. alt)"),
      controls,
      table,
      provenance,
      warningList,
      limits,
    ].filter(Boolean)),
  );
}
