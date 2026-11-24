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

  // TAM-RICHTWERT-BEGIN (#1637, register entry "Preise für TAM", owner decisions 2026-11-21/22).
  // The only place of the Studio pages where price wording may stand. Prices only for the
  // commander TAM, only with the Zukauf mode on, only for cards not owned. The planning
  // functions are exactly: show, sum, sort and budget filter of the TAM purchase list, each
  // value labelled with its source and date. Nothing here feeds a suggestion, a cut/swap, a
  // rating or a figure; the copied wishlist text stays a plain card list. A missing value is
  // "unbekannt", never 0. Precedence: the Cardmarket price the Owner entered (not older than
  // 14 days) > Cardmarket price guide (lowest "low", no country/condition filter) > Scryfall
  // approximation (Cardmarket trend). The Cardmarket link only opens the Owner's own browser;
  // this page never loads a Cardmarket address itself.
  const TAM_COMMANDER = "Tam, the Possibility";
  const UNKNOWN = "unbekannt";
  const CM_CARD_BASE = "https://www.cardmarket.com/de/Magic/Cards/";
  const CM_SEARCH_BASE = "https://www.cardmarket.com/de/Magic/Products/Search?searchString=";
  // Filter values of the Owner's example link (sellerCountry=7, language=1,3, minCondition=3).
  // The other condition numbers follow Cardmarket's order and are not confirmed: marked
  // "Nummer unbelegt" wherever they are offered.
  const CM_COUNTRIES = { DE: ["7", "Deutschland"], alle: [null, "alle Länder"] };
  const CM_LANGUAGES = { EN: ["1", "Englisch"], DE: ["3", "Deutsch"] };
  const CM_CONDITIONS = { MT: ["1", "Mint"], NM: ["2", "Near Mint"], EX: ["3", "Excellent"], GD: ["4", "Good"], LP: ["5", "Light Played"], PL: ["6", "Played"] };
  const CM_DEFAULT = { country: "DE", languages: ["EN", "DE"], condition: "EX" };

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

  // --- Cardmarket link (opened by the Owner's browser only) ---------------------------------
  // Only filter values of the lists above; anything else falls back to the Owner's default.
  function cmFilters(raw) {
    const value = raw && typeof raw === "object" ? raw : {};
    const country = Object.prototype.hasOwnProperty.call(CM_COUNTRIES, value.country) ? value.country : CM_DEFAULT.country;
    const condition = Object.prototype.hasOwnProperty.call(CM_CONDITIONS, value.condition) ? value.condition : CM_DEFAULT.condition;
    const languages = Array.isArray(value.languages)
      ? Object.keys(CM_LANGUAGES).filter((code) => value.languages.includes(code))
      : [...CM_DEFAULT.languages];
    return { country, languages, condition };
  }

  function cmFilterCode(filters) {
    const f = cmFilters(filters);
    return `${f.country}/${f.condition}/${f.languages.join("+") || "alle"}`;
  }

  function cmFilterText(filters) {
    const f = cmFilters(filters);
    const languages = f.languages.map((code) => CM_LANGUAGES[code][1]).join(", ") || "alle";
    const unconfirmed = f.condition === "EX" ? "" : " (Nummer unbelegt)";
    return `Land: ${CM_COUNTRIES[f.country][1]} · Sprache: ${languages} · Mindestzustand: ${CM_CONDITIONS[f.condition][1]}${unconfirmed}`;
  }

  function cmQuery(filters) {
    const f = cmFilters(filters);
    const parts = [];
    if (CM_COUNTRIES[f.country][0]) parts.push(`sellerCountry=${CM_COUNTRIES[f.country][0]}`);
    if (f.languages.length) parts.push(`language=${f.languages.map((code) => CM_LANGUAGES[code][0]).join(",")}`);
    parts.push(`minCondition=${CM_CONDITIONS[f.condition][0]}`);
    return parts.join("&");
  }

  // Only a name whose address is certain gets the card page ("Rograkh, Son of Rohgahh" ->
  // Rograkh-Son-of-Rohgahh, "Urza's Saga" -> Urzas-Saga): ASCII words joined by a space, ", " or
  // a straight apostrophe. Everything else (//, colon, hyphen, digits, umlauts, Æ, curly quotes)
  // gets the Cardmarket search page instead of a guessed address.
  const CM_SAFE_NAME = /^[A-Za-z]+(?:(?:, | |')[A-Za-z]+)*$/;
  function cmSlug(name) {
    const text = String(name || "");
    return CM_SAFE_NAME.test(text) ? text.replace(/,/g, "").replace(/'/g, "").replace(/ /g, "-") : null;
  }

  function cmLink(name, filters) {
    const slug = cmSlug(name);
    // encoded like the server (Python quote): also ! ' ( ) *
    const query = encodeURIComponent(String(name || "")).replace(/[!'()*]/g, (c) => `%${c.charCodeAt(0).toString(16).toUpperCase()}`);
    if (slug === null) return { url: CM_SEARCH_BASE + query, kind: "suche" };
    return { url: `${CM_CARD_BASE}${slug}?${cmQuery(filters)}`, kind: "karte" };
  }

  // --- rows -----------------------------------------------------------------------------------
  function deDate(iso) {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || ""));
    return match ? `${match[3]}.${match[2]}.${match[1]}` : String(iso || "–");
  }

  function finishText(finish) {
    return finish === "foil" ? "Foil" : finish === "nonfoil" ? "Nicht-Foil" : "Finish unbekannt";
  }

  // The filters an entry was read under, in full: a price read under DE/EX/alle never looks
  // like one read under DE/EX/EN+DE; every condition but EX carries "Nummer unbelegt".
  function cmShortCode(code) {
    const [country, condition, languages] = String(code || "").split("/");
    const where = country === "alle" ? "alle Länder" : country || "?";
    const tongue = languages === "alle" ? "alle Sprachen" : languages || "Sprache ?";
    const unconfirmed = condition === "EX" ? "" : " (Nummer unbelegt)";
    return `${where}/${condition || "?"}/${tongue}${unconfirmed}`;
  }

  // One row per missing card. The value used for sum, sorting and filter (cents/basis): the
  // entered Cardmarket price when it is not stale, else the price guide "ab" value (or its trend
  // when it has no low), else the Scryfall approximation, else none.
  function tamPurchaseRows(missingCards, answer) {
    const byId = new Map(((answer && answer.cards) || []).map((item) => [item.card_id, item]));
    const guideLoaded = Boolean(answer && answer.guide_snapshot);
    // a price guide older than 14 days is shown, marked, and never used for sum/sort/filter
    const guideStale = guideLoaded && answer.guide_snapshot.stale !== false;
    return (missingCards || []).map((card) => {
      const item = byId.get(card.card_id);
      // a card the server did not answer (not in the stored deck list) is "absent", not unknown
      const status = !item ? "absent" : item.status === "owned" ? "owned" : item.status === "value" && validCents(item.eur_cents) !== null ? "value" : "unknown";
      const row = {
        card_id: card.card_id,
        name: String((item && item.name) || card.name || card.card_id),
        missing: Math.max(0, Number(card.missing || 0)),
        status,
        approx: status === "value" ? { cents: item.eur_cents, finish: item.finish || "", printing: item.printing || "" } : null,
        guide: null,
        guideStale,
        entered: null,
        stale: null,
        cents: null,
        basis: null,
      };
      if (status === "owned" || status === "absent") return row;
      const guide = guideLoaded && item.guide ? item.guide : null;
      if (guide && (validCents(guide.low_cents) !== null || validCents(guide.trend_cents) !== null)) {
        row.guide = { low: validCents(guide.low_cents), trend: validCents(guide.trend_cents), finish: guide.low_finish || "", printing: guide.low_printing || "" };
      }
      const entered = item.entered;
      if (entered && validCents(entered.eur_cents) !== null) {
        const value = { cents: entered.eur_cents, date: entered.price_date, code: entered.filter_code, age: entered.age_days };
        if (entered.stale === false) row.entered = value;
        else row.stale = value;
      }
      if (row.entered) { row.cents = row.entered.cents; row.basis = "eingetragen"; }
      else if (row.guide && !guideStale && row.guide.low !== null) { row.cents = row.guide.low; row.basis = "preisfuehrer"; }
      else if (row.guide && !guideStale) { row.cents = row.guide.trend; row.basis = "preisfuehrer-trend"; }
      else if (row.approx) { row.cents = row.approx.cents; row.basis = "naeherung"; }
      return row;
    });
  }

  // Sorting of the purchase list only: by name, or by the value used; rows without a value
  // always come last, by name.
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
  // owned or not in the saved deck) are hidden while the filter is on and counted apart.
  function filterTamBudget(rows, maxCents) {
    const limit = validCents(maxCents);
    if (limit === null) return { rows: [...(rows || [])], hiddenOver: 0, hiddenUnknown: 0, hiddenOwned: 0, hiddenAbsent: 0, active: false };
    let hiddenOver = 0;
    let hiddenUnknown = 0;
    let hiddenOwned = 0;
    let hiddenAbsent = 0;
    const kept = [];
    for (const row of rows || []) {
      if (row.status === "owned") hiddenOwned += 1;
      else if (row.status === "absent") hiddenAbsent += 1;
      else if (row.cents === null) hiddenUnknown += 1;
      else if (row.cents > limit) hiddenOver += 1;
      else kept.push(row);
    }
    return { rows: kept, hiddenOver, hiddenUnknown, hiddenOwned, hiddenAbsent, active: true };
  }

  // Sum of the shown rows (value x missing copies); null when no shown row has a value. Cards
  // already owned (in any printing) or not in the saved deck are counted apart: they carry no
  // value and are no gap.
  function summarizeTamRows(rows) {
    let sum = 0;
    let priced = 0;
    let owned = 0;
    let absent = 0;
    let stale = 0;
    const byBasis = { eingetragen: 0, preisfuehrer: 0, naeherung: 0 };
    for (const row of rows || []) {
      if (row.status === "owned") { owned += 1; continue; }
      if (row.status === "absent") { absent += 1; continue; }
      if (row.stale) stale += 1;
      if (row.cents === null) continue;
      priced += 1;
      byBasis[row.basis === "preisfuehrer-trend" ? "preisfuehrer" : row.basis] += 1;
      sum += row.cents * Math.max(1, row.missing);
    }
    const total = (rows || []).length - owned - absent;
    return { sumCents: priced ? sum : null, priced, without: total - priced, total, owned, absent, stale, entered: byBasis.eingetragen, guide: byBasis.preisfuehrer, approx: byBasis.naeherung };
  }

  function tamSumText(summary) {
    const sum = summary.sumCents === null ? UNKNOWN : formatEur(summary.sumCents);
    const parts = [
      `Summe (eingetragen, sonst Cardmarket-Preisführer, sonst Näherung): ${sum}`,
      `${summary.entered} von ${summary.total} Karten mit eingetragenem Preis`,
      `${summary.guide} Preisführer`,
      `${summary.approx} Näherung`,
      `${summary.without} von ${summary.total} Karten ohne Preis`,
    ];
    if (summary.stale) parts.push(`${summary.stale} veraltete Einträge (älter als 14 Tage) nicht gezählt`);
    if (summary.owned) parts.push(`${summary.owned} im Besitz (kein Preis)`);
    if (summary.absent) parts.push(`${summary.absent} nicht im gespeicherten Deck (kein Preis)`);
    return parts.join(" · ");
  }

  function sourceText(answer) {
    const lines = [];
    const guide = answer && answer.guide_snapshot;
    lines.push(guide
      ? `Cardmarket-Preisführer: Stand ${deDate(guide.guide_date)} (${guide.date_basis}), importiert ${guide.imported_at}${guide.stale !== false ? " – veraltet (älter als 14 Tage), zählt nicht" : ""}; ${guide.printings_matched} von ${guide.printings_known} Drucken zugeordnet, ${guide.name_check === true ? "Namen mit der Produktliste geprüft" : "Namen nicht geprüft (ohne Produktliste)"}${guide.name_mismatches ? `, ${guide.name_mismatches} wegen abweichendem Namen ausgelassen` : ""}. ${answer.guide_notice}`
      : "Kein Cardmarket-Preisführer importiert. Import im Terminal: python -m commander_lab.studio import-cardmarket-priceguide.");
    const snap = answer && answer.snapshot;
    lines.push(snap
      ? `Näherung aus Scryfall (Cardmarket-Preisführer, kein Filter Deutschland/Excellent), Stand ${snap.bulk_date} (${snap.date_basis}), importiert ${snap.imported_at}. ${answer.notice} Regel: ${answer.rule}.`
      : "Kein Scryfall-Schnappschuss importiert: keine Näherung. Import im Terminal: python -m commander_lab.studio import-tam-prices <Scryfall-Bulk-Datei>.");
    lines.push(`${(answer && answer.cardmarket_notice) || ""}`);
    return lines.filter(Boolean);
  }

  function enteredText(value, stale) {
    const base = `Cardmarket ${cmShortCode(value.code)}: ${formatEur(value.cents)} (eingetragen am ${deDate(value.date)})`;
    return stale ? `veraltet: ${base}, älter als 14 Tage, zählt nicht` : base;
  }

  function guideText(guide, answer) {
    const date = answer && answer.guide_snapshot ? deDate(answer.guide_snapshot.guide_date) : "–";
    const print = guide.low !== null ? ` · ${guide.printing || "Druck ?"}, ${finishText(guide.finish)}` : "";
    const low = guide.low !== null ? `Cardmarket ab ${formatEur(guide.low)}` : "Cardmarket ab unbekannt";
    const trend = guide.trend !== null ? ` (Trend ${formatEur(guide.trend)})` : "";
    return `${low}${trend} · ohne Filter Land/Sprache/Zustand · Stand ${date}${print}`;
  }

  function approxText(approx, answer) {
    const date = answer && answer.snapshot ? answer.snapshot.bulk_date : "–";
    return `Näherung aus Scryfall (Cardmarket-Preisführer, kein Filter Deutschland/Excellent), Stand ${date}: ${formatEur(approx.cents)} · ${approx.printing || "Druck ?"}, ${finishText(approx.finish)}`;
  }

  // The lines of the value cell: the value used first, the other known values smaller.
  function cellLines(row, answer) {
    if (row.status === "owned") return { main: "im Besitz (kein Preis)", more: [] };
    if (row.status === "absent") return { main: "nicht im gespeicherten Deck (kein Preis)", more: [] };
    const more = [];
    let main = UNKNOWN;
    if (row.basis === "eingetragen") main = enteredText(row.entered, false);
    else if (row.basis === "preisfuehrer" || row.basis === "preisfuehrer-trend") main = guideText(row.guide, answer);
    else if (row.basis === "naeherung") main = approxText(row.approx, answer);
    if (row.stale) more.push(enteredText(row.stale, true));
    if (row.guide && row.guideStale) more.push(`veraltet: ${guideText(row.guide, answer)}, älter als 14 Tage, zählt nicht`);
    else if (row.guide && row.basis === "eingetragen") more.push(guideText(row.guide, answer));
    if (row.approx && row.basis !== "naeherung") more.push(approxText(row.approx, answer));
    return { main, more };
  }

  function todayIso() {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  }

  function centsInput(cents) {
    const value = validCents(cents);
    return value === null ? "" : `${Math.floor(value / 100)},${String(value % 100).padStart(2, "0")}`;
  }

  // The TAM purchase list view; h is the page's element helper. view.onSave(cardId, price,
  // date, filterCode) stores an entered price and resolves to the new answer; view.onFilters
  // keeps the chosen Cardmarket filters. Re-renders only its result part.
  function tamPurchaseView(h, answer, missingCards, view) {
    const state = view || {};
    state.sort = state.sort || "name";
    state.budget = state.budget || "";
    state.filters = cmFilters(state.filters);
    let current = answer;
    let rows = tamPurchaseRows(missingCards, current);
    const results = h("div", { id: "tam-zukauf-results" });
    const source = h("div", { id: "tam-zukauf-source" });
    const filterLabel = h("p", { class: "note", id: "tam-zukauf-filter-text" });
    const drawSource = () => source.replaceChildren(...sourceText(current).map((line) => h("p", { class: "note" }, line)));
    const save = (row, priceInput, dateInput, message) => {
      if (typeof state.onSave !== "function") return;
      message.replaceChildren("speichert …");
      Promise.resolve(state.onSave(row.card_id, priceInput.value, dateInput.value, cmFilterCode(state.filters)))
        .then((next) => { current = next; rows = tamPurchaseRows(missingCards, current); drawSource(); draw(); })
        .catch((error) => { message.replaceChildren(`nicht gespeichert: ${typeof StudioUI !== "undefined" ? StudioUI.germanError(error) : String(error)}`); });
    };
    const editCell = (row) => {
      if (row.status === "owned" || row.status === "absent") return h("td", {}, "–");
      const known = row.entered || row.stale;
      const priceInput = h("input", { type: "text", inputmode: "decimal", class: "tam-cm-price", value: known ? centsInput(known.cents) : "", placeholder: "z. B. 12,50", "aria-label": `Cardmarket-Preis in Euro für ${row.name} (leer oder 0: unbekannt)` });
      const dateInput = h("input", { type: "date", class: "tam-cm-date", value: todayIso(), "aria-label": `Datum des abgelesenen Preises für ${row.name}` });
      const message = h("span", { class: "note tam-cm-message" });
      return h("td", {}, priceInput, " ", dateInput, " ",
        h("button", { type: "button", class: "small tam-cm-save", onclick: () => save(row, priceInput, dateInput, message) }, "Speichern"), " ", message);
    };
    const linkCell = (row) => {
      if (row.status === "owned" || row.status === "absent") return h("td", {}, "–");
      const link = cmLink(row.name, state.filters);
      return h("td", {}, h("a", { href: link.url, target: "_blank", rel: "noopener noreferrer", referrerpolicy: "no-referrer", class: "tam-cm-link", dataset: { kind: link.kind } },
        link.kind === "karte" ? "Cardmarket ↗" : "Cardmarket-Suche ↗ (Filter dort wählen)"));
    };
    const draw = () => {
      filterLabel.replaceChildren(cmFilterText(state.filters));
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
          ? h("p", { class: "note", id: "tam-zukauf-absent" }, `${absent} Karten stehen nicht in der gespeicherten Deckliste und haben keinen Preis; erst speichern.`)
          : "",
        filtered.active
          ? h("p", { class: "note", id: "tam-zukauf-hidden" }, `Budgetfilter: ${filtered.hiddenOver} Karten über dem Höchstwert, ${filtered.hiddenUnknown} Karten ohne Preis${filtered.hiddenAbsent ? `, ${filtered.hiddenAbsent} nicht im gespeicherten Deck` : ""} und ${filtered.hiddenOwned} im Besitz ausgeblendet.`)
          : "",
        h("div", { class: "table-wrap" },
          h("table", { id: "tam-zukauf-table" },
            h("thead", {}, h("tr", {}, h("th", {}, "Karte"), h("th", { class: "num" }, "fehlend"), h("th", {}, "Preis je Karte (Quelle, Stand)"), h("th", {}, "Cardmarket-Preis eintragen"), h("th", {}, "Link"))),
            h("tbody", {}, shown.map((row) => {
              const lines = cellLines(row, current);
              return h("tr", { dataset: { status: row.status, basis: row.basis || "", cardId: row.card_id } },
                h("td", {}, row.name),
                h("td", { class: "num" }, String(row.missing)),
                h("td", { class: "tam-cm-value" }, h("span", { class: "tam-cm-main" }, lines.main),
                  ...lines.more.map((line) => h("small", { class: line.startsWith("veraltet") ? "tam-cm-stale" : "tam-cm-more" }, line))),
                editCell(row),
                linkCell(row));
            })))));
    };
    const keep = () => { if (typeof state.onFilters === "function") state.onFilters(state.filters); draw(); };
    const countrySelect = h("select", { id: "tam-cm-country", "aria-label": "Cardmarket-Filter Land", onchange: (event) => { state.filters = cmFilters({ ...state.filters, country: event.target.value }); keep(); } },
      ...Object.entries(CM_COUNTRIES).map(([code, [, label]]) => h("option", { value: code, selected: state.filters.country === code }, label)));
    const conditionSelect = h("select", { id: "tam-cm-condition", "aria-label": "Cardmarket-Filter Mindestzustand", onchange: (event) => { state.filters = cmFilters({ ...state.filters, condition: event.target.value }); keep(); } },
      ...Object.entries(CM_CONDITIONS).map(([code, [, label]]) => h("option", { value: code, selected: state.filters.condition === code }, code === "EX" ? label : `${label} (Nummer unbelegt)`)));
    const languageBoxes = Object.entries(CM_LANGUAGES).map(([code, [, label]]) => h("label", {},
      h("input", { type: "checkbox", class: "tam-cm-language", value: code, checked: state.filters.languages.includes(code), onchange: (event) => {
        const chosen = new Set(state.filters.languages);
        if (event.target.checked) chosen.add(code); else chosen.delete(code);
        state.filters = cmFilters({ ...state.filters, languages: [...chosen] });
        keep();
      } }), ` ${label}`));
    const sortSelect = h("select", { id: "tam-zukauf-sort", "aria-label": "Sortierung der Zukauf-Liste", onchange: (event) => { state.sort = event.target.value; draw(); } },
      h("option", { value: "name", selected: state.sort === "name" }, "Name"),
      h("option", { value: "price-asc", selected: state.sort === "price-asc" }, "Preis aufsteigend"),
      h("option", { value: "price-desc", selected: state.sort === "price-desc" }, "Preis absteigend"));
    const budgetInput = h("input", { type: "text", id: "tam-zukauf-budget", inputmode: "decimal", value: state.budget, placeholder: "z. B. 10", "aria-label": "Budget je Karte in Euro (Höchstwert)", oninput: (event) => { state.budget = event.target.value; draw(); } });
    drawSource();
    draw();
    return h("div", { id: "tam-zukauf" },
      h("h2", {}, `Zukauf-Liste TAM mit Preisen (${rows.length} Karten)`),
      source,
      h("div", { class: "actions", id: "tam-cm-filters" },
        h("label", {}, "Cardmarket-Filter Land ", countrySelect),
        h("span", {}, "Sprache ", ...languageBoxes),
        h("label", {}, "Mindestzustand ", conditionSelect)),
      filterLabel,
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
    cmFilters,
    cmFilterCode,
    cmFilterText,
    cmShortCode,
    cmSlug,
    cmLink,
  };
})();
if (typeof module !== "undefined") module.exports = StudioWishlist;
