"use strict";
/* BUILD-Werkbank: work modes (Sammeln, Bauen, Analysieren), the resizable split between pool and
   deck, the colour-identity theme of the chosen commander, the icon tab rail, the command mode of
   the quick search (">") and the shortcut sheet. Pure view layer: it never changes the deck itself,
   it only calls the page's own functions (or clicks its own buttons, so every guard still holds).
   All text is set as text, never as HTML. */
const StudioWorkbench = (() => {
  const MODE_KEY = "studio.builder.workbench-mode";
  const WIDTH_KEY = "studio.builder.deck-width";
  const MODES = ["collect", "build", "analyze"];
  const MODE_NAMES = { collect: "Sammeln", build: "Bauen", analyze: "Analysieren" };
  const MODE_HINTS = {
    collect: "Pool groß, Deck als schmales Dock: Karten finden und einsammeln",
    build: "Pool und Deck nebeneinander, Breite per Teiler verstellbar",
    analyze: "Deck und Auswertungen über die ganze Breite",
  };
  const MIN_DECK = 320;
  const MIN_POOL = 360;
  const STEP = 32;

  // Colour of each identity letter, tuned to read on the dark and the light scheme.
  const IDENTITY_HEX = { W: "#e9d9a6", U: "#3f8fe0", B: "#8d6cc0", R: "#e2553f", G: "#3aa568", C: "#a3acb9" };
  const IDENTITY_NAMES = { W: "Weiß", U: "Blau", B: "Schwarz", R: "Rot", G: "Grün", C: "farblos" };
  const WUBRG = ["W", "U", "B", "R", "G"];

  // Icon and one-line purpose of each deck tab; the label itself stays with the page.
  const TAB_INFO = {
    list: ["▤", "Deckliste, Stapel und Kurve"],
    state: ["◎", "Zustand des Decks auf einen Blick"],
    numbers: ["∑", "Manakurve, Typen und Länder"],
    evidence: ["◆", "Belege aus Quelldecks"],
    plan: ["✎", "Bauplan nach Rollen"],
    packages: ["▣", "Pakete und Upgrade-Kandidaten"],
    check: ["✓", "Regel- und Datenprüfung"],
    facts: ["⚖", "Bracket-Signale und Lücken"],
    tokens: ["◌", "Spielsteine des Decks"],
    compare: ["⇆", "Aufbau im Vergleich zu Quelldecks"],
    similar: ["≈", "Ähnliche Decks im Korpus"],
    diff: ["±", "Unterschied zwischen Varianten"],
    modules: ["⬡", "Module und Synergie-Gruppen"],
    primer: ["❡", "Primer und Notizen"],
    cut: ["✂", "Kürzen auf 100 Karten"],
    sim: ["▶", "Simulationsserien"],
  };

  // ---------- pure helpers (tested with node) ----------
  function normalizeMode(value) {
    return MODES.includes(value) ? value : "build";
  }

  function identityLetters(colors) {
    const text = String(colors || "").toUpperCase();
    const found = WUBRG.filter((letter) => text.includes(letter));
    return found.length ? found : ["C"];
  }

  function identityHex(colors) {
    return identityLetters(colors).map((letter) => IDENTITY_HEX[letter]);
  }

  function identityGradient(colors) {
    const hex = identityHex(colors);
    if (hex.length === 1) return `linear-gradient(90deg, ${hex[0]}, ${hex[0]})`;
    const stops = hex.map((value, idx) => `${value} ${Math.round((100 * idx) / (hex.length - 1))}%`);
    return `linear-gradient(90deg, ${stops.join(", ")})`;
  }

  function identityLabel(colors) {
    return identityLetters(colors).map((letter) => IDENTITY_NAMES[letter]).join(", ");
  }

  // Deck column width in pixels, kept so that both pool and deck stay usable.
  function clampDeckWidth(px, mainWidth) {
    const width = Number(mainWidth) || 0;
    const max = Math.max(MIN_DECK, width - MIN_POOL);
    const value = Number(px);
    if (!Number.isFinite(value)) return null;
    return Math.round(Math.min(max, Math.max(MIN_DECK, value)));
  }

  // Commands for the quick search: every word of the query must occur in label or hint.
  function rankActions(actions, query) {
    const words = String(query || "").replace(/^\s*>/, "").trim().toLowerCase().split(/\s+/).filter(Boolean);
    const list = (actions || []).filter((action) => action && action.label);
    if (!words.length) return list.slice();
    const scored = [];
    list.forEach((action, idx) => {
      const label = action.label.toLowerCase();
      const hay = `${label} ${String(action.hint || "").toLowerCase()} ${String(action.group || "").toLowerCase()}`;
      if (!words.every((word) => hay.includes(word))) return;
      const tier = label.startsWith(words[0]) ? 0 : label.includes(words[0]) ? 1 : 2;
      scored.push([tier, idx, action]);
    });
    scored.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
    return scored.map((item) => item[2]);
  }

  // ---------- DOM ----------
  let deps = null;
  let mode = "build";
  let helpEl = null;
  let lastIdentity = null;

  const byId = (id) => (typeof document !== "undefined" ? document.getElementById(id) : null);
  const recall = (key, fallback) => (typeof StudioUI !== "undefined" ? StudioUI.recall(key, fallback) : fallback);
  const remember = (key, value) => { if (typeof StudioUI !== "undefined") StudioUI.remember(key, value); };
  const isTyping = (el) => {
    if (!el) return false;
    const tag = el.tagName;
    return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable;
  };

  function clickButton(id) {
    const button = byId(id);
    if (!button) return false;
    if (button.disabled) {
      if (deps && deps.toast) deps.toast(id === "save" ? "Nichts zu speichern: der Entwurf entspricht dem gespeicherten Stand." : "Gerade nicht verfügbar.");
      return false;
    }
    button.click();
    return true;
  }

  function setMode(next, { quiet = false } = {}) {
    mode = normalizeMode(next);
    const body = document.body;
    for (const m of MODES) body.classList.toggle(`wb-mode-${m}`, m === mode);
    for (const button of document.querySelectorAll("#wb-modes [data-mode]")) {
      const on = button.dataset.mode === mode;
      button.classList.toggle("on", on);
      button.setAttribute("aria-pressed", on ? "true" : "false");
    }
    remember(MODE_KEY, mode);
    // The dock of "Sammeln" has no tab rail: it always shows the deck list.
    if (mode === "collect" && deps && deps.currentTab && deps.currentTab() !== "list" && deps.setTab) deps.setTab("list");
    applyDeckWidth();
    if (!quiet && deps && deps.toast) deps.toast(`Arbeitsmodus: ${MODE_NAMES[mode]}`);
  }

  function getMode() { return mode; }

  function mainEl() { return document.querySelector("body.build-studio main"); }

  function applyDeckWidth() {
    const main = mainEl();
    if (!main) return;
    const stored = Number(recall(WIDTH_KEY, ""));
    const width = stored ? clampDeckWidth(stored, main.clientWidth) : null;
    if (width) main.style.setProperty("--wb-deck-w", `${width}px`);
    else main.style.removeProperty("--wb-deck-w");
    const splitter = byId("wb-splitter");
    if (splitter) {
      const deck = byId("deck");
      const now = deck ? Math.round(deck.getBoundingClientRect().width) : 0;
      splitter.setAttribute("aria-valuenow", String(width || now || MIN_DECK));
      splitter.setAttribute("aria-valuemin", String(MIN_DECK));
      splitter.setAttribute("aria-valuemax", String(Math.max(MIN_DECK, main.clientWidth - MIN_POOL)));
    }
  }

  function storeDeckWidth(px) {
    const main = mainEl();
    if (!main) return;
    const width = clampDeckWidth(px, main.clientWidth);
    if (!width) return;
    remember(WIDTH_KEY, String(width));
    applyDeckWidth();
  }

  function resetDeckWidth() {
    remember(WIDTH_KEY, "");
    applyDeckWidth();
  }

  function setupSplitter() {
    const main = mainEl();
    const deck = byId("deck");
    if (!main || !deck || byId("wb-splitter")) return;
    const splitter = deps.h("div", {
      id: "wb-splitter",
      role: "separator",
      tabindex: "0",
      "aria-orientation": "vertical",
      "aria-label": "Breite von Pool und Deck verstellen (Pfeiltasten, Doppelklick setzt zurück)",
      title: "Ziehen: Breite verstellen · Doppelklick: zurücksetzen",
    }, deps.h("span", { class: "wb-grip" }));
    main.insertBefore(splitter, deck);
    let dragging = false;
    const onMove = (event) => {
      if (!dragging) return;
      const rect = main.getBoundingClientRect();
      storeDeckWidth(rect.right - event.clientX);
    };
    const stop = () => {
      if (!dragging) return;
      dragging = false;
      document.body.classList.remove("wb-resizing");
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", stop);
    };
    splitter.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      event.preventDefault();
      dragging = true;
      document.body.classList.add("wb-resizing");
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", stop);
    });
    splitter.addEventListener("dblclick", resetDeckWidth);
    splitter.addEventListener("keydown", (event) => {
      const current = Math.round(deck.getBoundingClientRect().width);
      if (event.key === "ArrowLeft") { event.preventDefault(); storeDeckWidth(current + STEP); }
      else if (event.key === "ArrowRight") { event.preventDefault(); storeDeckWidth(current - STEP); }
      else if (event.key === "Home" || event.key === "Enter") { event.preventDefault(); resetDeckWidth(); }
    });
    window.addEventListener("resize", applyDeckWidth);
  }

  // Colour identity of the commander as page theme: a gradient line, tinted backdrops and pips.
  function applyIdentity(commanderCard) {
    const colors = commanderCard ? commanderCard.colors || "" : null;
    const key = colors === null ? "" : identityLetters(colors).join("");
    if (key === lastIdentity) return;
    lastIdentity = key;
    const body = document.body;
    if (colors === null) {
      for (const name of ["--wb-identity", "--wb-c1", "--wb-c2", "--wb-c3"]) body.style.removeProperty(name);
      body.classList.remove("wb-has-identity");
    } else {
      const hex = identityHex(colors);
      body.style.setProperty("--wb-identity", identityGradient(colors));
      body.style.setProperty("--wb-c1", hex[0]);
      body.style.setProperty("--wb-c2", hex[1 % hex.length]);
      body.style.setProperty("--wb-c3", hex[hex.length - 1]);
      body.classList.add("wb-has-identity");
    }
    const pips = byId("wb-identity");
    if (pips) {
      if (colors === null) {
        pips.replaceChildren();
        pips.hidden = true;
      } else {
        const letters = identityLetters(colors);
        pips.hidden = false;
        pips.title = `Farbidentität des Commanders: ${identityLabel(colors)}`;
        pips.setAttribute("aria-label", pips.title);
        pips.replaceChildren(...letters.map((letter) => deps.h("span", { class: `wb-pip wb-pip-${letter}` }, letter)));
      }
    }
  }

  // Icons and purpose lines for the tab rail; the page draws the buttons with data-tab.
  function decorateTabs(container) {
    if (!container) return;
    for (const button of container.querySelectorAll("button[data-tab]")) {
      if (button.dataset.wbDone) continue;
      const info = TAB_INFO[button.dataset.tab];
      if (!info) continue;
      const label = button.textContent;
      button.dataset.wbDone = "1";
      button.title = `${label}: ${info[1]}`;
      button.replaceChildren(
        deps.h("span", { class: "wb-tab-icon", "aria-hidden": "true" }, info[0]),
        deps.h("span", { class: "wb-tab-text" },
          deps.h("span", { class: "wb-tab-label" }, label),
          deps.h("span", { class: "wb-tab-desc" }, info[1])));
    }
  }

  function tabActions() {
    const actions = [];
    for (const button of document.querySelectorAll("#deck-tabs button[data-tab]")) {
      const key = button.dataset.tab;
      const label = button.querySelector(".wb-tab-label") ? button.querySelector(".wb-tab-label").textContent : button.textContent;
      const info = TAB_INFO[key];
      actions.push({
        id: `tab:${key}`,
        group: "Ansicht",
        label: `Ansicht: ${label}`,
        hint: info ? info[1] : "",
        icon: info ? info[0] : "›",
        run: () => {
          if (mode === "collect") setMode("build", { quiet: true });
          if (deps.setTab) deps.setTab(key);
        },
      });
    }
    return actions;
  }

  function actions() {
    if (!deps) return [];
    const list = MODES.map((m, idx) => ({
      id: `mode:${m}`, group: "Arbeitsmodus", label: `Arbeitsmodus: ${MODE_NAMES[m]}`, hint: MODE_HINTS[m], keys: `Alt ${idx + 1}`, icon: ["◧", "◫", "◨"][idx],
      run: () => setMode(m),
    }));
    list.push(
      { id: "save", group: "Deck", label: "Als Stand speichern", hint: "Entwurf als neuen Stand sichern", keys: "Strg S", icon: "⤓", run: () => clickButton("save") },
      { id: "play", group: "Deck", label: "Mit diesem Stand eine Partie spielen", hint: "Partien öffnen", icon: "▶", run: () => clickButton("play-state") },
      { id: "history", group: "Deck", label: "Verlauf öffnen", hint: "Gespeicherte Stände", icon: "↺", run: () => clickButton("history") },
      { id: "export", group: "Deck", label: "Export", hint: "Deckliste ausgeben", icon: "⇪", run: () => clickButton("export") },
      { id: "labels", group: "Deck", label: "Archetyp-Marken bearbeiten", hint: "Marken", icon: "#", run: () => clickButton("deck-labels") },
      { id: "new-branch", group: "Deck", label: "Neue Variante", hint: "Variante abzweigen", icon: "⑂", run: () => clickButton("new-branch") },
      { id: "new-deck", group: "Deck", label: "Neues Deck", hint: "leeres Deck anlegen", icon: "+", run: () => clickButton("new-deck") },
      { id: "import", group: "Deck", label: "Deckliste einfügen", hint: "Text importieren", icon: "⎘", run: () => clickButton("import-text") },
      { id: "search", group: "Pool", label: "Pool durchsuchen", hint: "Suchfeld der Sammlung", keys: "F", icon: "⌕", run: () => focusPoolSearch() },
      { id: "theme", group: "Ansicht", label: "Hell / dunkel umschalten", hint: "Farbschema", icon: "◐", run: () => clickButton("theme-toggle") },
      { id: "width", group: "Ansicht", label: "Breite von Pool und Deck zurücksetzen", hint: "Teiler", icon: "↔", run: () => resetDeckWidth() },
      { id: "help", group: "Hilfe", label: "Tastenkürzel zeigen", hint: "Übersicht", keys: "?", icon: "?", run: () => openHelp() },
    );
    return list.concat(tabActions());
  }

  function focusPoolSearch() {
    if (mode === "analyze") setMode("build", { quiet: true });
    const q = byId("q");
    if (q) { q.focus(); q.select(); }
  }

  const SHORTCUTS = [
    ["Strg K oder /", "Karte schnell suchen und hinzufügen"],
    ["Strg Umschalt K oder >", "Befehle: Ansichten, Speichern, Export …"],
    ["Alt 1 · Alt 2 · Alt 3", "Arbeitsmodus Sammeln · Bauen · Analysieren"],
    ["Strg S", "Als Stand speichern"],
    ["F", "Pool durchsuchen"],
    ["[ und ]", "vorige / nächste Deck-Ansicht"],
    ["Pfeiltasten am Teiler", "Breite von Pool und Deck"],
    ["?", "diese Übersicht"],
    ["Esc", "schließen"],
  ];

  function openHelp() {
    const h = deps.h;
    if (!helpEl) {
      helpEl = h("div", { id: "wb-help", hidden: true, onclick: closeHelp },
        h("div", { class: "wb-help-panel", role: "dialog", "aria-modal": "true", "aria-label": "Tastenkürzel", onclick: (event) => event.stopPropagation() },
          h("div", { class: "wb-help-head" }, h("strong", {}, "Tastenkürzel der Werkbank"), h("button", { type: "button", class: "ghost", onclick: closeHelp }, "Esc")),
          h("dl", { class: "wb-help-list" }, ...SHORTCUTS.flatMap(([keys, text]) => [h("dt", {}, h("kbd", {}, keys)), h("dd", {}, text)])),
          h("p", { class: "muted wb-help-foot" }, "Arbeitsmodus und Teilerbreite merkt sich nur dieser Browser; am Deck ändert sich dadurch nichts.")));
      document.body.append(helpEl);
    }
    helpEl.hidden = false;
    const close = helpEl.querySelector("button");
    if (close) close.focus();
  }

  function closeHelp() {
    if (helpEl && !helpEl.hidden) { helpEl.hidden = true; return true; }
    return false;
  }

  function stepTab(direction) {
    const buttons = [...document.querySelectorAll("#deck-tabs button[data-tab]")];
    if (!buttons.length || !deps.setTab || !deps.currentTab) return;
    const idx = Math.max(0, buttons.findIndex((b) => b.dataset.tab === deps.currentTab()));
    const next = buttons[(idx + direction + buttons.length) % buttons.length];
    if (mode === "collect") setMode("build", { quiet: true });
    deps.setTab(next.dataset.tab);
    const again = document.querySelector(`#deck-tabs button[data-tab="${next.dataset.tab}"]`);
    if (again) again.focus();
  }

  function onKey(event) {
    if (event.defaultPrevented) return;
    const typing = isTyping(document.activeElement);
    const modalOpen = byId("modal") && !byId("modal").hidden;
    if (event.key === "Escape" && closeHelp()) { event.preventDefault(); return; }
    if ((event.ctrlKey || event.metaKey) && !event.altKey && !event.shiftKey && event.key.toLowerCase() === "s") {
      event.preventDefault();
      // An open dialog (card window, input) keeps its own focus; the draft is saved from the page.
      if (!modalOpen) clickButton("save");
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === "k") {
      event.preventDefault();
      event.stopImmediatePropagation();
      openCommands();
      return;
    }
    if (event.altKey && !event.ctrlKey && !event.metaKey && ["1", "2", "3"].includes(event.key)) {
      event.preventDefault();
      setMode(MODES[Number(event.key) - 1]);
      return;
    }
    if (typing || modalOpen || event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.key === "?") { event.preventDefault(); openHelp(); }
    else if (event.key === ">") { event.preventDefault(); openCommands(); }
    else if (event.key === "f" || event.key === "F") { event.preventDefault(); focusPoolSearch(); }
    else if (event.key === "[") { event.preventDefault(); stepTab(-1); }
    else if (event.key === "]") { event.preventDefault(); stepTab(1); }
  }

  function openCommands() {
    if (typeof StudioDeckHud !== "undefined" && StudioDeckHud.open) StudioDeckHud.open(">");
  }

  function setup(pageDeps) {
    deps = pageDeps;
    if (!document.body.classList.contains("build-studio")) return;
    for (const button of document.querySelectorAll("#wb-modes [data-mode]")) {
      const m = button.dataset.mode;
      button.title = `${MODE_NAMES[m]}: ${MODE_HINTS[m]} (Alt ${MODES.indexOf(m) + 1})`;
      button.addEventListener("click", () => setMode(m, { quiet: true }));
    }
    const commandsButton = byId("wb-commands");
    if (commandsButton) commandsButton.addEventListener("click", openCommands);
    const helpButton = byId("wb-help-open");
    if (helpButton) helpButton.addEventListener("click", openHelp);
    setupSplitter();
    // Capture phase: Strg Umschalt K must reach the command mode before the quick search's Strg K.
    document.addEventListener("keydown", onKey, true);
    if (typeof StudioDeckHud !== "undefined" && StudioDeckHud.setActionProvider) StudioDeckHud.setActionProvider(actions);
    setMode(recall(MODE_KEY, "build"), { quiet: true });
  }

  // Apply the remembered mode at once, so the page does not jump when the data arrives.
  if (typeof document !== "undefined" && document.body && document.body.classList.contains("build-studio")) {
    setMode(recall(MODE_KEY, "build"), { quiet: true });
  }

  return {
    MODES, MODE_NAMES, TAB_INFO, IDENTITY_HEX,
    normalizeMode, identityLetters, identityHex, identityGradient, identityLabel, clampDeckWidth, rankActions,
    setup, setMode, getMode, applyIdentity, decorateTabs, actions, openHelp, closeHelp,
  };
})();

if (typeof module !== "undefined") module.exports = StudioWorkbench;
