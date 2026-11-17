"use strict";
// Deck tab "Belege" (#1404): evidence per deck card. One row per card, one column per kind of
// evidence, every cell a counted value of one source with its n/N and the group named in the
// column header. Nothing is added up or rated; unknown stays text ("unbekannt", "keine Zeile"),
// never 0. The Owner's marks play no part in the order or in any figure. The text is set as
// text only (no HTML strings), the table is built with h().
// Rendered by app.js through renderDeckEvidence(body, deps).

// The columns whose text is long and may wrap; the count columns stay on one line.
const EVIDENCE_WRAP = new Set(["edhrec", "playgroup", "fit"]);
const EVIDENCE_COLUMNS_KEY = "studio-evidence-columns";
// Sort and filter of the open page (kept when app.js redraws the tab, gone on reload).
const evidenceView = { sortKey: "decks_all", descending: false, filter: "" };

const evidenceNumber = (value, digits = 0) =>
  Number(value).toLocaleString("de-DE", { minimumFractionDigits: digits, maximumFractionDigits: digits });
const evidencePercent = (share, digits = 1) => `${evidenceNumber(share * 100, digits)} %`;
const evidenceSigned = (value, digits = 1) => `${value > 0 ? "+" : ""}${evidenceNumber(value, digits)}`;

// The one contract of the order: by the chosen column's own value, unknown ALWAYS last (both
// directions), ties by name, cards that are not applicable (commander, basic lands) at the end.
function evidenceOrder(cards, key, descending) {
  const name = (card) => String(card.name).toLocaleLowerCase("de");
  const valueOf = (card) => {
    if (key === "name") return name(card);
    const cell = card.cells[key];
    return cell === undefined || cell === null ? null : cell.sort;
  };
  const byName = (a, b) => name(a).localeCompare(name(b), "de");
  const applicable = cards.filter((card) => card.applicable);
  const known = applicable.filter((card) => valueOf(card) !== null);
  const unknown = applicable.filter((card) => valueOf(card) === null);
  const other = cards.filter((card) => !card.applicable);
  known.sort((a, b) => {
    const x = valueOf(a);
    const y = valueOf(b);
    const order = typeof x === "string" ? x.localeCompare(y, "de") : x - y;
    return order !== 0 ? (descending ? -order : order) : byName(a, b);
  });
  unknown.sort(byName);
  other.sort((a, b) => (a.zone === "commander" ? 0 : 1) - (b.zone === "commander" ? 0 : 1) || byName(a, b));
  return [...known, ...unknown, ...other];
}

// Where an EDHREC figure comes from: the commander's main page, a sub page (theme) or the signal import.
function evidencePageText(cell) {
  const page = String(cell.page);
  if (cell.main_page) return "Hauptseite";
  if (page.includes("/")) return `Unterseite „${page.split("/").pop()}“`;
  return page;
}

// The text of one cell: [text, flag] where flag says "small number" (shown as a hint).
function evidenceCellText(key, cell) {
  if (cell === null || cell === undefined) return null;
  switch (key) {
    case "decks_all":
    case "decks_tuned":
    case "combos":
      return [`${evidenceNumber(cell.n)} / ${evidenceNumber(cell.of)}`, false];
    case "edhrec": {
      const page = evidencePageText(cell);
      if (cell.note) return [`${cell.note}${cell.of ? ` (N = ${evidenceNumber(cell.of)})` : ""}; ${page}`, false];
      const count = cell.n === null || cell.of === null
        ? (cell.of === null ? "Nenner unbekannt" : `Zähler unbekannt, N = ${evidenceNumber(cell.of)}`)
        : `${evidenceNumber(cell.n)} / ${evidenceNumber(cell.of)}`;
      return [`${evidenceNumber(cell.pct, 1)} % (${count}); ${page}`, cell.small_group];
    }
    case "shells":
      return [`${evidenceNumber(cell.count)} Shells`, false];
    case "playgroup": {
      const interval = cell.ci_low_pp === null || cell.ci_high_pp === null
        ? "Intervall unbekannt"
        : `95 %: ${evidenceSigned(cell.ci_low_pp)} bis ${evidenceSigned(cell.ci_high_pp)} Pp`;
      const n = cell.n === null ? "n unbekannt" : `n = ${evidenceNumber(cell.n)}`;
      return [`${evidenceSigned(cell.gap_pp)} Pp (${interval}, ${n})`, cell.small_group];
    }
    case "topdeck":
    case "edhtop16": {
      const count = cell.n === null ? `Zähler unbekannt` : `${evidenceNumber(cell.n)} / ${evidenceNumber(cell.of)}`;
      return [`${count}${cell.derived_numerator ? " (aus Rate)" : ""}`, cell.small_group];
    }
    case "roles":
      return [cell.roles.join(", "), false];
    case "role_count":
      return [evidenceNumber(cell.n), false];
    case "fit": {
      const base = cell.baseline === null ? "Grundwert unbekannt" : `Grundwert ${evidencePercent(cell.baseline)}`;
      if (cell.value === null) return [`keine Quelldecks der Gruppe (0 / ${evidenceNumber(cell.of)}); ${base}`, false];
      return [`${evidencePercent(cell.value)} (${base}; ${evidenceNumber(cell.decks)} Decks)`, cell.small_group];
    }
    default:
      return null;
  }
}

function evidenceFooterText(key, footer, groups) {
  if (key === "decks_all") return `N = ${evidenceNumber(footer.decks_all.of)}${groups.all.small_group ? " (kleine Gruppe)" : ""}`;
  if (key === "decks_tuned") return footer.decks_tuned.of ? `N = ${evidenceNumber(footer.decks_tuned.of)}${groups.tuned.small_group ? " (kleine Gruppe)" : ""}` : "keine Decks in dieser Gruppe";
  if (key === "fit") {
    if (footer.fit.baseline === null) return "Grundwert unbekannt";
    return `Grundwert ${evidencePercent(footer.fit.baseline)} (${evidenceNumber(footer.fit.decks)} Quelldecks, ${evidenceNumber(footer.fit.deck_cards)} Karten)`;
  }
  return "";
}

// The plain text of the visible table for the Owner's notes: tab separated, only the shown counts.
function evidenceTextTable(data, columns, cards) {
  const lines = [["Karte", ...columns.map((column) => column.label)].join("\t")];
  for (const card of cards) {
    const cells = columns.map((column) => {
      if (!card.applicable) return "nicht anwendbar";
      const shown = evidenceCellText(column.key, card.cells[column.key]);
      return shown === null ? column.missing : shown[0] + (shown[1] ? " (kleine Zahl)" : "");
    });
    lines.push([card.name + (card.quantity > 1 ? ` (${card.quantity}×)` : ""), ...cells].join("\t"));
  }
  lines.push(["Gruppe / Grundwert", ...columns.map((column) => evidenceFooterText(column.key, data.footer, data.groups))].join("\t"));
  return `${lines.join("\n")}\n\n${data.note}\n`;
}

function evidenceStoredColumns(all) {
  try {
    const raw = StudioUI.recall(EVIDENCE_COLUMNS_KEY, null);
    const parsed = raw === null ? null : JSON.parse(raw);
    if (Array.isArray(parsed)) return new Set(parsed.filter((key) => all.includes(key)));
  } catch (error) { /* damaged memory: show everything */ }
  return new Set(all);
}

// The whole view (controls, table, notes) as nodes. ``wide`` is the modal version: the same data
// and the same sort/filter, a table that fits the page width.
function buildEvidenceView(data, deps, wide) {
  const { h } = deps;
  const allKeys = data.columns.map((column) => column.key);
  let visible = evidenceStoredColumns(allKeys);
  const view = evidenceView;
  const cohortLabel = deps.cohortName ? deps.cohortName(data.cohort.key) : data.cohort.key;

  const table = h("div", { class: "table-wrap" });
  const status = h("span", { class: "note", role: "status", id: wide ? "evidence-status-wide" : "evidence-status" });
  const copyText = h("textarea", { id: wide ? "evidence-copy-text-wide" : "evidence-copy-text", readonly: true, rows: 6, hidden: true, "aria-label": "Text zum Kopieren" });
  const shownColumns = () => data.columns.filter((column) => visible.has(column.key));
  const shownCards = () => {
    const needle = view.filter.trim().toLocaleLowerCase("de");
    return evidenceOrder(data.cards, view.sortKey, view.descending)
      .filter((card) => !needle || String(card.name).toLocaleLowerCase("de").includes(needle));
  };

  const sortButton = (key, label) => {
    const active = view.sortKey === key;
    return h("button", {
      type: "button", class: "ghost small sortbtn", "data-sort": key,
      title: "Nach dieser Spalte sortieren; unbekannte Werte stehen immer ganz unten",
      onclick: () => {
        if (view.sortKey === key) view.descending = !view.descending;
        else { view.sortKey = key; view.descending = false; }
        draw();
      },
    }, label + (active ? (view.descending ? " ↓" : " ↑") : ""));
  };
  const groupNote = (size, small) => (size ? `N = ${evidenceNumber(size)}${small ? ", kleine Gruppe (unter 30)" : ""}` : "keine Decks in dieser Gruppe");
  const headerNote = (column) => {
    const parts = [column.short];
    if (column.key === "decks_all") parts.push(groupNote(data.groups.all.decks, data.groups.all.small_group));
    if (column.key === "decks_tuned") parts.push(groupNote(data.groups.tuned.decks, data.groups.tuned.small_group));
    if (column.of) parts.push(`N = ${column.of.map((size) => evidenceNumber(size)).join(" / ")}${column.of.some((size) => size < data.small_group_below) ? ", sehr kleine Gruppe" : ""}`);
    if (column.key === "fit") parts.push(`Gruppe „${cohortLabel}“ (${groupNote(data.cohort.decks, data.cohort.small_group)})`);
    return parts.join(" · ");
  };

  const cellNode = (column, card) => {
    const shown = evidenceCellText(column.key, card.cells[column.key]);
    if (shown === null) return h("td", { class: "muted" }, column.missing);
    return h("td", { class: column.key === "roles" ? "" : (EVIDENCE_WRAP.has(column.key) ? "num" : "num nowrap") }, shown[0], shown[1] ? [" ", h("span", { class: "pill warn", title: "Kleine Zahl (unter 30): mit Vorsicht lesen" }, "klein")] : "");
  };

  function draw() {
    const columns = shownColumns();
    const cards = shownCards();
    const rows = cards.map((card) => h("tr", { class: card.applicable ? "" : "na" },
      h("td", { class: "nm", onclick: () => deps.open(card.card_id) },
        card.name + (card.quantity > 1 ? ` (${card.quantity}×)` : "")),
      card.applicable
        ? columns.map((column) => cellNode(column, card))
        : h("td", { class: "muted", colspan: Math.max(columns.length, 1) }, `nicht anwendbar (${card.reason})`)));
    table.replaceChildren(h("table", { class: "evidence-table", id: wide ? "evidence-table-wide" : "evidence-table" },
      h("thead", {}, h("tr", {},
        h("th", { scope: "col", "aria-sort": view.sortKey === "name" ? (view.descending ? "descending" : "ascending") : "none" }, sortButton("name", "Karte")),
        columns.map((column) => h("th", {
          scope: "col", class: column.key === "roles" ? "" : "num",
          "aria-sort": view.sortKey === column.key ? (view.descending ? "descending" : "ascending") : "none",
        }, sortButton(column.key, column.label), h("div", { class: "basis" }, headerNote(column)))))),
      h("tbody", {}, rows),
      h("tfoot", {}, h("tr", {},
        h("td", {}, h("b", {}, "Gruppe / Grundwert")),
        columns.map((column) => h("td", { class: "num" }, evidenceFooterText(column.key, data.footer, data.groups)))))));
    status.textContent = `${cards.length} von ${data.cards.length} Zeilen`;
  }

  const columnBoxes = data.columns.map((column) => h("label", { class: "evidence-col" },
    h("input", {
      type: "checkbox", "data-column": column.key, checked: visible.has(column.key),
      onchange: (event) => {
        if (event.target.checked) visible.add(column.key); else visible.delete(column.key);
        StudioUI.remember(EVIDENCE_COLUMNS_KEY, JSON.stringify([...visible]));
        draw();
      },
    }), " ", column.label));
  const filter = h("input", {
    type: "search", id: wide ? "evidence-filter-wide" : "evidence-filter", value: view.filter, placeholder: "Kartenname filtern", "aria-label": "Kartenname filtern",
    oninput: (event) => { view.filter = event.target.value; draw(); },
  });
  const copy = h("button", {
    type: "button", id: wide ? "evidence-copy-wide" : "evidence-copy",
    onclick: async () => {
      const text = evidenceTextTable(data, shownColumns(), shownCards());
      copyText.value = text;
      try {
        await navigator.clipboard.writeText(text);
        copyText.hidden = true;
        StudioUI.toast("Tabelle als Text kopiert.");
      } catch (error) {
        copyText.hidden = false;
        copyText.select();
        StudioUI.toast("Kopieren nicht erlaubt: der Text steht unter der Tabelle zum Markieren.", "error");
      }
    },
  }, "Als Text kopieren");

  const thin = data.thinnest;
  const thinList = thin.cards.length
    ? thin.cards.map((card) => `${card.name} ${evidenceNumber(card.n)} / ${evidenceNumber(card.of)}`).join(" · ")
    : "keine Karte mit bekannter Zahl";
  draw();
  return [
    h("h3", {}, "Belege je Deckkarte"),
    h("p", { class: "note" }, `Commander: ${data.commander.join(" + ")}. Jede Zelle ist ein Zählwert einer Quelle mit Zähler und Nenner; die Gruppe steht in der Spaltenüberschrift. Sortierung: ${data.order}.`),
    h("div", { class: "evidence-controls" },
      h("details", { class: "evidence-columns" }, h("summary", {}, "Spalten wählen"), h("div", { class: "evidence-col-list" }, columnBoxes)),
      h("div", { class: "evidence-actions" }, filter, copy, status,
        wide ? null : h("button", { type: "button", id: "evidence-wide", onclick: () => deps.openWide(data) }, "Große Ansicht"))),
    table,
    copyText,
    h("p", { class: "note", id: wide ? "evidence-note-wide" : "evidence-note" }, data.note),
    h("p", { class: "note", id: wide ? "evidence-thin-wide" : "evidence-thin" },
      `Dünne Beleglage (wenigste Quelldecks in „alle“, n / N): ${thinList}.`
      + (thin.unknown ? ` Dazu ${evidenceNumber(thin.unknown)} von ${evidenceNumber(thin.applicable)} Karten ohne Angabe (kein Quelldeck nennt sie): unbekannt, nicht 0.` : "")),
    h("details", { class: "evidence-explain" }, h("summary", {}, "Was die Spalten zählen"),
      h("ul", { class: "note" }, data.columns.map((column) => h("li", {}, h("b", {}, `${column.label}: `), column.basis)))),
  ];
}

// deps: { h, api, entries, fail, open(card_id), token(), isCurrent(token), cohort, cohortName }
async function renderDeckEvidence(body, deps) {
  const { h } = deps;
  const box = h("div", { id: "deck-evidence" }, h("p", { class: "muted" }, "Wird berechnet …"));
  body.append(box);
  const token = deps.token();
  let data;
  try {
    data = await deps.api("/api/deck-evidence", "POST", { cards: deps.entries(), cohort: deps.cohort || "all" });
  } catch (error) {
    if (!deps.isCurrent(token)) return;
    box.replaceChildren(h("p", { class: "warn" }, "Die Belege konnten nicht berechnet werden."));
    deps.fail(error);
    return;
  }
  if (!deps.isCurrent(token)) return;
  // The same table in the wide dialog (the side panel is narrow), as the overview does.
  const openWide = (payload) => {
    const modal = document.getElementById("modal");
    const modalBox = document.getElementById("modal-box");
    if (!modal || !modalBox) return;
    modalBox.className = "plain wide";
    modalBox.replaceChildren(
      ...buildEvidenceView(payload, { ...deps, openWide: null }, true),
      h("div", { class: "actions" }, h("button", { type: "button", onclick: () => { modal.hidden = true; } }, "Schließen")));
    modal.hidden = false;
  };
  box.replaceChildren(...buildEvidenceView(data, { ...deps, openWide }, false));
}
