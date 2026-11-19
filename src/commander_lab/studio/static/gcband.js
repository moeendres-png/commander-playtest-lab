"use strict";
// Rule-derived Game-Changer-Band (Refs #1552) and the one place that says which deck cohort the
// builder's numbers come from. A Game-Changer-Band is not a bracket: it is never mixed with a
// declared bracket cohort, neither in a count nor in a selection nor in a label.
//
// The active scope decides where a card's count comes from:
//   universe profile  card.universe (counted spread of that profile)
//   Game-Changer-Band card.universe (counted spread of the band's decks)
//   neither           the legacy cohort figures (state.cohort), handled by the page
// Choosing a band resets the declared cohort to "all" and clears the deck filter; choosing a
// declared cohort or a universe profile clears the band. A deck whose band cannot be
// determined (no marking, unknown marking or unresolved cards) is "unbekannt", never 0.
// The pure functions below take plain objects and are tested with node; only renderBar and the
// two text helpers touch the page's StudioUI.

const StudioGcBand = (() => {
  const BAND_SHORT = {
    "gc_band:0": "0 GC",
    "gc_band:1-3": "1–3 GC",
    "gc_band:4+": "4+ GC",
  };
  const BAND_ORDER = ["gc_band:0", "gc_band:1-3", "gc_band:4+"];
  const UNKNOWN = "gc_band:unknown";
  const DISCLAIMER = "Das Band ist kein Bracket: die offizielle Bracket-Regel kennt weitere Kriterien, die hier nicht geprüft werden.";
  const PROVENANCE_FALLBACK = "regelabgeleitet aus Deckliste und Game-Changer-Liste; Datum der Markierung unbekannt";

  const fmt = (value) => (typeof StudioUI !== "undefined" ? StudioUI.num(value ?? 0, 0) : String(value ?? 0));
  const bandLabel = (key) => `Game-Changer-Band ${BAND_SHORT[key] || key} (regelabgeleitet, kein Bracket)`;

  // The scope whose counted spread the pool shows, or null for the legacy cohort figures.
  function activeScope(view) {
    const v = view || {};
    if (v.universe) return { kind: "universe", key: v.universe, param: "profile", label: `Universum ${v.universe}` };
    if (v.gcBand) return { kind: "gc_band", key: v.gcBand, param: "gc_band", label: bandLabel(v.gcBand) };
    return null;
  }

  // The query part of /api/pool for the active scope.
  function scopeQuery(view) {
    const scope = activeScope(view);
    return scope ? `&${scope.param}=${encodeURIComponent(scope.key)}` : "";
  }

  // The next view after a choice. kind: "gc_band" | "cohort" | "universe" | "subset".
  // Returns { universe, gcBand, cohort, clearSubset }: the other side is reset explicitly.
  function select(view, kind, value) {
    const v = view || {};
    const next = { universe: v.universe || "", gcBand: v.gcBand || "", cohort: v.cohort || "all", clearSubset: false };
    if (kind === "gc_band") {
      next.gcBand = value || "";
      if (next.gcBand) { next.universe = ""; next.cohort = "all"; next.clearSubset = true; }
    } else if (kind === "cohort") {
      next.cohort = value || "all";
      next.gcBand = "";
    } else if (kind === "universe") {
      next.universe = value || "";
      if (next.universe) next.gcBand = "";
    } else if (kind === "subset") {
      if (value && value.length) next.gcBand = "";
    }
    return next;
  }

  // A card's count in the active scope: { hits, total, share, filter }, or null when the page
  // should fall back to its cohort figures (no scope; a universe profile without a row keeps
  // the earlier behaviour). Inside a band a card without a row is unknown, never 0.
  function scopedFreq(card, scope, denominator) {
    if (!scope) return null;
    const u = card && card.universe;
    if (u) return { hits: u.matched && !u.filter_card ? u.hits : null, total: u.denominator, share: u.share, filter: Boolean(u.filter_card) };
    if (scope.kind === "gc_band") return { hits: null, total: denominator || 0, share: null, filter: false };
    return null;
  }

  // Chip rows: the three bands plus the "unbekannt" row (shown, never selectable).
  function bandRows(data) {
    if (!data || !data.rows) return [];
    const rows = BAND_ORDER.map((key) => {
      const row = data.rows[key] || {};
      return { key, short: BAND_SHORT[key], count: row.total ?? 0, selectable: true, unresolved: row.unresolved_cards ?? 0 };
    });
    const unknown = data.rows[UNKNOWN];
    if (unknown) rows.push({ key: UNKNOWN, short: "unbekannt", count: unknown.total ?? 0, selectable: false, unresolved: unknown.unresolved_cards ?? 0, decksWithUnresolved: unknown.decks_with_unresolved ?? 0 });
    return rows;
  }

  function bracketOriginText(data) {
    if (!data || !data.declared_bracket_origins) return "";
    const entries = Object.values(data.declared_bracket_origins);
    if (!entries.length) return "";
    const parts = entries.map((item) => `${item.origin}: ${fmt(item.decks_with_bracket)}/${fmt(item.decks_total)} mit Bracket`);
    return `Herkunft erklärter Brackets: ${parts.join(" · ")}`;
  }

  function infoText(universeInfo) {
    if (!universeInfo || !universeInfo.gc_band) return "";
    const meta = universeInfo.gc_band_meta || {};
    const parts = [`${bandLabel(universeInfo.gc_band)}: ${fmt(universeInfo.denominator)} Decks (Nenner)`];
    if (universeInfo.empty_reason) parts.push(universeInfo.empty_reason);
    parts.push(meta.provenance || PROVENANCE_FALLBACK, meta.disclaimer || DISCLAIMER);
    return parts.join(" · ");
  }

  function renderBar(host, data, activeBand, disabled, onSelect) {
    if (!host) return;
    if (!data || !data.rows) { host.replaceChildren(); return; }
    const h = StudioUI.h;
    const prov = data.provenance || PROVENANCE_FALLBACK;
    const disc = data.disclaimer || DISCLAIMER;
    const total = data.total_decks ?? 0;
    const nodes = [h("span", { class: "muted", title: `${prov}. ${disc}` }, "Game-Changer-Band (regelabgeleitet, kein Bracket):")];
    for (const row of bandRows(data)) {
      if (!row.selectable) {
        nodes.push(h("span", {
          class: "chip chip-static",
          title: `Band unbekannt: ${fmt(row.count)}/${fmt(total)} Decks (Markierung fehlt oder ist unbekannt, oder Karten sind unaufgelöst: ${fmt(row.decksWithUnresolved)} Decks mit ${fmt(row.unresolved)} unaufgelösten Karten). Nie als 0 gezählt.`,
        }, `unbekannt (${fmt(row.count)})`));
        continue;
      }
      const active = !disabled && activeBand === row.key;
      nodes.push(h("button", {
        type: "button",
        class: "chip" + (active ? " on" : ""),
        "aria-pressed": active,
        disabled: disabled || row.count === 0,
        title: `${bandLabel(row.key)}: ${fmt(row.count)}/${fmt(total)} Decks (${prov}). ${disc}`,
        onclick: () => onSelect(active ? "" : row.key),
      }, `${row.short} (${fmt(row.count)})`));
    }
    nodes.push(h("span", { class: "muted", title: `${prov}. ${disc}` }, data.list_date ? `Markierung vom ${data.list_date}` : (data.list_imported_at ? `Datum der Markierung unbekannt (Import ${data.list_imported_at})` : "Datum der Markierung unbekannt")));
    host.replaceChildren(...nodes);
  }

  return { BAND_SHORT, BAND_ORDER, UNKNOWN, activeScope, scopeQuery, select, scopedFreq, bandRows, bracketOriginText, infoText, renderBar };
})();
if (typeof module !== "undefined") module.exports = StudioGcBand;
