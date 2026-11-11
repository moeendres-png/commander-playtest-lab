"use strict";
// Spectator view of a recorded game. The page only shows what the rules engine published
// and what the pilots chose; it never works out a rule itself.

const PHASES = { beginning: "Beginn", precombat_main: "Hauptphase 1", combat: "Kampf", postcombat_main: "Hauptphase 2", end: "Ende" };
const STEPS = { untap: "Enttappen", upkeep: "Versorgung", draw: "Ziehen", precombat_main: "Hauptphase 1", beginning_combat: "Kampfbeginn", declare_attackers: "Angreifer", declare_blockers: "Blocker", first_combat_damage: "Erstschlagschaden", combat_damage: "Kampfschaden", end_combat: "Kampfende", postcombat_main: "Hauptphase 2", end_turn: "Endsegment", cleanup: "Aufräumen" };
const CLASSES = { priority: "Aktion", mana_payment: "Mana zahlen", choose_object: "Auswahl", choose_use: "Ja oder Nein", target: "Ziel", declare_attacker: "Angriff", declare_blocker: "Block", mulligan: "Mulligan", choice: "Wahl", trigger_order: "Reihenfolge", announce_x: "Wert für X", multi_amount: "Verteilung", mode: "Modus", pile: "Stapelwahl", target_amount: "Zielmenge", replacement_effect: "Ersatzeffekt", order: "Reihenfolge" };
const SPEEDS = [[2000, "langsam"], [1000, "1 pro Sekunde"], [500, "2 pro Sekunde"], [250, "4 pro Sekunde"], [120, "8 pro Sekunde"], [50, "sehr schnell"]];

const state = { games: [], gameId: null, header: null, result: null, running: false, frames: [], index: 0, playing: false, timer: 0, facts: {}, noImage: new Set(), lines: [], seatKeys: [], poll: 0 };

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
async function api(path, method = "GET", body) {
  const options = { method, headers: { "X-Studio": "1" } };
  if (body !== undefined) { options.headers["Content-Type"] = "application/json"; options.body = JSON.stringify(body); }
  const response = await fetch(path, options);
  if (!response.ok) {
    let detail = response.statusText;
    try { detail = (await response.json()).detail || detail; } catch (error) { /* keep status text */ }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return response.json();
}
let toastTimer = 0;
function toast(text) {
  const box = $("toast"); box.textContent = text; box.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { box.hidden = true; }, 3500);
}

const seatName = (seat) => (seat === null || seat === undefined ? "?" : `Sitz ${seat + 1}`);
function seatInfo(seat) { return ((state.header && state.header.seats) || []).find((entry) => entry.seat === seat) || {}; }
function seatLabel(seat) {
  const info = seatInfo(seat);
  return info.commanders && info.commanders.length ? info.commanders.join(" + ") : (info.deck_id || seatName(seat));
}
const isPass = (frame) => frame.decision_class === "priority" && frame.chosen.length === 1 && frame.chosen[0] === "Pass priority";
const isMinor = (frame) => isPass(frame) || frame.decision_class === "mana_payment";
function isLand(name) { const fact = state.facts[name]; return Boolean(fact && fact.type_line && fact.type_line.split("//")[0].includes("Land")); }
function isCreature(name, card) {
  const fact = state.facts[name];
  if (fact && fact.type_line) return fact.type_line.includes("Creature") || fact.type_line.includes("Vehicle");
  return Boolean(card && (card.power || card.toughness));
}

function localizeActionText(text) {
  if (!text) return "";
  let s = text.replace(/Full Game Seat (\d)/g, "Sitz $1");
  if (s.startsWith("Play ")) s = "Spiele " + s.slice(5);
  else if (s.startsWith("Cast ")) s = "Wirke " + s.slice(5);
  else if (s.startsWith("Activate: ")) s = "Aktiviere: " + s.slice(10);
  else if (s.startsWith("Activate ")) s = "Aktiviere " + s.slice(9);
  else if (s.startsWith("Discard ")) s = "Wirf ab: " + s.slice(8);
  else if (s === "Pass priority") s = "Priorität abgeben";
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

// ---- cards ---------------------------------------------------------------------------------
function cardFace(name) {
  if (state.noImage.has(name) || name === "(verdeckt)") return h("div", { class: "nocard" }, name);
  const img = h("img", { alt: name, loading: "lazy", src: `/img-name?name=${encodeURIComponent(name)}` });
  img.addEventListener("error", () => { state.noImage.add(name); img.replaceWith(h("div", { class: "nocard" }, name)); });
  return img;
}
function hover(el, name) {
  el.addEventListener("mouseenter", (event) => {
    if (state.noImage.has(name)) return;
    const box = $("preview"); box.firstChild.src = `/img-name?name=${encodeURIComponent(name)}`; box.hidden = false; move(event);
  });
  el.addEventListener("mousemove", move);
  el.addEventListener("mouseleave", () => { $("preview").hidden = true; });
}
function move(event) {
  const box = $("preview");
  box.style.left = `${Math.min(event.clientX + 18, window.innerWidth - 280)}px`;
  box.style.top = `${Math.max(8, Math.min(event.clientY - 120, window.innerHeight - 380))}px`;
}
function cardTile(name, options = {}) {
  const classes = [
    "card",
    options.tapped && "tapped",
    options.small && "small",
    options.attacking && "attacking",
    options.blocking && "blocking",
    options.targeted && "targeted"
  ].filter(Boolean).join(" ");
  const el = h("div", { class: classes, title: options.title || name }, cardFace(name));
  if (options.count > 1) el.append(h("span", { class: "badge count" }, `×${options.count}`));
  if (options.pt) el.append(h("span", { class: `badge pt${options.damage ? " hurt" : ""}` }, options.pt));
  if (options.counters) el.append(h("span", { class: "badge counter" }, options.counters));
  if (options.combatBadge) {
    const bClass = `badge combat${options.blocking ? " blocking" : ""}${options.targeted ? " targeted" : ""}`;
    el.append(h("span", { class: bClass, title: options.combatBadge }, options.combatBadge));
  }
  hover(el, name);
  return el;
}
function grouped(cards) {
  // identical permanents (same name, same state) share one tile with a count
  const groups = new Map();
  for (const card of cards) {
    const key = JSON.stringify([card.name, card.tapped, card.power, card.toughness, card.damage, card.counters || null]);
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
    combatBadge
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
      return (
        tgt === `Sitz ${player.seat + 1}` ||
        tgt === `Full Game Seat ${player.seat}` ||
        tgt === `Full Game Seat ${player.seat + 1}` ||
        tgt === `p${player.seat}` ||
        tgt === `Seat ${player.seat}` ||
        tgt === `Seat ${player.seat + 1}`
      );
    })
  );
  const classes = [
    "seat",
    frame.active_seat === player.seat && "active",
    frame.seat === player.seat && "acting",
    isTargetSeat && "attacked",
    player.lost && "out",
    last && winners.includes(player.seat) && "winner"
  ].filter(Boolean).join(" ");
  const lands = grouped(player.battlefield.filter((card) => isLand(card.name)));
  const others = grouped(player.battlefield.filter((card) => !isLand(card.name)));
  const yard = h("span", { class: "stat link", title: "Friedhof ansehen", onclick: () => showList(`Friedhof von ${seatName(player.seat)}`, player.graveyard) }, `Friedhof ${player.graveyard.length}`);
  const exileList = player.exile || [];
  const exileCount = player.exile_count || exileList.length;
  const exileStat = exileCount
    ? h("span", {
        class: "stat link",
        title: "Exil ansehen",
        onclick: () => showList(`Exil von ${seatName(player.seat)}`, exileList)
      }, `Exil ${exileCount}`)
    : null;
  return h("div", { class: classes },
    h("div", { class: "seat-head" },
      h("span", { class: `life${player.life !== null && player.life <= 10 ? " low" : ""}` }, player.life === null ? "?" : player.life),
      h("b", { class: `s${player.seat}` }, seatName(player.seat)),
      h("span", null, seatLabel(player.seat)),
      h("span", { class: "muted" }, info.deck_id || ""),
      frame.active_seat === player.seat && h("span", { class: "pill good" }, "am Zug"),
      isTargetSeat && h("span", { class: "pill bad" }, "⚔️ Ziel"),
      info.style !== undefined && h("span", { class: "pill", title: `KI-Stil: ${info.style} (${info.style_name || ""})` }, `Stil ${info.style}`),
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
    player.command.length ? h("div", null, h("div", { class: "zone-title" }, "Kommandozone"), h("div", { class: "cards" }, player.command.map((name) => cardTile(name, { small: true })))) : null,
    h("div", { class: "zone-title" }, `Spielfeld (${player.battlefield.length})`),
    h("div", { class: "cards" }, others.map((item) => permanentTile(item, frame))),
    lands.length ? h("div", { class: "cards lands" }, lands.map((item) => permanentTile(item, frame))) : null);
}
function showList(title, names) {
  const box = $("modal-box"); box.textContent = "";
  box.append(h("h2", null, title), names.length ? h("div", { class: "cards" }, names.map((name) => cardTile(name))) : h("p", { class: "muted" }, "leer"), h("p", null, h("button", { type: "button", onclick: () => { $("modal").hidden = true; } }, "Schließen")));
  $("modal").hidden = false;
}
function showDeckPlan(title, plan) {
  const box = $("modal-box"); box.textContent = "";
  box.append(
    h("h2", null, `Spielplan (${title})`),
    h("p", { class: "muted" }, `Herkunft: ${plan.provenance || "abgeleitet, nicht gemessen"}`),
    h("div", { class: "plan-details", style: "display:flex; flex-direction:column; gap:0.5rem; margin:1rem 0;" },
      h("p", null, h("b", null, "Fokus: "), plan.focus || "–"),
      h("p", null, h("b", null, "Gewinn-Plan: "), plan.win_condition || "–"),
      h("p", null, h("b", null, "Motoren: "), (plan.engines || []).join(", ") || "–"),
      h("p", null, h("b", null, "Antworten: "), (plan.answers || []).join(", ") || "–"),
      plan.key_cards && plan.key_cards.length ? h("p", null, h("b", null, "Schlüsselkarten: "), plan.key_cards.join(", ")) : null
    ),
    h("p", null, h("button", { type: "button", onclick: () => { $("modal").hidden = true; } }, "Schließen"))
  );
  $("modal").hidden = false;
}

function render() {
  const frame = state.frames[state.index];
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
  const keys = frame.players.map((player) => JSON.stringify([player, frame.active_seat, frame.seat, finished]));
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
    h("div", { class: "what" }, answer(frame)),
    h("div", { class: "ask" }, [CLASSES[frame.decision_class] || frame.decision_class, frame.prompt, frame.source ? `Quelle: ${frame.source}` : null, `${frame.options} Möglichkeiten`].filter(Boolean).join(" · ")),
    h("div", { class: "hint" }, "Der Spielstand zeigt den Tisch zum Zeitpunkt der Frage; das Ergebnis der gewählten Aktion wird im nächsten Schritt sichtbar."));
  const stack = $("stack"); stack.textContent = "";
  if (frame.stack.length) frame.stack.forEach((name) => stack.append(name.startsWith("stack ability") ? h("div", { class: "muted" }, name.replace(/^stack ability \(/, "Fähigkeit: ").replace(/\)$/, "")) : cardTile(name, { small: true })));
  else stack.append(h("span", { class: "muted" }, "leer"));
  const actor = frame.players.find((player) => player.seat === frame.seat);
  $("hand-title").textContent = `Hand von ${seatName(frame.seat)}`;
  const hand = $("hand"); hand.textContent = "";
  if (actor && actor.hand && actor.hand.length) actor.hand.forEach((name) => hand.append(cardTile(name, { small: true })));
  else hand.append(h("span", { class: "muted" }, actor && actor.hand ? "leer" : "nicht sichtbar"));

  $("position").value = String(state.index);
  const phase = frame.phase ? (STEPS[frame.step] || PHASES[frame.phase] || frame.phase) : "Spielbeginn";
  $("where").textContent = `Zug ${frame.turn ?? "?"} · ${phase} · Entscheidung ${frame.n} von ${state.frames.length}${state.running ? " (Partie läuft noch)" : ""}`;
  for (const line of document.querySelectorAll("#log .here")) line.classList.remove("here");
  const line = lineFor(state.index);
  if (line) { line.classList.add("here"); line.scrollIntoView({ block: "nearest" }); }
}
function endText() {
  const result = state.result || {};
  if (result.status !== "finished") {
    const reason = result.failure_message || result.failure_class || "abgebrochen";
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
    const el = h("div", { class: "line", onclick: () => go(index) }, h("span", { class: `tag s${frame.seat}` }, `S${(frame.seat ?? 0) + 1}`), h("span", null, answer(frame)));
    log.append(el);
    state.lines.push({ index, el });
  }
}

// ---- playback ------------------------------------------------------------------------------
function go(index) { state.index = Math.max(0, Math.min(state.frames.length - 1, index)); render(); }
function step(direction) {
  let index = state.index + direction;
  if ($("skip").checked) while (index > 0 && index < state.frames.length - 1 && isMinor(state.frames[index])) index += direction;
  go(index);
}
function nextTurn() {
  const turn = state.frames[state.index] ? state.frames[state.index].turn : null;
  let index = state.index + 1;
  while (index < state.frames.length - 1 && state.frames[index].turn === turn) index += 1;
  go(index);
}
function setPlaying(on) {
  state.playing = on;
  $("play").textContent = on ? "⏸ Anhalten" : "▶ Abspielen";
  clearTimeout(state.timer);
  if (on) tick();
}
function tick() {
  if (!state.playing) return;
  if (state.index >= state.frames.length - 1) { if (!state.running) { setPlaying(false); return; } }
  else step(1);
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
async function loadMore() {
  let added = false;
  for (;;) {
    const page = await api(`/api/games/${encodeURIComponent(state.gameId)}?start=${state.frames.length}&count=1000`);
    state.header = page.header; state.result = page.result; state.running = page.running;
    if (page.frames.length) {
      const from = state.frames.length;
      state.frames.push(...page.frames);
      await loadFacts(from);
      appendLog(from);
      added = true;
    }
    if (state.frames.length >= page.total) break;
  }
  $("position").max = String(Math.max(0, state.frames.length - 1));
  return added;
}
async function openGame(gameId) {
  setPlaying(false); clearTimeout(state.poll);
  Object.assign(state, { gameId, frames: [], lines: [], index: 0, seatKeys: [], header: null, result: null });
  $("log").textContent = ""; $("table").textContent = ""; delete $("table").dataset.banner;
  await loadMore();
  const header = state.header || {};
  $("game-info").textContent = `Seed ${header.seed} · Regeln: XMage ${String(header.engine_commit || "").slice(0, 10)} · KI: ${header.pilot || "?"} · begonnen ${header.started_at || "?"}`;
  $("table").classList.toggle("one", (header.seats || []).length <= 1);
  render();
  follow();
}
function follow() {
  if (!state.running) return;
  state.poll = setTimeout(async () => {
    try { const atEnd = state.index >= state.frames.length - 1; if (await loadMore() && atEnd && !state.playing) go(state.frames.length - 1); else render(); } catch (error) { /* try again */ }
    if (!state.running) refreshTitles();
    follow();
  }, 2000);
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
  const end = game.running ? "läuft" : game.result && game.result.status === "finished" ? `Sieger ${(game.result.winner_seats || []).map(seatName).join(", ") || "keiner"}` : "abgebrochen";
  return `${seats} · Seed ${game.header.seed} · ${game.frames} Entscheidungen · ${end}`;
}
// ---- new game ------------------------------------------------------------------------------
async function newGame() {
  let table;
  try { table = await api("/api/table"); } catch (error) { toast(`Fehler: ${error.message}`); return; }
  const box = $("modal-box"); box.textContent = "";
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
  const styleOptions = () => [
    h("option", { value: "0.0" }, "0.0 · Aggressiv"),
    h("option", { value: "0.25" }, "0.25 · Druckvoll"),
    h("option", { value: "0.5", selected: true }, "0.50 · Ausgeglichen"),
    h("option", { value: "0.75" }, "0.75 · Defensiv"),
    h("option", { value: "1.0" }, "1.00 · Kontrollierend")
  ];
  const ownStyle = h("select", { class: "style-pick" }, ...styleOptions());
  const count = h("select", null, [1, 2, 3, 4, 5].map((n) => h("option", { value: String(n) }, `${n + 1} Spieler`)));
  count.value = "3";
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
  count.addEventListener("change", fill); fill();
  const applyPod = (ids) => {
    count.value = String(ids.length);
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
      const made = await api("/api/games", "POST", {
        revision_id: own.value,
        opponent_ids: opponents,
        seed: Number(seed.value) || 0,
        style: Number(ownStyle.value),
        seat_styles: seatStyles,
      });
      $("modal").hidden = true;
      await listGames(made.game_id);
      setPlaying(true);
    } catch (error) { note.textContent = `Start nicht möglich: ${error.message}`; go.disabled = false; }
  });
  box.append(
    h("p", { class: "muted" }, "Alle Plätze spielt die KI. XMage entscheidet jede Regel. Die Partie wird mitgeschrieben und läuft hier direkt mit."),
    h("div", { class: "form" },
      h("label", null, "Dein Deck auf Sitz 1 (KI) ", own, " Stil ", ownStyle),
      h("label", null, "Tisch ", count),
      seats,
      h("div", { class: "actions" },
        h("button", { type: "button", onclick: () => { seats.textContent = ""; fill(); } }, "Andere Gegner würfeln"),
        ...podButtons),
      h("label", null, "Seed ", seed)),
    note, h("p", null, go, " ", close));
}
async function listGames(wanted) {
  state.games = await api("/api/games");
  const select = $("game-select"); select.textContent = "";
  for (const game of state.games) select.append(h("option", { value: game.game_id }, gameTitle(game)));
  if (!state.games.length) {
    state.gameId = null;
    state.frames = [];
    state.lines = [];
    $("game-info").textContent = "";
    $("now").textContent = "";
    $("stack").textContent = "";
    $("hand").textContent = "";
    $("log").textContent = "";
    $("position").value = "0";
    $("position").max = "0";
    $("where").textContent = "";
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
  $("speed").value = "500";
  $("first").addEventListener("click", () => go(0));
  $("back").addEventListener("click", () => step(-1));
  $("next").addEventListener("click", () => step(1));
  $("next-turn").addEventListener("click", nextTurn);
  $("play").addEventListener("click", () => setPlaying(!state.playing));
  $("position").addEventListener("input", () => go(Number($("position").value)));
  $("game-select").addEventListener("change", () => openGame($("game-select").value));
  $("modal").addEventListener("click", (event) => { if (event.target === $("modal")) $("modal").hidden = true; });
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
    if (["INPUT", "SELECT", "TEXTAREA"].includes(event.target.tagName) && event.target.type !== "range") return;
    if (event.key === " ") { event.preventDefault(); setPlaying(!state.playing); }
    else if (event.key === "ArrowRight") { event.preventDefault(); step(1); }
    else if (event.key === "ArrowLeft") { event.preventDefault(); step(-1); }
    else if (event.key === "Escape") $("modal").hidden = true;
  });
  $("new-game").addEventListener("click", newGame);
  let any = false;
  try { any = await listGames(new URLSearchParams(location.search).get("partie")); } catch (error) { toast(`Partien konnten nicht geladen werden: ${error.message}`); return; }
  if (!any) {
    $("table").classList.add("one");
    $("table").textContent = "";
    $("table").append(h("div", { class: "empty" },
      h("h2", null, "Noch keine Partie aufgezeichnet"),
      h("p", null, "Eine Partie wird von der Regel-Engine XMage gespielt, mit einer KI auf jedem Platz, und dabei mitgeschrieben. Starte eine mit „Neue Partie“.")));
  }
}
start();
