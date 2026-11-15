"use strict";
// Tausch-Helfer of the deck builder. Two questions, answered from counts of the chosen
// comparison group (POST /api/swap):
//   - a card in the deck: "Was ersetzt diese Karte?"  (same role, most played first)
//   - a pool card:        "Was nehme ich dafür raus?" (deck cards with the same role, rarest first)
// Every frequency reads "n von N Decks"; groups under 30 decks are flagged; an unknown count is
// shown as "unbekannt", listed last and never read as zero. Marks, labels and favourites do not
// change the list. Text from data is set as text through StudioUI.el, never as HTML.
//
// app.js hands in what it owns (the deck, the chosen group, add and remove) as `host`:
//   { commander, deckIds(), cohort(), universe(), inDeck(card), byId(id), maxCopies(card),
//     add(card), remove(card), open(card, mode), roleName(role), groupName(group), typeName(type), small() }

const StudioSwap = (() => {
  const h = StudioUI.el;
  const FIRST = 15; // rows shown before "mehr zeigen"
  const REQUEST_LIMIT = 100;
  const UNKNOWN_REASONS = {
    not_in_decks: "Kein Deck der Gruppe nennt diese Karte unter einem bekannten Namen. Das ist nicht dasselbe wie selten gespielt.",
    filter_card: "Filterkarte des Universums: sie steht per Definition in jedem Deck, es wird nicht gezählt.",
    no_source_decks: "In dieser Gruppe liegen keine Quelldecks vor.",
  };
  // Only a view setting: the switch stays as the person left it until the page is reloaded.
  let includeUnowned = false;

  const questionOf = (inDeck) => (inDeck ? "Was ersetzt diese Karte?" : "Was nehme ich dafür raus?");
  const percent = (share) => `${(100 * share).toFixed(1)} %`;

  function freqCells(item) {
    if (item.decks === null || item.decks === undefined) {
      return [
        h("td", { class: "num", title: UNKNOWN_REASONS[item.unknown_reason] || "unbekannt" }, "unbekannt"),
        h("td", { class: "num" }, "unbekannt"),
      ];
    }
    return [
      h("td", { class: "num", title: `wird in ${item.decks} von ${item.of} Decks gespielt` }, `${item.decks} von ${item.of}`),
      h("td", { class: "num" }, item.share === null ? "unbekannt" : percent(item.share)),
    ];
  }

  function mvText(item) {
    const delta = item.mv_delta;
    if (!delta) return `${item.mana_value}`;
    return `${item.mana_value} (${delta > 0 ? "+" : "−"}${Math.abs(delta)})`;
  }

  function mount(into, card, host, initialMode = null) {
    const inDeck = host.inDeck(card);
    const mode = inDeck ? "replace" : "cut";
    const body = h("div", { id: "swap-helper-body" });
    let open = Boolean(initialMode);
    let shown = FIRST;
    let token = 0;

    const toggle = h("button", {
      type: "button", id: "swap-helper-ask", class: "chip" + (open ? " on" : ""), "aria-pressed": String(open),
      onclick: () => { open = !open; shown = FIRST; render(); },
    }, questionOf(inDeck));

    async function load() {
      const mine = ++token;
      body.replaceChildren(h("p", { class: "muted" }, "Lädt …"));
      try {
        const res = await StudioUI.request("/api/swap", "POST", {
          commander: host.commander,
          deck_card_ids: host.deckIds(),
          card_id: card.card_id,
          mode,
          cohort: host.cohort(),
          universe: host.universe() || null,
          include_unowned: mode === "replace" && includeUnowned,
          limit: REQUEST_LIMIT,
        });
        if (mine !== token) return;
        body.replaceChildren(...result(res));
      } catch (error) {
        if (mine !== token) return;
        body.replaceChildren(h("p", { class: "muted", id: "swap-helper-error" }, `Tausch-Helfer nicht lesbar: ${StudioUI.germanError(error)}`));
      }
    }

    function rowFor(item) {
      const other = item.card_id ? host.byId(item.card_id) : null;
      let action = null;
      if (other && mode === "replace" && inDeck && host.maxCopies(other) > 0) {
        action = h("button", { type: "button", class: "small", onclick: () => { host.remove(card); host.add(other); host.open(other, "replace"); } }, "Tauschen");
      } else if (other && mode === "cut" && host.maxCopies(card) > 0) {
        action = h("button", { type: "button", class: "small", onclick: () => { host.remove(other); host.add(card); host.open(card, "replace"); } }, "Gegen diese tauschen");
      }
      const notes = [];
      if (!item.in_collection) notes.push("nicht in der Sammlung");
      else if (mode === "replace" && item.available < 1) notes.push("keine freie Kopie");
      if (item.favorite) notes.push("★ Favorit");
      if (item.excluded) notes.push("von dir ausgeschlossen");
      return h("tr", { class: item.small_group ? "low" : "" },
        h("td", { class: "name", onclick: other ? () => host.open(other) : null }, item.name,
          notes.length ? h("div", { class: "note" }, notes.join(" · ")) : null),
        h("td", {}, item.shared_roles.length ? item.shared_roles.map((role) => host.roleName(role)).join(", ") : "gleicher Kartentyp"),
        h("td", { class: "num" }, mvText(item)),
        ...freqCells(item),
        h("td", {}, action));
    }

    function tableFor(rows, caption) {
      return h("div", { class: "table-wrap" }, h("table", {},
        h("thead", {}, h("tr", {},
          h("th", {}, caption),
          h("th", {}, "Gemeinsame Rolle"),
          h("th", { class: "num", title: "Manawert, in Klammern der Unterschied zu dieser Karte" }, "MW"),
          h("th", { class: "num", title: "In wie vielen Decks der Gruppe die Karte steht" }, "Gespielt in … Decks"),
          h("th", { class: "num" }, "Anteil"),
          h("th", {}, ""))),
        h("tbody", {}, rows.map(rowFor))));
    }

    function result(res) {
      const group = res.group;
      const parts = [];
      parts.push(h("p", { class: "note", id: "swap-helper-group" },
        `Vergleichsgruppe „${host.groupName(group)}“: ${group.decks} Decks (Nenner). `,
        res.small_group ? h("span", { class: "pill low", id: "swap-helper-small" }, `Kleine Gruppe: unter ${host.small()} Decks, die Zahlen sind unsicher`) : null));
      if (res.fallback) {
        parts.push(h("p", { class: "pill warn", id: "swap-helper-fallback" }, `Für diese Karte sind keine Rollen erfasst. Verglichen wird nach Kartentyp (${host.typeName(res.fallback.type_group)}).`));
      } else {
        parts.push(h("p", { class: "note" }, `Rollen dieser Karte: ${res.roles_of_card.map((role) => host.roleName(role)).join(", ")}`));
      }
      parts.push(h("p", { class: "note", id: "swap-helper-basis" }, res.basis));
      if (mode === "replace") {
        const box = h("input", { type: "checkbox", id: "swap-helper-unowned", checked: includeUnowned, onchange: () => { includeUnowned = box.checked; shown = FIRST; load(); } });
        parts.push(h("label", { class: "note" }, box, " auch Karten, die ich nicht besitze"));
      }
      const known = res.items.filter((item) => item.decks !== null);
      const unknown = res.items.filter((item) => item.decks === null);
      if (!res.items.length) {
        parts.push(h("p", { class: "muted", id: "swap-helper-empty" }, mode === "replace" ? "Keine Karten mit gleicher Rolle gefunden, die frei und nicht im Deck sind." : "Keine Karten im Deck mit gleicher Rolle."));
        return parts;
      }
      const caption = mode === "replace" ? "Karte (häufigste zuerst)" : "Karte im Deck (seltenste zuerst)";
      if (known.length) {
        parts.push(tableFor(known.slice(0, shown), caption));
        if (known.length > shown) {
          parts.push(h("button", { type: "button", class: "small", id: "swap-helper-more", onclick: () => { shown += FIRST; body.replaceChildren(...result(res)); } }, `Weitere ${Math.min(FIRST, known.length - shown)} zeigen`));
        }
      }
      if (res.unknown_count) {
        parts.push(h("h4", {}, `Häufigkeit unbekannt (${res.unknown_count})`));
        parts.push(h("p", { class: "note" }, "Unbekannt heißt nicht „selten gespielt“: die Decks der Gruppe nennen diese Karten unter keinem bekannten Namen. Sie stehen immer am Ende."));
        if (unknown.length) parts.push(tableFor(unknown.slice(0, FIRST), "Karte"));
      }
      if (res.total > res.items.length) {
        parts.push(h("p", { class: "note" }, `Geladen sind die ersten ${res.items.length} von ${res.total} Karten.`));
      }
      return parts;
    }

    function render() {
      toggle.className = "chip" + (open ? " on" : "");
      toggle.setAttribute("aria-pressed", String(open));
      if (!open) { token++; body.replaceChildren(); return; }
      load();
    }

    into.replaceChildren(h("h3", {}, "Tausch-Helfer"), toggle, body);
    if (open) load();
  }

  return { mount };
})();
