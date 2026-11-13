"use strict";
// Commander Studio: what all pages share. Colour scheme (system choice plus a toggle that is
// remembered), the area bar with the chosen commander, toasts, German error sentences, busy
// buttons and the data-state box. Text from data is always set as text, never as HTML.

const StudioUI = (() => {
  const THEME_KEY = "studio-theme";

  // ---------- remembered view settings (never anything that must persist) ----------
  function recall(key, fallback = null) {
    try { const value = localStorage.getItem(key); return value === null ? fallback : value; } catch (error) { return fallback; }
  }
  function remember(key, value) {
    try { localStorage.setItem(key, value); } catch (error) { /* private mode: no memory */ }
  }

  // ---------- colour scheme ----------
  const systemDark = () => window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  function effectiveTheme() {
    const chosen = document.documentElement.dataset.theme;
    return chosen === "light" || chosen === "dark" ? chosen : (systemDark() ? "dark" : "light");
  }
  function applyTheme(value) {
    if (value === "light" || value === "dark") document.documentElement.dataset.theme = value;
    else delete document.documentElement.dataset.theme;
  }
  applyTheme(recall(THEME_KEY, ""));

  // ---------- small helpers ----------
  function el(tag, props, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(props || {})) {
      if (value === null || value === undefined || value === false) continue;
      if (key === "class") node.className = value;
      else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
      else if (key in node && key !== "list") node[key] = value;
      else node.setAttribute(key, value);
    }
    for (const child of children.flat(Infinity)) {
      if (child === null || child === undefined || child === false) continue;
      node.append(child.nodeType ? child : document.createTextNode(String(child)));
    }
    return node;
  }

  // ---------- toasts ----------
  let toastTimer = 0;
  function toast(text, kind = "") {
    let box = document.getElementById("toast");
    if (!box) { box = el("div", { id: "toast", role: "status", "aria-live": "polite" }); document.body.append(box); }
    box.textContent = text;
    box.className = kind;
    box.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { box.hidden = true; }, kind === "error" ? 7000 : 4000);
  }
  const fail = (text) => toast(text, "error");

  // ---------- German sentences for server errors ----------
  const FIELD_NAMES = {
    min_main_cards: "Mindestgröße Hauptdeck", min_universe: "Mindest-Universum", date_from: "Datum ab", date_to: "Datum bis",
    min_coverage: "Mindest-Abdeckung", min_components: "Mindestanzahl Signale", must_contain: "Muss enthalten",
    platforms: "Plattformen", cohorts: "Kohorten", commanders: "Commander", weights: "Gewichte", tier_cuts: "Tier-Grenzen",
    min_denominators: "Mindest-Nenner", name: "Name", commander: "Commander", settings: "Einstellungen",
  };
  function fieldName(loc) {
    const parts = (loc || []).filter((part) => part !== "body" && part !== "query" && part !== "path");
    return parts.map((part) => FIELD_NAMES[part] || String(part)).join(" / ") || "Eingabe";
  }
  function pydanticSentence(item) {
    const field = fieldName(item.loc), ctx = item.ctx || {};
    switch (item.type) {
      case "greater_than_equal": return `${field}: Der Wert muss mindestens ${ctx.ge} sein.`;
      case "less_than_equal": return `${field}: Der Wert darf höchstens ${ctx.le} sein.`;
      case "greater_than": return `${field}: Der Wert muss größer als ${ctx.gt} sein.`;
      case "less_than": return `${field}: Der Wert muss kleiner als ${ctx.lt} sein.`;
      case "missing": return `${field}: Dieses Feld fehlt.`;
      case "string_too_short": return `${field}: Der Text ist zu kurz.`;
      case "string_too_long": return `${field}: Der Text ist zu lang (höchstens ${ctx.max_length} Zeichen).`;
      case "too_long": return `${field}: Zu viele Einträge (höchstens ${ctx.max_length}).`;
      case "extra_forbidden": return `${field}: Dieses Feld gibt es nicht.`;
      case "int_parsing": case "int_type": case "float_parsing": case "float_type": return `${field}: Hier ist eine Zahl nötig.`;
      case "bool_parsing": case "bool_type": return `${field}: Hier ist ja oder nein nötig.`;
      default: return `${field}: Der Wert ist nicht erlaubt.`;
    }
  }
  const KNOWN = [
    [/^unknown commander, preset, profile or universe profile/, "Commander, Voreinstellung, Einstellung oder Universum ist unbekannt."],
    [/^unknown universe profile/, "Dieses Universum gibt es nicht."],
    [/^unknown strength profile/, "Diese gespeicherte Einstellung gibt es nicht."],
    [/^commander not in the collection/, "Der Commander steht nicht in der Sammlung."],
    [/^unknown card/, "Diese Karte kennt das Studio nicht."],
    [/^unknown revision/, "Diesen Stand gibt es nicht."],
    [/^unknown deck/, "Dieses Deck gibt es nicht."],
    [/^local use only/, "Das Studio läuft nur auf diesem Rechner."],
    [/^missing request marker/, "Die Anfrage kam nicht von der Studio-Seite."],
    [/^the universe is defined for/, "Dieses Universum gehört zu einem anderen Commander."],
    [/^unknown universe card/, "Diese Karte kennt das Studio nicht. Wähle eine Karte aus der Vorschlagsliste."],
    [/^(Not Found|Unprocessable)/i, "Die Eingabe ist nicht gültig."],
    [/^Failed to fetch|NetworkError|Load failed/i, "Das Studio ist nicht erreichbar. Läuft der Server noch?"],
  ];
  function germanError(error) {
    const detail = error && error.detail !== undefined ? error.detail : error && error.message !== undefined ? error.message : String(error);
    if (Array.isArray(detail)) return detail.map(pydanticSentence).join(" ");
    const text = String(detail);
    if (/[äöüß]|Wähle|Teilmenge|Diese Karte|Gib ein/.test(text)) return text; // the server already wrote German
    for (const [pattern, sentence] of KNOWN) if (pattern.test(text)) return sentence;
    return `Das hat nicht geklappt (${text}).`;
  }
  // The same fetch wrapper for every page: errors carry the server detail for germanError.
  async function request(path, method = "GET", body) {
    const options = { method, headers: { "X-Studio": "1" } };
    if (body !== undefined) { options.headers["Content-Type"] = "application/json"; options.body = JSON.stringify(body); }
    let response;
    try { response = await fetch(path, options); } catch (error) { const failure = new Error("Failed to fetch"); failure.detail = "Failed to fetch"; throw failure; }
    if (!response.ok) {
      let detail = response.statusText;
      try { detail = (await response.json()).detail || detail; } catch (error) { /* keep status text */ }
      const failure = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
      failure.detail = detail;
      failure.status = response.status;
      throw failure;
    }
    return response.json();
  }

  // ---------- busy buttons ----------
  async function busy(button, work) {
    if (button) { button.disabled = true; button.classList.add("busy"); button.setAttribute("aria-busy", "true"); }
    try { return await work(); } finally {
      if (button) { button.disabled = false; button.classList.remove("busy"); button.removeAttribute("aria-busy"); }
    }
  }
  const loading = (text = "lädt …") => el("div", { class: "loading", role: "status" }, el("span", { class: "spinner", "aria-hidden": "true" }), text);
  const skeleton = (lines = 6) => el("div", { class: "skeleton-box", "aria-hidden": "true" }, Array.from({ length: lines }, () => el("div", { class: "skeleton" })));

  // ---------- number inputs with limits ----------
  // Every numeric field gets min, max and step; a typed value is clamped on leaving the field.
  function limitNumber(input, min, max, step = 1) {
    input.min = String(min); input.max = String(max); input.step = String(step);
    input.addEventListener("change", () => {
      if (input.value.trim() === "") return;
      const number = Number(input.value);
      if (!Number.isFinite(number)) { input.value = ""; return; }
      const clamped = Math.min(max, Math.max(min, number));
      if (clamped !== number) { input.value = String(clamped); toast(`Der Wert wurde auf ${clamped} gesetzt (erlaubt: ${min} bis ${max}).`); }
    });
    return input;
  }

  // ---------- area bar ----------
  function mountBar() {
    const here = location.pathname.split("/").pop() || "index.html";
    for (const link of document.querySelectorAll("#areas a")) {
      if (link.getAttribute("href") === here) link.setAttribute("aria-current", "page");
    }
    const bar = document.getElementById("brand");
    if (bar && typeof StudioCommander !== "undefined" && !document.getElementById("commander-badge")) {
      const badge = el("span", { id: "commander-badge", class: "commander-badge", title: StudioCommander.current }, StudioCommander.shortName(StudioCommander.current));
      const select = document.getElementById("commander-select");
      if (select && select.closest("label")) select.closest("label").before(badge); else bar.append(badge);
    }
    const toggle = document.getElementById("theme-toggle");
    if (toggle) {
      const paint = () => {
        const dark = effectiveTheme() === "dark";
        toggle.textContent = dark ? "☀ Hell" : "☾ Dunkel";
        toggle.title = dark ? "Zum hellen Farbschema wechseln" : "Zum dunklen Farbschema wechseln";
      };
      toggle.addEventListener("click", () => {
        const next = effectiveTheme() === "dark" ? "light" : "dark";
        applyTheme(next); remember(THEME_KEY, next); paint();
      });
      paint();
    }
  }
  document.addEventListener("DOMContentLoaded", mountBar);

  // ---------- data state: which layers are there, which are missing ----------
  const STATUS_TEXT = { COMPLETE: "vollständig", PARTIAL: "teilweise", MISSING: "fehlt" };
  async function dataState(host, commander, { onlyWhenMissing = true } = {}) {
    let overview;
    try { overview = await request(`/api/layers?commander=${encodeURIComponent(commander)}`); } catch (error) { host.replaceChildren(); return; }
    const missing = overview.layers.filter((layer) => layer.status === "MISSING");
    if (onlyWhenMissing && !missing.length) { host.replaceChildren(); return; }
    const rows = overview.layers.map((layer) => el("tr", {},
      el("td", {}, layer.layer),
      el("td", { class: "num" }, layer.rows),
      el("td", { class: "num" }, layer.pool === null ? "unbekannt" : `${layer.covered} von ${layer.pool}`),
      el("td", {}, el("span", { class: `badge status-${layer.status}` }, STATUS_TEXT[layer.status] || layer.status)),
      el("td", {}, layer.status === "MISSING" ? el("code", { class: "cmd" }, layer.command) : "")));
    host.replaceChildren(el("details", { class: "datastate", open: missing.some((layer) => ["inventory", "scryfall", "decklists"].includes(layer.key)) },
      el("summary", {}, missing.length ? `Es fehlen Daten: ${missing.length} von ${overview.layers.length} Schichten sind leer` : "Datenstand"),
      el("p", { class: "note" }, `Gezählt für ${StudioCommander.shortName(commander)}. Eine leere Schicht ist keine schwache Karte, sondern fehlende Beobachtung. ${overview.pool_size === null ? "Der Commander steht nicht in der Sammlung: zuerst die Sammlung importieren." : `Kartenpool: ${overview.pool_size} Karten.`}`),
      el("div", { class: "table-wrap" }, el("table", {},
        el("thead", {}, el("tr", {}, ["Schicht", "Zeilen", "Pool abgedeckt", "Stand", "Befehl zum Importieren"].map((label, index) => el("th", { class: index === 1 || index === 2 ? "num" : "" }, label)))),
        el("tbody", {}, rows))),
      missing.some((layer) => layer.key.startsWith("signal:")) ? el("p", { class: "note" }, "Nutzungsdaten (EDHREC, Turnierlisten, Kombos) laden: ", el("code", { class: "cmd" }, overview.signals_command)) : null,
      el("p", { class: "note" }, `Ein Aufruf mit allen Dateien: ${overview.doc}. Unter Windows kommt vor „import-all“ die Option --data "$env:LOCALAPPDATA\\CommanderStudio".`)));
  }

  return { recall, remember, el, toast, fail, germanError, request, busy, loading, skeleton, limitNumber, dataState, effectiveTheme, applyTheme };
})();
