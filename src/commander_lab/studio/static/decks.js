"use strict";

const $ = (id) => document.getElementById(id);
const h = StudioUI.h;
const api = StudioUI.api;
// replaceChildren passes null straight to the DOM (it would show the text "null"): drop empty children.
const kids = (...items) => items.filter((item) => item !== null && item !== undefined && item !== false);

const state = {
  commander: "",
  q: "",
  origin: "source",
  cohort: "all",
  label: "",
  mustIn: [],
  mustOut: [],
  includeUnowned: false,
  data: null,
};

function parseCardList(raw) {
  return (raw || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function closeModal() {
  $("modal").hidden = true;
}

async function openDeckDetail(item) {
  const box = $("modal-box");
  box.className = "plain";
  box.replaceChildren(h("h2", {}, item.name), StudioUI.loading("Deckliste lädt …"));
  $("modal").hidden = false;
  try {
    const detail = await api(`/api/deck-browser/${encodeURIComponent(item.id)}`);
    const cards = detail.cards || [];
    const inColl = cards.filter((c) => c.in_collection).reduce((acc, c) => acc + (c.quantity || 1), 0);
    const total = cards.reduce((acc, c) => acc + (c.quantity || 1), 0);
    const tbl = h("table", {},
      h("thead", {}, h("tr", {},
        h("th", {}, "Sektion"),
        h("th", { class: "num" }, "Anzahl"),
        h("th", {}, "Karte"),
        h("th", {}, "Sammlung"))),
      h("tbody", {}, cards.map((c) => h("tr", {},
        h("td", {}, c.section),
        h("td", { class: "num" }, c.quantity),
        h("td", {}, c.name),
        h("td", {}, c.in_collection ? `${c.available} frei / ${c.owned} im Besitz` : h("span", { class: "muted" }, "nicht in deiner Sammlung"))))));
    box.replaceChildren(...kids(
      h("h2", {}, detail.name),
      h("p", { class: "note" },
        `Nur-Lese-Ansicht (${detail.origin === "saved" ? "Gespeichertes Studio-Deck" : `Quelldeck · ${detail.platform || "Korpus"}`})` +
        ` · ${inColl} von ${total} Karten in deiner Sammlung.`),
      detail.url ? h("p", {}, h("a", { href: detail.url, target: "_blank", rel: "noopener" }, "Quelladresse öffnen ↗")) : null,
      tbl,
      h("div", { class: "actions" }, h("button", { type: "button", onclick: closeModal }, "Schließen"))
    ));
  } catch (error) {
    box.replaceChildren(
      h("h2", {}, item.name),
      h("p", { class: "muted" }, "Deckliste nicht lesbar: " + StudioUI.germanError(error)),
      h("div", { class: "actions" }, h("button", { type: "button", onclick: closeModal }, "Schließen"))
    );
  }
}

function renderBrowser() {
  const data = state.data;
  if (!data) return;
  const total = data.total_decks || 0;
  const small = Boolean(data.small_sample);
  const counts = data.origin_counts || {};
  const originBreakdown = counts.source && counts.saved
    ? `${StudioUI.num(counts.source, 0)} Quelldecks + ${StudioUI.num(counts.saved, 0)} gespeicherte Studio-Decks`
    : "";
  const activeFilters = [];
  if (state.commander) activeFilters.push(`Commander: ${state.commander}`);
  if (state.origin !== "all") activeFilters.push(`Herkunft: ${state.origin === "saved" ? "Studio" : "Quelldecks"}`);
  if (state.cohort !== "all") activeFilters.push(`Gruppe: ${state.cohort}`);
  if (state.label) activeFilters.push(`Marke/Tag: ${state.label}`);
  if (state.mustIn.length) activeFilters.push(`Enthält: ${state.mustIn.join(", ")}`);
  if (state.mustOut.length) activeFilters.push(`Ohne: ${state.mustOut.join(", ")}`);

  $("db-summary").replaceChildren(...kids(
    h("b", {}, `${StudioUI.num(total, 0)} Decks in der aktuellen Filtermenge`),
    originBreakdown ? ` (= ${originBreakdown})` : null,
    activeFilters.length ? ` · Filter: ${activeFilters.join(" · ")}` : " · alle passenden Decks",
    " ",
    small ? h("span", { class: "pill low" }, `Kleine Stichprobe (< ${data.small_denominator || 30} Decks)`) : null
  ));

  const decksBox = $("db-decks");
  const decks = data.decks || [];
  if (!decks.length) {
    decksBox.replaceChildren(h("p", { class: "muted" }, "Keine Decks passen auf die gewählten Filter."));
  } else {
    const tbl = h("table", { id: "deck-browser-table" },
      h("thead", {}, h("tr", {},
        h("th", {}, "Deck / Kennung"),
        h("th", {}, "Commander"),
        h("th", {}, "Herkunft / Plattform"),
        h("th", {}, "Gruppe / Bracket"),
        h("th", {}, "Marken / Tags"),
        h("th", { class: "num" }, "Karten"),
        h("th", {}, "Datum"),
        h("th", {}, ""))),
      h("tbody", {}, decks.map((d) => h("tr", {},
        h("td", { class: "name", onclick: () => openDeckDetail(d) }, d.name),
        h("td", {}, d.commander || "–"),
        h("td", {}, d.origin === "saved" ? "Gespeichert (Studio)" : (d.platform || "Quelldeck")),
        h("td", {}, d.bracket || d.cohort || "–"),
        h("td", {}, (d.labels || []).length ? d.labels.slice(0, 4).join(", ") : "–"),
        h("td", { class: "num" }, d.cards ?? "–"),
        h("td", {}, d.deck_date || "–"),
        h("td", {}, h("button", { type: "button", class: "small", onclick: () => openDeckDetail(d) }, "Ansehen"))))));
    decksBox.replaceChildren(
      h("h3", {}, `Gefilterte Decks (${StudioUI.num(decks.length, 0)} von ${StudioUI.num(total, 0)} angezeigt)`),
      tbl
    );
  }

  const coBox = $("db-cooccurrence");
  const coRows = data.cooccurrence || [];
  if (!total) {
    coBox.replaceChildren(
      h("h3", {}, "Karten-Kookkurrenz in der Filtermenge"),
      h("p", { class: "muted" }, "Keine Decks in der Filtermenge (Nenner 0).")
    );
    return;
  }
  const coTable = coRows.length
    ? h("table", { id: "deck-browser-cooccurrence" },
        h("thead", {}, h("tr", {},
          h("th", {}, "Karte (ohne Standardländer)"),
          h("th", { class: "num" }, "Decks (n/N)"),
          h("th", { class: "num" }, "Anteil"),
          h("th", {}, "Sammlung"),
          h("th", {}, ""))),
        h("tbody", {}, coRows.map((row) => h("tr", { class: small ? "low" : "" },
          h("td", {}, row.name),
          h("td", { class: "num" }, `${StudioUI.num(row.decks, 0)}/${StudioUI.num(row.of, 0)}`),
          h("td", { class: "num" }, `${StudioUI.num(100 * row.share, 1)} %`),
          h("td", {}, row.in_collection ? `${row.available} frei / ${row.owned}` : h("span", { class: "muted" }, "nicht in deiner Sammlung")),
          h("td", {},
            h("button", {
              type: "button",
              class: "small",
              title: "Nur Decks mit dieser Karte filtern",
              onclick: () => {
                if (!state.mustIn.includes(row.name)) {
                  state.mustIn.push(row.name);
                  $("db-must-in").value = state.mustIn.join(", ");
                  loadBrowser();
                }
              },
            }, "+ Filter"))))))
    : h("p", { class: "muted" }, "Keine weiteren Karten in dieser Filtermenge gefunden.");

  coBox.replaceChildren(...kids(
    h("h3", {}, `Karten-Kookkurrenz (Nenner: ${StudioUI.num(total, 0)} Decks)`),
    originBreakdown ? h("p", { class: "note" }, `${StudioUI.num(total, 0)} Decks = ${originBreakdown}. Beide Gruppen sind hier gemischt; „Nur Quelldecks“ trennt sie.`) : null,
    small ? h("p", { class: "pill low" }, `Kleine Stichprobe: nur ${total} Decks in der Filtermenge (< ${data.small_denominator || 30}).`) : null,
    h("p", { class: "note" }, "Reine Zählung über die aktuell gefilterte Deckmenge: wie viele dieser Decks jede andere Karte spielen (n von N und Prozent). Ein Klick auf „+ Filter“ engt die Deckmenge auf Decks mit dieser Karte ein."),
    coTable
  ));
}

async function loadBrowser() {
  state.q = $("db-q").value.trim();
  state.origin = $("db-origin").value;
  state.cohort = $("db-cohort").value;
  state.label = $("db-label").value.trim();
  state.mustIn = parseCardList($("db-must-in").value);
  state.mustOut = parseCardList($("db-must-out").value);
  state.includeUnowned = $("db-unowned").checked;

  const params = new URLSearchParams();
  if (state.commander) params.set("commander", state.commander);
  if (state.q) params.set("q", state.q);
  params.set("origin", state.origin);
  params.set("cohort", state.cohort);
  if (state.label) params.set("label", state.label);
  for (const card of state.mustIn) params.append("must_contain", card);
  for (const card of state.mustOut) params.append("must_not_contain", card);
  if (state.includeUnowned) params.set("include_unowned", "true");

  $("db-decks").replaceChildren(StudioUI.loading("Decks werden gefiltert …"));
  try {
    state.data = await api("/api/deck-browser?" + params.toString());
    renderBrowser();
  } catch (error) {
    $("db-decks").replaceChildren(h("p", { class: "muted" }, "Deck-Browser konnte nicht geladen werden: " + StudioUI.germanError(error)));
  }
}

async function start() {
  await StudioCommander.fill($("commander-select"));
  state.commander = StudioCommander.current || "";
  StudioUI.dataState($("data-state"), state.commander);
  const urlParams = new URLSearchParams(location.search);
  if (urlParams.get("q")) $("db-q").value = urlParams.get("q");
  if (urlParams.get("origin")) $("db-origin").value = urlParams.get("origin");
  if (urlParams.get("cohort")) $("db-cohort").value = urlParams.get("cohort");
  if (urlParams.get("label")) $("db-label").value = urlParams.get("label");
  const mustIn = urlParams.getAll("must").concat(urlParams.getAll("must_contain")).filter(Boolean);
  if (mustIn.length) $("db-must-in").value = mustIn.join(", ");
  const mustOut = urlParams.getAll("must_not").concat(urlParams.getAll("must_not_contain")).filter(Boolean);
  if (mustOut.length) $("db-must-out").value = mustOut.join(", ");
  if (urlParams.get("include_unowned") === "true" || urlParams.get("unowned") === "1") {
    $("db-unowned").checked = true;
  }
  $("db-apply").addEventListener("click", loadBrowser);
  $("db-reset").addEventListener("click", () => {
    $("db-q").value = "";
    $("db-origin").value = "source";
    $("db-cohort").value = "all";
    $("db-label").value = "";
    $("db-must-in").value = "";
    $("db-must-out").value = "";
    $("db-unowned").checked = false;
    loadBrowser();
  });
  $("db-unowned").addEventListener("change", loadBrowser);
  $("db-origin").addEventListener("change", loadBrowser);
  $("db-cohort").addEventListener("change", loadBrowser);
  for (const id of ["db-q", "db-label", "db-must-in", "db-must-out"]) {
    $(id).addEventListener("keydown", (event) => {
      if (event.key === "Enter") loadBrowser();
    });
  }
  $("modal").addEventListener("click", (event) => { if (event.target === $("modal")) closeModal(); });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeModal(); });
  await loadBrowser();
}

start();
