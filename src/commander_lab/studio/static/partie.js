"use strict";
// Spectator view of a recorded game. The page only shows what the rules engine published
// and what the pilots chose; it never works out a rule itself.

const PHASES = { beginning: "Beginn", precombat_main: "Hauptphase 1", combat: "Kampf", postcombat_main: "Hauptphase 2", end: "Ende" };
const STEPS = { untap: "Enttappen", upkeep: "Versorgung", draw: "Ziehen", precombat_main: "Hauptphase 1", begin_combat: "Kampfbeginn", declare_attackers: "Angreifer", declare_blockers: "Blocker", first_combat_damage: "Erstschlagschaden", combat_damage: "Kampfschaden", end_combat: "Kampfende", postcombat_main: "Hauptphase 2", end_turn: "Endsegment", cleanup: "Aufräumen" };
const CLASSES = { priority: "Aktion", mana_payment: "Mana zahlen", choose_object: "Auswahl", choose_use: "Ja oder Nein", target: "Ziel", declare_attacker: "Angriff", declare_blocker: "Block", mulligan: "Mulligan", choice: "Wahl", trigger_order: "Reihenfolge", announce_x: "Wert für X", amount: "Anzahl", multi_amount: "Verteilung", mode: "Modus", pile: "Stapelwahl", target_amount: "Zielmenge", replacement_effect: "Ersatzeffekt", order: "Reihenfolge" };
// Table sizes the new-game dialog offers, as numbers of opponents. Two locks, as on the server:
// a game with a human seat follows launch.MAX_RELEASED_PLAY_SEATS, a game of AI seats only follows
// launch.MAX_RELEASED_SEATS (the SIMULATE lock, like the series dialog in paired.js), but on this page only
// up to launch.MAX_PARTIE_SEATS (six: the board ends there; seven and eight seats, E18 #1672, run as series
// only). A size above its lock is not offered and the dialog says so; the server refuses it too. Five and
// six seats are released (conditional Owner go of 2026-11-22, register E16); a guard test keeps both lists
// equal to the server locks.
const OPPONENT_COUNTS_PLAY = [1, 2, 3, 4, 5];
const OPPONENT_COUNTS_AI = [1, 2, 3, 4, 5];
const OPPONENT_COUNTS_MAX = 5; // six seats: the most this page shows (launch.MAX_PARTIE_SEATS)

const DEFAULT_AI_DELAY_MS = 250;
const SPEEDS = [[2000, "langsam"], [1000, "1 pro Sekunde"], [500, "2 pro Sekunde"], [250, "250 ms (sichtbare KI-Schritte)"], [120, "8 pro Sekunde"], [50, "sehr schnell"], [0, "ohne Pause"]];

const POOL_COLORS = { white: "Weiß", blue: "Blau", black: "Schwarz", red: "Rot", green: "Grün", colorless: "Farblos" };
const OPTION_TYPES = { pass_priority: "Passen", play_land: "Land spielen", cast_spell: "Zauber wirken", activated_ability: "Fähigkeit aktivieren", mana_ability: "Mana-Fähigkeit", special_action: "Sonderaktion", target: "Ziel", choose_object: "Objekt wählen", attacker: "Angreifer", blocker: "Blocker", mode: "Modus", choice: "Auswahl", mana_payment: "Mana", trigger_order: "Auslöser", yes: "Ja", no: "Nein" };

const state = { cohortRecord: null, click: null, clickActive: false, menu: null, openZone: null, games: [], gameId: null, header: null, result: null, running: false, interactive: false, humanSeats: [], pendingDecision: null, pendingDecisionId: null, selectedOptions: [], orderList: [], submitting: false, canConcede: false, handsRevealed: false, autoPassAttempt: null, pollFailures: 0, revision: null, followGen: 0, foreground: 0, pollAbort: null, renderedKey: null, ownCombat: StudioPlayP1a.emptyCombatLedger(), ff: { on: false, boosted: false, mode: "until_my_turn", startTurn: null, stopOnOpponentStack: true, watchStackObjectId: null }, frames: [], index: 0, playing: false, timer: 0, facts: {}, noImage: new Set(), lines: [], seatKeys: [], poll: 0 };

const $ = (id) => document.getElementById(id);
function h(tag, props, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(props || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") el.className = value;
    else if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else if (key in el) el[key] = value;
    else el.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return el;
}
async function api(path, method = "GET", body, signal) {
  const options = { method, headers: { "X-Studio": "1" } };
  if (signal) options.signal = signal;
  if (body !== undefined) { options.headers["Content-Type"] = "application/json"; options.body = JSON.stringify(body); }
  const response = await fetch(path, options);
  if (!response.ok) {
    let detail = response.statusText;
    try { detail = (await response.json()).detail || detail; } catch (error) { /* keep status text */ }
    const failure = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    failure.status = response.status;
    throw failure;
  }
  return response.json();
}
let toastTimer = 0;
function toast(text, milliseconds = 3500) {
  const box = $("toast"); box.textContent = text; box.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { box.hidden = true; }, milliseconds);
}

const seatName = (seat) => (seat === null || seat === undefined ? "?" : `Sitz ${seat + 1}`);
// The pill in the header says what the open game is, from the server's reading of the game log
// (`cohort`, `played_seats`, `table_size`; StudioCohort). Nothing is guessed here: with no record yet it claims
// nothing, and an unreadable origin is never worded as a simulation (#1662).
function renderCohortPill() {
  const pill = $("sim-pill");
  const view = StudioCohort.pill(state.cohortRecord);
  pill.className = view.cls;
  pill.title = view.title;
  pill.textContent = view.text;
}
function seatInfo(seat) { return ((state.header && state.header.seats) || []).find((entry) => entry.seat === seat) || {}; }
function seatLabel(seat) {
  const info = seatInfo(seat);
  return info.commanders && info.commanders.length ? info.commanders.join(" + ") : (info.deck_id || seatName(seat));
}
const { isPass, isMinor } = StudioReplay; // one definition, shared with replay.js
function isLand(name) { const fact = state.facts[name]; return Boolean(fact && fact.type_line && fact.type_line.split("//")[0].includes("Land")); }
function isCreature(name, card) {
  const fact = state.facts[name];
  if (fact && fact.type_line) return fact.type_line.includes("Creature") || fact.type_line.includes("Vehicle");
  return Boolean(card && (card.power || card.toughness));
}

function localizeActionText(text) {
  if (!text) return "";
  // labels may carry the engine's reminder markup; the page shows text only
  let s = text.replace(/<[^>]*>/g, "").replace(/Full Game Seat (\d)/g, "Sitz $1");
  const pool = /^Spend (\w+) mana from pool$/.exec(s);
  if (pool) s = `Mana aus dem Pool ausgeben: ${POOL_COLORS[pool[1].toLowerCase()] || pool[1]}`;
  if (s.startsWith("Play ")) s = "Spiele " + s.slice(5);
  else if (s.startsWith("Cast ")) s = "Wirke " + s.slice(5);
  else if (s.startsWith("Activate: ")) s = "Aktiviere: " + s.slice(10);
  else if (s.startsWith("Activate ")) s = "Aktiviere " + s.slice(9);
  else if (s.startsWith("Discard ")) s = "Wirf ab: " + s.slice(8);
  else if (s === "Pass priority") s = "Priorität abgeben";
  else if (s === "Cancel mana payment") s = "Zahlung abbrechen";
  else if (s.startsWith("Do not attack with ")) s = `${s.slice(19)} greift nicht an`;
  if (s.includes(" attacks ")) {
    const [att, def] = s.split(" attacks ", 2);
    s = `${att} greift ${def} an`;
  } else if (s.includes(" blocks ")) {
    const [blk, att] = s.split(" blocks ", 2);
    s = `${blk} blockt ${att}`;
  }
  return s;
}

function answer(frame) {
  if (isPass(frame)) return "passt";
  const parts = [...frame.chosen];
  if (frame.numeric_choice !== undefined) parts.push(String(frame.numeric_choice));
  if (Array.isArray(frame.numeric_choices)) parts.push(frame.numeric_choices.join(", "));
  if (frame.decision_class === "mulligan") return parts[0] === "Take mulligan" ? "nimmt einen Mulligan" : "behält die Hand";
  if (frame.private_selection && !parts.length) return "wählt verdeckt (bis zum Spielende nicht sichtbar)";
  if (frame.decision_class === "declare_blocker" && !parts.length) return "blockt nicht";
  if (frame.decision_class === "declare_attacker" && !parts.length) return "greift nicht an";
  if (frame.decision_class === "choose_use" && parts.length === 1) return `${frame.prompt} ${parts[0] === "Yes" ? "Ja" : parts[0] === "No" ? "Nein" : parts[0]}`;
  if (!parts.length) return "wählt nichts";
  const text = parts.map((part) => {
    const clean = part.includes(" — ") ? part.split(" — ").slice(1).join(" — ").replace("{this}", part.split(" — ")[0]) : part;
    return localizeActionText(clean);
  }).join("; ");
  return frame.decision_class === "priority" ? text : `${CLASSES[frame.decision_class] || frame.decision_class}: ${text}`;
}

// ---- board clicks (boardclick.js maps, the engine decides) -----------------------------------------
// A card or a player field is clickable only if the pending decision offers an option for it; a click
// sends exactly that option's id (one unique option), toggles it (several to choose from, the page
// confirms) or opens a menu of the offered options. Nothing here answers a decision by itself.
const SELECTING_KINDS = ["target", "attacker", "blocker", "trigger_order", "mana_payment"];
const SVG_NS = "http://www.w3.org/2000/svg";
function offeredOption(optionId) {
  const options = (state.pendingDecision && state.pendingDecision.legal_options) || [];
  return options.find((option) => String(option.option_id) === optionId) || null;
}
function clickEntry(objectId) { return state.clickActive && objectId ? (state.click.objects[objectId] || null) : null; }
function seatEntry(seat) { return state.clickActive ? (state.click.seats[String(seat)] || null) : null; }
// A decision whose options sit off the board (a library card, a number) lights nothing up and dims nothing.
function boardHasClickables(model) { return Object.keys(model.objects).length > 0 || Object.keys(model.seats).length > 0; }
function clickDimmed(objectId) { return state.clickActive && Boolean(objectId) && SELECTING_KINDS.includes(state.click.kind) && boardHasClickables(state.click) && !state.click.objects[objectId]; }
function clickAction(target) {
  if (!state.clickActive) return "none";
  return StudioBoardClick.resolve(state.pendingDecision, state.click, target).action;
}
function objectName(objectId) {
  const pilot = state.pendingDecision && state.pendingDecision.pilot_state;
  if (!pilot || !objectId) return null;
  const rows = [];
  for (const player of pilot.players || []) for (const zone of ["battlefield", "hand", "command", "graveyard", "exile"]) rows.push(...(player[zone] || []));
  rows.push(...(pilot.stack || []));
  const found = rows.find((row) => row && row.object_id === objectId);
  return found && !found.face_down && found.name ? found.name : null;
}
function entryPicked(entry) { return Boolean(entry) && entry.optionIds.some((id) => state.selectedOptions.includes(id)); }
function clickAria(name, entry) {
  const who = name === "(verdeckt)" ? "Verdeckte Karte" : name;
  const options = entry.optionIds.map(offeredOption).filter(Boolean);
  if (entry.role === "asked") return `${who}: die Engine fragt jetzt nach dieser Kreatur. Menü mit ${options.length} Möglichkeiten öffnen`;
  if (options.length !== 1) return `${who}: ${options.length} Möglichkeiten, Menü öffnen`;
  const label = localizeActionText(options[0].label || options[0].option_id);
  if (state.click.mode === "staged") return `${who}: ${entryPicked(entry) ? "Auswahl aufheben" : "auswählen"} (${label})`;
  return label;
}
function clickBadge(objectId, entry) {
  if (!entry) return null;
  const picked = entryPicked(entry);
  if (entry.role === "asked") {
    if (state.click.kind === "blocker") return state.selectedOptions.length ? "🛡️ blockt" : "🛡️ blockt?";
    return "⚔️ greift an?";
  }
  if (entry.role === "block-target" && picked) return "🛡️ geblockt";
  if (entry.role === "defender") return "🎯 Angriffsziel";
  if (entry.role === "target" && picked) return "🎯 gewählt";
  if (entry.role === "source") return "⚡ Auslöser";
  return null;
}
function focusClickKey(key) {
  if (!key) return;
  const el = document.querySelector(`[data-click-key="${key}"]`);
  if (el) el.focus();
}
// The board model belongs to one decision. While a poll is still loading, the pending decision can
// already be a newer one: then no board click, menu or confirmation may answer anything.
function boardDecision() {
  const pending = state.pendingDecision;
  return pending && state.click && state.click.decisionId === pending.decision_id ? pending : null;
}
// The option list (also for decisions with a number) toggles against the pending decision itself.
function toggleOption(optionId) {
  const pending = state.pendingDecision;
  if (!pending || !offeredOption(optionId)) return;
  const maxSel = Number(pending.maximum_selections ?? 0);
  if (state.selectedOptions.includes(optionId)) state.selectedOptions = state.selectedOptions.filter((id) => id !== optionId);
  else if (maxSel <= 1) state.selectedOptions = [optionId];
  else if (state.selectedOptions.length < maxSel) state.selectedOptions = [...state.selectedOptions, optionId];
  else toast(`Höchstens ${maxSel} Auswahlen möglich.`);
  render();
}
// Takes over the decision a poll delivered. Another decision (or none) drops what was picked, opened
// or modelled for the old one at once, not only at the next render.
function adoptPendingDecision(nextDecision) {
  if (!nextDecision || !state.pendingDecision || nextDecision.decision_id !== state.pendingDecision.decision_id) {
    closeBoardMenu(false);
    state.selectedOptions = [];
    state.click = null;
    state.clickActive = false;
  }
  state.pendingDecision = nextDecision;
}
function toggleBoardOption(optionId) {
  if (boardDecision()) toggleOption(optionId);
}
function sendBoardOption(optionId) {
  const pending = boardDecision();
  if (!pending || state.submitting) return;
  if (!offeredOption(optionId)) { toast("Diese Möglichkeit bietet die Engine gerade nicht an."); return; }
  closeBoardMenu(false);
  $("modal").hidden = true;
  // the id of the decision the click was made on: the server refuses an answer to an outdated one
  submitHumanChoice({ decision_id: state.click.decisionId, selected_option_ids: [optionId], ordering: [] });
}
function confirmSelection() {
  const pending = boardDecision();
  if (!pending || state.submitting) return;
  if (!state.selectedOptions.every((id) => offeredOption(id))) { toast("Diese Auswahl bietet die Engine gerade nicht an."); return; }
  submitHumanChoice({ decision_id: state.click.decisionId, selected_option_ids: [...state.selectedOptions], ordering: [] });
}
function boardClick(target, anchor) {
  const pending = boardDecision();
  if (!state.clickActive || !pending || state.submitting) return;
  const result = StudioBoardClick.resolve(pending, state.click, target);
  const key = anchor && anchor.dataset ? anchor.dataset.clickKey : null;
  if (result.action === "send") sendBoardOption(result.optionId);
  else if (result.action === "toggle") { closeBoardMenu(false); toggleBoardOption(result.optionId); focusClickKey(key); }
  else if (result.action === "menu") openBoardMenu(anchor, result, key, target.type === "seat" ? seatName(target.seat) : (objectName(target.id) || "Karte"));
  else toast("Dafür bietet die Engine gerade keine Aktion an.");
}
function openBoardMenu(anchor, result, key, title) {
  const box = $("board-menu");
  box.textContent = "";
  box.setAttribute("aria-label", `Möglichkeiten für ${title}`);
  box.append(h("div", { class: "board-menu-title" }, title));
  for (const option of result.options) {
    const picked = result.mode === "staged" && state.selectedOptions.includes(option.optionId);
    box.append(h("button", {
      type: "button",
      role: "menuitem",
      class: `board-menu-item${picked ? " picked" : ""}`,
      onclick: () => {
        closeBoardMenu(false);
        if (result.mode === "immediate") sendBoardOption(option.optionId);
        else { toggleBoardOption(option.optionId); focusClickKey(key); }
      }
    }, `${picked ? "✓ " : ""}${localizeActionText(option.label)}`));
  }
  state.menu = { key };
  box.hidden = false;
  const rect = anchor && anchor.getBoundingClientRect ? anchor.getBoundingClientRect() : { left: 40, right: 40, top: 40, bottom: 40 };
  const width = box.offsetWidth;
  const height = box.offsetHeight;
  const below = rect.bottom + 6;
  box.style.left = `${Math.max(8, Math.min(rect.left, window.innerWidth - width - 8))}px`;
  box.style.top = `${Math.max(8, below + height > window.innerHeight - 8 ? rect.top - height - 6 : below)}px`;
  const first = box.querySelector("button");
  if (first) first.focus();
}
function closeBoardMenu(restoreFocus) {
  const box = $("board-menu");
  if (!box || box.hidden) return false;
  const key = state.menu && state.menu.key;
  box.hidden = true;
  box.textContent = "";
  state.menu = null;
  if (restoreFocus) focusClickKey(key);
  return true;
}
// Lines from the blocker the engine asks about to the attackers chosen so far.
function drawBlockLinks() {
  const svg = $("board-links");
  if (!svg) return;
  svg.textContent = "";
  if (!state.clickActive || state.click.kind !== "blocker" || !state.click.asked) return;
  const from = document.querySelector(`[data-object-id="${state.click.asked}"]`);
  if (!from) return;
  const a = from.getBoundingClientRect();
  for (const optionId of state.selectedOptions) {
    const to = document.querySelector(`[data-object-id="${optionId}"]`);
    if (!to) continue;
    const b = to.getBoundingClientRect();
    const line = document.createElementNS(SVG_NS, "line");
    line.setAttribute("class", "board-link");
    line.setAttribute("x1", String(Math.round(a.left + a.width / 2)));
    line.setAttribute("y1", String(Math.round(a.top + a.height / 2)));
    line.setAttribute("x2", String(Math.round(b.left + b.width / 2)));
    line.setAttribute("y2", String(Math.round(b.top + b.height / 2)));
    svg.append(line);
  }
}
const BAR_HINTS = {
  priority: "Klicke eine leuchtende Karte (Hand oder Brett) oder gib die Priorität ab.",
  mana_payment: "Klicke eine leuchtende Mana-Quelle.",
  target: "Klicke ein leuchtendes Ziel (Karte, Spielerfeld, Friedhof oder Exil).",
  attacker: "Klicke ein Angriffsziel oder die leuchtende Kreatur für das Menü.",
  blocker: "Klicke die Angreifer, die geblockt werden sollen, und bestätige.",
  trigger_order: "Die Quelle des Auslösers leuchtet; die Reihenfolge legst du in der Liste fest."
};
function renderBoardBar(pending, model) {
  const bar = $("board-bar");
  if (!bar) return;
  bar.textContent = "";
  if (!pending || !model || model.kind === "none") { bar.hidden = true; return; }
  const minSel = Number(pending.minimum_selections ?? 0);
  const maxSel = Number(pending.maximum_selections ?? 0);
  const askedName = model.asked ? objectName(model.asked) : null;
  const lead = askedName && (model.kind === "attacker" || model.kind === "blocker")
    ? `${CLASSES[pending.decision_class] || ""}: ${askedName}`
    : (CLASSES[pending.decision_class] || pending.decision_class);
  const hint = boardHasClickables(model) ? (BAR_HINTS[model.kind] || "") : "Die Möglichkeiten dieser Entscheidung liegen nicht auf dem Brett (zum Beispiel in der Bibliothek): wähle in der Liste.";
  bar.append(h("b", { class: "board-bar-title" }, lead), h("span", { class: "board-bar-hint" }, hint));
  if (model.mode === "staged") bar.append(h("span", { class: "board-bar-count" }, `${state.selectedOptions.length} von ${maxSel} gewählt (mindestens ${minSel})`));
  for (const optionId of model.loose) {
    const option = offeredOption(optionId);
    if (!option) continue;
    bar.append(h("button", {
      type: "button",
      class: option.option_type === "pass_priority" ? "primary" : "",
      disabled: state.submitting,
      onclick: () => (model.mode === "staged" ? toggleBoardOption(optionId) : sendBoardOption(optionId))
    }, localizeActionText(option.label || optionId)));
  }
  if (model.mode === "staged") {
    const count = state.selectedOptions.length;
    const label = count === 0 && minSel === 0 ? (model.kind === "blocker" ? "Nicht blocken" : "Bestätigen (0 gewählt)") : "Auswahl bestätigen";
    bar.append(h("button", { type: "button", class: "primary", disabled: state.submitting || count < minSel || count > maxSel, onclick: confirmSelection }, label));
  }
  bar.hidden = false;
}

// ---- cards ---------------------------------------------------------------------------------
function cardFace(name) {
  if (state.noImage.has(name) || name === "(verdeckt)") return h("div", { class: "nocard" }, name);
  const img = h("img", { alt: name, loading: "lazy", referrerpolicy: "no-referrer", src: `/img-name?name=${encodeURIComponent(name)}` });
  img.addEventListener("error", () => { state.noImage.add(name); img.replaceWith(h("div", { class: "nocard" }, name)); });
  return img;
}
function showPreview(name, event) {
  if (state.noImage.has(name) || name === "(verdeckt)") return;
  const box = $("preview");
  const img = box.firstChild;
  img.referrerPolicy = "no-referrer";
  img.onerror = () => { box.hidden = true; };
  img.src = `/img-name?name=${encodeURIComponent(name)}`;
  box.hidden = false; move(event);
}
function hover(el, name) {
  el.addEventListener("mouseenter", (event) => showPreview(name, event));
  el.addEventListener("mousemove", move);
  el.addEventListener("mouseleave", () => { $("preview").hidden = true; });
  // keyboard focus shows the same enlarged preview next to the card
  el.addEventListener("focus", () => {
    if (!el.matches(":focus-visible")) return;
    const rect = el.getBoundingClientRect();
    showPreview(name, { clientX: rect.right, clientY: rect.top + rect.height / 2 });
  });
  el.addEventListener("blur", () => { $("preview").hidden = true; });
}
function move(event) {
  const box = $("preview");
  // beside the pointer: to its right, or to its left when the right edge of the window is too close
  const right = event.clientX + 18;
  box.style.left = `${Math.max(8, right + 270 > window.innerWidth ? event.clientX - 18 - 270 : right)}px`;
  box.style.top = `${Math.max(8, Math.min(event.clientY - 120, window.innerHeight - 380))}px`;
}
function cardTile(name, options = {}) {
  const entry = clickEntry(options.objectId);
  const answerable = Boolean(entry) && clickAction({ type: "object", id: options.objectId }) !== "none";
  const picked = Boolean(entry) && entry.optionIds.some((id) => state.selectedOptions.includes(id));
  const classes = [
    "card",
    options.tapped && "tapped",
    options.small && "small",
    options.attacking && "attacking",
    options.blocking && "blocking",
    options.targeted && "targeted",
    entry && "legal",
    entry && `role-${entry.role}`,
    answerable && "clickable",
    picked && "picked",
    !entry && clickDimmed(options.objectId) && "dimmed"
  ].filter(Boolean).join(" ");
  const props = { class: classes, title: options.title || name };
  if (options.objectId) props["data-object-id"] = options.objectId;
  let el;
  if (answerable) {
    Object.assign(props, { type: "button", "data-click-key": `obj:${options.objectId}`, "aria-label": clickAria(name, entry), onclick: (event) => boardClick({ type: "object", id: options.objectId }, event.currentTarget) });
    el = h("button", props, cardFace(name));
  } else {
    el = h("div", props, cardFace(name));
  }
  if (options.count > 1) el.append(h("span", { class: "badge count" }, `×${options.count}`));
  if (options.pt) el.append(h("span", { class: `badge pt${options.damage ? " hurt" : ""}` }, options.pt));
  if (options.counters) el.append(h("span", { class: "badge counter" }, options.counters));
  const badge = options.combatBadge || clickBadge(options.objectId, entry);
  if (badge) {
    const bClass = `badge combat${options.blocking ? " blocking" : ""}${options.targeted ? " targeted" : ""}`;
    el.append(h("span", { class: bClass, title: badge }, badge));
  }
  hover(el, name);
  return el;
}
function grouped(cards) {
  // identical permanents (same name, same state) share one tile with a count; a permanent the
  // current decision points at stays its own tile, so a click never has to guess between twins
  const groups = new Map();
  for (const card of cards) {
    const own = state.clickActive && card.object_id && state.click.objects[card.object_id] ? card.object_id : null;
    const key = JSON.stringify([card.name, card.tapped, card.power, card.toughness, card.damage, card.counters || null, own]);
    const entry = groups.get(key) || { card, count: 0 };
    entry.count += 1; groups.set(key, entry);
  }
  return [...groups.values()];
}
function permanentTile({ card, count }, frame) {
  const counters = card.counters ? Object.entries(card.counters).map(([type, amount]) => `${amount} ${type}`).join(", ") : null;
  const pt = isCreature(card.name, card) ? `${card.power}/${card.toughness}${card.damage ? ` −${card.damage}` : ""}` : null;
  let attacking = false;
  let blocking = false;
  let targeted = false;
  let combatBadge = null;
  if (frame) {
    if (frame.combat) {
      const atk = (frame.combat.attacks || []).find((a) => a.attacker === card.name);
      if (atk) {
        attacking = true;
        combatBadge = `⚔️ ${atk.target}`;
      }
      const blk = (frame.combat.blocks || []).find((b) => b.blocker === card.name);
      if (blk) {
        blocking = true;
        combatBadge = `🛡️ ${blk.attacker}`;
      }
    }
    if (frame.targets && frame.targets.includes(card.name)) {
      targeted = true;
      combatBadge = "🎯 Ziel";
    }
  }
  return cardTile(card.name, {
    tapped: card.tapped,
    count,
    pt,
    damage: card.damage,
    counters,
    attacking,
    blocking,
    targeted,
    combatBadge,
    objectId: count === 1 ? card.object_id : null
  });
}

// ---- table ---------------------------------------------------------------------------------
function seatPanel(player, frame) {
  const info = seatInfo(player.seat);
  const winners = (state.result && state.result.winner_seats) || [];
  const last = state.index === state.frames.length - 1 && !state.running;
  const isTargetSeat = Boolean(
    frame.combat &&
    (frame.combat.attacks || []).some((atk) => {
      const tgt = atk.target || "";
      // the engine names a player "Full Game Seat N" with N = seat + 1 (the bridge's seat names);
      // a 0-based reading would also mark the seat after the attacked one (#1661)
      return (
        tgt === `Sitz ${player.seat + 1}` ||
        tgt === `Full Game Seat ${player.seat + 1}` ||
        tgt === `p${player.seat}` ||
        tgt === `Seat ${player.seat}` ||
        tgt === `Seat ${player.seat + 1}`
      );
    })
  );
  const humanPending = Boolean(state.interactive && state.pendingDecision && state.pendingDecision.seat === player.seat);
  const seatClick = seatEntry(player.seat);
  const seatAnswerable = Boolean(seatClick) && clickAction({ type: "seat", seat: player.seat }) !== "none";
  const inZone = (zone) => state.clickActive && Object.values(state.click.objects).some((entry) => entry.zone === zone && entry.seat === player.seat);
  const classes = [
    "seat",
    seatAnswerable && "targetable",
    entryPicked(seatClick) && "picked",
    frame.active_seat === player.seat && "active",
    frame.seat === player.seat && "acting",
    humanPending && "human-turn",
    isTargetSeat && "attacked",
    player.lost && "out",
    last && winners.includes(player.seat) && "winner"
  ].filter(Boolean).join(" ");
  const lands = grouped(player.battlefield.filter((card) => isLand(card.name)));
  const others = grouped(player.battlefield.filter((card) => !isLand(card.name)));
  const yard = h("button", { type: "button", class: `stat link${inZone("graveyard") ? " zone-legal" : ""}`, title: "Friedhof ansehen", onclick: () => showZone(player, "graveyard") }, `Friedhof ${player.graveyard.length}`);
  const exileList = player.exile || [];
  const exileCount = player.exile_count || exileList.length;
  const exileStat = exileCount
    ? h("button", {
        type: "button",
        class: `stat link${inZone("exile") ? " zone-legal" : ""}`,
        title: "Exil ansehen",
        onclick: () => showZone(player, "exile")
      }, `Exil ${exileCount}`)
    : null;
  return h("div", { class: classes },
    h("div", { class: "seat-head" },
      h("span", { class: `life${player.life !== null && player.life <= 10 ? " low" : ""}` }, player.life === null ? "?" : player.life),
      h("b", { class: `s${player.seat}` }, seatName(player.seat)),
      h("span", null, seatLabel(player.seat)),
      h("span", { class: "muted" }, info.deck_id || ""),
      info.pilot === "Mensch" && h("span", { class: "pill good", title: "Von dir gesteuert" }, "Mensch"),
      humanPending && h("span", { class: "pill warn" }, "Du bist am Zug!"),
      frame.active_seat === player.seat && h("span", { class: "pill good" }, "am Zug"),
      isTargetSeat && h("span", { class: "pill bad" }, "⚔️ Ziel"),
      seatAnswerable && h("button", {
        type: "button",
        class: `seat-pick${entryPicked(seatClick) ? " picked" : ""}`,
        "data-click-key": `seat:${player.seat}`,
        "aria-label": seatAria(player.seat, seatClick),
        onclick: (event) => boardClick({ type: "seat", seat: player.seat }, event.currentTarget)
      }, seatClickText(seatClick)),
      info.style !== undefined && info.pilot !== "Mensch" && h("span", { class: "pill", title: `KI-Stil: ${info.style} (${info.style_name || ""})` }, `Stil ${info.style}`),
      info.deck_plan && h("span", { class: "pill link", title: "Spielplan ansehen (abgeleitet)", onclick: () => showDeckPlan(seatName(player.seat), info.deck_plan) }, "Plan"),
      player.lost && h("span", { class: "pill bad" }, "ausgeschieden"),
      last && winners.includes(player.seat) && h("span", { class: "pill warn" }, "Sieger")),
    h("div", { class: "seat-head" },
      h("span", { class: "stat" }, `Hand ${player.hand_count ?? "?"}`),
      h("span", { class: "stat" }, `Bibliothek ${player.library_count ?? "?"}`),
      yard,
      exileStat,
      player.poison ? h("span", { class: "stat" }, `Gift ${player.poison}`) : null,
      player.mana_pool ? h("span", { class: "stat" }, `Mana ${Object.entries(player.mana_pool).map(([color, amount]) => `${amount} ${color}`).join(", ")}`) : null),
    frame.commanders ? commanderLine(frame.commanders[player.seat] || { commanders: [], received: [] }) : null,
    player.command.length ? h("div", null, h("div", { class: "zone-title" }, "Kommandozone"), h("div", { class: "cards" }, player.command.map((name, at) => cardTile(name, { small: true, objectId: (player.command_ids || [])[at] })))) : null,
    h("div", { class: "zone-title" }, `Spielfeld (${player.battlefield.length})`),
    h("div", { class: "cards" }, others.map((item) => permanentTile(item, frame))),
    lands.length ? h("div", { class: "cards lands" }, lands.map((item) => permanentTile(item, frame))) : null);
}
function seatAria(seat, entry) {
  const options = entry.optionIds.map(offeredOption).filter(Boolean);
  const who = `${seatName(seat)} (${seatLabel(seat)})`;
  if (options.length !== 1) return `${who}: ${options.length} Möglichkeiten, Menü öffnen`;
  const label = localizeActionText(options[0].label || options[0].option_id);
  return state.click.mode === "staged" ? `${who}: ${entryPicked(entry) ? "Auswahl aufheben" : "auswählen"} (${label})` : `${who}: ${label}`;
}
function seatClickText(entry) {
  if (state.click.kind === "attacker") return "⚔️ Angreifen";
  return entryPicked(entry) ? "✓ Ziel" : "🎯 Ziel wählen";
}
function showList(title, names, ids, zoneKey) {
  const box = $("modal-box"); box.textContent = "";
  box.dataset.zone = zoneKey || "";
  box.append(h("h2", null, title), names.length ? h("div", { class: "cards" }, names.map((name, at) => cardTile(name, { objectId: (ids || [])[at] }))) : h("p", { class: "muted" }, "leer"), h("p", null, h("button", { type: "button", onclick: () => { $("modal").hidden = true; } }, "Schließen")));
  $("modal").hidden = false;
}
function showZone(player, zone) {
  const graveyard = zone === "graveyard";
  showList(`${graveyard ? "Friedhof" : "Exil"} von ${seatName(player.seat)}`, graveyard ? player.graveyard : (player.exile || []), player[`${zone}_ids`], `${player.seat}:${zone}`);
}
function showDeckPlan(title, plan) {
  const box = $("modal-box"); box.textContent = ""; box.dataset.zone = "";
  const combos = Array.isArray(plan.combos) ? plan.combos : [];
  const winAxes = Array.isArray(plan.win_axes) ? plan.win_axes : [];
  const tutors = Array.isArray(plan.tutor_priorities) ? plan.tutor_priorities : [];
  const protect = Array.isArray(plan.protection_targets) ? plan.protection_targets : [];
  const details = h("div", { class: "plan-details" },
    h("p", null, h("b", null, "Fokus: "), plan.focus || "–"),
    h("p", null, h("b", null, "Gewinn-Plan: "), plan.win_condition || "–"),
    winAxes.length ? h("p", null, h("b", null, "Gewinn-Achsen: "), winAxes.join(" · ")) : null,
    h("p", null, h("b", null, "Motoren: "), (plan.engines || []).join(", ") || "–"),
    h("p", null, h("b", null, "Antworten: "), (plan.answers || []).join(", ") || "–"),
    plan.key_cards && plan.key_cards.length ? h("p", null, h("b", null, "Schlüsselkarten: "), plan.key_cards.join(", ")) : null,
    tutors.length ? h("p", null, h("b", null, "Tutor-Priorität: "), tutors.slice(0, 8).join(", ")) : null,
    protect.length ? h("p", null, h("b", null, "Schutz-Ziele: "), protect.slice(0, 8).join(", ")) : null
  );
  const children = [
    h("h2", null, `Spielplan (${title})`),
    h("p", { class: "muted" }, `Herkunft: ${plan.provenance || "abgeleitet, nicht gemessen"}`),
    details
  ];
  if (combos.length) {
    children.push(
      h("h3", null, `Combo-Linien (${combos.length})`),
      h("ul", null, combos.slice(0, 12).filter((combo) => combo && typeof combo === "object").map((combo) => {
        const cardsText = Array.isArray(combo.cards) ? combo.cards.join(" + ") : "";
        const resultText = combo.result ? ` → ${combo.result}` : "";
        return h("li", null, `${cardsText}${resultText}`);
      }))
    );
  }
  children.push(h("p", null, h("button", { type: "button", onclick: () => { $("modal").hidden = true; } }, "Schließen")));
  box.append(...children);
  $("modal").hidden = false;
}

// Commander facts of the live decision, exactly as the engine published them in pilot_state.commander_status:
// the commanders a seat owns (with the casts from the command zone, or null when unknown) and the combat
// damage a seat has taken from each commander. Nothing is added up or derived here; the engine publishes
// no commander tax, so the page says so instead of working it out.
function commanderRows(ps) {
  // no list from the engine (missing, wrong type, empty) means unknown: the page then shows no commander line at all
  if (!ps || !Array.isArray(ps.commander_status) || !ps.commander_status.length) return null;
  const status = ps.commander_status;
  const players = ps && Array.isArray(ps.players) ? ps.players : [];
  const seatOf = (playerId) => { const found = players.find((p) => p && p.player_id === playerId); return found && Number.isInteger(found.seat) ? found.seat : null; };
  const bySeat = {};
  const seatRow = (seat) => (bySeat[seat] = bySeat[seat] || { commanders: [], received: [] });
  for (const entry of status) {
    if (!entry || typeof entry !== "object") continue;
    const owner = seatOf(entry.owner_id);
    if (owner === null) continue;
    const casts = Number.isInteger(entry.casts_from_command) ? entry.casts_from_command : null;
    seatRow(owner).commanders.push({ name: typeof entry.name === "string" ? entry.name : "?", casts });
    for (const hit of Array.isArray(entry.commander_damage_to_player) ? entry.commander_damage_to_player : []) {
      const target = hit && seatOf(hit.player_id);
      if (target === null || target === undefined || !Number.isFinite(hit.total)) continue;
      seatRow(target).received.push({ fromSeat: owner, fromName: typeof entry.name === "string" ? entry.name : "?", total: hit.total });
    }
  }
  return bySeat;
}
function commanderLine(info) {
  if (!info) return null;
  const owned = info.commanders.map((c) => h("span", { class: "stat", title: "Die Engine meldet die Casts aus der Kommandozone, aber keine Commander-Steuer: die Seite rechnet sie nicht aus." },
    `${c.name}: ${c.casts === null ? "Casts unbekannt" : `${c.casts}× aus der Kommandozone`} · Steuer unbekannt`));
  const taken = info.received.length
    ? info.received.map((r) => h("span", { class: "stat", title: "Kampfschaden dieses Kommandanten an diesem Spieler, Wert der Engine" }, `${r.total} von ${r.fromName} (${seatName(r.fromSeat)})`))
    : [h("span", { class: "stat", title: "Die Engine meldet keinen Kommandantenschaden an diesem Spieler" }, "keiner")];
  return h("div", { class: "commander-line" }, ...owned, h("span", { class: "muted" }, "Kommandantenschaden erhalten:"), ...taken);
}
function pilotStateToFrame(pending) {
  const ps = (pending && pending.pilot_state) || {};
  const playersRaw = Array.isArray(ps.players) ? ps.players : [];
  const activeId = ps.active_player_id;
  let activeSeat = null;
  const players = playersRaw.map((p) => {
    if (activeId && p.player_id === activeId) activeSeat = p.seat;
    const cardName = (c) => (c && c.face_down ? "(verdeckt)" : (c && c.name) || "?");
    const objectIdOf = (c) => (c && typeof c.object_id === "string" ? c.object_id : null);
    const row = {
      seat: p.seat,
      life: p.life ?? null,
      poison: p.poison_counters || 0,
      hand_count: p.hand_count ?? null,
      library_count: p.library_count ?? null,
      lost: Boolean(p.has_lost),
      won: Boolean(p.has_won),
      battlefield: (p.battlefield || []).map((c) => {
        const rawCounters = c && c.counters;
        let counters = null;
        if (Array.isArray(rawCounters)) {
          const map = {};
          for (const entry of rawCounters) {
            if (entry && entry.type && Number(entry.count) > 0) map[entry.type] = Number(entry.count);
          }
          if (Object.keys(map).length) counters = map;
        } else if (rawCounters && typeof rawCounters === "object" && Object.keys(rawCounters).length) {
          counters = rawCounters;
        }
        const rowCard = {
          object_id: c && typeof c.object_id === "string" ? c.object_id : null,
          name: cardName(c),
          tapped: Boolean(c.tapped),
          power: c.power,
          toughness: c.toughness,
          damage: c.damage
        };
        if (counters) rowCard.counters = counters;
        return rowCard;
      }),
      graveyard: (p.graveyard || []).map(cardName),
      graveyard_ids: (p.graveyard || []).map(objectIdOf),
      command: (p.command || []).map(cardName),
      command_ids: (p.command || []).map(objectIdOf),
      exile_count: p.exile_count || (p.exile || []).length,
      exile: (p.exile || []).map(cardName),
      exile_ids: (p.exile || []).map(objectIdOf)
    };
    if (Array.isArray(p.hand)) { row.hand = p.hand.map(cardName); row.hand_ids = p.hand.map(objectIdOf); }
    if (p.mana_pool && typeof p.mana_pool === "object") row.mana_pool = p.mana_pool;
    return row;
  });
  const stack = (ps.stack || []).map((s) => (s && s.face_down ? "(verdeckt)" : (s && s.name) || "?"));
  const stackIds = (ps.stack || []).map((s) => (s && typeof s.object_id === "string" ? s.object_id : null));
  const commanders = commanderRows(ps);
  return {
    n: state.frames.length + 1,
    commanders,
    turn: ps.turn_number ?? null,
    phase: ps.phase ?? null,
    step: ps.step ?? null,
    active_seat: activeSeat,
    seat: pending.seat,
    decision_class: pending.decision_class,
    prompt: pending.prompt || "",
    options: (pending.legal_options || []).length,
    chosen: [],
    players,
    stack,
    stack_ids: stackIds
  };
}

// opts.autoPassReason marks an automatic pass: its log line is written only after the engine
// accepted the answer (play_p1a.js submitAnswer), a refused pass leaves no line.
// The answer asks for the state from the frames the page holds (start, #1578): the server sends it
// with its acceptance, built like a state request, so no second request follows. The follow loop is
// stopped first, so its held request cannot take those frames in between; it starts again once no
// further answer is on its way.
async function submitHumanChoice(payload, opts) {
  if (!state.gameId || !state.pendingDecision || state.submitting) return;
  if (!state.ff.on) ffStatus("");
  state.submitting = true;
  clearTimeout(state.poll); state.followGen += 1; abortHeldRequest();
  renderHumanDecision();
  let reply = null;
  const sent = Object.assign({}, payload, { start: state.frames.length });
  try {
    await StudioPlayP1a.submitAnswer({
      getPendingDecision: () => state.pendingDecision,
      post: (body) => api(`/api/play/${encodeURIComponent(state.gameId)}/decision`, "POST", body),
      getLedger: () => state.ownCombat,
      setLedger: (ledger) => { state.ownCombat = ledger; },
      logAutoPass: appendAutoPassLog,
      keepReply: (answer) => { reply = answer; }
    }, sent, opts);
    state.selectedOptions = [];
    state.orderList = [];
    await loadMore({ prefetched: reply && reply.state });
    go(Math.max(0, state.frames.length - 1));
  } catch (error) {
    // A click or button that arrives after the decision moved on (or that the engine refuses) is
    // never silent: say what happened, then show the table as the engine has it now.
    const stale = error.status === 422 || error.status === 409;
    toast(stale
      ? `Die Engine hat diese Antwort nicht angenommen (${error.message}). Vermutlich hat sich die Entscheidung inzwischen geändert; der Tisch wird neu geladen, bitte wähle noch einmal.`
      : `Entscheidung abgelehnt: ${error.message}`, 8000);
    endFastForward(`die Engine hat die Antwort nicht angenommen (${error.message})`);
    state.selectedOptions = [];
    if (stale) { try { await loadMore(); } catch (reloadError) { /* the next poll tries again */ } }
  } finally {
    state.submitting = false;
    render();
    // the drawing may already have sent the next answer (fast-forward, auto-pass): that answer
    // starts the follow loop when it is done, a held request now would take its frames
    if (!state.submitting) follow();
  }
}

// ---- fast-forward (Owner decision 2026-11-17) ----------------------------------------------------
// While on, a priority question of the human is answered with the pass option the engine offered and
// nothing else (vorspulen.js decides; every other decision stops it). The AI delay of the session is
// set to 0 and the page polls faster. The slider keeps its value and is restored when it ends.
function ffStatus(text, kind) {
  const box = $("ff-status");
  if (!box) return;
  box.textContent = text || "";
  box.hidden = !text;
  box.className = `ff-status${kind ? ` ${kind}` : ""}`;
}
function selectedFastForwardMode() {
  const sel = $("ff-mode");
  return sel && sel.value ? sel.value : "until_my_turn";
}
function topStackObjectId() {
  const stack = state.pendingDecision && state.pendingDecision.pilot_state && state.pendingDecision.pilot_state.stack;
  if (!Array.isArray(stack) || !stack.length) return null;
  const top = stack[0];
  return top && typeof top.object_id === "string" && top.object_id ? top.object_id : null;
}
function appendAutoPassLog(line) {
  const log = $("log");
  if (!log || !line) return;
  const el = h("div", { class: "line event auto-pass" },
    h("span", { class: `tag s${line.seat}` }, line.tag),
    h("span", null, line.text));
  log.append(el);
  state.lines.push({ index: Math.max(0, state.frames.length - 1), el });
}
// The "stop at opponent spells" checkbox does nothing in the mode "until the stack entry resolved":
// it is disabled there and the page says why (vorspulen.js stackCheckboxState).
function syncFastForwardControls() {
  const box = $("ff-stack");
  const hint = $("ff-stack-hint");
  if (!box) return;
  const info = StudioFastForward.stackCheckboxState(selectedFastForwardMode());
  box.disabled = info.disabled;
  if (hint) { hint.textContent = info.hint; hint.hidden = !info.hint; }
}
function renderFastForwardButton() {
  const button = $("ff-btn");
  if (!button) return;
  const available = state.interactive && state.running;
  $("ff-wrap").hidden = !available;
  button.setAttribute("aria-pressed", state.ff.on ? "true" : "false");
  button.textContent = state.ff.on ? "⏹ Vorspulen beenden" : "⏩ Vorspulen bis zu meiner nächsten Entscheidung";
}
async function setAiDelay(milliseconds) {
  if (!state.interactive || !state.running || !state.gameId) return;
  try { await api(`/api/play/${encodeURIComponent(state.gameId)}/speed`, "POST", { ai_delay_ms: milliseconds }); } catch (error) { toast(`Tempo konnte nicht gesetzt werden: ${error.message}`); }
}
// The session keeps the fast AI delay if the page goes away while fast-forwarding: give the slider
// value back for the game that was open (page close, switching the game).
function restoreAiDelayOnLeave(gameId) {
  if (!state.ff.boosted || !gameId) return;
  try {
    fetch(`/api/play/${encodeURIComponent(gameId)}/speed`, {
      method: "POST",
      keepalive: true,
      headers: { "X-Studio": "1", "Content-Type": "application/json" },
      body: JSON.stringify({ ai_delay_ms: Number($("speed").value) })
    }).catch(() => { /* the page is leaving; the next load sets the slider value again */ });
  } catch (error) { /* same */ }
}
function currentTurn() {
  const pending = state.pendingDecision;
  if (pending && pending.pilot_state && Number.isInteger(pending.pilot_state.turn_number)) return pending.pilot_state.turn_number;
  const last = state.frames[state.frames.length - 1];
  return last && Number.isInteger(last.turn) ? last.turn : null;
}
function startFastForward() {
  if (state.ff.on || !state.interactive || !state.running) return;
  const mode = selectedFastForwardMode();
  const watchStackObjectId = mode === "until_stack_resolves" ? topStackObjectId() : null;
  state.ff = { on: true, boosted: true, mode, startTurn: currentTurn(), stopOnOpponentStack: $("ff-stack").checked, watchStackObjectId };
  ffStatus(`Vorspulen läuft (${StudioFastForward.modeLabel(mode)}): auf Prioritätsabfragen wird nur „Passen“ gesendet. Bei jeder anderen Entscheidung hält es sofort an.`, "run");
  renderFastForwardButton();
  setAiDelay(0);
  if (state.pendingDecision) maybeAutoPassHuman(state.pendingDecision);
  follow();
}
function endFastForward(reason) {
  if (!state.ff.on) return;
  const boosted = state.ff.boosted;
  state.ff = { on: false, boosted: false, mode: selectedFastForwardMode(), startTurn: null, stopOnOpponentStack: $("ff-stack").checked, watchStackObjectId: null };
  state.autoPassAttempt = null; // a pass that was never sent must not block the next try
  if (boosted) setAiDelay(Number($("speed").value));
  ffStatus(`Vorspulen beendet: ${reason}.`, "stop");
  renderFastForwardButton();
  clearTimeout(state.poll);
  follow();
}

function maybeAutoPassHuman(pending) {
  if (!pending || state.submitting || pending.decision_id === state.autoPassAttempt) return false;
  if (state.ff.on) {
    // Fast-forward: the pass option of the engine on a priority question, otherwise it stops.
    const verdict = StudioFastForward.verdict(pending, {
      mode: state.ff.mode,
      startTurn: state.ff.startTurn,
      stopOnOpponentStack: state.ff.stopOnOpponentStack,
      watchStackObjectId: state.ff.watchStackObjectId,
      labelOf: (value) => CLASSES[value] || value
    });
    if (verdict.action !== "pass") { endFastForward(verdict.reason); return false; }
    state.autoPassAttempt = pending.decision_id;
    submitHumanChoice({ decision_id: pending.decision_id, selected_option_ids: [verdict.optionId], ordering: [] },
      { autoPassReason: StudioFastForward.modeLabel(state.ff.mode) });
    return true;
  }
  const autoBox = $("auto-pass-human");
  if (!autoBox || !autoBox.checked) return false;
  if (pending.decision_class !== "priority") return false;
  const options = Array.isArray(pending.legal_options) ? pending.legal_options : [];
  const passOpt = options.find((opt) => opt.option_type === "pass_priority");
  if (!passOpt) return false;
  const ps = pending.pilot_state || {};
  const stack = Array.isArray(ps.stack) ? ps.stack : [];
  const frame = pilotStateToFrame(pending);
  const onlyPass = options.length === 1;
  const safeOpponentEmptyStack = frame.active_seat !== pending.seat && stack.length === 0;
  if (!onlyPass && !safeOpponentEmptyStack) return false;
  state.autoPassAttempt = pending.decision_id;
  submitHumanChoice({
    decision_id: pending.decision_id,
    selected_option_ids: [passOpt.option_id],
    ordering: []
  }, { autoPassReason: "Auto-Pass bis eigene Aktion" });
  return true;
}

function announceDecision(pending) {
  const box = $("sr-announce");
  if (!box) return;
  const count = Array.isArray(pending.legal_options) ? pending.legal_options.length : 0;
  box.textContent = `Neue Entscheidung für ${seatName(pending.seat)}: ${CLASSES[pending.decision_class] || pending.decision_class}. ${pending.prompt || ""} ${count} Möglichkeiten.`;
}
function renderHumanDecision() {
  const panel = $("human-decision");
  const concedebtn = $("concede-btn");
  const autoWrap = $("auto-pass-wrap");
  if (concedebtn) concedebtn.hidden = !(state.interactive && state.running && state.canConcede);
  if (autoWrap) autoWrap.hidden = !(state.interactive && state.running);
  renderFastForwardButton();
  const pending = state.interactive && state.running ? state.pendingDecision : null;
  if (!pending) {
    panel.hidden = true;
    panel.textContent = "";
    panel.dataset.sig = "";
    state.click = null;
    closeBoardMenu(false);
    renderBoardBar(null, null);
    return;
  }
  const isNew = state.pendingDecisionId !== pending.decision_id;
  if (isNew) {
    state.pendingDecisionId = pending.decision_id;
    state.selectedOptions = [];
    state.orderList = (pending.legal_options || []).map((opt) => String(opt.option_id));
    closeBoardMenu(false);
  }
  if (maybeAutoPassHuman(pending)) return;
  if (state.ff.on) {
    panel.hidden = true; panel.textContent = ""; panel.dataset.sig = "";
    state.click = null;
    closeBoardMenu(false);
    renderBoardBar(null, null);
    return;
  }
  if (isNew) announceDecision(pending);
  if (!state.click || state.click.decisionId !== pending.decision_id) state.click = StudioBoardClick.build(pending);
  // The poll renders again every moment: an unchanged decision keeps its panel, so a typed number,
  // an open menu and the keyboard focus survive.
  const panelSig = JSON.stringify([pending.decision_id, state.selectedOptions, state.orderList, state.submitting]);
  if (!panel.hidden && panel.dataset.sig === panelSig) return;
  panel.dataset.sig = panelSig;
  panel.hidden = false;
  panel.textContent = "";
  renderBoardBar(pending, state.click);
  const dc = pending.decision_class || "choice";
  const options = Array.isArray(pending.legal_options) ? pending.legal_options : [];
  const minSel = Number(pending.minimum_selections ?? 0);
  const maxSel = Number(pending.maximum_selections ?? 0);
  const ctx = pending.context || {};
  const numericLegs = Array.isArray(ctx.numeric_legs) ? ctx.numeric_legs : null;
  const hasJointNumeric = Boolean(numericLegs && numericLegs.length);
  const hasScalarNumeric = !hasJointNumeric && (dc === "announce_x" || dc === "amount" || ctx.numeric_min !== undefined || ctx.numeric_max !== undefined);
  const hasNumeric = hasScalarNumeric || hasJointNumeric;
  const isOrder = (dc === "trigger_order" || dc === "order") && !(minSel === 1 && maxSel === 1);
  const isSingleImmediate = !hasNumeric && !isOrder && minSel === 1 && maxSel === 1;
  const title = CLASSES[dc] || dc;
  const headerText = `${seatName(pending.seat)} · ${title}`;
  const groupLabel = `${title}: ${pending.prompt || "Optionen"}`;
  panel.append(h("h3", null, headerText));
  if (pending.prompt) panel.append(h("div", { class: "human-prompt" }, pending.prompt));

  if (isOrder) {
    const byId = new Map(options.map((o) => [String(o.option_id), o]));
    panel.append(h("div", { class: "human-counter" }, "Reihenfolge festlegen (oberster Eintrag zuerst)"));
    const listEl = h("div", { class: "human-options", role: "group", "aria-label": `${title}: Reihenfolge` });
    state.orderList.forEach((optId, idx) => {
      const opt = byId.get(optId) || { label: optId };
      const upBtn = h("button", { type: "button", "aria-label": `Nach oben: ${localizeActionText(opt.label || optId)}`, disabled: idx === 0 || state.submitting, onclick: () => {
        const next = [...state.orderList];
        [next[idx - 1], next[idx]] = [next[idx], next[idx - 1]];
        state.orderList = next;
        renderHumanDecision();
      } }, "↑");
      const downBtn = h("button", { type: "button", "aria-label": `Nach unten: ${localizeActionText(opt.label || optId)}`, disabled: idx === state.orderList.length - 1 || state.submitting, onclick: () => {
        const next = [...state.orderList];
        [next[idx], next[idx + 1]] = [next[idx + 1], next[idx]];
        state.orderList = next;
        renderHumanDecision();
      } }, "↓");
      listEl.append(h("div", { class: "order-row" },
        h("span", { class: "order-label" }, `${idx + 1}. ${localizeActionText(opt.label || optId)}`),
        upBtn, downBtn));
    });
    panel.append(listEl);
    panel.append(h("div", { class: "human-actions" },
      h("button", { type: "button", class: "primary", disabled: state.submitting, onclick: () => submitHumanChoice({
        decision_id: pending.decision_id,
        selected_option_ids: [],
        ordering: [...state.orderList]
      }) }, "Reihenfolge bestätigen")));
    return;
  }

  let numericInput = null;
  const legEntries = [];
  let confirmButton = null;
  let totalStatusEl = null;
  const totalMin = hasJointNumeric ? Number(ctx.numeric_total_min ?? 0) : 0;
  const totalMax = hasJointNumeric ? Number(ctx.numeric_total_max ?? 999) : 0;

  const isJointValid = () => {
    if (!hasJointNumeric) return true;
    let sum = 0;
    for (const entry of legEntries) {
      const val = Number(entry.input.value);
      if (!Number.isInteger(val) || val < entry.min || val > entry.max) return false;
      sum += val;
    }
    return sum >= totalMin && sum <= totalMax;
  };

  if (hasJointNumeric) {
    const legsBox = h("div", { class: "human-options" });
    totalStatusEl = h("div", { class: "human-counter" }, "");
    const updateJointState = () => {
      const sum = legEntries.reduce((acc, item) => acc + (Number(item.input.value) || 0), 0);
      totalStatusEl.textContent = `Summe: ${sum} (erlaubt: ${totalMin}..${totalMax})`;
      if (confirmButton) {
        const chosenCount = state.selectedOptions.length;
        const validSel = chosenCount >= minSel && chosenCount <= maxSel;
        confirmButton.disabled = state.submitting || !validSel || !isJointValid();
      }
    };
    numericLegs.forEach((leg, idx) => {
      const lMin = Number(leg.min ?? 0);
      const lMax = Number(leg.max ?? 99);
      const legLabel = leg.prompt ? localizeActionText(String(leg.prompt)) : `Teil ${idx + 1}`;
      const input = h("input", {
        type: "number",
        min: String(lMin),
        max: String(lMax),
        value: String(lMin),
        "aria-label": `${legLabel} (${lMin}..${lMax})`
      });
      input.addEventListener("input", updateJointState);
      legEntries.push({ input, min: lMin, max: lMax });
      legsBox.append(h("div", { class: "human-numeric" },
        h("label", null, `${legLabel} (${lMin}..${lMax}) `, input)));
    });
    panel.append(totalStatusEl, legsBox);
    updateJointState();
  } else if (hasScalarNumeric) {
    const nMin = ctx.numeric_min !== undefined ? Number(ctx.numeric_min) : 0;
    const nMax = ctx.numeric_max !== undefined ? Number(ctx.numeric_max) : 99;
    numericInput = h("input", { type: "number", min: String(nMin), max: String(nMax), value: String(nMin), "aria-label": "Zahlenwert wählen" });
    panel.append(h("div", { class: "human-numeric" },
      h("label", null, `Wert (${nMin}..${nMax}) `, numericInput)));
  }

  if (isSingleImmediate && dc === "priority") {
    const passOpt = options.find((opt) => opt.option_type === "pass_priority");
    if (passOpt) {
      panel.append(h("div", { class: "human-actions", role: "group", "aria-label": "Priorität abgeben" },
        h("button", { type: "button", class: "primary", disabled: state.submitting, onclick: () => submitHumanChoice({
          decision_id: pending.decision_id,
          selected_option_ids: [passOpt.option_id],
          ordering: []
        }) }, "Priorität abgeben (Pass)")));
    }
    const listEl = h("div", { class: "human-options" });
    const otherOpts = options.filter((opt) => opt.option_type !== "pass_priority");
    const groups = new Map();
    for (const opt of otherOpts) {
      const grp = OPTION_TYPES[opt.option_type] || opt.option_type || "Aktion";
      if (!groups.has(grp)) groups.set(grp, []);
      groups.get(grp).push(opt);
    }
    for (const [grp, members] of groups) {
      listEl.append(h("div", { class: "human-opt-group", role: "group", "aria-label": grp },
        h("div", { class: "human-opt-group-title" }, grp),
        members.map((opt) => h("button", {
          type: "button",
          class: "human-opt",
          disabled: state.submitting,
          onclick: () => submitHumanChoice({ decision_id: pending.decision_id, selected_option_ids: [opt.option_id], ordering: [] })
        }, localizeActionText(opt.label || opt.option_id)))));
    }
    if (otherOpts.length) panel.append(listEl);
    return;
  }

  if (isSingleImmediate) {
    if (dc === "trigger_order") {
      panel.append(h("div", { class: "human-counter" }, "Nächsten Auslöser wählen (wird als Nächstes auf den Stapel gelegt)"));
    }
    const listEl = h("div", { class: "human-options", role: "group", "aria-label": groupLabel });
    for (const opt of options) {
      listEl.append(h("button", {
        type: "button",
        class: "human-opt legal-target",
        disabled: state.submitting,
        onclick: () => submitHumanChoice({ decision_id: pending.decision_id, selected_option_ids: [opt.option_id], ordering: [] })
      }, localizeActionText(opt.label || opt.option_id)));
    }
    panel.append(listEl);
    return;
  }

  const chosenCount = state.selectedOptions.length;
  if (options.length || maxSel > 0) {
    panel.append(h("div", { class: "human-counter" }, `${chosenCount} von ${maxSel} gewählt (mindestens ${minSel})`));
  }
  const listEl = h("div", { class: "human-options", role: "group", "aria-label": groupLabel });
  for (const opt of options) {
    const optId = String(opt.option_id);
    const active = state.selectedOptions.includes(optId);
    listEl.append(h("button", {
      type: "button",
      class: `human-opt legal-target${active ? " selected" : ""}`,
      "aria-pressed": active ? "true" : "false",
      disabled: state.submitting,
      onclick: () => toggleOption(optId)
    }, `${active ? "✓ " : ""}${localizeActionText(opt.label || optId)}`));
  }
  if (options.length) panel.append(listEl);

  const validCount = chosenCount >= minSel && chosenCount <= maxSel && isJointValid();
  const confirmLabel = !hasNumeric && minSel === 0 && chosenCount === 0
    ? (dc === "declare_attacker" ? "Nicht angreifen" : dc === "declare_blocker" ? "Nicht blocken" : "Bestätigen (0 gewählt)")
    : "Auswahl bestätigen";
  confirmButton = h("button", {
    type: "button",
    class: "primary",
    disabled: state.submitting || !validCount,
    onclick: () => {
      const body = { decision_id: pending.decision_id, selected_option_ids: [...state.selectedOptions], ordering: [] };
      if (hasJointNumeric) {
        body.numeric_choices = legEntries.map((entry) => Number(entry.input.value));
      } else if (numericInput) {
        const val = Number(numericInput.value);
        if (dc === "multi_amount") body.numeric_choices = [val];
        else body.numeric_choice = val;
      }
      submitHumanChoice(body);
    }
  }, confirmLabel);
  panel.append(h("div", { class: "human-actions" }, confirmButton));
}

function renderBridgeBanner() {
  const banner = $("bridge-status");
  if (!banner) return;
  const header = state.header;
  if (!header || header.covered_by_sealed_epoch) {
    banner.hidden = true;
    banner.textContent = "";
    return;
  }
  const jarShort = header.bridge_jar_sha256 ? String(header.bridge_jar_sha256).slice(0, 12) : "–";
  banner.textContent = `BRIDGE_AHEAD_OF_QUALIFICATION · Bridge-JAR ${jarShort} · Status ${header.bridge_qualification_state || "unbekannt"} (nicht durch versiegelte Epoche abgedeckt)`;
  banner.hidden = false;
}

function renderOwnCombat(frame, atLiveTail) {
  const box = $("own-combat");
  if (!box) return;
  // the ledger is cleaned up only at the live end; a rewind just hides the box (play_p1a.js)
  const view = StudioPlayP1a.ownCombatView(state.ownCombat, frame, Boolean(atLiveTail), state.interactive);
  state.ownCombat = view.ledger;
  box.textContent = "";
  if (!view.visible) {
    box.hidden = true;
    return;
  }
  box.append(
    h("div", { class: "own-combat-title" }, state.ownCombat.label),
    h("ul", { class: "own-combat-list" }, state.ownCombat.entries.map((entry) => h("li", null, localizeActionText(entry.text))))
  );
  box.hidden = false;
}

function renderStackRail(frame, atLiveTail) {
  const stack = $("stack");
  if (!stack) return;
  stack.textContent = "";
  const pilotState = atLiveTail && state.pendingDecision && state.pendingDecision.pilot_state
    ? state.pendingDecision.pilot_state
    : {
        players: [],
        stack: (frame.stack || []).map((name, at) => ({
          name: name === "(verdeckt)" ? null : name,
          face_down: name === "(verdeckt)",
          object_id: (frame.stack_ids || [])[at] || null
        }))
      };
  const rail = StudioPlayP1a.buildStackRail(pilotState, seatName);
  if (!rail.length) {
    stack.append(h("span", { class: "muted" }, "leer"));
    return;
  }
  for (const item of rail) {
    const body = h("div", { class: "stack-item-body" },
      h("div", { class: "stack-item-head" },
        item.isTop && h("span", { class: "pill warn" }, "oben"),
        h("span", { class: "stack-item-name" }, item.displayName)),
      item.controllerLabel && h("div", { class: "stack-item-meta" }, `Kontrolle: ${item.controllerLabel}`),
      item.targetsPublished && h("div", { class: "stack-item-targets" }, `Ziel: ${item.targets.join(", ")}`)
    );
    const tile = item.isAbility
      ? null
      : cardTile(item.faceDown ? "(verdeckt)" : item.name, { small: true, objectId: item.objectId });
    stack.append(h("div", {
      class: `stack-item${item.isTop ? " top" : ""}`,
      role: "listitem"
    }, tile, body));
  }
}

// Draws the page and notes what it drew (#1578): the follow loop compares StudioFollow.viewKey of
// the state with the note and skips a drawing that would show the same again.
function render() {
  renderView();
  state.renderedKey = StudioFollow.viewKey(viewState());
}
function viewState() {
  return {
    gameId: state.gameId, revision: state.revision, frames: state.frames.length, index: state.index,
    running: state.running, interactive: state.interactive,
    pendingDecisionId: state.pendingDecision ? state.pendingDecision.decision_id : null,
    handsRevealed: state.handsRevealed, canConcede: state.canConcede,
    resultStatus: state.result ? state.result.status || "?" : null,
    fastForward: state.ff.on, autoPassAttempt: state.autoPassAttempt, submitting: state.submitting,
    playing: state.playing
  };
}
function renderView() {
  renderBridgeBanner();
  if (state.ff.on && !state.running) endFastForward("die Partie ist zu Ende");
  renderHumanDecision();
  renderReplayControls();
  const atLiveTail = state.interactive && state.running && state.pendingDecision && state.index >= Math.max(0, state.frames.length - 1);
  const frame = atLiveTail ? pilotStateToFrame(state.pendingDecision) : state.frames[state.index];
  // board clicks exist only on the live decision of the human, never on a recorded frame
  state.clickActive = Boolean(atLiveTail && state.click && state.click.kind !== "none" && state.click.decisionId === state.pendingDecision.decision_id && !state.submitting && !state.ff.on);
  const clickSig = state.clickActive ? JSON.stringify([state.click.decisionId, state.selectedOptions]) : "";
  const table = $("table");
  if (!frame) {
    table.textContent = ""; state.seatKeys = [];
    table.append(h("div", { class: "empty" }, state.running ? "Die Engine startet und mischt die Decks. Gleich geht es los." : `Diese Partie hat keine Entscheidung aufgezeichnet. ${endText()}`));
    if (state.result && state.result.stdout && state.result.status !== "finished") {
      table.append(h("pre", { class: "error-out" }, state.result.stdout));
    }
    $("where").textContent = "";
    return;
  }
  const finished = state.index === state.frames.length - 1 && !state.running;
  const banner = finished ? `banner:${JSON.stringify(state.result)}` : "";
  const humanPendingSeat = state.interactive && state.pendingDecision ? state.pendingDecision.seat : null;
  const keys = frame.players.map((player) => JSON.stringify([player, frame.active_seat, frame.seat, humanPendingSeat, finished, clickSig]));
  if (table.dataset.banner !== banner || keys.length !== state.seatKeys.length) {
    table.textContent = ""; state.seatKeys = []; table.dataset.banner = banner;
    if (finished) {
      table.append(h("div", { class: "banner" }, endText()));
      if (state.result && state.result.stdout && state.result.status !== "finished") {
        table.append(h("pre", { class: "error-out" }, state.result.stdout));
      }
    }
  }
  const offset = finished ? 1 : 0;
  frame.players.forEach((player, position) => {
    if (state.seatKeys[position] === keys[position]) return;
    const panel = seatPanel(player, frame);
    const old = table.children[position + offset];
    if (old) old.replaceWith(panel); else table.append(panel);
  });
  state.seatKeys = keys;

  const now = $("now"); now.textContent = "";
  now.append(
    h("div", { class: "who" }, h("span", { class: `s${frame.seat}` }, seatName(frame.seat)), ` · ${seatLabel(frame.seat)}`),
    h("div", { class: "what" }, atLiveTail ? "Wartet auf deine Entscheidung" : answer(frame)),
    h("div", { class: "ask" }, [CLASSES[frame.decision_class] || frame.decision_class, frame.prompt, frame.source ? `Quelle: ${frame.source}` : null, `${frame.options} Möglichkeiten`].filter(Boolean).join(" · ")),
    h("div", { class: "hint" }, "Der Spielstand zeigt den Tisch zum Zeitpunkt der Frage; das Ergebnis der gewählten Aktion wird im nächsten Schritt sichtbar."));
  renderOwnCombat(frame, atLiveTail);
  renderStackRail(frame, atLiveTail);
  const actor = frame.players.find((player) => player.seat === frame.seat);
  const handOwner = actor && Array.isArray(actor.hand)
    ? actor
    : (state.interactive && state.humanSeats.length
        ? frame.players.find((player) => state.humanSeats.includes(player.seat) && Array.isArray(player.hand)) || actor
        : actor);
  const handSeat = handOwner ? handOwner.seat : frame.seat;
  const revealedNote = state.handsRevealed && !state.humanSeats.includes(handSeat) ? " (nach Spielende aufgedeckt)" : "";
  $("hand-title").textContent = `Hand von ${seatName(handSeat)}${revealedNote}`;
  const hand = $("hand"); hand.textContent = "";
  if (handOwner && handOwner.hand && handOwner.hand.length) handOwner.hand.forEach((name, at) => hand.append(cardTile(name, { small: !state.humanSeats.includes(handSeat), objectId: (handOwner.hand_ids || [])[at] })));
  else hand.append(h("span", { class: "muted" }, handOwner && handOwner.hand ? "leer" : "nicht sichtbar"));

  $("position").value = String(state.index);
  const phase = frame.phase ? (STEPS[frame.step] || PHASES[frame.phase] || frame.phase) : "Spielbeginn";
  const skippedCount = Number((state.result && state.result.forced_decisions_skipped) || 0);
  const skippedSuffix = skippedCount > 0 ? ` (+ ${skippedCount} erzwungene Pässe)` : "";
  const decisionPosText = atLiveTail
    ? `Entscheidung ${frame.n} (Live)`
    : `Entscheidung ${frame.n} von ${state.frames.length}`;
  $("where").textContent = `Zug ${frame.turn ?? "?"} · ${phase} · ${decisionPosText}${skippedSuffix}${state.running ? " (Partie läuft noch)" : ""}`;
  // a graveyard or exile list that is open follows the decision (targets in it are clickable)
  const openKey = $("modal").hidden ? "" : ($("modal-box").dataset.zone || "");
  if (openKey && $("modal-box").dataset.sig !== clickSig) {
    const [openSeat, openName] = openKey.split(":");
    const owner = frame.players.find((player) => player.seat === Number(openSeat));
    if (owner) { showZone(owner, openName); $("modal-box").dataset.sig = clickSig; }
  }
  drawBlockLinks();
  for (const line of document.querySelectorAll("#log .here")) line.classList.remove("here");
  const line = lineFor(state.index);
  if (line) { line.classList.add("here"); line.scrollIntoView({ block: "nearest" }); }
}
function endText() {
  const result = state.result || {};
  if (result.status !== "finished") {
    if (result.game_reached_engine_end === true && result.shutdown_disposition) {
      const base = `Partie zu Ende gespielt, Engine-Prozess endete nicht sauber (${result.shutdown_disposition}), Ergebnis nicht gewertet.`;
      const uncredited = Array.isArray(result.uncredited_winner_seats) ? result.uncredited_winner_seats : [];
      return uncredited.length
        ? `${base} (Engine-Sieger, nicht gewertet: ${uncredited.map((seat) => `${seatName(seat)} (${seatLabel(seat)})`).join(", ")})`
        : base;
    }
    const reason = result.failure_message || result.failure_class || "abgebrochen";
    if (String(reason).includes("DECISION_TIMEOUT")) return "Die Partie wurde beendet: die Engine hat ein Entscheidungslimit gemeldet (DECISION_TIMEOUT). Im Studio gibt es kein Zeitlimit; bitte die Partie neu starten.";
    return `Die Partie wurde nicht zu Ende gespielt (${reason}).`;
  }
  const winners = result.winner_seats || [];
  return winners.length ? `Partie beendet. Sieger: ${winners.map((seat) => `${seatName(seat)} (${seatLabel(seat)})`).join(", ")}` : "Partie beendet ohne Sieger.";
}

// ---- log -----------------------------------------------------------------------------------
function lineFor(index) {
  let found = null;
  for (const entry of state.lines) { if (entry.index > index) break; found = entry.el; }
  return found;
}
function appendLog(from) {
  const log = $("log");
  for (let index = from; index < state.frames.length; index += 1) {
    const frame = state.frames[index];
    const before = index > 0 ? state.frames[index - 1] : null;
    if (frame.turn !== null && (!before || before.turn !== frame.turn) && frame.active_seat !== null) {
      log.append(h("div", { class: "line turn" }, `Zug ${frame.turn}: `, h("span", { class: `s${frame.active_seat}` }, `${seatName(frame.active_seat)} · ${seatLabel(frame.active_seat)}`)));
    }
    if (before) {
      for (const player of frame.players) {
        const old = before.players.find((entry) => entry.seat === player.seat);
        if (!old) continue;
        if (old.life !== player.life && old.life !== null && player.life !== null) log.append(h("div", { class: "line event" }, `${seatName(player.seat)}: Leben ${old.life} auf ${player.life}`));
        if (!old.lost && player.lost) log.append(h("div", { class: "line event" }, `${seatName(player.seat)} scheidet aus`));
      }
    }
    if (isMinor(frame)) continue;
    const el = h("div", { class: "line", onclick: () => { if (!StudioReplay.isReplayAvailable(state)) return; setPlaying(false); go(index); } }, h("span", { class: `tag s${frame.seat}` }, `S${(frame.seat ?? 0) + 1}`), h("span", null, answer(frame)));
    log.append(el);
    state.lines.push({ index, el });
  }
}

// ---- playback (finished games only; replay.js navigates loaded frames without extra requests) --
function isInteractive(target) {
  return Boolean(target && target.closest && target.closest("button, a[href], input, select, textarea, summary, [contenteditable], [role=button]"));
}
function renderReplayControls() {
  const box = $("replay-controls");
  if (!box) return;
  const available = StudioReplay.isReplayAvailable(state);
  box.hidden = !available;
  const turns = available ? StudioReplay.listTurns(state.frames) : [];
  const select = $("turn-jump");
  if (select) {
    const sig = turns.map((entry) => entry.turn).join(",");
    if (select.dataset.turns !== sig) {
      select.dataset.turns = sig;
      select.textContent = "";
      for (const entry of turns) select.append(h("option", { value: String(entry.turn) }, `Zug ${entry.turn}`));
    }
    const frame = available ? state.frames[state.index] : null;
    const turnValue = frame && Number.isInteger(frame.turn) ? String(frame.turn) : "";
    if (turnValue && turns.some((entry) => String(entry.turn) === turnValue)) select.value = turnValue;
    select.disabled = !available || turns.length === 0;
  }
  const atStart = !available || state.index <= 0;
  const atEnd = !available || state.index >= state.frames.length - 1;
  const prevIdx = available ? StudioReplay.prevTurn(state.frames, state.index) : 0;
  $("first").disabled = atStart;
  $("prev-turn").disabled = !available || prevIdx === state.index;
  $("back").disabled = atStart;
  $("play").disabled = !available;
  $("next").disabled = atEnd;
  $("next-turn").disabled = atEnd;
  $("skip").disabled = !available;
  $("position").disabled = !available;
  const note = $("replay-note");
  if (note) note.hidden = !(available && state.interactive);
  if (!available && state.playing) setPlaying(false);
}
function go(index) { state.index = Math.max(0, Math.min(state.frames.length - 1, index)); render(); }
function step(direction) {
  if (!StudioReplay.isReplayAvailable(state)) return;
  const skipMinor = $("skip").checked;
  const nextIndex = direction >= 0
    ? StudioReplay.stepForward(state.frames, state.index, skipMinor)
    : StudioReplay.stepBackward(state.frames, state.index, skipMinor);
  go(nextIndex);
}
function prevTurn() {
  if (!StudioReplay.isReplayAvailable(state)) return;
  go(StudioReplay.prevTurn(state.frames, state.index));
}
function nextTurn() {
  if (!StudioReplay.isReplayAvailable(state)) return;
  go(StudioReplay.nextTurn(state.frames, state.index));
}
function setPlaying(on) {
  const active = Boolean(on) && StudioReplay.isReplayAvailable(state);
  state.playing = active;
  $("play").textContent = active ? "⏸ Anhalten" : "▶ Abspielen";
  clearTimeout(state.timer);
  if (active) tick();
}
function tick() {
  if (!state.playing || !StudioReplay.isReplayAvailable(state)) { setPlaying(false); return; }
  if (state.index >= state.frames.length - 1) {
    // a running AI game keeps playing as frames arrive; a finished one stops at its end
    if (!state.running) { setPlaying(false); return; }
  } else step(1);
  state.timer = setTimeout(tick, Number($("speed").value));
}

// ---- loading -------------------------------------------------------------------------------
async function loadFacts(from) {
  const names = new Set();
  for (const frame of state.frames.slice(from)) {
    for (const player of frame.players) {
      for (const card of player.battlefield) names.add(card.name);
    }
  }
  const missing = [...names].filter((name) => !(name in state.facts));
  if (!missing.length) return;
  try { Object.assign(state.facts, await api("/api/public-cards", "POST", { names: missing.slice(0, 2000) })); } catch (error) { /* without card data the board is shown unsorted */ }
  for (const name of missing) if (!(name in state.facts)) state.facts[name] = null;
}
// One load at a time: loads run one after the other, so two calls never ask for the same frames
// and an older answer can never overwrite a newer pending decision.
let loadTail = Promise.resolve();
// opts.hold: the follow loop asks the server to hold the request until the game changed (#1593).
// Every other load (after an own answer, a concede, a reload) is wanted now, so it ends a held
// request that is still waiting, and a held request that has not started yet is asked plainly.
// opts.prefetched: a state the server already sent (with an own answer); used instead of the first
// request when StudioFollow.usableAnswerState accepts it, otherwise the page asks as before.
function loadMore(opts) {
  const hold = Boolean(opts && opts.hold);
  const prefetched = (opts && opts.prefetched) || null;
  if (!hold) { state.foreground += 1; abortHeldRequest(); }
  const run = loadTail.then(() => loadMoreOnce(hold, prefetched));
  loadTail = run.catch(() => { /* the caller of this load sees the error */ });
  if (!hold) { const done = () => { state.foreground -= 1; }; run.then(done, done); }
  return run;
}
function abortHeldRequest() {
  if (state.pollAbort) { state.pollAbort.abort(); state.pollAbort = null; }
}
function resetFrames() {
  Object.assign(state, { frames: [], lines: [], seatKeys: [] });
  $("log").textContent = ""; $("table").textContent = ""; delete $("table").dataset.banner;
}
async function loadMoreOnce(hold, prefetched) {
  let added = false;
  const gameId = state.gameId;
  let holdThis = Boolean(hold) && state.foreground === 0;
  let ready = prefetched || null;
  for (;;) {
    const requestedStart = state.frames.length;
    let page;
    if (ready && StudioFollow.usableAnswerState(ready, gameId, requestedStart, state.revision)) {
      page = ready;
    } else {
      const endpoint = StudioFollow.statePath(gameId, requestedStart, state.interactive, state.revision, holdThis);
      let controller = null;
      if (holdThis && state.interactive && state.revision !== null) { controller = new AbortController(); state.pollAbort = controller; }
      try {
        page = await api(endpoint, "GET", undefined, controller ? controller.signal : undefined);
      } finally {
        if (controller && state.pollAbort === controller) state.pollAbort = null;
      }
    }
    ready = null; // a state sent with an answer is used once, for the first page only
    holdThis = false; // the pages after the first one are asked for at once
    if (state.gameId !== gameId) return false; // another game was opened meanwhile
    const hasHumans = Boolean(page.interactive || (page.header && Array.isArray(page.header.human_seats) && page.header.human_seats.length));
    if (hasHumans && !state.interactive) {
      state.interactive = true;
      continue;
    }
    if (state.interactive && page.hands_revealed && !state.handsRevealed && state.frames.length) {
      // The game ended while this page watched it: the frames held so far were served without the
      // AI hands. Load them again from the start, once, now that the server reveals them.
      state.handsRevealed = true;
      resetFrames();
      added = true;
      continue;
    }
    if (page.frames.length && page.start !== requestedStart) continue; // stale page: ask again
    state.header = page.header;
    state.cohortRecord = { cohort: page.cohort, played_seats: page.played_seats, table_size: page.table_size };
    renderCohortPill();
    state.result = page.result;
    state.running = page.running;
    state.revision = state.interactive ? StudioFollow.parseRevision(page) : null;
    if (state.interactive) {
      state.humanSeats = Array.isArray(page.human_seats) ? page.human_seats : [];
      adoptPendingDecision(page.pending_decision || null);
      state.canConcede = Boolean(page.can_concede);
      state.handsRevealed = Boolean(page.hands_revealed);
    } else {
      state.humanSeats = [];
      state.pendingDecision = null;
      state.canConcede = false;
      state.handsRevealed = false;
    }
    if (page.frames.length) {
      const from = state.frames.length;
      state.frames.push(...page.frames);
      await loadFacts(from);
      if (state.gameId !== gameId) return false;
      appendLog(from);
      added = true;
    }
    if (state.frames.length >= page.total) break;
  }
  state.index = Math.max(0, Math.min(state.index, state.frames.length - 1));
  $("position").max = String(Math.max(0, state.frames.length - 1));
  return added;
}
async function openGame(gameId) {
  setPlaying(false); clearTimeout(state.poll); abortHeldRequest(); state.followGen += 1;
  restoreAiDelayOnLeave(state.gameId);
  const listed = state.games.find((entry) => entry.game_id === gameId);
  const listedInteractive = Boolean(listed && listed.header && Array.isArray(listed.header.human_seats) && listed.header.human_seats.length);
  Object.assign(state, { gameId, cohortRecord: null, frames: [], lines: [], index: 0, seatKeys: [], header: null, result: null, interactive: listedInteractive, humanSeats: [], pendingDecision: null, pendingDecisionId: null, selectedOptions: [], orderList: [], submitting: false, canConcede: false, handsRevealed: false, autoPassAttempt: null, pollFailures: 0, revision: null, ownCombat: StudioPlayP1a.emptyCombatLedger(), ff: { on: false, boosted: false, mode: selectedFastForwardMode(), startTurn: null, stopOnOpponentStack: $("ff-stack").checked, watchStackObjectId: null } });
  ffStatus(""); showConnectionLost(0, ""); renderCohortPill();
  $("log").textContent = ""; $("table").textContent = ""; delete $("table").dataset.banner;
  await loadMore();
  const header = state.header || {};
  const jarShort = header.bridge_jar_sha256 ? String(header.bridge_jar_sha256).slice(0, 12) : "–";
  const epochLabel = header.covered_by_sealed_epoch ? "versiegelt" : (header.bridge_qualification_state || "unbekannt");
  // The same reading as the pill (the server's cohort), so the two statements never differ.
  const cohort = StudioCohort.cohortOf(state.cohortRecord);
  const modeLabel = cohort === StudioCohort.PLAYED ? "Mensch gegen KI" : cohort === StudioCohort.SIMULATED ? `KI: ${header.pilot || "?"}` : "Herkunft unbekannt";
  $("game-info").textContent = `Seed ${header.seed} · Regeln: XMage ${String(header.engine_commit || "").slice(0, 10)} · Bridge-JAR: ${jarShort} · Epoche: ${epochLabel} · ${modeLabel} · begonnen ${header.started_at || "?"}`;
  $("table").classList.toggle("one", (header.seats || []).length <= 1);
  if (state.interactive && state.frames.length) state.index = state.frames.length - 1;
  render();
  follow();
  // A fast AI delay left behind by an earlier page is replaced by the slider value.
  if (state.interactive && state.running) setAiDelay(Number($("speed").value));
}
const POLL_FAILURES_BEFORE_BANNER = 3;
function showConnectionLost(failures, detail) {
  const banner = $("conn-status");
  if (!banner) return;
  banner.hidden = failures < POLL_FAILURES_BEFORE_BANNER;
  banner.textContent = banner.hidden ? "" : `Verbindung zum Studio unterbrochen (${failures} Abfragen in Folge fehlgeschlagen: ${detail}). Die Seite versucht es weiter; ob die Partie weiterläuft, ist unbekannt.`;
}
// The follow loop (#1593). While a live game of a human runs, the page asks the server to hold each
// state request until the game changed, so a new decision shows up as soon as the engine published
// it, not at the next fixed interval. Without a revision from the server, or after a failed request,
// the fixed intervals of StudioFollow.legacyIntervalMs apply. Frames are always requested from the
// number the page already holds, so a dropped connection loses none.
function follow() {
  clearTimeout(state.poll);
  abortHeldRequest();
  state.followGen += 1;
  if (!state.running) return;
  armFollow(state.followGen, false, false, 0);
}
function armFollow(generation, held, failed, elapsedMs, changed) {
  clearTimeout(state.poll);
  const delay = StudioFollow.nextDelayMs({
    interactive: state.interactive, fastForward: state.ff.on, hasPendingDecision: Boolean(state.pendingDecision),
    revision: state.revision, failed, held, changed: Boolean(changed), elapsedMs
  });
  state.poll = setTimeout(() => followTick(generation), delay);
}
async function followTick(generation) {
  const atEnd = state.index >= state.frames.length - 1;
  const held = state.interactive && state.revision !== null;
  const revisionBefore = state.revision;
  const startedAt = performance.now();
  let added = null;
  let failed = false;
  try {
    added = await loadMore({ hold: held });
  } catch (error) {
    if (error.name === "AbortError") {
      // An own load ended the held request: ask again once it is done (unless a newer loop took over).
      if (generation === state.followGen) armFollow(generation, false, false, 0);
      return;
    }
    if (error.status === 404) {
      // The game is gone (deleted): that is not a lost connection; stop following it.
      state.running = false;
      toast("Die Partie existiert nicht mehr (gelöscht).");
      refreshTitles();
      return;
    }
    // No silent retry: after a few failures in a row the page says the connection is lost.
    failed = true;
    state.pollFailures += 1;
    showConnectionLost(state.pollFailures, error.message);
  }
  if (added !== null) {
    state.pollFailures = 0;
    showConnectionLost(0, "");
    if (added && atEnd && !state.playing) go(Math.max(0, state.frames.length - 1));
    else if (StudioFollow.viewKey(viewState()) !== state.renderedKey) render();
  }
  if (!state.running) { refreshTitles(); return; }
  if (generation !== state.followGen) return; // a newer follow loop took over
  armFollow(generation, held, failed, performance.now() - startedAt, state.revision !== revisionBefore);
}
async function refreshTitles() {
  try { state.games = await api("/api/games"); } catch (error) { return; }
  for (const option of $("game-select").options) {
    const game = state.games.find((entry) => entry.game_id === option.value);
    if (game) option.textContent = gameTitle(game);
  }
}
function gameTitle(game) {
  const seats = (game.header.seats || []).map((seat) => (seat.commanders || []).join(" + ") || seat.deck_id).join(" · ");
  const cohortMark = StudioCohort.mark(game);
  const res = game.result || {};
  const reachedEnd = Boolean(game.game_reached_engine_end || res.game_reached_engine_end);
  const shutdownDisp = game.shutdown_disposition || res.shutdown_disposition || "";
  const finished = res.status === "finished" || game.status === "finished";
  const end = game.running
    ? "läuft"
    : finished
      ? `Sieger ${(res.winner_seats || []).map(seatName).join(", ") || "keiner"}`
      : reachedEnd && shutdownDisp
        ? `nicht gewertet (${shutdownDisp})`
        : "abgebrochen";
  const skipped = Number(res.forced_decisions_skipped || 0);
  const skippedPart = skipped > 0 ? ` (+ ${skipped} erzwungene Pässe)` : "";
  return `${cohortMark ? `[${cohortMark.cohort === StudioCohort.PLAYED ? "Mensch" : cohortMark.text}] ` : ""}${seats} · Seed ${game.header.seed} · ${game.frames} Entscheidungen${skippedPart} · ${end}`;
}
// ---- new game ------------------------------------------------------------------------------
async function newGame(wantedRevision) {
  let table;
  try { table = await api("/api/table"); } catch (error) { toast(`Fehler: ${error.message}`); return; }
  const box = $("modal-box"); box.textContent = ""; box.dataset.zone = "";
  const close = h("button", { type: "button", onclick: () => { $("modal").hidden = true; } }, "Schließen");
  box.append(h("h2", null, "Neue Partie"));
  $("modal").hidden = false;
  if (!table.engine.ready) {
    box.append(h("p", null, "Die Regel-Engine ist auf diesem Rechner noch nicht eingerichtet."), h("p", { class: "muted" }, table.engine.reason), h("p", null, close));
    return;
  }
  const revisions = table.decks.flatMap((deck) => deck.branches.map((branch) => ({ id: branch.revision_id, label: `${deck.name} · ${branch.branch} (${branch.cards} Karten)`, cards: branch.cards })));
  if (!revisions.length) { box.append(h("p", null, "Es gibt noch kein gespeichertes Deck. Speichere zuerst im Deckbau einen Stand."), h("p", null, close)); return; }
  const own = h("select", null, revisions.map((entry) => h("option", { value: entry.id }, entry.label)));
  const preselected = typeof wantedRevision === "string" && revisions.some((entry) => entry.id === wantedRevision);
  if (preselected) own.value = wantedRevision;
  const styleOptions = () => [
    h("option", { value: "0.0" }, "0.0 · Aggressiv"),
    h("option", { value: "0.25" }, "0.25 · Druckvoll"),
    h("option", { value: "0.5", selected: true }, "0.50 · Ausgeglichen"),
    h("option", { value: "0.75" }, "0.75 · Defensiv"),
    h("option", { value: "1.0" }, "1.00 · Kontrollierend")
  ];
  const ownStyle = h("select", { class: "style-pick" }, ...styleOptions());
  const humanPlay = h("input", { type: "checkbox" });
  // Owner decision 2026-11-17: in PLAY nobody has a time limit and no timeout ends the game.
  const timeoutNote = h("p", { class: "muted", hidden: true }, "Kein Zeitlimit: Die Partie wartet unbegrenzt auf deine Entscheidung.");
  const count = h("select", null);
  const sizeNote = h("p", { class: "muted", hidden: true });
  const offeredCounts = () => (humanPlay.checked ? OPPONENT_COUNTS_PLAY : OPPONENT_COUNTS_AI);
  // The sizes of the current lock; a table above it is not offered and the note says why. Six seats
  // are recorded and can be replayed from the frames, but the semantic replay proof (tape) stops at five.
  const fillCounts = () => {
    const counts = offeredCounts();
    const wanted = Number(count.value) || 3;
    count.textContent = "";
    for (const n of counts) count.append(h("option", { value: String(n) }, `${n + 1} Spieler`));
    count.value = String(counts.includes(wanted) ? wanted : counts[counts.length - 1]);
    const lines = [];
    const topOffered = counts[counts.length - 1] + 1; // players at the biggest offered table
    if (topOffered < OPPONENT_COUNTS_MAX + 1) lines.push(`${topOffered + 1 === OPPONENT_COUNTS_MAX + 1 ? "6" : `${topOffered + 1} bis 6`} Spieler sind noch nicht freigegeben (Owner-Entscheid); der Server lehnt sie ab.`);
    if (Number(count.value) === OPPONENT_COUNTS_MAX) lines.push("6 Spieler: Die Partie wird aufgezeichnet und lässt sich nachspielen. Einen Replay-Nachweis (Semantik-Replay) gibt es bisher nur bis 5 Sitze.");
    sizeNote.textContent = lines.join(" ");
    sizeNote.hidden = lines.length === 0;
  };
  const seats = h("div", { class: "seat-picks" });
  const pick = () => Math.floor(Math.random() * table.opponents.length);
  const fill = () => {
    const chosen = [...seats.querySelectorAll(".opp-deck")].map((el) => el.value);
    const chosenStyles = [...seats.querySelectorAll(".opp-style")].map((el) => el.value);
    seats.textContent = "";
    const used = new Set();
    for (let index = 0; index < Number(count.value); index += 1) {
      let value = chosen[index];
      while (!value || used.has(value)) value = table.opponents[pick()].deck_id;
      used.add(value);
      const select = h("select", { class: "opp-deck" }, table.opponents.map((deck) => h("option", { value: deck.deck_id }, `${deck.commanders.join(" + ")} · ${deck.name} ${deck.year}`)));
      select.value = value;
      const sSelect = h("select", { class: "opp-style style-pick" }, ...styleOptions());
      if (chosenStyles[index]) sSelect.value = chosenStyles[index];
      seats.append(h("label", null, `Sitz ${index + 2} (KI) `, select, " Stil ", sSelect));
    }
  };
  count.addEventListener("change", () => { fillCounts(); fill(); }); fillCounts(); fill();
  humanPlay.addEventListener("change", () => {
    ownStyle.disabled = humanPlay.checked;
    timeoutNote.hidden = !humanPlay.checked;
    fillCounts(); fill();
  });
  const applyPod = (preset) => {
    // never more seats than the current list offers (after a rollback of a lock a preset may name more)
    const offered = offeredCounts();
    const ids = preset.slice(0, offered[offered.length - 1]);
    if (!ids.length) return;
    count.value = String(ids.length);
    fillCounts();
    seats.textContent = "";
    ids.forEach((id, index) => {
      const select = h("select", { class: "opp-deck" }, table.opponents.map((deck) => h("option", { value: deck.deck_id }, `${deck.commanders.join(" + ")} · ${deck.name} ${deck.year}`)));
      select.value = id;
      const sSelect = h("select", { class: "opp-style style-pick" }, ...styleOptions());
      seats.append(h("label", null, `Sitz ${index + 2} (KI) `, select, " Stil ", sSelect));
    });
  };
  const podButtons = table.pods ? Object.entries(table.pods).map(([name, ids]) =>
    h("button", { type: "button", onclick: () => applyPod(ids) }, `Pod: ${name}`)) : [];
  const seed = h("input", { type: "number", min: "0", max: "2000000000", value: String(Math.floor(Math.random() * 1000000)) });
  const go = h("button", { type: "button", class: "primary" }, "Partie starten");
  const note = h("p", { class: "muted" });
  go.addEventListener("click", async () => {
    const opponents = [...seats.querySelectorAll(".opp-deck")].map((el) => el.value);
    const oppStyles = [...seats.querySelectorAll(".opp-style")].map((el) => Number(el.value));
    const seatStyles = [Number(ownStyle.value), ...oppStyles];
    if (new Set(opponents).size !== opponents.length) { note.textContent = "Jeder Sitz braucht ein anderes Deck."; return; }
    go.disabled = true; note.textContent = "Die Engine startet. Das dauert etwa 20 Sekunden.";
    try {
      const body = {
        revision_id: own.value,
        opponent_ids: opponents,
        seed: Number(seed.value) || 0,
        style: Number(ownStyle.value),
        seat_styles: seatStyles
      };
      if (humanPlay.checked) {
        body.human_seats = [0];
        body.decision_timeout_seconds = 0; // explicit: unlimited, the bridge default of 120 s must not apply
        body.ai_delay_ms = Number($("speed").value);
      }
      const made = await api("/api/games", "POST", body);
      $("modal").hidden = true;
      await listGames(made.game_id);
      if (!made.interactive) setPlaying(true);
    } catch (error) { note.textContent = `Start nicht möglich: ${error.message}`; go.disabled = false; }
  });
  const qual = table.engine && table.engine.bridge_qualification;
  const qualNotice = qual && qual.status && !qual.covered_by_sealed_epoch
    ? [h("p", { class: "pill warn inline-warn", title: qual.reason || "" }, `${qual.status} · nicht durch versiegelte Epoche abgedeckt`)]
    : [];
  box.append(
    h("p", { class: "muted" }, `XMage entscheidet jede Regel (${table.engine && table.engine.pin ? table.engine.pin.slice(0, 10) : "gepinnt"}). Du kannst Platz 1 selbst spielen oder alle Plätze von der KI führen lassen.`),
    ...(table.engine && table.engine.warning ? [h("p", { class: "pill warn inline-warn" }, table.engine.warning)] : []),
    ...qualNotice,
    h("div", { class: "form" },
      h("label", null, humanPlay, " Sitz 1 selbst spielen (Mensch)"),
      h("label", null, "Dein Deck auf Sitz 1 ", own, " Stil ", ownStyle),
      timeoutNote,
      h("label", null, "Tisch ", count),
      sizeNote,
      seats,
      h("div", { class: "actions" },
        h("button", { type: "button", onclick: () => { seats.textContent = ""; fill(); } }, "Andere Gegner würfeln"),
        ...podButtons),
      h("label", null, "Seed ", seed)),
    ...(typeof wantedRevision === "string" && !preselected ? [h("p", { class: "pill warn" }, "Der gewünschte Stand ist nicht mehr gespeichert. Bitte ein Deck wählen.")] : []),
    note, h("p", null, go, " ", close));
}
async function listGames(wanted) {
  state.games = await api("/api/games");
  const select = $("game-select"); select.textContent = "";
  for (const game of state.games) select.append(h("option", { value: game.game_id }, gameTitle(game)));
  if (!state.games.length) {
    state.gameId = null;
    state.cohortRecord = null;
    renderCohortPill();
    state.interactive = false;
    state.pendingDecision = null;
    state.canConcede = false;
    state.frames = [];
    state.lines = [];
    state.ownCombat = StudioPlayP1a.emptyCombatLedger();
    $("game-info").textContent = "";
    $("now").textContent = "";
    if ($("own-combat")) { $("own-combat").textContent = ""; $("own-combat").hidden = true; }
    $("stack").textContent = "";
    $("hand").textContent = "";
    $("log").textContent = "";
    $("position").value = "0";
    $("position").max = "0";
    $("where").textContent = "";
    renderHumanDecision();
    renderReplayControls();
    return false;
  }
  const first = state.games.some((game) => game.game_id === wanted) ? wanted : state.games[0].game_id;
  select.value = first;
  $("table").classList.remove("one");
  await openGame(first);
  return true;
}
async function start() {
  for (const [delay, label] of SPEEDS) $("speed").append(h("option", { value: String(delay) }, label));
  $("speed").value = String(DEFAULT_AI_DELAY_MS);
  $("speed").title = "Pause vor sichtbaren KI-Schritten (erzwungene Schritte und Prioritäts-Pässe laufen ohne Pause)";
  $("speed").addEventListener("change", async () => {
    // While fast-forwarding the AI delay stays 0; the chosen value is restored when it ends.
    if (state.ff.boosted) return;
    if (state.interactive && state.running && state.gameId) {
      try { await api(`/api/play/${encodeURIComponent(state.gameId)}/speed`, "POST", { ai_delay_ms: Number($("speed").value) }); } catch (error) { /* ignore speed update errors */ }
    }
  });
  window.addEventListener("pagehide", () => restoreAiDelayOnLeave(state.gameId));
  $("ff-btn").addEventListener("click", () => { if (state.ff.on) endFastForward("von dir beendet"); else startFastForward(); });
  $("ff-mode").addEventListener("change", () => {
    syncFastForwardControls();
    // a run in progress takes the target of the new mode from the table as it is now
    if (state.ff.on) state.ff = StudioFastForward.retarget(state.ff, selectedFastForwardMode(), { topStackObjectId: topStackObjectId(), currentTurn: currentTurn() });
  });
  syncFastForwardControls();
  $("ff-stack").addEventListener("change", () => { state.ff.stopOnOpponentStack = $("ff-stack").checked; });
  $("first").addEventListener("click", () => { if (!StudioReplay.isReplayAvailable(state)) return; setPlaying(false); go(0); });
  $("prev-turn").addEventListener("click", () => { if (!StudioReplay.isReplayAvailable(state)) return; setPlaying(false); prevTurn(); });
  $("back").addEventListener("click", () => { if (!StudioReplay.isReplayAvailable(state)) return; setPlaying(false); step(-1); });
  $("next").addEventListener("click", () => { if (!StudioReplay.isReplayAvailable(state)) return; setPlaying(false); step(1); });
  $("next-turn").addEventListener("click", () => { if (!StudioReplay.isReplayAvailable(state)) return; setPlaying(false); nextTurn(); });
  $("turn-jump").addEventListener("change", () => { if (!StudioReplay.isReplayAvailable(state)) return; setPlaying(false); go(StudioReplay.jumpToTurn(state.frames, Number($("turn-jump").value))); });
  $("play").addEventListener("click", () => { if (!StudioReplay.isReplayAvailable(state)) return; setPlaying(!state.playing); });
  $("position").addEventListener("input", () => { if (!StudioReplay.isReplayAvailable(state)) return; setPlaying(false); go(Number($("position").value)); });
  $("game-select").addEventListener("change", () => openGame($("game-select").value));
  $("modal").addEventListener("click", (event) => { if (event.target === $("modal")) $("modal").hidden = true; });
  $("auto-pass-human").addEventListener("change", () => {
    if ($("auto-pass-human").checked && state.interactive && state.pendingDecision) maybeAutoPassHuman(state.pendingDecision);
  });
  $("concede-btn").addEventListener("click", async () => {
    if (!state.gameId || !state.interactive || !state.running) return;
    if (!confirm("Möchtest du diese Partie wirklich aufgeben?")) return;
    try {
      await api(`/api/play/${encodeURIComponent(state.gameId)}/concede`, "POST", {});
      await loadMore();
      render();
      refreshTitles();
    } catch (error) {
      toast(`Aufgeben fehlgeschlagen: ${error.message}`);
    }
  });
  $("delete-game").addEventListener("click", async () => {
    if (!state.gameId) return;
    if (!confirm(`Soll die Partie „${state.gameId}“ wirklich gelöscht werden?`)) return;
    try {
      await api(`/api/games/${encodeURIComponent(state.gameId)}`, "DELETE");
      toast("Partie gelöscht.");
      const any = await listGames();
      if (!any) {
        $("table").classList.add("one");
        $("table").textContent = "";
        $("table").append(h("div", { class: "empty" },
          h("h2", null, "Noch keine Partie aufgezeichnet"),
          h("p", null, "Eine Partie wird von der Regel-Engine XMage gespielt, mit einer KI auf jedem Platz, und dabei mitgeschrieben. Starte eine mit „Neue Partie“.")));
      }
    } catch (error) {
      toast(`Fehler beim Löschen: ${error.message}`);
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.key === "Escape") { if (closeBoardMenu(true)) return; $("modal").hidden = true; return; }
    const target = event.target;
    const field = target && target.closest ? target.closest("input, select, textarea") : null;
    if (field && field.type !== "range") return;
    if (!StudioReplay.isReplayAvailable(state)) return;
    // Space belongs to a focused button, link or field (it activates it); only without such a
    // focus does it toggle the playback.
    if (event.key === " ") { if (isInteractive(target)) return; event.preventDefault(); setPlaying(!state.playing); }
    else if (event.key === "ArrowRight") { event.preventDefault(); setPlaying(false); if (event.shiftKey) nextTurn(); else step(1); }
    else if (event.key === "ArrowLeft") { event.preventDefault(); setPlaying(false); if (event.shiftKey) prevTurn(); else step(-1); }
  });
  $("new-game").addEventListener("click", () => newGame());
  // board menu: arrow keys move inside it, a click elsewhere or a scroll closes it (Esc is above)
  $("board-menu").addEventListener("keydown", (event) => {
    const items = [...$("board-menu").querySelectorAll("button")];
    const at = items.indexOf(document.activeElement);
    if (event.key === "ArrowDown") { event.preventDefault(); items[(at + 1) % items.length].focus(); }
    else if (event.key === "ArrowUp") { event.preventDefault(); items[(at - 1 + items.length) % items.length].focus(); }
    else if (event.key === "Tab") { event.preventDefault(); items[(at + (event.shiftKey ? -1 : 1) + items.length) % items.length].focus(); }
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") event.stopPropagation();
  });
  document.addEventListener("click", (event) => {
    if (!$("board-menu").hidden && !event.target.closest("#board-menu, .clickable, .seat-pick")) closeBoardMenu(false);
  });
  $("table").addEventListener("scroll", () => { closeBoardMenu(false); drawBlockLinks(); }, { passive: true });
  window.addEventListener("resize", () => { closeBoardMenu(false); drawBlockLinks(); });
  let any = false;
  try { any = await listGames(new URLSearchParams(location.search).get("partie")); } catch (error) { toast(`Partien konnten nicht geladen werden: ${error.message}`); return; }
  const query = new URLSearchParams(location.search);
  if (query.get("neu") === "1") {
    history.replaceState(null, "", location.pathname); // a reload must not reopen the dialog
    await newGame(query.get("revision") || "");
  }
  if (!any) {
    $("table").classList.add("one");
    $("table").textContent = "";
    $("table").append(h("div", { class: "empty" },
      h("h2", null, "Noch keine Partie aufgezeichnet"),
      h("p", null, "Eine Partie wird von der Regel-Engine XMage gespielt, mit einer KI auf jedem Platz, und dabei mitgeschrieben. Starte eine mit „Neue Partie“.")));
  }
}
start();
