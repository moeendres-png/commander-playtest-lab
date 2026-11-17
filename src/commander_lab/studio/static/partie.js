"use strict";
// Spectator view of a recorded game. The page only shows what the rules engine published
// and what the pilots chose; it never works out a rule itself.

const PHASES = { beginning: "Beginn", precombat_main: "Hauptphase 1", combat: "Kampf", postcombat_main: "Hauptphase 2", end: "Ende" };
const STEPS = { untap: "Enttappen", upkeep: "Versorgung", draw: "Ziehen", precombat_main: "Hauptphase 1", beginning_combat: "Kampfbeginn", declare_attackers: "Angreifer", declare_blockers: "Blocker", first_combat_damage: "Erstschlagschaden", combat_damage: "Kampfschaden", end_combat: "Kampfende", postcombat_main: "Hauptphase 2", end_turn: "Endsegment", cleanup: "Aufräumen" };
const CLASSES = { priority: "Aktion", mana_payment: "Mana zahlen", choose_object: "Auswahl", choose_use: "Ja oder Nein", target: "Ziel", declare_attacker: "Angriff", declare_blocker: "Block", mulligan: "Mulligan", choice: "Wahl", trigger_order: "Reihenfolge", announce_x: "Wert für X", multi_amount: "Verteilung", mode: "Modus", pile: "Stapelwahl", target_amount: "Zielmenge", replacement_effect: "Ersatzeffekt", order: "Reihenfolge" };
const SPEEDS = [[2000, "langsam"], [1000, "1 pro Sekunde"], [500, "2 pro Sekunde"], [250, "4 pro Sekunde"], [120, "8 pro Sekunde"], [50, "sehr schnell"]];

const OPTION_TYPES = { pass_priority: "Passen", play_land: "Land spielen", cast_spell: "Zauber wirken", activated_ability: "Fähigkeit aktivieren", mana_ability: "Mana-Fähigkeit", special_action: "Sonderaktion", target: "Ziel", choose_object: "Objekt wählen", attacker: "Angreifer", blocker: "Blocker", mode: "Modus", choice: "Auswahl", mana_payment: "Mana", trigger_order: "Auslöser", yes: "Ja", no: "Nein" };

const state = { games: [], gameId: null, header: null, result: null, running: false, interactive: false, humanSeats: [], pendingDecision: null, pendingDecisionId: null, selectedOptions: [], orderList: [], submitting: false, canConcede: false, handsRevealed: false, autoPassAttempt: null, pollFailures: 0, ff: { on: false, boosted: false, startTurn: null, stopOnOpponentStack: true }, frames: [], index: 0, playing: false, timer: 0, facts: {}, noImage: new Set(), lines: [], seatKeys: [], poll: 0 };

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

// ---- cards ---------------------------------------------------------------------------------
function cardFace(name) {
  if (state.noImage.has(name) || name === "(verdeckt)") return h("div", { class: "nocard" }, name);
  const img = h("img", { alt: name, loading: "lazy", referrerpolicy: "no-referrer", src: `/img-name?name=${encodeURIComponent(name)}` });
  img.addEventListener("error", () => { state.noImage.add(name); img.replaceWith(h("div", { class: "nocard" }, name)); });
  return img;
}
function hover(el, name) {
  el.addEventListener("mouseenter", (event) => {
    if (state.noImage.has(name)) return;
    const box = $("preview");
    const img = box.firstChild;
    img.referrerPolicy = "no-referrer";
    img.onerror = () => { box.hidden = true; };
    img.src = `/img-name?name=${encodeURIComponent(name)}`;
    box.hidden = false; move(event);
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
  const humanPending = Boolean(state.interactive && state.pendingDecision && state.pendingDecision.seat === player.seat);
  const classes = [
    "seat",
    frame.active_seat === player.seat && "active",
    frame.seat === player.seat && "acting",
    humanPending && "human-turn",
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
      info.pilot === "Mensch" && h("span", { class: "pill good", title: "Von dir gesteuert" }, "Mensch"),
      humanPending && h("span", { class: "pill warn" }, "Du bist am Zug!"),
      frame.active_seat === player.seat && h("span", { class: "pill good" }, "am Zug"),
      isTargetSeat && h("span", { class: "pill bad" }, "⚔️ Ziel"),
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

function pilotStateToFrame(pending) {
  const ps = (pending && pending.pilot_state) || {};
  const playersRaw = Array.isArray(ps.players) ? ps.players : [];
  const activeId = ps.active_player_id;
  let activeSeat = null;
  const players = playersRaw.map((p) => {
    if (activeId && p.player_id === activeId) activeSeat = p.seat;
    const cardName = (c) => (c && c.face_down ? "(verdeckt)" : (c && c.name) || "?");
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
      command: (p.command || []).map(cardName),
      exile_count: p.exile_count || (p.exile || []).length,
      exile: (p.exile || []).map(cardName)
    };
    if (Array.isArray(p.hand)) row.hand = p.hand.map(cardName);
    if (p.mana_pool && typeof p.mana_pool === "object") row.mana_pool = p.mana_pool;
    return row;
  });
  const stack = (ps.stack || []).map((s) => (s && s.face_down ? "(verdeckt)" : (s && s.name) || "?"));
  return {
    n: state.frames.length + 1,
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
    stack
  };
}

async function submitHumanChoice(payload) {
  if (!state.gameId || !state.pendingDecision || state.submitting) return;
  if (!state.ff.on) ffStatus("");
  state.submitting = true;
  renderHumanDecision();
  try {
    await api(`/api/play/${encodeURIComponent(state.gameId)}/decision`, "POST", payload);
    state.selectedOptions = [];
    state.orderList = [];
    await loadMore();
    go(Math.max(0, state.frames.length - 1));
    follow();
  } catch (error) {
    toast(`Entscheidung abgelehnt: ${error.message}`);
    endFastForward(`die Engine hat die Antwort nicht angenommen (${error.message})`);
  } finally {
    state.submitting = false;
    render();
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
function currentTurn() {
  const pending = state.pendingDecision;
  if (pending && pending.pilot_state && Number.isInteger(pending.pilot_state.turn_number)) return pending.pilot_state.turn_number;
  const last = state.frames[state.frames.length - 1];
  return last && Number.isInteger(last.turn) ? last.turn : null;
}
function startFastForward() {
  if (state.ff.on || !state.interactive || !state.running) return;
  state.ff = { on: true, boosted: true, startTurn: currentTurn(), stopOnOpponentStack: $("ff-stack").checked };
  ffStatus("Vorspulen läuft: auf Prioritätsabfragen wird nur „Passen“ gesendet. Es hält an, sobald dein Zug beginnt oder du etwas anderes entscheiden musst.", "run");
  renderFastForwardButton();
  setAiDelay(0);
  if (state.pendingDecision) maybeAutoPassHuman(state.pendingDecision);
  follow();
}
function endFastForward(reason) {
  if (!state.ff.on) return;
  const boosted = state.ff.boosted;
  state.ff = { on: false, boosted: false, startTurn: null, stopOnOpponentStack: $("ff-stack").checked };
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
      startTurn: state.ff.startTurn,
      stopOnOpponentStack: state.ff.stopOnOpponentStack,
      labelOf: (value) => CLASSES[value] || value
    });
    if (verdict.action !== "pass") { endFastForward(verdict.reason); return false; }
    state.autoPassAttempt = pending.decision_id;
    submitHumanChoice({ decision_id: pending.decision_id, selected_option_ids: [verdict.optionId], ordering: [] });
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
  });
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
    return;
  }
  const isNew = state.pendingDecisionId !== pending.decision_id;
  if (isNew) {
    state.pendingDecisionId = pending.decision_id;
    state.selectedOptions = [];
    state.orderList = (pending.legal_options || []).map((opt) => String(opt.option_id));
  }
  if (maybeAutoPassHuman(pending)) return;
  if (state.ff.on) { panel.hidden = true; panel.textContent = ""; return; }
  if (isNew) announceDecision(pending);
  panel.hidden = false;
  panel.textContent = "";
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
      onclick: () => {
        if (active) state.selectedOptions = state.selectedOptions.filter((id) => id !== optId);
        else if (maxSel <= 1) state.selectedOptions = [optId];
        else if (state.selectedOptions.length < maxSel) state.selectedOptions = [...state.selectedOptions, optId];
        else toast(`Höchstens ${maxSel} Auswahlen möglich.`);
        renderHumanDecision();
      }
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

function render() {
  renderBridgeBanner();
  if (state.ff.on && !state.running) endFastForward("die Partie ist zu Ende");
  renderHumanDecision();
  const atLiveTail = state.interactive && state.running && state.pendingDecision && state.index >= Math.max(0, state.frames.length - 1);
  const frame = atLiveTail ? pilotStateToFrame(state.pendingDecision) : state.frames[state.index];
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
  const keys = frame.players.map((player) => JSON.stringify([player, frame.active_seat, frame.seat, humanPendingSeat, finished]));
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
  const stack = $("stack"); stack.textContent = "";
  if (frame.stack.length) frame.stack.forEach((name) => stack.append(name.startsWith("stack ability") ? h("div", { class: "muted" }, name.replace(/^stack ability \(/, "Fähigkeit: ").replace(/\)$/, "")) : cardTile(name, { small: true })));
  else stack.append(h("span", { class: "muted" }, "leer"));
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
  if (handOwner && handOwner.hand && handOwner.hand.length) handOwner.hand.forEach((name) => hand.append(cardTile(name, { small: true })));
  else hand.append(h("span", { class: "muted" }, handOwner && handOwner.hand ? "leer" : "nicht sichtbar"));

  $("position").value = String(state.index);
  const phase = frame.phase ? (STEPS[frame.step] || PHASES[frame.phase] || frame.phase) : "Spielbeginn";
  const skippedCount = Number((state.result && state.result.forced_decisions_skipped) || 0);
  const skippedSuffix = skippedCount > 0 ? ` (+ ${skippedCount} erzwungene Pässe)` : "";
  const decisionPosText = atLiveTail
    ? `Entscheidung ${frame.n} (Live)`
    : `Entscheidung ${frame.n} von ${state.frames.length}`;
  $("where").textContent = `Zug ${frame.turn ?? "?"} · ${phase} · ${decisionPosText}${skippedSuffix}${state.running ? " (Partie läuft noch)" : ""}`;
  for (const line of document.querySelectorAll("#log .here")) line.classList.remove("here");
  const line = lineFor(state.index);
  if (line) { line.classList.add("here"); line.scrollIntoView({ block: "nearest" }); }
}
function endText() {
  const result = state.result || {};
  if (result.status !== "finished") {
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
    const el = h("div", { class: "line", onclick: () => go(index) }, h("span", { class: `tag s${frame.seat}` }, `S${(frame.seat ?? 0) + 1}`), h("span", null, answer(frame)));
    log.append(el);
    state.lines.push({ index, el });
  }
}

// ---- playback ------------------------------------------------------------------------------
function isInteractive(target) {
  return Boolean(target && target.closest && target.closest("button, a[href], input, select, textarea, summary, [contenteditable], [role=button]"));
}
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
    const endpoint = state.interactive
      ? `/api/play/${encodeURIComponent(state.gameId)}?start=${state.frames.length}&count=1000`
      : `/api/games/${encodeURIComponent(state.gameId)}?start=${state.frames.length}&count=1000`;
    const page = await api(endpoint);
    const hasHumans = Boolean(page.interactive || (page.header && Array.isArray(page.header.human_seats) && page.header.human_seats.length));
    if (hasHumans && !state.interactive) {
      state.interactive = true;
      return loadMore();
    }
    state.header = page.header;
    state.result = page.result;
    state.running = page.running;
    if (state.interactive) {
      state.humanSeats = Array.isArray(page.human_seats) ? page.human_seats : [];
      state.pendingDecision = page.pending_decision || null;
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
  const listed = state.games.find((entry) => entry.game_id === gameId);
  const listedInteractive = Boolean(listed && listed.header && Array.isArray(listed.header.human_seats) && listed.header.human_seats.length);
  Object.assign(state, { gameId, frames: [], lines: [], index: 0, seatKeys: [], header: null, result: null, interactive: listedInteractive, humanSeats: [], pendingDecision: null, pendingDecisionId: null, selectedOptions: [], orderList: [], submitting: false, canConcede: false, handsRevealed: false, autoPassAttempt: null, pollFailures: 0, ff: { on: false, boosted: false, startTurn: null, stopOnOpponentStack: $("ff-stack").checked } });
  ffStatus(""); showConnectionLost(0, "");
  $("log").textContent = ""; $("table").textContent = ""; delete $("table").dataset.banner;
  await loadMore();
  const header = state.header || {};
  const jarShort = header.bridge_jar_sha256 ? String(header.bridge_jar_sha256).slice(0, 12) : "–";
  const epochLabel = header.covered_by_sealed_epoch ? "versiegelt" : (header.bridge_qualification_state || "unbekannt");
  const modeLabel = state.interactive ? "Mensch gegen KI" : `KI: ${header.pilot || "?"}`;
  $("game-info").textContent = `Seed ${header.seed} · Regeln: XMage ${String(header.engine_commit || "").slice(0, 10)} · Bridge-JAR: ${jarShort} · Epoche: ${epochLabel} · ${modeLabel} · begonnen ${header.started_at || "?"}`;
  $("table").classList.toggle("one", (header.seats || []).length <= 1);
  if (state.interactive && state.frames.length) state.index = state.frames.length - 1;
  render();
  follow();
}
const POLL_FAILURES_BEFORE_BANNER = 3;
function showConnectionLost(failures, detail) {
  const banner = $("conn-status");
  if (!banner) return;
  banner.hidden = failures < POLL_FAILURES_BEFORE_BANNER;
  banner.textContent = banner.hidden ? "" : `Verbindung zum Studio unterbrochen (${failures} Abfragen in Folge fehlgeschlagen: ${detail}). Die Seite versucht es weiter; ob die Partie weiterläuft, ist unbekannt.`;
}
function follow() {
  clearTimeout(state.poll);
  if (!state.running) return;
  const intervalMs = state.interactive ? (state.ff.on ? 150 : (state.pendingDecision ? 1500 : 400)) : 2000;
  state.poll = setTimeout(async () => {
    const atEnd = state.index >= state.frames.length - 1;
    let added = null;
    try {
      added = await loadMore();
    } catch (error) {
      // No silent retry: after a few failures in a row the page says the connection is lost.
      state.pollFailures += 1;
      showConnectionLost(state.pollFailures, error.message);
    }
    if (added !== null) {
      state.pollFailures = 0;
      showConnectionLost(0, "");
      if (added && atEnd && !state.playing) go(Math.max(0, state.frames.length - 1));
      else render();
    }
    if (!state.running) refreshTitles();
    follow();
  }, intervalMs);
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
  const hasHuman = Array.isArray(game.header.human_seats) && game.header.human_seats.length > 0;
  const end = game.running ? "läuft" : game.result && game.result.status === "finished" ? `Sieger ${(game.result.winner_seats || []).map(seatName).join(", ") || "keiner"}` : "abgebrochen";
  const skipped = Number((game.result && game.result.forced_decisions_skipped) || 0);
  const skippedPart = skipped > 0 ? ` (+ ${skipped} erzwungene Pässe)` : "";
  return `${hasHuman ? "[Mensch] " : ""}${seats} · Seed ${game.header.seed} · ${game.frames} Entscheidungen${skippedPart} · ${end}`;
}
// ---- new game ------------------------------------------------------------------------------
async function newGame(wantedRevision) {
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
  humanPlay.addEventListener("change", () => {
    ownStyle.disabled = humanPlay.checked;
    timeoutNote.hidden = !humanPlay.checked;
  });
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
    state.interactive = false;
    state.pendingDecision = null;
    state.canConcede = false;
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
    renderHumanDecision();
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
  $("speed").addEventListener("change", async () => {
    // While fast-forwarding the AI delay stays 0; the chosen value is restored when it ends.
    if (state.ff.boosted) return;
    if (state.interactive && state.running && state.gameId) {
      try { await api(`/api/play/${encodeURIComponent(state.gameId)}/speed`, "POST", { ai_delay_ms: Number($("speed").value) }); } catch (error) { /* ignore speed update errors */ }
    }
  });
  $("ff-btn").addEventListener("click", () => { if (state.ff.on) endFastForward("von dir beendet"); else startFastForward(); });
  $("ff-stack").addEventListener("change", () => { state.ff.stopOnOpponentStack = $("ff-stack").checked; });
  $("first").addEventListener("click", () => go(0));
  $("back").addEventListener("click", () => step(-1));
  $("next").addEventListener("click", () => step(1));
  $("next-turn").addEventListener("click", nextTurn);
  $("play").addEventListener("click", () => setPlaying(!state.playing));
  $("position").addEventListener("input", () => go(Number($("position").value)));
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
    if (event.key === "Escape") { $("modal").hidden = true; return; }
    const target = event.target;
    const field = target && target.closest ? target.closest("input, select, textarea") : null;
    if (field && field.type !== "range") return;
    // Space belongs to a focused button, link or field (it activates it); only without such a
    // focus does it toggle the playback.
    if (event.key === " ") { if (isInteractive(target)) return; event.preventDefault(); setPlaying(!state.playing); }
    else if (event.key === "ArrowRight") { event.preventDefault(); step(1); }
    else if (event.key === "ArrowLeft") { event.preventDefault(); step(-1); }
  });
  $("new-game").addEventListener("click", () => newGame());
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
