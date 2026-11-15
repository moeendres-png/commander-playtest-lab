"use strict";
// Commander Studio deck builder: the section "Ähnliche Quelldecks" (tab "Ähnliche Decks").
// Loaded before app.js, which hooks in through renderSimilarDecks(body); everything here reads
// the helpers of app.js (h, state, api, cohortName, ...) only when it runs. All text from data is
// set as text, never as HTML. It counts: "ähnlich" means the same cards, not success.

const SIMILAR_NOTE = "Ähnlich heißt: gleiche Karten, nicht: erfolgreich.";
const similarNumber = (value) => Number(value).toLocaleString("de-DE");
const similarPercent = (value) => `${Math.round(100 * value)} %`;
const similarHasLink = (url) => /^https?:\/\//i.test(String(url || ""));

function similarCacheKey() {
  return `${state.deckId || ""}|${state.branch || ""}|${state.changeSeq}|${state.cohort}|${Boolean(state.similarIncludeUnowned)}`;
}
// One request per list, group and switch; the answer is kept until one of them changes.
function loadSimilarDecks() {
  const key = similarCacheKey();
  if (state.similarDecks && state.similarDecks.key === key) return;
  if (state.similarDecksBusy === key) return;
  state.similarDecksBusy = key;
  api("/api/similar-decks", "POST", {
    commander: COMMANDER,
    deck_card_ids: [...state.list.keys()],
    cohort: state.cohort,
    n: 20,
    include_unowned: Boolean(state.similarIncludeUnowned),
  }).then((data) => {
    state.similarDecks = { key, data, error: null };
    state.similarDecksBusy = null;
    if (state.tab === "similar" || state.tab === "numbers") renderDeck();
  }, (error) => {
    state.similarDecks = { key, data: null, error: StudioUI.germanError(error) };
    state.similarDecksBusy = null;
    fail(error);
    if (state.tab === "similar" || state.tab === "numbers") renderDeck();
  });
}
async function openSourceDeckModal(deckId) {
  try {
    const incUnowned = Boolean(state.similarIncludeUnowned);
    const detail = await api(`/api/deck-browser/source:${encodeURIComponent(deckId)}`);
    const box = $("modal-box"); box.className = "plain";
    const cards = detail.cards || [];
    const ownedRows = cards.filter((c) => c.in_collection);
    const unownedRows = cards.filter((c) => !c.in_collection);
    const makeRow = (c) => {
      const poolCard = c.card_id ? state.byId.get(c.card_id) : null;
      return h("tr", {},
        h("td", { class: "num" }, c.quantity || 1),
        h("td", {}, c.name),
        h("td", {}, c.section || "main"),
        h("td", {}, c.in_collection ? (c.available > 0 ? `im Pool (${c.available} frei)` : "im Pool (0 frei)") : "nicht in Sammlung"),
        h("td", {}, poolCard && poolCard.available > 0 && !qty(poolCard.card_id) ? h("button", { class: "small", type: "button", onclick: () => add(poolCard) }, "+") : null));
    };
    box.replaceChildren(
      h("h2", {}, detail.name || `Quelldeck ${deckId}`),
      h("p", { class: "note" }, `Plattform: ${detail.platform || "–"} · Kohorte: ${cohortName(detail.cohort || "all")} · Karten: ${cards.length} (${ownedRows.length} in deiner Sammlung, ${unownedRows.length} außerhalb)`),
      similarHasLink(detail.url) ? h("p", {}, h("a", { href: detail.url, target: "_blank", rel: "noopener noreferrer" }, "Quelldeck extern öffnen ↗")) : null,
      h("h3", {}, `Karten in deiner Sammlung (${ownedRows.length})`),
      h("table", {},
        h("thead", {}, h("tr", {}, h("th", { class: "num" }, "Anz."), h("th", {}, "Karte"), h("th", {}, "Sektion"), h("th", {}, "Sammlung"), h("th", {}, ""))),
        h("tbody", {}, ownedRows.map(makeRow))),
      incUnowned && unownedRows.length ? h("details", {},
        h("summary", {}, `Karten außerhalb deiner Sammlung (${unownedRows.length})`),
        h("table", {},
          h("thead", {}, h("tr", {}, h("th", { class: "num" }, "Anz."), h("th", {}, "Karte"), h("th", {}, "Sektion"), h("th", {}, "Sammlung"), h("th", {}, ""))),
          h("tbody", {}, unownedRows.map(makeRow)))) : null,
      h("div", { class: "actions" }, h("button", { type: "button", onclick: closeModal }, "Schließen")),
    );
    $("modal").hidden = false;
  } catch (error) { fail(error); }
}
// The group list is the one of the comparison tabs (state.cohorts); picking one here sets the
// same group as the pool filter above.
function similarGroupSelect() {
  const select = h("select", { id: "similar-group", "aria-label": "Gruppe der Quelldecks" },
    ...Object.entries(state.cohorts).map(([key, size]) => h("option", { value: key, selected: key === state.cohort }, `${cohortName(key)} (${similarNumber(size)})`)));
  select.addEventListener("change", () => {
    state.cohort = select.value;
    if (!$("cohort").disabled) $("cohort").value = state.cohort;
    renderPool(); renderDeck();
  });
  return select;
}
function similarCardName(item) {
  const poolCard = item.card_id ? state.byId.get(item.card_id) : null;
  const label = h("span", { class: poolCard ? "nm" : "", onclick: () => { if (poolCard) openCard(poolCard); } }, item.name);
  if (poolCard) hoverPreview(label, poolCard);
  return label;
}
function similarOwnership(item) {
  if (!item.owned) return "nicht in der Sammlung";
  if (!item.in_pool) return "in der Sammlung, nicht spielbar mit diesem Commander";
  return item.available > 0 ? `frei (${item.available})` : "0 frei";
}
function similarCardTable(id, rows, withOwnership, action) {
  return h("table", { id },
    h("thead", {}, h("tr", {},
      h("th", {}, "Karte"),
      h("th", { class: "num" }, "In ähnlichen Decks (n/N)"),
      h("th", { class: "num" }, "Anteil"),
      withOwnership ? h("th", {}, "Sammlung") : null,
      h("th", {}, ""))),
    h("tbody", {}, rows.map((item) => {
      const poolCard = item.card_id ? state.byId.get(item.card_id) : null;
      return h("tr", {},
        h("td", {}, similarCardName(item)),
        h("td", { class: "num" }, `${item.hits}/${item.of}`),
        h("td", { class: "num" }, similarPercent(item.share)),
        withOwnership ? h("td", {}, similarOwnership(item)) : null,
        h("td", {}, poolCard ? action(poolCard) : null));
    })));
}
function renderSimilarDecks(body) {
  renderDeckStatusBox(body);
  body.append(h("h3", {}, "Ähnliche Quelldecks"));
  loadSimilarDecks();
  const toggle = h("input", {
    type: "checkbox",
    id: "similar-include-unowned",
    checked: Boolean(state.similarIncludeUnowned),
    onchange: (event) => { state.similarIncludeUnowned = event.target.checked; renderDeck(); },
  });
  body.append(
    h("p", { class: "note", id: "similar-disclosure" }, `${SIMILAR_NOTE} Zu Erfolg je Deck gibt es für ${StudioCommander.shortName(COMMANDER)} keine Daten.`),
    h("div", { class: "actions" },
      h("label", {}, "Gruppe: ", similarGroupSelect()),
      h("label", {}, toggle, " auch Karten, die ich nicht besitze"),
      h("a", { class: "nav", href: "decks.html" }, "Deck-Browser öffnen →")));
  const key = similarCacheKey();
  const entry = state.similarDecks && state.similarDecks.key === key ? state.similarDecks : null;
  if (entry && entry.error) { body.append(h("p", { class: "muted", id: "similar-error" }, `Nicht berechnet: ${entry.error}`)); return; }
  const found = entry ? entry.data : null;
  if (!found) { body.append(h("p", { class: "muted", id: "similar-wait" }, "Wird berechnet …")); return; }
  if (found.empty_reason || !found.decks_considered) {
    body.append(h("p", { class: "muted", id: "similar-empty" }, found.empty_reason || "zu wenige Decks in dieser Gruppe"));
    return;
  }
  if (found.small_group) {
    body.append(h("p", { class: "pill warn", id: "similar-small" }, `Kleine Gruppe: nur ${similarNumber(found.decks_considered)} Quelldecks in „${cohortName(state.cohort)}“ (unter ${found.small_group_limit}). Die Zahlen sind unsicher.`));
  }
  const median = found.median_similarity_all === null ? "unbekannt" : similarPercent(found.median_similarity_all);
  const left = [];
  if (found.duplicates_removed) left.push(`${similarNumber(found.duplicates_removed)} mit gleicher Kartenliste nur einmal gezählt`);
  if (found.identical_to_deck) left.push(`${similarNumber(found.identical_to_deck)} mit genau deiner Kartenliste weggelassen`);
  body.append(h("p", { class: "note", id: "similar-basis" },
    `Verglichen mit ${similarNumber(found.decks_considered)} Quelldecks (Gruppe „${cohortName(state.cohort)}“), ohne Standardländer und Commander${left.length ? `; ${left.join(", ")}` : ""}. Mittlere Übereinstimmung über alle: ${median}. Gezeigt: die ${similarNumber(found.n)} nächsten.`));
  const nearest = found.nearest || [];
  body.append(h("table", { id: "similar-decks-table" },
    h("thead", {}, h("tr", {},
      h("th", {}, "Quelldeck"),
      h("th", {}, "Bracket"),
      h("th", {}, "Plattform"),
      h("th", {}, "Datum"),
      h("th", { class: "num" }, "Übereinstimmung"),
      h("th", { class: "num" }, "Gemeinsame Karten"),
      h("th", {}, ""))),
    h("tbody", {}, nearest.map((d) => h("tr", {},
      h("td", {}, similarHasLink(d.url) ? h("a", { href: d.url, target: "_blank", rel: "noopener noreferrer", title: "Quelldeck extern öffnen" }, d.deck_id) : d.deck_id),
      h("td", {}, d.bracket ? cohortName(d.bracket) : "–"),
      h("td", {}, d.platform || "–"),
      h("td", {}, d.deck_date || "–"),
      h("td", { class: "num" }, similarPercent(d.similarity)),
      h("td", { class: "num" }, `${d.shared} von ${d.size}`),
      h("td", {}, h("button", { class: "small", type: "button", onclick: () => openSourceDeckModal(d.deck_id) }, "Ansehen")))))));
  const theyPlay = found.they_play_you_dont || [];
  body.append(h("h4", {}, `In mindestens ${found.min_hits} dieser ${found.n} Decks gespielt, in deinem Deck nicht`));
  body.append(theyPlay.length
    ? similarCardTable("similar-they-play", theyPlay, true, (card) => card.available > 0 && !qty(card.card_id) ? h("button", { class: "small", type: "button", onclick: () => add(card) }, "+") : null)
    : h("p", { class: "muted" }, "Keine solche Karte in deiner Sammlung."));
  const youPlay = found.you_play_they_dont || [];
  body.append(h("h4", {}, `In deinem Deck, in höchstens einem dieser ${found.n} Decks gespielt`));
  if (!youPlay.length) { body.append(h("p", { class: "muted" }, "Jede Karte deines Decks kommt in mindestens zwei dieser Decks vor.")); return; }
  const none = youPlay.filter((item) => item.none_play), one = youPlay.filter((item) => !item.none_play);
  const remover = (card) => qty(card.card_id) ? h("button", { class: "small", type: "button", onclick: () => remove(card) }, "−") : null;
  if (none.length) body.append(h("p", { class: "note" }, `Keines der ${found.n} Decks spielt sie (0/${found.n}):`), similarCardTable("similar-you-play", none, false, remover));
  if (one.length) body.append(h("p", { class: "note" }, `Nur eines der ${found.n} Decks spielt sie (1/${found.n}):`), similarCardTable("similar-you-play-one", one, false, remover));
}
