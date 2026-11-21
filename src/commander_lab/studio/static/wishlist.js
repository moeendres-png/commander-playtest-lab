"use strict";
// Wishlist (Zukauf) helpers and literal Oracle/Superfriends filters (Refs #1636, Refs #1187).
// Pure functions: objective collection counts and literal Oracle-text / type-line matching only.

const StudioWishlist = (() => {
  function lookupCard(poolMap, cardId) {
    if (!poolMap || !cardId) return null;
    if (typeof poolMap.get === "function") return poolMap.get(cardId) || null;
    return poolMap[cardId] || null;
  }

  function isUnowned(card) {
    if (!card) return true;
    return card.in_collection === false || Number(card.owned || 0) < 1;
  }

  function summarizeDeckOwnership(deckEntries, poolMap) {
    const byId = new Map();
    for (const entry of deckEntries || []) {
      if (!entry || !entry.card_id) continue;
      const quantity = Math.max(0, Number(entry.quantity || 0));
      if (!quantity) continue;
      const prev = byId.get(entry.card_id);
      if (prev) {
        prev.quantity += quantity;
      } else {
        byId.set(entry.card_id, {
          card_id: entry.card_id,
          quantity,
          name: entry.name || "",
        });
      }
    }
    let total = 0;
    let owned = 0;
    let missing = 0;
    const missingCards = [];
    for (const item of byId.values()) {
      const card = lookupCard(poolMap, item.card_id);
      const ownedCount =
        card && card.in_collection !== false ? Math.max(0, Number(card.owned || 0)) : 0;
      const have = Math.min(item.quantity, ownedCount);
      const need = Math.max(0, item.quantity - ownedCount);
      total += item.quantity;
      owned += have;
      missing += need;
      if (need > 0) {
        missingCards.push({
          card_id: item.card_id,
          name: (card && (card.name || card.oracle_name)) || item.name || item.card_id,
          quantity: item.quantity,
          owned: ownedCount,
          missing: need,
        });
      }
    }
    missingCards.sort((a, b) => a.name.localeCompare(b.name));
    return { total, owned, missing, missingCards };
  }

  function formatWishlistText(missingCards) {
    if (!Array.isArray(missingCards) || !missingCards.length) return "";
    const sorted = [...missingCards].sort((a, b) =>
      String(a.name || "").localeCompare(String(b.name || ""))
    );
    return sorted
      .filter((item) => Number(item.missing !== undefined ? item.missing : item.quantity || 0) > 0)
      .map((item) => {
        const count = Number(item.missing !== undefined ? item.missing : item.quantity || 1);
        return `${count} ${item.name}`;
      })
      .join("\n");
  }

  function oracleOf(card) {
    return String(card.oracle_text !== undefined ? card.oracle_text : card.text || "");
  }

  // The verb "counter" (counter target spell ...) is no counter on a permanent: it is taken
  // out of the text before the word is looked for (#1648).
  const COUNTER_VERB = /\bcounter (?:target|that|it\b|them\b|this|those|up to|another|all\b|each\b|a |an |the )/gi;

  function mentionsCounterOrLoyalty(card) {
    const rest = oracleOf(card).replace(COUNTER_VERB, " ");
    return /\bcounters?\b|\bloyalty\b/i.test(rest);
  }

  // A card that makes mana of all five colors, read from the public "produced mana" letters.
  function producesAllFiveColors(card) {
    const letters = String(card.produced_mana || "").toUpperCase();
    return ["W", "U", "B", "R", "G"].every((letter) => letters.includes(letter));
  }

  // The Scryfall tagger role "board_wipe": a public community label, not complete. A card
  // without role data is unknown, not "no board wipe"; it simply does not match here.
  function hasBoardWipeRole(card) {
    return Array.isArray(card.roles) && card.roles.includes("board_wipe");
  }

  function matchesSuperfriendsFilter(card, kind) {
    if (!card || !kind) return true;
    if (kind === "planeswalker") {
      return /planeswalker/i.test(String(card.type_line || ""));
    }
    if (kind === "proliferate") {
      return /proliferate/i.test(oracleOf(card));
    }
    if (kind === "counters") return mentionsCounterOrLoyalty(card);
    if (kind === "boardwipe") return hasBoardWipeRole(card);
    if (kind === "fixing5c") return producesAllFiveColors(card);
    if (kind === "missing") {
      return isUnowned(card);
    }
    return true;
  }

  // TAM-RICHTWERT-BEGIN (#1637, register entry "Preise für TAM", owner decision 2026-11-21).
  // The only place of the Studio pages where price wording may stand. Guide values (Richtwerte)
  // only for the commander TAM, only with the Zukauf mode on, only for cards not owned. The
  // planning functions are exactly: show, sum, sort and budget filter of the TAM purchase list,
  // marked as a guide value. Nothing here feeds a suggestion, a cut/swap, a rating or a figure;
  // the copied wishlist text stays a plain card list. A missing value is "unbekannt", never 0.
  const TAM_COMMANDER = "Tam, the Possibility";
  const UNKNOWN = "unbekannt";

  function tamPricesAllowed(commander, includeUnowned) {
    return commander === TAM_COMMANDER && includeUnowned === true;
  }

  function validCents(value) {
    return Number.isInteger(value) && value > 0 ? value : null;
  }

  // Integer cents as German euro text ("1.234,56 €"); anything else is "unbekannt".
  function formatEur(cents) {
    const value = validCents(cents);
    if (value === null) return UNKNOWN;
    const euros = String(Math.floor(value / 100)).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return `${euros},${String(value % 100).padStart(2, "0")} €`;
  }

  // German or plain input -> cents: "12", "12,5", "12.50", "1.000" (thousands), "1.234,56",
  // "10 €"; empty, zero or unreadable -> null (no filter; the view says when it could not read).
  function parseBudget(text) {
    let clean = String(text === undefined || text === null ? "" : text).trim().replace(/\s*€$/, "").replace(/\s/g, "");
    if (/^\d{1,3}(\.\d{3})+(,\d{1,2})?$/.test(clean)) clean = clean.replace(/\./g, "");
    clean = clean.replace(",", ".");
    if (!/^\d{1,7}(\.\d{1,2})?$/.test(clean)) return null;
    const [whole, part = ""] = clean.split(".");
    const cents = Number(whole) * 100 + Number((part + "00").slice(0, 2));
    return cents > 0 ? cents : null;
  }

  // One row per missing card; a value only where the server answered status "value".
  function tamPurchaseRows(missingCards, answer) {
    const byId = new Map(((answer && answer.cards) || []).map((item) => [item.card_id, item]));
    return (missingCards || []).map((card) => {
      const item = byId.get(card.card_id);
      // a card the server did not answer (not in the stored deck list) is "absent", not unknown
      const status = !item ? "absent" : item.status === "owned" ? "owned" : item.status === "value" && validCents(item.eur_cents) !== null ? "value" : "unknown";
      return {
        card_id: card.card_id,
        name: String(card.name || card.card_id),
        missing: Math.max(0, Number(card.missing || 0)),
        status,
        cents: status === "value" ? item.eur_cents : null,
      };
    });
  }

  // Sorting of the purchase list only: by name, or by guide value; rows without a value always
  // come last, by name.
  function sortTamRows(rows, key) {
    const byName = (a, b) => a.name.localeCompare(b.name);
    const list = [...(rows || [])];
    if (key !== "price-asc" && key !== "price-desc") return list.sort(byName);
    const sign = key === "price-asc" ? 1 : -1;
    return list.sort((a, b) => {
      if (a.cents === null || b.cents === null) return (a.cents === null) - (b.cents === null) || byName(a, b);
      return sign * (a.cents - b.cents) || byName(a, b);
    });
  }

  // Budget filter: a per-card upper limit, nothing cumulative. Rows without a value (unknown,
  // or owned) are hidden while the filter is on and counted apart.
  function filterTamBudget(rows, maxCents) {
    const limit = validCents(maxCents);
    if (limit === null) return { rows: [...(rows || [])], hiddenOver: 0, hiddenUnknown: 0, hiddenOwned: 0, active: false };
    let hiddenOver = 0;
    let hiddenUnknown = 0;
    let hiddenOwned = 0;
    const kept = [];
    for (const row of rows || []) {
      if (row.status === "owned") hiddenOwned += 1;
      else if (row.cents === null) hiddenUnknown += 1;
      else if (row.cents > limit) hiddenOver += 1;
      else kept.push(row);
    }
    return { rows: kept, hiddenOver, hiddenUnknown, hiddenOwned, active: true };
  }

  // Sum of the shown rows (value x missing copies); null when no shown row has a value. Cards
  // already owned (in any printing) are counted apart: they carry no value and are no gap.
  function summarizeTamRows(rows) {
    let sum = 0;
    let priced = 0;
    let owned = 0;
    for (const row of rows || []) {
      if (row.status === "owned") { owned += 1; continue; }
      if (row.cents === null) continue;
      priced += 1;
      sum += row.cents * Math.max(1, row.missing);
    }
    const total = (rows || []).length - owned;
    return { sumCents: priced ? sum : null, priced, without: total - priced, total, owned };
  }

  function tamSumText(summary) {
    const sum = summary.sumCents === null ? UNKNOWN : formatEur(summary.sumCents);
    const owned = summary.owned ? ` · ${summary.owned} im Besitz (kein Preis)` : "";
    return `Summe (Richtwert): ${sum} · ${summary.without} von ${summary.total} Karten ohne Preis${owned}`;
  }

  function sourceText(answer) {
    const snap = answer && answer.snapshot;
    if (!snap) {
      return "Kein Preis-Schnappschuss importiert: alle Preise unbekannt. Import im Terminal: python -m commander_lab.studio import-tam-prices <Scryfall-Bulk-Datei>.";
    }
    return `Quelle: ${answer.source}, Bulk-Datum ${snap.bulk_date} (${snap.date_basis}), importiert ${snap.imported_at}. ${answer.kind}: ${answer.notice} Regel: ${answer.rule}.`;
  }

  function cellText(row) {
    if (row.status === "owned") return "im Besitz (kein Preis)";
    if (row.status === "absent") return "nicht im gespeicherten Deck (kein Preis)";
    return formatEur(row.cents);
  }

  // The TAM purchase list view; h is the page's element helper. Re-renders only its result part.
  function tamPurchaseView(h, answer, missingCards, view) {
    const state = view || { sort: "name", budget: "" };
    const rows = tamPurchaseRows(missingCards, answer);
    const snap = answer && answer.snapshot;
    const results = h("div", { id: "tam-zukauf-results" });
    const draw = () => {
      const budgetText = String(state.budget || "").trim();
      const limit = parseBudget(budgetText);
      const filtered = filterTamBudget(rows, limit);
      const absent = rows.filter((row) => row.status === "absent").length;
      const unreadable = budgetText !== "" && !(limit > 0);
      const shown = sortTamRows(filtered.rows, state.sort);
      const summary = summarizeTamRows(shown);
      results.replaceChildren(
        h("p", { id: "tam-zukauf-sum" }, h("b", {}, tamSumText(summary))),
        unreadable
          ? h("p", { class: "note", id: "tam-zukauf-budget-invalid" }, `Budget „${budgetText}“ nicht lesbar (Beispiele: 10, 12,50, 1.000): Filter aus.`)
          : "",
        absent
          ? h("p", { class: "note", id: "tam-zukauf-absent" }, `${absent} Karten stehen nicht in der gespeicherten Deckliste und haben keinen Richtwert; erst speichern.`)
          : "",
        filtered.active
          ? h("p", { class: "note", id: "tam-zukauf-hidden" }, `Budgetfilter: ${filtered.hiddenOver} Karten über dem Höchstwert, ${filtered.hiddenUnknown} Karten ohne Preis und ${filtered.hiddenOwned} im Besitz ausgeblendet.`)
          : "",
        h("div", { class: "table-wrap" },
          h("table", { id: "tam-zukauf-table" },
            h("thead", {}, h("tr", {}, h("th", {}, "Karte"), h("th", { class: "num" }, "fehlend"), h("th", { class: "num" }, "Richtwert je Karte"), h("th", {}, "Stand (Bulk-Datum)"))),
            h("tbody", {}, shown.map((row) => h("tr", { dataset: { status: row.status } },
              h("td", {}, row.name),
              h("td", { class: "num" }, String(row.missing)),
              h("td", { class: "num", title: row.status === "value" ? `${answer.source} · ${answer.kind}` : "" }, cellText(row)),
              h("td", {}, row.status === "value" && snap ? snap.bulk_date : "–")))))));
    };
    const sortSelect = h("select", { id: "tam-zukauf-sort", "aria-label": "Sortierung der Zukauf-Liste", onchange: (event) => { state.sort = event.target.value; draw(); } },
      h("option", { value: "name", selected: state.sort === "name" }, "Name"),
      h("option", { value: "price-asc", selected: state.sort === "price-asc" }, "Preis aufsteigend"),
      h("option", { value: "price-desc", selected: state.sort === "price-desc" }, "Preis absteigend"));
    const budgetInput = h("input", { type: "text", id: "tam-zukauf-budget", inputmode: "decimal", value: state.budget, placeholder: "z. B. 10", "aria-label": "Budget je Karte in Euro (Höchstwert)", oninput: (event) => { state.budget = event.target.value; draw(); } });
    draw();
    return h("div", { id: "tam-zukauf" },
      h("h2", {}, `Zukauf-Liste TAM mit Richtwerten (${rows.length} Karten)`),
      h("p", { class: "note", id: "tam-zukauf-source" }, sourceText(answer)),
      h("div", { class: "actions" },
        h("label", {}, "Sortierung ", sortSelect),
        h("label", {}, "Budget je Karte (€, Höchstwert) ", budgetInput)),
      results);
  }
  // TAM-RICHTWERT-END

  return {
    isUnowned,
    summarizeDeckOwnership,
    formatWishlistText,
    matchesSuperfriendsFilter,
    tamPricesAllowed,
    formatEur,
    parseBudget,
    tamPurchaseRows,
    sortTamRows,
    filterTamBudget,
    summarizeTamRows,
    tamSumText,
    tamPurchaseView,
  };
})();
if (typeof module !== "undefined") module.exports = StudioWishlist;
