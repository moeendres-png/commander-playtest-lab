"use strict";
// Rule-derived Game-Changer-Band UI helper (Refs #1552).
// Strictly separate from declared brackets: never mixed in counts or selection.

(function () {
  const BAND_SHORT = {
    "gc_band:0": "0 GC",
    "gc_band:1-3": "1–3 GC",
    "gc_band:4+": "4+ GC",
  };
  const BAND_ORDER = ["gc_band:0", "gc_band:1-3", "gc_band:4+"];

  function bracketOriginText(data) {
    if (!data || !data.declared_bracket_origins) return "";
    const entries = Object.values(data.declared_bracket_origins);
    if (!entries.length) return "";
    const parts = entries.map((item) => {
      const withB = StudioUI.num(item.decks_with_bracket ?? 0, 0);
      const total = StudioUI.num(item.decks_total ?? 0, 0);
      return `${item.origin}: ${withB}/${total} mit Bracket`;
    });
    return `Herkunft erklärter Brackets: ${parts.join(" · ")}`;
  }

  function infoText(universeInfo) {
    if (!universeInfo || !universeInfo.gc_band) return "";
    const meta = universeInfo.gc_band_meta || {};
    const label = BAND_SHORT[universeInfo.gc_band] || universeInfo.gc_band;
    const denom = StudioUI.num(universeInfo.denominator ?? 0, 0);
    const prov = meta.provenance || "regelabgeleitet aus Deckliste und Game-Changer-Liste vom unbekannt";
    const disc = meta.disclaimer || "Das Band ist kein Bracket: die offizielle Bracket-Regel kennt weitere Kriterien, die hier nicht geprüft werden.";
    return `Game-Changer-Band (regelabgeleitet, kein Bracket): ${label} · ${denom} Decks (Nenner) · ${prov} · ${disc}`;
  }

  function renderBar(host, data, activeBand, disabled, onSelect) {
    if (!host) return;
    if (!data || !data.rows) {
      host.replaceChildren();
      return;
    }
    const h = StudioUI.h;
    const listDate = data.list_date || "unbekannt";
    const prov = data.provenance || `regelabgeleitet aus Deckliste und Game-Changer-Liste vom ${listDate}`;
    const disc = data.disclaimer || "Das Band ist kein Bracket: die offizielle Bracket-Regel kennt weitere Kriterien, die hier nicht geprüft werden.";
    const nodes = [
      h("span", { class: "muted", title: `${prov}. ${disc}` }, "Game-Changer-Band (regelabgeleitet, kein Bracket):"),
    ];
    for (const key of BAND_ORDER) {
      const row = data.rows[key];
      const count = row ? (row.total ?? 0) : 0;
      const total = data.total_decks ?? 0;
      const active = !disabled && activeBand === key;
      const label = BAND_SHORT[key] || key;
      nodes.push(
        h(
          "button",
          {
            type: "button",
            class: "chip" + (active ? " on" : ""),
            "aria-pressed": active,
            disabled: disabled || count === 0,
            title: `${row ? row.label : label}: ${StudioUI.num(count, 0)}/${StudioUI.num(total, 0)} Decks (${prov}). ${disc}`,
            onclick: () => onSelect(active ? "" : key),
          },
          `${label} (${StudioUI.num(count, 0)})`
        )
      );
    }
    nodes.push(
      h("span", { class: "muted", title: `${prov}. ${disc}` }, `Liste: ${listDate}`)
    );
    host.replaceChildren(...nodes);
  }

  window.StudioGcBand = {
    BAND_SHORT,
    BAND_ORDER,
    bracketOriginText,
    infoText,
    renderBar,
  };
})();
